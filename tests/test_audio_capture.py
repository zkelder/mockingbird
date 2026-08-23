"""Acoustic / BirdNET Observation Foundation v1: bounded audio-input
mechanics -- decode, command construction, and the live-microphone
capture-session building blocks. See docs/acoustic-birdnet-observation-
foundation-v1-contract.md.

Real ffmpeg-decoded synthetic clips throughout (skipped, never faked, when
genuinely unavailable) -- mirrors the established convention in
`tests/test_offline_ingest.py`/`tests/test_recorded_video_source.py`.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation import audio_capture


def _has_real_ffmpeg_suite() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


requires_ffmpeg = pytest.mark.skipif(
    not _has_real_ffmpeg_suite(), reason="real ffmpeg/ffprobe not available on this host"
)


def _generate_tone(path: Path, *, duration_seconds: float, sample_rate: int = 44100) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration_seconds}:sample_rate={sample_rate}",
            "-ac", "2", str(path),
        ],
        check=True, timeout=30, capture_output=True,
    )


@requires_ffmpeg
class TestDecodeAudioToCanonicalWav:
    def test_decodes_real_audio_to_canonical_format(self, tmp_path: Path) -> None:
        source = tmp_path / "source.wav"
        _generate_tone(source, duration_seconds=3.0, sample_rate=44100)
        destination = tmp_path / "canonical.wav"

        result = audio_capture.decode_audio_to_canonical_wav(source, destination)

        assert result.output_path == destination
        assert destination.is_file()
        assert result.sample_rate_hz == audio_capture.CANONICAL_SAMPLE_RATE_HZ
        assert result.channel_count == audio_capture.CANONICAL_CHANNEL_COUNT
        assert result.duration_seconds is not None
        assert result.duration_seconds == pytest.approx(3.0, abs=0.2)
        assert result.truncated is False

    def test_truncates_and_discloses_when_source_exceeds_max_duration(self, tmp_path: Path) -> None:
        source = tmp_path / "source.wav"
        _generate_tone(source, duration_seconds=5.0)
        destination = tmp_path / "canonical.wav"

        result = audio_capture.decode_audio_to_canonical_wav(
            source, destination, max_duration_seconds=2.0,
        )

        assert result.truncated is True
        assert result.duration_seconds is not None
        assert result.duration_seconds == pytest.approx(2.0, abs=0.2)

    def test_missing_source_file_raises_media_file_invalid(self, tmp_path: Path) -> None:
        with pytest.raises(audio_capture.AudioDecodeError, match="media_file_invalid"):
            audio_capture.decode_audio_to_canonical_wav(
                tmp_path / "does-not-exist.wav", tmp_path / "out.wav",
            )

    def test_non_audio_file_raises_media_file_invalid(self, tmp_path: Path) -> None:
        source = tmp_path / "not-audio.wav"
        source.write_bytes(b"this is not a real audio file, just plain bytes")

        with pytest.raises(audio_capture.AudioDecodeError):
            audio_capture.decode_audio_to_canonical_wav(source, tmp_path / "out.wav")

    def test_invalid_max_duration_rejected(self, tmp_path: Path) -> None:
        source = tmp_path / "source.wav"
        _generate_tone(source, duration_seconds=1.0)
        with pytest.raises(audio_capture.AudioDecodeError, match="invalid_max_duration"):
            audio_capture.decode_audio_to_canonical_wav(
                source, tmp_path / "out.wav", max_duration_seconds=0,
            )


class TestFfmpegUnavailable:
    def test_missing_ffmpeg_binary_raises_ffmpeg_unavailable(self, tmp_path: Path) -> None:
        source = tmp_path / "source.wav"
        source.write_bytes(b"irrelevant -- ffprobe check fails first")
        with pytest.raises(audio_capture.AudioDecodeError, match="ffmpeg_unavailable"):
            audio_capture.decode_audio_to_canonical_wav(
                source, tmp_path / "out.wav", ffmpeg_binary="definitely-not-a-real-ffmpeg-binary",
            )


class TestBuildMicrophoneCaptureCommand:
    def test_linux_uses_pulse_input(self, tmp_path: Path) -> None:
        command = audio_capture.build_microphone_capture_command(
            "default", tmp_path, platform_name="linux",
        )
        assert "-f" in command
        pulse_index = command.index("pulse")
        assert command[pulse_index - 1] == "-f"
        assert command[pulse_index + 1] == "-i"
        assert command[pulse_index + 2] == "default"

    def test_windows_uses_dshow_input(self, tmp_path: Path) -> None:
        command = audio_capture.build_microphone_capture_command(
            "Microphone (Realtek)", tmp_path, platform_name="win32",
        )
        dshow_index = command.index("dshow")
        assert command[dshow_index - 1] == "-f"
        assert command[dshow_index + 1] == "-i"
        assert command[dshow_index + 2] == "audio=Microphone (Realtek)"

    def test_uses_canonical_format_and_bounded_segmenting(self, tmp_path: Path) -> None:
        command = audio_capture.build_microphone_capture_command(
            "default", tmp_path, segment_seconds=30, platform_name="linux",
        )
        assert str(audio_capture.CANONICAL_SAMPLE_RATE_HZ) in command
        assert "segment" in command
        assert "30" in command
        assert str(tmp_path / "segment-%08d.wav") in command

    def test_invalid_segment_seconds_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(audio_capture.AudioDecodeError, match="invalid_segment_seconds"):
            audio_capture.build_microphone_capture_command(
                "default", tmp_path, segment_seconds=0, platform_name="linux",
            )


class _FakeCaptureProcess:
    """A minimal stand-in for `subprocess.Popen` -- this codebase's
    established "inject a fake for the OS-process-adjacent seam" convention
    (mirrors `tests/test_camera_node.py`'s fake camera/process patterns),
    used here so `MicrophoneCaptureSession` unit tests never depend on a
    real audio input device (none exists in this sandbox)."""

    def __init__(self) -> None:
        self._returncode: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = 0

    def kill(self) -> None:
        self.killed = True
        self._returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        return self._returncode if self._returncode is not None else 0


class TestMicrophoneCaptureSession:
    def test_start_raises_when_ffmpeg_unavailable(self, tmp_path: Path) -> None:
        session = audio_capture.MicrophoneCaptureSession(
            device="default", output_directory=tmp_path / "capture",
            ffmpeg_binary="definitely-not-a-real-ffmpeg-binary",
        )
        with pytest.raises(audio_capture.AudioDecodeError, match="ffmpeg_unavailable"):
            session.start()
        assert session.is_running is False

    def test_start_is_idempotent_while_running(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_process = _FakeCaptureProcess()
        popen_calls = []

        def fake_popen(command, **kwargs):
            popen_calls.append(command)
            return fake_process

        monkeypatch.setattr(audio_capture, "is_ffmpeg_available", lambda binary="ffmpeg": True)
        monkeypatch.setattr(audio_capture.subprocess, "Popen", fake_popen)

        session = audio_capture.MicrophoneCaptureSession(device="default", output_directory=tmp_path / "capture")
        session.start()
        session.start()  # second call while "running" must not spawn a second process
        assert len(popen_calls) == 1
        assert session.is_running is True

    def test_stop_terminates_the_process(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_process = _FakeCaptureProcess()
        monkeypatch.setattr(audio_capture, "is_ffmpeg_available", lambda binary="ffmpeg": True)
        monkeypatch.setattr(audio_capture.subprocess, "Popen", lambda command, **kwargs: fake_process)

        session = audio_capture.MicrophoneCaptureSession(device="default", output_directory=tmp_path / "capture")
        session.start()
        session.stop()
        assert fake_process.terminated is True
        assert session.is_running is False

    def test_poll_new_finalized_segments_excludes_the_actively_written_one(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "capture"
        output_dir.mkdir()
        (output_dir / "segment-00000000.wav").write_bytes(b"finalized-1")
        (output_dir / "segment-00000001.wav").write_bytes(b"finalized-2")
        (output_dir / "segment-00000002.wav").write_bytes(b"still-being-written")

        session = audio_capture.MicrophoneCaptureSession(device="default", output_directory=output_dir)
        session._process = _FakeCaptureProcess()  # simulate "running" without a real subprocess

        finalized = session.poll_new_finalized_segments()
        assert [path.name for path in finalized] == ["segment-00000000.wav", "segment-00000001.wav"]

        # A second poll with no new segments returns nothing -- already seen.
        assert session.poll_new_finalized_segments() == []

    def test_poll_after_process_exit_returns_the_final_segment_too(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "capture"
        output_dir.mkdir()
        (output_dir / "segment-00000000.wav").write_bytes(b"only-segment")

        session = audio_capture.MicrophoneCaptureSession(device="default", output_directory=output_dir)
        # No process at all (never started, or already stopped) -- not running.
        assert session.is_running is False
        finalized = session.poll_new_finalized_segments()
        assert [path.name for path in finalized] == ["segment-00000000.wav"]


class TestCapturedSegmentTiming:
    """Acoustic Runtime & Quality v1, Phase F: deterministic segment
    timestamp identity. `sequence_index` is parsed from ffmpeg's own
    filename (the muxer's own ground truth); `started_at`/`ended_at` are
    derived as `session_started_at + sequence_index * segment_seconds` --
    proven deterministic here via an injected clock, never the real
    ambient clock inside a test."""

    def test_timing_is_derived_from_session_start_plus_sequence_index(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "capture"
        output_dir.mkdir()
        (output_dir / "segment-00000000.wav").write_bytes(b"seg-0")
        (output_dir / "segment-00000001.wav").write_bytes(b"seg-1")
        (output_dir / "segment-00000002.wav").write_bytes(b"still-writing")

        fixed_start = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
        session = audio_capture.MicrophoneCaptureSession(
            device="default", output_directory=output_dir, segment_seconds=15,
            clock=lambda: fixed_start,
        )
        session._process = _FakeCaptureProcess()  # simulate "running" without a real subprocess
        session._session_started_at = fixed_start  # mirrors what .start() would have set

        segments = session.poll_new_finalized_segments_with_timing()

        assert [s.sequence_index for s in segments] == [0, 1]
        assert segments[0].started_at == fixed_start
        assert segments[0].ended_at == fixed_start + timedelta(seconds=15)
        assert segments[1].started_at == fixed_start + timedelta(seconds=15)
        assert segments[1].ended_at == fixed_start + timedelta(seconds=30)

    def test_already_returned_segments_are_never_returned_again(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "capture"
        output_dir.mkdir()
        (output_dir / "segment-00000000.wav").write_bytes(b"seg-0")

        session = audio_capture.MicrophoneCaptureSession(
            device="default", output_directory=output_dir,
            clock=lambda: datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC),
        )
        first = session.poll_new_finalized_segments_with_timing()
        second = session.poll_new_finalized_segments_with_timing()
        assert len(first) == 1
        assert second == []

    def test_bare_path_method_still_returns_the_same_finalized_paths(self, tmp_path: Path) -> None:
        # The pre-existing `poll_new_finalized_segments` must remain
        # byte-for-byte unchanged for existing callers/tests -- it now
        # delegates to the timing-aware method internally, stripping the
        # timing back off.
        output_dir = tmp_path / "capture"
        output_dir.mkdir()
        (output_dir / "segment-00000000.wav").write_bytes(b"seg-0")

        session = audio_capture.MicrophoneCaptureSession(device="default", output_directory=output_dir)
        assert [p.name for p in session.poll_new_finalized_segments()] == ["segment-00000000.wav"]


class TestMicrophoneSessionManager:
    def test_start_stop_status_lifecycle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_process = _FakeCaptureProcess()
        monkeypatch.setattr(audio_capture, "is_ffmpeg_available", lambda binary="ffmpeg": True)
        monkeypatch.setattr(audio_capture.subprocess, "Popen", lambda command, **kwargs: fake_process)

        manager = audio_capture.MicrophoneSessionManager()
        assert manager.is_running("stream-1") is False

        manager.start("stream-1", device="default", output_directory=tmp_path / "cap")
        assert manager.is_running("stream-1") is True
        assert manager.is_running("stream-2") is False  # per-Stream isolation

        manager.stop("stream-1")
        assert manager.is_running("stream-1") is False

    def test_stop_all_stops_every_running_session(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        processes = [_FakeCaptureProcess(), _FakeCaptureProcess()]
        call_count = {"n": 0}

        def fake_popen(command, **kwargs):
            process = processes[call_count["n"]]
            call_count["n"] += 1
            return process

        monkeypatch.setattr(audio_capture, "is_ffmpeg_available", lambda binary="ffmpeg": True)
        monkeypatch.setattr(audio_capture.subprocess, "Popen", fake_popen)

        manager = audio_capture.MicrophoneSessionManager()
        manager.start("stream-1", device="default", output_directory=tmp_path / "a")
        manager.start("stream-2", device="default", output_directory=tmp_path / "b")
        manager.stop_all()

        assert all(process.terminated for process in processes)
        assert manager.is_running("stream-1") is False
        assert manager.is_running("stream-2") is False
