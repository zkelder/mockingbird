"""Structural tests for scripts/build_local_product.py.

These stay hermetic and fast: no real `npm run build`, no real network fetch
of the CPython embeddable distribution, and no real cross-platform PyPI
dependency resolution (that step is injected as a fake). What they do
exercise for real: the bundle-assembly filesystem logic (`._pth` patching,
stray-shim removal, launcher/readme contents), byte-for-byte zip
determinism, and manifest/checksum structure.

The full pipeline (frontend build, real wheel build, real win_amd64
dependency resolution, and a fidelity boot of the assembled dependency
layout) was validated by actually running `build_local_product.py` for real
during this milestone's own validation pass -- see
docs/local-product-packaging-design.md -- rather than re-run here on every
test invocation, which would require network access and roughly a minute per
run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import zipfile


ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(ROOT / "scripts" / "build_local_product.py")
assemble_windows_bundle = _MODULE["assemble_windows_bundle"]
sync_packaged_web_dist = _MODULE["sync_packaged_web_dist"]
write_deterministic_zip = _MODULE["write_deterministic_zip"]
write_manifest = _MODULE["write_manifest"]
LocalProductBuildError = _MODULE["LocalProductBuildError"]


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

    result = assemble_windows_bundle(
        bundle_dir=bundle_dir,
        wheel_path=wheel_path,
        embed_zip_path=embed_zip,
        install_dependencies=fake_install_dependencies,
    )

    assert result == bundle_dir
    assert installed_targets == [bundle_dir / "python" / "site-packages"]

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
