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
