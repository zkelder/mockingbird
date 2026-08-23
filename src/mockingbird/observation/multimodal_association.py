"""Multimodal Observation & Soundscape v1, Phase D: a bounded, deterministic
decision for whether one candidate Visit and a set of opposite-modality
candidate Visits describe the same wildlife encounter, a merely-coincident
one, or are clearly independent.

Explicitly NOT a probabilistic fusion framework (see "Governing doctrine" in
docs/multimodal-observation-soundscape-v1-contract.md): every threshold here
is a fixed, disclosed constant, not a learned or tuned score. This module
never reads a species/taxon suggestion at all -- association is timing-only;
agreement/conflict is a separate, read-time-only concern (see
`product_repository.py`'s `_multimodal_association_summary`), matching "do
not require same species suggestion for temporal association."

Direction-agnostic by design: the same `evaluate_temporal_association` runs
for "one new acoustic Visit vs. nearby visual candidates" and "one visual
Event's full sibling set vs. nearby acoustic candidates" -- the caller
decides which side is the `subject` and which is the `candidates` list. See
`ProductRepository._reconcile_multimodal_association_for_event` for how the
repository assembles each side's candidate set (always the *current*, full
set -- including every visual sibling -- never a partial snapshot; this
matters for the multi-subject downgrade case below).

Tiers:

- ``"associated"``: exactly one opposite-modality candidate is in range at
  all, and it is within the strict window -- confident enough for Today/
  Bird Log presentation to merge into one history entry and for Research
  Export to record a multimodal fact.
- ``"possible"``: temporally coincident but not confidently exclusive --
  more than one candidate competes for the same subject, or the sole match
  is only within the wider (non-strict) window. Surfaced to a reviewer,
  never merged into one history entry.

"Independent" is not a tier value at all: a candidate outside even the wider
window is simply absent from the result -- the caller persists no
`VisitAssociationModel` row for it rather than recording a third,
always-false state (never fabricate a relationship that was never found).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mockingbird.observation.temporal_evidence import EvidenceInterval, interval_relationship_ms

AssociationTier = Literal["associated", "possible"]

#: Deterministic, disclosed constants -- not yet field-tuned (see "Hardware-
#: deferred acceptance" in the contract doc: real colocated camera+
#: microphone timing has not been measured yet). BirdNET clips are
#: typically a few seconds to tens of seconds; a visual candidate Visit can
#: span from a couple of seconds to several minutes. A bird is not always
#: audibly vocalizing at the exact instant it is visible, so some slack
#: beyond raw interval overlap is deliberate, bounded, and disclosed here
#: rather than hidden inside a black-box score.
STRICT_WINDOW_MS = 15_000
POSSIBLE_WINDOW_MS = 60_000

#: Bumped only if the tiering rule itself changes -- persisted on every
#: `VisitAssociationModel` row so a future stricter/looser engine can tell
#: which rule produced a given historical row without guessing, mirroring
#: `ObservationCandidateVisitModel.assembler_version`'s own precedent.
ENGINE_VERSION = "multimodal-association-v1"


@dataclass(frozen=True)
class AssociationConfig:
    strict_window_ms: int = STRICT_WINDOW_MS
    possible_window_ms: int = POSSIBLE_WINDOW_MS


@dataclass(frozen=True)
class AssociationCandidate:
    """The minimal facts the engine needs about one opposite-modality
    Visit -- callers build this from already-loaded `VisitModel`/
    `EventModel` rows; this module never touches the ORM/session itself
    (pure decision module convention, matching `scene_confusor.py`)."""

    visit_id: str
    interval: EvidenceInterval


@dataclass(frozen=True)
class AssociationDecision:
    visit_id: str
    tier: AssociationTier
    overlap_ms: int
    gap_ms: int


def evaluate_temporal_association(
    subject: EvidenceInterval,
    candidates: tuple[AssociationCandidate, ...],
    *,
    config: AssociationConfig = AssociationConfig(),
) -> tuple[AssociationDecision, ...]:
    """Decide, for one `subject` interval, which of the already-queried
    opposite-modality `candidates` it should link to and at what tier.

    Conservative by construction (Phase H, "multiple subjects/multiple
    species"): when more than one candidate falls in range at all, NONE of
    them is `"associated"` -- a piece of evidence is never confidently
    attributed to one of several simultaneous competitors, only honestly
    marked `"possible"` against each. A candidate outside even the wider
    `possible_window_ms` is dropped entirely from the result (independent).

    Pure and order-independent: calling this twice with the same inputs
    always returns the same decisions, in the same order as `candidates`
    -- required for both idempotent re-association after restart
    (Scenario 9) and the repository's own full-recompute-then-upsert
    reconciliation (see module docstring)."""

    in_range: list[tuple[AssociationCandidate, int, int]] = []
    for candidate in candidates:
        overlap_ms, gap_ms = interval_relationship_ms(subject, candidate.interval)
        if overlap_ms > 0 or gap_ms <= config.possible_window_ms:
            in_range.append((candidate, overlap_ms, gap_ms))

    if not in_range:
        return ()

    unambiguous = len(in_range) == 1
    decisions: list[AssociationDecision] = []
    for candidate, overlap_ms, gap_ms in in_range:
        is_strict = overlap_ms > 0 or gap_ms <= config.strict_window_ms
        tier: AssociationTier = "associated" if (unambiguous and is_strict) else "possible"
        decisions.append(
            AssociationDecision(visit_id=candidate.visit_id, tier=tier, overlap_ms=overlap_ms, gap_ms=gap_ms)
        )
    return tuple(decisions)


TaxonAgreement = Literal["agrees", "differs", "not_comparable"]


def classify_taxon_agreement(
    subject_label: str | None, candidate_label: str | None,
) -> TaxonAgreement:
    """Read-time-only agreement classification (Phase F/G) -- never an
    input to `evaluate_temporal_association` above, and never persisted (a
    suggestion can change after a re-run; agreement is always recomputed
    from whatever the two Visits' current top suggestions are). Case/
    whitespace-normalized exact match on the same taxonomy-normalized
    `suggested_label`/`reviewed_label` string both modalities already
    write -- no new taxonomy resolution, no fuzzy matching, no synthetic
    fused confidence. Either side missing/blank (an abstained or not-yet-
    suggested Visit) is honestly `"not_comparable"`, never treated as a
    conflict."""

    a = (subject_label or "").strip().casefold()
    b = (candidate_label or "").strip().casefold()
    if not a or not b:
        return "not_comparable"
    return "agrees" if a == b else "differs"
