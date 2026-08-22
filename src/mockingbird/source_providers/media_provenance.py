"""Bounded, honest provenance extraction for imported (offline/camera-trap)
media -- v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.9
Camera-trap / media ingest", "II.11 Imported timestamps", "II.12 Duplicate
protection"). Every function here is a small, independent, side-effect-free
read of a single already-downloaded local file; none of them create
product records, none of them decode more than the header/metadata a
library needs, and none of them assume a fact this codebase cannot
actually support.

## Why this exists as its own module

`folder_import_preview.py` and the folder-import creation path in
`product_repository.py` previously extracted zero metadata beyond a raw
`os.stat()` (size, filesystem mtime) -- no EXIF capture timestamp, no
video duration, no content hash, despite `MediaAssetModel` already having
columns for two of these (`captured_at`, `content_sha256`) that nothing
populated for an imported file (see docs/todays-coverage-truth-contract.md
and the localization-attribution migration that added `content_sha256`
for a completely different, unrelated purpose). This module is the small,
bounded fix -- not a general media-processing pipeline.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Literal

from PIL import ExifTags, Image, UnidentifiedImageError

# Bounded read: a content hash must cover the whole file for a meaningful
# duplicate check, but it is streamed in fixed chunks -- see "II.25
# Performance" (no unbounded byte loading in analytics/import code).
_HASH_CHUNK_BYTES = 1_048_576

# EXIF DateTimeOriginal/DateTimeDigitized/DateTime tag ids, in the order a
# camera-trap image is most likely to carry a trustworthy capture moment.
# `DateTimeOriginal` (in the Exif sub-IFD) is the moment the shutter
# opened; `DateTime` (in the base IFD) is often only "last modified" by
# editing software, so it is tried last, purely as a fallback.
_EXIF_SUB_IFD_TAG = 0x8769  # "ExifOffset" / Exif IFD pointer
_TAG_DATETIME_ORIGINAL = 36867
_TAG_DATETIME_DIGITIZED = 36868
_TAG_DATETIME_BASE = 306

_FFPROBE_TIMEOUT_SECONDS = 10.0
_MAX_FFPROBE_OUTPUT_BYTES = 262_144


@dataclass(frozen=True)
class ImageCaptureMetadata:
    """EXIF-derived capture provenance for one image file.

    `captured_at` is `None` whenever no usable EXIF timestamp tag exists
    at all -- an honest "not known," never a fabricated fallback to the
    filesystem's own mtime or the import moment (those remain separately
    available as `modified_at`/`imported_at`, never collapsed into this
    field -- see "II.11 Imported timestamps").

    `timezone_assumed` is `True` whenever `captured_at` is populated: EXIF
    `DateTimeOriginal` carries no timezone of its own (see "II.11...
    Timezone uncertainty must be represented honestly" -- this codebase
    does not silently assume UTC). `captured_at` is constructed by
    attaching the caller-supplied `local_timezone` (this host's own
    resolved local zone, the same "local" this codebase already uses for
    every other local-time computation -- see `resolve_host_local_
    timezone` in `mockingbird.time_utils`) to the naive EXIF wall-clock
    string; a caller/UI displaying this fact should disclose that
    assumption rather than presenting it as equally certain as a live-
    captured, camera-node-timestamped frame.
    """

    captured_at: datetime | None
    timezone_assumed: bool


def extract_image_captured_at(path: Path, *, local_timezone: tzinfo) -> ImageCaptureMetadata:
    """Read the EXIF capture timestamp from one image file, if any.

    Never raises: a file with no EXIF block, a corrupt/truncated header,
    or a format PIL cannot identify all produce `ImageCaptureMetadata(None,
    False)` -- exactly as honest as "we do not know," matching this
    codebase's "no fabricated confidence for legacy/uncertain records"
    discipline. Only opens the file's header/metadata (`Image.open` is
    lazy; this never calls `.load()`), so this stays cheap even for a
    large image.
    """

    try:
        with Image.open(path) as image:
            exif = image.getexif()
            raw_value = _first_exif_datetime(exif)
    except (UnidentifiedImageError, OSError, ValueError):
        return ImageCaptureMetadata(captured_at=None, timezone_assumed=False)

    if raw_value is None:
        return ImageCaptureMetadata(captured_at=None, timezone_assumed=False)

    parsed = _parse_exif_datetime(raw_value)
    if parsed is None:
        return ImageCaptureMetadata(captured_at=None, timezone_assumed=False)

    return ImageCaptureMetadata(captured_at=parsed.replace(tzinfo=local_timezone), timezone_assumed=True)


def _first_exif_datetime(exif) -> str | None:  # noqa: ANN001 -- PIL.Image.Exif has no public type
    sub_ifd = exif.get_ifd(_EXIF_SUB_IFD_TAG) if exif else {}
    for source, tag in (
        (sub_ifd, _TAG_DATETIME_ORIGINAL),
        (sub_ifd, _TAG_DATETIME_DIGITIZED),
        (exif, _TAG_DATETIME_BASE),
    ):
        value = source.get(tag) if source else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_exif_datetime(raw_value: str) -> datetime | None:
    # The EXIF spec's own fixed format: "YYYY:MM:DD HH:MM:SS", no timezone.
    try:
        return datetime.strptime(raw_value, "%Y:%m:%d %H:%M:%S")  # noqa: DTZ007 -- intentionally naive; see caller
    except ValueError:
        return None


@dataclass(frozen=True)
class VideoProbeResult:
    """ffprobe-derived provenance for one video file -- informational
    only; never wired into `MonitoringExposureIntervalModel`/coverage math
    (see "II.10 Offline vs monitoring coverage" -- importing a clip must
    never imply continuous monitoring; that boundary is enforced by
    omission at the call site, not by this module)."""

    duration_seconds: float | None
    width: int | None
    height: int | None
    codec_name: str | None


def is_ffprobe_available(ffprobe_binary: str = "ffprobe") -> bool:
    return shutil.which(ffprobe_binary) is not None


def probe_video_metadata(
    path: Path,
    *,
    ffprobe_binary: str = "ffprobe",
    timeout_seconds: float = _FFPROBE_TIMEOUT_SECONDS,
) -> VideoProbeResult | None:
    """Bounded, read-only `ffprobe` metadata probe -- reuses the same
    ffmpeg-suite dependency `mockingbird.playback.rtsp_bridge` already
    requires (see `is_ffmpeg_available`), not a new one. Returns `None`
    (never raises) when ffprobe is unavailable, the file is not a video
    ffprobe can parse, or the process times out -- every one of these is
    an ordinary, expected outcome for camera-trap media of unknown
    provenance, not a product error.
    """

    if not is_ffprobe_available(ffprobe_binary):
        return None
    try:
        completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell, local file path only
            [
                ffprobe_binary,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout:
        return None

    try:
        payload = json.loads(completed.stdout[:_MAX_FFPROBE_OUTPUT_BYTES])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    duration_seconds = _safe_float((payload.get("format") or {}).get("duration"))
    video_stream = next(
        (
            stream
            for stream in payload.get("streams") or []
            if stream.get("codec_type") == "video"
        ),
        None,
    )
    return VideoProbeResult(
        duration_seconds=duration_seconds,
        width=_safe_int(video_stream.get("width")) if video_stream else None,
        height=_safe_int(video_stream.get("height")) if video_stream else None,
        codec_name=(video_stream.get("codec_name") if video_stream else None),
    )


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def compute_content_sha256(path: Path, *, chunk_size: int = _HASH_CHUNK_BYTES) -> str | None:
    """Stream-hash one local file -- bounded memory regardless of file
    size (see "II.25 Performance"). Returns `None` (never raises) only
    when the file genuinely cannot be read; a caller treats that as "no
    duplicate check possible for this file," never a fabricated hash."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


MediaKind = Literal["image", "video"]

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


def media_kind_for_extension(extension: str) -> MediaKind:
    return "video" if extension.lower() in VIDEO_EXTENSIONS else "image"


__all__ = [
    "VIDEO_EXTENSIONS",
    "ImageCaptureMetadata",
    "MediaKind",
    "VideoProbeResult",
    "compute_content_sha256",
    "extract_image_captured_at",
    "is_ffprobe_available",
    "media_kind_for_extension",
    "probe_video_metadata",
]
