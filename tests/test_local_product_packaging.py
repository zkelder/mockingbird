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
Every such call also passes `include_bioclip_runtime=False` unless it is
specifically testing BioCLIP packaging (see "BioCLIP species-suggestion
runtime packaging" below), for the identical reason: never the real ~150 MB
BioCLIP dependency download or this repository's own real ~1.6 GB local
BioCLIP model file. Two exceptions, clearly marked and skipped when
unavailable: `test_real_local_model_bundle_matches_accepted_provenance_when_present`
reads (never writes/downloads) whatever real bundle already sits at
`DEFAULT_MODEL_BUNDLE_SOURCE` on *this* machine, the same real,
GPU-validated MDv5 artifact `build_local_product.py`'s own module docstring
describes; `test_real_windows_gpu_runtime_dll_closure_against_the_pinned_
wheel_cache` really installs (offline, from this machine's own local wheel
cache -- never the network) the pinned win_amd64 CUDA/cuDNN stack and runs
the real `verify_windows_gpu_runtime_dll_closure` against it. Both are
genuine, not-faked proofs, skipped rather than failed on a build host that
does not have the real asset they need. "BioCLIP species-suggestion runtime
packaging" below adds the identical pair of genuine, skip-when-unavailable
proofs for the BioCLIP bundle/wheel cache.

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
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tomllib
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(ROOT / "scripts" / "build_local_product.py")
assemble_windows_bundle = _MODULE["assemble_windows_bundle"]
build_local_product = _MODULE["build_local_product"]
export_clean_source_tree = _MODULE["export_clean_source_tree"]
install_windows_runtime_dependencies = _MODULE["install_windows_runtime_dependencies"]
install_windows_gpu_runtime_dependencies = _MODULE["install_windows_gpu_runtime_dependencies"]
install_windows_bioclip_runtime_dependencies = _MODULE["install_windows_bioclip_runtime_dependencies"]
package_observation_runtime_assets = _MODULE["package_observation_runtime_assets"]
package_bioclip_runtime_assets = _MODULE["package_bioclip_runtime_assets"]
sync_packaged_web_dist = _MODULE["sync_packaged_web_dist"]
verify_clean_tracked_source = _MODULE["verify_clean_tracked_source"]
verify_windows_gpu_runtime_dll_closure = _MODULE["verify_windows_gpu_runtime_dll_closure"]
verify_no_duplicate_site_packages_metadata = _MODULE["verify_no_duplicate_site_packages_metadata"]
verify_no_nc_licensed_acoustic_model_redistribution = _MODULE[
    "verify_no_nc_licensed_acoustic_model_redistribution"
]
package_third_party_notices = _MODULE["package_third_party_notices"]
package_license = _MODULE["package_license"]
verify_no_bundled_ffmpeg_binary = _MODULE["verify_no_bundled_ffmpeg_binary"]
write_build_identity = _MODULE["write_build_identity"]
write_deterministic_zip = _MODULE["write_deterministic_zip"]
write_manifest = _MODULE["write_manifest"]
BuildIdentity = _MODULE["BuildIdentity"]
LocalProductBuildError = _MODULE["LocalProductBuildError"]
ModelBundleProvenance = _MODULE["ModelBundleProvenance"]
NativeRuntimeVerification = _MODULE["NativeRuntimeVerification"]
BioClipBundleProvenance = _MODULE["BioClipBundleProvenance"]
ACCEPTED_ONNX_MODEL_SHA256 = _MODULE["ACCEPTED_ONNX_MODEL_SHA256"]
ACCEPTED_SOURCE_MODEL_SHA256 = _MODULE["ACCEPTED_SOURCE_MODEL_SHA256"]
ACCEPTED_MODEL_KEY = _MODULE["ACCEPTED_MODEL_KEY"]
ACCEPTED_MODEL_DECODER = _MODULE["ACCEPTED_MODEL_DECODER"]
ACCEPTED_MODEL_LICENSE = _MODULE["ACCEPTED_MODEL_LICENSE"]
ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256 = _MODULE["ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256"]
ACCEPTED_BIOCLIP_MODEL_CONFIG_SHA256 = _MODULE["ACCEPTED_BIOCLIP_MODEL_CONFIG_SHA256"]
ACCEPTED_BIOCLIP_LABELS_SHA256 = _MODULE["ACCEPTED_BIOCLIP_LABELS_SHA256"]
ACCEPTED_BIOCLIP_EMBEDDING_CACHE_SHA256 = _MODULE["ACCEPTED_BIOCLIP_EMBEDDING_CACHE_SHA256"]
PACKAGED_BUILD_INFO_FILENAME = _MODULE["PACKAGED_BUILD_INFO_FILENAME"]
PACKAGED_OBSERVATION_RUNTIME_DIRNAME = _MODULE["PACKAGED_OBSERVATION_RUNTIME_DIRNAME"]
PACKAGED_PROVIDER_CONFIG_FILENAME = _MODULE["PACKAGED_PROVIDER_CONFIG_FILENAME"]
PACKAGED_BIOCLIP_RUNTIME_DIRNAME = _MODULE["PACKAGED_BIOCLIP_RUNTIME_DIRNAME"]
BIOCLIP_MODEL_CONFIG_FILENAME = _MODULE["BIOCLIP_MODEL_CONFIG_FILENAME"]
BIOCLIP_MODEL_WEIGHTS_FILENAME = _MODULE["BIOCLIP_MODEL_WEIGHTS_FILENAME"]
BIOCLIP_LABELS_FILENAME = _MODULE["BIOCLIP_LABELS_FILENAME"]
BIOCLIP_EMBEDDING_CACHE_FILENAME = _MODULE["BIOCLIP_EMBEDDING_CACHE_FILENAME"]
DEFAULT_MODEL_BUNDLE_SOURCE = _MODULE["DEFAULT_MODEL_BUNDLE_SOURCE"]
WINDOWS_RUNTIME_REQUIREMENTS = _MODULE["WINDOWS_RUNTIME_REQUIREMENTS"]
DEFAULT_BIOCLIP_BUNDLE_SOURCE = _MODULE["DEFAULT_BIOCLIP_BUNDLE_SOURCE"]
DEFAULT_WHEEL_CACHE_DIR = _MODULE["DEFAULT_WHEEL_CACHE_DIR"]
DEFAULT_BIOCLIP_WHEEL_CACHE_DIR = _MODULE["DEFAULT_BIOCLIP_WHEEL_CACHE_DIR"]
WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS = _MODULE["WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS"]
REQUIRED_CUDA_RUNTIME_DLL_BASENAMES = _MODULE["REQUIRED_CUDA_RUNTIME_DLL_BASENAMES"]
REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES = _MODULE["REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES"]
WEB_ROOT = _MODULE["WEB_ROOT"]
build_frontend = _MODULE["build_frontend"]
compute_frontend_source_fingerprint = _MODULE["compute_frontend_source_fingerprint"]
verify_frontend_dist_freshness = _MODULE["verify_frontend_dist_freshness"]
write_frontend_source_fingerprint = _MODULE["write_frontend_source_fingerprint"]
FRONTEND_SOURCE_FINGERPRINT_FILENAME = _MODULE["FRONTEND_SOURCE_FINGERPRINT_FILENAME"]
generate_release_sbom = _MODULE["generate_release_sbom"]
write_release_sbom = _MODULE["write_release_sbom"]
sign_release_artifact = _MODULE["sign_release_artifact"]
SbomResult = _MODULE["SbomResult"]
SigningResult = _MODULE["SigningResult"]
ACCEPTED_BIOCLIP_MODEL_LICENSE = _MODULE["ACCEPTED_BIOCLIP_MODEL_LICENSE"]
ACCEPTED_BIOCLIP_MODEL_VERSION = _MODULE["ACCEPTED_BIOCLIP_MODEL_VERSION"]


def _fake_fresh_frontend_dist(*, dist_dir: Path, web_root: Path = WEB_ROOT) -> tuple[bool, str]:
    """A stand-in for `verify_frontend_dist_freshness` reporting an always-
    fresh frontend -- for tests exercising unrelated `build_local_product`
    behavior (dirty-source refusal, relative-path resolution, build-
    identity wiring) that must not depend on whatever this real checkout's
    own `web/dist` happens to contain right now."""

    return True, "fresh (faked for this test)"


def _noop_gpu_installer(_site_packages: Path) -> None:
    """Explicit no-op fake -- never installs anything -- for tests that must
    never trigger the real ~1.1 GB CUDA/cuDNN download."""


def _noop_bioclip_installer(_site_packages: Path) -> None:
    """Explicit no-op fake -- never installs anything -- for tests that must
    never trigger the real ~150 MB BioCLIP dependency download."""


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


def _write_fake_dll_package(
    site_packages: Path,
    *,
    package_name: str,
    dll_relative_paths_and_bytes: dict[str, bytes],
    omit_from_disk: frozenset[str] = frozenset(),
) -> None:
    """A minimal fake installed package: a real `RECORD` declaring each given
    relative path at its real byte size, shaped exactly like what a real
    `pip install --target ... --platform win_amd64` writes (a real `RECORD`
    is generated from the wheel's own manifest regardless of whether the
    installed platform matches the build host) -- but with a few bytes of
    fixture content standing in for a real multi-hundred-MB NVIDIA/
    onnxruntime-gpu DLL, and the hash field left blank (verification never
    reads it), matching this file's existing `_fake_wheel` RECORD convention.

    `omit_from_disk` declares a path in `RECORD` (a real byte size and all)
    without actually writing the file -- reproducing the exact real
    discovered defect: a package's own manifest claims a DLL that is not
    actually present in the assembled bundle.
    """

    dist_info = site_packages / f"{package_name}-1.0.0.dist-info"
    dist_info.mkdir(parents=True, exist_ok=True)
    record_lines = []
    for relative_path, data in dll_relative_paths_and_bytes.items():
        if relative_path not in omit_from_disk:
            target = site_packages / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        record_lines.append(f"{relative_path},,{len(data)}")
    record_lines.append(f"{package_name}-1.0.0.dist-info/RECORD,,")
    (dist_info / "RECORD").write_text("\n".join(record_lines) + "\n", encoding="utf-8")


# The real, confirmed directory each required DLL's real Windows wheel nests
# it under (see docs/local-product-packaging-design.md and the module
# docstring's "Native GPU/CUDA runtime DLL verification" section) -- fixture
# data describing the real layout, never read by the production RECORD-driven
# verification itself.
_FAKE_GPU_DLL_DIRECTORY_BY_BASENAME: dict[str, str] = {
    "cudart64_13.dll": "nvidia/cu13/bin/x86_64",
    "cublas64_13.dll": "nvidia/cu13/bin/x86_64",
    "cublasLt64_13.dll": "nvidia/cu13/bin/x86_64",
    "cudnn64_9.dll": "nvidia/cudnn/bin",
    "onnxruntime_providers_cuda.dll": "onnxruntime/capi",
    "onnxruntime_providers_shared.dll": "onnxruntime/capi",
}


def _write_fake_complete_gpu_runtime(site_packages: Path) -> dict[str, bytes]:
    """Writes a minimal-but-complete fake install satisfying every DLL
    `verify_windows_gpu_runtime_dll_closure` requires -- derived from the
    real `REQUIRED_CUDA_RUNTIME_DLL_BASENAMES`/`REQUIRED_ORT_CUDA_PROVIDER_
    DLL_BASENAMES` constants (so this fixture cannot silently drift out of
    sync with what the real verification actually demands) placed at each
    basename's real confirmed directory. Returns the relative-path -> bytes
    mapping actually written, for tests that want to tamper with one entry
    afterward."""

    required_basenames = (*REQUIRED_CUDA_RUNTIME_DLL_BASENAMES, *REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES)
    contents = {
        f"{_FAKE_GPU_DLL_DIRECTORY_BY_BASENAME[name]}/{name}": f"fake-{name}-content".encode()
        for name in required_basenames
    }
    _write_fake_dll_package(
        site_packages, package_name="fake_nvidia_cuda_stack", dll_relative_paths_and_bytes=contents,
    )
    return contents


def _fake_web_dist(directory: Path) -> Path:
    dist = directory / "fake-web-dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>MockingBird</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok');", encoding="utf-8")
    return dist


# --- Dependency-closure drift (Release Engineering Foundation v1) --------


def _pyproject_core_dependency_names() -> set[str]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    names = set()
    for requirement in data["project"]["dependencies"]:
        # Strip any `[extra]` marker (e.g. "uvicorn[standard]") and any
        # version/environment-marker suffix, then PEP 503-normalize so
        # "opencv-python-headless" and a hypothetical "opencv_python_headless"
        # compare equal.
        name = re.split(r"[\[<>=!~; ]", requirement, maxsplit=1)[0]
        names.add(re.sub(r"[-_.]+", "-", name).lower())
    return names


def _windows_runtime_requirement_names() -> set[str]:
    names = set()
    for requirement in WINDOWS_RUNTIME_REQUIREMENTS:
        name = re.split(r"[\[<>=!~; ]", requirement, maxsplit=1)[0]
        names.add(re.sub(r"[-_.]+", "-", name).lower())
    return names


def test_windows_runtime_requirements_matches_every_pyproject_core_dependency() -> None:
    """Real, confirmed defect this milestone's own native-Windows deployment
    hit directly: `pyproject.toml` gained `astral` as a plain core
    dependency (Environmental Context Foundation v1) with no corresponding
    update to this mirrored, hand-maintained tuple, so a real packaged
    build crashed on first launch -- `ModuleNotFoundError: No module named
    'astral'` -- the moment `product_repository.py`'s own unconditional
    `from mockingbird.environment import solar_context` import ran, before
    the app ever bound a port. `idna==3.18` is `WINDOWS_RUNTIME_
    REQUIREMENTS`'s one deliberate, documented exception (a transitive-
    dependency pin with no `pyproject.toml` counterpart at all -- see that
    tuple's own comment) and is correctly excluded from this check in the
    harmless direction: extra pins in the Windows list are fine, only a
    pyproject.toml core dependency *missing* from the Windows list is the
    real defect class this guards against."""

    missing = _pyproject_core_dependency_names() - _windows_runtime_requirement_names()

    assert missing == set(), (
        f"pyproject.toml core dependencies {missing} have no matching entry in "
        "WINDOWS_RUNTIME_REQUIREMENTS -- a packaged Windows build would fail to "
        "import the app at startup. Add each to WINDOWS_RUNTIME_REQUIREMENTS in "
        "scripts/build_local_product.py."
    )


def test_windows_runtime_requirements_package_the_windows_timezone_stack() -> None:
    """Native-Windows Field Reliability Corrections v1, Blocker 1. Neither
    half of this is guarded by the pyproject-mirror test above, and both are
    load-bearing for correct local-time rendering on the first-class
    acceptance platform:

    - `tzlocal` is the CLDR `windowsZones` mapping that turns the Windows
      registry's own zone name into an IANA key. It *is* a pyproject core
      dependency, so the mirror test would catch its removal from this
      tuple -- but not its removal from both places at once, which is what
      this asserts.
    - `tzdata` is deliberately NOT a pyproject core dependency, so the
      mirror test cannot see it at all. Both `astral` and `tzlocal` declare
      it conditionally for Windows, but `install_windows_runtime_
      dependencies` resolves environment markers against the Linux build
      host while only wheel *tags* honor `--platform win_amd64` -- so those
      conditional requirements evaluate False and `tzdata` silently is not
      packaged. That was directly confirmed in the field at `d5dd1d9`
      ("tzdata: NOT present", docs/field-validation-closure-v1-report.md
      Q-1). Without it, `zoneinfo` has no database on Windows and
      `ZoneInfo("America/New_York")` cannot construct even once `tzlocal`
      has correctly produced that name.
    """

    names = _windows_runtime_requirement_names()

    assert "tzlocal" in names, (
        "tzlocal is missing from WINDOWS_RUNTIME_REQUIREMENTS -- a packaged "
        "Windows build could not derive an IANA timezone name at all, and every "
        "server-side local-time surface would silently revert to one fixed UTC "
        "offset applied to every date (the reproduced Q-1 field defect)."
    )
    assert "tzdata" in names, (
        "tzdata is missing from WINDOWS_RUNTIME_REQUIREMENTS -- see this test's "
        "docstring: the conditional markers on astral/tzlocal cannot supply it "
        "from a Linux build host, so it must be listed explicitly."
    )


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


def _fake_web_root(directory: Path) -> Path:
    """A minimal stand-in for the real `web/` checkout: a `src/` tree plus
    the handful of root-level files `compute_frontend_source_fingerprint`
    actually reads."""

    web_root = directory / "fake-web-root"
    (web_root / "src" / "pages").mkdir(parents=True)
    (web_root / "src" / "App.tsx").write_text("export const App = () => null;", encoding="utf-8")
    (web_root / "src" / "pages" / "DashboardPage.tsx").write_text("// dashboard", encoding="utf-8")
    (web_root / "package.json").write_text('{"name": "web"}', encoding="utf-8")
    (web_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return web_root


def test_compute_frontend_source_fingerprint_is_deterministic_and_content_sensitive(
    tmp_path: Path,
) -> None:
    web_root = _fake_web_root(tmp_path)

    first = compute_frontend_source_fingerprint(web_root)
    second = compute_frontend_source_fingerprint(web_root)
    assert first == second, "hashing the same unchanged tree twice must be deterministic"

    (web_root / "src" / "App.tsx").write_text("export const App = () => 'changed';", encoding="utf-8")
    changed = compute_frontend_source_fingerprint(web_root)
    assert changed != first, "a real source-content change must change the fingerprint"


def test_compute_frontend_source_fingerprint_ignores_e2e_and_playwright_config(tmp_path: Path) -> None:
    """Test/e2e configuration does not affect `npm run build`'s own output
    -- an e2e-only change must never trigger a false staleness refusal."""

    web_root = _fake_web_root(tmp_path)
    before = compute_frontend_source_fingerprint(web_root)

    (web_root / "e2e").mkdir()
    (web_root / "e2e" / "smoke.spec.ts").write_text("test('x', () => {});", encoding="utf-8")
    (web_root / "playwright.config.ts").write_text("export default {};", encoding="utf-8")

    after = compute_frontend_source_fingerprint(web_root)
    assert after == before


def test_write_and_verify_frontend_dist_freshness_roundtrip(tmp_path: Path) -> None:
    web_root = _fake_web_root(tmp_path)
    dist_dir = _fake_web_dist(tmp_path)
    write_frontend_source_fingerprint(dist_dir=dist_dir, web_root=web_root)

    fresh, detail = verify_frontend_dist_freshness(dist_dir=dist_dir, web_root=web_root)
    assert fresh is True
    assert "matches" in detail

    (web_root / "src" / "App.tsx").write_text("export const App = () => 'now different';", encoding="utf-8")
    stale, stale_detail = verify_frontend_dist_freshness(dist_dir=dist_dir, web_root=web_root)
    assert stale is False
    assert "different frontend source" in stale_detail


def test_verify_frontend_dist_freshness_treats_a_missing_stamp_as_not_fresh(tmp_path: Path) -> None:
    """A `dist` with no recorded fingerprint at all (an older build from
    before this check existed, or one assembled some other way) must never
    be assumed safe -- "cannot prove freshness" is treated as "not fresh."
    """

    web_root = _fake_web_root(tmp_path)
    dist_dir = _fake_web_dist(tmp_path)  # never stamped

    fresh, detail = verify_frontend_dist_freshness(dist_dir=dist_dir, web_root=web_root)

    assert fresh is False
    assert "no recorded source fingerprint" in detail


def test_build_frontend_stamps_a_real_fingerprint_after_building(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`build_frontend` itself (not just the lower-level helpers) must
    leave a verifiable stamp behind -- proven by faking only the actual
    `npm` subprocess call, never `write_frontend_source_fingerprint`."""

    web_root = _fake_web_root(tmp_path)
    dist_dir = web_root / "dist"

    def _fake_run(command, *, cwd: Path) -> None:
        if list(command)[:2] == ["npm", "run"]:
            dist_dir.mkdir(parents=True, exist_ok=True)
            (dist_dir / "index.html").write_text("<!doctype html>", encoding="utf-8")

    monkeypatch.setitem(build_local_product.__globals__, "_run", _fake_run)
    monkeypatch.setitem(build_local_product.__globals__, "WEB_ROOT", web_root)
    (web_root / "node_modules").mkdir()  # skip the npm-ci branch

    build_frontend()

    fresh, _detail = verify_frontend_dist_freshness(dist_dir=dist_dir, web_root=web_root)
    assert fresh is True


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

    bundle_dir_result, model_provenance, native_runtime_verification, bioclip_provenance = assemble_windows_bundle(
        bundle_dir=bundle_dir,
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=fake_install_dependencies,
        # This test is about the base Python/pip-free bundle shape, not the
        # GPU/CUDA stack -- `include_gpu_runtime=False` keeps it that way
        # rather than coupling it to a fake DLL closure it does not care
        # about (see the "Windows GPU/CUDA native runtime" section below for
        # that verification's own dedicated tests). Same reasoning for
        # `include_bioclip_runtime=False` and the BioCLIP dependency/model
        # download (see "BioCLIP species-suggestion runtime packaging").
        include_gpu_runtime=False,
        model_bundle_source=None,
        include_bioclip_runtime=False,
        bioclip_bundle_source=None,
    )

    assert bundle_dir_result == bundle_dir
    assert installed_targets == [bundle_dir / "python" / "site-packages"]
    assert model_provenance.included is False
    assert model_provenance.reason == "no_model_bundle_source_supplied"
    assert native_runtime_verification.checked is False
    assert native_runtime_verification.reason == "gpu_runtime_skipped"
    assert bioclip_provenance.included is False
    assert bioclip_provenance.reason == "no_bioclip_bundle_source_supplied"

    # No Python/pip/npm knowledge needed: one launcher, no visible interpreter
    # concept, no console window (`pythonw.exe`, window style 0).
    launcher = (bundle_dir / "Start MockingBird.vbs").read_text(encoding="utf-8")
    assert "pythonw.exe" in launcher
    assert "-m mockingbird" in launcher
    assert ", 0, False" in launcher
    # Pre-Release Trust & Correctness Correction v1 (PKG-1): the launcher
    # forwards its own command-line arguments (for example --host 0.0.0.0
    # --allow-network, see docs/using-mockingbird.md "Use MockingBird on
    # your phone") to MockingBird -- confirmed for real, end to end, on
    # native Windows against this exact generated file (real packaged
    # Python runtime, real WScript.Arguments), not only by this structural
    # check. `forwardedArgs` starting empty (no trailing space glued onto
    # "-m mockingbird" when no arguments are given) keeps an ordinary,
    # no-argument double-click launch byte-identical to before this fix.
    assert "WScript.Arguments" in launcher
    assert 'forwardedArgs = ""' in launcher
    assert 'mockingbird" & forwardedArgs' in launcher
    readme_text = (bundle_dir / "README-FIRST.txt").read_text(encoding="utf-8")
    # External Acceptance Entry Readiness & Uninstall Closure v1: the
    # in-box README is the *only* uninstall documentation an unpacked
    # end user actually has (docs/using-mockingbird.md is not shipped
    # inside the bundle) -- it must state plainly that the application
    # folder and the local data folder are two separate, independently
    # removable things, not merely that data lives "somewhere local."
    assert "To remove MockingBird" in readme_text
    assert readme_text.count("%LOCALAPPDATA%\\MockingBird") >= 2
    assert "separate from this application" in readme_text or "separate local data" in readme_text
    assert "Revoke current pairing" in readme_text
    # Release Licensing, Distribution & Third-Party Legal Closure v1: every
    # official bundle ships the repository's own third-party notices file,
    # not only a copy an interested user would have to go find in the
    # source repository.
    notices_text = (bundle_dir / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "BirdNET" in notices_text
    assert "ffmpeg" in notices_text.lower()
    # MIT Source License Adoption & Lane P Mechanical Closure v1: every
    # official bundle also ships the repository's own root LICENSE file,
    # visible alongside THIRD_PARTY_NOTICES.md -- not only buried inside
    # python/site-packages/mockingbird-*.dist-info/licenses/ where an end
    # user unpacking the release folder would never look.
    license_text = (bundle_dir / "LICENSE").read_text(encoding="utf-8")
    assert license_text == (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text

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
    ~1.1 GB download. The fake installer still writes a minimal-but-complete
    fake DLL closure (`_write_fake_complete_gpu_runtime`) so it satisfies
    `verify_windows_gpu_runtime_dll_closure`, which now also runs by default
    whenever `include_gpu_runtime` is True -- this test's own concern is
    only "was the installer actually invoked", not that verification."""

    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")
    gpu_installed_targets: list[Path] = []

    def fake_gpu_installer(site_packages: Path) -> None:
        gpu_installed_targets.append(site_packages)
        _write_fake_complete_gpu_runtime(site_packages)

    _, _provenance, native_runtime_verification, _bioclip_provenance = assemble_windows_bundle(
        bundle_dir=tmp_path / "bundle",
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=lambda _target: None,
        install_gpu_dependencies=fake_gpu_installer,
        model_bundle_source=None,
        include_bioclip_runtime=False,
        bioclip_bundle_source=None,
    )

    assert gpu_installed_targets == [tmp_path / "bundle" / "python" / "site-packages"]
    assert native_runtime_verification.checked is True


def test_assemble_windows_bundle_skip_gpu_runtime_never_calls_installer(tmp_path: Path) -> None:
    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")
    calls: list[Path] = []

    _, _provenance, native_runtime_verification, _bioclip_provenance = assemble_windows_bundle(
        bundle_dir=tmp_path / "bundle",
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=lambda _target: None,
        install_gpu_dependencies=calls.append,
        include_gpu_runtime=False,
        model_bundle_source=None,
        include_bioclip_runtime=False,
        bioclip_bundle_source=None,
    )

    assert calls == []
    # `--skip-gpu-runtime` is an explicitly supported, honestly-reported
    # state -- never a build failure -- but must also never *claim* a DLL
    # closure it never actually checked.
    assert native_runtime_verification.checked is False
    assert native_runtime_verification.reason == "gpu_runtime_skipped"
    assert native_runtime_verification.verified_dlls == ()


# --- Windows GPU/CUDA native runtime DLL closure verification --------------
#
# The real discovered defect this section's tests target: a real native-
# Windows acceptance pass against a real GPU found `onnxruntime_providers_
# cuda.dll` present and `onnxruntime.get_available_providers()` correctly
# reporting `CUDAExecutionProvider`, with its own `cublasLt64_13.dll`
# dependency silently absent from the assembled bundle -- CUDA session
# creation then failed with Windows Error 126. Nothing in the build had ever
# verified the DLLs `pip install` claimed to install were actually present.


def test_verify_windows_gpu_runtime_dll_closure_passes_with_a_complete_closure(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    contents = _write_fake_complete_gpu_runtime(site_packages)

    result = verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)

    assert result.checked is True
    assert result.reason is None
    expected_names = {Path(path).name for path in contents}
    assert set(result.verified_dlls) == expected_names
    assert "nvidia/cu13/bin/x86_64" in result.dll_directories
    assert "nvidia/cudnn/bin" in result.dll_directories
    assert "onnxruntime/capi" in result.dll_directories


def test_verify_windows_gpu_runtime_dll_closure_fails_when_cublas_lt_missing_from_disk(
    tmp_path: Path,
) -> None:
    """The exact real discovered defect, reproduced directly: the owning
    package's own `RECORD` declares `cublasLt64_13.dll` (a real size and
    all) but the file itself was never actually written to the bundle."""

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    contents = {
        f"{_FAKE_GPU_DLL_DIRECTORY_BY_BASENAME[name]}/{name}": f"fake-{name}-content".encode()
        for name in (*REQUIRED_CUDA_RUNTIME_DLL_BASENAMES, *REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES)
    }
    _write_fake_dll_package(
        site_packages,
        package_name="fake_nvidia_cuda_stack",
        dll_relative_paths_and_bytes=contents,
        omit_from_disk=frozenset({"nvidia/cu13/bin/x86_64/cublasLt64_13.dll"}),
    )

    with pytest.raises(LocalProductBuildError, match="cublasLt64_13.dll"):
        verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)


def test_verify_windows_gpu_runtime_dll_closure_fails_when_a_dll_is_truncated(tmp_path: Path) -> None:
    """Catches corruption, not only outright absence: the file exists but is
    a different size than its own package's `RECORD` declares -- e.g. an
    interrupted/partial download or write."""

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    _write_fake_complete_gpu_runtime(site_packages)
    truncated = site_packages / "nvidia/cu13/bin/x86_64/cublasLt64_13.dll"
    truncated.write_bytes(b"short")

    with pytest.raises(LocalProductBuildError, match="cublasLt64_13.dll"):
        verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)


def test_verify_windows_gpu_runtime_dll_closure_fails_when_required_ort_provider_dll_missing(
    tmp_path: Path,
) -> None:
    """A complete CUDA/cuDNN runtime with no onnxruntime-gpu provider DLL at
    all is still refused -- `cublasLt64_13.dll` is not the only thing that
    must be present for a real CUDA session to actually load."""

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    contents = {
        f"{_FAKE_GPU_DLL_DIRECTORY_BY_BASENAME[name]}/{name}": f"fake-{name}-content".encode()
        for name in REQUIRED_CUDA_RUNTIME_DLL_BASENAMES
    }
    _write_fake_dll_package(site_packages, package_name="fake_nvidia_cuda_stack", dll_relative_paths_and_bytes=contents)

    with pytest.raises(LocalProductBuildError, match="onnxruntime_providers_cuda.dll"):
        verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)


def test_verify_windows_gpu_runtime_dll_closure_fails_when_no_dlls_present(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    with pytest.raises(LocalProductBuildError, match="zero .dll files"):
        verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)


def test_verify_windows_gpu_runtime_dll_closure_ignores_a_record_entry_that_escapes_site_packages(
    tmp_path: Path,
) -> None:
    """A `RECORD` row is untrusted, RECORD-declared data, not a guaranteed-
    safe path -- a `../`-escaping entry must be skipped, never resolved to
    (and checked, or worse reported as verified) somewhere outside
    `site_packages` entirely."""

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    _write_fake_complete_gpu_runtime(site_packages)
    outside_target = tmp_path / "outside-site-packages.dll"
    outside_target.write_bytes(b"should-never-be-considered")
    sneaky_dist_info = site_packages / "sneaky-1.0.0.dist-info"
    sneaky_dist_info.mkdir()
    (sneaky_dist_info / "RECORD").write_text(
        f"../outside-site-packages.dll,,{outside_target.stat().st_size}\n"
        "sneaky-1.0.0.dist-info/RECORD,,\n",
        encoding="utf-8",
    )

    result = verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)

    assert "outside-site-packages.dll" not in result.verified_dlls


def test_verify_windows_gpu_runtime_dll_closure_never_consults_system_cuda_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves the "no system CUDA Toolkit required" packaging contract:
    verification passes or fails purely from the bundled `site_packages`,
    unaffected by a build host's own (here, deliberately bogus/nonexistent)
    system CUDA environment -- it must never let a build host's own CUDA
    install, or lack of one, influence the result either way."""

    monkeypatch.setenv("CUDA_PATH", str(tmp_path / "not-a-real-cuda-toolkit"))
    monkeypatch.setenv("PATH", f"{tmp_path / 'not-a-real-cuda-bin'}{os.pathsep}/usr/bin")
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    _write_fake_complete_gpu_runtime(site_packages)

    result = verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)

    assert result.checked is True


def test_assemble_windows_bundle_fails_release_build_when_required_gpu_dll_missing(
    tmp_path: Path,
) -> None:
    """Integration proof that the verification is actually wired into the
    real build path, not merely a standalone unused function: a build must
    fail outright -- never silently ship, never silently fall back to a
    CPU-only artifact -- when the GPU install leaves a required DLL missing.
    """

    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")

    def broken_gpu_installer(site_packages: Path) -> None:
        _write_fake_complete_gpu_runtime(site_packages)
        # Simulate the real defect directly against a real installer shape:
        # everything else lands, `cublasLt64_13.dll` alone does not.
        (site_packages / "nvidia/cu13/bin/x86_64/cublasLt64_13.dll").unlink()

    with pytest.raises(LocalProductBuildError, match="cublasLt64_13.dll"):
        assemble_windows_bundle(
            bundle_dir=tmp_path / "bundle",
            wheel_path=wheel_path,
            embed_zip_path=embed_zip,
            install_dependencies=lambda _target: None,
            install_gpu_dependencies=broken_gpu_installer,
            model_bundle_source=None,
        )


def test_assemble_windows_bundle_records_native_runtime_verification(tmp_path: Path) -> None:
    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")

    _, _provenance, native_runtime_verification, _bioclip_provenance = assemble_windows_bundle(
        bundle_dir=tmp_path / "bundle",
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=lambda _target: None,
        install_gpu_dependencies=lambda target: _write_fake_complete_gpu_runtime(target),
        model_bundle_source=None,
        include_bioclip_runtime=False,
        bioclip_bundle_source=None,
    )

    assert native_runtime_verification.checked is True
    for name in (*REQUIRED_CUDA_RUNTIME_DLL_BASENAMES, *REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES):
        assert name in native_runtime_verification.verified_dlls
    assert any("nvidia" in directory for directory in native_runtime_verification.dll_directories)


def test_write_manifest_records_native_cuda_runtime_verification(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")
    verification = NativeRuntimeVerification(
        checked=True,
        verified_dlls=("cublasLt64_13.dll", "cublas64_13.dll", "cudart64_13.dll", "cudnn64_9.dll"),
        dll_directories=("nvidia/cu13/bin/x86_64", "nvidia/cudnn/bin"),
    )

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path,
        source_state="git:deadbeef", gpu_runtime_included=True,
        native_runtime_verification=verification,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["native_cuda_runtime"]["checked"] is True
    assert "cublasLt64_13.dll" in manifest["native_cuda_runtime"]["verified_dlls"]
    assert "nvidia/cu13/bin/x86_64" in manifest["native_cuda_runtime"]["dll_directories"]


def test_write_manifest_defaults_native_cuda_runtime_to_not_evaluated(tmp_path: Path) -> None:
    """Mirrors `ModelBundleProvenance`'s own `not_evaluated` default: a
    caller that forgets to pass `native_runtime_verification` gets an honest
    "not evaluated" record, never a manifest that looks like a real pass."""

    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path, source_state="git:deadbeef",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["native_cuda_runtime"]["checked"] is False
    assert manifest["native_cuda_runtime"]["reason"] == "not_evaluated"


def test_install_windows_gpu_runtime_dependencies_uses_local_wheel_cache_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "wheel-cache"
    cache_dir.mkdir()
    captured_commands: list[list[str]] = []
    monkeypatch.setitem(
        install_windows_gpu_runtime_dependencies.__globals__,
        "_run",
        lambda command, *, cwd: captured_commands.append(list(command)),
    )

    install_windows_gpu_runtime_dependencies(
        site_packages=tmp_path / "site-packages", requirements=("fake-pkg==1.0",), wheel_cache_dir=cache_dir,
    )

    [command] = captured_commands
    assert "--find-links" in command
    assert str(cache_dir) in command
    assert "--no-index" in command
    assert "fake-pkg==1.0" in command


def test_install_windows_gpu_runtime_dependencies_falls_back_to_network_when_cache_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_commands: list[list[str]] = []
    monkeypatch.setitem(
        install_windows_gpu_runtime_dependencies.__globals__,
        "_run",
        lambda command, *, cwd: captured_commands.append(list(command)),
    )

    install_windows_gpu_runtime_dependencies(
        site_packages=tmp_path / "site-packages",
        requirements=("fake-pkg==1.0",),
        wheel_cache_dir=tmp_path / "no-such-cache-directory",
    )

    [command] = captured_commands
    assert "--find-links" not in command
    assert "--no-index" not in command
    assert "fake-pkg==1.0" in command


@pytest.mark.slow  # real offline pip install from a ~1.3 GB local wheel cache.
@pytest.mark.skipif(
    not DEFAULT_WHEEL_CACHE_DIR.is_dir(),
    reason="real win_amd64 CUDA/cuDNN wheel cache not present on this build host",
)
def test_real_windows_gpu_runtime_dll_closure_against_the_pinned_wheel_cache(tmp_path: Path) -> None:
    """Not a fixture: really installs the pinned win_amd64/cp312 CUDA/cuDNN +
    onnxruntime-gpu stack from this build host's own local wheel cache
    (offline, real NVIDIA/onnxruntime-gpu wheels, no network -- see
    `DEFAULT_WHEEL_CACHE_DIR`) and runs the real `verify_windows_gpu_runtime_
    dll_closure` against it -- the genuine "the actual required files from
    the pinned Windows NVIDIA packages" proof, skipped (never failed) on a
    build host that does not have this ~1.3 GB cache rather than requiring
    every contributor to have it locally."""

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    install_windows_gpu_runtime_dependencies(site_packages=site_packages, wheel_cache_dir=DEFAULT_WHEEL_CACHE_DIR)
    result = verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)

    assert result.checked is True
    for name in (*REQUIRED_CUDA_RUNTIME_DLL_BASENAMES, *REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES):
        assert name in result.verified_dlls
    assert any(directory.endswith("nvidia/cu13/bin/x86_64") for directory in result.dll_directories)
    assert any(directory.endswith("onnxruntime/capi") for directory in result.dll_directories)


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


# --- BioCLIP species-suggestion runtime packaging ---------------------------


def _valid_bioclip_bundle_source(
    directory: Path,
    *,
    weights_bytes: bytes = b"fixture-bioclip-weights",
    config_bytes: bytes = b'{"fixture": "config"}',
    labels_bytes: bytes = b"House Finch\n",
    cache_bytes: bytes = b"fixture-embedding-cache-bytes",
) -> Path:
    """A source directory shaped exactly like the real, already-accepted
    `data/models/bioclip-2/` convention, but with tiny fixture content --
    tests must never depend on this repository's real ~1.6 GB weights file.
    Also writes an unrelated scratch file, proving `package_bioclip_
    runtime_assets` looks up its four expected files individually rather
    than copying the source directory wholesale."""

    source = directory / "bioclip-2"
    source.mkdir()
    (source / BIOCLIP_MODEL_WEIGHTS_FILENAME).write_bytes(weights_bytes)
    (source / BIOCLIP_MODEL_CONFIG_FILENAME).write_bytes(config_bytes)
    (source / BIOCLIP_LABELS_FILENAME).write_bytes(labels_bytes)
    (source / BIOCLIP_EMBEDDING_CACHE_FILENAME).write_bytes(cache_bytes)
    (source / "bioclip-batch-1.txt").write_text("scratch evaluation artifact\n", encoding="utf-8")
    return source


def _monkeypatch_accepted_bioclip_hashes(monkeypatch: pytest.MonkeyPatch, *, weights: bytes, config: bytes, labels: bytes, cache: bytes) -> None:
    for name, content in (
        ("ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256", weights),
        ("ACCEPTED_BIOCLIP_MODEL_CONFIG_SHA256", config),
        ("ACCEPTED_BIOCLIP_LABELS_SHA256", labels),
        ("ACCEPTED_BIOCLIP_EMBEDDING_CACHE_SHA256", cache),
    ):
        monkeypatch.setitem(
            package_bioclip_runtime_assets.__globals__, name, hashlib.sha256(content).hexdigest(),
        )


def test_package_bioclip_runtime_assets_accepts_the_exact_accepted_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uses tiny fixture files whose SHA-256s are monkeypatched in as the
    "accepted" hashes -- proves the verification/copy logic without
    shipping (or requiring) the real ~1.6 GB model in the test suite."""

    weights, config, labels, cache = b"w" * 32, b'{"c":1}', b"House Finch\n", b"cache-bytes"
    source = _valid_bioclip_bundle_source(
        tmp_path, weights_bytes=weights, config_bytes=config, labels_bytes=labels, cache_bytes=cache,
    )
    _monkeypatch_accepted_bioclip_hashes(monkeypatch, weights=weights, config=config, labels=labels, cache=cache)
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_bioclip_runtime_assets(site_packages=site_packages, bioclip_bundle_source=source)

    assert provenance.included is True
    assert provenance.reason is None
    assert provenance.model_weights_sha256 == hashlib.sha256(weights).hexdigest()
    assert provenance.model_config_sha256 == hashlib.sha256(config).hexdigest()
    assert provenance.labels_sha256 == hashlib.sha256(labels).hexdigest()
    assert provenance.embedding_cache_sha256 == hashlib.sha256(cache).hexdigest()

    destination = site_packages / "mockingbird" / PACKAGED_BIOCLIP_RUNTIME_DIRNAME
    assert (destination / BIOCLIP_MODEL_WEIGHTS_FILENAME).read_bytes() == weights
    assert (destination / BIOCLIP_MODEL_CONFIG_FILENAME).read_bytes() == config
    assert (destination / BIOCLIP_LABELS_FILENAME).read_bytes() == labels
    assert (destination / BIOCLIP_EMBEDDING_CACHE_FILENAME).read_bytes() == cache
    # The unrelated scratch file sitting in the same source directory is
    # never packaged -- each expected file is looked up individually.
    assert not (destination / "bioclip-batch-1.txt").exists()


def test_package_bioclip_runtime_assets_rejects_a_bundle_that_does_not_match_accepted_provenance(
    tmp_path: Path,
) -> None:
    """A bundle whose SHA-256s do not match the real, doctrine-recorded
    `ACCEPTED_BIOCLIP_*_SHA256` constants (never monkeypatched in this
    test) is refused, not silently packaged as if it were the accepted
    model."""

    source = _valid_bioclip_bundle_source(tmp_path, weights_bytes=b"a-different-unapproved-model-file")
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_bioclip_runtime_assets(site_packages=site_packages, bioclip_bundle_source=source)

    assert provenance.included is False
    assert provenance.reason is not None and "does_not_match_accepted_provenance" in provenance.reason
    assert not (site_packages / "mockingbird" / PACKAGED_BIOCLIP_RUNTIME_DIRNAME).exists()


def test_package_bioclip_runtime_assets_rejects_a_bundle_missing_one_expected_file(tmp_path: Path) -> None:
    """A bundle missing even one of the four expected files (labels,
    here) is refused with a specific, actionable reason -- never silently
    packages a partial/inconsistent bundle."""

    source = _valid_bioclip_bundle_source(tmp_path)
    (source / BIOCLIP_LABELS_FILENAME).unlink()
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_bioclip_runtime_assets(site_packages=site_packages, bioclip_bundle_source=source)

    assert provenance.included is False
    assert provenance.reason == "bioclip_labels_missing"


def test_package_bioclip_runtime_assets_missing_source_is_honest_not_fatal(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_bioclip_runtime_assets(
        site_packages=site_packages, bioclip_bundle_source=tmp_path / "no-such-directory",
    )

    assert provenance.included is False
    assert provenance.reason == "no_bioclip_bundle_source_supplied"


def test_package_bioclip_runtime_assets_none_source_is_honest_not_fatal(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_bioclip_runtime_assets(site_packages=site_packages, bioclip_bundle_source=None)

    assert provenance.included is False
    assert provenance.reason == "no_bioclip_bundle_source_supplied"


def test_install_windows_bioclip_runtime_dependencies_uses_the_pinned_wheel_cache_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_commands: list[list[str]] = []
    monkeypatch.setitem(
        install_windows_bioclip_runtime_dependencies.__globals__,
        "_run",
        lambda command, *, cwd: captured_commands.append(list(command)),
    )
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    install_windows_bioclip_runtime_dependencies(
        site_packages=tmp_path / "site-packages", requirements=("fake-pkg==1.0",), wheel_cache_dir=cache_dir,
    )

    [command] = captured_commands
    assert "--find-links" in command
    assert str(cache_dir) in command
    assert "--no-index" in command
    assert "--extra-index-url" in command
    assert "fake-pkg==1.0" in command


def test_install_windows_bioclip_runtime_dependencies_falls_back_to_network_when_cache_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_commands: list[list[str]] = []
    monkeypatch.setitem(
        install_windows_bioclip_runtime_dependencies.__globals__,
        "_run",
        lambda command, *, cwd: captured_commands.append(list(command)),
    )

    install_windows_bioclip_runtime_dependencies(
        site_packages=tmp_path / "site-packages",
        requirements=("fake-pkg==1.0",),
        wheel_cache_dir=tmp_path / "no-such-cache-directory",
    )

    [command] = captured_commands
    assert "--find-links" not in command
    assert "--no-index" not in command
    assert "--extra-index-url" in command
    assert "fake-pkg==1.0" in command


def test_assemble_windows_bundle_includes_bioclip_runtime_by_default_via_injected_installer(
    tmp_path: Path,
) -> None:
    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")
    bioclip_installed_targets: list[Path] = []

    _, _model_provenance, _native_verification, bioclip_provenance = assemble_windows_bundle(
        bundle_dir=tmp_path / "bundle",
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=lambda _target: None,
        install_bioclip_dependencies=bioclip_installed_targets.append,
        include_gpu_runtime=False,
        model_bundle_source=None,
        bioclip_bundle_source=None,
    )

    assert bioclip_installed_targets == [tmp_path / "bundle" / "python" / "site-packages"]
    assert bioclip_provenance.included is False  # no bioclip_bundle_source supplied in this test


def test_assemble_windows_bundle_skip_bioclip_runtime_never_calls_installer(tmp_path: Path) -> None:
    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")
    calls: list[Path] = []

    assemble_windows_bundle(
        bundle_dir=tmp_path / "bundle",
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=lambda _target: None,
        install_bioclip_dependencies=calls.append,
        include_gpu_runtime=False,
        model_bundle_source=None,
        include_bioclip_runtime=False,
        bioclip_bundle_source=None,
    )

    assert calls == []


def test_write_manifest_records_bioclip_bundle_provenance(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")
    provenance = BioClipBundleProvenance(
        included=True,
        model_weights_sha256=ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256,
        model_config_sha256=ACCEPTED_BIOCLIP_MODEL_CONFIG_SHA256,
        labels_sha256=ACCEPTED_BIOCLIP_LABELS_SHA256,
        embedding_cache_sha256=ACCEPTED_BIOCLIP_EMBEDDING_CACHE_SHA256,
    )

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path,
        source_state="git:deadbeef", bioclip_bundle_provenance=provenance, bioclip_runtime_included=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["bioclip_runtime_included"] is True
    assert manifest["bioclip_runtime_requirements"]  # non-empty
    assert manifest["bioclip_model_bundle"]["included"] is True
    assert manifest["bioclip_model_bundle"]["model_weights_sha256"] == ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256


def test_write_manifest_records_missing_bioclip_bundle_honestly(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path, source_state="git:deadbeef",
        bioclip_bundle_provenance=BioClipBundleProvenance(included=False, reason="no_bioclip_bundle_source_supplied"),
        bioclip_runtime_included=False,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["bioclip_model_bundle"]["included"] is False
    assert manifest["bioclip_model_bundle"]["reason"] == "no_bioclip_bundle_source_supplied"
    assert manifest["bioclip_runtime_included"] is False
    assert manifest["bioclip_runtime_requirements"] == []


# --- Duplicate site-packages metadata: the real corruption class found -----
# while validating WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS (see that constant's
# own docstring): a second `pip install --target` call resolving a loosely
# -bounded transitive dependency to a different version than an earlier
# call already installed leaves stale code on disk next to a second,
# newer-versioned `.dist-info/` -- an ambiguous, corrupted install.


def test_verify_no_duplicate_site_packages_metadata_passes_when_clean(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    for name in ("pillow-11.3.0.dist-info", "numpy-2.5.2.dist-info", "mockingbird-0.1.0.dist-info"):
        (site_packages / name).mkdir(parents=True)

    verify_no_duplicate_site_packages_metadata(site_packages=site_packages)  # must not raise


def test_verify_no_duplicate_site_packages_metadata_fails_on_a_real_duplicate_shape(tmp_path: Path) -> None:
    """Exact real shape found for real: `pillow-11.3.0.dist-info` (already
    installed by the core tier) sitting next to a freshly-resolved
    `pillow-12.3.0.dist-info` from a later, independent install call."""

    site_packages = tmp_path / "site-packages"
    for name in ("pillow-11.3.0.dist-info", "pillow-12.3.0.dist-info"):
        (site_packages / name).mkdir(parents=True)

    with pytest.raises(LocalProductBuildError, match="pillow"):
        verify_no_duplicate_site_packages_metadata(site_packages=site_packages)


def test_verify_no_duplicate_site_packages_metadata_normalizes_dashes_and_underscores(tmp_path: Path) -> None:
    """`open_clip_torch` and a hypothetical `open-clip-torch` (or
    `Open.Clip.Torch`) name the *same* PyPI distribution -- PEP 503
    normalization must catch this even though the literal directory names
    differ."""

    site_packages = tmp_path / "site-packages"
    for name in ("open_clip_torch-3.3.0.dist-info", "open-clip-torch-3.4.0.dist-info"):
        (site_packages / name).mkdir(parents=True)

    with pytest.raises(LocalProductBuildError, match="open-clip-torch"):
        verify_no_duplicate_site_packages_metadata(site_packages=site_packages)


# Acoustic Productization, Licensing & Field Acceptance v1: the packaged
# Windows product must never redistribute the CC BY-NC-SA-licensed BirdNET
# model that ships as real package data inside the `birdnetlib` wheel -- see
# docs/acoustic-productization-licensing-field-acceptance-v1-contract.md.


def test_verify_no_nc_licensed_acoustic_model_redistribution_passes_when_absent(
    tmp_path: Path,
) -> None:
    site_packages = tmp_path / "site-packages"
    for name in ("pillow-11.3.0.dist-info", "numpy-2.5.2.dist-info"):
        (site_packages / name).mkdir(parents=True)
    (site_packages / "PIL").mkdir()

    verify_no_nc_licensed_acoustic_model_redistribution(site_packages=site_packages)  # must not raise


def test_verify_no_nc_licensed_acoustic_model_redistribution_fails_on_the_package_directory(
    tmp_path: Path,
) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "birdnetlib").mkdir(parents=True)

    with pytest.raises(LocalProductBuildError, match="birdnetlib"):
        verify_no_nc_licensed_acoustic_model_redistribution(site_packages=site_packages)


def test_verify_no_nc_licensed_acoustic_model_redistribution_fails_on_the_dist_info(
    tmp_path: Path,
) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "birdnetlib-0.18.1.dist-info").mkdir(parents=True)

    with pytest.raises(LocalProductBuildError, match="birdnetlib"):
        verify_no_nc_licensed_acoustic_model_redistribution(site_packages=site_packages)


def test_package_third_party_notices_copies_the_real_repository_file(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    destination = package_third_party_notices(bundle_dir=bundle_dir)

    assert destination == bundle_dir / "THIRD_PARTY_NOTICES.md"
    real_source = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert destination.read_text(encoding="utf-8") == real_source


def test_package_third_party_notices_fails_the_build_when_source_is_missing(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    missing_source = tmp_path / "does-not-exist" / "THIRD_PARTY_NOTICES.md"

    # Never optional, never best-effort -- unlike a model bundle, a release
    # built without this file must fail outright rather than ship silently
    # without any third-party/model-license disclosure at all.
    with pytest.raises(LocalProductBuildError, match="THIRD_PARTY_NOTICES.md"):
        package_third_party_notices(bundle_dir=bundle_dir, notices_source=missing_source)


def test_package_license_copies_the_real_repository_file(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    destination = package_license(bundle_dir=bundle_dir)

    assert destination == bundle_dir / "LICENSE"
    real_source = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert destination.read_text(encoding="utf-8") == real_source


def test_package_license_fails_the_build_when_source_is_missing(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    missing_source = tmp_path / "does-not-exist" / "LICENSE"

    # Never optional, never best-effort -- the identical contract
    # `package_third_party_notices` already established: a release built
    # without this file must fail outright rather than ship silently with no
    # visible source-code license at all.
    with pytest.raises(LocalProductBuildError, match="LICENSE"):
        package_license(bundle_dir=bundle_dir, license_source=missing_source)


def test_verify_no_bundled_ffmpeg_binary_passes_when_absent(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "python" / "site-packages" / "mockingbird").mkdir(parents=True)
    (bundle_dir / "python" / "site-packages" / "mockingbird" / "__init__.py").write_text(
        "", encoding="utf-8"
    )

    verify_no_bundled_ffmpeg_binary(bundle_dir=bundle_dir)  # must not raise


@pytest.mark.parametrize("ffmpeg_basename", ["ffmpeg", "ffmpeg.exe", "FFmpeg.EXE"])
def test_verify_no_bundled_ffmpeg_binary_fails_on_a_planted_executable(
    tmp_path: Path, ffmpeg_basename: str
) -> None:
    bundle_dir = tmp_path / "bundle"
    nested = bundle_dir / "python" / "site-packages" / "some_package" / "bin"
    nested.mkdir(parents=True)
    (nested / ffmpeg_basename).write_bytes(b"not a real binary, just a planted name")

    with pytest.raises(LocalProductBuildError, match="ffmpeg"):
        verify_no_bundled_ffmpeg_binary(bundle_dir=bundle_dir)


def test_verify_no_bundled_ffmpeg_binary_ignores_a_directory_merely_named_ffmpeg(
    tmp_path: Path,
) -> None:
    # Only a *file* named ffmpeg/ffmpeg.exe is the redistribution risk this
    # guards against -- a directory that happens to share the name (for
    # example, some unrelated package's own internal folder) is not one.
    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "ffmpeg").mkdir(parents=True)
    (bundle_dir / "ffmpeg" / "readme.txt").write_text("unrelated", encoding="utf-8")

    verify_no_bundled_ffmpeg_binary(bundle_dir=bundle_dir)  # must not raise


def test_assemble_windows_bundle_fails_the_whole_build_on_a_duplicate_dependency(
    tmp_path: Path,
) -> None:
    """Integration proof this is actually wired into the real build path:
    an installer that leaves a duplicated `.dist-info/` behind fails the
    whole build, never silently ships it."""

    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")

    def duplicate_leaving_installer(site_packages: Path) -> None:
        (site_packages / "pillow-11.3.0.dist-info").mkdir(parents=True, exist_ok=True)
        (site_packages / "pillow-12.3.0.dist-info").mkdir(parents=True, exist_ok=True)

    with pytest.raises(LocalProductBuildError, match="pillow"):
        assemble_windows_bundle(
            bundle_dir=tmp_path / "bundle",
            wheel_path=wheel_path,
            embed_zip_path=embed_zip,
            install_dependencies=duplicate_leaving_installer,
            include_gpu_runtime=False,
            model_bundle_source=None,
            include_bioclip_runtime=False,
            bioclip_bundle_source=None,
        )


def test_assemble_windows_bundle_fails_the_whole_build_on_a_bundled_ffmpeg_binary(
    tmp_path: Path,
) -> None:
    """Integration proof this is actually wired into the real build path:
    a dependency that leaves an `ffmpeg.exe` behind (for example, a future
    optional-extra installer that vendors one for convenience) fails the
    whole build, never silently ships it -- see
    `verify_no_bundled_ffmpeg_binary`'s own docstring for why this posture
    matters."""

    embed_zip = _fake_embeddable_zip(tmp_path)
    wheel_path = _fake_wheel(tmp_path, package_name="mockingbird")

    def ffmpeg_vendoring_installer(site_packages: Path) -> None:
        vendored_bin = site_packages / "some_camera_extra" / "bin"
        vendored_bin.mkdir(parents=True, exist_ok=True)
        (vendored_bin / "ffmpeg.exe").write_bytes(b"not a real binary, just a planted name")

    with pytest.raises(LocalProductBuildError, match="ffmpeg"):
        assemble_windows_bundle(
            bundle_dir=tmp_path / "bundle",
            wheel_path=wheel_path,
            embed_zip_path=embed_zip,
            install_dependencies=ffmpeg_vendoring_installer,
            include_gpu_runtime=False,
            model_bundle_source=None,
            include_bioclip_runtime=False,
            bioclip_bundle_source=None,
        )


@pytest.mark.slow  # real SHA-256 hashing of a ~1.6 GB local model bundle.
@pytest.mark.skipif(
    not DEFAULT_BIOCLIP_BUNDLE_SOURCE.is_dir(),
    reason="real local BioCLIP evaluation bundle not present on this build host",
)
def test_real_local_bioclip_bundle_matches_accepted_provenance_when_present(tmp_path: Path) -> None:
    """Not a fixture: reads the real local `data/models/bioclip-2/` bundle
    when this build host has one (this repository's own real, already
    -validated BioCLIP 2 artifact) and proves it packages cleanly with the
    exact accepted provenance -- skipped (never failed) on a host without
    it rather than requiring every contributor to have a ~1.6 GB model
    file locally."""

    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)

    provenance = package_bioclip_runtime_assets(
        site_packages=site_packages, bioclip_bundle_source=DEFAULT_BIOCLIP_BUNDLE_SOURCE,
    )

    assert provenance.included is True, provenance.reason
    assert provenance.model_weights_sha256 == ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256
    assert provenance.model_config_sha256 == ACCEPTED_BIOCLIP_MODEL_CONFIG_SHA256
    assert provenance.labels_sha256 == ACCEPTED_BIOCLIP_LABELS_SHA256
    assert provenance.embedding_cache_sha256 == ACCEPTED_BIOCLIP_EMBEDDING_CACHE_SHA256


@pytest.mark.slow  # real offline pip install of the BioCLIP dependency closure.
@pytest.mark.skipif(
    not DEFAULT_BIOCLIP_WHEEL_CACHE_DIR.is_dir(),
    reason="real win_amd64 BioCLIP wheel cache not present on this build host",
)
def test_real_windows_bioclip_dependency_closure_installs_offline_with_no_duplicates(tmp_path: Path) -> None:
    """Not a fixture: really installs the pinned win_amd64/cp312 BioCLIP
    dependency closure from this build host's own local wheel cache
    (offline, real torch/open_clip/... wheels, no network -- see
    `DEFAULT_BIOCLIP_WHEEL_CACHE_DIR`), on top of the real core+GPU tiers,
    and proves `verify_no_duplicate_site_packages_metadata` finds the
    result clean -- the genuine "the pinned closure actually installs
    together with no duplication" proof, skipped (never failed) on a build
    host that does not have this cache locally."""

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    install_windows_runtime_dependencies(site_packages=site_packages)
    install_windows_gpu_runtime_dependencies(site_packages=site_packages, wheel_cache_dir=DEFAULT_WHEEL_CACHE_DIR)
    install_windows_bioclip_runtime_dependencies(
        site_packages=site_packages, wheel_cache_dir=DEFAULT_BIOCLIP_WHEEL_CACHE_DIR,
    )

    verify_no_duplicate_site_packages_metadata(site_packages=site_packages)  # must not raise

    for name in ("torch", "open_clip_torch", "safetensors", "timm", "sympy"):
        assert any(
            entry.name.lower().startswith(f"{name}-") and entry.name.endswith(".dist-info")
            for entry in site_packages.iterdir()
        ), f"{name} not installed"


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
    monkeypatch.setitem(
        build_local_product.__globals__, "verify_frontend_dist_freshness", _fake_fresh_frontend_dist
    )

    with pytest.raises(LocalProductBuildError, match="uncommitted changes"):
        build_local_product(
            tmp_path / "out",
            skip_frontend_build=True,
            install_dependencies=lambda _target: None,
            install_gpu_dependencies=_noop_gpu_installer,
            model_bundle_source=None,
        )


def test_build_local_product_refuses_a_stale_skipped_frontend_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1 Release Hardening v1 -- 5a: `--skip-frontend-build` must not be
    able to silently package a `web/dist` that does not correspond to
    current frontend source. `verify_clean_tracked_source` is deliberately
    left unfaked here (and would raise a *different*, easily-confused
    error if reached) -- the freshness refusal must happen first, on its
    own, without depending on the unrelated dirty-source check."""

    def _fake_stale_frontend_dist(*, dist_dir: Path, web_root: Path = WEB_ROOT) -> tuple[bool, str]:
        return False, "recorded fingerprint does not match current source (faked)"

    monkeypatch.setitem(
        build_local_product.__globals__, "verify_frontend_dist_freshness", _fake_stale_frontend_dist
    )

    with pytest.raises(LocalProductBuildError, match="stale or unverifiable"):
        build_local_product(
            tmp_path / "out",
            skip_frontend_build=True,
            install_dependencies=lambda _target: None,
            install_gpu_dependencies=_noop_gpu_installer,
            model_bundle_source=None,
        )


def test_build_local_product_allows_a_stale_skipped_frontend_with_explicit_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit `--allow-stale-frontend` escape hatch (mirroring
    `--allow-dirty-source`'s exact contract) proceeds past the same
    refusal instead of blocking it -- proven by reaching a *later*,
    distinctly-worded faked failure rather than the freshness one."""

    def _fake_stale_frontend_dist(*, dist_dir: Path, web_root: Path = WEB_ROOT) -> tuple[bool, str]:
        return False, "recorded fingerprint does not match current source (faked)"

    def _raising_verify(*_args: object, **_kwargs: object) -> str:
        raise LocalProductBuildError("stop here -- proves execution proceeded past the freshness check")

    monkeypatch.setitem(
        build_local_product.__globals__, "verify_frontend_dist_freshness", _fake_stale_frontend_dist
    )
    monkeypatch.setitem(build_local_product.__globals__, "verify_clean_tracked_source", _raising_verify)

    with pytest.raises(LocalProductBuildError, match="stop here"):
        build_local_product(
            tmp_path / "out",
            skip_frontend_build=True,
            allow_stale_frontend=True,
            install_dependencies=lambda _target: None,
            install_gpu_dependencies=_noop_gpu_installer,
            model_bundle_source=None,
        )


def test_write_manifest_records_frontend_source_state(tmp_path: Path) -> None:
    """`manifest.json` must disclose which of the three frontend states
    produced this artifact -- built fresh, reused-and-verified-fresh, or
    reused-while-stale-and-explicitly-overridden -- never silently."""

    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = tmp_path / "MockingBird-windows-x64.zip"
    zip_path.write_bytes(b"fake zip contents")

    manifest_path, _checksums_path = write_manifest(
        output_dir=tmp_path,
        bundle_dir=bundle_dir,
        zip_path=zip_path,
        source_state="git:" + "a" * 40,
        frontend_source_state="reused:stale_allowed",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["frontend_source_state"] == "reused:stale_allowed"


@pytest.mark.slow  # real SHA-256 hashing of a ~500 MB-1 GB local model bundle.
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


# --- Build identity (git commit / build id a running instance self-reports,
# see docs/windows-dev-deployment-design.md) ---


def test_write_build_identity_writes_the_expected_file(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "mockingbird").mkdir(parents=True)
    identity = BuildIdentity(
        git_commit="a" * 40, build_id="deadbeefcafef00d", built_at="2026-01-01T00:00:00+00:00",
        app_version="0.1.0", source_clean=True,
    )

    destination = write_build_identity(site_packages=site_packages, identity=identity)

    assert destination == site_packages / "mockingbird" / PACKAGED_BUILD_INFO_FILENAME
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload == {
        "git_commit": "a" * 40, "build_id": "deadbeefcafef00d", "built_at": "2026-01-01T00:00:00+00:00",
        "app_version": "0.1.0", "source_clean": True,
    }


def test_write_manifest_records_build_identity(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "file.txt").write_text("x", encoding="utf-8")
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")
    identity = BuildIdentity(
        git_commit="b" * 40, build_id="0123456789abcdef", built_at="2026-02-02T00:00:00+00:00",
        app_version="0.1.0", source_clean=True,
    )

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path, source_state=f"git:{'b' * 40}",
        build_identity=identity,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["build_identity"] == {
        "git_commit": "b" * 40, "build_id": "0123456789abcdef", "built_at": "2026-02-02T00:00:00+00:00",
        "app_version": "0.1.0", "source_clean": True,
    }


def test_write_manifest_defaults_build_identity_to_none_when_not_evaluated(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "file.txt").write_text("x", encoding="utf-8")
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path, source_state="test-fixture-state",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["build_identity"] is None


def test_build_local_product_resolves_a_relative_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for a real discovered defect (see
    docs/windows-dev-deployment-design.md and this module's own "Release
    -build source integrity" docstring section): `output_dir` must be
    resolved to an absolute path before it is used for *anything*. A
    *relative* `output_dir` previously resolved against two different
    directories -- the release-build subprocess's own `cwd` (a `git
    archive` staging temp directory) for the actual `pip wheel` write, vs.
    this process's own cwd for the later `output_dir.glob(...)` existence
    check -- so the wheel silently landed in the staging tree, which was
    then deleted before anything looked there
    (`LocalProductBuildError: Wheel build did not produce a
    mockingbird-*.whl file`, discovered validating the CUDA dependency
    -closure fix). Never reproduces once `output_dir` is absolute
    throughout, which is exactly what this proves: the relative path
    resolves against *this process's actual cwd at call time*, immediately
    -- before the (here, faked-to-raise) clean-source check ever runs, let
    alone a subprocess with a different cwd.
    """

    def _raising_verify(*_args: object, **_kwargs: object) -> str:
        raise LocalProductBuildError("stop here -- this test only cares what happened before this point")

    monkeypatch.setitem(build_local_product.__globals__, "verify_clean_tracked_source", _raising_verify)
    monkeypatch.setitem(
        build_local_product.__globals__, "verify_frontend_dist_freshness", _fake_fresh_frontend_dist
    )

    different_cwd = tmp_path / "somewhere-else-entirely"
    different_cwd.mkdir()
    monkeypatch.chdir(different_cwd)

    with pytest.raises(LocalProductBuildError):
        build_local_product(
            Path("relative-output"),
            skip_frontend_build=True,
            install_dependencies=lambda _target: None,
            install_gpu_dependencies=_noop_gpu_installer,
            model_bundle_source=None,
        )

    assert (different_cwd / "relative-output").is_dir()


def test_build_local_product_end_to_end_records_a_verified_build_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real wiring, start to finish: `build_local_product` ->
    `assemble_windows_bundle` -> `write_build_identity` places
    `build_info.json` inside the installed package, and `write_manifest`
    records the identical identity in `manifest.json` -- proving a
    deployment tool reading either source can trust the exact commit/build
    this artifact was produced from (`mockingbird.runtime_state.
    resolve_build_identity` reads the packaged copy at runtime; see
    docs/windows-dev-deployment-design.md).

    Everything that would otherwise need network access, a real git
    history, or a real `npm run build` is faked (matching this module's
    own stated hermetic-test philosophy); what genuinely runs is the exact
    file-assembly wiring this test exists to prove.
    """

    fake_commit = "c" * 40

    def _fake_verify_clean_tracked_source(*_args: object, **_kwargs: object) -> str:
        return fake_commit

    def _fake_export_clean_source_tree(*, ref: str, destination: Path, cwd: Path = ROOT) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        return destination

    def _fake_sync_packaged_web_dist(*, source_dist: Path | None = None, target_dir: Path | None = None) -> Path:
        assert target_dir is not None
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text("<!doctype html><title>MockingBird</title>", encoding="utf-8")
        return target_dir

    def _fake_build_wheel(output_dir: Path, *, source_root: Path = ROOT) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        return _fake_wheel(output_dir, package_name="mockingbird")

    for name, fake in (
        ("verify_clean_tracked_source", _fake_verify_clean_tracked_source),
        ("export_clean_source_tree", _fake_export_clean_source_tree),
        ("sync_packaged_web_dist", _fake_sync_packaged_web_dist),
        ("build_wheel", _fake_build_wheel),
        ("verify_frontend_dist_freshness", _fake_fresh_frontend_dist),
    ):
        monkeypatch.setitem(build_local_product.__globals__, name, fake)

    artifact = build_local_product(
        tmp_path / "out",
        skip_frontend_build=True,
        embed_zip_override=_fake_embeddable_zip(tmp_path),
        install_dependencies=lambda _target: None,
        include_gpu_runtime=False,
        model_bundle_source=None,
        include_bioclip_runtime=False,
        bioclip_bundle_source=None,
    )

    assert artifact.build_identity.git_commit == fake_commit
    assert len(artifact.build_identity.build_id) == 16
    assert all(character in "0123456789abcdef" for character in artifact.build_identity.build_id)
    assert artifact.build_identity.app_version
    assert artifact.build_identity.source_clean is True

    build_info_path = (
        artifact.bundle_dir / "python" / "site-packages" / "mockingbird" / PACKAGED_BUILD_INFO_FILENAME
    )
    payload = json.loads(build_info_path.read_text(encoding="utf-8"))
    assert payload["git_commit"] == fake_commit
    assert payload["build_id"] == artifact.build_identity.build_id
    assert payload["source_clean"] is True

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    assert manifest["build_identity"]["git_commit"] == fake_commit
    assert manifest["build_identity"]["build_id"] == artifact.build_identity.build_id
    assert manifest["build_identity"]["source_clean"] is True
    assert manifest["source_state"] == f"git:{fake_commit}"


def test_build_local_product_dirty_source_records_a_best_effort_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--allow-dirty-source` never proves a clean commit the way the
    default path does, but a build identity is still recorded -- best
    -effort, from plain `git rev-parse HEAD` (`_current_head_commit`),
    never fabricated. Distinguishable from a verified build purely by
    `source_state` (`dirty:unverified-working-tree`, never `git:<hash>`),
    matching the existing convention the manifest's `source_state` field
    already uses for this distinction."""

    def _fake_sync_packaged_web_dist(*, source_dist: Path | None = None, target_dir: Path | None = None) -> Path:
        destination = target_dir or (tmp_path / "packaged-web-dist")
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "index.html").write_text("<!doctype html><title>MockingBird</title>", encoding="utf-8")
        return destination

    def _fake_build_wheel(output_dir: Path, *, source_root: Path = ROOT) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        return _fake_wheel(output_dir, package_name="mockingbird")

    def _fake_current_head_commit(*, cwd: Path = ROOT) -> str:
        return "d" * 40

    for name, fake in (
        ("sync_packaged_web_dist", _fake_sync_packaged_web_dist),
        ("build_wheel", _fake_build_wheel),
        ("_current_head_commit", _fake_current_head_commit),
        ("verify_frontend_dist_freshness", _fake_fresh_frontend_dist),
    ):
        monkeypatch.setitem(build_local_product.__globals__, name, fake)

    artifact = build_local_product(
        tmp_path / "out",
        skip_frontend_build=True,
        embed_zip_override=_fake_embeddable_zip(tmp_path),
        install_dependencies=lambda _target: None,
        include_gpu_runtime=False,
        model_bundle_source=None,
        include_bioclip_runtime=False,
        bioclip_bundle_source=None,
        allow_dirty_source=True,
    )

    assert artifact.build_identity.git_commit == "d" * 40
    # Release Engineering Foundation v1: `git_commit` alone does not mean
    # clean (it's populated here too, from a best-effort `git rev-parse`) --
    # `source_clean` is the one explicit, structured field a consumer can
    # check without parsing `source_state`'s string prefix.
    assert artifact.build_identity.source_clean is False
    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_state"] == "dirty:unverified-working-tree"
    assert manifest["build_identity"]["git_commit"] == "d" * 40
    assert manifest["build_identity"]["source_clean"] is False


# --- Final Release Hardening & Launch Readiness v1: SBOM / signing --------


def test_generate_release_sbom_lists_every_installed_package_with_name_and_version(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    _fake_wheel(tmp_path, package_name="fakepkg")
    (site_packages / "fakepkg").mkdir()
    (site_packages / "fakepkg-1.0.0.dist-info").mkdir()
    (site_packages / "fakepkg-1.0.0.dist-info" / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: fakepkg\nVersion: 1.0.0\nLicense-Expression: MIT\n",
        encoding="utf-8",
    )

    sbom = generate_release_sbom(site_packages=site_packages, app_version="1.0.0")

    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["metadata"]["component"] == {"type": "application", "name": "mockingbird", "version": "1.0.0"}
    fakepkg_components = [c for c in sbom["components"] if c["name"] == "fakepkg"]
    assert len(fakepkg_components) == 1
    assert fakepkg_components[0]["version"] == "1.0.0"
    assert fakepkg_components[0]["licenses"] == [{"license": {"name": "MIT"}}]
    assert fakepkg_components[0]["purl"] == "pkg:pypi/fakepkg@1.0.0"
    # The embedded CPython runtime itself is always listed, even with zero
    # installed packages.
    runtime_components = [c for c in sbom["components"] if c["name"] == "cpython-embeddable"]
    assert len(runtime_components) == 1


def test_generate_release_sbom_falls_back_to_a_legacy_license_classifier(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    (site_packages / "legacypkg-2.0.dist-info").mkdir(parents=True)
    (site_packages / "legacypkg-2.0.dist-info" / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: legacypkg\nVersion: 2.0\n"
        "Classifier: License :: OSI Approved :: Apache Software License\n",
        encoding="utf-8",
    )

    sbom = generate_release_sbom(site_packages=site_packages, app_version="1.0.0")

    component = next(c for c in sbom["components"] if c["name"] == "legacypkg")
    assert component["licenses"] == [{"license": {"name": "Apache Software License"}}]


def test_generate_release_sbom_never_fails_on_a_malformed_metadata_file(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    dist_info = site_packages / "brokenpkg-1.0.dist-info"
    dist_info.mkdir(parents=True)
    # Not valid UTF-8 -- must not raise, and the package must still be listed.
    (dist_info / "METADATA").write_bytes(b"\xff\xfe not utf-8 metadata")

    sbom = generate_release_sbom(site_packages=site_packages, app_version="1.0.0")

    names = [c["name"] for c in sbom["components"]]
    assert "brokenpkg" in names


def test_generate_release_sbom_includes_packaged_models_only_when_included(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    included_model = ModelBundleProvenance(
        included=True, model_key=ACCEPTED_MODEL_KEY, model_version="MDv5a.0.1-onnx-opset18",
        decoder_key=ACCEPTED_MODEL_DECODER, license_name=ACCEPTED_MODEL_LICENSE,
        source_model_sha256=ACCEPTED_SOURCE_MODEL_SHA256, onnx_model_sha256=ACCEPTED_ONNX_MODEL_SHA256,
    )
    included_bioclip = BioClipBundleProvenance(
        included=True, model_weights_sha256=ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256,
        model_config_sha256=ACCEPTED_BIOCLIP_MODEL_CONFIG_SHA256, labels_sha256=ACCEPTED_BIOCLIP_LABELS_SHA256,
        embedding_cache_sha256=ACCEPTED_BIOCLIP_EMBEDDING_CACHE_SHA256,
    )

    sbom_with_models = generate_release_sbom(
        site_packages=site_packages, app_version="1.0.0",
        model_bundle_provenance=included_model, bioclip_bundle_provenance=included_bioclip,
    )
    sbom_without_models = generate_release_sbom(
        site_packages=site_packages, app_version="1.0.0",
        model_bundle_provenance=ModelBundleProvenance(included=False, reason="no_model_bundle_source_supplied"),
        bioclip_bundle_provenance=BioClipBundleProvenance(included=False, reason="no_bioclip_bundle_source_supplied"),
    )

    names_with = {c["name"] for c in sbom_with_models["components"]}
    names_without = {c["name"] for c in sbom_without_models["components"]}
    assert {"megadetector-v5a-onnx", "bioclip-2"} <= names_with
    assert not ({"megadetector-v5a-onnx", "bioclip-2"} & names_without)
    model_component = next(c for c in sbom_with_models["components"] if c["name"] == "megadetector-v5a-onnx")
    assert model_component["hashes"] == [{"alg": "SHA-256", "content": ACCEPTED_ONNX_MODEL_SHA256}]
    assert model_component["licenses"] == [{"license": {"name": "MIT"}}]
    bioclip_component = next(c for c in sbom_with_models["components"] if c["name"] == "bioclip-2")
    assert bioclip_component["version"] == ACCEPTED_BIOCLIP_MODEL_VERSION
    assert bioclip_component["licenses"] == [{"license": {"name": ACCEPTED_BIOCLIP_MODEL_LICENSE}}]


def test_write_release_sbom_writes_a_real_file_and_returns_its_hash(tmp_path: Path) -> None:
    sbom = generate_release_sbom(site_packages=tmp_path / "empty-site-packages", app_version="1.0.0")

    sbom_path, result = write_release_sbom(output_dir=tmp_path, sbom=sbom)

    assert sbom_path == tmp_path / "sbom.json"
    assert sbom_path.is_file()
    assert result.file_name == "sbom.json"
    assert result.sha256 == hashlib.sha256(sbom_path.read_bytes()).hexdigest()
    # Zero installed packages still yields the always-present CPython
    # runtime component.
    assert result.component_count == 1


def test_write_manifest_records_sbom_and_default_unsigned_signing(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")
    sbom_result = SbomResult(component_count=5, file_name="sbom.json", sha256="a" * 64)
    (tmp_path / "sbom.json").write_text("{}", encoding="utf-8")

    manifest_path, checksums_path = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path,
        source_state="git:deadbeef", sbom_result=sbom_result,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["sbom"] == {
        "format": "CycloneDX", "spec_version": "1.5", "file": "sbom.json",
        "component_count": 5, "sha256": "a" * 64,
    }
    # No `signing_result` was passed -- the honest, non-fatal default.
    assert manifest["signing"] == {"requested": False, "key_id": None}
    checksums_text = checksums_path.read_text(encoding="utf-8")
    assert "sbom.json" in checksums_text


def test_write_manifest_records_a_requested_signing_key(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    zip_path = write_deterministic_zip(bundle_dir, tmp_path / "out.zip")

    manifest_path, _ = write_manifest(
        output_dir=tmp_path, bundle_dir=bundle_dir, zip_path=zip_path,
        source_state="git:deadbeef", signing_result=SigningResult(requested=True, key_id="ABCDEF1234567890"),
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["signing"] == {"requested": True, "key_id": "ABCDEF1234567890"}


def test_sign_release_artifact_with_no_key_is_honest_and_non_fatal(tmp_path: Path) -> None:
    result = sign_release_artifact(output_dir=tmp_path, key_id=None)

    assert result == SigningResult(requested=False, key_id=None)
    assert not (tmp_path / "SHA256SUMS.asc").exists()


def test_sign_release_artifact_refuses_when_no_checksums_file_exists(tmp_path: Path) -> None:
    with pytest.raises(LocalProductBuildError, match="SHA256SUMS"):
        sign_release_artifact(output_dir=tmp_path, key_id="some-key")


def test_sign_release_artifact_raises_on_a_real_gpg_failure_with_an_unknown_key(tmp_path: Path) -> None:
    """A configured key that cannot actually sign must fail the whole build,
    never silently ship an unsigned artifact while claiming a key was used."""

    (tmp_path / "SHA256SUMS").write_text("deadbeef  fake.zip\n", encoding="utf-8")

    with pytest.raises(LocalProductBuildError, match="signing failed"):
        sign_release_artifact(output_dir=tmp_path, key_id="0xNONEXISTENTKEYID")


@pytest.mark.skipif(shutil.which("gpg") is None, reason="requires a real local gpg binary")
def test_sign_release_artifact_produces_a_real_verifiable_detached_signature(tmp_path: Path) -> None:
    """A genuine, disposable-keyring end-to-end proof: generate a throwaway
    GPG key (never a real project/owner key), sign a real SHA256SUMS with
    it, and verify the produced signature really validates -- not merely
    that gpg exited zero."""

    gnupg_home = tmp_path / "gnupghome"
    gnupg_home.mkdir(mode=0o700)
    env = {**os.environ, "GNUPGHOME": str(gnupg_home)}
    # Plain `--batch --gen-key` with an explicit RSA key spec (not
    # `--quick-generate-key`'s "default" curve, which fails with "Unknown
    # elliptic curve" against this environment's libgcrypt build) --
    # `%no-protection` skips passphrase protection so no pinentry/TTY is
    # needed in this headless test environment.
    key_spec = (
        "%no-protection\n"
        "Key-Type: RSA\n"
        "Key-Length: 2048\n"
        "Name-Real: test-fixture-key\n"
        "Name-Email: test-fixture@example.invalid\n"
        "Expire-Date: 1d\n"
        "%commit\n"
    )
    key_generation = subprocess.run(
        ["gpg", "--batch", "--gen-key"],
        input=key_spec, env=env, capture_output=True, text=True, check=False,
    )
    assert key_generation.returncode == 0, key_generation.stderr

    output_dir = tmp_path / "release"
    output_dir.mkdir()
    (output_dir / "SHA256SUMS").write_text("deadbeef  fake.zip\n", encoding="utf-8")

    # sign_release_artifact itself always invokes the ambient `gpg` on PATH;
    # point it at this disposable keyring via the environment rather than a
    # parameter this function deliberately does not expose (the real
    # operator flow uses their own default, non-test keyring).
    original_gnupghome = os.environ.get("GNUPGHOME")
    os.environ["GNUPGHOME"] = str(gnupg_home)
    try:
        result = sign_release_artifact(output_dir=output_dir, key_id="test-fixture@example.invalid")
    finally:
        if original_gnupghome is None:
            os.environ.pop("GNUPGHOME", None)
        else:
            os.environ["GNUPGHOME"] = original_gnupghome

    assert result.requested is True
    signature_path = output_dir / "SHA256SUMS.asc"
    assert signature_path.is_file()

    verification = subprocess.run(
        ["gpg", "--verify", str(signature_path), str(output_dir / "SHA256SUMS")],
        env=env, capture_output=True, text=True, check=False,
    )
    assert verification.returncode == 0, verification.stderr


# --- MIT Source License Adoption & Lane P Mechanical Closure v1 ------------
# Package-metadata and user-facing-truth checks for the mechanical adoption
# of the owner's MIT decision (see docs/release-execution-state.md, Lane P,
# and docs/mit-source-license-adoption-lane-p-mechanical-closure-v1-report.md).
# `package_license`/`package_third_party_notices`'s own dedicated tests,
# above, already prove Windows-bundle inclusion; these prove the source-of-
# -truth artifacts themselves (the `LICENSE` file, `pyproject.toml`'s
# metadata, `web/package.json`, and README.md's user-facing claim) are
# actually correct, not merely that a copy step exists.


def test_pyproject_declares_mit_license_metadata() -> None:
    """`pyproject.toml`'s own PEP 639 SPDX metadata must name MIT and the
    real `LICENSE` file, and the `hatchling` floor must be high enough to
    actually emit that metadata correctly -- empirically verified this
    milestone that hatchling 1.24-1.25 reject `license-files` as an array
    outright, and 1.26 accepts it but silently omits the `License-Expression`
    /`License-File` Metadata-Version 2.4 fields; 1.27 is the first version
    confirmed to emit both correctly."""

    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)

    assert data["project"]["license"] == "MIT"
    assert data["project"]["license-files"] == ["LICENSE"]
    hatchling_requirement = next(
        req for req in data["build-system"]["requires"] if req.startswith("hatchling")
    )
    version = tuple(int(part) for part in re.match(r"hatchling>=(\d+)\.(\d+)", hatchling_requirement).groups())
    assert version >= (1, 27), (
        f"hatchling floor {hatchling_requirement!r} is below the (1, 27) minimum this milestone "
        "empirically confirmed is required for correct license-expression/license-file metadata"
    )


def test_web_package_json_declares_mit_license() -> None:
    data = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    assert data["license"] == "MIT"


def test_license_file_exists_with_correct_mit_text_and_copyright() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 MockingBird contributors" in text
    # The canonical, unaltered MIT permission/warranty boilerplate -- the
    # identical text already reproduced (for MDv5a) in THIRD_PARTY_NOTICES.md,
    # confirming this repository treats this as its one standard MIT text.
    assert "Permission is hereby granted, free of charge" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text
    assert "MERCHANTABILITY" in text and "NONINFRINGEMENT" in text


def test_readme_states_mit_license_and_points_to_license_file() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    license_section = readme.split("## License", maxsplit=1)[1]

    assert "has not yet been finalized" not in license_section
    assert "MIT" in license_section
    assert "[LICENSE](LICENSE)" in license_section or "(LICENSE)" in license_section
    assert "THIRD_PARTY_NOTICES.md" in license_section


def test_third_party_notices_no_longer_calls_the_source_license_undecided() -> None:
    """THIRD_PARTY_NOTICES.md's own self-referential note about MockingBird's
    *own* license status must stay truthful once Lane P's mechanical
    adoption lands -- it must not keep telling a reader the decision is
    still open. This does not touch, and must not touch, any third-party
    fact in the same file (MDv5a/BioCLIP-2/ffmpeg/BirdNET provenance)."""

    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert "still-open question" not in notices
    assert "pending an explicit owner decision" not in notices
    assert "MIT" in notices
    # Third-party facts this milestone must never alter:
    assert "Microsoft Corporation" in notices
    assert "CC BY-NC-SA 4.0" in notices
    assert "verify_no_bundled_ffmpeg_binary" in notices
    assert "verify_no_nc_licensed_acoustic_model_redistribution" in notices
