"""Place Features & Habitat Change v2: coverage-normalized activity for one
Place Feature's own monitored scope -- "how active is this feeder" (Phase
12 of the governing brief), and, given more than one comparable Feature,
"which one is more active" (Phase 13).

Deliberately the same shape as `source_activity.compute_source_activity`,
scoped one level finer (a Feature's own Zone, or its Source when no Zone is
linked, rather than a whole Source) and extended with a distinct-taxon
diversity count -- reusing the identical `>=2` healthy-hour minimum-support
floor rather than inventing a second number, so a Feature-level rate and a
Source-level rate for the same camera can never disagree about what counts
as "enough to trust." A Feature's own scoped `monitored_seconds` (not
reimplemented here -- see `ProductRepository._feature_scoped_coverage`)
comes from the exact same durable `MonitoringExposureIntervalModel` ledger
every other coverage figure in this product reads, at whatever Stream
granularity the Feature's own association resolves to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mockingbird.analytics.place_activity_report import VisitFact, _Classification, _classify

# Reused verbatim from `source_activity.MIN_MONITORED_HOURS_FOR_RATE` /
# `zone_insights.quality_status`'s identical floor -- never a new number.
MIN_MONITORED_HOURS_FOR_RATE = 2.0


@dataclass(frozen=True)
class FeatureYield:
    """One Place Feature's confirmed-wildlife activity within its own
    associated monitoring scope, coverage-normalized where there is enough
    coverage to trust the rate. `monitored_seconds=None` means no durable
    exposure history exists at all yet for this Feature's scope -- an
    honest absence, never a fabricated zero (mirrors
    `SourceCoverageFact`/`CoverageSummary`'s own convention)."""

    confirmed_wildlife_visit_count: int
    distinct_taxon_count: int
    monitored_seconds: float | None
    visits_per_monitored_hour: float | None
    data_sufficient: bool


def compute_feature_yield(
    window_visits: Iterable[VisitFact],
    *,
    monitored_seconds: float | None,
) -> FeatureYield:
    """`window_visits` must already be scoped to exactly this Feature's own
    association (its Zone, or its Source's Streams) and already have had
    any cross-camera-associated duplicate excluded by the caller -- this
    function performs neither scoping nor exclusion itself, matching
    `compute_source_activity`'s identical "the caller has already scoped
    and deduplicated" contract."""

    confirmed = [visit for visit in window_visits if _classify(visit) is _Classification.CONFIRMED_WILDLIFE]
    distinct_taxa = {visit.confirmed_taxon.label for visit in confirmed if visit.confirmed_taxon is not None}
    monitored_hours = (monitored_seconds / 3600.0) if monitored_seconds else None
    data_sufficient = monitored_hours is not None and monitored_hours >= MIN_MONITORED_HOURS_FOR_RATE
    rate = (len(confirmed) / monitored_hours) if data_sufficient and monitored_hours else None
    return FeatureYield(
        confirmed_wildlife_visit_count=len(confirmed),
        distinct_taxon_count=len(distinct_taxa),
        monitored_seconds=monitored_seconds,
        visits_per_monitored_hour=round(rate, 4) if rate is not None else None,
        data_sufficient=data_sufficient,
    )


__all__ = ["MIN_MONITORED_HOURS_FOR_RATE", "FeatureYield", "compute_feature_yield"]
