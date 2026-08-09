"""Build the Windows MockingBird local-product bundle.

See docs/local-product-packaging-design.md for the packaging decision this
implements. This script is a developer/CI-only build tool: the milestone's
"no terminal acceptance" rule governs *using* MockingBird, not *building* its
distributable artifact -- a normal user only ever receives the finished
`.zip` this script produces.

The bundle is an "unpack and run" folder, not an installer: unzip it anywhere
and double-click `Start MockingBird.vbs`. It contains:

- `python/`: the official CPython embeddable distribution for Windows, with
  every MockingBird runtime dependency and the MockingBird wheel itself
  pre-installed into `python/site-packages` at *build* time on this
  (Linux) host, and `python312._pth` patched to see them. The user's
  machine never runs pip, npm, or a venv -- there is nothing to install.
  `python/site-packages/mockingbird/observation_runtime/` additionally
  carries the packaged default Observation Engine provider configuration
  and model bundle (see "Observation runtime packaging" below) and, for a
  compatible NVIDIA PC, the ONNX Runtime GPU + CUDA/cuDNN redistributable
  stack -- so "Start observing" needs no environment variable, no manually
  installed CUDA Toolkit, and no developer knowledge to work.
- `Start MockingBird.vbs`: a silent (no console window) double-click
  launcher that runs `python\\pythonw.exe -m mockingbird`.
- `README-FIRST.txt`: plain-language instructions.
- `manifest.json` / `SHA256SUMS`: build provenance, mirroring the existing
  convention in scripts/build_camera_node_artifact.py, including Observation
  runtime model/GPU provenance.

Usage:

    python scripts/build_local_product.py dist/mockingbird-local-product

Requires `npm` (to build the frontend once) and network access (to fetch the
embeddable Python distribution and the pinned Windows wheels) on the build
machine. None of that is required on the machine that later runs the bundle.

## Release-build source integrity

`pip wheel .` (and hatchling's default file selection under it) builds from
whatever is physically present in the working tree. An untracked-but-not-
gitignored file sitting under `src/mockingbird/` -- a work-in-progress
script an operator forgot to `git add`, for example -- has no reason to be
excluded by that logic and previously shipped in a real release wheel
undetected. This build now compiles the wheel from a *clean tracked source
snapshot* (`git archive`) rather than the live checkout, so an untracked
file structurally cannot enter the package regardless of what is sitting in
the working tree; see `verify_clean_tracked_source`/`export_clean_source_tree`.
Uncommitted *modifications to already-tracked* packaged-input files (the one
remaining real ambiguity `git archive` alone cannot resolve -- which version
did the operator actually mean to ship) still fail the build by default,
with an explicit `--allow-dirty-source` opt-out for local/dev iteration that
a real release must never use.

## Observation runtime packaging

`package_observation_runtime_assets` copies the already-accepted Observation
Engine's default provider configuration and MDv5 ONNX model bundle
(docs/megadetector-runtime-findings.md's approved local-artifact provenance,
converted to ONNX and validated with a real NVIDIA GPU during the
Observation Engine v2 Stage 3 activation) into the bundle, verifying the
model's SHA-256 against the exact hashes this project has actually accepted
before ever including it -- this build never invents, substitutes, or
silently downloads a different model. Model weights are still never
committed to git (docs/model-adapter-guardrails.md); the source bundle is a
local, ignored, developer/CI-supplied directory (`--model-bundle-source`,
defaulting to the existing `data/models/observation-onnx-cuda` convention
per docs/megadetector-local-setup.md). A build with no such source available
is not a failure -- the produced artifact still boots and honestly reports a
"missing model/runtime" Observation Engine state (an explicitly supported,
tested end state) until an operator supplies a bundle and rebuilds.

## Native GPU/CUDA runtime DLL verification

A real native-Windows acceptance pass against a real GPU found the packaged
CUDA execution provider fail at session-creation time with Windows Error 126
(a missing dependency DLL): `onnxruntime_providers_cuda.dll` was present and
`onnxruntime.get_available_providers()` correctly listed
`CUDAExecutionProvider`, but its own `cublasLt64_13.dll` dependency -- the
single largest file in the entire GPU/CUDA closure at roughly 400-480 MB --
was silently absent from the assembled bundle. Nothing in the build had ever
verified the DLLs pip claimed to install were actually present on disk;
`pip install`'s own zero exit code was the only signal trusted.
`verify_windows_gpu_runtime_dll_closure` closes that gap: it reads every
installed package's own `RECORD` (which `pip install --target` writes for
real regardless of host platform) to discover exactly which `.dll` files
each pinned wheel actually ships and where -- never a hard-coded directory
depth or fixed file list, since NVIDIA's Windows wheels nest `.dll` files a
different number of directories deep per package -- then confirms each one
is genuinely present at its declared byte size. It raises
`LocalProductBuildError` (failing the release build outright, never a
warning) the moment any required native DLL is missing, wrong-sized, or the
whole closure is empty. `install_windows_gpu_runtime_dependencies` also now
reuses the verified local wheel cache (`--wheel-cache-dir`, defaulting to
`.build-cache/wheels-win_amd64-cp312-cuda13`) via `pip --find-links ...
--no-index` when present, so a build no longer depends on re-fetching ~1.3 GB
over the network -- including that same ~400 MB `cublasLt64_13.dll`-bearing
wheel -- every single time.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence
from urllib.request import urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
PACKAGED_WEB_DIST = ROOT / "src" / "mockingbird" / "web_dist"
DEFAULT_BUILD_CACHE_DIR = ROOT / ".build-cache"
# The verified, already-downloaded win_amd64/cp312 GPU-stack wheel cache (see
# docs/local-product-packaging-design.md and the accepted-Observation-model-
# provenance record) -- reused via `pip install --find-links ... --no-index`
# whenever present so a build never re-fetches ~1.3 GB (including the ~400 MB
# `nvidia-cublas` wheel alone) over the network on every run. Falls back to a
# normal network install untouched when a build host has no local cache yet.
DEFAULT_WHEEL_CACHE_DIR = DEFAULT_BUILD_CACHE_DIR / "wheels-win_amd64-cp312-cuda13"

EMBED_PYTHON_VERSION = "3.12.7"
EMBED_PYTHON_TAG = "amd64"
EMBED_PYTHON_URL = (
    f"https://www.python.org/ftp/python/{EMBED_PYTHON_VERSION}/"
    f"python-{EMBED_PYTHON_VERSION}-embed-{EMBED_PYTHON_TAG}.zip"
)

# `uvicorn[standard]` pulls in `uvloop`, which has no Windows wheels and is
# gated by a `sys_platform != "win32"` marker. pip's cross-platform
# `--platform win_amd64` download resolves markers against the *host*
# interpreter, not the requested target, so it tries (and fails) to satisfy
# uvloop for Windows anyway. Bare `uvicorn` sidesteps this cleanly --
# MockingBird does not use anything from the "standard" extra (uvloop,
# httptools, websockets, watchfiles, python-dotenv, PyYAML, colorama); it
# runs on uvicorn's default asyncio loop and h11 HTTP implementation, which
# is exactly what already runs in this repository's own dev/test/CI use.
# Keep this in sync with the runtime dependency list in pyproject.toml.
WINDOWS_RUNTIME_REQUIREMENTS: tuple[str, ...] = (
    "anyio>=3.7,<4.0",
    "fastapi>=0.111,<0.116",
    "Pillow>=10,<12",
    "pydantic>=2.7,<3.0",
    "python-multipart>=0.0.9,<1.0",
    "SQLAlchemy>=2.0,<3.0",
    "opencv-python-headless>=4.10,<5.0",
    "uvicorn>=0.30,<1.0",
)

# The accepted Observation Engine's optional GPU detector stack (pyproject
# .toml's `observation-onnx-cuda` extra), pre-installed unconditionally for
# the Windows product artifact -- a normal packaged install must not require
# the user to separately `pip install` anything to press "Start observing"
# on a compatible NVIDIA PC. Exact-pinned (not a floating range, unlike the
# extra's own `>=1.18,<2.0`): this is the *specific* version already
# validated end-to-end against the accepted MDv5 ONNX bundle with a real
# NVIDIA GPU (RTX 4060 Ti, `cuda_only_verified`, 886/886 CUDA-executed model
# nodes, zero CPU/unknown) during the Observation Engine v2 Stage 3
# activation -- a proven-together combination, not "any recent version".
WINDOWS_GPU_RUNTIME_REQUIREMENTS: tuple[str, ...] = (
    "numpy>=1.26,<3.0",
    "onnxruntime-gpu==1.28.0",
)
# The CUDA 13/cuDNN 9 redistributable wheels `onnxruntime-gpu`'s CUDA
# execution provider dlopens at inference time -- the same versions reused
# read-only from the primary runtime during that real activation (see
# `activation-environment.json` in the ignored local field-acceptance
# record). This "unpack and run" product has no system-wide CUDA Toolkit
# install and no PATH entry pointing at one, so these are pip-installed into
# the same flat site-packages layout as every other dependency;
# `mockingbird.observation.onnx_provider._prepare_windows_onnxruntime_dll_
# search_path` adds each one's DLL directory to the process's DLL search
# path at runtime (`os.add_dll_directory`) -- the packaged-runtime
# replacement for a manually configured PATH/LD_LIBRARY_PATH. Large
# (roughly 1.1 GB total): kept in its own optional requirement list, never
# folded into the always-installed CPU-only `WINDOWS_RUNTIME_REQUIREMENTS`.
WINDOWS_CUDA_REDISTRIBUTABLE_REQUIREMENTS: tuple[str, ...] = (
    "nvidia-cuda-runtime==13.0.96",
    "nvidia-cuda-nvrtc==13.0.88",
    "nvidia-cublas==13.1.1.3",
    "nvidia-cufft==12.0.0.61",
    "nvidia-curand==10.4.0.35",
    "nvidia-cudnn-cu13==9.20.0.48",
)

# The minimum floor `verify_windows_gpu_runtime_dll_closure` always demands by
# exact basename, regardless of what each pinned wheel's own RECORD claims --
# a real native-Windows acceptance pass found `onnxruntime_providers_cuda.dll`
# present and loadable, `onnxruntime.get_available_providers()` correctly
# reporting `CUDAExecutionProvider`, and the packaged model resolving
# correctly, with only `cublasLt64_13.dll` (the single largest file in the
# entire GPU/CUDA closure, ~400-480 MB) actually missing from the assembled
# bundle -- every earlier signal looked fine. These are exactly the DLLs
# `onnxruntime_providers_cuda.dll` dlopens at CUDA-session-creation time for
# the accepted MDv5 model (see docs/local-product-packaging-design.md).
REQUIRED_CUDA_RUNTIME_DLL_BASENAMES: tuple[str, ...] = (
    "cudart64_13.dll",
    "cublas64_13.dll",
    "cublasLt64_13.dll",
    "cudnn64_9.dll",
)
# `onnxruntime_providers_shared.dll` is the loader every ONNX Runtime
# execution-provider DLL (including `_cuda`) depends on -- both must be
# present for `CUDAExecutionProvider` to actually instantiate, not just be
# listed by `get_available_providers()`.
REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES: tuple[str, ...] = (
    "onnxruntime_providers_cuda.dll",
    "onnxruntime_providers_shared.dll",
)

# Mirrors `mockingbird.observation.engine_runtime.PACKAGED_OBSERVATION_
# RUNTIME_DIRNAME`/`PACKAGED_PROVIDER_CONFIG_FILENAME` exactly -- duplicated
# as literals (like `WINDOWS_RUNTIME_REQUIREMENTS` above) rather than
# imported, so this build script never depends on `mockingbird` itself being
# importable from the build host's ambient environment. Keep these two
# values in sync with engine_runtime.py.
PACKAGED_OBSERVATION_RUNTIME_DIRNAME = "observation_runtime"
PACKAGED_PROVIDER_CONFIG_FILENAME = "provider-config.json"

# Doctrine-recorded provenance for the one accepted Observation Engine model
# (docs/megadetector-runtime-findings.md's "Approved local-artifact
# provenance" record for `md-v5a`, and the real NVIDIA-GPU-validated ONNX
# export from the Observation Engine v2 Stage 3 activation). A build must
# never silently ship a *different* model than the one this project has
# actually accepted for production use -- these are the only fingerprints a
# packaged bundle is allowed to match; anything else is refused (not
# packaged, never crashes the build) with an honest, logged reason.
ACCEPTED_MODEL_KEY = "md-v5a"
ACCEPTED_MODEL_DECODER = "megadetector_v5_yolov5_raw_v1"
ACCEPTED_MODEL_LICENSE = "MIT"
# The official upstream MDv5a.0.1 PyTorch checkpoint this bundle was
# exported from (agentmorris/MegaDetector v5.0 release, MIT-licensed --
# see docs/megadetector-runtime-findings.md).
ACCEPTED_SOURCE_MODEL_SHA256 = "fe3e90e4b1955821ab7c1f88b446dc0c8cb25e109fdd1872916a55305294a5ef"
# The ONNX export of that checkpoint (opset 18, raw fixed-1280 MDv5 decoder
# contract) this project has actually validated with a real CUDA GPU.
ACCEPTED_ONNX_MODEL_SHA256 = "b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc"

# The existing, documented local-artifact convention (docs/megadetector
# -local-setup.md: "Use an ignored local path for model files, such as
# data/models/<subsystem>/") -- never a repository-tracked path; model
# weights are never committed (docs/model-adapter-guardrails.md). Used only
# as this build's default source when the operator does not pass
# `--model-bundle-source` explicitly.
DEFAULT_MODEL_BUNDLE_SOURCE = ROOT / "data" / "models" / "observation-onnx-cuda"

# `pip wheel .`'s actual inputs: the wheel's own package content plus the
# two files hatchling/PEP 621 reads directly (`pyproject.toml`, and the
# `readme` it points at). Scoped precisely to what is packaged, not the
# whole repository -- docs/tests/scripts changes never block a release build.
RELEASE_SOURCE_PATHS: tuple[str, ...] = ("src/mockingbird", "pyproject.toml", "README.md")

# A fixed timestamp keeps the produced zip byte-identical across rebuilds of
# identical input, matching the existing convention in
# scripts/build_camera_node_artifact.py.
_FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)

LAUNCHER_VBS = (
    "' MockingBird local product launcher.\r\n"
    "' Double-click this file to start MockingBird. It opens no terminal\r\n"
    "' window; MockingBird opens your browser automatically once ready. If\r\n"
    "' MockingBird cannot start, it shows its own message explaining why --\r\n"
    "' pythonw.exe has no console/terminal of its own to show one in.\r\n"
    "Set shell = CreateObject(\"WScript.Shell\")\r\n"
    "Set fso = CreateObject(\"Scripting.FileSystemObject\")\r\n"
    "scriptDirectory = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
    "shell.CurrentDirectory = scriptDirectory\r\n"
    "pythonwPath = scriptDirectory & \"\\python\\pythonw.exe\"\r\n"
    "If Not fso.FileExists(pythonwPath) Then\r\n"
    "    MsgBox \"MockingBird cannot start: \" & pythonwPath & \" is missing.\" & Chr(13) & \"Try re-extracting the MockingBird folder from its zip file.\", vbCritical, \"MockingBird\"\r\n"
    "    WScript.Quit 1\r\n"
    "End If\r\n"
    "shell.Run \"\"\"\" & pythonwPath & \"\"\" -m mockingbird\", 0, False\r\n"
)

README_FIRST = (
    "MockingBird - local wildlife-camera product\r\n"
    "============================================\r\n"
    "\r\n"
    "To start MockingBird, double-click \"Start MockingBird.vbs\" in this folder.\r\n"
    "\r\n"
    "MockingBird opens in your default web browser once it is ready. The first\r\n"
    "time you start it, it walks you through a short guided setup: where to\r\n"
    "keep its local data, adding a camera, and starting observation.\r\n"
    "\r\n"
    "If MockingBird cannot start, a message box explains why. For more detail,\r\n"
    "check logs\\mockingbird.log inside MockingBird's local data folder (open\r\n"
    "%LOCALAPPDATA%\\MockingBird in File Explorer, unless you changed where\r\n"
    "MockingBird keeps its data), or run \"python\\python.exe -m mockingbird\"\r\n"
    "from a command prompt in this folder to see the full error directly.\r\n"
    "\r\n"
    "MockingBird keeps everything -- cameras, Zones, reviewed visits, and\r\n"
    "backups -- in one local folder on this computer. Nothing is uploaded\r\n"
    "anywhere. You can close MockingBird at any time by closing its browser\r\n"
    "tab and, if you want to fully stop it, ending the \"pythonw.exe\" process\r\n"
    "from Task Manager (it does not keep running with no window open once you\r\n"
    "choose Stop observing on every camera, but the local web server itself\r\n"
    "stays available at http://127.0.0.1:8000 until stopped that way).\r\n"
    "\r\n"
    "If MockingBird is already running and you start it again (for example by\r\n"
    "double-clicking twice), it reuses the already-running copy and opens your\r\n"
    "browser to it. It never opens a different program that merely happens to\r\n"
    "answer on the same port; it explains that as a port conflict instead.\r\n"
    "\r\n"
    "This folder can be moved or copied anywhere; nothing outside this folder\r\n"
    "is required to run MockingBird.\r\n"
    "\r\n"
    "Wildlife observation on an NVIDIA PC\r\n"
    "-------------------------------------\r\n"
    "Pressing \"Start observing\" on a paired Camera Node needs no extra setup\r\n"
    "on a PC with a compatible NVIDIA GPU and a current driver -- the model and\r\n"
    "GPU runtime MockingBird needs are already included in this folder. If your\r\n"
    "PC's GPU is not supported, MockingBird says so in plain language instead\r\n"
    "of guessing or silently running slower than expected.\r\n"
)


class LocalProductBuildError(RuntimeError):
    """Raised when a required build step fails."""


@dataclass(frozen=True)
class LocalProductArtifact:
    bundle_dir: Path
    zip_path: Path
    manifest_path: Path
    checksums_path: Path


@dataclass(frozen=True)
class ModelBundleProvenance:
    """What `package_observation_runtime_assets` actually did, recorded in
    `manifest.json` either way -- inclusion is never silent, and neither is
    its absence."""

    included: bool
    reason: str | None = None
    model_key: str | None = None
    model_version: str | None = None
    decoder_key: str | None = None
    license_name: str | None = None
    source_model_sha256: str | None = None
    onnx_model_sha256: str | None = None

    def as_manifest_dict(self) -> dict[str, object]:
        return {
            "included": self.included,
            "reason": self.reason,
            "model_key": self.model_key,
            "model_version": self.model_version,
            "decoder_key": self.decoder_key,
            "license": self.license_name,
            "source_model_sha256": self.source_model_sha256,
            "onnx_model_sha256": self.onnx_model_sha256,
        }


@dataclass(frozen=True)
class NativeRuntimeVerification:
    """What `verify_windows_gpu_runtime_dll_closure` actually found, recorded
    in `manifest.json` like `ModelBundleProvenance` -- a build must never
    silently ship (or silently skip checking) an incomplete native CUDA/cuDNN
    DLL closure. `checked=False` is itself an honestly-reported, explicitly
    supported state (matching `--skip-gpu-runtime`); `checked=True` is only
    ever produced after every required DLL was confirmed present on disk at
    its RECORD-declared size -- this dataclass cannot represent "checked but
    incomplete", because that case raises `LocalProductBuildError` instead of
    ever being constructed."""

    checked: bool
    reason: str | None = None
    verified_dlls: tuple[str, ...] = ()
    dll_directories: tuple[str, ...] = ()

    def as_manifest_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "reason": self.reason,
            "verified_dlls": list(self.verified_dlls),
            "dll_directories": list(self.dll_directories),
        }


def _run(command: Sequence[str], *, cwd: Path) -> None:
    completed = subprocess.run(list(command), cwd=cwd, check=False)
    if completed.returncode != 0:
        raise LocalProductBuildError(
            f"Build command failed ({completed.returncode}): {' '.join(command)}"
        )


def build_frontend() -> None:
    """Build the production frontend from source. Requires `npm`."""

    if not (WEB_ROOT / "node_modules").is_dir():
        _run(["npm", "ci"], cwd=WEB_ROOT)
    _run(["npm", "run", "build"], cwd=WEB_ROOT)


def sync_packaged_web_dist(
    *,
    source_dist: Path | None = None,
    target_dir: Path | None = None,
) -> Path:
    """Copy a built frontend into the path `web_app.py` already prefers.

    Never invoked implicitly by import; `web_dist/` stays absent (and
    `web_app.resolve_frontend_dist` falls back to the dev checkout's
    `web/dist`) until this is explicitly run, matching the existing
    "do not build a packaged artifact just by importing the package" rule.
    `target_dir` exists so tests (and the clean-source-snapshot build path
    below) can redirect the destination instead of writing into this
    checkout's real `src/mockingbird/web_dist`.
    """

    dist = source_dist or (WEB_ROOT / "dist")
    destination = target_dir or PACKAGED_WEB_DIST
    if not (dist / "index.html").is_file():
        raise LocalProductBuildError(
            f"No built frontend at {dist}. Run build_frontend() (or `npm run build`) first."
        )
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(dist, destination)
    return destination


def verify_clean_tracked_source(
    *, paths: Sequence[str] = RELEASE_SOURCE_PATHS, cwd: Path = ROOT,
) -> str:
    """Prove the exact wheel inputs match a real git commit, with no
    uncommitted edit sitting unreviewed on top of it. Returns the resolved
    commit hash a clean build is taken from.

    This deliberately checks `git diff` (working tree vs. `HEAD`) rather
    than `git status`: a plain *untracked* file is not an ambiguity this
    check needs to resolve at all -- `export_clean_source_tree` (`git
    archive`) already structurally excludes anything untracked from the
    packaged snapshot regardless, the actual fix for the discovered "an
    untracked file leaked into the release wheel" defect. What `git diff`
    alone can catch, and what really would make the source state
    unprovable, is a *tracked* packaged-input file with uncommitted
    modifications: building from `HEAD` would then silently ship a stale
    version while the working tree shows something the operator may have
    intended to include.
    """

    completed = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", *paths],
        cwd=cwd, check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise LocalProductBuildError(
            f"Could not verify source cleanliness with git: {completed.stderr.strip()}"
        )
    dirty = completed.stdout.strip()
    if dirty:
        changed = ", ".join(dirty.splitlines())
        raise LocalProductBuildError(
            "Refusing to build a release artifact: uncommitted changes exist in tracked "
            f"packaged-input files ({changed}). Commit them first, or pass "
            "--allow-dirty-source for a local/development build only -- never for a "
            "release artifact."
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cwd, check=False, capture_output=True, text=True,
    )
    if head.returncode != 0 or not head.stdout.strip():
        raise LocalProductBuildError(
            f"Could not resolve the current git commit for a clean release build: {head.stderr.strip()}"
        )
    return head.stdout.strip()


def export_clean_source_tree(*, ref: str, destination: Path, cwd: Path = ROOT) -> Path:
    """Materialize exactly `ref`'s tracked tree into `destination` -- the
    actual "clean tracked source snapshot" the release wheel is compiled
    from, structurally immune to any untracked file physically present in
    the live working tree (unlike running `pip wheel .` directly against
    the checkout, which is what previously let one leak into a real
    release wheel undetected)."""

    destination.mkdir(parents=True, exist_ok=True)
    archive_zip = destination.parent / f"{destination.name}-source.zip"
    _run(["git", "archive", "--format=zip", "--output", str(archive_zip), ref], cwd=cwd)
    with zipfile.ZipFile(archive_zip) as archive:
        archive.extractall(destination)
    archive_zip.unlink()
    return destination


def build_wheel(output_dir: Path, *, source_root: Path = ROOT) -> Path:
    """Build the MockingBird wheel (an internal artifact, not the deliverable).

    Requires `web_dist/` to already exist under `source_root` (see
    `sync_packaged_web_dist`) so the wheel's `artifacts` config in
    pyproject.toml has something to include. `source_root` is the *clean
    tracked source snapshot* by default in the real build path
    (`build_local_product`), never the live checkout directly -- see
    `verify_clean_tracked_source`/`export_clean_source_tree`.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    _run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(output_dir)],
        cwd=source_root,
    )
    wheels = sorted(output_dir.glob("mockingbird-*.whl"))
    if not wheels:
        raise LocalProductBuildError("Wheel build did not produce a mockingbird-*.whl file.")
    return wheels[-1]


def fetch_embeddable_python(
    *,
    cache_dir: Path = DEFAULT_BUILD_CACHE_DIR,
    override_zip_path: Path | None = None,
) -> Path:
    """Return a local copy of the CPython embeddable distribution for Windows.

    `override_zip_path` lets tests and offline builds supply an existing
    (real or fixture) zip instead of fetching python.org.
    """

    if override_zip_path is not None:
        return override_zip_path
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_path = cache_dir / f"python-{EMBED_PYTHON_VERSION}-embed-{EMBED_PYTHON_TAG}.zip"
    if cached_path.is_file():
        return cached_path
    with urlopen(EMBED_PYTHON_URL, timeout=60) as response:
        cached_path.write_bytes(response.read())
    return cached_path


def install_windows_runtime_dependencies(
    *,
    site_packages: Path,
    requirements: Sequence[str] = WINDOWS_RUNTIME_REQUIREMENTS,
) -> None:
    """Pre-install every runtime dependency for win_amd64/cp312 at build time.

    This is the one step that talks to PyPI; tests inject a fake
    `install_dependencies` callable instead of calling this for real, so the
    unit-test suite stays hermetic and fast. See
    docs/local-product-packaging-design.md for the verified cross-platform
    `pip install --target` technique this uses.
    """

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(site_packages),
            "--platform",
            "win_amd64",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--abi",
            "cp312",
            "--only-binary=:all:",
            "--no-compile",
            *requirements,
        ],
        cwd=ROOT,
    )


def install_windows_gpu_runtime_dependencies(
    *,
    site_packages: Path,
    requirements: Sequence[str] = WINDOWS_GPU_RUNTIME_REQUIREMENTS + WINDOWS_CUDA_REDISTRIBUTABLE_REQUIREMENTS,
    wheel_cache_dir: Path | None = DEFAULT_WHEEL_CACHE_DIR,
) -> None:
    """Pre-install the ONNX Runtime GPU + CUDA/cuDNN redistributable stack,
    same cross-platform `pip install --target` technique as
    `install_windows_runtime_dependencies`. Kept as its own function/
    requirement list -- large (roughly 1.1 GB) and optional
    (`--skip-gpu-runtime`) -- rather than folded into the base CPU-only
    installer; tests inject a fake installer here too, for the same
    hermetic/fast reason.

    When `wheel_cache_dir` exists (the default: the verified local cache
    documented in docs/local-product-packaging-design.md), installs with
    `--find-links <dir> --no-index` -- entirely offline, and immune to a
    partial/interrupted fetch of any of this stack's several-hundred-MB
    wheels over the network on every single build. A build host with no
    cache yet (`wheel_cache_dir` absent, or explicitly passed as `None`)
    falls back to a normal network install, unchanged from before. Either
    way, `verify_windows_gpu_runtime_dll_closure` (called right after this by
    `assemble_windows_bundle`) is what actually proves the result is
    complete -- this cache reuse only makes that outcome more likely, it is
    never itself trusted as proof.
    """

    find_links_arguments: list[str] = []
    if wheel_cache_dir is not None and wheel_cache_dir.is_dir():
        find_links_arguments = ["--find-links", str(wheel_cache_dir), "--no-index"]

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(site_packages),
            "--platform",
            "win_amd64",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--abi",
            "cp312",
            "--only-binary=:all:",
            "--no-compile",
            *find_links_arguments,
            *requirements,
        ],
        cwd=ROOT,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_observation_runtime_assets(
    *,
    site_packages: Path,
    model_bundle_source: Path | None = DEFAULT_MODEL_BUNDLE_SOURCE,
) -> ModelBundleProvenance:
    """Copy the accepted Observation Engine's default provider configuration
    and MDv5 ONNX model bundle into
    `<site_packages>/mockingbird/observation_runtime/` -- the path
    `mockingbird.observation.engine_runtime.packaged_observation_runtime_root`
    resolves at app startup, so a normal packaged install needs no
    `MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH`.

    `model_bundle_source` is a local, ignored, developer/CI-supplied
    directory holding exactly the existing `frame-driven-onnx-cuda`
    provider-config/model-bundle/`.onnx` layout `replay-benchmark`/
    `candidate-authority-trial` already document (never a repository-
    tracked path -- model weights are never committed). Every fingerprint
    is independently re-verified against `ACCEPTED_SOURCE_MODEL_SHA256`/
    `ACCEPTED_ONNX_MODEL_SHA256` before anything is copied: this build can
    only ever ship the one model this project has actually accepted, never
    a substitute, and never a corrupted file that merely claims to match.

    Never raises: a missing/invalid/mismatched source is reported (not
    packaged) rather than failing the whole release build, because
    "missing model bundle" is an explicitly supported, honestly-reported
    Observation Engine state, not a packaging error. The caller is
    responsible for surfacing `ModelBundleProvenance.reason` (the CLI does).
    """

    if model_bundle_source is None or not model_bundle_source.is_dir():
        return ModelBundleProvenance(included=False, reason="no_model_bundle_source_supplied")

    provider_config_source = model_bundle_source / "frame-driven-provider-config.json"
    if provider_config_source.is_symlink() or not provider_config_source.is_file():
        return ModelBundleProvenance(included=False, reason="provider_config_missing")
    try:
        provider_config = json.loads(provider_config_source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return ModelBundleProvenance(included=False, reason=f"provider_config_unreadable:{error}")

    model_bundle_name = provider_config.get("model_bundle")
    if (
        not isinstance(model_bundle_name, str)
        or not model_bundle_name
        or Path(model_bundle_name).is_absolute()
        or ".." in Path(model_bundle_name).parts
    ):
        return ModelBundleProvenance(included=False, reason="invalid_model_bundle_reference")
    bundle_manifest_source = model_bundle_source / model_bundle_name
    if bundle_manifest_source.is_symlink() or not bundle_manifest_source.is_file():
        return ModelBundleProvenance(included=False, reason="model_bundle_manifest_missing")
    try:
        bundle_manifest = json.loads(bundle_manifest_source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return ModelBundleProvenance(included=False, reason=f"model_bundle_manifest_unreadable:{error}")

    model_file_name = bundle_manifest.get("model_file")
    if (
        not isinstance(model_file_name, str)
        or not model_file_name
        or Path(model_file_name).is_absolute()
        or ".." in Path(model_file_name).parts
    ):
        return ModelBundleProvenance(included=False, reason="invalid_model_file_reference")
    model_file_source = model_bundle_source / model_file_name
    if model_file_source.is_symlink() or not model_file_source.is_file():
        return ModelBundleProvenance(included=False, reason="model_file_missing")

    onnx_sha256 = _sha256(model_file_source)
    declared_fingerprint = bundle_manifest.get("model_fingerprint")
    source_sha256 = bundle_manifest.get("source_model_fingerprint")

    if declared_fingerprint != onnx_sha256:
        # The manifest's own claimed hash does not even match the file next
        # to it -- corrupt/truncated download or a tampered bundle. Refused
        # before the "is this the accepted model" comparison below, so the
        # reported reason is specific.
        return ModelBundleProvenance(included=False, reason="model_file_corrupt_or_hash_mismatch")

    if (
        onnx_sha256 != ACCEPTED_ONNX_MODEL_SHA256
        or source_sha256 != ACCEPTED_SOURCE_MODEL_SHA256
        or bundle_manifest.get("decoder_key") != ACCEPTED_MODEL_DECODER
        or bundle_manifest.get("model_key") != ACCEPTED_MODEL_KEY
        or bundle_manifest.get("license") != ACCEPTED_MODEL_LICENSE
    ):
        return ModelBundleProvenance(
            included=False,
            reason=f"model_bundle_does_not_match_accepted_provenance:sha256={onnx_sha256}",
        )

    destination = site_packages / "mockingbird" / PACKAGED_OBSERVATION_RUNTIME_DIRNAME
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(provider_config_source, destination / PACKAGED_PROVIDER_CONFIG_FILENAME)
    shutil.copy2(bundle_manifest_source, destination / model_bundle_name)
    shutil.copy2(model_file_source, destination / model_file_name)

    return ModelBundleProvenance(
        included=True,
        model_key=bundle_manifest.get("model_key"),
        model_version=bundle_manifest.get("model_version"),
        decoder_key=bundle_manifest.get("decoder_key"),
        license_name=bundle_manifest.get("license"),
        source_model_sha256=source_sha256,
        onnx_model_sha256=onnx_sha256,
    )


def _iter_installed_dll_entries(site_packages: Path) -> list[tuple[Path, int | None]]:
    """Every `.dll` file actually declared by an installed package's own
    `RECORD`, resolved to an absolute path under `site_packages`, paired with
    the byte size that `RECORD` declares for it (`None` only if a `RECORD`
    row omits a size, which a real content entry never does -- only a
    package's self-referential `.../RECORD,,` line does, and that never ends
    in `.dll`).

    `pip install --target ... --platform win_amd64 ...` writes a real
    `RECORD` for every installed package regardless of whether the installed
    platform matches this (Linux) build host -- it is generated from the
    wheel's own manifest, not by importing/executing anything. Reading it is
    therefore a way to discover exactly which `.dll` files (and where) a
    pinned package's *real* Windows wheel actually ships, without hard-coding
    a directory depth or a fixed file list: NVIDIA's own Windows wheels nest
    `.dll` files a different number of directories deep per package (see
    `onnx_provider._prepare_windows_onnxruntime_dll_search_path`), and a
    future pinned-version bump could change that layout again -- this keeps
    working either way, and would have caught the real discovered defect
    (`cublasLt64_13.dll` declared by `nvidia-cublas`'s own `RECORD` but not
    actually present in the assembled bundle) regardless of *why* the file
    went missing.
    """

    entries: list[tuple[Path, int | None]] = []
    for record_path in sorted(site_packages.glob("*.dist-info/RECORD")):
        try:
            text = record_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for row in csv.reader(text.splitlines()):
            if not row or not row[0]:
                continue
            relative_path = row[0]
            if not relative_path.lower().endswith(".dll"):
                continue
            if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
                continue
            declared_size = int(row[2]) if len(row) > 2 and row[2].isdigit() else None
            entries.append((site_packages / relative_path, declared_size))
    return entries


def verify_windows_gpu_runtime_dll_closure(*, site_packages: Path) -> NativeRuntimeVerification:
    """Prove every native DLL the packaged `onnxruntime-gpu` CUDA execution
    provider actually depends on at session-creation time is really present
    on disk in the assembled bundle -- not merely that the owning package's
    Python metadata was importable, or that `pip install` exited zero. A real
    native-Windows acceptance pass against a real GPU found `onnxruntime_
    providers_cuda.dll` present and `onnxruntime.get_available_providers()`
    correctly reporting `CUDAExecutionProvider`, with only its own
    `cublasLt64_13.dll` dependency silently absent -- every earlier,
    metadata-level signal looked fine (see
    docs/local-product-packaging-design.md).

    Only ever inspects `site_packages` itself (via `_iter_installed_dll_
    entries`): never `PATH`, `CUDA_PATH`, or any other system/environment
    CUDA installation, matching this product's "no system CUDA Toolkit
    required" packaging contract -- a build host with CUDA installed
    system-wide must not be able to pass this check by accident on that
    host's behalf.

    Never silently passes and never falls back: raises
    `LocalProductBuildError` (failing the whole release build, not a
    warning) the moment either failure shape a good-looking-but-broken
    install can take is found --

    - any `RECORD`-declared `.dll` missing from disk, or present at a
      different size than `RECORD` declares (catches truncation/corruption,
      not only outright absence); or
    - zero `.dll` files found at all, or any of
      `REQUIRED_CUDA_RUNTIME_DLL_BASENAMES`/`REQUIRED_ORT_CUDA_PROVIDER_DLL_
      BASENAMES` specifically missing from what *was* found --

    never by silently continuing with a CPU-only or partial artifact. Callers
    only reach this with `include_gpu_runtime=True`; a build that explicitly
    opts out (`--skip-gpu-runtime`) never calls this at all, matching the
    honestly-reported (not failed) `ModelBundleProvenance` "missing" state.
    """

    entries = _iter_installed_dll_entries(site_packages)
    if not entries:
        raise LocalProductBuildError(
            "Windows GPU runtime verification found zero .dll files declared by any "
            f"installed package under {site_packages} -- the CUDA/cuDNN redistributable "
            "install did not place any native runtime library in the bundle at all."
        )

    verified_names: set[str] = set()
    dll_directories: set[Path] = set()
    for dll_path, declared_size in entries:
        relative = dll_path.relative_to(site_packages)
        if not dll_path.is_file():
            raise LocalProductBuildError(
                f"Windows GPU runtime verification failed: {relative} is declared by its "
                "package's own RECORD but is not actually present in the assembled bundle "
                "-- the exact defect class a real native-Windows CUDA session-creation "
                "failure surfaced (Error 126, a missing dependency DLL). See "
                "docs/local-product-packaging-design.md."
            )
        actual_size = dll_path.stat().st_size
        if declared_size is not None and actual_size != declared_size:
            raise LocalProductBuildError(
                f"Windows GPU runtime verification failed: {relative} is {actual_size} bytes "
                f"but its package's own RECORD declares {declared_size} bytes -- truncated or "
                "corrupted during install or packaging."
            )
        verified_names.add(dll_path.name)
        dll_directories.add(dll_path.parent)

    missing = [
        name
        for name in (*REQUIRED_CUDA_RUNTIME_DLL_BASENAMES, *REQUIRED_ORT_CUDA_PROVIDER_DLL_BASENAMES)
        if name not in verified_names
    ]
    if missing:
        raise LocalProductBuildError(
            "Windows GPU runtime verification failed: required native DLL(s) not found in "
            f"the assembled bundle: {', '.join(missing)}. Present instead: "
            f"{', '.join(sorted(verified_names)) or '(none)'}."
        )

    return NativeRuntimeVerification(
        checked=True,
        verified_dlls=tuple(sorted(verified_names)),
        dll_directories=tuple(sorted(str(directory.relative_to(site_packages)) for directory in dll_directories)),
    )


def _patch_pth_file(python_dir: Path) -> None:
    """Point the embeddable interpreter at `site-packages` -- no venv, no pip.

    Embeddable Python ships with `import site` commented out and a `._pth`
    file that fixes `sys.path` explicitly; appending the one extra relative
    directory here is the documented, minimal way to make a flat
    `pip install --target` layout importable without enabling `site` (which
    would also require pip/setuptools present, which this bundle deliberately
    omits).
    """

    candidates = sorted(python_dir.glob("python3*._pth"))
    if not candidates:
        raise LocalProductBuildError(
            "Embeddable Python distribution is missing its python3*._pth file."
        )
    pth_path = candidates[0]
    text = pth_path.read_text(encoding="utf-8")
    if "site-packages" in text.splitlines():
        return
    pth_path.write_text(text.rstrip("\n") + "\nsite-packages\n", encoding="utf-8")


def assemble_windows_bundle(
    *,
    bundle_dir: Path,
    wheel_path: Path,
    embed_zip_path: Path,
    install_dependencies: Callable[[Path], None] | None = None,
    install_gpu_dependencies: Callable[[Path], None] | None = None,
    include_gpu_runtime: bool = True,
    model_bundle_source: Path | None = DEFAULT_MODEL_BUNDLE_SOURCE,
    wheel_cache_dir: Path | None = DEFAULT_WHEEL_CACHE_DIR,
) -> tuple[Path, ModelBundleProvenance, NativeRuntimeVerification]:
    """Assemble the unpack-and-run Windows folder. Returns `(bundle_dir,
    model_bundle_provenance, native_runtime_verification)`."""

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    python_dir = bundle_dir / "python"
    python_dir.mkdir(parents=True)

    with zipfile.ZipFile(embed_zip_path) as archive:
        archive.extractall(python_dir)

    site_packages = python_dir / "site-packages"
    site_packages.mkdir()

    installer = install_dependencies or (
        lambda target: install_windows_runtime_dependencies(site_packages=target)
    )
    installer(site_packages)

    if include_gpu_runtime:
        gpu_installer = install_gpu_dependencies or (
            lambda target: install_windows_gpu_runtime_dependencies(
                site_packages=target, wheel_cache_dir=wheel_cache_dir,
            )
        )
        gpu_installer(site_packages)
        # Fails the whole build (raises, never a warning) the moment any
        # required native DLL -- `cublasLt64_13.dll` foremost, the real
        # discovered defect -- is missing or the wrong size. Runs before the
        # (slow, ~2 GB) zip step below so a broken GPU stack fails fast.
        native_runtime_verification = verify_windows_gpu_runtime_dll_closure(site_packages=site_packages)
    else:
        native_runtime_verification = NativeRuntimeVerification(checked=False, reason="gpu_runtime_skipped")

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(site_packages),
            "--no-deps",
            "--no-compile",
            str(wheel_path),
        ],
        cwd=ROOT,
    )
    # A cross-platform `--target` install writes a host-OS console-script
    # shim (a Linux shell script here) that is meaningless on Windows and
    # never used -- the launcher runs `-m mockingbird` directly. Drop it so
    # the bundle contains nothing that looks executable but is not.
    for stray_directory in ("bin", "Scripts"):
        shutil.rmtree(site_packages / stray_directory, ignore_errors=True)

    _patch_pth_file(python_dir)

    model_provenance = package_observation_runtime_assets(
        site_packages=site_packages, model_bundle_source=model_bundle_source,
    )
    if not model_provenance.included:
        print(
            f"WARNING: Observation Engine model bundle not packaged ({model_provenance.reason}). "
            "The produced artifact still boots; 'Start observing' will honestly report a "
            "missing model/runtime state until a bundle is supplied and this build is re-run "
            "with --model-bundle-source.",
            file=sys.stderr,
        )

    (bundle_dir / "Start MockingBird.vbs").write_text(LAUNCHER_VBS, encoding="utf-8")
    (bundle_dir / "README-FIRST.txt").write_text(README_FIRST, encoding="utf-8")
    return bundle_dir, model_provenance, native_runtime_verification


def _iter_files_sorted(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file())


def write_deterministic_zip(source_dir: Path, zip_path: Path) -> Path:
    """Zip `source_dir` with fixed timestamps and sorted entries.

    Byte-identical input therefore produces a byte-identical archive across
    rebuilds -- the practical, testable form of "deterministic" for a bundle
    whose contents are pip-installed released wheels (themselves stable byte
    -for-byte from PyPI for a pinned version) rather than freshly compiled
    output. Mirrors the fixed-timestamp convention already used in
    scripts/build_camera_node_artifact.py.
    """

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in _iter_files_sorted(source_dir):
            arcname = f"{source_dir.name}/{file_path.relative_to(source_dir).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_ZIP_TIMESTAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, file_path.read_bytes())
    return zip_path


def write_manifest(
    *,
    output_dir: Path,
    bundle_dir: Path,
    zip_path: Path,
    source_state: str,
    model_bundle_provenance: ModelBundleProvenance | None = None,
    gpu_runtime_included: bool | None = None,
    native_runtime_verification: NativeRuntimeVerification | None = None,
) -> tuple[Path, Path]:
    version = _source_version()
    files = _iter_files_sorted(bundle_dir)
    manifest = {
        "artifact": zip_path.name,
        "package": "mockingbird-local-product-windows-x64",
        "version": version,
        "source_state": source_state,
        "embedded_python_version": EMBED_PYTHON_VERSION,
        "runtime_requirements": list(WINDOWS_RUNTIME_REQUIREMENTS),
        "gpu_runtime_included": gpu_runtime_included,
        "gpu_runtime_requirements": (
            list(WINDOWS_GPU_RUNTIME_REQUIREMENTS + WINDOWS_CUDA_REDISTRIBUTABLE_REQUIREMENTS)
            if gpu_runtime_included
            else []
        ),
        "observation_model_bundle": (
            model_bundle_provenance.as_manifest_dict()
            if model_bundle_provenance is not None
            else ModelBundleProvenance(included=False, reason="not_evaluated").as_manifest_dict()
        ),
        "native_cuda_runtime": (
            native_runtime_verification.as_manifest_dict()
            if native_runtime_verification is not None
            else NativeRuntimeVerification(checked=False, reason="not_evaluated").as_manifest_dict()
        ),
        "bundle_file_count": len(files),
        "bundle_total_bytes": sum(path.stat().st_size for path in files),
        "zip_sha256": _sha256(zip_path),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checksums_path = output_dir / "SHA256SUMS"
    checksums_path.write_text(
        "".join(
            f"{_sha256(path)}  {path.name}\n" for path in (zip_path, manifest_path) if path.exists()
        ),
        encoding="utf-8",
    )
    return manifest_path, checksums_path


def _source_version() -> str:
    import tomllib

    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def build_local_product(
    output_dir: Path,
    *,
    source_state: str | None = None,
    skip_frontend_build: bool = False,
    embed_zip_override: Path | None = None,
    install_dependencies: Callable[[Path], None] | None = None,
    install_gpu_dependencies: Callable[[Path], None] | None = None,
    include_gpu_runtime: bool = True,
    model_bundle_source: Path | None = DEFAULT_MODEL_BUNDLE_SOURCE,
    wheel_cache_dir: Path | None = DEFAULT_WHEEL_CACHE_DIR,
    allow_dirty_source: bool = False,
) -> LocalProductArtifact:
    """Run the complete build: frontend -> clean source snapshot -> wheel ->
    Windows bundle -> zip.

    By default (`allow_dirty_source=False`, the only mode a real release
    should ever use) the wheel is built from a `git archive` snapshot of
    `HEAD`, not the live checkout -- see `verify_clean_tracked_source`/
    `export_clean_source_tree`. `allow_dirty_source=True` exists only for
    iterating on this build script itself against uncommitted local edits.
    """

    if not skip_frontend_build:
        build_frontend()

    output_dir.mkdir(parents=True, exist_ok=True)

    if allow_dirty_source:
        resolved_source_state = source_state or "dirty:unverified-working-tree"
        sync_packaged_web_dist()
        wheel_path = build_wheel(output_dir / "_wheel", source_root=ROOT)
    else:
        commit = verify_clean_tracked_source()
        resolved_source_state = source_state or f"git:{commit}"
        with tempfile.TemporaryDirectory(prefix="mockingbird-release-source-") as staging:
            staging_root = Path(staging)
            export_clean_source_tree(ref=commit, destination=staging_root)
            sync_packaged_web_dist(target_dir=staging_root / "src" / "mockingbird" / "web_dist")
            wheel_path = build_wheel(output_dir / "_wheel", source_root=staging_root)

    embed_zip_path = fetch_embeddable_python(override_zip_path=embed_zip_override)

    bundle_dir = output_dir / "MockingBird-windows-x64"
    _, model_provenance, native_runtime_verification = assemble_windows_bundle(
        bundle_dir=bundle_dir,
        wheel_path=wheel_path,
        embed_zip_path=embed_zip_path,
        install_dependencies=install_dependencies,
        install_gpu_dependencies=install_gpu_dependencies,
        include_gpu_runtime=include_gpu_runtime,
        model_bundle_source=model_bundle_source,
        wheel_cache_dir=wheel_cache_dir,
    )

    zip_path = write_deterministic_zip(bundle_dir, output_dir / "MockingBird-windows-x64.zip")
    manifest_path, checksums_path = write_manifest(
        output_dir=output_dir,
        bundle_dir=bundle_dir,
        zip_path=zip_path,
        source_state=resolved_source_state,
        model_bundle_provenance=model_provenance,
        gpu_runtime_included=include_gpu_runtime,
        native_runtime_verification=native_runtime_verification,
    )
    return LocalProductArtifact(
        bundle_dir=bundle_dir,
        zip_path=zip_path,
        manifest_path=manifest_path,
        checksums_path=checksums_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--source-state",
        default=None,
        help=(
            "override the manifest's recorded source identifier; defaults to the "
            "verified git commit (git:<hash>) actually built from"
        ),
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="reuse an existing web/dist instead of running npm ci/build",
    )
    parser.add_argument(
        "--allow-dirty-source",
        action="store_true",
        help=(
            "build the wheel from the live working tree instead of a clean git-archive "
            "snapshot of HEAD -- for local/development iteration only; never for a "
            "release artifact"
        ),
    )
    parser.add_argument(
        "--skip-gpu-runtime",
        action="store_true",
        help=(
            "omit the ONNX Runtime GPU + CUDA/cuDNN redistributable stack (roughly 1.1 GB); "
            "the produced artifact will honestly report an unsupported-GPU/runtime state "
            "instead of ever silently falling back to CPU"
        ),
    )
    parser.add_argument(
        "--model-bundle-source",
        type=Path,
        default=DEFAULT_MODEL_BUNDLE_SOURCE,
        help=(
            "local directory holding the accepted Observation Engine provider-config/"
            "model-bundle/.onnx files to package (never a repository-tracked path); "
            f"defaults to the existing {DEFAULT_MODEL_BUNDLE_SOURCE} convention"
        ),
    )
    parser.add_argument(
        "--wheel-cache-dir",
        type=Path,
        default=DEFAULT_WHEEL_CACHE_DIR,
        help=(
            "local directory of pre-downloaded win_amd64/cp312 GPU-stack wheels to install "
            "the CUDA/cuDNN redistributable stack from offline (`pip --find-links ... "
            f"--no-index`); defaults to the existing {DEFAULT_WHEEL_CACHE_DIR} convention. "
            "Falls back to a normal network install if this directory does not exist."
        ),
    )
    arguments = parser.parse_args()
    artifact = build_local_product(
        arguments.output_dir,
        source_state=arguments.source_state,
        skip_frontend_build=arguments.skip_frontend_build,
        include_gpu_runtime=not arguments.skip_gpu_runtime,
        model_bundle_source=arguments.model_bundle_source,
        wheel_cache_dir=arguments.wheel_cache_dir,
        allow_dirty_source=arguments.allow_dirty_source,
    )
    print(artifact.zip_path)


if __name__ == "__main__":
    main()
