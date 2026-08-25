# Place / Yard Intelligence v2 -- Changes, Trends & Actionable Understanding

Locked implementation contract, written before broad edits, per the
milestone's own "separate investigation and implementation" rule. Starting
state verified: branch `main`, HEAD `731ee30`, schema v53, worktree exactly
the seven preserved untracked files, no other session writing this tree.

This composes the existing Gate C / Biodiversity & Place Intelligence
foundation (`historical_baseline`, `place_change_summary`,
`place_activity_report`, `representative_evidence`, `daily_digest`,
`place_biodiversity_summary`, `zone_insights`) into deeper intelligence. It
does not replace or duplicate any of that foundation.

## 1. Phase 1 -- current intelligence inventory

| User question | Existing behavior | Missing capability | Existing evidence | Proposed bounded implementation |
|---|---|---|---|---|
| What's new or regular? | `historical_baseline.compute_species_historical_statuses`: `new`/`first_record`/`regular`/`seen_before`, all-time + 366-day trailing window, `>=3` distinct usable days for `regular` | No synthesis of historical status + recent change into one narrative; no "becoming regular," "quieter lately," "returned after absence" | `SpeciesHistoricalStatus`, `TaxonChangeStatus` (both already computed, zero extra queries) | New `regularity_narrative.py`: pure synthesis of the two existing statuses -- Phase 4 |
| Has activity changed lately? | `place_change_summary`: 7-usable-day recent vs 14-usable-day reference, presence-day recurrence, `higher/lower_recent_presence` | Feeds Today/Bird Log already; no "worth noticing" synthesis, no weekly narrative | `PlaceChangeSummary` | Feed into `daily_digest` new tiers + weekly digest -- Phase 3/12/13 |
| Is there a seasonal pattern? | Nothing. Explicitly named non-goal in `historical_baseline` and `biodiversity-place-intelligence-v1-contract.md` | Whole capability missing | `window_visits`/`usable_dates` already span a 366-day trailing window (a full year once mature) | New `seasonal_pattern.py`: month-of-year presence-rate bucketing over the same window -- Phase 5 |
| When does a species typically appear (time of day / daylight)? | `compute_taxon_place_patterns` gives raw `hour_activity`/`most_active_hour` over the 366-day window (`>=5` reviewed Visits gate) | No day/night dimension, no plain-language time band, no "was this Visit's timing typical" | `TaxonPlacePattern`, `solar_context` (day/night per timestamp) | New `temporal_pattern.py`: day/night tally + time-of-day band + single-Visit typicality check -- Phase 6 |
| Which camera/area is most active? | `zone_insights` gives per-**Zone** `confirmed_bird_visits_per_monitored_hour` (>=2 healthy-hour gate); nested under `stream_id`/`source_id` but never rolled up to one per-Source ranked comparison. `WildlifeInsightsPanel`'s `stream_breakdown` is a **raw**, non-coverage-normalized count list on a separate, older analytics surface | No coverage-normalized cross-Source rollup on the accepted Place-Report/Biodiversity surface | `MonitoringExposureIntervalModel` (keyed by `stream_id`+`source_id`), `_associated_visit_ids_to_exclude_from_counting` (cross-camera dedup) | New `source_activity.py`: per-Source coverage-normalized rate, reusing existing exposure primitives -- Phase 7 |
| Is this camera producing useful evidence? | Live counterfactual ledger exists but is **in-memory, per-process, ~60-minute retention, released on restart** -- confirmed not durable/queryable historically. `ObservationAuthoritySettingsModel` has durable, per-Stream, **lifetime-cumulative** `candidates_attempted_count`/`candidates_created_count`/`suppressed_count` | No cross-source comparison of yield/suppression today | `ObservationAuthoritySettingsModel` counters | `source_activity.py` quality signal: lifetime yield-ratio comparison across Sources, honestly labeled non-time-windowed -- Phase 8 |
| Does habitat/phenology coincide with activity? | `place_context`/`get_place_habitat_context` give a **single-observation, "right now" snapshot** association (day/night + current phenology) for one taxon's most recent record only | No association across *many* Visits, no minimum-sample gating, no "more/less often during X" language | `PlacePhenologyObservationModel` (start/end date interval, free-text phenomenon), `window_visits` | New `conditional_association.py` (generic) + `habitat_association.py`: presence-rate-inside-interval vs outside, gated -- Phase 11 |
| Does weather coincide with activity? | Nothing beyond day/night (`solar_local` is the *only* environmental provider; confirmed by exhaustive grep -- no temperature/precipitation code exists anywhere) | Not buildable without a new provider (out of scope) | -- | **Not implemented.** Recorded as a missing data-model dependency (below), not built by adjacency |
| What's worth noticing right now? | `daily_digest`'s 5-tier `HighlightReason` (`first_confirmed_record`/`meaningful_change`/`strong_representative_evidence`/`regular_activity`/`confirmed_activity`) | No regularity-narrative, unusual-timing, or seasonal tiers | `DailyDigest`, `_TIER_ORDER` | Extend `daily_digest.py`'s tier vocabulary -- Phase 12 |
| What happened this week? | Only a daily digest (period-generic function, misleadingly named) | No weekly framing | `compute_daily_digest` already takes explicit `period_start_at`/`period_end_at` -- nothing calendar-day-specific in its logic | Call the *same* function with the 7-usable-day recent-window bounds -- Phase 13, no new ranking logic needed |
| Is there a reviewed habitat *change* (before/after)? | `PlacePhenologyObservationModel` is an interval fact (start/end date), not a discrete transition/change event; no before/after model exists anywhere | Whole data model missing | -- | **Not built.** Recorded as a missing product/data-model opportunity (Phase 9/11 instruction) |
| Does a Feeder/habitat-feature entity exist? | Only `PlaceHabitatFactModel` (free-text `setting`/`vegetation`/`feature` category, no ROI/geometry tie) | No structured Feeder/water-feature/nest-box entity | -- | **Not built**, per Phase 9's own instruction. Recorded below |

## 2. Primitives locked (Phase 2)

- **Observation window**: today / 7-usable-day recent / 14-usable-day
  reference / 366-day trailing baseline -- all four already accepted
  (`historical_baseline`, `place_change_summary`); no fifth window
  invented.
- **Monitoring coverage/effort**: `MonitoringExposureIntervalModel` via
  `usable_dates`/`CoverageSummary` (Place-wide, already accepted) and a
  **new** per-Source rollup (`source_activity.py`) at the same 2-healthy-hour
  minimum-support floor `zone_insights` already established.
- **Encounter activity**: Visit counts, never framed as individual-animal
  counts (unchanged doctrine).
- **Place baseline**: `HistoricalPlaceBaseline` (unchanged, reused).
- **Change**: `PlaceChangeSummary` (unchanged, reused) plus the new
  seasonal/temporal/habitat conditional-association primitive for
  non-recency-based comparisons.
- **Maturity**: every new primitive defines its own explicit
  `insufficient_*`/`developing`/`established`-shaped states; none silently
  reuses another module's maturity label for a different question.
- **Strength/evidence support**: minimum-sample floors on every new ratio
  claim (documented per module below); no z-scores/confidence intervals
  exposed in any API field name or normal UI copy.

Six new pure modules (`src/mockingbird/analytics/`), zero new database
tables/columns -- every fact is derivable from already-durable
`VisitModel`/`EventModel`/`TaxonomyLabelModel`/`MonitoringExposureInterval
Model`/`ObservationAuthoritySettingsModel`/`PlacePhenologyObservationModel`
rows. **Schema stays v53.**

1. `regularity_narrative.py` -- Phase 4
2. `seasonal_pattern.py` -- Phase 5 (also exports `presence_dates_by_taxon`,
   a small shared helper `habitat_association.py` reuses)
3. `conditional_association.py` -- generic presence-rate-inside-a-date-set
   vs outside-it primitive, used only by `habitat_association.py` today
4. `temporal_pattern.py` -- Phase 6 + the day/night slice of Phase 10
5. `habitat_association.py` -- Phase 11
6. `source_activity.py` -- Phase 7 + Phase 8

Plus an additive extension of `daily_digest.py` (Phase 12 new tiers, Phase
13 weekly digest via the *same* function, no new ranking module) and two
new optional fields on `place_activity_report.VisitFact`
(`source_id`/`source_name`, default `None` -- backward compatible with
every existing call site).

## 3. Module design

### 3.1 `regularity_narrative.py`

Pure synthesis, **zero new data gathering** -- consumes the two already-
computed statuses.

```
RegularityStateValue = Literal[
    "first_record", "new", "occasional", "becoming_regular",
    "regular", "quieter_lately", "returned_after_absence",
]

def compute_regularity_narrative(
    historical_status: SpeciesHistoricalStatusValue,
    change_status: TaxonChangeStatusValue | None,
    *, reference_presence_days: int | None,
) -> RegularityNarrative  # frozen dataclass: state, basis
```

Decision table (most specific first): `first_record`/`new` pass through
unchanged (baseline too immature, or genuinely all-time-new, for a change
overlay to add anything honest). Otherwise (`seen_before`/`regular`): no
change signal (`None`/`insufficient_*`/`no_supported_change`) falls back to
plain `occasional`/`regular`; `higher_recent_presence` with
`reference_presence_days == 0` is `returned_after_absence` (a real gap then
reappearance, stronger than a generic increase); `higher_recent_presence`
otherwise is `becoming_regular` (from `seen_before`) or stays `regular`;
`lower_recent_presence` on `regular` is `quieter_lately`, on `seen_before`
stays `occasional`. Never implies individual-animal return -- wording is
taxon-level presence only.

### 3.2 `seasonal_pattern.py`

Reuses the *same* `window_visits`/`usable_dates`/`taxa` the shared
historical-intelligence bundle already fetches -- zero additional queries.

```
SeasonalPatternStatus = Literal[
    "insufficient_history", "no_pattern_detected",
    "developing_pattern", "established_pattern",
]
SEASONAL_MIN_DISTINCT_USABLE_MONTHS = 9   # Place-wide gate: of 12 calendar
                                           # months, how many need >=1 usable day
SEASONAL_MIN_USABLE_DAYS_IN_MONTH = 2     # a month needs this many usable
                                           # days before it counts toward a rate
SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN = 3  # taxon's own total, else insufficient
SEASONAL_MONTH_MIN_RATE_MULTIPLE = 2.0    # a month must be >=2x the taxon's
                                           # own average rate across covered months
SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH = 2  # guards a single lucky day

def presence_dates_by_taxon(window_visits, *, local_timezone) -> dict[str, set[date]]
def compute_seasonal_patterns(window_visits, *, taxa, usable_dates,
    local_timezone, reference_month: int) -> dict[str, SeasonalPattern]
```

Place-wide gate first (mirrors `historical_baseline`'s "regular is
structurally impossible while insufficient" cross-check): if fewer than 9
of 12 calendar months have >=2 usable days anywhere in the 366-day window,
every taxon reads `insufficient_history` -- full stop, regardless of that
taxon's own count. This is the expected, honest state for this product's
current real history (a handful of usable days total). Only a genuinely
week-long-to-year-long-monitored installation can ever clear this gate.
`SeasonalPattern` always carries all 12 `MonthPresence` entries
(`usable_day_count`, `presence_day_count`) for transparent drill-down even
when `insufficient_history`. Deliberately **single-year window** (the
366-day trailing window resets, never accumulates across years) -- true
year-over-year seasonality is out of scope, recorded below.

### 3.3 `conditional_association.py`

Generic, taxon-agnostic, domain-agnostic date-set math -- no Visit/taxon
concept at all, maximally reusable for a future environmental provider.

```
AssociationStatus = Literal[
    "insufficient_data", "no_clear_association",
    "more_common_under_condition", "less_common_under_condition",
]
def compute_conditional_association(
    presence_dates: AbstractSet[date], *, usable_dates: AbstractSet[date],
    condition_dates: AbstractSet[date],
    min_usable_days_in_condition: int = 5,
    min_usable_days_out_of_condition: int = 5,
    min_rate_difference: float = 0.25,
) -> ConditionalAssociation
```

Same threshold shape as `place_change_summary`'s own policy (a minimum
sample floor on both sides, a minimum proportional-difference gate) --
deliberately mirrored for consistency, not reinvented.

### 3.4 `habitat_association.py`

```
def compute_habitat_associations(window_visits, *, taxa, usable_dates,
    local_timezone, phenology_observations: Iterable[PhenologyIntervalFact],
    window_end_at) -> list[TaxonHabitatAssociation]
```

`condition_dates` for one phenomenon = every calendar date from
`observed_start_date` through `observed_end_date` (or through
`window_end_at`'s date when still ongoing). Computed per (taxon,
phenomenon) pair, skipped silently when either side has too few days to
ever clear `conditional_association`'s own gate (no point computing a
result that will always read `insufficient_data`). Association language
only ("observed more/less often during X") -- never causal. This is as far
as Phase 11 goes: there is no reviewed before/after *change-event* model in
this codebase (confirmed absent by exhaustive grep), so a true before/after
comparison around a habitat change is **not built** -- recorded as a
missing data-model dependency, per the milestone's own Phase 9 instruction
not to invent the entity.

### 3.5 `temporal_pattern.py`

Day/night is an intraday (per-Visit), not per-calendar-day, fact -- it does
not fit `conditional_association`'s date-set shape, so this stays a
dedicated small module.

```
DaylightBucket = Literal["day", "night"]
TimeOfDayBand = Literal["early_morning","morning","midday","afternoon","evening","night"]
DaylightAssociation = Literal["insufficient_data","mostly_daytime","mostly_nighttime","spans_day_and_night"]

def time_of_day_band(local_hour: int) -> TimeOfDayBand
def compute_taxon_temporal_patterns(visits: Iterable[VisitFact], *,
    daylight_by_visit_id: Mapping[str, DaylightBucket], local_timezone
    ) -> dict[str, TaxonTemporalPattern]
def compare_visit_timing(local_hour: int, pattern: TaxonTemporalPattern
    ) -> Literal["typical","unusual","insufficient_data"]
```

`local_hour` is computed the same way `compute_taxon_place_patterns`
already does (`activity_started_at.astimezone(local_timezone).hour`);
`MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN` (5, imported from
`place_activity_report`) gates `dominant_band`/`daylight_association`.
`daylight_by_visit_id` is supplied by the repository via one bounded
per-**distinct-date** solar lookup (never per-Visit) reusing
`_get_or_compute_daily_solar_facts_in_session` unmodified; a Visit whose
date has no resolvable solar fact (coordinates not configured) is simply
absent from the mapping and contributes to neither day nor night --
`daylight_association` reads `insufficient_data` rather than a fabricated
guess when solar isn't configured at all. This directly answers "was this
observation typical for this species at this time" (Phase 6) and the
day/night slice of Phase 10 (a taxon "more often observed during
daylight," associative language only).

### 3.6 `source_activity.py`

```
def compute_source_activity(window_visits: Iterable[VisitFact], *,
    coverage_by_source: Mapping[str, SourceCoverageFact]
    ) -> list[SourceActivityEntry]
def compute_source_quality_signals(
    counters_by_source: Mapping[str, SourceAuthorityCounters], *,
    min_candidates_attempted: int = 20, yield_ratio_threshold: float = 0.5,
    ) -> list[SourceQualitySignal]
```

`window_visits` must carry the new `source_id`/`source_name` VisitFact
fields; `_classify`'d to `CONFIRMED_WILDLIFE` only, counted **after** the
existing `_associated_visit_ids_to_exclude_from_counting` exclusion so one
physical encounter seen by two cameras never inflates either Source's rate
(Phase 21 multi-camera safety). `visits_per_monitored_hour` gated at
`>=2` healthy hours, the exact `zone_insights` precedent, never a second
number. Ranking answers "which camera currently sees the most wildlife
activity" (Phase 7) directly; "which monitored area" is deliberately
answered at the **Source** level, never a persisted "Area" (confirmed not
to exist -- `_representative_area_name` is a read-time, single-Zone-name
convention only, per Spatial doctrine).

Quality signal (Phase 8) sources `ObservationAuthoritySettingsModel`'s
durable, per-Stream, **lifetime-cumulative** `candidates_attempted_count`/
`candidates_created_count`/`suppressed_count` -- explicitly disclosed as
lifetime-since-activation, not scoped to the report's own period (the only
alternative, the live counterfactual ledger, is in-memory/~60-minute/
per-process and cannot answer a durable cross-session question at all, so
using it here would misrepresent an ephemeral diagnostic as durable Place
Intelligence). A Source's own admission-yield ratio
(`candidates_created_count / candidates_attempted_count`) is flagged
`lower_yield_than_place_average` only when it clears both a minimum-sample
floor and a proportional-difference gate against the Place's own average --
mirroring every other threshold policy in this contract, never a bare
outlier off tiny counts. No physical placement instruction is ever
generated (explicitly forbidden by the milestone).

### 3.7 `daily_digest.py` extension

`HighlightReason` grows from 5 to 8 values; `_TIER_ORDER` becomes:

```
("first_confirmed_record", "returned_after_absence", "meaningful_change",
 "unusual_timing", "seasonal_pattern_typical", "strong_representative_evidence",
 "regular_activity", "confirmed_activity")
```

`DigestTaxonFact` gains four optional fields:
`regularity_state: RegularityStateValue | None`,
`unusual_timing_today: bool = False`,
`seasonal_status: SeasonalPatternStatus | None`,
`is_in_typical_season: bool | None`. `_highlight_reason` checks the three
new conditions in tier order before falling through to the existing five.
New wording dicts follow the exact same pattern as `_HISTORICAL_NOTES`/
`_CHANGE_NOTES` (plain-language, no jargon): e.g. `returned_after_absence`
-> "Back after a quiet stretch"; `becoming_regular` -> "Becoming a regular
visitor"; `quieter_lately` -> "Quieter than usual lately"; seasonal-typical
-> "Typical for this time of year."

**Weekly digest (Phase 13):** `compute_daily_digest` is already period-
generic (nothing in its body is calendar-day-specific -- confirmed by
direct reading). A new repository method builds the identical
`DigestTaxonFact` sequence over the 7-usable-day **recent window**
(reusing `place_change_summary`'s own window boundaries) instead of
"today," and calls the *same* function. No new ranking/highlight logic. A
new `PlaceActivityReportResponse.weekly_digest` field (same
`PlaceActivityReportDigest` shape as `digest`) is computed unconditionally
alongside `digest`, independent of whatever period the caller actually
requested -- exactly like `overall_change_status`'s own recent-window
independence from the report's own period.

## 4. Backend wiring

- `place_activity_report.VisitFact` gains `source_id: str | None = None`,
  `source_name: str | None = None` (keyword-defaulted, so every existing
  positional-free call site is unaffected).
- `_historical_place_baseline_and_species_statuses`'s `window_rows` query
  gains a join to `StreamModel`/`CameraSourceModel` (mirroring the existing
  `ZoneModel` outer join added for Zone/Time Pattern Intelligence v1) to
  populate the two new `VisitFact` fields at zero additional queries.
- That method's return type changes from a bare 4-tuple to a small
  `NamedTuple` (`HistoricalPlaceIntelligence`) bundling the existing four
  facts plus three new ones (`regularity_narratives`,
  `seasonal_patterns`, `habitat_associations`) -- a deliberate safety
  improvement while every one of its 5 call sites is being touched anyway
  (avoids silent tuple-position mistakes across a shared 7-element return).
- New `_source_activity_summary` repository method (separate from the
  bundle above -- Place-wide, not per-taxon), called only from
  `place_activity_report` and `place_biodiversity_summary`.
- New `_weekly_digest` repository method reusing `compute_daily_digest`
  over the recent-window bounds.
- `PlaceActivityReportResponse` gains: `activity_by_source: list[...]`,
  `source_quality_notes: list[...]`, `weekly_digest`. `PlaceActivityReport
  TaxonEntry` gains: `regularity_narrative`, `seasonal_pattern`,
  `temporal_pattern`, `habitat_associations`. `WildlifeJournalLabelSummary`/
  `WildlifeJournalHistoryResponse` gain the same four per-taxon fields
  (identical shapes, Bird Log reuses Today's types exactly as it already
  does for `change_status`). No new API route -- every field purely
  additive to the two existing rich routes.

## 5. Frontend wiring (bounded, highest-value surfaces only)

- `TodayReportPanel.tsx`: extend the existing generic highlight rendering
  with the three new note fields (already generic pill/note rendering,
  small diff).
- New `WeeklySummaryCard.tsx` on `DashboardPage.tsx` (between
  `TodayReportPanel` and `BiodiversitySummaryCard`) rendering
  `weekly_digest` as a short deterministic templated paragraph, matching
  the milestone's own worked example style.
- `PlaceActivityReportPage.tsx`: new "Camera activity" section
  (`activity_by_source`, coverage-gated, calm ranked list) and extended
  `TaxonCard` regularity/seasonal sentence.
- `BirdLogPage.tsx` per-label history: extend the existing historical/
  change sentence block with regularity-narrative, seasonal, and habitat-
  association sentences, and extend the existing `place_context` panel.
- **Not touched**: `AnalyticsPage.tsx`/`WildlifeInsightsPanel.tsx`
  (confirmed legacy QA-flavored surface, explicitly out of scope --
  doctrine deprioritizes "huge generic analytics dashboards");
  `BiodiversitySummaryCard.tsx` (stays minimal by design).

## 6. Explicitly not built (Phase 27 boundaries, recorded not by adjacency)

- **Weather/temperature/precipitation association** -- no provider exists;
  building one is a new external-integration milestone, not this one.
- **Reviewed habitat before/after change-event comparison** -- no discrete
  change-event data model exists (only interval facts); inventing one is a
  data-model decision outside this milestone's bounded scope, per the
  brief's own Phase 9/11 instruction.
- **A structured Feeder/water-feature/nest-box entity** -- only free-text
  `PlaceHabitatFactModel.category`/`label` exist today; not invented here.
- **Year-over-year seasonality** -- the 366-day window is trailing/
  resetting, never a multi-year accumulation; a future milestone with a
  different historical-accumulation strategy is needed.
- **Camera-placement physical instructions** -- explicitly forbidden;
  `source_activity`'s quality signal states a comparison only.
- Notifications/push infrastructure, multi-site, mobile/PWA, any cloud
  LLM dependency, population/ecological modeling -- unchanged exclusions.

## 7. Validation plan

Tier 1 (focused): `tests/test_regularity_narrative.py`,
`test_seasonal_pattern.py`, `test_conditional_association.py`,
`test_habitat_association.py`, `test_temporal_pattern.py`,
`test_source_activity.py`, extended `test_daily_digest.py` -- pure,
no-DB, synthetic-fixture style matching `test_historical_baseline.py`'s
own convention.

Tier 2: `python scripts/verify_core.py` (this touches
`place_activity_report`/repository/API-schema surfaces, so Core is
mandatory regardless of diff size, per the repo's own escalation rule) plus
new repository/API integration tests (`*_repository.py` siblings) covering
the mandatory correction-safety case for each new derived fact.

Frontend: `tsc --noEmit`, `npm run build`, targeted new/extended Playwright
specs, `git diff --check`.
