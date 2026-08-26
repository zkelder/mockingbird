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
import random
import time
from typing import Mapping

from mockingbird.observation.contracts import CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE, EvidenceCandidate
from mockingbird.observation.evidence_scoring import EvidenceScoringBounds, score_proposal_evidence
from mockingbird.observation.visit_episode_assembler import ASSEMBLER_VERSION, AssembledVisitProposal, project_to_visit_proposal
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    ProductRepository,
)

# Concurrent Candidate Visit Persistence Reliability v1 (see docs/concurrent-
# candidate-visit-persistence-reliability-v1-report.md): the one demonstrated,
# reproducible failure -- a real `sqlalchemy.exc.OperationalError` ("database
# is locked") under real concurrent multi-Stream SQLite writes -- is retried
# *here*, at the caller boundary, never inside `ProductRepository.create_
# candidate_visit_from_proposal` itself (Multi-Camera Place Experience v2
# already tried that and reverted it -- see that method's own docstring).
# Each attempt below calls the repository method completely fresh, so it
# always opens a brand-new session/transaction; the method's own idempotency
# guarantee (re-validated from scratch every call, keyed on `proposal_id`,
# inside one atomic transaction) is what makes retrying the *whole* call
# safe -- a retried attempt either creates the candidate or discovers it was
# already created by a racing attempt and returns that same one, never a
# duplicate. Only the one classified-retryable code is retried; every other
# repository failure still fails on the very first attempt, unchanged.
_PERSISTENCE_CONTENTION_CODE = "observation_candidate_visit_persistence_contention"
#: Short, deterministic, jittered backoff between attempts -- long enough to
#: let a genuinely transient SQLite writer finish and release its lock, far
#: too short to meaningfully delay the next frame on this Stream's own
#: dedicated processing thread (a live Camera Node's own frame cadence is
#: far slower than this). Bounded: exactly 3 total attempts, never unbounded.
_PERSISTENCE_RETRY_DELAYS_SECONDS: tuple[float, ...] = (0.05, 0.15)
_MAX_PERSISTENCE_ATTEMPTS = len(_PERSISTENCE_RETRY_DELAYS_SECONDS) + 1


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
        ambiguous_boundary_resolved: bool = False,
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

        `ambiguous_boundary_resolved` is copied verbatim onto the repository
        -level proposal facts, never recomputed here: this adapter has no
        visibility into sibling proposals, so only a caller that already ran
        `candidate_visit_authority.resolve_ambiguous_boundary_arbitration`
        over the full current tick may honestly set it `True` (see
        "Ambiguous boundary arbitration" in
        docs/tracklet-visit-assembly-contract.md).

        Never raises: a repository-level failure is caught, recorded as a
        sanitized diagnostic, and returned as an ordinary `"failed"`
        outcome, so a caller driving a live observation loop can always
        continue to the next frame/proposal.

        Concurrent Candidate Visit Persistence Reliability v1: a repository
        failure classified as `_PERSISTENCE_CONTENTION_CODE` (real SQLite
        lock/busy contention -- see `ProductRepository.create_candidate_
        visit_from_proposal`'s own docstring) is retried up to
        `_MAX_PERSISTENCE_ATTEMPTS` times, fresh each time, before being
        recorded and returned as `"failed"`. Every other repository failure
        is recorded and returned exactly as before -- on the first
        attempt, no retry."""

        visit_proposal = project_to_visit_proposal(proposal)
        # Same-Frame Species Evidence v1 (see docs/same-frame-species-
        # evidence-contract.md): a `classifier_same_frame` candidate is
        # deliberately excluded from the ordinary identification/context/
        # alternate scoring competition below -- it must never displace the
        # human-facing high-resolution burst as "identification", and it is
        # not context/alternate evidence either. `_build_evidence_items`
        # gives it its own small, guaranteed, non-competitive slot instead
        # (still reading from the full, unfiltered `candidates_by_id`).
        scoring_candidates = tuple(
            candidate for candidate in evidence_candidates
            if candidate.role != CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE
        )
        selection = score_proposal_evidence(
            visit_proposal, scoring_candidates, media=evidence_bytes, bounds=self._scoring_bounds,
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
            # Multi-Subject Visit Assembly & Review v1, Phase 2: copied
            # verbatim, never recomputed here -- the assembler alone owns
            # this fact (see docs/multi-subject-visit-assembly-review-v1.md
            # and docs/tracklet-visit-assembly-contract.md "Concurrent-
            # sibling detection").
            concurrent_sibling_proposal_ids=proposal.concurrent_sibling_proposal_ids,
            # Visit Continuity / Provisional Admission Fix v1: copied
            # verbatim, never recomputed here -- the assembler alone owns
            # this fact (see docs/tracklet-visit-assembly-contract.md).
            continuation_pending=proposal.continuation_pending,
            # Ambiguous boundary arbitration: copied verbatim from this
            # call's own explicit parameter, never recomputed here -- see
            # this method's own docstring.
            ambiguous_boundary_resolved=ambiguous_boundary_resolved,
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
        attempt = 0
        retried = False
        while True:
            attempt += 1
            try:
                outcome = self._repository.create_candidate_visit_from_proposal(request)
            except ValueError as error:
                # A genuine repository/storage failure (never an ordinary
                # policy rejection -- those come back as a typed outcome,
                # not a raised error).
                failure_code = str(error) or "observation_candidate_visit_persistence_failed"
                if failure_code == _PERSISTENCE_CONTENTION_CODE and attempt < _MAX_PERSISTENCE_ATTEMPTS:
                    retried = True
                    delay = _PERSISTENCE_RETRY_DELAYS_SECONDS[attempt - 1]
                    time.sleep(delay + random.uniform(0, delay))
                    continue
                # Permanent failure, or a retryable one that exhausted its
                # bounded budget -- either way, record it and keep going;
                # this adapter must never be the reason a live observation
                # loop crashes. A retry-exhausted contention failure gets a
                # distinguishable suffix so the bounded per-Stream diagnostic
                # (`last_failure_code`) can tell "we tried and gave up" apart
                # from "this was never retryable in the first place".
                recorded_code = f"{failure_code}:retries_exhausted" if retried else failure_code
                self._repository.record_observation_authority_failure(
                    stream_id=proposal.stream_id, failure_code=recorded_code, now=observed_at,
                )
                return CandidateAttemptResult(proposal.proposal_id, "failed", failure_code, None, None)
            else:
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
    # Same-Frame Species Evidence v1: a guaranteed, non-competitive slot --
    # never chosen by the scorer (see `attempt_candidate`'s `scoring_
    # candidates` filter), so at most one exists here, deterministically
    # (dict iteration order mirrors `evidence_candidates`' own arrival
    # order). Placed right after `context`, ahead of `alternate`s, so it
    # reliably survives the repository's own bounded `max_evidence_items_
    # per_candidate` truncation (default 4) even when 3 alternates are also
    # present -- persisting this asset is the point of this milestone, an
    # extra alternate is not.
    same_frame_candidate_id = next(
        (
            candidate_id
            for candidate_id, candidate in candidates_by_id.items()
            if candidate.role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE
        ),
        None,
    )
    picks = (
        (selection.identification_candidate_id, "identification"),
        (selection.context_candidate_id, "context"),
        (same_frame_candidate_id, CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE),
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
                # Localization Attribution / Detection Geometry Lineage v1
                # (see docs/localization-attribution-contract.md): serialized
                # here, the one place this module already imports the
                # engine-side `EvidenceCandidate` -- mirrors exactly how
                # `attempt_candidate` below already serializes `proposal.
                # confidence_evidence` before it crosses into repository-level
                # vocabulary. `None` when the candidate predates this field
                # (never fabricated).
                geometry_attribution_json=(
                    json.dumps(asdict(candidate.geometry_attribution), sort_keys=True)
                    if candidate.geometry_attribution is not None
                    else None
                ),
            )
        )
    return tuple(items)
