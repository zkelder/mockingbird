"""Structural tests for scripts/build_local_product.py.

These stay hermetic and fast: no real `npm run build`, no real network fetch
of the CPython embeddable distribution, no real cross-platform PyPI
dependency resolution (CPU or GPU/CUDA), and no real multi-hundred-MB model
file (that step is injected as a fake). What they do exercise for real: the
bundle-assembly filesystem logic (`._pth` patching, stray-shim removal,
launcher/readme contents), byte-for-byte zip determinism, manifest/checksum
structure, the clean-tracked-source-snapshot release-integrity logic (real
`git` calls against small throwaway fixture repos), and the Observation
Engine model-bundle provenance verification (real SHA-256 hashing of tiny
fixture files).

Every call into `assemble_windows_bundle`/`build_local_product` below passes
an explicit fake `install_gpu_dependencies` (or `include_gpu_runtime=False`)
and a `model_bundle_source` under the test's own `tmp_path` -- never the real
~1.1 GB CUDA/cuDNN download or this repository's own real ~500 MB model file.
One exception, clearly marked and skipped when unavailable:
`test_real_local_model_bundle_matches_accepted_provenance_when_present`
reads (never writes/downloads) whatever real bundle already sits at
`DEFAULT_MODEL_BUNDLE_SOURCE` on *this* machine, the same real,
GPU-validated MDv5 artifact `build_local_product.py`'s own module docstring
describes -- a genuine, not-faked provenance proof, skipped rather than
failed on a build host that does not have it.

The full pipeline (frontend build, real wheel build, real win_amd64
dependency resolution including the GPU/CUDA stack, real model-bundle
packaging, and a fidelity boot of the assembled dependency layout) was
validated by actually running `build_local_product.py` for real during this
milestone's own validation pass -- see docs/local-product-packaging-design.md
-- rather than re-run here on every test invocation, which would require
network access and several minutes per run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(ROOT / "scripts" / "build_local_product.py")
assemble_windows_bundle = _MODULE["assemble_windows_bundle"]
build_local_product = _MODULE["build_local_product"]
export_clean_source_tree = _MODULE["export_clean_source_tree"]
package_observation_runtime_assets = _MODULE["package_observation_runtime_assets"]
sync_packaged_web_dist = _MODULE["sync_packaged_web_dist"]
verify_clean_tracked_source = _MODULE["verify_clean_tracked_source"]
write_deterministic_zip = _MODULE["write_deterministic_zip"]
write_manifest = _MODULE["write_manifest"]
LocalProductBuildError = _MODULE["LocalProductBuildError"]
ModelBundleProvenance = _MODULE["ModelBundleProvenance"]
ACCEPTED_ONNX_MODEL_SHA256 = _MODULE["ACCEPTED_ONNX_MODEL_SHA256"]
ACCEPTED_SOURCE_MODEL_SHA256 = _MODULE["ACCEPTED_SOURCE_MODEL_SHA256"]
ACCEPTED_MODEL_KEY = _MODULE["ACCEPTED_MODEL_KEY"]
ACCEPTED_MODEL_DECODER = _MODULE["ACCEPTED_MODEL_DECODER"]
ACCEPTED_MODEL_LICENSE = _MODULE["ACCEPTED_MODEL_LICENSE"]
PACKAGED_OBSERVATION_RUNTIME_DIRNAME = _MODULE["PACKAGED_OBSERVATION_RUNTIME_DIRNAME"]
PACKAGED_PROVIDER_CONFIG_FILENAME = _MODULE["PACKAGED_PROVIDER_CONFIG_FILENAME"]
DEFAULT_MODEL_BUNDLE_SOURCE = _MODULE["DEFAULT_MODEL_BUNDLE_SOURCE"]


def _noop_gpu_installer(_site_packages: Path) -> None:
    """Explicit no-op fake -- never installs anything -- for tests that must
    never trigger the real ~1.1 GB CUDA/cuDNN download."""


def _fake_embeddable_zip(directory: Path) -> Path:
    """A tiny stand-in for the real ~11 MB CPython embeddable distribution.

    Only what bundle assembly actually touches: a `python3NN._pth` file (the
    exact one shipped by python.org, unpatched) and placeholder executables.
    """

    zip_path = directory / "fake-python-embed.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "python312._pth",
            "python312.zip\n.\n\n# Uncomment to run site.main() automatically\n#import site\n",
        )
        archive.writestr("pythonw.exe", b"fake-windows-binary")
        archive.writestr("python.exe", b"fake-windows-binary")
    return zip_path


def _fake_wheel(directory: Path, *, package_name: str = "fakepkg") -> Path:
    """A minimal, genuinely `pip install`-able wheel with no dependencies."""

    files = {
        f"{package_name}/__init__.py": b"VALUE = 1\n",
        f"{package_name}-1.0.0.dist-info/METADATA": (
            f"Metadata-Version: 2.3\nName: {package_name}\nVersion: 1.0.0\n"
        ).encode(),
        f"{package_name}-1.0.0.dist-info/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: test-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    record_lines = [f"{name}," for name in files] + [f"{package_name}-1.0.0.dist-info/RECORD,,"]
    files[f"{package_name}-1.0.0.dist-info/RECORD"] = ("\n".join(record_lines) + "\n").encode()

    wheel_path = directory / f"{package_name}-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return wheel_path


def _fake_web_dist(directory: Path) -> Path:
    dist = directory / "fake-web-dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>MockingBird</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok');", encoding="utf-8")
    return dist


def test_sync_packaged_web_dist_copies_the_built_frontend_to_a_target(tmp_path: Path) -> None:
    fake_dist = _fake_web_dist(tmp_path)
    target = tmp_path / "packaged-web-dist"

    result = sync_packaged_web_dist(source_dist=fake_dist, target_dir=target)

    assert result == target
    assert (target / "index.html").read_text(encoding="utf-8") == (fake_dist / "index.html").read_text(
        encoding="utf-8"
    )
    assert (target / "assets" / "app.js").is_file()


def test_sync_packaged_web_dist_refuses_a_missing_build(tmp_path: Path) -> None:
    missing_dist = tmp_path / "no-such-dist"

    try:
        sync_packaged_web_dist(source_dist=missing_dist, target_dir=tmp_path / "target")
    except LocalProductBuildError as error:
        assert "No built frontend" in str(error)
    else:
        raise AssertionError("expected LocalProductBuildError for a missing frontend build")


def test_assemble_windows_bundle_produces_a_python_and_pip_free_user_experience(tmp_path: Path) -> None:
    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")
    bundle_dir = tmp_path / "bundle"
    installed_targets: list[Path] = []

    def fake_install_dependencies(site_packages: Path) -> None:
        installed_targets.append(site_packages)
        # Simulate a stray host-OS console-script shim, matching what a real
        # cross-platform `pip install --target` leaves behind.
        (site_packages / "bin").mkdir(parents=True)
        (site_packages / "bin" / "some-console-script").write_text("#!/bin/sh\n", encoding="utf-8")
        (site_packages / "fastapi_stub").mkdir()
        (site_packages / "fastapi_stub" / "__init__.py").write_text("", encoding="utf-8")

    bundle_dir_result, model_provenance = assemble_windows_bundle(
        bundle_dir=bundle_dir,
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=fake_install_dependencies,
        install_gpu_dependencies=_noop_gpu_installer,
        model_bundle_source=None,
    )

    assert bundle_dir_result == bundle_dir
    assert installed_targets == [bundle_dir / "python" / "site-packages"]
    assert model_provenance.included is False
    assert model_provenance.reason == "no_model_bundle_source_supplied"

    # No Python/pip/npm knowledge needed: one launcher, no visible interpreter
    # concept, no console window (`pythonw.exe`, window style 0).
    launcher = (bundle_dir / "Start MockingBird.vbs").read_text(encoding="utf-8")
    assert "pythonw.exe" in launcher
    assert "-m mockingbird" in launcher
    assert ", 0, False" in launcher
    assert (bundle_dir / "README-FIRST.txt").is_file()

    # The interpreter is pre-wired to see the pre-installed packages -- no
    # `site` module, no pip, no venv activation step for the user.
    pth_text = (bundle_dir / "python" / "python312._pth").read_text(encoding="utf-8")
    assert "site-packages" in pth_text.splitlines()
    assert "import site" not in pth_text.replace("#import site", "")

    site_packages = bundle_dir / "python" / "site-packages"
    assert (site_packages / "mockingbird" / "__init__.py").is_file()
    assert (site_packages / "fastapi_stub").is_dir()
    # The host-OS (Linux, here) script shim a cross-platform install leaves
    # behind is meaningless on Windows and is never used by the launcher;
    # it must not ship in the bundle.
    assert not (site_packages / "bin").exists()
    assert not (site_packages / "Scripts").exists()


def test_assemble_windows_bundle_includes_gpu_runtime_by_default_via_injected_installer(
    tmp_path: Path,
) -> None:
    """`include_gpu_runtime` defaults to True (a real release always wants
    the GPU stack) -- proven here with a fake installer, never the real
    ~1.1 GB download."""

    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")
    gpu_installed_targets: list[Path] = []

    _, _provenance = assemble_windows_bundle(
        bundle_dir=tmp_path / "bundle",
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=lambda _target: None,
        install_gpu_dependencies=gpu_installed_targets.append,
        model_bundle_source=None,
    )

    assert gpu_installed_targets == [tmp_path / "bundle" / "python" / "site-packages"]


def test_assemble_windows_bundle_skip_gpu_runtime_never_calls_installer(tmp_path: Path) -> None:
    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")
    calls: list[Path] = []

    assemble_windows_bundle(
        bundle_dir=tmp_path / "bundle",
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=lambda _target: None,
        install_gpu_dependencies=calls.append,
        include_gpu_runtime=False,
        model_bundle_source=None,
    )

    assert calls == []


def test_patch_pth_file_is_idempotent(tmp_path: Path) -> None:
    _patch_pth_file = _MODULE["_patch_pth_file"]
    python_dir = tmp_path / "python"
    python_dir.mkdir()
    pth_path = python_dir / "python312._pth"
    pth_path.write_text("python312.zip\n.\n", encoding="utf-8")

    _patch_pth_file(python_dir)
    _patch_pth_file(python_dir)

    assert pth_path.read_text(encoding="utf-8").count("site-packages") == 1


def test_deterministic_zip_is_byte_identical_across_rebuilds_of_identical_input(tmp_path: Path) -> None:
    source_dir = tmp_path / "bundle"
    (source_dir / "sub").mkdir(parents=True)
    (source_dir / "a.txt").write_text("hello", encoding="utf-8")
    (source_dir / "sub" / "b.txt").write_text("world", encoding="utf-8")

    first = write_deterministic_zip(source_dir, tmp_path / "out1.zip")
    first_bytes = first.read_bytes()
    # Rewriting one file with identical content changes its mtime on disk;
    # a truly deterministic zip must not let that leak into the archive.
    (source_dir / "a.txt").write_text("hello", encoding="utf-8")
    second = write_deterministic_zip(source_dir, tmp_path / "out2.zip")

    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second.read_bytes()).hexdigest()


def test_write_manifest_records_provenance_without_leaking_local_paths(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "python").mkdir(parents=True)
    (bundle_dir / "python" / "marker.txt").write_text("x", encoding="utf-8")
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")

    manifest_path, checksums_path = write_manifest(
        output_dir=tmp_path,
        bundle_dir=bundle_dir,
        zip_path=zip_path,
        source_state="test-fixture-state",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_state"] == "test-fixture-state"
    assert manifest["package"] == "mockingbird-local-product-windows-x64"
    assert manifest["zip_sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert str(tmp_path) not in json.dumps(manifest)

    checksums_text = checksums_path.read_text(encoding="utf-8")
    assert zip_path.name in checksums_text
    assert manifest["zip_sha256"] in checksums_text


def test_write_manifest_records_gpu_and_model_bundle_provenance(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")
    provenance = ModelBundleProvenance(
        included=True,
        model_key="md-v5a",
        model_version="MDv5a.0.1-onnx-opset18",
        decoder_key="megadetector_v5_yolov5_raw_v1",
        license_name="MIT",
        source_model_sha256=ACCEPTED_SOURCE_MODEL_SHA256,
        onnx_model_sha256=ACCEPTED_ONNX_MODEL_SHA256,
    )

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path,
        source_state="git:deadbeef", model_bundle_provenance=provenance, gpu_runtime_included=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["gpu_runtime_included"] is True
    assert manifest["gpu_runtime_requirements"]  # non-empty
    assert manifest["observation_model_bundle"]["included"] is True
    assert manifest["observation_model_bundle"]["onnx_model_sha256"] == ACCEPTED_ONNX_MODEL_SHA256
    assert manifest["observation_model_bundle"]["source_model_sha256"] == ACCEPTED_SOURCE_MODEL_SHA256
    assert manifest["observation_model_bundle"]["license"] == "MIT"


def test_write_manifest_records_missing_model_bundle_honestly(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path, source_state="git:deadbeef",
        model_bundle_provenance=ModelBundleProvenance(included=False, reason="no_model_bundle_source_supplied"),
        gpu_runtime_included=False,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["observation_model_bundle"]["included"] is False
    assert manifest["observation_model_bundle"]["reason"] == "no_model_bundle_source_supplied"
    assert manifest["gpu_runtime_included"] is False
    assert manifest["gpu_runtime_requirements"] == []


# --- Observation Engine model bundle packaging/provenance -------------------


def _valid_model_bundle_source(directory: Path, *, onnx_bytes: bytes = b"fixture-onnx-weights") -> Path:
    """A source directory shaped exactly like the real, already-accepted
    `data/models/observation-onnx-cuda/` convention, but with the *content*
    swapped for a tiny fixture -- tests must never depend on this
    repository's real ~500 MB model file. `onnx_bytes` lets a test produce
    a bundle whose declared fingerprint matches ACCEPTED_ONNX_MODEL_SHA256
    (by monkeypatching the accepted-hash constants) without shipping a real
    model."""

    source = directory / "observation-onnx-cuda"
    source.mkdir()
    onnx_path = source / "model.onnx"
    onnx_path.write_bytes(onnx_bytes)
    onnx_sha256 = hashlib.sha256(onnx_bytes).hexdigest()
    (source / "model-bundle.json").write_text(
        json.dumps({
            "model_key": ACCEPTED_MODEL_KEY,
            "model_version": "MDv5a.0.1-onnx-opset18",
            "model_file": "model.onnx",
            "model_fingerprint": onnx_sha256,
            "source_model_fingerprint": ACCEPTED_SOURCE_MODEL_SHA256,
            "decoder_key": ACCEPTED_MODEL_DECODER,
            "license": ACCEPTED_MODEL_LICENSE,
        }),
        encoding="utf-8",
    )
    (source / "frame-driven-provider-config.json").write_text(
        json.dumps({"schema_version": 1, "model_bundle": "model-bundle.json", "settings": {}}),
        encoding="utf-8",
    )
    return source


def test_package_observation_runtime_assets_accepts_the_exact_accepted_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uses a tiny fixture .onnx whose SHA-256 is monkeypatched in as the
    "accepted" hash -- proves the verification/copy logic without shipping
    (or requiring) the real multi-hundred-MB model in the test suite."""

    onnx_bytes = b"tiny-fixture-onnx-weights-standing-in-for-the-real-mdv5-export"
    source = _valid_model_bundle_source(tmp_path, onnx_bytes=onnx_bytes)
    monkeypatch.setitem(
        package_observation_runtime_assets.__globals__,
        "ACCEPTED_ONNX_MODEL_SHA256",
        hashlib.sha256(onnx_bytes).hexdigest(),
    )
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_observation_runtime_assets(site_packages=site_packages, model_bundle_source=source)

    assert provenance.included is True
    assert provenance.reason is None
    assert provenance.model_key == ACCEPTED_MODEL_KEY
    assert provenance.onnx_model_sha256 == hashlib.sha256(onnx_bytes).hexdigest()
    assert provenance.source_model_sha256 == ACCEPTED_SOURCE_MODEL_SHA256

    destination = site_packages / "mockingbird" / PACKAGED_OBSERVATION_RUNTIME_DIRNAME
    packaged_config = json.loads((destination / PACKAGED_PROVIDER_CONFIG_FILENAME).read_text(encoding="utf-8"))
    assert packaged_config["model_bundle"] == "model-bundle.json"
    packaged_manifest = json.loads((destination / "model-bundle.json").read_text(encoding="utf-8"))
    assert packaged_manifest["model_file"] == "model.onnx"
    assert (destination / "model.onnx").read_bytes() == onnx_bytes


def test_package_observation_runtime_assets_rejects_a_bundle_that_does_not_match_accepted_provenance(
    tmp_path: Path,
) -> None:
    """A model whose SHA-256 does not match `ACCEPTED_ONNX_MODEL_SHA256`
    (the real, doctrine-recorded hash -- never monkeypatched in this test)
    is refused, not silently packaged as if it were the accepted model."""

    source = _valid_model_bundle_source(tmp_path, onnx_bytes=b"a-different-unapproved-model-file")
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_observation_runtime_assets(site_packages=site_packages, model_bundle_source=source)

    assert provenance.included is False
    assert provenance.reason is not None and "does_not_match_accepted_provenance" in provenance.reason
    assert not (site_packages / "mockingbird" / PACKAGED_OBSERVATION_RUNTIME_DIRNAME).exists()


def test_package_observation_runtime_assets_rejects_a_corrupt_model_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The manifest's own declared fingerprint no longer matches the file
    next to it (truncated/corrupted download) -- refused before the
    accepted-provenance comparison even runs, with a specific reason."""

    onnx_bytes = b"originally-fine-bytes"
    source = _valid_model_bundle_source(tmp_path, onnx_bytes=onnx_bytes)
    monkeypatch.setitem(
        package_observation_runtime_assets.__globals__,
        "ACCEPTED_ONNX_MODEL_SHA256",
        hashlib.sha256(onnx_bytes).hexdigest(),
    )
    # Corrupt the file in place after the manifest already recorded the
    # original (good) hash.
    (source / "model.onnx").write_bytes(b"corrupted-after-the-manifest-was-written")
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_observation_runtime_assets(site_packages=site_packages, model_bundle_source=source)

    assert provenance.included is False
    assert provenance.reason == "model_file_corrupt_or_hash_mismatch"


def test_package_observation_runtime_assets_missing_source_is_honest_not_fatal(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_observation_runtime_assets(
        site_packages=site_packages, model_bundle_source=tmp_path / "no-such-directory",
    )

    assert provenance.included is False
    assert provenance.reason == "no_model_bundle_source_supplied"


def test_package_observation_runtime_assets_none_source_is_honest_not_fatal(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_observation_runtime_assets(site_packages=site_packages, model_bundle_source=None)

    assert provenance.included is False
    assert provenance.reason == "no_model_bundle_source_supplied"


# --- Release-build source integrity (git archive, not the live checkout) ---


def _init_fixture_repo(directory: Path) -> None:
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(command, cwd=directory, check=True, capture_output=True)


def test_verify_clean_tracked_source_passes_on_a_clean_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "mockingbird").mkdir(parents=True)
    (repo / "src" / "mockingbird" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo / "README.md").write_text("# x\n", encoding="utf-8")
    _init_fixture_repo(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    commit = verify_clean_tracked_source(cwd=repo)

    resolved = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert commit == resolved


def test_verify_clean_tracked_source_ignores_untracked_files(tmp_path: Path) -> None:
    """The exact discovered defect this fix targets: an untracked file under
    a packaged source path must never block (or contaminate) a release
    build -- `export_clean_source_tree` (`git archive`) already excludes it
    structurally, so this check does not need to (and must not) demand its
    absence too."""

    repo = tmp_path / "repo"
    (repo / "src" / "mockingbird").mkdir(parents=True)
    (repo / "src" / "mockingbird" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo / "README.md").write_text("# x\n", encoding="utf-8")
    _init_fixture_repo(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    # An untracked work-in-progress file -- never `git add`ed.
    (repo / "src" / "mockingbird" / "untracked_scratch.py").write_text("oops = True\n", encoding="utf-8")

    commit = verify_clean_tracked_source(cwd=repo)  # must not raise

    exported = export_clean_source_tree(ref=commit, destination=tmp_path / "exported", cwd=repo)
    assert not (exported / "src" / "mockingbird" / "untracked_scratch.py").exists()
    assert (exported / "src" / "mockingbird" / "__init__.py").is_file()


def test_verify_clean_tracked_source_fails_on_uncommitted_tracked_modification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "mockingbird").mkdir(parents=True)
    (repo / "src" / "mockingbird" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo / "README.md").write_text("# x\n", encoding="utf-8")
    _init_fixture_repo(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    # An uncommitted edit to an *already-tracked* packaged-input file.
    (repo / "src" / "mockingbird" / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(LocalProductBuildError, match="uncommitted changes"):
        verify_clean_tracked_source(cwd=repo)


def test_export_clean_source_tree_matches_head_exactly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "mockingbird").mkdir(parents=True)
    (repo / "src" / "mockingbird" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    _init_fixture_repo(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()

    destination = export_clean_source_tree(ref=commit, destination=tmp_path / "exported", cwd=repo)

    assert (destination / "src" / "mockingbird" / "__init__.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (destination / "pyproject.toml").is_file()


def test_build_local_product_refuses_dirty_source_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: `build_local_product` itself refuses (does not silently
    build) when a packaged-input source path has an uncommitted
    modification, without `--allow-dirty-source`."""

    def _raising_verify(*_args: object, **_kwargs: object) -> str:
        raise LocalProductBuildError("Refusing to build a release artifact: uncommitted changes exist.")

    monkeypatch.setitem(build_local_product.__globals__, "verify_clean_tracked_source", _raising_verify)

    with pytest.raises(LocalProductBuildError, match="uncommitted changes"):
        build_local_product(
            tmp_path / "out",
            skip_frontend_build=True,
            install_dependencies=lambda _target: None,
            install_gpu_dependencies=_noop_gpu_installer,
            model_bundle_source=None,
        )


@pytest.mark.skipif(
    not DEFAULT_MODEL_BUNDLE_SOURCE.is_dir(),
    reason="real Observation Engine model bundle not present on this build host",
)
def test_real_local_model_bundle_matches_accepted_provenance_when_present(tmp_path: Path) -> None:
    """Not a fixture: reads the real local `data/models/observation-onnx-
    cuda/` bundle when this build host has one (this repository's own real,
    GPU-validated MDv5 ONNX export) and proves it packages cleanly with the
    exact accepted provenance -- the genuine "exact expected model SHA/
    provenance" proof, skipped (never failed) on a host without it rather
    than requiring every contributor to have a ~500 MB model file locally."""

    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_observation_runtime_assets(
        site_packages=site_packages, model_bundle_source=DEFAULT_MODEL_BUNDLE_SOURCE,
    )

    assert provenance.included is True, provenance.reason
    assert provenance.model_key == ACCEPTED_MODEL_KEY
    assert provenance.decoder_key == ACCEPTED_MODEL_DECODER
    assert provenance.license_name == ACCEPTED_MODEL_LICENSE
    assert provenance.onnx_model_sha256 == ACCEPTED_ONNX_MODEL_SHA256
    assert provenance.source_model_sha256 == ACCEPTED_SOURCE_MODEL_SHA256

    destination = site_packages / "mockingbird" / PACKAGED_OBSERVATION_RUNTIME_DIRNAME
    packaged_onnx = next(destination.glob("*.onnx"))
    assert hashlib.sha256(packaged_onnx.read_bytes()).hexdigest() == ACCEPTED_ONNX_MODEL_SHA256

    # The packaged config resolves and validates end to end through the real
    # (unmodified) Observation Engine bundle loaders -- proves the packaged
    # layout is not just present but actually loadable.
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    try:
        from mockingbird.observation.frame_driven_provider import FrameDrivenProviderConfiguration
        from mockingbird.observation.onnx_provider import OnnxModelBundle

        configuration = FrameDrivenProviderConfiguration.load(
            destination / PACKAGED_PROVIDER_CONFIG_FILENAME
        )
        bundle = OnnxModelBundle.load(configuration.model_bundle_path)
        assert bundle.model_fingerprint == ACCEPTED_ONNX_MODEL_SHA256
        assert bundle.source_model_fingerprint == ACCEPTED_SOURCE_MODEL_SHA256
    finally:
        sys.path.remove(str(ROOT / "src"))
