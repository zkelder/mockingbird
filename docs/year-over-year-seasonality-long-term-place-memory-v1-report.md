# Year-over-Year Seasonality & Long-Term Place Memory v1

A deliberately-authorized, one-time, bounded product-development reopening
(see [release-execution-state.md](release-execution-state.md) §3 for the
full governing brief). Builds MockingBird's first true **year-over-year**
comparison -- "how does this season compare with the same time last
year," at this Place -- closing the exact gap `seasonal_pattern.py`'s own
docstring, the Place / Yard Intelligence v2 report, and the Global
Remaining Product-Development & Release-Queue Reconciliation v1 report all
independently named as the honest ceiling of every existing seasonality
primitive: a single trailing 366-day window that resets forward, never
accumulates across years.

## Starting state

- Branch `main`, accepted HEAD `c07171b` (the report commit for
  Environmental Context x Place Story & Habitat Change Composition v1).
- Schema `v58`, unchanged by that milestone and unchanged by this one.
- `CURRENT PHASE`: `FEATURE FREEZE -- EVIDENCE, RELEASE READINESS &
  HOUSEKEEPING`. Lane P `CLOSED`. Lane R `OPEN -- RELEASE-CRITICAL -- TRUE
  LATENCY TAIL EVIDENCE REMAINS` (untouched by this milestone, per its own
  explicit instruction not to touch it).
- Authorization before this milestone: `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED`.
- Worktree verified safe at start: all seven preserved untracked detector
  files (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) present and untouched throughout;
  confirmed again at close.

## Why product development was reopened

The Global Remaining Product-Development & Release-Queue Reconciliation v1
report (2026-09-06) explicitly named year-over-year seasonality as
"blocked on elapsed real history, not engineering" and recorded MockingBird
as functionally at feature freeze. This milestone is a separate, explicit,
owner-authorized reopening for exactly this one capability -- not a
resumption of general product development, and not self-authorized. Its
own governing brief requires returning to feature freeze at close unless a
concrete new dependency is found; none was (see "Feature-freeze impact,"
below).

## Existing architecture reused

Archaeology (governing brief §5, three parallel Explore agents plus direct
reads) found a mature, directly-reusable foundation. Nothing below was
rebuilt:

- **Coverage/effort primitive**: `_monitoring_exposure_intervals_and_
  history` -> `historical_baseline.bucket_intervals_by_local_day` ->
  `historical_baseline.usable_dates_from_daily_monitored_seconds` -- the
  exact chain `_historical_usable_dates` already composes for its own
  366-day trailing window, now extracted into a window-parameterized
  sibling, `_usable_dates_for_window` (see "API/domain changes"). This is
  the *union*-based (not summed) exposure computation Multi-Camera Place
  Experience v2 already fixed at Place scope, so two overlapping cameras
  never double the effective monitored time.
- **Materiality/coverage-gating primitive**: `conditional_association.
  compute_conditional_association` -- the exact same presence-day-rate
  primitive `place_change_summary`/`seasonal_pattern`/`habitat_
  association`/`feature_change_comparison` already use. Year-over-year
  reuses it *unmodified*: `condition_dates` is set to the current period's
  own calendar days, and `usable_dates` is narrowed to exactly the two
  compared periods, so the primitive's own "in condition" / "out of
  condition" split becomes exactly "current period" / "prior-year
  comparable period" with zero new statistical logic. Every threshold this
  milestone needs (the 5-usable-day floor, the 25-percentage-point
  rate-difference gate) comes from that one already-accepted module.
- **Multi-camera dedup**: `ProductRepository._associated_visit_ids_to_
  exclude_from_counting` (Camera / Source + Multi-Camera Maturity v1) --
  applied once, over the pooled Visit ids of *both* compared periods
  (never two separate dedup calls), before any presence date is derived.
- **Archived-Stream policy**: `place_story`'s own unconditionally-inclusive
  Stream selection (no `CameraSourceModel.status` filter) -- reused
  verbatim for the identical "a Place-memory surface must not lose real
  history to a later archival" reasoning.
- **Truth-precedence classification**: a new `compute_period_presence_
  facts` function in the new module applies the exact same `_classify`/
  `_Classification` truth-precedence `place_activity_report.py` owns,
  imported directly (matching this package's established per-module
  convention of writing a small local classification loop rather than
  importing a sibling module's private helper -- see e.g. `source_
  activity.compute_source_activity`'s own independent copy of the same
  pattern).
- **Story-event composition shape**: `place_story.comparison_insight_event`
  -- year-over-year's own `year_over_year_place_event`/`year_over_year_
  species_event` mirror its established "a separate, later-dated
  `\"inferred\"` event, never fused into the wildlife fact it explains"
  shape.
- **Response-schema convention**: `PlaceFeatureAssociation`'s flattened
  `ConditionalAssociation` field naming, reused verbatim for `PlaceYear
  OverYearAssociation` (see "API/domain changes" for the one deliberate
  divergence -- a wider status range).
- **N+1 avoidance**: `_taxonomy_label_index` (one query, indexed by every
  normalized candidate key) -- reused unmodified; no second per-row
  taxonomy lookup anywhere in the new code.

No prior seasonality module (`seasonal_pattern.py`) was modified. It
remains exactly what its own docstring says it is: a single-trailing-year,
non-accumulating primitive, explicitly out of scope for reuse here because
its month-of-year buckets carry no year dimension at all -- the one
concept genuinely new to this milestone.

## Comparable-period contract

A `[start_date, end_date)` half-open calendar range, matched to the
identical range one year earlier by shifting *both* boundaries
independently via `date.replace(year=...)` (`comparable_prior_period` in
the new `year_over_year_comparison.py`), not a fixed 365/366-day
`timedelta` -- deterministic, and immune to the day-of-week drift a
364/365-day shift would introduce. Feb 29 maps to Feb 28 in a non-leap
target year, the one documented, always-applied rule (never a per-call
choice); the disclosed consequence is that a span crossing Feb 29 shifts to
a same-shaped prior span exactly one calendar day shorter -- accepted, not
defended against, because every comparison is a *rate* (presence days /
usable days) computed independently on each side, never a raw count
assumed to share one denominator, so the one-day mismatch never biases a
result (proven directly: `TestShiftYearAndComparablePeriod::test_span_
crossing_feb_29_is_one_day_shorter_in_the_prior_non_leap_year`).

**Month is the supported period shape** -- the one calendar-aligned
granularity with real precedent (`seasonal_pattern.py`'s own whole-month
buckets) and the shape every one of the milestone brief's own worked
examples uses ("this September... last September"). `calendar_month_
period(year, month)` is a small, direct helper; week-level or named-season
comparison is an explicit non-goal (see "Explicit non-goals").

**Partial-period honesty**: the current period's own natural end is
clamped to `min(natural_end_date, today + 1 day)`, and `is_complete` is
carried alongside it. An in-progress calendar month (the common case --
`ProductRepository.place_year_over_year_comparison()` defaults to *the
current* Place-local month) is never compared as if finished: `is_complete
= False` forces the dedicated `partial_period` abstention status, checked
*after* both coverage floors so a period that is both incomplete and
under-monitored reports the more fundamental coverage problem instead
(`TestPlaceLevelAbstention::test_coverage_floor_takes_priority_over_
partial_period`). The prior-year comparable period is always complete by
construction (it ends in the past whenever the current period's own end is
at or before "today").

## Coverage / effort normalization

This is the requirement the governing brief called "the most important
correctness requirement," and it is answered by **not inventing a new
metric at all**: the verdict is a coverage-normalized *presence-day rate*
(distinct days a taxon/the Place was confirmed present, divided by distinct
*usable* days), the same convention `place_change_summary`, `seasonal_
pattern`, and `habitat_association` already established. A day only counts
as usable once real monitored exposure clears `historical_baseline.
USABLE_DAY_MONITORED_SECONDS_THRESHOLD` (2 hours, unioned across every
in-scope Stream) -- so raw monitored-hours totals never factor into the
verdict, only the binary usable-day gate does. Proven directly, not merely
asserted: `TestUnequalEffortNormalization` constructs a current period
monitored 8x more intensively per day than an "equal effort" baseline (20
hours/day vs. 2.5 hours/day) and shows the verdict, direction, and even the
underlying `ConditionalAssociation` object come out byte-identical, because
both periods clear the identical usable-day count either way; a second test
shows a period racking up far more *raw* hours (24 hours/day, 4 usable
days) than another (2 hours/day, 20 usable days) is correctly *not*
favored -- its own thin usable-day count still triggers an honest
`insufficient_prior_coverage` abstention. This directly satisfies the
brief's own worked example (100 Visits/20 monitored hours must never read
as "more active" than 90 Visits/200 monitored hours): a presence-day rate
is structurally immune to that exact trap without needing to reason about
camera-hours arithmetic at all.

Overlapping-camera coverage is not double-counted: the union math
(`merge_intervals`, reused unmodified) already collapses two cameras both
healthy for the same hour into one hour of Place-wide exposure, proven with
real before/after numbers (`TestPlaceComparison::test_overlapping_multi_
camera_coverage_is_not_double_counted` -- two fully-overlapping 30-day
cameras produce exactly 30 usable days, not 60).

## Species comparison contract

Deliverable A (normalized activity difference) and Deliverable B (first-
observed timing difference) only -- the brief's own suggested minimal
scope, chosen deliberately over the fuller candidate list (sustained
seasonal presence window, regularity difference) it also offered but did
not require. `compute_species_year_over_year_comparisons` returns one entry
per taxon confirmed in *either* period (never silently dropping a taxon
seen only a year ago, or only this year -- both get an honest, direction-
bearing entry: `TestEveryTaxonRepresented`), each independently gated
through the identical `compute_conditional_association` primitive the
Place-level comparison uses. `select_notable_species_changes` then
bounds/ranks the result for presentation: eligible only when a real
activity difference exists (`status == "comparable"`) or a material timing
shift does; ranked by *evidence strength* (`min` of the two sides' presence
-day counts, never the larger side and never the raw percent difference)
descending, then alphabetically; bounded to
`MAX_SPECIES_CHANGES_RETURNED` (5). Proven directly that a dramatic-looking
tiny-denominator ratio (1 of 30 days vs. 0) never outranks a real,
well-evidenced difference (16 vs. 4 of 30): `TestSelectNotableSpeciesChanges
::test_ranks_by_evidence_strength_not_raw_percent_change`.

## First-observed timing contract (implemented)

`current_first_observed_date`/`prior_first_observed_date` are each
period's own earliest confirmed date for that taxon. Per the governing
brief's section 11 ("first observed" is not "arrived"), the contract is
strictly:

- Requires a first-observed date on **both** sides -- a taxon absent from
  one period entirely has no "N days earlier/later" to report (that case
  is `historical_baseline`'s own "new"/"first_record"/"seen_before"
  territory, not re-claimed here).
- Requires at least `MIN_USABLE_DAYS_BEFORE_FIRST_OBSERVATION_FOR_TIMING_
  CLAIM` (5, reusing the identical numeral as the coverage floor)
  **usable** days *before* the first-observed date, on **both** sides,
  before the date is trusted at all -- otherwise "first observed on day 2"
  may only mean "monitoring itself started on day 1," never a genuine
  absence beforehand (`TestFirstObservedTiming::test_thin_lead_in_
  coverage_suppresses_the_timing_claim`, and the boundary-inclusive proof
  `test_lead_in_floor_is_exactly_the_documented_constant`).
- A day-difference is computed as each period's own offset from its start
  date (never a raw calendar-date subtraction, which the leap-year span
  exception would bias) and is narrated only when its absolute value clears
  `MIN_MATERIAL_TIMING_DIFFERENCE_DAYS` (7 -- a small, explicit, documented
  contract per the brief's own section 12 instruction, since no existing
  threshold answers this specific question; reuses the codebase's own
  recurring "a week is a meaningful, explainable unit" judgment).
- Wording is always **"first observed here"**, never "arrived" -- audited
  directly in both `place_story.year_over_year_species_event` and
  `YearOverYearCard`'s frontend sentence composer, plus a dedicated e2e/
  unit assertion that the word never appears.

## Materiality

No new threshold invented for the core verdict: `conditional_association`'s
own existing 25-percentage-point rate-difference gate (`DEFAULT_MIN_RATE_
DIFFERENCE`) and 5-usable-day floor (`DEFAULT_MIN_USABLE_DAYS_IN_
CONDITION`) are imported and reused, not re-derived -- the same numbers
`place_change_summary`/`habitat_association`/`feature_change_comparison`
already converged on, satisfying the brief's own "prefer existing
association strength bands" instruction directly. Exactly two genuinely new
numbers were needed, both a small, explicit, documented product contract
per the brief's section 12 (no existing threshold answers either
question):

- `MIN_USABLE_DAYS_BEFORE_FIRST_OBSERVATION_FOR_TIMING_CLAIM` (5) -- reuses
  the coverage-floor numeral for a different judgment (lead-in coverage,
  not overall period coverage).
- `MIN_MATERIAL_TIMING_DIFFERENCE_DAYS` (7) -- a week, this codebase's
  recurring "meaningful, explainable unit."

Species ranking is by evidence strength, never raw percent change (see
"Species comparison contract").

## Abstention

`PlaceYoYStatus` -- `comparable | no_material_difference |
insufficient_prior_history | insufficient_current_coverage |
insufficient_prior_coverage | partial_period` -- matches the governing
brief's own suggested vocabulary (section 9) exactly; no gratuitous
proliferation beyond it. Priority order, most-fundamental-blocker first
(`_status_from_association` in the new module):

1. `insufficient_prior_history` -- zero usable days a year ago **and** no
   durable monitoring history reaches back to at or before that period's
   own end (a real defect caught and fixed during this milestone's own
   development before it shipped -- see "New defects").
2. `insufficient_current_coverage` -- current period below the 5-usable-day
   floor.
3. `insufficient_prior_coverage` -- prior period below the floor, but not
   zero (some real history exists, just not enough).
4. `partial_period` -- the current period has not finished yet (checked
   only after both coverage floors pass).
5. `no_material_difference` -- both periods are well-monitored, the
   comparison ran fully, and the difference simply is not material -- a
   positive, complete result ("Activity is similar..."), never conflated
   with "we don't know."
6. `comparable` -- a real, material difference was found.

Every abstention case the brief's section 13 requires is reachable and
tested: no prior-year data; inadequate current/prior coverage; highly
asymmetric coverage (the unequal-effort tests above); too few eligible
observations (tiny-denominator tests); period not complete enough to
interpret (`partial_period`); a materiality floor not cleared
(`no_material_difference`). "Corrected/unresolved truth that makes
comparison unstable" is structurally prevented rather than separately
gated: only `resolution == "reviewed"` Visits with a resolved `confirmed_
taxon` ever contribute presence (the identical `_classify` boundary every
sibling module already enforces), so no unresolved/provisional truth can
enter the comparison at all.

## Reviewed correction safety

Every fact is computed fresh from current rows on every call -- no
persisted comparison, no cache, no invalidation step, matching this
codebase's universal discipline for every other Place read-model. Proven,
not assumed, at three levels:

- **Pure module**: `TestDeterminism` -- identical inputs give an identical
  result, twice.
- **Repository**: `TestCorrectionSafety::test_reviewed_species_correction_
  changes_the_very_next_call` (re-labeling 16 Visits from Northern Cardinal
  to Blue Jay moves the notable-species entry on the very next read) and
  `test_rejecting_a_visit_removes_it_from_the_comparison` (a `false_
  positive` correction drops the Visit's contribution to `confirmed_
  wildlife_visit_count` immediately).
- **Product-shaped scenario**: Act 4 corrects a real 2025 Visit from an
  incorrect label (House Finch) to its true one (Carolina Wren) and asserts
  a *precise* number moved -- that taxon's own prior-period presence-day
  count in the drill-down `association` object goes from exactly 0 to
  exactly 1, the identical Visit now counted under its corrected label,
  proving propagation is exact, not merely "something changed somewhere."

## Archived Stream behavior

Unconditionally inclusive -- the same policy `place_story` already
established for the identical reasoning (a long-term Place-memory surface
must not silently lose real history because a camera was later retired),
deliberately *not* Today/Bird Log's current-active-observatory default.
Proven directly: `TestCorrectionSafety::test_archived_stream_history_
remains_reachable` (archiving a camera mid-test leaves every count
byte-identical) and the product-shaped scenario's Act 3 (Back Yard is
archived after both Septembers are seeded; the comparison's status,
direction, and every count are unchanged).

## Multi-camera duplicate safety

`_associated_visit_ids_to_exclude_from_counting` is applied once, over the
pooled Visit ids of both compared periods together (a real cross-camera
"associated" pair only ever forms between Visits close in time, which by
construction never spans the year-apart boundary between the two periods,
so pooling costs one dedup query pair instead of two). Proven directly:
`TestMultiCameraDuplicateSafety::test_associated_cross_camera_encounter_
counts_once` and `test_independent_simultaneous_animals_both_count`
(two different species at the same instant, no association row, both
genuinely count), plus the product-shaped scenario's own real cross-camera
pair (a Blue Jay seen by both cameras three seconds apart, counted once in
a total of 31, never 32).

## Local Only

No network call exists anywhere in the new code path -- confirmed
structurally (the new module and repository method touch only SQLite via
SQLAlchemy) and proven directly, not merely asserted by reading the source:
the product-shaped scenario patches `socket.socket.connect` to raise for
its entire duration, and the full scenario (five Acts, two repository
methods, real Reviewed corrections) still passes.

## Performance

The forbidden pattern this milestone's own governing brief and Place
Story's own disclosed "period summaries" finding both warn against is
calling the expensive 366-day-trailing `_historical_place_baseline_and_
species_statuses` once per period in a range. This milestone never does:
exactly two short (typically ~30-day) Visit/coverage query pairs total, one
per compared period, regardless of how much unrelated history exists.
Proven two ways:

- **Query count, not merely timing**: `TestPerformance::test_query_count_
  does_not_grow_with_unrelated_historical_depth` seeds three additional,
  unrelated years of monthly coverage plus a confirmed Visit in every one
  of those 36 months, and shows the exact SQL query count for one `place_
  year_over_year_comparison()` call is unchanged before and after (a
  `before_cursor_execute` SQLAlchemy event-listener harness, mirroring
  `tests/test_place_activity_report_repository.py`'s own established
  `_count_taxonomy_queries` pattern).
- **Real wall-clock timing against a realistic seeded history**: an ad-hoc
  script (not part of the committed suite) seeded a synthetic 3-year,
  2-camera, ~1,644-Visit, ~2,192-exposure-row history (denser than any real
  installation this product has today, mirroring Place Story's own
  "3-year, 20-taxa, 1,637-Visit" precedent proof) and measured:
  - `place_year_over_year_comparison()`: **17.9 ms** (16.2 ms on a repeat
    run, confirming no growth).
  - The *isolated* marginal cost of the new Place Story integration --
    the identical requested Story period, once with "now" inside its
    range (the year-over-year gate fires) and once just after it (the
    gate does not fire), holding every other cost fixed -- was **-4.9 ms**
    (noise-level; effectively zero). The ~330 ms `place_story()` totals
    observed are entirely the pre-existing wildlife-checkpoint-scan cost
    that milestone's own report already measured and accepted, confirmed
    unrelated to this change by this isolation.

Place Story's own integration is additionally bounded at the call-site
level, not just by query shape: it computes the year-over-year facts *at
all* only when the requested Story range actually contains "now" (a deep
historical-archive browse has no "current period" to anchor to and skips
this entirely, at exactly zero cost) -- proven directly by `test_year_
over_year_insight_is_skipped_for_a_historical_archive_range`.

## API/domain changes

**Zero schema change** (stays v58). `PlaceYearOverYearComparison`/
`TaxonYearOverYearComparison`/`PeriodInput`/`ComparablePeriod`/
`PeriodPresenceFacts` are plain, never-persisted dataclasses in the new
`mockingbird/analytics/year_over_year_comparison.py` (~450 lines of pure
computation, ~210 lines of module/threshold documentation). One
pre-existing repository method was refactored, not behaviorally changed:
`_historical_usable_dates` now delegates to a new, window-parameterized
sibling, `_usable_dates_for_window` (pure extraction -- its own 6
pre-existing call sites' full test coverage passes unmodified, confirmed
directly). Two new repository methods compose the new module:
`_year_over_year_comparison_facts_in_session` (the query+compute core,
reusing a caller's already-open session and already-fetched `stream_ids`/
`taxonomy_index` -- never opens a second session, matching `_place_story_
feature_events`'s identical session-reuse shape) and the public `place_
year_over_year_comparison`.

New API route: `GET /api/place/year-over-year` (optional `year`/`month`
query params, defaulting to the current Place-local month; a future month
or a lone `year`/`month` returns HTTP 400). New response schemas in
`schemas.py`: `PlaceYearOverYearResponse` (`generated_at`, `place`,
`notable_species_changes`), `PlaceYearOverYearComparison`, `PlaceYearOverYear
Period`, `PlaceYearOverYearAssociation`, `PlaceYearOverYearSpeciesEntry`.
`PlaceYearOverYearAssociation` deliberately widens `PlaceFeatureAssociation`'s
own flattened-`ConditionalAssociation` shape to include `"insufficient_
data"` in its status range (a real difference from `FeatureAssociationStatus`,
which structurally excludes it because `FeatureChangeComparison`'s own
contract guarantees `association` is `None` whenever that value would
occur -- year-over-year's own `association` is always populated, even in
an abstention, so drill-down can still show "0 of 5 usable days" behind an
abstention verdict). `PlaceStoryEventKind` gains one additive value,
`"year_over_year"` (group `"context"`, alongside `comparison_insight`).

## UI

**Place / Yard Intelligence** (the primary surface, per the brief's own
example): a new `YearOverYearCard` -- "Compared with last year," the
current/prior period labels, a `StatusPill` + one plain sentence for the
Place-level verdict (identical non-judgmental "quiet" tone for both
`"higher"` and `"lower"`, matching `overallChangeBadge`'s own precedent),
and up to five notable species entries, each composed from raw fields on
the frontend (mirroring `featureAssociationSentence`'s established
per-surface composition convention, not backend-provided prose). Rendered
identically on both the Dashboard and the Place Report page (a genuinely
separate, period-independent fetch on each -- the report's own period
picker answers a different question, "activity in the period I chose,"
from "this calendar month vs. a year ago"). Absence-safe: renders nothing
while the fetch is in flight or failed, the same discipline every sibling
card (`BiodiversitySummaryCard`, `PlaceFeaturesCard`) already follows.

**Place Story** (the secondary surface): `year_over_year_place_event`/
`year_over_year_species_event` emit calm, dated, `"inferred"` entries under
the existing "Insights" category filter -- gated in the repository so the
computation is only attempted when the Story's own requested range
includes "now" (see "Performance").

No new top-level navigation destination; no new chart library; no giant
analytics dashboard; no trend arrows without accompanying text; no red/
green value judgment for wildlife increase/decrease -- verified directly by
a dedicated e2e test asserting no arrow glyph or "declined"/"population"
wording ever appears.

## First-year experience

A Place with no comparable prior-year history renders the calm, honest
sentence the brief's own section 24 suggested almost verbatim: "Long-term
patterns will appear here once MockingBird has a full comparable year of
history." Never an error banner, never an empty chart, never implied
misconfiguration -- proven by a dedicated e2e test (`a brand-new Place
shows an honest, calm first-year message, not an error`) that also asserts
no text matching `/error/i` ever appears on the card.

## Product-shaped proof

One real, executable, end-to-end scenario
(`tests/test_year_over_year_product_shaped_scenario.py`), mirroring this
codebase's own established capstone-proof convention (Multi-Camera Place
Experience v2's 3-camera scenario, Ecological Interoperability's 12-Visit
scenario) -- matches the governing brief's own section 26 example closely:
2 cameras (Front Feeder, Back Yard); September 2025 with moderate Cardinal
regularity (6 of 30 days) and Eastern Bluebird first observed the 25th
(the brief's own hummingbird example, substituted for a taxonomy label
this codebase's demo data actually carries -- "ruby_throated_hummingbird"
does not exist in it, confirmed by direct grep); September 2026 with
genuinely higher Cardinal activity (16 of 30 days), Eastern Bluebird first
observed materially earlier (the 8th), one real cross-camera associated
encounter, and Back Yard archived partway through. Demonstrates, in one
coherent run with real seeded SQLite state and no mocking of product
logic: the normalized Place-level comparison (`comparable`/`higher`); the
species-level activity and timing verdicts with their exact dates and
signs; archived-camera history remaining fully reachable and numerically
identical before/after archival; the cross-camera pair counting once (31
confirmed Visits, never 32); a Reviewed correction moving a precise count
(0 -> 1) on the very next read; a calm, non-causal Place Story entry; and
zero network access for the entire scenario.

## Validation

**Tier 1 (pure computation)**: 38 tests in `tests/test_year_over_year_
comparison.py` (`compute_period_presence_facts`, comparable-period/leap-year
math, Place-level and species-level status/direction, first-observed
timing, ranking, unequal-effort normalization, determinism, every-taxon-
represented) -- all passing. 16 new tests added to `tests/test_place_
story.py` for the three new Story-event functions (activity-only, timing-
only, both-signals, abstention, causal-language audit, composition/
bounding) -- all passing.

**Tier 2 (repository/integration)**: 25 tests in `tests/test_year_over_
year_comparison_repository.py` (Place comparison, history sufficiency,
species, correction safety, multi-camera, a real HTTP round trip via
`GET /api/place/year-over-year`, and the query-count performance proof) --
all passing. 2 new tests added to `tests/test_place_story_repository.py`
(the Story integration firing when the range includes "now," and being
skipped when it does not) -- all passing. 1 product-shaped scenario test
(above) -- passing.

**Broader Tier 2.5 sweep**: every directly-affected subsystem re-run
together (`test_calm_attention`, `test_canonical_new_regular_species_
consistency`, `test_conditional_association`, `test_daily_digest`,
`test_dashboard_today`, `test_ecological_interoperability_repository`,
`test_environmental_context`, `test_environmental_period_comparison`,
`test_habitat_association`, `test_historical_baseline[_repository]`,
`test_local_only_privacy`, `test_multi_camera_place_experience_scenario`,
`test_multimodal_observation_acceptance`, `test_place_activity_report_
repository`, `test_place_biodiversity_summary[_repository]`, `test_place_
change_summary[_repository]`, `test_place_story[_repository]`, `test_
regularity_narrative`, `test_review_decision_provenance`, `test_seasonal_
pattern`, `test_source_activity`, `test_temporal_pattern`, plus every new
file above): **677 passed, 1 failed** -- the one failure is `test_place_
change_summary_repository.py::test_api_round_trip_exposes_change_detection_
fields`, independently re-confirmed pre-existing and unrelated via a fresh
`git stash push -u` bisection against the exact commit this milestone
started from (identical failure, identical assertion, before any of this
milestone's own code existed) -- a real-calendar-date-dependent flake
already documented in this session's own memory as encountered before.

**ruff**: zero new findings, proven by a message-level (not merely
line-number) diff against a `git stash`-isolated clean baseline across
every touched file, run twice at different points in the session for
rigor -- both times byte-identical to baseline. The ~82-83 pre-existing
findings in `product_repository.py`/other large files are untouched by
this milestone's own diff, confirmed directly.

**Frontend**: `tsc --noEmit` clean; `vite build` clean; 7/7 new `year-
over-year.spec.ts` e2e tests passing (first-year state, a real material
increase with notable species, a genuinely similar period, an in-progress
partial period, no red/green judgment, the Place Report page showing the
identical card, phone-width legibility); 23/23 directly-adjacent existing
e2e specs re-run unmodified and passing (`dashboard-live-camera-ownership`,
`place-activity-report`, `today-report`); 29/29 across the four Place-
Story/Biodiversity/Features specs re-run together, confirming the
`PlaceStoryEventKind` extension introduced no regression.

**Local Only**: proven directly in the product-shaped scenario (see
above), not merely by architecture review.

Not run: full Core (per the governing brief's own explicit "do not run
full Core by reflex" instruction -- this milestone's changes are additive
plus one behavior-preserving, fully-regression-tested extraction, not
materially cross-cutting in the sense that would warrant it).

## New defects

**Found and fixed during this milestone's own development, never
shipped**: an early draft of `PeriodInput.has_any_monitoring_history`
conflated "this Stream has *some* durable history, ever, at any point
(including the future, or the *other* compared period)" with "history
reaches back to at or before *this specific* period's own end" -- the
first, weaker signal is what `_monitoring_exposure_intervals_and_history`'s
`history_available_from is not None` actually answers, but the
`insufficient_prior_history` vs. `insufficient_prior_coverage` distinction
this milestone's own status vocabulary requires needs the second, stronger
one. Caught by this milestone's own `TestHistorySufficiency::test_no_prior_
year_history_at_all` before any commit; fixed by widening `_usable_dates_
for_window`'s own return shape to expose the raw `history_available_from`
instant (not a pre-collapsed boolean) and comparing it against each
period's own end at the call site -- `_historical_usable_dates`'s external
behavior is unchanged (it collapses the same instant to the identical
boolean it always returned, at its own call site; its full pre-existing
test suite across all 6 real call sites confirms this).

A second, smaller defect of the same "caught before shipping" character:
the first `PlaceYearOverYearAssociation.status` schema reused `Feature
AssociationStatus` directly, which structurally excludes `"insufficient_
data"` -- correct for `PlaceFeatureAssociation` (whose `association` is
`None` exactly when that value would occur) but wrong here (year-over-
year's `association` is always populated). Caught immediately by a real
`pydantic_core.ValidationError` in the repository test suite; fixed by a
dedicated, wider `PlaceYearOverYearAssociationStatus` Literal.

A third: the first pass added `"year_over_year"` to `place_story.py`'s own
`PlaceStoryEventKind`/`_KIND_GROUP` (the pure analytics module) but missed
the mirrored Pydantic `PlaceStoryEventKind` in `schemas.py` -- caught
immediately by a real `pydantic_core.ValidationError` in `test_place_story_
repository.py` when the first end-to-end Story integration test ran; fixed
by adding the missing Literal value. A fourth, purely frontend instance of
the identical "extend an enum in one place, forget its mirror" class: added
to `PlaceStoryPage.tsx`'s `KINDS_BY_GROUP` (would have silently hidden
every year-over-year Story entry from the "Insights" category filter) and
`KIND_LABEL` (a TypeScript `Record<PlaceStoryEventKind, string>`, which
would have been a compile error had it been missed) -- both caught by
direct code review before any test run, not by a failure.

**Pre-existing, re-confirmed, unrelated**: `test_place_change_summary_
repository.py::test_api_round_trip_exposes_change_detection_fields` (see
"Validation") -- documented in this session's own persisted memory as
having been encountered and independently bisected in at least one prior
milestone; re-confirmed here via a fresh, independent bisection against
this milestone's own exact starting commit.

## Explicit non-goals / remaining opportunities

Per the governing brief's own section 27, and its instruction to choose
"the smallest high-value subset" rather than build every possible signal:

- **Week-level or named-seasonal-period comparison** -- only whole
  calendar months are supported (the one shape with real precedent and
  matching every worked example in the brief). A future milestone wanting
  "compare this week to the same week last year" would need a second
  period-boundary contract; not attempted here.
- **"Sustained seasonal presence window" and "regularity difference"**
  species signals -- named as candidates in the brief's own section 10 but
  explicitly not required; deferred to keep the delivered scope the
  brief's own suggested minimal one (normalized activity + first-observed
  timing).
- **Environmental/weather context on a year-over-year insight** -- the
  brief's own section 19 explicitly discourages this milestone from
  re-opening that scope; not attempted.
- **A year/month picker in the UI** -- the API already accepts arbitrary
  `year`/`month`, but the shipped `YearOverYearCard` always shows only the
  current month vs. a year ago (the brief's own "no giant analytics
  dashboard" instruction). Browsing other months is a natural, bounded
  follow-on, not built here.
- **A real, live production proof of a `"comparable"` (material-difference)
  outcome** -- this product does not yet have a full year of *real*
  accumulated field history anywhere. Confirmed directly, not assumed: a
  read-only copy of this repository's own real, unmodified local
  development database (`data/mockingbird.sqlite3`, never itself written
  to -- confirmed byte-identical by checksum before and after) was queried
  through the real `place_year_over_year_comparison()` call with no
  parameters (today's real date). It returned `status="insufficient_prior_
  history"`, `current_period` `[2026-09-01, 2026-09-07)` with `usable_day_
  count=0`, `prior_period` `[2025-09-01, 2025-09-07)` also `usable_day_
  count=0` -- the honest, correct answer for a real installation this
  young, not a contrived success. Every "comparable"/"higher"/"lower" proof
  in this
  report is synthetic (pure-module tests, repository tests with seeded
  fixtures, the product-shaped scenario) -- correct and thorough, but not
  a substitute for a real deployment eventually reaching real year-over-
  year depth. This is the identical, unavoidable "blocked on elapsed real
  history, not engineering" constraint the Global Remaining Reconciliation
  already named; it does not block acceptance of the engineering itself.
- **`select_notable_species_changes`'s bounded list has no "see all"
  drill-down** -- deliberately: the brief's own section 18/23 explicitly
  wants a small, calm, ranked set, not a full sortable table. A future
  milestone wanting the complete per-taxon list (for research/export
  purposes, say) has `compute_species_year_over_year_comparisons`'s own
  unranked, unbounded return value already available at the repository
  layer; only the presentation layer bounds it.

## Feature-freeze impact

No concrete new dependency was found. This milestone's own implementation
was fully self-contained: zero schema change, one behavior-preserving
extraction of an existing repository helper (fully regression-tested
across all 6 of its pre-existing call sites), and additive-only changes
everywhere else. `CURRENT PHASE` returns unchanged to `FEATURE FREEZE --
EVIDENCE, RELEASE READINESS & HOUSEKEEPING`. This closure does **not**
authorize External Pre-Release Acceptance, Final Release Hardening, the
next Lane R daylight tranche, or any further product-development
milestone. Lane R (`OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
REMAINS`) is completely untouched, exactly as the governing brief required.

## Decision

**B** -- a real, working, well-tested, well-integrated major capability
(the first true year-over-year comparison this product has ever had,
closing a gap named across at least five prior milestone reports),
composed almost entirely from already-accepted primitives with zero schema
change, a real product-shaped end-to-end proof, a real measured
performance proof, and several genuine defects caught and fixed by this
milestone's own test-writing before anything shipped. Not **A**: the one
inherent, undeferrable limitation is that no real deployment can yet
demonstrate a live `"comparable"` outcome, since this product does not yet
have a full year of real accumulated field history anywhere -- every
positive-outcome proof in this report is necessarily synthetic (correct
and thorough, but a real field proof remains a future opportunity once
real history exists, not a defect of this milestone). A small number of
deliberately bounded scope choices (month-only periods, two species
signals instead of the fuller candidate list, no year/month picker UI) are
recorded above as explicit, brief-consistent non-goals, not gaps.
