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
    classify_detection_triggers,
    has_track_event,
    markers_near,
)


def _det(score: float, *, is_animal: bool = True) -> DetectionObservation:
    return DetectionObservation(
        "fixture", "animal", score, datetime.now(UTC), bounding_box=(0.1, 0.1, 0.2, 0.2), is_animal=is_animal,
    )


def _config(**overrides) -> CaptureSessionConfig:
    defaults = dict(
        schema_version=1, capture_version="temporal-capture-session-v1", stream_id="s1",
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
