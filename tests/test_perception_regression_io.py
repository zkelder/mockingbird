"""Perception Replay Regression Harness v1: `perception_regression_io.py`."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from mockingbird.observation.perception_regression_io import (
    load_acceptance_recording,
    load_fixture_registry,
)
from mockingbird.observation.replay import ReplayValidationError


def _jpeg_bytes(color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 48), color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _write_synthetic_recording(directory: Path, *, count: int = 6, interval_ms: int = 3_000, start_offset_ms: int = 1_000_000) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for sequence in range(count):
        payload = _jpeg_bytes(color=(sequence * 10, 20, 30))
        offset_ms = start_offset_ms + sequence * interval_ms
        filename = f"frame-{sequence:06d}-offset{offset_ms:09d}ms.jpg"
        (directory / filename).write_bytes(payload)
        lines.append(json.dumps({
            "sequence": sequence,
            "frame_id": f"frame-{sequence}",
            "source_offset_ms": offset_ms,
            "captured_at": f"2026-08-19T21:{14 + sequence:02d}:00+00:00",
            "filename": filename,
            "content_hash": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
        }))
    (directory / "manifest.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_acceptance_recording_rebases_offsets_to_start_at_zero(tmp_path: Path) -> None:
    recording = tmp_path / "recording"
    _write_synthetic_recording(recording, count=5, interval_ms=3_000, start_offset_ms=500_000)
    bundle = load_acceptance_recording(recording, stream_id="replay:fixture", input_id="fixture-input")
    assert [frame.source_offset_ms for frame in bundle.replay.frames] == [0, 3000, 6000, 9000, 12000]
    assert [frame.index for frame in bundle.replay.frames] == [0, 1, 2, 3, 4]
    assert bundle.manifest.input_fingerprint == bundle.replay.fingerprint
    assert bundle.manifest.visits == ()
    assert bundle.manifest.appearances == ()


def test_load_acceptance_recording_preserves_real_captured_at(tmp_path: Path) -> None:
    recording = tmp_path / "recording"
    _write_synthetic_recording(recording, count=3)
    bundle = load_acceptance_recording(recording, stream_id="replay:fixture", input_id="fixture-input")
    first = bundle.replay.frames[0]
    assert first.captured_at_iso == "2026-08-19T21:14:00+00:00"
    packet = bundle.replay.packets()[0]
    assert packet.captured_at is not None
    assert packet.captured_at.isoformat() == "2026-08-19T21:14:00+00:00"


def test_load_acceptance_recording_applies_a_bounded_window(tmp_path: Path) -> None:
    recording = tmp_path / "recording"
    _write_synthetic_recording(recording, count=10, interval_ms=1_000, start_offset_ms=0)
    bundle = load_acceptance_recording(
        recording, stream_id="replay:fixture", input_id="fixture-input",
        window_start_ms=3_000, window_end_ms=6_000,
    )
    # Frames at rebased offsets 3000/4000/5000/6000 -> re-based again to 0/1000/2000/3000.
    assert [frame.source_offset_ms for frame in bundle.replay.frames] == [0, 1000, 2000, 3000]
    assert len(bundle.replay.frames) == 4


def test_load_acceptance_recording_rejects_an_empty_window(tmp_path: Path) -> None:
    recording = tmp_path / "recording"
    _write_synthetic_recording(recording, count=5, interval_ms=1_000, start_offset_ms=0)
    with pytest.raises(ReplayValidationError, match="empty_window_selection"):
        load_acceptance_recording(
            recording, stream_id="replay:fixture", input_id="fixture-input",
            window_start_ms=100_000, window_end_ms=200_000,
        )


def test_load_acceptance_recording_rejects_a_missing_manifest(tmp_path: Path) -> None:
    recording = tmp_path / "recording"
    recording.mkdir()
    with pytest.raises(ReplayValidationError, match="unsafe_recording_manifest_path"):
        load_acceptance_recording(recording, stream_id="replay:fixture", input_id="fixture-input")


def test_load_acceptance_recording_rejects_a_frame_path_escaping_the_directory(tmp_path: Path) -> None:
    recording = tmp_path / "recording"
    _write_synthetic_recording(recording, count=2)
    payload = json.loads((recording / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    payload["filename"] = "../escape.jpg"
    lines = (recording / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    lines[0] = json.dumps(payload)
    (recording / "manifest.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ReplayValidationError, match="unsafe_recording_frame_path"):
        load_acceptance_recording(recording, stream_id="replay:fixture", input_id="fixture-input")


def _fixture_registry_payload(**overrides: object) -> dict[str, object]:
    entry = {
        "fixture_id": "known_valid_bird_visit",
        "description": "A known real bird encounter, for regression comparison.",
        "source_kind": "acceptance_recording",
        "frames_path": "/mnt/example/recording",
        "manifest_path": None,
        "provider_key": "frame-driven-onnx-cuda",
        "provider_config_path": "/mnt/example/provider-config.json",
        "stream_id": "replay:fixture-feeder",
        "base_observed_at": "2026-08-19T17:27:10+00:00",
        "window_start_ms": 0,
        "window_end_ms": 60_000,
    }
    entry.update(overrides)
    return {"version": 1, "fixtures": [entry]}


def test_load_fixture_registry_parses_a_valid_entry(tmp_path: Path) -> None:
    registry_path = tmp_path / "fixtures.json"
    registry_path.write_text(json.dumps(_fixture_registry_payload()), encoding="utf-8")
    fixtures = load_fixture_registry(registry_path)
    assert set(fixtures) == {"known_valid_bird_visit"}
    fixture = fixtures["known_valid_bird_visit"]
    assert fixture.source_kind == "acceptance_recording"
    assert fixture.base_observed_at == datetime.fromisoformat("2026-08-19T17:27:10+00:00")
    assert fixture.window_start_ms == 0
    assert fixture.window_end_ms == 60_000


def test_load_fixture_registry_rejects_a_duplicate_fixture_id(tmp_path: Path) -> None:
    payload = _fixture_registry_payload()
    payload["fixtures"].append(payload["fixtures"][0])
    registry_path = tmp_path / "fixtures.json"
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ReplayValidationError, match="duplicate_fixture_id"):
        load_fixture_registry(registry_path)


def test_load_fixture_registry_rejects_an_unsupported_source_kind(tmp_path: Path) -> None:
    registry_path = tmp_path / "fixtures.json"
    registry_path.write_text(json.dumps(_fixture_registry_payload(source_kind="video_file")), encoding="utf-8")
    with pytest.raises(ReplayValidationError, match="unsupported_fixture_source_kind"):
        load_fixture_registry(registry_path)
