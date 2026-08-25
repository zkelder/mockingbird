# Place Features & Habitat Change v2 Report

## Identity

- **Starting HEAD:** `b0bd312`
- **Substantive implementation HEAD:** `47b7cc9` ("Place Features &
  Habitat Change v2: Feeders, Water, Nest Boxes & Before/After
  Understanding")
- **Final docs HEAD:** this commit (reconciles release-execution-state.md
  + roadmap.md + adds this report)
- **Schema:** v54 -> v55 (two additive tables: `place_features`,
  `place_feature_change_events`)
- **Commits:** two -- `47b7cc9` (implementation) and this one
  (reconciliation)
- **Push state:** local only -- not pushed, matching the standing
  "Push state: explicit authorization required" instruction

See [place-features-habitat-change-v2-contract.md](place-features-habitat-change-v2-contract.md)
for the full design contract; this report records what was actually built,
what evidence backs it, and what remains open.

## Archaeology

Directly inspected before writing any code (Phase 1 of the governing
brief):

- `PlaceHabitatFactModel`/`PlacePhenologyObservationModel`
  (`src/mockingbird/storage/models.py`) and their governing contract
  (`docs/habitat-phenology-foundation-v1-contract.md`).
- `mockingbird.analytics.conditional_association`/`habitat_association`/
  `weather_association`/`seasonal_pattern`/`temporal_pattern`/
  `source_activity`/`daily_digest`/`place_activity_report`/
  `place_activity_report_adapter`/`zone_insights`/`historical_baseline`/
  `place_biodiversity_summary`/`place_change_summary` -- every public
  signature, every coverage/maturity floor constant, and the exact
  `presence_dates`/`usable_dates`/`condition_dates` mechanism.
- `ZoneModel`/`StreamModel`/`CameraSourceModel`/
  `MonitoringExposureIntervalModel` and how coverage is queried and
  bucketed by day (`ProductRepository._historical_usable_dates`/
  `_monitoring_exposure_intervals_and_history`/`_zone_insights_exposure`).
- The habitat/phenology and Zone API routers, Pydantic schemas, and the
  `ReviewLabel` correction/provenance machinery, as the two available
  correction-pattern templates.
- `HabitatPhenologyCard.tsx`, `WeeklySummaryCard.tsx`,
  `DashboardPage.tsx`'s fetch orchestration, and
  `PlaceActivityReportPage.tsx`'s period-independent Habitat & Season
  section, as the frontend templates.

### Gap table

| User need | Existing model | Missing structured concept | Product consequence | Implemented |
|---|---|---|---|---|
| "I have a sunflower feeder" | `PlaceHabitatFactModel` (free-text tag) | No feature *identity*, lifecycle, or association | Can't refer to "the feeder" as one thing over time | `PlaceFeatureModel` |
| "I added it March 15 / moved it / changed food" | `PlacePhenologyObservationModel` (recurring-phenomenon interval) | No closed `event_type`, no feature link, no single-instant fact | No queryable "a change happened at time T" | `PlaceFeatureChangeEventModel` |
| "What changed after I added the feeder?" | **Confirmed absent** -- `habitat_association.py`'s own docstring states this outright | No before/after engine at all | The product's whole point for this milestone was unmet | `mockingbird.analytics.feature_change_comparison`, reusing `conditional_association` unmodified |
| "Which feeder is most active?" | `source_activity.py` (per-**Source** only) | No per-feature yield | Two feeders on one camera indistinguishable | `mockingbird.analytics.feature_yield` |
| "Is there enough monitoring to trust this?" | Coverage floors exist but keyed to intervals/all-time | No caller for a point-event window | Risk of a confident result from a tiny base | Floors reused verbatim (5 usable days/side, 2 healthy hours) |
| "I correct the date I recorded" | PATCH-in-place precedent exists | No derived intelligence cached in this domain (so nothing to invalidate) | A new feature must not accidentally introduce a cache that then needs invalidation | Before/after is a pure read-time computation, by construction |

Confirmed, by direct inspection, absent before this milestone: any Feature
entity, any Change Event entity, any before/after comparison code, any
feeder/water/nest-box-specific field anywhere in `models.py`. No
`PlaceModel`, no `AreaModel` ("Area" is prose-only in the spatial-doctrine
hierarchy).

## Product/data contract

See the contract doc's "Data model," "Feature taxonomy," and
"Change-event vocabulary" sections. Both new tables carry the same
`information_class="reviewed"`/`provenance="user_manual_entry"` pair
`PlaceHabitatFactModel` established, plus a new, deliberately stronger,
on-row `actor_user_id` (the governing brief explicitly asked for durable
"reviewed actor provenance" twice) -- populated only from the
authenticated session, matching `ReviewLabelModel.reviewed_by_user_id`'s
exact idiom.

## Feature model

`PlaceFeatureModel` -- current mutable state (name, type, note,
active/inactive, best-known install/removed dates, optional Zone/Source
link, feeder food type). See the contract doc for the full field-by-field
rationale. 15 columns, two indexes, purely additive.

## Change-event model

`PlaceFeatureChangeEventModel` -- one row per dated, typed, human-recorded
change (`added`/`removed`/`moved`/`modified`/`replenished`/
`food_changed`/`vegetation_changed`/`other`), optionally linked to a
Feature, always carrying `effective_date`/`note`/`prior_value`/
`new_value`/provenance/actor. This is the concrete object
`habitat_association.py`'s own docstring said did not exist.

## User-facing feature types

`feeder`, `water`, `nest_box`, `vegetation_patch`, `structure`,
`habitat_area`, `other` -- seven values, deliberately bounded (see
"Feature taxonomy" in the contract doc). Ordinary yard vocabulary ("Back
hedge," "Brush pile") is carried by the free-text `name`, not by growing
the type list.

## Lifecycle / history semantics

Dual-write, not event sourcing (contract doc, "Feature state vs change
history"): current state lives on `PlaceFeatureModel`, corrected in
place; the append-in-spirit `PlaceFeatureChangeEventModel` table is the
durable timeline. Recording a `"removed"` or `"food_changed"` event also
updates the Feature's own current-state columns in the same transaction
(`ProductRepository._recompute_feature_derived_state`), deliberately
one-directional for `"removed"` (never auto-reactivates). Hard deletion of
a Feature is blocked once it has any change-event history
(`PlaceFeatureHasHistoryError` -> HTTP 409); deactivation is the
always-available alternative. Deleting an individual change event is an
ordinary, always-available correction.

## Camera / Zone / Area association

A single optional `zone_id` (preferred) or `source_id` (coarser) per
Feature, validated and normalized by `ProductRepository.
_resolve_feature_association` -- a Zone's own Stream's Source is always
authoritative over an independently-supplied `source_id`, so a Feature can
never hold an inconsistent pair. No many-to-many join table; a Feature
seen by two cameras is a documented, recorded-not-built v2 limitation
(Phase 28). "Area" was confirmed, again, to not exist as a persisted
concept anywhere in this codebase.

## Before/after analysis

`mockingbird.analytics.feature_change_comparison.
compute_feature_change_comparison` -- see the contract doc's own section
for the full window-selection/maturity mechanism. The headline result:
**no new statistical primitive was needed.** `conditional_association.
compute_conditional_association` (Place / Yard Intelligence v2's own
generic presence-rate-in-a-date-set primitive) turned out to be exactly
reusable for a before/after comparison once the caller pre-restricts
`usable_dates` to the union of the two symmetric windows and passes the
post-window as `condition_dates` -- confirmed correct by
`test_compute_feature_change_comparison_matches_conditional_association_primitive`,
which asserts the engine's own output is byte-identical to calling the
shared primitive directly with the same date sets.

Scope is always the Feature's own association (its Zone, or its Source's
Streams) -- never a Place-wide fallback that would misrepresent one
corner of the yard. A Feature with no camera/Zone link cannot have
before/after computed at all (`comparison: null`, distinct from a
`maturity` of `"too_soon"`/`"insufficient_coverage"`).

## Coverage / maturity rules

Every floor is reused, not reinvented: `conditional_association`'s
default 5-usable-days-each-side gate and 25-percentage-point minimum
rate difference; `source_activity`/`zone_insights`'s 2-healthy-hour
floor for yield. Four honest maturity states surface to the API/UI:
`too_soon`, `insufficient_coverage`, `early_signal`, `comparable` -- see
the contract doc for exactly what distinguishes them. No raw percentage
is ever computed or rendered from these comparisons; only the same four
qualitative `AssociationStatus` values `habitat_association`/
`weather_association` already use in production.

## Environmental / phenology composition

**Not built this pass, and the most significant deliberate scope
trade-off in this milestone.** Phase 17 of the governing brief asked for
an environmental-context caveat on before/after results ("Activity was
higher after the feeder change, but the post-change period was also
substantially cooler"). Given the size of the rest of this milestone
(full CRUD + migration + a new comparison engine + full-stack UI + a
comprehensive test matrix), this composition was consciously deferred
rather than built shallowly under time pressure. `PlacePhenologyObservationModel`
and `PlaceFeatureChangeEventModel` remain deliberately separate concepts,
as instructed (Phase 16) -- both are preserved, neither collapses into
the other, and nothing about this milestone makes composing them together
later (or composing weather deltas onto `PlaceFeatureAssociation`) harder;
it is a strict additive follow-up, not a redesign. Recorded explicitly
below under "Remaining major PRODUCT opportunities," not silently
dropped.

## Product surfaces

- **Dashboard (Today):** `PlaceFeaturesCard.tsx`, a sibling of
  `HabitatPhenologyCard`, same calm-view/inline-edit-toggle shape --
  restrained highlight sentence + active-feature tags when calm; full
  add/deactivate/remove-Feature and record-a-change forms when editing,
  including a real Zone-name picker (self-fetched via the existing
  `getZones()` client method).
- **Place Report page:** a new "Features & changes" section, mirroring
  the existing Habitat & Season section's exact period-independent,
  read-only, fetch-once pattern. Each Feature expands in place to lazily
  load its own full change history + before/after insight -- never
  fetched for every Feature up front.
- **Today (a single restrained line):** intentionally **not** wired into
  `daily_digest.py`'s highlight-tier ranking -- a small, independent,
  absence-safe `GET /api/place/features-summary` call instead, so this
  shared, delicate ranking module needed zero changes. This is a
  deliberately lighter-weight integration than the brief's own worked
  example implies is possible; recorded below as a future opportunity.
- No new page/route was added (Phase 20 permits, does not require, a
  dedicated "Feature detail" page); a Feature's full detail is reached by
  expanding it inline on the Place Report page instead, keeping this
  milestone's navigation footprint at zero.

## Correction safety

Both new tables are PATCH-corrected in place (the lighter of the two
available precedents in this codebase; see "Correction model" in the
contract doc for the deliberate choice between it and `ReviewLabel`'s
heavier append-only-superseding pattern). This is safe specifically
because every derived comparison is a **pure read-time computation, never
persisted** -- a correction is reflected on the very next `GET .../detail`
call with no invalidation step to get wrong. Directly proven, not just
asserted:

- `test_correcting_change_event_date_changes_comparison_on_next_read` --
  moving an event's `effective_date` flips its comparison from
  `"comparable"` to `"too_soon"` on the very next read.
- `test_correcting_food_changed_event_date_reorders_which_is_latest` --
  correcting an earlier event's date past a later one changes which
  event's `new_value` the Feature's own `feeder_food_type` reflects.
- `test_deleting_only_removed_event_does_not_reactivate` -- proves the
  deliberate one-directional design decision, not just describes it.

## Production-shaped examples

Every repository/API test uses real seeded `EventModel`/`VisitModel`/
`MonitoringExposureIntervalModel` rows and the real `create_review_label`
write path (never hand-set `reviewed_label`), the same discipline
`test_place_activity_report_repository.py` established. Representative
scenarios actually exercised, end to end:

- A feeder added on a known date, zero confirmed activity before, daily
  confirmed activity after, 14 days of seeded coverage -> `"comparable"`
  / `"more_common_under_condition"`.
- The same shape with only 2 days elapsed -> `"too_soon"`.
- A food-change event, then a second one, then a date-correction on the
  first that reorders which is latest -> `feeder_food_type` tracks
  correctly through all three states.
- A Feature with change history whose hard-deletion is attempted -> a
  real HTTP 409 with a user-safe message, verified over the real
  `TestClient`, not merely asserted from the repository layer.
- The Dashboard/Place Report frontend surfaces were driven end-to-end
  through a real running app + real browser (Playwright), not only
  React-level assertions -- see "Tests / validation," below.

Per the governing brief's own instruction, no ecological claim is drawn
from any of this synthetic data; this is product/mechanism validation
only.

## Performance

Feature/change history is small by design (a handful of rows per
Feature). Before/after computation issues one `_historical_usable_dates`
call (2 queries) and one bounded, coarsely-padded Visit query per change
event -- proportionate to the number of *change events on one Feature*
(inherently small), not to total Visit volume. Feature yield issues one
bounded Visit query plus one `_zone_insights_exposure` call per Stream in
scope (in practice almost always exactly one Stream, per this codebase's
own "1:1 in practice today" precedent). The `GET .../features-summary`
endpoint computes yield for every *active* Feature to find its one
highlight -- proportionate to Feature count, which this milestone treats
as inherently small ("several features," per the governing brief's own
Phase 25 test scenario), not to history length. No new N+1-over-Visits
pattern was introduced. Not separately profiled against a synthetic
years-of-Visits/many-Features fixture beyond what the seeded test
scenarios already exercise; flagged below as unverified at true scale
rather than claimed proven.

## Tests / validation

**Tier 1 (`tests/test_place_feature.py`, 50 tests, all passing):** pure
window-selection/maturity logic (too-soon, escalation across all three
window sizes, insufficient-coverage, higher/lower, and a direct proof the
engine's output is identical to calling `conditional_association`
directly); pure yield computation (floor gate, rate, diversity, honest
`None` absence); full Feature/change-event repository CRUD including
association resolution/validation/clearing and hard-delete-blocked-by-
history; dual-write reconciliation including the one-directional
non-reactivation rule and a date-correction reordering test; the full
detail/summary bundles against real seeded before/after scenarios; a
direct proof a correction changes the very next read; the real HTTP
surface (401 unauthenticated, 404s, 422s for a bad/mismatched
association or an unknown Feature, 409 for a blocked hard-delete); every
value in both closed vocabularies round-tripped through the real
repository/schema layer in one test.

**Tier 2:**
- `tests/test_persistence.py::test_schema_54_upgrades_to_current_with_place_features_habitat_change`
  -- a real v54 database (two tables dropped, version rolled back)
  upgrades cleanly, both tables created empty, existing data untouched.
- 14 hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 54` guard-rail
  assertions across 8 unrelated files (`test_visit_tags.py`,
  `test_candidate_visit_repository.py` x7, `test_camera_health.py`,
  `test_camera_node.py`, `test_species_candidate_packs.py`,
  `test_yard_map.py`, `test_visit_collections.py`) this milestone's own
  correct v54->v55 bump was always going to trip -- found by grep before
  running the suite (matching this exact codebase's own documented
  precedent for the last two schema bumps), bumped to `55`, all affected
  files re-run and passing (76 + 52 = 128 tests).
- Directly adjacent subsystem re-run for regressions:
  `test_habitat_phenology.py`, `test_habitat_association.py`,
  `test_place_activity_report.py`,
  `test_place_activity_report_repository.py`, `test_source_activity.py`
  -- 174 passed.
- Frontend `tsc --noEmit` (clean) and `vite build` (clean, produces a
  normal chunked bundle).
- A new Playwright spec, `web/e2e/place-features.spec.ts` (7 tests, all
  passing against a real running app + real browser): the genuine empty
  state against the **real, unmocked** backend (proving the new
  endpoints wire correctly end to end, not just against a mock); no
  "Features & changes" section renders on the Place Report page when
  nothing is recorded; the highlight/tag render; the add-feature form's
  accessible structure (`getByLabel`/`getByRole`); a
  `"more_common_under_condition"` sentence with an explicit assertion
  that no `%` or causal wording (`caused`/`because of`) ever appears; a
  `"too_soon"` restrained sentence; a narrow (375px) viewport check.
- Directly adjacent existing e2e suites re-run for regressions
  (`today-report.spec.ts`, `place-activity-report.spec.ts`,
  `biodiversity-summary.spec.ts`) -- 30 passed.
- `git diff --check` -- clean.

**Tier 3:** full Core (`scripts/verify_core.py`) -- **4926 passed / 2
failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed (23m27s)**.
Both failures are in `test_place_biodiversity_summary_repository.py`
(`test_api_route_returns_the_summary`,
`test_human_correction_updates_place_biodiversity_intelligence_correctly`)
-- the identical, already-documented pair every one of the last several
milestones' own validation baselines in
[release-execution-state.md](release-execution-state.md) records as
pre-existing, timing-sensitive flakiness (a fixed test `NOW` constant
drifting against the real historical-baseline window as real wall-clock
time advances). Directly re-confirmed this session, not merely cited: a
`git stash` bisection ran this exact file against the clean `b0bd312`
baseline with **zero** of this milestone's changes applied, and it
reproduced the identical two failures with byte-identical assertion text
(`'seen_before' == 'new'`) -- conclusive proof this milestone introduced
no regression here. Justified by the same real cross-cutting surface
(`models.py`/`database.py`/`product_repository.py`/`main.py`/
`schemas.py`, plus a schema version bump) prior schema-bump milestones
used to justify their own full-Core run.

An untracked, uv-generated `uv.lock` (never gitignored, never tracked,
zero relation to this milestone's own dependencies) appeared in the
working tree mid-session from ordinary `uv run` tool invocations --
investigated and removed, mirroring the identical, already-documented
decision from Representative Field Acceptance & Release-Budget Closure
v1. Working tree confirmed to hold exactly the seven preserved detector
files plus this milestone's own additions before and after that removal.

## Remaining major PRODUCT opportunities

Recorded as future dependencies, deliberately not built by adjacency (per
the governing brief's own repeated instruction):

- **Environmental-context caveat composition** (Phase 17) -- the single
  largest explicitly-requested piece not built this pass. Composing a
  pre/post average-temperature (or wet/dry) delta onto
  `PlaceFeatureAssociation` as a plain-language caveat is additive on top
  of both this milestone's before/after engine and the already-accepted
  Environmental Context v2 weather associations; no redesign required.
- **Multi-camera Feature linking** (Phase 28) -- a Feature seen by more
  than one camera can only be linked to one today; a join table plus a
  small UI change would lift this, with no confirmed real demand yet.
- **Representative evidence in Feature detail** -- Gate C's existing
  representative-evidence selector is not yet wired to show "the best
  recent photo from this feeder's Zone" in `PlaceFeatureDetail`.
- **A ranked, side-by-side feature-comparison view** (Phase 13) -- the
  backend yield primitive fully supports "which feeder is more active,"
  but the only UI surface today is a single restrained Today-style
  highlight sentence, not a comparison table/view.
- **Deeper Today/`daily_digest` integration** -- today's Dashboard
  highlight is a wholly separate fetch/endpoint rather than a ranked
  `daily_digest` highlight tier alongside species highlights; unifying
  the two (if ever warranted) is additive, not a redesign.
- **A dedicated Feature detail page/route** -- today folded into an
  inline expand on the Place Report page; a real standalone page (with
  its own URL, deep-linkable) is a natural, small follow-up if usage
  shows the inline expand is not enough.
- **True production-scale performance verification** -- see
  "Performance," above: proportionate by design, but not profiled
  against a synthetic years-of-history/many-Features fixture.
- **Research/export representation** (Phase 26) -- explicitly left open
  by the governing brief itself ("do not automatically force this into
  Camtrap DP... research-safe export can evolve separately"); Feature/
  change-event provenance is durably present in the database (feature
  type, effective dates, actor, provenance) and ready for a future export
  slice to read, but no export code was touched this pass.

None of these are release blockers; all are genuine product depth still
available on this same substrate.

## Capability maturity

**B** -- major useful capability, bounded feature/data-model maturity
gaps. This milestone delivers the specific, concrete thing two prior
accepted milestones both explicitly named as their own honest ceiling
(Place / Yard Intelligence v2: "no discrete before/after habitat
*change-event* model exists anywhere in this codebase... building one is
recorded as a future data-model dependency"; `habitat_association.py`'s
own docstring, unmodified since v1: "confirmed absent... not built
here") -- a full, tested, honestly-scoped Place Feature + Change Event
model, a before/after engine built on pure reuse of an already-accepted
statistical primitive, coverage-gated maturity states, per-feature yield,
and a working full-stack UI, all without ever producing a causal claim or
a raw percentage from a small count. The bounded gaps are real and listed
above, most notably the deferred environmental-context caveat Phase 17
explicitly asked for and the still-single-camera-only association model.
This is not a release-readiness classification.

## Scheduler reconciliation

Confirmed: **CURRENT PHASE = SUBSTANTIAL PRODUCT DEVELOPMENT**, unchanged.
Representative Field Acceptance, External Beta, and Final Release
Hardening remain downstream while major roadmap capabilities remain
intentionally unfinished (see "Remaining major PRODUCT opportunities,"
above, and the still-open lanes in
[release-execution-state.md](release-execution-state.md) §6). This
milestone does not authorize its own next step; see that file's own
updated §3 for the required-reconciliation statement.

## Preserved files

Confirmed present, untouched, at both the start and the close of this
session (`git status --short`, both times, matched exactly):

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

## Exact git status --short

Captured immediately before this report's own (second, reconciliation)
commit -- everything staged for that commit plus exactly the seven
preserved files, nothing else:

```
 M docs/release-execution-state.md
 M docs/roadmap.md
?? docs/place-features-habitat-change-v2-report.md
?? docs/wildlife-detector-training-contract.md.orig
?? scripts/evaluate_small_bird_detector.py
?? scripts/materialize_wildlife_stage2.py.orig
?? scripts/train_wildlife_stage2_rfdetr.py.orig
?? src/mockingbird/detectors/small_bird_benchmark.py
?? src/mockingbird/training/wildlife.py.orig
?? tests/test_small_bird_benchmark.py
```
