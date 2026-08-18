"""Encounter-level accounting: reconstructing plausible real-world wildlife
encounters from already-retained Observation Engine lineage (Admission
Recall Investigation + Conditional Fix v1; see "Ambiguous boundary
arbitration" in docs/tracklet-visit-assembly-contract.md).

Every prior accounting pass in this package
(`detection_quality_accounting.py`, `counterfactual_lineage.py`) is scoped
to raw/track/proposal *artifacts* -- deliberately, since those are the
system's own honest units of work. A real biological encounter is a
different, coarser unit: one visible animal appearance may be split, by the
tracker's own conservative bounded confirmation policy and the assembler's
own conservative ambiguity policy, into many tracks, generations, and
proposals (see "Wildlife-native semantics" in product-doctrine.md: do not
assume every occurrence can be accurately counted). This module answers a
narrower, complementary question: given already-retained track-generation
lineage for one bounded window, what is a defensible, reproducible
*encounter*-level grouping, and how many of those groupings reached each
stage of the required funnel --
`genuine visible encounter -> detected -> viable proposal -> Visit`?

`total_encounter_clusters` (see `EncounterFunnelReport`) is this module's
own reconstructed candidate-encounter count -- an evidence-based, disclosed
*reconstruction* from geometry/timestamp/lineage facts, never the "genuine
visible encounter" ground truth itself. Only independent human observation
can supply that denominator; this module never claims otherwise, and a
caller must not use MockingBird's own Visit list as the source of truth for
what wildlife actually occurred.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every sibling Stage
6.x/7 decision module in this package follows. Reuses the assembler's own
already-calibrated geometry/gap tolerance
(`visit_episode_assembler.boxes_geometry_compatible`) rather than a second,
independently-drifting clustering policy -- this module's own clustering is
deliberately *more permissive* than the assembler's own episode assembly:
it clusters both confirmed and unconfirmed generations, and never itself
distinguishes a confident merge from an ambiguous one (any temporally- and
geometrically-compatible pair joins one candidate encounter). That is
intentional: this module answers "could a human reviewer plausibly call
these fragments the same encounter," a coarser, more inclusive question
than "may these fragments become one persisted Visit" -- reusing the
assembler's *tolerance formula* without reusing its *conservatism*.

Confidence-based plausibility tiers are disclosed evidence, never a truth/
animal-presence judgment (see "The truth boundary" in product-doctrine.md):
a cluster with a genuinely strong detection at some point is materially
more likely to be a real animal than one whose own detector confidence
never rose above a persistent low floor across many minutes -- exactly the
"hard negative" shape this codebase has already documented more than once
(see docs/sustained-visit-continuity-contract.md's own attempt-2 red-glass
-feeder clutter, whose measured maximum score, 0.417, never once reached
`strong_detection_threshold`). No tier is ever reported as a certainty;
`insufficient_evidence` is a first-class, honest outcome, never silently
defaulted away -- see "preserve an explicit ambiguous/unreviewable state
rather than manufacturing precision" in this milestone's own governing
constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, Sequence

from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord, TrackGenerationRecord
from mockingbird.observation.visit_episode_assembler import VisitAssemblyConfiguration, boxes_geometry_compatible

ENCOUNTER_ACCOUNTING_VERSION = "encounter-accounting-v1"

BoundingBox = tuple[float, float, float, float]

EncounterPlausibility = Literal[
    "strong_confidence", "moderate_confidence", "weak_confidence", "insufficient_evidence",
]

# Reused, not invented: `STRONG_CONFIDENCE_THRESHOLD` mirrors `frame_tracker.
# TrackerConfiguration.strong_detection_threshold`'s own deployed default
# (see docs/sustained-visit-continuity-contract.md); `MODERATE_CONFIDENCE_
# FLOOR` mirrors Detection Quality Accounting v1's own shadow-evaluated
# ~0.3 threshold, the best-measured true-positive/false-positive tradeoff
# point on real reviewed historical data (never promoted to production --
# see "Production authority gate" in docs/detection-quality-accounting
# -contract.md -- but a legitimate, precedented number for a *disclosure*
# tier here, not a new admission policy).
STRONG_CONFIDENCE_THRESHOLD = 0.7
MODERATE_CONFIDENCE_FLOOR = 0.3


@dataclass(frozen=True)
class EncounterCluster:
    """One deterministic, defensible grouping of temporally- and
    geometrically-compatible track generations -- a candidate real-world
    encounter, never itself a claim that exactly one animal was present
    (see "A biological encounter is the denominator" in this milestone's
    own governing constraints). `cluster_id` is a stable sha256 of its own
    sorted constituent generation ids, mirroring `visit_episode_assembler.
    _proposal_id`'s own determinism convention -- the same input always
    reproduces the same id."""

    cluster_id: str
    generation_ids: tuple[str, ...]
    confirmed_generation_ids: tuple[str, ...]
    start_offset_ms: int
    end_offset_ms: int
    geometry_envelope: BoundingBox
    max_confidence: float | None
    total_detection_count: int
    # Every distinct `proposal_id` any of this cluster's own *confirmed*
    # generations was ever a constituent of (an unconfirmed generation
    # never reaches Visit assembly at all -- see `build_tracklets`).
    proposal_ids: tuple[str, ...]
    admitted_visit_ids: tuple[str, ...]
    outcome_reasons: tuple[str, ...]

    @property
    def duration_ms(self) -> int:
        return self.end_offset_ms - self.start_offset_ms

    @property
    def has_confirmed_tracking(self) -> bool:
        return bool(self.confirmed_generation_ids)

    @property
    def has_viable_proposal(self) -> bool:
        return bool(self.proposal_ids)

    @property
    def has_visit(self) -> bool:
        return bool(self.admitted_visit_ids)

    @property
    def is_fragmented(self) -> bool:
        """More than one raw track generation for this one candidate
        encounter -- the tracker-fragmentation fact this milestone
        explicitly warns must not be conflated with encounter count."""
        return len(self.generation_ids) > 1

    @property
    def has_multiple_proposals(self) -> bool:
        """More than one distinct assembled proposal for this one
        candidate encounter -- proposal-level fragmentation, a distinct,
        usually-smaller number than track fragmentation (the assembler
        already merges confident-boundary generations together)."""
        return len(self.proposal_ids) > 1

    @property
    def plausibility(self) -> EncounterPlausibility:
        """Disclosed, non-authoritative evidence tier -- see this module's
        own docstring. Never treated as proof of a real animal or of
        clutter; a human reviewer's own visual judgment is the only
        authority for that (see "The truth boundary" in
        product-doctrine.md)."""
        if self.max_confidence is None:
            return "insufficient_evidence"
        if self.max_confidence >= STRONG_CONFIDENCE_THRESHOLD:
            return "strong_confidence"
        if self.max_confidence >= MODERATE_CONFIDENCE_FLOOR:
            return "moderate_confidence"
        return "weak_confidence"


def _union_box(boxes: Sequence[BoundingBox]) -> BoundingBox:
    return (
        min(box[0] for box in boxes), min(box[1] for box in boxes),
        max(box[2] for box in boxes), max(box[3] for box in boxes),
    )


def cluster_encounters(
    track_generations: Sequence[TrackGenerationRecord],
    proposal_outcomes: Sequence[ProposalOutcomeRecord] = (),
    *,
    config: VisitAssemblyConfiguration | None = None,
) -> tuple[EncounterCluster, ...]:
    """Deterministic, order-independent connected-components clustering of
    `track_generations` (confirmed *and* unconfirmed -- see this module's
    own docstring for why unconfirmed generations are included here even
    though `visit_episode_assembler.build_tracklets` correctly excludes
    them from Visit assembly) into candidate real-world encounters.

    Two generations join one cluster when they share a `broad_class`, do
    not temporally overlap (an overlap is either two simultaneous/crossing
    subjects or a tracker-association artifact -- either way, never one
    encounter, mirroring `classify_boundary`'s own "incompatible" rule),
    and are within `config.ambiguous_gap_ms` of each other with `visit_
    episode_assembler.boxes_geometry_compatible` geometry across that gap
    -- the identical outer bound and tolerance formula the assembler
    itself already uses, reused rather than reinvented. Clustering is
    transitive (a chain of pairwise-compatible generations joins one
    cluster even if the first and last are not themselves directly
    compatible), unlike the assembler's own bounded per-episode ambiguity
    scope -- an intentional difference: this module reconstructs a
    generous upper bound on what one real encounter's fragments could be,
    never a persistence decision.

    `proposal_outcomes` is optional and purely additive: when supplied,
    each cluster's `proposal_ids`/`admitted_visit_ids`/`outcome_reasons`
    are populated from whichever recorded outcomes reference one of the
    cluster's own confirmed generation ids -- omitted, every cluster
    honestly reports these as empty rather than guessed. Bounded: cost is
    O(n^2) pairwise comparisons over `track_generations`, matching the
    counterfactual ledger's own bounded per-session retention (at most a
    few thousand generations), never intended for an unbounded corpus.
    """

    config = config or VisitAssemblyConfiguration()
    ordered = sorted(
        track_generations, key=lambda item: (item.start_offset_ms, item.end_offset_ms, item.generation_id),
    )
    count = len(ordered)
    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root

    for i in range(count):
        earlier = ordered[i]
        for j in range(i + 1, count):
            later = ordered[j]
            if later.start_offset_ms < earlier.end_offset_ms:
                continue  # temporal overlap: never one encounter
            gap_ms = later.start_offset_ms - earlier.end_offset_ms
            if gap_ms > config.ambiguous_gap_ms:
                continue
            if earlier.broad_class != later.broad_class:
                continue
            if boxes_geometry_compatible(earlier.end_bounding_box, later.start_bounding_box, gap_ms, config):
                union(i, j)

    members_by_root: dict[int, list[TrackGenerationRecord]] = {}
    for index in range(count):
        members_by_root.setdefault(find(index), []).append(ordered[index])

    # A live session re-attempts the identical `proposal_id` on every tick
    # it stays `blocked_continuation_pending` (see docs/tracklet-visit
    # -assembly-contract.md "Episode finality") -- `proposal_outcomes` can
    # legitimately hold several records for one proposal id, and only the
    # *last-decided* one is that proposal's own actual final fate (an
    # earlier, superseded `blocked_continuation_pending` record must never
    # shadow a later `created`/`blocked_ambiguous_boundary` verdict for the
    # same id). Deduplicated once, globally, before per-generation lookup,
    # since a given proposal's own constituent generations never change
    # across repeated attempts.
    latest_outcome_by_proposal_id: dict[str, ProposalOutcomeRecord] = {}
    for outcome in proposal_outcomes:
        existing = latest_outcome_by_proposal_id.get(outcome.proposal_id)
        if existing is None or _decision_offset(outcome) >= _decision_offset(existing):
            latest_outcome_by_proposal_id[outcome.proposal_id] = outcome

    proposals_by_generation: dict[str, list[ProposalOutcomeRecord]] = {}
    for outcome in latest_outcome_by_proposal_id.values():
        for generation_id in outcome.constituent_generation_ids:
            proposals_by_generation.setdefault(generation_id, []).append(outcome)

    clusters = [_build_cluster(members, proposals_by_generation) for members in members_by_root.values()]
    return tuple(sorted(clusters, key=lambda item: item.start_offset_ms))


def _decision_offset(outcome: ProposalOutcomeRecord) -> int:
    """`decided_at_offset_ms` is the honest, source-relative fact this
    module prefers (never a wall clock); `end_offset_ms` is a reasonable,
    always-present fallback for a caller/fixture that never supplied it,
    never a fabricated value -- both already monotonic with real decision
    order in practice (a proposal's own tail only ever grows later)."""
    return outcome.decided_at_offset_ms if outcome.decided_at_offset_ms is not None else outcome.end_offset_ms


def _build_cluster(
    members: list[TrackGenerationRecord],
    proposals_by_generation: dict[str, list[ProposalOutcomeRecord]],
) -> EncounterCluster:
    ordered = sorted(members, key=lambda item: (item.start_offset_ms, item.generation_id))
    generation_ids = tuple(item.generation_id for item in ordered)
    confirmed_ids = tuple(item.generation_id for item in ordered if item.confirmed)

    seen_proposal_ids: set[str] = set()
    outcomes: list[ProposalOutcomeRecord] = []
    for generation_id in confirmed_ids:
        for outcome in proposals_by_generation.get(generation_id, ()):
            if outcome.proposal_id not in seen_proposal_ids:
                seen_proposal_ids.add(outcome.proposal_id)
                outcomes.append(outcome)

    confidences = [
        item.confidence_evidence.max_confidence for item in ordered
        if item.confidence_evidence.max_confidence is not None
    ]
    return EncounterCluster(
        cluster_id="encounter:" + sha256(
            "|".join((ENCOUNTER_ACCOUNTING_VERSION, *generation_ids)).encode()
        ).hexdigest()[:24],
        generation_ids=generation_ids,
        confirmed_generation_ids=confirmed_ids,
        start_offset_ms=min(item.start_offset_ms for item in ordered),
        end_offset_ms=max(item.end_offset_ms for item in ordered),
        geometry_envelope=_union_box([item.geometry_envelope for item in ordered]),
        max_confidence=max(confidences) if confidences else None,
        total_detection_count=sum(item.confidence_evidence.detection_count for item in ordered),
        proposal_ids=tuple(sorted(seen_proposal_ids)),
        admitted_visit_ids=tuple(sorted({outcome.visit_id for outcome in outcomes if outcome.visit_id})),
        outcome_reasons=tuple(sorted({outcome.outcome for outcome in outcomes})),
    )


@dataclass(frozen=True)
class EncounterFunnelReport:
    """Encounter-level funnel counts for the required accounting:
    `genuine visible encounter -> detected -> viable proposal -> Visit`.
    `total_encounter_clusters` is this module's own reconstruction, not
    the "genuine visible encounter" ground truth -- see this module's own
    docstring and this milestone's own "Do not use MockingBird's own Visit
    list as the source of truth for what wildlife occurred." Every rate
    uses the `{"state": ..., "value": ...}` convention already established
    by `detection_quality_accounting.py`/`replay.py`: `insufficient_data`
    rather than a fabricated number when its own denominator is zero."""

    schema_version: int
    total_encounter_clusters: int
    clusters_with_confirmed_tracking: int
    clusters_with_viable_proposal: int
    clusters_with_visit: int
    fragmented_cluster_count: int
    multi_proposal_cluster_count: int
    plausibility_counts: dict[str, int]
    admitted_visit_count: int
    # A cluster whose own reconstructed span attracted more than one
    # *admitted* Visit id -- a directly-measurable duplicate-Visit signal,
    # distinct from `multi_proposal_cluster_count` (multiple proposals
    # attempted; not all necessarily admitted).
    duplicate_visit_cluster_count: int
    tracking_recall: dict[str, object]
    proposal_recall: dict[str, object]
    admission_recall: dict[str, object]


def _rate(numerator: int, denominator: int) -> dict[str, object]:
    if denominator == 0:
        return {"state": "insufficient_data", "value": None}
    return {"state": "evaluated", "value": numerator / denominator}


def build_encounter_funnel_report(clusters: Sequence[EncounterCluster]) -> EncounterFunnelReport:
    """Pure aggregation over already-clustered encounters -- see
    `cluster_encounters`. Every count/rate here answers a question about
    *reconstructed candidate encounters*, never raw tracks or proposals
    directly, satisfying this milestone's own "Do not count every
    fragmented track as a miss or every detection as an independent
    animal.\""""

    total = len(clusters)
    with_tracking = sum(1 for cluster in clusters if cluster.has_confirmed_tracking)
    with_proposal = sum(1 for cluster in clusters if cluster.has_viable_proposal)
    with_visit = sum(1 for cluster in clusters if cluster.has_visit)
    fragmented = sum(1 for cluster in clusters if cluster.is_fragmented)
    multi_proposal = sum(1 for cluster in clusters if cluster.has_multiple_proposals)
    duplicates = sum(1 for cluster in clusters if len(cluster.admitted_visit_ids) > 1)

    plausibility_counts: dict[str, int] = {}
    for cluster in clusters:
        plausibility_counts[cluster.plausibility] = plausibility_counts.get(cluster.plausibility, 0) + 1

    return EncounterFunnelReport(
        schema_version=1,
        total_encounter_clusters=total,
        clusters_with_confirmed_tracking=with_tracking,
        clusters_with_viable_proposal=with_proposal,
        clusters_with_visit=with_visit,
        fragmented_cluster_count=fragmented,
        multi_proposal_cluster_count=multi_proposal,
        plausibility_counts=plausibility_counts,
        admitted_visit_count=sum(len(cluster.admitted_visit_ids) for cluster in clusters),
        duplicate_visit_cluster_count=duplicates,
        tracking_recall=_rate(with_tracking, total),
        proposal_recall=_rate(with_proposal, with_tracking),
        admission_recall=_rate(with_visit, with_proposal),
    )
