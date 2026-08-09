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
- `Start MockingBird.vbs`: a silent (no console window) double-click
  launcher that runs `python\\pythonw.exe -m mockingbird`.
- `README-FIRST.txt`: plain-language instructions.
- `manifest.json` / `SHA256SUMS`: build provenance, mirroring the existing
  convention in scripts/build_camera_node_artifact.py.

Usage:

    python scripts/build_local_product.py dist/mockingbird-local-product

Requires `npm` (to build the frontend once) and network access (to fetch the
embeddable Python distribution and the pinned Windows wheels) on the build
machine. None of that is required on the machine that later runs the bundle.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable, Sequence
from urllib.request import urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
PACKAGED_WEB_DIST = ROOT / "src" / "mockingbird" / "web_dist"
DEFAULT_BUILD_CACHE_DIR = ROOT / ".build-cache"

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
)


class LocalProductBuildError(RuntimeError):
    """Raised when a required build step fails."""


@dataclass(frozen=True)
class LocalProductArtifact:
    bundle_dir: Path
    zip_path: Path
    manifest_path: Path
    checksums_path: Path


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
    `target_dir` exists so tests can redirect the destination instead of
    writing into this checkout's real `src/mockingbird/web_dist`.
    """

    dist = source_dist or (WEB_ROOT / "dist")
    destination = target_dir or PACKAGED_WEB_DIST
    if not (dist / "index.html").is_file():
        raise LocalProductBuildError(
            f"No built frontend at {dist}. Run build_frontend() (or `npm run build`) first."
        )
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(dist, destination)
    return destination


def build_wheel(output_dir: Path) -> Path:
    """Build the MockingBird wheel (an internal artifact, not the deliverable).

    Requires `web_dist/` to already exist (see `sync_packaged_web_dist`) so
    the wheel's `artifacts` config in pyproject.toml has something to include.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    _run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(output_dir)],
        cwd=ROOT,
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
) -> Path:
    """Assemble the unpack-and-run Windows folder. Returns `bundle_dir`."""

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

    (bundle_dir / "Start MockingBird.vbs").write_text(LAUNCHER_VBS, encoding="utf-8")
    (bundle_dir / "README-FIRST.txt").write_text(README_FIRST, encoding="utf-8")
    return bundle_dir


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    source_state: str = "unspecified",
    skip_frontend_build: bool = False,
    embed_zip_override: Path | None = None,
    install_dependencies: Callable[[Path], None] | None = None,
) -> LocalProductArtifact:
    """Run the complete build: frontend -> wheel -> Windows bundle -> zip."""

    if not skip_frontend_build:
        build_frontend()
    sync_packaged_web_dist()

    output_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = build_wheel(output_dir / "_wheel")
    embed_zip_path = fetch_embeddable_python(override_zip_path=embed_zip_override)

    bundle_dir = output_dir / "MockingBird-windows-x64"
    assemble_windows_bundle(
        bundle_dir=bundle_dir,
        wheel_path=wheel_path,
        embed_zip_path=embed_zip_path,
        install_dependencies=install_dependencies,
    )

    zip_path = write_deterministic_zip(bundle_dir, output_dir / "MockingBird-windows-x64.zip")
    manifest_path, checksums_path = write_manifest(
        output_dir=output_dir,
        bundle_dir=bundle_dir,
        zip_path=zip_path,
        source_state=source_state,
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
        default="unspecified",
        help="human-readable committed or working-tree source identifier for this artifact",
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="reuse an existing web/dist instead of running npm ci/build",
    )
    arguments = parser.parse_args()
    artifact = build_local_product(
        arguments.output_dir,
        source_state=arguments.source_state,
        skip_frontend_build=arguments.skip_frontend_build,
    )
    print(artifact.zip_path)


if __name__ == "__main__":
    main()
