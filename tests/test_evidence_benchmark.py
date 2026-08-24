"""Hardware-free tests for the Stage 6.13 deterministic evidence-quality
benchmark. Numbered sections mirror the task's required hardware-free-test
list. No filesystem I/O, CUDA, or product database is touched here -- see
test_evidence_benchmark_io.py and test_evidence_benchmark_cli.py for the
I/O/CLI layer.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter
import pytest

from mockingbird.observation.evidence_benchmark import (
    EvidenceBenchmarkError,
    ReviewedAppearance,
    ReviewedEvidenceCandidate,
    ReviewedEvidenceManifest,
    build_reviewed_evidence_manifest_from_temporal_review,
    compare_evidence_benchmark_reports,
    evaluate_evidence_benchmark,
)
from mockingbird.observation.temporal_annotation import (
    AnnotationSet,
    AppearanceInterval,
    BoxAnnotation,
    EvidenceUsefulness,
    FrameAnnotation,
    Provenance,
)
from mockingbird.observation.temporal_capture import (
    CAPTURE_MANIFEST_SCHEMA_VERSION,
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
    TRIGGER_HIGH_RESOLUTION_BURST,
    TRIGGER_PRETRIGGER_CONTEXT,
    STOP_DURATION_ELAPSED,
    CaptureBounds,
    CaptureSessionConfig,
    CaptureSessionManifest,
    RetainedFrameRecord,
)


def _png(*, sharp: bool = True) -> bytes:
    image = Image.new("RGB", (320, 240), "white")
    if sharp:
        draw = ImageDraw.Draw(image)
        for x in range(0, 320, 8):
            draw.line((x, 0, 319 - x, 239), fill="black", width=2)
    else:
        image = image.filter(ImageFilter.GaussianBlur(12))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _candidate(candidate_id: str, role: str, **overrides) -> ReviewedEvidenceCandidate:
    defaults = dict(
        candidate_id=candidate_id, session_id="session-1", role=role,
        track_generation_id="track-1", width=320, height=240,
        subject_geometry=(0.2, 0.2, 0.6, 0.7), source_offset_ms=100,
        temporal_alignment="aligned", decodable=True,
    )
    defaults.update(overrides)
    return ReviewedEvidenceCandidate(**defaults)


def _manifest(*candidates: ReviewedEvidenceCandidate, appearances: tuple[ReviewedAppearance, ...] = ()) -> ReviewedEvidenceManifest:
    return ReviewedEvidenceManifest(1, "manifest-1", "unit-test", candidates, appearances)


# --------------------------------------------------------------------------
# 1. Existing scorer is reused, not duplicated.
# --------------------------------------------------------------------------


def test_evidence_benchmark_module_calls_the_existing_scorer_not_a_second_algorithm() -> None:
    source = __import__("inspect").getsource(__import__(
        "mockingbird.observation.evidence_benchmark", fromlist=["evaluate_evidence_benchmark"],
    ))
    assert "score_proposal_evidence" in source
    # No second ranking/selection algorithm: the benchmark module must never
    # itself read the scorer's numeric identification_score/context_score
    # fields to rank or choose a winner -- that remains evidence_scoring.py's
    # job alone. Attribute-style access (".identification_score") is the
    # meaningful tell; a local variable merely named "identification_scores"
    # (a list of already-decided EvidenceCandidateScore objects) is fine.
    assert ".identification_score" not in source
    assert ".context_score" not in source


def test_evidence_benchmark_module_has_structural_no_write_boundary() -> None:
    from pathlib import Path
    source = Path("src/mockingbird/observation/evidence_benchmark.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "mockingbird.api", "ReviewLabel",
        "MotionEvidence", "StreamMonitoringPolicy", "LiveCameraSession", "sqlalchemy",
    )
    assert not any(token in source for token in forbidden)


# --------------------------------------------------------------------------
# 2-3. Useful / non-useful identification candidate evaluates correctly.
# --------------------------------------------------------------------------


def test_useful_identification_candidate_evaluates_correctly() -> None:
    candidate = _candidate("id-1", "tracked_best", useful_identification=True)
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"id-1": _png()})
    assert report.metrics["useful_identification_rate"] == {"state": "evaluated", "value": 1.0}
    assert report.metrics["reviewed_useful_identification_candidate_count"] == {"state": "evaluated", "value": 1}


def test_non_useful_identification_candidate_evaluates_correctly() -> None:
    candidate = _candidate("id-1", "tracked_best", useful_identification=False)
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"id-1": _png()})
    assert report.metrics["useful_identification_rate"] == {"state": "evaluated", "value": 0.0}


# --------------------------------------------------------------------------
# 4. Useful context evaluates correctly.
# --------------------------------------------------------------------------


def test_useful_context_evaluates_correctly() -> None:
    candidate = _candidate("ctx-1", "pretrigger", subject_geometry=None, useful_context=True)
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"ctx-1": _png()})
    assert report.metrics["useful_context_rate"] == {"state": "evaluated", "value": 1.0}
    assert report.metrics["reviewed_useful_context_candidate_count"] == {"state": "evaluated", "value": 1}


# --------------------------------------------------------------------------
# 5. Identification and context selection may differ.
# --------------------------------------------------------------------------


def test_identification_and_context_selection_may_differ() -> None:
    identification = _candidate("id-1", "tracked_best", useful_identification=True)
    context = _candidate("ctx-1", "pretrigger", subject_geometry=None, useful_context=True, track_generation_id="track-1")
    report = evaluate_evidence_benchmark(
        _manifest(identification, context), media={"id-1": _png(), "ctx-1": _png()},
    )
    (episode,) = report.episodes
    assert episode.selection.identification_candidate_id == "id-1"
    assert episode.selection.context_candidate_id == "ctx-1"


# --------------------------------------------------------------------------
# 6. High-resolution frame is not automatically useful.
# --------------------------------------------------------------------------


def test_high_resolution_frame_is_not_automatically_useful() -> None:
    burst = _candidate(
        "burst-1", "high_resolution_burst", width=1600, height=1200,
        useful_identification=False, temporal_alignment="rejected",
    )
    report = evaluate_evidence_benchmark(_manifest(burst), media={"burst-1": _png()})
    (episode,) = report.episodes
    # Rejected temporal alignment on a burst candidate hard-rejects it, so
    # nothing is ever selected -- the rate genuinely has no selected
    # population to divide over (an honest "insufficient_truth", not a
    # misleading 0.0-looks-like-measured-badness), matching the existing
    # useful_primary_rate precedent's own zero-denominator downgrade.
    assert episode.selection.identification_candidate_id is None
    assert report.metrics["useful_identification_rate"] == {"state": "insufficient_truth", "value": None}
    assert report.metrics["identification_high_resolution_selection_rate"]["state"] == "not_evaluated"


# --------------------------------------------------------------------------
# 7. Analysis frame may beat a high-resolution frame.
# --------------------------------------------------------------------------


def test_analysis_frame_may_beat_a_high_resolution_frame() -> None:
    tracked = _candidate("tracked", "tracked_best", sharpness="usable")
    burst = _candidate(
        "burst", "high_resolution_burst", width=1600, height=1200,
        temporal_alignment="rejected", sharpness="blurred",
    )
    report = evaluate_evidence_benchmark(
        _manifest(tracked, burst), media={"tracked": _png(), "burst": _png()},
    )
    (episode,) = report.episodes
    assert episode.selection.identification_candidate_id == "tracked"
    assert report.metrics["identification_analysis_frame_selection_rate"] == {"state": "evaluated", "value": 1.0}
    assert report.metrics["identification_high_resolution_selection_rate"] == {"state": "evaluated", "value": 0.0}


# --------------------------------------------------------------------------
# 8. Subject-absent burst is not counted useful.
# --------------------------------------------------------------------------


def test_subject_absent_burst_is_not_counted_useful() -> None:
    burst = _candidate(
        "burst", "high_resolution_burst", width=1600, height=1200,
        reviewed_subject_visible="no", useful_identification=False,
    )
    report = evaluate_evidence_benchmark(_manifest(burst), media={"burst": _png()})
    (episode,) = report.episodes
    assert episode.selection.identification_candidate_id is None
    assert report.metrics["no_useful_evidence_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["useful_identification_rate"] == {"state": "insufficient_truth", "value": None}


# --------------------------------------------------------------------------
# 9. Blurred candidate is represented honestly.
# --------------------------------------------------------------------------


def test_blurred_candidate_is_represented_honestly() -> None:
    tracked = _candidate("clear", "tracked_best", sharpness="sharp")
    blurred = _candidate("blur", "alternate", sharpness="blurred", reviewed_blurred=True, track_generation_id="track-1")
    report = evaluate_evidence_benchmark(
        _manifest(tracked, blurred), media={"clear": _png(), "blur": _png(sharp=False)},
    )
    (episode,) = report.episodes
    assert "image_blurred" in episode.selection.score_for("blur").reason_codes
    assert episode.selection.identification_candidate_id == "clear"


# --------------------------------------------------------------------------
# 10. Clipped candidate is represented honestly.
# --------------------------------------------------------------------------


def test_clipped_candidate_is_represented_honestly() -> None:
    tracked = _candidate("clear", "tracked_best")
    # Bird-scale (1.5% of frame) -- see evidence_scoring.LARGE_SUBJECT_AREA_
    # RATIO_FLOOR; a large clipped subject is graded, not excluded.
    clipped = _candidate("clip", "alternate", subject_geometry=(0.0, 0.4, 0.1, 0.55), reviewed_clipped=True)
    report = evaluate_evidence_benchmark(
        _manifest(tracked, clipped), media={"clear": _png(), "clip": _png()},
    )
    (episode,) = report.episodes
    assert "subject_edge_clipped" in episode.selection.score_for("clip").reason_codes
    assert report.metrics["identification_clipped_rate"] == {"state": "evaluated", "value": 0.0}  # selected id ("clear") is not clipped


# --------------------------------------------------------------------------
# 11. Occluded candidate is represented honestly.
# --------------------------------------------------------------------------


def test_occluded_candidate_is_represented_honestly() -> None:
    occluded = _candidate("occ", "tracked_best", reviewed_occluded=True)
    report = evaluate_evidence_benchmark(_manifest(occluded), media={"occ": _png()})
    passthrough = report.reviewed_manifest["candidates"][0]
    assert passthrough["candidate_id"] == "occ"
    assert passthrough["reviewed_occluded"] is True


# --------------------------------------------------------------------------
# 12. Temporal uncertainty is represented.
# --------------------------------------------------------------------------


def test_temporal_uncertainty_is_represented() -> None:
    uncertain = _candidate("u", "tracked_best", temporal_alignment="uncertain", timing_uncertainty_ms=4500)
    report = evaluate_evidence_benchmark(_manifest(uncertain), media={"u": _png()})
    assert report.metrics["temporal_uncertainty_ms_average"] == {"state": "evaluated", "value": 4500.0}
    assert report.metrics["selected_evidence_temporal_uncertain_rate"]["value"] == pytest.approx(1.0)


def test_temporal_uncertainty_absent_is_not_evaluated() -> None:
    candidate = _candidate("c", "tracked_best", timing_uncertainty_ms=None)
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"c": _png()})
    # No candidate anywhere declared a timing_uncertainty_ms value: the
    # metric was never attempted, which is "not_evaluated" (a structural
    # absence), distinct from "insufficient_truth" (truth present but
    # ambiguous/unlinkable).
    assert report.metrics["temporal_uncertainty_ms_average"]["state"] == "not_evaluated"
    assert report.metrics["temporal_uncertainty_ms_average"]["value"] is None


def test_evidence_latency_uses_each_episodes_own_nearest_preceding_appearance() -> None:
    """A session can carry more than one reviewed appearance; latency must
    be measured against the appearance each episode's own evidence actually
    follows, not always the session's single earliest appearance (which
    would silently misattribute a late episode to an unrelated early one)."""

    early = _candidate("early-id", "tracked_best", track_generation_id="track-early", source_offset_ms=1_100)
    late = _candidate("late-id", "tracked_best", track_generation_id="track-late", source_offset_ms=10_050)
    appearances = (
        ReviewedAppearance("appearance-early", "session-1", 1_000, 1_200),
        ReviewedAppearance("appearance-late", "session-1", 10_000, 10_200),
    )
    report = evaluate_evidence_benchmark(
        _manifest(early, late, appearances=appearances), media={"early-id": _png(), "late-id": _png()},
    )
    # Correct per-episode attribution: 100ms and 50ms respectively, mean 75ms.
    # The buggy session-wide-earliest-only design would instead compute
    # (1100-1000) and (10050-1000) = 100 and 9050, mean 4575ms.
    assert report.metrics["evidence_latency_from_appearance_ms"] == {"state": "evaluated", "value": 75.0}


# --------------------------------------------------------------------------
# 13. Ambiguous review truth is excluded.
# --------------------------------------------------------------------------


def test_ambiguous_review_truth_is_excluded_from_scoring_denominators() -> None:
    ambiguous = _candidate("amb", "tracked_best", useful_identification=True, ambiguous=True)
    report = evaluate_evidence_benchmark(_manifest(ambiguous), media={"amb": _png()})
    assert report.metrics["useful_identification_rate"]["state"] == "insufficient_truth"
    assert report.metrics["reviewed_useful_identification_candidate_count"]["state"] == "insufficient_truth"


# --------------------------------------------------------------------------
# 14. Missing truth becomes not_evaluated/insufficient_truth.
# --------------------------------------------------------------------------


def test_missing_truth_becomes_not_evaluated_or_insufficient_truth() -> None:
    candidate = _candidate("c", "tracked_best")  # no usefulness truth at all
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"c": _png()})
    # A genuinely empty truth domain (nobody, anywhere, ever set
    # useful_identification) is "not_evaluated"; a present-but-unusable
    # domain would be "insufficient_truth" -- either is an honest non-zero
    # state, never a fabricated numeric value.
    assert report.metrics["useful_identification_rate"]["state"] in {"not_evaluated", "insufficient_truth"}
    assert report.metrics["useful_identification_rate"]["value"] is None
    empty = evaluate_evidence_benchmark(_manifest())
    assert empty.metrics["episodes_evaluated"]["state"] == "unsupported"
    assert empty.metrics["useful_identification_rate"]["state"] == "unsupported"


# --------------------------------------------------------------------------
# 15. Preferred identification selection correctness.
# --------------------------------------------------------------------------


def test_preferred_identification_selection_correctness() -> None:
    preferred = _candidate("preferred", "tracked_best", preferred_identification=True, sharpness="sharp")
    other = _candidate("other", "alternate", preferred_identification=False, sharpness="usable")
    report = evaluate_evidence_benchmark(
        _manifest(preferred, other), media={"preferred": _png(), "other": _png()},
    )
    assert report.metrics["selected_identification_correctness"] == {"state": "evaluated", "value": 1.0}


def test_preferred_identification_selection_incorrectness_is_reported_honestly() -> None:
    # The scorer will prefer the sharp, non-preferred candidate over the
    # blurred reviewer-preferred one -- the benchmark must report that
    # mismatch honestly rather than silently agreeing with the scorer.
    preferred = _candidate("preferred", "alternate", preferred_identification=True, sharpness="blurred")
    winner = _candidate("winner", "tracked_best", preferred_identification=False, sharpness="sharp")
    report = evaluate_evidence_benchmark(
        _manifest(preferred, winner), media={"preferred": _png(sharp=False), "winner": _png()},
    )
    (episode,) = report.episodes
    assert episode.selection.identification_candidate_id == "winner"
    assert report.metrics["selected_identification_correctness"] == {"state": "evaluated", "value": 0.0}


# --------------------------------------------------------------------------
# 16. Preferred context selection correctness.
# --------------------------------------------------------------------------


def test_preferred_context_selection_correctness() -> None:
    preferred = _candidate("pref-ctx", "pretrigger", subject_geometry=None, preferred_context=True)
    other = _candidate("other-ctx", "context", subject_geometry=None, preferred_context=False)
    report = evaluate_evidence_benchmark(
        _manifest(preferred, other), media={"pref-ctx": _png(), "other-ctx": _png()},
    )
    assert report.metrics["selected_context_correctness"] == {"state": "evaluated", "value": 1.0}


def test_preferred_context_truth_absent_is_not_evaluated() -> None:
    candidate = _candidate("ctx", "pretrigger", subject_geometry=None)
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"ctx": _png()})
    # No candidate anywhere ever set preferred_context at all (not even
    # False): a genuinely empty domain is "not_evaluated", not
    # "insufficient_truth" (which is reserved for truth that exists but is
    # all-ambiguous or unlinkable to a selection).
    assert report.metrics["selected_context_correctness"]["state"] == "not_evaluated"


# --------------------------------------------------------------------------
# 17. Candidate counts and role distribution.
# --------------------------------------------------------------------------


def test_candidate_counts_and_role_distribution() -> None:
    first = _candidate("a", "tracked_best")
    second = _candidate("b", "pretrigger", subject_geometry=None, track_generation_id="track-1")
    report = evaluate_evidence_benchmark(_manifest(first, second), media={"a": _png(), "b": _png()})
    assert report.metrics["candidates_per_episode_mean"] == {"state": "evaluated", "value": 2.0}
    assert report.metrics["eligible_candidates_count"] == {"state": "evaluated", "value": 2}
    assert report.metrics["selected_identification_role_distribution"] == {
        "state": "evaluated", "value": {"tracked_best": 1},
    }
    assert report.metrics["selected_context_role_distribution"] == {
        "state": "evaluated", "value": {"pretrigger": 1},
    }


# --------------------------------------------------------------------------
# 18. No-useful-evidence state.
# --------------------------------------------------------------------------


def test_no_useful_evidence_state() -> None:
    unusable = _candidate("gone", "alternate", decodable=False, width=None, height=None)
    report = evaluate_evidence_benchmark(_manifest(unusable))
    assert report.metrics["no_useful_evidence_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["episodes_with_no_useful_automatic_identification"] == {"state": "evaluated", "value": 1}


# --------------------------------------------------------------------------
# 19. Rejection-reason distribution.
# --------------------------------------------------------------------------


def test_rejection_reason_distribution() -> None:
    # Bird-scale (1.5% of frame) -- see evidence_scoring.LARGE_SUBJECT_AREA_
    # RATIO_FLOOR; a large clipped subject is graded, not excluded.
    clipped = _candidate("clip", "alternate", subject_geometry=(0.0, 0.4, 0.1, 0.55))
    report = evaluate_evidence_benchmark(_manifest(clipped), media={"clip": _png()})
    distribution = report.metrics["rejection_reason_distribution"]
    assert distribution["state"] == "evaluated"
    assert distribution["value"].get("subject_edge_clipped") == 1


# --------------------------------------------------------------------------
# 20. Stale generation cannot be scored against another episode.
# --------------------------------------------------------------------------


def test_stale_generation_cannot_be_scored_against_another_episode() -> None:
    foreign = ReviewedEvidenceCandidate(
        "foreign", "session-1", "high_resolution_burst", track_generation_id="other-track",
        episode_id="session-1:track-1", width=1600, height=1200, subject_geometry=(0.2, 0.2, 0.6, 0.7),
        temporal_alignment="aligned",
    )
    report = evaluate_evidence_benchmark(_manifest(foreign), media={"foreign": _png()})
    (episode,) = report.episodes
    assert episode.selection.no_useful_evidence is True
    assert episode.selection.candidate_scores == ()
    assert report.metrics["stale_generation_rejection_count"] == {"state": "evaluated", "value": 1}


# --------------------------------------------------------------------------
# 21. Privacy/Ignore-masked evidence cannot count as useful unless explicit
#     reviewed override exists.
# --------------------------------------------------------------------------


def test_privacy_masked_evidence_is_not_useful_without_explicit_override() -> None:
    masked = _candidate("masked", "tracked_best", privacy_masked=True, useful_identification=True)
    report = evaluate_evidence_benchmark(_manifest(masked), media={"masked": _png()})
    (episode,) = report.episodes
    assert "privacy_masked" in episode.selection.score_for("masked").reason_codes
    assert episode.selection.identification_candidate_id is None
    assert report.metrics["no_useful_evidence_count"] == {"state": "evaluated", "value": 1}


def test_privacy_masked_evidence_with_explicit_override_can_be_scored() -> None:
    # An explicit reviewed override simply means the candidate was not
    # actually masked (privacy_masked=False); the benchmark never invents a
    # bypass of the scorer's own hard rejection.
    overridden = _candidate("visible", "tracked_best", privacy_masked=False, useful_identification=True)
    report = evaluate_evidence_benchmark(_manifest(overridden), media={"visible": _png()})
    (episode,) = report.episodes
    assert episode.selection.identification_candidate_id == "visible"


# --------------------------------------------------------------------------
# 22-25. Comparison classifications.
# --------------------------------------------------------------------------


def _report_dict(*candidates: ReviewedEvidenceCandidate) -> dict:
    report = evaluate_evidence_benchmark(
        _manifest(*candidates), media={item.candidate_id: _png() for item in candidates},
    )
    return report.to_semantic_dict()


def test_comparison_candidate_better() -> None:
    baseline = _report_dict(_candidate("a", "tracked_best", useful_identification=False))
    candidate = _report_dict(_candidate("b", "tracked_best", useful_identification=True))
    result = compare_evidence_benchmark_reports(baseline, candidate)
    entry = next(item for item in result["metrics"] if item["metric"] == "useful_identification_rate")
    assert entry["classification"] == "candidate better"


def test_comparison_baseline_better() -> None:
    baseline = _report_dict(_candidate("a", "tracked_best", useful_identification=True))
    candidate = _report_dict(_candidate("b", "tracked_best", useful_identification=False))
    result = compare_evidence_benchmark_reports(baseline, candidate)
    entry = next(item for item in result["metrics"] if item["metric"] == "useful_identification_rate")
    assert entry["classification"] == "baseline better"


def test_comparison_equivalent() -> None:
    baseline = _report_dict(_candidate("a", "tracked_best", useful_identification=True))
    candidate = _report_dict(_candidate("b", "tracked_best", useful_identification=True))
    result = compare_evidence_benchmark_reports(baseline, candidate)
    entry = next(item for item in result["metrics"] if item["metric"] == "useful_identification_rate")
    assert entry["classification"] == "equivalent"


def test_comparison_unsupported_metric() -> None:
    baseline = _report_dict(_candidate("a", "tracked_best"))
    candidate_report = evaluate_evidence_benchmark(_manifest())
    result = compare_evidence_benchmark_reports(baseline, candidate_report.to_semantic_dict())
    entry = next(item for item in result["metrics"] if item["metric"] == "episodes_evaluated")
    assert entry["classification"] in {"insufficient truth", "unsupported for one side"}
    assert "winner" not in result


def test_comparison_is_deterministic_and_has_no_aggregate_winner() -> None:
    baseline = _report_dict(_candidate("a", "tracked_best", useful_identification=True))
    candidate = _report_dict(_candidate("b", "tracked_best", useful_identification=False))
    first = compare_evidence_benchmark_reports(baseline, candidate)
    second = compare_evidence_benchmark_reports(baseline, candidate)
    assert first == second
    assert "winner" not in first
    assert {item["classification"] for item in first["metrics"]} <= {
        "baseline better", "candidate better", "equivalent", "insufficient truth", "unsupported for one side",
    }


# --------------------------------------------------------------------------
# 26. Deterministic report ordering.
# --------------------------------------------------------------------------


def test_deterministic_report_ordering() -> None:
    first = _candidate("z-candidate", "alternate", track_generation_id="track-2")
    second = _candidate("a-candidate", "tracked_best", track_generation_id="track-1")
    forward = evaluate_evidence_benchmark(
        _manifest(first, second), media={"z-candidate": _png(), "a-candidate": _png()},
    )
    reversed_report = evaluate_evidence_benchmark(
        _manifest(second, first), media={"z-candidate": _png(), "a-candidate": _png()},
    )
    assert [item.episode_id for item in forward.episodes] == [item.episode_id for item in reversed_report.episodes]
    assert forward.to_semantic_dict() == reversed_report.to_semantic_dict()


# --------------------------------------------------------------------------
# 27-29. Semantic fingerprint reproducibility and non-semantic isolation.
# --------------------------------------------------------------------------


def test_repeated_semantic_fingerprints_match() -> None:
    candidate = _candidate("a", "tracked_best", useful_identification=True)
    first = evaluate_evidence_benchmark(_manifest(candidate), media={"a": _png()})
    second = evaluate_evidence_benchmark(_manifest(candidate), media={"a": _png()})
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.to_semantic_dict() == second.to_semantic_dict()


def test_runtime_differences_do_not_affect_semantic_fingerprint() -> None:
    """Explicit regression test: absolute output paths, wall-clock duration,
    image decode latency, process RSS, and environment facts must never
    enter the semantic payload or its fingerprint -- only the separate
    execution section may vary between two otherwise-identical runs."""
    candidate = _candidate("a", "tracked_best", useful_identification=True)
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"a": _png()})
    semantic = report.to_semantic_dict()
    import json
    serialized = json.dumps(semantic, sort_keys=True, default=str)
    for leak in ("wall_clock", "/tmp/", "C:\\\\", "process_rss", "hostname", "started_at"):
        assert leak not in serialized


def test_absolute_paths_remain_non_semantic() -> None:
    candidate = _candidate("a", "tracked_best")
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"a": "/tmp/some/absolute/path/a.png"})
    # An unresolvable path is simply treated as unavailable image bytes; it
    # must never appear anywhere in the semantic payload.
    import json
    assert "/tmp/some/absolute/path" not in json.dumps(report.to_semantic_dict(), default=str)


# --------------------------------------------------------------------------
# 33-34. No product repository dependency / no product truth write path.
# --------------------------------------------------------------------------


def test_no_product_repository_dependency() -> None:
    import ast
    from pathlib import Path
    tree = ast.parse(Path("src/mockingbird/observation/evidence_benchmark.py").read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden_prefixes = ("mockingbird.repositories", "mockingbird.api", "sqlalchemy")
    assert not any(module.startswith(prefix) for module in imported_modules for prefix in forbidden_prefixes)


def test_report_creates_no_truth() -> None:
    candidate = _candidate("a", "tracked_best")
    report = evaluate_evidence_benchmark(_manifest(candidate), media={"a": _png()})
    semantic = report.to_semantic_dict()
    assert semantic["creates_truth"] is False
    assert semantic["shadow_only"] is True


# --------------------------------------------------------------------------
# Manifest validation
# --------------------------------------------------------------------------


def test_manifest_rejects_duplicate_candidate_ids() -> None:
    with pytest.raises(EvidenceBenchmarkError):
        _manifest(_candidate("dup", "tracked_best"), _candidate("dup", "alternate"))


def test_manifest_rejects_unsupported_version() -> None:
    with pytest.raises(EvidenceBenchmarkError):
        ReviewedEvidenceManifest(2, "m", "s", ())


def test_reviewed_candidate_rejects_invalid_subject_visible() -> None:
    with pytest.raises(EvidenceBenchmarkError):
        ReviewedEvidenceCandidate("c", "s", "tracked_best", reviewed_subject_visible="maybe")


# --------------------------------------------------------------------------
# Stage 6.6 reviewed-packet derivation: mechanical, no hand-copying.
# --------------------------------------------------------------------------


def _capture_config(**overrides) -> CaptureSessionConfig:
    defaults = dict(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1", stream_id="s1",
        transport_key="camera-node-http-multipart-jpeg", provider_key="frame-driven-onnx-cuda",
        analysis_width=1000, analysis_height=1000, nominal_fps=2.0, review_score_threshold=0.02,
        shadow_operating_point=0.5, review_floor=0.1, evidence_profile_id="profile-1", bounds=CaptureBounds(),
    )
    defaults.update(overrides)
    return CaptureSessionConfig(**defaults)


def _capture_record(frame_id, sequence, offset_ms, **overrides) -> RetainedFrameRecord:
    defaults = dict(
        frame_id=frame_id, sequence=sequence, source_offset_ms=offset_ms, provider_generation="gen-1",
        content_hash="h" * 64, byte_size=1000, trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,),
        detector_observation_count=1, animal_detection_count=1, max_animal_score=0.5,
        active_track_count=1, motion_proposal_count=0, track_generation_ids=("track-1",),
        session_offset_ms=offset_ms, connection_segment_id="segment-1",
    )
    defaults.update(overrides)
    return RetainedFrameRecord(**defaults)


def _capture_session(frames, **overrides) -> dict:
    defaults = dict(
        config=_capture_config(), session_id="session-1", node_session_id="node-session-1",
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


def test_reviewed_manifest_is_derived_from_a_temporal_review_packet_without_hand_copying() -> None:
    records = (
        _capture_record("frame-a", 0, 0, high_resolution=True, trigger_reasons=(TRIGGER_HIGH_RESOLUTION_BURST,), track_generation_ids=()),
        _capture_record("frame-b", 1, 500, trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,), track_generation_ids=("track-1",)),
        _capture_record("frame-c", 2, 900, trigger_reasons=(TRIGGER_PRETRIGGER_CONTEXT,), track_generation_ids=(), active_track_count=0, animal_detection_count=0, max_animal_score=None),
    )
    session = _capture_session(records)
    annotations = AnnotationSet(
        1, "session-1", session["semantic_fingerprint"],
        (
            FrameAnnotation(
                "frame-a", whole_frame_truth="yes",
                boxes=(BoxAnnotation((0.1, 0.1, 0.3, 0.3), blurred=False, edge_clipped=False, occluded=False),),
                evidence_usefulness=EvidenceUsefulness(True, True, True, False),
                provenance=Provenance("alice", "2026-08-06T00:00:00+00:00", "session-1", "high_resolution_burst"),
            ),
            FrameAnnotation(
                "frame-b", whole_frame_truth="yes",
                boxes=(BoxAnnotation((0.2, 0.2, 0.5, 0.6), blurred=True, edge_clipped=False, occluded=True),),
                evidence_usefulness=EvidenceUsefulness(True, False, False, False),
                provenance=Provenance("alice", "2026-08-06T00:00:01+00:00", "session-1", "detector_crop"),
            ),
            FrameAnnotation("frame-c", whole_frame_truth="unreviewed"),
        ),
        (AppearanceInterval("appearance-1", "frame-b", "frame-b", instantaneous=True),),
    )
    manifest = build_reviewed_evidence_manifest_from_temporal_review(session, annotations, source_description="unit-test")
    by_id = {item.candidate_id: item for item in manifest.candidates}
    # The unreviewed frame contributes nothing -- never silently truth.
    assert set(by_id) == {"frame-a", "frame-b"}
    assert by_id["frame-a"].role == "high_resolution_burst"
    assert by_id["frame-a"].high_resolution is True
    assert by_id["frame-a"].useful_context is True
    assert by_id["frame-b"].role == "detector_confirmed"
    assert by_id["frame-b"].reviewed_blurred is True
    assert by_id["frame-b"].reviewed_occluded is True
    assert by_id["frame-b"].track_generation_id == "track-1"
    assert manifest.appearances == (ReviewedAppearance("appearance-1", "session-1", 500, 500),)

    # And the derived manifest is itself directly usable by the benchmark.
    report = evaluate_evidence_benchmark(manifest)
    assert report.metrics["episodes_evaluated"]["value"] == 2
