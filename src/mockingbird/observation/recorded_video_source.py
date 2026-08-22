"""Bounded, deterministic recorded-video frame decode into the Observation
Engine's own `FramePacket` seam -- Offline / Recorded Observation Ingest v1.
See docs/offline-recorded-media-observation-contract.md for the full policy
this module implements; only the mechanics live here.

This module does not detect, track, assemble, or persist anything -- it only
turns one already-imported recorded-video `MediaAsset` file into an ordered,
bounded tuple of `FramePacket`s, identical in shape to what a live Camera
Node session or the existing replay harness already produces. Everything
downstream of that (detection, tracking, Visit assembly, evidence
persistence, multi-subject handling) is the existing, unmodified Observation
Engine -- see `mockingbird.observation.offline_ingest`, the caller that
drives these packets through it.

## Sampling policy

`DEFAULT_SAMPLE_FPS` (2.0 fps, one sampled frame every 500ms) is deliberately
denser than this product's own empirically-observed live analysis cadence
(~0.85 fps / ~1.17s per frame, see the 2026-08-19 End-to-End Bird Encounter
Recall Closure v1 field report) -- not merely "1 frame/sec because it is
simple". Recorded media has no live bandwidth/hardware constraint forcing a
slower rate, so sampling denser than the already-accepted live cadence is
cheap for a bounded clip and only reduces (never increases) the risk of
missing a brief encounter. 500ms gaps between consecutive sampled frames
also sit comfortably below every temporal tolerance the shared tracker/
assembler already use to decide "same encounter" -- `maximum_unsupported_
detector_ms` (~5000ms, `frame_tracker.py`) and `merge_gap_ms` (15000ms,
`visit_episode_assembler.py`) -- so uniform, fixed-interval sampling cannot
itself manufacture an artificial gap large enough to fragment or separate
one continuous encounter. Fixed via ffmpeg's own deterministic `fps` video
filter (not frame-by-frame Python throttling), so re-decoding the same file
with the same `sample_fps` always yields the same frame count at the same
offsets -- required for `FrameDrivenObservationProvider`'s own
`deterministic_replay` capability to hold for this frame source too.

## Frame identity and timing

Each sampled frame gets a deterministic `source_offset_ms = round(index *
1000 / sample_fps)` -- never read from ffmpeg's own re-encoded output
timestamps, which are not reliably recoverable once frames are piped as a
bare MJPEG byte stream. This is exact by construction of the `fps` filter,
not an approximation.

`captured_at` is populated only when the caller supplies a trustworthy
`capture_start` (see `frame_packets_from_recorded_video`); otherwise every
`FramePacket.captured_at` is left `None`, and the existing, already-reviewed
`frame_driven_provider._with_fallback_captured_at` fallback applies exactly
as it already does for any other caller with no known capture time --
anchoring at the Unix epoch plus offset, never a fabricated "now". This
module never invents a capture time itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

from mockingbird.observation.contracts import FramePacket
from mockingbird.playback.rtsp_bridge import iter_multipart_mjpeg
from mockingbird.source_providers import media_provenance

#: Denser than the empirically-validated live analysis cadence (~0.85fps) --
#: see the module docstring's "Sampling policy" for the full justification.
DEFAULT_SAMPLE_FPS = 2.0

#: Bounded safety cap on sampled-frame count for one decode call, regardless
#: of `sample_fps`/source duration -- at the default 2fps this is 30 minutes
#: of sampled coverage, comfortably beyond "a normal short trail-camera
#: clip" (this milestone's own stated performance bar) while keeping the
#: worst case (every sampled frame is later selected as real, source-
#: resolution evidence and held in memory for the one bounded
#: `replay_frames` call -- see docs/offline-recorded-media-observation-
#: contract.md "Bounded memory, not bounded duration") from growing
#: unbounded for an unusually long recording. A pathological/oversized
#: input is truncated, never allowed to exhaust memory; truncation is
#: always disclosed (`truncated`), never silent. Configurable per call for
#: an operator who deliberately wants to process a longer recording.
DEFAULT_MAX_FRAMES = 3600

#: Bounded overall wall-clock safety valve for the decode subprocess itself,
#: independent of `DEFAULT_MAX_FRAMES` (a slow/stalled decode of a huge or
#: exotic file must still terminate deterministically).
DEFAULT_DECODE_TIMEOUT_SECONDS = 900.0

_MAX_STDERR_BYTES = 4096


class RecordedVideoDecodeError(ValueError):
    """Stable, bounded decode-failure code -- see "Error taxonomy" in
    docs/offline-recorded-media-observation-contract.md. The message is
    always one of a small fixed vocabulary (`media_file_invalid`,
    `unsupported_codec`, `decode_failed`, `ffmpeg_unavailable`), matching
    this codebase's established convention (`SavedMediaFrameDecodeError`,
    `OnvifClientError`); never a raw filesystem path or ffmpeg stderr."""


@dataclass(frozen=True)
class RecordedVideoFrame:
    """One sampled, decoded frame -- bounded JPEG bytes plus its
    deterministic source-relative identity. Never carries an absolute
    timestamp itself; that is only assigned once a caller supplies (or
    honestly omits) a `capture_start` in `frame_packets_from_recorded_video`."""

    index: int
    source_offset_ms: int
    payload: bytes


@dataclass(frozen=True)
class RecordedFrameSamplingResult:
    """The bounded, ordered decode result for one recorded-video file."""

    frames: tuple[RecordedVideoFrame, ...]
    sample_fps: float
    truncated: bool
    source_duration_seconds: float | None
    source_width: int | None
    source_height: int | None

    @property
    def frame_count(self) -> int:
        return len(self.frames)


def build_recorded_video_sample_command(
    path: Path,
    *,
    sample_fps: float,
    max_frames: int,
    ffmpeg_binary: str = "ffmpeg",
    quality: int = 5,
) -> list[str]:
    """The exact, deterministic ffmpeg invocation for bounded frame
    sampling: fixed `fps` resampling (never native/variable source frame
    timing), no audio, hard-capped output frame count, piped raw MJPEG --
    mirrors `mockingbird.playback.rtsp_bridge.build_rtsp_mjpeg_command`'s
    own flag style and quality default, adapted for a local file input
    instead of a live RTSP URL."""

    if sample_fps <= 0:
        raise RecordedVideoDecodeError("invalid_sample_fps")
    if max_frames <= 0:
        raise RecordedVideoDecodeError("invalid_max_frames")
    return [
        ffmpeg_binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-an",
        "-vf",
        f"fps={sample_fps}",
        "-frames:v",
        str(max_frames),
        "-f",
        "mjpeg",
        "-q:v",
        str(quality),
        "pipe:1",
    ]


def sample_recorded_video_frames(
    path: Path,
    *,
    sample_fps: float = DEFAULT_SAMPLE_FPS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    ffmpeg_binary: str = "ffmpeg",
    timeout_seconds: float = DEFAULT_DECODE_TIMEOUT_SECONDS,
) -> RecordedFrameSamplingResult:
    """Bounded, streaming, deterministic decode of one recorded-video file
    into sampled JPEG frames.

    Never buffers the whole source file or the whole raw decoded stream in
    memory: ffmpeg's own stdout pipe is read incrementally, one JPEG frame
    at a time (reusing `rtsp_bridge.iter_multipart_mjpeg`'s already-tested
    bounded buffer-scan, the same mechanism the live RTSP bridge already
    uses -- see the module docstring's "Frame identity and timing"). Only
    the bounded, already-sampled-down, JPEG-compressed *output* frames
    (capped at `max_frames`) are ever held as a Python list at once, never
    the source video's own raw/native-rate frame sequence.

    A pre-flight `media_provenance.probe_video_metadata` call (cheap,
    already-existing, side-effect-free) classifies an unreadable container
    as `media_file_invalid` and a readable container with no usable video
    stream as `unsupported_codec` *before* attempting the more expensive
    full decode -- see "Error taxonomy" in
    docs/offline-recorded-media-observation-contract.md. A container that
    probes fine but genuinely fails to decode (corrupt frame data, or a
    codec name ffprobe recognizes but this ffmpeg build cannot decode)
    raises `decode_failed`.
    """

    if not path.is_file():
        raise RecordedVideoDecodeError("media_file_invalid")
    if not media_provenance.is_ffprobe_available(ffprobe_binary=_ffprobe_binary_for(ffmpeg_binary)):
        raise RecordedVideoDecodeError("ffmpeg_unavailable")

    probe = media_provenance.probe_video_metadata(
        path, ffprobe_binary=_ffprobe_binary_for(ffmpeg_binary), timeout_seconds=timeout_seconds,
    )
    if probe is None:
        raise RecordedVideoDecodeError("media_file_invalid")
    if probe.width is None or probe.height is None:
        raise RecordedVideoDecodeError("unsupported_codec")

    command = build_recorded_video_sample_command(
        path, sample_fps=sample_fps, max_frames=max_frames, ffmpeg_binary=ffmpeg_binary,
    )
    try:
        process = subprocess.Popen(  # noqa: S603 -- fixed argv, no shell, local file path only
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as error:
        raise RecordedVideoDecodeError("ffmpeg_unavailable") from error

    frames: list[RecordedVideoFrame] = []
    truncated = False

    def _capture(payload: bytes) -> None:
        frames.append(
            RecordedVideoFrame(
                index=len(frames),
                source_offset_ms=round(len(frames) * 1000 / sample_fps),
                payload=payload,
            )
        )

    generator = iter_multipart_mjpeg(process, on_frame=_capture)
    try:
        for _ in generator:
            if len(frames) >= max_frames:
                truncated = True
                break
    finally:
        # Deterministic cleanup regardless of how the loop above exits:
        # closing the generator unwinds its own `finally`, which terminates
        # the ffmpeg subprocess bounded (`_stop_process`'s terminate-then-
        # kill discipline) -- never a leaked/zombie decode process, matching
        # "Failure/resume" in docs/offline-recorded-media-observation-
        # contract.md.
        generator.close()

    if not frames:
        stderr_tail = (process.stderr.read(_MAX_STDERR_BYTES) if process.stderr else b"")
        raise RecordedVideoDecodeError("decode_failed" if stderr_tail else "unsupported_codec")

    return RecordedFrameSamplingResult(
        frames=tuple(frames),
        sample_fps=sample_fps,
        truncated=truncated,
        source_duration_seconds=probe.duration_seconds,
        source_width=probe.width,
        source_height=probe.height,
    )


def frame_packets_from_recorded_video(
    sampling: RecordedFrameSamplingResult,
    *,
    stream_id: str,
    media_asset_id_prefix: str,
    capture_start: datetime | None,
    analysis_excluded_regions: tuple[tuple[float, float, float, float], ...] = (),
) -> tuple[FramePacket, ...]:
    """Project one decode result into the exact `FramePacket` shape the
    Observation Engine's `FrameDrivenObservationProvider.replay_frames`
    already accepts (see docs/offline-recorded-media-observation-contract.md
    "Common seam"). Every field mirrors the live construction site
    (`CameraNodeAnalysisSource._pop_latest`) as closely as a recorded file
    honestly can:

    - `captured_at = capture_start + source_offset_ms` when `capture_start`
      is a trustworthy fact the caller actually has (video container
      creation_time, or explicit operator-supplied capture time); `None`
      otherwise -- never a fabricated absolute time (see the module
      docstring's "Frame identity and timing").
    - `frame_id`/`media_asset_id` are synthetic, deterministic, local to
      this decode -- never a real persisted `MediaAssetModel` id (no
      MediaAsset is created for a frame merely because it was decoded;
      only frames the evidence scorer actually selects are ever persisted,
      exactly like a live session's own bounded burst evidence).
    - `analysis_excluded_regions` must be this Stream's own
      `stream_privacy_ignore_regions(stream_id)` result, threaded through
      unchanged by the caller -- the same tuple a live session passes,
      giving identical Privacy/Ignore Zone protection with no code change
      to any enforcement layer.
    """

    packets: list[FramePacket] = []
    for frame in sampling.frames:
        frame_id = f"{media_asset_id_prefix}:{frame.index:08d}"
        captured_at = (
            capture_start + timedelta(milliseconds=frame.source_offset_ms)
            if capture_start is not None
            else None
        )
        packets.append(
            FramePacket(
                stream_id=stream_id,
                media_asset_id=f"offline-frame:{frame_id}",
                captured_at=captured_at,
                frame_id=frame_id,
                source_offset_ms=frame.source_offset_ms,
                width=sampling.source_width,
                height=sampling.source_height,
                analysis_excluded_regions=analysis_excluded_regions,
                payload=frame.payload,
                frame_sequence=frame.index,
            )
        )
    return tuple(packets)


def _ffprobe_binary_for(ffmpeg_binary: str) -> str:
    """The paired `ffprobe` binary name for a given `ffmpeg` binary --
    `"ffprobe"` for the ordinary default, or the sibling path when a caller
    points at a non-default ffmpeg location (mirrors the pairing every
    other ffmpeg/ffprobe call site in this codebase already assumes)."""

    if ffmpeg_binary == "ffmpeg":
        return "ffprobe"
    path = Path(ffmpeg_binary)
    return str(path.with_name(path.name.replace("ffmpeg", "ffprobe")))


__all__ = [
    "DEFAULT_DECODE_TIMEOUT_SECONDS",
    "DEFAULT_MAX_FRAMES",
    "DEFAULT_SAMPLE_FPS",
    "RecordedFrameSamplingResult",
    "RecordedVideoDecodeError",
    "RecordedVideoFrame",
    "build_recorded_video_sample_command",
    "frame_packets_from_recorded_video",
    "sample_recorded_video_frames",
]
