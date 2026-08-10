"""Detection Quality Accounting v1 (see
docs/detection-quality-accounting-contract.md): focused, hardware-free unit
tests for the bounded six-stage accounting pass."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mockingbird.observation.contracts import (
    ConfidenceEvidenceSummary,
    DetectionEvidenceSample,
    DetectionObservation,
    EMPTY_CONFIDENCE_EVIDENCE,
    TrackUpdate,
)
from mockingbird.observation.detection_quality_accounting import (
    AdmissionRecord,
    STAGE_ADMISSION_ATTEMPT,
    STAGE_ANIMAL_PRESENCE_PROPOSAL,
    STAGE_CANDIDATE_VISIT_CREATION,
    STAGE_CONFIRMED_TRACK_FORMATION,
    STAGE_LOCALIZATION_TRACKING,
    STAGE_VISIT_PROPOSAL_ASSEMBLY,
    build_detection_quality_report,
    confidence_values_from,
    summarize_confidence_distribution,
)
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal, Tracklet

NOW = datetime(2026, 8, 10, tzinfo=UTC)


def test_detection_quality_accounting_module_has_no_product_repository_import() -> None:
    """Structural guard, matching every other Stage 6.x/7 pure decision
    module's own established convention (see e.g.
    `test_candidate_visit_authority_module_has_no_product_repository_import`)."""
    source = Path("src/mockingbird/observation/detection_quality_accounting.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy",
        "import socket", "import requests", "onnxruntime", "cv2",
    )
    for token in forbidden:
        assert token not in source, f"detection_quality_accounting.py must not reference {token}"


def _detection(confidence: float | None, *, is_animal: bool = True) -> DetectionObservation:
    return DetectionObservation(
        "mdv5:1", "animal" if is_animal else "person", confidence, NOW, is_animal=is_animal,
    )


def _track_update(generation_id: str, status: str) -> TrackUpdate:
    return TrackUpdate(f"track-{generation_id}", generation_id, NOW, status, "confirmed")


def _tracklet(generation_id: str, *, confidence_evidence: ConfidenceEvidenceSummary = EMPTY_CONFIDENCE_EVIDENCE) -> Tracklet:
    box = (0.4, 0.4, 0.5, 0.5)
    return Tracklet(
        generation_id=generation_id, stream_id="stream-1", broad_class="animal",
        start_offset_ms=0, end_offset_ms=1000, start_bounding_box=box, end_bounding_box=box,
        geometry_envelope=box, terminal_reason="end_of_replay", track_ids=(f"track-{generation_id}",),
        confidence_evidence=confidence_evidence,
    )


def _proposal(proposal_id: str, *, confidence_evidence: ConfidenceEvidenceSummary = EMPTY_CONFIDENCE_EVIDENCE) -> AssembledVisitProposal:
    return AssembledVisitProposal(
        proposal_id=proposal_id, stream_id="stream-1", broad_class="animal",
        start_offset_ms=0, end_offset_ms=1000, constituent_generation_ids=("gen-1",),
        constituent_track_ids=("track-1",), supporting_frame_ids=("frame-1",),
        source_capture_frame_ids=(), evidence_candidate_ids=("media-1",), assembly_decisions=(),
        confidence_evidence=confidence_evidence,
    )


def _summary(*, max_confidence: float, samples: tuple[float, ...] = ()) -> ConfidenceEvidenceSummary:
    return ConfidenceEvidenceSummary(
        detection_count=max(1, len(samples)),
        max_confidence=max_confidence,
        mean_confidence=(sum(samples) / len(samples)) if samples else None,
        median_confidence=None,
        strong_detection_count=0,
        weak_detection_count=max(1, len(samples)),
        max_consecutive_detector_confirmed_frames=1,
        samples=tuple(
            DetectionEvidenceSample(confidence=value, source_offset_ms=0, frame_id=None, observation_id=None, is_strong=False)
            for value in samples
        ),
        broad_class="animal",
        first_detection_offset_ms=0,
        last_detection_offset_ms=0,
    )


# --- confidence_values_from ---------------------------------------------------


def test_confidence_values_from_prefers_samples_over_max() -> None:
    evidence = _summary(max_confidence=0.9, samples=(0.3, 0.5, 0.9))
    assert confidence_values_from(evidence) == (0.3, 0.5, 0.9)


def test_confidence_values_from_falls_back_to_max_confidence_when_no_samples() -> None:
    evidence = ConfidenceEvidenceSummary(
        detection_count=3, max_confidence=0.6, mean_confidence=None, median_confidence=None,
        strong_detection_count=0, weak_detection_count=0, max_consecutive_detector_confirmed_frames=0,
        samples=(), broad_class="animal", first_detection_offset_ms=None, last_detection_offset_ms=None,
        sample_truncated=True,
    )
    assert confidence_values_from(evidence) == (0.6,)


def test_confidence_values_from_none_evidence_is_empty() -> None:
    assert confidence_values_from(None) == ()
    assert confidence_values_from(EMPTY_CONFIDENCE_EVIDENCE) == ()


# --- summarize_confidence_distribution ----------------------------------------


def test_confidence_distribution_labels_insufficient_data_when_empty() -> None:
    distribution = summarize_confidence_distribution(())
    assert distribution["count"] == 0
    assert distribution["mean"] == {"state": "insufficient_data", "value": None}
    assert distribution["buckets"] == []


def test_confidence_distribution_computes_stats_and_deciles() -> None:
    distribution = summarize_confidence_distribution((0.05, 0.15, 0.95, 1.0))
    assert distribution["count"] == 4
    assert distribution["minimum"] == {"state": "evaluated", "value": 0.05}
    assert distribution["maximum"] == {"state": "evaluated", "value": 1.0}
    assert distribution["median"]["state"] == "evaluated"
    buckets = {(bucket["low"], bucket["high"]): bucket["count"] for bucket in distribution["buckets"]}
    assert buckets[(0.0, 0.1)] == 1  # 0.05
    assert buckets[(0.1, 0.2)] == 1  # 0.15
    assert buckets[(0.9, 1.0)] == 2  # 0.95 and the inclusive top edge 1.0


# --- build_detection_quality_report -------------------------------------------


def test_report_counts_all_six_stages() -> None:
    report = build_detection_quality_report(
        detections=(_detection(0.3), _detection(0.6), _detection(0.1, is_animal=False)),
        track_updates=(_track_update("gen-1", "started"), _track_update("gen-1", "updated")),
        tracklets=(_tracklet("gen-1"),),
        assembled_proposals=(_proposal("visit-episode:1"),),
        admission_records=(AdmissionRecord("visit-episode:1", "created", admitted=True),),
    )
    stages = {item["stage"]: item["count"] for item in report["pipeline_stage_counts"]}
    assert stages[STAGE_ANIMAL_PRESENCE_PROPOSAL] == 2  # only the two is_animal=True detections
    assert stages[STAGE_LOCALIZATION_TRACKING] == 1  # one distinct generation started
    assert stages[STAGE_CONFIRMED_TRACK_FORMATION] == 1
    assert stages[STAGE_VISIT_PROPOSAL_ASSEMBLY] == 1
    assert stages[STAGE_ADMISSION_ATTEMPT] == 1
    assert stages[STAGE_CANDIDATE_VISIT_CREATION] == 1


def test_report_separates_admitted_and_rejected_confidence_characteristics() -> None:
    admitted_evidence = _summary(max_confidence=0.8, samples=(0.75, 0.8))
    rejected_evidence = _summary(max_confidence=0.15, samples=(0.1, 0.15))
    report = build_detection_quality_report(
        admission_records=(
            AdmissionRecord("visit-episode:admit", "created", admitted=True, confidence_evidence=admitted_evidence),
            AdmissionRecord(
                "visit-episode:reject", "reject_subject_geometry_invalid", admitted=False,
                confidence_evidence=rejected_evidence,
            ),
        ),
    )
    assert report["admitted_confidence_distribution"]["minimum"]["value"] == 0.75
    assert report["rejected_confidence_distribution"]["maximum"]["value"] == 0.15
    assert report["suppression_reason_counts"] == [{"reason": "reject_subject_geometry_invalid", "count": 1}]


def test_report_explains_continuation_pending_suppressions_like_any_other_reason() -> None:
    """Visit Continuity / Provisional Admission Fix v1 (see
    docs/tracklet-visit-assembly-contract.md "Episode finality"): the new
    `blocked_continuation_pending` outcome needs no special-casing here --
    this module already counts *any* admission-attempt outcome string
    honestly, so a caller can explain that several internal admission
    attempts (one still-forming episode, reconsidered across ticks)
    represented one eventual encounter without this module ever hiding
    them from the funnel."""
    report = build_detection_quality_report(
        admission_records=(
            AdmissionRecord("visit-episode:pending-1", "blocked_continuation_pending", admitted=False),
            AdmissionRecord("visit-episode:pending-1", "blocked_continuation_pending", admitted=False),
            AdmissionRecord("visit-episode:pending-1", "created", admitted=True),
        ),
    )
    stages = {item["stage"]: item["count"] for item in report["pipeline_stage_counts"]}
    assert stages[STAGE_ADMISSION_ATTEMPT] == 3  # every attempt stays visible, none hidden
    assert stages[STAGE_CANDIDATE_VISIT_CREATION] == 1  # exactly one real admission
    assert report["suppression_reason_counts"] == [{"reason": "blocked_continuation_pending", "count": 2}]


def test_report_rates_are_insufficient_data_when_denominator_unknown() -> None:
    report = build_detection_quality_report()
    assert report["track_confirmation_rate"] == {"state": "insufficient_data", "value": None}
    assert report["visit_proposal_admission_rate"] == {"state": "insufficient_data", "value": None}
    stages = {item["stage"]: item["count"] for item in report["pipeline_stage_counts"]}
    assert all(count == 0 for count in stages.values())


def test_report_rates_are_evaluated_when_denominator_known() -> None:
    report = build_detection_quality_report(
        track_updates=(_track_update("gen-1", "started"), _track_update("gen-2", "started")),
        tracklets=(_tracklet("gen-1"),),
        admission_records=(
            AdmissionRecord("p1", "created", admitted=True),
            AdmissionRecord("p2", "blocked_ambiguous_boundary", admitted=False),
        ),
    )
    assert report["track_confirmation_rate"] == {"state": "evaluated", "value": 0.5}
    assert report["visit_proposal_admission_rate"] == {"state": "evaluated", "value": 0.5}


def test_report_is_deterministic_and_never_writes_product_truth() -> None:
    kwargs = dict(
        detections=(_detection(0.4),),
        admission_records=(AdmissionRecord("p1", "created", admitted=True),),
    )
    first = build_detection_quality_report(**kwargs)
    second = build_detection_quality_report(**kwargs)
    assert first["semantic_fingerprint"] == second["semantic_fingerprint"]
    assert first["safety"] == {
        "product_writes": False,
        "reviewed_truth_created": False,
        "confidence_used_as_observational_authority": False,
    }
