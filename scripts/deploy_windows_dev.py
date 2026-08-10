"""Deploy MockingBird to a dedicated Windows development location, from WSL.

See docs/windows-dev-deployment-design.md for the full design this
implements. This is a developer-tooling script only -- it changes nothing
about how MockingBird itself behaves; it automates the previously-manual
"build a Windows artifact, copy it to Windows, extract it, launch it,
confirm it is actually the build under test" loop described there.

Usage (from a WSL checkout, on a machine with Windows/WSL interop):

    python scripts/deploy_windows_dev.py                  # build+deploy HEAD
    python scripts/deploy_windows_dev.py --commit <ref>    # a specific commit
    python scripts/deploy_windows_dev.py --artifact <path> # accept an already-built bundle/zip
    python scripts/deploy_windows_dev.py --rollback        # stop current, launch the previous release
    python scripts/deploy_windows_dev.py --keep 3          # cleanup: keep only the 3 most recent releases
    python scripts/deploy_windows_dev.py --status          # report the current dev deployment, no changes

Every deployment lands at a versioned, never-overwritten
``%LOCALAPPDATA%\\MockingBirdDev\\releases\\<git-short-sha>\\``. A single
shared ``userdata\\`` directory (never per-release) is reused across every
dev deployment and rollback, kept completely separate from a real
production install's own ``%LOCALAPPDATA%\\MockingBird`` -- Camera Node
pairings, reviewed Visits, and every other local fact a developer built up
while testing persist across redeploys and are never touched by this tool.

This script *reuses* ``scripts/build_local_product.py`` for every actual
packaging step (wheel build, embeddable-Python assembly, model/GPU-runtime
verification, manifest/checksum generation) -- it never re-implements or
bypasses any of that. What this script adds on top is Windows-side
deployment: versioned release directories, a content-addressed
runtime/model cache (so ordinary app-only iteration does not require
re-copying the ~1.9 GB CUDA/Python/model payload through the WSL/Windows
filesystem boundary on every deploy), launch, bounded-timeout build-identity
verification, safe stop-only-if-verified process management, rollback, and
bounded cleanup.

## Why HTTP/process/junction operations shell out to PowerShell

An early validation pass found that this sandboxed WSL2 environment's
loopback traffic from WSL directly to a Windows-bound TCP listener is not
reachable (neither ``127.0.0.1`` nor the WSL-reported default-route host IP
accepted a connection to a real Windows-side listener in that test) even
though plain Windows-native loopback (a Windows process talking to another
Windows process on ``127.0.0.1``) works normally. Rather than depend on
WSL2's bidirectional-localhost-forwarding configuration (which varies across
Windows/WSL versions and local network policy), every check that must
observe the real running Windows process -- HTTP health/identity polling,
port-owner PID lookup, process liveness/kill, junction creation -- runs as a
*Windows-native* PowerShell process, invoked through the same WSL/Windows
interop already used to launch the app itself. This is also simply more
representative: it is the same vantage point a real user's double-click
launch is observed from.

All of that lives behind the `WindowsHost` seam below; every orchestration
function above it takes a `WindowsHost` and is otherwise pure/hermetic, the
same injectable-dependency pattern `build_local_product.py` already uses for
its own real-vs-test installers (`install_dependencies`,
`install_gpu_dependencies`). The test suite never shells out to a real
`powershell.exe` or touches a real Windows filesystem; it supplies an
entirely in-memory fake `WindowsHost` that a temp POSIX directory tree
stands in for.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterable, Sequence
import zipfile


ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Reuse scripts/build_local_product.py -- never duplicate packaging logic.
#
# `scripts/` is deliberately not a package (matching the rest of this
# directory: build_camera_node_artifact.py/build_local_product.py are each
# freestanding scripts), so this loads it the same way the existing test
# suite already does (`runpy.run_path`, see tests/test_local_product_
# packaging.py) rather than manipulating sys.path. Cached at module level:
# this script only ever needs one real load per process.
# ---------------------------------------------------------------------------

_build_local_product_module: dict[str, object] | None = None


def _blp() -> dict[str, object]:
    global _build_local_product_module
    if _build_local_product_module is None:
        _build_local_product_module = runpy.run_path(str(ROOT / "scripts" / "build_local_product.py"))
    return _build_local_product_module


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sibling of the real production `%LOCALAPPDATA%\MockingBird` (see
# `mockingbird.runtime.resolve_runtime_home`) -- never the same directory.
# Everything this tool ever writes to a real Windows filesystem lives under
# this one root, so "never touch the real MockingBird user-data directory"
# is a structural property, not a per-call discipline.
DEV_ROOT_DIRNAME = "MockingBirdDev"
RELEASES_DIRNAME = "releases"
RUNTIME_CACHE_DIRNAME = "runtime"
MODEL_CACHE_DIRNAME = "models"
# One directory, shared and reused by *every* dev deployment and rollback
# regardless of git sha -- never per-release. This is what makes "never
# reset/re-pair Camera Nodes" and "never modify Visits/reviews/truth" true
# by construction: the dev app's own data directory simply never changes
# out from under it just because the running code was redeployed.
USERDATA_DIRNAME = "userdata"

DEPLOYMENTS_LEDGER_FILENAME = "deployments.json"
CURRENT_POINTER_FILENAME = "current.json"
RELEASE_INFO_FILENAME = "release_info.json"
CACHE_MANIFEST_FILENAME = "cache_manifest.json"

DEFAULT_PORT = 8000
DEFAULT_HOST = "127.0.0.1"
DEFAULT_VERIFY_TIMEOUT_SECONDS = 90.0
DEFAULT_KEEP = 5

# A `site-packages` top-level entry belongs to the small, always-fresh "app
# tier" (never cached/junctioned) exactly when its name is this or starts
# with this followed by `-` (`mockingbird`, `mockingbird-0.1.0.dist-info`,
# a hypothetical `mockingbird-0.1.0.data`). Every *other* top-level
# `site-packages` entry -- every third-party dependency -- belongs to the
# large, content-addressed, cross-release-shared "runtime tier".
APP_TIER_PACKAGE_NAME = "mockingbird"

# Recorded as a model-tier hash when a build did not package a model bundle
# at all (`ModelBundleProvenance.included=False`) -- an explicit, honest
# value rather than an empty string or `None` threaded through cache
# bookkeeping that expects a hash-shaped key.
NO_MODEL_BUNDLE_HASH = "no-model-bundle-packaged"


class DeploymentError(RuntimeError):
    """Raised when a deployment step fails, or a safety check refuses to
    proceed. Every raise site's message is written to be printed directly
    to an operator -- concise and actionable, per this tool's own
    'if verification fails, report exactly why' requirement."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseSource:
    """The bundle to deploy, plus the identity it claims -- either just
    built by `build_local_product.py` (`build_release_source`), or an
    already-built artifact accepted as-is (`accept_release_source`; task
    requirement: 'build or accept an already-built artifact'). Either way,
    every deploy proceeds from one of these, never from a guess."""

    bundle_dir: Path
    git_commit: str | None
    build_id: str | None
    app_version: str
    source_state: str


@dataclass(frozen=True)
class CachePopulationResult:
    cache_dir: Path
    content_hash: str
    reused: bool


@dataclass(frozen=True)
class MaterializedRelease:
    release_dir: Path
    runtime_hash: str
    model_hash: str
    junctioned_relative_paths: tuple[str, ...]
    bytes_copied: int


@dataclass(frozen=True)
class ReleaseRecord:
    """One entry in the deployment ledger (`deployments.json`) -- the
    durable, append-only record `--rollback`/`--cleanup`/process-safety all
    read back, rather than re-deriving deploy history from directory
    timestamps or guessing from folder names."""

    sha: str
    full_commit: str | None
    build_id: str | None
    app_version: str | None
    runtime_hash: str
    model_hash: str
    deployed_at: str
    junctioned_relative_paths: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "sha": self.sha,
            "full_commit": self.full_commit,
            "build_id": self.build_id,
            "app_version": self.app_version,
            "runtime_hash": self.runtime_hash,
            "model_hash": self.model_hash,
            "deployed_at": self.deployed_at,
            "junctioned_relative_paths": list(self.junctioned_relative_paths),
        }

    @staticmethod
    def from_dict(payload: dict[str, object]) -> "ReleaseRecord":
        return ReleaseRecord(
            sha=str(payload["sha"]),
            full_commit=payload.get("full_commit"),  # type: ignore[arg-type]
            build_id=payload.get("build_id"),  # type: ignore[arg-type]
            app_version=payload.get("app_version"),  # type: ignore[arg-type]
            runtime_hash=str(payload.get("runtime_hash", "")),
            model_hash=str(payload.get("model_hash", "")),
            deployed_at=str(payload.get("deployed_at", "")),
            junctioned_relative_paths=tuple(payload.get("junctioned_relative_paths", []) or []),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class CurrentPointer:
    """Which release this tool itself most recently started, and the PID it
    saw for it -- the seed fact process-safety cross-checks against a live
    identity re-read before ever stopping anything (see `verified_running_
    deployment`). Never trusted alone."""

    sha: str
    pid: int | None
    port: int

    def as_dict(self) -> dict[str, object]:
        return {"sha": self.sha, "pid": self.pid, "port": self.port}

    @staticmethod
    def from_dict(payload: dict[str, object]) -> "CurrentPointer":
        pid = payload.get("pid")
        return CurrentPointer(
            sha=str(payload["sha"]),
            pid=int(pid) if isinstance(pid, int) else None,
            port=int(payload.get("port", DEFAULT_PORT)),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason: str
    reported_git_commit: str | None = None
    reported_build_id: str | None = None
    reported_instance_id: str | None = None
    executable_path: str | None = None
    pid: int | None = None


@dataclass(frozen=True)
class DeployReport:
    sha: str
    release_dir_windows: str
    pid: int | None
    url: str
    previous_release_sha: str | None
    verification: VerificationResult

    def render(self) -> str:
        lines = [
            f"DEPLOYED {self.sha}",
            f"Runtime: {self.release_dir_windows}",
            f"Process: {self.pid if self.pid is not None else '(unknown)'}",
            f"URL: {self.url}",
        ]
        if self.previous_release_sha:
            lines.append(f"Previous release: {self.previous_release_sha}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Git identity (requirement 1: verify the requested/source commit)
# ---------------------------------------------------------------------------


def resolve_commit(ref: str, *, cwd: Path) -> str:
    """The full 40-character commit hash `ref` (default `HEAD`) names right
    now. Raises `DeploymentError` -- never silently falls back -- if `ref`
    does not resolve, so a typo'd `--commit` fails before any build work
    starts rather than deploying the wrong thing."""

    completed = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=cwd, check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise DeploymentError(
            f"Could not resolve {ref!r} to a git commit in {cwd}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def short_sha(commit: str, *, cwd: Path) -> str:
    """Git's own short form for `commit` (matching what a developer would
    already see with `git log --oneline`/`git status`) -- the release
    directory name. `--short=7` pins a fixed width so directory names stay
    predictable rather than growing as the repository does."""

    completed = subprocess.run(
        ["git", "rev-parse", "--short=7", commit],
        cwd=cwd, check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise DeploymentError(f"Could not compute a short sha for {commit} in {cwd}: {completed.stderr.strip()}")
    return completed.stdout.strip()


# ---------------------------------------------------------------------------
# Build or accept an already-built artifact (requirement 2)
# ---------------------------------------------------------------------------


def build_release_source(
    *,
    repo_root: Path,
    commit_ref: str,
    build_output_dir: Path,
    skip_gpu_runtime: bool = False,
    model_bundle_source: Path | None = None,
    wheel_cache_dir: Path | None = None,
) -> ReleaseSource:
    """Build a fresh artifact for `commit_ref` via `build_local_product.py`,
    never bypassing its clean-source-snapshot requirement, model
    provenance/CUDA-DLL-closure verification, or manifest/checksum
    generation -- this only ever calls that module's own public functions.

    `build_output_dir` **must** already be absolute: `build_local_product`
    itself now resolves it defensively (see its own docstring), but this
    caller resolves it too so a relative path can never silently mean two
    different directories to the build subprocess and to this process (the
    exact defect this guards against; see docs/windows-dev-deployment-design.md).
    """

    if not build_output_dir.is_absolute():
        raise DeploymentError(f"build_output_dir must be absolute, got {build_output_dir}")

    module = _blp()
    # Resolve *before* building: build_local_product builds whatever HEAD
    # currently is, so this deploy tool independently confirms `commit_ref`
    # names the exact commit that is about to become HEAD's build input --
    # never a guess about what "the requested commit" ended up meaning.
    requested_commit = resolve_commit(commit_ref, cwd=repo_root)
    current_head = resolve_commit("HEAD", cwd=repo_root)
    if requested_commit != current_head:
        raise DeploymentError(
            f"--commit {commit_ref} resolves to {requested_commit[:12]}, but the repository's "
            f"checked-out HEAD is {current_head[:12]}. Check out {commit_ref} first (this tool "
            "never builds a commit that is not actually checked out -- build_local_product.py "
            "always builds from the working tree/index at HEAD)."
        )

    build_local_product = module["build_local_product"]
    artifact = build_local_product(
        build_output_dir,
        include_gpu_runtime=not skip_gpu_runtime,
        model_bundle_source=(
            model_bundle_source if model_bundle_source is not None else module["DEFAULT_MODEL_BUNDLE_SOURCE"]
        ),
        wheel_cache_dir=(
            wheel_cache_dir if wheel_cache_dir is not None else module["DEFAULT_WHEEL_CACHE_DIR"]
        ),
        allow_dirty_source=False,
    )
    identity = artifact.build_identity
    return ReleaseSource(
        bundle_dir=artifact.bundle_dir,
        git_commit=identity.git_commit,
        build_id=identity.build_id,
        app_version=identity.app_version,
        source_state=f"git:{identity.git_commit}" if identity.git_commit else "unknown",
    )


def accept_release_source(artifact_path: Path) -> ReleaseSource:
    """Accept an already-built artifact instead of building one now
    (requirement 2). `artifact_path` may be a bundle *directory* (as
    `build_local_product.py` leaves it before zipping) or a `.zip` of one
    (extracted into a temp staging directory). Either way, this reads the
    build identity `write_build_identity` already placed inside the bundle
    -- never re-derives or guesses it -- so an accepted artifact is
    identified exactly as reliably as a freshly built one."""

    module = _blp()
    bundle_dir = artifact_path
    if artifact_path.is_file() and artifact_path.suffix == ".zip":
        staging = Path(tempfile.mkdtemp(prefix="mockingbird-deploy-artifact-"))
        with zipfile.ZipFile(artifact_path) as archive:
            archive.extractall(staging)
        entries = [entry for entry in staging.iterdir() if entry.is_dir()]
        if len(entries) != 1:
            raise DeploymentError(
                f"Expected exactly one top-level folder inside {artifact_path}, found {len(entries)}."
            )
        bundle_dir = entries[0]
    elif not artifact_path.is_dir():
        raise DeploymentError(f"--artifact {artifact_path} is neither a bundle directory nor a .zip file.")

    build_info_path = bundle_dir / "python" / "site-packages" / APP_TIER_PACKAGE_NAME / module["PACKAGED_BUILD_INFO_FILENAME"]
    if not build_info_path.is_file():
        raise DeploymentError(
            f"{artifact_path} has no {build_info_path.name} -- it was not built by this "
            "checkout's scripts/build_local_product.py (or predates build-identity support). "
            "Rebuild it before deploying."
        )
    try:
        payload = json.loads(build_info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DeploymentError(f"Could not read build identity from {build_info_path}: {error}") from error

    git_commit = payload.get("git_commit")
    if not isinstance(git_commit, str) or not git_commit:
        raise DeploymentError(
            f"{build_info_path} has no recorded git_commit -- it was likely built with "
            "--allow-dirty-source against a host with no git history. Refusing to deploy an "
            "artifact whose source commit cannot be verified."
        )
    return ReleaseSource(
        bundle_dir=bundle_dir,
        git_commit=git_commit,
        build_id=payload.get("build_id") if isinstance(payload.get("build_id"), str) else None,
        app_version=str(payload.get("app_version", "unknown")),
        source_state=f"git:{git_commit}",
    )


# ---------------------------------------------------------------------------
# Runtime/model/app tier split and cryptographic hashing
#
# See docs/windows-dev-deployment-design.md "Runtime/model cache" for the
# full design. Three tiers, split purely by *where* a file lives inside the
# bundle `build_local_product.py` already produces -- nothing about
# packaging itself changes:
#
# - "app" tier: `python/site-packages/mockingbird` (minus the nested
#   `observation_runtime/` model bundle) and `mockingbird-*.dist-info` --
#   small, changes on every commit, always copied fresh into each release,
#   never cached or shared.
# - "model" tier: `python/site-packages/mockingbird/observation_runtime/`
#   -- the packaged MDv5 ONNX model + provider config. Changes only when
#   the accepted model changes.
# - "runtime" tier: everything else under `python/` -- the embeddable
#   CPython distribution plus every third-party dependency, including the
#   ~1.3 GB ONNX Runtime GPU/CUDA/cuDNN stack. Changes only when
#   `EMBED_PYTHON_VERSION` or a pinned dependency version changes.
# ---------------------------------------------------------------------------


def is_app_tier_entry(name: str) -> bool:
    """True for a `site-packages` top-level entry that belongs to
    MockingBird's own installed package (`mockingbird`,
    `mockingbird-0.1.0.dist-info`, a hypothetical `mockingbird-0.1.0.data`)
    -- the only entries copied fresh into every release rather than cached
    and shared."""

    return name == APP_TIER_PACKAGE_NAME or name.startswith(f"{APP_TIER_PACKAGE_NAME}-")


def _model_bundle_dir(bundle_dir: Path) -> Path:
    module = _blp()
    return (
        bundle_dir / "python" / "site-packages" / APP_TIER_PACKAGE_NAME
        / module["PACKAGED_OBSERVATION_RUNTIME_DIRNAME"]
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _combined_hash(entries: Iterable[tuple[str, str, int]]) -> str:
    """One deterministic digest over a set of (relative_path, file_sha256,
    size) facts -- sorted first so hashing is independent of filesystem
    iteration order. Any content change anywhere in the input, a missing
    file, an extra file, or a size change all produce a different result;
    identical bytes always produce the same one, which is the entire basis
    for content-addressed cache reuse below."""

    digest = hashlib.sha256()
    for relative_path, file_hash, size in sorted(entries):
        digest.update(f"{relative_path}\0{file_hash}\0{size}\n".encode("utf-8"))
    return digest.hexdigest()


def _is_under_app_tier(relative_to_python_dir: Path) -> bool:
    parts = relative_to_python_dir.parts
    return len(parts) >= 2 and parts[0] == "site-packages" and is_app_tier_entry(parts[1])


def _runtime_tier_files(bundle_dir: Path) -> list[Path]:
    """Every file under `python/` except the app package (and, nested
    inside it, the model bundle) -- the exact file set both
    `compute_runtime_hash` and `ensure_runtime_cache` operate on, kept as
    one shared list so hashing, stats, and copying can never drift apart."""

    python_dir = bundle_dir / "python"
    return sorted(
        path
        for path in python_dir.rglob("*")
        if path.is_file() and not _is_under_app_tier(path.relative_to(python_dir))
    )


def _model_tier_files(bundle_dir: Path) -> list[Path]:
    """Every file under `mockingbird/observation_runtime/`, or `[]` if this
    build did not package a model bundle at all -- shared between
    `compute_model_hash` and `ensure_model_cache` for the same reason as
    `_runtime_tier_files`."""

    model_dir = _model_bundle_dir(bundle_dir)
    if not model_dir.is_dir():
        return []
    return sorted(path for path in model_dir.rglob("*") if path.is_file())


def compute_runtime_hash(bundle_dir: Path) -> str:
    """Cryptographic content hash of the runtime tier: every file under
    `python/` except the app package (and, nested inside it, the model
    bundle -- hashed separately by `compute_model_hash`)."""

    python_dir = bundle_dir / "python"
    files = _runtime_tier_files(bundle_dir)
    if not files:
        raise DeploymentError(f"No runtime-tier files found under {python_dir} -- is this a real build output?")
    return _combined_hash((f.relative_to(python_dir).as_posix(), _hash_file(f), f.stat().st_size) for f in files)


def compute_model_hash(bundle_dir: Path) -> str:
    """Cryptographic content hash of the model tier
    (`mockingbird/observation_runtime/`), or `NO_MODEL_BUNDLE_HASH` if this
    build did not package a model bundle at all -- an explicit, honest
    sentinel rather than an empty/`None` hash threaded through cache
    bookkeeping that otherwise always expects a real hash string."""

    model_dir = _model_bundle_dir(bundle_dir)
    files = _model_tier_files(bundle_dir)
    if not files:
        return NO_MODEL_BUNDLE_HASH
    return _combined_hash((f.relative_to(model_dir).as_posix(), _hash_file(f), f.stat().st_size) for f in files)


@dataclass(frozen=True)
class HttpProbe:
    """The result of one bounded HTTP GET against the Windows-deployed
    instance -- see the module docstring for why this always runs as a
    Windows-native process rather than a direct WSL socket call."""

    ok: bool
    status: int | None = None
    json_body: dict | None = None
    error: str | None = None


@dataclass(frozen=True)
class WindowsHost:
    """Every operation that touches a real Windows filesystem path, the
    Windows process table, or the Windows network stack -- one injectable
    seam (mirrors `build_local_product.py`'s own `install_dependencies`/
    `install_gpu_dependencies` pattern) so every function above this stays
    hermetic and fast under test. `real_windows_host()` below is the only
    production implementation; tests always supply a `fake_windows_host()`
    (see tests/test_deploy_windows_dev.py) backed by a plain temp directory
    tree, never a real `powershell.exe` or a real Windows path.

    Every path parameter/return value here is WSL-visible (a normal POSIX
    path, typically under `/mnt/c/...` for anything really on Windows) --
    translation to a Windows-style path string happens only at the last
    moment, inside each real implementation, via `to_windows_path`.
    """

    local_appdata: Callable[[], Path]
    to_windows_path: Callable[[Path], str]
    ensure_dir: Callable[[Path], None]
    copy_file: Callable[[Path, Path], None]
    rename: Callable[[Path, Path], None]
    make_junction: Callable[[Path, Path], None]
    remove_junction: Callable[[Path], None]
    remove_tree: Callable[[Path], None]
    launch_release: Callable[[Path, dict[str, str]], None]
    http_get: Callable[[str, float], HttpProbe]
    port_owner_pid: Callable[[int], "int | None"]
    process_alive: Callable[[int], bool]
    process_image_path: Callable[[int], "str | None"]
    kill_process: Callable[[int], None]


# ---------------------------------------------------------------------------
# Immutable, versioned, content-addressed cache population
# ---------------------------------------------------------------------------


def _write_cache_manifest(path: Path, *, content_hash: str, file_count: int, total_bytes: int) -> None:
    path.write_text(
        json.dumps(
            {
                "content_hash": content_hash,
                "file_count": file_count,
                "total_bytes": total_bytes,
                "cached_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _cache_directory_matches(cache_dir: Path, *, content_hash: str, file_count: int, total_bytes: int) -> bool:
    """Whether an existing `cache_dir` genuinely, currently holds
    `file_count` files totaling `total_bytes` under the claimed
    `content_hash` -- checked two ways, both required:

    1. its own recorded manifest claims exactly that;
    2. a fresh count of what is *actually, currently* sitting in
       `cache_dir` right now matches too.

    Check 1 alone is not enough: a manifest file records what was true the
    moment the entry was written, but proves nothing about whether the
    directory around it was later tampered with, partially deleted, or
    corrupted by a filesystem error -- exactly the gap a first version of
    this function had (it compared the fresh source bundle's expected
    stats only against the cache's own *stored claim*, never against the
    cache directory's actual current contents, so a stale-but-untouched
    manifest sitting next to quietly-deleted files was wrongly trusted).
    This still never re-hashes the cached content byte-for-byte on every
    reuse (see `ensure_cache`'s own docstring for why) -- counting files
    and summing sizes is a cheap structural check, not the expensive one.
    """

    manifest_path = cache_dir / CACHE_MANIFEST_FILENAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    if (
        payload.get("content_hash") != content_hash
        or payload.get("file_count") != file_count
        or payload.get("total_bytes") != total_bytes
    ):
        return False

    actual_file_count = 0
    actual_total_bytes = 0
    for path in cache_dir.rglob("*"):
        if path.is_file() and path != manifest_path:
            actual_file_count += 1
            actual_total_bytes += path.stat().st_size
    return actual_file_count == file_count and actual_total_bytes == total_bytes


def _copy_files_preserving_structure(
    files: Sequence[Path], *, relative_root: Path, destination: Path, windows_host: WindowsHost,
) -> None:
    """Copy exactly `files` (every path already known relative to
    `relative_root`) into `destination`, preserving their relative
    directory structure. The population half of the hash/stats/copy
    consistency `ensure_runtime_cache`/`ensure_model_cache` depend on: the
    same `files` list this was given is always exactly what
    `compute_runtime_hash`/`compute_model_hash` hashed and what
    `_tier_stats` counted -- there is structurally no way for what gets
    copied into a cache entry to drift from what its own hash/manifest
    claims."""

    windows_host.ensure_dir(destination)
    created_dirs = {destination}
    for source in files:
        target = destination / source.relative_to(relative_root)
        if target.parent not in created_dirs:
            windows_host.ensure_dir(target.parent)
            created_dirs.add(target.parent)
        windows_host.copy_file(source, target)


def ensure_cache(
    *,
    populate: Callable[[Path], None],
    content_hash: str,
    expected_file_count: int,
    expected_total_bytes: int,
    cache_root: Path,
    windows_host: WindowsHost,
) -> CachePopulationResult:
    """Populate `<cache_root>/<content_hash>/` by calling
    `populate(staging_dir)` if it is not already there with a manifest
    matching `content_hash`/`expected_file_count`/`expected_total_bytes`,
    or reuse it untouched if it already is.

    Content-addressed by construction: a different hash always means a
    different directory name, so "automatic reuse only when hashes match"
    and "safe rebuild when runtime/model versions change" both fall
    directly out of the naming scheme rather than needing separate
    comparison logic. An existing directory at the expected hash-named path
    that does *not* match its own recorded manifest (corrupted, tampered,
    or from an interrupted run predating the atomic-rename fix below) is
    never trusted just because its name matches -- it is rebuilt fresh, the
    same as a genuine cache miss, but never by deleting the old entry *in
    place*: it is renamed out of the way first (a same-volume rename does
    not require closing any file handle already open inside it, unlike
    deletion), so a release currently running with files open straight out
    of this exact path is never disturbed and the trusted path itself is
    never left in a partially-deleted state -- see the real incident this
    fixed in docs/windows-dev-deployment-design.md's "Real end-to-end
    findings".

    Reuse only re-verifies a cheap structural fact (file count/total bytes
    against the manifest `_write_cache_manifest` recorded when the entry
    was created) rather than re-hashing a multi-gigabyte cached tree's
    content on every single deploy, which would defeat the entire purpose
    of caching. The expensive, real cryptographic hash is always computed
    fresh on the *source* side by the caller (`compute_runtime_hash`/
    `compute_model_hash`, over the exact same file list `populate` copies)
    -- reuse can only ever be granted for a directory whose full-content
    hash has already, genuinely matched by name.

    Population is staged into a sibling `<hash>.staging-<random>` directory
    and atomically renamed into place only once `populate` returns -- an
    interrupted population can never leave a partial directory sitting at
    the trusted, hash-named path a concurrent or later run would reuse
    without question (requirement: "no reliance on mutable shared files";
    once written, `<cache_root>/<content_hash>/` is never modified again).
    """

    cache_dir = cache_root / content_hash

    stale_dir: Path | None = None
    if cache_dir.is_dir():
        if _cache_directory_matches(
            cache_dir, content_hash=content_hash, file_count=expected_file_count, total_bytes=expected_total_bytes,
        ):
            return CachePopulationResult(cache_dir=cache_dir, content_hash=content_hash, reused=True)
        # A mismatching entry at the trusted, hash-named path is never
        # deleted *in place* -- renamed out of the way first instead, real
        # end-to-end evidence for why: a release currently running can have
        # files open straight out of this exact path (via its own junction
        # into it), and deleting a directory that contains a currently
        # -loaded `.pyd`/`.dll` only ever succeeds *partially* (Windows
        # refuses to delete a loaded module; `rmdir /s /q` quietly deletes
        # everything else and leaves those behind) -- corrupting the entry
        # for every release that reuses it, reproduced for real once (see
        # docs/windows-dev-deployment-design.md's "Real end-to-end
        # findings"). A same-volume rename, by contrast, does not require
        # closing any open handle inside it -- Windows binds an open handle
        # to the file object, not the path, so a process already using
        # files from here is completely undisturbed by the directory
        # itself moving. The new, correct content is staged and atomically
        # renamed into the real, trusted `cache_dir` path below *before*
        # this renamed-away copy is ever touched again, so a later,
        # best-effort cleanup of it can fail (still-locked files) without
        # ever leaving `cache_dir` itself in a corrupted or ambiguous
        # state.
        stale_dir = cache_root / f"{content_hash}.stale-{secrets.token_hex(4)}"
        windows_host.rename(cache_dir, stale_dir)

    windows_host.ensure_dir(cache_root)
    staging_dir = cache_root / f"{content_hash}.staging-{secrets.token_hex(4)}"
    if staging_dir.exists():
        windows_host.remove_tree(staging_dir)
    try:
        populate(staging_dir)
        _write_cache_manifest(
            staging_dir / CACHE_MANIFEST_FILENAME,
            content_hash=content_hash,
            file_count=expected_file_count,
            total_bytes=expected_total_bytes,
        )
    except BaseException:
        # Never leave a failed population's partial content sitting around
        # under a name a future run might otherwise need to notice and
        # clean up itself -- best-effort (a failure here must never mask
        # the original error).
        try:
            if staging_dir.exists():
                windows_host.remove_tree(staging_dir)
        except Exception:
            pass
        raise
    windows_host.rename(staging_dir, cache_dir)

    if stale_dir is not None:
        # Best-effort only: whatever was still using the old, mismatching
        # entry may still be holding some of its files open, so this can
        # genuinely fail (or partially fail) -- that must never mask the
        # successful population above, and by this point nothing depends
        # on `stale_dir` any more regardless.
        try:
            windows_host.remove_tree(stale_dir)
        except Exception:
            pass

    return CachePopulationResult(cache_dir=cache_dir, content_hash=content_hash, reused=False)


def ensure_runtime_cache(bundle_dir: Path, *, cache_root: Path, windows_host: WindowsHost) -> CachePopulationResult:
    """`ensure_cache` specialized for the runtime tier: hashes, counts, and
    (only on a genuine cache miss) copies exactly the same file list --
    every file under `python/` except the app package/model bundle nested
    inside it."""

    python_dir = bundle_dir / "python"
    files = _runtime_tier_files(bundle_dir)
    if not files:
        raise DeploymentError(f"No runtime-tier files found under {python_dir} -- is this a real build output?")
    content_hash = _combined_hash(
        (f.relative_to(python_dir).as_posix(), _hash_file(f), f.stat().st_size) for f in files
    )
    file_count, total_bytes = len(files), sum(f.stat().st_size for f in files)
    return ensure_cache(
        populate=lambda staging: _copy_files_preserving_structure(
            files, relative_root=python_dir, destination=staging / "python", windows_host=windows_host,
        ),
        content_hash=content_hash,
        expected_file_count=file_count,
        expected_total_bytes=total_bytes,
        cache_root=cache_root,
        windows_host=windows_host,
    )


def ensure_model_cache(bundle_dir: Path, *, cache_root: Path, windows_host: WindowsHost) -> CachePopulationResult | None:
    """`ensure_cache` specialized for the model tier, or `None` if this
    build did not package a model bundle at all (an explicitly supported,
    honestly reported state -- nothing to cache, and `materialize_release`
    links nothing for the model tier in that case either)."""

    model_dir = _model_bundle_dir(bundle_dir)
    files = _model_tier_files(bundle_dir)
    if not files:
        return None
    content_hash = _combined_hash(
        (f.relative_to(model_dir).as_posix(), _hash_file(f), f.stat().st_size) for f in files
    )
    file_count, total_bytes = len(files), sum(f.stat().st_size for f in files)
    return ensure_cache(
        populate=lambda staging: _copy_files_preserving_structure(
            files, relative_root=model_dir, destination=staging, windows_host=windows_host,
        ),
        content_hash=content_hash,
        expected_file_count=file_count,
        expected_total_bytes=total_bytes,
        cache_root=cache_root,
        windows_host=windows_host,
    )


# ---------------------------------------------------------------------------
# Release materialization: junctions for runtime/model, fresh copy for app
# ---------------------------------------------------------------------------


def _copy_app_tier_entry(
    source: Path, destination: Path, *, skip_relative: Path | None, windows_host: WindowsHost,
) -> int:
    """Copy `source` (a file, or a real directory such as the installed
    `mockingbird` package itself) to `destination`, except for
    `skip_relative` -- the nested model-bundle directory, materialized
    separately as its own cache junction so copying "the app" never means
    also copying the much larger, much less frequently changing model.
    Returns bytes copied."""

    if source.is_file():
        windows_host.copy_file(source, destination)
        return source.stat().st_size

    windows_host.ensure_dir(destination)
    bytes_copied = 0
    for child in sorted(source.iterdir()):
        if skip_relative is not None and child.relative_to(source) == skip_relative:
            continue
        bytes_copied += _copy_app_tier_entry(
            child, destination / child.name, skip_relative=None, windows_host=windows_host,
        )
    return bytes_copied


def materialize_release(
    *,
    bundle_dir: Path,
    release_dir: Path,
    runtime_hash: str,
    model_hash: str,
    runtime_cache_root: Path,
    model_cache_root: Path,
    windows_host: WindowsHost,
) -> MaterializedRelease:
    """Build `release_dir` (must not already exist -- requirement: never
    overwrite another release directory) as a mix of junctions into the
    shared, already-populated runtime/model caches and a small number of
    freshly copied app-tier files/directories -- never a full copy of the
    ~1.9 GB payload on an ordinary app-only redeploy.

    Structurally identical to what `build_local_product.py` itself produces
    (the same relative paths throughout `python/...`): a developer testing
    a dev deployment is testing the exact same directory shape a real end
    user's unzipped bundle has -- just with the large, rarely-changing
    parts backed by shared, immutable, hash-verified cache directories via
    NTFS junctions instead of separate copies.

    `ensure_cache` for both tiers must already have been called (this
    raises if the expected cache directory is missing) -- this function
    only ever links to or copies from what is already verified-present.
    """

    if release_dir.exists():
        raise DeploymentError(f"Refusing to materialize into an already-existing release directory: {release_dir}")

    runtime_cache_dir = runtime_cache_root / runtime_hash
    if not runtime_cache_dir.is_dir():
        raise DeploymentError(f"Runtime cache {runtime_cache_dir} does not exist -- call ensure_cache first.")
    model_cache_dir: Path | None = None
    if model_hash != NO_MODEL_BUNDLE_HASH:
        model_cache_dir = model_cache_root / model_hash
        if not model_cache_dir.is_dir():
            raise DeploymentError(f"Model cache {model_cache_dir} does not exist -- call ensure_cache first.")

    windows_host.ensure_dir(release_dir)
    junctioned: list[str] = []
    bytes_copied = 0

    bundle_python_dir = bundle_dir / "python"
    release_python_dir = release_dir / "python"
    windows_host.ensure_dir(release_python_dir)
    cached_python_dir = runtime_cache_dir / "python"

    for entry in sorted(bundle_python_dir.iterdir()):
        if entry.name == "site-packages":
            continue
        target = release_python_dir / entry.name
        if entry.is_dir():
            windows_host.make_junction(target, cached_python_dir / entry.name)
            junctioned.append(str(target.relative_to(release_dir)))
        else:
            windows_host.copy_file(entry, target)
            bytes_copied += entry.stat().st_size

    bundle_site_packages = bundle_python_dir / "site-packages"
    release_site_packages = release_python_dir / "site-packages"
    windows_host.ensure_dir(release_site_packages)
    cached_site_packages = cached_python_dir / "site-packages"

    module = _blp()
    model_relative = Path(module["PACKAGED_OBSERVATION_RUNTIME_DIRNAME"])

    for entry in sorted(bundle_site_packages.iterdir()):
        target = release_site_packages / entry.name
        if is_app_tier_entry(entry.name):
            # Always a fresh, real copy -- the small, every-commit-changes
            # tier. The model bundle nested inside it (if any) is peeled
            # out and linked to the model cache instead of copied.
            skip = model_relative if entry.name == APP_TIER_PACKAGE_NAME else None
            bytes_copied += _copy_app_tier_entry(entry, target, skip_relative=skip, windows_host=windows_host)
            if skip is not None and (entry / skip).is_dir():
                if model_cache_dir is None:
                    raise DeploymentError(
                        "Bundle packages an observation_runtime model bundle, but model_hash is "
                        f"{NO_MODEL_BUNDLE_HASH!r} (no model cache to link to). This should be "
                        "unreachable: compute_model_hash inspects the same directory."
                    )
                model_target = target / skip
                windows_host.make_junction(model_target, model_cache_dir)
                junctioned.append(str(model_target.relative_to(release_dir)))
        else:
            # Every third-party dependency -- the large, rarely-changing
            # runtime tier, linked (not copied) to the shared cache. A
            # top-level `site-packages` entry is not always a directory:
            # some distributions ship a single-file top-level module
            # alongside their own `<name>.dist-info/` (`typing_extensions`
            # is exactly this shape) rather than a package directory. NTFS
            # junctions can only target a directory -- `New-Item -ItemType
            # Junction` fails outright on a file target ("A directory is
            # required for the operation") -- so a bare-file entry here is
            # copied fresh from the cache's own verified copy instead,
            # mirroring the `python/`-top-level-files branch above. Found
            # only by a real end-to-end deploy against a real built bundle:
            # `make_bundle`'s hermetic fixture only ever synthesizes
            # directory-shaped third-party packages.
            cached_entry = cached_site_packages / entry.name
            if entry.is_dir():
                windows_host.make_junction(target, cached_entry)
                junctioned.append(str(target.relative_to(release_dir)))
            else:
                windows_host.copy_file(cached_entry, target)
                bytes_copied += cached_entry.stat().st_size

    for name in ("Start MockingBird.vbs", "README-FIRST.txt"):
        source = bundle_dir / name
        if source.is_file():
            windows_host.copy_file(source, release_dir / name)
            bytes_copied += source.stat().st_size

    return MaterializedRelease(
        release_dir=release_dir,
        runtime_hash=runtime_hash,
        model_hash=model_hash,
        junctioned_relative_paths=tuple(junctioned),
        bytes_copied=bytes_copied,
    )


def remove_release_directory(release_dir: Path, *, junctioned_relative_paths: Sequence[str], windows_host: WindowsHost) -> None:
    """Safely delete a materialized release directory: every recorded
    junction is unlinked *individually* first (never touching its shared
    cache target -- verified empirically, see docs/windows-dev-deployment
    -design.md), and only then is whatever real, non-shared content remains
    (the app tier, `release_info.json`, the launcher) recursively removed.

    Driven entirely by `junctioned_relative_paths` as recorded at
    materialization time (`MaterializedRelease`/`ReleaseRecord`), never by
    re-deriving "is this a junction" from live filesystem attributes --
    deterministic and independent of whatever this specific Windows/
    PowerShell version reports for a reparse point.
    """

    for relative in junctioned_relative_paths:
        windows_host.remove_junction(release_dir / relative)
    windows_host.remove_tree(release_dir)


def cleanup_releases(
    *, dev_root: Path, keep: int, protected_shas: Iterable[str], windows_host: WindowsHost,
) -> list[str]:
    """Remove release directories beyond the most recent `keep`, always
    additionally preserving every sha in `protected_shas` (the current
    release and the rollback target) regardless of `keep`'s value -- even
    `--keep 0` can never remove either. Returns the shas actually removed,
    oldest-affected first.

    Bounded to release directories only: this never touches the
    runtime/model cache (immutable, versioned, content-addressed, and
    shared across every release that still references it -- deleting a
    cache entry an existing release still depends on is out of scope for
    this bounded cleanup, see docs/windows-dev-deployment-design.md for the
    follow-up this leaves open), the shared `userdata/` directory, or
    anything outside `releases/`.

    "Most recent" is the ledger's own append order (`read_deployments`
    returns oldest-first; reversing it is newest-first) -- never a sort by
    the `deployed_at` timestamp *string*, which can genuinely collide at
    whole-second resolution between two deploys run back-to-back (routine
    in scripted/fast dev iteration, and exactly what a first version of
    this function got wrong: two same-second deploys sorted arbitrarily,
    silently keeping the wrong one). Ledger order is always correctly
    chronological and never collides, by construction -- `previous_
    release_for_rollback` already relies on the same fact.
    """

    records = read_deployments(dev_root)  # oldest-appended first
    existing = [record for record in records if release_directory_for(dev_root, record.sha).is_dir()]
    most_recent_first = list(reversed(existing))

    keep_shas = {record.sha for record in most_recent_first[: max(keep, 0)]}
    keep_shas |= set(protected_shas)

    removed: list[str] = []
    for record in most_recent_first:
        if record.sha in keep_shas:
            continue
        remove_release_directory(
            release_directory_for(dev_root, record.sha),
            junctioned_relative_paths=record.junctioned_relative_paths,
            windows_host=windows_host,
        )
        removed.append(record.sha)
    return removed


# ---------------------------------------------------------------------------
# Deployment ledger: durable history for rollback/cleanup, and the
# authoritative record process-safety cross-checks a live port occupant
# against before ever stopping it.
# ---------------------------------------------------------------------------


def _releases_root(dev_root: Path) -> Path:
    return dev_root / RELEASES_DIRNAME


def _ledger_path(dev_root: Path) -> Path:
    return _releases_root(dev_root) / DEPLOYMENTS_LEDGER_FILENAME


def _current_pointer_path(dev_root: Path) -> Path:
    return _releases_root(dev_root) / CURRENT_POINTER_FILENAME


def read_deployments(dev_root: Path) -> list[ReleaseRecord]:
    """Every deployment ever recorded, oldest first. Missing/corrupt ledger
    reads as empty (never raises) -- the same "a first-ever run has no
    history" honest-empty-state the rest of this tool already treats as
    normal, not an error."""

    try:
        payload = json.loads(_ledger_path(dev_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    records = []
    for entry in payload:
        if isinstance(entry, dict):
            try:
                records.append(ReleaseRecord.from_dict(entry))
            except (KeyError, ValueError, TypeError):
                continue
    return records


def append_deployment(dev_root: Path, record: ReleaseRecord, *, windows_host: WindowsHost) -> None:
    """Append-only: a past deployment's ledger entry is never edited or
    removed by a later deploy (cleanup removes the release *directory*
    separately -- see `cleanup_releases` -- but the historical record of
    what was once deployed stays, matching an audit-log convention rather
    than a live index)."""

    windows_host.ensure_dir(_releases_root(dev_root))
    records = read_deployments(dev_root)
    records = [entry for entry in records if entry.sha != record.sha]
    records.append(record)
    _ledger_path(dev_root).write_text(
        json.dumps([entry.as_dict() for entry in records], indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


def read_current(dev_root: Path) -> CurrentPointer | None:
    try:
        payload = json.loads(_current_pointer_path(dev_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or "sha" not in payload:
        return None
    try:
        return CurrentPointer.from_dict(payload)
    except (KeyError, ValueError, TypeError):
        return None


def write_current(dev_root: Path, pointer: CurrentPointer, *, windows_host: WindowsHost) -> None:
    windows_host.ensure_dir(_releases_root(dev_root))
    _current_pointer_path(dev_root).write_text(
        json.dumps(pointer.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


def release_directory_for(dev_root: Path, sha: str) -> Path:
    return _releases_root(dev_root) / sha


def previous_release_for_rollback(dev_root: Path, *, exclude_sha: str | None) -> ReleaseRecord | None:
    """The most recently deployed release that is not `exclude_sha`
    (normally the current one) and whose directory still actually exists on
    disk (a ledger entry alone is not enough -- `--keep` cleanup may have
    already removed the directory for an old entry, and rollback must never
    launch a release that is not really there)."""

    records = read_deployments(dev_root)
    for record in reversed(records):
        if record.sha == exclude_sha:
            continue
        if release_directory_for(dev_root, record.sha).is_dir():
            return record
    return None


def write_release_info(release_dir: Path, record: ReleaseRecord, *, windows_host: WindowsHost) -> None:
    """A small, self-describing marker physically inside the release
    directory itself -- always a real file (the release directory's own
    top level is never junctioned), never shared, so it stays correct and
    available even if the central ledger were ever lost or manually
    edited. Not what verification trusts for the *running process's own*
    identity claim (that is `build_info.json`, self-reported by the
    process itself over HTTP) -- this is this deployment tool's own record
    of what it *intended* to deploy here, used for cleanup/rollback
    bookkeeping and as a human-readable "what is this folder" marker."""

    (release_dir / RELEASE_INFO_FILENAME).write_text(
        json.dumps(record.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Launch (requirement: launch Start MockingBird.vbs / the packaged entry point)
# ---------------------------------------------------------------------------


def launch_release(release_dir: Path, *, host: str, port: int, userdata_dir: Path, windows_host: WindowsHost) -> None:
    """Fire-and-forget launch of the real packaged entry point
    (`Start MockingBird.vbs`) -- never a bespoke re-implementation of it --
    with `MOCKINGBIRD_HOME` pointed at the shared dev user-data directory.

    That one environment variable is the entire reason a dev deployment can
    never touch a real production install's own data: it is *never* the
    real default `%LOCALAPPDATA%\\MockingBird` (`mockingbird.runtime.
    resolve_runtime_home`'s own default with no override) -- Camera Node
    pairings, reviewed Visits, and every other local fact this dev instance
    builds up live only in `userdata_dir`, persist across every future
    redeploy/rollback of any commit (never reset merely because the running
    code changed), and are structurally incapable of colliding with a real
    install's own data directory.

    The packaged launcher takes no arguments and always starts on
    `127.0.0.1:8000` (`mockingbird.runtime.build_argument_parser`'s own
    defaults) -- this raises rather than silently deploying to the wrong
    place if `host`/`port` name anything else; free the real 127.0.0.1:8000
    first, or accept that this tool only ever manages that address.
    """

    vbs_path = release_dir / "Start MockingBird.vbs"
    if not vbs_path.is_file():
        raise DeploymentError(f"{vbs_path} is missing -- was this release fully materialized?")
    _validate_host_port(host, port)
    # `to_windows_path`, never a bare `str(userdata_dir)`: `userdata_dir` is
    # WSL-visible (typically `/mnt/c/...`), but this becomes a real Windows
    # process's own environment variable, read back by `mockingbird.runtime.
    # resolve_runtime_home` via native Windows `pathlib`. A bare POSIX-style
    # string is not absolute to Windows `pathlib` (no drive letter) -- it
    # silently resolves *relative to whatever drive the launched process's
    # own current directory happens to be on* (`Start MockingBird.vbs`
    # always sets that to the release directory, always on the same drive
    # as `%LOCALAPPDATA%`), landing on a bogus `C:\mnt\c\Users\...` sibling
    # of the real, documented `%LOCALAPPDATA%\MockingBirdDev\userdata`
    # rather than raising -- a real, always-reproducing defect found only by
    # actually launching a real release on a real Windows host and finding
    # a live `mockingbird.sqlite3` sitting under `C:\mnt\c\...` instead of
    # the documented path. No hermetic test caught it because the fake
    # `WindowsHost.to_windows_path` used in tests is the identity function,
    # so a bare `str(path)` and a real conversion happen to produce the
    # same value there either way.
    windows_host.launch_release(
        release_dir,
        {
            "MOCKINGBIRD_HOME": windows_host.to_windows_path(userdata_dir),
            # The runtime cache is junctioned, not copied, into every
            # release that shares it -- so *every* file the running process
            # itself writes through that junction lands directly in the
            # shared cache directory, not somewhere private to this
            # release. CPython does exactly this on every first import: it
            # writes a `.pyc` next to the `.py` it just compiled. Real
            # end-to-end evidence: after a release actually ran for a
            # while, its runtime cache directory had genuinely grown from
            # 2626 files to 3060 -- all 434 extra ones freshly written
            # `__pycache__/*.pyc` files, nothing else differed -- which
            # then made `ensure_cache`'s own manifest-vs-live-content check
            # correctly (not spuriously) report a mismatch on the next
            # deploy, since the manifest still claimed the pre-run file
            # count. `ensure_cache` now recovers from that safely either
            # way (see its own docstring), but suppressing bytecode writes
            # for *this dev tool's own* launches avoids manufacturing the
            # mismatch in the first place -- never a change to the real
            # product's own packaging or normal (non-dev-tool) startup
            # behavior, which keeps writing `.pyc`s as usual.
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


# ---------------------------------------------------------------------------
# Bounded HTTP verification -- always via WindowsHost.http_get (see module
# docstring for why this never talks to the Windows port directly from WSL).
# ---------------------------------------------------------------------------


def _local_base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


@dataclass(frozen=True)
class PortOccupant:
    """What -- if anything -- currently answers on a port, and everything
    this tool's safety decisions need to know about it. `healthy_
    mockingbird=False` covers both "nothing is listening" and "something is
    listening but does not look like MockingBird" -- both must be treated
    identically (never touched) by every caller, so they are not
    distinguished further here; `occupied` alone answers "is the address
    free to bind."""

    occupied: bool
    healthy_mockingbird: bool
    instance_id: str | None = None
    git_commit: str | None = None
    build_id: str | None = None
    app_version: str | None = None
    pid: int | None = None


def probe_port(host: str, port: int, *, windows_host: WindowsHost, timeout: float = 3.0) -> PortOccupant:
    """Bounded, tolerant read of whatever is on `host:port` right now.
    Mirrors `mockingbird.runtime.healthy_mockingbird_at`'s own two-step
    check (a well-formed `/health` body first) plus `/api/product/instance`
    for the identity fields this tool's process-safety decisions depend on
    -- run as a Windows-native HTTP client (see module docstring), never a
    direct WSL socket call. Any failure at any step (nothing listening,
    connection refused, malformed JSON, wrong body shape) is treated
    identically as "not a healthy MockingBird" -- never a guess in either
    direction, matching `mockingbird.runtime._remote_instance_id`'s own
    "any failure means cannot confirm" philosophy.
    """

    base_url = _local_base_url(host, port)
    pid = windows_host.port_owner_pid(port)
    health = windows_host.http_get(f"{base_url}/health", timeout)
    if not health.ok or health.status != 200 or health.json_body != {"status": "ok"}:
        return PortOccupant(occupied=pid is not None or health.ok, healthy_mockingbird=False, pid=pid)

    identity = windows_host.http_get(f"{base_url}/api/product/instance", timeout)
    if not identity.ok or identity.status != 200 or not isinstance(identity.json_body, dict):
        # A healthy `/health` alone is never enough to identify anything --
        # exactly an older MockingBird build with no `/api/product/
        # instance`, or a transient failure reading it. Reported as
        # "healthy but unconfirmed", never silently treated as absent.
        return PortOccupant(occupied=True, healthy_mockingbird=True, pid=pid)

    payload = identity.json_body

    def _optional_str(key: str) -> str | None:
        value = payload.get(key)
        return value if isinstance(value, str) and value else None

    return PortOccupant(
        occupied=True,
        healthy_mockingbird=True,
        instance_id=_optional_str("instance_id"),
        git_commit=_optional_str("git_commit"),
        build_id=_optional_str("build_id"),
        app_version=_optional_str("app_version"),
        pid=pid,
    )


def verified_owning_release(occupant: PortOccupant, dev_root: Path) -> ReleaseRecord | None:
    """Prove -- never assume -- that whatever is answering on the port is a
    dev instance *this deployment system* created: both its self-reported
    `git_commit` AND `build_id` (an unguessable-per-build random token, see
    `BuildIdentity`) must match a release this tool's own ledger recorded.

    Matching `git_commit` alone would not be enough: a completely separate
    MockingBird checkout (a WSL-native dev server, or a real production
    install) could coincidentally be built from the same commit.
    `build_id` is the fact that is true only for a specific artifact this
    exact tool actually built and deployed -- it is what makes "old build
    cannot masquerade as new" provable rather than assumed, even when two
    builds share a commit (a rebuild after an unrelated local fix).

    `None` for anything that fails either check -- an arbitrary process, a
    WSL-forwarded MockingBird, an older build with no build identity at
    all, a real production install, or a stale/mismatched build_id. Every
    caller must never stop, or claim ownership of, a process this returns
    `None` for.
    """

    if not occupant.healthy_mockingbird or not occupant.git_commit or not occupant.build_id:
        return None
    for record in read_deployments(dev_root):
        if record.full_commit == occupant.git_commit and record.build_id == occupant.build_id:
            return record
    return None


def verify_deployment(
    *,
    host: str,
    port: int,
    expected_commit: str,
    expected_build_id: str | None,
    release_dir: Path,
    runtime_cache_dir: Path,
    windows_host: WindowsHost,
    timeout_seconds: float = DEFAULT_VERIFY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> VerificationResult:
    """Poll the deployed instance, bounded by `timeout_seconds`, until it
    is healthy and self-reports exactly the commit/build this deploy just
    materialized -- or report exactly which fact never checked out
    (requirement: "if verification fails, report exactly why"), never a
    generic timeout message.

    Checks, in order, each a distinct honest failure reason:
    1. becomes a healthy MockingBird at all within the timeout;
    2. self-reports `git_commit == expected_commit` (an old/different
       build still answering is reported by name, never silently retried
       forever or accepted);
    3. self-reports `build_id == expected_build_id` when the caller has one
       to compare (an old build *of the same commit* still running);
    4. the port-owning process's own OS-reported image path is under
       either the release directory or its runtime cache (defense in
       depth alongside 2/3 -- accepts either root since an NTFS junction's
       *reported* path can resolve to either the logical release path or
       the physical cache target depending on Windows/PowerShell version;
       both are correct, no other root is);
    5. `/api/product/health` answers with a well-formed body and a valid
       `database_schema_version` -- the "schema/API health" check. This
       intentionally never requires `ready: true`: a fresh dev instance
       honestly reporting "no camera configured yet" is a successful
       deployment, not a failure -- this tool verifies the *deployment*,
       never the product's own onboarding state.
    """

    base_url = _local_base_url(host, port)
    deadline = now() + timeout_seconds
    occupant = probe_port(host, port, windows_host=windows_host)
    while now() < deadline and not (occupant.healthy_mockingbird and occupant.git_commit == expected_commit):
        sleep(poll_interval_seconds)
        occupant = probe_port(host, port, windows_host=windows_host)

    if not occupant.healthy_mockingbird:
        return VerificationResult(
            ok=False,
            reason=f"{base_url} never became a healthy MockingBird instance within {timeout_seconds:.0f}s.",
        )
    if occupant.git_commit != expected_commit:
        return VerificationResult(
            ok=False,
            reason=(
                f"{base_url} is healthy but reports git_commit={occupant.git_commit!r}, expected "
                f"{expected_commit!r} -- a different or stale build answered instead."
            ),
            reported_git_commit=occupant.git_commit,
            reported_build_id=occupant.build_id,
            reported_instance_id=occupant.instance_id,
            pid=occupant.pid,
        )
    if expected_build_id is not None and occupant.build_id != expected_build_id:
        return VerificationResult(
            ok=False,
            reason=(
                f"{base_url} reports the expected commit, but build_id={occupant.build_id!r} does not "
                f"match the build just deployed ({expected_build_id!r}) -- an old build of the same "
                "commit is still the one actually running, and must not be mistaken for the new one."
            ),
            reported_git_commit=occupant.git_commit,
            reported_build_id=occupant.build_id,
            reported_instance_id=occupant.instance_id,
            pid=occupant.pid,
        )

    executable_path = windows_host.process_image_path(occupant.pid) if occupant.pid is not None else None
    if executable_path is not None:
        expected_roots = (
            windows_host.to_windows_path(release_dir).lower(),
            windows_host.to_windows_path(runtime_cache_dir).lower(),
        )
        if not executable_path.lower().startswith(expected_roots):
            return VerificationResult(
                ok=False,
                reason=(
                    f"Process {occupant.pid} answering {base_url} runs from {executable_path!r}, which "
                    "is under neither the release directory nor its runtime cache -- refusing to treat "
                    "it as this deployment."
                ),
                reported_git_commit=occupant.git_commit,
                reported_build_id=occupant.build_id,
                reported_instance_id=occupant.instance_id,
                executable_path=executable_path,
                pid=occupant.pid,
            )

    health = windows_host.http_get(f"{base_url}/api/product/health", 5.0)
    if not health.ok or health.status != 200 or not isinstance(health.json_body, dict):
        return VerificationResult(
            ok=False,
            reason=f"{base_url}/api/product/health did not return a valid product-health body.",
            reported_git_commit=occupant.git_commit,
            reported_build_id=occupant.build_id,
            reported_instance_id=occupant.instance_id,
            executable_path=executable_path,
            pid=occupant.pid,
        )
    schema_version = health.json_body.get("database_schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        return VerificationResult(
            ok=False,
            reason=(
                f"{base_url}/api/product/health reports an invalid database_schema_version: "
                f"{schema_version!r}."
            ),
            reported_git_commit=occupant.git_commit,
            reported_build_id=occupant.build_id,
            reported_instance_id=occupant.instance_id,
            executable_path=executable_path,
            pid=occupant.pid,
        )

    return VerificationResult(
        ok=True,
        reason="ok",
        reported_git_commit=occupant.git_commit,
        reported_build_id=occupant.build_id,
        reported_instance_id=occupant.instance_id,
        executable_path=executable_path,
        pid=occupant.pid,
    )


# ---------------------------------------------------------------------------
# Process/port safety: stop only a provably-owned dev deployment.
# ---------------------------------------------------------------------------


def stop_verified_deployment(
    *,
    dev_root: Path,
    host: str,
    port: int,
    windows_host: WindowsHost,
    wait_seconds: float = 15.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> ReleaseRecord | None:
    """Stop whatever is on `host:port` **only** when a fresh, live re-check
    (never a previously recorded PID alone) proves it is a dev instance
    this deployment system created -- see `verified_owning_release`.

    Returns the `ReleaseRecord` that was stopped, or `None` if nothing was
    running at all (not an error: a first deploy has nothing to stop).
    Raises `DeploymentError` -- and stops nothing -- for every other case:
    the port occupied by something that is not a healthy MockingBird at
    all (an arbitrary service, WSL MockingBird forwarded to this port,
    wslrelay.exe, another Python app), or a healthy MockingBird whose
    identity does not match this tool's own ledger (a real production
    install, a WSL-native dev server, or any other unrelated MockingBird).
    The message always names which case applies.
    """

    occupant = probe_port(host, port, windows_host=windows_host)
    if not occupant.occupied:
        return None
    if not occupant.healthy_mockingbird:
        raise DeploymentError(
            f"Port {port} is occupied by something that is not a healthy MockingBird "
            f"(pid={occupant.pid if occupant.pid is not None else 'unknown'}). Refusing to touch it -- "
            "it may be WSL MockingBird forwarded to this port, wslrelay.exe, or an unrelated "
            "service. Close it yourself, or deploy with --port to use a different address."
        )
    owning_release = verified_owning_release(occupant, dev_root)
    if owning_release is None:
        raise DeploymentError(
            f"Port {port} already answers a healthy MockingBird (instance_id={occupant.instance_id}, "
            f"git_commit={occupant.git_commit}), but its identity does not match any release this "
            "deployment system created. Refusing to stop it -- it may be a real production "
            "MockingBird install, a WSL-native dev server, or another tool's own build. Close it "
            "yourself, or deploy with --port to use a different address."
        )
    if occupant.pid is None:
        raise DeploymentError(
            f"Port {port} answers as a verified dev deployment ({owning_release.sha}), but its owning "
            "process id could not be determined -- refusing to guess which process to stop."
        )

    windows_host.kill_process(occupant.pid)
    deadline = now() + wait_seconds
    while now() < deadline and windows_host.process_alive(occupant.pid):
        sleep(0.5)
    if windows_host.process_alive(occupant.pid):
        raise DeploymentError(
            f"Process {occupant.pid} ({owning_release.sha}) did not exit within {wait_seconds:.0f}s of "
            "being asked to stop."
        )
    return owning_release


# ---------------------------------------------------------------------------
# Top-level operations: deploy, rollback, cleanup, status
# ---------------------------------------------------------------------------


def _validate_host_port(host: str, port: int) -> None:
    """Fail fast, before any build/materialize work, on a `--host`/`--port`
    the packaged launcher could never actually use -- see `launch_release`.
    Both `deploy` and `rollback` check this immediately rather than
    discovering it only after a potentially expensive build."""

    if (host, port) != (DEFAULT_HOST, DEFAULT_PORT):
        raise DeploymentError(
            f"The packaged launcher always starts MockingBird on {DEFAULT_HOST}:{DEFAULT_PORT} "
            f"(it takes no arguments); {host}:{port} was requested. This tool cannot deploy to a "
            "different address."
        )


def deploy(
    *,
    repo_root: Path,
    dev_root: Path,
    windows_host: WindowsHost,
    commit_ref: str = "HEAD",
    artifact_path: Path | None = None,
    build_staging_dir: Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    verify_timeout_seconds: float = DEFAULT_VERIFY_TIMEOUT_SECONDS,
    keep_after_deploy: int | None = None,
    skip_gpu_runtime: bool = False,
    model_bundle_source: Path | None = None,
    wheel_cache_dir: Path | None = None,
    poll_interval_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> DeployReport:
    """The one-command deployment: verify the requested commit, build or
    accept an artifact, populate/reuse the runtime+model cache, materialize
    a versioned release directory (never overwriting another release),
    stop only a provably-owned previous dev instance, launch the real
    packaged entry point, and verify build identity/schema health within a
    bounded timeout. See the module docstring and
    docs/windows-dev-deployment-design.md.

    On a verification failure this raises `DeploymentError` *after* the
    release directory has already been fully materialized and recorded in
    the ledger -- a failed deploy never deletes or corrupts the previous
    release, which stays retained and immediately usable via `--rollback`.
    """

    _validate_host_port(host, port)
    windows_host.ensure_dir(dev_root)
    userdata_dir = dev_root / USERDATA_DIRNAME
    windows_host.ensure_dir(userdata_dir)
    runtime_cache_root = dev_root / RUNTIME_CACHE_DIRNAME
    model_cache_root = dev_root / MODEL_CACHE_DIRNAME
    windows_host.ensure_dir(_releases_root(dev_root))

    if artifact_path is not None:
        source = accept_release_source(artifact_path)
    else:
        staging = (build_staging_dir or Path(tempfile.mkdtemp(prefix="mockingbird-deploy-build-"))).resolve()
        source = build_release_source(
            repo_root=repo_root,
            commit_ref=commit_ref,
            build_output_dir=staging,
            skip_gpu_runtime=skip_gpu_runtime,
            model_bundle_source=model_bundle_source,
            wheel_cache_dir=wheel_cache_dir,
        )
    if source.git_commit is None:
        raise DeploymentError("The build/accepted artifact has no verified git commit -- refusing to deploy it.")

    sha = short_sha(source.git_commit, cwd=repo_root)
    release_dir = release_directory_for(dev_root, sha)
    existing_record = next((entry for entry in read_deployments(dev_root) if entry.sha == sha), None)

    if release_dir.is_dir():
        if existing_record is None or existing_record.full_commit != source.git_commit:
            raise DeploymentError(
                f"{release_dir} already exists but does not match a ledger entry for commit "
                f"{source.git_commit} -- refusing to overwrite another release directory. If you are "
                "certain it is stale/corrupt, remove it manually first."
            )
        # Idempotent redeploy of a commit that is already fully
        # materialized here -- reuse it rather than rebuild, and certainly
        # never "overwrite" it; proceed straight to (re)launch/verify.
        record = existing_record
    else:
        runtime_cache = ensure_runtime_cache(source.bundle_dir, cache_root=runtime_cache_root, windows_host=windows_host)
        model_cache = ensure_model_cache(source.bundle_dir, cache_root=model_cache_root, windows_host=windows_host)
        model_hash = model_cache.content_hash if model_cache is not None else NO_MODEL_BUNDLE_HASH

        materialized = materialize_release(
            bundle_dir=source.bundle_dir,
            release_dir=release_dir,
            runtime_hash=runtime_cache.content_hash,
            model_hash=model_hash,
            runtime_cache_root=runtime_cache_root,
            model_cache_root=model_cache_root,
            windows_host=windows_host,
        )
        record = ReleaseRecord(
            sha=sha,
            full_commit=source.git_commit,
            build_id=source.build_id,
            app_version=source.app_version,
            runtime_hash=materialized.runtime_hash,
            model_hash=materialized.model_hash,
            deployed_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            junctioned_relative_paths=materialized.junctioned_relative_paths,
        )
        write_release_info(release_dir, record, windows_host=windows_host)
        append_deployment(dev_root, record, windows_host=windows_host)

    previous_pointer = read_current(dev_root)
    previous_sha = previous_pointer.sha if previous_pointer is not None and previous_pointer.sha != sha else None

    stopped = stop_verified_deployment(
        dev_root=dev_root, host=host, port=port, windows_host=windows_host, sleep=sleep, now=now,
    )
    if stopped is not None and stopped.sha != sha:
        previous_sha = stopped.sha

    launch_release(release_dir, host=host, port=port, userdata_dir=userdata_dir, windows_host=windows_host)

    runtime_cache_dir = runtime_cache_root / record.runtime_hash
    verification = verify_deployment(
        host=host,
        port=port,
        expected_commit=source.git_commit,
        # `record.build_id`, never `source.build_id`: in the reuse branch
        # above, `record` is the *existing* ledger entry and `release_dir`
        # was deliberately left untouched (never re-materialized) -- but
        # `source` still comes from a brand new call to
        # `build_release_source`/`build_local_product`, which mints a fresh
        # random `build_id` on *every* invocation regardless of whether the
        # commit changed. Verifying against `source.build_id` therefore
        # checks for a build identity that was never written into the
        # reused release directory's own `build_info.json` at all --
        # `deploy()` would then always reject its own legitimate idempotent
        # reuse, unconditionally, for any commit redeployed a second time
        # without an intervening change. `record.build_id` matches
        # `source.build_id` exactly in the fresh-materialize branch (the
        # `ReleaseRecord` there is built from `source` directly) and is the
        # *only* correct expectation in the reuse branch, so using it
        # unconditionally here is correct either way. Real end-to-end
        # deploys always rebuild (`build_release_source` has no equivalent
        # of `accept_release_source`'s "read the identity already on disk"
        # shortcut), so this is not a narrow edge case -- simply running
        # `python scripts/deploy_windows_dev.py` a second time with no
        # intervening commit hit this every time. The existing
        # `test_deploy_redeploying_the_identical_commit_is_idempotent`
        # never caught it: it redeploys via `artifact_path`, which reads a
        # fixed, already-on-disk `build_id` via `accept_release_source`
        # rather than minting a fresh one on each call the way a real
        # `python scripts/deploy_windows_dev.py` rebuild does.
        expected_build_id=record.build_id,
        release_dir=release_dir,
        runtime_cache_dir=runtime_cache_dir,
        windows_host=windows_host,
        timeout_seconds=verify_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
        now=now,
    )
    if not verification.ok:
        raise DeploymentError(
            f"Deployment verification failed: {verification.reason} The release directory "
            f"({release_dir}) and its ledger entry were left in place -- "
            + (f"roll back to {previous_sha} with --rollback, or " if previous_sha else "")
            + "investigate and retry."
        )

    write_current(dev_root, CurrentPointer(sha=sha, pid=verification.pid, port=port), windows_host=windows_host)

    if keep_after_deploy is not None:
        protected = {sha}
        if previous_sha is not None:
            protected.add(previous_sha)
        cleanup_releases(dev_root=dev_root, keep=keep_after_deploy, protected_shas=protected, windows_host=windows_host)

    return DeployReport(
        sha=sha,
        release_dir_windows=windows_host.to_windows_path(release_dir),
        pid=verification.pid,
        url=_local_base_url(host, port),
        previous_release_sha=previous_sha,
        verification=verification,
    )


def rollback(
    *,
    dev_root: Path,
    windows_host: WindowsHost,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    verify_timeout_seconds: float = DEFAULT_VERIFY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> DeployReport:
    """Stop only the verified current dev deployment, launch the previous
    retained release, and verify its build identity -- never touching user
    data (the shared `userdata/` directory is unaffected by which release
    is running; see `launch_release`).

    "Current" is always re-established from a fresh live probe (never
    solely from the last-recorded pointer file, which could be stale if a
    release was launched or stopped outside this tool) before deciding
    what "previous" even means, so a rollback target is never computed
    relative to a guess.
    """

    _validate_host_port(host, port)
    current_pointer = read_current(dev_root)
    if current_pointer is None:
        raise DeploymentError("Nothing has been deployed by this tool yet -- there is no rollback target.")

    occupant = probe_port(host, port, windows_host=windows_host)
    owning_release = verified_owning_release(occupant, dev_root)
    effective_current_sha = owning_release.sha if owning_release is not None else current_pointer.sha

    previous = previous_release_for_rollback(dev_root, exclude_sha=effective_current_sha)
    if previous is None:
        raise DeploymentError(
            f"No previous release is retained to roll back to from {effective_current_sha} -- it may "
            "have been removed by cleanup, or this is the only deployment made so far."
        )

    # Re-checks the same safety proof as any other stop -- rollback is not
    # a special case that bypasses it.
    stop_verified_deployment(
        dev_root=dev_root, host=host, port=port, windows_host=windows_host, sleep=sleep, now=now,
    )

    release_dir = release_directory_for(dev_root, previous.sha)
    userdata_dir = dev_root / USERDATA_DIRNAME
    launch_release(release_dir, host=host, port=port, userdata_dir=userdata_dir, windows_host=windows_host)

    runtime_cache_dir = dev_root / RUNTIME_CACHE_DIRNAME / previous.runtime_hash
    verification = verify_deployment(
        host=host,
        port=port,
        expected_commit=previous.full_commit,
        expected_build_id=previous.build_id,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
        now=now,
        release_dir=release_dir,
        runtime_cache_dir=runtime_cache_dir,
        windows_host=windows_host,
        timeout_seconds=verify_timeout_seconds,
    )
    if not verification.ok:
        raise DeploymentError(f"Rollback verification failed: {verification.reason}")

    write_current(
        dev_root, CurrentPointer(sha=previous.sha, pid=verification.pid, port=port), windows_host=windows_host,
    )

    return DeployReport(
        sha=previous.sha,
        release_dir_windows=windows_host.to_windows_path(release_dir),
        pid=verification.pid,
        url=_local_base_url(host, port),
        previous_release_sha=effective_current_sha if effective_current_sha != previous.sha else None,
        verification=verification,
    )


def cleanup_command(*, dev_root: Path, keep: int, windows_host: WindowsHost) -> list[str]:
    """`--cleanup`/`--keep N`: bounded cleanup that always additionally
    protects the current release and its immediate rollback target,
    regardless of `keep` -- a purely filesystem/ledger operation, never
    requires the deployed instance to be running or probes any port."""

    current_pointer = read_current(dev_root)
    protected: set[str] = set()
    if current_pointer is not None:
        protected.add(current_pointer.sha)
        previous = previous_release_for_rollback(dev_root, exclude_sha=current_pointer.sha)
        if previous is not None:
            protected.add(previous.sha)
    return cleanup_releases(dev_root=dev_root, keep=keep, protected_shas=protected, windows_host=windows_host)


def status_report(*, dev_root: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, windows_host: WindowsHost) -> str:
    """A read-only summary of the current dev deployment. Makes no changes
    -- safe to run at any time, including while unsure what state things
    are in."""

    current_pointer = read_current(dev_root)
    occupant = probe_port(host, port, windows_host=windows_host)
    owning_release = verified_owning_release(occupant, dev_root)

    lines = []
    lines.append(
        f"Last deployed by this tool: {current_pointer.sha}" if current_pointer is not None
        else "No deployment recorded by this tool yet."
    )
    if not occupant.occupied:
        lines.append(f"Port {port}: free.")
    elif not occupant.healthy_mockingbird:
        lines.append(
            f"Port {port}: occupied by a process (pid={occupant.pid}) that is not a healthy "
            "MockingBird -- not managed by this tool."
        )
    elif owning_release is None:
        lines.append(
            f"Port {port}: a healthy MockingBird is running (instance_id={occupant.instance_id}, "
            f"git_commit={occupant.git_commit}) but is not a release this tool deployed."
        )
    else:
        lines.append(f"Port {port}: verified dev release {owning_release.sha} running (pid={occupant.pid}).")

    present = [
        record.sha for record in read_deployments(dev_root) if release_directory_for(dev_root, record.sha).is_dir()
    ]
    lines.append(f"Retained releases: {', '.join(present) if present else '(none)'}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Real WindowsHost: the only place this script actually shells out to
# `wslpath`/`powershell.exe`. Nothing above this line touches a real
# process, a real Windows path, or a real network socket -- every test
# exercises the orchestration above against a fake `WindowsHost` instead
# (see tests/test_deploy_windows_dev.py). See the module docstring for why
# HTTP/process/junction operations all run as genuine Windows-native
# PowerShell processes rather than direct WSL socket/filesystem calls.
# ---------------------------------------------------------------------------


def _ps_quote(value: str) -> str:
    """Escape `value` for embedding inside a PowerShell single-quoted
    string literal (PowerShell's own escaping convention: a literal `'` is
    written `''`). Every real operation below builds its script by
    substituting values into an f-string this way, rather than trying to
    shell-escape across the bash/PowerShell/cmd.exe boundary with
    %-style or backtick escaping -- fragile, and empirically the source of
    real quoting bugs while validating this design against a real WSL2
    host (see docs/windows-dev-deployment-design.md)."""

    return value.replace("'", "''")


def _wslpath(args: Sequence[str]) -> str:
    completed = subprocess.run(["wslpath", *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise DeploymentError(f"wslpath {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _to_windows_path_real(path: Path) -> str:
    return _wslpath(["-w", str(path)])


_windows_temp_root_cache: Path | None = None


def _windows_temp_root() -> Path:
    """A WSL-visible path to a *real Windows-native* temp directory.
    `powershell.exe`, launched via WSL interop, is a genuine Windows
    process -- it cannot read a pure WSL path like `/tmp/...` (invisible
    to Windows entirely), only something reachable through a drive letter.
    Every generated `.ps1` script is written here, then referenced by its
    translated Windows path, empirically the only reliable way found to
    avoid a three-shell (bash -> PowerShell -> cmd.exe) quoting mess for
    anything beyond a trivial one-liner (see docs/windows-dev-deployment
    -design.md)."""

    global _windows_temp_root_cache
    if _windows_temp_root_cache is None:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('TEMP')"],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            raise DeploymentError(
                f"Could not resolve the Windows TEMP directory via powershell.exe: {completed.stderr.strip()}"
            )
        _windows_temp_root_cache = Path(_wslpath(["-u", completed.stdout.strip()]))
    return _windows_temp_root_cache


def _run_powershell(script: str, *, timeout: float | None = None) -> str:
    """Run `script` as a real Windows-native PowerShell process and return
    its stdout. Raises `DeploymentError` (including stderr) on a non-zero
    exit -- every real `WindowsHost` operation below is built on this one
    choke point."""

    work_dir = _windows_temp_root() / f"mockingbird-deploy-ps-{secrets.token_hex(4)}"
    work_dir.mkdir(parents=True, exist_ok=True)
    script_path = work_dir / "run.ps1"
    try:
        script_path.write_text(script, encoding="utf-8")
        windows_script_path = _wslpath(["-w", str(script_path)])
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", windows_script_path],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as error:
            # A named, actionable `DeploymentError` -- never a bare
            # traceback -- matching every other failure path here. Killing
            # this `powershell.exe` process (`subprocess.run`'s own timeout
            # behavior) does not necessarily kill whatever native process it
            # itself launched (no Windows job-object linkage) -- a real,
            # observed case: `wscript.exe`, left running well past this
            # timeout by an unrelated quoting defect (see
            # `_launch_release_real`), stayed orphaned rather than exiting
            # with its waiter. Includes a script excerpt (there is no
            # per-call-site label otherwise) -- diagnosing a real timeout
            # here once meant manually cross-referencing every `timeout=`
            # call site in this file against the bare number in the error.
            excerpt = " | ".join(line.strip() for line in script.splitlines() if line.strip())[:200]
            raise DeploymentError(
                f"powershell.exe did not finish within {timeout}s running: {excerpt} -- it (or a process it "
                "launched) may still be running orphaned on the Windows side; check Task Manager if this recurs."
            ) from error
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    if completed.returncode != 0:
        raise DeploymentError(
            f"powershell.exe failed ({completed.returncode}): {(completed.stderr or completed.stdout).strip()}"
        )
    return completed.stdout


def _local_appdata_real() -> Path:
    output = _run_powershell(
        "[Environment]::GetEnvironmentVariable('LOCALAPPDATA')\n", timeout=15,
    ).strip()
    if not output:
        raise DeploymentError("Could not resolve %LOCALAPPDATA% via powershell.exe.")
    return Path(_wslpath(["-u", output]))


def _make_junction_real(link: Path, target: Path) -> None:
    link_windows = _to_windows_path_real(link)
    target_windows = _to_windows_path_real(target)
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"New-Item -ItemType Junction -Path '{_ps_quote(link_windows)}' "
        f"-Target '{_ps_quote(target_windows)}' | Out-Null\n"
    )
    _run_powershell(script, timeout=30)


def _retrying_rmdir_powershell(quoted_windows_path: str, *, recursive: bool) -> str:
    """A `cmd.exe /c rmdir ...` (native, junction-safe -- see the two
    callers below) wrapped in a bounded retry loop with a final
    `Test-Path` verification, as one PowerShell script.

    `cmd.exe`'s own exit code is not a terminating PowerShell error --
    `$ErrorActionPreference = 'Stop'` does not catch an external command
    quietly failing. Real, empirically reproduced while validating this
    design: reading a junction's content through its *WSL-side* (drvfs)
    view holds it busy long enough that an immediately-following native
    `rmdir` of that same junction fails silently, clearing within a couple
    of seconds on its own. This tool's own real operations never do that
    (`materialize_release` only ever creates a junction, never reads
    through it again; the running MockingBird process reads its own files
    natively on the Windows side, never through WSL) -- but the same
    "something transiently held this path busy" shape is a well-known,
    generic possibility on Windows regardless (antivirus, the Search
    indexer), so this retries several times with a short pause rather than
    assuming a single attempt is enough, and reports the real, final,
    freshly-checked state; the caller raises unless that final state says
    gone -- a silent failure here would be worse than useless, since every
    caller depends on this having actually happened before doing anything
    else.
    """

    rmdir_flags = "/s /q " if recursive else ""
    return (
        "$ErrorActionPreference = 'Stop'\n"
        f"$target = '{quoted_windows_path}'\n"
        "$stillPresent = $true\n"
        "for ($attempt = 0; $attempt -lt 10; $attempt++) {\n"
        "    if (-not (Test-Path $target)) { $stillPresent = $false; break }\n"
        f"    cmd.exe /c \"rmdir {rmdir_flags}`\"$target`\"\" | Out-Null\n"
        "    Start-Sleep -Milliseconds 300\n"
        "    if (-not (Test-Path $target)) { $stillPresent = $false; break }\n"
        "}\n"
        "if ($stillPresent) { Write-Output 'STILL-PRESENT' } else { Write-Output 'GONE' }\n"
    )


def _run_verified_removal(path: Path, *, windows_path: str, recursive: bool, timeout: float) -> None:
    script = _retrying_rmdir_powershell(_ps_quote(windows_path), recursive=recursive)
    result = _run_powershell(script, timeout=timeout).strip().splitlines()
    if not result or result[-1].strip() != "GONE":
        raise DeploymentError(f"Could not remove {path} -- it is still present after retrying.")


def _remove_junction_real(link: Path) -> None:
    """Unlink *only* the junction/reparse point at `link` -- never its
    target's content. `cmd.exe`'s native `rmdir` (no `/s`) on a reparse
    point removes just the link; empirically the safe, reliable way to do
    this -- PowerShell's own `Remove-Item -Force` threw a spurious
    `NullReferenceException` on a junction in validation, and
    `Remove-Item -Recurse` has real historical bugs that can follow a
    reparse point into its target. See docs/windows-dev-deployment
    -design.md. Retried and verified -- see `_retrying_rmdir_powershell`.

    Deliberately does *not* resolve `link`'s own Windows path via plain
    `_to_windows_path_real(link)`: by the time this runs, `link` always
    already exists as a real junction, and WSL's drvfs surfaces an NTFS
    junction as a POSIX symlink on the Linux side (confirmed: `stat`/
    `readlink -f` on an already-created junction reports `symbolic link`,
    target the junction's real target) -- `wslpath -w`, like `realpath`,
    transparently resolves through it, silently returning the *target*'s
    (the shared cache's) Windows path instead of the junction's own. That
    is a real, reproducible defect, found only by actually removing a
    junction against a real Windows host: every hermetic test fakes a
    junction as a plain symlink under an ordinary temp directory with
    `to_windows_path`/`remove_junction` themselves faked, so it never went
    through real `wslpath` resolution at all. Luckily never destructive --
    `rmdir` with no `/s` refuses a real, non-empty directory -- but it does
    mean every attempt silently targets the wrong path and exhausts every
    retry ("STILL-PRESENT"), never actually unlinking `link`. This tool's
    own junction topology never nests one junction's target inside
    another, so `link`'s *parent* is always a real directory, never itself
    a symlink -- resolving the parent via `_to_windows_path_real` and
    appending `link.name` as a literal string reaches `link` itself
    without ever asking `wslpath` to resolve through it.
    """

    windows_path = f"{_to_windows_path_real(link.parent)}\\{link.name}"
    _run_verified_removal(link, windows_path=windows_path, recursive=False, timeout=60)


def _remove_tree_real(path: Path) -> None:
    """Recursively delete `path`. Always `cmd.exe`'s native `rmdir /s /q`
    -- never PowerShell's `Remove-Item -Recurse`, which has real
    historical bugs around reparse points -- so this is safe to call even
    on a directory that (should never, but might due to a bug elsewhere)
    still contain an un-unlinked junction: native `rmdir /s` has never
    followed a reparse point into its target, by long-standing documented
    Windows behavior. `remove_release_directory` still always unlinks
    every *known* junction individually first regardless, as the primary,
    audited safety mechanism -- this is defense in depth, not a
    substitute for it. Retried and verified -- see
    `_retrying_rmdir_powershell`.
    """

    _run_verified_removal(path, windows_path=_to_windows_path_real(path), recursive=True, timeout=180)


def _launch_release_real(release_dir: Path, extra_env: dict[str, str]) -> None:
    vbs_windows = _to_windows_path_real(release_dir / "Start MockingBird.vbs")
    env_lines = "\n".join(f"$env:{name} = '{_ps_quote(value)}'" for name, value in extra_env.items())
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"{env_lines}\n"
        # `-ArgumentList` takes a *value*, not a pre-tokenized argv -- a bare
        # path containing a space (the release directory, or simply the
        # literal filename "Start MockingBird.vbs" itself, always) is handed
        # to CreateProcess unquoted and silently splits into two arguments
        # for wscript.exe, which then treats the first half as the script to
        # run, fails to find it, and shows a blocking "Windows Script Host"
        # error dialog. Wrapping the value in an embedded, literal `"..."`
        # pair (inside the outer PowerShell single-quoted string) makes
        # `-ArgumentList` hand wscript.exe one properly quoted token, same
        # fix shape as `_retrying_rmdir_powershell`'s own `cmd.exe` call
        # already uses for the same reason. Found only by actually launching
        # a real release on a real Windows host and inspecting the child's
        # own received command line via `Get-CimInstance Win32_Process`.
        #
        # Deliberately `-PassThru` + a short bounded poll on `$p.HasExited`,
        # never `-Wait`: proven by hand, repeatably, that `Start-Process
        # -Wait` on `wscript.exe` here does not return when `wscript.exe`
        # itself exits (confirmed separately, via `-PassThru`, to exit in
        # about a second with `ExitCode=0`) -- it still had not returned
        # after 180s. `shell.Run(..., 0, False)` inside the vbs launches
        # `pythonw.exe` without giving it a fresh console of its own, so it
        # inherits wscript.exe's own (WSL-interop-spawned, so already
        # somewhat unusual) console/handle set; `-Wait`'s underlying
        # `Process.WaitForExit()` was observed to block until every process
        # sharing those handles exits, not just `wscript.exe` -- and
        # `pythonw.exe` is a long-running server that is never expected to
        # exit on its own, so `-Wait` would never return by design, not
        # merely slowly. `verify_deployment`'s own bounded HTTP polling is
        # the real confirmation the server actually started; this only
        # needs to know whether the tiny launcher script itself ran
        # successfully (its one failure mode: `WScript.Quit 1` when
        # `pythonw.exe` is missing from the release).
        f"""$p = Start-Process -FilePath 'wscript.exe' -ArgumentList '"{_ps_quote(vbs_windows)}"' -PassThru\n"""
        "for ($i = 0; $i -lt 30; $i++) {\n"
        "    Start-Sleep -Milliseconds 500\n"
        "    if ($p.HasExited) { break }\n"
        "}\n"
        "if ($p.HasExited -and $p.ExitCode -ne 0) {\n"
        "    Write-Output \"LAUNCHER-FAILED exit-code=$($p.ExitCode)\"\n"
        "} else {\n"
        "    Write-Output \"LAUNCHER-OK has-exited=$($p.HasExited)\"\n"
        "}\n"
    )
    output = _run_powershell(script, timeout=30)
    if "LAUNCHER-FAILED" in output:
        raise DeploymentError(
            f"Start MockingBird.vbs exited with a non-zero code ({output.strip()}) -- see its own message box "
            '(e.g. "pythonw.exe is missing") on the Windows desktop for the exact reason.'
        )


def _http_get_real(url: str, timeout: float) -> HttpProbe:
    timeout_seconds = max(1, int(timeout) + 1)
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "try {\n"
        f"    $r = Invoke-WebRequest -Uri '{_ps_quote(url)}' -TimeoutSec {timeout_seconds} -UseBasicParsing\n"
        "    $result = @{ ok = $true; status = [int]$r.StatusCode; body = $r.Content }\n"
        "} catch {\n"
        "    $status = $null\n"
        "    if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }\n"
        "    $result = @{ ok = $false; status = $status; error = $_.Exception.Message }\n"
        "}\n"
        "$result | ConvertTo-Json -Compress\n"
    )
    raw_lines = [line for line in _run_powershell(script, timeout=timeout_seconds + 15).splitlines() if line.strip()]
    if not raw_lines:
        return HttpProbe(ok=False, error="powershell.exe produced no output")
    try:
        payload = json.loads(raw_lines[-1])
    except ValueError:
        return HttpProbe(ok=False, error=f"could not parse powershell output: {raw_lines[-1]!r}")
    if not payload.get("ok"):
        return HttpProbe(ok=False, status=payload.get("status"), error=payload.get("error"))
    json_body = None
    body_text = payload.get("body")
    if isinstance(body_text, str):
        try:
            json_body = json.loads(body_text)
        except ValueError:
            json_body = None
    return HttpProbe(ok=True, status=payload.get("status"), json_body=json_body)


def _port_owner_pid_real(port: int) -> int | None:
    script = (
        f"$conn = Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue "
        "| Select-Object -First 1\n"
        "if ($conn) { Write-Output $conn.OwningProcess } else { Write-Output 'NONE' }\n"
    )
    lines = [line.strip() for line in _run_powershell(script, timeout=15).splitlines() if line.strip()]
    if not lines or lines[-1] == "NONE":
        return None
    try:
        return int(lines[-1])
    except ValueError:
        return None


def _process_alive_real(pid: int) -> bool:
    script = (
        f"$p = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue\n"
        "if ($p) { Write-Output 'ALIVE' } else { Write-Output 'GONE' }\n"
    )
    lines = [line.strip() for line in _run_powershell(script, timeout=15).splitlines() if line.strip()]
    return bool(lines) and lines[-1] == "ALIVE"


def _process_image_path_real(pid: int) -> str | None:
    script = (
        f"$p = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue\n"
        "if ($p -and $p.Path) { Write-Output $p.Path } else { Write-Output 'NONE' }\n"
    )
    lines = [line.strip() for line in _run_powershell(script, timeout=15).splitlines() if line.strip()]
    if not lines or lines[-1] == "NONE":
        return None
    return lines[-1]


def _kill_process_real(pid: int) -> None:
    _run_powershell(f"Stop-Process -Id {int(pid)} -Force -ErrorAction SilentlyContinue\n", timeout=15)


def real_windows_host() -> WindowsHost:
    """The only production `WindowsHost`. Every field either shells out to
    a genuine Windows-native `powershell.exe`/`wslpath` process (see the
    section docstring above) or, for plain filesystem operations that work
    correctly and far more cheaply as ordinary WSL-side Python calls on a
    `/mnt/c/...` path (creating a directory, copying/renaming one file),
    stays a direct `pathlib`/`shutil` call -- never PowerShell purely for
    the sake of uniformity, since each real `powershell.exe` invocation
    costs a real process spawn."""

    return WindowsHost(
        local_appdata=_local_appdata_real,
        to_windows_path=_to_windows_path_real,
        ensure_dir=lambda path: path.mkdir(parents=True, exist_ok=True),
        copy_file=lambda source, destination: shutil.copy2(source, destination),
        rename=lambda source, destination: source.rename(destination),
        make_junction=_make_junction_real,
        remove_junction=_remove_junction_real,
        remove_tree=_remove_tree_real,
        launch_release=_launch_release_real,
        http_get=_http_get_real,
        port_owner_pid=_port_owner_pid_real,
        process_alive=_process_alive_real,
        process_image_path=_process_image_path_real,
        kill_process=_kill_process_real,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build (or accept) a MockingBird Windows local-product artifact and deploy it to a "
            "versioned %LOCALAPPDATA%\\MockingBirdDev\\releases\\<git-short-sha>\\ directory, "
            "launch it, and verify its build identity -- see docs/windows-dev-deployment-design.md."
        ),
    )
    parser.add_argument(
        "--commit", default="HEAD",
        help="git ref to verify and deploy (default: HEAD). Must already be checked out -- this "
        "never runs `git checkout` on your behalf.",
    )
    parser.add_argument(
        "--artifact", type=Path, default=None,
        help="deploy an already-built bundle directory or .zip instead of building one now",
    )
    parser.add_argument(
        "--dev-root", type=Path, default=None,
        help="override the MockingBirdDev root (default: %%LOCALAPPDATA%%\\MockingBirdDev)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_VERIFY_TIMEOUT_SECONDS,
        help="bounded seconds to wait for post-launch verification (default: %(default)s)",
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="stop the current verified dev deployment and launch the previous retained release",
    )
    parser.add_argument(
        "--status", action="store_true", help="report the current dev deployment; makes no changes",
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help=f"remove old release directories, keeping the {DEFAULT_KEEP} most recent (see --keep)",
    )
    parser.add_argument(
        "--keep", type=int, default=None,
        help="keep only this many most recent release directories; implies --cleanup",
    )
    parser.add_argument(
        "--skip-gpu-runtime", action="store_true",
        help="passthrough to build_local_product.py: omit the ~1.1 GB CUDA/cuDNN stack for a faster build",
    )
    parser.add_argument("--model-bundle-source", type=Path, default=None, help="passthrough to build_local_product.py")
    parser.add_argument("--wheel-cache-dir", type=Path, default=None, help="passthrough to build_local_product.py")
    parser.add_argument(
        "--build-output-dir", type=Path, default=None,
        help="staging directory for the build (default: a fresh temp directory)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    windows_host = real_windows_host()
    dev_root = (
        args.dev_root.resolve() if args.dev_root is not None else (windows_host.local_appdata() / DEV_ROOT_DIRNAME)
    )

    try:
        if args.rollback:
            report = rollback(
                dev_root=dev_root, windows_host=windows_host, host=args.host, port=args.port,
                verify_timeout_seconds=args.timeout,
            )
            print(report.render())
            return 0

        if args.status:
            print(status_report(dev_root=dev_root, host=args.host, port=args.port, windows_host=windows_host))
            return 0

        if args.cleanup or args.keep is not None:
            keep = args.keep if args.keep is not None else DEFAULT_KEEP
            removed = cleanup_command(dev_root=dev_root, keep=keep, windows_host=windows_host)
            print(f"Removed releases: {', '.join(removed)}" if removed else "Nothing to remove.")
            return 0

        report = deploy(
            repo_root=ROOT,
            dev_root=dev_root,
            windows_host=windows_host,
            commit_ref=args.commit,
            artifact_path=args.artifact,
            build_staging_dir=args.build_output_dir,
            host=args.host,
            port=args.port,
            verify_timeout_seconds=args.timeout,
            skip_gpu_runtime=args.skip_gpu_runtime,
            model_bundle_source=args.model_bundle_source,
            wheel_cache_dir=args.wheel_cache_dir,
        )
        print(report.render())
        return 0
    except DeploymentError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
