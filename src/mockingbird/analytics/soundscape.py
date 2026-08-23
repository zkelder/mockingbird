"""Multimodal Observation & Soundscape v1, Phase K: the minimum useful
acoustic-history foundation (see docs/multimodal-observation-soundscape-v1-
contract.md, "Soundscape foundation").

Deliberately NOT a soundscape analytics product: no raw inference dump, no
continuous spectrogram dashboard, no ecological claim beyond the observed/
reviewed data. This is a small, pure, deterministic aggregation over already-
resolved per-Visit facts -- answering only the bounded questions the
contract names: which species were heard, how many acoustic encounters
occurred, when, and the visual-only/acoustic-only/multimodal breakdown.

Reuses the same truth-precedence discipline as
`place_activity_report.compute_place_activity_report` (confirmed always
outranks provisional; a genuinely unresolved Visit contributes no taxon) by
consuming facts the repository adapter builds from the identical canonical
resolver (`visit_fact_from_stream_visit_summary`) -- never a second
independent taxonomy/truth path. This module itself never reads a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from mockingbird.analytics.place_activity_report import TaxonFact

EvidenceModality = Literal["visual", "acoustic"]
MultimodalTier = Literal["none", "possible", "associated"]


@dataclass(frozen=True)
class SoundscapeVisitFact:
    """One Visit's already-resolved facts, as far as the soundscape summary
    needs them. `effective_taxon` is `None` for a genuinely unresolved
    Visit (no reviewed truth and no usable wildlife-species suggestion) --
    never guessed."""

    visit_id: str
    evidence_modality: EvidenceModality
    activity_started_at: datetime
    multimodal_tier: MultimodalTier
    effective_taxon: TaxonFact | None = None


@dataclass(frozen=True)
class SpeciesHeardEntry:
    label: str
    display_name: str
    encounter_count: int


@dataclass(frozen=True)
class HourlyAcousticActivity:
    """`hour` is 0-23, local to whatever timezone the caller's `SoundscapeVisitFact.activity_started_at` values were already normalized to -- this module performs no timezone conversion of its own."""

    hour: int
    encounter_count: int


@dataclass(frozen=True)
class SoundscapeSummary:
    period_start: datetime
    period_end: datetime
    species_heard: tuple[SpeciesHeardEntry, ...]
    acoustic_encounter_count: int
    visual_only_count: int
    acoustic_only_count: int
    multimodal_count: int
    hourly_acoustic_activity: tuple[HourlyAcousticActivity, ...]


def compute_soundscape_summary(
    visits: tuple[SoundscapeVisitFact, ...],
    *,
    period_start: datetime,
    period_end: datetime,
) -> SoundscapeSummary:
    """Pure aggregation over already-resolved facts for one period. Never
    reads a database, never invents a species, never claims abundance or a
    population trend -- only observed/reviewed counts for this period."""

    acoustic_visits = [v for v in visits if v.evidence_modality == "acoustic"]
    visual_visits = [v for v in visits if v.evidence_modality == "visual"]

    # "multimodal" is judged per-Visit from its own strongest association
    # tier -- both a visual and an acoustic Visit belonging to the same
    # associated pair each independently count as multimodal, matching the
    # per-Visit shape every other count in this summary already uses (a
    # single "encounter" identity spanning two Visit rows does not exist in
    # the current schema -- see the contract doc's "Known limitations").
    visual_only_count = sum(1 for v in visual_visits if v.multimodal_tier == "none")
    acoustic_only_count = sum(1 for v in acoustic_visits if v.multimodal_tier == "none")
    multimodal_count = sum(1 for v in visits if v.multimodal_tier != "none")

    species_totals: dict[str, SpeciesHeardEntry] = {}
    for visit in acoustic_visits:
        if visit.effective_taxon is None:
            continue
        existing = species_totals.get(visit.effective_taxon.label)
        if existing is None:
            species_totals[visit.effective_taxon.label] = SpeciesHeardEntry(
                label=visit.effective_taxon.label,
                display_name=visit.effective_taxon.display_name,
                encounter_count=1,
            )
        else:
            species_totals[visit.effective_taxon.label] = SpeciesHeardEntry(
                label=existing.label, display_name=existing.display_name,
                encounter_count=existing.encounter_count + 1,
            )
    species_heard = tuple(
        sorted(species_totals.values(), key=lambda entry: (-entry.encounter_count, entry.label))
    )

    hourly_counts: dict[int, int] = {}
    for visit in acoustic_visits:
        hour = visit.activity_started_at.hour
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
    hourly_acoustic_activity = tuple(
        HourlyAcousticActivity(hour=hour, encounter_count=hourly_counts[hour])
        for hour in sorted(hourly_counts)
    )

    return SoundscapeSummary(
        period_start=period_start,
        period_end=period_end,
        species_heard=species_heard,
        acoustic_encounter_count=len(acoustic_visits),
        visual_only_count=visual_only_count,
        acoustic_only_count=acoustic_only_count,
        multimodal_count=multimodal_count,
        hourly_acoustic_activity=hourly_acoustic_activity,
    )
