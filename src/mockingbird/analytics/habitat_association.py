"""Place / Yard Intelligence v2: bounded, association-only wildlife-activity
/ recorded-phenology associations -- "goldfinches were observed more often
while flowering was current," never a causal claim.

This is the honest ceiling of what Phase 11 (Habitat / Phenology
Associations) can build today: `PlacePhenologyObservationModel` is an
*interval* fact (an observed phenomenon with a start date and an optional
end date -- see `mockingbird.habitat.phenology`), not a discrete
before/after *change-event* model. No such change-event concept exists
anywhere in this codebase (confirmed by exhaustive grep for
`change_event`/`before_state`/`after_state` across `src/mockingbird`), so a
true "wildlife activity changed after this reviewed habitat change"
comparison is **not built** here -- see
docs/place-yard-intelligence-v2-contract.md section 6. What this module
*can* honestly do, using the interval facts that do exist, is compare a
taxon's presence-day rate on usable days while a phenomenon was current
against usable days it was not, reusing `conditional_association`'s
generic, gated primitive.

Reviewed habitat facts remain authoritative and are never inferred by this
module: `phenology_observations` must already be reviewed
`PlacePhenologyObservationModel` rows (see `mockingbird.habitat.phenology`'s
own `HABITAT_INFORMATION_CLASS = "reviewed"`). This module performs no
automatic plant/phenology inference of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from typing import AbstractSet, Iterable, Mapping

from mockingbird.analytics.conditional_association import (
    ConditionalAssociation,
    compute_conditional_association,
)
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.seasonal_pattern import presence_dates_by_taxon

# A phenomenon's own interval needs to cover at least this many usable days
# before any taxon association is even attempted against it -- avoids
# computing (and then discarding as insufficient_data) an association for a
# phenomenon logged only a day or two ago.
MIN_CONDITION_INTERVAL_DAYS = 5


@dataclass(frozen=True)
class PhenologyIntervalFact:
    """The minimal shape this module needs from one reviewed
    `PlacePhenologyObservationModel` row -- deliberately not importing the
    full repository/API type, matching this package's "stay
    dependency-free" convention (see `daily_digest.py`'s own local Literal
    re-declarations)."""

    subject_label: str
    phenomenon: str
    observed_start_date: date
    observed_end_date: date | None  # None means "still ongoing"


@dataclass(frozen=True)
class TaxonHabitatAssociation:
    """One taxon's presence-rate association with one recorded phenology
    interval."""

    taxon: TaxonFact
    subject_label: str
    phenomenon: str
    association: ConditionalAssociation


def _condition_dates(observation: PhenologyIntervalFact, *, window_end_at: date) -> set[date]:
    end = observation.observed_end_date or window_end_at
    if end < observation.observed_start_date:
        return set()
    span_days = (end - observation.observed_start_date).days
    return {observation.observed_start_date + timedelta(days=offset) for offset in range(span_days + 1)}


def compute_habitat_associations(
    window_visits: Iterable[VisitFact],
    *,
    taxa: Mapping[str, TaxonFact],
    usable_dates: AbstractSet[date],
    local_timezone: tzinfo,
    phenology_observations: Iterable[PhenologyIntervalFact],
    window_end_at: datetime,
) -> list[TaxonHabitatAssociation]:
    """Compute one `TaxonHabitatAssociation` per (taxon, phenomenon) pair
    that has any realistic chance of clearing `conditional_association`'s
    own minimum-sample gate -- a pair with too short an interval is skipped
    silently rather than returned as a guaranteed `insufficient_data`
    result, keeping the output list short and worth reading (Phase 28's
    product-value test: do not surface a result nobody can act on).

    Returns an empty list when `phenology_observations` is empty -- missing
    habitat/phenology data must never break core Place intelligence (Phase
    10/16's coverage-safety instruction, applied here to habitat data too).
    """

    window_end_date = window_end_at.astimezone(local_timezone).date()
    presence_by_taxon = presence_dates_by_taxon(window_visits, local_timezone=local_timezone)

    results: list[TaxonHabitatAssociation] = []
    for observation in phenology_observations:
        condition_dates = _condition_dates(observation, window_end_at=window_end_date)
        if len(usable_dates & condition_dates) < MIN_CONDITION_INTERVAL_DAYS:
            continue
        if len(usable_dates - condition_dates) < MIN_CONDITION_INTERVAL_DAYS:
            continue

        for label, taxon in taxa.items():
            presence_dates = presence_by_taxon.get(label, set())
            if not presence_dates:
                continue
            association = compute_conditional_association(
                presence_dates, usable_dates=usable_dates, condition_dates=condition_dates
            )
            if association.status == "insufficient_data":
                continue
            results.append(
                TaxonHabitatAssociation(
                    taxon=taxon,
                    subject_label=observation.subject_label,
                    phenomenon=observation.phenomenon,
                    association=association,
                )
            )

    return results
