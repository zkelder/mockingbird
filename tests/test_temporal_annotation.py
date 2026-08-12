"""Hardware-free tests for the Stage 6.6 annotation schema, validation,
active-learning classification, dataset statistics, and benchmark export
transforms. No filesystem I/O, CUDA, or product database is touched.
Numbered sections mirror the task's required hardware-free-test list.
"""
from __future__ import annotations

import json

import pytest

from mockingbird.observation.temporal_annotation import (
    AL_AMBIGUOUS_TRUTH,
    AL_BELOW_THRESHOLD_TRUE_POSITIVE,
    AL_FALSE_NEGATIVE,
    AL_FALSE_POSITIVE,
    AL_HOLD_FOR_REVIEW,
    AL_TRUE_POSITIVE,
    AL_USEFUL_TRAINING_NEGATIVE,
    AL_USEFUL_TRAINING_POSITIVE,
    DIFFICULTY_TAGS,
    DIFFICULTY_TAG_FAR,
    DIFFICULTY_TAG_VERY_SMALL,
    V_APPEARANCE_INTERVAL_REVERSED,
    V_CAPTURE_FINGERPRINT_MISMATCH,
    V_EXCESSIVE_DISCONTINUITY_UNMARKED,
    V_MISSING_SESSION_TIMELINE,
    V_NEGATIVE_FRAME_HAS_POSITIVE_BOXES,
    V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE,
    V_SCORABLE_YES_REQUIRES_BOX,
    V_STALE_GENERATION_EVIDENCE,
    V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS,
    VISIT_TRUTH_EXCLUDED_AMBIGUOUS_TRUTH,
    VISIT_TRUTH_EXCLUDED_INVALID_ENDPOINT,
    VISIT_TRUTH_EXCLUDED_REVERSED_INTERVAL,
    VISIT_TRUTH_EXCLUDED_UNRESOLVED_CONTINUITY,
    VISIT_TRUTH_EXCLUDED_UNSCORABLE_TRUTH,
    AnnotationSet,
    AppearanceInterval,
    BoxAnnotation,
    FrameAnnotation,
    Provenance,
    TemporalAnnotationError,
    build_detector_calibration_export,
    build_motion_proposal_export,
    build_replay_export,
    classify_active_learning,
    classify_export_sufficiency,
    compute_dataset_statistics,
    validate_annotations,
)
from mockingbird.observation.temporal_capture import (
    CAPTURE_MANIFEST_SCHEMA_VERSION,
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
    CaptureBounds,
    CaptureSessionConfig,
    CaptureSessionManifest,
    RetainedFrameRecord,
    STOP_DURATION_ELAPSED,
)


def _config(**overrides) -> CaptureSessionConfig:
    defaults = dict(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1", stream_id="s1",
        transport_key="camera-node-http-multipart-jpeg", provider_key="frame-driven-onnx-cuda",
        analysis_width=1000, analysis_height=1000, nominal_fps=2.0, review_score_threshold=0.02,
        shadow_operating_point=0.5, review_floor=0.1, evidence_profile_id="profile-1", bounds=CaptureBounds(),
    )
    defaults.update(overrides)
    return CaptureSessionConfig(**defaults)


def _record(frame_id, sequence, offset_ms, **overrides) -> RetainedFrameRecord:
    defaults = dict(
        frame_id=frame_id, sequence=sequence, source_offset_ms=offset_ms, provider_generation="gen-1",
        content_hash="h" * 64, byte_size=1000, trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,),
        detector_observation_count=0, animal_detection_count=0, max_animal_score=None,
        active_track_count=0, motion_proposal_count=0,
        # Stage 6.8: `validate_annotations` reads the derived session
        # timeline, not the raw source-local fields above. Most existing
        # fixtures describe one single connection, so the sensible default
        # mirrors `session_offset_ms` onto the same value as
        # `source_offset_ms` and keeps every record in one shared segment;
        # a test that specifically wants cross-reconnect behavior overrides
        # `session_offset_ms`/`connection_segment_id` explicitly.
        session_offset_ms=offset_ms, connection_segment_id="segment-1",
    )
    defaults.update(overrides)
    return RetainedFrameRecord(**defaults)


def _session(frames, **overrides) -> dict:
    defaults = dict(
        config=_config(), session_id="session-1", node_session_id="node-session-1",
        start_host_time_iso="2026-08-05T20:00:00+00:00", end_host_time_iso="2026-08-05T20:01:00+00:00",
        start_source_offset_ms=0, end_source_offset_ms=2000, first_sequence=0, last_sequence=1,
        sequence_gap_count=0, dropped_frame_count=0, coalesced_frame_count=0, stale_frame_count=0,
        generation_reset_count=0, provider_generations=("gen-1",), model_fingerprint="model-fp",
        tracker_proposal_config_fingerprint="cfg-fp", frames=frames, operator_markers=(),
        stop_condition=STOP_DURATION_ELAPSED,
    )
    defaults.update(overrides)
    manifest = CaptureSessionManifest(**defaults)
    document = manifest.to_semantic_dict()
    document["semantic_fingerprint"] = manifest.fingerprint
    return document


def _yes_annotation(frame_id: str) -> FrameAnnotation:
    return FrameAnnotation(frame_id, whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),))


def _provenance(**overrides) -> Provenance:
    defaults = dict(reviewer="alice", reviewed_at_iso="2026-08-05T20:05:00+00:00", source_capture_session="session-1", truth_source="full_frame_inspection")
    defaults.update(overrides)
    return Provenance(**defaults)


# --------------------------------------------------------------------------
# 18. Annotation schema validation (basic construction rules)
# --------------------------------------------------------------------------


def test_box_annotation_rejects_a_box_outside_image_bounds() -> None:
    with pytest.raises(TemporalAnnotationError):
        BoxAnnotation((0.1, 0.1, 1.5, 0.5))


def test_frame_annotation_rejects_an_unknown_whole_frame_truth() -> None:
    with pytest.raises(TemporalAnnotationError):
        FrameAnnotation("f1", whole_frame_truth="maybe")  # type: ignore[arg-type]


def test_provenance_rejects_an_unknown_truth_source() -> None:
    with pytest.raises(TemporalAnnotationError):
        Provenance("alice", "2026-08-05T20:05:00", "session-1", "guessed")  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 19. Whole-frame negative cannot contain positive boxes
# --------------------------------------------------------------------------


def test_negative_frame_with_a_box_is_rejected() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="no", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ))
    report = validate_annotations(session, annotations)
    assert report.ok is False
    assert any(item.code == V_NEGATIVE_FRAME_HAS_POSITIVE_BOXES for item in report.issues)


def test_yes_frame_without_a_box_or_unscorable_flag_is_rejected() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes"),
    ))
    report = validate_annotations(session, annotations)
    assert report.ok is False
    assert any(item.code == V_SCORABLE_YES_REQUIRES_BOX for item in report.issues)


def test_yes_but_unscorable_frame_without_a_box_is_accepted() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", yes_but_unscorable=True),
    ))
    report = validate_annotations(session, annotations)
    assert report.ok is True


# --------------------------------------------------------------------------
# 20. Ambiguous frames excluded from scoring
# --------------------------------------------------------------------------


def test_ambiguous_frame_is_flagged_not_rejected_and_excluded_from_scorable_count() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="ambiguous"),
    ))
    report = validate_annotations(session, annotations)
    assert report.ok is True
    assert report.ambiguous_frame_count == 1
    assert report.scorable_frame_count == 0


def test_ambiguous_frame_exports_as_ambiguous_for_downstream_denominator_exclusion() -> None:
    # Ambiguous frames ARE reviewed (a definite "ambiguous" truth value), so
    # the exporter includes them -- exclusion from precision/recall
    # denominators is the existing detector_benchmark pipeline's own job at
    # scoring time (see detector-calibration-benchmark-contract.md), not the
    # exporter's. This matches the established Stage 6.2 cohort convention.
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="ambiguous"),
        FrameAnnotation("f2", whole_frame_truth="no"),
    ))
    export = build_detector_calibration_export(session, annotations, scene_group="scene-1")
    assert len(export["frames"]) == 2
    truths = {item["animal_present"] for item in export["frames"]}
    assert truths == {"ambiguous", "no"}


# --------------------------------------------------------------------------
# 21. Visit-level false-positive label does not become frame-level negative
# --------------------------------------------------------------------------


def test_product_false_positive_used_as_negative_without_confirmation_is_rejected() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="no", provenance=_provenance(
            truth_source="product_review_record", product_review_label="false_positive", whole_frame_independently_confirmed=False,
        )),
    ))
    report = validate_annotations(session, annotations)
    assert report.ok is False
    assert any(item.code == V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE for item in report.issues)


def test_product_false_positive_with_independent_confirmation_is_accepted() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="no", provenance=_provenance(
            truth_source="product_review_record", product_review_label="false_positive", whole_frame_independently_confirmed=True,
        )),
    ))
    report = validate_annotations(session, annotations)
    assert report.ok is True


# --------------------------------------------------------------------------
# 22. Temporal interval validation
# --------------------------------------------------------------------------


def test_appearance_interval_outside_the_session_duration_is_rejected() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    # The session-timeline bound comes from every retained frame's own
    # session_offset_ms, not a separately-settable top-level field (which
    # would itself be another source-local-style fact, not authoritative) --
    # simulate corrupted/impossible provenance directly on the referenced
    # frame's own derived coordinate instead.
    session["frames"][1]["session_offset_ms"] = -100
    report = validate_annotations(session, annotations)
    assert any(item.code == V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS for item in report.issues)


# --------------------------------------------------------------------------
# Stage 6.8: cross-reconnect appearance-interval validation
# --------------------------------------------------------------------------


def test_appearance_interval_reversed_by_a_reconnect_reset_alone_still_validates() -> None:
    # f1 is the last, high-offset frame of connection segment A; f2 is the
    # first, near-zero-offset frame of segment B, genuinely *later* in the
    # session despite its lower connection-local source_offset_ms. Only the
    # (correctly monotonic) session_offset_ms should decide ordering.
    session = _session((
        _record("f1", 12, 6825, connection_segment_id="segment-a", session_offset_ms=6825),
        _record("f2", 1, 0, connection_segment_id="segment-b", session_offset_ms=6830),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    report = validate_annotations(session, annotations)
    assert report.ok is True
    assert not any(item.code == V_APPEARANCE_INTERVAL_REVERSED for item in report.issues)


def test_short_span_across_a_reconnect_boundary_validates_without_continuity_ambiguous() -> None:
    session = _session((
        _record("f1", 12, 6825, connection_segment_id="segment-a", session_offset_ms=6825),
        _record("f2", 1, 0, connection_segment_id="segment-b", session_offset_ms=6900),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    report = validate_annotations(session, annotations)
    assert report.ok is True


def test_excessive_span_across_a_reconnect_boundary_requires_continuity_ambiguous() -> None:
    session = _session((
        _record("f1", 12, 1000, connection_segment_id="segment-a", session_offset_ms=1000),
        _record("f2", 1, 0, connection_segment_id="segment-b", session_offset_ms=60_000),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    report = validate_annotations(session, annotations)
    assert not report.ok
    assert any(item.code == V_EXCESSIVE_DISCONTINUITY_UNMARKED for item in report.issues)


def test_excessive_span_across_a_reconnect_boundary_validates_when_marked_continuity_ambiguous() -> None:
    session = _session((
        _record("f1", 12, 1000, connection_segment_id="segment-a", session_offset_ms=1000),
        _record("f2", 1, 0, connection_segment_id="segment-b", session_offset_ms=60_000),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2", continuity_ambiguous=True),))
    report = validate_annotations(session, annotations)
    assert report.ok is True
    assert not any(item.code == V_EXCESSIVE_DISCONTINUITY_UNMARKED for item in report.issues)


def test_instantaneous_appearance_within_one_segment_validates() -> None:
    session = _session((_record("f1", 1, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f1", instantaneous=True),))
    report = validate_annotations(session, annotations)
    assert report.ok is True


def test_appearance_on_a_manifest_with_insufficient_temporal_provenance_is_rejected() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    session["session_timeline_classification"] = "insufficient_temporal_provenance"
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    report = validate_annotations(session, annotations)
    assert not report.ok
    assert any(item.code == V_MISSING_SESSION_TIMELINE for item in report.issues)


def test_appearance_interval_with_reversed_times_is_rejected() -> None:
    session = _session((_record("f1", 0, 1000), _record("f2", 1, 0)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    report = validate_annotations(session, annotations)
    assert any(item.code == V_APPEARANCE_INTERVAL_REVERSED for item in report.issues)


# --------------------------------------------------------------------------
# 23. Same versus separate appearance annotation
# --------------------------------------------------------------------------


def test_overlapping_appearances_without_continuity_ambiguous_are_flagged() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 500), _record("f3", 2, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (_yes_annotation("f1"), _yes_annotation("f2"), _yes_annotation("f3")), appearances=(
        AppearanceInterval("a1", "f1", "f2"), AppearanceInterval("a2", "f2", "f3"),
    ))
    report = validate_annotations(session, annotations)
    assert report.ok is True  # a flag, not a rejection
    assert any(item.code == "overlapping_appearance_continuity_unmarked" for item in report.issues)


def test_overlapping_appearances_with_continuity_ambiguous_are_not_flagged() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 500), _record("f3", 2, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (_yes_annotation("f1"), _yes_annotation("f2"), _yes_annotation("f3")), appearances=(
        AppearanceInterval("a1", "f1", "f2", continuity_ambiguous=True), AppearanceInterval("a2", "f2", "f3"),
    ))
    report = validate_annotations(session, annotations)
    assert not any(item.code == "overlapping_appearance_continuity_unmarked" for item in report.issues)


# --------------------------------------------------------------------------
# 24. Stale-generation evidence rejection
# --------------------------------------------------------------------------


def test_appearance_spanning_a_generation_reset_is_rejected() -> None:
    session = _session((_record("f1", 0, 0, provider_generation="gen-1"), _record("f2", 1, 1000, provider_generation="gen-2")))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    report = validate_annotations(session, annotations)
    assert any(item.code == V_STALE_GENERATION_EVIDENCE for item in report.issues)


# --------------------------------------------------------------------------
# 25. Content-hash verification
# --------------------------------------------------------------------------


def test_missing_source_media_is_rejected() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (FrameAnnotation("f1", whole_frame_truth="no"),))
    report = validate_annotations(session, annotations, actual_content_hash=lambda fid: None)
    assert report.ok is False
    assert any(item.code == "missing_source_media" for item in report.issues)


def test_content_hash_mismatch_is_rejected() -> None:
    session = _session((_record("f1", 0, 0, content_hash="a" * 64),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (FrameAnnotation("f1", whole_frame_truth="no"),))
    report = validate_annotations(session, annotations, actual_content_hash=lambda fid: "b" * 64)
    assert report.ok is False
    assert any(item.code == "content_hash_mismatch" for item in report.issues)


def test_matching_content_hash_is_accepted() -> None:
    session = _session((_record("f1", 0, 0, content_hash="a" * 64),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (FrameAnnotation("f1", whole_frame_truth="no"),))
    report = validate_annotations(session, annotations, actual_content_hash=lambda fid: "a" * 64)
    assert report.ok is True


def test_capture_manifest_fingerprint_mismatch_is_rejected() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", "the-wrong-fingerprint", (FrameAnnotation("f1", whole_frame_truth="no"),))
    report = validate_annotations(session, annotations)
    assert any(item.code == V_CAPTURE_FINGERPRINT_MISMATCH for item in report.issues)


# --------------------------------------------------------------------------
# 26-28. Export transforms
# --------------------------------------------------------------------------


def _reviewed_pair():
    session = _session((
        _record("f1", 0, 0, animal_detection_count=1, detector_observation_count=1, max_animal_score=0.8),
        _record("f2", 1, 1000, animal_detection_count=0),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.3, 0.3, 0.5, 0.5)),), provenance=_provenance()),
        FrameAnnotation("f2", whole_frame_truth="no", provenance=_provenance()),
    ), appearances=(AppearanceInterval("a1", "f1", "f1", instantaneous=True),))
    return session, annotations


def test_detector_calibration_export_matches_the_existing_schema_fields() -> None:
    session, annotations = _reviewed_pair()
    export = build_detector_calibration_export(session, annotations, scene_group="scene-1")
    assert export["version"] == 1
    assert {"cohort_id", "annotation_policy", "frames", "scene_static_structures"} <= export.keys()
    assert len(export["frames"]) == 2
    yes_frame = next(item for item in export["frames"] if item["animal_present"] == "yes")
    assert yes_frame["boxes"] == [{"box": [0.3, 0.3, 0.5, 0.5], "broad_class": "animal"}]
    assert yes_frame["scene_group"] == "scene-1"


def test_high_resolution_frame_export_omits_width_height_instead_of_declaring_the_wrong_analysis_dimensions() -> None:
    """A `high_resolution=True` retained frame's real decoded pixel
    dimensions come from the evidence-burst profile (typically larger than
    the analysis stream -- e.g. a 4624x3472 burst frame against a 1920x1440
    analysis stream), not `config.analysis_width`/`analysis_height`. Export
    previously declared every frame's `width`/`height` as the analysis
    dimensions unconditionally, including high-resolution ones: the very
    next real consumer, `detector_benchmark_io.load_calibration_manifest`
    (reused unchanged by detector-benchmark/multi-scale-benchmark/motion-
    proposal-benchmark), decodes the real file and rejects the whole
    manifest with `frame_dimensions_mismatch` the moment a declared
    dimension disagrees with reality -- making any Stage 6.6 export
    containing so much as one high-resolution frame unloadable by every
    benchmark it is meant to feed. Declaring no width/height for a
    high-resolution frame instead relies on that loader's own optional-
    declared-dimension contract (see docs/detector-calibration-benchmark-
    contract.md: "optional declared width/height/content_hash") to fall
    back to the real decoded size -- exactly the behavior that contract
    already promises, applied to the one case Stage 6.6 export skipped."""

    session = _session((
        _record("analysis-frame", 0, 0, high_resolution=False),
        _record("burst-frame", 1, 1000, high_resolution=True),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("analysis-frame", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),), provenance=_provenance()),
        FrameAnnotation("burst-frame", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),), provenance=_provenance()),
    ))

    export = build_detector_calibration_export(session, annotations, scene_group="scene-1")

    frames_by_id = {item["frame_id"]: item for item in export["frames"]}
    analysis_frame = frames_by_id["temporal-review:analysis-frame"]
    burst_frame = frames_by_id["temporal-review:burst-frame"]
    assert (analysis_frame["width"], analysis_frame["height"]) == (1000, 1000)
    assert burst_frame["width"] is None
    assert burst_frame["height"] is None


def test_motion_proposal_export_includes_real_sequencing() -> None:
    session, annotations = _reviewed_pair()
    export = build_motion_proposal_export(session, annotations, scene_group="scene-1")
    assert export["temporal_sequences"][0]["ordered_frame_ids"] == [item["frame_id"] for item in export["frames"]]
    # Grounded in the two real retained frames' own session_offset_ms (0 and
    # 1000), not an independently-settable top-level field that could
    # (and, before Stage 6.8, silently did) disagree with actual frame data.
    assert export["temporal_sequences"][0]["source_offset_ms_range"] == [0, 1000]
    assert export["temporal_sequences"][0]["connection_segment_count"] == 1


def test_replay_export_produces_frame_indices_and_evidence_facts() -> None:
    session, annotations = _reviewed_pair()
    export = build_replay_export(session, annotations)
    assert len(export["frames"]) == 2
    assert export["appearances"] == [{"appearance_id": "a1", "start_offset_ms": 0, "end_offset_ms": 0, "outcome": None, "ambiguous": False}]
    assert export["detections"][0]["frame_index"] == 0
    # Stage 6.17: the single reviewed, unambiguous, scorable appearance
    # interval deterministically becomes exactly one ExpectedVisit -- see
    # docs/reviewed-visit-truth-contract.md. No Visit grouping is invented:
    # this is a 1:1 conversion of the reviewer's own appearance interval.
    assert export["visits"] == [{
        "visit_id": "visit:a1", "appearance_ids": ["a1"], "start_offset_ms": 0, "end_offset_ms": 0,
        "outcome": None, "zone_id": None, "ambiguous": False, "broad_class": "animal",
        "entry_uncertain": False, "exit_uncertain": False, "source_capture_frame_ids": ["f1"], "reviewer": "alice",
    }]
    assert export["visit_truth_exclusions"] == []


def test_replay_export_matches_the_flat_top_level_schema_replay_io_actually_loads() -> None:
    """`replay_io.load_replay_bundle` reads `version`/`width`/`height`/
    `input_id`/`stream_id`/`nominal_fps`/`frames`/`input_fingerprint` at the
    JSON document's own top level (see the real fixture
    data/observation-replay-stage2-smoke/root-a/manifest.json) and each
    frame's image reference under the key `path` -- not nested under an
    `input` object, and not under a `source_path` key. `build_replay_export`
    previously nested those fields under `"input"` and omitted
    `input_fingerprint` entirely, so a real `temporal-review-export --target
    replay` output could never actually be loaded by `replay-benchmark`,
    the one command this export exists to feed. This test proves interop
    directly against the real Stage 2 `ReplayInput`/`BenchmarkManifest`
    types (pure, no filesystem) rather than merely re-asserting dict shape."""

    from mockingbird.observation.replay import BenchmarkManifest, ReplayFrame, ReplayInput

    session, annotations = _reviewed_pair()
    export = build_replay_export(session, annotations)

    assert "input" not in export
    assert all("path" in frame and "source_path" not in frame for frame in export["frames"])

    replay_input = ReplayInput(
        export["input_id"], export["stream_id"], export["width"], export["height"], export["nominal_fps"],
        tuple(
            # Mirrors exactly what replay_io.load_replay_bundle reads,
            # including the Stage 6.8 reconnect-safe provenance fields and
            # the Stage 6.14 reviewed-source-lineage fields.
            ReplayFrame(
                item["index"], item["source_offset_ms"], item["content_hash"], item["path"],
                tuple(tuple(box) for box in item.get("analysis_excluded_regions", ())),
                captured_at_iso=item.get("captured_at_iso"), source_sequence=item.get("source_sequence"),
                original_source_offset_ms=item.get("original_source_offset_ms"),
                connection_segment_id=item.get("connection_segment_id"),
                connection_segment_ordinal=item.get("connection_segment_ordinal"),
                provider_generation=item.get("provider_generation"),
                temporal_discontinuity=bool(item.get("temporal_discontinuity", False)),
                temporal_uncertainty_ms=item.get("temporal_uncertainty_ms"),
                source_capture_frame_id=item.get("source_capture_frame_id"),
                source_capture_session_id=item.get("source_capture_session_id"),
                session_sequence=item.get("session_sequence"),
            )
            for item in export["frames"]
        ),
    )
    manifest = BenchmarkManifest(
        export["version"], export["benchmark_id"], export["input_fingerprint"],
        appearances=(), visits=(), detections=(), evidence=(),
    )
    manifest.validate(replay_input)  # raises ReplayValidationError on any mismatch; must not raise


def test_replay_export_excludes_high_resolution_frames_and_their_evidence() -> None:
    """A `high_resolution=True` frame's real pixel size is the evidence-
    burst profile's, not the session's single analysis resolution every
    other retained frame shares, so `replay.ReplayInput` -- one ordered feed
    at one consistent resolution -- cannot honestly include it alongside
    them. `replay_io.load_replay_bundle` would hard-reject the whole export
    the moment it decoded that one larger file (no optional-dimension
    bypass exists for replay, unlike the calibration export). Excluding it
    is the only honest option; its own box/evidence facts are excluded too
    since they would otherwise reference an undefined replay frame index."""

    session = _session((
        _record("f1", 0, 0),
        _record("f2", 1, 1000, high_resolution=True),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),), provenance=_provenance()),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.3, 0.3, 0.4, 0.4)),), provenance=_provenance()),
    ))

    export = build_replay_export(session, annotations)

    assert [item["path"] for item in export["frames"]] == ["images/f1.jpg"]
    assert all(item["candidate_id"] != "f2" for item in export["evidence"])
    assert all(not item["annotation_id"].startswith("f2:") for item in export["detections"])
    # Exclusion is explicit and reported, never silent.
    assert export["high_resolution_exclusion"] == {
        "excluded_frame_count": 1, "excluded_frame_ids": ["f2"],
        "reason": "high_resolution_burst_frames_are_not_analysis_resolution",
    }


# --------------------------------------------------------------------------
# Stage 6.8: full-session replay export across a reconnect
# --------------------------------------------------------------------------


def _reconnect_session_and_annotations():
    """Two connection segments: segment-a ends at local sequence 12 /
    source_offset_ms 6825 (mirrors the real session-01 Stage 6.7 capture's
    own last frame), segment-b restarts at local sequence 1 / offset 0 --
    exactly the pattern that broke the pre-Stage-6.8 export."""

    session = _session((
        _record(
            "f1", 12, 6825, connection_segment_id="segment-a", connection_segment_ordinal=0,
            session_sequence=0, session_offset_ms=0, provider_generation="gen-1",
        ),
        _record(
            "f2", 1, 0, connection_segment_id="segment-b", connection_segment_ordinal=1,
            session_sequence=1, session_offset_ms=6826, temporal_discontinuity=True,
            temporal_uncertainty_ms=50, provider_generation="gen-1",
        ),
        _record(
            "f3", 2, 500, connection_segment_id="segment-b", connection_segment_ordinal=1,
            session_sequence=2, session_offset_ms=7326, provider_generation="gen-1",
        ),
    ), session_timeline_classification="native_session_timeline")
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),), provenance=_provenance()),
        FrameAnnotation("f2", whole_frame_truth="no", provenance=_provenance()),
        FrameAnnotation("f3", whole_frame_truth="yes", boxes=(BoxAnnotation((0.2, 0.2, 0.3, 0.3)),), provenance=_provenance()),
    ))
    return session, annotations


def test_replay_export_orders_by_session_timeline_across_a_reconnect() -> None:
    session, annotations = _reconnect_session_and_annotations()
    export = build_replay_export(session, annotations)
    assert [item["path"] for item in export["frames"]] == ["images/f1.jpg", "images/f2.jpg", "images/f3.jpg"]
    offsets = [item["source_offset_ms"] for item in export["frames"]]
    assert offsets == sorted(offsets) and len(set(offsets)) == 3


def test_replay_export_full_session_loads_through_the_real_ordered_timestamps_check() -> None:
    """The exact defect this task fixes: a full multi-reconnect session must
    load as one ordered `ReplayInput` without `ordered_timestamps` failing
    and without manually selecting a single connection-safe sub-window."""

    from mockingbird.observation.replay import ReplayFrame, ReplayInput

    session, annotations = _reconnect_session_and_annotations()
    export = build_replay_export(session, annotations)
    # ReplayInput.__post_init__ raises ReplayValidationError("ordered_timestamps")
    # on any non-strictly-increasing source_offset_ms; constructing it here
    # without that exception *is* the assertion.
    replay_input = ReplayInput(
        export["input_id"], export["stream_id"], export["width"], export["height"], export["nominal_fps"],
        tuple(
            ReplayFrame(
                item["index"], item["source_offset_ms"], item["content_hash"], item["path"],
                tuple(tuple(box) for box in item.get("analysis_excluded_regions", ())),
                connection_segment_id=item.get("connection_segment_id"),
                temporal_discontinuity=bool(item.get("temporal_discontinuity", False)),
            )
            for item in export["frames"]
        ),
    )
    assert len(replay_input.frames) == 3


def test_replay_export_preserves_original_source_local_provenance_across_a_reconnect() -> None:
    session, annotations = _reconnect_session_and_annotations()
    export = build_replay_export(session, annotations)
    by_path = {item["path"]: item for item in export["frames"]}
    boundary = by_path["images/f2.jpg"]
    assert boundary["original_source_offset_ms"] == 0  # the real, reset, connection-local value
    assert boundary["source_sequence"] == 1
    assert boundary["connection_segment_id"] == "segment-b"
    assert boundary["temporal_discontinuity"] is True


def test_repeated_replay_export_produces_an_identical_fingerprint() -> None:
    session, annotations = _reconnect_session_and_annotations()
    first = build_replay_export(session, annotations)
    second = build_replay_export(session, annotations)
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first == second


def test_replay_export_refuses_a_manifest_with_insufficient_temporal_provenance() -> None:
    session, annotations = _reviewed_pair()
    session["session_timeline_classification"] = "insufficient_temporal_provenance"
    with pytest.raises(TemporalAnnotationError, match="replay_export_requires_session_timeline"):
        build_replay_export(session, annotations)


# --------------------------------------------------------------------------
# Stage 6.14: reviewed-to-replay evidence identity lineage
# --------------------------------------------------------------------------


def test_replay_export_places_the_reviewed_frame_id_into_the_replay_frame_lineage_contract() -> None:
    """(1, 20/22 cross-check) `build_replay_export` explicitly places the
    original reviewed `frame_id` -- what a human annotation actually refers
    to -- into each exported replay frame's own `source_capture_frame_id`,
    alongside the session identity and session-timeline sequence, rather
    than only implying it through the `path` string (never a valid join
    key). The Stage 6.8 high-resolution exclusion rule keeps applying
    unchanged: an excluded frame contributes no replay frame and therefore
    no source lineage entry either."""

    session = _session((
        _record("f1", 0, 0, session_sequence=0, session_offset_ms=0, animal_detection_count=1),
        _record("f2", 1, 1000, session_sequence=1, session_offset_ms=1000, animal_detection_count=0),
        _record("burst", 2, 1500, session_sequence=2, session_offset_ms=1500, high_resolution=True),
    ), session_id="session-lineage-1")
    annotations = AnnotationSet(1, "session-lineage-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.3, 0.3, 0.5, 0.5)),), provenance=_provenance()),
        FrameAnnotation("f2", whole_frame_truth="no", provenance=_provenance()),
    ))

    export = build_replay_export(session, annotations)

    assert len(export["frames"]) == 2  # the high-resolution burst frame stays excluded, unchanged
    by_index = {item["index"]: item for item in export["frames"]}
    assert by_index[0]["source_capture_frame_id"] == "f1"
    assert by_index[0]["source_capture_session_id"] == "session-lineage-1"
    assert by_index[0]["session_sequence"] == 0
    assert by_index[1]["source_capture_frame_id"] == "f2"
    assert by_index[1]["source_capture_session_id"] == "session-lineage-1"
    assert by_index[1]["session_sequence"] == 1
    # Distinct identity spaces: the replay-frame `path`/`index` are never
    # the join key, and the original frame_id is not derivable from them
    # without this explicit field.
    assert by_index[0]["path"] == "images/f1.jpg"


def test_replay_export_source_lineage_survives_alongside_privacy_ignore_regions() -> None:
    """(23) Reviewed source lineage and the existing Privacy/Ignore
    `analysis_excluded_regions` export are independent, both-present facts
    on the same exported frame -- neither addition displaced the other."""

    session = _session(
        (_record("f1", 0, 0, session_sequence=0, session_offset_ms=0),),
        session_id="session-privacy-1",
        config=_config(privacy_ignore_regions=((0.1, 0.1, 0.4, 0.4),)),
    )
    annotations = AnnotationSet(1, "session-privacy-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.5, 0.5, 0.6, 0.6)),), provenance=_provenance()),
    ))
    export = build_replay_export(session, annotations)
    frame = export["frames"][0]
    assert list(frame["analysis_excluded_regions"][0]) == [0.1, 0.1, 0.4, 0.4]
    assert frame["source_capture_frame_id"] == "f1"
    assert frame["source_capture_session_id"] == "session-privacy-1"


# --------------------------------------------------------------------------
# Stage 6.17: reviewed appearance intervals as deterministic replay Visit
# truth -- see docs/reviewed-visit-truth-contract.md. Numbered comments below
# mirror this stage's own required hardware-free-test list.
# --------------------------------------------------------------------------


def _yes_box(frame_id: str, *, broad_class: str = "animal", reviewer: str = "alice",
             box: tuple[float, float, float, float] = (0.1, 0.1, 0.2, 0.2)) -> FrameAnnotation:
    return FrameAnnotation(
        frame_id, whole_frame_truth="yes", boxes=(BoxAnnotation(box, broad_class=broad_class),),
        provenance=_provenance(reviewer=reviewer),
    )


def _reconnect_session_with_appearance():
    """Same two-segment reconnect shape as `_reconnect_session_and_annotations`
    above, with one reviewed appearance spanning the reconnect boundary."""

    session = _session((
        _record(
            "f1", 12, 6825, connection_segment_id="segment-a", connection_segment_ordinal=0,
            session_sequence=0, session_offset_ms=0, provider_generation="gen-1",
        ),
        _record(
            "f2", 1, 0, connection_segment_id="segment-b", connection_segment_ordinal=1,
            session_sequence=1, session_offset_ms=6826, temporal_discontinuity=True,
            temporal_uncertainty_ms=50, provider_generation="gen-1",
        ),
        _record(
            "f3", 2, 500, connection_segment_id="segment-b", connection_segment_ordinal=1,
            session_sequence=2, session_offset_ms=7326, provider_generation="gen-1",
        ),
    ), session_timeline_classification="native_session_timeline")
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), FrameAnnotation("f2", whole_frame_truth="no", provenance=_provenance()), _yes_box("f3"),
    ), appearances=(AppearanceInterval("a1", "f1", "f3"),))
    return session, annotations


def _overlapping_session(*, first_ambiguous: bool = False, second_ambiguous: bool = False):
    session = _session((
        _record("f1", 0, 0), _record("f2", 1, 1000), _record("f3", 2, 2000), _record("f4", 3, 3000),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), _yes_box("f2"), _yes_box("f3"), _yes_box("f4"),
    ), appearances=(
        AppearanceInterval("a1", "f1", "f3", continuity_ambiguous=first_ambiguous),
        AppearanceInterval("a2", "f2", "f4", continuity_ambiguous=second_ambiguous),
    ))
    return session, annotations


# 1. One reviewed interval creates one ExpectedVisit.
def test_one_reviewed_appearance_interval_creates_exactly_one_expected_visit() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), _yes_box("f2"),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    export = build_replay_export(session, annotations)
    assert len(export["visits"]) == 1
    visit = export["visits"][0]
    assert visit["visit_id"] == "visit:a1"
    assert visit["appearance_ids"] == ["a1"]
    assert visit["start_offset_ms"] == 0 and visit["end_offset_ms"] == 1000
    assert export["visit_truth_exclusions"] == []


# 2. Two separate reviewed intervals create two ExpectedVisits.
def test_two_separate_reviewed_appearance_intervals_create_two_expected_visits() -> None:
    session = _session((
        _record("f1", 0, 0), _record("f2", 1, 1000), _record("f3", 2, 5000), _record("f4", 3, 6000),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), _yes_box("f2"), _yes_box("f3"), _yes_box("f4"),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"), AppearanceInterval("a2", "f3", "f4")))
    export = build_replay_export(session, annotations)
    assert {item["visit_id"] for item in export["visits"]} == {"visit:a1", "visit:a2"}
    assert {tuple(item["appearance_ids"]) for item in export["visits"]} == {("a1",), ("a2",)}


# 3. Instantaneous reviewed appearance is supported.
def test_instantaneous_reviewed_appearance_creates_a_zero_duration_visit() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"),
    ), appearances=(AppearanceInterval("a1", "f1", "f1", instantaneous=True),))
    export = build_replay_export(session, annotations)
    assert export["visits"] == [{
        "visit_id": "visit:a1", "appearance_ids": ["a1"], "start_offset_ms": 0, "end_offset_ms": 0,
        "outcome": None, "zone_id": None, "ambiguous": False, "broad_class": "animal",
        "entry_uncertain": False, "exit_uncertain": False, "source_capture_frame_ids": ["f1"], "reviewer": "alice",
    }]


# 4. Ambiguous interval does not export.
def test_appearance_with_an_ambiguous_endpoint_frame_does_not_export_a_visit() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="ambiguous"), _yes_box("f2"),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    export = build_replay_export(session, annotations)
    assert export["visits"] == []
    assert export["visit_truth_exclusions"] == [{"appearance_id": "a1", "reason": VISIT_TRUTH_EXCLUDED_AMBIGUOUS_TRUTH}]
    # The exclusion is Visit-level only: the appearance interval itself is
    # still honestly reported as an ExpectedAppearance.
    assert len(export["appearances"]) == 1


# 5. Unscorable interval does not export.
def test_appearance_with_a_yes_but_unscorable_endpoint_does_not_export_a_visit() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"),
        FrameAnnotation("f2", whole_frame_truth="yes", yes_but_unscorable=True, provenance=_provenance()),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    export = build_replay_export(session, annotations)
    assert export["visits"] == []
    assert export["visit_truth_exclusions"] == [{"appearance_id": "a1", "reason": VISIT_TRUTH_EXCLUDED_UNSCORABLE_TRUTH}]


# 6. Reconnect-spanning interval exports in session-relative order.
def test_reconnect_spanning_appearance_exports_a_visit_in_session_relative_order() -> None:
    session, annotations = _reconnect_session_with_appearance()
    export = build_replay_export(session, annotations)
    assert len(export["visits"]) == 1
    visit = export["visits"][0]
    assert visit["start_offset_ms"] == 0     # f1's session-relative offset
    assert visit["end_offset_ms"] == 7326    # f3's session-relative offset


# 7. Source-local offset resets do not corrupt Visit truth.
def test_source_local_offset_reset_across_a_reconnect_does_not_corrupt_visit_bounds() -> None:
    session, annotations = _reconnect_session_with_appearance()
    export = build_replay_export(session, annotations)
    visit = export["visits"][0]
    # f3's raw, connection-local source_offset_ms (500) is lower than f1's
    # (6825) purely because its connection reset; the exported Visit must use
    # the reconnect-safe session-relative coordinate, never the raw one.
    assert visit["start_offset_ms"] < visit["end_offset_ms"]


# 8. Same-vs-separate review is respected.
def test_unresolved_overlapping_appearances_export_neither_visit() -> None:
    session, annotations = _overlapping_session()
    export = build_replay_export(session, annotations)
    assert export["visits"] == []
    reasons = {item["appearance_id"]: item["reason"] for item in export["visit_truth_exclusions"]}
    assert reasons == {"a1": VISIT_TRUTH_EXCLUDED_UNRESOLVED_CONTINUITY, "a2": VISIT_TRUTH_EXCLUDED_UNRESOLVED_CONTINUITY}


def test_overlap_acknowledged_with_continuity_ambiguous_exports_both_as_separate_visits() -> None:
    session, annotations = _overlapping_session(first_ambiguous=True)
    export = build_replay_export(session, annotations)
    assert {item["visit_id"] for item in export["visits"]} == {"visit:a1", "visit:a2"}
    assert export["visit_truth_exclusions"] == []


# 9. Reviewed broad class preserved.
def test_visit_preserves_the_reviewed_broad_class() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1", broad_class="bird"),
    ), appearances=(AppearanceInterval("a1", "f1", "f1", instantaneous=True),))
    export = build_replay_export(session, annotations)
    assert export["visits"][0]["broad_class"] == "bird"


# 10. Missing broad class remains honest/optional.
def test_visit_without_any_reviewed_box_leaves_broad_class_none() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(), provenance=_provenance()),
    ), appearances=(AppearanceInterval("a1", "f1", "f1", instantaneous=True),))
    export = build_replay_export(session, annotations)
    assert len(export["visits"]) == 1
    assert export["visits"][0]["broad_class"] is None


# 11. Reviewed Zone preserved only when explicit.
def test_visit_zone_id_preserved_only_when_explicitly_reviewed() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), _yes_box("f2"),
    ), appearances=(
        AppearanceInterval("a1", "f1", "f1", instantaneous=True, zone_id="feeder-zone"),
        AppearanceInterval("a2", "f2", "f2", instantaneous=True),
    ))
    export = build_replay_export(session, annotations)
    by_id = {item["visit_id"]: item for item in export["visits"]}
    assert by_id["visit:a1"]["zone_id"] == "feeder-zone"
    assert by_id["visit:a2"]["zone_id"] is None


# 12. No product Visit dependency.
def test_expected_visit_conversion_reads_nothing_but_the_annotation_set_and_capture_manifest() -> None:
    """A `session`/`annotations` pair carrying no field that could plausibly
    be a product Visit record still exports the Visit correctly -- proving
    conversion never depends on one existing. See also the module-wide
    source-grep test asserting no product-repository import at all
    (test_stage_6_6_modules_never_reference_product_truth_tables)."""

    session = _session((_record("f1", 0, 0),))
    assert "visit_id" not in session and "product_visit_id" not in session
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"),
    ), appearances=(AppearanceInterval("a1", "f1", "f1", instantaneous=True),))
    export = build_replay_export(session, annotations)
    assert len(export["visits"]) == 1


# 13. Frame-level positive alone does not create ExpectedVisit.
def test_frame_level_yes_truth_without_an_appearance_interval_creates_no_visit() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (_yes_box("f1"),))  # no appearances
    assert build_replay_export(session, annotations)["visits"] == []


# 14. Detector output alone does not create ExpectedVisit.
def test_strong_detector_output_alone_creates_no_visit() -> None:
    session = _session((
        _record("f1", 0, 0, animal_detection_count=3, detector_observation_count=3, max_animal_score=0.95),
    ))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="unreviewed"),
    ))
    assert build_replay_export(session, annotations)["visits"] == []


# 15. Track output alone does not create ExpectedVisit.
def test_active_track_count_alone_creates_no_visit() -> None:
    session = _session((_record("f1", 0, 0, active_track_count=4),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="unreviewed"),
    ))
    assert build_replay_export(session, annotations)["visits"] == []


# 16. Product false_positive label cannot create or suppress ExpectedVisit.
def test_product_false_positive_label_neither_creates_nor_suppresses_a_visit() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    # f1 carries a product false_positive label but the reviewer
    # independently confirmed real animal presence anyway (the existing
    # V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE acceptance path).
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation(
            "f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),),
            provenance=Provenance("alice", "2026-08-05T20:05:00+00:00", "session-1", "full_frame_inspection",
                                   product_review_label="false_positive", whole_frame_independently_confirmed=True),
        ),
        _yes_box("f2"),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    export = build_replay_export(session, annotations)
    # The product label neither suppressed this eligible interval nor is it
    # what created the Visit -- the explicit AppearanceInterval did, wholly
    # independent of any product_review_label value.
    assert len(export["visits"]) == 1

    # Conversely: a product false_positive label alone, with no
    # AppearanceInterval at all, creates nothing either.
    no_appearance_annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation(
            "f1", whole_frame_truth="no",
            provenance=Provenance("alice", "2026-08-05T20:05:00+00:00", "session-1", "full_frame_inspection",
                                   product_review_label="false_positive"),
        ),
        FrameAnnotation("f2", whole_frame_truth="no", provenance=_provenance()),
    ))
    assert build_replay_export(session, no_appearance_annotations)["visits"] == []


# 17. Stable ExpectedVisit IDs.
def test_expected_visit_id_is_derived_from_the_appearance_id_only() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"),
    ), appearances=(AppearanceInterval("attempt3-appearance-feeder-bird", "f1", "f1", instantaneous=True),))
    export = build_replay_export(session, annotations)
    assert export["visits"][0]["visit_id"] == "visit:attempt3-appearance-feeder-bird"


# 18. Repeated export fingerprint identical.
def test_repeated_export_with_populated_visits_is_byte_identical() -> None:
    session, annotations = _reviewed_pair()
    first = build_replay_export(session, annotations)
    second = build_replay_export(session, annotations)
    assert first["visits"]
    assert first == second
    assert first["input_fingerprint"] == second["input_fingerprint"]


# 19. Different absolute roots produce identical semantic output.
def test_visit_export_is_identical_from_two_independent_absolute_roots(tmp_path) -> None:
    from mockingbird.observation.temporal_capture_io import load_capture_manifest, write_capture_manifest
    from mockingbird.observation.temporal_review_io import load_annotation_set, write_annotation_set

    session, annotations = _reviewed_pair()
    root_a = tmp_path / "root-a" / "nested" / "review"
    root_b = tmp_path / "completely" / "different" / "root-b" / "review"
    for root in (root_a, root_b):
        root.mkdir(parents=True)
        write_capture_manifest(root, session)
        write_annotation_set(root, annotations)

    export_a = build_replay_export(load_capture_manifest(root_a), load_annotation_set(root_a))
    export_b = build_replay_export(load_capture_manifest(root_b), load_annotation_set(root_b))
    assert export_a["visits"]
    assert export_a == export_b
    assert "root-a" not in json.dumps(export_a, default=str)
    assert "root-b" not in json.dumps(export_b, default=str)


# 20. Existing generic replay without Visit truth still works.
def test_generic_replay_manifest_with_empty_visits_still_validates() -> None:
    """A manifest that legitimately carries no Visit truth at all (a plain
    Stage 2 frame-directory benchmark, or a reviewed session with zero
    reviewed appearances) keeps working exactly as before: an empty `visits`
    list is a normal, well-supported case, not a defect."""

    from mockingbird.observation.replay import BenchmarkManifest, ReplayFrame, ReplayInput

    replay_input = ReplayInput("id", "stream", 4, 4, 1.0, (ReplayFrame(0, 0, "a"), ReplayFrame(1, 100, "b")))
    manifest = BenchmarkManifest(1, "generic", replay_input.fingerprint, appearances=(), visits=())
    manifest.validate(replay_input)  # must not raise


# 21. Old reviewed packets without intervals remain backward-compatible.
def test_old_annotation_json_without_appearances_or_zone_id_loads_and_exports_cleanly(tmp_path) -> None:
    from mockingbird.observation.temporal_capture_io import load_capture_manifest, write_capture_manifest
    from mockingbird.observation.temporal_review_io import load_annotation_set

    session = _session((_record("f1", 0, 0),))
    review_directory = tmp_path / "review"
    review_directory.mkdir()
    write_capture_manifest(review_directory, session)
    # Hand-written, pre-Stage-6.17 annotation.json: no "appearances" key at
    # all, and the one box never mentions a Zone (it didn't exist yet).
    (review_directory / "annotation.json").write_text(json.dumps({
        "schema_version": 1, "capture_session_id": "session-1",
        "capture_manifest_fingerprint": session["semantic_fingerprint"],
        "frames": [{
            "frame_id": "f1", "whole_frame_truth": "yes",
            "boxes": [{"box": [0.1, 0.1, 0.2, 0.2], "broad_class": "bird"}],
            "provenance": {"reviewer": "alice", "reviewed_at_iso": "2026-08-05T20:05:00+00:00",
                           "source_capture_session": "session-1", "truth_source": "full_frame_inspection"},
        }],
    }))
    annotations = load_annotation_set(review_directory)
    assert annotations.appearances == ()
    export = build_replay_export(load_capture_manifest(review_directory), annotations)
    assert export["visits"] == [] and export["visit_truth_exclusions"] == []


# 22. Invalid endpoint rejects.
def test_appearance_referencing_an_unknown_frame_does_not_export_a_visit() -> None:
    session = _session((_record("f1", 0, 0),))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"),
    ), appearances=(AppearanceInterval("a1", "f1", "does-not-exist"),))
    export = build_replay_export(session, annotations)
    assert export["visits"] == []
    assert export["visit_truth_exclusions"] == [{"appearance_id": "a1", "reason": VISIT_TRUTH_EXCLUDED_INVALID_ENDPOINT}]


# 23. Reversed interval rejects.
def test_reversed_appearance_interval_does_not_export_a_visit() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), _yes_box("f2"),
    ), appearances=(AppearanceInterval("a1", "f2", "f1"),))  # end before start
    export = build_replay_export(session, annotations)
    assert export["visits"] == []
    assert export["visit_truth_exclusions"] == [{"appearance_id": "a1", "reason": VISIT_TRUTH_EXCLUDED_REVERSED_INTERVAL}]


# 24. Duplicate interval identity rejects.
def test_duplicate_appearance_identity_raises_when_converting_to_visit_truth() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), _yes_box("f2"),
    ), appearances=(
        AppearanceInterval("a1", "f1", "f1", instantaneous=True), AppearanceInterval("a1", "f2", "f2", instantaneous=True),
    ))
    with pytest.raises(TemporalAnnotationError, match="duplicate_logical_identity"):
        build_replay_export(session, annotations)


# 25. Appearance uncertainty retained.
def test_visit_retains_entry_and_exit_uncertainty_flags() -> None:
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)))
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        _yes_box("f1"), _yes_box("f2"),
    ), appearances=(AppearanceInterval("a1", "f1", "f2", entry_uncertain=True, exit_uncertain=False),))
    export = build_replay_export(session, annotations)
    assert export["visits"][0]["entry_uncertain"] is True
    assert export["visits"][0]["exit_uncertain"] is False


# 26. Matcher receives exported Visits unchanged.
def test_matcher_consumes_an_exported_visit_exactly_as_produced() -> None:
    from mockingbird.observation.contracts import VisitProposal
    from mockingbird.observation.replay import Match, _match
    from mockingbird.observation.replay_io import _visit as load_expected_visit

    session, annotations = _reviewed_pair()
    export = build_replay_export(session, annotations)
    visit = load_expected_visit(export["visits"][0])
    assert visit.visit_id == "visit:a1"

    proposal = VisitProposal("proposal-1", "source", "stream", ("media",), "fake",
                             start_offset_ms=visit.start_offset_ms, end_offset_ms=visit.end_offset_ms)
    matches = _match((visit,), (proposal,))
    assert matches == (Match(visit.visit_id, "proposal-1", "matched"),)


# --------------------------------------------------------------------------
# 29. Stable active-learning classifications
# --------------------------------------------------------------------------


def test_true_positive_classification() -> None:
    record = {"detection_boxes": [(0.3, 0.3, 0.5, 0.5, 0.9)], "trigger_reasons": (), "motion_proposal_count": 0, "active_track_count": 1, "privacy_ignore_interaction": False}
    annotation = FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.3, 0.3, 0.5, 0.5)),))
    categories = classify_active_learning(record, annotation, shadow_operating_point=0.5)
    assert AL_TRUE_POSITIVE in categories
    assert AL_USEFUL_TRAINING_POSITIVE in categories


def test_below_threshold_true_positive_classification() -> None:
    record = {"detection_boxes": [(0.3, 0.3, 0.5, 0.5, 0.2)], "trigger_reasons": (), "motion_proposal_count": 0, "active_track_count": 0, "privacy_ignore_interaction": False}
    annotation = FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.3, 0.3, 0.5, 0.5)),))
    categories = classify_active_learning(record, annotation, shadow_operating_point=0.5)
    assert AL_BELOW_THRESHOLD_TRUE_POSITIVE in categories


def test_false_negative_classification() -> None:
    record = {"detection_boxes": [], "trigger_reasons": (), "motion_proposal_count": 0, "active_track_count": 0, "privacy_ignore_interaction": False}
    annotation = FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.3, 0.3, 0.5, 0.5)),))
    categories = classify_active_learning(record, annotation, shadow_operating_point=0.5)
    assert AL_FALSE_NEGATIVE in categories


def test_false_positive_classification() -> None:
    record = {"detection_boxes": [(0.3, 0.3, 0.5, 0.5, 0.9)], "trigger_reasons": (), "motion_proposal_count": 0, "active_track_count": 0, "privacy_ignore_interaction": False}
    annotation = FrameAnnotation("f1", whole_frame_truth="no")
    categories = classify_active_learning(record, annotation, shadow_operating_point=0.5)
    assert AL_FALSE_POSITIVE in categories


def test_useful_training_negative_classification() -> None:
    record = {"detection_boxes": [], "trigger_reasons": (), "motion_proposal_count": 0, "active_track_count": 0, "privacy_ignore_interaction": False}
    annotation = FrameAnnotation("f1", whole_frame_truth="no")
    categories = classify_active_learning(record, annotation, shadow_operating_point=0.5)
    assert AL_USEFUL_TRAINING_NEGATIVE in categories


def test_unreviewed_frame_is_hold_for_review() -> None:
    categories = classify_active_learning({}, FrameAnnotation("f1"), shadow_operating_point=0.5)
    assert categories == (AL_HOLD_FOR_REVIEW,)


def test_ambiguous_frame_is_ambiguous_truth_category() -> None:
    categories = classify_active_learning({}, FrameAnnotation("f1", whole_frame_truth="ambiguous"), shadow_operating_point=0.5)
    assert AL_AMBIGUOUS_TRUTH in categories


def test_active_learning_classification_is_deterministic() -> None:
    record = {"detection_boxes": [(0.3, 0.3, 0.5, 0.5, 0.9)], "trigger_reasons": (), "motion_proposal_count": 0, "active_track_count": 1, "privacy_ignore_interaction": False}
    annotation = FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.3, 0.3, 0.5, 0.5)),))
    first = classify_active_learning(record, annotation, shadow_operating_point=0.5)
    second = classify_active_learning(record, annotation, shadow_operating_point=0.5)
    assert first == second


# --------------------------------------------------------------------------
# 30. Dataset statistics and sufficiency
# --------------------------------------------------------------------------


def test_dataset_statistics_counts_are_honest_for_a_small_sample() -> None:
    session, annotations = _reviewed_pair()
    stats = compute_dataset_statistics((session,), (annotations,))
    assert stats.total_sessions == 1
    assert stats.reviewed_frame_count == 2
    assert stats.positive_frame_count == 1
    assert stats.negative_frame_count == 1
    assert stats.benchmark_sufficiency["detector_calibration"]["sufficient"] is False


def test_sufficiency_never_claims_sufficient_from_one_session() -> None:
    result = classify_export_sufficiency(100, 100, scene_groups=1, sequences=1)
    assert result["sufficient"] is False
    assert result["reasons"]


def test_sufficiency_passes_only_once_every_bound_clears() -> None:
    result = classify_export_sufficiency(25, 25, scene_groups=3, sequences=5)
    assert result["sufficient"] is True
    assert result["reasons"] == []


# --------------------------------------------------------------------------
# Stage-3: difficulty tags
# --------------------------------------------------------------------------


def test_difficulty_tags_default_empty_and_round_trip() -> None:
    frame = FrameAnnotation("f1", whole_frame_truth="no")
    assert frame.difficulty_tags == ()
    tagged = FrameAnnotation("f1", whole_frame_truth="no", difficulty_tags=(DIFFICULTY_TAG_VERY_SMALL, DIFFICULTY_TAG_FAR))
    assert tagged.difficulty_tags == (DIFFICULTY_TAG_VERY_SMALL, DIFFICULTY_TAG_FAR)


def test_difficulty_tags_reject_unknown_value() -> None:
    with pytest.raises(TemporalAnnotationError):
        FrameAnnotation("f1", whole_frame_truth="no", difficulty_tags=("not_a_real_tag",))


def test_difficulty_tags_reject_duplicates() -> None:
    with pytest.raises(TemporalAnnotationError):
        FrameAnnotation("f1", whole_frame_truth="no", difficulty_tags=(DIFFICULTY_TAG_FAR, DIFFICULTY_TAG_FAR))


def test_every_documented_difficulty_tag_is_individually_accepted() -> None:
    for tag in DIFFICULTY_TAGS:
        FrameAnnotation("f1", whole_frame_truth="no", difficulty_tags=(tag,))


def test_difficulty_tags_are_advisory_never_required_for_a_valid_negative() -> None:
    """A tag is optional review context, never a substitute for whole_frame_truth."""

    frame = FrameAnnotation("f1", whole_frame_truth="no")
    manifest = {"frames": [{"frame_id": "f1", "content_hash": "a" * 64}], "semantic_fingerprint": "fp"}
    annotations = AnnotationSet(1, "session-1", "fp", (frame,))
    report = validate_annotations(manifest, annotations)
    assert report.ok
