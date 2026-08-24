# Habitat & Phenology Foundation v1 Contract

## Purpose

Give MockingBird a small, durable, evidence-honest representation of the
habitat and seasonal biological context around a Place, named in
[roadmap.md](roadmap.md) "Remaining roadmap -- canonical sequence" #3
("Habitat & Phenology Foundation") and [product-doctrine.md](product-doctrine.md)
"Spatial doctrine" ("Do not force Habitat or Phenology architecture through
Zones").

This is **foundation** work: a durable Place habitat profile (a flexible
tag/fact model) and dated/interval phenology observations, both entirely
user-recorded. It is not the roadmap's full eventual layer -- see "Scope:
narrower than the roadmap's own sketch," below.

## Scope: narrower than the roadmap's own sketch

[roadmap.md](roadmap.md)'s own "Habitat & Phenology Foundation" entry
sketches a larger eventual layer: a `HabitatScene` (a comparable,
scheduled-sampling camera view with stable pose identity and
comparability/quality status) and a `HabitatObservation` domain driven by
image analyzers (PhenoVision, PlantCV-style measurements) producing
semantic phenomena (flowering, bud break, senescence, and so on) as
Inferred/provisional facts. This milestone's own governing brief
explicitly excludes all of that for v1 -- no automatic plant recognition,
no scheduled camera sampling, no new ML models, no remote sensing. What
ships here is the smaller, durable substrate underneath that eventual
layer: user-recorded habitat facts and user-recorded phenology
observations, with an `information_class` vocabulary that already reserves
room for a future `inferred_model` writer (see "Future compatibility,"
below) without redesigning either table. The `HabitatScene`/analyzer
layer, when it comes, is future work building *on* this substrate, not a
replacement for it.

## Governing doctrine

Same triad as everywhere else in this product (see "Measured, Inferred,
and Reviewed" in [product-doctrine.md](product-doctrine.md)), applied
honestly to a domain that, in v1, has exactly one writer: a human directly
describing their own Place. Neither table's `information_class` reuses
"measured" (no sensor), "inferred" (no model), or "reviewed" (no
antecedent proposal for a human to correct) -- see "Information class /
provenance," below, for the actual vocabulary and why. Human-reviewed
wildlife identification remains the only dataset-grade truth; nothing in
this milestone reads or writes `visits`, `events`, `review_labels`, or any
other wildlife-truth table (directly proven by
`test_habitat_phenology_never_touches_review_truth`).

## Design contract

### 1. Place

No `PlaceModel` exists or is added (unchanged from
[environmental-context-foundation-v1-contract.md](environmental-context-foundation-v1-contract.md)
"1. Place," which itself traces the same statement back to
[camera-source-multi-camera-maturity-v1-contract.md](camera-source-multi-camera-maturity-v1-contract.md)).
Both new tables' `source_id` column is nullable, mirroring
`EnvironmentalContextRecordModel.source_id` exactly: `NULL` means "applies
to the whole Place" (v1's only populated case); a real value is reserved
for a future per-camera habitat-scene association (see "Future
compatibility," below) without a schema change.

### 2. Information class / provenance

Every row in both tables carries two small string columns, mirroring
`EnvironmentalContextRecordModel.information_class`/`.provider_key`'s
two-column split (epistemic tier vs. specific method), but with this
domain's own vocabulary:

- `information_class` -- v1's only writer is a human directly describing
  their own Place, so every row is `"user_reported"`. This is deliberately
  a fourth value distinct from the wildlife Measured/Inferred/Reviewed
  triad (the same reasoning `EnvironmentalContextRecordModel` used to add
  `"derived"`): none of those three words honestly describe "a person
  typed a fact about their own yard" -- there is no sensor (not
  Measured), no model (not Inferred), and no antecedent proposal for a
  human to correct (not Reviewed, which the product-doctrine ties
  specifically to correcting a Detection Proposal). The column is a plain
  string, not a closed enum, reserving room for a future
  `"inferred_model"` (automatic plant recognition) or `"external_provider"`
  (an imported ecological dataset) without a schema change -- see "Future
  compatibility," below. No separate "review state" column exists: with
  nothing here a machine proposal awaiting human confirmation,
  `information_class` alone already says precisely what this is, without
  importing `ReviewLabel`/`reviewed_by_user_id` machinery this feature
  does not use.
- `provenance` -- v1's only value is `"user_manual_entry"`, the specific
  recording method (mirrors `provider_key`'s "plain string, not a growing
  enum" idiom).

Both are validated as a `Literal["user_reported"]` at the response-schema
layer (matching `SolarContext.information_class: Literal["derived"]`'s
"the response type reflects what can actually be returned today, not the
full future vocabulary" discipline) while staying a plain string in the
database.

### 3. Habitat facts: a flexible tag/fact model, not dozens of columns

`PlaceHabitatFactModel` (table `place_habitat_facts`) is one row per
recorded fact: `category` (a genuinely closed, small set --
`"setting"`/`"vegetation"`/`"feature"`, validated as a `Literal` at the
API layer, not a DB `CHECK` -- matching house style for other
string-vocabulary columns) and `label` (free text, with the frontend
offering a curated suggestion list per category -- a user is never
blocked from recording something the list did not anticipate). "Does this
Place have a water feature" is one row (`category="feature"`,
`label="Water feature"`), never a `has_water_feature` boolean column, so a
future new habitat concept needs no migration.

**Absence must not imply false.** There is no "confirmed absent" row for
every conceivable category/label -- only "recorded" or "not recorded."
Every reader (API and both frontend surfaces) presents a sparse/empty
result as "nothing recorded yet," never as "this Place lacks X." This is
how the governing brief's "users must be able to record 'unknown/not
specified'" is satisfied: by never manufacturing a negative claim, not by
adding an explicit "not present" sentinel row.

### 4. Phenology observations: dated, never silently "still current"

`PlacePhenologyObservationModel` (table `place_phenology_observations`)
is one row per dated/interval biological observation:
`subject_label` (free text -- a common name, a resource description like
"sunflower feeder," or anything else a user types; do not assume every
row is a plant species identification) and `phenomenon` (free text, with
a suggested list drawn from the governing brief's own examples:
flowering, fruiting/seed availability, leaf-out, leaf fall, emergence,
nesting-resource availability, feeder/resource availability).

`observed_start_date`/`observed_end_date` are plain `date` columns, never
`datetime` -- a phenology entry is a human-entered, day-granularity fact,
and a fabricated time-of-day would overclaim precision that was never
observed. `observed_end_date=NULL` means a single-date observation,
**exactly equivalent to `observed_end_date == observed_start_date`** for
every "is this currently applicable" purpose -- it never means "ongoing
indefinitely." This is the specific, deliberate mechanism that satisfies
the governing brief's own worked example precisely: "do not pretend an
observation from April is still current in August unless its interval
explicitly covers August." A single-date April entry's own "current"
window is exactly that one day; by August, comparing today's UTC calendar
date against `[April date, April date]` is honestly `False`, and the
observation reads as historical -- proven directly by
`test_classify_phenology_status_april_observation_is_not_current_in_august`.
A user who wants a fact to keep reading as current for longer must say so
explicitly with a real end date
(`test_classify_phenology_status_april_observation_with_explicit_august_interval_is_current`).

### 5. Temporal semantics: current / recent / past, always re-derived

`status` (`"current" | "recent" | "past"`) is **never persisted** --
mirrors `EnvironmentalContextRecordModel`'s "day/night classification is
never persisted per-Visit, always re-derived at read time" discipline
applied to phenology's own date-range shape. `mockingbird.habitat.
phenology.classify_phenology_status` computes it fresh on every read
against today's UTC calendar date:

- **current**: today falls within `[start_date, end_date or start_date]`.
- **recent**: concluded, but its effective end date falls within the last
  `DEFAULT_RECENT_WINDOW_DAYS` (14, a bounded, explicit grace window, never
  an open-ended "still probably relevant" guess) days before today.
- **past**: everything else, including a future-dated interval that has
  not started yet.

**No timezone invention.** "Today" is always `datetime.now(UTC).date()` --
the exact same UTC-calendar-date convention
`environmental-context-foundation-v1-contract.md`'s "Solar temporal
semantics acceptance closure" established for solar's own `for_date`,
applied here without that milestone's own astral-specific instant-pairing
complexity (there is no instant to bracket, only a plain date-range
containment check). This was directly, empirically exercised during
implementation: the sandbox's real local date and real UTC date disagreed
by one full day at the moment this was built (local `2026-08-23`, UTC
`2026-08-24`), and an ad hoc smoke test written against local `date.
today()` produced exactly the wrong classification until corrected to use
`datetime.now(UTC).date()` -- direct, real proof that this discipline is
load-bearing, not decorative.

Habitat facts have no such classification: they are durable/open-ended by
design (see "3. Habitat facts," above) and are always "current" simply by
existing.

## Data model

`PlaceHabitatFactModel` (table `place_habitat_facts`, schema 52):

- `id: str` (PK)
- `source_id: str | None` (FK `camera_sources.id`, nullable; `NULL` =
  Place-wide, v1's only populated case)
- `category: str` (`"setting"` | `"vegetation"` | `"feature"`)
- `label: str`
- `note: str | None`
- `information_class: str` (v1: always `"user_reported"`)
- `provenance: str` (v1: always `"user_manual_entry"`)
- `created_at: datetime`, `updated_at: datetime`

Index: non-unique, on `(source_id, category)`.

`PlacePhenologyObservationModel` (table `place_phenology_observations`,
schema 52):

- `id: str` (PK)
- `source_id: str | None` (same idiom as above)
- `subject_label: str`
- `phenomenon: str`
- `information_class: str`, `provenance: str` (same v1 values as above)
- `observed_start_date: date` (required)
- `observed_end_date: date | None` (nullable; `NULL` = single-date
  observation, never "ongoing indefinitely" -- see "4.," above)
- `note: str | None`
- `created_at: datetime`, `updated_at: datetime`

`__table_args__` includes a DB `CHECK` (`observed_end_date IS NULL OR
observed_end_date >= observed_start_date`) as defense-in-depth beneath the
identical Pydantic-layer validator. Index: non-unique, on `(source_id,
observed_start_date)`.

Both tables are purely additive (schema 51 -> 52, one migration function,
`Base.metadata.tables[...].create(bind=connection, checkfirst=True)`,
mirroring `_migrate_to_environmental_context_foundation` exactly): an
upgraded installation starts with zero rows in either table, identical to
a brand-new install. Neither table is ever joined against `visits`,
`events`, `review_labels`, or any other wildlife-truth table.

## Pure logic module

New `mockingbird.habitat.phenology` (new package `mockingbird/habitat/`,
parallel to `mockingbird/environment/`): `phenology_interval_covers`,
`classify_phenology_status`, `PhenologyStatusResult`,
`HABITAT_FACT_CATEGORIES`, `DEFAULT_RECENT_WINDOW_DAYS`,
`HABITAT_INFORMATION_CLASS`, `HABITAT_PROVENANCE_MANUAL_ENTRY`. No
database access, no network access -- directly unit-testable, mirroring
`mockingbird.environment.solar_context`'s own "small pure function"
shape.

## Repository surface

New `ProductRepository` methods (mirroring `create_zone`/`update_zone`/
`delete_zone`'s exact CRUD shape, and `update_environmental_context_
settings`'s "audit event recorded inside the same transaction" idiom):

- `list_place_habitat_facts() -> list[PlaceHabitatFact]`
- `add_place_habitat_fact(payload, *, acting_user) -> PlaceHabitatFact`
- `update_place_habitat_fact(fact_id, payload, *, acting_user) ->
  PlaceHabitatFact | None` (`None` = not found)
- `remove_place_habitat_fact(fact_id, *, acting_user) -> bool`
- `list_place_phenology_observations() -> list[PlacePhenologyObservation]`
  (full history, newest-observed-first, each with a freshly computed
  `status`)
- `add_place_phenology_observation(payload, *, acting_user) ->
  PlacePhenologyObservation`
- `update_place_phenology_observation(observation_id, payload, *,
  acting_user) -> PlacePhenologyObservation | None`
- `remove_place_phenology_observation(observation_id, *, acting_user) ->
  bool`
- `get_place_habitat_context() -> PlaceHabitatContext` (the compact
  current/recent bundle for a Today-style surface -- see "API surface,"
  below)

Every mutation records an audit event (`place_habitat.fact_added` /
`.fact_updated` / `.fact_removed`, `place_phenology.observation_added` /
`.observation_updated` / `.observation_removed`) inside the same
transaction as the mutation itself.

### The `clear_observed_end_date` convention

A plain `date | None` field on a PATCH-semantics update schema cannot
itself distinguish "omit this field" (leave unchanged) from "explicitly
set it to null" (clear it) -- the same ambiguity `PlaceHabitatFactUpdate.
note` resolves with an empty-string convention, which does not work for a
date-typed field. `PlacePhenologyObservationUpdate.clear_observed_end_
date: bool` is the explicit, separate mechanism: a real date sets it,
`None`/omitted leaves it unchanged, `clear_observed_end_date=True` clears
it back to "single-date observation." The schema layer rejects supplying
both `observed_end_date` and `clear_observed_end_date=True` in the same
request (a validation error, not a silent "one wins"); the repository
checks `clear_observed_end_date` first as the authoritative,
defense-in-depth enforcement point.

## API surface

- `GET /api/place/habitat`, `POST /api/place/habitat`,
  `PATCH /api/place/habitat/{fact_id}`, `DELETE /api/place/habitat/{fact_id}`
- `GET /api/place/phenology`, `POST /api/place/phenology`,
  `PATCH /api/place/phenology/{observation_id}`,
  `DELETE /api/place/phenology/{observation_id}`
- `GET /api/place/habitat-context` -- the compact, efficient "what's
  relevant right now" bundle (`habitat_facts`, `current_phenology`,
  `recent_phenology`; never contains a `"past"` entry), deliberately
  separate from the full list endpoints above -- mirrors exactly how `GET
  /api/place/environmental-context/today` is its own dedicated read
  rather than a field bolted onto a fuller report.

Every mutation requires an authenticated session (`current_user_or_401`),
matching the Zone/environmental-context-settings precedent. Unlike `GET
/api/settings/installation` (a narrow, documented exception letting a
signed-out sign-in screen show an installation name --
`mockingbird.api.auth._ALWAYS_PUBLIC_PATHS`), no route in this domain is
on that allowlist: reads also require a signed-in session, matching the
rest of this product's ordinary data (empirically confirmed during
implementation -- see `test_habitat_context_reads_also_require_
authentication`).

## Frontend surface

- `web/src/api/types.ts` / `web/src/api/client.ts` -- hand-mirrored
  interfaces and one `request<T>` arrow function per route, matching this
  file's existing no-codegen convention.
- `web/src/utils.ts` -- `formatCalendarDate` (a UTC-anchored, `timeZone:
  "UTC"`-formatted date-only display helper, deliberately distinct from
  `formatDateTime`/`formatTimeOfDay`: those format a real instant in the
  viewer's local timezone, which is correct for them but would risk
  displaying a bare `YYYY-MM-DD` phenology date as the *previous* calendar
  day for any negative-UTC-offset viewer -- the exact `new Date("YYYY-MM-
  DD")` pitfall `PlaceActivityReportPage.tsx`'s own `parseLocalDateInput`
  already documents and avoids for input parsing, applied here to
  display) and `phenologyDateRange` (shared by both surfaces below so they
  can never drift into presenting the same interval differently).
- **Dashboard (Today)**: a new sibling component,
  `HabitatPhenologyCard.tsx`, rendered directly from `DashboardPage.tsx`
  next to (not nested inside) `EnvironmentalContextCard` -- a genuinely
  independent fetch (`GET /api/place/habitat-context`) that must keep
  working, or stay quietly absent, regardless of whether the report or
  environmental context loaded. Calm view mode (habitat facts as small tag
  chips; current/recent phenology as a short list, a "Recently" pill
  distinguishing concluded-but-recent entries from currently-happening
  ones) with an inline edit-mode toggle for add/edit/remove -- both the
  "quiet contextual section" and the "settings editing" surface the
  governing brief asks for: there is no dedicated Place/settings page, and
  Environmental Context Foundation v1 already established the precedent
  of durable Place-level editing living inline here rather than behind a
  new page/nav entry.
- **Place Report page** (`PlaceActivityReportPage.tsx`, the closest
  existing "Place/history" surface): one small, deliberately
  period-*independent* read-only panel -- habitat facts (durable) plus the
  *full* phenology history (not filtered to the selected report period),
  each observation showing its own status pill (`Current`/`Recently`/no
  pill for `past`) and exact date range, so a historical entry never
  reads as ambiguously "maybe current." No second edit UI; editing lives
  on the Dashboard card only.
- Normal-user copy throughout: "Woodland edge," "Sunflower feeder,"
  "Azalea &middot; flowering." No `information_class`/`provenance`/schema
  jargon in either surface.

## Future compatibility

Both tables' `source_id`/`information_class` columns are already shaped
for, without requiring a schema change:

- A future per-camera `HabitatScene` association (`source_id` becomes
  populated instead of always `NULL`).
- A future automatic-plant-recognition analyzer
  (`information_class="inferred_model"`).
- A future external ecological dataset/import
  (`information_class="external_provider"`).
- Structured plant taxonomy layered on top of today's free-text
  `label`/`subject_label` (a future taxonomy-linking column, additive).
- Correlations with wildlife activity (a future read-only query joining
  this substrate against Place Activity Report facts by date/Place --
  this milestone deliberately does not build that; see "Explicitly
  deferred," below).

## Explicitly deferred

Everything the governing brief names as out of scope: a plant/ecology
database, automatic plant recognition, speculative phenology prediction,
remote sensing, weather expansion, generalized ecological scoring,
habitat-quality scores, wildlife prediction, a recommendations engine,
new external cloud dependencies, new ML models, audio, GIS complexity,
research-network features, and the roadmap's own larger
`HabitatScene`/scheduled-sampling/analyzer sketch (see "Scope," above).
Also not built: per-Source (as opposed to Place-wide) habitat/phenology
context (the schema supports it; nothing populates it yet); wildlife-
activity correlation (Biodiversity & Place Intelligence, once this
foundation has real history behind it); a dedicated Place/Settings page.

## Testing

Tier 1: pure temporal-status logic (interval containment; current/recent/
past classification including the exact April-not-current-in-August
boundary and its explicit-interval counter-case; the recent-window
boundary; future-dated intervals; negative-window rejection); habitat-fact
and phenology-observation repository CRUD (add/list/update/remove, note-
clearing via `""`, `clear_observed_end_date`, interval-validity guards,
Place-wide-only scoping, audit events, absence produces an empty list
never a fabricated claim); the compact current/recent context bundle
(including a direct proof a 200-day-old entry appears in neither current
nor recent); a direct proof this domain never touches wildlife review
truth; restart/reload persistence (a real repository close-and-reopen
against the same database file).

Tier 2: `test_persistence.py` schema-52 migration test (mirroring the
schema-51 template); a backup/restore round-trip test for both new
tables; the real HTTP surface (auth-required mutations *and* reads, 404s
for missing rows, 422s for invalid category/interval/conflicting-update
payloads); frontend `tsc --noEmit` and `vite build`.

Tier 3: full Core, justified by the same real cross-cutting surface
Environmental Context Foundation v1 used to justify its own full-Core run
(`models.py`, `database.py`, `product_repository.py`, `main.py`,
`schemas.py` all touched, plus a schema version bump).
