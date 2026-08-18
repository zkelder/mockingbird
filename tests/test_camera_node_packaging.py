import json
import os
from pathlib import Path
import runpy
import subprocess
import venv
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(ROOT / "scripts" / "build_camera_node_artifact.py")
BUILD_ARTIFACT = _MODULE["build_camera_node_artifact"]
VERIFY_CLEAN_SOURCE = _MODULE["verify_clean_camera_node_source"]
CameraNodeArtifactError = _MODULE["CameraNodeArtifactError"]


def _init_fixture_repo(directory: Path) -> None:
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(command, cwd=directory, check=True, capture_output=True)


def _commit_fixture_node_package(repo: Path) -> None:
    (repo / "src" / "mockingbird_node").mkdir(parents=True)
    (repo / "src" / "mockingbird_node" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    _init_fixture_repo(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=repo, check=True, capture_output=True)


def test_camera_node_artifact_is_slim_and_launcher_checks_without_starting(tmp_path) -> None:
    # allow_dirty_source=True: this test is about wheel *contents* and launcher
    # behavior, not source-provenance verification (covered separately below),
    # so it must not depend on whether this real checkout's own
    # src/mockingbird_node happens to be clean at test time.
    artifact = BUILD_ARTIFACT(tmp_path / "artifact", allow_dirty_source=True)
    with zipfile.ZipFile(artifact.wheel) as wheel:
        names = set(wheel.namelist())
        assert {"mockingbird_node/__init__.py", "mockingbird_node/__main__.py", "mockingbird_node/app.py", "mockingbird_node/config.py", "mockingbird_node/providers.py"} <= names
        assert not any(name.startswith(prefix) for name in names for prefix in ("mockingbird/", "web/", "tests/", "data/"))
        assert not any("sqlalchemy" in wheel.read(name).decode("utf-8", errors="ignore").lower() for name in names)

    manifest = json.loads(artifact.manifest.read_text(encoding="utf-8"))
    assert manifest["artifact"] == artifact.wheel.name
    assert manifest["source_state"] == "dirty:unverified-working-tree"
    assert manifest["provenance"]["source_clean"] is False
    assert manifest["provenance"]["git_commit"] is None or len(manifest["provenance"]["git_commit"]) == 40
    assert len(manifest["provenance"]["build_id"]) == 32
    assert manifest["provenance"]["built_at"]  # a non-empty ISO-8601 timestamp
    assert manifest["runtime_requirements"] == [
        "fastapi>=0.111,<0.116",
        "pydantic>=2.7,<3.0",
        "uvicorn[standard]>=0.30,<1.0",
    ]
    assert "MOCKINGBIRD_NODE_PROVIDERS=picamera2,v4l2" in artifact.configuration_example.read_text(encoding="utf-8")
    assert "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH=10000" in artifact.configuration_example.read_text(encoding="utf-8")
    assert "synthetic" not in artifact.requirements.read_text(encoding="utf-8")

    environment_root = tmp_path / "node-environment"
    venv.EnvBuilder(with_pip=True).create(environment_root)
    python = environment_root / "bin" / "python"
    install_result = subprocess.run(
        [python, "-m", "pip", "install", "--no-deps", artifact.wheel],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_result.returncode == 0, install_result.stderr
    environment = {**os.environ, "PYTHONNOUSERSITE": "1"}
    help_result = subprocess.run(
        [python, "-m", "mockingbird_node", "--help"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "local-only MockingBird Camera Node" in help_result.stdout
    check_result = subprocess.run(
        [python, "-m", "mockingbird_node", "--check"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check_result.returncode == 0
    assert "configuration is valid" in check_result.stdout
    picamera2_result = subprocess.run(
        [python, "-c", "from mockingbird_node.config import CameraNodeConfig; from mockingbird_node.providers import PiCamera2Provider; print(PiCamera2Provider(CameraNodeConfig.from_environment()).cameras()[0].status)"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert picamera2_result.returncode == 0, picamera2_result.stderr
    assert picamera2_result.stdout.strip() == "setup_required"


def test_default_build_calls_the_clean_source_verifier_and_records_its_commit(tmp_path, monkeypatch) -> None:
    """The default (`allow_dirty_source=False`) path must actually route
    through `verify_clean_camera_node_source` and record exactly what it
    returns -- proven hermetically (never depending on whether this real
    checkout happens to be clean at test time) by substituting a fake in the
    module's own globals, mirroring build_local_product.py's identical
    pattern for `verify_clean_tracked_source`."""

    def _fake_verify(**_kwargs: object) -> str:
        return "f" * 40

    # `runpy.run_path` returns a *copy* of the executed module's globals
    # (confirmed: `BUILD_ARTIFACT.__globals__ is not _MODULE`), so the
    # substitution must go through the live namespace every function in the
    # file actually shares -- `BUILD_ARTIFACT.__globals__` -- exactly the
    # pattern `tests/test_local_product_packaging.py` already uses for
    # `verify_clean_tracked_source`, not the dict `run_path` returned.
    monkeypatch.setitem(BUILD_ARTIFACT.__globals__, "verify_clean_camera_node_source", _fake_verify)

    artifact = BUILD_ARTIFACT(tmp_path / "artifact")

    manifest = json.loads(artifact.manifest.read_text(encoding="utf-8"))
    assert manifest["source_state"] == f"git:{'f' * 40}"
    assert manifest["provenance"] == {
        "git_commit": "f" * 40,
        "source_clean": True,
        "build_id": manifest["provenance"]["build_id"],
        "built_at": manifest["provenance"]["built_at"],
    }
    assert len(manifest["provenance"]["build_id"]) == 32


def test_default_build_refuses_a_dirty_source(tmp_path, monkeypatch) -> None:
    def _raising_verify(**_kwargs: object) -> str:
        raise CameraNodeArtifactError("uncommitted changes exist in tracked packaged-input files")

    monkeypatch.setitem(BUILD_ARTIFACT.__globals__, "verify_clean_camera_node_source", _raising_verify)

    with pytest.raises(CameraNodeArtifactError, match="uncommitted changes"):
        BUILD_ARTIFACT(tmp_path / "artifact")


def test_two_builds_of_the_same_commit_get_different_build_ids(tmp_path, monkeypatch) -> None:
    """`build_id` distinguishes independent build *invocations*, not commits
    -- see docs/camera-node-installer-design.md "Reproducibility hardening".
    The installer's update/idempotency logic depends on this."""

    monkeypatch.setitem(BUILD_ARTIFACT.__globals__, "verify_clean_camera_node_source", lambda **_kwargs: "a" * 40)

    first = BUILD_ARTIFACT(tmp_path / "first")
    second = BUILD_ARTIFACT(tmp_path / "second")

    first_manifest = json.loads(first.manifest.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest.read_text(encoding="utf-8"))
    assert first_manifest["provenance"]["git_commit"] == second_manifest["provenance"]["git_commit"]
    assert first_manifest["provenance"]["build_id"] != second_manifest["provenance"]["build_id"]


def test_verify_clean_camera_node_source_passes_on_a_clean_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _commit_fixture_node_package(repo)

    commit = VERIFY_CLEAN_SOURCE(cwd=repo)

    resolved = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert commit == resolved


def test_verify_clean_camera_node_source_ignores_untracked_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _commit_fixture_node_package(repo)

    # An untracked work-in-progress file -- never `git add`ed. This builder
    # already reads its five source files by fixed name (never a directory
    # glob), so this must never block the build.
    (repo / "src" / "mockingbird_node" / "untracked_scratch.py").write_text("oops = True\n", encoding="utf-8")

    commit = VERIFY_CLEAN_SOURCE(cwd=repo)  # must not raise
    assert len(commit) == 40


def test_verify_clean_camera_node_source_ignores_dirt_outside_its_own_path(tmp_path: Path) -> None:
    """Scoped to `src/mockingbird_node` only -- an unrelated dirty file
    elsewhere in the repository must never block a Camera Node build."""

    repo = tmp_path / "repo"
    _commit_fixture_node_package(repo)
    (repo / "src" / "mockingbird_node").parent.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# tracked elsewhere\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "add readme"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# uncommitted edit, unrelated path\n", encoding="utf-8")

    commit = VERIFY_CLEAN_SOURCE(cwd=repo)  # must not raise
    assert len(commit) == 40


def test_verify_clean_camera_node_source_fails_on_uncommitted_tracked_modification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _commit_fixture_node_package(repo)

    # An uncommitted edit to an *already-tracked* packaged-input file.
    (repo / "src" / "mockingbird_node" / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(CameraNodeArtifactError, match="uncommitted changes"):
        VERIFY_CLEAN_SOURCE(cwd=repo)


def test_allow_dirty_source_records_best_effort_commit_without_verifying_clean(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _commit_fixture_node_package(repo)
    (repo / "src" / "mockingbird_node" / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")

    current_head_commit = _MODULE["_current_head_commit"]
    commit = current_head_commit(cwd=repo)  # must not raise despite the dirty tree
    resolved = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert commit == resolved


def test_current_head_commit_is_none_with_no_git_history(tmp_path: Path) -> None:
    current_head_commit = _MODULE["_current_head_commit"]
    assert current_head_commit(cwd=tmp_path) is None
