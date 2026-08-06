"""Hardware-free tests for the Stage 6.6 annotation schema, validation,
active-learning classification, dataset statistics, and benchmark export
transforms. No filesystem I/O, CUDA, or product database is touched.
Numbered sections mirror the task's required hardware-free-test list.
"""
from __future__ import annotations

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
    V_APPEARANCE_INTERVAL_REVERSED,
    V_CAPTURE_FINGERPRINT_MISMATCH,
    V_NEGATIVE_FRAME_HAS_POSITIVE_BOXES,
    V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE,
    V_SCORABLE_YES_REQUIRES_BOX,
    V_STALE_GENERATION_EVIDENCE,
    V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS,
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
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
    CaptureBounds,
    CaptureSessionConfig,
    CaptureSessionManifest,
    RetainedFrameRecord,
    STOP_DURATION_ELAPSED,
)


def _config(**overrides) -> CaptureSessionConfig:
    defaults = dict(
        schema_version=1, capture_version="temporal-capture-session-v1", stream_id="s1",
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
    session = _session((_record("f1", 0, 0), _record("f2", 1, 1000)), end_source_offset_ms=1000)
    annotations = AnnotationSet(1, "session-1", session["semantic_fingerprint"], (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
        FrameAnnotation("f2", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),)),
    ), appearances=(AppearanceInterval("a1", "f1", "f2"),))
    # Force an out-of-bounds appearance by referencing a frame beyond duration.
    session["end_source_offset_ms"] = 500
    report = validate_annotations(session, annotations)
    assert any(item.code == V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS for item in report.issues)


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
    assert export["temporal_sequences"][0]["source_offset_ms_range"] == [0, 2000]


def test_replay_export_produces_frame_indices_and_evidence_facts() -> None:
    session, annotations = _reviewed_pair()
    export = build_replay_export(session, annotations)
    assert len(export["frames"]) == 2
    assert export["appearances"] == [{"appearance_id": "a1", "start_offset_ms": 0, "end_offset_ms": 0, "outcome": None, "ambiguous": False}]
    assert export["detections"][0]["frame_index"] == 0
    assert export["visits"] == []  # no invented Visit grouping


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
            ReplayFrame(
                item["index"], item["source_offset_ms"], item["content_hash"], item["path"],
                tuple(tuple(box) for box in item.get("analysis_excluded_regions", ())),
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
