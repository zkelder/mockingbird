"""Detection Quality Accounting v1: a bounded, reusable accounting pass over
already-emitted Observation Engine facts (see
docs/detection-quality-accounting-contract.md).

Answers the six-stage question this milestone exists to make honest: how
many raw detections occurred and what did their confidence look like, how
many tracks formed and were confirmed, how many Visit proposals were
assembled, why an admission attempt was suppressed, and how confidence/
evidence characteristics differ between admitted and rejected candidates.
Diagnostic accounting only -- it never creates, mutates, or implies product
truth, and it is not itself an admission policy (see
`mockingbird.observation.admission_policy` for the *shadow* evaluator this
module's output feeds).

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every other Stage
6.x/7 decision module in this package follows
(`test_detection_quality_accounting_module_has_no_product_repository_import`).
It invents no new detector/evidence-quality threshold and recomputes no fact
another module already owns; every count here is read from already-emitted
`DetectionObservation`/`TrackUpdate`/`Tracklet`/`AssembledVisitProposal`/
`AdmissionRecord` facts.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from statistics import median
from typing import Sequence

from mockingbird.observation.contracts import ConfidenceEvidenceSummary, DetectionObservation, TrackUpdate
from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal, Tracklet

DETECTION_QUALITY_REPORT_SCHEMA_VERSION = 1

# The six stages this milestone names explicitly (Detection Quality
# Accounting v1, Part 3): animal-presence proposal, localization/tracking,
# confirmed-track formation, Visit proposal/assembly, admission attempt,
# candidate Visit creation. Stable, ordered keys -- never renamed once
# reports referencing them exist.
STAGE_ANIMAL_PRESENCE_PROPOSAL = "animal_presence_proposal"
STAGE_LOCALIZATION_TRACKING = "localization_tracking"
STAGE_CONFIRMED_TRACK_FORMATION = "confirmed_track_formation"
STAGE_VISIT_PROPOSAL_ASSEMBLY = "visit_proposal_assembly"
STAGE_ADMISSION_ATTEMPT = "admission_attempt"
STAGE_CANDIDATE_VISIT_CREATION = "candidate_visit_creation"
PIPELINE_STAGES = (
    STAGE_ANIMAL_PRESENCE_PROPOSAL,
    STAGE_LOCALIZATION_TRACKING,
    STAGE_CONFIRMED_TRACK_FORMATION,
    STAGE_VISIT_PROPOSAL_ASSEMBLY,
    STAGE_ADMISSION_ATTEMPT,
    STAGE_CANDIDATE_VISIT_CREATION,
)

# Fixed decile histogram bounds for a confidence distribution -- an obvious,
# non-scene-specific choice (like `detector_benchmark.DEFAULT_THRESHOLD_
# GRID`'s own fixed sweep), not a value tuned to any one cohort.
_DISTRIBUTION_BUCKET_EDGES: tuple[float, ...] = tuple(round(index * 0.1, 1) for index in range(11))


def semantic_fingerprint(value: object) -> str:
    """Small, self-contained determinism helper -- deliberately duplicated
    from (never imported from) `replay.semantic_fingerprint`, matching every
    other Stage 6.x pure decision module's own established dependency shape
    (see the identical note in `visit_episode_assembler.semantic_fingerprint`)."""
    import json

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AdmissionRecord:
    """One already-decided admission attempt, combining what
    `candidate_visit_authority.evaluate_candidate_authority` and
    `candidate_quality_gate.evaluate_evidence_admission` (or the repository's
    own transactional re-check) actually decided for one proposal -- stages
    5 and 6 of Detection Quality Accounting. `outcome` reuses the existing
    stable outcome vocabulary those gates and
    `product_repository.CandidateVisitCreationOutcome` already define
    (`"created"`, `"blocked_shadow_mode"`, `"reject_subject_geometry_
    invalid"`, ...) -- this module invents no new outcome code of its own.
    `confidence_evidence` is the same proposal's own
    `ConfidenceEvidenceSummary`, when known, so admitted-versus-rejected
    confidence characteristics can be compared without recomputing anything.
    """

    proposal_id: str
    outcome: str
    admitted: bool
    confidence_evidence: ConfidenceEvidenceSummary | None = None


def admission_records_from_counterfactual_ledger(
    proposal_outcomes: Sequence[ProposalOutcomeRecord],
) -> tuple[AdmissionRecord, ...]:
    """Connect Rejected / Suppressed Detection Attribution v1's own bounded,
    live-session-standing `ProposalOutcomeRecord` ledger (see
    docs/rejected-detection-attribution-contract.md) to this module's
    existing stage 5/6 accounting -- deliberately the *only* integration
    point this milestone adds, per that contract's own "do not build a
    parallel metrics universe" boundary. `ProposalOutcomeRecord` already
    carries exactly the three facts `AdmissionRecord` needs
    (`proposal_id`/`outcome`/`confidence_evidence`, plus `admitted`, reusing
    the identical `outcome in ("created", "idempotent_repeat")` rule the
    ledger itself already applied) -- this is a pure field projection, never
    a recomputation, so `build_detection_quality_report` itself needed zero
    changes to accept it. Closes the previously-disclosed gap that today's
    accounting mechanism was "an offline pass over already-recorded facts"
    with no standing live-session record at all (see "Remains open" in
    docs/detection-quality-accounting-contract.md): a live session's own
    counterfactual ledger can now feed this exact function directly, no
    replay-report.json round trip required.
    """

    return tuple(
        AdmissionRecord(
            proposal_id=record.proposal_id,
            outcome=record.outcome,
            admitted=record.admitted,
            confidence_evidence=record.confidence_evidence,
        )
        for record in proposal_outcomes
    )


def confidence_values_from(evidence: ConfidenceEvidenceSummary | None) -> tuple[float, ...]:
    """The representative confidence values one `ConfidenceEvidenceSummary`
    actually has available for a distribution -- its retained `samples` when
    present, else its lone `max_confidence` when that alone is known, else
    nothing. Never fabricates a value for evidence that carries none."""
    if evidence is None:
        return ()
    if evidence.samples:
        return tuple(sample.confidence for sample in evidence.samples)
    if evidence.max_confidence is not None:
        return (evidence.max_confidence,)
    return ()


def _metric(value: object, state: str) -> dict[str, object]:
    """Mirrors the `{"state": ..., "value": ...}` convention already
    established by `replay.py`/`detector_benchmark.py`/
    `visit_episode_assembler.py` for an honestly-labeled, possibly-
    insufficient-data metric -- reused here for consistency, not
    reimplemented differently."""
    return {"state": state, "value": value}


def summarize_confidence_distribution(values: Sequence[float]) -> dict[str, object]:
    """A model-neutral confidence distribution: count, min/max/mean/median,
    and a fixed decile histogram. Every statistic is `insufficient_data`
    (never a fabricated number) when `values` is empty."""

    if not values:
        return {
            "count": 0,
            "minimum": _metric(None, "insufficient_data"),
            "maximum": _metric(None, "insufficient_data"),
            "mean": _metric(None, "insufficient_data"),
            "median": _metric(None, "insufficient_data"),
            "buckets": [],
        }
    ordered = sorted(values)
    buckets: list[dict[str, object]] = []
    for index in range(len(_DISTRIBUTION_BUCKET_EDGES) - 1):
        low, high = _DISTRIBUTION_BUCKET_EDGES[index], _DISTRIBUTION_BUCKET_EDGES[index + 1]
        is_last = index == len(_DISTRIBUTION_BUCKET_EDGES) - 2
        count = sum(1 for value in ordered if (low <= value < high) or (is_last and value == high))
        buckets.append({"low": low, "high": high, "count": count})
    return {
        "count": len(ordered),
        "minimum": _metric(ordered[0], "evaluated"),
        "maximum": _metric(ordered[-1], "evaluated"),
        "mean": _metric(sum(ordered) / len(ordered), "evaluated"),
        "median": _metric(median(ordered), "evaluated"),
        "buckets": buckets,
    }


def build_detection_quality_report(
    *,
    detections: Sequence[DetectionObservation] = (),
    track_updates: Sequence[TrackUpdate] = (),
    tracklets: Sequence[Tracklet] = (),
    assembled_proposals: Sequence[AssembledVisitProposal] = (),
    admission_records: Sequence[AdmissionRecord] = (),
) -> dict[str, object]:
    """Build one bounded Detection Quality Accounting report from already-
    emitted facts across all six stages. Every input is optional and
    defaults to empty so a caller with only a partial pipeline slice (for
    example a detector-only benchmark with no tracker/assembly facts at
    all) still gets an honest, correctly `insufficient_data`-labeled report
    for the stages it did not supply, rather than an error.
    """

    animal_detections = [item for item in detections if item.is_animal is True]
    tracks_started = len({item.generation_id for item in track_updates if item.status == "started"})
    tracks_confirmed = len(tracklets)
    proposals_assembled = len(assembled_proposals)
    attempts = len(admission_records)
    created = sum(1 for record in admission_records if record.admitted)
    rejected_records = [record for record in admission_records if not record.admitted]

    detection_confidences = tuple(
        item.confidence for item in detections if item.confidence is not None
    )
    admitted_confidences = tuple(
        value
        for record in admission_records
        if record.admitted
        for value in confidence_values_from(record.confidence_evidence)
    )
    rejected_confidences = tuple(
        value
        for record in rejected_records
        for value in confidence_values_from(record.confidence_evidence)
    )

    stage_counts = [
        {"stage": STAGE_ANIMAL_PRESENCE_PROPOSAL, "count": len(animal_detections), "raw_detection_count": len(detections)},
        {"stage": STAGE_LOCALIZATION_TRACKING, "count": tracks_started},
        {"stage": STAGE_CONFIRMED_TRACK_FORMATION, "count": tracks_confirmed},
        {"stage": STAGE_VISIT_PROPOSAL_ASSEMBLY, "count": proposals_assembled},
        {"stage": STAGE_ADMISSION_ATTEMPT, "count": attempts},
        {"stage": STAGE_CANDIDATE_VISIT_CREATION, "count": created},
    ]
    suppression_reason_counts = sorted(Counter(record.outcome for record in rejected_records).items())

    semantic = {
        "schema_version": DETECTION_QUALITY_REPORT_SCHEMA_VERSION,
        "pipeline_stage_counts": stage_counts,
        "detection_confidence_distribution": summarize_confidence_distribution(detection_confidences),
        "admitted_confidence_distribution": summarize_confidence_distribution(admitted_confidences),
        "rejected_confidence_distribution": summarize_confidence_distribution(rejected_confidences),
        "suppression_reason_counts": [{"reason": reason, "count": count} for reason, count in suppression_reason_counts],
        "track_confirmation_rate": (
            _metric(tracks_confirmed / tracks_started, "evaluated")
            if tracks_started
            else _metric(None, "insufficient_data")
        ),
        "visit_proposal_admission_rate": (
            _metric(created / attempts, "evaluated") if attempts else _metric(None, "insufficient_data")
        ),
        "safety": {
            "product_writes": False,
            "reviewed_truth_created": False,
            "confidence_used_as_observational_authority": False,
        },
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic)}
