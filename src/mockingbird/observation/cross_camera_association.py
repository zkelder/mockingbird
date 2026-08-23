"""Camera / Source + Multi-Camera Maturity v1, Phase I: a bounded,
deterministic decision for whether one visual candidate Event and a
same-modality candidate Event on a *different* Source (a different camera)
describe the same wildlife encounter, a merely-coincident one, or are
clearly independent.

This is deliberately the smallest defensible v1, not a tracking/
re-identification model (see "Governing doctrine," Phase I, in the
milestone brief): it reuses `multimodal_association.evaluate_temporal_
association` completely unchanged for the timing signal -- that function
was already written direction-agnostic ("the same `evaluate_temporal_
association` runs for... the caller decides which side is the `subject`
and which is the `candidates` list") -- and adds exactly two additional,
downgrade-only gates on top, both required to be satisfied simultaneously
before a pair can ever reach the confident `"associated"` tier:

1. **Single-subject on both sides.** Two cameras each showing more than one
   concurrent subject (multi-subject Events, Phase J) can never be
   confidently paired -- there is no way to tell *which* subject on Camera A
   corresponds to *which* subject on Camera B from timing alone, so any such
   pair is capped at `"possible"` even if timing alone looked unambiguous.
   This mirrors, and is a direct generalization of, the existing engine's
   own "more than one candidate in range -> none associated" conservatism.
2. **Spatial plausibility.** Unlike a microphone and a camera (which a user
   deliberately co-located on purpose), two cameras are not presumed to
   cover overlapping physical space just because their timestamps are
   close -- two feeders 50 feet apart can both see the same common species
   constantly, entirely independently. Lacking real per-camera geometry for
   most installations, this uses the one real, already-user-authored
   spatial fact available: whether both Streams have an unambiguous single
   representative "Area" name (see `ProductRepository._representative_area_
   name`). Three cases, not two: both sides name the *same* Area
   (`"matching_area_name"`, the only case that can reach `"associated"`);
   both sides name a *different* Area (`"differing_area_name"`) -- real,
   user-authored evidence of physical separation, so this candidate is
   dropped entirely, exactly as if it were never in temporal range at all,
   and (importantly) never counts toward the "how many candidates are
   competing" ambiguity check below either; or one or both sides have no
   unambiguous Area at all (`"unknown"`) -- genuine ambiguity, capped at
   `"possible"`. A future pass with real Yard Map placement geometry
   (`YardMapStreamPlacementModel`) could add a second, richer signal; this
   v1 deliberately does not attempt field-of-view geometry (see "Known
   bounded gaps" in the milestone report).

`"associated"` therefore requires: a matching Area name, and -- among only
the candidates that were not already dropped for a confirmed differing
Area -- exactly one competitor in temporal range, the strict timing window,
and exactly one Visit on each side. Every other still-in-range case is
honestly `"possible"` -- surfaced to a reviewer, never auto-merged.
`classify_taxon_agreement` (already in `multimodal_association.py`) is
reused unmodified and, exactly as for multimodal pairs, is never an input
to tiering here either -- species/taxon equality alone never creates or
upgrades an association.

Pure and dependency-light, matching this package's `scene_confusor.py`/
`multimodal_association.py` "pure decision module" convention: this module
never touches the ORM/session/database itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mockingbird.observation.multimodal_association import (
    AssociationCandidate,
    AssociationConfig,
    AssociationTier,
    evaluate_temporal_association,
)
from mockingbird.observation.temporal_evidence import EvidenceInterval

#: Bumped only if this tiering rule itself changes -- persisted on every
#: `CrossCameraVisitAssociationModel` row, mirroring `multimodal_
#: association.ENGINE_VERSION`'s own precedent.
ENGINE_VERSION = "cross-camera-association-v1"

#: Why (if at all) the spatial-plausibility gate passed or failed. A
#: candidate with `"differing_area_name"` never appears in the returned
#: decisions at all (see module docstring) -- this value only ever shows up
#: read-time, resolved fresh from current Zone data, for a pair that a
#: reviewer is looking at directly (Visit Detail); it is not itself a tier
#: input.
SpatialSignal = Literal["matching_area_name", "differing_area_name", "unknown"]


@dataclass(frozen=True)
class CrossCameraEventCandidate:
    """The minimal facts needed about one nearby, different-Source visual
    Event -- callers (`ProductRepository._reconcile_cross_camera_
    association_for_event`) build this from already-loaded `EventModel`/
    `VisitModel`/`ZoneModel` rows; this module never touches the ORM
    itself."""

    event_id: str
    interval: EvidenceInterval
    sibling_visit_count: int
    area_name: str | None


@dataclass(frozen=True)
class CrossCameraAssociationDecision:
    event_id: str
    tier: AssociationTier
    overlap_ms: int
    gap_ms: int
    spatial_signal: SpatialSignal
    multi_subject: bool


def evaluate_cross_camera_association(
    subject_interval: EvidenceInterval,
    *,
    subject_sibling_count: int,
    subject_area_name: str | None,
    candidates: tuple[CrossCameraEventCandidate, ...],
    config: AssociationConfig = AssociationConfig(),
) -> tuple[CrossCameraAssociationDecision, ...]:
    """Decide, for one `subject` visual Event, which of the already-queried
    different-Source `candidates` it should link to and at what tier.

    Conservative by construction, and pure/order-independent exactly like
    `evaluate_temporal_association` (required for idempotent re-association
    and the repository's own full-recompute-then-upsert reconciliation)."""

    def _spatial_signal(area_name: str | None) -> SpatialSignal:
        if subject_area_name is None or area_name is None:
            return "unknown"
        if subject_area_name.strip().casefold() == area_name.strip().casefold():
            return "matching_area_name"
        return "differing_area_name"

    # A confirmed-differing Area is real, user-authored evidence of physical
    # separation -- dropped before temporal ambiguity is even evaluated, so
    # it never counts as a "competing candidate" against a genuinely
    # plausible one (see module docstring).
    plausible = tuple(
        candidate for candidate in candidates if _spatial_signal(candidate.area_name) != "differing_area_name"
    )
    temporal_candidates = tuple(
        AssociationCandidate(visit_id=candidate.event_id, interval=candidate.interval)
        for candidate in plausible
    )
    temporal_decisions = {
        decision.visit_id: decision
        for decision in evaluate_temporal_association(subject_interval, temporal_candidates, config=config)
    }

    decisions: list[CrossCameraAssociationDecision] = []
    for candidate in plausible:
        temporal = temporal_decisions.get(candidate.event_id)
        if temporal is None:
            continue  # Outside even the wider window -- independent, no row at all.

        spatial_signal = _spatial_signal(candidate.area_name)
        multi_subject = subject_sibling_count != 1 or candidate.sibling_visit_count != 1

        tier: AssociationTier = temporal.tier
        if tier == "associated" and (multi_subject or spatial_signal != "matching_area_name"):
            tier = "possible"

        decisions.append(
            CrossCameraAssociationDecision(
                event_id=candidate.event_id,
                tier=tier,
                overlap_ms=temporal.overlap_ms,
                gap_ms=temporal.gap_ms,
                spatial_signal=spatial_signal,
                multi_subject=multi_subject,
            )
        )
    # Stable, input-order output for deterministic callers/tests.
    order = {candidate.event_id: index for index, candidate in enumerate(candidates)}
    return tuple(sorted(decisions, key=lambda decision: order[decision.event_id]))
