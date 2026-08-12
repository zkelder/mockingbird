"""Hardware-free tests for the Stage 6.6 pure temporal-capture contract:
bounds, triggers, operator markers, recurring geometry, periodic negative
sampling, and capture-session manifest assembly/fingerprinting. No Camera
Node, CUDA, ONNX Runtime, or product database is touched. Numbered sections
mirror the task's required hardware-free-test list.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.temporal_capture import (
    CAPTURE_MANIFEST_SCHEMA_VERSION,
    OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW,
    STOP_DURATION_ELAPSED,
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
    TRIGGER_ANIMAL_BELOW_OPERATING_POINT_ABOVE_REVIEW_FLOOR,
    CaptureBounds,
    CaptureSessionConfig,
    CaptureSessionManifest,
    OperatorMarker,
    PeriodicNegativeScheduler,
    RecurringGeometryTracker,
    RetainedFrameRecord,
    TemporalCaptureError,
    attach_session_timeline,
    classify_detection_triggers,
    correlate_markers_to_frames,
    has_track_event,
    markers_near,
    upgrade_capture_manifest_timeline,
)
from mockingbird.observation.session_timeline import DERIVED_SESSION_TIMELINE, NATIVE_SESSION_TIMELINE


def _det(score: float, *, is_animal: bool = True) -> DetectionObservation:
    return DetectionObservation(
        "fixture", "animal", score, datetime.now(UTC), bounding_box=(0.1, 0.1, 0.2, 0.2), is_animal=is_animal,
    )


def _config(**overrides) -> CaptureSessionConfig:
    defaults = dict(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1", stream_id="s1",
        transport_key="camera-node-http-multipart-jpeg", provider_key="frame-driven-onnx-cuda",
        analysis_width=1920, analysis_height=1440, nominal_fps=2.0, review_score_threshold=0.02,
        shadow_operating_point=0.5, review_floor=0.1, evidence_profile_id="profile-1", bounds=CaptureBounds(),
    )
    defaults.update(overrides)
    return CaptureSessionConfig(**defaults)


def _frame_record(frame_id: str, sequence: int, offset_ms: int, **overrides) -> RetainedFrameRecord:
    defaults = dict(
        frame_id=frame_id, sequence=sequence, source_offset_ms=offset_ms, provider_generation="gen-1",
        content_hash="a" * 64, byte_size=1000, trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,),
        detector_observation_count=1, animal_detection_count=1, max_animal_score=0.8,
        active_track_count=0, motion_proposal_count=0,
    )
    defaults.update(overrides)
    return RetainedFrameRecord(**defaults)


def _manifest(frames: tuple[RetainedFrameRecord, ...] = (), **overrides) -> CaptureSessionManifest:
    defaults = dict(
        config=_config(), session_id="session-1", node_session_id="node-session-1",
        start_host_time_iso="2026-08-05T20:00:00+00:00", end_host_time_iso="2026-08-05T20:01:00+00:00",
        start_source_offset_ms=0, end_source_offset_ms=60000, first_sequence=0, last_sequence=10,
        sequence_gap_count=0, dropped_frame_count=0, coalesced_frame_count=0, stale_frame_count=0,
        generation_reset_count=0, provider_generations=("gen-1",), model_fingerprint="model-fp",
        tracker_proposal_config_fingerprint="cfg-fp", frames=frames, operator_markers=(),
        stop_condition=STOP_DURATION_ELAPSED,
    )
    defaults.update(overrides)
    return CaptureSessionManifest(**defaults)


# --------------------------------------------------------------------------
# 1. Capture-session manifest determinism
# --------------------------------------------------------------------------


def test_manifest_fingerprint_is_deterministic_across_rebuilds() -> None:
    frame = _frame_record("f1", 0, 0)
    first = _manifest((frame,)).fingerprint
    second = _manifest((frame,)).fingerprint
    assert first == second


# --------------------------------------------------------------------------
# 3. Duration/frame/byte bounds (config-level validation)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("field,value", [
    ("max_duration_seconds", 0), ("max_analysis_frames", 0), ("max_bytes_stored", 1),
    ("max_high_resolution_frames", -1), ("pretrigger_frame_count", -1), ("post_trigger_frame_count", 999),
])
def test_capture_bounds_reject_out_of_range_values(field: str, value: object) -> None:
    with pytest.raises(TemporalCaptureError):
        CaptureBounds(**{field: value})


def test_manifest_rejects_more_retained_frames_than_the_configured_bound() -> None:
    tiny_bounds = CaptureBounds(max_analysis_frames=1)
    frames = (_frame_record("f1", 0, 0), _frame_record("f2", 1, 1000))
    with pytest.raises(TemporalCaptureError, match="analysis_frame_limit_exceeded"):
        _manifest(frames, config=_config(bounds=tiny_bounds))


def test_manifest_rejects_more_high_resolution_frames_than_the_configured_bound() -> None:
    tiny_bounds = CaptureBounds(max_high_resolution_frames=1)
    frames = (
        _frame_record("f1", 0, 0, high_resolution=True),
        _frame_record("f2", 1, 1000, high_resolution=True),
    )
    with pytest.raises(TemporalCaptureError, match="high_resolution_frame_limit_exceeded"):
        _manifest(frames, config=_config(bounds=tiny_bounds))


# --------------------------------------------------------------------------
# 5. Periodic negative sampling
# --------------------------------------------------------------------------


def test_periodic_negative_scheduler_fires_at_the_configured_interval_and_stops_at_the_bound() -> None:
    scheduler = PeriodicNegativeScheduler(interval_seconds=10, max_samples=2)
    assert scheduler.due(0) is True
    assert scheduler.due(5_000) is False  # too soon
    assert scheduler.due(10_000) is True
    assert scheduler.due(20_000) is False  # bound reached


def test_periodic_negative_scheduler_rejects_invalid_configuration() -> None:
    with pytest.raises(TemporalCaptureError):
        PeriodicNegativeScheduler(interval_seconds=0, max_samples=1)


# --------------------------------------------------------------------------
# 6. Below-threshold candidate retention
# --------------------------------------------------------------------------


def test_below_operating_point_but_above_review_floor_is_a_distinct_trigger() -> None:
    triggers = classify_detection_triggers((_det(0.2),), operating_point=0.5, review_floor=0.1)
    assert triggers == (TRIGGER_ANIMAL_BELOW_OPERATING_POINT_ABOVE_REVIEW_FLOOR,)


def test_below_review_floor_produces_no_animal_trigger() -> None:
    triggers = classify_detection_triggers((_det(0.05),), operating_point=0.5, review_floor=0.1)
    assert triggers == ()


def test_above_operating_point_is_the_stronger_trigger() -> None:
    triggers = classify_detection_triggers((_det(0.9),), operating_point=0.5, review_floor=0.1)
    assert triggers == (TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,)


def test_non_animal_detections_never_produce_an_animal_trigger() -> None:
    triggers = classify_detection_triggers((_det(0.9, is_animal=False),), operating_point=0.5, review_floor=0.1)
    assert triggers == ()


def test_has_track_event_reflects_any_track_update() -> None:
    assert has_track_event(()) is False


# --------------------------------------------------------------------------
# 7. Operator marker lookback
# --------------------------------------------------------------------------


def test_operator_marker_correlates_within_its_own_lookback_window() -> None:
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=20)
    near = markers_near((marker,), host_time_iso="2026-08-05T20:00:15+00:00", default_lookback_seconds=20)
    assert near == (marker,)


def test_operator_marker_does_not_correlate_outside_its_lookback_window() -> None:
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=20)
    near = markers_near((marker,), host_time_iso="2026-08-05T19:59:00+00:00", default_lookback_seconds=20)
    assert near == ()


def test_operator_marker_never_correlates_to_a_frame_after_it() -> None:
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=20)
    near = markers_near((marker,), host_time_iso="2026-08-05T20:00:45+00:00", default_lookback_seconds=20)
    assert near == ()


def test_operator_marker_rejects_unknown_kind() -> None:
    with pytest.raises(TemporalCaptureError):
        OperatorMarker("m1", "not_a_real_kind", "2026-08-05T20:00:30+00:00")


# --------------------------------------------------------------------------
# Stage 6.8: post-hoc, reconnect-safe operator-marker correlation
# --------------------------------------------------------------------------


def test_correlate_markers_backfills_an_already_retained_frame() -> None:
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=20)
    frames = ({"frame_id": "f1", "host_received_at": "2026-08-05T20:00:15+00:00", "operator_marker_ids": ()},)
    associations = correlate_markers_to_frames(frames, (marker,))
    assert associations == {"f1": ("m1",)}


def test_correlate_markers_crosses_a_reconnect_boundary_when_timing_supports_it() -> None:
    # Frame f1 (an earlier connection segment) and f2 (a later one, after a
    # reconnect) both fall inside the marker's lookback -- correlation is
    # purely host-time based and does not care that they belong to
    # different connections.
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=25)
    frames = (
        {"frame_id": "f1", "host_received_at": "2026-08-05T20:00:10+00:00", "operator_marker_ids": ()},
        {"frame_id": "f2", "host_received_at": "2026-08-05T20:00:20+00:00", "operator_marker_ids": ()},
    )
    associations = correlate_markers_to_frames(frames, (marker,))
    assert associations["f1"] == ("m1",)
    assert associations["f2"] == ("m1",)


def test_correlate_markers_does_not_attach_beyond_lookback() -> None:
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=5)
    frames = ({"frame_id": "f1", "host_received_at": "2026-08-05T20:00:00+00:00", "operator_marker_ids": ()},)
    assert correlate_markers_to_frames(frames, (marker,)) == {"f1": ()}


def test_correlate_markers_collapses_duplicate_association_deterministically() -> None:
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=20)
    # The frame already carries this marker id (e.g. from the live bounded
    # rescue path); re-running post-hoc correlation must not duplicate it.
    frames = ({"frame_id": "f1", "host_received_at": "2026-08-05T20:00:15+00:00", "operator_marker_ids": ("m1",)},)
    assert correlate_markers_to_frames(frames, (marker,)) == {"f1": ("m1",)}


def test_correlate_markers_preserves_existing_associations_when_no_new_marker_matches() -> None:
    frames = ({"frame_id": "f1", "host_received_at": "2026-08-05T20:00:15+00:00", "operator_marker_ids": ("m-old",)},)
    assert correlate_markers_to_frames(frames, ()) == {"f1": ("m-old",)}


def test_correlate_markers_skips_a_frame_with_no_recorded_receive_time() -> None:
    marker = OperatorMarker("m1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:30+00:00", lookback_seconds=20)
    frames = ({"frame_id": "f1", "host_received_at": "", "operator_marker_ids": ()},)
    assert correlate_markers_to_frames(frames, (marker,)) == {"f1": ()}


# --------------------------------------------------------------------------
# Stage 6.8: session-timeline attachment
# --------------------------------------------------------------------------


def test_attach_session_timeline_gives_every_frame_a_unique_monotonic_order() -> None:
    frames = (
        _frame_record("a1", 1, 0, provider_generation="gen-1", connection_segment_id="conn-a", host_received_at="2026-08-06T12:00:00+00:00"),
        _frame_record("b1", 1, 0, provider_generation="gen-1", connection_segment_id="conn-b", host_received_at="2026-08-06T12:00:05+00:00"),
        _frame_record("b2", 2, 500, provider_generation="gen-1", connection_segment_id="conn-b", host_received_at="2026-08-06T12:00:05.500000+00:00"),
    )
    updated, timeline = attach_session_timeline(frames, session_id="session-1")
    assert timeline.classification == NATIVE_SESSION_TIMELINE
    orders = sorted(item.session_sequence for item in updated)
    assert orders == [0, 1, 2]
    offsets = sorted(item.session_offset_ms for item in updated)
    assert offsets == sorted(set(offsets))
    by_id = {item.frame_id: item for item in updated}
    assert by_id["b1"].temporal_discontinuity is True
    assert by_id["b1"].connection_segment_id == "conn-b"
    # Source-local facts are untouched.
    assert by_id["b1"].sequence == 1
    assert by_id["b1"].source_offset_ms == 0


def test_attach_session_timeline_falls_back_to_derived_for_legacy_frames() -> None:
    frames = (
        _frame_record("a1", 1, 0), _frame_record("b1", 1, 0), _frame_record("a2", 2, 500),
    )
    updated, timeline = attach_session_timeline(frames, session_id="session-1")
    assert timeline.classification == DERIVED_SESSION_TIMELINE
    assert len({item.session_sequence for item in updated}) == 3


# --------------------------------------------------------------------------
# Stage 6.8: manifest-dict upgrade (temporal-review-build's own upgrade path)
# --------------------------------------------------------------------------


def _manifest_dict(frames: tuple[RetainedFrameRecord, ...], **overrides) -> dict:
    manifest = _manifest(frames, **overrides)
    semantic = manifest.to_semantic_dict()
    semantic["semantic_fingerprint"] = manifest.fingerprint
    return semantic


def test_upgrade_capture_manifest_timeline_passes_through_an_already_native_manifest_unchanged() -> None:
    frames = (
        _frame_record(
            "a1", 1, 0, connection_segment_id="conn-a", host_received_at="2026-08-06T12:00:00+00:00",
            session_sequence=0, session_offset_ms=0,
        ),
    )
    raw = _manifest_dict(frames, session_timeline_classification=NATIVE_SESSION_TIMELINE)
    upgraded = upgrade_capture_manifest_timeline(raw)
    assert upgraded is raw
    assert upgraded["semantic_fingerprint"] == raw["semantic_fingerprint"]


def test_upgrade_capture_manifest_timeline_derives_a_legacy_manifest() -> None:
    frames = (_frame_record("a1", 1, 0), _frame_record("b1", 1, 0), _frame_record("a2", 2, 500))
    raw = _manifest_dict(frames)
    assert raw["session_timeline_classification"] == NATIVE_SESSION_TIMELINE  # default, not yet meaningful
    upgraded = upgrade_capture_manifest_timeline(raw)
    assert upgraded is not raw
    assert upgraded["session_timeline_classification"] == DERIVED_SESSION_TIMELINE
    assert upgraded["timeline_upgrade_provenance"]["reconstructed_segment_count"] == 2
    # The written frames array itself is in session order (not merely "the
    # right values exist somewhere in the list") -- mirrors what
    # CaptureSessionManifest.to_semantic_dict() guarantees for a native
    # capture, since every other consumer (review-packet ordering, replay
    # export) reads this array's own order as session order.
    session_sequences = [item["session_sequence"] for item in upgraded["frames"]]
    assert session_sequences == [0, 1, 2]
    # Greedy first-fit: a1(seq1) opens segment 0; b1(seq1) can't join it
    # (still at seq1) so opens segment 1; a2(seq2) *can* extend segment 0.
    # Concatenated by segment ordinal: [a1, a2] (segment 0) then [b1].
    assert [item["frame_id"] for item in upgraded["frames"]] == ["a1", "a2", "b1"]
    # The original capture manifest dict passed in is never mutated.
    assert raw["session_timeline_classification"] == NATIVE_SESSION_TIMELINE
    assert "session_sequence" not in raw["frames"][0] or raw["frames"][0]["session_sequence"] == 0
    # Repeated upgrades of the same raw manifest are deterministic.
    assert upgrade_capture_manifest_timeline(raw) == upgraded


def test_upgrade_capture_manifest_timeline_fails_honestly_on_missing_sequence() -> None:
    frames = (_frame_record("a1", 1, 0),)
    raw = _manifest_dict(frames)
    del raw["frames"][0]["sequence"]
    original_frame = dict(raw["frames"][0])
    upgraded = upgrade_capture_manifest_timeline(raw)
    assert upgraded["session_timeline_classification"] == "insufficient_temporal_provenance"
    assert upgraded["timeline_upgrade_provenance"]["derivation_method"] == "none"
    # Frames are never rewritten with a fabricated order when provenance is
    # insufficient to derive one honestly.
    assert upgraded["frames"][0] == original_frame


# --------------------------------------------------------------------------
# 13. Recurring static geometry grouping
# --------------------------------------------------------------------------


def test_recurring_geometry_flags_only_after_minimum_recurrence() -> None:
    tracker = RecurringGeometryTracker()
    assert tracker.observe((0.1, 0.1, 0.2, 0.2)) is False
    assert tracker.observe((0.1, 0.1, 0.2, 0.2)) is True


def test_recurring_geometry_treats_distant_boxes_as_separate_clusters() -> None:
    tracker = RecurringGeometryTracker()
    assert tracker.observe((0.1, 0.1, 0.2, 0.2)) is False
    assert tracker.observe((0.8, 0.8, 0.9, 0.9)) is False
    assert tracker.observe((0.8, 0.8, 0.9, 0.9)) is True
    # The first cluster still requires its own second recurrence.
    assert tracker.observe((0.1, 0.1, 0.2, 0.2)) is True


# --------------------------------------------------------------------------
# 14. Privacy/Ignore metadata preservation
# --------------------------------------------------------------------------


def test_privacy_ignore_regions_are_preserved_in_the_semantic_manifest() -> None:
    regions = ((0.0, 0.0, 0.2, 0.2),)
    manifest = _manifest((), config=_config(privacy_ignore_regions=regions))
    semantic = manifest.to_semantic_dict()
    assert semantic["config"]["privacy_ignore_regions"] == regions


def test_privacy_ignore_regions_survive_a_legacy_timeline_upgrade() -> None:
    regions = ((0.0, 0.0, 0.2, 0.2),)
    frames = (_frame_record("a1", 1, 0), _frame_record("b1", 1, 0))
    raw = _manifest_dict(frames, config=_config(privacy_ignore_regions=regions))
    upgraded = upgrade_capture_manifest_timeline(raw)
    assert upgraded["session_timeline_classification"] == DERIVED_SESSION_TIMELINE
    assert upgraded["config"]["privacy_ignore_regions"] == regions


# --------------------------------------------------------------------------
# 31. Absolute paths excluded from semantic fingerprints
# --------------------------------------------------------------------------


def test_semantic_manifest_never_contains_an_absolute_path_or_credential() -> None:
    import json
    frame = _frame_record("f1", 0, 0)
    manifest = _manifest((frame,))
    serialized = json.dumps(manifest.to_semantic_dict())
    assert "/home/" not in serialized
    assert "credential" not in serialized.lower()
    assert "bearer" not in serialized.lower()


def test_config_carries_no_hostname_or_credential_field() -> None:
    import dataclasses
    field_names = {field.name for field in dataclasses.fields(CaptureSessionConfig)}
    assert not field_names & {"credential", "base_address", "hostname", "bearer_token"}


# --------------------------------------------------------------------------
# 32. Repeated semantic fingerprints match
# --------------------------------------------------------------------------


def test_repeated_fingerprint_calls_on_the_same_manifest_match() -> None:
    frame = _frame_record("f1", 0, 0, trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,))
    manifest = _manifest((frame,))
    assert manifest.fingerprint == manifest.fingerprint


def test_fingerprint_changes_when_a_retained_frame_changes() -> None:
    manifest_a = _manifest((_frame_record("f1", 0, 0),))
    manifest_b = _manifest((_frame_record("f1", 0, 0, max_animal_score=0.99),))
    assert manifest_a.fingerprint != manifest_b.fingerprint


# --------------------------------------------------------------------------
# Duplicate frame identity / retained-frame validation
# --------------------------------------------------------------------------


def test_manifest_rejects_duplicate_frame_identity() -> None:
    frames = (_frame_record("f1", 0, 0), _frame_record("f1", 1, 1000))
    with pytest.raises(TemporalCaptureError, match="duplicate_frame_identity"):
        _manifest(frames)


def test_retained_frame_requires_at_least_one_trigger_reason() -> None:
    with pytest.raises(TemporalCaptureError):
        RetainedFrameRecord(
            frame_id="f1", sequence=0, source_offset_ms=0, provider_generation="gen-1",
            content_hash="a" * 64, byte_size=100, trigger_reasons=(), detector_observation_count=0,
            animal_detection_count=0, max_animal_score=None, active_track_count=0, motion_proposal_count=0,
        )


def test_review_floor_cannot_exceed_shadow_operating_point() -> None:
    with pytest.raises(TemporalCaptureError):
        _config(shadow_operating_point=0.3, review_floor=0.5)


def test_review_score_threshold_must_stay_at_or_below_review_floor() -> None:
    with pytest.raises(TemporalCaptureError):
        _config(review_score_threshold=0.2, review_floor=0.1)


# --------------------------------------------------------------------------
# Stage-3 Holdout v2 groundwork
# --------------------------------------------------------------------------


def test_holdout_v2_candidate_defaults_false() -> None:
    record = _frame_record("f1", 0, 0)
    assert record.holdout_v2_candidate is False


def test_holdout_v2_candidate_can_be_set_and_round_trips_through_asdict() -> None:
    from dataclasses import asdict

    record = _frame_record("f1", 0, 0, holdout_v2_candidate=True)
    assert record.holdout_v2_candidate is True
    assert asdict(record)["holdout_v2_candidate"] is True
