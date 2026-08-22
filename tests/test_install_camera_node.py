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

import json
import os
from pathlib import Path
import runpy
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(ROOT / "scripts" / "install_camera_node.py")
InstallPaths = _MODULE["InstallPaths"]
InstallerError = _MODULE["InstallerError"]
install = _MODULE["install"]
rollback = _MODULE["rollback"]
status = _MODULE["status"]
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


def _fake_healthy(_url: str) -> tuple:
    return True, "healthy: node_id=fake-node pairing_required=True"


def _fake_unhealthy(_url: str) -> tuple:
    return False, "connection refused (fake)"


def _write_fake_artifact(directory: Path, *, build_id: str = "a" * 32, git_commit: str = "c" * 40) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "mockingbird_camera_node-0.1.0-py3-none-any.whl").write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    (directory / "requirements.txt").write_text("fastapi\npydantic\nuvicorn\n", encoding="utf-8")
    (directory / "manifest.json").write_text(
        json.dumps({
            "artifact": "mockingbird_camera_node-0.1.0-py3-none-any.whl",
            "provenance": {"git_commit": git_commit, "source_clean": True, "build_id": build_id, "built_at": "2026-08-18T00:00:00+00:00"},
        }),
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
