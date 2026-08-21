# Historical Baseline Maturity + New/Regular Species v1

`mockingbird.analytics.historical_baseline` is the first bounded slice of
[product-doctrine.md](product-doctrine.md)'s "Place Intelligence" layer:
whether accumulated monitoring history at a Place is deep enough to trust a
new-vs-regular species statement, and, per taxon, whether today's
confirmation is a first-ever record or a recurring, well-evidenced regular.
It deliberately does not implement anomaly/change detection, "more/less
than normal" language, seasonality, or ecological rarity -- see "Explicit
non-goals" below. It extends, and is read alongside,
[place-activity-report-contract.md](place-activity-report-contract.md),
whose own "Baselines / trends" section named this exact future layer and
deliberately left it unbuilt.

## What already existed, reused here

No prior "baseline maturity" concept existed anywhere in the codebase
before this milestone (confirmed by exhaustive search). Three related, but
narrower, precedents did, and are reused rather than re-invented:

- `ProductRepository._dashboard_today_summary`'s legacy `new_today`/
  `recent_regulars` (feeding `DashboardTodaySummary`, rendered as sibling
  panels below `TodayReportPanel` on the Dashboard): "regular" already
  meant "confirmed on >= 3 distinct local days," not raw Visit count -- the
  "3" threshold this module's own `MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR`
  reuses. But that computation is a fixed 14-day trailing window with no
  coverage awareness at all (a 3-minute day counts identically to an
  8-hour day), and "new" there means only "never confirmed on any earlier
  day," with no baseline-maturity gate on the wording. This module answers
  a genuinely different question -- "is this species a well-established
  regular across this Place's whole *monitored* history," not "was it
  active in the last two weeks" -- so `_dashboard_today_summary` was left
  untouched rather than unified with it; see "Known limitations."
- `ProductRepository.wildlife_journal_history`'s `is_new_label_in_range`:
  already a genuine all-time-earliest-record check (per label, computed
  on demand), just without any baseline-maturity gate on its wording and
  scoped to whatever date range the caller happens to be viewing, not the
  Place's own historical baseline. Left unchanged; this milestone adds
  `baseline_maturity` alongside it so the frontend can word it honestly.
- `mockingbird.analytics.place_activity_report.compute_report_maturity`'s
  2-hour "enough monitoring to trust" threshold (itself reused from
  `zone_insights.quality_status`): reused verbatim as `historical_baseline.
  USABLE_DAY_MONITORED_SECONDS_THRESHOLD`, applied per calendar day instead
  of per report period.

## Reuse, not a second analytics path

`historical_baseline.py` imports `VisitFact`/`TaxonFact`/`_classify`
directly from `place_activity_report.py` (the exact same truth-precedence
resolution -- confirmed always wins outright over provisional, never
blended) and `TimeInterval`/`merge_intervals` from `zone_insights.py` (the
exact same overlap-safe interval union math). It never re-derives either.
`ProductRepository._historical_place_baseline_and_species_statuses` (Today
integration) and the inline usable-day/regularity computation in
`wildlife_journal_overview`/`wildlife_journal_history` (Bird Log
integration) both read from the one shared primitive, `ProductRepository.
_historical_usable_dates`, so a usable day can never be defined two
different ways in two different places.

## Truth contract

Only an authority-eligible `ReviewLabel` (`VisitModel.review_status ==
"reviewed"`, non-superseded, resolved to a real wildlife taxon) can
establish or extend a taxon's historical record. Concretely:

- A provisional `SpeciesSuggestion` alone (`resolution == "needs_review"`)
  is filtered out by `_classify` before this module ever sees it -- it can
  never create a first-ever record, extend distinct-day/regularity counts,
  or appear in `taxa`/`all_time_first_confirmed_at` at all.
- A later correction is authoritative going forward: `ProductRepository.
  revise_visit_review` mutates the same `VisitModel.reviewed_label` this
  module's queries read, so a corrected label's historical facts update
  and the superseded label's phantom record disappears, with no separate
  bookkeeping.
- An "unknown_bird"/"unknown_animal" confirmation (`_Classification.
  CONFIRMED_SPECIES_UNRESOLVED`) is real, counted wildlife activity, but
  never a named taxon's historical record -- it never appears in `taxa`,
  `distinct_taxa_count`, or any `SpeciesHistoricalStatus`.
- Multiple simultaneous sibling Visits under one Event (Multi-Subject Visit
  Assembly) each resolve to their own taxon's history independently -- a
  three-bird Event is never collapsed into one historical occurrence.

## Baseline maturity

`compute_baseline_maturity(usable_day_count)` (`historical_baseline.py`)
is purely a function of accumulated *usable* day count -- never of taxa or
Visit counts (mirrors `compute_report_maturity`'s identical discipline)
and never of raw calendar age alone:

- **`insufficient`** -- fewer than `MIN_USABLE_DAYS_FOR_DEVELOPING_
  BASELINE` (3) usable days. Covers both "literally zero monitoring
  history" and "a little, but not yet a pattern." A system installed 30
  days ago but monitored for 4 real hours stays here.
- **`developing`** -- 3 to 6 usable days. Some real history exists, but a
  regularity claim would still be weak.
- **`established`** -- `MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE` (7) or
  more usable days -- a full week's worth of genuinely well-monitored
  days, not necessarily consecutive.

3 and 7 are not picked from nothing: 3 reuses `_dashboard_today_summary`'s
own pre-existing regularity threshold (see above); 7 is a little over
double that floor and was checked directly against the real local dev
database's own retained history (2026-07-28 through 2026-08-09): only 6 of
that ~13-calendar-day span's days ever cleared the usable-day bar, which
should read -- and does read -- as "developing," not "established." That
is real-data grounding, not a claim that 7 is somehow the objectively
correct number; a future milestone may revisit it with more accumulated
real history.

## Usable day

A Place-local calendar day whose union of durable monitoring exposure
(across every non-archived Stream, from `MonitoringExposureIntervalModel`
-- never inferred from armed policy, runtime checkpoints, or the calendar)
totals at least `USABLE_DAY_MONITORED_SECONDS_THRESHOLD` (2 hours, the
same boundary `compute_report_maturity` already uses). `ProductRepository.
_historical_usable_dates` computes this via `historical_baseline.
bucket_intervals_by_local_day` (splitting any interval crossing a
Place-local midnight so overnight monitoring attributes correctly to each
real day, DST-transition-tested) and `usable_dates_from_daily_monitored_
seconds` (the one place the threshold is applied). A calendar day with a
real sighting but zero recorded exposure is never usable; a day with
substantial exposure spread across two Streams is unioned, never summed
(reuses `zone_insights.merge_intervals`, so overlapping coverage never
double-counts).

## "New" semantics

A taxon's per-report `historical_status.status` is `"new"` only when
*all* of the following hold, exactly matching the milestone's contract:

1. its all-time-earliest authoritative confirmation falls within this
   report's own `[period_start_at, period_end_at)`;
2. (implied by 1, since "earliest" is a true minimum) no earlier
   authoritative confirmation of that taxon exists for the Place;
3. `historical_baseline.maturity == "established"`.

When 1-2 hold but baseline maturity is `"insufficient"` or `"developing"`,
the status is `"first_record"` instead -- the frontend renders "First
confirmed record so far," never "New to your reviewed history," so an
immature Place never implies ecological novelty it cannot support.

## "Regular" semantics

A taxon is `"regular"` when it was confirmed on at least
`MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR` (3) distinct *usable* days within
the bounded historical window (below) -- never raw Visit count, and never
just any calendar day. Thirty Visits in one afternoon is still exactly one
usable day; a species confirmed on three different days that each had only
a few real monitored minutes is not regular, because those days never
cleared the usable-day bar in the first place. "Regular here" means
regular in this Place's own reviewed, monitored history -- no ecological
rarity/frequency claim, no comparison to any other place or species.

`"regular"` is structurally impossible while `historical_baseline.maturity
== "insufficient"` (fewer usable days exist Place-wide than the regularity
bar itself requires) -- `compute_species_historical_statuses` asserts this
explicitly rather than trusting the numeric coincidence silently, so a
future threshold change cannot quietly violate it.

## Historical window

Regularity and baseline-maturity computation are bounded to a trailing
`HISTORICAL_BASELINE_WINDOW_DAYS` (366-day) window -- reusing
`PlaceActivityReportRequest`'s own existing maximum report span, not a new
cap. This keeps per-day/per-Visit computation linear and bounded regardless
of how long a Place has been running, and keeps "regular" meaningfully
*recent* (a species regular five years ago but silent since should not
read "Regular here" forever).

The "no earlier authoritative record" check behind "new" cannot be bounded
the same way -- narrowing it to the window would let a taxon that first
appeared just outside it incorrectly read "new" again -- so it is answered
separately, cheaply, and genuinely unbounded: one `GROUP BY reviewed_label`
aggregate (`MIN`/`MAX` of `EventModel.started_at`) costs the same
regardless of total Visit volume, bounded only by the number of distinct
confirmed labels ever (small, in practice a few dozen at most), never a
per-Visit scan. See "Historical window" in place-activity-report-
contract.md for the identical two-tier design rationale this reuses.

The window's own end (`window_end_at`) is deliberately anchored
differently per surface:

- **Today (`place_activity_report`)**: the report's own `period_end_at` --
  never "now." A report for a past period reproduces identical historical
  facts regardless of when it is re-viewed, matching product-doctrine.md's
  "Derived insights... must remain reproducible from persisted facts."
- **Bird Log (`wildlife_journal_overview`/`wildlife_journal_history`)**:
  "now" -- Bird Log is a live view, not a fixed past report, so "regular
  as of right now" is the correct question.

## Coverage-aware, not archived-Stream-aware

Historical facts are scoped to the same non-archived-Stream set `place_
activity_report` already uses for its own "current Place" definition. A
Visit confirmed on a Stream whose Source has since been archived does not
contribute to `distinct_taxa_count`, usable-day accounting, or any
taxon's historical status -- a deliberate reuse of an existing scoping
decision, not a new policy invented here; see "Known limitations."

## Required outputs

Place-level (`HistoricalPlaceBaseline` / `PlaceActivityReportHistoricalBaseline`
on `PlaceActivityReportResponse.historical_baseline`, and `baseline_
maturity` on `WildlifeJournalOverviewResponse`/`WildlifeJournalHistoryResponse`):
`maturity`, `usable_day_count`, `total_monitored_seconds` (`None`
specifically when no durable exposure history exists at all -- the same
honest-absence convention `CoverageSummary.monitored_seconds` already
uses, distinct from a real zero for a Place monitored heavily outside the
current window), `distinct_taxa_count`, `earliest_authoritative_record_at`,
`latest_authoritative_record_at` (both all-time).

Per-taxon (`SpeciesHistoricalStatus` / `PlaceActivityReportTaxonHistoricalStatus`
on each `taxa[]` entry, present only for an authoritatively-confirmed
taxon; `WildlifeJournalLabelSummary.distinct_confirmed_usable_days`/
`is_regular` for Bird Log's own always-available per-label facts):
`first_confirmed_at`/`last_confirmed_at` (all-time), `distinct_confirmed_
days`/`distinct_confirmed_usable_days`/`total_confirmed_count` (window-
bounded), `status`.

No false precision is added anywhere: nothing here claims "normal,"
"unusual," a trend direction, or a population estimate.

## Today integration

`PlaceActivityReportTaxonEntry.historical_status` is additive and `None`
when a taxon in today's report has no authoritative confirmation at all
(purely provisional so far) -- exactly the truth-contract requirement that
a provisional suggestion can never earn a historical claim. `TodayReport
Panel.tsx` shows one small, reused `StatusPill` per species row only for
`"new"`/`"first_record"`/`"regular"` -- `"seen_before"` renders nothing,
keeping an ordinary day's report calm rather than annotating every row.

## Bird Log integration

Bird Log owns the deeper, always-available detail: `distinct_confirmed_
usable_days` and `is_regular` on every overview card and the label-history
detail view, plus a Place-wide `baseline_maturity` on both responses so
the existing `is_new_label_in_range` notice (an already-shipped,
range-relative "first record in the currently-viewed range" fact, left
unmodified) can be worded honestly -- "New to your reviewed history" only
when the baseline is established, "First confirmed record so far"
otherwise -- without a second, competing status enum. This mirrors the
existing "First on Stream"/"First in Zone" milestone-badge precedent
already in the per-observation gallery.

## Timezone correctness

Every local-day boundary (usable-day bucketing, distinct-confirmed-day
counting, the "new"/"first_record" period check) uses the same
Place-local timezone resolution `place_activity_report` already
establishes (`resolve_host_local_timezone` for Today; each surface's own
existing `datetime.now().astimezone()` convention for Bird Log, unchanged
by this milestone) -- no second timezone interpretation was introduced.
DST-transition correctness for `bucket_intervals_by_local_day` is tested
directly (spring-forward and fall-back, real 2026 US transition instants)
in `tests/test_historical_baseline.py`, mirroring `place_activity_report`'s
own DST test section.

## Performance

Bounded, not O(Visits): the all-time first/last lookup is one `GROUP BY`
aggregate; the windowed regularity lookup is one Visit query scoped to
366 days (mirroring `place_activity_report`'s own bounded Visit query
shape); usable-day bucketing is one interval fetch reused via extraction
(`ProductRepository._monitoring_exposure_intervals_and_history`, shared
with `_place_activity_coverage_summary`, a pure behavior-preserving
extraction proven by its full pre-existing test suite passing unmodified)
plus pure in-memory bucketing. Bird Log's own regularity figures reuse
records its existing `_wildlife_journal_confirmed_records` call already
fetched for the overview -- no second Visit query for that surface.

## Schema

No migration. Every fact here derives from `VisitModel`/`EventModel`/
`TaxonomyLabelModel` (already durable, already the same truth `place_
activity_report` reads) and `MonitoringExposureIntervalModel` (already
durable, schema v27). `maturity`/`status`/`is_regular` are computed fresh
on every read, never persisted -- they are derived statements that
legitimately evolve as reviewed history and monitoring accumulate, per the
milestone's own explicit instruction not to freeze them as permanent
truth.

## Explicit non-goals

Not implemented, deliberately, per this milestone's own scope: anomaly/
change detection, "more/less than normal" language, week/month/year report
UI, notifications/digests, eBird/weather causal context, ecological
rarity/absence claims, species-model changes, per-species Zone breakdown.
All require either a stronger historical/change-detection milestone or
fall outside this module's concern entirely -- see "Place Intelligence" in
product-doctrine.md and Phase 5 in roadmap.md for where they belong.

## Known limitations

- `_dashboard_today_summary`'s legacy `new_today`/`recent_regulars` (the
  Dashboard's "New today"/"Recent regulars" panels, still rendered
  alongside `TodayReportPanel`) answer a genuinely different, still-useful
  question ("active in the last 14 days," not coverage-aware) and were
  deliberately left untouched -- see "What already existed" above. A
  future bounded milestone could unify them onto this module's own
  coverage-aware primitives if the two surfaces' continued divergence is
  ever found confusing in practice; not attempted here to keep this
  milestone's blast radius to the surfaces it was actually asked to
  change.
- Historical facts are scoped to non-archived Streams only, matching
  `place_activity_report`'s own existing scoping -- a species only ever
  confirmed on a since-archived Stream will not contribute to `distinct_
  taxa_count`, usable-day accounting, or its own historical status. This
  is a reuse of an existing, already-accepted product scoping decision,
  not a new gap introduced here.
- The 3/7 usable-day thresholds are grounded in the real local dev
  database's retained history (see "Baseline maturity" above), which is
  still genuinely young. They are round, explainable, precedent-reusing
  numbers, not derived from a large real cohort -- a future milestone with
  more accumulated real field history is the natural place to revisit
  them, if warranted.
- No true multi-Place concept exists (MockingBird remains single-site);
  "Place-wide" here means "every non-archived Stream," identical to
  `place_activity_report`'s own existing scope.
