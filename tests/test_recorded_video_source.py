"""Tier 1 tests for `mockingbird.observation.recorded_video_source` --
Offline / Recorded Observation Ingest v1. Real ffmpeg-generated synthetic
clips only (skipped if genuinely unavailable in this environment); no
network access, no product repository, no detector.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation import recorded_video_source as source
from mockingbird.observation.contracts import FramePacket


def _has_real_ffmpeg_suite() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _generate_clip(path: Path, *, duration_seconds: float, color: str = "blue", size: str = "64x64") -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s={size}:d={duration_seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True, timeout=30, capture_output=True,
    )


@pytest.fixture
def four_second_clip(tmp_path: Path) -> Path:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    path = tmp_path / "four-seconds.mp4"
    _generate_clip(path, duration_seconds=4.0)
    return path


def test_sample_recorded_video_frames_decodes_at_the_deterministic_cadence(four_second_clip: Path) -> None:
    result = source.sample_recorded_video_frames(four_second_clip, sample_fps=2.0)
    # A real ~4s clip sampled at 2fps yields ~8 frames -- ffmpeg's own fps
    # filter rounding can land one frame either side of the exact count.
    assert 7 <= result.frame_count <= 9
    assert result.truncated is False
    assert result.source_duration_seconds == pytest.approx(4.0, abs=0.3)
    assert result.source_width == 64
    assert result.source_height == 64
    # Deterministic, evenly-spaced, monotonically increasing offsets --
    # never read from ffmpeg's own re-encoded timestamps.
    offsets = [frame.source_offset_ms for frame in result.frames]
    assert offsets == sorted(offsets)
    assert offsets[0] == 0
    for index, offset in enumerate(offsets):
        assert offset == round(index * 1000 / 2.0)
    # Every sampled frame is a real, independently decodable JPEG.
    for frame in result.frames:
        assert frame.payload.startswith(b"\xff\xd8")
        assert frame.payload.endswith(b"\xff\xd9")


def test_sample_recorded_video_frames_is_deterministic_across_reruns(four_second_clip: Path) -> None:
    first = source.sample_recorded_video_frames(four_second_clip, sample_fps=2.0)
    second = source.sample_recorded_video_frames(four_second_clip, sample_fps=2.0)
    assert [frame.source_offset_ms for frame in first.frames] == [
        frame.source_offset_ms for frame in second.frames
    ]
    assert len(first.frames) == len(second.frames)


def test_sample_recorded_video_frames_honors_a_bounded_max_frames_cap(four_second_clip: Path) -> None:
    result = source.sample_recorded_video_frames(four_second_clip, sample_fps=2.0, max_frames=3)
    assert result.frame_count == 3
    assert result.truncated is True


def test_sample_recorded_video_frames_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(source.RecordedVideoDecodeError, match="media_file_invalid"):
        source.sample_recorded_video_frames(tmp_path / "missing.mp4")


def test_sample_recorded_video_frames_rejects_a_malformed_file(tmp_path: Path) -> None:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    bogus = tmp_path / "not-a-real-video.mp4"
    bogus.write_bytes(b"this is not a video file, just plain bytes" * 10)
    with pytest.raises(source.RecordedVideoDecodeError, match="media_file_invalid"):
        source.sample_recorded_video_frames(bogus)


def test_sample_recorded_video_frames_rejects_an_audio_only_container(tmp_path: Path) -> None:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    audio_only = tmp_path / "audio-only.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:a", "aac", str(audio_only),
        ],
        check=True, timeout=30, capture_output=True,
    )
    with pytest.raises(source.RecordedVideoDecodeError, match="unsupported_codec"):
        source.sample_recorded_video_frames(audio_only)


def test_sample_recorded_video_frames_rejects_invalid_sampling_config(four_second_clip: Path) -> None:
    with pytest.raises(source.RecordedVideoDecodeError, match="invalid_sample_fps"):
        source.build_recorded_video_sample_command(four_second_clip, sample_fps=0, max_frames=10)
    with pytest.raises(source.RecordedVideoDecodeError, match="invalid_max_frames"):
        source.build_recorded_video_sample_command(four_second_clip, sample_fps=1, max_frames=0)


def test_frame_packets_from_recorded_video_derives_capture_time_from_a_trustworthy_anchor(
    four_second_clip: Path,
) -> None:
    sampling = source.sample_recorded_video_frames(four_second_clip, sample_fps=2.0)
    capture_start = datetime(2024, 5, 1, 14, 23, 1, tzinfo=UTC)
    packets = source.frame_packets_from_recorded_video(
        sampling,
        stream_id="stream-1",
        media_asset_id_prefix="media-video-1",
        capture_start=capture_start,
    )
    assert len(packets) == sampling.frame_count
    for packet in packets:
        assert isinstance(packet, FramePacket)
        assert packet.stream_id == "stream-1"
        assert packet.captured_at == capture_start + timedelta(milliseconds=packet.source_offset_ms)
        assert packet.media_asset_id.startswith("offline-frame:media-video-1:")
    # Deterministic, distinct frame ids in source order.
    assert [packet.frame_id for packet in packets] == sorted(packet.frame_id for packet in packets)
    assert len({packet.frame_id for packet in packets}) == len(packets)


def test_frame_packets_from_recorded_video_leaves_captured_at_unset_when_capture_start_unknown(
    four_second_clip: Path,
) -> None:
    sampling = source.sample_recorded_video_frames(four_second_clip, sample_fps=2.0)
    packets = source.frame_packets_from_recorded_video(
        sampling, stream_id="stream-1", media_asset_id_prefix="media-video-1", capture_start=None,
    )
    # Never a fabricated absolute time -- the existing frame_driven_provider
    # epoch-anchored fallback applies once these packets are actually fed
    # through the Observation Engine seam (see docs/offline-recorded-media-
    # observation-contract.md, "Frame-time semantics").
    assert all(packet.captured_at is None for packet in packets)


def test_frame_packets_from_recorded_video_threads_privacy_ignore_regions_unchanged(
    four_second_clip: Path,
) -> None:
    sampling = source.sample_recorded_video_frames(four_second_clip, sample_fps=2.0, max_frames=2)
    regions = ((0.1, 0.1, 0.4, 0.4),)
    packets = source.frame_packets_from_recorded_video(
        sampling,
        stream_id="stream-1",
        media_asset_id_prefix="media-video-1",
        capture_start=None,
        analysis_excluded_regions=regions,
    )
    assert all(packet.analysis_excluded_regions == regions for packet in packets)
