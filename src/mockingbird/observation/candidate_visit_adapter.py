"""Stage 7 candidate-Visit persistence adapter.

This is the one module in the whole Observation Engine v2 tree that imports
both the shadow assembler's output type and the product repository -- see
"Persistence adapter boundary" in docs/candidate-visit-authority-contract.md:

    VisitEpisodeAssembler -> AssembledVisitProposal
                           -> (this module) -> authority gate
                           -> product repository candidate Visit creation

`visit_episode_assembler.py` itself has no knowledge of this module or of
`mockingbird.repository` at all (enforced by
`test_visit_episode_assembler.py::test_no_product_repository_dependency` and
this package's own `test_candidate_visit_authority.py` structural test).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from typing import Mapping

from mockingbird.observation.contracts import EvidenceCandidate
from mockingbird.observation.evidence_scoring import EvidenceScoringBounds, score_proposal_evidence
from mockingbird.observation.visit_episode_assembler import ASSEMBLER_VERSION, AssembledVisitProposal, project_to_visit_proposal
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    ProductRepository,
)


@dataclass(frozen=True)
class CandidateAttemptResult:
    """What the caller (a live session driver, a replay/offline harness, or
    a test) actually needs to know about one attempt -- deliberately not the
    raw repository outcome type, so this module stays the one seam between
    engine-side and repository-side vocabulary."""

    proposal_id: str
    outcome: str
    reason: str
    visit_id: str | None
    event_id: str | None

    @property
    def created(self) -> bool:
        return self.outcome == "created"


class CandidateVisitAuthorityAdapter:
    """Bounded orchestration only: score already-retained evidence, project
    it into the repository's plain request shape, call the repository, and
    never let a repository failure escape as an unhandled exception. Holds
    no authority state of its own -- every decision still happens inside
    `ProductRepository.create_candidate_visit_from_proposal`'s own
    transaction; this class never duplicates that policy."""

    def __init__(
        self,
        repository: ProductRepository,
        *,
        detector_provenance: str | None = None,
        tracker_provenance: str | None = None,
        provider_key: str | None = None,
        scoring_bounds: EvidenceScoringBounds | None = None,
    ) -> None:
        self._repository = repository
        self._detector_provenance = detector_provenance
        self._tracker_provenance = tracker_provenance
        self._provider_key = provider_key
        self._scoring_bounds = scoring_bounds

    def attempt_candidate(
        self,
        proposal: AssembledVisitProposal,
        *,
        evidence_candidates: tuple[EvidenceCandidate, ...],
        evidence_bytes: Mapping[str, bytes],
        observed_at: datetime,
    ) -> CandidateAttemptResult:
        """Score `proposal`'s already-retained evidence exactly the way
        Stage 6 already does (`evidence_scoring.score_proposal_evidence`,
        unchanged), build the bounded evidence items this adapter can
        actually back with real bytes, and hand the whole request to the
        repository. `evidence_bytes` is a bounded, caller-owned lookup
        (e.g. a live session's own bounded burst-payload cache, or a
        replay/test fixture's synthetic bytes) keyed by `EvidenceCandidate.
        media_asset_id` -- a candidate with no entry here is honestly
        skipped, never fabricated.

        Never raises: a repository-level failure is caught, recorded as a
        sanitized diagnostic, and returned as an ordinary `"failed"`
        outcome, so a caller driving a live observation loop can always
        continue to the next frame/proposal."""

        visit_proposal = project_to_visit_proposal(proposal)
        selection = score_proposal_evidence(
            visit_proposal, evidence_candidates, media=evidence_bytes, bounds=self._scoring_bounds,
        )
        candidates_by_id = {candidate.media_asset_id: candidate for candidate in evidence_candidates}
        evidence_items = _build_evidence_items(candidates_by_id, selection, evidence_bytes)
        facts = CandidateVisitProposalFacts(
            proposal_id=proposal.proposal_id,
            stream_id=proposal.stream_id,
            zone_id=proposal.zone_id,
            broad_class=proposal.broad_class,
            start_offset_ms=proposal.start_offset_ms,
            end_offset_ms=proposal.end_offset_ms,
            constituent_generation_ids=proposal.constituent_generation_ids,
            constituent_track_ids=proposal.constituent_track_ids,
            source_capture_frame_ids=proposal.source_capture_frame_ids,
            supporting_frame_ids=proposal.supporting_frame_ids,
            evidence_candidate_ids=proposal.evidence_candidate_ids,
            limitation_facts=proposal.limitation_facts,
            ambiguous_adjacent_proposal_ids=proposal.ambiguous_adjacent_proposal_ids,
            assembler_version=ASSEMBLER_VERSION,
            detector_provenance=self._detector_provenance,
            tracker_provenance=self._tracker_provenance,
            provider_key=self._provider_key,
            # Detection Quality Accounting v1 (see
            # docs/detection-quality-accounting-contract.md): this proposal's
            # own merged detector-confidence/evidence accounting, persisted
            # as diagnostic lineage on the Stage 7 ledger row -- evidence for
            # quality accounting / shadow admission-policy evaluation,
            # never itself observational authority or reviewed truth.
            confidence_evidence_json=json.dumps(asdict(proposal.confidence_evidence), sort_keys=True),
        )
        request = CreateCandidateVisitRequest(proposal=facts, observed_at=observed_at, evidence_items=evidence_items)
        try:
            outcome = self._repository.create_candidate_visit_from_proposal(request)
        except ValueError as error:
            # A genuine repository/storage failure (never an ordinary policy
            # rejection -- those come back as a typed outcome, not a raised
            # error). Record it and keep going; this adapter must never be
            # the reason a live observation loop crashes.
            failure_code = str(error) or "observation_candidate_visit_persistence_failed"
            self._repository.record_observation_authority_failure(failure_code=failure_code, now=observed_at)
            return CandidateAttemptResult(proposal.proposal_id, "failed", failure_code, None, None)
        return CandidateAttemptResult(
            outcome.proposal_id, outcome.outcome, outcome.reason, outcome.visit_id, outcome.event_id,
        )


def _build_evidence_items(
    candidates_by_id: Mapping[str, EvidenceCandidate],
    selection,
    evidence_bytes: Mapping[str, bytes],
) -> tuple[CandidateEvidenceItem, ...]:
    """Translate the scorer's own identification/context/alternate picks
    into bounded, byte-backed evidence items -- skipping (never
    fabricating) any pick this adapter has no real bytes for. The
    repository applies the final count/byte bounds; this only avoids
    building an item with nothing behind it."""

    items: list[CandidateEvidenceItem] = []
    seen: set[str] = set()
    picks = (
        (selection.identification_candidate_id, "identification"),
        (selection.context_candidate_id, "context"),
        *((candidate_id, "alternate") for candidate_id in selection.alternate_candidate_ids),
    )
    for candidate_id, role in picks:
        if candidate_id is None or candidate_id in seen:
            continue
        candidate = candidates_by_id.get(candidate_id)
        content = evidence_bytes.get(candidate_id)
        if candidate is None or not content:
            continue
        seen.add(candidate_id)
        content_type = "image/jpeg" if content.startswith(b"\xff\xd8") else "application/octet-stream"
        items.append(
            CandidateEvidenceItem(
                engine_media_id=candidate.media_asset_id,
                role=role,
                content=content,
                content_type=content_type,
                width=candidate.width,
                height=candidate.height,
                captured_at=candidate.captured_at,
                subject_geometry=candidate.subject_geometry,
            )
        )
    return tuple(items)
