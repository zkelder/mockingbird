"""Place / Yard Intelligence v2: time-of-day / daylight intelligence --
"mostly seen early in the morning," "usually observed during daylight," and
"was this observation's timing typical for this species here."

`place_activity_report.compute_taxon_place_patterns` already computes raw
`hour_activity`/`most_active_hour` over the same 366-day window this module
reuses; this module adds two things that do not exist yet: a day/night
dimension (using the accepted `solar_local` day/night facts, absence-safe
when coordinates are not configured) and a plain-language time-of-day band,
plus a single-Visit "was this typical" comparison. See
docs/place-yard-intelligence-v2-contract.md section 3.5.

Day/night is an intraday (per-Visit) fact, not a per-calendar-day one, so it
does not fit `conditional_association`'s date-set shape -- this stays its
own small, dedicated module rather than being forced through that
generic primitive.

No civil timezone is invented from longitude anywhere in this module: every
`local_hour` a caller passes in must already come from the same
`resolve_host_local_timezone`/explicit-timezone convention every sibling
module in this package uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import tzinfo
from typing import Iterable, Literal, Mapping

from mockingbird.analytics.place_activity_report import (
    MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN,
    TaxonFact,
    VisitFact,
)

DaylightBucket = Literal["day", "night"]

TimeOfDayBand = Literal[
    "early_morning", "morning", "midday", "afternoon", "evening", "night"
]

DaylightAssociation = Literal[
    "insufficient_data", "mostly_daytime", "mostly_nighttime", "spans_day_and_night"
]

VisitTypicality = Literal["typical", "unusual", "insufficient_data"]

# A daylight bucket needs a supermajority, not a bare majority, to be called
# "mostly" one or the other -- a near-50/50 split is genuinely "spans both,"
# not weakly "mostly" one side, matching the milestone's own instruction not
# to manufacture a confident-sounding claim from a marginal split.
_DAYLIGHT_DOMINANCE_THRESHOLD = 0.75

# A Visit's own hour is "unusual" only when it falls outside every band that
# together holds at least this fraction of the taxon's own reviewed
# activity -- a simple, explainable coverage rule (Phase 18), not a
# statistical test.
_TYPICAL_HOUR_COVERAGE_THRESHOLD = 0.90

# A Visit's own hour is always "typical" if it falls within this many hours
# of the taxon's own most-active hour, regardless of the coverage rule
# above -- guards against a taxon with perfectly flat, genuinely all-day
# activity having every single hour read as "unusual."
_TYPICAL_HOUR_TOLERANCE = 3


def time_of_day_band(local_hour: int) -> TimeOfDayBand:
    """A fixed, non-solar, purely clock-hour banding -- deliberately not
    tied to that day's actual sunrise/sunset (which would need a per-date
    solar lookup this cheap classifier should not require). `"early_morning"`
    5-7, `"morning"` 8-10, `"midday"` 11-13, `"afternoon"` 14-16,
    `"evening"` 17-19, `"night"` 20-4."""

    if not 0 <= local_hour <= 23:
        raise ValueError("local_hour must be 0..23")
    if 5 <= local_hour <= 7:
        return "early_morning"
    if 8 <= local_hour <= 10:
        return "morning"
    if 11 <= local_hour <= 13:
        return "midday"
    if 14 <= local_hour <= 16:
        return "afternoon"
    if 17 <= local_hour <= 19:
        return "evening"
    return "night"


@dataclass(frozen=True)
class TaxonTemporalPattern:
    """One taxon's time-of-day / daylight pattern over the reviewed Visits
    it was given."""

    taxon: TaxonFact
    reviewed_visit_count: int
    day_count: int
    night_count: int
    unknown_daylight_count: int
    daylight_association: DaylightAssociation
    hour_counts: tuple[tuple[int, int], ...]  # (local_hour 0-23, count), all 24 present
    dominant_band: TimeOfDayBand | None  # gated by MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN
    most_active_hour: int | None  # gated the same way


def _daylight_association(day_count: int, night_count: int) -> DaylightAssociation:
    total = day_count + night_count
    if total == 0:
        return "insufficient_data"
    day_fraction = day_count / total
    if day_fraction >= _DAYLIGHT_DOMINANCE_THRESHOLD:
        return "mostly_daytime"
    if (1 - day_fraction) >= _DAYLIGHT_DOMINANCE_THRESHOLD:
        return "mostly_nighttime"
    return "spans_day_and_night"


def compute_taxon_temporal_patterns(
    visits: Iterable[VisitFact],
    *,
    daylight_by_visit_id: Mapping[str, DaylightBucket],
    local_timezone: tzinfo,
) -> dict[str, TaxonTemporalPattern]:
    """Compute one `TaxonTemporalPattern` per taxon with at least one
    confirmed Visit in `visits`.

    `daylight_by_visit_id` is deliberately a caller-supplied, possibly
    partial mapping: a Visit absent from it (solar not configured for that
    calendar date, or at all) contributes to neither `day_count` nor
    `night_count`, only `unknown_daylight_count` -- never a fabricated
    guess. This mirrors `historical_baseline`'s own "insufficiently
    monitored" honesty discipline, applied to daylight data instead of
    monitoring coverage.
    """

    hour_counts_by_taxon: dict[str, list[int]] = {}
    day_counts: dict[str, int] = {}
    night_counts: dict[str, int] = {}
    unknown_counts: dict[str, int] = {}
    taxa: dict[str, TaxonFact] = {}

    for visit in visits:
        if visit.confirmed_taxon is None:
            continue
        label = visit.confirmed_taxon.label
        taxa[label] = visit.confirmed_taxon
        hours = hour_counts_by_taxon.setdefault(label, [0] * 24)
        local_hour = visit.activity_started_at.astimezone(local_timezone).hour
        hours[local_hour] += 1

        bucket = daylight_by_visit_id.get(visit.visit_id)
        if bucket == "day":
            day_counts[label] = day_counts.get(label, 0) + 1
        elif bucket == "night":
            night_counts[label] = night_counts.get(label, 0) + 1
        else:
            unknown_counts[label] = unknown_counts.get(label, 0) + 1

    results: dict[str, TaxonTemporalPattern] = {}
    for label, taxon in taxa.items():
        hours = hour_counts_by_taxon[label]
        reviewed_visit_count = sum(hours)
        day_count = day_counts.get(label, 0)
        night_count = night_counts.get(label, 0)
        unknown_count = unknown_counts.get(label, 0)

        dominant_band: TimeOfDayBand | None = None
        most_active_hour: int | None = None
        if reviewed_visit_count >= MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN:
            most_active_hour = max(range(24), key=lambda hour: (hours[hour], -hour))
            band_totals: dict[TimeOfDayBand, int] = {}
            for hour, count in enumerate(hours):
                if count:
                    band = time_of_day_band(hour)
                    band_totals[band] = band_totals.get(band, 0) + count
            if band_totals:
                dominant_band = max(band_totals, key=lambda band: (band_totals[band], band))

        results[label] = TaxonTemporalPattern(
            taxon=taxon,
            reviewed_visit_count=reviewed_visit_count,
            day_count=day_count,
            night_count=night_count,
            unknown_daylight_count=unknown_count,
            daylight_association=_daylight_association(day_count, night_count),
            hour_counts=tuple((hour, count) for hour, count in enumerate(hours)),
            dominant_band=dominant_band,
            most_active_hour=most_active_hour,
        )

    return results


def compare_visit_timing(local_hour: int, pattern: TaxonTemporalPattern) -> VisitTypicality:
    """Was `local_hour` typical for this taxon's own established pattern?

    `"insufficient_data"` whenever the pattern itself has no
    `most_active_hour` (below the minimum-sample floor) -- never guessed at
    from too little history. Otherwise: typical when within
    `_TYPICAL_HOUR_TOLERANCE` hours of the taxon's own most-active hour, OR
    when the smallest set of hours covering `_TYPICAL_HOUR_COVERAGE_
    THRESHOLD` of this taxon's own reviewed activity includes `local_hour`;
    `"unusual"` otherwise.
    """

    if not 0 <= local_hour <= 23:
        raise ValueError("local_hour must be 0..23")
    if pattern.most_active_hour is None or pattern.reviewed_visit_count == 0:
        return "insufficient_data"

    hour_distance = min(
        abs(local_hour - pattern.most_active_hour),
        24 - abs(local_hour - pattern.most_active_hour),
    )
    if hour_distance <= _TYPICAL_HOUR_TOLERANCE:
        return "typical"

    ordered_hours = sorted(pattern.hour_counts, key=lambda item: (-item[1], item[0]))
    covered = 0
    threshold_count = _TYPICAL_HOUR_COVERAGE_THRESHOLD * pattern.reviewed_visit_count
    typical_hours: set[int] = set()
    for hour, count in ordered_hours:
        if covered >= threshold_count:
            break
        if count == 0:
            continue
        typical_hours.add(hour)
        covered += count

    return "typical" if local_hour in typical_hours else "unusual"
