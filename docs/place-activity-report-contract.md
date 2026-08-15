# Place Activity Report (Reporting Foundation v1)

`mockingbird.analytics.place_activity_report` is the deterministic,
read-only reporting foundation the future "Today in Your Yard" and history
dashboards build on: what wildlife appeared, how often it visited, when,
and where, for one reporting period. It is a pure computation layer, the
same shape as the existing `mockingbird.analytics.zone_insights` --
`ProductRepository.zone_insights` is the precedent for how a future
repository-side adapter is expected to feed it real data.

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

This precedence is not re-derived here: a future adapter is expected to
build `VisitFact` from `ProductRepository._stream_visit_summary_from_models`
/ `_visit_review_outcome` output, the same canonical per-Visit resolver
`zone_insights` already reuses. This module's own `_classify` only ever
*sorts* an already-resolved fact into a report bucket.

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

## Integration (the one remaining step)

This milestone deliberately stops at the pure computation layer plus its
typed result -- no API route, no repository method, no schema/migration
change (see the milestone's explicit freeze list). The one integration
step for a future task: a `ProductRepository` method that

1. fetches `StreamVisitSummary` rows the same way `zone_insights()`
   already does (reusing `_stream_visit_summary_from_models`),
2. adapts each into a `VisitFact` (`confirmed_taxon`/`provisional_taxon`
   from a `_taxonomy_label_model_for_input` lookup on `reviewed_label`/
   `suggested_label`),
3. optionally fetches `MonitoringExposureIntervalModel` rows per in-scope
   Stream and calls `compute_coverage_summary`, and
4. calls `compute_place_activity_report` and returns the typed result
   (via a new Pydantic response schema, the same pairing `ZoneInsightsSummary`
   already provides for `zone_insights`).

No new service is warranted for this: it is a natural new method on the
existing `ProductRepository`, exactly like `zone_insights` and
`dashboard_summary` already are.
