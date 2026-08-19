"""Independent biological-encounter denominator recorder (see
docs/independent-encounter-denominator-design.md and "Evidence-cache
capacity" in docs/candidate-visit-authority-contract.md's sibling
discussion). Pure filesystem-boundary behavior: bounded interval sampling,
bounded count/byte caps, honest skip accounting, and -- critically -- zero
product-repository/evidence-pipeline coupling, so this tool can never
become admission evidence even by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation.acceptance_recorder import (
    AcceptanceRecorderConfig,
    BoundedFrameSampleRecorder,
)

NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)


@dataclass(frozen=True)
class _Frame:
    frame_id: str | None
    source_offset_ms: int | None
    captured_at: datetime | None
    payload: bytes | None


def _frame(offset_ms: int, *, payload: bytes = b"\xff\xd8fake-jpeg\xff\xd9") -> _Frame:
    return _Frame(
        frame_id=f"frame-{offset_ms}", source_offset_ms=offset_ms,
        captured_at=NOW + timedelta(milliseconds=offset_ms), payload=payload,
    )


def test_config_rejects_out_of_range_bounds(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        AcceptanceRecorderConfig(output_dir=tmp_path, sample_interval_ms=0)
    with pytest.raises(ValueError):
        AcceptanceRecorderConfig(output_dir=tmp_path, max_frames=0)
    with pytest.raises(ValueError):
        AcceptanceRecorderConfig(output_dir=tmp_path, max_total_bytes=1)


def test_saves_frames_at_the_configured_interval_only(tmp_path: Path) -> None:
    recorder = BoundedFrameSampleRecorder(AcceptanceRecorderConfig(output_dir=tmp_path, sample_interval_ms=1000))
    # 0ms: saved (first). 500ms: too soon, skipped. 1000ms: saved (exactly
    # at the boundary). 1999ms: too soon. 2000ms: saved.
    assert recorder.maybe_record(_frame(0)) is True
    assert recorder.maybe_record(_frame(500)) is False
    assert recorder.maybe_record(_frame(1000)) is True
    assert recorder.maybe_record(_frame(1999)) is False
    assert recorder.maybe_record(_frame(2000)) is True

    status = recorder.status()
    assert status.frames_saved == 3
    assert status.frames_skipped_interval == 2
    assert status.frames_considered == 5
    assert status.stopped_reason is None


def test_saved_frames_and_manifest_are_real_and_retrievable(tmp_path: Path) -> None:
    recorder = BoundedFrameSampleRecorder(AcceptanceRecorderConfig(output_dir=tmp_path, sample_interval_ms=1000))
    recorder.maybe_record(_frame(0, payload=b"\xff\xd8AAAA\xff\xd9"))
    recorder.maybe_record(_frame(1000, payload=b"\xff\xd8BBBB\xff\xd9"))

    saved_jpegs = sorted(tmp_path.glob("*.jpg"))
    assert len(saved_jpegs) == 2
    assert saved_jpegs[0].read_bytes() == b"\xff\xd8AAAA\xff\xd9"
    assert saved_jpegs[1].read_bytes() == b"\xff\xd8BBBB\xff\xd9"

    manifest_lines = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest_lines) == 2
    import json

    first = json.loads(manifest_lines[0])
    assert first["source_offset_ms"] == 0
    assert first["sequence"] == 0
    assert first["byte_count"] == len(b"\xff\xd8AAAA\xff\xd9")
    assert first["content_hash"]  # a real sha256 hex digest was recorded
    assert (tmp_path / first["filename"]).is_file()


def test_stops_accepting_once_max_frames_reached(tmp_path: Path) -> None:
    recorder = BoundedFrameSampleRecorder(
        AcceptanceRecorderConfig(output_dir=tmp_path, sample_interval_ms=100, max_frames=2),
    )
    assert recorder.maybe_record(_frame(0)) is True
    assert recorder.maybe_record(_frame(100)) is True
    assert recorder.is_accepting is True  # still accepting up to and including the cap
    assert recorder.maybe_record(_frame(200)) is False  # the cap itself now blocks a third
    assert recorder.is_accepting is False
    assert recorder.status().stopped_reason == "max_frames_reached"
    # Never silently truncates a bound violation into "just keep going" --
    # a later frame is honestly refused, not fabricated or dropped without
    # accounting.
    assert recorder.maybe_record(_frame(300)) is False
    assert recorder.status().frames_saved == 2


def test_stops_accepting_once_max_total_bytes_reached(tmp_path: Path) -> None:
    big_payload = b"\xff\xd8" + b"0" * 600_000 + b"\xff\xd9"
    recorder = BoundedFrameSampleRecorder(
        AcceptanceRecorderConfig(output_dir=tmp_path, sample_interval_ms=100, max_total_bytes=1_000_000),
    )
    assert recorder.maybe_record(_frame(0, payload=big_payload)) is True
    # A second frame of the same size would exceed the byte bound -- refused
    # before ever writing partial bytes to disk.
    assert recorder.maybe_record(_frame(100, payload=big_payload)) is False
    assert recorder.status().stopped_reason == "max_total_bytes_reached"
    assert recorder.status().total_bytes_saved == len(big_payload)


def test_honestly_skips_a_frame_with_no_payload_or_missing_identity(tmp_path: Path) -> None:
    recorder = BoundedFrameSampleRecorder(AcceptanceRecorderConfig(output_dir=tmp_path, sample_interval_ms=100))
    assert recorder.maybe_record(_Frame(frame_id="a", source_offset_ms=0, captured_at=NOW, payload=None)) is False
    assert recorder.maybe_record(_Frame(frame_id="b", source_offset_ms=None, captured_at=NOW, payload=b"x")) is False
    assert recorder.maybe_record(_Frame(frame_id="c", source_offset_ms=0, captured_at=None, payload=b"x")) is False
    status = recorder.status()
    assert status.frames_saved == 0
    assert status.frames_considered == 3
    assert status.stopped_reason is None  # never a bound violation, just missing facts


def test_default_byte_bound_has_real_headroom_over_the_old_undersized_default(tmp_path: Path) -> None:
    """Regression test for a real field-use defect: the original 750MB
    `max_total_bytes` default was sized off an assumed ~200KB/frame, but the
    2026-08-19 live field session measured analysis-resolution JPEGs
    averaging ~801KB (max ~841KB) -- so the byte bound silently bound FIRST,
    at 936 of an intended ~2400 frames, ending recording ~30 minutes before
    the session's actual Stop and losing independent coverage of the last
    three admitted Visits that session.

    This locks in that `max_frames`'s own default (a full 120-minute session
    at the default 3-second interval) now fits under `max_total_bytes`'s own
    default even at a per-frame size somewhat above the worst real frame
    observed -- i.e. the frame-count/duration bound is the one that binds in
    ordinary operation, not a silent early byte-cap stop.
    """
    config = AcceptanceRecorderConfig(output_dir=tmp_path)
    worst_case_real_frame_bytes = 850_000  # above the ~841KB observed real max
    assert config.max_frames * worst_case_real_frame_bytes <= config.max_total_bytes


def test_module_has_no_product_repository_or_admission_pipeline_import() -> None:
    """The structural guarantee this whole tool exists to provide: it can
    never become admission evidence even by accident, because it has no way
    to reach the code paths that create one."""

    import ast
    from pathlib import Path as _Path

    source = _Path("src/mockingbird/observation/acceptance_recorder.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_prefixes = (
        "mockingbird.repository",
        "mockingbird.observation.candidate_visit_authority",
        "mockingbird.observation.candidate_visit_adapter",
        "mockingbird.observation.candidate_quality_gate",
        "mockingbird.observation.visit_episode_assembler",
    )
    for module in imported_modules:
        assert not module.startswith(forbidden_prefixes), f"unexpected coupling: {module}"
