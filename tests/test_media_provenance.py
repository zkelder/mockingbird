"""Tier 1 tests for `mockingbird.source_providers.media_provenance` --
v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.9", "II.11",
"II.12"). Real local files only (a synthetic in-memory JPEG/PNG built with
Pillow, and -- for the ffprobe tests -- a tiny real clip generated with the
same real `ffmpeg` binary already required elsewhere in this suite); no
network access.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC
from pathlib import Path

import pytest
from PIL import Image

from mockingbird.source_providers import media_provenance


@pytest.fixture
def exif_image(tmp_path: Path) -> Path:
    path = tmp_path / "capture.jpg"
    image = Image.new("RGB", (4, 4), color="red")
    exif = image.getexif()
    exif_ifd = exif.get_ifd(0x8769)
    exif_ifd[36867] = "2026:08:15 14:30:00"
    image.save(path, format="JPEG", exif=exif)
    return path


@pytest.fixture
def plain_image(tmp_path: Path) -> Path:
    path = tmp_path / "plain.jpg"
    Image.new("RGB", (4, 4), color="blue").save(path, format="JPEG")
    return path


def test_extract_image_captured_at_reads_exif_date_time_original(exif_image: Path) -> None:
    result = media_provenance.extract_image_captured_at(exif_image, local_timezone=UTC)
    assert result.captured_at == pytest_datetime(2026, 8, 15, 14, 30, 0)
    assert result.timezone_assumed is True


def test_extract_image_captured_at_is_none_with_no_exif_block(plain_image: Path) -> None:
    result = media_provenance.extract_image_captured_at(plain_image, local_timezone=UTC)
    assert result.captured_at is None
    assert result.timezone_assumed is False


def test_extract_image_captured_at_never_raises_on_a_missing_file(tmp_path: Path) -> None:
    result = media_provenance.extract_image_captured_at(tmp_path / "missing.jpg", local_timezone=UTC)
    assert result.captured_at is None


def test_extract_image_captured_at_never_raises_on_a_non_image_file(tmp_path: Path) -> None:
    text_file = tmp_path / "not-an-image.jpg"
    text_file.write_text("this is not an image")
    result = media_provenance.extract_image_captured_at(text_file, local_timezone=UTC)
    assert result.captured_at is None


def test_extract_image_captured_at_attaches_the_given_local_timezone(exif_image: Path) -> None:
    from datetime import timedelta, timezone

    offset = timezone(timedelta(hours=-5))
    result = media_provenance.extract_image_captured_at(exif_image, local_timezone=offset)
    assert result.captured_at is not None
    assert result.captured_at.tzinfo == offset
    assert result.captured_at.utcoffset() == timedelta(hours=-5)


def pytest_datetime(*args: int):  # noqa: ANN201 -- small local helper, not a pytest hook
    from datetime import datetime

    return datetime(*args, tzinfo=UTC)


# -- Content hashing ----------------------------------------------------------


def test_compute_content_sha256_is_deterministic_and_content_sensitive(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"identical content")
    b.write_bytes(b"identical content")
    different = tmp_path / "c.bin"
    different.write_bytes(b"different content")

    hash_a = media_provenance.compute_content_sha256(a)
    hash_b = media_provenance.compute_content_sha256(b)
    hash_c = media_provenance.compute_content_sha256(different)

    assert hash_a == hash_b
    assert hash_a != hash_c
    assert len(hash_a) == 64


def test_compute_content_sha256_streams_in_bounded_chunks_for_a_larger_file(tmp_path: Path) -> None:
    path = tmp_path / "bigger.bin"
    path.write_bytes(b"x" * 5000)
    assert media_provenance.compute_content_sha256(path, chunk_size=1024) == media_provenance.compute_content_sha256(
        path, chunk_size=8192
    )


def test_compute_content_sha256_returns_none_for_a_missing_file(tmp_path: Path) -> None:
    assert media_provenance.compute_content_sha256(tmp_path / "missing.bin") is None


# -- Video probing (real ffprobe; skipped if genuinely unavailable) ---------


def _has_real_ffmpeg_suite() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.fixture
def tiny_video_clip(tmp_path: Path) -> Path:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    path = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        timeout=30,
        capture_output=True,
    )
    return path


def test_probe_video_metadata_reads_real_duration_and_resolution(tiny_video_clip: Path) -> None:
    result = media_provenance.probe_video_metadata(tiny_video_clip)
    assert result is not None
    assert result.duration_seconds == pytest.approx(2.0, abs=0.2)
    assert result.width == 320
    assert result.height == 240
    assert result.codec_name == "h264"


def test_probe_video_metadata_returns_none_for_a_missing_file(tmp_path: Path) -> None:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    assert media_provenance.probe_video_metadata(tmp_path / "missing.mp4") is None


def test_probe_video_metadata_returns_none_when_ffprobe_binary_is_wrong() -> None:
    result = media_provenance.probe_video_metadata(
        Path(__file__), ffprobe_binary="definitely-not-a-real-binary"
    )
    assert result is None


def test_is_ffprobe_available_matches_real_environment() -> None:
    assert media_provenance.is_ffprobe_available() == _has_real_ffmpeg_suite()


# -- Media-kind classification -----------------------------------------------


@pytest.mark.parametrize(
    "extension,expected",
    [
        (".jpg", "image"),
        (".JPG", "image"),
        (".png", "image"),
        (".webp", "image"),
        (".mp4", "video"),
        (".MOV", "video"),
        (".mkv", "video"),
        (".avi", "video"),
    ],
)
def test_media_kind_for_extension(extension: str, expected: str) -> None:
    assert media_provenance.media_kind_for_extension(extension) == expected
