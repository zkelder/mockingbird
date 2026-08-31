"""Gate A Measurement Closure v1: fragmentation accounting (see
docs/gate-a-measurement-closure-fragmentation-latency-v1-report.md
"Fragmentation truth contract").

Representative Daylight Gate A Field Acceptance v7 disclosed that running
`encounter_accounting.cluster_encounters`'s raw output through its own
`duplicate_visit_cluster_count` field and treating that as "the fragmentation
count" breaks under sustained, near-continuous activity: transitive
`ambiguous_gap_ms`-chained clustering produces very large, multi-Visit
mega-clusters (v7's own largest: 26.9 minutes, 65 distinct proposals) that
correctly contain several genuinely separate real encounters, not one
encounter wrongly split -- v7 manually confirmed two of its own flagged
"duplicate" clusters were exactly this shape. `cluster_encounters` itself is
not wrong (`encounter_accounting.py`'s own docstring already discloses it
reconstructs "a generous upper bound on what one real encounter's fragments
could be, never a persistence decision"); the gap is that nothing downstream
of it previously turned "this cluster contains more than one admitted Visit"
into a reviewable, correctable *disposition* about whether that is
fragmentation, a duplicate, simultaneous siblings, or simply several
genuinely separate encounters close together in time.

This module is that missing, explicitly human-correctable layer -- it never
replaces `cluster_encounters`, never invents a second clustering policy, and
never silently promotes a clustering heuristic into Reviewed fragmentation
truth (see "The truth boundary" / "Measured, Inferred, and Reviewed" in
product-doctrine.md):

- **Measured**: `EncounterCluster`/`ProposalOutcomeRecord` facts, unchanged,
  read from the counterfactual ledger exactly as `encounter_accounting.py`
  already produces them.
- **Inferred/suggested**: this module's own auto-classification -- a
  cluster with zero or one admitted Visit needs no review (trivially not a
  fragmentation candidate); a cluster whose admitted Visits share *any*
  underlying tracker evidence (`constituent_generation_ids`) is a confident
  `duplicate`, never `fragmented`; a cluster whose admitted Visits all share
  one Event id (Multi-Subject Visit Assembly Phase 2's own already-accepted
  "simultaneous subjects share one Event" signature -- see
  docs/multi-subject-visit-assembly-review-v1.md) with no shared evidence is
  a confident `correctly_represented` (concurrent siblings, never
  fragmentation solely from temporal proximity). Everything else -- the
  genuinely hard case v7's own report named "honestly ambiguous... does not
  have a single correct granularity" for a sustained-activity feeder scene
  -- is left `ambiguous`, deliberately never guessed.
- **Reviewed**: `apply_reviewer_dispositions` -- the only way an `ambiguous`
  unit (or a wrong auto-classification) ever becomes `fragmented`,
  `correctly_represented`, `duplicate`, `merged`, or `missed` with
  `denominator_confidence="reviewed"`. Every override requires a non-empty
  `reviewer_note`, by construction -- there is no code path that silently
  turns a guess into truth.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import, matching every sibling Stage 6.x/7 decision module in
this package (see `test_fragmentation_accounting_module_has_no_product_
repository_import`).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
from typing import Literal, Mapping, Sequence

from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord
from mockingbird.observation.encounter_accounting import EncounterCluster

FRAGMENTATION_ACCOUNTING_VERSION = "fragmentation-accounting-v1"

FragmentationDisposition = Literal[
    "correctly_represented", "fragmented", "duplicate", "merged", "missed", "ambiguous",
]

# "confident": this module's own auto-classification, from a structural
# signal strong enough to need no human review (zero/one admitted Visit,
# shared tracker evidence, or a shared-Event concurrent-sibling signature).
# "reviewed": a human supplied or overrode this unit's own disposition --
# always carries a `reviewer_note`. "ambiguous": neither -- the honest,
# first-class "cannot decide automatically" state; see product-doctrine.md
# "preserve an explicit ambiguous/unreviewable state rather than
# manufacturing precision."
DenominatorConfidence = Literal["confident", "ambiguous", "reviewed"]


@dataclass(frozen=True)
class DenominatorUnit:
    """One accounting representation of "a candidate logical wildlife
    activity unit and how the product represented it" -- the smallest
    durable shape a fragmentation disposition can attach to (see this
    milestone's own "Required fragmentation data model"). Never itself an
    `EncounterCluster` (a `denominator_unit_id` is a distinct, stable
    identity even though most units are seeded 1:1 from one cluster) and
    never itself a claim about how many real animals were present unless
    `subject_count` is set from independent review."""

    denominator_unit_id: str
    start_offset_ms: int
    end_offset_ms: int
    admitted_visit_ids: tuple[str, ...]
    disposition: FragmentationDisposition
    denominator_confidence: DenominatorConfidence
    # Only ever set from independent human review (never guessed from
    # detection/track/proposal counts -- see product-doctrine.md
    # "Wildlife-native semantics": do not assume every occurrence can be
    # accurately counted).
    subject_count: int | None = None
    reviewer_note: str | None = None
    evidence_pointer: str | None = None
    # The raw facts this unit's own auto-classification (or lack of one)
    # was decided from -- kept for audit/transparency, never itself
    # authoritative. Always JSON-serializable (str/bool/int/tuple values
    # only).
    auto_signals: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.denominator_confidence == "reviewed" and not (self.reviewer_note or "").strip():
            raise ValueError("reviewed_denominator_unit_requires_a_reviewer_note")


def _shares_any_generation(
    left: ProposalOutcomeRecord, right: ProposalOutcomeRecord,
) -> bool:
    return bool(set(left.constituent_generation_ids) & set(right.constituent_generation_ids))


def _admitted_outcomes_for_cluster(
    cluster: EncounterCluster, outcomes_by_visit_id: Mapping[str, ProposalOutcomeRecord],
) -> tuple[ProposalOutcomeRecord, ...]:
    return tuple(
        outcomes_by_visit_id[visit_id] for visit_id in cluster.admitted_visit_ids if visit_id in outcomes_by_visit_id
    )


def _classify_cluster(
    cluster: EncounterCluster,
    outcomes_by_visit_id: Mapping[str, ProposalOutcomeRecord],
    visit_event_ids: Mapping[str, str] | None,
) -> tuple[FragmentationDisposition, DenominatorConfidence, dict[str, object]]:
    admitted = _admitted_outcomes_for_cluster(cluster, outcomes_by_visit_id)
    if len(cluster.admitted_visit_ids) <= 1:
        # Nothing to fragment against -- trivially confident, never review.
        return "correctly_represented", "confident", {"reason": "single_or_no_admitted_visit"}

    shared_evidence = any(
        _shares_any_generation(admitted[i], admitted[j])
        for i in range(len(admitted)) for j in range(i + 1, len(admitted))
    )
    if shared_evidence:
        return "duplicate", "confident", {"reason": "shared_constituent_generation_ids"}

    event_ids: tuple[str, ...] | None = None
    all_one_event = None
    if visit_event_ids is not None:
        known = [visit_event_ids.get(visit_id) for visit_id in cluster.admitted_visit_ids]
        if all(item is not None for item in known):
            event_ids = tuple(dict.fromkeys(known))  # type: ignore[arg-type]
            all_one_event = len(event_ids) == 1
    if all_one_event:
        # Multi-Subject Visit Assembly Phase 2's own already-accepted
        # signature: disjoint tracker evidence (checked above) plus one
        # shared Event id is concurrent siblings, never fragmentation
        # merely because the Visits overlap or sit close together in time
        # (see this milestone's own "Fragmentation principle").
        return "correctly_represented", "confident", {
            "reason": "shared_event_id_disjoint_evidence_concurrent_siblings", "event_ids": event_ids,
        }

    # Genuinely undecidable from structure alone -- matches Representative
    # Daylight Gate A Field Acceptance v7's own honest finding for a
    # sustained-activity feeder scene: "does not have a single correct
    # granularity." Left `ambiguous`, never guessed.
    return "ambiguous", "ambiguous", {
        "reason": "multiple_admitted_visits_no_shared_evidence_no_confident_sibling_signal",
        "event_ids": event_ids,
    }


def build_denominator_units(
    clusters: Sequence[EncounterCluster],
    proposal_outcomes: Sequence[ProposalOutcomeRecord] = (),
    *,
    visit_event_ids: Mapping[str, str] | None = None,
) -> tuple[DenominatorUnit, ...]:
    """Suggest one `DenominatorUnit` per `EncounterCluster` that produced at
    least one admitted Visit -- a zero-Visit cluster is a recall question
    (already tracked separately as end-to-end Visit recall; see "Numeric
    release budgets" in roadmap.md), never a fragmentation one, and is
    deliberately not surfaced here (see `reviewer_denominator_unit` for how
    a genuinely independently-reviewed "missed" unit is authored instead).

    `visit_event_ids` is optional and purely additive -- an
    id-to-`event_id` mapping the caller already has (for example from a
    `GET /api/visits` export), used only for the concurrent-siblings auto
    -classification above; omitted, every multi-Visit cluster with no
    shared evidence is honestly `ambiguous` rather than guessed.

    Deterministic: `denominator_unit_id` is a stable sha256 of this
    version's own tag plus the cluster's own `cluster_id`, mirroring
    `EncounterCluster.cluster_id`'s own determinism convention."""

    outcomes_by_visit_id = {
        outcome.visit_id: outcome for outcome in proposal_outcomes if outcome.admitted and outcome.visit_id
    }
    units: list[DenominatorUnit] = []
    for cluster in clusters:
        if not cluster.admitted_visit_ids:
            continue
        disposition, confidence, signals = _classify_cluster(cluster, outcomes_by_visit_id, visit_event_ids)
        units.append(
            DenominatorUnit(
                denominator_unit_id="denominator:" + sha256(
                    f"{FRAGMENTATION_ACCOUNTING_VERSION}|{cluster.cluster_id}".encode()
                ).hexdigest()[:24],
                start_offset_ms=cluster.start_offset_ms,
                end_offset_ms=cluster.end_offset_ms,
                admitted_visit_ids=cluster.admitted_visit_ids,
                disposition=disposition,
                denominator_confidence=confidence,
                auto_signals=signals,
            )
        )
    return tuple(units)


@dataclass(frozen=True)
class ReviewerDisposition:
    """One human correction/confirmation for exactly one
    `denominator_unit_id` -- the only way an `ambiguous` unit (or a wrong
    auto-classification) becomes reviewed truth. `reviewer_note` is
    required and non-empty (enforced by `DenominatorUnit.__post_init__`):
    there is no override path that silently promotes a guess."""

    denominator_unit_id: str
    disposition: FragmentationDisposition
    reviewer_note: str
    subject_count: int | None = None
    evidence_pointer: str | None = None


def apply_reviewer_dispositions(
    units: Sequence[DenominatorUnit], overrides: Sequence[ReviewerDisposition],
) -> tuple[DenominatorUnit, ...]:
    """Pure override merge: every `unit` whose own id appears in
    `overrides` is replaced with the reviewer's disposition/note/subject
    count (`denominator_confidence` forced to `"reviewed"`); every other
    unit passes through unchanged. Raises on an override naming a
    `denominator_unit_id` not present in `units` -- a stale/typo'd
    reference must never be silently dropped."""

    by_id = {unit.denominator_unit_id: unit for unit in units}
    override_by_id = {item.denominator_unit_id: item for item in overrides}
    unknown = set(override_by_id) - set(by_id)
    if unknown:
        raise ValueError(f"reviewer_override_for_unknown_denominator_unit_id:{sorted(unknown)}")
    result: list[DenominatorUnit] = []
    for unit in units:
        override = override_by_id.get(unit.denominator_unit_id)
        if override is None:
            result.append(unit)
            continue
        result.append(
            replace(
                unit, disposition=override.disposition, denominator_confidence="reviewed",
                reviewer_note=override.reviewer_note, subject_count=override.subject_count,
                evidence_pointer=override.evidence_pointer,
            )
        )
    return tuple(result)


def reviewer_denominator_unit(
    denominator_unit_id: str,
    *,
    start_offset_ms: int,
    end_offset_ms: int,
    disposition: FragmentationDisposition,
    reviewer_note: str,
    admitted_visit_ids: tuple[str, ...] = (),
    subject_count: int | None = None,
    evidence_pointer: str | None = None,
) -> DenominatorUnit:
    """Author one `DenominatorUnit` directly from independent human review
    -- never suggested by `build_denominator_units` -- for the two
    dispositions that are structurally outside any single
    `EncounterCluster`'s own scope: `missed` (a real encounter an
    independent reviewer confirmed, e.g. against acceptance-recorder
    frames, that produced zero admitted Visits -- see
    docs/independent-encounter-denominator-design.md) and `merged` (a
    reviewer's own judgment that two or more separately-clustered units
    actually represent one real encounter, referenced by
    `evidence_pointer`/`reviewer_note`, not automatically detected).
    `denominator_confidence` is always `"reviewed"`."""

    return DenominatorUnit(
        denominator_unit_id=denominator_unit_id, start_offset_ms=start_offset_ms, end_offset_ms=end_offset_ms,
        admitted_visit_ids=admitted_visit_ids, disposition=disposition, denominator_confidence="reviewed",
        subject_count=subject_count, reviewer_note=reviewer_note, evidence_pointer=evidence_pointer,
    )


def _rate(numerator: int, denominator: int) -> dict[str, object]:
    """Mirrors `encounter_accounting._rate` exactly -- deliberately
    duplicated, never imported, matching this package's own established
    "self-contained pure module" convention (see
    `counterfactual_lineage._valid_box`'s own docstring for the identical
    rationale)."""
    if denominator == 0:
        return {"state": "insufficient_data", "value": None}
    return {"state": "evaluated", "value": numerator / denominator}


@dataclass(frozen=True)
class FragmentationAccountingReport:
    """The product fragmentation-rate accounting: "of the denominator units
    we could confidently or reviewedly assess as either correctly
    represented or fragmented, what fraction were fragmented." Duplicates,
    merges, misses, and ambiguous units are counted for transparency but
    deliberately excluded from `fragmentation_rate`'s own numerator and
    denominator (see this milestone's own "Fragmentation + latency
    interaction": fragmentation is evaluated separately, never diluted by
    a different concept)."""

    schema_version: int
    total_units: int
    correctly_represented_count: int
    fragmented_count: int
    duplicate_count: int
    merged_count: int
    missed_count: int
    ambiguous_count: int
    needs_review_unit_ids: tuple[str, ...]
    fragmentation_rate: dict[str, object]


def build_fragmentation_accounting_report(units: Sequence[DenominatorUnit]) -> FragmentationAccountingReport:
    counts: dict[FragmentationDisposition, int] = {
        "correctly_represented": 0, "fragmented": 0, "duplicate": 0, "merged": 0, "missed": 0, "ambiguous": 0,
    }
    for unit in units:
        counts[unit.disposition] += 1
    return FragmentationAccountingReport(
        schema_version=1,
        total_units=len(units),
        correctly_represented_count=counts["correctly_represented"],
        fragmented_count=counts["fragmented"],
        duplicate_count=counts["duplicate"],
        merged_count=counts["merged"],
        missed_count=counts["missed"],
        ambiguous_count=counts["ambiguous"],
        needs_review_unit_ids=tuple(unit.denominator_unit_id for unit in units if unit.disposition == "ambiguous"),
        fragmentation_rate=_rate(counts["fragmented"], counts["correctly_represented"] + counts["fragmented"]),
    )
