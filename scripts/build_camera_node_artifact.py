"""Build a deterministic, slim Camera Node wheel without the main application."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import tomllib
from typing import Sequence
import zipfile


ROOT = Path(__file__).resolve().parents[1]
NODE_PACKAGE = ROOT / "src" / "mockingbird_node"
#: Pre-Release Trust & Correctness Correction v1 (PKG-2): `docs/camera-node-
#: install-guide.md`'s own step 2 tells the user to run this script against
#: the artifact directory, but it was never actually packaged into that
#: directory -- a real downloaded/rebuilt artifact could not be installed
#: from itself, only from a full repository checkout. Shipped alongside the
#: wheel/manifest/checksums below, not inside the wheel (the installer runs
#: *before* any Python environment exists to `pip install` into).
INSTALLER_SCRIPT = ROOT / "scripts" / "install_camera_node.py"
#: The complete transitive import closure of `app.py`/`__main__.py`, verified
#: by `test_node_files_cover_the_real_internal_import_closure` (a fast,
#: static AST check -- no venv/pip needed) rather than trusted by hand a
#: second time. Camera Node Upgrade & Compatibility Recovery v1: this list
#: was missing `atomic_io.py`/`transport_client.py`/`transport_credential.py`/
#: `transport_log.py`/`transport_spool.py`/`transport_worker.py` -- added by
#: Remote / Intermittent-WAN Transport Foundation v1 (`bf7ba27`) without a
#: matching `NODE_FILES` update, the identical class of gap Camera Node Boot
#: Identity + Autonomous Recovery v1 already found and fixed once for
#: `identity.py`/`selftest.py`/`watchdog.py`. Confirmed by direct reproduction
#: (not merely inferred): a real venv install of the pre-fix wheel raised
#: `ModuleNotFoundError: No module named 'mockingbird_node.transport_client'`
#: at `python -m mockingbird_node` startup -- every fresh install *and* every
#: upgrade using the pre-fix builder was completely broken. See "Existing
#: state" in docs/camera-node-upgrade-compatibility-recovery-v1-report.md.
#: Release Reliability & First-Run Recovery v1: `hardware_health.py` (new)
#: hit the identical class of gap a third time -- caught by this same test
#: before landing, not shipped and discovered later like the two instances
#: above.
NODE_FILES = (
    "__init__.py",
    "__main__.py",
    "app.py",
    "atomic_io.py",
    "config.py",
    "hardware_health.py",
    "identity.py",
    "providers.py",
    "selftest.py",
    "transport_client.py",
    "transport_credential.py",
    "transport_log.py",
    "transport_spool.py",
    "transport_worker.py",
    "watchdog.py",
)
RUNTIME_REQUIREMENTS = (
    "fastapi>=0.111,<0.116",
    "pydantic>=2.7,<3.0",
    "uvicorn[standard]>=0.30,<1.0",
)
#: This builder's entire input surface: it reads exactly these eight files by
#: fixed name (`NODE_FILES`, never a directory glob), so an untracked stray
#: file under `src/mockingbird_node/` was already structurally unable to
#: enter the wheel -- unlike `scripts/build_local_product.py`'s `pip wheel .`
#: (which sweeps a whole directory and needed a `git archive` clean-tree
#: export to close that class of leak). Only the narrower "uncommitted edit
#: to an already-tracked file" ambiguity needs a reproducibility guard here.
#: See "Reproducibility hardening" in docs/camera-node-installer-design.md.
#: Includes `scripts/install_camera_node.py` (PKG-2): it now ships alongside
#: the wheel (see `INSTALLER_SCRIPT`), so it is as much a build input as
#: `src/mockingbird_node` and deserves the identical clean-commit guarantee.
RELEASE_SOURCE_PATHS: tuple[str, ...] = ("src/mockingbird_node", "scripts/install_camera_node.py")


class CameraNodeArtifactError(RuntimeError):
    """Raised when the artifact cannot be built reproducibly from a known source state."""


@dataclass(frozen=True)
class CameraNodeArtifact:
    wheel: Path
    requirements: Path
    configuration_example: Path
    installer: Path
    manifest: Path
    checksums: Path


def verify_clean_camera_node_source(
    *, paths: Sequence[str] = RELEASE_SOURCE_PATHS, cwd: Path = ROOT,
) -> str:
    """Prove the exact wheel inputs match a real git commit, with no
    uncommitted edit sitting unreviewed on top of it. Returns the resolved
    commit hash a clean build is taken from.

    Mirrors `build_local_product.verify_clean_tracked_source` at a scope
    proportionate to this builder's own narrower, fixed-file-list input
    surface -- see `RELEASE_SOURCE_PATHS` above. Deliberately checks
    `git diff` (working tree vs. `HEAD`) rather than `git status`: this
    builder never globs a directory, so an untracked file is not an
    ambiguity it needs to resolve at all.
    """

    completed = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", *paths],
        cwd=cwd, check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise CameraNodeArtifactError(
            f"Could not verify source cleanliness with git: {completed.stderr.strip()}"
        )
    dirty = completed.stdout.strip()
    if dirty:
        changed = ", ".join(dirty.splitlines())
        raise CameraNodeArtifactError(
            "Refusing to build a Camera Node artifact: uncommitted changes exist in "
            f"tracked packaged-input files ({changed}). Commit them first, or pass "
            "--allow-dirty-source for a local/development build only -- never for a "
            "release artifact."
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cwd, check=False, capture_output=True, text=True,
    )
    if head.returncode != 0 or not head.stdout.strip():
        raise CameraNodeArtifactError(
            f"Could not resolve the current git commit for a clean release build: {head.stderr.strip()}"
        )
    return head.stdout.strip()


def _current_head_commit(*, cwd: Path = ROOT) -> str | None:
    """Best-effort HEAD commit for an `--allow-dirty-source` build, which by
    definition has no *verified* clean commit the way
    `verify_clean_camera_node_source` proves for a real release build.
    Never raises: a build host with no git history at all simply gets
    `None`, an honest "unknown" rather than a build failure over a
    provenance nicety.
    """

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cwd, check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return completed.stdout.strip()


#: Camera Node Upgrade & Compatibility Recovery v1: a candidate artifact's
#: own wire-protocol identity, so `scripts/install_camera_node.py` can
#: compare a candidate against the currently-installed build *without*
#: importing/executing either wheel (this builder stays stdlib-only -- see
#: the module docstring) and without a live network call to any Host (the
#: Node has no configured Host address to call -- see "Compatibility" in
#: docs/camera-node-upgrade-compatibility-recovery-v1-report.md). A plain
#: literal-assignment regex over source already read into `files` below,
#: never an import: `NODE_API_VERSION`/`TRANSPORT_PROTOCOL_VERSION` are
#: always simple `NAME = "value"` module constants (see `mockingbird_node.
#: app`/`mockingbird_node.transport_client`) -- if a future edit ever makes
#: that untrue, this fails loudly at build time rather than silently
#: shipping a manifest with a missing/wrong protocol fact.
_VERSION_LITERAL_PATTERN = r'^{name}\s*=\s*"([^"]+)"\s*$'


def _extract_version_literal(source: bytes, name: str) -> str:
    match = re.search(_VERSION_LITERAL_PATTERN.format(name=re.escape(name)), source.decode("utf-8"), re.MULTILINE)
    if match is None:
        raise CameraNodeArtifactError(
            f"Could not find a `{name} = \"...\"` literal to record this artifact's protocol provenance. "
            "This builder reads it via a plain text pattern, not an import, so a renamed or restructured "
            "constant needs this pattern updated too."
        )
    return match.group(1)


def _source_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_digest(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
    return f"sha256={digest}"


def _write_zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (2026, 1, 1, 0, 0, 0)
    info.external_attr = 0o644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def _metadata(version: str) -> bytes:
    lines = [
        "Metadata-Version: 2.3",
        "Name: mockingbird-camera-node",
        f"Version: {version}",
        "Summary: Local-only bounded MockingBird Camera Node.",
        "Requires-Python: >=3.11",
        *(f"Requires-Dist: {requirement}" for requirement in RUNTIME_REQUIREMENTS),
        "",
    ]
    return "\n".join(lines).encode()


def _configuration_example() -> bytes:
    return (
        b"# Local-only MockingBird Camera Node configuration\n"
        b"MOCKINGBIRD_NODE_NAME=Pi Camera Node\n"
        b"MOCKINGBIRD_NODE_BIND=0.0.0.0\n"
        b"MOCKINGBIRD_NODE_PORT=8787\n"
        b"MOCKINGBIRD_NODE_PROVIDERS=picamera2,v4l2\n"
        b"MOCKINGBIRD_NODE_MAX_IMAGE_BYTES=1500000\n"
        b"MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=1920\n"
        b"MOCKINGBIRD_NODE_MAX_IMAGE_HEIGHT=1080\n"
        b"# Optional bounded evidence still; monitoring remains 1920x1080.\n"
        b"MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_BYTES=16000000\n"
        b"MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH=10000\n"
        b"MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_HEIGHT=8000\n"
        b"MOCKINGBIRD_NODE_PAIRING_TTL_SECONDS=600\n"
        b"# Persists a hash verifier only, so an existing pairing survives a restart.\n"
        b"# MOCKINGBIRD_NODE_PAIRING_STATE_PATH=/home/pi/.local/state/mockingbird-camera-node/pairing.json\n"
        b"MOCKINGBIRD_NODE_MAX_PREVIEW_VIEWERS=2\n"
        b"# Synthetic is intentionally omitted: it is test-only.\n"
    )


def build_camera_node_artifact(
    output_dir: Path,
    *,
    source_state: str | None = None,
    allow_dirty_source: bool = False,
) -> CameraNodeArtifact:
    """Write a standalone wheel and deployment metadata with no application files.

    By default (`allow_dirty_source=False`, the only mode a real release
    should ever use) this refuses to build unless `src/mockingbird_node`
    matches a real, clean git commit -- see `verify_clean_camera_node_source`.
    `allow_dirty_source=True` exists only for iterating on this build script
    itself against uncommitted local edits, or a build host with no git
    history at all. `source_state`, when given, overrides only the derived
    human-readable label; it never overrides the independently-computed
    `provenance` facts written into `manifest.json`.
    """

    version = _source_version()
    if allow_dirty_source:
        commit = _current_head_commit()
        source_clean = False
        resolved_source_state = source_state or "dirty:unverified-working-tree"
    else:
        commit = verify_clean_camera_node_source()
        source_clean = True
        resolved_source_state = source_state or f"git:{commit}"

    normalized_name = "mockingbird_camera_node"
    distribution = f"{normalized_name}-{version}"
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {f"mockingbird_node/{name}": (NODE_PACKAGE / name).read_bytes() for name in NODE_FILES}
    node_api_version = _extract_version_literal(files["mockingbird_node/app.py"], "NODE_API_VERSION")
    transport_protocol_version = _extract_version_literal(
        files["mockingbird_node/transport_client.py"], "TRANSPORT_PROTOCOL_VERSION"
    )
    dist_info = f"{distribution}.dist-info"
    files[f"{dist_info}/METADATA"] = _metadata(version)
    files[f"{dist_info}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: MockingBird Camera Node artifact builder\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    files[f"{dist_info}/entry_points.txt"] = b"[console_scripts]\nmockingbird-camera-node = mockingbird_node.__main__:main\n"

    wheel = output_dir / f"{distribution}-py3-none-any.whl"
    records = [f"{name},{_record_digest(data)},{len(data)}" for name, data in sorted(files.items())]
    files[f"{dist_info}/RECORD"] = ("\n".join(records + [f"{dist_info}/RECORD,,"]) + "\n").encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in sorted(files.items()):
            _write_zip_entry(archive, name, data)

    requirements = output_dir / "requirements.txt"
    requirements.write_text("\n".join(RUNTIME_REQUIREMENTS) + "\n", encoding="utf-8")
    configuration_example = output_dir / "camera-node.env.example"
    configuration_example.write_bytes(_configuration_example())
    installer = output_dir / INSTALLER_SCRIPT.name
    installer.write_bytes(INSTALLER_SCRIPT.read_bytes())
    manifest = output_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifact": wheel.name,
                "package": "mockingbird-camera-node",
                "source_state": resolved_source_state,
                # Structured, verifiable provenance alongside the human-readable
                # `source_state` label above -- `build_id` mirrors
                # `build_local_product.BuildIdentity.build_id`: a fresh random
                # token per *build invocation*, not per commit, so two
                # independent builds of the identical commit stay
                # distinguishable (the installer's update/idempotency logic
                # depends on this -- see "Update behavior" in
                # docs/camera-node-installer-design.md).
                "provenance": {
                    "git_commit": commit,
                    "source_clean": source_clean,
                    "build_id": secrets.token_hex(16),
                    "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
                },
                # Camera Node Upgrade & Compatibility Recovery v1: this
                # candidate's own wire-protocol identity -- see
                # `_extract_version_literal` above. Read by the installer's
                # upgrade preflight to compare a candidate against whatever
                # is currently installed (never a live Host call -- the Node
                # has no configured Host address). A pre-this-milestone
                # artifact's manifest simply lacks this key, which the
                # installer reads as "unknown," never as "incompatible."
                "protocol": {
                    "node_api_version": node_api_version,
                    "transport_protocol_version": transport_protocol_version,
                },
                "version": version,
                "runtime_requirements": list(RUNTIME_REQUIREMENTS),
                "wheel_contents": [
                    {"path": name, "sha256": _sha256(data), "size": len(data)}
                    for name, data in sorted(files.items())
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    checksums = output_dir / "SHA256SUMS"
    checksum_files = (wheel, requirements, configuration_example, installer, manifest)
    checksums.write_text(
        "".join(f"{_sha256(path.read_bytes())}  {path.name}\n" for path in checksum_files),
        encoding="utf-8",
    )
    return CameraNodeArtifact(wheel, requirements, configuration_example, installer, manifest, checksums)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--source-state",
        default=None,
        help="override the derived human-readable source label "
        "(default: git:<hash>, or dirty:unverified-working-tree with --allow-dirty-source)",
    )
    parser.add_argument(
        "--allow-dirty-source",
        action="store_true",
        help="build from the live working tree without a clean-git-commit guarantee -- "
        "local iteration only, never for a release artifact",
    )
    arguments = parser.parse_args()
    artifact = build_camera_node_artifact(
        arguments.output_dir,
        source_state=arguments.source_state,
        allow_dirty_source=arguments.allow_dirty_source,
    )
    print(artifact.wheel)


if __name__ == "__main__":
    main()
