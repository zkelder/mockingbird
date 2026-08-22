"""Idempotent local installer for the MockingBird Camera Node systemd service.

See docs/camera-node-installer-design.md for the full contract this
implements. Standard-library only -- runnable with the system `python3`
already present before any virtual environment exists, matching every other
`scripts/*.py` build/deploy tool in this repository. Never fetches anything
remotely and never executes on any machine other than the one it is invoked
on: `artifact_dir` must already be a local directory produced by
`scripts/build_camera_node_artifact.py` (copied here by the operator through
whatever transport they already trust -- `scp`, a USB drive, ...).

Usage (on the Camera Node device itself, as root):

    sudo python3 scripts/install_camera_node.py /path/to/artifact
    sudo python3 scripts/install_camera_node.py --status
    sudo python3 scripts/install_camera_node.py --rollback
    sudo python3 scripts/install_camera_node.py --export-config backup.json
    sudo python3 scripts/install_camera_node.py /path/to/artifact --import-config backup.json

Safe to re-run: an unchanged artifact is a no-op beyond ensuring the service
is enabled/running; a changed artifact keeps exactly one prior version for
`--rollback`. An existing `node.env` or paired state is never overwritten --
`--import-config` extends that same guarantee rather than replacing it: it
only ever materializes `node.env` when one does not already exist. See
"Configuration Backup + Reprovision" in docs/camera-node-reprovision-
recovery-design.md.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from typing import Callable
import urllib.error
import urllib.request


SERVICE_NAME = "mockingbird-camera-node"
SERVICE_USER = "mockingbird-node"
SERVICE_GROUP = "mockingbird-node"
CAMERA_GROUP = "video"
STATE_DIRECTORY_NAME = "mockingbird-camera-node"
#: Every device file a real, multi-day-running reference Camera Node process
#: actually had open (/proc/<pid>/fd) was root:video, mode 660 -- see
#: "Service identity and device access" in docs/camera-node-installer-design.md.
#: No other group (gpio, render, i2c, spi, dialout, plugdev) is load-bearing.
REQUIRED_APT_PACKAGES = ("python3-venv",)
OPTIONAL_APT_PACKAGES = ("python3-picamera2", "python3-opencv")

#: Versioned, explicit -- see "Configuration export/import contract" in
#: docs/camera-node-reprovision-recovery-design.md. Bump only for a breaking
#: `node_env` shape change; `import_node_config_if_absent` accepts any
#: version <= this one and refuses a newer one honestly rather than guessing.
CONFIG_BUNDLE_VERSION = 1
CONFIG_BUNDLE_KIND = "mockingbird_camera_node_config"
#: The portable *intent* subset of `node.env` -- display name, network bind,
#: provider selection, camera/image bounds, pairing TTL, preview cap, log
#: level. Deliberately excludes `MOCKINGBIRD_NODE_PAIRING_STATE_PATH` (an
#: install-path detail recomputed fresh for the current install, never
#: trusted from an old bundle -- see `_normalize_config_bundle`) and
#: `MOCKINGBIRD_NODE_TESTING` (a test-only escape hatch, never worth
#: preserving across a backup). Contains no secret: pairing credentials live
#: only in `pairing.json` (node-local, hash-only) and the host's own
#: database -- never in `node.env` at all.
PORTABLE_NODE_ENV_KEYS = (
    "MOCKINGBIRD_NODE_NAME",
    "MOCKINGBIRD_NODE_BIND",
    "MOCKINGBIRD_NODE_PORT",
    "MOCKINGBIRD_NODE_PROVIDERS",
    "MOCKINGBIRD_NODE_CAMERA",
    "MOCKINGBIRD_NODE_MAX_IMAGE_BYTES",
    "MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH",
    "MOCKINGBIRD_NODE_MAX_IMAGE_HEIGHT",
    "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_BYTES",
    "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH",
    "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_HEIGHT",
    "MOCKINGBIRD_NODE_PAIRING_TTL_SECONDS",
    "MOCKINGBIRD_NODE_MAX_PREVIEW_VIEWERS",
    "MOCKINGBIRD_NODE_LOG_LEVEL",
)

CommandRunner = Callable[[list], "subprocess.CompletedProcess"]
HealthChecker = Callable[[str], "tuple[bool, str]"]


class InstallerError(RuntimeError):
    """A clear, operator-facing installer failure."""


def real_command_runner(command: list) -> "subprocess.CompletedProcess":
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _real_is_root() -> bool:
    return os.geteuid() == 0


@dataclass(frozen=True)
class InstallPaths:
    """Every filesystem location this installer touches, rooted under
    `prefix` -- real `/` in production, an isolated `tmp_path` in tests, so
    hermetic tests never touch real system paths."""

    prefix: Path = Path("/")

    @property
    def install_root(self) -> Path:
        return self.prefix / "opt" / "mockingbird-camera-node"

    @property
    def venv_dir(self) -> Path:
        return self.install_root / "venv"

    @property
    def previous_venv_dir(self) -> Path:
        return self.install_root / "venv.previous"

    @property
    def manifest_path(self) -> Path:
        return self.install_root / "manifest.json"

    @property
    def previous_manifest_path(self) -> Path:
        return self.install_root / "manifest.json.previous"

    @property
    def config_dir(self) -> Path:
        return self.prefix / "etc" / "mockingbird-camera-node"

    @property
    def env_file(self) -> Path:
        return self.config_dir / "node.env"

    @property
    def state_dir(self) -> Path:
        return self.prefix / "var" / "lib" / STATE_DIRECTORY_NAME

    @property
    def unit_path(self) -> Path:
        return self.prefix / "etc" / "systemd" / "system" / f"{SERVICE_NAME}.service"

    @property
    def hardware_watchdog_device(self) -> Path:
        return self.prefix / "dev" / "watchdog"

    @property
    def systemd_watchdog_dropin_path(self) -> Path:
        # A machine-wide `system.conf.d/` drop-in, not a `[Service]` unit
        # option: `RuntimeWatchdogSec=` is a `systemd-system.conf(5)`
        # setting owned by PID 1 itself (it pets the hardware device
        # directly), not something an individual unit file can configure --
        # see "Hardware watchdog" in docs/camera-node-installer-design.md.
        return self.prefix / "etc" / "systemd" / "system.conf.d" / f"{SERVICE_NAME}-watchdog.conf"


# --- System prerequisites ---------------------------------------------------

@dataclass(frozen=True)
class PrerequisiteReport:
    required_ok: bool
    packages: dict


def _dpkg_installed(package: str, *, runner: CommandRunner) -> bool:
    return runner(["dpkg", "-s", package]).returncode == 0


def ensure_system_prerequisites(*, runner: CommandRunner) -> PrerequisiteReport:
    """Best-effort per-package: a missing *optional* provider dependency
    (PiCamera2/OpenCV) must never break the whole install -- see "System
    prerequisites" in docs/camera-node-installer-design.md. Only
    `python3-venv` is fatal if unavailable."""

    all_packages = [(name, True) for name in REQUIRED_APT_PACKAGES] + [
        (name, False) for name in OPTIONAL_APT_PACKAGES
    ]
    missing = [name for name, _required in all_packages if not _dpkg_installed(name, runner=runner)]
    if missing:
        runner(["apt-get", "update", "-y"])

    results: dict = {}
    required_ok = True
    for name, required in all_packages:
        if _dpkg_installed(name, runner=runner):
            results[name] = "already installed"
            continue
        completed = runner(["apt-get", "install", "-y", name])
        if completed.returncode == 0:
            results[name] = "installed"
            continue
        tail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "apt-get failed"
        results[name] = f"unavailable ({tail})"
        if required:
            required_ok = False
    return PrerequisiteReport(required_ok=required_ok, packages=results)


# --- Service identity --------------------------------------------------------

def ensure_service_account(*, runner: CommandRunner) -> str:
    """Dedicated, unprivileged system account with exactly one supplementary
    group (`video`) -- see "Service identity and device access" in
    docs/camera-node-installer-design.md."""

    if runner(["id", "-u", SERVICE_USER]).returncode == 0:
        outcome = "already exists"
    else:
        created = runner([
            "useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin",
            "--user-group", SERVICE_USER,
        ])
        if created.returncode != 0:
            raise InstallerError(f"Could not create service account {SERVICE_USER}: {created.stderr.strip()}")
        outcome = "created"
    groups = runner(["id", "-nG", SERVICE_USER])
    if CAMERA_GROUP not in groups.stdout.split():
        added = runner(["usermod", "--append", "--groups", CAMERA_GROUP, SERVICE_USER])
        if added.returncode != 0:
            raise InstallerError(f"Could not add {SERVICE_USER} to the {CAMERA_GROUP} group: {added.stderr.strip()}")
    return outcome


# --- Directories and configuration ------------------------------------------

def ensure_directories(paths: InstallPaths) -> None:
    """`state_dir` is deliberately not created here -- systemd's own
    `StateDirectory=` creates and owns it (correct permissions, matching
    `User=`/`Group=`) before every service start, including a first-ever
    boot; see "State paths" in docs/camera-node-installer-design.md."""

    paths.install_root.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.install_root, 0o755)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.config_dir, 0o755)


def _default_node_env_content(paths: InstallPaths) -> str:
    lines = [
        "# Local-only MockingBird Camera Node configuration.",
        "# Installed by scripts/install_camera_node.py -- see docs/camera-node-install-guide.md.",
        "# An update never overwrites this file once it exists.",
        "MOCKINGBIRD_NODE_NAME=Pi Camera Node",
        "MOCKINGBIRD_NODE_BIND=0.0.0.0",
        "MOCKINGBIRD_NODE_PORT=8787",
        "MOCKINGBIRD_NODE_PROVIDERS=picamera2,v4l2",
        "MOCKINGBIRD_NODE_MAX_IMAGE_BYTES=1500000",
        "MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=1920",
        "MOCKINGBIRD_NODE_MAX_IMAGE_HEIGHT=1080",
        "# Optional bounded evidence still; monitoring remains 1920x1080.",
        "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_BYTES=16000000",
        "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH=10000",
        "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_HEIGHT=8000",
        "MOCKINGBIRD_NODE_PAIRING_TTL_SECONDS=600",
        "MOCKINGBIRD_NODE_MAX_PREVIEW_VIEWERS=2",
        # Explicit, predictable, systemd-StateDirectory-backed path -- never
        # an inherited XDG_STATE_HOME/$HOME guess for a system service
        # account. See "State paths" in docs/camera-node-installer-design.md.
        f"MOCKINGBIRD_NODE_PAIRING_STATE_PATH={paths.state_dir}/pairing.json",
        "# Conservative default; raise (e.g. to info) for more verbose uvicorn",
        "# access logs while diagnosing -- see docs/camera-node-installer-design.md.",
        "MOCKINGBIRD_NODE_LOG_LEVEL=warning",
        "# Synthetic is intentionally omitted: it is test-only.",
    ]
    return "\n".join(lines) + "\n"


def atomic_write_text(path: Path, content: str, *, mode: int) -> None:
    """Write-temp-then-rename so a crash/power-loss mid-write can never leave
    a partially-written file behind -- see "Configuration-write safety" in
    docs/camera-node-reprovision-recovery-design.md. Same O_EXCL + fsync +
    `os.replace` shape as the Node's own `_PairingState._persist_state`
    (`src/mockingbird_node/app.py`), the only precedent for this in the
    codebase; there was previously no shared, importable helper for it."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    os.chmod(path, mode)


def _render_node_env(values: dict, paths: InstallPaths, *, header: list) -> str:
    """Shared rendering for both a fresh default `node.env` and one
    materialized from an imported backup bundle -- one template, not two
    diverging copies. `MOCKINGBIRD_NODE_PAIRING_STATE_PATH` is always
    recomputed for *this* install rather than trusted from a bundle (see
    `PORTABLE_NODE_ENV_KEYS`'s docstring)."""

    lines = list(header)
    for key in PORTABLE_NODE_ENV_KEYS:
        if key in values:
            lines.append(f"{key}={values[key]}")
    lines.append(f"MOCKINGBIRD_NODE_PAIRING_STATE_PATH={paths.state_dir}/pairing.json")
    return "\n".join(lines) + "\n"


def ensure_config_file(paths: InstallPaths, *, import_bundle_path: "Path | None" = None) -> bool:
    """Never overwrites an existing file -- "an update must not overwrite
    existing operator configuration." Returns whether a new file was
    written. When `import_bundle_path` names a valid exported configuration
    bundle (see `export_node_config`) and no `node.env` exists yet, the new
    file is materialized from it instead of the hardcoded template -- this
    is what lets a same-hardware reinstall recover its prior display name
    (and therefore its prior `node_id`, and therefore ordinary repair-
    pairing) without manual reconstruction. See "Reinstall same hardware" in
    docs/camera-node-reprovision-recovery-design.md."""

    if paths.env_file.exists():
        return False
    if import_bundle_path is not None:
        values = _normalized_config_bundle_values(_load_config_bundle(import_bundle_path))
        header = [
            "# Local-only MockingBird Camera Node configuration.",
            f"# Restored from a configuration backup ({import_bundle_path.name}) by",
            "# scripts/install_camera_node.py -- see docs/camera-node-install-guide.md.",
            "# An update never overwrites this file once it exists.",
        ]
        content = _render_node_env(values, paths, header=header)
    else:
        content = _default_node_env_content(paths)
    atomic_write_text(paths.env_file, content, mode=0o600)
    return True


def parse_env_file(path: Path) -> dict:
    values: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


# --- Configuration backup / export / import ---------------------------------
#
# Node-local configuration (node.env) never contains a secret: the pairing
# credential lives only in pairing.json (node-local, hash-only -- see
# _PairingState) and the host's own database, neither of which is portable
# or reusable off-device anyway. Reprovisioning always requires fresh
# pairing regardless of what is restored here (Model A -- see "Secrets" in
# docs/camera-node-reprovision-recovery-design.md), so the export bundle
# below is safe to inspect, copy, and store without any redaction step.

def export_node_config(paths: InstallPaths) -> dict:
    """Read-only: the current `node.env`'s portable intent fields, wrapped in
    a small versioned envelope. Raises `InstallerError` if no configuration
    exists yet -- nothing to back up."""

    if not paths.env_file.is_file():
        raise InstallerError(f"No configuration exists yet at {paths.env_file}; nothing to export.")
    current = parse_env_file(paths.env_file)
    node_env = {key: current[key] for key in PORTABLE_NODE_ENV_KEYS if key in current}
    manifest_summary = None
    if paths.manifest_path.is_file():
        try:
            manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
            manifest_summary = manifest.get("provenance", {}).get("build_id")
        except (OSError, ValueError):
            manifest_summary = None
    return {
        "bundle_version": CONFIG_BUNDLE_VERSION,
        "bundle_kind": CONFIG_BUNDLE_KIND,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "installed_build_id": manifest_summary,
        "node_env": node_env,
    }


def _load_config_bundle(bundle_path: Path) -> dict:
    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise InstallerError(f"Could not read configuration backup {bundle_path}: {error}") from None
    except ValueError as error:
        raise InstallerError(f"Configuration backup {bundle_path} is not valid JSON: {error}") from None
    if not isinstance(data, dict):
        raise InstallerError(f"Configuration backup {bundle_path} is malformed (expected a JSON object).")
    return data


def _normalized_config_bundle_values(data: dict) -> dict:
    """Validate a loaded bundle and return its safe, ready-to-render
    `node_env` values. Every rejection is a clear `InstallerError` raised
    before anything is written -- see "Configuration validation" in
    docs/camera-node-reprovision-recovery-design.md. An unknown *future*
    bundle version is refused outright (this installer cannot safely
    interpret a shape it has never seen); an unknown *key* inside an
    otherwise-valid bundle is dropped with a printed notice rather than
    failing the whole import, so an older installer stays forward-
    compatible with a newer one's bundle where practical."""

    version = data.get("bundle_version")
    if not isinstance(version, int) or version < 1:
        raise InstallerError("Configuration backup is missing a valid bundle_version.")
    if version > CONFIG_BUNDLE_VERSION:
        raise InstallerError(
            f"Configuration backup was created by a newer format (version {version}); "
            f"this installer supports up to version {CONFIG_BUNDLE_VERSION}. Use a matching "
            "or newer scripts/install_camera_node.py to import it."
        )
    if data.get("bundle_kind") != CONFIG_BUNDLE_KIND:
        raise InstallerError("Configuration backup does not look like a Camera Node configuration bundle.")
    node_env = data.get("node_env")
    if not isinstance(node_env, dict):
        raise InstallerError("Configuration backup is missing its node_env settings.")

    values: dict = {}
    for key, value in node_env.items():
        if key not in PORTABLE_NODE_ENV_KEYS:
            print(f"note: ignoring unrecognized configuration key {key!r} from backup", file=sys.stderr)
            continue
        if not isinstance(value, str):
            raise InstallerError(f"Configuration backup value for {key} must be a string.")
        if "\n" in value or "\r" in value or "\x00" in value:
            raise InstallerError(f"Configuration backup value for {key} contains an unsafe character.")
        values[key] = value
    return values


def import_node_config_if_absent(bundle_path: Path, paths: InstallPaths) -> str:
    """Standalone entry point for `--import-config` without a fresh install
    under way -- validates then delegates to `ensure_config_file` so the
    "never overwrite an existing node.env" guarantee has exactly one
    implementation. Returns an operator-facing outcome message."""

    _normalized_config_bundle_values(_load_config_bundle(bundle_path))  # validate before any write
    if paths.env_file.exists():
        return (
            f"{paths.env_file} already exists; import skipped to avoid overwriting existing "
            "configuration. Remove it first (or edit it directly) to replace it."
        )
    ensure_config_file(paths, import_bundle_path=bundle_path)
    return f"Restored {paths.env_file} from {bundle_path}."


# --- Package install/update/rollback ----------------------------------------

@dataclass(frozen=True)
class VenvUpdateOutcome:
    changed: bool
    message: str


def install_or_update_venv(artifact_dir: Path, paths: InstallPaths, *, runner: CommandRunner) -> VenvUpdateOutcome:
    """A fresh venv is always built from scratch rather than upgraded in
    place -- more robust across dependency changes, and it naturally keeps
    exactly one prior version for `--rollback` (see "Update behavior"/
    "Rollback" in docs/camera-node-installer-design.md). Identified by
    `manifest.json`'s `provenance.build_id`, not the version string alone,
    so two independent builds of the identical commit are still
    distinguishable."""

    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file():
        raise InstallerError(f"{artifact_dir} does not look like a Camera Node artifact directory (no manifest.json).")
    new_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    new_build_id = new_manifest["provenance"]["build_id"]

    if paths.manifest_path.is_file():
        current_manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
        if current_manifest.get("provenance", {}).get("build_id") == new_build_id:
            return VenvUpdateOutcome(changed=False, message=f"already installed (build {new_build_id})")

        if paths.previous_venv_dir.exists():
            shutil.rmtree(paths.previous_venv_dir)
        if paths.venv_dir.exists():
            paths.venv_dir.rename(paths.previous_venv_dir)
        if paths.previous_manifest_path.exists():
            paths.previous_manifest_path.unlink()
        if paths.manifest_path.exists():
            paths.manifest_path.rename(paths.previous_manifest_path)

    created = runner(["python3", "-m", "venv", "--system-site-packages", str(paths.venv_dir)])
    if created.returncode != 0:
        raise InstallerError(f"Could not create the Camera Node virtual environment: {created.stderr.strip()}")

    venv_python = str(paths.venv_dir / "bin" / "python")
    wheel = next(artifact_dir.glob("mockingbird_camera_node-*.whl"), None)
    if wheel is None:
        raise InstallerError(f"No mockingbird_camera_node wheel found in {artifact_dir}")
    requirements = artifact_dir / "requirements.txt"
    installed = runner([venv_python, "-m", "pip", "install", "--quiet", str(wheel), "-r", str(requirements)])
    if installed.returncode != 0:
        raise InstallerError(f"Could not install the Camera Node package: {installed.stderr.strip()}")
    runner([venv_python, "-m", "compileall", "-q", str(paths.venv_dir)])  # best-effort only

    shutil.copy2(manifest_path, paths.manifest_path)
    return VenvUpdateOutcome(changed=True, message=f"installed build {new_build_id}")


# --- systemd -----------------------------------------------------------------

def render_systemd_unit(paths: InstallPaths) -> str:
    return f"""[Unit]
Description=MockingBird Camera Node
Documentation=https://github.com/anthropics/mockingbird/blob/main/docs/camera-node-install-guide.md
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=notify
NotifyAccess=main
User={SERVICE_USER}
Group={SERVICE_GROUP}
EnvironmentFile={paths.env_file}
Environment=PYTHONDONTWRITEBYTECODE=1
StateDirectory={STATE_DIRECTORY_NAME}
WorkingDirectory={paths.state_dir}
ExecStart={paths.venv_dir}/bin/python -m mockingbird_node
Restart=on-failure
RestartSec=5
TimeoutStartSec=30
TimeoutStopSec=15
WatchdogSec=30
KillSignal=SIGTERM
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
# First-Hour Onboarding + Whole-Product Observability Closure v1 ("B5 log
# retention"): the Node deliberately logs to journald, not a custom file/
# rotation subsystem (see "Logs" in docs/camera-node-installer-design.md) --
# journald's own size-based retention (`SystemMaxUse=`/`RuntimeMaxUse=` in
# journald.conf) already bounds total disk use machine-wide by OS default;
# this installer does not additionally edit that machine-wide file (a
# broader blast radius than one service warrants). What journald's own
# defaults do *not* bound is the *rate* one unit can log at -- a crash loop
# emitting a burst of failure messages every restart could otherwise spam
# the journal indefinitely (see `StartLimitIntervalSec=300`/
# `StartLimitBurst=5` above, which stops the *restarts*, not the logging).
# These two values match systemd's own built-in per-unit default explicitly
# -- not a new behavior, but a disclosed, defensible, always-on policy
# instead of an implicit one an operator would otherwise need to know to
# look up.
LogRateLimitIntervalSec=30
LogRateLimitBurst=1000

[Install]
WantedBy=multi-user.target
"""


def _systemctl(*args: str, runner: CommandRunner) -> "subprocess.CompletedProcess":
    return runner(["systemctl", *args])


def service_is_active(*, runner: CommandRunner) -> bool:
    return _systemctl("is-active", "--quiet", SERVICE_NAME, runner=runner).returncode == 0


def service_is_enabled(*, runner: CommandRunner) -> bool:
    return _systemctl("is-enabled", "--quiet", SERVICE_NAME, runner=runner).returncode == 0


def install_systemd_unit(paths: InstallPaths, *, runner: CommandRunner) -> bool:
    """Only rewrites the unit file, and only `daemon-reload`s, if its
    content actually changed -- avoids unnecessary churn on an already
    -correct install."""

    content = render_systemd_unit(paths)
    if paths.unit_path.is_file() and paths.unit_path.read_text(encoding="utf-8") == content:
        return False
    paths.unit_path.parent.mkdir(parents=True, exist_ok=True)
    paths.unit_path.write_text(content, encoding="utf-8")
    os.chmod(paths.unit_path, 0o644)
    _systemctl("daemon-reload", runner=runner)
    return True


# --- Hardware watchdog (OS-hang recovery; optional, capability-gated) -------
#
# Distinct from the service-level `WatchdogSec=`/`sd_notify` watchdog above,
# which only recovers a *hung Camera Node process* while the kernel and
# systemd itself are still scheduling normally. If the machine's own kernel
# wedges, nothing running as an ordinary process -- including systemd -- can
# act; only a piece of hardware that resets the SoC regardless of software
# state can recover that. Raspberry Pi 4's SoC has one (`bcm2835_wdt`). See
# "Hardware watchdog" in docs/camera-node-installer-design.md.
#
# This installer never edits boot-time configuration (Raspberry Pi OS's
# `/boot/firmware/config.txt`): a mistake there risks the exact
# powered-but-never-boots failure this whole milestone exists to diagnose,
# which is categorically worse than leaving the hardware watchdog off. The
# `dtparam=watchdog=on` step therefore stays a manual, documented, one-time
# operator action (see the install guide); this installer only acts *after*
# that already-manual step has made `/dev/watchdog` appear, and only when
# explicitly requested with `--enable-hardware-watchdog`.

def hardware_watchdog_device_present(paths: InstallPaths) -> bool:
    """Read-only capability probe -- never mutates anything. Safe to call
    from `--status` on every run."""

    return paths.hardware_watchdog_device.exists()


def enable_hardware_watchdog(paths: InstallPaths) -> str:
    """Write the smallest safe systemd-level configuration that pets an
    *already-present* hardware watchdog device -- refuses clearly, and
    writes nothing, if the device does not exist yet (the operator has not
    completed the manual `dtparam=watchdog=on` step). Idempotent: an
    unchanged drop-in is left untouched, matching `install_systemd_unit`'s
    own "no unnecessary churn" convention.

    `RuntimeWatchdogSec=14` is comfortably shorter than most hardware
    watchdog maximum timeouts (`bcm2835_wdt`'s default is 15s) while still
    generous for a healthy, merely momentarily busy system -- PID 1 pets it
    on its own schedule, unrelated to this Node's own `WatchdogSec=30`
    above.
    """

    if not hardware_watchdog_device_present(paths):
        return (
            "Hardware watchdog device not found "
            f"({paths.hardware_watchdog_device}). Add `dtparam=watchdog=on` to "
            "/boot/firmware/config.txt yourself, reboot, then re-run with "
            "--enable-hardware-watchdog. This installer never edits boot "
            "configuration itself -- see docs/camera-node-install-guide.md."
        )
    content = "[Manager]\nRuntimeWatchdogSec=14\n"
    if paths.systemd_watchdog_dropin_path.is_file() and paths.systemd_watchdog_dropin_path.read_text(encoding="utf-8") == content:
        return f"Hardware watchdog already configured ({paths.systemd_watchdog_dropin_path}); no change needed."
    paths.systemd_watchdog_dropin_path.parent.mkdir(parents=True, exist_ok=True)
    paths.systemd_watchdog_dropin_path.write_text(content, encoding="utf-8")
    os.chmod(paths.systemd_watchdog_dropin_path, 0o644)
    return (
        f"Wrote {paths.systemd_watchdog_dropin_path}. This takes effect after "
        "the next reboot (or `systemctl daemon-reexec`, run as root) -- systemd "
        "PID 1 only reads system.conf.d/ at its own startup."
    )


# --- Health check --------------------------------------------------------

def _health_check_url(paths: InstallPaths) -> "str | None":
    if not paths.env_file.is_file():
        return None
    env = parse_env_file(paths.env_file)
    port = env.get("MOCKINGBIRD_NODE_PORT", "8787")
    bind = env.get("MOCKINGBIRD_NODE_BIND", "0.0.0.0")
    host = "[::1]" if bind in {"::", "::1"} else "127.0.0.1"
    return f"http://{host}:{port}/node/v1/health"


def _quick_health_check(url: str) -> "tuple[bool, str]":
    """`--status` is a read-only, fast report, not a long blocking wait --
    a much shorter bound than the install/rollback default."""

    return wait_for_health(url, timeout_seconds=5.0)


def wait_for_health(url: str, *, timeout_seconds: float = 20.0) -> "tuple[bool, str]":
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return True, f"healthy: node_id={payload.get('node_id')} pairing_required={payload.get('pairing_required')}"
        except (urllib.error.URLError, OSError, ValueError) as error:
            last_error = str(error)
            time.sleep(1.0)
    return False, f"did not become healthy within {timeout_seconds:.0f}s: {last_error}"


# --- Orchestration -----------------------------------------------------------

@dataclass(frozen=True)
class InstallReport:
    steps: tuple
    healthy: bool
    health_message: str


def install(
    *,
    artifact_dir: Path,
    paths: InstallPaths = InstallPaths(),
    runner: CommandRunner = real_command_runner,
    is_root: Callable[[], bool] = _real_is_root,
    health_checker: HealthChecker = wait_for_health,
    import_config_path: "Path | None" = None,
) -> InstallReport:
    if not is_root():
        raise InstallerError(
            "This installer must be run as root, e.g.: "
            "sudo python3 scripts/install_camera_node.py <artifact_dir>"
        )
    if import_config_path is not None:
        # Validate up front, before any other step runs, so a malformed
        # backup fails the whole install cleanly rather than leaving a
        # half-configured Node -- see "Failure/recovery semantics" in
        # docs/camera-node-reprovision-recovery-design.md.
        _normalized_config_bundle_values(_load_config_bundle(import_config_path))

    steps: list = []
    prerequisites = ensure_system_prerequisites(runner=runner)
    if not prerequisites.required_ok:
        raise InstallerError(f"Missing required prerequisite: {prerequisites.packages}")
    steps.append(f"prerequisites: {prerequisites.packages}")

    account_outcome = ensure_service_account(runner=runner)
    steps.append(f"service account {SERVICE_USER}: {account_outcome}")

    ensure_directories(paths)
    steps.append(f"directories ready under {paths.install_root} and {paths.config_dir}")

    venv_outcome = install_or_update_venv(artifact_dir, paths, runner=runner)
    steps.append(f"package: {venv_outcome.message}")

    config_written = ensure_config_file(paths, import_bundle_path=import_config_path)
    if config_written and import_config_path is not None:
        step = f"configuration: restored node.env from {import_config_path}"
    elif config_written:
        step = "configuration: wrote new node.env from example"
    else:
        step = "configuration: existing node.env preserved untouched"
    steps.append(step)

    unit_changed = install_systemd_unit(paths, runner=runner)
    steps.append("systemd unit: installed/updated" if unit_changed else "systemd unit: unchanged")

    _systemctl("enable", SERVICE_NAME, runner=runner)
    needs_restart = venv_outcome.changed or unit_changed or not service_is_active(runner=runner)
    if needs_restart:
        restart = _systemctl("restart", SERVICE_NAME, runner=runner)
        if restart.returncode != 0:
            raise InstallerError(f"systemctl restart {SERVICE_NAME} failed: {restart.stderr.strip()}")
    steps.append("service: restarted" if needs_restart else "service: already running, left untouched")

    url = _health_check_url(paths)
    healthy, message = health_checker(url) if url else (False, "no configuration to health-check")
    steps.append(f"health check: {message}")
    return InstallReport(steps=tuple(steps), healthy=healthy, health_message=message)


def rollback(
    *,
    paths: InstallPaths = InstallPaths(),
    runner: CommandRunner = real_command_runner,
    is_root: Callable[[], bool] = _real_is_root,
    health_checker: HealthChecker = wait_for_health,
) -> InstallReport:
    """Swap `venv`/`manifest.json` with the one retained prior version --
    see "Rollback" in docs/camera-node-installer-design.md.
    `node.env`/pairing state are never touched by an update in the first
    place, so a rollback never has to reconcile either."""

    if not is_root():
        raise InstallerError("Rollback must be run as root.")
    if not paths.previous_venv_dir.exists() or not paths.previous_manifest_path.exists():
        raise InstallerError("No previous installed version is available to roll back to.")

    _systemctl("stop", SERVICE_NAME, runner=runner)

    rolled_back_from = None
    if paths.manifest_path.is_file():
        rolled_back_from = json.loads(paths.manifest_path.read_text(encoding="utf-8"))["provenance"]["build_id"]

    swap_venv = paths.install_root / "venv.rollback-swap"
    if paths.venv_dir.exists():
        paths.venv_dir.rename(swap_venv)
    paths.previous_venv_dir.rename(paths.venv_dir)
    if swap_venv.exists():
        swap_venv.rename(paths.previous_venv_dir)

    swap_manifest = paths.install_root / "manifest.json.rollback-swap"
    if paths.manifest_path.exists():
        paths.manifest_path.rename(swap_manifest)
    paths.previous_manifest_path.rename(paths.manifest_path)
    if swap_manifest.exists():
        swap_manifest.rename(paths.previous_manifest_path)

    restored = json.loads(paths.manifest_path.read_text(encoding="utf-8"))["provenance"]["build_id"]
    restart = _systemctl("restart", SERVICE_NAME, runner=runner)
    if restart.returncode != 0:
        raise InstallerError(f"systemctl restart {SERVICE_NAME} failed during rollback: {restart.stderr.strip()}")

    url = _health_check_url(paths)
    healthy, message = health_checker(url) if url else (False, "no configuration to health-check")
    return InstallReport(
        steps=(f"rolled back from build {rolled_back_from} to build {restored}", f"health check: {message}"),
        healthy=healthy,
        health_message=message,
    )


@dataclass(frozen=True)
class StatusReport:
    lines: tuple
    healthy: bool


def status(
    *,
    paths: InstallPaths = InstallPaths(),
    runner: CommandRunner = real_command_runner,
    health_checker: HealthChecker = _quick_health_check,
) -> StatusReport:
    """Fully read-only: makes no changes. Never requires root, but a
    non-root caller cannot read `node.env` (deliberately root-only -- see
    "Configuration paths" in docs/camera-node-installer-design.md) and is
    told so plainly rather than crashing."""

    lines: list = [
        f"service enabled: {service_is_enabled(runner=runner)}",
        f"service active: {service_is_active(runner=runner)}",
        f"hardware watchdog device present: {hardware_watchdog_device_present(paths)}",
    ]
    if paths.manifest_path.is_file():
        try:
            manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
            provenance = manifest.get("provenance", {})
            lines.append(
                f"installed build: {provenance.get('build_id')} "
                f"(commit {provenance.get('git_commit')}, built {provenance.get('built_at')})"
            )
        except (OSError, ValueError) as error:
            lines.append(f"installed manifest unreadable: {error}")
    else:
        lines.append("not installed")
    if paths.previous_manifest_path.is_file():
        try:
            previous = json.loads(paths.previous_manifest_path.read_text(encoding="utf-8"))
            lines.append(f"rollback target: build {previous.get('provenance', {}).get('build_id')}")
        except (OSError, ValueError):
            lines.append("rollback target: present but unreadable")
    else:
        lines.append("rollback target: none")

    try:
        url = _health_check_url(paths)
    except PermissionError:
        lines.append("configuration unreadable (run as root to check health)")
        url = None
    healthy = False
    if url is not None:
        healthy, message = health_checker(url)
        lines.append(f"health check: {message}")
    return StatusReport(lines=tuple(lines), healthy=healthy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "artifact_dir", type=Path, nargs="?",
        help="directory produced by scripts/build_camera_node_artifact.py",
    )
    parser.add_argument("--status", action="store_true", help="read-only report; makes no changes")
    parser.add_argument("--rollback", action="store_true", help="swap back to the previously installed version")
    parser.add_argument(
        "--enable-hardware-watchdog", action="store_true",
        help=(
            "opt in to systemd's own OS-hang recovery via an already-present "
            "/dev/watchdog device; never edits boot configuration itself -- "
            "see 'Hardware watchdog' in docs/camera-node-installer-design.md"
        ),
    )
    parser.add_argument(
        "--export-config", type=Path, default=None, metavar="PATH",
        help="read-only: write the current node.env's portable settings to PATH as a backup bundle",
    )
    parser.add_argument(
        "--import-config", type=Path, default=None, metavar="PATH",
        help=(
            "restore node.env from a bundle written by --export-config; only ever "
            "materializes node.env when one does not already exist, same as a fresh "
            "install -- combine with artifact_dir to restore during install, or use alone "
            "on an already-installed node"
        ),
    )
    parser.add_argument("--prefix", type=Path, default=Path("/"), help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    paths = InstallPaths(prefix=arguments.prefix)

    try:
        if arguments.enable_hardware_watchdog:
            print(enable_hardware_watchdog(paths))
            return
        if arguments.export_config is not None:
            if not _real_is_root():
                raise InstallerError("Exporting the configuration must be run as root (node.env is root-only).")
            bundle = export_node_config(paths)
            atomic_write_text(arguments.export_config, json.dumps(bundle, indent=2, sort_keys=True) + "\n", mode=0o600)
            print(f"Wrote configuration backup to {arguments.export_config} (bundle_version {bundle['bundle_version']}).")
            return
        if arguments.status:
            report = status(paths=paths)
            print("\n".join(report.lines))
            return
        if arguments.rollback:
            result = rollback(paths=paths)
        elif arguments.artifact_dir is None:
            if arguments.import_config is not None:
                if not _real_is_root():
                    raise InstallerError("Importing the configuration must be run as root.")
                print(import_node_config_if_absent(arguments.import_config, paths))
                return
            parser.error(
                "artifact_dir is required unless --status, --rollback, --export-config, "
                "or a standalone --import-config is given"
            )
        else:
            result = install(artifact_dir=arguments.artifact_dir, paths=paths, import_config_path=arguments.import_config)
        for step in result.steps:
            print(f"- {step}")
        if not result.healthy:
            print(f"WARNING: {result.health_message}", file=sys.stderr)
            raise SystemExit(1)
        print("Camera Node install/update complete and healthy.")
    except InstallerError as error:
        print(f"Camera Node installer error: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
