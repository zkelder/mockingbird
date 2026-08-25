# Environmental Context v2 -- Weather, Climate & Place Conditions Contract

## Purpose

Extend Environmental Context Foundation v1 (solar/daylight only, schema 51 --
see
[environmental-context-foundation-v1-contract.md](environmental-context-foundation-v1-contract.md))
with the first general weather/climate provider: air temperature, relative
humidity, precipitation (amount and rain/snow state), wind speed/direction,
cloud cover, and surface pressure. Bounded current-vs-recent-history context
plus a Place-relative "cooler/warmer than typical" and "wet/dry" association
with wildlife activity, composed onto the Place / Yard Intelligence v2
association machinery. Architecture-plus-one-provider, not a weather
platform -- see "Scope boundaries" in the governing milestone brief for what
this deliberately does not build (forecasting, alerts, causal claims,
multi-provider abstraction breadth).

## Phase 1 -- confirmed archaeology (bounded)

- No weather/temperature/precipitation/wind/pressure code exists anywhere in
  this codebase before this milestone (confirmed by the v1 contract's own
  "Explicitly deferred" list and Place / Yard Intelligence v2's exhaustive
  grep, both re-confirmed this session).
- `EnvironmentalContextRecordModel` (schema 51) already anticipates exactly
  this: `value_numeric`/`value_text`/`unit` for a future numeric metric,
  `observed_at_end` for a future interval/aggregate, `provider_key` as a
  flat string (not an enum requiring a schema change per provider),
  `information_class` as the closed Measured/Inferred/Reviewed vocabulary
  with the model's own docstring naming "a future public weather/
  environmental API" as the anticipated next writer. **No schema change to
  this table is needed or made.**
- `EnvironmentalContextSettingsModel` (schema 51) has only
  `coarse_latitude`/`coarse_longitude`/`updated_at`. It has no notion of
  "the user has consented to an outbound network call," because v1's only
  provider (`solar_local`) never makes one. **This is the one genuine
  schema gap** -- see "Privacy / location," below.
- `mockingbird.analytics.conditional_association.compute_conditional_
  association` (Place / Yard Intelligence v2) is a generic, already-tested,
  already-accepted "presence-rate inside a date-set" primitive with its own
  minimum-sample gating (`min_usable_days_in_condition`/`_out_of_condition`,
  default 5 each) and causal-safe output vocabulary
  (`more_common_under_condition`/`less_common_under_condition`/
  `no_clear_association`/`insufficient_data`). `habitat_association.py` is a
  ~140-line thin wrapper that prepares date-sets from `PhenologyIntervalFact`
  rows and calls this primitive per taxon. Both the Place/Yard v2 contract
  and report name this exact pattern as the intended shape for a future
  weather association, once a provider exists. **v2 follows this pattern
  exactly** via a new `weather_association.py` sibling -- no new statistical
  gating logic is invented.
- House outbound-network-call convention (`external_url_preview.py`,
  `onvif_client.py`): stdlib `urllib`, a small bounded timeout, a
  dependency-injected requester `Protocol` for testability, one attempt, no
  retry/backoff, degrade to a typed status/result on any failure, never
  raise to the caller. `httpx` exists only as a `test`-extra dependency for
  ASGI test-client plumbing (`main.py:778`), not a production HTTP client.
  **v2 introduces no new dependency** -- `urllib.request` only.
- Structured-health precedent: `BioClipAdapterStatus`/`BirdNetRuntimeStatus`
  -- a frozen dataclass, a `Literal` status vocabulary, a status function
  that never raises. **v2's weather status mirrors this shape.**
- `_daylight_bucket_by_visit_id` (product_repository.py) is the precedent
  for "resolve an absence-safe, bounded, per-report environmental fact
  without ever making the report a live network caller": it reads only
  already-configured coordinates and already-cached solar facts, returns
  `{}` at zero cost when unconfigured. **v2's report-time weather-band
  resolution follows the identical discipline: read-only over already-
  persisted `environmental_context_records`, never a live provider call
  from inside report generation.**

## Phase 2 -- provider-neutral contract

New metric vocabulary (durable, provider-neutral -- never a raw provider
field name), stored as additional `metric` values on the existing
`environmental_context_records` table:

| `metric` | `unit` | Open-Meteo hourly field |
|---|---|---|
| `air_temperature` | `celsius` | `temperature_2m` |
| `relative_humidity` | `percent` | `relative_humidity_2m` |
| `precipitation_amount` | `mm` | `precipitation` (rain+showers+snow water-equivalent, combined) |
| `snowfall_amount` | `cm` | `snowfall` |
| `wind_speed` | `km/h` | `wind_speed_10m` |
| `wind_direction` | `degrees` | `wind_direction_10m` |
| `cloud_cover` | `percent` | `cloud_cover` |
| `surface_pressure` | `hPa` | `surface_pressure` |

Rationale for exactly these eight, against the milestone brief's "clear
wildlife/Place value, stable semantics, honestly representable, provider-
supported" test:

- The six explicitly named in the brief (temperature, humidity,
  precipitation, wind speed, wind direction, cloud cover) plus pressure --
  all stable, well-understood, directly supported.
- `snowfall_amount` is the one addition beyond the brief's literal list,
  justified on honesty grounds: without it, "precipitation occurred" cannot
  be described as rain vs. snow, and describing a snowy morning as "light
  rain" (Phase 16's own example UI text) would be a factually wrong plain-
  language claim. It costs nothing extra (same API request, one more
  field), so it is not "implementing a field merely because the provider
  exposes it" -- it is fixing an honesty gap the other seven fields would
  otherwise create.
- Explicitly **not** stored as separate metrics: dew point, apparent
  temperature, wind gusts, shortwave radiation, soil temperature/moisture,
  weather codes. All are real Open-Meteo fields with no clear, distinct
  product use identified for this milestone -- recorded as a future
  opportunity, not built by adjacency (Phase 30 test).
- No categorical `"precipitation_state"` metric is stored. `precipitation_
  amount` + `snowfall_amount` together already let read-time code derive
  rain/snow/dry honestly (see `condition_bands.py`, below) without a ninth
  stored value duplicating information already present in the other two.

`information_class` is **always `"inferred"`**, hard-coded, never
`"measured"`, for every record this provider ever writes -- including
"current" conditions. Per the governing milestone brief's own information
model: Open-Meteo blends multiple numerical weather-prediction models and
interpolates to the requested coordinate; it is a gridded model estimate for
the Place, not a physical sensor physically attached to the observatory,
"even for 'current conditions' from a model-based gridded API." This is the
same reasoning the v1 contract already applied to deterministic solar
computation, extended to a genuinely probabilistic external estimate. A
future locally-attached physical sensor (temperature probe, rain gauge)
would be the first `"measured"` writer this table ever has; this milestone
adds no such writer.

`provider_key = "open_meteo"`, a new sibling to `"solar_local"` in the same
flat-string family (no enum, no `SourceProviderKind`-style `elif` chain --
see v1 contract's "Source / provider").

## Phase 3 -- provider selection

**Selected: Open-Meteo** (`https://api.open-meteo.com/v1/forecast` for
current/recent-past hourly conditions). All claims below were verified this
session via direct `WebFetch`/`WebSearch` against Open-Meteo's own
terms/licence/docs pages and real HTTPS calls from this sandbox (not
recalled from training knowledge), per the milestone brief's "current
authoritative documentation" instruction.

**License/terms (quoted).** Terms
(<https://open-meteo.com/en/terms>): non-commercial examples explicitly
include *"personal home automation purposes"* -- language that describes
exactly this product's shape (a self-hosted, local, personal-use
application calling the API from the end user's own network on that user's
own behalf, the same shape Home Assistant's own built-in Open-Meteo weather
integration already uses). Free-tier limits: *"less than 10'000 API calls
per day, 5'000 per hour and 600 per minute"* -- with this milestone's cache
design (below), a single Place needs on the order of tens of calls per day,
not thousands. No API key, account, or credit card is required for
non-commercial use (confirmed both via the terms page and a real,
unauthenticated HTTPS call from this sandbox returning `HTTP 200` with a
complete forecast payload). Data license
(<https://open-meteo.com/en/licence>): *"Attribution 4.0 International (CC
BY 4.0)"*, requiring *"appropriate credit, [a] link to the licence, and
indicat[ion] if changes were made,"* applying identically to non-commercial
and commercial use, with a documented attribution snippet ("Weather data by
Open-Meteo.com" linked to the site). The server code itself is AGPLv3
(irrelevant here -- MockingBird calls the hosted API, it does not
redistribute or modify Open-Meteo's server).

**Unresolved caveat, preserved rather than resolved** (mirroring the
existing, still-open BirdNET commercial-adjacent caveat in
[release-execution-state.md](release-execution-state.md) &sect;2): whether
MockingBird's own optional donation/paid-support posture could ever make an
individual end user's personal, non-commercial Open-Meteo usage
implicated is not a question this milestone resolves. The judgment made
here -- consistent with, not overriding, that existing caveat -- is that
each self-hosted MockingBird instance calls Open-Meteo directly from the
end user's own network for that user's own Place, never through a
MockingBird-operated central proxy or on MockingBird's own account, which is
the ordinary "personal home automation" shape the terms describe, not
MockingBird-the-project's own commercial use of the API. This is a
documented product judgment, not a legal conclusion.

**Alternatives considered and rejected:**

- **api.weather.gov (NWS)** -- free, no key, public-domain data, excellent
  terms. Rejected: US-only coverage fails "reasonable geographic coverage
  for initial users" (criterion 4) for a product with no geographic
  restriction in its doctrine.
- **OpenWeatherMap** -- global coverage, but the free tier requires account
  sign-up and an API key, with a materially lower free rate limit and less
  generous historical access. Rejected against "credential-free strongly
  preferred" and "credential/API-key burden" (criteria 9).
- **Archive/ERA5 endpoint** (`archive-api.open-meteo.com`) -- same
  provider, same free/non-commercial/no-key terms (confirmed via the same
  licence page and a real HTTPS call), 1940-present reanalysis. Not
  integrated in v2: the forecast endpoint's own `past_days`/`start_date`
  range (up to 92 days, confirmed by a real `400` response naming the exact
  allowed window) already exceeds this product's entire real accumulated
  history (~2 weeks in-repo, ~5 usable days per the Place/Yard v2 report's
  own real-install evidence). Recorded as a future capability for deeper
  historical backfill/multi-year seasonality, not built now (Phase 25/30
  test: do not implement by adjacency).

**Real-call evidence (this session, no secrets involved):**
`GET https://api.open-meteo.com/v1/forecast?latitude=40.7&longitude=-74.0&hourly=...&start_date=2026-08-20&end_date=2026-08-20&timezone=UTC`
returned `HTTP 200` with the documented `hourly_units`/`hourly.time[]`
shape; an out-of-range `start_date` returns `HTTP 400` with
`{"reason": "Parameter 'start_date' is out of allowed range from
<today-92d> to <today+16d>", "error": true}`; an out-of-range latitude
(`999`) returns `HTTP 400` with `{"reason": "Latitude must be in range of
-90 to 90°. Given: 999.0.", "error": true}`; a mid-ocean coordinate
returns `HTTP 200` with a normal payload (global grid coverage, no
"unsupported location" case for any valid lat/lon). These exact shapes
drive the parser's error taxonomy below.

## Phase 4/25 -- current vs. historical scope

Single endpoint, single bounded window: `WEATHER_MAX_PAST_DAYS = 92`
(the provider's own confirmed maximum). No archive/ERA5 integration.
"Historical backfill" is **on-demand, per-UTC-calendar-date, resumable, and
happens automatically only through ordinary product use** -- there is no
separate backfill job/command:

- Viewing Today or a Visit for a date within the last 92 days that has never
  been fetched triggers exactly one bounded fetch for that one date (see
  caching below), the same "compute or reuse cached" idiom v1 uses for
  solar.
- A date older than 92 days, or in the future, returns `out_of_range`
  honestly (Phase 8's required "not enough environmental history to
  compare" outcome) -- never a fabricated value, never a crash. This gates
  a new fetch *attempt* only, checked after the cache-hit check, never
  before it: a date already cached (for example, fetched while it was
  still inside the window, then viewed again much later) remains readable
  forever -- it does not retroactively become unusable merely because the
  calendar moved on. Implemented this way after an implementation-time
  correction; see the milestone report's "Tests / validation" for the
  concrete bug this fixed.
- Because this product's entire real history is younger than 92 days today,
  this bound is not a practical limitation of anything real yet; it is an
  explicit, honest ceiling for the future.

## Phase 5 -- temporal semantics

- `observed_at` = the exact hour the value describes (Open-Meteo returns
  hourly instants; requested with `timezone=UTC`, confirmed to return plain
  `YYYY-MM-DDTHH:MM` strings meaning UTC wall-clock, parsed as
  timezone-aware UTC, never assumed local).
- `retrieved_at` = when MockingBird made the HTTP call, distinct from
  `observed_at` -- this is the one place v1's "these are computed in the
  same call for solar" simplification genuinely stops applying: a weather
  fetch can retrieve many past hours in one call, and "today"'s own rows
  get **re-fetched** (new `retrieved_at`, same `observed_at` range) as the
  day progresses -- see "Correction / immutability," below.
- `for_date` = the UTC calendar date of `observed_at`, populated on every
  hourly row (unlike solar, where a metric can be `NULL`) -- this is the
  cache-lookup key, reusing the existing `(source_id, provider_key, metric,
  for_date)` index with no migration.
- A Visit's weather context resolves from `StreamVisitSummary.
  activity_started_at` (the identical canonical instant v1 already uses for
  solar), rounded down to the containing UTC hour to find the matching
  hourly row -- never `captured_at`, matching v1's existing precedent
  exactly.
- Never civil/local time anywhere in this module. No timezone or DST
  concept is introduced, matching the corrected solar model's own standing
  rule.

## Phase 6/7 -- association design

Two condition axes, each a thin `mockingbird.analytics.weather_association`
wrapper around the existing, unmodified `compute_conditional_association`
primitive -- mirroring `habitat_association.py` field-for-field:

1. **Temperature, Place-relative.** `condition_bands.compute_temperature_
   baseline` computes the lower/upper tertile of daily-mean temperature
   over the trailing `WEATHER_MAX_PAST_DAYS`-bounded window of cached
   weather data, requiring at least `MIN_DAYS_FOR_TEMPERATURE_BASELINE =
   10` distinct days or the baseline is `insufficient_baseline` (a
   distinct, explicit outcome, never a fabricated split). Each day is then
   `cooler_than_typical` / `typical` / `warmer_than_typical` --
   deliberately Place-relative (tertiles of this Place's own recent
   distribution), directly avoiding the brief's own anti-example ("a
   65&deg;F morning should not be called 'cold' everywhere"). **The window
   is anchored at the instant being classified, not at "now"**: a
   historical Visit's temperature is judged against conditions typical
   around *that* Visit's own date, reproducibly regardless of when it is
   later viewed -- the identical "anchor at the caller's own period" rule
   `_historical_place_baseline_and_species_statuses` already applies to its
   own trailing window. Two association passes per taxon:
   `cooler_than_typical` vs. the rest, and `warmer_than_typical` vs. the
   rest.
2. **Precipitation, physical threshold.** `WET_DAY_PRECIPITATION_THRESHOLD_
   MM = 0.2` (any measurable precipitation, liquid-equivalent, rain or
   snow combined) classifies each day `wet_day`/`dry_day`. Not
   Place-relative -- "measurable precipitation occurred" has stable
   physical meaning independent of climate, unlike temperature. One
   association pass per taxon: `wet_day` vs. `dry_day`.

**Deliberately not built as a third/fourth statistical axis:** wind-band
and cloud-cover associations. Both are named as "if data quality/usefulness
supports it" (explicitly softer than temperature/precipitation) in the
governing brief; adding them would double the association surface (more
stored output, more test surface, more UI text) for a v2 slice whose own
"do not expose every weather variable automatically" instruction favors a
smaller, higher-confidence initial surface. Wind speed, wind direction, and
cloud cover are still fetched/stored/exposed (they have direct value for the
Today plain-language summary and future opportunities), just not run
through the statistical association machinery this milestone. Recorded as a
future opportunity (Phase 30 test), not built by adjacency.

**Output shape carries no free text**, matching `conditional_association`'s
own "association language only, never causal" discipline exactly:
`TaxonWeatherAssociation(taxon, band_label, condition, association:
ConditionalAssociation)`. Phrasing happens only at the existing
presentation layer, reusing `PlaceActivityReportPage.tsx`'s established
`TaxonCard` idiom for `habitat_associations` verbatim (find the first
non-`no_clear_association` entry, render one compact `meta-text` line:
"Observed more/less often" + condition phrase) -- no new phrasing
convention invented.

**Report-time cost:** zero additional provider calls (see Phase 1's
`_daylight_bucket_by_visit_id` precedent, above) -- `_historical_place_
baseline_and_species_statuses` reads only whatever hourly weather rows
already exist in `environmental_context_records` for its report window,
computes daily bands from them, and skips the whole computation (empty
dict, matching habitat association's "skipped entirely when no phenology
has ever been recorded") when weather is not configured/enabled or no
cached data exists yet for the window. Recorded limitation: a report's
weather-association coverage depends on which dates were already visited
via Today/Visit lookups (the only paths that ever fetch); this is honest
and bounded, not silently biased, but is recorded as a future opportunity
("proactively backfill the report's own comparison window") rather than
solved here, to keep report generation free of live network calls.

## Phase 8 -- environmental coverage

Two independent, non-conflated "usable" concepts, both explicit, both
tested:

- **Per-date data availability**: `WeatherDayResult.status` --
  `"available" | "not_configured" | "disabled" | "out_of_range" |
  "unavailable" | "stale"`. `out_of_range` = the bounded-window limitation
  (Phase 4); `unavailable` = provider genuinely failed and nothing is
  cached for that date; `stale` = today's own row exists but is older than
  the refresh interval and a refresh attempt just failed.
- **Baseline sufficiency**: `TemperatureBaseline.status` --
  `"insufficient_baseline" | "established"`, gating whether *any* day can be
  Place-relative-classified at all, independent of whether that day's own
  raw reading exists.

Both compose into the association layer's existing `insufficient_data`
outcome (via `usable_dates` intersection, see Phase 6) without inventing a
third insufficiency vocabulary -- `compute_conditional_association` already
returns `insufficient_data` honestly whenever the environmental-coverage
dates intersected with wildlife-usable dates fall below its existing
`min_usable_days_in_condition`/`_out_of_condition` floors (5 each).

## Phase 9 -- failure / degraded mode

`weather_provider.py` error taxonomy, all inheriting `WeatherProviderError`,
all caught at the repository boundary and converted to `WeatherDayResult(
status="unavailable")` -- **never** raised past the repository into API/UI
code, **never** touching global Host health, **never** blocking Today,
Visit, or observation creation:

- `WeatherProviderTimeoutError` -- socket timeout (bounded
  `DEFAULT_TIMEOUT_SECONDS = 5.0`, matching the existing
  `external_url_preview.py`-style bounded-timeout convention).
- `WeatherProviderUnavailableError` -- connection failure, DNS failure, HTTP
  5xx.
- `WeatherProviderRateLimitedError` -- HTTP 429 (distinct code, so a
  diagnostics surface can say "rate limited," not a generic failure).
- `WeatherUnsupportedLocationError` -- HTTP 400 whose `reason` mentions
  latitude/longitude range (defensive only; MockingBird's own coordinate
  input is already range-validated at the settings layer, so this should be
  unreachable in practice).
- `WeatherProviderMalformedResponseError` -- HTTP 200 with a body that does
  not parse as JSON, or parses but is missing the expected `hourly`/
  `hourly_units` keys, or a requested metric's array length does not match
  `hourly.time`'s length.

No retry/backoff (matching house convention -- one bounded attempt, degrade
honestly). No persisted "last error" column: health for the *current*
process is inferred entirely from data recency (`retrieved_at` vs. the
refresh interval), matching "do not create a schema change if current
storage already cleanly supports it" -- a restart naturally retries on next
access, which is correct for a bounded-cadence background-free design.

## Phase 10/29 -- caching / request budget

- `WEATHER_REFRESH_INTERVAL = timedelta(minutes=30)` -- gates re-fetching
  **today's own date only**. A cold Place checked once every 30 minutes all
  day is 48 calls/day; realistic usage (a few dashboard loads/day) is far
  lower. Both comfortably inside the 600/minute, 5'000/hour, 10'000/day free
  limits with enormous headroom.
- Every other (non-today) date is fetched **at most once, ever**, per
  distinct location (see Phase 14) -- immutable-reuse, identical in spirit
  to solar's per-day cache.
- One HTTP request covers one full UTC calendar date's 24 hours in one
  call (`start_date=end_date=for_date`) -- no per-hour, per-Visit, or
  per-metric request fan-out. Viewing many Visits that fall on the same
  cached date costs zero additional requests.
- Report generation costs **zero** provider requests (Phase 6, above).
- No background poller/scheduler is introduced. All fetching is lazy,
  triggered only by an actual Today/Visit read that needs data not already
  cached -- request volume is proportional to product usage, never to
  Visit count, never a fixed background cadence independent of use.

## Phase 11/12 -- local-first / retention

All fetched hourly rows persist in the existing `environmental_context_
records` table (already the durable product database, not an ephemeral
cache) -- once fetched, a date's weather remains available with zero
internet access, identical to v1's local-first guarantee for solar.
Retention estimate: 8 metrics &times; 24 hours = 192 rows on a freshly
fetched date; over one year of daily coverage, &asymp;70,000 rows,
estimated (short strings/floats/UUID/timestamps, SQLite row overhead)
&asymp;15-20 MB/year -- compact, no separate cleanup/rollup policy needed at
this scale, consistent with Phase 29's "do not optimize prematurely."

## Phase 13/14/15 -- provenance, correction, location change

- `provenance_json` (existing bounded fixed-shape column, schema
  unchanged): `{"api_field": "<open-meteo field name>", "model":
  "best_match"}` per metric -- enough for debugging without ever storing a
  raw payload dump or an API key (there is no key), matching v1's "never a
  raw provider-response dump" discipline exactly.
- `basis_latitude`/`basis_longitude` (existing columns): populated from the
  coordinates actually used for that specific fetch. **Cache-lookup now
  additionally checks basis match**: a lookup for `for_date` only reuses
  existing rows if their `basis_latitude`/`basis_longitude` match the
  *current* settings value; a location change therefore causes the next
  lookup for any previously-cached date to fetch fresh data for the new
  location and write new rows -- old rows are never deleted or
  reinterpreted, remaining an honest audit trail for whatever location was
  configured when they were acquired. (Recorded observation, not fixed in
  this milestone: the pre-existing, accepted, frozen solar cache-lookup
  does not perform this same basis check, a latent low-impact edge case
  --a user changing location mid-day and re-querying the same UTC date
  could see stale-location sunrise/sunset. Out of scope to touch frozen
  solar code here; noted for transparency, not silently ignored.)
- **Immutability policy**: once any date strictly before "today" (UTC) has
  a successfully fetched row, it is never re-fetched or overwritten by a
  later run, even if Open-Meteo would now return a revised value for that
  date -- "preserve acquired-context provenance," per Phase 14. Only
  "today"'s own rows are re-fetched, bounded by the refresh interval, since
  the day has not finished (the reanalysis/near-term model view of the
  still-ongoing day legitimately changes as more hours elapse). This is a
  conservative policy choice, documented rather than silently assumed.
- No `reviewed` weather record is ever created automatically -- `reviewed`
  remains reserved, unused by any writer, exactly as v1 left it.

## Phase 16 -- UI/product experience

- **Settings** (`EnvironmentalContextCard.tsx`, the same component that
  already owns the coordinate-configuration UI): one new checkbox,
  `weather_enabled`, defaulting unchecked, with disclosure text ("Also
  fetch local weather conditions from Open-Meteo.com using this same
  approximate location. Sends your rounded location over the internet;
  never shared or exported automatically.") and the CC BY 4.0 attribution
  line ("Weather data by Open-Meteo.com", linked) placed beside it --
  satisfying the license's actual attribution requirement without adding a
  provider-name-as-primary-UX violation elsewhere.
- **Today**: one small additional fact line in the same card, present only
  when `weather` is available: current temperature + a plain-language
  description composed from the Place-relative temperature band (falling
  back to a neutral, non-qualitative phrase when the baseline itself is
  `insufficient_baseline` -- never an absolute "cold"/"warm" claim without a
  Place-relative basis) plus cloud-cover/precipitation-state words, e.g.
  "62&deg;F, cooler than typical &middot; light snow." Absent entirely
  (not a loading/error state) when unavailable/disabled/not configured,
  matching `SolarContext`'s own "absence is silence, not an error banner"
  convention.
- **Visit detail**: one optional additional line in the existing
  "Conditions" card, read-only, same absence-safe omission rule as the
  existing sunrise/sunset facts.
- **Place Report / Bird Log**: `weather_associations` rendered with the
  exact same one-line, first-match, `meta-text` idiom
  `PlaceActivityReportPage.tsx` already uses for `habitat_associations` --
  no new visual pattern.
- Explicitly **not** built: a dedicated weather page, a chart, a forecast
  of any kind, an hourly/daily table.

## Explicitly not built (recorded, not by adjacency)

- Archive/ERA5 deep historical backfill and true multi-year climatology.
- Wind-band and cloud-cover statistical associations (fetched/stored/shown
  in Today's summary only, not run through `conditional_association`).
- A second weather provider or a user-facing provider-choice setting.
- Any forecast/future-dated fetch (the code path structurally never
  requests a date after "today"; there is no `forecast_days` parameter use
  beyond `0`/omitted for-current-hour reads).
- Habitat before/after change-event modeling composed with weather (Place /
  Yard Intelligence v2's own recorded gap; still not attempted here).
- Proactive report-window backfill (Phase 6, above).
- Export/research-grade weather redistribution beyond what the existing
  generic export already carries as ordinary Observation-adjacent context;
  no new Camtrap DP weather extension field.

## Validation plan

Tier 1: `weather_provider.py` parsing (normal/missing-field/malformed/
timeout/rate-limit/unsupported-location, using canned fixtures plus the
real captured response/error shapes from Phase 3's live probes, and one
opt-in real-network smoke test guarded the same way any other
real-network-dependent test in this repo would be); `condition_bands.py`
pure banding math; `weather_association.py` pure association wiring
(mirrors `test_habitat_association.py`); repository caching/idempotency/
basis-change/immutability/refresh-gate behavior; settings CRUD with the new
column; degraded-mode behavior (offline, disabled, not configured, stale).
Tier 2: `test_environmental_context.py` additions for the extended API
surface; Place Activity Report / Bird Log weather-association wiring;
frontend typecheck/build. Tier 3: full Core, justified by the schema bump
and `product_repository.py`/`schemas.py`/`main.py` changes.
