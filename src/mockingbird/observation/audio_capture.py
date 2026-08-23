"""Bounded audio-input abstraction -- Acoustic / BirdNET Observation
Foundation v1. See docs/acoustic-birdnet-observation-foundation-v1-contract.md
for the full policy this module implements; only the mechanics live here.

This module does not classify, admit, or persist anything -- it only turns
either an already-imported recorded-audio `MediaAsset` file, or a live local
microphone device, into one or more bounded, canonical-format audio clip
files on disk. Everything downstream of that (BirdNET inference, candidate
admission, Visit/Event/Evidence/SpeciesSuggestion persistence) is
`mockingbird.species.birdnet_adapter` and `mockingbird.observation.
acoustic_ingest`, not this module.

## Canonical format

Every clip this module produces -- whether transcoded from an arbitrary
imported file or captured live -- is 48kHz mono 16-bit PCM WAV
(`CANONICAL_SAMPLE_RATE_HZ`/`CANONICAL_CHANNEL_COUNT`): BirdNET-Analyzer's
own native analysis rate (confirmed directly against the real bundled
model, not assumed), so no further resampling decision is deferred to the
adapter layer, and so a live-captured segment and a file-imported clip are
byte-format-identical inputs to `birdnet_adapter.run_birdnet_on_clip`.
Reuses `ffmpeg`, already a hard runtime dependency of this product's video
decode/playback path (`mockingbird.playback.rtsp_bridge`,
`mockingbird.observation.recorded_video_source`) -- no new native audio
library (PortAudio/`sounddevice`/`pyaudio`) is added.

## Bounded clip/window semantics

A file-decode call is bounded by `max_duration_seconds` (ffmpeg's own `-t`
flag truncates the *source read*, not merely the output -- never buffers an
oversized source before truncating). A live microphone capture is bounded
per-segment by ffmpeg's own `segment` muxer (`-f segment -segment_time`),
which closes and finalizes one file at a time and starts the next -- there
is no indefinite in-memory accumulation on either path; ffmpeg always
writes directly to a file, never held as a Python byte buffer of unbounded
size (audio PCM at this rate is `~96KB/s`; a 15-minute clip is comfortably
small on disk but still never accumulated as an in-process buffer here).

## Restart-safety

Neither path holds state that must survive a process restart. A file decode
is a single bounded subprocess call with no persisted intermediate state. A
live `MicrophoneCaptureSession` does not survive process restart by design
-- mirroring `LiveCameraSessionManager`'s identical, already-accepted
"current-process resource, explicit start/stop, no cross-restart resume"
contract (see "Live camera ownership" in docs/architecture.md); a caller
that wants a completed segment to survive a restart is responsible for
importing it as a `MediaAsset` promptly (the same discipline already
expected of any bounded local capture in this product).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import subprocess
import sys

from mockingbird.source_providers import media_provenance
from mockingbird.time_utils import utc_now

#: BirdNET-Analyzer's own native analysis sample rate -- verified directly
#: against the real bundled model (see docs/acoustic-birdnet-observation-
#: foundation-v1-contract.md "BirdNET runtime decision"), not assumed.
CANONICAL_SAMPLE_RATE_HZ = 48_000
CANONICAL_CHANNEL_COUNT = 1

#: Bounded safety cap on one file-decode call, regardless of the source
#: file's own duration -- comfortably beyond a normal field acoustic clip
#: while keeping worst-case decode time/disk bounded for an unusually long
#: recording. Configurable per call, mirroring `recorded_video_source.
#: DEFAULT_MAX_FRAMES`'s identical "bounded but caller-overridable" role.
DEFAULT_MAX_DURATION_SECONDS = 900.0

#: Bounded overall wall-clock safety valve for the decode subprocess itself.
DEFAULT_DECODE_TIMEOUT_SECONDS = 120.0

#: Default live-capture segment length -- a single bounded acoustic clip
#: short enough to reach BirdNET analysis promptly, long enough to comfortably
#: contain multiple BirdNET analysis windows (BirdNET's own native window is
#: 3s) without excessive per-clip overhead.
DEFAULT_SEGMENT_SECONDS = 15

_MAX_STDERR_BYTES = 4096
_PROCESS_STOP_TIMEOUT_SECONDS = 2.0


class AudioDecodeError(ValueError):
    """Stable, bounded decode-failure code -- mirrors
    `mockingbird.observation.recorded_video_source.RecordedVideoDecodeError`'s
    established convention exactly: the message is always one of a small
    fixed vocabulary (`media_file_invalid`, `unsupported_codec`,
    `decode_failed`, `ffmpeg_unavailable`), never a raw filesystem path or
    ffmpeg stderr."""


@dataclass(frozen=True)
class AudioTranscodeResult:
    """The bounded outcome of one file-decode call."""

    output_path: Path
    duration_seconds: float | None
    sample_rate_hz: int
    channel_count: int
    truncated: bool


def _ffprobe_binary_for(ffmpeg_binary: str) -> str:
    """The paired `ffprobe` binary name for a given `ffmpeg` binary --
    mirrors `recorded_video_source._ffprobe_binary_for` exactly (same
    literal-default-vs-sibling-path convention every other ffmpeg/ffprobe
    call site in this codebase already assumes)."""

    if ffmpeg_binary == "ffmpeg":
        return "ffprobe"
    path = Path(ffmpeg_binary)
    return str(path.with_name(path.name.replace("ffmpeg", "ffprobe")))


def build_audio_transcode_command(
    source_path: Path,
    destination_path: Path,
    *,
    max_duration_seconds: float,
    ffmpeg_binary: str = "ffmpeg",
) -> list[str]:
    """The exact, deterministic ffmpeg invocation transcoding an arbitrary
    supported audio file into the canonical 48kHz mono PCM16 WAV form,
    truncated (never silently dropped) at `max_duration_seconds` of
    *source* audio -- mirrors `recorded_video_source.
    build_recorded_video_sample_command`'s own deterministic-flags,
    bounded-output style."""

    if max_duration_seconds <= 0:
        raise AudioDecodeError("invalid_max_duration")
    return [
        ffmpeg_binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-t",
        str(max_duration_seconds),
        "-vn",
        "-ac",
        str(CANONICAL_CHANNEL_COUNT),
        "-ar",
        str(CANONICAL_SAMPLE_RATE_HZ),
        "-sample_fmt",
        "s16",
        "-f",
        "wav",
        "-y",
        str(destination_path),
    ]


def decode_audio_to_canonical_wav(
    source_path: Path,
    destination_path: Path,
    *,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    ffmpeg_binary: str = "ffmpeg",
    timeout_seconds: float = DEFAULT_DECODE_TIMEOUT_SECONDS,
) -> AudioTranscodeResult:
    """Bounded, deterministic transcode of one recorded-audio file into the
    canonical clip format on disk (never buffered fully in memory --
    ffmpeg writes directly to `destination_path`).

    A pre-flight `media_provenance.probe_audio_metadata` call (cheap,
    side-effect-free) classifies an unreadable container as
    `media_file_invalid` and a readable container with no usable audio
    stream as `unsupported_codec` *before* attempting the more expensive
    full transcode -- same "Error taxonomy" discipline as
    `recorded_video_source.sample_recorded_video_frames`. A container that
    probes fine but genuinely fails to transcode raises `decode_failed`.
    """

    if not source_path.is_file():
        raise AudioDecodeError("media_file_invalid")
    ffprobe_binary = _ffprobe_binary_for(ffmpeg_binary)
    if not media_provenance.is_ffprobe_available(ffprobe_binary=ffprobe_binary):
        raise AudioDecodeError("ffmpeg_unavailable")

    probe = media_provenance.probe_audio_metadata(
        source_path, ffprobe_binary=ffprobe_binary, timeout_seconds=timeout_seconds,
    )
    if probe is None:
        raise AudioDecodeError("media_file_invalid")
    if probe.sample_rate_hz is None:
        raise AudioDecodeError("unsupported_codec")

    command = build_audio_transcode_command(
        source_path,
        destination_path,
        max_duration_seconds=max_duration_seconds,
        ffmpeg_binary=ffmpeg_binary,
    )
    try:
        completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell, local file paths only
            command,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as error:
        raise AudioDecodeError("ffmpeg_unavailable") from error
    except subprocess.TimeoutExpired as error:
        raise AudioDecodeError("decode_failed") from error

    if completed.returncode != 0 or not destination_path.is_file():
        raise AudioDecodeError("decode_failed")

    output_probe = media_provenance.probe_audio_metadata(
        destination_path, ffprobe_binary=ffprobe_binary, timeout_seconds=timeout_seconds,
    )
    output_duration = output_probe.duration_seconds if output_probe is not None else None
    truncated = bool(
        probe.duration_seconds is not None and probe.duration_seconds > max_duration_seconds
    )
    return AudioTranscodeResult(
        output_path=destination_path,
        duration_seconds=output_duration,
        sample_rate_hz=CANONICAL_SAMPLE_RATE_HZ,
        channel_count=CANONICAL_CHANNEL_COUNT,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Live local-microphone capture. Deliberately reuses ffmpeg (already a hard
# runtime dependency) rather than adding a native PortAudio-backed Python
# dependency (`sounddevice`/`pyaudio`) -- the same architectural choice this
# product already made for every other capture path (RTSP, Windows
# DirectShow, recorded-video decode). Device selection is explicit adapter
# configuration (see the "Audio-aware boundary" in docs/durable-camera-
# monitor-lifecycle-design.md: "device selection and credentials remain
# adapter configuration, not core policy fields"), not a core policy field.
# ---------------------------------------------------------------------------


def is_ffmpeg_available(ffmpeg_binary: str = "ffmpeg") -> bool:
    return shutil.which(ffmpeg_binary) is not None


def build_microphone_capture_command(
    device: str,
    output_directory: Path,
    *,
    segment_seconds: int = DEFAULT_SEGMENT_SECONDS,
    ffmpeg_binary: str = "ffmpeg",
    platform_name: str | None = None,
) -> list[str]:
    """The exact, deterministic ffmpeg invocation for bounded, rolling
    microphone capture -- one finalized canonical-format WAV segment every
    `segment_seconds`, via ffmpeg's own `segment` muxer (bounded by
    construction: ffmpeg itself closes and finalizes one file before
    starting the next, never an unbounded single recording).

    `device` is opaque adapter configuration (an explicit PulseAudio/ALSA
    source name on Linux, or a DirectShow device name on Windows) -- this
    function does not validate or enumerate real devices; that is a
    deployment-time operator concern, mirroring how `windows_camera_
    bridge.py` treats a camera device name today.

    `platform_name` is injectable for deterministic, hardware-free testing
    -- mirrors `windows_camera_bridge.py`'s identical
    `platform_name: str = sys.platform` convention -- never read from the
    real `sys.platform` inside a test.
    """

    if segment_seconds <= 0:
        raise AudioDecodeError("invalid_segment_seconds")
    host_platform = platform_name or sys.platform
    if host_platform.startswith("win"):
        input_args = ["-f", "dshow", "-i", f"audio={device}"]
    else:
        input_args = ["-f", "pulse", "-i", device]
    output_pattern = str(output_directory / "segment-%08d.wav")
    return [
        ffmpeg_binary,
        "-hide_banner",
        "-loglevel",
        "error",
        *input_args,
        "-ac",
        str(CANONICAL_CHANNEL_COUNT),
        "-ar",
        str(CANONICAL_SAMPLE_RATE_HZ),
        "-sample_fmt",
        "s16",
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        "-reset_timestamps",
        "1",
        "-strftime",
        "0",
        output_pattern,
    ]


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate-then-kill discipline, mirroring
    `mockingbird.playback.rtsp_bridge._stop_process` exactly -- deterministic
    subprocess cleanup, never a leaked/zombie capture process."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=_PROCESS_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_PROCESS_STOP_TIMEOUT_SECONDS)


@dataclass(frozen=True)
class CapturedSegment:
    """One finalized live-capture segment, with real temporal provenance --
    Acoustic Runtime & Quality v1 (Phase F: "timestamped segment identity").
    `poll_new_finalized_segments` (unchanged) returns bare `Path`s only;
    this is the richer shape the automatic runtime consumes.

    `sequence_index` is parsed directly from ffmpeg's own `segment-%08d.wav`
    filename -- the segment muxer's own ground truth, not a separately
    tracked Python counter that could desync from what actually landed on
    disk. `started_at`/`ended_at` are derived as `session_started_at +
    sequence_index * segment_seconds` (nominal, assuming ffmpeg's segment
    muxer produces exactly back-to-back segments with no gap or drift) --
    disclosed, not silently treated as lab-verified: this codebase has no
    physical microphone to confirm real segment-boundary timing against a
    long real capture. A future milestone with real microphone hardware
    should verify actual segment timing against a real, long-running ffmpeg
    process and check for accumulated drift."""

    path: Path
    sequence_index: int
    started_at: datetime
    ended_at: datetime


def _segment_sequence_index(path: Path) -> int:
    """Parse the zero-padded sequence number ffmpeg's own `segment` muxer
    embeds in `segment-%08d.wav` -- the muxer's own ground truth. Returns 0
    for any name that does not match the expected pattern (defensive only;
    every segment this module itself writes always matches)."""

    stem = path.stem
    _, _, suffix = stem.rpartition("-")
    return int(suffix) if suffix.isdigit() else 0


class MicrophoneCaptureSession:
    """One bounded, explicit-start/stop, current-process-only live capture.

    Does not survive process restart (by design -- see the module
    docstring's "Restart-safety"). Never starts implicitly: a caller must
    construct and `.start()` this explicitly, mirroring `LiveCameraSession
    Manager`'s identical "no browser-close/status-poll implicit policy"
    discipline. `.completed_segments()` yields each rolling segment file
    only after ffmpeg has actually finalized it (detected by the *next*
    segment file appearing, or by `.stop()` finalizing the last one) --
    never a partially-written file.
    """

    def __init__(
        self,
        *,
        device: str,
        output_directory: Path,
        segment_seconds: int = DEFAULT_SEGMENT_SECONDS,
        ffmpeg_binary: str = "ffmpeg",
        platform_name: str | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._device = device
        self._output_directory = output_directory
        self._segment_seconds = segment_seconds
        self._ffmpeg_binary = ffmpeg_binary
        self._platform_name = platform_name
        self._clock = clock
        self._process: subprocess.Popen[bytes] | None = None
        self._known_segments: set[Path] = set()
        #: Real wall-clock instant `.start()` began capture -- the anchor
        #: `CapturedSegment.started_at` is derived from (see its own
        #: docstring's disclosed "nominal, assumes gapless segments" caveat).
        #: Injectable via `clock` for deterministic tests, mirroring
        #: `platform_name`'s identical "never read the real ambient value
        #: inside a test" convention.
        self._session_started_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        if self.is_running:
            return
        if not is_ffmpeg_available(self._ffmpeg_binary):
            raise AudioDecodeError("ffmpeg_unavailable")
        self._output_directory.mkdir(parents=True, exist_ok=True)
        command = build_microphone_capture_command(
            self._device,
            self._output_directory,
            segment_seconds=self._segment_seconds,
            ffmpeg_binary=self._ffmpeg_binary,
            platform_name=self._platform_name,
        )
        try:
            self._process = subprocess.Popen(  # noqa: S603 -- fixed argv, no shell
                command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError as error:
            raise AudioDecodeError("ffmpeg_unavailable") from error
        self._session_started_at = self._clock()

    def stop(self) -> None:
        if self._process is not None:
            _stop_process(self._process)
            self._process = None

    def poll_new_finalized_segments(self) -> list[Path]:
        """Side-effect-free-ish (advances only this session's own
        already-seen-segment bookkeeping): returns every segment file that
        is now finalized (ffmpeg has moved on to writing a later segment,
        or the process has exited) and has not been returned before.
        Bounded: never returns a segment still being actively written."""

        return [segment.path for segment in self.poll_new_finalized_segments_with_timing()]

    def poll_new_finalized_segments_with_timing(self) -> list[CapturedSegment]:
        """Identical finalization/bookkeeping semantics to
        `poll_new_finalized_segments` (this method IS its implementation --
        that method just strips the timing back off), but returns each
        segment's derived temporal identity too. This is the method
        `acoustic_runtime` uses."""

        if not self._output_directory.is_dir():
            return []
        all_segments = sorted(self._output_directory.glob("segment-*.wav"))
        if self.is_running and all_segments:
            # The lexicographically-last segment may still be the one
            # ffmpeg is actively writing -- never return it as finalized
            # while the process is still running.
            all_segments = all_segments[:-1]
        newly_finalized = [path for path in all_segments if path not in self._known_segments]
        self._known_segments.update(newly_finalized)
        session_started_at = self._session_started_at or self._clock()
        return [
            CapturedSegment(
                path=path,
                sequence_index=(index := _segment_sequence_index(path)),
                started_at=session_started_at + timedelta(seconds=index * self._segment_seconds),
                ended_at=session_started_at
                + timedelta(seconds=(index + 1) * self._segment_seconds),
            )
            for path in newly_finalized
        ]


class MicrophoneSessionManager:
    """A bounded, process-local registry of at most one
    `MicrophoneCaptureSession` per Stream -- mirrors `LiveCameraSession
    Manager`'s identical "one camera subprocess/session per Stream"
    ownership shape (see "Live camera ownership" in docs/architecture.md),
    scoped to audio capture. Does not survive process restart (see the
    module docstring's "Restart-safety"); the app constructs exactly one of
    these lazily, the same established `get_live_camera_session_manager`
    pattern `api/main.py` already uses for its video counterpart.

    Deliberately does not itself import captured segments as MediaAssets or
    trigger BirdNET analysis -- capture and analysis remain two separate,
    explicit actions (mirroring the file-import path's own "explicit
    Analyze imported media action" discipline); a caller drains
    `poll_new_finalized_segments` and decides what to do with each file.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, MicrophoneCaptureSession] = {}

    def is_running(self, stream_id: str) -> bool:
        session = self._sessions.get(stream_id)
        return session is not None and session.is_running

    def start(
        self,
        stream_id: str,
        *,
        device: str,
        output_directory: Path,
        segment_seconds: int = DEFAULT_SEGMENT_SECONDS,
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:
        existing = self._sessions.get(stream_id)
        if existing is not None and existing.is_running:
            return
        session = MicrophoneCaptureSession(
            device=device, output_directory=output_directory,
            segment_seconds=segment_seconds, ffmpeg_binary=ffmpeg_binary,
        )
        session.start()
        self._sessions[stream_id] = session

    def stop(self, stream_id: str) -> None:
        session = self._sessions.get(stream_id)
        if session is not None:
            session.stop()

    def poll_new_finalized_segments(self, stream_id: str) -> list[Path]:
        session = self._sessions.get(stream_id)
        if session is None:
            return []
        return session.poll_new_finalized_segments()

    def poll_new_finalized_segments_with_timing(self, stream_id: str) -> list[CapturedSegment]:
        session = self._sessions.get(stream_id)
        if session is None:
            return []
        return session.poll_new_finalized_segments_with_timing()

    def running_stream_ids(self) -> list[str]:
        """Every Stream this process currently has an active capture session
        for -- `acoustic_runtime.AcousticRuntimeService` polls exactly this
        set each tick, never a full Stream table scan."""

        return [
            stream_id
            for stream_id, session in self._sessions.items()
            if session.is_running
        ]

    def stop_all(self) -> None:
        """Bounded application-shutdown cleanup -- mirrors
        `LiveCameraSessionManager`'s identical "graceful application
        shutdown" responsibility for its own sessions."""

        for session in self._sessions.values():
            session.stop()


__all__ = [
    "CANONICAL_CHANNEL_COUNT",
    "CANONICAL_SAMPLE_RATE_HZ",
    "DEFAULT_DECODE_TIMEOUT_SECONDS",
    "DEFAULT_MAX_DURATION_SECONDS",
    "DEFAULT_SEGMENT_SECONDS",
    "AudioDecodeError",
    "AudioTranscodeResult",
    "CapturedSegment",
    "MicrophoneCaptureSession",
    "MicrophoneSessionManager",
    "build_audio_transcode_command",
    "build_microphone_capture_command",
    "decode_audio_to_canonical_wav",
    "is_ffmpeg_available",
]
