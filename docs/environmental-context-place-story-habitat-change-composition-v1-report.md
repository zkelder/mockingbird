# Environmental Context x Place Story & Habitat Change Composition v1

**Classification: A** (bounded composition over already-accepted engines; zero
schema change; zero new statistical primitive).

## Starting state

Verified exactly as the governing brief expected before any change:

- Branch `main`, HEAD `d3b9820` (the report commit for MIT Source License
  Adoption & Lane P Mechanical Closure v1).
- Schema `v58` (`mockingbird.storage.database.CURRENT_DATABASE_SCHEMA_VERSION`).
- `CURRENT PHASE`: `FEATURE FREEZE -- EVIDENCE, RELEASE READINESS &
  HOUSEKEEPING`; Lane P `CLOSED`; Lane R `OPEN -- RELEASE-CRITICAL -- TRUE
  LATENCY TAIL EVIDENCE REMAINS`; authorization `NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED`.
- Worktree safe: no active writer process, no `.git/index.lock`; all seven
  preserved untracked detector files present and byte-unchanged throughout
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`).

## Why product development was deliberately reopened

This milestone's own governing brief is an explicit, one-time, bounded
override of feature freeze: it names exactly one product relationship
(environmental context -> Feature/habitat-change understanding -> Place
Story understanding) that the immediately-prior reconciliation
(`global-remaining-product-development-release-queue-reconciliation-v1-report.md`)
had itself examined under its five-question product-opportunity test and
found did not clear the bar for *unprompted* pre-release development. The
owner's explicit choice tonight overrides that specific conclusion for this
one item only. This does not reopen the roadmap generally, does not
authorize a second milestone, and does not change Lane R or Lane P.

## Existing architecture (archaeology, before any code change)

Answering the brief's own eight archaeology questions directly:

1. **Environmental facts and granularity.** `environmental_context_records`
   (schema v51, additive since) stores one row per hour per metric:
   `provider_key` (`solar_local` | `open_meteo`), `information_class`
   (closed Measured/Inferred/Reviewed vocabulary -- both existing writers
   emit `"inferred"` only, never `"measured"`/`"reviewed"`), `metric`,
   `value_numeric`/`unit`, `observed_at`/`for_date` (UTC calendar date, the
   cache key), `retrieved_at`, `basis_latitude`/`basis_longitude`,
   `provenance_json`. Open-Meteo's eight metrics (`air_temperature`,
   `relative_humidity`, `precipitation_amount`, `snowfall_amount`,
   `wind_speed`, `wind_direction`, `cloud_cover`, `surface_pressure`) are
   already fully persisted at this granularity; this milestone uses exactly
   two (`air_temperature`, `precipitation_amount`), matching the two axes
   `weather_association.py` already exercises.
2. **Historical periods already queryable.** Any UTC calendar date within
   the provider's confirmed `WEATHER_MAX_PAST_DAYS = 92`-day recent-history
   window that a prior Today/Visit/report lookup already caused to be
   fetched -- read-only, lazily populated, `for_date` indexed
   (`ix_environmental_context_records_lookup`). Older-than-92-day cached
   rows remain readable forever; nothing outside what is already cached is
   ever reachable.
3. **Before/after period boundaries.** `mockingbird.analytics.
   feature_change_comparison.compute_feature_change_comparison` already
   defines a 7/14/30-day symmetric-window escalation around one
   `PlaceFeatureChangeEventModel.effective_date`, returning
   `pre_start`/`post_end`/`window_days` on its `FeatureChangeComparison`
   result. This milestone reuses these three fields as the *only* source of
   truth for "before"/"after" -- see "Contract," below.
4. **Place Story event/insight structures.** `mockingbird.analytics.
   place_story.PlaceStoryEvent` is a pure, frozen, non-persisted read-model
   dataclass with a bounded event taxonomy. Its `comparison_insight` kind
   already had a wired-but-unimplemented `weather_caveat: str | None = None`
   parameter on `comparison_insight_event()` -- confirmed, not assumed, by
   reading `place_story.py` directly and its own report's "Environmental /
   phenology composition" section, which names this exact gap.
5. **Provenance/epistemic fields already available.** `information_class`
   (`"inferred"` for all environmental facts), `provider_key`,
   `retrieved_at`, `basis_latitude`/`basis_longitude` on every environmental
   record; `SolarContext`/`WeatherConditions`'s established "always-present
   object, `available`/`status` carries honest absence" convention (never
   `None` standing in for "not configured").
6. **Composable without schema change?** Yes, confirmed by direct
   inspection of every table this milestone touches: zero new columns, zero
   new tables. `CURRENT_DATABASE_SCHEMA_VERSION` stays `58`.
7. **An internal presentation contract already intended for this gap?**
   Yes, on both sides: `PlaceFeatureAssociation`/`PlaceFeatureChangeEventWithComparison`
   already carry the exact `pre_start`/`post_end`/`window_days` triple this
   milestone needed to align against, and Place Story's `comparison_insight_event`
   already had the `weather_caveat` parameter wired end-to-end (repository
   call site included) and unit-tested (`test_comparison_insight_never_fuses_weather_into_a_causal_claim`)
   before this milestone ever touched it -- it was simply never populated.
8. **Canonical frontend homes.** `PlaceActivityReportPage.tsx`'s "Features &
   changes" section (the existing `featureAssociationSentence` before/after
   copy) for Deliverable A; `PlaceStoryPage.tsx`'s existing card `summary`
   rendering (no frontend change needed at all) for Deliverable B.

Also confirmed while reading `condition_bands.py`/`weather_association.py`/
`conditional_association.py`: **three**, not two, near-identical
"query cached `air_temperature` rows over a trailing window and build a
`TemperatureBaseline`" blocks existed in `product_repository.py` before this
milestone -- `_recent_temperature_band` (Visit/Today single-instant
banding, UTC-bucketed), the inline block inside
`_historical_place_baseline_and_species_statuses` (report-period banding,
local-timezone-bucketed), and (now) this milestone's own need. The first two
use genuinely different day-bucketing conventions for different reasons
(documented in "Existing architecture (archaeology)" above); only the
second was extracted and reused (see "Feature before/after composition,"
below) -- `_recent_temperature_band` is deliberately left untouched, a
disclosed, bounded, out-of-scope third occurrence, not a defect.

## Contract

**No second engine, anywhere.** One new pure module,
`mockingbird.analytics.environmental_period_comparison`, shared unmodified
by both deliverables through one new repository method,
`ProductRepository._feature_environmental_period_comparison`
(`product_repository.py`), which itself reuses
`_cached_place_weather_context` -- a second new repository method, but not
a second *engine*: it is the exact query/banding
logic `_historical_place_baseline_and_species_statuses` already ran,
extracted so both call sites share one cached-weather-read path.
`comparison_window_dates(pre_start, post_end, window_days)`, one small new
public function added to the existing, accepted `feature_change_comparison.py`,
reconstructs the *identical* before/after calendar-day sets the wildlife
comparison already used, from only the three fields `PlaceFeatureAssociation`
already returns -- so the environmental comparison can never silently judge
a different period than the wildlife one it sits beside.

**Additive schema-shape only.** One new Pydantic response type,
`FeatureEnvironmentalComparison`, and one new field on the existing
`PlaceFeatureChangeEventWithComparison` (`environmental_comparison:
FeatureEnvironmentalComparison | None`). Place Story needed **zero** new
API/schema surface: `comparison_insight_event`'s `weather_caveat` parameter
already existed, wired through the repository, tested at the pure-function
level, simply never populated.

## Epistemic / causal-safety rules

- `FeatureEnvironmentalComparison.information_class` is typed
  `Literal["inferred"] | None` -- the type system itself forbids assigning
  `"reviewed"` here, not merely a convention. `PlaceFeature`/
  `PlaceFeatureChangeEvent.information_class` (`Literal["reviewed"]`) are
  untouched by this milestone; no code path this milestone added ever
  writes to them.
- Every producible sentence is one of exactly five fixed templates (two
  temperature, two precipitation, one neutral), all in
  `summarize_environmental_period_comparison`, none containing "caused,"
  "led to," "resulted in," "because of," "drove," "due to," or "may
  explain." Enforced by a parametrized test over every reachable sentence
  (`test_no_producible_sentence_ever_uses_causal_language`), plus a
  redundant substring audit in the repository-level and e2e tests, plus the
  real product-shaped proof's own audit (see below) -- checked, not assumed.
- `comparison_insight`'s wildlife sentence and the environmental caveat
  remain two independently-composed clauses joined with a space, never
  fused into one causal statement -- unchanged, pre-existing behavior in
  `comparison_insight_event`, now finally exercised with a real caveat.
- Place Story only ever *adds* the caveat when a metric is genuinely
  evaluated and meaningfully different (`include_neutral=False`); it never
  states "conditions were similar" on an ordinary entry, because Place
  Story's own doctrine ("never a weather log") specifically forbids
  narrating the *absence* of news, whereas Place Feature's dedicated
  comparison surface (`include_neutral=True`) correctly treats "similar" as
  a valid, useful answer to the question a user came there to ask.

## Environmental materiality rule

No new number was invented. Materiality reuses two already-accepted
classifiers unmodified:

- **Temperature**: each period's own mean daily temperature (`condition_bands.
  daily_mean`, restricted to hourly-complete days) is classified against the
  Place's existing `TemperatureBaseline` (`condition_bands.
  compute_temperature_baseline`/`classify_temperature_day` -- the identical
  tertile computation `weather_association.py` already runs for a single
  day). A note is produced *only* when the two periods land in genuinely
  different Place-relative bands; both landing in the same band (even "both
  cooler than typical") stays silent -- a deliberate conservative bias
  toward abstention, verified directly
  (`test_both_periods_cooler_than_typical_is_not_a_difference`).
- **Precipitation**: each period's own per-day wet/dry classification
  (`condition_bands.classify_precipitation_day`, a fixed 0.2mm physical
  threshold, not Place-relative) rolls up into a period-level wet-majority/
  dry-majority verdict (`>50%` of usable days, so an exact tie counts as
  "not predominantly wet" -- verified directly,
  `test_exact_half_wet_days_is_not_a_majority`). A note is produced only
  when the two periods' majorities differ.
- **Coverage floor**: `MIN_USABLE_DAYS_PER_PERIOD` is not a new number --
  it is *literally* `conditional_association.DEFAULT_MIN_USABLE_DAYS_IN_CONDITION`
  (`5`), imported and aliased, so a future change to that shared floor
  automatically applies here too. `status = "insufficient_coverage"` only
  when *neither* metric clears this floor in *both* periods; one metric
  succeeding while the other abstains still yields `"comparable"` overall
  (`TaxonPlaceContext`'s established "neither field blocks the other"
  convention, reused, not reinvented).
- The Place's own broader (up to 92-day) cached history -- not just the two
  windows under comparison -- forms the temperature baseline, avoiding the
  circular case of tertiles computed only from the exact two samples being
  judged.

## Feature before/after composition

`get_place_feature_detail`'s existing per-change-event loop now also calls
`_feature_environmental_period_comparison` whenever the wildlife
`comparison.maturity` is already `"early_signal"`/`"comparable"` (i.e., a
real window exists to align against), producing a
`FeatureEnvironmentalComparison` with one of four statuses
(`not_configured`/`disabled` -- mirroring `WeatherConditions.status`'s own
identical values; `insufficient_coverage` -- mirroring
`FeatureComparisonMaturity`'s own value; `comparable`). `pre_start`/
`post_end`/`window_days` are always populated once the method is even
called, so a caller can state which period was or was not compared even
when nothing else could be said. On the frontend
(`PlaceActivityReportPage.tsx`),
a new `environmentalComparisonSentence` helper renders `comparison.summary`
as a small, quiet second line directly beneath the existing wildlife
sentence, visible only when `status === "comparable"` -- every other status
renders nothing at all, matching `EnvironmentalContextCard`'s established
"absence is silence" convention. The wildlife insight remains the visually
primary fact; the environmental line is unambiguously secondary (same
`meta-text` styling, no new visual weight).

## Place Story composition

`_place_story_feature_events`'s existing `comparison_insight` construction
(already gated on `maturity in ("early_signal", "comparable")` and
`association.status in ("more_common_under_condition",
"less_common_under_condition")`) now calls the identical shared method with
`include_neutral=False`, replacing the previous hardcoded `weather_caveat=None`.
No new Story event kind, no weather-only entries, no schema/API change:
the caveat is appended as a trailing clause onto the *existing*
`comparison_insight` sentence exactly as `comparison_insight_event`'s own
pre-existing (and pre-tested) contract already specified. An ordinary
`feature_change`/`first_seen`/`regularity_change`/`phenology` entry is
completely untouched by this milestone -- the only Story surface capable of
carrying environmental context at all remains the one place the brief
explicitly named ("meaningful before/after wildlife shift").

## Sparse/abstention behavior

| State | Feature surface | Place Story surface |
| --- | --- | --- |
| Meaningful difference | Restrained sentence (e.g. "The after period was notably cooler.") | Same sentence family, appended as a trailing clause |
| No meaningful difference | "Conditions were broadly similar across the two periods." | Silent -- no caveat appended |
| Partial coverage (one metric only) | Whichever metric was evaluated speaks; the other silently abstains | Same |
| Insufficient coverage | `status="insufficient_coverage"`; frontend renders nothing | Silent |
| Not configured / weather disabled | `status="not_configured"`/`"disabled"`; frontend renders nothing | Silent |
| No trustworthy period alignment (wildlife side itself `too_soon`/`insufficient_coverage`) | `environmental_comparison` is `None` entirely -- never attempted | N/A (`comparison_insight` itself is never emitted) |

No status is ever rendered as raw enum text; no `0.0`/`None` is ever
presented as "no change" (the neutral sentence is only reachable through
`status == "comparable"`, i.e. real, sufficient data that happened to show
no difference -- structurally distinct from "we don't know").

## Provenance

`FeatureEnvironmentalComparison` retains `information_class` (`"inferred"`),
`provider_key` (`"open_meteo"`), the exact `pre_start`/`post_end`/
`window_days` window, and the raw `pre_mean_temperature_c`/
`post_mean_temperature_c`/`pre_total_precipitation_mm`/
`post_total_precipitation_mm` measured-style values -- available in the API
for provenance and testing, deliberately not surfaced prominently in the
UI (which shows only the composed `summary`), per "compact and selective."
Place Story deliberately duplicates none of this: the caveat is a plain
string composed dynamically at read time from the same underlying facts,
never a second persisted copy, consistent with the accepted precedent that
Place Story "never queries a database, never re-derives review truth."

## Correction safety

Nothing new is persisted, so nothing new can go stale by construction --
both new repository methods run inside the existing "computed fresh at read
time, never cached" call graph. Proven directly, not merely argued:

- `test_correcting_change_event_date_also_collapses_environmental_comparison`
  moves a change event's `effective_date` so the wildlife comparison drops
  to `"too_soon"`, and asserts the previously-`"comparable"` environmental
  comparison (which had been stating "The after period was notably cooler")
  becomes `None` on the very next read, no invalidation call.
- Deleting a change event already removes its `feature_change` Story entry
  entirely (`test_removed_feature_change_event_disappears_from_the_story`,
  pre-existing); `comparison_insight` is derived from the identical
  per-event loop with no independent query of its own, so deleting the
  event structurally removes any would-be `comparison_insight` (and its
  caveat) the same way -- confirmed by direct code inspection of
  `_place_story_feature_events`, which has exactly one `event_models` query
  feeding both event kinds.

## Local Only behavior

Neither new repository method ever calls a weather provider -- both are
pure reads over already-persisted `environmental_context_records` rows.
Proven, not assumed: `test_feature_environmental_comparison_never_calls_the_network`
injects the same always-raises fake requester
`test_local_only_privacy.py` uses, seeds a full comparable-with-a-real-
difference scenario entirely via direct ORM inserts (bypassing the fetch
path), and asserts the requester's `call_count` stays exactly `0` after a
full `get_place_feature_detail` read that correctly produces "The after
period was notably cooler." Every other new test in this milestone also
seeds weather this same way (direct row insertion, never the fetch path),
so the entire test suite for this milestone already exercises the
network-independent path by construction.

## UI

Only one frontend file changed, `PlaceActivityReportPage.tsx` (the existing
"Features & changes" section) -- no new page, no new nav
entry, no Dashboard change. `PlaceStoryPage.tsx` needed zero changes: its
existing card already renders `entry.summary` verbatim, so a populated
`weather_caveat` flows through automatically. `web/src/api/types.ts` gained
the two new hand-mirrored types (`EnvironmentalComparisonStatus`,
`FeatureEnvironmentalComparison`) plus the new field, matching this
repository's established "no codegen, manually kept in sync" convention.

## Validation

**Tier 1 (focused, during implementation):** every new/changed test file
run individually as it was written (RED->GREEN loop throughout).

**Tier 2 (affected environmental-context + Feature + Story subsystem --
deliberately not the full `scripts/verify_core.py` gate, per this
milestone's own explicit instruction not to escalate merely because
feature freeze was reopened tonight):**

```
python -m pytest tests/test_environmental_period_comparison.py tests/test_place_feature.py \
  tests/test_place_story.py tests/test_place_story_repository.py tests/test_conditional_association.py \
  tests/test_condition_bands.py tests/test_weather_association.py tests/test_environmental_context.py \
  tests/test_place_activity_report.py tests/test_place_activity_report_repository.py \
  tests/test_wildlife_journal.py tests/test_place_biodiversity_summary.py tests/test_local_only_privacy.py
```

**377 passed, 0 failed.** Additionally ran (separately, once, to prove the
`_cached_place_weather_context` extraction is behavior-preserving for its
pre-existing caller): `test_environmental_context.py`,
`test_weather_association.py`, `test_weather_provider.py`,
`test_place_activity_report_repository.py`, `test_local_only_privacy.py`,
`test_ecological_interoperability_repository.py`, `test_persistence.py` --
**220 passed, 1 pre-existing skip, 0 failed**. Separately confirmed (via a
direct `git stash` comparison) that `test_place_biodiversity_summary_repository.py`'s
2 failures (`test_api_route_returns_the_summary`,
`test_human_correction_updates_place_biodiversity_intelligence_correctly`,
both `'seen_before' == 'new'`) are byte-identical on unmodified baseline
HEAD -- a pre-existing, date-sensitive flake unrelated to this milestone,
not a regression it introduced.

`python scripts/verify_fast.py` (Tier A, the repository's own broader cheap
regression net): **1,801 passed, 0 failed** (204s).

`ruff check` on every new/changed Python file: clean. `ruff check` on the
two large files this milestone edited (`product_repository.py`,
`test_place_feature.py`) shows the identical pre-existing finding sets as
unmodified baseline HEAD (confirmed via a line-by-line diff of `ruff`'s own
output before/after), with one exception: this milestone's own new
`PlaceWeatherContext(NamedTuple)` finally uses the `typing.NamedTuple`
import that baseline HEAD had sitting unused, so the changed file has
**one fewer** finding than baseline, not more.

**Frontend:** `npm run typecheck` clean; `npm run build` succeeds (104
modules, no new warnings); `npm run test:e2e -- place-features` (8 passed,
2 new), `npm run test:e2e -- place-story` (6 passed, unchanged),
`npm run test:e2e -- place-activity-report` (3 passed, unchanged).

Tier 3 (full cross-cutting gate) was not run -- nothing in this milestone
touches Observation truth, review/correction provenance, Visit admission,
evidence lineage, migrations, backup/restore, Camera Node, or packaging;
the change is additive-schema-shape, reuse-only, and its two riskiest
surfaces (the weather-context extraction, and the correction-safety/
Local-Only properties) were each independently, directly proven above.

## Product-shaped proof

A real, product-shaped scenario run end-to-end through `ProductRepository`
(real SQLite, zero mocks) -- a Reviewed feeder Feature added, confirmed
wildlife activity absent before and daily after, and locally persisted
`air_temperature` context showing a genuine, meaningful, non-causal
difference:

```
--- What the user sees: Place Feature before/after comparison ---

Feature: Sunflower Feeder -- added on 2026-06-20
Wildlife: more_common_under_condition (maturity=comparable, window=7d)
Environmental: status=comparable, information_class=inferred, provider=open_meteo
  pre_mean_temperature_c=15.0, post_mean_temperature_c=0.0
  summary: "The after period was notably cooler."

--- What the user sees: Place Story timeline ---

[2026-06-20] (feature_change, reviewed) Sunflower Feeder added
    "Sunflower Feeder added."
[2026-06-20] (first_seen, reviewed) First Northern Cardinal observation
    "First reviewed observation of Northern Cardinal recorded at this Place."
[2026-06-22] (regularity_change, reviewed) Northern Cardinal became a regular presence
    "Northern Cardinal has become a regular presence at this Place."
[2026-06-27] (comparison_insight, inferred) Activity higher after sunflower feeder added
    "Confirmed wildlife activity was higher during the monitored period after Sunflower Feeder was added, compared with the monitored period before. The after period was notably cooler."

--- Causal-safety audit over every rendered sentence above ---
Forbidden causal words found: NONE
```

This demonstrates, in one run: what changed in wildlife (confirmed,
Reviewed-truth-backed); what changed in environmental conditions (Inferred,
Place-relative, non-causal); and that MockingBird states both side by side
without ever claiming one caused the other -- the exact product goal this
milestone's brief stated. (One-off demonstration script, not committed as a
permanent tool -- the same result is exercised as durable, checked-in
coverage by `tests/test_place_story_repository.py::test_comparison_insight_gains_environmental_caveat_when_meaningfully_different`
and `tests/test_place_feature.py::test_feature_environmental_comparison_notably_cooler_after`.)

## Remaining opportunities explicitly NOT promoted

Per the brief's own scope guard, none of the following were implemented,
and none should be inferred as newly authorized by this milestone's
closure of the weather-caveat gap specifically:

- deeper ERA5/Open-Meteo archive backfill;
- wind or cloud-cover statistical associations;
- year-over-year seasonality;
- ranked Feature comparison;
- multi-camera Feature linking;
- Place Story period summaries as a general feature (the `"period_summary"`
  kind stays reserved, unused);
- a dedicated taxon/Feature Story page;
- representative Story imagery;
- a new Explore page;
- new weather providers;
- forecast alerts;
- ML-based ecological explanation;
- the pre-existing, separately-disclosed asymmetry between
  `comparison_insight_event`'s own "(an early signal, not yet a firm
  comparison)" qualifier for `early_signal` maturity and
  `featureAssociationSentence`'s frontend copy, which renders identical
  wording for `early_signal` and `comparable` today -- found during this
  milestone's own frontend archaeology, real, pre-existing, and
  independent of environmental-context composition; recorded here as fact
  only, not fixed (out of this milestone's bounded scope);
- the pre-existing third near-duplicate temperature-baseline query block
  (`_recent_temperature_band`, Visit/Today single-instant banding) --
  disclosed above, deliberately not consolidated (different, legitimate
  bucketing convention; no correctness defect).

## Feature-freeze impact

This milestone is the one explicitly-authorized, bounded exception for
tonight only. It does not reopen any other lane, does not authorize a
second product-development milestone, and does not change the
`CURRENT PHASE` label. Immediately after this milestone, MockingBird
returns to `FEATURE FREEZE -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING`.

## Decision

**A** -- accept. Bounded, reuse-only composition; zero schema change; zero
new statistical primitive; zero new causal-language surface; every
correction-safety and Local-Only property proven directly, not assumed;
375+ passing tests covering both deliverables' full sparse-state matrix;
one real product-shaped end-to-end proof. No defect found in the pre-existing
code this milestone read closely, beyond the two disclosed, out-of-scope,
independently-recorded findings above (the `early_signal` copy asymmetry;
the third near-duplicate baseline query block) -- neither blocks acceptance,
neither was introduced by this milestone.
