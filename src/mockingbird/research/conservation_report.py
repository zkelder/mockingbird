"""Conservation Reporting v1 (see "Conservation Reporting v1" and "Coverage-
aware conservation semantics" in the governing milestone brief, and
docs/research-conservation-export-contract.md "Conservation report
semantics").

Answers one bounded question: "what was recorded here, under how much
defensible observation effort?" This module never claims abundance,
population size, occupancy, a biodiversity index, ecological significance, or
a decline/increase trend -- those are explicitly out of scope (see the
milestone's own "Do NOT claim" list). Every count stays a reviewed-Visit
count with its effort denominator attached, never a bare percentage or a
population inference.

This is a thin synthesis layer, exactly like `mockingbird.analytics.
daily_digest` sits above `PlaceActivityReport` -- it never re-derives Visit
truth classification or Zone/hour aggregation itself; it takes an already-
computed `PlaceActivityReport` (confirmed/provisional/unresolved counts,
per-taxon Visit counts, coverage) plus the already-resolved `VisitFact`s that
produced it (to compute per-taxon *occurrence days*, a concept
`PlaceActivityReport` does not itself carry) and an already-computed
`OfflineAcquisitionEffort` (see `mockingbird.research.acquisition_effort`),
and reshapes them into one bounded conservation summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, tzinfo, UTC
from typing import Iterable, Mapping

from mockingbird.analytics.place_activity_report import (
    PlaceActivityReport,
    ReportMaturity,
    VisitFact,
)
from mockingbird.research.acquisition_effort import OfflineAcquisitionEffort


@dataclass(frozen=True)
class ConservationSpeciesRecord:
    """One confirmed taxon's reviewed presence this period, with its own
    occurrence-day count -- never a bare Visit count alone, since a
    conservation reader needs the "how many distinct days" fact to avoid
    reading "14 visits" as "occupied the site continuously." `occurrence_
    note` is a ready-to-display sentence in the required coverage-aware
    phrasing (see `format_occurrence_note`); `None` only when usable-day
    context is not available at all."""

    label: str
    display_name: str
    scientific_name: str | None
    is_species: bool
    confirmed_visit_count: int
    occurrence_day_count: int
    first_confirmed_at: datetime
    last_confirmed_at: datetime
    occurrence_note: str | None


@dataclass(frozen=True)
class ConservationReport:
    """One bounded conservation/natural-history report. Every wildlife claim
    keeps its effort denominator attached -- see the module docstring."""

    period_start_at: datetime
    period_end_at: datetime
    generated_at: datetime
    maturity: ReportMaturity

    live_monitoring_monitored_seconds: float | None
    live_monitoring_usable_day_count: int | None

    offline_acquisition: OfflineAcquisitionEffort

    confirmed_species: list[ConservationSpeciesRecord]
    confirmed_unidentified_wildlife_visit_count: int
    reviewed_wildlife_visit_count: int
    provisional_wildlife_visit_count: int
    unresolved_visit_count: int
    total_visit_count: int

    first_activity_at: datetime | None
    last_activity_at: datetime | None

    confirmed_wildlife_visits_with_evidence_count: int


def format_occurrence_note(
    display_name: str, occurrence_day_count: int, usable_day_count: int | None
) -> str | None:
    """The one sanctioned phrasing for a per-species occurrence claim (see
    "Coverage-aware conservation semantics" in the governing milestone
    brief). Always states the effort denominator; never a percentage, and
    never a claim beyond "confirmed on N of M usable monitored days."
    `None` when no usable-day context exists yet (a report too early/sparse
    to support even this bounded a claim) -- an honest omission, not a
    fabricated "0 of 0 days.\""""

    if usable_day_count is None or usable_day_count <= 0:
        return None
    day_word = "day" if usable_day_count == 1 else "days"
    return (
        f"{display_name} was confirmed on {occurrence_day_count} of "
        f"{usable_day_count} usable monitored {day_word}."
    )


def _distinct_confirmed_days_by_label(
    visits: Iterable[VisitFact],
    *,
    valid_labels: set[str],
    local_timezone: tzinfo,
) -> dict[str, set[date]]:
    """Regroup already-classified `VisitFact`s (each one's `confirmed_taxon`
    is only ever populated when `PlaceActivityReport` itself already treated
    it as confirmed wildlife truth -- see `VisitFact.__post_init__`) by
    local calendar day. `valid_labels` restricts to labels the caller's own
    `PlaceActivityReport.taxa` already accepted, so this can never diverge
    from that report's truth precedence -- it only re-buckets the same
    already-settled facts by day, never re-classifies them."""

    days: dict[str, set[date]] = {}
    for visit in visits:
        taxon = visit.confirmed_taxon
        if taxon is None or taxon.label not in valid_labels:
            continue
        local_day = visit.activity_started_at.astimezone(local_timezone).date()
        days.setdefault(taxon.label, set()).add(local_day)
    return days


def compute_conservation_report(
    report: PlaceActivityReport,
    *,
    visits: Iterable[VisitFact],
    scientific_names_by_label: Mapping[str, str | None] = {},
    offline_acquisition: OfflineAcquisitionEffort,
    live_monitoring_usable_day_count: int | None,
    confirmed_wildlife_visits_with_evidence_count: int,
    local_timezone: tzinfo = UTC,
    generated_at: datetime | None = None,
) -> ConservationReport:
    """Compute one deterministic Conservation Report from an already-
    computed `PlaceActivityReport` (see the module docstring for why this
    never re-derives truth). `scientific_names_by_label` is an optional,
    purely additive taxonomy lookup (`TaxonomyLabelModel.scientific_name`,
    keyed by `label`) -- omitted or missing entries correctly leave
    `scientific_name=None` rather than inventing one (see "Taxonomy" in the
    governing milestone brief).
    """

    valid_labels = {entry.label for entry in report.taxa if entry.confirmed_visit_count > 0}
    days_by_label = _distinct_confirmed_days_by_label(
        visits, valid_labels=valid_labels, local_timezone=local_timezone
    )

    # `PlaceActivityReport.taxa` never contains an "unknown" (confirmed but
    # species-unresolved) entry at all -- `compute_place_activity_report`'s
    # own classification loop counts that case into `confirmed_species_
    # unresolved_visit_count` and `continue`s before ever touching its
    # per-taxon accumulator (see that module's `_Classification.CONFIRMED_
    # SPECIES_UNRESOLVED` branch). Reusing that already-computed count
    # directly -- rather than trying to rediscover it from `taxa` -- is
    # required, not stylistic.
    confirmed_unidentified_wildlife_visit_count = report.confirmed_species_unresolved_visit_count

    confirmed_species: list[ConservationSpeciesRecord] = []
    for entry in report.taxa:
        if entry.confirmed_visit_count <= 0:
            # A purely-provisional taxon (never authoritatively confirmed
            # this period) is not a conservation-report species record --
            # see `PlaceActivityReport.provisional_wildlife_visit_count` for
            # its own honest, separate accounting.
            continue
        occurrence_day_count = len(days_by_label.get(entry.label, ()))
        confirmed_species.append(
            ConservationSpeciesRecord(
                label=entry.label,
                display_name=entry.display_name,
                scientific_name=scientific_names_by_label.get(entry.label),
                is_species=entry.is_species,
                confirmed_visit_count=entry.confirmed_visit_count,
                occurrence_day_count=occurrence_day_count,
                first_confirmed_at=entry.first_activity_at,
                last_confirmed_at=entry.last_activity_at,
                occurrence_note=format_occurrence_note(
                    entry.display_name, occurrence_day_count, live_monitoring_usable_day_count
                ),
            )
        )

    confirmed_species.sort(key=lambda record: (-record.confirmed_visit_count, record.display_name.lower()))

    reviewed_wildlife_visit_count = (
        sum(record.confirmed_visit_count for record in confirmed_species)
        + confirmed_unidentified_wildlife_visit_count
    )
    assert reviewed_wildlife_visit_count == report.confirmed_wildlife_visit_count, (
        "internal accounting error: conservation species records must sum to "
        "PlaceActivityReport.confirmed_wildlife_visit_count"
    )

    return ConservationReport(
        period_start_at=report.period_start_at,
        period_end_at=report.period_end_at,
        generated_at=generated_at or report.generated_at,
        maturity=report.maturity,
        live_monitoring_monitored_seconds=(
            report.coverage.monitored_seconds if report.coverage is not None else None
        ),
        live_monitoring_usable_day_count=live_monitoring_usable_day_count,
        offline_acquisition=offline_acquisition,
        confirmed_species=confirmed_species,
        confirmed_unidentified_wildlife_visit_count=confirmed_unidentified_wildlife_visit_count,
        reviewed_wildlife_visit_count=reviewed_wildlife_visit_count,
        provisional_wildlife_visit_count=report.provisional_wildlife_visit_count,
        unresolved_visit_count=report.unresolved_visit_count,
        total_visit_count=report.total_visit_count,
        first_activity_at=report.first_activity_at,
        last_activity_at=report.last_activity_at,
        confirmed_wildlife_visits_with_evidence_count=confirmed_wildlife_visits_with_evidence_count,
    )
