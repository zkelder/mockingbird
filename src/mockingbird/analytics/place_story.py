"""Place Story & Seasonal Timeline v1: a small, derived read-model that
composes already-authoritative Place facts -- wildlife regularity/history,
Reviewed Place Feature changes, Reviewed phenology observations, and
period-recap digests -- into one chronological, ranked "Place Story," so a
person can answer "what happened here, when, and why does MockingBird think
it mattered" without mentally stitching together five separate surfaces
themselves (see docs/place-story-seasonal-timeline-v1-report.md).

## Reuse, not a second analytics/truth path

This module never queries a database, never re-derives review truth, and
never invents a new statistical threshold. Every event kind is either:

- a direct, dated projection of an already-Reviewed fact (`PlaceFeatureChangeEvent.
  effective_date`, `PlacePhenologyObservation.observed_start_date`) -- zero new
  logic, just a stable id and a plain-language title/summary; or
- a thin re-application of an existing, accepted pure decision function
  (`historical_baseline.compute_species_historical_statuses`, `place_change_summary.
  compute_place_change_windows`/`compute_place_change_summary`, `regularity_narrative.
  compute_regularity_narrative`) evaluated at one or more historical checkpoints
  instead of only "now" -- see `detect_regularity_transition_events` below for why
  that is honest and bounded, not a second regularity model.

## Why "checkpoints," not a per-Visit or per-day scan

`compute_place_change_summary` (and, through it, `compute_regularity_narrative`)
answers "what is this taxon's regularity state as of one instant" -- a snapshot,
not an event log. There is no persisted "regularity changed on date X" fact
anywhere in this codebase (confirmed by exhaustive archaeology before this module
was written), and Phase 2/6 of the governing milestone brief are explicit: do not
invent a second, divergent definition of "quiet period" just to attach a date to
it. So this module re-evaluates the *existing, unmodified* snapshot classification
at a bounded sequence of historical checkpoints spanning the requested period, and
reports the first checkpoint at which a taxon's (or the Place's overall) state
changes -- exactly the state a person checking Today or Bird Log *would have seen*
had they looked that day.

Checkpoints land on every distinct **usable** calendar date in the lookback-padded
period, not a fixed calendar stride (a first implementation tried weekly
striding; a synthetic-history regression test caught it silently *missing* a real
`"returned_after_absence"` transition whenever the narrow instant where
`reference_presence_days` is exactly `0` fell on a non-checkpoint day -- see
`test_place_story.py`). This is not arbitrary: `compute_place_change_windows`
walks backward through `usable_dates` only, so the recent/reference window
membership -- and therefore every downstream classification -- provably cannot
change on a calendar day that is not itself newly usable; checkpointing on every
other date would be redundant, and skipping *any* usable date risks exactly the
miss above. A non-monitored stretch (no usable days) costs nothing extra: there
is simply nothing to checkpoint there. This still satisfies the brief's Phase 6
"meaningful transition/hysteresis" requirement -- not by coarse checkpoint
spacing, but structurally: the underlying comparison itself is windowed in
7-usable-day/14-usable-day units (`place_change_summary.RECENT_WINDOW_USABLE_DAYS`/
`REFERENCE_WINDOW_USABLE_DAYS`), so the *classification* it returns cannot move
faster than about a week's worth of usable days regardless of how often it is
sampled; only genuine transitions are ever recorded (`_record_transition`'s own
previous-state dedup), never a re-fire for an unchanged state.

Every checkpoint call passes its own historical instant as `window_end_at` --
never "now" -- mirroring `ProductRepository._historical_place_baseline_and_
species_statuses`'s own documented discipline ("a report for a past period
always reproduces the same historical facts regardless of when it is re-viewed").
A Place Story event for a past day is therefore reproducible from persisted
facts, not a snapshot of whatever "now" happened to look like when computed.

## A discovered gap in the existing composition: `"returned_after_absence"`

`place_change_summary._presence_status` returns `"no_supported_change"`
unconditionally whenever `reference_presence_days < MIN_REFERENCE_PRESENCE_
DAYS_FOR_COMPARISON` (i.e. whenever it is `0`) -- so `TaxonChangeStatus.status`
can never actually be `"higher_recent_presence"` at the same time
`reference_presence_days == 0`. That means `regularity_narrative.compute_
regularity_narrative`'s own documented `"returned_after_absence"` branch
(`change_status == "higher_recent_presence" and reference_presence_days == 0`)
is structurally unreachable through the only existing caller composition
(confirmed by a synthetic-history regression test in `test_place_story.py`
before this fix; `place_change_summary.py`'s own docstring explains the `>= 1`
floor as deliberately deferring the "never seen in the reference window" case
to `historical_baseline`'s "new"/"first_record" handling -- correct for a
genuinely brand-new taxon, but that reasoning does not hold for an
already-established taxon's real absence-then-return, which is exactly the
case `regularity_narrative.py` names and this milestone brief's own headline
example describes).

This module does not patch `place_change_summary.py` to close that gap --
that module is frozen, already governs Today's and Bird Log's own live
digest wording today, and "Threshold policy (versioned)" changes there are
explicitly outside a Place Story milestone's authority (see Phase 6 of the
governing brief: "use existing... primitives," not rewrite them). Instead,
`_effective_regularity_state` below applies one narrow, clearly-labeled
supplemental check using only fields `compute_place_change_summary` already
computes correctly (`TaxonChangeStatus.reference_presence_days`/`.recent_
presence_days` -- the *counts* are right; only the derived `.status` collapses
them) and the module's own already-versioned `MIN_ABSOLUTE_PRESENCE_DAY_
DIFFERENCE` constant (reused, not reinvented) as the "is this recent presence
non-trivial" bar. See "Remaining major PRODUCT opportunities" in
docs/place-story-seasonal-timeline-v1-report.md for the recommendation to
revisit `place_change_summary.py` itself in a future, dedicated milestone.

## Truth boundary

Every wildlife-kind event here is built only from `_Classification.CONFIRMED_WILDLIFE`
facts (via the exact same `historical_baseline`/`place_change_summary` inputs, which
already enforce that boundary) -- a provisional SpeciesSuggestion can never create,
extend, or antedate a Place Story milestone. Every Place-kind event
(`feature_change`, `phenology`) is a direct projection of an already-`information_
class="reviewed"` record. `comparison_insight` events are always `"inferred"` and
are kept as a separate event from the `feature_change` they explain -- never fused
into one causal sentence (see product-doctrine.md's "External ecological context"
and Phase 8 of the governing brief).

## What this module deliberately does NOT do

- It never creates one event per Visit -- Bird Log already owns granular
  chronological wildlife history; see Phase 4/14 of the governing brief.
- It never suppresses a Reviewed Place fact (`feature_change`/`phenology`) by
  importance -- only wildlife-derived candidate events are selected/ranked; a
  user-recorded Place fact always appears (Phase 13's explicit instruction).
- It never fabricates a causal ecological claim, individual-animal identity, or
  a "the same animal returned" implication (product-doctrine.md's "Wildlife-native
  semantics"; every wildlife event describes the *taxon's* presence at this Place).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo
from typing import AbstractSet, Iterable, Literal, Mapping, Sequence

from mockingbird.analytics.historical_baseline import (
    SpeciesHistoricalStatus,
    compute_baseline_maturity,
    compute_species_historical_statuses,
)
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.place_change_summary import (
    MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE,
    PlaceChangeStatusValue,
    TaxonChangeStatus,
    compute_place_change_summary,
    compute_place_change_windows,
)
from mockingbird.analytics.regularity_narrative import (
    RegularityStateValue,
    compute_regularity_narrative,
)

# ---------------------------------------------------------------------------
# Vocabulary (Phase 3 of the governing brief: small, product-legible, never
# exposed raw in normal UI copy -- `title`/`summary` on each event already
# carry the plain-language reader-facing text).
# ---------------------------------------------------------------------------

PlaceStoryEventGroup = Literal["wildlife", "place", "context", "summary"]

PlaceStoryEventKind = Literal[
    # wildlife
    "first_seen",
    "return",
    "regularity_change",
    "noteworthy_activity",
    "diversity_milestone",
    # place
    "feature_change",
    "phenology",
    # context
    "comparison_insight",
    # summary
    "period_summary",
]

_KIND_GROUP: dict[PlaceStoryEventKind, PlaceStoryEventGroup] = {
    "first_seen": "wildlife",
    "return": "wildlife",
    "regularity_change": "wildlife",
    "noteworthy_activity": "wildlife",
    "diversity_milestone": "wildlife",
    "feature_change": "place",
    "phenology": "place",
    "comparison_insight": "context",
    "period_summary": "summary",
}

# Two tiers only (Phase 13): every event kind this module actually emits was
# already selected for inclusion (Phase 4's suppression happens upstream, in
# *whether* an event is created at all -- see the module docstring), so
# nothing surviving that gate is ever "minor." Kept as a real, small,
# interpretable weighting -- never a black-box score -- and User-recorded
# Place facts are never demoted below "notable" regardless of algorithmic
# signal strength (Phase 13's explicit instruction).
PlaceStoryImportance = Literal["major", "notable"]

InformationClass = Literal["measured", "inferred", "reviewed"]

# Species-debut milestones worth naming -- small, fixed, deterministic tiers,
# never a continuously-scored "achievement" (Phase 21: no gamification).
DIVERSITY_MILESTONE_ORDINALS: tuple[int, ...] = (1, 5, 10, 25, 50, 100)



@dataclass(frozen=True)
class PlaceStoryEvent:
    """One Place Story entry -- a presentation derived from one or more
    underlying authoritative facts, never a new fact of its own (Phase 2 of
    the governing brief: "preserve the underlying evidence/provenance").

    `id` is a stable, deterministic identifier derived from the underlying
    fact(s) it presents (a taxon label, a change-event id, a checkpoint
    date) -- never a random/incrementing value -- so pagination across two
    reads of an unchanged Place never duplicates or drops an entry (Phase 29).

    `event_date` is the single best-effort "when this happened" anchor used
    for sorting/display; `event_end_date` is set only for a genuine interval
    (a phenology observation's own end date, a period summary's period end).
    """

    id: str
    kind: PlaceStoryEventKind
    group: PlaceStoryEventGroup
    event_date: date
    event_end_date: date | None
    title: str
    summary: str
    information_class: InformationClass
    importance: PlaceStoryImportance
    taxon_label: str | None = None
    taxon_display_name: str | None = None
    feature_id: str | None = None
    feature_name: str | None = None
    visit_id: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    source_id: str | None = None
    # Small, bounded, string-keyed drill-down handles only -- e.g.
    # {"change_event_id": ..., "phenology_observation_id": ...} -- never a
    # duplicated copy of the underlying record's own fields (Phase 2: "do
    # not duplicate the underlying authoritative fact merely to display it
    # in a timeline").
    detail_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_end_date is not None and self.event_end_date < self.event_date:
            raise ValueError("event_end_date must not precede event_date")


def _local_midnight(day: date, local_timezone: tzinfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=local_timezone)


# ---------------------------------------------------------------------------
# Wildlife: first-seen + diversity milestones (Phase 5, Phase 21).
#
# Both come from the exact same all-time `first_confirmed_at` per taxon
# `historical_baseline` already computes -- no new query, no new statistic.
# ---------------------------------------------------------------------------


def compute_first_seen_events(
    statuses: Sequence[SpeciesHistoricalStatus],
    *,
    period_start_at: datetime,
    period_end_at: datetime,
    local_timezone: tzinfo,
) -> list[PlaceStoryEvent]:
    """One `first_seen` event per taxon whose all-time-first confirmed
    record falls in `[period_start_at, period_end_at)` -- i.e. exactly the
    taxa `compute_species_historical_statuses` already marked `"new"`/
    `"first_record"` for this period (see that function's own decision
    table). `"new"` (established baseline) is `major`; `"first_record"`
    (baseline not yet established enough to call it ecologically novel) is
    `notable` -- the same honest distinction `daily_digest.py` already
    draws in its own copy, reused here as an importance signal instead of
    a wording signal only.
    """

    events: list[PlaceStoryEvent] = []
    for status in statuses:
        if status.status not in ("new", "first_record"):
            continue
        local_date = status.first_confirmed_at.astimezone(local_timezone).date()
        display = status.taxon.display_name
        events.append(
            PlaceStoryEvent(
                id=f"first-seen:{status.taxon.label}",
                kind="first_seen",
                group="wildlife",
                event_date=local_date,
                event_end_date=None,
                title=f"First {display} observation",
                summary=f"First reviewed observation of {display} recorded at this Place.",
                information_class="reviewed",
                importance="major" if status.status == "new" else "notable",
                taxon_label=status.taxon.label,
                taxon_display_name=display,
            )
        )
    return events


def compute_diversity_milestone_events(
    all_time_first_confirmed_at: Mapping[str, datetime],
    taxa: Mapping[str, TaxonFact],
    *,
    local_timezone: tzinfo,
    ordinals: tuple[int, ...] = DIVERSITY_MILESTONE_ORDINALS,
) -> list[PlaceStoryEvent]:
    """One event per fixed species-count ordinal this Place has ever
    reached (1st/5th/10th/25th/50th/100th species), dated at the debut of
    the taxon that reached it. Ranking taxa by their own already-computed
    all-time `first_confirmed_at` gives a true cumulative species-over-time
    ordering "for free" -- no new query, no stored counter, no time-series
    table (see the module docstring; Phase 21 explicitly rules out
    gamification/streaks -- these are small, fixed, deterministic tiers,
    never a continuously-scored achievement)."""

    ordered_labels = sorted(all_time_first_confirmed_at, key=lambda label: all_time_first_confirmed_at[label])
    events: list[PlaceStoryEvent] = []
    for ordinal in ordinals:
        if ordinal > len(ordered_labels):
            continue
        label = ordered_labels[ordinal - 1]
        taxon = taxa.get(label)
        if taxon is None:
            continue
        first_at = all_time_first_confirmed_at[label]
        local_date = first_at.astimezone(local_timezone).date()
        events.append(
            PlaceStoryEvent(
                id=f"diversity-milestone:{ordinal}",
                kind="diversity_milestone",
                group="wildlife",
                event_date=local_date,
                event_end_date=None,
                title=f"{_ordinal_word(ordinal)} species recorded",
                summary=(
                    f"{taxon.display_name} became the {_ordinal_word(ordinal).lower()} distinct species "
                    "confirmed at this Place."
                ),
                information_class="reviewed",
                importance="major",
                taxon_label=label,
                taxon_display_name=taxon.display_name,
            )
        )
    return events


_ORDINAL_WORDS: dict[int, str] = {1: "1st", 5: "5th", 10: "10th", 25: "25th", 50: "50th", 100: "100th"}


def _ordinal_word(ordinal: int) -> str:
    return _ORDINAL_WORDS.get(ordinal, f"{ordinal}th")


# ---------------------------------------------------------------------------
# Wildlife: regularity transitions (Phase 5, Phase 6) -- the checkpoint scan.
# ---------------------------------------------------------------------------

_TRANSITION_KIND_BY_STATE: dict[RegularityStateValue, PlaceStoryEventKind] = {
    "returned_after_absence": "return",
    "becoming_regular": "regularity_change",
    "regular": "regularity_change",
    "quieter_lately": "regularity_change",
}

# Only transitions *into* one of these states are story-worthy -- becoming
# "occasional" or falling back to plain "regular" from "becoming_regular"
# without a `place_change_summary` signal are ordinary noise, not a
# meaningful change (Phase 6: "do not emit a new timeline item every time
# the rolling number changes slightly").
_STORY_WORTHY_STATES: frozenset[RegularityStateValue] = frozenset(_TRANSITION_KIND_BY_STATE)

_REGULARITY_TITLES: dict[RegularityStateValue, str] = {
    "returned_after_absence": "returned after a quiet stretch",
    "becoming_regular": "becoming a regular presence",
    "regular": "became a regular presence",
    "quieter_lately": "quieter lately",
}


def _usable_date_checkpoints(
    usable_dates: AbstractSet[date],
    checkpoint_range_start_at: datetime,
    period_end_at: datetime,
    *,
    local_timezone: tzinfo,
) -> list[datetime]:
    """One checkpoint instant per distinct usable date in
    `[checkpoint_range_start_at, period_end_at]`, each the local midnight
    beginning the *next* day after that usable date -- i.e. each
    checkpoint's own `window_end_at` mirrors what `compute_place_change_
    windows` expects (the instant just after the day being evaluated). See
    the module docstring's "Why checkpoints" section for why every usable
    date, and only usable dates, is correct and sufficient. Always includes
    a final checkpoint at `period_end_at` itself (local-midnight-normalized
    to the day after its own local date) so the loop's very last
    classification is never silently skipped merely because that trailing
    day was not itself independently usable.

    Callers must pass the *trailing-lookback* start here (e.g. `period_end_
    at - baseline_window_days`), never the requested Story period's own
    `period_start_at` -- `_record_transition`'s own `period_start_at`/
    `period_end_at` bounds check is what keeps a pre-period transition from
    becoming a *visible* entry; this function's job is only to make sure
    `previous_states`/`ever_reached_regular` are correctly *seeded* by
    walking through every checkpoint since well before the period, so the
    first checkpoint actually inside the requested period is compared
    against the taxon's real prior state, not against "never seen before in
    this scan" (a regression a synthetic-history test caught: requesting
    only a *later* period, e.g. "this month," falsely re-announced a
    regularity transition that had genuinely happened months earlier)."""

    start_date = checkpoint_range_start_at.astimezone(local_timezone).date()
    end_date = period_end_at.astimezone(local_timezone).date()
    checkpoint_dates = sorted(day for day in usable_dates if start_date <= day <= end_date)
    checkpoints = [_local_midnight(day + timedelta(days=1), local_timezone) for day in checkpoint_dates]
    final_checkpoint = _local_midnight(end_date + timedelta(days=1), local_timezone)
    if not checkpoints or checkpoints[-1] < final_checkpoint:
        checkpoints.append(final_checkpoint)
    # Every checkpoint is local-midnight-based (in `local_timezone`),
    # including the fallback above -- never a raw `period_end_at` with
    # whatever tzinfo the caller happened to pass, so every later `.date()`
    # call in this module (never re-converted) still yields the correct
    # local calendar day. See product-doctrine.md's day-boundary-must-
    # honor-Place-timezone discipline.
    return checkpoints


def _latest_presence_date_in_recent_window(
    dates: AbstractSet[date], *, recent_usable_dates: AbstractSet[date], fallback: date
) -> date:
    candidates = dates & recent_usable_dates
    return max(candidates) if candidates else fallback


def _visits_sorted_by_start(window_visits: Iterable[VisitFact]) -> tuple[list[datetime], list[VisitFact]]:
    """Sort once so every checkpoint can slice its own `[window_start_at,
    checkpoint_at)` range in `O(log n)` via `bisect` instead of re-scanning
    the full Visit list per checkpoint -- the difference between `O(checkpoints
    * visits)` and `O(checkpoints * log(visits) + visits)` total work across a
    Place Story request spanning a long history (Phase 24: "avoid N+1
    queries" -- this is the equivalent discipline for a pure in-memory scan)."""

    ordered = sorted(window_visits, key=lambda visit: visit.activity_started_at)
    return [visit.activity_started_at for visit in ordered], ordered


def _visit_slice(
    starts: list[datetime], visits: list[VisitFact], *, window_start_at: datetime, window_end_at: datetime
) -> list[VisitFact]:
    lo = bisect.bisect_left(starts, window_start_at)
    hi = bisect.bisect_left(starts, window_end_at)
    return visits[lo:hi]


def detect_regularity_transition_events(
    window_visits: Sequence[VisitFact],
    *,
    taxa: Mapping[str, TaxonFact],
    all_time_first_confirmed_at: Mapping[str, datetime],
    all_time_last_confirmed_at: Mapping[str, datetime],
    usable_dates: AbstractSet[date],
    local_timezone: tzinfo,
    period_start_at: datetime,
    period_end_at: datetime,
    baseline_window_days: int,
) -> list[PlaceStoryEvent]:
    """Usable-date-checkpoint scan for regularity transitions landing
    inside `[period_start_at, period_end_at)` -- see the module docstring's
    "Why checkpoints" section. `window_visits`/`usable_dates` must already
    cover a trailing `baseline_window_days`-day lookback before
    `period_start_at` (mirroring `historical_baseline.HISTORICAL_BASELINE_
    WINDOW_DAYS`'s own bound) so the *first* checkpoint inside the
    requested period can still see its own full reference window; callers
    should fetch that wider superset once, not per checkpoint.

    Checkpoints are generated across `[period_start_at - baseline_window_
    days, period_end_at]` -- not just `[period_start_at, period_end_at]` --
    so `previous_states`/`ever_reached_regular` are correctly *seeded* by
    walking through the taxon's real prior history before the first
    checkpoint actually inside the requested period is reached (a
    synthetic-history regression test caught a first implementation that
    checkpointed only within the requested period itself: requesting a
    *later* period alone, e.g. "this month," falsely re-announced a
    regularity transition that had genuinely happened months earlier,
    because the scan had nothing to compare the first in-period checkpoint
    against). `_record_transition`'s own bounds check is what keeps a
    pre-period seeding checkpoint from becoming a *visible* entry -- this
    function only needs to walk far back enough to seed correctly.

    Presence-date lookup used only to refine the display date of a
    `"return"` event is built once from `window_visits`, not re-scanned per
    checkpoint.
    """

    presence_by_taxon: dict[str, set[date]] = {}
    for visit in window_visits:
        if visit.confirmed_taxon is None:
            continue
        presence_by_taxon.setdefault(visit.confirmed_taxon.label, set()).add(
            visit.activity_started_at.astimezone(local_timezone).date()
        )

    checkpoint_range_start_at = period_start_at - timedelta(days=baseline_window_days)
    checkpoints = _usable_date_checkpoints(
        usable_dates, checkpoint_range_start_at, period_end_at, local_timezone=local_timezone
    )
    visit_starts, visits_sorted = _visits_sorted_by_start(window_visits)

    previous_states: dict[str, RegularityStateValue] = {}
    ever_reached_regular: set[str] = set()
    events: list[PlaceStoryEvent] = []
    for checkpoint_at in checkpoints:
        # Each checkpoint's own trailing lookback is simply its natural
        # `baseline_window_days`-day window -- no further floor is needed:
        # `checkpoint_usable_dates`/`checkpoint_visits` below are filtered
        # from whatever the caller actually fetched, so a window reaching
        # earlier than the caller's own fetched data naturally (and
        # honestly) just finds nothing there, exactly like a genuinely
        # thin history would.
        window_start_at = checkpoint_at - timedelta(days=baseline_window_days)
        # `usable_dates` are Place-*local* calendar dates (see
        # `historical_baseline.usable_dates_from_daily_monitored_seconds`);
        # every boundary compared against them must be converted to that
        # same local calendar day first -- never a raw `.date()` on an
        # instant that may carry a different (e.g. UTC) tzinfo. See
        # product-doctrine.md's day-boundary-must-honor-Place-timezone
        # discipline.
        window_start_local_date = window_start_at.astimezone(local_timezone).date()
        checkpoint_local_date = checkpoint_at.astimezone(local_timezone).date()
        checkpoint_usable_dates = {
            day for day in usable_dates if window_start_local_date <= day < checkpoint_local_date
        }
        checkpoint_visits = _visit_slice(
            visit_starts, visits_sorted, window_start_at=window_start_at, window_end_at=checkpoint_at
        )

        statuses = compute_species_historical_statuses(
            checkpoint_visits,
            taxa=taxa,
            all_time_first_confirmed_at=all_time_first_confirmed_at,
            all_time_last_confirmed_at=all_time_last_confirmed_at,
            usable_dates=checkpoint_usable_dates,
            local_timezone=local_timezone,
            # Deliberately degenerate/empty (`period_start_at ==
            # period_end_at`): this checkpoint scan only ever wants the
            # "regular"/"seen_before" distinction, never "new"/"first_
            # record" -- `compute_first_seen_events` (a real, short-period
            # call, not this trailing 366-day lookback) already owns that
            # determination correctly. Passing the wide lookback window
            # here instead would make `is_first_in_period` true for every
            # checkpoint throughout a taxon's entire first year (its
            # all-time-first confirmation is trivially "inside" any
            # 366-day window that starts before it), which would keep
            # `compute_regularity_narrative` on its `historical_status_
            # only` branch forever and silently suppress every genuine
            # regularity transition during that whole first year -- caught
            # by this module's own synthetic-history test.
            period_start_at=checkpoint_at,
            period_end_at=checkpoint_at,
            baseline_maturity=compute_baseline_maturity(len(checkpoint_usable_dates)),
        )
        change_summary = compute_place_change_summary(
            checkpoint_visits,
            taxa=taxa,
            usable_dates=checkpoint_usable_dates,
            local_timezone=local_timezone,
            window_end_at=checkpoint_at,
        )
        change_by_label = {entry.taxon.label: entry for entry in change_summary.taxa}

        for status in statuses:
            change = change_by_label.get(status.taxon.label)
            narrative = compute_regularity_narrative(
                status.status,
                change.status if change is not None else None,
                reference_presence_days=change.reference_presence_days if change is not None else None,
            )
            effective_state = _effective_regularity_state(
                narrative.state,
                change=change,
                first_confirmed_at=all_time_first_confirmed_at.get(status.taxon.label),
                reference_window_start_at=change_summary.windows.reference_window_start_at,
            )
            _record_transition(
                events,
                previous_states=previous_states,
                ever_reached_regular=ever_reached_regular,
                key=status.taxon.label,
                new_state=effective_state,
                checkpoint_at=checkpoint_at,
                checkpoint_date=checkpoint_local_date - timedelta(days=1),
                taxon=status.taxon,
                presence_dates=presence_by_taxon.get(status.taxon.label, set()),
                # `recent_usable_dates` is one shared set per checkpoint
                # (all taxa are compared over the same recent window), not
                # a per-taxon field on `TaxonChangeStatus` -- it lives on
                # `PlaceChangeSummary.windows`, populated only when the
                # windows themselves were valid.
                recent_usable_dates=change_summary.windows.recent_usable_dates,
                period_start_at=period_start_at,
                period_end_at=period_end_at,
            )

    return events


def _effective_regularity_state(
    narrative_state: RegularityStateValue,
    *,
    change: TaxonChangeStatus | None,
    first_confirmed_at: datetime | None,
    reference_window_start_at: datetime | None,
) -> RegularityStateValue:
    """`compute_regularity_narrative`'s own state, with one narrow
    supplemental override for the discovered `"returned_after_absence"` gap
    -- see the module docstring's "A discovered gap" section for why this
    exists and why it does not touch `place_change_summary.py`.

    Fires only when: (a) `compute_regularity_narrative` did not already
    reach a story-worthy state; (b) the reference window had truly zero
    presence (`TaxonChangeStatus.reference_presence_days == 0`, a field
    `compute_place_change_summary` already computes correctly -- only its
    derived `.status` collapses this case); (c) the recent window's
    presence clears the *existing* `MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE`
    floor (2 days) `place_change_summary.py` already uses for "is this
    difference real," not a new number; and (d) the taxon's own all-time
    first confirmation predates the reference window entirely -- so a
    taxon in only its first few days of ever existing at this Place (whose
    reference window is trivially empty because it did not exist yet, not
    because it went quiet) is never mistaken for a real return. (d) is
    what keeps this from double-counting `compute_first_seen_events`' own,
    separate "new"/"first_record" events.
    """

    # "regular"/"occasional" are `compute_regularity_narrative`'s own two
    # fallback states (from `historical_status == "regular"`/`"seen_before"`
    # respectively) when no usable change signal was available -- exactly
    # the case the discovered gap collapses `"higher_recent_presence"`
    # into. Every other narrative state either already reached a real
    # change-driven verdict (impossible here anyway when `reference_
    # presence_days == 0`, since that always yields one of these two
    # fallbacks -- see the module docstring) or is `"new"`/`"first_record"`,
    # which this checkpoint scan never produces by construction.
    if narrative_state not in ("regular", "occasional") or change is None:
        return narrative_state
    if change.reference_presence_days != 0 or change.recent_presence_days < MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE:
        return narrative_state
    if (
        first_confirmed_at is None
        or reference_window_start_at is None
        or first_confirmed_at >= reference_window_start_at
    ):
        return narrative_state
    return "returned_after_absence"


def _record_transition(
    events: list[PlaceStoryEvent],
    *,
    previous_states: dict[str, RegularityStateValue],
    ever_reached_regular: set[str],
    key: str,
    new_state: RegularityStateValue,
    checkpoint_at: datetime,
    checkpoint_date: date,
    taxon: TaxonFact,
    presence_dates: AbstractSet[date],
    recent_usable_dates: AbstractSet[date],
    period_start_at: datetime,
    period_end_at: datetime,
) -> None:
    previous_state = previous_states.get(key)
    previous_states[key] = new_state
    if previous_state == new_state or new_state not in _STORY_WORTHY_STATES:
        return

    if new_state == "regular":
        # "Became a regular presence" is a one-time milestone per taxon,
        # not a repeating transition. `historical_status` only ever climbs
        # (it counts distinct usable days within a trailing 366-day
        # window, so it cannot drop once >= MIN_DISTINCT_USABLE_DAYS_FOR_
        # REGULAR is reached), but the *narrative* can still fall back to
        # a plain "regular" a second time purely because `change_status`
        # reverted to "no_supported_change" once a long-enough quiet
        # stretch empties even the 14-usable-day reference window (see the
        # module docstring's worked example) -- not because the taxon
        # newly became regular again. Suppress every re-fire past the
        # first; a real resumption after such a stretch is still honestly
        # reported, just as `"returned_after_absence"`, which has no such
        # gate.
        if key in ever_reached_regular:
            return
        ever_reached_regular.add(key)

    if not (period_start_at <= checkpoint_at <= period_end_at):
        # A transition detected by a checkpoint that itself falls outside
        # the requested period (the loop's trailing lookback checkpoint,
        # see `_week_end_checkpoints`) is still needed to seed `previous_
        # states` correctly, but must never itself become a visible entry.
        return

    if new_state == "returned_after_absence":
        display_date = _latest_presence_date_in_recent_window(
            presence_dates, recent_usable_dates=recent_usable_dates, fallback=checkpoint_date
        )
    else:
        display_date = checkpoint_date

    kind = _TRANSITION_KIND_BY_STATE[new_state]
    title = f"{taxon.display_name} {_REGULARITY_TITLES[new_state]}"
    if new_state == "returned_after_absence":
        summary = (
            f"{taxon.display_name} appeared again after a period with no reviewed observations, "
            "during periods with adequate monitoring."
        )
        importance: PlaceStoryImportance = "major"
    elif new_state == "regular":
        summary = f"{taxon.display_name} has become a regular presence at this Place."
        importance = "major"
    elif new_state == "becoming_regular":
        summary = f"{taxon.display_name} has been appearing more often recently."
        importance = "notable"
    else:  # quieter_lately
        summary = f"{taxon.display_name} has been seen less often recently."
        importance = "notable"

    events.append(
        PlaceStoryEvent(
            id=f"regularity:{key}:{new_state}:{display_date.isoformat()}",
            kind=kind,
            group="wildlife",
            event_date=display_date,
            event_end_date=None,
            title=title,
            summary=summary,
            information_class="reviewed",
            importance=importance,
            taxon_label=taxon.label,
            taxon_display_name=taxon.display_name,
        )
    )


def detect_overall_activity_events(
    window_visits: Sequence[VisitFact],
    *,
    usable_dates: AbstractSet[date],
    local_timezone: tzinfo,
    period_start_at: datetime,
    period_end_at: datetime,
    baseline_window_days: int,
) -> list[PlaceStoryEvent]:
    """Place-wide (not per-taxon) `noteworthy_activity` events -- the same
    usable-date-checkpoint scan as `detect_regularity_transition_events`
    (including its seeding-range discipline, see that function's own
    docstring), but watching `PlaceChangeSummary.overall.status` instead of
    a per-taxon narrative. Kept as a separate, smaller pass (rather than
    folded into the per-taxon loop) since it needs no `taxa`/historical-
    status input at all -- `compute_place_change_summary` already returns
    `overall` unconditionally."""

    checkpoint_range_start_at = period_start_at - timedelta(days=baseline_window_days)
    checkpoints = _usable_date_checkpoints(
        usable_dates, checkpoint_range_start_at, period_end_at, local_timezone=local_timezone
    )
    visit_starts, visits_sorted = _visits_sorted_by_start(window_visits)

    previous_status: PlaceChangeStatusValue | None = None
    events: list[PlaceStoryEvent] = []
    for checkpoint_at in checkpoints:
        window_start_at = checkpoint_at - timedelta(days=baseline_window_days)
        window_start_local_date = window_start_at.astimezone(local_timezone).date()
        checkpoint_local_date = checkpoint_at.astimezone(local_timezone).date()
        checkpoint_usable_dates = {
            day for day in usable_dates if window_start_local_date <= day < checkpoint_local_date
        }
        checkpoint_visits = _visit_slice(
            visit_starts, visits_sorted, window_start_at=window_start_at, window_end_at=checkpoint_at
        )
        windows = compute_place_change_windows(
            checkpoint_usable_dates, window_end_at=checkpoint_at, local_timezone=local_timezone
        )
        if not windows.is_valid:
            previous_status = None
            continue
        summary = compute_place_change_summary(
            checkpoint_visits, taxa={}, usable_dates=checkpoint_usable_dates,
            local_timezone=local_timezone, window_end_at=checkpoint_at,
        )
        assert summary.overall is not None
        new_status = summary.overall.status
        changed = previous_status is not None and previous_status != new_status
        previous_status = new_status
        if not changed or new_status not in ("more_activity_recorded", "less_activity_recorded"):
            continue
        if not (period_start_at <= checkpoint_at <= period_end_at):
            continue

        checkpoint_date = checkpoint_local_date - timedelta(days=1)
        direction = "higher" if new_status == "more_activity_recorded" else "lower"
        events.append(
            PlaceStoryEvent(
                id=f"overall-activity:{new_status}:{checkpoint_date.isoformat()}",
                kind="noteworthy_activity",
                group="wildlife",
                event_date=checkpoint_date,
                event_end_date=None,
                title=f"Overall wildlife activity {direction} lately",
                summary=(
                    f"Confirmed wildlife activity across this Place has been {direction} recently "
                    "than its own recent history, under comparable monitoring."
                ),
                information_class="reviewed",
                importance="notable",
            )
        )
    return events


# ---------------------------------------------------------------------------
# Place: Feature change events + before/after comparison insights (Phase 7, 8).
# ---------------------------------------------------------------------------

_FEATURE_CHANGE_TITLES: dict[str, str] = {
    "added": "added",
    "removed": "removed",
    "moved": "moved",
    "modified": "modified",
    "replenished": "replenished",
    "food_changed": "food changed",
    "vegetation_changed": "vegetation changed",
    "other": "changed",
}

_MAJOR_FEATURE_CHANGE_TYPES: frozenset[str] = frozenset({"added", "removed"})


def feature_change_event_to_story_event(
    *,
    change_event_id: str,
    feature_id: str | None,
    feature_name: str,
    event_type: str,
    effective_date: date,
    note: str | None,
    prior_value: str | None,
    new_value: str | None,
    zone_id: str | None,
    source_id: str | None,
) -> PlaceStoryEvent:
    """Project one already-Reviewed `PlaceFeatureChangeEvent` directly into
    a Story event -- no new logic, only a stable id and plain-language
    copy (Phase 7: "these are human-reviewed Place facts")."""

    verb = _FEATURE_CHANGE_TITLES.get(event_type, "changed")
    title = f"{feature_name} {verb}" if feature_id is not None else f"Place {verb}"
    parts = [title + "."]
    if prior_value and new_value:
        parts.append(f"Changed from {prior_value} to {new_value}.")
    elif new_value:
        parts.append(f"{new_value}.")
    if note:
        parts.append(note)
    return PlaceStoryEvent(
        id=f"feature-change:{change_event_id}",
        kind="feature_change",
        group="place",
        event_date=effective_date,
        event_end_date=None,
        title=title[0].upper() + title[1:],
        summary=" ".join(parts),
        information_class="reviewed",
        importance="major" if event_type in _MAJOR_FEATURE_CHANGE_TYPES else "notable",
        feature_id=feature_id,
        feature_name=feature_name,
        zone_id=zone_id,
        source_id=source_id,
        detail_refs={"change_event_id": change_event_id},
    )


def comparison_insight_event(
    *,
    change_event_id: str,
    feature_id: str,
    feature_name: str,
    event_type: str,
    maturity: Literal["early_signal", "comparable"],
    window_days: int,
    post_end: date,
    association_status: Literal["more_common_under_condition", "less_common_under_condition"],
    weather_caveat: str | None = None,
) -> PlaceStoryEvent:
    """A separate, later-dated `"inferred"` event explaining a mature
    before/after comparison for one Feature change -- kept distinct from
    the `feature_change` event it explains (Phase 8: "do not merge them
    into a causal statement"). Dated at `post_end` -- the day the
    comparison window this maturity level required actually closed, i.e.
    the day this insight genuinely first became evaluable, not the
    original change's own `effective_date`.

    Callers must gate on `maturity in ("early_signal", "comparable")`
    before calling this (a `"too_soon"`/`"insufficient_coverage"`
    `FeatureChangeComparison` produces no Story event at all -- an
    unresolved comparison is not yet a Place fact worth narrating)."""

    verb = _FEATURE_CHANGE_TITLES.get(event_type, "changed")
    direction = "higher" if association_status == "more_common_under_condition" else "lower"
    confidence = "" if maturity == "comparable" else " (an early signal, not yet a firm comparison)"
    summary = (
        f"Confirmed wildlife activity was {direction} during the monitored period after "
        f"{feature_name} was {verb}, compared with the monitored period before{confidence}."
    )
    if weather_caveat:
        summary = f"{summary} {weather_caveat}"
    return PlaceStoryEvent(
        id=f"comparison-insight:{change_event_id}",
        kind="comparison_insight",
        group="context",
        event_date=post_end,
        event_end_date=None,
        title=f"Activity {direction} after {feature_name.lower()} {verb}",
        summary=summary,
        information_class="inferred",
        importance="notable",
        feature_id=feature_id,
        feature_name=feature_name,
        detail_refs={"change_event_id": change_event_id, "window_days": str(window_days)},
    )


# ---------------------------------------------------------------------------
# Place: phenology observations (Phase 10).
# ---------------------------------------------------------------------------


def phenology_observation_to_story_event(
    *,
    observation_id: str,
    subject_label: str,
    phenomenon: str,
    observed_start_date: date,
    observed_end_date: date | None,
    note: str | None,
) -> PlaceStoryEvent:
    """Project one already-Reviewed `PlacePhenologyObservation` directly
    into a Story event -- no new logic (Phase 10: "use reviewed
    phenology dates/intervals")."""

    title = f"{subject_label}: {phenomenon}"
    summary = f"Recorded {phenomenon.lower()} for {subject_label.lower()}."
    if observed_end_date is not None and observed_end_date != observed_start_date:
        summary += f" Observed from {observed_start_date.isoformat()} to {observed_end_date.isoformat()}."
    if note:
        summary += f" {note}"
    return PlaceStoryEvent(
        id=f"phenology:{observation_id}",
        kind="phenology",
        group="place",
        event_date=observed_start_date,
        event_end_date=observed_end_date,
        title=title,
        summary=summary,
        information_class="reviewed",
        importance="notable",
        detail_refs={"phenology_observation_id": observation_id},
    )


# ---------------------------------------------------------------------------
# Composition: merge, dedupe, filter, sort, paginate (Phase 4, 13, 14, 19, 25).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlaceStoryPage:
    events: list[PlaceStoryEvent]
    has_more: bool
    next_offset: int | None
    total_matched: int


def build_place_story(
    event_sources: Iterable[Iterable[PlaceStoryEvent]],
    *,
    event_date_start: date | None = None,
    event_date_end: date | None = None,
    kinds: AbstractSet[PlaceStoryEventKind] | None = None,
    taxon_label: str | None = None,
    feature_id: str | None = None,
    offset: int = 0,
    page_size: int = 30,
) -> PlaceStoryPage:
    """Merge every already-computed event source into one deterministically
    ordered, filtered, paginated page.

    `event_date_start`/`event_date_end` (both inclusive) filter by interval
    *overlap*, not containment: an event whose own `[event_date, event_end_
    date or event_date]` span overlaps the requested range at all is kept --
    a multi-week phenology observation that began before the requested
    window but is still ongoing within it must not silently disappear just
    because its own start date falls outside the filter. Some event sources
    (e.g. `compute_diversity_milestone_events`) intentionally look across a
    taxon's entire all-time history to decide *whether* a milestone exists
    at all, but the resulting event's own `event_date` still anchors it to
    one real day -- this filter is what actually scopes the final page to
    the caller's requested period, independent of how far back any one
    source function had to look to compute its answer.

    Ordering: newest `event_date` first, then a fixed importance tier
    (`major` before `notable`), then `id` as a final stable tie-break -- so
    two reads of an unchanged Place always return byte-identical ordering
    (Phase 29: "no duplicates between pages").

    Deduplication is structural, not a post-hoc pass: every source function
    above already emits at most one event per underlying fact (one per
    taxon-transition, one per change-event row, one per phenology row), so
    the only work left here is merging already-distinct ids -- asserted
    below as a defensive invariant, never silently dropped.
    """

    merged: dict[str, PlaceStoryEvent] = {}
    for source in event_sources:
        for event in source:
            if event.id in merged and merged[event.id] != event:
                raise AssertionError(f"duplicate Place Story event id with divergent content: {event.id!r}")
            merged[event.id] = event

    def _in_date_range(event: PlaceStoryEvent) -> bool:
        event_span_end = event.event_end_date or event.event_date
        if event_date_end is not None and event.event_date > event_date_end:
            return False
        if event_date_start is not None and event_span_end < event_date_start:
            return False
        return True

    filtered = [
        event
        for event in merged.values()
        if (kinds is None or event.kind in kinds)
        and (taxon_label is None or event.taxon_label == taxon_label)
        and (feature_id is None or event.feature_id == feature_id)
        and _in_date_range(event)
    ]
    _IMPORTANCE_RANK = {"major": 0, "notable": 1}
    filtered.sort(key=lambda event: (event.event_date, _IMPORTANCE_RANK[event.importance], event.id), reverse=False)
    filtered.sort(key=lambda event: event.event_date, reverse=True)
    # Two-pass stable sort: first establish the tie-break order ascending,
    # then reverse-sort by date only, which Python's stable Timsort
    # preserves the prior tie-break order within -- so equal-date events
    # end up date-desc, importance-major-first, id-ascending, without a
    # single composite key needing a mixed asc/desc tuple.

    total_matched = len(filtered)
    bounded_offset = max(0, offset)
    page = filtered[bounded_offset : bounded_offset + page_size]
    has_more = bounded_offset + page_size < total_matched
    next_offset = bounded_offset + page_size if has_more else None
    return PlaceStoryPage(events=page, has_more=has_more, next_offset=next_offset, total_matched=total_matched)


__all__ = [
    "DIVERSITY_MILESTONE_ORDINALS",
    "InformationClass",
    "PlaceStoryEvent",
    "PlaceStoryEventGroup",
    "PlaceStoryEventKind",
    "PlaceStoryImportance",
    "PlaceStoryPage",
    "build_place_story",
    "comparison_insight_event",
    "compute_diversity_milestone_events",
    "compute_first_seen_events",
    "detect_overall_activity_events",
    "detect_regularity_transition_events",
    "feature_change_event_to_story_event",
    "phenology_observation_to_story_event",
]
