"""Hardware-free tests for the Stage 6.8 pure session-timeline derivation.

No Camera Node, CUDA, ONNX Runtime, filesystem, or product database is
touched. Numbered sections mirror the task's required hardware-free-test
list where applicable.
"""
from __future__ import annotations

import pytest

from datetime import UTC, datetime

from mockingbird.observation.session_timeline import (
    DERIVED_SESSION_TIMELINE,
    LEGACY_RECONNECT_GAP_UNCERTAINTY_MS,
    LONG_GAP_THRESHOLD_MS,
    NATIVE_CLOCK_REGRESSION_UNCERTAINTY_MS,
    NATIVE_RECONNECT_UNCERTAINTY_MS,
    NATIVE_SESSION_TIMELINE,
    SessionTimelineError,
    SourceFrameFact,
    derive_session_timeline,
    native_reconnect_step,
)


def _native(frame_id: str, sequence: int, offset_ms: int, *, segment: str, received: str, generation: str = "gen-1") -> SourceFrameFact:
    return SourceFrameFact(
        frame_id=frame_id, source_sequence=sequence, source_offset_ms=offset_ms, provider_generation=generation,
        connection_segment_hint=segment, host_received_at_iso=received,
    )


def _legacy(frame_id: str, sequence: int, offset_ms: int, *, generation: str = "gen-1") -> SourceFrameFact:
    return SourceFrameFact(
        frame_id=frame_id, source_sequence=sequence, source_offset_ms=offset_ms, provider_generation=generation,
    )


# --------------------------------------------------------------------------
# 1. One connection produces a native monotonic timeline.
# --------------------------------------------------------------------------


def test_single_connection_produces_native_monotonic_timeline() -> None:
    facts = (
        _native("f1", 1, 0, segment="conn-a", received="2026-08-06T12:00:00+00:00"),
        _native("f2", 2, 500, segment="conn-a", received="2026-08-06T12:00:00.500000+00:00"),
        _native("f3", 3, 1000, segment="conn-a", received="2026-08-06T12:00:01+00:00"),
    )
    timeline = derive_session_timeline(facts, session_id="s1")
    assert timeline.classification == NATIVE_SESSION_TIMELINE
    offsets = [item.session_offset_ms for item in timeline.frames]
    assert offsets == sorted(offsets)
    assert len(set(offsets)) == 3
    assert all(not item.temporal_discontinuity for item in timeline.frames)
    assert len(timeline.segments) == 1
    assert timeline.segments[0].frame_count == 3


# --------------------------------------------------------------------------
# 2. Sequence reset creates a new connection segment.
# 4. Same provider generation can contain multiple connection segments.
# --------------------------------------------------------------------------


def test_reconnect_with_unchanged_generation_creates_a_new_segment() -> None:
    facts = (
        _native("f1", 10, 5000, segment="conn-a", received="2026-08-06T12:00:00+00:00", generation="gen-1"),
        # A real reconnect: sequence and source_offset_ms both reset near zero,
        # but provider_generation (the Node's own camera identity) is unchanged.
        _native("f2", 1, 0, segment="conn-b", received="2026-08-06T12:00:02+00:00", generation="gen-1"),
    )
    timeline = derive_session_timeline(facts, session_id="s1")
    assert timeline.classification == NATIVE_SESSION_TIMELINE
    assert len(timeline.segments) == 2
    assert timeline.segments[0].segment_ordinal == 0
    assert timeline.segments[1].segment_ordinal == 1
    assert timeline.frames[1].temporal_discontinuity is True
    assert timeline.frames[1].connection_segment_id != timeline.frames[0].connection_segment_id
    # A shared provider_generation across the reconnect is a distinct fact
    # from the connection-segment boundary and never collapses it away.
    assert facts[0].provider_generation == facts[1].provider_generation


# --------------------------------------------------------------------------
# 3. Source-offset reset does not reset session offset.
# --------------------------------------------------------------------------


def test_source_offset_reset_does_not_reset_session_offset() -> None:
    facts = (
        _native("f1", 12, 6825, segment="conn-a", received="2026-08-06T12:00:10+00:00"),
        _native("f2", 1, 0, segment="conn-b", received="2026-08-06T12:00:11+00:00"),
    )
    timeline = derive_session_timeline(facts, session_id="s1")
    first, second = timeline.frames
    assert second.session_offset_ms > first.session_offset_ms
    # The reset, connection-local fact remains untouched as provenance.
    assert facts[1].source_offset_ms == 0


# --------------------------------------------------------------------------
# 5. Equal host receive timestamps are ordered deterministically.
# --------------------------------------------------------------------------


def test_equal_host_receive_timestamps_are_ordered_deterministically() -> None:
    facts = (
        _native("f1", 1, 0, segment="conn-a", received="2026-08-06T12:00:00+00:00"),
        _native("f2", 2, 10, segment="conn-a", received="2026-08-06T12:00:00+00:00"),
    )
    first = derive_session_timeline(facts, session_id="s1")
    second = derive_session_timeline(facts, session_id="s1")
    assert first.frames == second.frames
    # Strict monotonicity is preserved even though the wall clock tied.
    assert first.frames[1].session_offset_ms > first.frames[0].session_offset_ms


# --------------------------------------------------------------------------
# 6. Missing receive timestamp: session-wide honest fallback.
# --------------------------------------------------------------------------


def test_missing_receive_timestamp_falls_back_to_derived_classification() -> None:
    facts = (
        _native("f1", 1, 0, segment="conn-a", received="2026-08-06T12:00:00+00:00"),
        SourceFrameFact(frame_id="f2", source_sequence=2, source_offset_ms=500, provider_generation="gen-1"),
    )
    timeline = derive_session_timeline(facts, session_id="s1")
    assert timeline.classification == DERIVED_SESSION_TIMELINE
    assert len(timeline.frames) == 2


# --------------------------------------------------------------------------
# 7. Host timestamp regression is represented, never silently reordered.
# --------------------------------------------------------------------------


def test_host_timestamp_regression_is_represented_not_reordered() -> None:
    facts = (
        _native("f1", 1, 0, segment="conn-a", received="2026-08-06T12:00:05+00:00"),
        # A clock correction makes the second frame's stamp look earlier,
        # even though it was genuinely received second.
        _native("f2", 2, 500, segment="conn-a", received="2026-08-06T12:00:01+00:00"),
    )
    timeline = derive_session_timeline(facts, session_id="s1")
    # True arrival order (the given input order) is preserved, not resorted
    # by the regressed timestamp value.
    assert [item.frame_id for item in timeline.frames] == ["f1", "f2"]
    assert timeline.frames[1].session_offset_ms > timeline.frames[0].session_offset_ms
    assert timeline.frames[1].temporal_uncertainty_ms > 0


# --------------------------------------------------------------------------
# 8. Long reconnect gap creates temporal discontinuity.
# --------------------------------------------------------------------------


def test_long_reconnect_gap_creates_temporal_discontinuity_and_limitation() -> None:
    facts = (
        _native("f1", 5, 2000, segment="conn-a", received="2026-08-06T12:00:00+00:00"),
        _native("f2", 1, 0, segment="conn-b", received="2026-08-06T12:10:00+00:00"),
    )
    timeline = derive_session_timeline(facts, session_id="s1")
    assert timeline.frames[1].temporal_discontinuity is True
    assert timeline.frames[1].session_offset_ms - timeline.frames[0].session_offset_ms >= LONG_GAP_THRESHOLD_MS
    assert any("long-gap" in item for item in timeline.limitations)


# --------------------------------------------------------------------------
# 19. Old manifest derives a deterministic timeline.
# --------------------------------------------------------------------------


def test_legacy_manifest_without_native_fields_derives_deterministic_timeline() -> None:
    # Mirrors the real Stage 6.7 pattern: many short connections, each
    # restarting its own local sequence, stored in sequence-sorted (not
    # chronological) order -- exactly what temporal_capture.py's frame
    # ordering wrote for a multi-reconnect session before Stage 6.8.
    facts = (
        _legacy("a1", 1, 0), _legacy("b1", 1, 0), _legacy("c1", 1, 0),
        _legacy("a2", 2, 500), _legacy("b2", 2, 480),
        _legacy("a3", 3, 1000),
    )
    first = derive_session_timeline(facts, session_id="s1")
    second = derive_session_timeline(facts, session_id="s1")
    assert first.classification == DERIVED_SESSION_TIMELINE
    assert first == second  # stable for repeated processing of the same input
    # Every frame gets one unique, monotonic session order.
    orders = [item.session_sequence for item in first.frames]
    assert orders == list(range(len(facts)))
    offsets = [item.session_offset_ms for item in first.frames]
    assert offsets == sorted(offsets) and len(set(offsets)) == len(offsets)
    # Reconstructed into 3 segments (a, b, c), matching the three distinct
    # connections implied by three frames sharing local sequence 1.
    assert len(first.segments) == 3
    assert first.upgrade_provenance["reconstructed_segment_count"] == 3
    for segment in first.segments:
        assert segment.timing_quality == "reconstructed_sequence_order"


def test_legacy_reconstruction_keeps_each_segment_internally_sequence_increasing() -> None:
    facts = (
        _legacy("a1", 1, 0), _legacy("b1", 1, 0),
        _legacy("a2", 2, 500), _legacy("b2", 2, 500),
        _legacy("a3", 3, 1000),
    )
    timeline = derive_session_timeline(facts, session_id="s1")
    by_segment: dict[str, list[str]] = {}
    for frame in timeline.frames:
        by_segment.setdefault(frame.connection_segment_id, []).append(frame.frame_id)
    # Segment "a" (created first, from a1) absorbs a1, a2, a3 in order.
    first_segment_id = timeline.frame("a1").connection_segment_id
    assert by_segment[first_segment_id] == ["a1", "a2", "a3"]


def test_legacy_reconnect_boundary_uses_bounded_uncertainty_not_a_fabricated_gap() -> None:
    facts = (_legacy("a1", 1, 0), _legacy("b1", 1, 0))
    timeline = derive_session_timeline(facts, session_id="s1")
    boundary_frame = timeline.frame("b1")
    assert boundary_frame.temporal_discontinuity is True
    assert boundary_frame.temporal_uncertainty_ms == LEGACY_RECONNECT_GAP_UNCERTAINTY_MS
    # Ordering advances by the minimal step, never claiming a known duration.
    assert boundary_frame.session_offset_ms == timeline.frame("a1").session_offset_ms + 1


# --------------------------------------------------------------------------
# 20. Insufficient old provenance fails honestly.
# --------------------------------------------------------------------------


def test_negative_source_offset_is_rejected_at_the_fact_boundary() -> None:
    with pytest.raises(SessionTimelineError, match="invalid_source_frame_fact"):
        SourceFrameFact(frame_id="f1", source_sequence=1, source_offset_ms=-1, provider_generation="gen-1")


def test_empty_session_identity_fails_honestly() -> None:
    with pytest.raises(SessionTimelineError, match="invalid_session_identity"):
        derive_session_timeline((_legacy("f1", 1, 0),), session_id="")


def test_duplicate_frame_identity_fails_honestly() -> None:
    with pytest.raises(SessionTimelineError, match="duplicate_frame_identity"):
        derive_session_timeline((_legacy("f1", 1, 0), _legacy("f1", 2, 500)), session_id="s1")


def test_unparseable_receive_timestamp_fails_honestly() -> None:
    facts = (
        SourceFrameFact(
            frame_id="f1", source_sequence=1, source_offset_ms=0, provider_generation="gen-1",
            connection_segment_hint="conn-a", host_received_at_iso="not-a-timestamp",
        ),
    )
    with pytest.raises(SessionTimelineError, match="invalid_host_received_at"):
        derive_session_timeline(facts, session_id="s1")


# --------------------------------------------------------------------------
# 21. Original source sequence/offset remain unchanged by derivation.
# --------------------------------------------------------------------------


def test_derivation_never_mutates_the_supplied_source_facts() -> None:
    facts = (
        _native("f1", 12, 6825, segment="conn-a", received="2026-08-06T12:00:10+00:00"),
        _native("f2", 1, 0, segment="conn-b", received="2026-08-06T12:00:11+00:00"),
    )
    before = tuple(facts)
    derive_session_timeline(facts, session_id="s1")
    assert facts == before
    assert facts[1].source_sequence == 1
    assert facts[1].source_offset_ms == 0


# --------------------------------------------------------------------------
# Bounds and empty input
# --------------------------------------------------------------------------


def test_empty_input_produces_an_empty_native_timeline() -> None:
    timeline = derive_session_timeline((), session_id="s1")
    assert timeline.classification == NATIVE_SESSION_TIMELINE
    assert timeline.frames == ()
    assert timeline.segments == ()


def test_timeline_frame_limit_is_enforced() -> None:
    facts = tuple(_legacy(f"f{i}", i, i * 10) for i in range(1, 20_002))
    with pytest.raises(SessionTimelineError, match="session_timeline_frame_limit"):
        derive_session_timeline(facts, session_id="s1")


# --------------------------------------------------------------------------
# Stage 6.11B: `native_reconnect_step` is the identical per-boundary
# forward-clamped step/uncertainty arithmetic `_derive_native` applies
# post-hoc, exposed standalone so a live Camera Node consumer
# (`camera_node_live.CameraNodeAnalysisSource`) can apply it incrementally,
# one already-delivered frame at a time, instead of a second, independently
# -tuned live timeline policy. See docs/reconnect-continuity-contract.md.
# --------------------------------------------------------------------------


def test_native_reconnect_step_measures_forward_gap_with_reconnect_uncertainty() -> None:
    step_ms, uncertainty_ms = native_reconnect_step(
        previous_received_at=datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC),
        current_received_at=datetime(2026, 8, 6, 12, 0, 2, 500000, tzinfo=UTC),
    )
    assert step_ms == 2500
    assert uncertainty_ms == NATIVE_RECONNECT_UNCERTAINTY_MS


def test_native_reconnect_step_clamps_a_clock_regression_forward() -> None:
    step_ms, uncertainty_ms = native_reconnect_step(
        previous_received_at=datetime(2026, 8, 6, 12, 0, 5, tzinfo=UTC),
        current_received_at=datetime(2026, 8, 6, 12, 0, 4, tzinfo=UTC),
    )
    assert step_ms == 1
    assert uncertainty_ms == NATIVE_CLOCK_REGRESSION_UNCERTAINTY_MS


def test_native_reconnect_step_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(SessionTimelineError, match="invalid_host_received_at"):
        native_reconnect_step(
            previous_received_at=datetime(2026, 8, 6, 12, 0, 0),
            current_received_at=datetime(2026, 8, 6, 12, 0, 1, tzinfo=UTC),
        )
