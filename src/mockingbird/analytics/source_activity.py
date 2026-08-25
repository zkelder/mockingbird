"""Place / Yard Intelligence v2: coverage-normalized, cross-Source (camera)
activity comparison, and a bounded observation-quality signal -- "which
camera currently sees the most wildlife activity" (Phase 7) and "is this
camera producing useful evidence relative to the others" (Phase 8).

Zone Insights already computes a coverage-normalized rate
(`confirmed_bird_visits_per_monitored_hour`) at per-**Zone** granularity,
nested under `stream_id`/`source_id` -- but never rolled up into one ranked
cross-Source comparison. This module fills exactly that gap by consuming an
already-gathered `VisitFact` sequence (extended with `source_id`/
`source_name`, see `place_activity_report.VisitFact`) grouped directly by
Source, reusing the same `>=2` healthy-hour minimum-support floor Zone
Insights already established rather than inventing a second number.

"Area" is deliberately not a dimension here: it is not a persisted concept
in this codebase (`ProductRepository._representative_area_name` is a
read-time, single-Zone-name convention only, never a join key) -- see
"Spatial doctrine" in product-doctrine.md. "Which monitored area is most
active" is answered at the Source level; a caller may additionally display
a Source's own representative area name for orientation, never as a
grouping key.

The quality signal (Phase 8) deliberately sources
`ObservationAuthoritySettingsModel`'s durable, per-Stream,
**lifetime-cumulative** counters, not the live counterfactual ledger: that
ledger is confirmed in-memory, per-process, released on restart, and
retains at most ~60 minutes of lineage -- it cannot answer a durable,
cross-session "this camera has a high false-positive burden" question at
all, so using it here would misrepresent an ephemeral diagnostic as durable
Place Intelligence. This module's own quality signal is explicitly
disclosed as lifetime-since-activation, never scoped to a report's own
period, and it never generates a physical-placement instruction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping

from mockingbird.analytics.place_activity_report import VisitFact, _Classification, _classify

# The same "at least 2 healthy monitored hours before a rate is trusted"
# floor `zone_insights.quality_status`/`ProductRepository._zone_insight_
# metrics` already established -- reused verbatim, not reinvented, so a
# Source-level rate and a Zone-level rate for the same camera can never
# disagree about what counts as "enough to trust."
MIN_MONITORED_HOURS_FOR_RATE = 2.0

# A Source needs at least this many lifetime `candidates_attempted_count`
# before its own admission-yield ratio is trusted at all -- a small count
# produces a noisy ratio (one suppressed candidate out of three looks
# dramatic; out of two hundred it does not).
DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL = 20

# A Source's own yield ratio must fall to at most this fraction of the
# Place's own (attempted-weighted) average yield ratio before it is flagged
# -- mirrors every other proportional-difference gate in this milestone
# (never a bare outlier off tiny counts).
DEFAULT_YIELD_RATIO_THRESHOLD = 0.5

# At least this many distinct Sources must clear the minimum-attempted
# floor before any "compared to other cameras" claim is made at all -- a
# single qualifying camera has nothing to be compared against.
MIN_QUALIFYING_SOURCES_FOR_COMPARISON = 2


@dataclass(frozen=True)
class SourceCoverageFact:
    """One Source's monitored time within the report's own window --
    `None` `monitored_seconds` means no durable exposure history exists at
    all for this Source yet (honest absence, never a fabricated zero,
    mirroring `CoverageSummary.monitored_seconds`'s own convention)."""

    source_id: str
    source_name: str
    monitored_seconds: float | None


@dataclass(frozen=True)
class SourceActivityEntry:
    """One Source's confirmed-wildlife activity, coverage-normalized where
    there is enough coverage to trust the rate."""

    source_id: str
    source_name: str
    confirmed_wildlife_visit_count: int
    monitored_seconds: float | None
    visits_per_monitored_hour: float | None
    data_sufficient: bool


def compute_source_activity(
    window_visits: Iterable[VisitFact],
    *,
    coverage_by_source: Mapping[str, SourceCoverageFact],
) -> list[SourceActivityEntry]:
    """Rank every Source in `coverage_by_source` by coverage-normalized
    confirmed-wildlife Visit rate.

    `window_visits` must already have `source_id` populated (see
    `place_activity_report.VisitFact`) and must already have had any
    cross-camera-associated duplicate excluded by the caller (via
    `_associated_visit_ids_to_exclude_from_counting`) -- this function does
    not perform that exclusion itself, so one physical encounter seen by
    two cameras is never silently double-counted here; see "Multi-camera
    behavior" in docs/place-yard-intelligence-v2-contract.md. A Visit whose
    `source_id` is not a key of `coverage_by_source` is ignored (it belongs
    to a Source outside this comparison's own scope, for example an
    archived Source the caller deliberately excluded).

    Sorted by `visits_per_monitored_hour` descending (an entry with
    `data_sufficient=False` always sorts after every sufficient entry,
    regardless of its raw count), then by raw confirmed count descending,
    then by `source_name` for a stable, explainable order.
    """

    counts: dict[str, int] = {source_id: 0 for source_id in coverage_by_source}
    for visit in window_visits:
        if visit.source_id is None or visit.source_id not in coverage_by_source:
            continue
        if _classify(visit) is not _Classification.CONFIRMED_WILDLIFE:
            continue
        counts[visit.source_id] = counts.get(visit.source_id, 0) + 1

    entries: list[SourceActivityEntry] = []
    for source_id, coverage in coverage_by_source.items():
        confirmed_count = counts.get(source_id, 0)
        monitored_hours = (coverage.monitored_seconds / 3600.0) if coverage.monitored_seconds else None
        data_sufficient = monitored_hours is not None and monitored_hours >= MIN_MONITORED_HOURS_FOR_RATE
        rate = (confirmed_count / monitored_hours) if data_sufficient and monitored_hours else None
        entries.append(
            SourceActivityEntry(
                source_id=source_id,
                source_name=coverage.source_name,
                confirmed_wildlife_visit_count=confirmed_count,
                monitored_seconds=coverage.monitored_seconds,
                visits_per_monitored_hour=round(rate, 4) if rate is not None else None,
                data_sufficient=data_sufficient,
            )
        )

    entries.sort(
        key=lambda entry: (
            entry.visits_per_monitored_hour is None,
            -(entry.visits_per_monitored_hour or 0.0),
            -entry.confirmed_wildlife_visit_count,
            entry.source_name,
        )
    )
    return entries


@dataclass(frozen=True)
class SourceAuthorityCounters:
    """One Source's lifetime-cumulative admission-authority counters,
    aggregated across that Source's Stream(s) (1:1 in practice today --
    see `camera-source-multi-camera-maturity-v1-contract.md`)."""

    source_id: str
    source_name: str
    candidates_attempted_count: int
    candidates_created_count: int
    suppressed_count: int


SourceQualitySignalValue = Literal[
    "insufficient_data", "typical_yield", "lower_yield_than_place_average"
]


@dataclass(frozen=True)
class SourceQualitySignal:
    source_id: str
    source_name: str
    candidates_attempted_count: int
    candidates_created_count: int
    suppressed_count: int
    admission_yield_ratio: float | None
    place_average_yield_ratio: float | None
    signal: SourceQualitySignalValue


def compute_source_quality_signals(
    counters: Iterable[SourceAuthorityCounters],
    *,
    min_candidates_attempted: int = DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL,
    yield_ratio_threshold: float = DEFAULT_YIELD_RATIO_THRESHOLD,
) -> list[SourceQualitySignal]:
    """Flag a Source whose own admission-yield ratio
    (`candidates_created_count / candidates_attempted_count`) is
    substantially below the Place's own attempted-weighted average --
    never a bare outlier off a handful of candidates, and never a physical
    placement instruction (Phase 8 explicitly forbids generating one)."""

    all_counters = list(counters)
    qualifying = [c for c in all_counters if c.candidates_attempted_count >= min_candidates_attempted]

    place_average: float | None = None
    if len(qualifying) >= MIN_QUALIFYING_SOURCES_FOR_COMPARISON:
        total_attempted = sum(c.candidates_attempted_count for c in qualifying)
        total_created = sum(c.candidates_created_count for c in qualifying)
        if total_attempted > 0:
            place_average = total_created / total_attempted

    results: list[SourceQualitySignal] = []
    for counter in all_counters:
        own_ratio = (
            counter.candidates_created_count / counter.candidates_attempted_count
            if counter.candidates_attempted_count > 0
            else None
        )
        signal: SourceQualitySignalValue = "insufficient_data"
        if (
            place_average is not None
            and own_ratio is not None
            and counter.candidates_attempted_count >= min_candidates_attempted
        ):
            signal = (
                "lower_yield_than_place_average"
                if own_ratio <= place_average * yield_ratio_threshold
                else "typical_yield"
            )
        results.append(
            SourceQualitySignal(
                source_id=counter.source_id,
                source_name=counter.source_name,
                candidates_attempted_count=counter.candidates_attempted_count,
                candidates_created_count=counter.candidates_created_count,
                suppressed_count=counter.suppressed_count,
                admission_yield_ratio=round(own_ratio, 4) if own_ratio is not None else None,
                place_average_yield_ratio=round(place_average, 4) if place_average is not None else None,
                signal=signal,
            )
        )
    return results
