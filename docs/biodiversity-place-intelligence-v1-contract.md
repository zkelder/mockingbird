# Biodiversity & Place Intelligence v1

The first vertical slice of [product-doctrine.md](product-doctrine.md)'s
"Place Intelligence" section combining the accepted wildlife system with
[Habitat & Phenology Foundation v1](habitat-phenology-foundation-v1-contract.md)
and [Environmental Context Foundation v1](environmental-context-foundation-v1-contract.md)
-- named as the intended consumer by both of those contracts' own
"Explicitly deferred" sections ("wildlife-activity correlation... once this
foundation has real history behind it"). It answers: what taxa have
actually been observed at this Place, which are new/recurring/recent, and
what habitat/environmental context accompanied them -- without becoming a
second analytics path, a prediction system, or a diversity-index calculator.

This is a synthesis milestone, not a new-computation milestone. Every fact
below is composed from already-accepted primitives:
[historical-baseline-maturity-contract.md](historical-baseline-maturity-contract.md)
(`mockingbird.analytics.historical_baseline`, the source of all-time Place
facts and per-taxon new/first_record/regular/seen_before status),
[canonical-new-regular-species-contract.md](canonical-new-regular-species-contract.md)
(the single reconciled definition every surface must share), habitat/
phenology's `classify_phenology_status`, and environmental context's
`get_visit_environmental_context`/`get_place_environmental_context_today`.
No new truth-precedence rule, no new species-classification logic, and no
new `information_class` value are introduced anywhere in this milestone.

## What already existed, reused here (not re-derived)

- `ProductRepository._historical_place_baseline_and_species_statuses`
  already computes, on every call, a genuinely **all-time** `Historical
  PlaceBaseline` (`distinct_taxa_count`/`earliest_authoritative_record_at`/
  `latest_authoritative_record_at`, unbounded `GROUP BY reviewed_label`
  query) alongside a 366-day-windowed `dict[str, SpeciesHistoricalStatus]`
  per confirmed taxon (`new`/`first_record`/`regular`/`seen_before`,
  first/last-confirmed, distinct usable days, total count). Every existing
  caller (Today, Bird Log overview, Bird Log history) narrows this to a
  report period, a single day, or a single label. **Nobody exposes the
  full, Place-wide result.** This milestone's Place Biodiversity Summary is
  that missing, thin composition layer -- the same call, Bird Log's own
  "live view, now-anchored" convention, unfiltered.
- `ProductRepository.list_likely_species_overview` already computes
  currently-provisional (needs-review) taxa, grouped, bounded. Reused
  verbatim for the Summary's `provisional_taxa` -- no second provisional
  query.
- `ProductRepository.get_place_habitat_context` /
  `get_place_environmental_context_today` already compute the Place's
  current habitat/phenology/daylight snapshot. Reused verbatim, embedded
  directly in the Summary response so the three foundations appear
  together in one read -- zero new environmental/habitat computation.
- `habitat.phenology.classify_phenology_status(start, end, *, today: date)`
  was already generic despite its parameter's name -- it works unmodified
  against any historical reference date. Only the plumbing above it
  (`list_place_phenology_observations`) hardcoded "now"; extended below.
- `get_visit_environmental_context(visit_id)` already resolves day/night
  context for an arbitrary Visit. Reused verbatim for taxon history --
  zero changes to Environmental Context Foundation's own code.

## 1. Truth contract: authoritative vs. provisional

Unchanged from `historical_baseline`'s own contract, restated because it is
this milestone's central invariant: only an authority-eligible `ReviewLabel`
(non-superseded, `review_status == "reviewed"`, resolved to a wildlife
taxon via `is_wildlife_category`'s denylist) can appear in `distinct_taxa_
count`, `distinct_species_count`, `taxa`, `new_taxa`, `regular_taxa`, or
`recently_observed_taxa`. A `SpeciesSuggestion` alone never contributes to
any of those fields, at any confidence. Provisional taxa surface **only**
in the separate `provisional_taxa` list (reusing `list_likely_species_
overview`'s existing needs-review grouping), which is structurally
incapable of being summed into the authoritative counts because it is
sourced from a disjoint query with no shared aggregate. A later correction
(`revise_visit_review`) is authoritative going forward through the same
mechanism `historical_baseline` already relies on -- no new bookkeeping,
no cache to invalidate (see "Caching," below).

## 2. Place Biodiversity Summary

New pure module `mockingbird.analytics.place_biodiversity_summary`
(`compute_place_biodiversity_summary`), new repository method
`ProductRepository.place_biodiversity_summary`, new route `GET /api/place/
biodiversity-summary` -> `PlaceBiodiversitySummaryResponse`.

Repository call sequence (mirrors `wildlife_journal_overview`'s exact
session/anchoring convention -- a live view, not a fixed report period):
non-archived Stream ids -> `_historical_place_baseline_and_species_
statuses(window_end_at=now, period_start_at=today's local midnight,
period_end_at=now)` -> `list_likely_species_overview()` -> `get_place_
habitat_context()` -> `get_place_environmental_context_today()` ->
`compute_place_biodiversity_summary(...)`. One extra small, already-
existing query per foundation; nothing new is queried.

Response fields:

- `generated_at` -- when this read was produced (this is a live view;
  re-requesting later can honestly change the answer, unlike a fixed-
  period report).
- `historical_baseline` -- the existing `PlaceActivityReportHistoricalBaseline`
  shape, reused verbatim (same Pydantic class Today's report already
  returns). Carries `maturity`/`usable_day_count`/`total_monitored_seconds`
  -- this **is** the effort/coverage context (see "Effort/coverage," below)
  -- plus the all-time `distinct_taxa_count`/earliest/latest.
- `distinct_species_count` -- the subset of `distinct_taxa_count` where
  `is_species=True` (mirrors `PlaceActivityReportResponse`'s own pairing;
  a confirmed non-species kind-level taxon, e.g. "squirrel" today, counts
  toward `distinct_taxa_count` but not this narrower figure).
- `taxa` -- every all-time-confirmed taxon's full `SpeciesHistoricalStatus`
  (nested as the existing `PlaceActivityReportTaxonHistoricalStatus` plus
  taxon identity), sorted most-recently-confirmed first. Unbounded --
  bounded only by distinct confirmed-label count, "small, in practice a
  few dozen at most" per `historical-baseline-maturity-contract.md`, the
  same reasoning that lets its own all-time lookup skip pagination.
- `new_taxa` / `regular_taxa` / `recently_observed_taxa` -- convenience
  subsets of `taxa` (see "New/Regular/Recent semantics," below). Not
  mutually exclusive; three independent lenses on the same list.
- `provisional_taxa` -- `DashboardTodaySpecies` entries (the exact type
  Bird Log's own "Likely sightings" panel already renders), reused as-is,
  bounded to 20 (matching `list_likely_species_overview`'s own default).
- `habitat_context: PlaceHabitatContext`, `environmental_context:
  PlaceEnvironmentalContext` -- the Place's current snapshot, embedded
  unmodified. Never blended into `taxa`; presented alongside.
- `warnings` -- calm, honest strings when `historical_baseline.total_
  monitored_seconds is None` (no monitoring history at all) or `maturity
  != "established"` (see "Product states," below). Empty list otherwise.

Nothing here is persisted. Like every sibling module, this is computed
fresh per request from already-durable facts (see "Caching," below).

## 3. Effort / coverage

Deliberately reuses `HistoricalPlaceBaseline`'s own 366-day-windowed
`usable_day_count`/`maturity`/`total_monitored_seconds` as the Summary's
entire effort accounting -- the same primitive every existing new/regular
claim already depends on for its own trustworthiness gate. This milestone
does **not** introduce a second, unbounded lifetime coverage scan (a
working pattern exists for that -- `export_research_dataset`'s `datetime(1970,
1, 1)` epoch fallback into `_place_activity_coverage_summary` -- but
adopting it here would mean maintaining two different "how much monitoring
supports this claim" numbers for the same product surface, which is
exactly the second-system risk this contract avoids). "12 species observed"
is always shown next to `historical_baseline.maturity`; when maturity is
`insufficient`, an explicit warning accompanies the count rather than
letting it stand unqualified.

## 4. New / Regular / Recent semantics

**New / first_record / regular / seen_before**: unchanged, reused verbatim
from `compute_species_historical_statuses` via the canonical call above --
see `historical-baseline-maturity-contract.md` and `canonical-new-regular-
species-contract.md` for the full definitions. This milestone adds no new
status value and no new eligibility rule. Because the Summary uses the
exact same "now"-anchored call Bird Log's overview already uses (same
`window_end_at`, same `period_start_at=today's local midnight`), a given
taxon's status here is always identical to what Bird Log shows for it at
the same moment -- no fourth place these can silently disagree.

**Recently observed** (new label, this milestone only): a taxon is
"recently observed" when `last_confirmed_at` falls within the trailing
`RECENTLY_OBSERVED_WINDOW_DAYS` (14) days of `generated_at`. Deliberately
**not** coverage-gated (unlike "regular"/"new") -- a single genuine
reviewed observation is a real fact regardless of how much monitoring
happened that specific day, and gating it would risk hiding an honest
recent sighting behind an unrelated coverage shortfall. 14 is not invented
for this milestone: it is the same window already used by Bird Log's
`recent_activity` sparkline, `_dashboard_today_summary`'s legacy regulars
lookback, and `place_change_summary.RECENT_WINDOW_FRESHNESS_CAP_DAYS` --
reused, not a fourth number.

**Deliberately not built**: a "recently absent" or "missing" category.
Per this milestone's own instruction and product-doctrine.md, "not
observed recently" must never read as "absent from the property" --
so absence from `recently_observed_taxa` is silent (the taxon simply
doesn't appear in that one list) rather than surfaced as its own claim.
A taxon can be `regular_taxa` and absent from `recently_observed_taxa`
simultaneously; the product never states this as "gone."

## 5. Taxon Place History (habitat/environment connection)

Bird Log's existing per-label history (`WildlifeJournalHistoryResponse`)
already carries first/latest/count/recent-encounters/temporal-pattern --
Phase 3B's only genuine gap. Rather than a second, parallel "taxon place
history" endpoint (which would duplicate an already-correct, already-
tested surface), this milestone adds one new optional field:
`place_context: TaxonPlaceContext | None`, populated for the taxon's
single most recent reviewed observation only (`observed_at`, `environmental_
context: SolarContext` -- never `None`, mirroring `SolarContext`'s own
"always-present object, honest absence via `available`" convention --
`phenology_context: list[PlacePhenologyObservation]` filtered to
`status == "current"` as of that observation's local date).

Bounded and cheap by construction: one extra `get_visit_environmental_
context` call and one extra `list_place_phenology_observations(as_of=...)`
call per taxon-history request (a single-taxon view, never a list) --
O(1), not O(gallery size). `list_place_phenology_observations` gained one
new optional `as_of: date | None = None` parameter (default preserves
existing behavior for both pre-existing call sites unchanged); `classify_
phenology_status` itself needed no change, since its `today` parameter was
already just a reference date.

Habitat facts (setting/vegetation/feature tags) are deliberately **not**
repeated per taxon -- they are non-temporal/always-current by design (see
habitat-phenology-foundation-v1-contract.md), so there is nothing
differentiated to say about them per observation; they remain Place-wide,
shown once, exactly where they already are (Dashboard card, Place Report
page's full history section).

Today's report (`PlaceActivityReportTaxonEntry`) does **not** gain this
field -- it stays calm/summary; Bird Log keeps ownership of per-taxon
depth, matching the existing "Bird Log owns the deeper, always-available
detail" precedent from `historical-baseline-maturity-contract.md`.

## 6. Habitat + Environment connection: language discipline

Every surface touched by this milestone states association, never cause.
`TaxonPlaceContext` and the Summary's embedded `habitat_context`/
`environmental_context` are labeled and phrased as "recorded near
sunrise," "recorded while [phenomenon] was current" -- never "caused,"
never a suitability or likelihood claim. No correlation ranking, no
statistics over multiple observations' contexts, no prediction. This
mirrors `product-doctrine.md`'s "External ecological context" and the
roadmap's explicit relationship-language mandate ("associated with,"
"coincided with," never causal absent causal evidence).

## 7. Information class

No new persisted fact, therefore no new `information_class` value at any
layer. `TaxonPlaceContext.environmental_context.information_class` is the
existing `"inferred"` (unchanged `SolarContext`); phenology/habitat facts
keep their existing `"reviewed"`. The closed Measured/Inferred/Reviewed
triad is untouched.

## 8. Research / export safety

`mockingbird.research.eligibility.evaluate_research_export_eligibility`
and `mockingbird.research.conservation_report` are untouched by this
milestone -- neither reads from nor is read by the new module. No new
export field was added: `conservation_report.py`'s own docstring already
disclaims a "biodiversity index," and the roadmap's explicit "avoid raw
species-count gamification where monitoring effort differs" caution argues
against exposing a bare, effort-blind count anywhere export-adjacent. If a
future milestone wants Place Biodiversity Summary facts in an export, that
is a separate, deliberately-scoped decision, not a side effect of this one.

## 9. Product states

- **Brand-new install / monitoring disabled** -- empty non-archived-Stream
  set: `_historical_place_baseline_and_species_statuses` already tolerates
  this (proven by its own existing "must run whenever Streams exist even
  if `taxa` is empty" handling); `taxa=[]`, `historical_baseline.maturity
  == "insufficient"`, `total_monitored_seconds is None` -> the "no
  monitoring history" warning fires. The Summary renders a calm "nothing
  recorded yet" state, never a bare "0."
- **Zero reviewed / only provisional observations** -- `taxa=[]` while
  `provisional_taxa` may be non-empty; the frontend keeps these visibly
  separate (an "awaiting review" sub-section, same visual treatment Bird
  Log's "Likely sightings" panel already uses), never summed into the
  headline count.
- **Sparse effort** -- `maturity in {insufficient, developing}`; `new`/
  `first_record`/`regular` already degrade correctly (inherited, unchanged);
  the Summary's own warning explains why "regular" claims are still thin.
- **Missing habitat/environmental data** -- both embedded objects already
  return an honest `available=False`/empty-lists shape rather than erroring
  or omitting the field; the frontend card treats each independently, same
  as `HabitatPhenologyCard`/`EnvironmentalContextCard` already do.
- **Old history, nothing recent** -- `taxa` non-empty, `recently_observed_
  taxa` empty: copy reads "Nothing recorded in the last two weeks -- N
  species known here overall," never a misleading blank/zero screen.

## 10. Caching

None, deliberately, matching the established convention (`historical_
baseline`/`place_activity_report`/`daily_digest`/`wildlife_journal_*` all
compute fresh per request; the one cache in this codebase's reporting
family, `_storage_summary_cache`, is unrelated disk-accounting). A human
correction is immediately visible on the next read with zero invalidation
code -- see the mandatory correction test in "Validation."

## Schema

No migration. Every fact derives from already-durable tables (`VisitModel`/
`EventModel`/`TaxonomyLabelModel`/`MonitoringExposureIntervalModel`/
`PlaceHabitatFactModel`/`PlacePhenologyObservationModel`/`EnvironmentalContextRecordModel`,
all pre-existing). Schema stays v52.

## Explicit non-goals

Diversity indices (Shannon/Simpson or any other), population/abundance/
occupancy estimates, habitat suitability scoring, ecological health
scoring, species interaction graphs, seasonality/year-over-year comparison,
correlation ranking between habitat/environment and activity, prediction
of any kind, a `PlaceModel` entity (none exists; "Place" remains the
entire local install, matching every prior accepted foundation), and any
change to the research/export eligibility boundary.

## Known limitations

- `recently_observed_taxa`'s 14-day window and the reused 366-day
  regularity window are both fixed constants, not user-configurable, per
  precedent throughout this codebase's Place Intelligence layer.
- `provisional_taxa` is bounded to 20 and is a genuinely live/current-state
  concept (a Visit stops being provisional the moment it is reviewed) --
  there is no persisted "all provisional taxa ever" fact to query, nor
  should there be one.
- `TaxonPlaceContext` is anchored to the single latest reviewed observation
  only; it does not summarize habitat/environmental context across a
  taxon's whole history (that would edge toward the correlation-ranking
  non-goal above).
- The Summary's `taxa` list has no explicit cap; a Place with an
  extraordinarily large distinct-taxon history (not realistic for a home
  install at this product's current scale) would return a proportionally
  larger response. Matches `historical_baseline`'s own existing, already-
  accepted reasoning for its identical unbounded all-time query.
