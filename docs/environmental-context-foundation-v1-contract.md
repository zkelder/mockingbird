# Environmental Context Foundation v1 Contract

## Purpose

Establish the durable, provider-neutral environmental-context substrate
named in [roadmap.md](roadmap.md) "Remaining roadmap -- canonical
sequence" #2 ("Environmental Context Foundation") and
[product-doctrine.md](product-doctrine.md) "External ecological context" /
"Place Intelligence", and prove it with one small, real, end-to-end
vertical slice: locally-derived sunrise/sunset and day/night context for a
Place, surfaced on the Today dashboard and on Visit detail.

This is architecture-plus-one-slice, not a weather platform. It does not
add a second provider, forecasting, causal claims, acoustics, MQTT/Home
Assistant, or any paid dependency. See "Explicitly deferred," below, for
everything this deliberately does not do yet.

## Why this exists now

[product-doctrine.md](product-doctrine.md) "External ecological context"
already names weather and sunrise/sunset as approved enrichment, with the
constraint that "External context must retain provenance and must never
become evidence that an animal actually appeared at the user's site."
[roadmap.md](roadmap.md) "Environmental Context Foundation" names the
target substrate shape (provider; Place/Source relation; observed/valid
time; measurement/value/unit; spatial resolution/distance; quality flags;
provenance; source version; cache/fetch time; license/attribution) and
names solar/time-relative context as the initial, highest-value slice.
Nothing in the current codebase implements any of this yet (confirmed by
repo-wide search: no weather/astral/sunrise/environmental code exists
before this milestone).

## Place coordinates: a deliberate, narrow exception to an existing privacy invariant

[research-conservation-export-contract.md](research-conservation-export-contract.md)
"Privacy" states, as a tested invariant: "MockingBird has no persisted
site/coordinate model (confirmed absent)" -- `CamtrapDpExportRequest.
latitude`/`.longitude` and `RecordedAudioAnalysisRequest.latitude`/
`.longitude` are accepted only per-call, never persisted, never inferred.

Real sunrise/sunset cannot be computed continuously, for every Visit,
without a coordinate stored *somewhere* durable -- asking a user to retype
coordinates per Visit is not a real product. This milestone therefore adds
exactly one new, narrow, opt-in, local-only coordinate setting, with a
deliberate mitigation the prior invariant did not need to consider because
it never persisted anything: **coordinates are rounded to one decimal
degree (~11 km) before they are ever written to disk.** At that
resolution, sunrise/sunset error is on the order of seconds to a couple of
minutes in virtually all inhabited latitudes -- far below the granularity
this feature presents (times to the nearest minute, plus a day/night
classification) -- while the stored value is no longer precise enough to
identify a residence. The column names (`coarse_latitude`/
`coarse_longitude`) encode this contract permanently, not just in a
comment.

This does **not** reverse the export/BirdNET precedent: those two request
schemas are untouched by this milestone, still require their own explicit
per-call value, and still never read the new setting automatically. A
future milestone could choose to let export optionally prefill from this
setting; this one deliberately does not, to keep this slice small and to
avoid quietly widening what export code paths can see. The "Privacy"
section of research-conservation-export-contract.md is amended with a
pointer to this doc rather than rewritten, so its own claims stay accurate
for the surface it actually governs (export/BirdNET), not overclaimed as a
repo-wide absolute.

## Design contract

### 1. Place

No `PlaceModel` exists or is added (unchanged from
[camera-source-multi-camera-maturity-v1-contract.md](camera-source-multi-camera-maturity-v1-contract.md):
"Place: unchanged -- the whole local installation. No `PlaceModel` exists
or is added"). Every new table's `source_id` column is nullable:
`NULL` means "applies to the whole Place" (today's only populated case);
a real value scopes a record to one Source/camera, for a future locally
attached per-camera sensor. This is the same idiom
`InstallationSettingsModel`/`StorageRetentionSettingsModel`/
`AppSetupStateModel` already use for "one row, one Host" settings, applied
to a new, narrower, single-purpose settings table rather than widened into
`InstallationSettingsModel` itself (whose own docstring scopes it to
"lightweight display metadata only").

### 2. Information class / provenance

Every environmental-context record carries `information_class`, one of:

- `measured_local` -- a locally attached sensor read a real physical
  quantity (not implemented yet; the column exists so a future sensor
  provider needs no schema change).
- `external_provider` -- retrieved from a public weather/environmental API
  (not implemented yet, same reasoning).
- `derived` -- computed deterministically from other durable inputs
  (Place coordinates + a timestamp, via a documented algorithm). This is
  what v1's solar provider always writes. `derived` is deliberately a
  third, distinct value from the wildlife Measured/Inferred/Reviewed
  triad in [product-doctrine.md](product-doctrine.md) "Measured, Inferred,
  and Reviewed" -- solar geometry has no confidence/uncertainty the way a
  species guess does, so reusing "Inferred" would overclaim a kind of
  doubt that does not apply, and reusing "Measured" would overclaim direct
  physical sensing that did not happen. `derived` says exactly what it is:
  an exact computation from known inputs.

This is a distinct vocabulary from wildlife review truth, on purpose, and
is validated as a `Literal` at the Pydantic layer (matching this
codebase's existing "keep provenance tiers as explicit sibling values with
a documented invariant" idiom, e.g. `PlaceActivityReportDigestSpeciesHighlight.
reason`) -- not a DB `CHECK` constraint, matching how `zone_type`/
`event_type`/`review_status` are validated (API layer, not schema layer).

### 3. Source / provider

Provider identity is a plain string (`provider_key`), not a growing enum
-- matching `_PROVIDER_COMPATIBILITY`'s flat-dict idiom in
`mockingbird.observation.provider_compatibility`, not the `SourceProviderKind`
`elif`-chain that module's own docstring calls out as a symptom to avoid
repeating. v1 defines exactly one: `"solar_local"`.

This is intentionally its own small family, not a member of
`SOURCE_PROVIDER_DEFINITIONS`/`classify_provider_compatibility` (the
camera/live-playback maturity scheme) -- environmental context has no
Stream, no playback, no Zone-editing capability, and forcing it through
that vocabulary would add dead fields. It instead mirrors the closer
analog, the species-adapter family (`bioclip_adapter.py`/
`birdnet_adapter.py`): a plain-string status vocabulary
(`"available"`/`"not_configured"`/`"unavailable"`), a frozen status
dataclass, and a status function that never raises. Unlike BioCLIP/BirdNET,
v1's solar provider has no optional heavy runtime dependency to guard
against (`astral` is a small, pure-Python, Apache-2.0, near-zero-dependency
library -- confirmed via wheel inspection: only conditional stdlib
backports for old Python / Windows `tzdata`, nothing else -- so it is a
plain core dependency, not an optional extra the way `open-clip-torch`/
`birdnetlib` are). `"unavailable"` is reserved for a future provider that
does have a real dependency-availability question; v1's own status is
either `"not_configured"` (no coordinates set) or `"available"`.

### 4. Temporal semantics

Every record has:

- `observed_at` (required) -- the instant (or interval start) the fact
  describes. For v1's `sunrise`/`sunset` metrics this is the exact
  computed instant.
- `observed_at_end` (nullable) -- interval end; `NULL` means
  instantaneous. v1 never populates this (sunrise/sunset are instants),
  but the column exists for a future daily min/max-style aggregate without
  a schema change.
- `retrieved_at` (required) -- when MockingBird computed or fetched this
  record, distinct from `observed_at`. For v1 these are computed in the
  same call, but the distinction matters as soon as an external provider
  or historical backfill exists.

A Visit has no timestamp column of its own (`VisitModel`/`DetectionModel`
carry none). This milestone associates environmental context with a Visit
using **`StreamVisitSummary.activity_started_at`** -- the same field
`place_activity_report_adapter.py` already treats as canonical for report
math (`VisitFact.activity_started_at`), not `captured_at` (the
evidence-grounded display instant, which can differ). Reusing the existing
canonical field, rather than introducing a second notion of "when a Visit
happened," keeps this slice consistent with the reporting pipeline it will
eventually feed.

Day/night classification is **never persisted per-Visit**. Only the daily
`sunrise`/`sunset` facts are persisted (bounded: at most 2 rows per
calendar day for the life of an installation); "was it daylight when this
Visit happened" is computed at read time by comparing the Visit's instant
against the persisted (or just-computed-and-cached) sunrise/sunset for the
relevant date(s). This avoids an unbounded row per Visit and keeps the
classification honestly re-derivable rather than frozen at write time.

### 5. Evidence / lineage

`basis_latitude`/`basis_longitude` snapshot the coordinates actually used
to compute one record, distinct from the live
`environmental_context_settings` value -- so a record remains
self-describing/auditable even if the user later edits their configured
location. `provenance_json` is one small, fixed-shape, bounded JSON object
(algorithm name/version, twilight definition used) -- matching
`MediaAssetModel.geometry_attribution_json`'s "one nullable TEXT column,
one fixed-shape object, never a growing list" precedent, not
`CounterfactualLedger`'s in-memory bounded-FIFO shape (that pattern is for
high-volume diagnostic data; environmental context is at most a couple of
rows a day and belongs in the durable product database).
`provenance_schema_version` (matching `BioClipIdentificationAttemptModel`'s
identical column) lets that JSON shape evolve later without a table
migration. Never a raw provider response dump -- matching
`AuditLogEntryModel.metadata_json`'s explicit "never a raw request-body
dump" discipline, extended here to "never a raw provider-response dump,"
so a future external-provider adapter cannot leak an API key or
unbounded payload into this table by accident.

Idempotency caveat, documented rather than silently assumed: a DB
`UNIQUE` constraint including nullable `source_id` would not actually
de-duplicate Place-level (`source_id IS NULL`) rows under standard SQL
NULL semantics (confirmed: SQLite treats every `NULL` as distinct from
every other `NULL` in a unique index, same as ANSI SQL). Idempotency for
"one sunrise/sunset per calendar day" is therefore enforced at the
repository layer (check-then-insert-or-reuse inside one transaction), not
by a DB constraint; a non-unique lookup index still exists for query
performance. Consumers of this table should tolerate (never assume
impossible) a rare duplicate row for the same day and prefer the most
recently created one -- documented here rather than silently relied upon.

### 6. Local-first behavior

Nothing in this milestone requires internet access. The only new
dependency (`astral`) is a local computation library, not a network
client. When coordinates are unset, every new API returns an explicit
"unavailable, not configured" result -- never a fabricated or
interpolated value, never an exception, never a degraded core-monitoring
path. Wildlife detection, review, Visit assembly, and export are
untouched by this milestone and function identically with zero
environmental data configured.

## Solar temporal semantics acceptance closure

A follow-up closure corrected a real error in this milestone's *first*
version of this document and its code: it described `astral` as
"mislabeling" a sunset's calendar date by a day when called with
`tzinfo=UTC` for a longitude far from Greenwich, and worked around that
supposed defect with a longitude-derived pseudo-timezone (`_approximate_
local_offset`/`approximate_local_date`) passed to `astral` as if it were
the Place's real civil time.

**That framing was wrong on two counts, confirmed by direct inspection of
`astral`'s own behavior, not merely reasoned about:**

1. `astral.sun.sun`'s `date` argument is interpreted *in the timezone
   passed as `tzinfo`*. Passing `tzinfo=UTC` asks, correctly, for
   "whichever sunrise/sunset instant falls within this UTC calendar day" --
   a real, well-defined, unambiguous pair of instants. A sunset instant
   landing on a UTC calendar date a naive reader might not expect (for a
   longitude far from Greenwich) is not a bug and not a mislabeling; it is
   exactly what "the sunset associated with this UTC day" means for that
   longitude. Confirmed directly: for New York, `date=2026-06-21,
   tzinfo=UTC` gives `sunrise=2026-06-21 09:25 UTC` and `sunset=2026-06-21
   00:30 UTC` -- both instants genuinely fall within UTC calendar day
   2026-06-21 itself, exactly as asked.
2. A longitude-derived offset is not a real timezone -- no DST, no
   political boundary, no legal standing -- and presenting one as if it
   resolved "the Place's local date" was itself the actual defect, not a
   workaround for one.

**The corrected model.** Day/night classification and "today's"
sunrise/sunset depend on exactly two inputs -- Place coordinates and the
UTC instant being evaluated -- and never on any timezone concept, real or
approximate:

- `compute_daily_solar_facts(latitude, longitude, for_date)` is unchanged
  in shape, but its contract is now stated precisely: it returns the
  sunrise/sunset that fall within *UTC calendar date* `for_date` (plain
  `tzinfo=UTC`, nothing else). Both instants are guaranteed to carry that
  same UTC date (confirmed directly, east and west of Greenwich alike),
  but the pair is **not** guaranteed to be a chronologically sane
  [sunrise, sunset) window by itself -- for a longitude far enough from
  Greenwich in *either* direction, `sunset_at` can carry an earlier
  time-of-day than `sunrise_at` on that same date (each is independently
  "whichever instance of that event falls in this UTC day"; the two need
  not belong to the same real day/night cycle).
- `find_daylight_window(candidates, instant)` (new) is the one place a
  usable [sunrise_at, sunset_at) pair is ever constructed: given the
  `DailySolarFacts` for `instant`'s own UTC calendar date and the day
  immediately before and after it (`candidate_dates_for_window`, new --
  three dates always suffice to bracket any instant, confirmed by direct
  hourly-resolution sweep across multiple hemispheres/longitudes/seasons,
  not merely reasoned about), it finds the most recent sunrise at or
  before `instant` and pairs it with the next sunset after that sunrise --
  never by pairing one date's own two fields. `classify_daylight_state`
  is unchanged (a plain three-argument compare) but is now always fed a
  window `find_daylight_window` actually vouches for.
- The repository's `_get_daylight_window_in_session` is the one place
  this fetch-three-candidate-dates-then-bracket logic runs against the
  cache (`_get_or_compute_daily_solar_facts_in_session`, now returning
  `DailySolarFacts` per date rather than a bare tuple): caching 3 dates
  per lookup (6 rows) instead of 1 (2 rows) is the direct, accepted cost
  of removing the pseudo-timezone shortcut -- still fully bounded (a fixed
  small multiple of distinct calendar dates ever queried, not unbounded
  per-Visit growth).
- `for_date` on `EnvironmentalContextRecordModel` keeps its column and its
  role as the cache lookup key, but its definition is now stated
  precisely: **the UTC calendar date passed to `astral.sun.sun` with
  `tzinfo=UTC`** -- never a claim about the Place's local/civil date. The
  same correction applies to `PlaceEnvironmentalContext.for_date`: it is
  the UTC calendar date "now" falls on, not a claim that the returned
  sunrise/sunset both "belong" to that date (the window can legitimately
  span two UTC dates).
- No civil/legal timezone model was added. No timezone configuration or
  selection UX was added to the product. `find_daylight_window` structurally
  cannot regress into "correct in one season, wrong in another because of
  an unstated DST assumption," because no DST concept, and no timezone
  concept of any kind, appears anywhere in the classification path --
  directly proven by a test that classifies the same kind of instant
  (mid-morning daylight) in both January and July and confirms identical,
  correct behavior with no season-specific code path to regress.
- The UI was reviewed and needed no change: `formatTimeOfDay` already
  renders the real, exact UTC instant returned by the backend in the
  *viewer's own real system timezone* (the same `Intl.DateTimeFormat`
  convention every other timestamp in this app already uses) -- that was
  never the dishonest part. The word "local" in the product copy ("local
  sunrise/sunset," "local device") means "at this geographic location,"
  the ordinary English sense, not a claim about civil time, and was left
  as-is.

## Data model

`EnvironmentalContextSettingsModel` (table `environmental_context_settings`,
schema 51) -- singleton (`singleton_id` PK = 1, same idiom as
`InstallationSettingsModel`):

- `coarse_latitude: float | None`, `coarse_longitude: float | None` --
  always rounded to 1 decimal degree before persisting (enforced in the
  repository setter, defense-in-depth beyond the Pydantic-layer rounding).
- `updated_at: datetime`

`EnvironmentalContextRecordModel` (table `environmental_context_records`,
schema 51):

- `id: str` (uuid, PK)
- `source_id: str | None` (FK `camera_sources.id`, nullable; `NULL` =
  Place-wide, v1's only populated case)
- `provider_key: str` (v1: always `"solar_local"`)
- `information_class: str` (v1: always `"derived"`)
- `metric: str` (v1: `"sunrise"` | `"sunset"`)
- `value_numeric: float | None`, `value_text: str | None`, `unit: str | None`
  (all `NULL` for v1's instant-valued metrics -- `observed_at` alone
  carries the fact; reserved for future numeric/categorical metrics, e.g.
  temperature would populate `value_numeric`/`unit`)
- `observed_at: datetime` (required), `observed_at_end: datetime | None`
- `for_date: date | None` -- the *UTC calendar date* passed to
  `astral.sun.sun` as `date` (with `tzinfo=timezone.utc`) to produce this
  row -- never a claim about the Place's local/civil date (see "Solar
  temporal semantics acceptance closure," below, for why that distinction
  matters and what this milestone originally got wrong about it). The
  lookup key for "the sunrise/sunset facts for this UTC date," computed
  once at write time. A single row's `for_date` does not by itself imply
  a coherent [sunrise, sunset) window -- see `find_daylight_window`.
  `NULL` for a future metric with no natural single day.
- `retrieved_at: datetime` (required)
- `basis_latitude: float | None`, `basis_longitude: float | None`
- `provenance_json: str | None` (Text; small fixed-shape object)
- `provenance_schema_version: int` (`>= 1`, DB `CHECK`, matching
  `BioClipIdentificationAttemptModel`'s identical constraint)
- `created_at: datetime`

Index: non-unique, on `(source_id, provider_key, metric, for_date)` for
cache lookup. No DB-level vocabulary `CHECK` on `information_class`/
`metric`/`provider_key` (matches house style for other string-vocabulary
columns; validated at the Pydantic/API layer instead).

## Provider: local solar context

New module `mockingbird.environment.solar_context` (new package
`mockingbird/environment/`, parallel to `mockingbird/species/`):

- `SOLAR_PROVIDER_KEY = "solar_local"`
- `get_solar_context_status(latitude, longitude) -> SolarContextStatus`
  (never raises; `"not_configured"` when either coordinate is `None`,
  otherwise `"available"`)
- `compute_daily_solar_facts(latitude, longitude, for_date) ->
  DailySolarFacts` (the sunrise/sunset within *UTC calendar date*
  `for_date`, both UTC-aware; plain `astral.sun.sun(..., tzinfo=UTC)`, no
  other timezone concept -- see "Solar temporal semantics acceptance
  closure," below, for why this function's own single-date pair is not
  always a self-consistent window)
- `classify_daylight_state(instant, sunrise_at, sunset_at) ->
  Literal["day", "night"]` (a plain three-argument compare; correct only
  when fed a genuinely bracketing pair)
- `candidate_dates_for_window(instant) -> tuple[date, date, date]` (the
  three UTC calendar dates -- `instant`'s own plus the one immediately
  before and after -- that always suffice to bracket it)
- `find_daylight_window(candidates, instant) -> tuple[datetime, datetime]
  | None` (the actual [sunrise_at, sunset_at) window for `instant`,
  depending only on the supplied facts and `instant` -- no timezone
  concept anywhere)

v1 deliberately implements day/night only, not civil/nautical/astronomical
twilight bands -- the roadmap's "twilight" bullet is explicitly deferred
(see "Explicitly deferred," below) to keep this slice's UI vocabulary to
exactly two, unambiguous words.

## Repository surface

New `ProductRepository` methods (mirroring `get_installation_settings`/
`update_installation_settings`'s exact shape, including the audit-log
call):

- `get_environmental_context_settings() -> EnvironmentalContextSettings`
- `update_environmental_context_settings(payload, *, acting_user) ->
  EnvironmentalContextSettings` (rounds to 1 decimal; writes an
  `settings.environmental_context_updated` audit entry)
- `_get_or_compute_daily_solar_facts_in_session(session, *, now, for_date,
  latitude, longitude) -> solar_context.DailySolarFacts | None` (private,
  session-scoped, single-*UTC-calendar-date* cacheable primitive: look up
  existing rows for that date; if absent, compute and insert one
  sunrise/sunset pair and return it; `None` only for a genuine polar
  day/night UTC date)
- `_get_daylight_window_in_session(session, *, now, instant, latitude,
  longitude) -> tuple[datetime, datetime] | None` (private: fetches, via
  the primitive above, the three UTC calendar dates `solar_context.
  candidate_dates_for_window(instant)` names, then hands whichever did not
  hit a polar-night gap to `solar_context.find_daylight_window` -- the one
  place a usable window is produced; depends only on coordinates and
  `instant`)
- `get_visit_environmental_context(visit_id) -> VisitEnvironmentalContext |
  None` (`None` means the Visit itself does not exist -- the API layer
  maps that to 404; resolves the Visit's `activity_started_at` via the
  existing `_stream_visit_summary_from_models` path, then calls the
  window primitive above with that instant; absence-safe throughout when
  no location is configured)
- `get_place_environmental_context_today() -> PlaceEnvironmentalContext`
  (same window primitive, called with `datetime.now(UTC)` as the instant,
  for the dashboard)

## API surface

- `GET /api/settings/environmental-context`
- `PUT /api/settings/environmental-context`
- `GET /api/visits/{visit_id}/environmental-context`
- `GET /api/place/environmental-context/today`

The Today-context endpoint is deliberately separate from
`place_activity_report`'s response, not a new field bolted onto it:
`place_activity_report.py`'s own contract states it is "a pure computation
layer" over reviewed/provisional Visit truth with "no thresholds, no
baselines" -- adding environmental data there would blur that boundary.
The frontend fetches both independently (already the existing
`Promise.all` pattern in `DashboardPage.refreshDashboard`), which is what
"environmental context is additive" means concretely here: a genuinely
separate fetch, not a modification of an existing, already-accepted
contract.

## Frontend surface

- `web/src/api/types.ts` -- hand-mirrored interfaces (this file has no
  codegen; convention is a `// Mirrors api.schemas.X` comment).
- `web/src/api/client.ts` -- one `request<T>(...)` arrow function per new
  route, alongside the existing visit-scoped calls.
- Today dashboard: a new small, self-contained sibling component
  (`EnvironmentalContextCard.tsx`), rendered directly from
  `DashboardPage.tsx` next to (not nested inside) `TodayReportPanel` --
  that component's own early-return states (loading/unavailable report)
  are specifically about Place Activity Report truth, and environmental
  context is a genuinely independent fetch that must keep working (or stay
  quietly absent) regardless of whether the report itself loaded. Shows
  one small, absence-safe fact row ("Sunrise 6:42 AM &middot; Sunset 7:58
  PM &middot; Daylight/Night") when configured; when not configured, a
  single muted prompt with an inline "Set approximate location" affordance
  (two number inputs, clearly labeled "used only to compute local
  sunrise/sunset on this device; rounded to ~11 km; never shared or
  exported automatically"). This is the only place coordinates are
  entered -- no new page, no new nav entry.
- Visit detail (`VisitDetailPage.tsx`): one small "Conditions" card in the
  existing `case-summary-grid`, showing a Daylight/Night badge (mirroring
  the existing `identificationBadge`/`StatusPill` shape) plus that day's
  sunrise/sunset. Omitted entirely (not a "loading"/error state) when
  unavailable -- consistent with other optional per-Visit facts.
- Language discipline: "Daylight" / "Night" as classification labels,
  sunrise/sunset as plain times. Never "the bird appeared because...".
  Never a bare confidence-free number presented as more precise than it
  is (times shown to the nearest minute; coordinates never shown back to
  the user more precisely than the rounded value actually stored).

## Explicitly deferred

Not built in this milestone (candidates for a later slice, each requiring
its own scoping): temperature/precipitation/humidity/wind/pressure/cloud
cover; any external weather provider/API; civil/nautical/astronomical
twilight bands; moon phase/context; locally attached sensor ingestion
(MQTT/HTTP/import); per-Source (as opposed to Place-wide) environmental
context; quality-flag/spatial-distance columns (meaningful once a
non-exact provider exists; would be dead weight with only an exact local
computation); license/attribution columns (no licensed data feed exists
yet); letting research export or BirdNET species-range narrowing
auto-fill from the new setting; any species-activity-vs-weather analytics
(Phase 5 of the governing milestone brief explicitly excludes this).

## Testing

Tier 1: model/provenance round-trip; `derived`/`measured_local`/
`external_provider` stay distinct; `compute_daily_solar_facts`'s exact UTC-
calendar-date contract (including that its own sunrise/sunset pair is not
always self-ordered, verified directly for both west- and east-of-
Greenwich coordinates); `find_daylight_window`/`candidate_dates_for_window`
against western-longitude (sunset crosses UTC midnight) and eastern-
longitude counterparts, exact sunrise/sunset boundary instants, and an
hourly-resolution 72-hour sweep across four hemispheres/longitudes proving
exactly the expected number of day/night transitions with no hidden
failure mode; a direct proof that classification of an unambiguously-
daylight UTC instant is identical in January and July, since no season or
timezone concept exists anywhere in the classification path to regress;
coordinate rounding (both schema-layer and repository-layer, plus the
~11 km accuracy claim itself, numerically verified); absence behavior (no
coordinates configured -> every new API returns "unavailable", never
raises, never fabricates); polar-night handling (a genuine no-sunrise/
sunset UTC date is "unavailable," never a crash); repository idempotency
(calling `get_place_environmental_context_today` twice does not create
duplicate rows -- 6 bounded rows across the 3 bracketing UTC dates, not
2, and not unbounded); `activity_started_at` association resolves
correctly; a direct proof that reading environmental context never
mutates a Visit's review truth; API request/response round trip for all
four routes, including authentication and validation failure cases.

Tier 2: `test_persistence.py` schema-51 migration test (mirroring the
schema-45/48 templates); a backup/restore round-trip test for the new
tables; existing Visit-detail/dashboard tests remain green with the new,
optional fields present but unset; frontend `typecheck`/build.

Tier 3: full Core, justified by real cross-cutting surface (`models.py`,
`database.py`, `product_repository.py`, `main.py`, `schemas.py` all
touched, plus a schema version bump).
