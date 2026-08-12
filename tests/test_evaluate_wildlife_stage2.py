"""Regression coverage for the Stage-2 evaluator's MDv5 input normalization.

`onnx_provider._preprocess` (production code, untouched) fail-closes on any
image whose PIL-detected format isn't exactly ``"JPEG"`` or ``"PNG"``. Real
Stage-2 validation/hard-negative frames sourced from Oregon Critters include
MPO files -- a multi-picture JPEG container some trail cameras use for
burst/stereo capture -- which PIL opens and decodes without complaint (same
as the RF-DETR side of this comparison) but reports a distinct ``.format``
for. ``_onnx_provider_compatible_bytes`` re-encodes exactly those frames to a
plain JPEG of the identical decoded pixels before they reach the adapter, so
the comparison stays fair across all three models on the same corpus without
changing anything under ``src/mockingbird/observation/``.
"""

from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import sys

from PIL import Image
import pytest


def _module():
    # `evaluate_wildlife_stage2.py` itself does a plain top-level
    # `import evaluate_wildlife_stage1` / `from run_detector_candidate_benchmark
    # import Mdv5Adapter`, which only resolves because Python puts a directly
    # `python scripts/evaluate_wildlife_stage2.py`-invoked script's own
    # directory on `sys.path[0]` automatically. Loading it here via
    # `spec_from_file_location` (the established pattern other tests use for
    # a `scripts/*.py` module, see `tests/test_zone_diagnostic.py`) doesn't
    # get that for free, so add `scripts/` for the duration of the import.
    scripts_dir = str(Path("scripts").resolve())
    inserted = scripts_dir not in sys.path
    if inserted:
        sys.path.insert(0, scripts_dir)
    try:
        path = Path("scripts/evaluate_wildlife_stage2.py")
        spec = importlib.util.spec_from_file_location("evaluate_wildlife_stage2", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            sys.path.remove(scripts_dir)


def _write(tmp_path: Path, name: str, image: Image.Image, **save_kwargs: object) -> Path:
    path = tmp_path / name
    image.save(path, **save_kwargs)
    return path


def test_already_supported_formats_pass_through_byte_identical(tmp_path: Path) -> None:
    module = _module()
    image = Image.new("RGB", (32, 24), (10, 20, 30))

    jpeg_path = _write(tmp_path, "frame.jpg", image, format="JPEG")
    png_path = _write(tmp_path, "frame.png", image, format="PNG")

    assert module._onnx_provider_compatible_bytes(jpeg_path) == jpeg_path.read_bytes()
    assert module._onnx_provider_compatible_bytes(png_path) == png_path.read_bytes()


def test_mpo_frame_is_reencoded_to_a_supported_format_with_identical_pixels(
    tmp_path: Path,
) -> None:
    module = _module()
    first_frame = Image.new("RGB", (48, 32), (200, 60, 10))
    second_frame = Image.new("RGB", (48, 32), (5, 5, 5))
    mpo_path = tmp_path / "trail-camera-frame.jpg"
    first_frame.save(mpo_path, format="MPO", save_all=True, append_images=[second_frame])

    # Confirm the fixture actually reproduces the real-world condition before
    # asserting anything about the fix: PIL must see this as MPO, not JPEG.
    with Image.open(mpo_path) as opened:
        assert opened.format == "MPO"

    converted = module._onnx_provider_compatible_bytes(mpo_path)

    with Image.open(BytesIO(converted)) as result:
        assert result.format in module._ONNX_PROVIDER_SUPPORTED_FORMATS
        assert result.size == (48, 32)
        # Same first-frame content RF-DETR's own `Image.open(path).convert("RGB")`
        # sees (both default to frame 0); flat color blocks survive JPEG
        # re-encoding at quality=95 essentially exactly.
        assert result.convert("RGB").getpixel((0, 0)) == pytest.approx(
            (200, 60, 10), abs=3
        )


def test_onnx_provider_supported_formats_are_exactly_jpeg_and_png() -> None:
    module = _module()
    assert module._ONNX_PROVIDER_SUPPORTED_FORMATS == frozenset({"JPEG", "PNG"})


def test_oversized_frame_is_downscaled_under_the_real_production_pixel_cap(
    tmp_path: Path,
) -> None:
    """A real Stage-2 corpus frame (5280x3960, ~20.9MP) exceeds the actual
    `onnx_provider.MAX_INPUT_PIXELS` production guard by about 25%. The
    corpus frame is too large to fixture directly here, but the shape of the
    problem -- and the exact constant the fix must respect -- is real."""

    module = _module()
    width, height = 5280, 3960
    assert width * height > module.MAX_INPUT_PIXELS

    oversized = Image.new("RGB", (width, height), (80, 120, 40))
    path = tmp_path / "oregon-oversized.jpg"
    oversized.save(path, format="JPEG", quality=90)

    converted = module._onnx_provider_compatible_bytes(path)

    with Image.open(BytesIO(converted)) as result:
        result_width, result_height = result.size
        assert result_width * result_height <= module.MAX_INPUT_PIXELS
        assert result.format in module._ONNX_PROVIDER_SUPPORTED_FORMATS
        # Aspect ratio preserved (whole scene resized, not cropped).
        assert result_width / result_height == pytest.approx(width / height, rel=1e-3)


def test_already_small_supported_frame_is_not_downscaled(tmp_path: Path) -> None:
    module = _module()
    image = Image.new("RGB", (64, 48), (1, 2, 3))
    path = tmp_path / "frame.jpg"
    image.save(path, format="JPEG")

    assert module._onnx_provider_compatible_bytes(path) == path.read_bytes()
