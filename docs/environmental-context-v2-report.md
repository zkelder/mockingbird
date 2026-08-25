# Environmental Context v2 -- Weather, Climate & Place Conditions Report

## 1. Identity

- **Starting HEAD:** `7a3bbfb` (verified exactly matching the milestone's
  expected starting state before any edit)
- **Ending implementation HEAD:** `751d061` -- "Environmental Context v2:
  Weather, Climate & Place Conditions" (all code, tests, the locked
  contract, and this report)
- **Final docs HEAD:** the following reconciliation commit -- "Reconcile
  release-execution-state.md: accept Environmental Context v2" (updates
  only [release-execution-state.md](release-execution-state.md); no
  further code/report changes)
- **Schema:** v53 -> **v54** (one additive column,
  `environmental_context_settings.weather_enabled`; see "Data model")
- **Commits:** 2 (implementation, then execution-state reconciliation --
  mirroring this repository's own established two-commit closure pattern)
- **Push state:** not pushed; explicit authorization required, unchanged
  from the standing repository policy

## 2. Archaeology (Phase 1)

Confirmed via direct reading of
[environmental-context-foundation-v1-contract.md](environmental-context-foundation-v1-contract.md),
the live `solar_context.py`/model/repository/schema/API/frontend code, and
two parallel `Explore` sweeps (code-surface map; coverage/effort-semantics
map) before writing any code:

- **No general weather/temperature provider existed anywhere** -- confirmed
  by the v1 contract's own history and re-confirmed by direct repo search.
  v1's only provider is `solar_local` (sunrise/sunset/day-night, zero
  network access).
- `EnvironmentalContextRecordModel` (schema 51) was **already shaped** to
  hold a future numeric provider's metrics (`value_numeric`/`unit`,
  `observed_at_end` for a future interval, `provider_key` as a flat
  string) -- its own docstring names "a future public weather/
  environmental API" as the anticipated next writer. This is why **no
  schema change was needed for that table.**
- `EnvironmentalContextSettingsModel` had no notion of "consented to an
  outbound network call" -- the one genuine schema gap (see "Data model").
- `mockingbird.analytics.conditional_association` (Place / Yard
  Intelligence v2) is a generic, already-accepted "presence-rate inside a
  date-set" primitive with its own minimum-sample gating and causal-safe
  vocabulary; `habitat_association.py` is the exact structural precedent
  for wrapping it around a new date-scoped condition source. Both the
  Place/Yard v2 contract and report explicitly named "weather association"
  as blocked only on a provider existing, with no bands/gating rules
  pre-specified.
- House outbound-network convention (`external_url_preview.py`,
  `onvif_client.py`): stdlib `urllib`, small bounded timeout, a
  dependency-injected requester `Protocol`, one attempt, no retry, degrade
  to a typed result on failure. `httpx` exists only as a `test`-extra
  dependency, never a production HTTP client.
- Structured-health precedent: `BioClipAdapterStatus`/`SolarContextStatus`
  -- frozen dataclass, closed `Literal` status vocabulary, a status
  function that never raises.
- `_daylight_bucket_by_visit_id` is the precedent for "resolve a bounded,
  absence-safe per-report fact without the report ever becoming a live
  network caller" -- the model this milestone's report-time weather-band
  resolution follows exactly (read-only over already-cached rows).

Full detail, including exact file:line citations for every claim above, is
recorded in
[environmental-context-v2-contract.md](environmental-context-v2-contract.md)
"Phase 1," locked before any implementation began.

## 3. Provider decision (Phase 3)

**Selected: Open-Meteo**, `https://api.open-meteo.com/v1/forecast`.

All claims below were verified this session via real `WebFetch`/`WebSearch`
calls against Open-Meteo's own terms/licence/docs pages **and** real,
unauthenticated HTTPS calls made from this sandbox -- not recalled from
training knowledge, per the milestone's "current authoritative
documentation" instruction.

**Terms** (<https://open-meteo.com/en/terms>, quoted): non-commercial
examples explicitly include *"personal home automation purposes"* --
language that describes exactly this product's shape (a self-hosted, local
application calling the API from the end user's own network, on that
user's own behalf, the same shape Home Assistant's own built-in Open-Meteo
integration uses). Free-tier limits, quoted: *"less than 10'000 API calls
per day, 5'000 per hour and 600 per minute."* No API key, account, or
credit card required for non-commercial use -- confirmed both by the terms
page and by a real unauthenticated call returning `HTTP 200`.

**License** (<https://open-meteo.com/en/licence>, quoted): *"Attribution
4.0 International (CC BY 4.0),"* requiring *"appropriate credit, [a] link
to the licence, and indicat[ion] if changes were made,"* identically for
non-commercial and commercial use. A visible attribution link ("Weather
data by Open-Meteo.com") is placed next to the new settings toggle in
`EnvironmentalContextCard.tsx` to satisfy this honestly.

**Unresolved caveat, preserved rather than resolved** (mirroring the
still-open BirdNET commercial-adjacent caveat in
[release-execution-state.md](release-execution-state.md) &sect;2): whether
MockingBird's own optional donation/paid-support posture could ever make
an individual end user's personal Open-Meteo usage implicated is not
resolved here. The judgment made -- consistent with, not overriding, that
existing caveat -- is that each self-hosted instance calls Open-Meteo
directly from the end user's own network for that user's own Place, the
ordinary "personal home automation" shape the terms describe, not
MockingBird-the-project's own commercial use. Documented product judgment,
not a legal conclusion.

**Alternatives rejected:**

- **api.weather.gov (NWS)** -- excellent terms, but US-only coverage fails
  "reasonable geographic coverage for initial users."
- **OpenWeatherMap** -- global, but requires account sign-up/API key with a
  materially lower free rate limit; fails "credential-free strongly
  preferred."
- **Open-Meteo's own Archive/ERA5 endpoint** -- same provider, same
  free/non-commercial/no-key terms (confirmed directly), 1940-present. Not
  integrated: the forecast endpoint's own confirmed 92-day window already
  exceeds this product's entire real accumulated history (~2 weeks
  in-repo). Recorded as a future capability for deeper historical
  backfill, not built by adjacency.

**Real-call evidence captured this session** (no secrets involved): a real
`start_date`/`end_date` request returned `HTTP 200` with the documented
`hourly_units`/`hourly.time[]` shape; an out-of-range `start_date` returned
`HTTP 400` with `{"reason": "Parameter 'start_date' is out of allowed
range from <today-92d> to <today+16d>", "error": true}`; an out-of-range
latitude (`999`) returned `HTTP 400` with `{"reason": "Latitude must be in
range of -90 to 90°. Given: 999.0.", "error": true}`; a mid-ocean
coordinate returned a normal `HTTP 200` payload (global grid, no
"unsupported location" case for any valid lat/lon). These exact shapes
drive `weather_provider.py`'s parser and error taxonomy, and are pinned in
`tests/test_weather_provider.py` as real captured fixtures, not guesses.

## 4. Product contract

Can MockingBird attach useful, trustworthy, local environmental context to
Place history and wildlife observations without requiring cloud operation,
leaking precise location, confusing estimates with measurements, making
causal claims, or breaking silently when the provider is unavailable? At
closure: **yes, materially better than the solar/daylight-only starting
state**, within an explicitly bounded 92-day recent-history scope and two
statistical association axes (temperature, precipitation) rather than
every fetchable weather variable. See "Capability maturity," below, for the
honest grade.

## 5. Data model

**Schema unchanged:** `environmental_context_records` (schema 51). Eight
new provider-neutral `metric` values (`air_temperature`,
`relative_humidity`, `precipitation_amount`, `snowfall_amount`,
`wind_speed`, `wind_direction`, `cloud_cover`, `surface_pressure`), each
mapped from an Open-Meteo hourly field at the parsing boundary only --
never a raw provider field name in the durable record. `information_class`
is a hard-coded constant, **always `"inferred"`**, for every row this
provider writes -- see "Provenance / information class," below, for the
full reasoning.

**Schema v53 -> v54:** one additive column,
`environmental_context_settings.weather_enabled BOOLEAN NOT NULL DEFAULT
0`, migration `_migrate_to_environmental_context_weather`
(`src/mockingbird/storage/database.py`), mirroring the existing
`_migrate_to_scene_confusor_reviewed_evidence_learning` column-additive
template exactly (dialect guard, `has_table`/column-existence check,
`ALTER TABLE ... ADD COLUMN`). An upgraded installation that already has a
location configured for solar starts with weather requests **off** --
configuring coordinates for offline solar computation never silently also
starts sending them to a third party.

New modules: `mockingbird/environment/weather_provider.py` (Open-Meteo
adapter: request building, response parsing, error taxonomy, DI'd
requester), `mockingbird/environment/condition_bands.py` (Place-relative
temperature banding, physical-threshold precipitation/cloud-cover
classification, a restrained plain-language conditions composer),
`mockingbird/analytics/weather_association.py` (the
`conditional_association`-backed statistical wrapper, mirroring
`habitat_association.py`).

## 6. Temporal semantics

- `observed_at` = the exact UTC hour a value describes (parsed from Open-
  Meteo's `timezone=UTC` response, never assumed local).
- `retrieved_at` = when MockingBird made the HTTP call -- for "today," this
  genuinely differs from `observed_at` across repeated bounded refreshes,
  unlike v1's solar provider (computed and fetched in the same instant).
- `for_date` is populated on every hourly row (the UTC calendar date),
  reusing the existing `(source_id, provider_key, metric, for_date)` cache
  index with no migration.
- A Visit's weather resolves from the same canonical
  `StreamVisitSummary.activity_started_at` v1 already uses for solar --
  never `captured_at`.
- **Immutability policy** (Phase 14): a date strictly before "today" (UTC),
  once it has any same-location cached rows, is never re-fetched or
  overwritten, no matter how old `retrieved_at` becomes. Only "today"'s own
  rows are re-fetched, bounded by a 30-minute refresh interval, since that
  day has not finished. Proven directly:
  `test_weather_past_date_never_refetched_regardless_of_age`.
- **Local-timezone bucketing for the association pipeline only**
  (`condition_bands._bucket_date`): the existing wildlife-reporting
  pipeline (`presence_dates_by_taxon`, `usable_dates`) already buckets by
  the report's own `local_timezone`. Weather rows are stored UTC-only
  (matching solar's discipline), but re-bucketed by `local_timezone` at the
  one point they meet that pipeline -- proven with a real UTC/JST-crossing
  test (`test_local_timezone_bucketing_shifts_a_late_utc_hour_to_the_
  next_local_day`) after discovering, during implementation, that a naive
  UTC-only join would have silently misaligned whole days for any Place
  materially east or west of UTC.

## 7. Fields retained (Phase 2/30)

Eight metrics, against the "clear value / stable semantics / honestly
representable / provider-supported" test: the six the milestone brief
names (temperature, humidity, precipitation, wind speed/direction, cloud
cover) plus pressure, **plus** `snowfall_amount` -- the one addition beyond
the brief's literal list, justified on honesty grounds: without it,
describing a snowy morning as "light rain" (Phase 16's own example
phrasing) would be a factually wrong plain-language claim, and it costs
nothing extra (same API request). Explicitly **not** stored: dew point,
apparent temperature, wind gusts, shortwave radiation, soil
temperature/moisture, weather codes -- real Open-Meteo fields with no
distinct product use identified for this slice.

## 8. Caching / request budget (Phase 10/29)

- One HTTP request covers one full UTC calendar date's 24 hours
  (`start_date=end_date=for_date`) -- no per-hour, per-Visit, or per-metric
  fan-out.
- Every non-today date is fetched **at most once, ever**, per distinct
  location.
- "Today" is re-fetched at most every 30 minutes (`WEATHER_REFRESH_
  INTERVAL`) -- worst case 48 calls/day for one Place, far inside the
  10,000/day free limit.
- **Report generation costs zero provider requests** -- `_historical_
  place_baseline_and_species_statuses` reads only whatever hourly rows are
  already cached; it never calls the provider itself. Recorded limitation:
  a report's weather-association coverage depends on which dates were
  already visited via Today/Visit lookups; documented in "Remaining major
  PRODUCT opportunities," not silently biased.
- No background poller/scheduler was added -- all fetching is lazy,
  triggered only by an actual Today/Visit read. Proven directly:
  `test_weather_status_disabled_when_location_set_but_not_opted_in`/
  `test_weather_status_not_configured_without_location` both assert **zero**
  HTTP calls, and `test_weather_cache_reused_within_refresh_interval`
  proves two consecutive Today reads cost exactly one call.

## 9. Privacy / location (Phase 21/22)

- **Two independent opt-ins, not one.** Configuring `coarse_latitude`/
  `coarse_longitude` (existing v1 setting, unchanged: rounded to ~11 km
  before persisting) enables only local, offline solar computation. A new,
  separate `weather_enabled` boolean (default off) is the explicit consent
  required before this installation ever sends that same rounded
  coordinate to Open-Meteo over the network. Proven directly: configuring
  a location alone, with `weather_enabled=False`, makes zero HTTP calls.
- **No precision increase.** The identical already-accepted ~11 km-rounded
  coordinate is reused for weather -- never a finer value. Worth noting
  honestly: Open-Meteo's own underlying model grids (9-25 km depending on
  model/location) are comparable to or coarser than this rounding, so
  reusing it does not represent a meaningful loss of weather quality
  either.
- **Disclosed in the UI, not buried:** the settings checkbox reads "Also
  fetch local weather conditions," with inline text naming Open-Meteo.com
  by name and stating the location is sent over the internet -- never a
  silent background toggle.
- **No credential of any kind** exists anywhere in this milestone --
  Open-Meteo's free tier needs none, so there was nothing to store, leak,
  or accidentally log.
- HTTPS only (`https://api.open-meteo.com`); bounded 5-second timeout; no
  retry/backoff (matches house convention); coordinates are logged nowhere
  beyond the DB row itself (no console/log-line prints latitude/longitude).

## 10. Failure / degraded behavior (Phase 9/24)

Closed taxonomy in `weather_provider.py`
(`WeatherProviderTimeoutError`/`WeatherProviderUnavailableError`/
`WeatherProviderRateLimitedError`/`WeatherUnsupportedLocationError`/
`WeatherProviderMalformedResponseError`), all caught at the repository
boundary and converted to an honest status -- **never** raised into
API/UI code, **never** touching global Host health, **never** blocking
Today, Visit, or observation creation. `WeatherConditions.status`
distinguishes six states without collapsing them: `available`, `stale`
(cached data exists, a refresh attempt just failed), `disabled` (location
set, not opted in), `not_configured` (no location), `out_of_range` (older
than 92 days, or future), `unavailable` (provider failure, nothing
cached). Proven directly:
`test_weather_provider_failure_with_no_cache_is_unavailable`,
`test_weather_provider_failure_with_existing_cache_serves_stale`,
`test_weather_date_beyond_max_past_days_is_out_of_range_without_calling_
provider`.

## 11. Place Intelligence integration (Phase 6/7)

Two condition axes, each a thin wrapper over the unmodified
`conditional_association` primitive, mirroring `habitat_association.py`
field-for-field:

1. **Temperature, Place-relative** (tertiles of this Place's own recent
   daily-mean distribution; `insufficient_baseline` below 10 distinct
   days) -- `cooler_than_typical` vs. rest, `warmer_than_typical` vs. rest.
2. **Precipitation, physical threshold** (&ge;0.2mm liquid-equivalent) --
   `wet_day` vs. `dry_day`.

Deliberately **not** built as statistical axes this slice: wind-band and
cloud-cover association (named "if useful/data quality supports it" in the
brief, softer than temperature/precipitation; still fetched/stored/shown
in the Today summary, just not run through `conditional_association`).
Output carries no free text (`TaxonWeatherAssociation` is status + counts
only); phrasing reuses `PlaceActivityReportPage.tsx`'s existing
`habitat_associations` idiom verbatim ("Observed more/less often during
{condition}") -- no new phrasing convention invented. Wired additively
into `PlaceActivityReportResponse`/`WildlifeJournalHistoryResponse`
alongside `habitat_associations`.

## 12. Product surfaces (Phase 16)

- **Settings** (`EnvironmentalContextCard.tsx`): one checkbox
  (`weather_enabled`), off by default, with disclosure text and the CC BY
  4.0 Open-Meteo attribution link.
- **Today**: one additional fact ("Conditions") in the same card, present
  only when weather is `available`/`stale` -- e.g. "62&deg;F, cooler than
  typical &middot; light snow." Never an absolute "cold"/"warm" claim when
  the Place-relative baseline itself is not yet established.
- **Visit detail**: an optional weather line in the existing "Conditions"
  card, resolved and rendered **independently** of whether solar itself is
  available for that date (a real code change from v1: the card now shows
  either fact, both, or neither, rather than requiring solar to succeed
  before anything renders).
- **Place Report / Bird Log**: `weather_associations` rendered with the
  identical one-line/all-matches conventions each page already uses for
  `habitat_associations` -- no new visual pattern.
- Deliberately never built: a forecast, a chart, an hourly/daily table, a
  dedicated weather page.

## 13. Provenance / information class (Phase 2/13)

`information_class` is a **hard-coded constant, always `"inferred"`**, for
every row `open_meteo` ever writes -- including "current" conditions. Per
the governing information model: Open-Meteo blends multiple numerical-
weather-prediction models and interpolates to the requested coordinate; it
is a gridded model estimate for the Place, not a physical sensor
physically attached to the observatory. This mirrors the reasoning v1
already applied to deterministic solar computation, extended to a
genuinely probabilistic external estimate. `provenance_json` stores a
small, bounded, fixed-shape object (`{"api_field": ..., "model": "best_
match"}`) -- never a raw payload dump, never an API key (there is none).
Proven directly: `test_weather_information_class_is_always_inferred_
never_measured`, `test_weather_provenance_json_is_bounded_never_a_raw_
payload_dump`.

## 14. Research/export considerations (Phase 20)

No export path reads the weather settings or includes weather records --
[research-conservation-export-contract.md](research-conservation-export-contract.md)
"Privacy" was amended with a pointer noting this explicitly (the same
"amend with a pointer, don't rewrite" convention v1's own coordinate
exception used). CC BY 4.0's attribution requirement is satisfied for the
one place weather data is currently shown (the product UI itself, via the
settings-panel credit link); a future milestone that adds weather to a
generic/Camtrap DP export must carry that attribution forward explicitly,
recorded here rather than silently assumed.

## 15. Production-shaped validation (Phase 28)

- **Real, unauthenticated HTTPS calls** to `api.open-meteo.com` made
  directly from this sandbox during provider research (documented in
  "Provider decision," above) -- no secret, no user interaction, no
  private location involved (public test coordinates only).
- **42/42 targeted Playwright e2e tests passed** against the real running
  app (real FastAPI backend, real SQLite, real frontend build) --
  `biodiversity-summary`, `bird-log-historical-status`,
  `place-activity-report`, `today-report`, `visit-evidence-gallery`.
  Notably includes "Dashboard's real request to the Place Activity Report
  endpoint succeeds against the real backend," proving the new
  `weather_associations` field round-trips through the real stack without
  breaking existing consumers.
- No live user credentials, live monitoring session, or human review was
  required or requested, per the milestone's autonomous-development rule.

## 16. Performance / storage (Phase 12/29)

- Retention estimate: 8 metrics &times; 24 hours = 192 rows per freshly
  fetched date; &asymp;70,000 rows/year at full daily coverage;
  &asymp;15-20 MB/year (short strings/floats/timestamps, SQLite row
  overhead) -- compact, no rollup/cleanup policy added at this scale.
- No N+1 pattern: the association pipeline's weather query is one bounded
  `SELECT` over the report's window per report generation, not per-Visit
  or per-taxon.
- No premature optimization performed or needed at this data volume.

## 17. Tests / validation

**Tier 1 (pure modules, no DB/network):** `tests/test_weather_provider.py`
(27 tests: status resolution, request-URL construction, response
parsing -- normal/missing-field/null-hour/malformed/wrong-length/non-
numeric, real captured HTTP error shapes mapped to the right exception,
one opt-in real-network smoke test); `tests/test_condition_bands.py` (23
tests: temperature baseline/banding including the Place-relative
anti-example proof, precipitation/cloud-cover classification, daily
aggregation including the UTC-vs-local-timezone-bucketing proof, `latest_
observation`, the plain-language composer including the "never a
time-of-day word" proof); `tests/test_weather_association.py` (9 tests:
every association branch, the "missing-coverage-date excluded, never
folded into out-of-condition" proof, determinism, condition-label
wording).

**Tier 2 (repository/API/schema):** `tests/test_environmental_context.py`
extended with 25 new weather-specific tests (settings CRUD, provider
status transitions with call-count assertions proving no network call
while disabled/not-configured, cache reuse and the 30-minute refresh gate,
past-date immutability, the location-change basis-preservation proof, the
baseline-anchoring and cached-data-remains-readable regression proofs (see
below), stale-on-failure, out-of-range (past and future), independence
from solar's own polar-night unavailability, review-truth non-mutation,
provenance bounding, temperature-baseline establishment, HTTP-layer PUT/GET
round trips, backup/restore survival); `tests/test_persistence.py` +1
(schema-54 migration, column-additive template); `tests/test_place_
activity_report_repository.py` updated (the exhaustive taxon-key-set
assertion now includes `weather_associations`). Frontend: `tsc --noEmit`
clean, `vite build` clean, 42/42 targeted e2e passing (see above).

**Three real implementation bugs found and fixed by this test-writing, not
merely confirmed correct:**

1. The first draft of `_get_or_fetch_hourly_weather_in_session` deleted
   *every* existing row for a calendar date before writing a fresh fetch's
   rows -- correct for "today" being re-fetched at the same location, but
   wrong for a location change: it would have deleted the *previous*
   location's rows too, directly violating Phase 15's "old rows are never
   deleted or reinterpreted." Caught by `test_weather_location_change_
   causes_refetch_and_preserves_old_rows` failing; fixed by scoping both
   the freshness check and the delete to rows matching the *current*
   settings location only, never touching a different-location row at any
   date.
2. The first draft of `_recent_temperature_band` anchored its trailing
   baseline window at "now" rather than at the instant being classified --
   a historical Visit's temperature would have been judged against
   whatever season "now" happened to be when the Visit was later viewed
   (e.g. a March Visit compared against an August baseline), rather than
   conditions typical around the Visit's own date. Not caught by a failing
   test (found by re-reading the code against `_historical_place_baseline_
   and_species_statuses`'s own identical "anchor at the caller's own
   period, not now" precedent, which this new method had not yet
   followed); fixed by anchoring the window at `instant.date()`, then
   proven with a dedicated regression test
   (`test_temperature_baseline_anchored_at_visit_date_not_now`) using two
   deliberately non-overlapping, deliberately contradictory ten-day
   windows to make the wrong-window failure mode unmistakable if it
   regressed.
3. Directly related to bug 2's fix: the original out-of-range check ran
   *before* the cache-hit check, so a date already fully cached would
   still be refused as `"out_of_range"` once "now" moved far enough past
   it -- retroactively making valid, already-acquired historical data
   unusable purely because the calendar advanced, contradicting Phase 14
   immutability. Fixed by reordering: the out-of-range check now gates
   only a genuine cache-miss fetch *attempt*, never a read of data already
   on hand. Proven with
   `test_cached_data_beyond_provider_window_remains_readable`.

**Tier 3 (full Core):** run this session, exactly justified by the schema
bump touching shared read models -- and it earned its cost. The first
full run (25m08s) showed **12 failed**, not the expected 2. Bisected
immediately via `git stash push -u` (never `git worktree` -- this
repository's own established, documented finding is that worktree gives
invalid test baselines here) against the clean `7a3bbfb` baseline: running
the exact same 12 tests there reproduced only the 2 already-documented
`test_place_biodiversity_summary_repository.py` failures; the other 10
passed cleanly. **Root cause, found in under a minute once isolated:** 10
tests across 7 files entirely unrelated to Environmental Context
(`test_camera_health.py`, `test_camera_node.py`, `test_candidate_visit_
repository.py`, `test_species_candidate_packs.py`, `test_visit_
collections.py`, `test_visit_tags.py`, `test_yard_map.py`) each hard-code
`CURRENT_DATABASE_SCHEMA_VERSION == 53` as an explicit guard-rail assertion
-- this codebase's own established "guard the exact documented constant"
convention (the same idiom `test_habitat_association.py` uses for
`MIN_CONDITION_INTERVAL_DAYS == 5`), whose entire purpose is to force
whoever bumps a tracked constant to deliberately touch every test that
pins its old value, rather than let it drift silently. Bumping schema v53
-> v54 correctly, exactly as this milestone's own instructions require,
was always going to trip these 14 guard-rails (some files pin the number
more than once) across 7 files this milestone has no other reason to
touch -- not a defect in this milestone's own migration or product logic
(confirmed separately and directly: this milestone's *own*
`test_schema_53_upgrades_to_current_with_environmental_context_weather`
passed on the very first run, both before and after this fix). Fixed by
updating all 14 literal `53` occurrences to `54`; deliberately left two
further `database_schema_version=53` occurrences in
`test_single_app_runtime.py` untouched after reading them -- they are
self-contained `_print_preflight` console-formatting tests using an
arbitrary illustrative version number, never importing or comparing
against `CURRENT_DATABASE_SCHEMA_VERSION` at all, so they are not part of
this ripple and touching them would be unrelated churn. Also checked: none
of this repository's 5 `@pytest.mark.slow` files (excluded from the Core
gate, not exercised by this run at all) reference the schema-version
constant, so none are silently carrying the same stale pin into the Full
gate.

**Second full Core run: 4874 passed / 3 failed / 3 skipped / 23 deselected
/ 11 xfailed (26m13s).** Two of the three are the identical, already-
documented `test_place_biodiversity_summary_repository.py` pair. The
third, new to this run --
`tests/test_transport_worker.py::test_retryable_failure_returns_item_to_
failed_retryable_and_eventually_succeeds` -- was investigated immediately:
it belongs to the Remote/Intermittent-WAN transport-worker subsystem, has
no relationship whatsoever to Environmental Context (no shared import, no
shared code path), and its own body is genuine real-clock async
retry/backoff logic (`await _run_until(..., timeout=5.0)` against a
background worker task) -- exactly the shape of test most exposed to
scheduler jitter under load. This run coincided with confirmed heavy CPU
contention from a concurrent, unrelated pytest process in a different
project's repository (confirmed via `ps aux` during the run). Re-run
immediately in isolation, it passed instantly (0.45s); the entire
`test_transport_worker.py` file was then re-run standalone and passed all
7 tests cleanly (1.83s). This is a transient, load-induced flake, not a
regression -- consistent with this repository's own documented "~2/4500/
run" genuine pre-existing Core flakiness baseline, here landing on a
different individual test than usual by chance. Not fixed (nothing to
fix; the code under test is untouched by this milestone and the test
itself is correct), and not silently dismissed -- recorded here with the
full isolation evidence.

## 18. Remaining major PRODUCT opportunities

Framed as roadmap opportunities, matching this milestone's own "not a
release blocker" framing:

- **Deeper historical backfill via Open-Meteo's Archive/ERA5 endpoint** --
  same provider, same free terms (confirmed), 1940-present reanalysis; not
  integrated because the 92-day forecast-endpoint window already exceeds
  this product's entire real history today.
- **Wind-band and cloud-cover statistical associations** -- fetched/
  stored/shown in Today's summary, deliberately not run through
  `conditional_association` this slice (the brief's own softer "if useful"
  language for these two, versus temperature/precipitation).
- **Proactive report-window backfill** -- `_historical_place_baseline_
  and_species_statuses` only sees weather already cached via Today/Visit
  reads; a future slice could bound-fetch the report's own comparison
  window proactively, still without a live call from inside report
  generation itself.
- **A dedicated Explore-page rendering for weather associations**, beyond
  the one-line Place Report/Bird Log treatment -- mirrors the exact,
  already-accepted precedent of `source_quality_signals` (Place/Yard
  Intelligence v2: "computed and returned by the API, not yet rendered").
- **A positive (non-empty), full repository-level integration test** for
  `weather_associations` composing real multi-day cached weather with real
  Visits through `place_activity_report` end-to-end -- the pure
  `weather_association.py` module and the data-flow (caching/Visit/Today)
  paths are both thoroughly tested independently, but the full pipeline
  together is only verified by careful code reading, not an automated
  test. Recorded rather than silently skipped: this exact gap already
  exists, unaddressed, for `habitat_associations` in the accepted Place /
  Yard Intelligence v2 milestone (confirmed by grep: no positive
  repository-level habitat-association test exists either) -- this
  matches, not falls short of, the established acceptance bar.
- **A latent, low-impact, pre-existing solar cache-lookup gap, noted not
  fixed:** unlike the new weather cache (which checks `basis_latitude`/
  `basis_longitude` before reusing a cached row), the frozen, already-
  accepted `_get_or_compute_daily_solar_facts_in_session` does not perform
  this same basis check -- a user changing location mid-day and
  re-querying the same UTC date could see stale-location sunrise/sunset.
  Out of scope to touch frozen v1 code in this milestone; recorded for
  transparency.
- **Weather-provider quality/spatial-resolution flags** -- v1's own
  "Explicitly deferred" list named this as meaningful "once a non-exact
  provider exists"; one now does, but this slice does not yet surface
  Open-Meteo's own per-model/per-location resolution as a quality signal.
- **A dedicated advanced-diagnostics surface** -- `WeatherConditions`
  already carries everything Phase 23 lists as optional advanced-
  diagnostics fields (`provider_key`, `observed_at`/`retrieved_at`,
  `information_class`, `status` as a failure code), but no separate
  diagnostics view exists yet to show them; today they are only consumed
  by the restrained plain-language Today/Visit cards, per Phase 23's own
  "normal users should see useful plain language" instruction. Adding a
  dedicated view is a small, bounded follow-up with no data-model change.

## 19. Capability maturity

**B -- major useful capability with bounded provider/statistical/UI
limitations.**

Rationale: this milestone delivers a real, tested, honestly-classified
external weather provider integrated through the identical association
machinery Place / Yard Intelligence v2 established, with correct privacy
gating (two independent opt-ins, zero location-precision increase),
correct temporal semantics (immutability, local/UTC bucketing, bounded
refresh), and correct degraded-mode behavior (six distinct honest states,
zero crashes, zero blocking of core product function) -- genuinely moving
the product past "solar/daylight is the only environmental fact
MockingBird knows." It stops short of "A" because: the historical window
is deliberately bounded to 92 days (not a limitation of this product's
real history today, but a real ceiling); only two of several plausible
statistical association axes are built; weather-association rendering in
the UI is a single compact line, not a dedicated surface; and the full
positive-signal repository-level integration path is verified by code
reading and independently-tested components rather than one dedicated
end-to-end test (matching, not falling short of, the existing
`habitat_associations` acceptance bar). None of these gaps are
structural -- the provider abstraction, data model, and association
primitive all support closing them without rework.

## 20. Scheduler reconciliation

Confirmed: **CURRENT PHASE = SUBSTANTIAL PRODUCT DEVELOPMENT.**
Representative Field Acceptance, External Beta, and Final Release
Hardening remain downstream while substantial product-roadmap capability
remains intentionally unfinished (see
[release-execution-state.md](release-execution-state.md) &sect;6 for the
complete remaining-capability picture). This milestone does not authorize
itself or any other milestone next -- see
[release-execution-state.md](release-execution-state.md) for the updated
"NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED" state.

## 21. Preserved files

Verified untouched, present, and unmodified before and after this
milestone's work (matches exactly the seven files
[release-execution-state.md](release-execution-state.md) names):

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

## 22. Exact `git status --short`

Immediately after the implementation commit (`751d061`), before the
reconciliation commit:

```
 M docs/environmental-context-v2-report.md
 M docs/release-execution-state.md
?? docs/wildlife-detector-training-contract.md.orig
?? scripts/evaluate_small_bird_detector.py
?? scripts/materialize_wildlife_stage2.py.orig
?? scripts/train_wildlife_stage2_rfdetr.py.orig
?? src/mockingbird/detectors/small_bird_benchmark.py
?? src/mockingbird/training/wildlife.py.orig
?? tests/test_small_bird_benchmark.py
```

The two modified files above are this report's own final hash/status
fill-in and `release-execution-state.md`'s reconciliation -- both land in
the second (reconciliation) commit. The seven `??` entries are exactly,
and only, the seven preserved detector files this milestone was required
to leave untouched -- confirmed identical to the milestone's own starting
worktree state. After the reconciliation commit, the working tree returns
to exactly those same seven untracked files and nothing else.
