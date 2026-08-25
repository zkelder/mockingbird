# Place Features & Habitat Change v2 Contract

## Purpose

Give MockingBird a first-class, structured representation of important
physical features around a Place (feeders, water features, nest boxes,
habitat patches) and of intentional or observed changes to them, named in
[roadmap.md](roadmap.md) "4. Biodiversity & Place Intelligence" (recorded
future dependency: "a structured Feeder/water-feature entity") and in
[release-execution-state.md](release-execution-state.md) §3 ("a habitat
before/after change-event data model"). This closes the single gap
[habitat-association.md's own docstring](../src/mockingbird/analytics/habitat_association.py)
names outright: *"a true 'wildlife activity changed after this reviewed
habitat change' comparison is not built here"* -- confirmed absent
everywhere in this codebase before this milestone by direct grep for
`change_event`/`before_state`/`after_state`, re-confirmed independently
this session.

This is a **product-capability** milestone, not release closure, field
acceptance, or a perception/model campaign -- see the governing brief's
"CURRENT DEVELOPMENT PHASE".

## Archaeology summary

See [place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)
"Archaeology" for the full gap table. In short: `PlaceHabitatFactModel`
(flexible tag/fact, durable/open-ended, no identity/lifecycle) and
`PlacePhenologyObservationModel` (dated *interval*, built for recurring
biological phenomena) both predate this milestone and remain unchanged and
fully separate. Neither can honestly represent a discrete, typed,
one-time change with a durable identity a comparison can anchor on. No
`PlaceModel`, no `AreaModel` (confirmed: "Area" is prose-only in the
spatial-doctrine hierarchy, never a table). `Zone`/`Source`/`Stream` remain
the only real spatial primitives.

## Data model

### `PlaceFeatureModel` (table `place_features`, schema 55)

Current mutable state only -- see "Feature state vs change history," below,
for why this is *not* the durable timeline.

- `id: str` (PK)
- `feature_type: str` -- closed vocabulary at the API layer
  (`mockingbird.habitat.place_feature.PlaceFeatureType`; see "Feature
  taxonomy," below), plain string in the DB, matching `zone_type`/
  `category` house style
- `name: str` -- free text ("Sunflower feeder")
- `note: str | None`
- `is_active: bool` -- a lightweight, reversible toggle; **not** the same
  act as recording a dated `"removed"` change event
- `installed_date: date | None` -- best-known start date, day-granularity
- `removed_date: date | None` -- set only as a side effect of recording a
  `"removed"` change event, never directly PATCH-editable
- `source_id: str | None` (FK `camera_sources.id`, nullable)
- `zone_id: str | None` (FK `zones.id`, nullable) -- finer-grained,
  preferred when set; its own Stream's Source is authoritative over any
  independently-supplied `source_id`
- `feeder_food_type: str | None` -- small, bounded, feeder-specific; no DB
  constraint ties it to `feature_type`
- `information_class: str` (always `"reviewed"`), `provenance: str`
  (always `"user_manual_entry"`) -- mirrors `PlaceHabitatFactModel` exactly
- `actor_user_id: str | None` (FK `users.id`, nullable) -- **new beyond**
  the Habitat & Phenology v1 precedent (which relies on the audit log
  alone); the governing brief explicitly requires durable on-row "reviewed
  actor provenance," so this reuses `ReviewLabelModel.reviewed_by_user_id`'s
  exact idiom instead: populated only by the authenticated handler from
  the signed-in session, never trusted from client payload
- `created_at`, `updated_at: datetime`

Indexes: `(source_id, is_active)`, `(zone_id)`.

### `PlaceFeatureChangeEventModel` (table `place_feature_change_events`,
schema 55)

The durable, append-in-spirit timeline. One row per recorded change.

- `id: str` (PK)
- `feature_id: str | None` (FK `place_features.id`, nullable) -- nullable
  so a Place-level habitat change ("changed mowing practice") can be
  recorded without inventing a Feature row it does not need
- `event_type: str` -- closed vocabulary (see "Change-event vocabulary,"
  below)
- `effective_date: date` -- required, day-granularity (mirrors
  `PlacePhenologyObservationModel.observed_start_date`'s exact discipline)
- `note: str | None`
- `prior_value: str | None`, `new_value: str | None` -- a small, bounded
  free-text pair, not a polymorphic JSON blob
- `information_class`/`provenance`/`actor_user_id` -- mirror
  `PlaceFeatureModel` exactly
- `created_at`, `updated_at: datetime`

Index: `(feature_id, effective_date)`.

Both tables are purely additive (schema 54 -> 55, one migration function,
`Base.metadata.tables[...].create(bind=connection, checkfirst=True)`,
mirroring `_migrate_to_habitat_phenology_foundation` exactly): an upgraded
installation starts with zero Features and zero change events, identical
to a brand-new install. Neither table is ever joined against `visits`,
`events`, `review_labels`, or any other wildlife-truth table.

## Feature taxonomy (Phase 3)

`PlaceFeatureType = "feeder" | "water" | "nest_box" | "vegetation_patch" |
"structure" | "habitat_area" | "other"`.

Deliberately bounded: ordinary yard vocabulary the governing brief itself
uses ("Back hedge," "Brush pile," "Native flower bed") is carried by the
free-text `name` field -- the same "category is closed, label is free
text" split `PlaceHabitatFactModel` already established -- not by growing
this list. `"other"` is the explicit escape hatch. No sub-taxonomy, no
taxonomy editor.

## Change-event vocabulary (Phase 4)

`PlaceFeatureChangeEventType = "added" | "removed" | "moved" | "modified" |
"replenished" | "food_changed" | "vegetation_changed" | "other"`.

Bounded from the governing brief's longer candidate list -- `"habitat_
restored"` deliberately folds into `"modified"`/`"vegetation_changed"`
plus a free-text note ("do not expose all of these unless useful").

## Feature state vs change history (Phase 5) -- dual-write, not event
sourcing

Current feature state (`is_active`, `feeder_food_type`, `removed_date`)
lives directly on `PlaceFeatureModel` and is corrected in place -- **not**
derived by replaying every event on every read. Recording certain events
*also* updates the Feature row's own current-state columns, in the same
transaction (`ProductRepository._recompute_feature_derived_state`):

- `event_type="removed"` -> `is_active=False`, `removed_date` = that
  event's own `effective_date` (the *latest* such event, if more than
  one)
- `event_type="food_changed"` with `new_value` set -> `feeder_food_type` =
  that event's `new_value` (again, the latest)
- Feature **creation** with `installed_date` set -> auto-seeds one
  `event_type="added"` change event at that date, in the same
  transaction, so the timeline always starts coherently without a second
  user action

**Deliberately one-directional for `"removed"`:** the presence of any
`"removed"` event pushes `is_active` to `False`; the *absence* of one --
including immediately after the only such event is deleted or retyped
away -- never automatically pushes `is_active` back to `True`. Silently
reactivating a Feature as a side effect of an unrelated correction would
be a more surprising outcome than leaving the previous state alone; a user
who really did reactivate the Feature says so directly via an ordinary
edit. `feeder_food_type` has no such asymmetry: it always reflects
whichever `"food_changed"` event is currently latest by `effective_date`
(a correction to an event's date can change which one that is), or the
Feature's own last directly-edited value if none remain.

This mirrors a shape already proven in this exact codebase --
`CameraConfigurationRevisionModel` (bounded revision history) sitting
alongside live `StreamModel`/`CameraSourceModel` current-state rows -- not
a new architectural pattern. Full event sourcing (deriving *all* current
state purely by replaying the event table) is not justified: most
current-state fields (`name`, `note`, association) have no corresponding
event type at all and are simply PATCHed, exactly like
`PlaceHabitatFactModel` today.

## Camera / Zone association (Phase 6)

A single optional `zone_id` (preferred/finer) or `source_id` (coarser) per
Feature -- not a many-to-many join table. `zone_id`, when given, is
authoritative: its own Stream's Source always wins over an independently-
supplied `source_id` rather than trusting the two as separately-correct
client facts that could disagree. Update semantics: a non-empty `zone_id`
always wins and re-derives `source_id` fresh from that Zone; a bare
non-empty `source_id` (no `zone_id` in the same request) sets the Source
and clears any existing Zone link, so a Feature can never hold an
inconsistent `(source_id, zone_id)` pair; `""` explicitly clears (clearing
`source_id` also clears `zone_id`).

**Documented v2 limitation (Phase 28):** a Feature visible from two
cameras can only be linked to one for now; its yield/before-after figures
are scoped to that one linked view. Recorded as a future opportunity, not
built by adjacency -- a join table plus UI would be real added complexity
for a case with no confirmed real demand yet.

## Correction model (Phase 22/23) -- PATCH-in-place, not append-only-
superseding

Both new tables are PATCH-corrected in place, mirroring
`PlaceHabitatFactModel`/`PlacePhenologyObservationModel`'s identical
precedent -- **not** `ReviewLabel`'s heavier append-only-superseding-with-
visible-`correction_history` machinery. This was a deliberate choice
between two real, already-proven patterns in this codebase (see
"Archaeology" in the report for the full comparison): a Place Feature's
install date or a change event's date/note is not dataset-grade wildlife
identification truth, and does not need `expected_state_token`/
`idempotency_key` optimistic concurrency or a visible `is_current`/
`is_authoritative` disclosure UI to be trustworthy.

This is safe *because* every derived comparison this milestone builds
(`mockingbird.analytics.feature_change_comparison`) is computed **fresh at
read time, never persisted or cached** -- mirroring `PhenologyStatus`'s
identical "classification is derived, not frozen at write time"
discipline. A correction to a Feature's association or a change event's
date/type is reflected on the very next `GET .../detail` call with no
separate invalidation step to get wrong -- directly proven by
`test_correcting_change_event_date_changes_comparison_on_next_read` and
`test_correcting_food_changed_event_date_reorders_which_is_latest`.

Deleting a change event is an ordinary, always-available correction
("removes an incorrect event" -- Phase 22). Hard-deleting a *Feature* is
different: allowed only when it has zero recorded change events
(`PlaceFeatureHasHistoryError`, mapped to HTTP 409) -- "constrain [hard
deletion] to safe cases with no historical references" (Phase 7). A
Feature with history should be deactivated instead, which preserves it and
every change event referencing it.

## Information class (Phase 23)

Human-entered Feature/change facts are `information_class="reviewed"`.
Every derived comparison (`PlaceFeatureAssociation`) carries **no**
`information_class` field at all -- matching the existing precedent that
none of `habitat_association.py`'s, `weather_association.py`'s, or any
other analytics-layer output dataclass in this product carries one
either (`information_class` is exclusively a storage-model field, set at
write time on genuinely reviewed/measured/inferred fact tables). A
derived "activity was higher after this change" statement is never
labeled `"reviewed"` merely because the underlying change event was --
doctrine's "Do not label a derived statement... as Reviewed merely
because the feeder change itself was reviewed," satisfied structurally by
never giving the derived type a field that could be misread that way.

## Before/after analysis (Phases 10/11/19)

`mockingbird.analytics.feature_change_comparison.compute_feature_change_
comparison` -- a thin date-set builder around `conditional_association.
compute_conditional_association`, **no new statistical primitive**. See
that module's own docstring for the full mechanism.

**Window selection:** try 7 days each side first, escalate to 14 then 30
only if the smaller window's usable dates cannot clear `conditional_
association`'s own default floor (5 usable days each side -- reused
verbatim, never a new number). A window is only attempted once its entire
post-period has already elapsed relative to `today`.

**Maturity vocabulary** (`FeatureComparisonMaturity`): `"too_soon"`
(not even the smallest window's post-period has elapsed yet),
`"insufficient_coverage"` (enough time has elapsed, but even the largest
window failed the usable-day floor -- a genuinely different, differently
-actionable fact from "too soon"), `"early_signal"` (only the largest,
30-day window cleared the floor), `"comparable"` (the smallest, freshest
window already cleared it). No literal "too soon to tell"/"early signal"
vocabulary existed anywhere in this codebase before this milestone
(confirmed by grep); this mirrors the *style* of existing tiers
(`BaselineMaturity`, `SeasonalPatternStatus`) without reusing an unrelated
one.

**Scope:** `usable_dates`/`presence_dates` are scoped to exactly the
Feature's own association -- its Zone only, when set, else every Visit
across its linked Source's Streams. A Feature with **no** camera/Zone
association at all cannot have before/after computed (`comparison=None`
in the API response, distinct from a `maturity` of `"too_soon"`/
`"insufficient_coverage"`, which means an association *was* attempted).
This is a deliberate refusal to fall back to Place-wide numbers that would
not actually describe that corner of the yard.

**Language:** only ever the same four `AssociationStatus` values already
in production (`no_clear_association`, `more_common_under_condition`,
`less_common_under_condition`, plus internally `insufficient_data`, which
never reaches the API -- the maturity/coverage gate already filters it
out). No percentage math, no causal wording, anywhere in this module or
its frontend rendering.

## Feature yield (Phase 12) -- `mockingbird.analytics.feature_yield`

Deliberately the same shape as `source_activity.compute_source_activity`,
scoped one level finer (a Feature's own Zone, or its Source when no Zone
is linked) and extended with a distinct-taxon diversity count. Reuses
`MIN_MONITORED_HOURS_FOR_RATE = 2.0` verbatim from `source_activity`/`zone_
insights` -- never a new floor. Coverage seconds are summed across the
Feature's `stream_ids` by calling `_zone_insights_exposure` per Stream
(unmodified), not a new coverage computation.

## Feeder-specific metadata (Phase 8)

`feeder_food_type` (free text) plus the `"food_changed"`/`"replenished"`
event types. Deliberately not an inventory system: no purchase receipts,
no exact food weight, no SKUs, no supply forecasting.

## API surface

- `GET/POST /api/place/features`, `PATCH/DELETE /api/place/features/{id}`
- `GET /api/place/features/{id}/detail` -- the full bundle: current state,
  complete change-event timeline (each with its own before/after
  comparison), a recent-window (7-day) yield snapshot
- `GET /api/place/features-summary` -- a compact, Dashboard-safe bundle
  (active count, recent-change count, at most one restrained highlight
  sentence), mirroring `GET /api/place/habitat-context`'s "dedicated
  bundle, not a field bolted onto a fuller report" precedent
- `GET/POST /api/place/feature-changes` (optional `?feature_id=` filter),
  `PATCH/DELETE /api/place/feature-changes/{id}`

Every mutation requires an authenticated session
(`current_user_or_401`); reads are protected by this product's existing
deny-by-default auth middleware (not on the `_ALWAYS_PUBLIC_PATHS`
allowlist), matching the Habitat & Phenology precedent -- confirmed by
`test_place_feature_mutations_require_authentication`.

**Deliberately not built:** composition into `PlaceActivityReportResponse`/
`place_activity_report_adapter.py`. Feature/change data gets its own
dedicated endpoints instead, exactly mirroring how `GET /api/place/habitat`
/`/phenology`/`/habitat-context` are already separate from `POST /api/
analytics/place-activity-report` -- avoids touching the large, delicate
report-composition machinery for a genuinely separate domain.

## Frontend surface

- `web/src/api/types.ts`/`client.ts` -- hand-mirrored interfaces and one
  `request<T>` method per route, matching this file's existing no-codegen
  convention.
- **Dashboard (Today):** `PlaceFeaturesCard.tsx`, a sibling of
  `HabitatPhenologyCard`, same calm-view/inline-edit-toggle shape. Calm
  view: the backend's own restrained highlight sentence plus active-
  feature tags. Edit view: add/deactivate/remove a Feature (with a real
  Zone-name picker, self-fetched via the existing `getZones()` client
  method), plus one "Record a change" form. `onRemoveFeature` returns a
  user-safe message (never a raw exception) so a blocked hard-delete can
  explain "deactivate it instead."
- **Place Report page:** a "Features & changes" section, mirroring the
  existing Habitat & Season section's exact "period-independent, fetch
  once, no edit UI" pattern. Each Feature can be expanded to lazily load
  its own before/after insight (`GET .../detail`) -- never fetched for
  every Feature up front, keeping the page's initial load cheap.
- **Today (Dashboard highlight):** deliberately **not** wired into
  `daily_digest.py`'s highlight-tier ranking -- a new, small, independently
  -fetched, absence-safe `GET /api/place/features-summary` call instead,
  avoiding any change to that shared, delicate ranking module. Recorded as
  a possible future integration, not built by adjacency.

## Scope boundaries honored

Not built (see Phase 31 of the governing brief and "Remaining major
PRODUCT opportunities" in the report): automated causal recommendations,
a dedicated new "Feature detail" route/page (folded into an inline
expand instead), a Zone/camera multi-link join table, representative
evidence wired into Feature detail, a rich taxonomy editor, purchase/
inventory tracking, Today/`daily_digest` highlight-tier integration.

## Testing

Tier 1: pure window-selection/maturity logic
(`compute_feature_change_comparison` -- too-soon, escalation, insufficient
-coverage, higher/lower/similar, identical output to calling
`conditional_association` directly); pure yield computation
(`compute_feature_yield` -- floor gate, rate, diversity, honest `None`
absence); Feature/change-event repository CRUD (add/list/update/remove,
association resolution and its validation/clearing rules, hard-delete
blocked-by-history); dual-write reconciliation (`removed` ->
deactivation, `food_changed` -> food type, the one-directional
non-reactivation rule, a date correction re-ordering which event is
latest); the full detail/summary bundles against a real seeded before/
after scenario; a direct proof a correction changes the very next read
with no cache to invalidate; the real HTTP surface (auth-required
mutations, 404s, 422s for a bad/mismatched association or an unknown
Feature, 409 for a blocked hard-delete); every value in both closed
vocabularies round-tripped through the real repository/schema layer.

Tier 2: `test_persistence.py` schema-55 migration test (mirroring the
schema-52 template exactly); the 14 hard-coded `CURRENT_DATABASE_SCHEMA_
VERSION == 54` guard-rails across 8 files this milestone's own v54->v55
bump was always going to trip, bumped to `55` (see "Validation" in the
report); frontend `tsc --noEmit` and `vite build`; a dedicated Playwright
spec (`e2e/place-features.spec.ts`) covering the real empty state (against
the real, unmocked backend), the highlight/tag render, the add-feature
form's accessible structure, a higher-after before/after sentence, a
`too_soon` restrained sentence, and a narrow-viewport check; the directly
adjacent existing e2e suites (today-report, place-activity-report,
biodiversity-summary) re-run for regressions.

Tier 3: full Core, justified by the same real cross-cutting surface prior
schema-bump milestones used to justify their own full-Core run
(`models.py`, `database.py`, `product_repository.py`, `main.py`,
`schemas.py` all touched, plus a schema version bump). See the report for
the actual run result.
