#!/usr/bin/env python3
"""Site-Specific Learning & Local Adaptation v1: baseline-vs-adapted
counterfactual evaluation for the new scene-confusor reviewed-evidence
suspicion path (see docs/scene-confusor-suspicion-contract.md, "Reviewed-
negative-evidence suspicion").

Never touches the real product database. Every case below runs twice,
through the real, unmodified `ProductRepository.create_candidate_visit_from_
proposal` / `create_review_label` code paths -- once against a fresh,
isolated, disposable SQLite database with the new mechanism's per-Stream
`scene_confusor_reviewed_evidence_enabled` setting left at its pre-milestone
value (`False`, "baseline"), and once against a second, independently fresh
isolated database with it left at its shipped default (`True`, "adapted").
Both runs replay the identical construction sequence, so the only variable
between them is whether the new reviewed-evidence path can fire.

Disclosed honestly, not glossed over: this repository's own real local
database (`data/mockingbird.sqlite3`) has zero pre-existing
`scene_confusor_regions` rows to replay organically -- see the milestone's
own archaeology finding. Every case below is therefore a constructed,
clearly-labeled scenario, not an organic field replay, in the same spirit
as (and modeled directly on) the original Scene Confusor Suppression v1
milestone's own "steady-state stress replay" (docs/scene-confusor-
suspicion-contract.md, "Replay of the previous cohort") -- a bespoke,
one-off evaluation script, not a permanent harness feature. Each case's own
"ground truth" is stated in its own docstring because the author constructed
it, not inferred after the fact -- avoiding exactly the evaluation-leakage
risk that precedent already disclosed.

Usage:
    .venv/bin/python scripts/scene_confusor_reviewed_evidence_counterfactual.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import tempfile
from pathlib import Path
from typing import Callable

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    ProductRepository,
)
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode

STREAM_ID = "stream-backyard-feeder"
NOW = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"

BoundingBox = tuple[float, float, float, float]


def _facts(*, proposal_id: str, confidence: float) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id, stream_id=STREAM_ID, zone_id=None, broad_class="animal",
        start_offset_ms=0, end_offset_ms=4500,
        constituent_generation_ids=(f"{proposal_id}-gen",), constituent_track_ids=(f"{proposal_id}-track",),
        source_capture_frame_ids=(f"{proposal_id}-frame",), supporting_frame_ids=(f"{proposal_id}-frame",),
        evidence_candidate_ids=(f"shadow-burst:{proposal_id}",), limitation_facts=(),
        ambiguous_adjacent_proposal_ids=(), assembler_version="tracklet-visit-assembler-v1",
        detector_provenance="onnx-cuda", tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key="frame-driven-onnx-cuda",
        confidence_evidence_json=f'{{"detection_count": 1, "max_confidence": {confidence}}}',
    )


def _evidence(box: BoundingBox) -> CandidateEvidenceItem:
    return CandidateEvidenceItem(
        engine_media_id="shadow-burst:evidence", role="identification", content=JPEG_BYTES,
        content_type="image/jpeg", width=3840, height=2160, captured_at=NOW, subject_geometry=box,
    )


def _attempt(repository: ProductRepository, box: BoundingBox, *, proposal_id: str, at: datetime, confidence: float = 0.3):
    return repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id=proposal_id, confidence=confidence), observed_at=at,
            evidence_items=(_evidence(box),),
        )
    )


def _review(repository: ProductRepository, visit_id: str, label: str, *, at: datetime) -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=visit_id, label=label,
            review_origin="human", reviewer_identity="counterfactual-script",
        ),
        created_at=at,
    )


@dataclass(frozen=True)
class CaseResult:
    name: str
    ground_truth: str  # "confusor" | "real_animal" | "ambiguous"
    final_outcome: str
    note: str = ""


@dataclass
class Scenario:
    """One named, disclosed, constructed scenario -- a sequence of
    admission attempts and (optionally) reviews, ending in one final
    "does this get created or blocked" decision this script scores."""

    name: str
    ground_truth: str
    run: Callable[[ProductRepository], str]  # returns the final outcome string
    note: str = ""


def _confusor_repeated_reviewed_false(repository: ProductRepository) -> str:
    """Ground truth: CONFUSOR (a static artifact). A reviewer looks at it
    twice and both times correctly says `false_positive` -- but only two
    admission attempts have happened at this geometry in total, one short
    of the pre-existing, unreviewed `min_occurrences_to_suspect` (3)."""

    box = (0.464, 0.535, 0.486, 0.551)
    jitter = [(0.4640, 0.5350, 0.4860, 0.5510), (0.4643, 0.5352, 0.4863, 0.5513)]
    for index, b in enumerate(jitter):
        outcome = _attempt(repository, b, proposal_id=f"case-a-{index}", at=NOW + timedelta(minutes=index))
        if outcome.outcome == "created":
            _review(repository, outcome.visit_id, "false_positive", at=NOW + timedelta(minutes=10 + index))
    final = _attempt(repository, box, proposal_id="case-a-final", at=NOW + timedelta(hours=1))
    return final.outcome


def _confusor_unreviewed_recurrence(repository: ProductRepository) -> str:
    """Ground truth: CONFUSOR. Recurs three times with nobody ever
    reviewing it -- the pre-existing, unreviewed occurrence-count mechanism
    alone should already handle this, identically in baseline and adapted
    (this new milestone adds nothing here, by design)."""

    box = (0.10, 0.10, 0.14, 0.14)
    jitter = [(0.100, 0.100, 0.140, 0.140), (0.101, 0.101, 0.141, 0.141), (0.099, 0.099, 0.139, 0.139)]
    for index, b in enumerate(jitter):
        _attempt(repository, b, proposal_id=f"case-b-{index}", at=NOW + timedelta(minutes=index))
    final = _attempt(repository, box, proposal_id="case-b-final", at=NOW + timedelta(hours=1))
    return final.outcome


def _popular_real_perch(repository: ProductRepository) -> str:
    """Ground truth: REAL ANIMAL (a popular perch, many different real
    birds -- geometric spread protects it in both baseline and adapted)."""

    boxes = [
        (0.460, 0.630, 0.490, 0.680), (0.475, 0.650, 0.505, 0.700), (0.450, 0.610, 0.480, 0.660),
    ]
    for index, b in enumerate(boxes):
        _attempt(repository, b, proposal_id=f"case-c-{index}", at=NOW + timedelta(hours=index), confidence=0.4 + 0.05 * index)
    final = _attempt(repository, boxes[0], proposal_id="case-c-final", at=NOW + timedelta(hours=10), confidence=0.55)
    return final.outcome


def _real_bird_reviewed_once_protects(repository: ProductRepository) -> str:
    """Ground truth: REAL ANIMAL, reviewed real once early -- unconditional
    protection must hold identically in baseline and adapted."""

    box = (0.700, 0.200, 0.740, 0.240)
    jitter = [(0.700, 0.200, 0.740, 0.240), (0.701, 0.201, 0.741, 0.241), (0.699, 0.199, 0.739, 0.239)]
    created_visit_id = None
    for index, b in enumerate(jitter):
        outcome = _attempt(repository, b, proposal_id=f"case-d-{index}", at=NOW + timedelta(minutes=index))
        if outcome.outcome == "created":
            created_visit_id = outcome.visit_id
    assert created_visit_id is not None
    _review(repository, created_visit_id, "house_finch", at=NOW + timedelta(minutes=10))
    final = _attempt(repository, box, proposal_id="case-d-final", at=NOW + timedelta(hours=1))
    return final.outcome


def _insufficient_single_reviewed_false(repository: ProductRepository) -> str:
    """Ground truth: AMBIGUOUS by construction -- only one admission
    attempt, reviewed false_positive once. Below every threshold on
    purpose: the correct behavior in both baseline and adapted is to admit
    (abstain from suppressing), not to guess from one example."""

    box = (0.300, 0.800, 0.330, 0.830)
    outcome = _attempt(repository, box, proposal_id="case-e-0", at=NOW)
    if outcome.outcome == "created":
        _review(repository, outcome.visit_id, "false_positive", at=NOW + timedelta(minutes=5))
    final = _attempt(repository, box, proposal_id="case-e-final", at=NOW + timedelta(hours=1))
    return final.outcome


def _new_species_escapes_after_reviewed_false_threshold(repository: ProductRepository) -> str:
    """Ground truth: REAL ANIMAL (a genuinely new, strong detection)
    arriving at a geometry that already has enough reviewed-false evidence
    to otherwise be suspected under the adapted mechanism. Recall
    protection (the independently-strong-detection escape) must let it
    through in adapted exactly as it always would have in baseline."""

    box = (0.550, 0.400, 0.580, 0.430)
    jitter = [(0.550, 0.400, 0.580, 0.430), (0.551, 0.401, 0.581, 0.431)]
    for index, b in enumerate(jitter):
        outcome = _attempt(repository, b, proposal_id=f"case-f-{index}", at=NOW + timedelta(minutes=index), confidence=0.3)
        if outcome.outcome == "created":
            _review(repository, outcome.visit_id, "false_positive", at=NOW + timedelta(minutes=10 + index))
    final = _attempt(repository, box, proposal_id="case-f-final", at=NOW + timedelta(hours=1), confidence=0.95)
    return final.outcome


SCENARIOS: list[Scenario] = [
    Scenario("A: repeated, reviewed-false confusor (below occurrence threshold)", "confusor", _confusor_repeated_reviewed_false),
    Scenario("B: repeated, never-reviewed confusor", "confusor", _confusor_unreviewed_recurrence),
    Scenario("C: popular real perch, many real birds", "real_animal", _popular_real_perch),
    Scenario("D: real bird, reviewed real once, protected", "real_animal", _real_bird_reviewed_once_protects),
    Scenario("E: single reviewed-false example (insufficient)", "ambiguous", _insufficient_single_reviewed_false),
    Scenario("F: new strong detection after reviewed-false threshold met", "real_animal", _new_species_escapes_after_reviewed_false_threshold),
]


def _run_all(*, reviewed_evidence_enabled: bool) -> list[CaseResult]:
    with tempfile.TemporaryDirectory() as tmp:
        repository = ProductRepository(db_url=f"sqlite:///{Path(tmp) / 'mockingbird.sqlite3'}", media_root=Path(tmp) / "media")
        try:
            repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
            repository.set_scene_confusor_reviewed_evidence_enabled(
                stream_id=STREAM_ID, enabled=reviewed_evidence_enabled, now=NOW,
            )
            results = []
            for scenario in SCENARIOS:
                outcome = scenario.run(repository)
                results.append(CaseResult(scenario.name, scenario.ground_truth, outcome))
            return results
        finally:
            repository.close()


def _score(ground_truth: str, outcome: str) -> str:
    """"correct" / "incorrect" / "abstain" against this case's own
    constructed ground truth. `abstain` means the mechanism honestly
    admitted for review rather than confidently (and wrongly) guessing --
    the only scoring this milestone's own doctrine treats as always safe."""

    blocked = outcome == "blocked_scene_confusor_suspected"
    if ground_truth == "confusor":
        return "correct" if blocked else "abstain"
    if ground_truth == "real_animal":
        return "incorrect" if blocked else "correct"
    return "abstain" if not blocked else "incorrect"  # ambiguous: admitting is always the safe default


def main() -> None:
    baseline = _run_all(reviewed_evidence_enabled=False)
    adapted = _run_all(reviewed_evidence_enabled=True)

    print("Site-Specific Learning & Local Adaptation v1 -- scene-confusor reviewed-evidence counterfactual")
    print("Constructed scenario, not an organic replay (real DB has zero pre-existing regions). See module docstring.\n")
    print(f"{'Case':<58} {'Truth':<11} {'Baseline':<32} {'Adapted':<32}")
    tally = {"baseline": {"correct": 0, "incorrect": 0, "abstain": 0}, "adapted": {"correct": 0, "incorrect": 0, "abstain": 0}}
    changed = 0
    for base_case, adapt_case in zip(baseline, adapted):
        base_score = _score(base_case.ground_truth, base_case.final_outcome)
        adapt_score = _score(adapt_case.ground_truth, adapt_case.final_outcome)
        tally["baseline"][base_score] += 1
        tally["adapted"][adapt_score] += 1
        if base_case.final_outcome != adapt_case.final_outcome:
            changed += 1
        print(
            f"{base_case.name:<58} {base_case.ground_truth:<11} "
            f"{base_case.final_outcome + ' (' + base_score + ')':<32} "
            f"{adapt_case.final_outcome + ' (' + adapt_score + ')':<32}"
        )

    print(f"\n{len(SCENARIOS)} eligible constructed examples; {changed} case(s) where adapted differs from baseline.")
    print(f"Baseline: {tally['baseline']}")
    print(f"Adapted:  {tally['adapted']}")
    recall_loss = tally["adapted"]["incorrect"] - tally["baseline"]["incorrect"]
    fp_reduction = tally["baseline"]["abstain"] - tally["adapted"]["abstain"]
    print(f"\nRecall-affecting regressions (adapted 'incorrect' minus baseline 'incorrect'): {recall_loss}")
    print(f"Review-burden reduction (cases moved from 'abstain'/admit to correctly blocked): {fp_reduction}")


if __name__ == "__main__":
    main()
