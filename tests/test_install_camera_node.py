"""Hermetic tests for scripts/install_camera_node.py.

Every mutating system operation (`apt-get`, `useradd`, `usermod`,
`systemctl`, `python3 -m venv`) goes through one injectable `CommandRunner`
seam, and every filesystem path is rooted under an isolated `tmp_path` via
`InstallPaths(prefix=...)` -- mirroring `scripts/deploy_windows_dev.py`'s
`WindowsHost` seam. None of these tests touch a real system, require root,
or need network access. See "Installer" in
docs/camera-node-installer-design.md.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(ROOT / "scripts" / "install_camera_node.py")
InstallPaths = _MODULE["InstallPaths"]
InstallerError = _MODULE["InstallerError"]
InstallReport = _MODULE["InstallReport"]
install = _MODULE["install"]
rollback = _MODULE["rollback"]
status = _MODULE["status"]
main = _MODULE["main"]
run_preflight = _MODULE["run_preflight"]
verify_artifact_checksums = _MODULE["verify_artifact_checksums"]
classify_node_upgrade_compatibility = _MODULE["classify_node_upgrade_compatibility"]
node_upgrade_compatibility_label = _MODULE["node_upgrade_compatibility_label"]
MIN_FREE_DISK_BYTES_FOR_UPGRADE = _MODULE["MIN_FREE_DISK_BYTES_FOR_UPGRADE"]
ensure_system_prerequisites = _MODULE["ensure_system_prerequisites"]
ensure_service_account = _MODULE["ensure_service_account"]
ensure_config_file = _MODULE["ensure_config_file"]
render_systemd_unit = _MODULE["render_systemd_unit"]
install_or_update_venv = _MODULE["install_or_update_venv"]
parse_env_file = _MODULE["parse_env_file"]
SERVICE_USER = _MODULE["SERVICE_USER"]
CAMERA_GROUP = _MODULE["CAMERA_GROUP"]
hardware_watchdog_device_present = _MODULE["hardware_watchdog_device_present"]
enable_hardware_watchdog = _MODULE["enable_hardware_watchdog"]
atomic_write_text = _MODULE["atomic_write_text"]
export_node_config = _MODULE["export_node_config"]
import_node_config_if_absent = _MODULE["import_node_config_if_absent"]
CONFIG_BUNDLE_VERSION = _MODULE["CONFIG_BUNDLE_VERSION"]
CONFIG_BUNDLE_KIND = _MODULE["CONFIG_BUNDLE_KIND"]
PORTABLE_NODE_ENV_KEYS = _MODULE["PORTABLE_NODE_ENV_KEYS"]


def _result(returncode: int, *, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class FakeCommandRunner:
    """Records every call; simulates just enough real filesystem effect for
    the mutating commands this installer actually issues so the
    orchestration logic around them (idempotency, rollback bookkeeping,
    restart decisions) can be verified against real resulting state."""

    def __init__(self, *, installed_packages: tuple = (), service_active: bool = False, service_enabled: bool = False) -> None:
        self.calls: list = []
        self._installed_packages = set(installed_packages)
        self._service_active = service_active
        self._service_enabled = service_enabled
        self._user_exists = False
        self._user_groups: set = set()

    def __call__(self, command: list) -> subprocess.CompletedProcess:
        self.calls.append(list(command))
        program = command[0]

        if program == "dpkg" and command[1] == "-s":
            return _result(0 if command[2] in self._installed_packages else 1)
        if program == "apt-get" and command[1] == "update":
            return _result(0)
        if program == "apt-get" and command[1] == "install":
            self._installed_packages.add(command[-1])
            return _result(0)
        if program == "id" and command[1] == "-u":
            return _result(0 if self._user_exists else 1)
        if program == "id" and command[1] == "-nG":
            return _result(0, stdout=" ".join(sorted(self._user_groups)))
        if program == "useradd":
            self._user_exists = True
            self._user_groups.add(SERVICE_USER)
            return _result(0)
        if program == "usermod":
            # ["usermod", "--append", "--groups", <group>, <username>] --
            # the group being added is second-to-last, not last.
            self._user_groups.add(command[-2])
            return _result(0)
        if program == "python3" and command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            (venv_dir / "bin").mkdir(parents=True, exist_ok=True)
            (venv_dir / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
            return _result(0)
        if command[0].endswith("/python") and len(command) > 2 and command[2] in {"pip", "compileall"}:
            return _result(0)
        if command[0].endswith("/python") and command[1:2] == ["-c"]:
            # The staged-venv post-install import smoke check
            # (`import mockingbird_node.app`) -- see "Staged activation" in
            # docs/camera-node-upgrade-compatibility-recovery-v1-report.md.
            # Fakes success by default; a test simulating a bad candidate
            # subclasses this and returns failure for this exact shape.
            return _result(0)
        if program == "systemctl":
            return self._systemctl(command[1:])
        raise AssertionError(f"Unexpected command in test: {command}")

    def _systemctl(self, args: list) -> subprocess.CompletedProcess:
        action = args[0]
        if action == "daemon-reload":
            return _result(0)
        if action == "enable":
            self._service_enabled = True
            return _result(0)
        if action == "is-active":
            return _result(0 if self._service_active else 3)
        if action == "is-enabled":
            return _result(0 if self._service_enabled else 1)
        if action in {"restart", "start"}:
            self._service_active = True
            return _result(0)
        if action == "stop":
            self._service_active = False
            return _result(0)
        raise AssertionError(f"Unexpected systemctl action: {args}")


def _fake_health_payload(*, node_id: str = "fake-node") -> dict:
    return {
        "node_id": node_id,
        "display_name": "Fake Node",
        "api_version": "v1",
        "status": "available",
        "camera_count": 1,
        "available_camera_count": 1,
        "pairing_required": True,
        "boot_id": "fake-boot-id",
        "service_version": "0.1.0",
        "self_test": {"status": "passed"},
    }


def _fake_healthy(_url: str) -> tuple:
    payload = _fake_health_payload()
    return True, f"healthy: node_id={payload['node_id']} pairing_required={payload['pairing_required']}", payload


def _fake_unhealthy(_url: str) -> tuple:
    return False, "connection refused (fake)", {}


class _ScriptedHealthChecker:
    """Returns each of `responses` in order, repeating the last one once
    exhausted -- lets a test control an exact *sequence* of health probes
    (`install()` itself calls the injected `health_checker` up to three
    times in one invocation: a pre-upgrade snapshot, the post-activation
    verification, and -- only on a triggered automatic rollback -- once
    more inside `rollback()`), unlike the fixed `_fake_healthy`/
    `_fake_unhealthy`. Each response is a `(healthy, message, payload)`
    tuple, matching `HealthChecker`'s real contract."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)

    def __call__(self, _url: str) -> tuple:
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_fake_artifact(
    directory: Path, *, build_id: str = "a" * 32, git_commit: str = "c" * 40,
    node_api_version: str = "v1", transport_protocol_version: str = "transport/v1",
) -> Path:
    """A real, checksum-verifiable artifact directory -- `run_preflight`'s
    `verify_artifact_checksums` runs unconditionally as part of `install()`,
    so every test using this helper needs a genuinely matching `SHA256SUMS`,
    not merely a `manifest.json`. Mirrors `build_camera_node_artifact.py`'s
    own real output shape closely enough for the installer's own logic
    (which never inspects wheel *contents*, only `manifest.json`/
    `SHA256SUMS`/the wheel's file name) -- not a substitute for the real
    builder's own dedicated tests in test_camera_node_packaging.py."""

    directory.mkdir(parents=True, exist_ok=True)
    wheel_path = directory / "mockingbird_camera_node-0.1.0-py3-none-any.whl"
    wheel_path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    requirements_path = directory / "requirements.txt"
    requirements_path.write_text("fastapi\npydantic\nuvicorn\n", encoding="utf-8")
    configuration_example_path = directory / "camera-node.env.example"
    configuration_example_path.write_bytes(b"MOCKINGBIRD_NODE_NAME=Pi Camera Node\n")
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(
        json.dumps({
            "artifact": wheel_path.name,
            "provenance": {"git_commit": git_commit, "source_clean": True, "build_id": build_id, "built_at": "2026-08-18T00:00:00+00:00"},
            "protocol": {"node_api_version": node_api_version, "transport_protocol_version": transport_protocol_version},
        }),
        encoding="utf-8",
    )
    checksummed = (wheel_path, requirements_path, configuration_example_path, manifest_path)
    (directory / "SHA256SUMS").write_text(
        "".join(f"{_sha256_hex(path.read_bytes())}  {path.name}\n" for path in checksummed),
        encoding="utf-8",
    )
    return directory


# --- Prerequisites / service account ----------------------------------------

def test_prerequisites_reports_each_optional_package_independently(tmp_path) -> None:
    runner = FakeCommandRunner(installed_packages=("python3-venv",))
    report = ensure_system_prerequisites(runner=runner)
    assert report.required_ok is True
    assert report.packages["python3-venv"] == "already installed"
    assert report.packages["python3-picamera2"] == "installed"
    assert report.packages["python3-opencv"] == "installed"


def test_missing_required_prerequisite_is_reported_but_optional_ones_still_attempted(tmp_path) -> None:
    class _RunnerRefusingVenv(FakeCommandRunner):
        def __call__(self, command):
            if command[:2] == ["apt-get", "install"] and command[-1] == "python3-venv":
                return _result(1, stderr="E: Unable to locate package python3-venv")
            return super().__call__(command)

    report = ensure_system_prerequisites(runner=_RunnerRefusingVenv())
    assert report.required_ok is False
    assert "unavailable" in report.packages["python3-venv"]
    # Optional packages are still individually attempted -- one missing
    # required package must not short-circuit the others.
    assert report.packages["python3-picamera2"] == "installed"


def test_service_account_created_idempotently_with_only_the_video_group(tmp_path) -> None:
    runner = FakeCommandRunner()
    first = ensure_service_account(runner=runner)
    assert first == "created"
    assert CAMERA_GROUP in runner._user_groups

    second = ensure_service_account(runner=runner)
    assert second == "already exists"
    useradd_calls = [call for call in runner.calls if call[0] == "useradd"]
    assert len(useradd_calls) == 1  # never re-created on the second run


# --- Config file preservation -------------------------------------------------

def test_config_file_written_once_and_never_overwritten(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path)
    assert ensure_config_file(paths) is True
    original = paths.env_file.read_text(encoding="utf-8")
    assert "MOCKINGBIRD_NODE_BIND=0.0.0.0" in original
    assert str(paths.state_dir) in original  # explicit, predictable pairing-state path

    # An operator hand-edits it.
    paths.env_file.write_text(original.replace("MOCKINGBIRD_NODE_PORT=8787", "MOCKINGBIRD_NODE_PORT=9000"), encoding="utf-8")

    assert ensure_config_file(paths) is False  # a second run must not touch it
    assert "MOCKINGBIRD_NODE_PORT=9000" in paths.env_file.read_text(encoding="utf-8")


def test_config_file_is_root_only(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path)
    ensure_config_file(paths)
    mode = paths.env_file.stat().st_mode & 0o777
    assert mode == 0o600


def test_parse_env_file_ignores_comments_and_blank_lines(tmp_path) -> None:
    path = tmp_path / "node.env"
    path.write_text("# comment\n\nMOCKINGBIRD_NODE_PORT=9000\nMOCKINGBIRD_NODE_BIND=127.0.0.1\n", encoding="utf-8")
    assert parse_env_file(path) == {"MOCKINGBIRD_NODE_PORT": "9000", "MOCKINGBIRD_NODE_BIND": "127.0.0.1"}


# --- systemd unit ------------------------------------------------------------

def test_rendered_unit_uses_dedicated_user_and_hardening_directives(tmp_path) -> None:
    unit = render_systemd_unit(InstallPaths(prefix=tmp_path))
    assert "User=mockingbird-node" in unit
    assert "Group=mockingbird-node" in unit
    assert "Restart=on-failure" in unit
    assert "StartLimitBurst=5" in unit  # bounded restart storm, never infinite
    assert "ProtectSystem=strict" in unit
    assert "NoNewPrivileges=true" in unit
    assert f"EnvironmentFile={tmp_path}/etc/mockingbird-camera-node/node.env" in unit
    assert f"ExecStart={tmp_path}/opt/mockingbird-camera-node/venv/bin/python -m mockingbird_node" in unit


def test_rendered_unit_enables_the_service_watchdog(tmp_path) -> None:
    """Boot Identity + Autonomous Recovery v1: `Type=notify` + `WatchdogSec=`
    let systemd detect and restart a genuinely *hung* Camera Node process
    (the event loop wedged but never exits) -- something `Restart=on-failure`
    alone (bare process exit) cannot catch. See "Watchdog" in
    docs/camera-node-installer-design.md and `mockingbird_node.watchdog`."""

    unit = render_systemd_unit(InstallPaths(prefix=tmp_path))
    assert "Type=notify" in unit
    assert "NotifyAccess=main" in unit
    assert "WatchdogSec=30" in unit
    # Unchanged: a genuine process crash/exit is still bounded exactly as
    # before -- the watchdog is additive, not a replacement.
    assert "Restart=on-failure" in unit
    assert "RestartSec=5" in unit
    assert "StartLimitIntervalSec=300" in unit


def test_rendered_unit_declares_an_explicit_bounded_log_rate_policy(tmp_path) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1 ("B5
    log retention"): journald's own size-based retention already bounds
    total disk use by OS default (the Node deliberately has no custom log
    file -- see "Logs" in docs/camera-node-installer-design.md); this unit
    now makes the per-unit *rate* bound explicit and disclosed rather than
    an unstated reliance on systemd's own implicit default."""

    unit = render_systemd_unit(InstallPaths(prefix=tmp_path))
    assert "LogRateLimitIntervalSec=30" in unit
    assert "LogRateLimitBurst=1000" in unit


# --- Hardware watchdog (OS-hang recovery; optional, capability-gated) -------


def test_hardware_watchdog_device_absent_by_default(tmp_path) -> None:
    assert hardware_watchdog_device_present(InstallPaths(prefix=tmp_path)) is False


def test_enable_hardware_watchdog_refuses_without_touching_boot_config(tmp_path) -> None:
    """This installer never edits `/boot/firmware/config.txt` itself --
    the one boot-critical file a mistake in could reproduce the exact
    powered-but-never-boots failure this whole milestone exists to
    diagnose. Refuses clearly, writes nothing, when the device is absent."""

    paths = InstallPaths(prefix=tmp_path)
    message = enable_hardware_watchdog(paths)
    assert "not found" in message.lower()
    assert "dtparam=watchdog=on" in message
    assert not paths.systemd_watchdog_dropin_path.exists()


def test_enable_hardware_watchdog_writes_a_drop_in_once_the_device_exists(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path)
    paths.hardware_watchdog_device.parent.mkdir(parents=True, exist_ok=True)
    paths.hardware_watchdog_device.write_bytes(b"")

    assert hardware_watchdog_device_present(paths) is True
    message = enable_hardware_watchdog(paths)
    assert "wrote" in message.lower()
    content = paths.systemd_watchdog_dropin_path.read_text(encoding="utf-8")
    assert "[Manager]" in content
    assert "RuntimeWatchdogSec=" in content

    # Idempotent: re-running with an unchanged drop-in reports no change,
    # matching `install_systemd_unit`'s own "no unnecessary churn" convention.
    second_message = enable_hardware_watchdog(paths)
    assert "already configured" in second_message.lower()
    assert paths.systemd_watchdog_dropin_path.read_text(encoding="utf-8") == content


# --- Venv install/update/idempotency -----------------------------------------

def test_fresh_install_creates_the_venv_and_records_the_manifest(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    paths = InstallPaths(prefix=tmp_path / "root")
    paths.install_root.mkdir(parents=True)
    runner = FakeCommandRunner()

    outcome = install_or_update_venv(artifact_dir, paths, runner=runner)

    assert outcome.changed is True
    assert (paths.venv_dir / "bin" / "python").is_file()
    assert paths.manifest_path.is_file()
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "a" * 32


def test_reinstalling_the_identical_build_is_a_no_op(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    paths = InstallPaths(prefix=tmp_path / "root")
    paths.install_root.mkdir(parents=True)
    runner = FakeCommandRunner()
    install_or_update_venv(artifact_dir, paths, runner=runner)
    venv_calls_before = len([c for c in runner.calls if c[:3] == ["python3", "-m", "venv"]])

    outcome = install_or_update_venv(artifact_dir, paths, runner=runner)

    assert outcome.changed is False
    assert "already installed" in outcome.message
    venv_calls_after = len([c for c in runner.calls if c[:3] == ["python3", "-m", "venv"]])
    assert venv_calls_after == venv_calls_before  # no unnecessary rebuild


def test_updating_to_a_new_build_keeps_exactly_one_previous_version(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    paths.install_root.mkdir(parents=True)
    runner = FakeCommandRunner()

    first_artifact = _write_fake_artifact(tmp_path / "first", build_id="1" * 32)
    install_or_update_venv(first_artifact, paths, runner=runner)
    first_venv_marker = paths.venv_dir / "bin" / "python"
    assert first_venv_marker.is_file()

    second_artifact = _write_fake_artifact(tmp_path / "second", build_id="2" * 32)
    outcome = install_or_update_venv(second_artifact, paths, runner=runner)
    assert outcome.changed is True
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "2" * 32
    assert json.loads(paths.previous_manifest_path.read_text())["provenance"]["build_id"] == "1" * 32
    assert paths.previous_venv_dir.is_dir()

    third_artifact = _write_fake_artifact(tmp_path / "third", build_id="3" * 32)
    install_or_update_venv(third_artifact, paths, runner=runner)
    # Exactly one prior version retained -- the "1" build is gone, replaced by "2".
    assert json.loads(paths.previous_manifest_path.read_text())["provenance"]["build_id"] == "2" * 32


# --- Full install() orchestration --------------------------------------------

def test_install_refuses_without_root(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    with pytest.raises(InstallerError, match="root"):
        install(
            artifact_dir=artifact_dir,
            paths=InstallPaths(prefix=tmp_path / "root"),
            runner=FakeCommandRunner(),
            is_root=lambda: False,
            health_checker=_fake_healthy,
        )


def test_full_install_is_healthy_and_idempotent_on_rerun(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()

    report = install(artifact_dir=artifact_dir, paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy)
    assert report.healthy is True
    assert any("restarted" in step for step in report.steps)
    assert paths.env_file.is_file()
    assert paths.unit_path.is_file()

    restart_calls_before = len([c for c in runner.calls if c == ["systemctl", "restart", "mockingbird-camera-node"]])
    second_report = install(artifact_dir=artifact_dir, paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy)
    assert second_report.healthy is True
    assert any("already running, left untouched" in step for step in second_report.steps)
    restart_calls_after = len([c for c in runner.calls if c == ["systemctl", "restart", "mockingbird-camera-node"]])
    assert restart_calls_after == restart_calls_before  # a true no-op re-run never restarts


def test_install_never_overwrites_existing_operator_config_or_pairing_state(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    paths = InstallPaths(prefix=tmp_path / "root")
    # Simulate an existing hand-edited config and a real prior pairing --
    # exactly the reference device's actual adoption scenario (see
    # "Relationship to the real reference device" in
    # docs/camera-node-installer-design.md).
    paths.config_dir.mkdir(parents=True)
    paths.env_file.write_text("MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=3840\n", encoding="utf-8")
    paths.state_dir.mkdir(parents=True)
    (paths.state_dir / "pairing.json").write_text('{"version": 1, "credential_sha256": "deadbeef"}', encoding="utf-8")

    install(artifact_dir=artifact_dir, paths=paths, runner=FakeCommandRunner(), is_root=lambda: True, health_checker=_fake_healthy)

    assert paths.env_file.read_text(encoding="utf-8") == "MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=3840\n"
    assert json.loads((paths.state_dir / "pairing.json").read_text())["credential_sha256"] == "deadbeef"


def test_install_reports_unhealthy_without_raising(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    report = install(
        artifact_dir=artifact_dir,
        paths=InstallPaths(prefix=tmp_path / "root"),
        runner=FakeCommandRunner(),
        is_root=lambda: True,
        health_checker=_fake_unhealthy,
    )
    assert report.healthy is False
    assert "connection refused" in report.health_message


# --- Rollback -----------------------------------------------------------------

def test_rollback_without_a_previous_version_refuses_clearly(tmp_path) -> None:
    with pytest.raises(InstallerError, match="No previous"):
        rollback(paths=InstallPaths(prefix=tmp_path / "root"), runner=FakeCommandRunner(), is_root=lambda: True, health_checker=_fake_healthy)


def test_rollback_swaps_back_to_the_prior_build_and_back_again(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v1", build_id="1" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v2", build_id="2" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "2" * 32

    report = rollback(paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy)
    assert report.healthy is True
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "1" * 32
    assert json.loads(paths.previous_manifest_path.read_text())["provenance"]["build_id"] == "2" * 32

    # Rolling back again swaps right back -- a real, reversible operation.
    second_report = rollback(paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy)
    assert second_report.healthy is True
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "2" * 32


def test_rollback_never_touches_config_or_state(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v1", build_id="1" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )
    paths.env_file.write_text("MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=3840\n", encoding="utf-8")
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v2", build_id="2" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )
    assert paths.env_file.read_text(encoding="utf-8") == "MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=3840\n"

    rollback(paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy)
    assert paths.env_file.read_text(encoding="utf-8") == "MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=3840\n"


# --- Status ---------------------------------------------------------------

def test_status_on_a_fresh_prefix_reports_not_installed(tmp_path) -> None:
    report = status(paths=InstallPaths(prefix=tmp_path / "root"), runner=FakeCommandRunner(), health_checker=_fake_unhealthy)
    assert any("not installed" in line for line in report.lines)
    assert any("rollback target: none" in line for line in report.lines)
    assert report.healthy is False


def test_status_never_mutates_anything(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "artifact"),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )
    before = json.loads(paths.manifest_path.read_text())
    mutating_calls_before = len(runner.calls)

    status(paths=paths, runner=runner, health_checker=_fake_healthy)

    after = json.loads(paths.manifest_path.read_text())
    assert before == after
    # status only issues read-only systemctl queries (is-active/is-enabled).
    new_calls = runner.calls[mutating_calls_before:]
    assert all(call[1] in {"is-active", "is-enabled"} for call in new_calls if call[0] == "systemctl")


# --- Configuration backup / export / import ----------------------------------
# See docs/camera-node-reprovision-recovery-design.md.

def test_export_config_produces_a_versioned_bundle_with_no_secrets(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    ensure_config_file(paths)
    edited = paths.env_file.read_text(encoding="utf-8").replace(
        "MOCKINGBIRD_NODE_NAME=Pi Camera Node", "MOCKINGBIRD_NODE_NAME=Backyard Feeder Node"
    )
    paths.env_file.write_text(edited, encoding="utf-8")

    bundle = export_node_config(paths)

    assert bundle["bundle_version"] == CONFIG_BUNDLE_VERSION
    assert bundle["bundle_kind"] == CONFIG_BUNDLE_KIND
    assert bundle["node_env"]["MOCKINGBIRD_NODE_NAME"] == "Backyard Feeder Node"
    assert bundle["node_env"]["MOCKINGBIRD_NODE_BIND"] == "0.0.0.0"
    # Install-path detail, deliberately never exported -- see
    # PORTABLE_NODE_ENV_KEYS's docstring.
    assert "MOCKINGBIRD_NODE_PAIRING_STATE_PATH" not in bundle["node_env"]
    # node.env never contains a credential in the first place (see
    # "Secrets" in docs/camera-node-reprovision-recovery-design.md); this is
    # a belt-and-suspenders confirmation, not a redaction step.
    serialized = json.dumps(bundle)
    assert "credential" not in serialized.lower()
    assert "pairing.json" not in serialized


def test_export_config_refuses_when_nothing_is_configured_yet(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    with pytest.raises(InstallerError, match="[Nn]othing to export"):
        export_node_config(paths)


def test_import_config_restores_the_display_name_so_repair_pairing_reattaches(tmp_path) -> None:
    """The whole point of export/import: a same-hardware reinstall that
    restores the same MOCKINGBIRD_NODE_NAME produces the same node_id
    (sha256 of the display name -- see mockingbird_node/app.py), so ordinary
    repair-pairing reattaches without ever needing to confirm a hardware
    replacement."""

    old_paths = InstallPaths(prefix=tmp_path / "old-sd-card")
    ensure_config_file(old_paths)
    old_paths.env_file.write_text(
        old_paths.env_file.read_text(encoding="utf-8").replace(
            "MOCKINGBIRD_NODE_NAME=Pi Camera Node", "MOCKINGBIRD_NODE_NAME=Backyard Feeder Node"
        ),
        encoding="utf-8",
    )
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(bundle_path, json.dumps(export_node_config(old_paths)), mode=0o600)

    # The old SD card is gone; a fresh install starts from nothing.
    new_paths = InstallPaths(prefix=tmp_path / "fresh-sd-card")
    message = import_node_config_if_absent(bundle_path, new_paths)

    assert "Restored" in message
    restored = parse_env_file(new_paths.env_file)
    assert restored["MOCKINGBIRD_NODE_NAME"] == "Backyard Feeder Node"
    # Recomputed for *this* install, never trusted from the old bundle.
    assert restored["MOCKINGBIRD_NODE_PAIRING_STATE_PATH"] == f"{new_paths.state_dir}/pairing.json"


def test_import_config_never_overwrites_an_existing_node_env(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    paths.config_dir.mkdir(parents=True)
    paths.env_file.write_text("MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=3840\n", encoding="utf-8")
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(
        bundle_path,
        json.dumps({
            "bundle_version": CONFIG_BUNDLE_VERSION,
            "bundle_kind": CONFIG_BUNDLE_KIND,
            "node_env": {"MOCKINGBIRD_NODE_NAME": "Someone Else's Node"},
        }),
        mode=0o600,
    )

    message = import_node_config_if_absent(bundle_path, paths)

    assert "already exists" in message
    assert paths.env_file.read_text(encoding="utf-8") == "MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=3840\n"


def test_import_config_rejects_a_newer_bundle_version_honestly(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(
        bundle_path,
        json.dumps({"bundle_version": CONFIG_BUNDLE_VERSION + 1, "bundle_kind": CONFIG_BUNDLE_KIND, "node_env": {}}),
        mode=0o600,
    )

    with pytest.raises(InstallerError, match="newer format"):
        import_node_config_if_absent(bundle_path, paths)
    assert not paths.env_file.exists()


@pytest.mark.parametrize(
    "bundle",
    [
        {"bundle_kind": CONFIG_BUNDLE_KIND, "node_env": {}},  # missing bundle_version
        {"bundle_version": CONFIG_BUNDLE_VERSION, "node_env": {}},  # missing/wrong bundle_kind
        {"bundle_version": CONFIG_BUNDLE_VERSION, "bundle_kind": CONFIG_BUNDLE_KIND},  # missing node_env
        {"bundle_version": CONFIG_BUNDLE_VERSION, "bundle_kind": CONFIG_BUNDLE_KIND, "node_env": "not-a-dict"},
        {"bundle_version": "one", "bundle_kind": CONFIG_BUNDLE_KIND, "node_env": {}},  # wrong type
    ],
)
def test_import_config_rejects_malformed_bundles_without_writing_anything(tmp_path, bundle) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(bundle_path, json.dumps(bundle), mode=0o600)

    with pytest.raises(InstallerError):
        import_node_config_if_absent(bundle_path, paths)
    assert not paths.env_file.exists()


def test_import_config_rejects_a_value_with_an_embedded_newline(tmp_path) -> None:
    """An EnvironmentFile= value containing a raw newline could inject an
    extra, attacker/corruption-controlled line into node.env -- reject the
    whole bundle rather than writing it."""

    paths = InstallPaths(prefix=tmp_path / "root")
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(
        bundle_path,
        json.dumps({
            "bundle_version": CONFIG_BUNDLE_VERSION,
            "bundle_kind": CONFIG_BUNDLE_KIND,
            "node_env": {"MOCKINGBIRD_NODE_NAME": "evil\nMOCKINGBIRD_NODE_BIND=0.0.0.0"},
        }),
        mode=0o600,
    )

    with pytest.raises(InstallerError, match="unsafe"):
        import_node_config_if_absent(bundle_path, paths)
    assert not paths.env_file.exists()


def test_import_config_drops_unrecognized_keys_with_a_notice_not_a_failure(tmp_path, capsys) -> None:
    """Forward-compatible: an older installer importing a newer bundle skips
    what it does not understand instead of refusing the whole restore."""

    paths = InstallPaths(prefix=tmp_path / "root")
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(
        bundle_path,
        json.dumps({
            "bundle_version": CONFIG_BUNDLE_VERSION,
            "bundle_kind": CONFIG_BUNDLE_KIND,
            "node_env": {
                "MOCKINGBIRD_NODE_NAME": "Backyard Feeder Node",
                "MOCKINGBIRD_NODE_SOME_FUTURE_SETTING": "not-yet-invented",
                # A rogue/hand-edited install-path override must never win
                # over this install's own computed path either.
                "MOCKINGBIRD_NODE_PAIRING_STATE_PATH": "/tmp/not-this-installs-path/pairing.json",
            },
        }),
        mode=0o600,
    )

    import_node_config_if_absent(bundle_path, paths)

    restored = parse_env_file(paths.env_file)
    assert restored["MOCKINGBIRD_NODE_NAME"] == "Backyard Feeder Node"
    assert "MOCKINGBIRD_NODE_SOME_FUTURE_SETTING" not in restored
    assert restored["MOCKINGBIRD_NODE_PAIRING_STATE_PATH"] == f"{paths.state_dir}/pairing.json"
    assert "ignoring unrecognized" in capsys.readouterr().err


def test_install_with_import_config_restores_before_the_first_health_check(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    old_paths = InstallPaths(prefix=tmp_path / "old-sd-card")
    ensure_config_file(old_paths)
    old_paths.env_file.write_text(
        old_paths.env_file.read_text(encoding="utf-8").replace(
            "MOCKINGBIRD_NODE_NAME=Pi Camera Node", "MOCKINGBIRD_NODE_NAME=Backyard Feeder Node"
        ),
        encoding="utf-8",
    )
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(bundle_path, json.dumps(export_node_config(old_paths)), mode=0o600)

    new_paths = InstallPaths(prefix=tmp_path / "fresh-sd-card")
    report = install(
        artifact_dir=artifact_dir, paths=new_paths, runner=FakeCommandRunner(),
        is_root=lambda: True, health_checker=_fake_healthy, import_config_path=bundle_path,
    )

    assert any("restored node.env from" in step for step in report.steps)
    assert parse_env_file(new_paths.env_file)["MOCKINGBIRD_NODE_NAME"] == "Backyard Feeder Node"


def test_install_with_malformed_import_config_refuses_before_touching_anything(tmp_path) -> None:
    """Interrupted/invalid replacement leaves recoverable state: a bad
    backup must fail before prerequisites, the service account, or the venv
    are touched -- not partway through."""

    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    paths = InstallPaths(prefix=tmp_path / "root")
    bundle_path = tmp_path / "backup.json"
    atomic_write_text(bundle_path, json.dumps({"bundle_version": "not-a-version"}), mode=0o600)
    runner = FakeCommandRunner()

    with pytest.raises(InstallerError):
        install(
            artifact_dir=artifact_dir, paths=paths, runner=runner,
            is_root=lambda: True, health_checker=_fake_healthy, import_config_path=bundle_path,
        )
    assert runner.calls == []  # refused before issuing a single system command
    assert not paths.env_file.exists()


def test_atomic_write_never_leaves_a_partial_file_on_a_mid_write_failure(tmp_path, monkeypatch) -> None:
    target = tmp_path / "node.env"
    target.write_text("MOCKINGBIRD_NODE_NAME=Original\n", encoding="utf-8")

    real_replace = os.replace

    def _failing_replace(*args, **kwargs):
        raise OSError("simulated power loss before rename completed")

    monkeypatch.setattr(os, "replace", _failing_replace)
    with pytest.raises(OSError, match="simulated power loss"):
        atomic_write_text(target, "MOCKINGBIRD_NODE_NAME=Corrupted\n", mode=0o600)
    monkeypatch.setattr(os, "replace", real_replace)

    # The original file is untouched, and no stray temp file survives.
    assert target.read_text(encoding="utf-8") == "MOCKINGBIRD_NODE_NAME=Original\n"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_atomic_write_round_trips_content_and_permissions(tmp_path) -> None:
    target = tmp_path / "nested" / "node.env"
    atomic_write_text(target, "MOCKINGBIRD_NODE_NAME=Roundtrip\n", mode=0o600)

    assert target.read_text(encoding="utf-8") == "MOCKINGBIRD_NODE_NAME=Roundtrip\n"
    assert (target.stat().st_mode & 0o777) == 0o600
    assert list(target.parent.glob(".*.tmp")) == []


# --- Camera Node Upgrade & Compatibility Recovery v1 -------------------------
# See docs/camera-node-upgrade-compatibility-recovery-v1-report.md.

# --- Artifact integrity (checksums) ------------------------------------------

def test_verify_artifact_checksums_passes_on_a_real_fake_artifact(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    verify_artifact_checksums(artifact_dir)  # must not raise


def test_verify_artifact_checksums_rejects_a_tampered_file(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    (artifact_dir / "mockingbird_camera_node-0.1.0-py3-none-any.whl").write_bytes(b"tampered contents")

    with pytest.raises(InstallerError, match="[Cc]hecksum mismatch"):
        verify_artifact_checksums(artifact_dir)


def test_verify_artifact_checksums_refuses_a_missing_sha256sums(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    (artifact_dir / "SHA256SUMS").unlink()

    with pytest.raises(InstallerError, match="SHA256SUMS"):
        verify_artifact_checksums(artifact_dir)


def test_verify_artifact_checksums_refuses_a_file_sha256sums_lists_but_is_missing(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    (artifact_dir / "requirements.txt").unlink()

    with pytest.raises(InstallerError, match="missing from"):
        verify_artifact_checksums(artifact_dir)


def test_install_refuses_a_tampered_artifact_before_touching_anything(tmp_path) -> None:
    """Fail-before-mutation for the single most safety-critical preflight
    check: a corrupted/tampered candidate must never reach the service
    account, the venv, or anything else -- see "Security / supply chain" in
    the governing report."""

    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    (artifact_dir / "mockingbird_camera_node-0.1.0-py3-none-any.whl").write_bytes(b"tampered contents")
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()

    with pytest.raises(InstallerError, match="Preflight failed"):
        install(artifact_dir=artifact_dir, paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy)

    assert runner.calls == []  # refused before issuing a single system command
    assert not paths.env_file.exists()
    assert not paths.venv_dir.exists()


# --- Preflight ----------------------------------------------------------------

def test_preflight_never_mutates_anything(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    paths = InstallPaths(prefix=tmp_path / "root")

    report = run_preflight(artifact_dir=artifact_dir, paths=paths)

    assert report.blocking is False
    assert not paths.install_root.exists()
    assert not paths.env_file.exists()


def test_preflight_reports_would_be_no_op_for_the_currently_installed_build(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    artifact_dir = _write_fake_artifact(tmp_path / "artifact", build_id="1" * 32)
    install_or_update_venv(artifact_dir, paths, runner=runner)

    report = run_preflight(artifact_dir=artifact_dir, paths=paths)

    assert report.would_be_no_op is True
    assert report.candidate_build_id == "1" * 32
    assert report.installed_build_id == "1" * 32
    assert report.blocking is False


def test_preflight_blocks_on_a_malformed_artifact_directory(tmp_path) -> None:
    empty_dir = tmp_path / "not-an-artifact"
    empty_dir.mkdir()

    report = run_preflight(artifact_dir=empty_dir, paths=InstallPaths(prefix=tmp_path / "root"))

    assert report.blocking is True
    assert any(not check.passed and check.name == "candidate_manifest" for check in report.checks)


def test_preflight_blocks_when_disk_space_is_insufficient(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact", build_id="2" * 32)
    paths = InstallPaths(prefix=tmp_path / "root")
    # Something is already installed (a different build), so this is a real
    # candidate upgrade, not a would-be no-op the disk check would skip.
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())

    def _tiny_free_space(_path):
        return type("_Usage", (), {"free": 1_000})()

    report = run_preflight(artifact_dir=artifact_dir, paths=paths, disk_usage=_tiny_free_space)

    assert report.blocking is True
    disk_check = next(check for check in report.checks if check.name == "disk_space")
    assert disk_check.passed is False
    assert "1,000 bytes free" in disk_check.detail


def test_preflight_disk_space_check_is_skipped_for_an_already_up_to_date_build(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    artifact_dir = _write_fake_artifact(tmp_path / "artifact", build_id="1" * 32)
    install_or_update_venv(artifact_dir, paths, runner=FakeCommandRunner())

    def _no_free_space(_path):
        return type("_Usage", (), {"free": 0})()

    report = run_preflight(artifact_dir=artifact_dir, paths=paths, disk_usage=_no_free_space)

    assert report.blocking is False
    disk_check = next(check for check in report.checks if check.name == "disk_space")
    assert disk_check.passed is True


# --- Wire-protocol compatibility ---------------------------------------------

def test_classify_node_upgrade_compatibility_current_when_protocol_matches() -> None:
    protocol = {"node_api_version": "v1", "transport_protocol_version": "transport/v1"}
    assert classify_node_upgrade_compatibility(protocol, dict(protocol)) == "current"


def test_classify_node_upgrade_compatibility_incompatible_when_protocol_differs() -> None:
    installed = {"node_api_version": "v1", "transport_protocol_version": "transport/v1"}
    candidate = {"node_api_version": "v2", "transport_protocol_version": "transport/v1"}
    assert classify_node_upgrade_compatibility(candidate, installed) == "incompatible"


@pytest.mark.parametrize("candidate,installed", [(None, {"node_api_version": "v1"}), ({"node_api_version": "v1"}, None), (None, None), ({}, {"node_api_version": "v1"})])
def test_classify_node_upgrade_compatibility_unknown_when_either_side_is_unavailable(candidate, installed) -> None:
    assert classify_node_upgrade_compatibility(candidate, installed) == "unknown"


def test_node_upgrade_compatibility_label_covers_every_value() -> None:
    for compatibility in ("current", "compatible_older", "incompatible", "unknown"):
        assert node_upgrade_compatibility_label(compatibility)  # never raises, never empty


def test_preflight_reports_current_wire_protocol_compatibility_for_a_matching_candidate(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())
    candidate = _write_fake_artifact(tmp_path / "v2", build_id="2" * 32)  # same default protocol values

    report = run_preflight(artifact_dir=candidate, paths=paths)

    assert report.compatibility == "current"


def test_preflight_reports_incompatible_wire_protocol_honestly(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())
    candidate = _write_fake_artifact(tmp_path / "v2", build_id="2" * 32, node_api_version="v2")

    report = run_preflight(artifact_dir=candidate, paths=paths)

    assert report.compatibility == "incompatible"
    # Never blocking on its own -- the Host's own real gate enforces this,
    # not the installer; an operator must still be able to *see* it.
    assert report.blocking is False


def test_preflight_reports_unknown_compatibility_against_a_pre_milestone_installed_manifest(tmp_path) -> None:
    """A currently-installed build from before this milestone has no
    `protocol` field in its manifest.json at all -- must read as honestly
    "unknown," never silently as "current."""

    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())
    installed_manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    del installed_manifest["protocol"]
    paths.manifest_path.write_text(json.dumps(installed_manifest), encoding="utf-8")

    candidate = _write_fake_artifact(tmp_path / "v2", build_id="2" * 32)
    report = run_preflight(artifact_dir=candidate, paths=paths)

    assert report.compatibility == "unknown"


# --- Staged activation / interrupted-update recovery -------------------------

def test_failed_staged_pip_install_leaves_the_running_install_untouched(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())
    before = (paths.venv_dir / "bin" / "python").read_text(encoding="utf-8")

    class _RunnerFailingPipInstall(FakeCommandRunner):
        def __call__(self, command):
            if command[0].endswith("/python") and len(command) > 2 and command[2] == "pip":
                return _result(1, stderr="simulated pip failure")
            return super().__call__(command)

    with pytest.raises(InstallerError, match="Could not install the Camera Node package"):
        install_or_update_venv(_write_fake_artifact(tmp_path / "v2", build_id="2" * 32), paths, runner=_RunnerFailingPipInstall())

    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "1" * 32
    assert (paths.venv_dir / "bin" / "python").read_text(encoding="utf-8") == before
    assert not paths.previous_venv_dir.exists()
    assert not paths.staging_venv_dir.exists()  # cleaned up, not left as debris
    assert not paths.staging_manifest_path.exists()


def test_failed_staged_import_check_leaves_the_running_install_untouched(tmp_path) -> None:
    """The exact check that would have caught this milestone's own found
    NODE_FILES packaging gap at install time -- see "Existing state" in
    the governing report."""

    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())

    class _RunnerFailingImportCheck(FakeCommandRunner):
        def __call__(self, command):
            if command[0].endswith("/python") and command[1:2] == ["-c"]:
                return _result(1, stderr="ModuleNotFoundError: simulated")
            return super().__call__(command)

    with pytest.raises(InstallerError, match="basic import check"):
        install_or_update_venv(_write_fake_artifact(tmp_path / "v2", build_id="2" * 32), paths, runner=_RunnerFailingImportCheck())

    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "1" * 32
    assert not paths.staging_venv_dir.exists()
    assert not paths.staging_manifest_path.exists()


def test_stale_staging_from_an_interrupted_attempt_is_discarded_and_rebuilt(tmp_path) -> None:
    """Live venv intact + a leftover `venv.staging` -- a prior attempt died
    before ever reaching activation. Safe to discard and rebuild fresh,
    never reused (a partially-`pip install`ed venv cannot be safely
    resumed) -- see "Idempotency" in the governing report."""

    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=runner)

    paths.staging_venv_dir.mkdir(parents=True)
    (paths.staging_venv_dir / "partial-junk").write_text("incomplete pip install", encoding="utf-8")
    paths.staging_manifest_path.write_text("{}", encoding="utf-8")

    outcome = install_or_update_venv(_write_fake_artifact(tmp_path / "v2", build_id="2" * 32), paths, runner=runner)

    assert outcome.changed is True
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "2" * 32
    assert json.loads(paths.previous_manifest_path.read_text())["provenance"]["build_id"] == "1" * 32
    assert not paths.staging_venv_dir.exists()


def test_interrupted_mid_activation_before_venv_promotion_is_completed_on_the_next_run(tmp_path) -> None:
    """Activation promotes the manifest *first*, the venv *second* (see
    `_recover_staged_activation`'s own docstring for why). This simulates a
    crash right after the manifest promotion succeeds but before the venv
    rename runs: `manifest.json` already names build 2, but `venv/` still
    physically holds build 1's content, and `venv.staging` (already fully
    verified before activation ever began) has not yet been promoted."""

    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=runner)
    v1_python_before = (paths.venv_dir / "bin" / "python").read_text(encoding="utf-8")

    v2_artifact = _write_fake_artifact(tmp_path / "v2", build_id="2" * 32)
    # Manifest promotion already completed (the real activation's first step).
    paths.manifest_path.rename(paths.previous_manifest_path)
    (paths.install_root / "manifest.json.tmp").write_bytes((v2_artifact / "manifest.json").read_bytes())
    (paths.install_root / "manifest.json.tmp").rename(paths.manifest_path)
    (paths.install_root / "manifest.json.staging").write_bytes((v2_artifact / "manifest.json").read_bytes())
    # Venv promotion has not run yet: build 2's staging already exists,
    # already verified, but venv/ is still build 1's, untouched.
    paths.staging_venv_dir.mkdir(parents=True)
    (paths.staging_venv_dir / "bin").mkdir()
    (paths.staging_venv_dir / "bin" / "python").write_text("#!/sh\necho build2\n", encoding="utf-8")

    outcome = install_or_update_venv(v2_artifact, paths, runner=runner)

    # The recovery step alone already completed the activation; being asked
    # to install the identical build 2 again is correctly a no-op.
    assert outcome.changed is False
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "2" * 32
    assert json.loads(paths.previous_manifest_path.read_text())["provenance"]["build_id"] == "1" * 32
    assert not paths.staging_venv_dir.exists()
    assert not paths.staging_manifest_path.exists()
    assert (paths.venv_dir / "bin" / "python").read_text(encoding="utf-8") == "#!/sh\necho build2\n"
    assert (paths.previous_venv_dir / "bin" / "python").read_text(encoding="utf-8") == v1_python_before


def test_interrupted_mid_activation_after_venv_promotion_is_reconciled_on_the_next_run(tmp_path) -> None:
    """Both promotions (manifest, then venv) already completed -- only the
    now-redundant `manifest.json.staging` cleanup never ran. This is the
    specific gap an earlier version of this recovery logic (keyed solely on
    `venv.staging` existing) missed entirely, since by this point
    `venv.staging` is already gone -- see "Existing state" in the governing
    report."""

    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=runner)

    v2_artifact = _write_fake_artifact(tmp_path / "v2", build_id="2" * 32)
    outcome_normal = install_or_update_venv(v2_artifact, paths, runner=runner)
    assert outcome_normal.changed is True  # a real, uninterrupted activation to build 2

    # Simulate the one remaining leftover: the staging marker was never
    # cleaned up (as if the process died on the very last line).
    (paths.install_root / "manifest.json.staging").write_bytes((v2_artifact / "manifest.json").read_bytes())
    assert paths.staging_manifest_path.exists()
    assert not paths.staging_venv_dir.exists()

    v3_artifact = _write_fake_artifact(tmp_path / "v3", build_id="3" * 32)
    outcome = install_or_update_venv(v3_artifact, paths, runner=runner)

    # Recovery only needed to clean up the leftover marker; the real
    # requested upgrade (to build 3) then proceeds normally.
    assert outcome.changed is True
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "3" * 32
    assert json.loads(paths.previous_manifest_path.read_text())["provenance"]["build_id"] == "2" * 32
    assert not paths.staging_manifest_path.exists()


# --- Automatic rollback on failed post-update verification -------------------

def test_failed_health_after_upgrade_triggers_automatic_rollback(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v1", build_id="1" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )

    health = _ScriptedHealthChecker([
        (True, "healthy (pre-upgrade)", _fake_health_payload()),      # pre-upgrade snapshot: build 1 fine
        (False, "simulated: build 2 never came up", {}),               # post-activation: build 2 broken
        (True, "healthy (restored)", _fake_health_payload()),          # rollback's own re-verification
    ])
    report = install(
        artifact_dir=_write_fake_artifact(tmp_path / "v2", build_id="2" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=health,
    )

    assert report.healthy is True
    assert report.rolled_back is True
    assert "automatically rolled back" in report.health_message
    assert any("automatic rollback succeeded" in step for step in report.steps)
    # The prior known-good build (1) is what's actually live again.
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "1" * 32
    assert json.loads(paths.previous_manifest_path.read_text())["provenance"]["build_id"] == "2" * 32


def test_failed_health_after_upgrade_with_rollback_also_failing_is_visible_not_silent(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v1", build_id="1" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )

    health = _ScriptedHealthChecker([
        (True, "healthy (pre-upgrade)", _fake_health_payload()),
        (False, "simulated: build 2 never came up", {}),
        (False, "simulated: still broken even restored -- e.g. a hardware fault", {}),
    ])
    report = install(
        artifact_dir=_write_fake_artifact(tmp_path / "v2", build_id="2" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=health,
    )

    assert report.healthy is False
    assert "hardware/environment problem" in report.health_message
    assert any("also failed to verify healthy" in step for step in report.steps)


def test_failed_health_on_first_install_does_not_attempt_rollback(tmp_path) -> None:
    """Nothing to roll back to -- must fail visibly, not pretend to recover."""

    report = install(
        artifact_dir=_write_fake_artifact(tmp_path / "artifact"),
        paths=InstallPaths(prefix=tmp_path / "root"),
        runner=FakeCommandRunner(),
        is_root=lambda: True,
        health_checker=_fake_unhealthy,
    )

    assert report.healthy is False
    assert report.rolled_back is False
    assert "connection refused" in report.health_message
    assert not any("rollback" in step for step in report.steps)


# --- Identity preservation ----------------------------------------------------

def test_unexpected_node_id_change_during_upgrade_raises_clearly(tmp_path) -> None:
    """An ordinary software upgrade never changes node_id -- see "Do not
    confuse upgrade with replacement" in the governing brief. Never
    auto-"fixed" by rolling back: this must surface loudly for diagnosis."""

    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v1", build_id="1" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )

    health = _ScriptedHealthChecker([
        (True, "healthy", _fake_health_payload(node_id="node-before")),
        (True, "healthy", _fake_health_payload(node_id="node-after-SURPRISE")),
    ])
    with pytest.raises(InstallerError, match="identity changed unexpectedly"):
        install(
            artifact_dir=_write_fake_artifact(tmp_path / "v2", build_id="2" * 32),
            paths=paths, runner=runner, is_root=lambda: True, health_checker=health,
        )


def test_ordinary_upgrade_with_a_stable_node_id_does_not_raise(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v1", build_id="1" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )

    report = install(
        artifact_dir=_write_fake_artifact(tmp_path / "v2", build_id="2" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )

    assert report.healthy is True
    assert any("service_version" in step for step in report.steps)


# --- Rollback interruption ----------------------------------------------------

def test_rollback_refuses_clearly_when_a_previous_rollback_attempt_was_interrupted(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    runner = FakeCommandRunner()
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v1", build_id="1" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )
    install(
        artifact_dir=_write_fake_artifact(tmp_path / "v2", build_id="2" * 32),
        paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy,
    )
    (paths.install_root / "venv.rollback-swap").mkdir()

    with pytest.raises(InstallerError, match="interrupted"):
        rollback(paths=paths, runner=runner, is_root=lambda: True, health_checker=_fake_healthy)

    # Nothing was changed by the refused attempt itself.
    assert json.loads(paths.manifest_path.read_text())["provenance"]["build_id"] == "2" * 32


def test_status_surfaces_an_interrupted_upgrade_leftover(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())
    paths.staging_venv_dir.mkdir(parents=True)

    report = status(paths=paths, runner=FakeCommandRunner(), health_checker=_fake_unhealthy)

    assert any("interrupted upgrade attempt" in line for line in report.lines)


# --- No secret leakage --------------------------------------------------------

def test_status_never_crashes_on_a_manifest_with_a_partial_protocol_object(tmp_path) -> None:
    """A manifest.json protocol object missing one of its two keys must
    degrade gracefully, not raise an uncaught KeyError -- see "Existing
    state" in the governing report."""

    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())
    manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    manifest["protocol"] = {"node_api_version": "v1"}  # missing transport_protocol_version
    paths.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = status(paths=paths, runner=FakeCommandRunner(), health_checker=_fake_unhealthy)  # must not raise

    assert any("node_api_version=v1" in line for line in report.lines)


def test_status_never_crashes_when_manifest_json_is_not_an_object(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    install_or_update_venv(_write_fake_artifact(tmp_path / "v1", build_id="1" * 32), paths, runner=FakeCommandRunner())
    paths.manifest_path.write_text("null", encoding="utf-8")

    report = status(paths=paths, runner=FakeCommandRunner(), health_checker=_fake_unhealthy)  # must not raise

    assert any("unreadable" in line for line in report.lines)


def test_run_preflight_reports_a_non_object_manifest_as_a_blocking_check_not_a_crash(tmp_path) -> None:
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "manifest.json").write_text("[1, 2, 3]", encoding="utf-8")

    report = run_preflight(artifact_dir=artifact_dir, paths=InstallPaths(prefix=tmp_path / "root"))  # must not raise

    assert report.blocking is True
    assert any(not check.passed and check.name == "candidate_manifest" for check in report.checks)


def test_verify_artifact_checksums_reports_a_clean_error_on_undecodable_sha256sums(tmp_path) -> None:
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")
    (artifact_dir / "SHA256SUMS").write_bytes(b"\xff\xfe\x00garbage-not-utf8")

    with pytest.raises(InstallerError, match="could not be read"):
        verify_artifact_checksums(artifact_dir)


def test_preflight_does_not_block_on_an_unrelated_corrupted_pairing_state(tmp_path) -> None:
    """The candidate artifact is fine; a pre-existing, unrelated corrupted
    pairing.json (never read or depended on by the upgrade mechanics) must
    not refuse an otherwise-valid upgrade -- see "Existing state" in the
    governing report."""

    paths = InstallPaths(prefix=tmp_path / "root")
    paths.state_dir.mkdir(parents=True)
    (paths.state_dir / "pairing.json").write_text("{not valid json", encoding="utf-8")
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")

    report = run_preflight(artifact_dir=artifact_dir, paths=paths)

    assert report.blocking is False
    pairing_check = next(check for check in report.checks if check.name == "pairing_state_readable")
    assert pairing_check.passed is True
    assert "could not be read" in pairing_check.detail


def test_preflight_skips_checksum_verification_for_an_already_up_to_date_build(tmp_path) -> None:
    """A tampered artifact whose build_id already matches what's installed
    is still detected as `would_be_no_op` and never needs the expensive
    checksum pass -- nothing will be staged or mutated either way."""

    paths = InstallPaths(prefix=tmp_path / "root")
    artifact_dir = _write_fake_artifact(tmp_path / "artifact", build_id="1" * 32)
    install_or_update_venv(artifact_dir, paths, runner=FakeCommandRunner())
    (artifact_dir / "requirements.txt").write_bytes(b"tampered after being installed")

    report = run_preflight(artifact_dir=artifact_dir, paths=paths)

    assert report.would_be_no_op is True
    assert report.blocking is False
    checksum_check = next(check for check in report.checks if check.name == "candidate_checksums")
    assert checksum_check.passed is True
    assert "skipped" in checksum_check.detail


# --- main() CLI-level behavior -------------------------------------------

def test_main_direct_rollback_success_exits_cleanly_with_no_false_recovery_note(monkeypatch, capsys) -> None:
    """A plain, explicitly-requested `--rollback` that succeeds must never
    be reported as if an upgrade's automatic recovery kicked in -- see
    "Existing state" in the governing report."""

    fake_report = InstallReport(
        steps=("rolled back from build a to build b", "health check: healthy"),
        healthy=True, health_message="healthy: node_id=fake pairing_required=True", rolled_back=True,
    )
    monkeypatch.setitem(main.__globals__, "rollback", lambda **_kwargs: fake_report)
    monkeypatch.setattr(sys, "argv", ["install_camera_node.py", "--rollback"])

    main()  # must return normally -- no SystemExit at all

    output = capsys.readouterr()
    assert "did not pass verification" not in output.err
    assert "rollback complete and healthy" in output.out


def test_main_install_with_automatic_rollback_still_warns_and_exits_nonzero(monkeypatch, capsys) -> None:
    """The one case that *should* produce the warning + non-zero exit:
    `install()` itself automatically restored the prior build after the
    requested upgrade failed verification. Guards against the fix for the
    finding above silencing this legitimate case too."""

    fake_report = InstallReport(
        steps=("automatic rollback succeeded",),
        healthy=True,
        health_message="requested build failed verification and was automatically rolled back (simulated)",
        rolled_back=True,
    )
    monkeypatch.setitem(main.__globals__, "install", lambda **_kwargs: fake_report)
    monkeypatch.setattr(sys, "argv", ["install_camera_node.py", "/some/artifact"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    output = capsys.readouterr()
    assert "did not pass verification" in output.err


def test_preflight_report_never_contains_a_credential_or_pairing_digest(tmp_path) -> None:
    paths = InstallPaths(prefix=tmp_path / "root")
    paths.state_dir.mkdir(parents=True)
    (paths.state_dir / "pairing.json").write_text(
        json.dumps({"version": 1, "credential_sha256": "deadbeefdeadbeef"}), encoding="utf-8",
    )
    artifact_dir = _write_fake_artifact(tmp_path / "artifact")

    report = run_preflight(artifact_dir=artifact_dir, paths=paths)

    serialized = " ".join(report.lines)
    assert "deadbeef" not in serialized
    assert "credential" not in serialized.lower()
