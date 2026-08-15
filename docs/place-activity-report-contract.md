# Place Activity Report (Reporting Foundation v1)

`mockingbird.analytics.place_activity_report` is the deterministic,
read-only reporting foundation the future "Today in Your Yard" and history
dashboards build on: what wildlife appeared, how often it visited, when,
and where, for one reporting period. It is a pure computation layer, the
same shape as the existing `mockingbird.analytics.zone_insights` --
`ProductRepository.zone_insights` was the precedent for the repository-side
adapter that now feeds it real data, `ProductRepository.
place_activity_report` (see "Integration," below).

This is the **reporting foundation**, not "Place Intelligence" itself:
[product-doctrine.md](product-doctrine.md) reserves that name for the
future Phase 5 layer (baselines, regular-vs-new visitors, seasonality,
year-over-year comparison). This module deliberately produces only the raw
deterministic facts that future layer will need -- no thresholds, no
"higher than normal" language, no baselines. See "Baselines / trends"
below.

No LLM is used or permitted in this computation path
([product-doctrine.md](product-doctrine.md)'s truth boundary already
forbids language-model output from becoming or shading reviewed truth;
this module extends the same discipline to reporting).

## Report truth precedence

Every Visit resolves to exactly one state before it is counted, matching
[review-decision-provenance-contract.md](review-decision-provenance-contract.md):

1. **Confirmed** -- an authority-eligible `ReviewLabel` exists. Always wins,
   even when a (now-stale) automatic species suggestion also exists on the
   same Visit.
2. **Provisional** -- no reviewed truth yet, but an automatic species-level
   `SpeciesSuggestion` does. Usable for a report fact, but always kept
   separate from confirmed counts (`confirmed_visit_count` /
   `provisional_visit_count` on each `TaxonReportEntry`), never blended
   into one number the way a normal dashboard might.
3. **Unresolved** -- neither exists, or a reviewed label did not resolve to
   any known taxonomy row. Counted (`unresolved_visit_count`), never
   guessed into a species.

This precedence is not re-derived here: the repository-side adapter builds
`VisitFact` from `ProductRepository._stream_visit_summary_from_models`
output (`mockingbird.analytics.place_activity_report_adapter.
visit_fact_from_stream_visit_summary`), the same canonical per-Visit
resolver `zone_insights` already reuses. This module's own `_classify` only
ever *sorts* an already-resolved fact into a report bucket.

## Wildlife classification boundary

MockingBird is bird-first but wildlife-native (product-doctrine.md). This
report's wildlife filter is deliberately broader than the bird-only scope
`zone-feeder-insights-metrics.md` documents for Zone Insights, and it is
defined the same way everywhere it is needed by one centralized, reusable
predicate: `mockingbird.wildlife_taxonomy.is_wildlife_category`. That
predicate is a **denylist**, not an allowlist: `"pet"`, `"person"`,
`"vehicle"`, `"object"`, `"false_positive"`, and `"unknown"`
(`api.schemas.LabelCategory`) are the specific, currently-known categories
it excludes; every other category -- including one that does not exist in
today's vocabulary yet -- counts as wildlife by default. This deliberately
does **not** hardcode wildlife as `category in {"bird", "mammal"}`: a
future taxonomy category (a reptile, amphibian, bat, or visible
invertebrate) is recognized as wildlife automatically the moment it is
added to `LabelCategory`, without a second reporting rewrite. Excluding
`"pet"` reuses an existing product distinction rather than inventing one --
the seed taxonomy (`api/demo_data.py`) already files "cat"/"dog" under the
separate `"pet"` category rather than `"mammal"`. See
`mockingbird.wildlife_taxonomy`'s own module docstring for the full
rationale, including why a hypothetical future *non*-wildlife category
would need one small addition there (not here) at the same review moment
it is introduced.

This is safe specifically because `TaxonomyLabel.category` is already a
closed `LabelCategory` enum -- a value can only reach this predicate
through a deliberate, reviewed code change adding a new enum member, never
by guessing a category from a free-text label or species name.

A confirmed `"unknown_bird"`/`"unknown_animal"` correction (category
`"unknown"`) is a human explicitly confirming an animal was present while
abstaining on species/kind. It counts toward confirmed wildlife activity
(`confirmed_wildlife_visit_count`, `confirmed_species_unresolved_visit_count`)
but is never fabricated into a taxon entry in `taxa` -- `_classify` checks
for this category explicitly, before consulting `is_wildlife_category`, so
it is never conflated with an ordinary wildlife-taxon Visit.

## Unknown / unresolved

`unresolved_visit_count` covers only not-yet-reviewed Visits with no usable
species-level suggestion. It is reported as an honest, separate count --
never centered in the report, never folded into `wildlife_visit_count`,
and never guessed at. `confirmed_species_unresolved_visit_count` is the
distinct, already-reviewed counterpart (see above). Both exist so a future
UI can decide how quietly to surface them, per this milestone's brief.

## Zone and hour aggregation

Zone aggregation groups by `zone_id` (a real, globally unique key), not by
`zone_name` -- two different Streams each having a same-named Zone are
never merged. A Visit with no Zone lands in a `"No Zone"` bucket, matching
the existing Dashboard Today convention exactly; that bucket can never be
reported as `busiest_zone`, since it is the absence of a Zone rather than
one the user drew.

Hour-of-day aggregation always returns 24 entries (0-23), even for hours
with no activity, and buckets by the caller-supplied local timezone -- this
module never reads the host clock's local timezone itself, to stay
deterministic.

## Local time and DST correctness

Each Visit's local hour is computed independently, inside the per-Visit
loop (`visit.activity_started_at.astimezone(local_timezone)` -- not once
for the whole batch), so `compute_place_activity_report` is DST-correct
for *any* period as long as it is given a real variable-offset `tzinfo`.
`ProductRepository.place_activity_report` supplies exactly that:
`mockingbird.time_utils.resolve_host_local_timezone` resolves this
single-site install's actual IANA timezone (for example
`ZoneInfo("America/New_York")`), tried in order from the `TZ` environment
variable, then the `/etc/localtime` symlink target (the standard
Linux/macOS convention) -- so a report period that itself spans a real DST
transition places each Visit in the local hour that genuinely applied to
its own timestamp, not one offset borrowed from whenever the report was
generated. MockingBird still has no per-Place timezone *setting* (nothing
here changes that); "local" is inferred from the host environment, exactly
as every other local-time analytics surface already does, just resolved
as a real zone instead of a fixed offset now.

When no IANA zone can be discovered on the host at all -- a plain Windows
install with no `tzdata` package and no way to name its zone in IANA terms
without one -- `resolve_host_local_timezone` falls back to a fixed-offset
snapshot of the current local UTC offset: this product's original
behavior, correct only for the moment it was resolved, not per-day across
a transition. This is a disclosed, honest degradation for that specific
host situation, never a crash and never an invented number; see "Remaining
limitations" below.

`ProductRepository.place_activity_report` also accepts a test-only
`local_timezone` keyword (mirroring its existing `now` test-only
override) so DST-transition tests stay fully deterministic regardless of
the host machine's own configured zone -- production callers never pass
it. See tests/test_place_activity_report.py's "DST-correct local-time
bucketing" section (pure computation) and
tests/test_place_activity_report_repository.py's spring-forward/fall-back/
period-spanning tests (real read path) for the ordinary-period,
spring-forward, fall-back, repeated-local-hour, and period-spanning-
transition cases this was proven against.

## Monitoring coverage

`compute_coverage_summary` is a real, tested computation, not a stub: it
reuses `mockingbird.analytics.zone_insights`'s existing interval math
(`merge_intervals`, `interval_seconds`, `subtract_intervals`) over the same
underlying durable fact `zone_insights` already relies on --
`MonitoringExposureIntervalModel`, a bounded healthy-frame interval history
that begins only once a Stream receives its first fresh monitoring frame,
and is never inferred from armed policy, runtime checkpoints, or the
calendar (see "Monitoring exposure and confidence" in
[zone-feeder-insights-metrics.md](zone-feeder-insights-metrics.md)).

`monitored_seconds`/`coverage_ratio` are `None` when no durable exposure
history exists at all for the reported scope -- an honest "not yet
computable" signal, never a fabricated number. Gaps are exposed as raw
sub-intervals (`gaps`, bounded with a `gaps_truncated` flag), not as a
judgment call about which gap is "material" -- this module does not invent
a materiality threshold; the future UI decides that.

### Place-wide coverage policy (partial-stream-aware, not all-or-nothing)

`ProductRepository.zone_insights`'s own aggregate-exposure construction
*sums* independent per-Stream camera-hours, so it cannot honestly
represent a Stream with zero durable history any way other than
all-or-nothing (`history_available_from=None` the moment *any* in-scope
Stream lacks history at all) -- that policy is unchanged and still
correct for Zone Insights' own additive shape.

`ProductRepository.place_activity_report`'s coverage is a different
shape: a *union* over raw intervals -- "was this Place being watched by
any camera at this moment" -- not a sum. A Stream with no durable exposure
history at all (for example one just added mid-period that has not yet
recorded its first healthy frame) contributes nothing to that union
either way, so excluding it from the figure loses no honest information.
Consequently this report's coverage-policy audit (Place Intelligence
Backend Hardening v1) concluded the inherited all-or-nothing policy was
**too conservative** for a place-wide, potentially year-scale report: it
would let one newly-added, not-yet-reporting Stream retroactively blank
out years of otherwise-trustworthy coverage from every *other* Stream.
The policy is now:

- **Withheld** (`monitored_seconds`/`coverage_ratio`/`history_available_from`
  all `None`) only when **no** in-scope Stream has ever recorded any
  durable exposure history at all -- the genuinely honest "not yet
  computable" case, unchanged from before.
- **Reported**, using only the Streams that *do* have durable history,
  when at least one in-scope Stream has some -- even if another does not.
  `history_available_from` is the earliest start among Streams that have
  history; a Stream with none is simply excluded from that computation,
  not averaged in as if it had zero coverage.
- **Disclosed, not hidden**: when some but not all in-scope Streams lack
  durable history, the response's `warnings` includes an explicit note
  ("One or more Streams have no durable monitoring exposure recorded
  yet...") so a caller can tell the figure does not reflect literally
  every configured Stream, without a fabricated number or a full
  withdrawal.

No schema change was needed for this: `CoverageSummary`/
`PlaceActivityReportCoverage`'s shape is unchanged; only
`ProductRepository._place_activity_coverage_summary`'s gating condition
and the accompanying `warnings` text changed. See
tests/test_place_activity_report_repository.py's
`test_coverage_reflects_established_streams_when_one_stream_has_no_history`,
`test_coverage_fully_withheld_only_when_no_in_scope_stream_has_any_history`,
and `test_coverage_survives_a_new_stream_added_midway_through_a_long_period`.

## Baselines / trends

Not implemented here, deliberately. "Higher than normal," "regular
visitor," seasonality, year-over-year comparison, and ecological-absence
claims all require sufficient history and explicit baseline-readiness
semantics this milestone does not define (see "Place Intelligence" in
[product-doctrine.md](product-doctrine.md) and Phase 5 in
[roadmap.md](roadmap.md)). This module produces exactly the raw facts --
Visit counts, first/last timestamps, per-taxon backing -- that future
baseline logic will need, and no arbitrary thresholds.

## Audio and external context

Not implemented; not referenced. No placeholder fields were added for
audio, weather, eBird, iNaturalist, or any other external source -- see
"External ecological context" in
[product-doctrine.md](product-doctrine.md). Nothing in this module's shape
currently prevents adding them later as their own extensions.

## Integration (complete)

Place Intelligence Repository/API Integration v1 wired this pure
computation layer to durable product state. No schema/migration change was
needed: every fact the report uses (`VisitModel`/`EventModel`/
`ReviewLabelModel`/`SpeciesSuggestionModel`/`TaxonomyLabelModel`/
`MonitoringExposureIntervalModel`) already existed and was already durable.

`ProductRepository.place_activity_report` (`product_repository.py`, next to
`zone_insights`/`wildlife_insights`) is the one new repository method --
exactly like `zone_insights` and `dashboard_summary`, no separate service
was warranted. It:

1. resolves an explicit, caller-supplied `[start_at, end_at)` UTC period
   (`PlaceActivityReportRequest`, validated the same way
   `ZoneInsightsRequest` is: `end_at` must follow `start_at`, span capped at
   366 days) and the Place-local timezone via
   `mockingbird.time_utils.resolve_host_local_timezone` -- a real IANA
   `zoneinfo.ZoneInfo` when the host environment names one (`TZ`/
   `/etc/localtime`), falling back to a fixed-offset snapshot only when it
   cannot -- rather than a caller-supplied field, since MockingBird has no
   per-Place timezone setting today. See "Local time and DST correctness"
   above.
2. fetches every non-archived Stream's in-scope Visits and adapts each into
   a `StreamVisitSummary` via `_stream_visit_summary_from_models`, the same
   canonical per-Visit resolver `zone_insights`/`wildlife_insights` already
   reuse -- truth precedence can never diverge from either. Optionally
   accepts a preloaded `taxonomy_index` (see point 3) as a purely additive
   performance parameter; its resolution logic itself is otherwise
   unchanged.
3. resolves `confirmed_taxon`/`provisional_taxon` from `reviewed_label`/
   `suggested_label` through a report-scoped taxonomy index
   (`_taxonomy_label_index`) that preloads the whole (small, bounded)
   taxonomy table once per report call instead of once per Visit, and
   passes that same index into `_stream_visit_summary_from_models` (which
   forwards it to `_visit_review_outcome`/`_taxonomy_label_model_for_input`)
   so the canonical resolver's own internal taxonomy lookup reuses it too,
   instead of issuing a second per-Visit full-table scan on top of it. See
   "Taxonomy query behavior (hardened)" below.
4. resolves Place-wide monitoring coverage (`_place_activity_coverage_
   summary`) from durable `MonitoringExposureIntervalModel` history across
   every in-scope Stream in at most two queries total (a grouped `MIN` plus
   a ranged interval fetch) rather than the O(Streams) round trips
   `_zone_insights_exposure` costs by running once per Stream. See
   "Place-wide coverage policy" above for the hardened, partial-stream-
   aware policy this now applies (no longer `zone_insights`' all-or-nothing
   one, for the reasons documented there).
5. calls `compute_place_activity_report`/`compute_coverage_summary` and
   adapts the typed result into `PlaceActivityReportResponse` through a
   new, deliberately small pure adapter module,
   `mockingbird.analytics.place_activity_report_adapter` -- kept out of the
   already-very-large `product_repository.py`/`api/schemas.py` pairing so
   this translation stays independently readable, mirroring the `zone_
   insights`/`ZoneInsightsSummary` pairing's shape without adding to either
   file's bulk.

`POST /api/analytics/place-activity-report` (`api/main.py`, next to
`zone-insights`/`wildlife-insights`) is the one new read-only route,
returning `PlaceActivityReportResponse`. It performs no independent report
math and creates no review/Observation/product state -- see
tests/test_place_activity_report_repository.py's read-only and API
serialization coverage.

## Taxonomy query behavior (hardened)

Before Place Intelligence Backend Hardening v1, this report's own
`confirmed_taxon`/`provisional_taxon` resolution avoided adding a *second*
per-Visit `taxonomy_labels` query on top of one the canonical resolver
already issued (`_stream_visit_summary_from_models` -> `_visit_review_
outcome` -> `_taxonomy_label_model_for_input`, one full-table scan per
reviewed Visit with a real species label) -- so the report still cost
`O(Visits) + 1` taxonomy queries total, the same shape `zone_insights`/
`wildlife_insights` already paid (`zone_insights` actually cost `2 x
O(Visits)`, since it also issued its own separate direct lookup for the
same field).

`_taxonomy_label_model_for_input` now accepts an optional `taxonomy_index`
parameter (a `dict[str, TaxonomyLabelModel]`, the same preloaded index
`_taxonomy_label_index` already built): when supplied, it does an O(1)
dict lookup instead of a fresh full-table scan; when omitted (the default,
unchanged for every other one of its many existing callers, several of
which back truth-writing paths), it behaves exactly as before.
`_visit_review_outcome` and `_stream_visit_summary_from_models` both
accept and forward the same optional parameter. `place_activity_report`
and `zone_insights` (the same "if the same safe improvement naturally
applies" case this milestone identified) both now build one
`_taxonomy_label_index` per call and pass it through, so their entire
taxonomy resolution -- both the report/summary's own and the canonical
resolver's internal one -- costs exactly **one** `taxonomy_labels` query
per call, regardless of Visit count. `wildlife_insights` and every other
caller of these three methods are unaffected (they simply do not pass the
new parameter). Measured directly (`tests/test_place_activity_report_
repository.py::test_taxonomy_resolution_costs_exactly_one_query_
regardless_of_visit_count`, `tests/test_zone_insights.py::test_taxonomy_
resolution_costs_exactly_one_query_regardless_of_visit_count`): both
`place_activity_report` and `zone_insights` cost exactly 1 `taxonomy_labels`
query at 3, 8, 20, 30, and 50 reviewed Visits alike -- before this
hardening, `place_activity_report` scaled as `N + 1` and `zone_insights`
as `2N`.

## Long-period performance

Report generation issues a small, fixed number of Place/coverage-level
queries (Stream id list, taxonomy index, monitoring-exposure `MIN` +
ranged fetch) plus one Visit/Event range query that returns every in-scope
row in a single round trip -- none of that grows with Visit count beyond
that one already-batched query. The remaining per-Visit cost is entirely
inside `_stream_visit_summary_from_models` (motion evidence, evidence
frames/links, the latest SpeciesSuggestion, and the effective Zone -- each
a genuinely per-Visit fact, not a reporting-specific concern, and shared
by `zone_insights`/`wildlife_insights` too), measured at a **constant 5
SQL queries per Visit**, giving an exactly linear total query count of
`5N + 4` (confirmed empirically at N = 25, 150, and 1000 reviewed Visits
spread across a full year -- no deviation from that formula at any of the
three scales) and a wall-clock time that scales similarly (roughly
1-2ms/Visit on developer hardware against real SQLite; about 1.2s for
1,000 Visits). This is bounded, predictable, linear behavior at
day/week/month/year scale -- no query explosion, no pathological pure-
computation cost in `compute_place_activity_report` itself (a handful of
dict/list operations per Visit). See "Remaining limitations" below for
where this shape would eventually matter, and
`tests/test_place_activity_report_repository.py::test_report_generation_
query_shape_stays_bounded_at_a_materially_larger_cohort` for the
regression proof (asserts the per-Visit query cost at 6x the cohort size
does not exceed the smaller cohort's by more than a generous tolerance,
rather than a brittle exact count). No caches, materialized views,
background jobs, or aggregation tables were added -- current evidence does
not show they are needed yet.

## Remaining limitations

- **DST fallback on a host with no discoverable IANA zone.** On a host
  where `mockingbird.time_utils.resolve_host_local_timezone` cannot
  determine a real IANA zone (the `TZ` environment variable unset/invalid
  and no `/etc/localtime` symlink to resolve -- realistically a plain
  Windows install without the optional `tzdata` package, since Windows
  does not otherwise name its local zone in IANA terms), local-time
  bucketing degrades to this product's original fixed-offset-per-call
  behavior: correct for the report's generation moment, not necessarily
  for every Visit in a period that spans a real DST transition. This is a
  disclosed, non-crashing degradation on that specific host situation, not
  a silent wrong answer masquerading as precision -- see "Local time and
  DST correctness" above.
- **Per-Visit evidence/suggestion/zone queries remain `O(Visits)`.** This
  hardening milestone removed the *taxonomy* N+1 specifically (see
  "Taxonomy query behavior" above); the canonical `_stream_visit_summary_
  from_models` resolver's other per-Visit lookups (motion evidence,
  evidence frames, SpeciesSuggestion, Zone) are unchanged and still cost a
  small constant number of queries per Visit. Measured linear and fast at
  up to 1,000 Visits (see "Long-period performance"); a batching fix
  similar to the taxonomy one is the natural next step if a much larger
  real deployment's history ever shows this mattering in practice -- not
  attempted here, since `_stream_visit_summary_from_models` is shared by
  nearly every Visit-reading feature in the product and current evidence
  does not show it is needed yet.
- **No per-Place timezone setting.** "Local" is still inferred from the
  host environment, not a Place-level configuration field -- unchanged by
  this milestone, and not required by it (MockingBird remains a
  single-site product today).
