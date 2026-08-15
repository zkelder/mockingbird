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
`zone-feeder-insights-metrics.md` documents for Zone Insights: a category
of `"bird"` or `"mammal"` (`api.schemas.LabelCategory`) counts as wildlife;
`"pet"`, `"person"`, `"vehicle"`, and `"object"` do not. This reuses an
existing product distinction rather than inventing one -- the seed taxonomy
(`api/demo_data.py`) already files "cat"/"dog" under the separate `"pet"`
category rather than `"mammal"`. Any category this module does not
recognize (including a future one) falls through to non-wildlife rather
than being silently counted -- a conservative default, not a guess.

A confirmed `"unknown_bird"`/`"unknown_animal"` correction (category
`"unknown"`) is a human explicitly confirming an animal was present while
abstaining on species/kind. It counts toward confirmed wildlife activity
(`confirmed_wildlife_visit_count`, `confirmed_species_unresolved_visit_count`)
but is never fabricated into a taxon entry in `taxa`.

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

A caller combining several Streams into one Place-level figure must apply
the same all-or-nothing honesty policy `ProductRepository.zone_insights`'s
own aggregate-exposure construction already uses: pass
`history_available_from=None` when *any* in-scope Stream lacks durable
history, rather than silently averaging partial coverage with full
coverage.

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
   366 days) and the Place-local timezone the same way every other
   local-time analytics surface already does --
   `(now or datetime.now().astimezone()).astimezone()` -- rather than a
   caller-supplied field, since MockingBird has no per-Place timezone
   setting today. This is a fixed-offset snapshot resolved once per call
   from the generation moment, DST-correct *for that moment* but not
   per-day across a period that itself straddles a transition -- the same
   known characteristic every existing local-time surface already has; see
   `test_local_offset_resolves_correctly_for_the_generation_moment` in
   tests/test_place_activity_report_repository.py.
2. fetches every non-archived Stream's in-scope Visits and adapts each into
   a `StreamVisitSummary` via `_stream_visit_summary_from_models`, the same
   canonical per-Visit resolver `zone_insights`/`wildlife_insights` already
   reuse, unmodified -- truth precedence can never diverge from either.
3. resolves `confirmed_taxon`/`provisional_taxon` from `reviewed_label`/
   `suggested_label` through a report-scoped taxonomy index
   (`_taxonomy_label_index`) that preloads the whole (small, bounded)
   taxonomy table once per report call instead of once per Visit.
   `_taxonomy_label_model_for_input` itself is intentionally left
   unmodified -- it backs many truth-writing paths
   (`_normalize_label_from_session` alone underlies every review-correction
   creation path), so a reporting-only performance concern is not a reason
   to change its signature. This does not eliminate every `taxonomy_labels`
   query the report issues: `_stream_visit_summary_from_models`'s own
   `_visit_review_outcome` still costs one such query per reviewed Visit
   with a real species label, exactly like it already costs
   `zone_insights`/`wildlife_insights` in production today -- out of scope
   to change here (see `_taxonomy_label_index`'s docstring and
   `test_taxonomy_resolution_adds_no_second_per_visit_query`).
4. resolves Place-wide monitoring coverage (`_place_activity_coverage_
   summary`) from durable `MonitoringExposureIntervalModel` history across
   every in-scope Stream in at most two queries total (a grouped `MIN` plus
   a ranged interval fetch) rather than the O(Streams) round trips
   `_zone_insights_exposure` costs by running once per Stream, applying the
   same all-or-nothing honesty policy `zone_insights`' own aggregate-
   exposure construction uses.
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
