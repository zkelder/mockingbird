# Gate C -- Meaningful Change Detection / Baseline Comparison v1

`mockingbird.analytics.place_change_summary` is the second bounded slice of
[product-doctrine.md](product-doctrine.md)'s "Place Intelligence" layer,
built directly on the first
([historical-baseline-maturity-contract.md](historical-baseline-maturity-contract.md)).
It answers one further question neither that module nor
[place-activity-report-contract.md](place-activity-report-contract.md)
answers: has a taxon's (or the Place's overall) recorded presence recently
been higher, lower, or about the same as its own recent history -- under
comparable, coverage-aware monitoring, and never framed as ecological
population science. See "Explicit non-goals" below.

## What already existed, reused here

No prior "change detection"/"trend" concept existed anywhere in the
codebase before this milestone (confirmed by exhaustive search of
`zone_insights.py`, `wildlife_insights`, `_dashboard_today_summary`, and
`historical_baseline.py` -- none compares one period against another).
Everything this module needs already existed as a primitive, reused
directly rather than re-derived:

- `historical_baseline.compute_historical_place_baseline`'s own
  `usable_dates` set (via `ProductRepository._historical_usable_dates`) is
  the exact input this module's window-splitting reuses -- never a second
  definition of "usable day."
- `place_activity_report.TaxonFact`/`VisitFact`/`_classify` is the exact
  same truth-precedence resolution reused for presence-day accumulation.
- `ProductRepository._historical_place_baseline_and_species_statuses`
  already fetched everything this module needs (`usable_dates`,
  `window_visits`, the all-time-confirmed `taxa` dict) for historical
  baseline -- this milestone extends that one method to *also* return a
  `PlaceChangeSummary`, from the same query results, at zero additional
  database round trips for Today's own integration.
- Zone Insights' own "Visits per monitored hour, only with >= 2 supported
  healthy hours" precedent was considered as a second, separate metric (see
  the milestone's own "Primary metric"/"If normalized subject-Visit rate is
  also useful" framing) but deliberately not implemented in v1 -- see
  "Known limitations."

## Truth contract

Identical to `historical_baseline`'s own: only an authority-eligible
`ReviewLabel` (`VisitModel.review_status == "reviewed"`, non-superseded,
resolved to a real wildlife taxon) can establish or extend a taxon's
recent/reference presence. Concretely:

- A provisional `SpeciesSuggestion` is never consulted -- `window_visits`
  is built only from `review_status == "reviewed"` rows, so a needs_review
  Visit can never contribute a presence day regardless of how many days it
  spans.
- A later correction is authoritative going forward: the same
  `ProductRepository.revise_visit_review` write path historical_baseline
  already relies on mutates the same `VisitModel.reviewed_label` this
  module's own query reads, so a corrected label's comparison updates and
  the superseded label's phantom comparison disappears, with no separate
  bookkeeping.
- An "unknown_bird"/"unknown_animal" confirmation is real, counted wildlife
  activity for the Place-wide `overall` aggregate only (see "Coverage-aware
  zero semantics" below) -- never a named taxon's presence day.
- Multiple simultaneous sibling Visits under one Event (Multi-Subject Visit
  Assembly) each resolve to their own taxon's presence independently, and a
  taxon confirmed many times in one day still counts as exactly one
  presence day for that day -- see "Busy-day protection."

## Baseline prerequisite

Strong change claims require `historical_baseline.maturity == "established"`
(section 4 of the milestone instructions), but this module's own gate is
*stricter* than that alone: `RECENT_WINDOW_USABLE_DAYS` (7) +
`REFERENCE_WINDOW_USABLE_DAYS` (14) = 21 usable days must exist within the
bounded 366-day lookback, more than the bare 7-day "established" floor
guarantees. Whenever this module's own `PlaceChangeWindows.is_valid` is
`True`, `historical_baseline.maturity` is *always* "established" too
(asserted explicitly in `compute_place_change_windows`, mirroring
`compute_species_historical_statuses`'s own defensive "regular is
structurally impossible while insufficient" assertion) -- but the reverse
does not hold, and this module's own gate, never the coarser Place-wide
maturity alone, governs whether any comparison may be shown.

**Verified against the real local dev database** (`data/mockingbird.sqlite3`,
the same install `historical-baseline-maturity-contract.md`'s own
"Baseline maturity" section measured), read-only, at closure: 5 usable
days, `historical_baseline.maturity == "developing"`,
`change_windows.is_valid == False`,
`change_windows.invalid_reason == "insufficient_baseline"`,
`overall_change_status.status == "building_baseline"`. This is the
mandatory regression the milestone instructions require (section 4/19.17):
the real installation is not yet deep enough for a change claim, and this
module says exactly that, honestly, rather than fabricating interest to
make the feature look active.

## Recent/reference window design

Reuses `historical_baseline`'s own `usable_dates` set (the bounded,
already-coverage-aware set of Place-local calendar days clearing the
2-hour usable-day bar), sorted most-recent-first, then split by *count*,
not raw calendar span:

- **Recent window**: the most recent `RECENT_WINDOW_USABLE_DAYS` (7,
  reusing `historical_baseline.MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE`
  directly -- "a full week's worth of genuinely well-monitored days" is
  already an accepted, explainable product unit) usable days, however far
  back in calendar time that reaches.
- **Reference window**: the `REFERENCE_WINDOW_USABLE_DAYS` (14, exactly
  double) usable days immediately preceding the recent window -- again by
  usable-day count, so a real calendar gap between the two (a camera
  outage) is skipped over silently rather than treated as an absence (see
  "Coverage-aware zero semantics").
- **Freshness cap**: even once 7 usable days are found somewhere in
  history, if the single most-recent one is more than
  `RECENT_WINDOW_FRESHNESS_CAP_DAYS` (14, reusing the exact "recent"
  calendar span `_dashboard_today_summary`'s `recent_regulars`/`new_today`
  and `wildlife_journal_overview`'s own 14-entry `recent_activity`
  sparkline already established elsewhere in this codebase) calendar days
  before "now," the recent picture is stale -- monitoring has recently
  lapsed, a materially different, more honest state than "still building a
  baseline" (see `insufficient_recent_coverage` below).

This directly satisfies "do not compare 8 monitored hours against 15
monitored minutes as equivalent days" (section 5 of the milestone
instructions): the window boundaries themselves are defined by usable-day
count, never raw calendar span.

`PLACE_CHANGE_POLICY_VERSION` (currently `1`) is exposed in
`PlaceActivityReportChangeWindows.policy_version` and bumped whenever any
window/threshold constant changes, so a caller/export can record which
policy produced a given result.

## Comparable-monitoring rule

A comparison is only ever produced from `PlaceChangeWindows.is_valid`
being `True`. Both windows are always exactly 7/14 usable days once valid
(asserted explicitly) -- a comparison is never attempted from a partial
window. Offline/no-monitoring periods contribute nothing to either window
(they are simply absent from `usable_dates`, per `historical_baseline`'s
own discipline) and can never widen or narrow a window's *denominator*;
they can only push its calendar boundaries further back in time.

## Primary metric: presence-day recurrence, not Visit count

Every count is a *distinct usable day a taxon was confirmed on*, the exact
same discipline `historical_baseline.compute_species_historical_statuses`
already applies to its own `distinct_confirmed_usable_days` -- this module
only adds the recent-vs-reference split on top of that existing metric.
Thirty Visits on one usable day is still exactly one presence day (see
"Busy-day protection," below); presence recurrence *across* days, not raw
Visit volume, drives the v1 interpretation.

A separate normalized subject-Visit-rate metric ("Visits / monitored
hour," mirroring Zone Insights' own precedent) was considered but not
implemented in v1 -- see "Known limitations."

## Threshold policy (versioned)

A status of `higher_recent_presence`/`lower_recent_presence` requires
*all* of:

1. at least `MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON` (1) reference-
   window presence days -- a taxon never seen in the reference window has
   no historical rate to compare against (that is a "new"/"first_record"
   question `historical_baseline` already answers honestly); zero
   reference presence always reads `no_supported_change`, never a
   fabricated increase, regardless of how much recent presence exists;
2. a rate difference (`recent_presence_days / 7` minus
   `reference_presence_days / 14`) of at least
   `MIN_PROPORTIONAL_DIFFERENCE` (0.25, i.e. 25 percentage points); and
3. an absolute difference (the recent count minus the reference count
   rescaled onto the recent window's own 7-day length, so both are
   compared "per 7 days" on a common basis) of at least
   `MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE` (2 days) -- this guards against a
   rate swing driven by tiny numbers, since a 7/14-day window is small
   enough that a single extra day already moves the rate substantially.

Both (2) and (3) must clear their bar together; either alone falling short
reads `no_supported_change`. These numbers were checked directly against
deterministic fixtures (`tests/test_place_change_summary.py`) and the
milestone's own worked example (`Recent: 5 of 7`, `Reference: 3 of 14` --
a 50-point rate difference and a 3.5-day rescaled absolute difference,
comfortably clearing both bars) rather than picked in isolation.

## Change-state semantics

Per-taxon (`TaxonChangeStatusValue`): `insufficient_baseline` (this
module's own 21-usable-day gate is not yet met -- "still building a
baseline"), `insufficient_recent_coverage` (deep total history exists, but
the single most-recent usable day is stale), `no_supported_change`
(comparison ran, but the threshold policy above was not cleared),
`higher_recent_presence`, `lower_recent_presence`. Window validity is a
Place-wide property, decided once and applied uniformly to every taxon and
the Place-wide `overall` aggregate -- never decided per taxon.

Place-level (`PlaceChangeStatusValue`, deliberately distinct wording from
the per-taxon vocabulary even though the underlying computation is the
same shape): `building_baseline`, `insufficient_recent_coverage`,
`no_supported_change`, `more_activity_recorded`, `less_activity_recorded`.

Neither vocabulary contains "increasing," "declining," "rare," "abnormal,"
a population claim, or a statistical-significance claim -- see "Explicit
non-goals."

## Busy-day protection

Structurally guaranteed by the metric choice (presence-days, never Visit
counts), not by a separate rule: `_presence_dates_by_taxon_and_overall`
accumulates a `set[date]` per taxon (and one for `overall`), so however
many Visits land on one calendar day, that day contributes exactly one
membership to the set. Thirty Visits on one usable day is exactly one
presence day, identical in its contribution to a single Visit on that same
day -- proven directly in `tests/test_place_change_summary.py::test_one_
busy_recent_day_does_not_imply_a_persistent_increase` and its reference-
window-side mirror, and again through the real write path in
`tests/test_place_change_summary_repository.py`.

## Place-level change summary

A single, honest Place-wide aggregate (`overall`/`PlaceOverallChangeStatus`)
is computed -- not a forced blend of potentially conflicting per-species
signals. This avoids the "do not force a global conclusion when species
signals conflict" trap by construction: `overall` never looks at
per-species presence at all, only whether *any* confirmed wildlife activity
(named-species and "unknown_bird"/"unknown_animal" abstentions alike) was
recorded on each usable day, using the exact same recent/reference windows
and threshold policy every per-taxon comparison uses. A Place with one
species trending up and another trending down still gets one honest,
independently-computed `overall` answer -- it is not an average or
majority vote over the per-taxon statuses.

## Coverage-aware zero semantics

Mandatory distinctions, all structurally guaranteed by reusing
`historical_baseline`'s own `usable_dates` set as this module's only input:

- **Sufficiently monitored + species not recorded** -- a usable day simply
  outside the taxon's (or, for `overall`, any taxon's) presence-date set;
  contributes a real, honest zero to that day's presence count.
- **Insufficiently monitored** -- a calendar day that never cleared the
  2-hour usable-day bar is never in `usable_dates` at all, so it can never
  be intersected into either window's presence-day count either way --
  never a fabricated absence.
- **No monitoring at all** -- covered by `insufficient_baseline`/
  `insufficient_recent_coverage` at the window level before any per-day
  accounting is even attempted.

A camera outage can therefore never produce "species appearing less
often": an outage either shrinks `usable_dates` (making a window harder to
populate, at worst producing an honest `insufficient_baseline`/
`insufficient_recent_coverage`, never a fabricated "lower" claim) or, if it
falls between two otherwise-fully-populated windows, is silently skipped
over with no effect on either window's presence-day accounting at all --
proven directly in `tests/test_place_change_summary.py::test_offline_
days_are_excluded_not_counted_as_absences` (up to a 90-day synthetic gap)
and its repository-level counterpart.

## Multi-subject behavior

Unchanged from `historical_baseline`'s own accepted semantics, reused
verbatim: multiple simultaneous sibling Visits under one Event (Multi-
Subject Visit Assembly) each resolve to their own taxon's presence
independently (a nuthatch-and-two-finches Event contributes one presence
day to the nuthatch's count and one to the finch's, never conflated), and
a taxon confirmed on the same calendar day by several sibling Visits still
counts as exactly one presence day for that taxon that day.

## Timezone / local-day semantics

No new timezone system. `compute_place_change_windows`/
`_presence_dates_by_taxon_and_overall` take the identical `local_timezone`
parameter historical_baseline's own bucketing already resolves
(`resolve_host_local_timezone` for Today's period-anchored calls; each
Bird Log surface's own existing `datetime.now().astimezone()` convention,
unchanged). The only timezone-sensitive operations this module performs
itself are anchoring `window_end_at` to a local calendar date and bucketing
each Visit's own local date -- both proven directly across the real 2026
US spring-forward and fall-back transitions in
`tests/test_place_change_summary.py`; the heavier interval-splitting DST
math itself is `historical_baseline.bucket_intervals_by_local_day`'s own
already-proven, reused-unchanged responsibility.

## Explicit non-goals

Not implemented, deliberately, per this milestone's own scope: ecological
population trends, statistical-significance claims, regional rarity,
migration timing, causal weather/eBird/LLM interpretation as observational
authority, alerts/notifications, digest delivery, week/month/year report
UI, per-species Zone breakdown, and a separate normalized Visits-per-
monitored-hour metric (considered, not built -- see "Known limitations").
All require either a stronger research-grade capability or fall outside
this module's concern entirely -- see "Place Intelligence" in
product-doctrine.md and Phase 5 in roadmap.md for where they belong.

## Backend integration

`ProductRepository._historical_place_baseline_and_species_statuses` is
extended (not duplicated) to also return a `PlaceChangeSummary`, computed
from the exact same `usable_dates`/`window_visits`/`taxa` it already
fetched for historical baseline. Two changes were needed to that method's
own query, both additive and behavior-preserving for its pre-existing
historical-baseline output (confirmed by the full pre-existing test suite
passing unmodified):

1. The `window_rows` query now runs whenever any Stream exists, not only
   when `taxa` (all-time confirmed *wildlife* taxa) is non-empty -- the
   Place-wide `overall` aggregate must still see a confirmed "unknown_
   bird"/"unknown_animal" abstention even when no named species has ever
   been confirmed.
2. Each `window_rows` row is now resolved through a broader taxonomy
   lookup (any category, not only wildlife) so `overall` can recognize a
   non-wildlife-category or "unknown"-category confirmation as a
   `VisitFact` at all. This never changes `compute_species_historical_
   statuses`'s own output: it already ignores any classification other
   than `CONFIRMED_WILDLIFE`, so a Visit resolved here to a non-wildlife
   category is filtered out downstream exactly as before this milestone.

`ProductRepository.place_activity_report` (Today), `wildlife_journal_
overview`, and `wildlife_journal_history` (Bird Log) each call the
(now-extended) method and thread `change_summary` through their own
existing response-building code -- Bird Log pays three additional bounded
queries (a taxonomy index, an all-time first/last aggregate, a windowed
Visit query) beyond what it already issued for `is_regular`/`baseline_
maturity`, none of them `O(labels)`/`O(Visits)` beyond what Today's own
identical computation already costs.

## API

Purely additive to the existing Place Activity Report / Bird Log response
shapes -- no new route, matching the milestone's own preference (section
22):

- `PlaceActivityReportResponse` gains `change_windows`
  (`PlaceActivityReportChangeWindows`) and `overall_change_status`
  (`PlaceActivityReportOverallChangeStatus`), both required (the repository
  always computes them, mirroring `historical_baseline`'s identical
  contract).
- `PlaceActivityReportTaxonEntry` gains `change_status`
  (`PlaceActivityReportTaxonChangeStatus | None`), `None` under the
  identical truth-contract condition as `historical_status`.
- `WildlifeJournalLabelSummary` and `WildlifeJournalHistoryResponse` each
  gain the same optional `change_status` field, reusing the identical
  `PlaceActivityReportTaxonChangeStatus` shape across both surfaces.

## Today integration

`taxa[].change_status` renders a small `StatusPill` next to the existing
historical-status badge only for `higher_recent_presence`
("More often recently") / `lower_recent_presence` ("Fewer recent visits")
-- every other status (including no `change_status` at all) renders
nothing, matching `historicalStatusBadge`'s own established "seen_before
renders nothing" discipline exactly, so an ordinary day is never decorated
with a wall of "no change" pills.

`overall_change_status` renders one calm, Place-level line (never per-
species) for the four "worth mentioning" states (`building_baseline`,
`insufficient_recent_coverage`, `more_activity_recorded`,
`less_activity_recorded`); `no_supported_change` deliberately renders
nothing at all -- silence is the calm default, mirroring the identical
per-species discipline one level up.

## Bird Log integration

Both the overview card and the label-history detail view expose the
identical `change_status` object (`recent_presence_days`/`recent_usable_
day_count`/`reference_presence_days`/`reference_usable_day_count`/
`status`), reusing the same shared `changeStatusBadge` helper (`web/src/
utils.ts`) Today uses, so both surfaces render identical wording for the
identical underlying fact. The label-history detail view additionally
shows the bounded explanatory sentence ("Recent: N of 7 usable monitored
days · Reference: M of 14 usable monitored days") the Today badge alone
does not have room for -- matching the milestone's own "Normal UI may
simplify this; API/provenance must retain enough bounded facts to explain
why" instruction.

## Place-level status decision

Evaluated and implemented, not omitted: see "Place-level change summary"
above for why a single, non-conflicting aggregate was achievable in v1
(unlike a forced per-species blend, which was correctly avoided).

## Schema

No migration. Every fact here derives from already-durable
`VisitModel`/`EventModel`/`TaxonomyLabelModel`/`MonitoringExposureInterval
Model` state (the exact same rows `historical_baseline`/`place_activity_
report` already read) plus the bounded `usable_dates` set those modules
already compute. `PlaceChangeSummary`/`TaxonChangeStatus`/
`PlaceOverallChangeStatus`/`PlaceChangeWindows` are computed fresh on every
read, never persisted -- "higher"/"lower" is never frozen as permanent
observational truth, per the milestone's own explicit instruction.
`policy_version` is exposed in the response for reproducibility, not
persisted as a separate row.

## Performance

Bounded, not `O(taxa)`/`O(days)`: `compute_place_change_windows` is one
`sorted()` over an already-bounded (at most 366-entry) usable-date set;
`_presence_dates_by_taxon_and_overall` is one pass over the same
`window_visits` list `historical_baseline` already built. Today's own
integration costs zero additional database queries (change summary is
computed from data `_historical_place_baseline_and_species_statuses`
already fetched for historical baseline); Bird Log's own integration costs
three additional bounded queries per call (see "Backend integration"
above), none proportional to label or Visit count.

## Known limitations

- **No separate normalized Visits-per-monitored-hour metric.** Considered
  (Zone Insights already has a "Visits per monitored hour, only with >= 2
  supported healthy hours" precedent this could have reused), but not
  implemented in v1 to keep this milestone's blast radius to the mandatory
  presence-day design -- a future bounded milestone could add it as a
  clearly-separate, never-blended metric on `TaxonChangeStatus`, per the
  milestone's own explicit "keep it as a separate metric" instruction.
- **No per-species Zone breakdown.** Not attempted; falls outside this
  milestone's explicit scope exclusions.
- **The 7/14/25%/2-day/14-day-freshness thresholds are grounded in
  deterministic fixtures and the milestone's own worked example, not a
  large real cohort** -- the real installation does not yet have anywhere
  near 21 usable days of history (see "Baseline prerequisite" above), so
  these numbers cannot yet be checked against real accumulated field data.
  A future milestone with materially more accumulated real history is the
  natural place to revisit them, exactly mirroring `historical_baseline`'s
  own disclosed limitation about its 3/7-usable-day thresholds.
- **Bird Log's `change_status` is computed from the same wildlife-general
  `taxa`/`window_visits` Today uses, not re-derived from Bird Log's own
  bird-only `_wildlife_journal_confirmed_records`.** This is intentional
  reuse, not a gap: every bird label Bird Log ever displays is also a
  wildlife taxon in Today's own `taxa` dict, so the lookup always succeeds
  for a real bird label; it simply means Bird Log's own per-surface
  historical-baseline computation (`is_regular`/`distinct_confirmed_
  usable_days`, unchanged by this milestone) and its new `change_status`
  are sourced from two different (but equally correct) query paths within
  the same call, not unified into one -- not attempted here to avoid
  touching the already-accepted `is_regular` computation's own tested
  behavior.
