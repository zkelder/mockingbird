"""Structural tests for scripts/deploy_windows_dev.py.

See docs/windows-dev-deployment-design.md for the design this implements.

Entirely hermetic and fast: no real `powershell.exe`, `wslpath`, or Windows
filesystem/process/network call anywhere in this file. Every test drives the
script's orchestration logic (hashing, caching, release materialization,
ledger bookkeeping, process-safety decisions, verification, deploy/rollback/
cleanup) against a `WindowsHost` entirely backed by plain temp-directory
filesystem operations and an in-memory fake "Windows OS" (`FakeWindowsOS`)
simulating listening ports and a process table. Real bundle-shaped fixtures
are tiny, hand-built directories (`make_bundle`) -- never a real ~1.9 GB
Windows local-product artifact, and no real git repository is required
(`deploy()`/`accept_release_source` are exercised through the `--artifact`
acceptance path, which needs no live git checkout; `resolve_commit`/
`short_sha`, which do, are tested directly against small throwaway fixture
repos, matching the existing convention in tests/test_local_product_
packaging.py).

Junctions are simulated with real POSIX symlinks (`os.symlink(target,
link, target_is_directory=True)`) in the fake `WindowsHost` -- close enough
to exercise every orchestration decision (what gets linked vs. copied, what
a safe removal unlinks vs. leaves alone) without needing a real Windows
reparse point; the *real* junction/removal mechanics themselves
(`New-Item -ItemType Junction`, `cmd.exe /c rmdir`) were validated by hand
against a real WSL2/Windows host while designing this script -- see the
module docstring in scripts/deploy_windows_dev.py.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(str(ROOT / "scripts" / "deploy_windows_dev.py"))

# --- names under test -------------------------------------------------------
DeploymentError = _MODULE["DeploymentError"]
WindowsHost = _MODULE["WindowsHost"]
HttpProbe = _MODULE["HttpProbe"]
ReleaseSource = _MODULE["ReleaseSource"]
ReleaseRecord = _MODULE["ReleaseRecord"]
CurrentPointer = _MODULE["CurrentPointer"]
PortOccupant = _MODULE["PortOccupant"]
DeployReport = _MODULE["DeployReport"]
VerificationResult = _MODULE["VerificationResult"]

resolve_commit = _MODULE["resolve_commit"]
short_sha = _MODULE["short_sha"]
accept_release_source = _MODULE["accept_release_source"]
build_release_source = _MODULE["build_release_source"]

is_app_tier_entry = _MODULE["is_app_tier_entry"]
compute_runtime_hash = _MODULE["compute_runtime_hash"]
compute_model_hash = _MODULE["compute_model_hash"]
NO_MODEL_BUNDLE_HASH = _MODULE["NO_MODEL_BUNDLE_HASH"]

ensure_cache = _MODULE["ensure_cache"]
ensure_runtime_cache = _MODULE["ensure_runtime_cache"]
ensure_model_cache = _MODULE["ensure_model_cache"]
materialize_release = _MODULE["materialize_release"]
remove_release_directory = _MODULE["remove_release_directory"]
cleanup_releases = _MODULE["cleanup_releases"]

read_deployments = _MODULE["read_deployments"]
append_deployment = _MODULE["append_deployment"]
read_current = _MODULE["read_current"]
write_current = _MODULE["write_current"]
release_directory_for = _MODULE["release_directory_for"]
previous_release_for_rollback = _MODULE["previous_release_for_rollback"]
write_release_info = _MODULE["write_release_info"]

launch_release = _MODULE["launch_release"]
probe_port = _MODULE["probe_port"]
verified_owning_release = _MODULE["verified_owning_release"]
verify_deployment = _MODULE["verify_deployment"]
stop_verified_deployment = _MODULE["stop_verified_deployment"]

deploy = _MODULE["deploy"]
rollback = _MODULE["rollback"]
cleanup_command = _MODULE["cleanup_command"]
status_report = _MODULE["status_report"]
build_argument_parser = _MODULE["build_argument_parser"]
main = _MODULE["main"]
_retrying_rmdir_powershell = _MODULE["_retrying_rmdir_powershell"]
_ps_quote = _MODULE["_ps_quote"]

DEV_ROOT_DIRNAME = _MODULE["DEV_ROOT_DIRNAME"]
USERDATA_DIRNAME = _MODULE["USERDATA_DIRNAME"]
RELEASES_DIRNAME = _MODULE["RELEASES_DIRNAME"]
DEFAULT_HOST = _MODULE["DEFAULT_HOST"]
DEFAULT_PORT = _MODULE["DEFAULT_PORT"]
DEFAULT_KEEP = _MODULE["DEFAULT_KEEP"]

_BLP = runpy.run_path(str(ROOT / "scripts" / "build_local_product.py"))
PACKAGED_BUILD_INFO_FILENAME = _BLP["PACKAGED_BUILD_INFO_FILENAME"]
PACKAGED_OBSERVATION_RUNTIME_DIRNAME = _BLP["PACKAGED_OBSERVATION_RUNTIME_DIRNAME"]


_NO_SLEEP = lambda _seconds: None  # noqa: E731 -- every test drives bounded polling instantly


# ---------------------------------------------------------------------------
# Fixture bundle construction
# ---------------------------------------------------------------------------


def make_bundle(
    root: Path,
    *,
    git_commit: str,
    build_id: str,
    app_version: str = "0.1.0",
    app_content: str = "APP = 1\n",
    third_party_packages: tuple[str, ...] = ("fastapi", "uvicorn"),
    include_model: bool = True,
    model_content: bytes = b"fake-onnx-model-bytes",
) -> Path:
    """A tiny, hand-built stand-in for what `build_local_product.py`
    actually produces -- exactly the directory shape `deploy_windows_dev.py`
    inspects (`python/`, `python/site-packages/<third-party packages>`,
    `python/site-packages/mockingbird/` with a nested `observation_runtime/`
    model bundle and a `build_info.json`, `Start MockingBird.vbs`), never a
    real ~1.9 GB artifact."""

    bundle = root / "MockingBird-windows-x64"
    python_dir = bundle / "python"
    python_dir.mkdir(parents=True)
    (python_dir / "python.exe").write_bytes(b"fake-python-exe")
    (python_dir / "pythonw.exe").write_bytes(b"fake-pythonw-exe")
    (python_dir / "python312._pth").write_text("python312.zip\n.\nsite-packages\n", encoding="utf-8")

    site_packages = python_dir / "site-packages"
    site_packages.mkdir()
    for package_name in third_party_packages:
        package_dir = site_packages / package_name
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text(f"# fake {package_name}\n", encoding="utf-8")
        dist_info = site_packages / f"{package_name}-1.0.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(f"Name: {package_name}\n", encoding="utf-8")

    mockingbird_dir = site_packages / "mockingbird"
    mockingbird_dir.mkdir()
    (mockingbird_dir / "__init__.py").write_text(app_content, encoding="utf-8")
    (mockingbird_dir / PACKAGED_BUILD_INFO_FILENAME).write_text(
        json.dumps(
            {
                "git_commit": git_commit, "build_id": build_id,
                "built_at": "2026-01-01T00:00:00+00:00", "app_version": app_version,
            }
        ),
        encoding="utf-8",
    )
    dist_info = site_packages / f"mockingbird-{app_version}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Name: mockingbird\n", encoding="utf-8")

    if include_model:
        model_dir = mockingbird_dir / PACKAGED_OBSERVATION_RUNTIME_DIRNAME
        model_dir.mkdir()
        (model_dir / "provider-config.json").write_text('{"model_bundle": "model-bundle.json"}', encoding="utf-8")
        (model_dir / "model-bundle.json").write_text('{"model_file": "model.onnx"}', encoding="utf-8")
        (model_dir / "model.onnx").write_bytes(model_content)

    (bundle / "Start MockingBird.vbs").write_text("' fake launcher\r\n", encoding="utf-8")
    (bundle / "README-FIRST.txt").write_text("readme\n", encoding="utf-8")
    return bundle


# ---------------------------------------------------------------------------
# Fake WindowsHost: plain filesystem ops (symlinks stand in for junctions)
# plus an in-memory fake Windows process/port table.
# ---------------------------------------------------------------------------


class FakeWindowsOS:
    """One fake Windows process table + listening-port table. Every fake
    `WindowsHost` callable below reads/mutates this -- lets `deploy()`/
    `rollback()`/`stop_verified_deployment()` be exercised against a
    believable simulated environment with no real subprocess, network, or
    filesystem reparse point anywhere."""

    def __init__(self) -> None:
        self._next_pid = 1000
        self.listeners: dict[int, dict] = {}  # port -> identity dict
        self.alive_pids: set[int] = set()

    def start_listener(self, *, port: int, image_path: str, git_commit, build_id, instance_id, app_version="0.1.0", schema_version=42):
        pid = self._next_pid
        self._next_pid += 1
        self.alive_pids.add(pid)
        self.listeners[port] = {
            "pid": pid, "image_path": image_path, "git_commit": git_commit, "build_id": build_id,
            "instance_id": instance_id, "app_version": app_version, "schema_version": schema_version,
        }
        return pid

    def start_non_mockingbird_listener(self, *, port: int, pid: int | None = None) -> int:
        """A port with *something* bound but no valid MockingBird body at
        all -- an arbitrary service, or wslrelay.exe."""

        pid = pid if pid is not None else self._next_pid
        self._next_pid = max(self._next_pid, pid + 1)
        self.alive_pids.add(pid)
        self.listeners[port] = {"pid": pid, "not_mockingbird": True}
        return pid


def make_fake_windows_host(os_sim: FakeWindowsOS, *, local_appdata: Path) -> WindowsHost:
    import re

    def http_get(url: str, _timeout: float) -> HttpProbe:
        match = re.search(r":(\d+)/(.*)", url)
        assert match is not None
        port, path = int(match.group(1)), match.group(2)
        listener = os_sim.listeners.get(port)
        if listener is None:
            return HttpProbe(ok=False, error="connection refused")
        if listener.get("not_mockingbird"):
            return HttpProbe(ok=False, error="connection reset")
        if path == "health":
            return HttpProbe(ok=True, status=200, json_body={"status": "ok"})
        if path == "api/product/instance":
            return HttpProbe(
                ok=True, status=200,
                json_body={
                    "instance_id": listener["instance_id"], "app_version": listener["app_version"],
                    "git_commit": listener["git_commit"], "build_id": listener["build_id"],
                },
            )
        if path == "api/product/health":
            return HttpProbe(
                ok=True, status=200,
                json_body={"app_version": listener["app_version"], "database_schema_version": listener["schema_version"]},
            )
        return HttpProbe(ok=False, error="not found")

    def port_owner_pid(port: int):
        listener = os_sim.listeners.get(port)
        return listener["pid"] if listener else None

    def process_alive(pid: int) -> bool:
        return pid in os_sim.alive_pids

    def process_image_path(pid: int):
        for listener in os_sim.listeners.values():
            if listener["pid"] == pid:
                return listener.get("image_path")
        return None

    def kill_process(pid: int) -> None:
        os_sim.alive_pids.discard(pid)
        for port, listener in list(os_sim.listeners.items()):
            if listener["pid"] == pid:
                del os_sim.listeners[port]

    def launch_release_fn(release_dir: Path, extra_env: dict) -> None:
        info_path = release_dir / "python" / "site-packages" / "mockingbird" / PACKAGED_BUILD_INFO_FILENAME
        info = json.loads(info_path.read_text(encoding="utf-8"))
        os_sim.start_listener(
            port=DEFAULT_PORT,
            image_path=str(release_dir / "python" / "pythonw.exe"),
            git_commit=info["git_commit"], build_id=info["build_id"], app_version=info["app_version"],
            instance_id=f"instance-for-{info['build_id']}",
        )
        launch_release_fn.calls.append({"release_dir": release_dir, "extra_env": dict(extra_env)})  # type: ignore[attr-defined]

    launch_release_fn.calls = []  # type: ignore[attr-defined]

    def make_junction(link: Path, target: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.exists() or link.is_symlink():
            raise DeploymentError(f"fake junction target already exists: {link}")
        link.symlink_to(target, target_is_directory=True)

    def remove_junction(link: Path) -> None:
        if link.is_symlink():
            link.unlink()

    def remove_tree(path: Path) -> None:
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)

    return WindowsHost(
        local_appdata=lambda: local_appdata,
        to_windows_path=lambda path: str(path),
        ensure_dir=lambda path: path.mkdir(parents=True, exist_ok=True),
        copy_file=lambda source, destination: shutil.copy2(source, destination),
        rename=lambda source, destination: source.rename(destination),
        make_junction=make_junction,
        remove_junction=remove_junction,
        remove_tree=remove_tree,
        launch_release=launch_release_fn,
        http_get=http_get,
        port_owner_pid=port_owner_pid,
        process_alive=process_alive,
        process_image_path=process_image_path,
        kill_process=kill_process,
    )


@pytest.fixture
def os_sim() -> FakeWindowsOS:
    return FakeWindowsOS()


@pytest.fixture
def fake_host(os_sim: FakeWindowsOS, tmp_path: Path) -> WindowsHost:
    return make_fake_windows_host(os_sim, local_appdata=tmp_path / "LOCALAPPDATA")


@pytest.fixture
def dev_root(tmp_path: Path) -> Path:
    return tmp_path / "LOCALAPPDATA" / DEV_ROOT_DIRNAME


def _init_fixture_repo(directory: Path) -> None:
    """Mirrors tests/test_local_product_packaging.py's own
    `_init_fixture_repo` -- a small throwaway git repo, never this
    worktree's own real git state."""

    directory.mkdir(parents=True, exist_ok=True)
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(command, cwd=directory, check=True, capture_output=True)


def _commit_all(directory: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=directory, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--quiet", "-m", message], cwd=directory, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=directory, check=True, capture_output=True, text=True,
    ).stdout.strip()


# ---------------------------------------------------------------------------
# Requirement 1: verify the requested/source git commit
# ---------------------------------------------------------------------------


def test_resolve_commit_verifies_head_by_default(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_fixture_repo(repo)
    (repo / "a.txt").write_text("1", encoding="utf-8")
    commit = _commit_all(repo, "initial")

    assert resolve_commit("HEAD", cwd=repo) == commit


def test_resolve_commit_rejects_an_unknown_ref(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_fixture_repo(repo)
    (repo / "a.txt").write_text("1", encoding="utf-8")
    _commit_all(repo, "initial")

    with pytest.raises(DeploymentError, match="no-such-ref"):
        resolve_commit("no-such-ref", cwd=repo)


def test_short_sha_matches_gits_own_short_form(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_fixture_repo(repo)
    (repo / "a.txt").write_text("1", encoding="utf-8")
    commit = _commit_all(repo, "initial")

    sha = short_sha(commit, cwd=repo)

    assert commit.startswith(sha)
    assert len(sha) == 7


def test_build_release_source_refuses_a_commit_that_is_not_the_checked_out_head(tmp_path: Path) -> None:
    """This tool never runs `git checkout` on an operator's behalf --
    `--commit` verifies what is already checked out, it does not make it
    so. See scripts/deploy_windows_dev.py's `build_release_source`."""

    repo = tmp_path / "repo"
    _init_fixture_repo(repo)
    (repo / "a.txt").write_text("1", encoding="utf-8")
    first = _commit_all(repo, "first")
    (repo / "a.txt").write_text("2", encoding="utf-8")
    _commit_all(repo, "second")  # HEAD now differs from `first`

    with pytest.raises(DeploymentError, match="checked out"):
        build_release_source(repo_root=repo, commit_ref=first, build_output_dir=tmp_path / "out")


# ---------------------------------------------------------------------------
# Requirement 2: build or accept an already-built artifact
# ---------------------------------------------------------------------------


def test_accept_release_source_from_a_bundle_directory(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="build-id-1")

    source = accept_release_source(bundle)

    assert source.bundle_dir == bundle
    assert source.git_commit == "a" * 40
    assert source.build_id == "build-id-1"
    assert source.source_state == f"git:{'a' * 40}"


def test_accept_release_source_from_a_zip(tmp_path: Path) -> None:
    import zipfile

    bundle = make_bundle(tmp_path / "build", git_commit="b" * 40, build_id="build-id-2")
    zip_path = tmp_path / "artifact.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for file_path in sorted(p for p in bundle.rglob("*") if p.is_file()):
            archive.write(file_path, arcname=str(Path(bundle.name) / file_path.relative_to(bundle)))

    source = accept_release_source(zip_path)

    assert source.git_commit == "b" * 40
    assert source.build_id == "build-id-2"
    assert (source.bundle_dir / "python" / "pythonw.exe").is_file()


def test_accept_release_source_refuses_a_bundle_with_no_build_info(tmp_path: Path) -> None:
    bundle = tmp_path / "MockingBird-windows-x64"
    (bundle / "python" / "site-packages" / "mockingbird").mkdir(parents=True)
    (bundle / "Start MockingBird.vbs").write_text("' vbs\n", encoding="utf-8")

    with pytest.raises(DeploymentError, match="build_info"):
        accept_release_source(bundle)


def test_accept_release_source_refuses_a_path_that_is_neither_directory_nor_zip(tmp_path: Path) -> None:
    stray_file = tmp_path / "not-a-bundle.txt"
    stray_file.write_text("nope", encoding="utf-8")

    with pytest.raises(DeploymentError):
        accept_release_source(stray_file)


# ---------------------------------------------------------------------------
# Runtime/model/app tier split and cryptographic hashing
# ---------------------------------------------------------------------------


def test_is_app_tier_entry_matches_the_installed_package_and_its_dist_info() -> None:
    assert is_app_tier_entry("mockingbird") is True
    assert is_app_tier_entry("mockingbird-0.1.0.dist-info") is True
    assert is_app_tier_entry("mockingbird-0.1.0.data") is True
    assert is_app_tier_entry("fastapi") is False
    assert is_app_tier_entry("mockingbird_other_package") is False  # no "-" separator: not this package


def test_compute_runtime_hash_is_stable_for_identical_content(tmp_path: Path) -> None:
    bundle1 = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1", app_content="APP=1\n")
    bundle2 = make_bundle(tmp_path / "b2", git_commit="b" * 40, build_id="id2", app_content="APP=2\n")

    # Different commit/build/app content -- runtime tier (third-party
    # packages + interpreter) is untouched, so its hash must be identical.
    assert compute_runtime_hash(bundle1) == compute_runtime_hash(bundle2)


def test_compute_runtime_hash_changes_when_a_third_party_package_changes(tmp_path: Path) -> None:
    bundle1 = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1")
    bundle2 = make_bundle(tmp_path / "b2", git_commit="a" * 40, build_id="id1")
    (bundle2 / "python" / "site-packages" / "fastapi" / "__init__.py").write_text(
        "# a real dependency version bump\n", encoding="utf-8",
    )

    assert compute_runtime_hash(bundle1) != compute_runtime_hash(bundle2)


def test_compute_runtime_hash_ignores_app_tier_and_model_changes(tmp_path: Path) -> None:
    bundle1 = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1", model_content=b"model-v1")
    bundle2 = make_bundle(tmp_path / "b2", git_commit="a" * 40, build_id="id1", model_content=b"a-completely-different-model")

    assert compute_runtime_hash(bundle1) == compute_runtime_hash(bundle2)


def test_compute_model_hash_changes_when_the_model_changes(tmp_path: Path) -> None:
    bundle1 = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1", model_content=b"model-v1")
    bundle2 = make_bundle(tmp_path / "b2", git_commit="a" * 40, build_id="id1", model_content=b"model-v2")

    assert compute_model_hash(bundle1) != compute_model_hash(bundle2)


def test_compute_model_hash_ignores_app_tier_changes(tmp_path: Path) -> None:
    bundle1 = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1", app_content="APP=1\n")
    bundle2 = make_bundle(tmp_path / "b2", git_commit="b" * 40, build_id="id2", app_content="APP=2\n")

    assert compute_model_hash(bundle1) == compute_model_hash(bundle2)


def test_compute_model_hash_is_an_explicit_sentinel_when_no_model_packaged(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1", include_model=False)

    assert compute_model_hash(bundle) == NO_MODEL_BUNDLE_HASH


# ---------------------------------------------------------------------------
# Immutable, versioned, content-addressed cache population
# ---------------------------------------------------------------------------


def test_ensure_runtime_cache_populates_then_reuses(tmp_path: Path, fake_host: WindowsHost) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    cache_root = tmp_path / "cache" / "runtime"

    first = ensure_runtime_cache(bundle, cache_root=cache_root, windows_host=fake_host)
    assert first.reused is False
    assert (first.cache_dir / "python" / "site-packages" / "fastapi" / "__init__.py").is_file()
    # The app tier must never leak into the runtime cache.
    assert not (first.cache_dir / "python" / "site-packages" / "mockingbird").exists()

    second = ensure_runtime_cache(bundle, cache_root=cache_root, windows_host=fake_host)
    assert second.reused is True
    assert second.content_hash == first.content_hash
    assert second.cache_dir == first.cache_dir


def test_ensure_runtime_cache_hash_mismatch_forces_fresh_assets(tmp_path: Path, fake_host: WindowsHost) -> None:
    """Requirement: 'runtime/model hash mismatch forces fresh assets'."""

    bundle1 = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1")
    cache_root = tmp_path / "cache" / "runtime"
    first = ensure_runtime_cache(bundle1, cache_root=cache_root, windows_host=fake_host)

    bundle2 = make_bundle(tmp_path / "b2", git_commit="b" * 40, build_id="id2")
    (bundle2 / "python" / "site-packages" / "fastapi" / "__init__.py").write_text("# bumped\n", encoding="utf-8")
    second = ensure_runtime_cache(bundle2, cache_root=cache_root, windows_host=fake_host)

    assert second.reused is False
    assert second.content_hash != first.content_hash
    assert second.cache_dir != first.cache_dir
    # The old cache entry is untouched, not overwritten -- both are real,
    # independently valid, content-addressed directories.
    assert (first.cache_dir / "python" / "site-packages" / "fastapi").is_dir()


def test_ensure_model_cache_returns_none_when_no_model_packaged(tmp_path: Path, fake_host: WindowsHost) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1", include_model=False)

    assert ensure_model_cache(bundle, cache_root=tmp_path / "cache" / "models", windows_host=fake_host) is None


def test_ensure_cache_detects_and_rebuilds_a_corrupted_entry(tmp_path: Path, fake_host: WindowsHost) -> None:
    """An existing directory at the expected hash-named path that does not
    match its own recorded manifest (tampered, or a leftover from an
    interrupted run) is never trusted just because the name matches."""

    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    cache_root = tmp_path / "cache" / "runtime"
    first = ensure_runtime_cache(bundle, cache_root=cache_root, windows_host=fake_host)

    # Corrupt it: delete a file the manifest still claims is present.
    victim = next((first.cache_dir / "python" / "site-packages").glob("fastapi/__init__.py"))
    victim.unlink()

    second = ensure_runtime_cache(bundle, cache_root=cache_root, windows_host=fake_host)

    assert second.reused is False  # rebuilt, not silently reused while corrupt
    assert second.content_hash == first.content_hash  # same hash: content is identical once rebuilt
    assert (second.cache_dir / "python" / "site-packages" / "fastapi" / "__init__.py").is_file()


def test_ensure_cache_population_is_atomic_no_partial_entry_left_on_a_failed_populate(
    tmp_path: Path, fake_host: WindowsHost,
) -> None:
    """A `populate` that writes *some* content and then fails partway
    through must never leave anything at the trusted, hash-named path --
    the rename into place only ever happens after `populate` returns
    successfully."""

    cache_root = tmp_path / "cache"

    def _failing_populate(staging: Path) -> None:
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "partial-file.txt").write_text("only part of the content", encoding="utf-8")
        raise RuntimeError("simulated interruption mid-copy")

    with pytest.raises(RuntimeError, match="simulated interruption"):
        ensure_cache(
            populate=_failing_populate, content_hash="deadbeef", expected_file_count=1, expected_total_bytes=1,
            cache_root=cache_root, windows_host=fake_host,
        )

    # No cache entry at the trusted path -- not a partially populated one a
    # later run could mistake for genuine -- and the failed staging
    # directory itself was cleaned up rather than left as debris.
    assert not (cache_root / "deadbeef").exists()
    assert not any(cache_root.glob("deadbeef.staging-*"))


# ---------------------------------------------------------------------------
# Release materialization: junctions for runtime/model, fresh copy for app
# (requirement: versioned deployment path; never overwrite another release)
# ---------------------------------------------------------------------------


def _materialize(bundle: Path, release_dir: Path, *, tmp_path: Path, fake_host: WindowsHost):
    runtime_root = tmp_path / "cache" / "runtime"
    model_root = tmp_path / "cache" / "models"
    runtime_cache = ensure_runtime_cache(bundle, cache_root=runtime_root, windows_host=fake_host)
    model_cache = ensure_model_cache(bundle, cache_root=model_root, windows_host=fake_host)
    model_hash = model_cache.content_hash if model_cache is not None else NO_MODEL_BUNDLE_HASH
    return materialize_release(
        bundle_dir=bundle, release_dir=release_dir, runtime_hash=runtime_cache.content_hash, model_hash=model_hash,
        runtime_cache_root=runtime_root, model_cache_root=model_root, windows_host=fake_host,
    )


def test_materialize_release_layout_matches_the_real_bundle_structure(tmp_path: Path, fake_host: WindowsHost) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1", app_content="APP=1\n")
    release_dir = tmp_path / "releases" / "aaaaaaa"

    materialized = _materialize(bundle, release_dir, tmp_path=tmp_path, fake_host=fake_host)

    # App tier: real, fresh copy -- editable/inspectable exactly like a
    # real unpacked release, never a link.
    app_init = release_dir / "python" / "site-packages" / "mockingbird" / "__init__.py"
    assert app_init.read_text(encoding="utf-8") == "APP=1\n"
    assert not app_init.parent.is_symlink()
    assert not (release_dir / "python" / "site-packages" / "mockingbird").is_symlink()

    # Runtime tier (third-party packages): linked, not copied.
    assert (release_dir / "python" / "site-packages" / "fastapi").is_symlink()
    assert (release_dir / "python" / "site-packages" / "fastapi" / "__init__.py").is_file()

    # Model tier: linked, nested correctly inside the real app package dir.
    model_link = release_dir / "python" / "site-packages" / "mockingbird" / PACKAGED_OBSERVATION_RUNTIME_DIRNAME
    assert model_link.is_symlink()
    assert (model_link / "model.onnx").read_bytes() == b"fake-onnx-model-bytes"

    # Launcher/readme: real, fresh copies.
    assert (release_dir / "Start MockingBird.vbs").is_file()
    assert not (release_dir / "Start MockingBird.vbs").is_symlink()

    assert materialized.junctioned_relative_paths  # something was actually linked


def test_materialize_release_copies_a_bare_file_top_level_runtime_entry(tmp_path: Path, fake_host: WindowsHost) -> None:
    """Regression test: a real `site-packages` is not only directories at
    the top level -- some third-party distributions ship a single-file
    top-level module (`typing_extensions.py` is exactly this shape)
    alongside their own `<name>.dist-info/`, rather than a package
    directory. NTFS junctions can only target a directory (`New-Item
    -ItemType Junction` fails outright on a file target, "A directory is
    required for the operation"), so a bare-file runtime-tier entry must be
    copied fresh from the cache's own verified copy instead of linked.
    Found only via a real end-to-end deploy against a real built bundle --
    `make_bundle` only ever synthesizes directory-shaped third-party
    packages, which is exactly why this shipped untested."""

    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    (bundle / "python" / "site-packages" / "typing_extensions.py").write_text(
        "# fake single-file top-level module\n", encoding="utf-8",
    )
    release_dir = tmp_path / "releases" / "aaaaaaa"

    materialized = _materialize(bundle, release_dir, tmp_path=tmp_path, fake_host=fake_host)

    copied = release_dir / "python" / "site-packages" / "typing_extensions.py"
    assert copied.is_file()
    assert not copied.is_symlink()
    assert copied.read_text(encoding="utf-8") == "# fake single-file top-level module\n"
    assert str(copied.relative_to(release_dir)) not in materialized.junctioned_relative_paths
    # The directory-shaped runtime-tier packages beside it are still linked as before.
    assert (release_dir / "python" / "site-packages" / "fastapi").is_symlink()


def test_materialize_release_never_overwrites_an_existing_release_directory(
    tmp_path: Path, fake_host: WindowsHost,
) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    release_dir = tmp_path / "releases" / "aaaaaaa"
    _materialize(bundle, release_dir, tmp_path=tmp_path, fake_host=fake_host)

    with pytest.raises(DeploymentError, match="already-existing"):
        _materialize(bundle, release_dir, tmp_path=tmp_path, fake_host=fake_host)


def test_materialize_release_without_a_model_bundle_links_nothing_for_the_model_tier(
    tmp_path: Path, fake_host: WindowsHost,
) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1", include_model=False)
    release_dir = tmp_path / "releases" / "aaaaaaa"

    materialized = _materialize(bundle, release_dir, tmp_path=tmp_path, fake_host=fake_host)

    assert materialized.model_hash == NO_MODEL_BUNDLE_HASH
    model_path = release_dir / "python" / "site-packages" / "mockingbird" / PACKAGED_OBSERVATION_RUNTIME_DIRNAME
    assert not model_path.exists()


def test_two_releases_of_different_commits_share_the_same_runtime_cache(tmp_path: Path, fake_host: WindowsHost) -> None:
    """The actual point of the cache: an app-only change (different commit,
    identical dependencies) must link to the *same* runtime cache
    directory across releases, never a second copy."""

    bundle1 = make_bundle(tmp_path / "b1", git_commit="a" * 40, build_id="id1", app_content="APP=1\n")
    bundle2 = make_bundle(tmp_path / "b2", git_commit="b" * 40, build_id="id2", app_content="APP=2\n")
    release1 = tmp_path / "releases" / "aaaaaaa"
    release2 = tmp_path / "releases" / "bbbbbbb"

    materialized1 = _materialize(bundle1, release1, tmp_path=tmp_path, fake_host=fake_host)
    materialized2 = _materialize(bundle2, release2, tmp_path=tmp_path, fake_host=fake_host)

    assert materialized1.runtime_hash == materialized2.runtime_hash
    link1 = (release1 / "python" / "site-packages" / "fastapi").resolve()
    link2 = (release2 / "python" / "site-packages" / "fastapi").resolve()
    assert link1 == link2  # both releases point at the identical cache directory


def test_remove_release_directory_never_touches_shared_cache_content(tmp_path: Path, fake_host: WindowsHost) -> None:
    """Requirement: cleanup must never delete a runtime/model cache entry
    another release still depends on -- proven here by removing the
    *only* release referencing a cache entry and confirming the cache
    content still survives regardless."""

    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    release_dir = tmp_path / "releases" / "aaaaaaa"
    materialized = _materialize(bundle, release_dir, tmp_path=tmp_path, fake_host=fake_host)
    runtime_cache_dir = tmp_path / "cache" / "runtime" / materialized.runtime_hash
    model_cache_dir = tmp_path / "cache" / "models" / materialized.model_hash

    remove_release_directory(
        release_dir, junctioned_relative_paths=materialized.junctioned_relative_paths, windows_host=fake_host,
    )

    assert not release_dir.exists()
    assert (runtime_cache_dir / "python" / "site-packages" / "fastapi" / "__init__.py").is_file()
    assert (model_cache_dir / "model.onnx").is_file()


# ---------------------------------------------------------------------------
# Deployment ledger
# ---------------------------------------------------------------------------


def _record(sha: str, *, commit: str, build_id: str) -> ReleaseRecord:
    return ReleaseRecord(
        sha=sha, full_commit=commit, build_id=build_id, app_version="0.1.0",
        runtime_hash="runtime-hash", model_hash="model-hash", deployed_at="2026-01-01T00:00:00.000000+00:00",
        junctioned_relative_paths=("python/site-packages/fastapi",),
    )


def test_read_deployments_is_empty_before_any_deploy(dev_root: Path) -> None:
    assert read_deployments(dev_root) == []


def test_append_deployment_then_read_round_trips(dev_root: Path, fake_host: WindowsHost) -> None:
    record = _record("aaaaaaa", commit="a" * 40, build_id="id1")

    append_deployment(dev_root, record, windows_host=fake_host)

    read_back = read_deployments(dev_root)
    assert len(read_back) == 1
    assert read_back[0] == record


def test_append_deployment_replaces_an_entry_with_the_same_sha(dev_root: Path, fake_host: WindowsHost) -> None:
    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id1"), windows_host=fake_host)
    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id2"), windows_host=fake_host)

    read_back = read_deployments(dev_root)
    assert len(read_back) == 1
    assert read_back[0].build_id == "id2"


def test_read_deployments_recovers_from_a_corrupt_ledger(dev_root: Path) -> None:
    dev_root.mkdir(parents=True)
    (dev_root / RELEASES_DIRNAME).mkdir()
    (dev_root / RELEASES_DIRNAME / "deployments.json").write_text("not valid json {{{", encoding="utf-8")

    assert read_deployments(dev_root) == []  # never raises


def test_current_pointer_round_trips(dev_root: Path, fake_host: WindowsHost) -> None:
    assert read_current(dev_root) is None

    write_current(dev_root, CurrentPointer(sha="aaaaaaa", pid=1234, port=DEFAULT_PORT), windows_host=fake_host)

    pointer = read_current(dev_root)
    assert pointer is not None
    assert pointer.sha == "aaaaaaa"
    assert pointer.pid == 1234


def test_previous_release_for_rollback_uses_ledger_append_order_not_timestamps(
    dev_root: Path, fake_host: WindowsHost,
) -> None:
    """Regression test: a first version of this logic sorted by the
    `deployed_at` *string*, which can collide at whole-second (or, before
    the microsecond-precision fix, even coarser) resolution between two
    deploys run back-to-back -- routine in scripted/fast dev iteration --
    silently picking the wrong 'most recent'. Every fixture record below
    shares the *exact same* `deployed_at` string on purpose to prove
    ledger append order (never timestamp comparison) is what actually
    decides recency."""

    same_timestamp = "2026-01-01T00:00:00.000000+00:00"
    for sha in ("aaaaaaa", "bbbbbbb", "ccccccc"):
        record = ReleaseRecord(
            sha=sha, full_commit=sha * 6, build_id=f"id-{sha}", app_version="0.1.0",
            runtime_hash="runtime-hash", model_hash="model-hash", deployed_at=same_timestamp,
        )
        append_deployment(dev_root, record, windows_host=fake_host)
        (release_directory_for(dev_root, sha)).mkdir(parents=True)

    previous = previous_release_for_rollback(dev_root, exclude_sha="ccccccc")

    assert previous is not None
    assert previous.sha == "bbbbbbb"  # the one appended immediately before "ccccccc", not "aaaaaaa"


def test_previous_release_for_rollback_skips_entries_whose_directory_was_removed(
    dev_root: Path, fake_host: WindowsHost,
) -> None:
    for sha in ("aaaaaaa", "bbbbbbb", "ccccccc"):
        append_deployment(dev_root, _record(sha, commit=sha * 6, build_id=f"id-{sha}"), windows_host=fake_host)
    # Only "aaaaaaa"'s directory still exists (as if --keep cleanup already
    # removed "bbbbbbb").
    (release_directory_for(dev_root, "aaaaaaa")).mkdir(parents=True)

    previous = previous_release_for_rollback(dev_root, exclude_sha="ccccccc")

    assert previous is not None
    assert previous.sha == "aaaaaaa"


def test_previous_release_for_rollback_is_none_when_nothing_else_is_retained(
    dev_root: Path, fake_host: WindowsHost,
) -> None:
    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id1"), windows_host=fake_host)
    (release_directory_for(dev_root, "aaaaaaa")).mkdir(parents=True)

    assert previous_release_for_rollback(dev_root, exclude_sha="aaaaaaa") is None


# ---------------------------------------------------------------------------
# Launch (requirement: preserve the real MockingBird user-data directory)
# ---------------------------------------------------------------------------


def test_launch_release_points_mockingbird_home_at_the_shared_dev_userdata_dir(
    tmp_path: Path, fake_host: WindowsHost,
) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    release_dir = tmp_path / "releases" / "aaaaaaa"
    shutil.copytree(bundle, release_dir)
    userdata_dir = tmp_path / "LOCALAPPDATA" / DEV_ROOT_DIRNAME / USERDATA_DIRNAME

    launch_release(release_dir, host=DEFAULT_HOST, port=DEFAULT_PORT, userdata_dir=userdata_dir, windows_host=fake_host)

    calls = fake_host.launch_release.calls  # type: ignore[attr-defined]
    assert len(calls) == 1
    assert calls[0]["extra_env"]["MOCKINGBIRD_HOME"] == str(userdata_dir)
    # Never the real product default (%LOCALAPPDATA%\MockingBird, sibling
    # of %LOCALAPPDATA%\MockingBirdDev) -- structurally a different path.
    assert calls[0]["extra_env"]["MOCKINGBIRD_HOME"] != str(tmp_path / "LOCALAPPDATA" / "MockingBird")


def test_launch_release_sends_mockingbird_home_through_to_windows_path(
    tmp_path: Path, fake_host: WindowsHost,
) -> None:
    """Regression test: `MOCKINGBIRD_HOME` becomes a real Windows process's
    own environment variable, so it must be built via `to_windows_path`,
    never a bare `str(userdata_dir)` -- `userdata_dir` is WSL-visible
    (typically `/mnt/c/...`), and native Windows `pathlib` treats that as
    rooted but *not absolute* (no drive letter), silently resolving it
    relative to whatever drive the launched process's own current directory
    happens to be on instead of raising. Found only by actually launching a
    real release on a real Windows host and finding a live
    `mockingbird.sqlite3` under a bogus `C:\\mnt\\c\\...` path instead of the
    documented one -- the *other* `launch_release` test above never caught
    it because the shared `fake_host`'s `to_windows_path` is the identity
    function, so a bare `str(path)` and a real conversion happen to produce
    the same value there either way. This test swaps in a
    non-identity `to_windows_path` specifically to prove `launch_release`
    actually routes the value through the seam rather than through `str`."""

    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    release_dir = tmp_path / "releases" / "aaaaaaa"
    shutil.copytree(bundle, release_dir)
    userdata_dir = tmp_path / "LOCALAPPDATA" / DEV_ROOT_DIRNAME / USERDATA_DIRNAME
    host = dataclasses.replace(fake_host, to_windows_path=lambda path: f"WIN:{path}")

    launch_release(release_dir, host=DEFAULT_HOST, port=DEFAULT_PORT, userdata_dir=userdata_dir, windows_host=host)

    calls = host.launch_release.calls  # type: ignore[attr-defined]
    assert calls[0]["extra_env"]["MOCKINGBIRD_HOME"] == f"WIN:{userdata_dir}"


def test_launch_release_refuses_a_non_default_host_or_port(tmp_path: Path, fake_host: WindowsHost) -> None:
    bundle = make_bundle(tmp_path / "build", git_commit="a" * 40, build_id="id1")
    release_dir = tmp_path / "releases" / "aaaaaaa"
    shutil.copytree(bundle, release_dir)

    with pytest.raises(DeploymentError, match="127.0.0.1:8000"):
        launch_release(release_dir, host=DEFAULT_HOST, port=9000, userdata_dir=tmp_path / "userdata", windows_host=fake_host)


def test_launch_release_refuses_a_release_with_no_launcher(tmp_path: Path, fake_host: WindowsHost) -> None:
    release_dir = tmp_path / "releases" / "aaaaaaa"
    release_dir.mkdir(parents=True)  # no Start MockingBird.vbs

    with pytest.raises(DeploymentError, match="missing"):
        launch_release(
            release_dir, host=DEFAULT_HOST, port=DEFAULT_PORT, userdata_dir=tmp_path / "userdata", windows_host=fake_host,
        )


# ---------------------------------------------------------------------------
# probe_port / verified_owning_release: the identity proof everything else
# in this section is built on.
# ---------------------------------------------------------------------------


def test_probe_port_reports_free_when_nothing_listens(fake_host: WindowsHost) -> None:
    occupant = probe_port(DEFAULT_HOST, DEFAULT_PORT, windows_host=fake_host)

    assert occupant.occupied is False
    assert occupant.healthy_mockingbird is False


def test_probe_port_reports_unhealthy_for_an_arbitrary_process(os_sim: FakeWindowsOS, fake_host: WindowsHost) -> None:
    """Requirement: an arbitrary process on the port (or `wslrelay.exe`, or
    WSL MockingBird forwarded here) must never be reported as a healthy
    MockingBird -- it does not answer this shape at all."""

    os_sim.start_non_mockingbird_listener(port=DEFAULT_PORT, pid=4242)

    occupant = probe_port(DEFAULT_HOST, DEFAULT_PORT, windows_host=fake_host)

    assert occupant.occupied is True
    assert occupant.healthy_mockingbird is False
    assert occupant.pid == 4242


def test_probe_port_reports_full_identity_for_a_healthy_mockingbird(os_sim: FakeWindowsOS, fake_host: WindowsHost) -> None:
    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=r"C:\releases\aaaaaaa\python\pythonw.exe",
        git_commit="a" * 40, build_id="id1", instance_id="instance-1",
    )

    occupant = probe_port(DEFAULT_HOST, DEFAULT_PORT, windows_host=fake_host)

    assert occupant.occupied is True
    assert occupant.healthy_mockingbird is True
    assert occupant.git_commit == "a" * 40
    assert occupant.build_id == "id1"
    assert occupant.instance_id == "instance-1"


def test_verified_owning_release_matches_git_commit_and_build_id(dev_root: Path, fake_host: WindowsHost) -> None:
    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id1"), windows_host=fake_host)
    occupant = PortOccupant(occupied=True, healthy_mockingbird=True, git_commit="a" * 40, build_id="id1")

    owning = verified_owning_release(occupant, dev_root)

    assert owning is not None
    assert owning.sha == "aaaaaaa"


def test_verified_owning_release_is_none_for_an_untracked_installation(dev_root: Path, fake_host: WindowsHost) -> None:
    """Covers 'WSL-forwarded port 8000 is rejected safely' and 'a normal
    production MockingBird install': a healthy MockingBird whose identity
    was never recorded by this deployment system is never matched, no
    matter how healthy it looks."""

    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id1"), windows_host=fake_host)
    occupant = PortOccupant(
        occupied=True, healthy_mockingbird=True, git_commit="z" * 40, build_id="unknown-build",
        instance_id="some-other-install",
    )

    assert verified_owning_release(occupant, dev_root) is None


def test_verified_owning_release_rejects_a_commit_match_with_a_different_build_id(
    dev_root: Path, fake_host: WindowsHost,
) -> None:
    """The exact 'old build cannot masquerade as new' proof: the same
    commit alone is not enough -- a *rebuild* of that commit (a different
    `build_id`) must not be treated as the tracked release."""

    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="the-real-build"), windows_host=fake_host)
    occupant = PortOccupant(
        occupied=True, healthy_mockingbird=True, git_commit="a" * 40, build_id="a-different-rebuild-of-the-same-commit",
    )

    assert verified_owning_release(occupant, dev_root) is None


def test_verified_owning_release_is_none_when_not_healthy(dev_root: Path, fake_host: WindowsHost) -> None:
    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id1"), windows_host=fake_host)
    occupant = PortOccupant(occupied=True, healthy_mockingbird=False, git_commit="a" * 40, build_id="id1")

    assert verified_owning_release(occupant, dev_root) is None


# ---------------------------------------------------------------------------
# stop_verified_deployment: the one place this tool ever terminates a
# process. Every "never kill" requirement lives here.
# ---------------------------------------------------------------------------


def test_stop_verified_deployment_is_a_noop_when_the_port_is_free(dev_root: Path, fake_host: WindowsHost) -> None:
    stopped = stop_verified_deployment(dev_root=dev_root, host=DEFAULT_HOST, port=DEFAULT_PORT, windows_host=fake_host)

    assert stopped is None


def test_stop_verified_deployment_never_kills_an_arbitrary_process(
    dev_root: Path, os_sim: FakeWindowsOS, fake_host: WindowsHost,
) -> None:
    """Covers 'arbitrary process on port 8000 is never killed' and
    'wslrelay.exe'/'another Python app': anything that does not even
    answer a healthy MockingBird `/health` is left completely untouched."""

    pid = os_sim.start_non_mockingbird_listener(port=DEFAULT_PORT, pid=5150)

    with pytest.raises(DeploymentError, match="not a healthy MockingBird"):
        stop_verified_deployment(dev_root=dev_root, host=DEFAULT_HOST, port=DEFAULT_PORT, windows_host=fake_host)

    assert pid in os_sim.alive_pids
    assert DEFAULT_PORT in os_sim.listeners


def test_stop_verified_deployment_never_kills_wsl_forwarded_or_production_mockingbird(
    dev_root: Path, os_sim: FakeWindowsOS, fake_host: WindowsHost,
) -> None:
    """Covers 'WSL-forwarded port 8000 is rejected safely' and 'a normal
    production MockingBird install': a *healthy*, real-looking MockingBird
    that this deployment system never created is still never touched."""

    pid = os_sim.start_listener(
        port=DEFAULT_PORT, image_path=r"C:\Users\dev\AppData\Local\MockingBird\python\pythonw.exe",
        git_commit="f" * 40, build_id="production-build-not-ours", instance_id="real-production-install",
    )

    with pytest.raises(DeploymentError, match="does not match any release"):
        stop_verified_deployment(dev_root=dev_root, host=DEFAULT_HOST, port=DEFAULT_PORT, windows_host=fake_host)

    assert pid in os_sim.alive_pids


def test_stop_verified_deployment_never_kills_an_old_build_masquerading_via_commit_alone(
    dev_root: Path, os_sim: FakeWindowsOS, fake_host: WindowsHost,
) -> None:
    """The port answers the *tracked commit*, but a different `build_id`
    -- proof that commit matching alone is never sufficient to authorize a
    kill."""

    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="the-tracked-build"), windows_host=fake_host)
    pid = os_sim.start_listener(
        port=DEFAULT_PORT, image_path=r"C:\somewhere\pythonw.exe",
        git_commit="a" * 40, build_id="a-rebuild-of-the-same-commit", instance_id="some-instance",
    )

    with pytest.raises(DeploymentError, match="does not match any release"):
        stop_verified_deployment(dev_root=dev_root, host=DEFAULT_HOST, port=DEFAULT_PORT, windows_host=fake_host)

    assert pid in os_sim.alive_pids


def test_stop_verified_deployment_stops_a_verified_dev_release(
    dev_root: Path, os_sim: FakeWindowsOS, fake_host: WindowsHost,
) -> None:
    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id1"), windows_host=fake_host)
    pid = os_sim.start_listener(
        port=DEFAULT_PORT, image_path=r"C:\MockingBirdDev\releases\aaaaaaa\python\pythonw.exe",
        git_commit="a" * 40, build_id="id1", instance_id="instance-1",
    )

    stopped = stop_verified_deployment(
        dev_root=dev_root, host=DEFAULT_HOST, port=DEFAULT_PORT, windows_host=fake_host, sleep=_NO_SLEEP,
    )

    assert stopped is not None
    assert stopped.sha == "aaaaaaa"
    assert pid not in os_sim.alive_pids
    assert DEFAULT_PORT not in os_sim.listeners


def test_stop_verified_deployment_raises_if_the_process_never_exits(
    dev_root: Path, os_sim: FakeWindowsOS, fake_host: WindowsHost, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified dev release that refuses to die (kill sent, process
    still alive) is reported, never silently ignored."""

    append_deployment(dev_root, _record("aaaaaaa", commit="a" * 40, build_id="id1"), windows_host=fake_host)
    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=r"C:\MockingBirdDev\releases\aaaaaaa\python\pythonw.exe",
        git_commit="a" * 40, build_id="id1", instance_id="instance-1",
    )
    # Simulate a process that never actually dies: kill_process is a no-op.
    stubborn_host = dataclasses.replace(fake_host, kill_process=lambda _pid: None)
    fake_now = iter([0.0, 0.1, 100.0])  # jumps straight past any wait_seconds bound

    with pytest.raises(DeploymentError, match="did not exit"):
        stop_verified_deployment(
            dev_root=dev_root, host=DEFAULT_HOST, port=DEFAULT_PORT, windows_host=stubborn_host,
            wait_seconds=1.0, sleep=_NO_SLEEP, now=lambda: next(fake_now),
        )


# ---------------------------------------------------------------------------
# verify_deployment: after launch, bounded proof the right thing is running.
# ---------------------------------------------------------------------------


def test_verify_deployment_succeeds_when_everything_matches(os_sim: FakeWindowsOS, fake_host: WindowsHost, tmp_path: Path) -> None:
    release_dir = tmp_path / "releases" / "aaaaaaa"
    runtime_cache_dir = tmp_path / "cache" / "runtime" / "runtime-hash-1"
    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=str(release_dir / "python" / "pythonw.exe"),
        git_commit="a" * 40, build_id="id1", instance_id="instance-1",
    )

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id1",
        release_dir=release_dir, runtime_cache_dir=runtime_cache_dir, windows_host=fake_host,
        timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    assert result.ok is True
    assert result.reported_git_commit == "a" * 40


def test_verify_deployment_accepts_an_executable_path_under_the_runtime_cache_too(
    os_sim: FakeWindowsOS, fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """`pythonw.exe` is junctioned in from the runtime cache -- depending on
    Windows/PowerShell version, the OS may report either the logical
    release path or the physical cache target for the running process's
    image path. Both must verify successfully (see scripts/deploy_windows_
    dev.py's `verify_deployment` docstring, check 4)."""

    release_dir = tmp_path / "releases" / "aaaaaaa"
    runtime_cache_dir = tmp_path / "cache" / "runtime" / "runtime-hash-1"
    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=str(runtime_cache_dir / "python" / "pythonw.exe"),  # cache path, not release path
        git_commit="a" * 40, build_id="id1", instance_id="instance-1",
    )

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id1",
        release_dir=release_dir, runtime_cache_dir=runtime_cache_dir, windows_host=fake_host,
        timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    assert result.ok is True


def test_verify_deployment_fails_when_it_never_becomes_healthy(fake_host: WindowsHost, tmp_path: Path) -> None:
    """Nothing is listening at all -- the bounded-timeout failure path,
    with an honest reason, never a silent hang."""

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id1",
        release_dir=tmp_path / "releases" / "aaaaaaa", runtime_cache_dir=tmp_path / "cache" / "runtime" / "h",
        windows_host=fake_host, timeout_seconds=0.05, poll_interval_seconds=0.01, sleep=_NO_SLEEP,
    )

    assert result.ok is False
    assert "never became" in result.reason


def test_verify_deployment_fails_with_a_specific_reason_on_commit_mismatch(
    os_sim: FakeWindowsOS, fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """Requirement: 'old build cannot masquerade as new' -- a *different*
    commit answering the port must be reported by name, not accepted."""

    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=str(tmp_path / "releases" / "aaaaaaa" / "python" / "pythonw.exe"),
        git_commit="z" * 40, build_id="some-other-build", instance_id="instance-1",
    )

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id1",
        release_dir=tmp_path / "releases" / "aaaaaaa", runtime_cache_dir=tmp_path / "cache" / "runtime" / "h",
        windows_host=fake_host, timeout_seconds=0.05, poll_interval_seconds=0.01, sleep=_NO_SLEEP,
    )

    assert result.ok is False
    assert "z" * 40 in result.reason
    assert "a" * 40 in result.reason


def test_verify_deployment_fails_with_a_specific_reason_on_build_id_mismatch(
    os_sim: FakeWindowsOS, fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """The exact 'old build cannot masquerade as new' proof at the
    verification layer: the *same commit*, but a stale build_id (an old
    build of that commit still actually running) is rejected by name."""

    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=str(tmp_path / "releases" / "aaaaaaa" / "python" / "pythonw.exe"),
        git_commit="a" * 40, build_id="stale-build-of-the-same-commit", instance_id="instance-1",
    )

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="the-fresh-build",
        release_dir=tmp_path / "releases" / "aaaaaaa", runtime_cache_dir=tmp_path / "cache" / "runtime" / "h",
        windows_host=fake_host, timeout_seconds=0.05, poll_interval_seconds=0.01, sleep=_NO_SLEEP,
    )

    assert result.ok is False
    assert "old build" in result.reason
    assert "stale-build-of-the-same-commit" in result.reason


def test_verify_deployment_fails_when_the_running_process_is_from_an_unrelated_path(
    os_sim: FakeWindowsOS, fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """Defense in depth on top of the commit/build_id proof: even a
    correct-looking identity running from a completely unrelated
    executable path is refused."""

    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=r"C:\Some\Completely\Unrelated\Place\pythonw.exe",
        git_commit="a" * 40, build_id="id1", instance_id="instance-1",
    )

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id1",
        release_dir=tmp_path / "releases" / "aaaaaaa", runtime_cache_dir=tmp_path / "cache" / "runtime" / "h",
        windows_host=fake_host, timeout_seconds=0.05, poll_interval_seconds=0.01, sleep=_NO_SLEEP,
    )

    assert result.ok is False
    assert "neither the release directory nor its runtime cache" in result.reason


def test_verify_deployment_fails_on_invalid_schema_health(os_sim: FakeWindowsOS, fake_host: WindowsHost, tmp_path: Path) -> None:
    release_dir = tmp_path / "releases" / "aaaaaaa"
    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=str(release_dir / "python" / "pythonw.exe"),
        git_commit="a" * 40, build_id="id1", instance_id="instance-1", schema_version=0,  # invalid: must be >= 1
    )

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id1",
        release_dir=release_dir, runtime_cache_dir=tmp_path / "cache" / "runtime" / "h", windows_host=fake_host,
        timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    assert result.ok is False
    assert "database_schema_version" in result.reason


def test_verify_deployment_does_not_require_ready_true(os_sim: FakeWindowsOS, fake_host: WindowsHost, tmp_path: Path) -> None:
    """This tool verifies the *deployment*, never the product's own
    onboarding/readiness state -- a fresh dev instance honestly reporting
    'no camera configured yet' is a successful deployment."""

    release_dir = tmp_path / "releases" / "aaaaaaa"
    os_sim.start_listener(
        port=DEFAULT_PORT, image_path=str(release_dir / "python" / "pythonw.exe"),
        git_commit="a" * 40, build_id="id1", instance_id="instance-1",
    )
    # `/api/product/health`'s `ready` field is never even inspected by
    # verify_deployment -- the fake host's response never sets it either,
    # matching a real ProductHealthStatus's `ready=False` first-run state.

    result = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id1",
        release_dir=release_dir, runtime_cache_dir=tmp_path / "cache" / "runtime" / "h", windows_host=fake_host,
        timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    assert result.ok is True


# ---------------------------------------------------------------------------
# deploy(): the one-command deployment, end to end (via --artifact
# acceptance -- no real git/build needed; build_release_source's git
# wiring is covered separately above).
# ---------------------------------------------------------------------------


def test_deploy_first_ever_deployment(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")

    report = deploy(
        repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle,
        verify_timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    assert report.sha == short_sha("a" * 40, cwd=ROOT)
    assert report.verification.ok is True
    assert report.previous_release_sha is None
    assert report.pid is not None
    assert release_directory_for(dev_root, report.sha).is_dir()
    assert read_current(dev_root).sha == report.sha


def test_deploy_versions_by_short_sha_under_localappdata_mockingbirddev(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost,
) -> None:
    bundle = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")

    report = deploy(
        repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle,
        verify_timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    expected_dir = dev_root / RELEASES_DIRNAME / short_sha("a" * 40, cwd=ROOT)
    assert Path(report.release_dir_windows) == expected_dir
    assert expected_dir.is_dir()
    assert dev_root.name == DEV_ROOT_DIRNAME
    assert dev_root.parent.name == "LOCALAPPDATA"  # this fixture's stand-in for %LOCALAPPDATA%


def test_deploy_stops_the_previous_release_and_reports_it(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b")
    report_a = deploy(
        repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_a,
        verify_timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    report_b = deploy(
        repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_b,
        verify_timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    assert report_b.previous_release_sha == report_a.sha
    # Requirement: previous release retained (directory still on disk).
    assert release_directory_for(dev_root, report_a.sha).is_dir()
    assert report_b.verification.reported_git_commit == "b" * 40


def test_deploy_reuses_the_runtime_cache_across_an_app_only_redeploy(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost,
) -> None:
    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a", app_content="APP=1\n")
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b", app_content="APP=2\n")

    deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_a, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)
    deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_b, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)

    runtime_cache_dirs = list((dev_root / "runtime").iterdir())
    assert len(runtime_cache_dirs) == 1  # one shared runtime cache entry, not two


def test_deploy_never_overwrites_an_existing_release_for_a_different_commit(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A short-sha collision between two different commits (astronomically
    unlikely in practice) must refuse rather than silently overwrite."""

    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_a, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)

    colliding_sha = short_sha("a" * 40, cwd=ROOT)
    # `runpy.run_path`'s *returned* dict (`_MODULE`) is a disconnected
    # snapshot, not the live module namespace every function defined in it
    # actually shares -- monkeypatching it would never be seen by `deploy`.
    # Patch through a function's own `__globals__` instead, matching the
    # established convention in tests/test_local_product_packaging.py.
    monkeypatch.setitem(deploy.__globals__, "short_sha", lambda _commit, *, cwd: colliding_sha)
    bundle_c = make_bundle(tmp_path / "build-c", git_commit="c" * 40, build_id="id-c")

    with pytest.raises(DeploymentError, match="already exists"):
        deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_c, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)


def test_deploy_redeploying_the_identical_commit_is_idempotent(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost,
) -> None:
    bundle = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")

    first = deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)
    second = deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)

    assert first.sha == second.sha
    assert second.verification.ok is True


def test_deploy_redeploying_the_identical_commit_from_a_fresh_rebuild_is_idempotent(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost,
) -> None:
    """Regression test for the realistic shape of an idempotent redeploy:
    a real `python scripts/deploy_windows_dev.py` rerun with no intervening
    commit always goes through `build_release_source` -> `build_local_
    product`, which mints a brand new random `build_id` on *every*
    invocation regardless of whether the commit changed -- unlike
    `accept_release_source` (`--artifact`), which just reads whatever
    `build_id` is already on the given bundle's disk. The test above only
    exercises the latter (both calls share one `bundle`/`build_id`), so it
    never caught this: a second deploy of the same commit reused the
    already-materialized release directory (correct -- nothing changed)
    but then verified against the brand new build's own `build_id`, which
    was never written into that reused directory (`materialize_release`
    never reran) -- rejecting its own legitimate idempotent reuse, every
    time, unconditionally. Simulated here with two separate bundles that
    share a commit but (like two independent real builds of it) do not
    share a `build_id`."""

    bundle_1 = make_bundle(tmp_path / "build-1", git_commit="a" * 40, build_id="first-build-id")
    bundle_2 = make_bundle(tmp_path / "build-2", git_commit="a" * 40, build_id="second-build-id")

    first = deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_1, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)
    second = deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_2, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)

    assert first.sha == second.sha
    assert second.verification.ok is True
    # The release directory was genuinely reused, not silently rebuilt out
    # from under the first deploy's own materialization.
    assert second.verification.reported_build_id == "first-build-id"


def test_deploy_failure_leaves_the_previous_release_usable(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost,
) -> None:
    """Requirement: 'failure leaves previous release usable'. A new build
    that crashes on startup (the realistic failure mode: it never binds
    the port at all, so `verify_deployment` times out) must not disturb
    the still-retained, still-launchable previous release -- and must not
    even mark itself "current", so a plain retry or `--rollback` both see
    the last known-good release as authoritative.
    """

    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    report_a = deploy(
        repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_a,
        verify_timeout_seconds=5.0, sleep=_NO_SLEEP,
    )

    # Bundle B "crashes on startup": its launcher runs (materialization
    # succeeds) but nothing ever actually binds the port.
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b")
    crashes_on_startup_host = dataclasses.replace(fake_host, launch_release=lambda _release_dir, _extra_env: None)

    with pytest.raises(DeploymentError, match="verification failed"):
        deploy(
            repo_root=ROOT, dev_root=dev_root, windows_host=crashes_on_startup_host, artifact_path=bundle_b,
            verify_timeout_seconds=0.05, poll_interval_seconds=0.01, sleep=_NO_SLEEP,
        )

    # The new (broken) release directory was still materialized (so it can
    # be inspected/retried) but the previous, known-good release is
    # untouched and its directory is still there.
    assert release_directory_for(dev_root, report_a.sha).is_dir()
    sha_b = short_sha("b" * 40, cwd=ROOT)
    assert release_directory_for(dev_root, sha_b).is_dir()

    # A failed deploy never marks itself current -- the last known-good
    # release is still what the ledger says is running.
    assert read_current(dev_root).sha == report_a.sha

    # And release A is genuinely still launchable: nothing is holding the
    # port (the crashed launch never bound it), so a plain relaunch of the
    # retained release directory verifies cleanly.
    launch_release(
        release_directory_for(dev_root, report_a.sha), host=DEFAULT_HOST, port=DEFAULT_PORT,
        userdata_dir=dev_root / USERDATA_DIRNAME, windows_host=fake_host,
    )
    recovery = verify_deployment(
        host=DEFAULT_HOST, port=DEFAULT_PORT, expected_commit="a" * 40, expected_build_id="id-a",
        release_dir=release_directory_for(dev_root, report_a.sha), runtime_cache_dir=dev_root / "runtime" / "irrelevant",
        windows_host=fake_host, timeout_seconds=5.0, sleep=_NO_SLEEP,
    )
    assert recovery.ok is True


def test_deploy_uses_one_shared_userdata_directory_across_redeploys(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost,
) -> None:
    """Requirement: preserve the real MockingBird user-data directory /
    never reset Camera Nodes -- the dev instance's own data directory must
    be the *same* path across every redeploy, never per-release."""

    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b")

    deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_a, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)
    deploy(repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle_b, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)

    calls = fake_host.launch_release.calls  # type: ignore[attr-defined]
    assert len(calls) == 2
    userdata_dirs = {call["extra_env"]["MOCKINGBIRD_HOME"] for call in calls}
    assert len(userdata_dirs) == 1
    assert userdata_dirs == {str(dev_root / USERDATA_DIRNAME)}


def test_deploy_fails_fast_on_a_non_default_port_before_any_build_work(
    tmp_path: Path, dev_root: Path, fake_host: WindowsHost,
) -> None:
    """The packaged launcher can only ever run on 127.0.0.1:8000 -- this
    must be rejected immediately, never after materializing a release that
    could then never actually be launched."""

    bundle = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")

    with pytest.raises(DeploymentError, match="127.0.0.1:8000"):
        deploy(
            repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle, port=9000,
            verify_timeout_seconds=5.0, sleep=_NO_SLEEP,
        )

    assert not (dev_root / RELEASES_DIRNAME).exists()  # nothing was materialized


# ---------------------------------------------------------------------------
# rollback()
# ---------------------------------------------------------------------------


def _deploy(bundle: Path, *, dev_root: Path, fake_host: WindowsHost, timeout: float = 5.0):
    return deploy(
        repo_root=ROOT, dev_root=dev_root, windows_host=fake_host, artifact_path=bundle,
        verify_timeout_seconds=timeout, sleep=_NO_SLEEP,
    )


def test_rollback_stops_current_and_launches_the_previous_release(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b")
    report_a = _deploy(bundle_a, dev_root=dev_root, fake_host=fake_host)
    _deploy(bundle_b, dev_root=dev_root, fake_host=fake_host)

    report = rollback(dev_root=dev_root, windows_host=fake_host, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)

    assert report.sha == report_a.sha
    assert report.verification.reported_git_commit == "a" * 40
    assert read_current(dev_root).sha == report_a.sha


def test_rollback_with_nothing_deployed_yet_refuses(dev_root: Path, fake_host: WindowsHost) -> None:
    with pytest.raises(DeploymentError, match="no rollback target"):
        rollback(dev_root=dev_root, windows_host=fake_host)


def test_rollback_with_no_previous_release_retained_refuses(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    _deploy(make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a"), dev_root=dev_root, fake_host=fake_host)

    with pytest.raises(DeploymentError, match="No previous release"):
        rollback(dev_root=dev_root, windows_host=fake_host, sleep=_NO_SLEEP)


def test_rollback_never_touches_user_data(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b")
    _deploy(bundle_a, dev_root=dev_root, fake_host=fake_host)
    _deploy(bundle_b, dev_root=dev_root, fake_host=fake_host)

    rollback(dev_root=dev_root, windows_host=fake_host, verify_timeout_seconds=5.0, sleep=_NO_SLEEP)

    calls = fake_host.launch_release.calls  # type: ignore[attr-defined]
    userdata_dirs = {call["extra_env"]["MOCKINGBIRD_HOME"] for call in calls}
    assert userdata_dirs == {str(dev_root / USERDATA_DIRNAME)}  # same one shared dir, every time


def test_rollback_refuses_when_the_current_port_occupant_is_unverified(
    tmp_path: Path, dev_root: Path, os_sim: FakeWindowsOS, fake_host: WindowsHost,
) -> None:
    """Rollback applies the exact same stop-safety proof as any other stop
    -- it is not a special case that bypasses it."""

    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b")
    _deploy(bundle_a, dev_root=dev_root, fake_host=fake_host)
    _deploy(bundle_b, dev_root=dev_root, fake_host=fake_host)

    # Something else now occupies the port -- as if a developer manually
    # started an unrelated service after the last dev deploy.
    for port in list(os_sim.listeners):
        del os_sim.listeners[port]
    os_sim.start_non_mockingbird_listener(port=DEFAULT_PORT, pid=7777)

    with pytest.raises(DeploymentError, match="not a healthy MockingBird"):
        rollback(dev_root=dev_root, windows_host=fake_host, sleep=_NO_SLEEP)


def test_rollback_fails_fast_on_a_non_default_port(dev_root: Path, fake_host: WindowsHost) -> None:
    with pytest.raises(DeploymentError, match="127.0.0.1:8000"):
        rollback(dev_root=dev_root, windows_host=fake_host, port=9000, sleep=_NO_SLEEP)


# ---------------------------------------------------------------------------
# Cleanup: bounded, protects current + rollback target
# ---------------------------------------------------------------------------


def test_cleanup_releases_keeps_the_most_recent_n(dev_root: Path, fake_host: WindowsHost) -> None:
    for sha in ("aaaaaaa", "bbbbbbb", "ccccccc", "ddddddd"):
        append_deployment(dev_root, _record(sha, commit=sha * 6, build_id=f"id-{sha}"), windows_host=fake_host)
        release_directory_for(dev_root, sha).mkdir(parents=True)

    removed = cleanup_releases(dev_root=dev_root, keep=2, protected_shas=(), windows_host=fake_host)

    assert set(removed) == {"aaaaaaa", "bbbbbbb"}
    assert release_directory_for(dev_root, "ccccccc").is_dir()
    assert release_directory_for(dev_root, "ddddddd").is_dir()


def test_cleanup_releases_never_removes_a_protected_sha_even_with_keep_zero(dev_root: Path, fake_host: WindowsHost) -> None:
    for sha in ("aaaaaaa", "bbbbbbb", "ccccccc"):
        append_deployment(dev_root, _record(sha, commit=sha * 6, build_id=f"id-{sha}"), windows_host=fake_host)
        release_directory_for(dev_root, sha).mkdir(parents=True)

    removed = cleanup_releases(dev_root=dev_root, keep=0, protected_shas={"aaaaaaa"}, windows_host=fake_host)

    assert "aaaaaaa" not in removed
    assert release_directory_for(dev_root, "aaaaaaa").is_dir()
    assert set(removed) == {"bbbbbbb", "ccccccc"}


def test_cleanup_command_protects_current_and_rollback_target(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    for letter in "abcde":
        bundle = make_bundle(tmp_path / f"build-{letter}", git_commit=letter * 40, build_id=f"id-{letter}")
        _deploy(bundle, dev_root=dev_root, fake_host=fake_host)

    removed = cleanup_command(dev_root=dev_root, keep=1, windows_host=fake_host)

    current_sha = read_current(dev_root).sha
    assert current_sha not in removed
    assert release_directory_for(dev_root, current_sha).is_dir()
    previous = previous_release_for_rollback(dev_root, exclude_sha=current_sha)
    assert previous is not None
    assert previous.sha not in removed
    assert release_directory_for(dev_root, previous.sha).is_dir()
    # 5 deployed; "current" is already the single most-recent kept by
    # keep=1, so protecting it *and* the separate rollback target (the
    # next-most-recent) keeps exactly 2 releases in total -- the other 3
    # are removed.
    assert len(removed) == 3


def test_cleanup_never_touches_the_runtime_or_model_cache(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    bundle_b = make_bundle(tmp_path / "build-b", git_commit="b" * 40, build_id="id-b")
    _deploy(bundle_a, dev_root=dev_root, fake_host=fake_host)
    _deploy(bundle_b, dev_root=dev_root, fake_host=fake_host)
    runtime_entries_before = sorted(p.name for p in (dev_root / "runtime").iterdir())
    model_entries_before = sorted(p.name for p in (dev_root / "models").iterdir())

    cleanup_command(dev_root=dev_root, keep=0, windows_host=fake_host)

    assert sorted(p.name for p in (dev_root / "runtime").iterdir()) == runtime_entries_before
    assert sorted(p.name for p in (dev_root / "models").iterdir()) == model_entries_before


def test_cleanup_never_touches_user_data(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle_a = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    _deploy(bundle_a, dev_root=dev_root, fake_host=fake_host)
    userdata_dir = dev_root / USERDATA_DIRNAME
    (userdata_dir / "mockingbird.sqlite3").write_text("pretend database", encoding="utf-8")

    cleanup_command(dev_root=dev_root, keep=0, windows_host=fake_host)

    assert (userdata_dir / "mockingbird.sqlite3").is_file()


# ---------------------------------------------------------------------------
# status_report: read-only
# ---------------------------------------------------------------------------


def test_status_report_before_any_deploy(dev_root: Path, fake_host: WindowsHost) -> None:
    report = status_report(dev_root=dev_root, windows_host=fake_host)

    assert "No deployment recorded" in report
    assert "free" in report


def test_status_report_reflects_a_running_verified_release(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    report = _deploy(bundle, dev_root=dev_root, fake_host=fake_host)

    text = status_report(dev_root=dev_root, windows_host=fake_host)

    assert report.sha in text
    assert "verified dev release" in text


# ---------------------------------------------------------------------------
# The production ZIP remains independently self-contained: nothing in this
# script ever mutates a source bundle it reads from -- it only reads from
# `bundle_dir` and writes to a *separate* cache/release directory. A real
# `build_local_product.py` artifact built for end-user distribution is
# therefore completely unaffected regardless of whether this dev-deployment
# tool ever runs against it at all.
# ---------------------------------------------------------------------------


def _bundle_fingerprint(bundle_dir: Path) -> dict[str, tuple[int, bytes]]:
    return {
        str(path.relative_to(bundle_dir)): (path.stat().st_size, path.read_bytes())
        for path in sorted(bundle_dir.rglob("*"))
        if path.is_file()
    }


def test_deploying_never_mutates_the_source_bundle(tmp_path: Path, dev_root: Path, fake_host: WindowsHost) -> None:
    bundle = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")
    before = _bundle_fingerprint(bundle)

    _deploy(bundle, dev_root=dev_root, fake_host=fake_host)

    after = _bundle_fingerprint(bundle)
    assert after == before  # byte-for-byte identical -- untouched by deploy, cache population, or materialization


def test_a_fresh_bundle_has_no_symlinks_or_external_references_of_its_own(tmp_path: Path) -> None:
    """The artifact `build_local_product.py` actually ships is plain files
    throughout -- self-contained by construction, before this dev tool
    (which only ever *reads* it) is involved at all."""

    bundle = make_bundle(tmp_path / "build-a", git_commit="a" * 40, build_id="id-a")

    for path in bundle.rglob("*"):
        assert not path.is_symlink(), f"{path} must not be a symlink in a real production bundle"


def test_retrying_rmdir_powershell_script_shape() -> None:
    """Pure string-generation test for the one PowerShell script real
    junction/tree removal is built on (see `_remove_junction_real`/
    `_remove_tree_real`) -- the actual removal behavior against a real
    Windows host (retry-and-verify against a transiently busy path) was
    validated by hand, see docs/windows-dev-deployment-design.md; this
    guards the generated script's shape doesn't silently regress (a bounded
    retry loop, a real `Test-Path` re-check, and reports exactly `GONE` or
    `STILL-PRESENT` -- what `_run_verified_removal` parses)."""

    script = _retrying_rmdir_powershell(_ps_quote(r"C:\Users\dev\AppData\Local\Temp\some path"), recursive=False)

    assert "Test-Path $target" in script
    assert "cmd.exe /c" in script
    assert "rmdir " in script
    assert "/s /q" not in script  # non-recursive: never the bulk-delete flags
    assert "GONE" in script
    assert "STILL-PRESENT" in script
    assert "some path''" not in script  # a literal single quote in the path would need doubling; this one has none

    recursive_script = _retrying_rmdir_powershell(_ps_quote("C:\\a"), recursive=True)
    assert "/s /q" in recursive_script


def test_ps_quote_escapes_embedded_single_quotes() -> None:
    assert _ps_quote("C:\\a'b") == "C:\\a''b"
    assert _ps_quote("no quotes here") == "no quotes here"


# ---------------------------------------------------------------------------
# CLI: argument parsing and dispatch (the underlying behavior is already
# covered directly above; these confirm main() wires flags to the right
# operation and turns a DeploymentError into a clean exit code, never a
# traceback).
# ---------------------------------------------------------------------------


def test_build_argument_parser_defaults() -> None:
    args = build_argument_parser().parse_args([])

    assert args.commit == "HEAD"
    assert args.host == DEFAULT_HOST
    assert args.port == DEFAULT_PORT
    assert args.rollback is False
    assert args.status is False
    assert args.cleanup is False
    assert args.keep is None


def _dummy_report(sha: str = "aaaaaaa") -> DeployReport:
    return DeployReport(
        sha=sha, release_dir_windows=f"C:\\MockingBirdDev\\releases\\{sha}", pid=1234,
        url="http://127.0.0.1:8000", previous_release_sha=None,
        verification=VerificationResult(ok=True, reason="ok"),
    )


def test_main_dispatches_to_deploy_by_default(monkeypatch: pytest.MonkeyPatch, fake_host: WindowsHost) -> None:
    calls: list[str] = []
    monkeypatch.setitem(main.__globals__, "real_windows_host", lambda: fake_host)
    monkeypatch.setitem(main.__globals__, "deploy", lambda **_kwargs: calls.append("deploy") or _dummy_report())
    monkeypatch.setitem(main.__globals__, "rollback", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not be called")))
    monkeypatch.setitem(main.__globals__, "cleanup_command", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not be called")))
    monkeypatch.setitem(main.__globals__, "status_report", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not be called")))

    exit_code = main([])

    assert exit_code == 0
    assert calls == ["deploy"]


def test_main_dispatches_to_rollback(monkeypatch: pytest.MonkeyPatch, fake_host: WindowsHost) -> None:
    calls: list[str] = []
    monkeypatch.setitem(main.__globals__, "real_windows_host", lambda: fake_host)
    monkeypatch.setitem(main.__globals__, "rollback", lambda **_kwargs: calls.append("rollback") or _dummy_report())
    monkeypatch.setitem(main.__globals__, "deploy", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not be called")))

    exit_code = main(["--rollback"])

    assert exit_code == 0
    assert calls == ["rollback"]


def test_main_dispatches_to_status(monkeypatch: pytest.MonkeyPatch, fake_host: WindowsHost) -> None:
    calls: list[str] = []
    monkeypatch.setitem(main.__globals__, "real_windows_host", lambda: fake_host)
    monkeypatch.setitem(main.__globals__, "status_report", lambda **_kwargs: calls.append("status") or "STATUS TEXT")
    monkeypatch.setitem(main.__globals__, "deploy", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not be called")))

    exit_code = main(["--status"])

    assert exit_code == 0
    assert calls == ["status"]


@pytest.mark.parametrize("argv", [["--keep", "3"], ["--cleanup"]])
def test_main_dispatches_to_cleanup(argv: list[str], monkeypatch: pytest.MonkeyPatch, fake_host: WindowsHost) -> None:
    calls: list[dict] = []
    monkeypatch.setitem(main.__globals__, "real_windows_host", lambda: fake_host)
    monkeypatch.setitem(main.__globals__, "cleanup_command", lambda **kwargs: calls.append(kwargs) or [])
    monkeypatch.setitem(main.__globals__, "deploy", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not be called")))

    exit_code = main(argv)

    assert exit_code == 0
    assert len(calls) == 1
    expected_keep = 3 if "--keep" in argv else DEFAULT_KEEP
    assert calls[0]["keep"] == expected_keep


def test_main_turns_a_deployment_error_into_exit_code_one_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, fake_host: WindowsHost,
) -> None:
    monkeypatch.setitem(main.__globals__, "real_windows_host", lambda: fake_host)
    monkeypatch.setitem(
        main.__globals__, "deploy", lambda **_kwargs: (_ for _ in ()).throw(DeploymentError("port 8000 is occupied"))
    )

    exit_code = main([])

    assert exit_code == 1
