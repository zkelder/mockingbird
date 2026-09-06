# Multi-Camera Place Feature Linking & Cross-View Habitat Context v1 Report

## Identity

- **Starting HEAD:** `2771d4c` (Year-over-Year Seasonality & Long-Term Place
  Memory v1, reconciled)
- **Implementation HEAD:** `3cce9e4` ("Multi-Camera Place Feature Linking &
  Cross-View Habitat Context v1: implementation")
- **Report/reconciliation HEAD:** this commit (reconciles
  release-execution-state.md + roadmap.md + adds this report)
- **Schema:** v58 → v59 (one new additive-and-backfilled table,
  `place_feature_observation_links`)
- **Commits:** two -- `3cce9e4` (implementation) and this one
  (reconciliation)
- **Push state:** local only -- not pushed, per standing instruction

## Starting state

Verified exactly as the authorization stated before any code was touched:
branch `main`, HEAD `2771d4c`, schema `v58`, Lane P `CLOSED`, Lane R `OPEN --
RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS` (untouched by this
milestone), current authorization `NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED`. `git status --short` matched the expected seven
preserved untracked detector files exactly, nothing else pending.

## Why product development was reopened

`docs/release-execution-state.md`'s own most recent reconciliation (Global
Remaining Product-Development & Release-Queue Reconciliation v1,
2026-09-06) had just found that every named remaining product opportunity
fails a five-question substantiality test -- **except** that reconciliation
did not itself re-examine "multi-camera Feature linking" against that test;
it simply listed it, unresolved, among the queue. This milestone is the
owner's explicit, one-time, bounded reopening to resolve exactly that one
named item, directly requested twice already: Place Features & Habitat
Change v2's own Phase 28 ("a Feature visible from two cameras can only be
linked to one for now... a join table plus a small UI change would lift
this, with no confirmed real demand yet") and Multi-Camera Place Experience
v2's own investigation ("judged real but smaller-priority than the gaps this
milestone actually found broken... recorded as a future opportunity, not
built by adjacency").

## Existing architecture

Bounded archaeology (four parallel research passes, matching the governing
brief's own instruction) confirmed, by direct code inspection, exactly what
existed before this milestone:

- `PlaceFeatureModel` (schema 55): `source_id`/`zone_id` are both singular,
  nullable FKs (`camera_sources.id`/`zones.id`), validated and normalized by
  `ProductRepository._resolve_feature_association` -- a Zone's own Stream's
  Source is always authoritative over an independently-supplied `source_id`.
  The model's own docstring named the exact limitation this milestone
  closes: *"A Feature currently associates with at most one Zone/Source...
  its yield/before-after figures are scoped to that one linked view."*
- `PlaceFeatureChangeEventModel.feature_id` was already the *only* field a
  change event carries -- never camera/Zone-specific. This satisfies the
  governing brief's "Feature change events remain attached to the canonical
  Place Feature" requirement (#14) **without any change**; it was already
  correct.
- The two singular-scoping chokepoints were `ProductRepository.
  _feature_monitoring_stream_ids` (resolves a Feature's association to a
  Stream list) and `_feature_scoped_visit_facts` (the Visit-fact query
  itself) -- both keyed off `feature.zone_id`/`feature.source_id` directly.
  `_feature_scoped_visit_facts`'s own docstring already disclosed a latent
  gap: *"Deliberately does not apply
  `_associated_visit_ids_to_exclude_from_counting`'s cross-camera-duplicate
  exclusion... a documented, bounded simplification for this single-Feature
  scope"* -- correct and inert before this milestone (a single-Source scope
  can never contain both sides of a cross-camera pair), but load-bearing
  the moment multi-view linking exists.
- `_feature_scoped_monitored_seconds` summed per-Stream `healthy_seconds` in
  a loop -- the exact naive-sum bug Multi-Camera Place Experience v2 already
  found and fixed for Zone Insights' own Place-wide aggregate, just not yet
  applied here (this scope had never had more than one Stream to sum before).
- `mockingbird.observation.cross_camera_association` /
  `ProductRepository._associated_visit_ids_to_exclude_from_counting` (the
  accepted cross-camera duplicate-encounter engine, schema 47) and
  `ProductRepository._place_activity_coverage_summary` (the accepted
  elapsed-time coverage-union primitive) both already existed, fully
  general, and were designed for exactly this kind of reuse.
- `PlaceFeaturesCard.tsx` (Dashboard) only ever sent `zone_id` at creation
  time -- its "Camera (optional)" field was, in fact, a bare Zone picker
  (mislabeled), and the frontend never exercised the bare-Source-only
  association path the backend already supported.
- No `AreaModel`/`PlaceModel` exists anywhere (confirmed by exhaustive
  grep, again); "Area" remains a purely derived, non-persisted Zone-name
  signal used only by the cross-camera dedup engine's own spatial
  pre-filter -- never a candidate for identity or linking.

## Canonical Feature identity contract

Unchanged, deliberately. `PlaceFeatureModel`'s own identity (`id`,
`feature_type`, `name`, `note`, `is_active`, `installed_date`,
`removed_date`, `feeder_food_type`, `information_class`, `provenance`,
`actor_user_id`, timestamps) is untouched by this milestone -- a Feature
remains one row, one durable identity, one lifecycle. `source_id`/`zone_id`
remain physically present on that same row, but their *meaning* changes:
they are now a **repository-maintained compatibility mirror**, not the
source of truth. `ProductRepository._recompute_feature_association_mirror`
keeps them equal to the Feature's single link's `(source_id, zone_id)` pair
whenever it has **exactly one** observation link, and resets both to `NULL`
for zero or two-or-more links -- an honest absence, never an arbitrary
"first" link standing in for a set (the identical abstention discipline
doctrine already requires for Inferred output, applied here to a structural
fact instead). A migrated single-link Feature (the overwhelmingly common
real-world case) reads back byte-identical to its pre-migration self.

## Observation-link contract

The canonical, possibly-plural relationship set lives in one new table,
`PlaceFeatureObservationLinkModel` (`place_feature_observation_links`):
`id`, `feature_id` (FK, required), `source_id` (FK to `camera_sources.id`,
**required**), `zone_id` (FK to `zones.id`, optional), plus the identical
`information_class`/`provenance`/`actor_user_id`/`created_at` provenance
quartet `PlaceFeatureModel`/`PlaceFeatureChangeEventModel` already
establish. No `updated_at` -- a link is only ever added or removed, never
edited in place, mirroring `VisitEvidenceLinkModel`'s identical
"created_at-only" precedent.

Deliberate deviation from the governing brief's own candidate schema: the
camera-identity column is named (and FK'd) `source_id`, not `stream_id`,
matching `PlaceFeatureModel.source_id`'s own existing FK target exactly
rather than introducing a second, differently-scoped identity concept at
this layer. This was a direct instruction to investigate repository
conventions before mechanically copying the candidate shape, and it pays
off concretely at migration time (see below): an existing Feature's
`source_id`/`zone_id` pair copies into exactly one new link row with **zero
translation, zero ambiguity, and zero risk** of a Source-to-Stream mapping
assumption turning out to be wrong for some installation.

Two hard requirements this contract must satisfy, both proven directly (not
merely asserted):

- **A Feature can hold two independent links against the very same
  Source** (e.g. two different drawn Zones on one wide-angle camera, both
  genuinely showing part of one physical Feature) --
  `test_feature_can_link_two_different_zones_on_the_same_source`.
- **The identical (Source, Zone) view cannot be linked twice** -- proven for
  both the Zone-scoped case (`test_add_duplicate_observation_link_is_
  rejected`) and, separately, the bare-Source case
  (`test_add_duplicate_bare_source_observation_link_is_rejected`, whose own
  docstring calls out exactly why this needs its own test: "SQLite's own
  NULL-is-distinct semantics would let this slip past a naive unique index").

## Schema / migration decision

Additive, not purely so: unlike every prior additive migration in this
codebase (which start an upgraded installation "as cold as a brand-new
one"), this one **backfills**, because there is real pre-existing data that
must migrate with zero semantic change (the governing brief's own hard
requirement). `_migrate_to_place_feature_observation_links`:

1. Creates the new table (`checkfirst=True`, matching house style exactly).
2. For every existing `place_features` row with a non-`NULL` `source_id`,
   inserts exactly one corresponding link row, copying `source_id`,
   `zone_id`, `information_class`, `provenance`, and `actor_user_id`
   verbatim from the Feature's own row, and reusing the Feature's own
   `created_at` as the link's honest "this association has existed since
   the Feature was created" timestamp.
3. A Feature whose `source_id` was already `NULL` (Place-wide knowledge,
   no camera association) correctly gets **zero** link rows -- not a
   fabricated empty one.

Duplicate prevention at the schema level uses two **partial** unique
indexes (`sqlite_where`), not one plain multi-column `UniqueConstraint`:
`EnvironmentalContextRecordModel`'s own docstring already documents, in
this exact codebase, that a `UNIQUE` index spanning a nullable column does
not actually deduplicate in SQLite (every `NULL` is distinct from every
other `NULL`). One partial index covers `(feature_id, source_id, zone_id)`
`WHERE zone_id IS NOT NULL`; the other covers `(feature_id, source_id)`
`WHERE zone_id IS NULL`. These are a backstop, not the primary guard --
the primary guard is an explicit `.is_(None)`-aware existence check in
`add_place_feature_observation_link`, mirroring the exact same
already-established convention that model's docstring names.

`CURRENT_DATABASE_SCHEMA_VERSION` 58 → 59. The 14 hardcoded
`CURRENT_DATABASE_SCHEMA_VERSION == 58` guard-rail assertions this exact
kind of bump has tripped at every prior schema-bump milestone (across
`test_visit_tags.py`, `test_camera_health.py`, `test_camera_node.py`
(×2), `test_candidate_visit_repository.py` (×8), `test_yard_map.py`,
`test_visit_collections.py`, `test_species_candidate_packs.py`) were found
by grep before running the suite and bumped to `59` -- the identical
8-file, 14-assertion set the v54→v55 (Place Features & Habitat Change v2)
bump already hit, confirming this is a stable, recurring, well-understood
cost of a schema bump in this codebase, not a new risk.

## Backward compatibility

Proven directly, not merely asserted, by
`test_schema_58_upgrades_to_current_with_place_feature_observation_links`:
a real v58-simulated database (an existing Feature with a Zone link, an
existing Feature with a bare-Source link including a `feeder_food_type`,
and an existing Feature with no association at all, all seeded through the
real repository, then the new table dropped and the schema version rolled
back to 58) upgrades cleanly, producing exactly the right link rows (one
each for the first two, zero for the third), with every one of the
Feature's own pre-existing columns -- name, type, `feeder_food_type`,
provenance -- byte-identical after the upgrade, and the compatibility-mirror
`source_id`/`zone_id` reading back exactly as they did before migration for
every single-link Feature.

## CRUD

**Multi-view editing** (Deliverable A): two new endpoints, additive to the
existing Feature CRUD surface:

- `POST /api/place/features/{feature_id}/observation-links` -- add one
  view. Requires at least one of `source_id`/`zone_id` (a dedicated
  Pydantic validator on `PlaceFeatureObservationLinkCreate` rejects a
  payload naming neither -- a "no association" state is meaningful for a
  *Feature*, but meaningless for a dedicated "add a link" call). Reuses
  `_resolve_feature_association` unmodified for Zone/Source
  validation/normalization, reapplied per link. 422 for invalid/mismatched
  Zone/Source or a duplicate view; 404 for an unknown Feature.
- `DELETE /api/place/features/{feature_id}/observation-links/{link_id}` --
  remove one view. Always allowed, even as the Feature's last remaining
  link (never deletes the Feature itself; a zero-link Feature is an
  ordinary, already-supported state). 404 for an unknown Feature or link,
  or a link belonging to a different Feature.

**Legacy compatibility, explicit, not silent**: `PlaceFeatureCreate`/
`PlaceFeatureUpdate` keep their existing `source_id`/`zone_id` fields
completely unchanged syntactically. `PlaceFeatureUpdate`'s own docstring now
states plainly that these fields are a **full-replacement** operation on
the canonical link set (mirroring their exact pre-multi-view "the whole
association, replaced" semantics) -- setting either collapses the Feature
back to exactly one view (or zero, for `source_id: ""`). This is a
deliberate, documented choice, not a silent behavior divergence: it
preserves every one of the 14 pre-existing `PlaceFeatureUpdate`-related
tests' behavior unchanged (a single-link Feature's update is a no-op-shaped
replacement of the one link with itself), and the frontend's own new
"add another view" UI never uses this path for incremental editing -- only
the dedicated link endpoints do, so the ambiguity this legacy field
introduces for a genuinely multi-linked Feature is never actually
triggered through the product surface this milestone ships.

Proven: one view (`test_add_and_list_place_features` family, unmodified);
multiple views (`test_add_observation_link_creates_second_view`); add
(`test_add_observation_link_via_bare_source`); remove
(`test_remove_observation_link_recomputes_mirror`); duplicate prevention
(both the Zone-scoped and bare-Source cases, above); invalid Stream/Zone
(`test_add_observation_link_with_unknown_zone_is_rejected`); Zone/Source
mismatch (`test_add_observation_link_with_mismatched_source_and_zone_is_
rejected`).

## Reviewed truth

`information_class`/`provenance`/`actor_user_id` on the new link table
mirror `PlaceFeatureModel`'s identical fields and reasoning exactly -- a
human explicitly linking a camera/Zone view is the same "reviewed"
epistemic tier as recording the Feature itself. No new review subsystem was
invented; the existing convention was extended, per the governing brief's
own explicit instruction to prefer that over building a new one. Model
inference never creates or removes a link row anywhere in this milestone --
confirmed by direct code inspection: the only writers of
`PlaceFeatureObservationLinkModel` rows are `add_place_feature`,
`add_place_feature_observation_link`, and the legacy-compatibility
`_replace_feature_observation_links`, all three exclusively driven by an
explicit, authenticated user action.

## Cross-view analytics

Both `_feature_yield_summary` (recent-window activity) and
`_compute_feature_change_event_comparison` (before/after) now resolve their
own scope through a new shared helper, `_feature_observation_scopes`, which
returns every `(stream_id, zone_id)` pair this Feature's own links
resolve to. `_feature_scoped_visit_facts` builds a per-link `OR` of precise
SQL clauses from these pairs (a Zone-scoped link matches only that exact
Zone; a bare-Source-scoped link matches any Visit on any of that Source's
Streams) -- **not** one flattened `stream_id.in_(...)` + `zone_id ==`
pair, which would have let two different Zone-links on the same Stream
cross-contaminate each other's counts. `feature_change_comparison.py`
(the pure before/after engine) and `compute_feature_yield` (the pure yield
math) needed **zero changes at all** -- both were already, by design,
"the caller has already scoped and deduplicated" contracts with no camera
concept of their own; this milestone only had to fix the caller.

## Duplicate safety

The hard correctness requirement (governing brief section 11), proven
directly with real seeded SQLite data, not asserted:

- **A confirmed cross-camera pair counts once.** `_feature_scoped_visit_
  facts` now calls `_associated_visit_ids_to_exclude_from_counting` --
  the identical primitive `place_activity_report`/Bird Log/historical
  baseline already use for the same Place-wide question -- reused
  completely unmodified, never a second duplicate-counting engine. Proven
  by `test_multi_view_yield_dedupes_a_confirmed_cross_camera_pair` and,
  end-to-end, by the product-shaped scenario's own cardinal encounter.
- **Two independent, simultaneous animals remain two.**
  `test_multi_view_yield_counts_independent_simultaneous_visits_twice`
  seeds the identical timing/camera shape with no association row at all
  (the engine's own "no row for an out-of-range or independent pair"
  convention) and confirms both survive.
- **A merely `"possible"` (not `"associated"`) pair is not deduplicated.**
  `test_multi_view_yield_does_not_dedupe_a_merely_possible_pair` -- genuine,
  disclosed ambiguity is not confident enough to exclude either side,
  matching the exclusion primitive's own existing contract exactly.

This was previously a **correct but inert** simplification: a single-link
Feature's one linked Source is definitionally the only side of any
cross-camera pair in its own scope, so the exclusion call could never
actually fire before this milestone. Multi-view linking makes it
load-bearing for the first time; the fix reuses, rather than duplicates,
the exact accepted mechanism.

## Coverage semantics

`_feature_scoped_monitored_seconds` now calls `_place_activity_coverage_
summary` (a real interval **union**) instead of its own prior per-Stream
`sum()` -- the identical fix Multi-Camera Place Experience v2 already
applied to Zone Insights' own Place-wide aggregate, reapplied here.
`test_multi_view_coverage_is_union_not_sum` proves it with real, measured
numbers: two linked cameras, one monitored for the first 2 of the last 3
hours, the other for the full 3 hours (a genuine 2-hour overlap) --
`monitored_seconds` correctly reports the union (3 hours = 10,800s), never
the naive sum (5 hours = 18,000s). A single-linked-Stream Feature (the
common case) sees **no numeric change at all**: a union of one Stream's
own intervals is identical to that Stream's own sum, confirmed directly by
the unchanged pre-existing single-link tests all still passing.

## Feature detail UX

`PlaceFeatureDetail.feature.observation_links` (additive) makes every
linked view visible wherever a Feature's identity is already rendered:

- **Dashboard (`PlaceFeaturesCard.tsx`, edit mode):** each Feature row now
  shows an "Observed by:" block -- a chip per linked view (`{camera
  name}{" (archived)" if archived}{" — " + zone name if any}`), each with a
  remove (`×`) button reusing the exact `.tag-remove-button` precedent
  `HabitatPhenologyCard` already established, plus a "+ Add another view"
  affordance that reveals a cascading camera → Zone picker (mirroring
  `ZoneInsightsPanel`'s own established camera-then-Zone cascade idiom,
  with a stable "Whole camera (no specific Zone)" sentinel option,
  mirroring `ManualImportPage`'s "Unzoned" precedent). The pre-existing
  "Camera (optional)" create-time field -- which was, in fact, a bare Zone
  picker mislabeled -- was corrected to a real cascading camera → Zone
  picker in the same pass, since it lives on the exact surface this
  milestone was already touching.
- **Place Report page (`PlaceActivityReportPage.tsx`):** a calm "Observed
  by: {view}, {view}, ..." line under each Feature's name/type, so a user
  never has to mentally merge separate per-camera analytics to understand
  which views feed one coherent Feature history.

Archived-camera labeling matches this codebase's own single established
precedent exactly (`StreamsPage.tsx`'s `" (archived)"` suffix), not a new
visual pattern.

## Story behavior

**Zero changes required.** `_place_story_feature_events` already read
`feature_model.zone_id`/`feature_model.source_id` directly into each Story
event's own singular `zone_id`/`source_id` fields -- since those columns
are now a repository-maintained mirror (rather than deleted or
repurposed), this caller continues to work completely unmodified: a
0-or-1-link Feature's Story events show exactly the same value as before;
a genuinely 2+-link Feature's events honestly show `None`/`None` rather
than an arbitrary "first" camera. `_place_story_feature_events`'s own
`_compute_feature_change_event_comparison` calls automatically become
multi-view-aware for free, since that method's own internal scoping was
the only thing that changed. Proven end-to-end by the product-shaped
scenario: one Reviewed "added" event with two linked cameras produces
**exactly one** `feature_change` Story entry and **exactly one**
`comparison_insight` entry -- never one per camera.

## Archived-camera behavior

A genuine, disclosed inconsistency was found and closed here (not merely
preserved): `_feature_monitoring_stream_ids`'s pre-existing Zone-linked
branch never excluded an archived Source's Streams, but its bare-Source-only
branch did -- meaning a Feature linked only by Source (no Zone) went
silently, completely quiet the instant its one camera was archived, while
an otherwise-identical Zone-linked Feature's history stayed reachable. This
directly contradicts the accepted "archiving preserves history" doctrine
(and the precedent Multi-Camera Place Experience v2 already established for
every other discovery surface). The new `_feature_observation_scopes` does
not exclude archived Sources at all, for **any** link shape -- unifying
both cases onto the correct, doctrine-consistent behavior. Proven directly
by `test_archived_camera_link_preserves_historical_comparison` (a
bare-Source Feature's historical comparison survives its camera's own
archival) and, end-to-end, by the product-shaped scenario (Garden Camera
archived after its historical window closes; that window's own before/after
comparison and yield numbers are unchanged, and the archived link is
visibly marked `source_archived: true`).

## Zone lifecycle behavior

A second genuine, pre-existing gap was found and closed: `delete_zone`'s
existing reference guard checked four tables (`EventModel.primary_zone_id`,
`DetectionModel.zone_id`, `MotionEvidenceModel.zone_id`,
`DetectionProposalModel.zone_id`) plus provider-config `default_zone_id`,
but never checked `PlaceFeatureModel.zone_id` or (necessarily, since it did
not exist yet) any Feature-linked Zone -- a Zone attached only to a Place
Feature could be silently hard-deleted, leaving a dangling reference. Now
extended with a fifth check against `place_feature_observation_links.
zone_id`, reusing the identical `zone_has_review_context` `ValueError`
vocabulary the other four checks already raise. Proven by
`test_zone_deletion_blocked_when_linked_to_a_feature`. Zone rename requires
no code change at all: a link stores `zone_id`, never a cached name, so a
renamed Zone's new name is always reflected on the very next read (proven
implicitly by every test that reads `zone_name` back through a live join).

## Correction safety

Proven directly: adding a second view changes the very next read
(`test_add_observation_link_creates_second_view`); removing a view changes
the very next read
(`test_remove_observation_link_recomputes_mirror`); a species correction
propagates through cross-view yield with no invalidation step
(`test_multi_camera_place_feature_linking_scenario.py`'s own Act 8, and
`test_correcting_change_event_date_changes_comparison_on_next_read`'s
pre-existing coverage, unaffected); a camera rename never breaks a link
(the scenario's own Act 6, and every response is joined fresh via
`source_by_id`/`zone_by_id`, never a cached name); a hard-deleted Feature's
own link rows are deleted alongside it in the same transaction, never
orphaned (`test_hard_deleting_feature_cascades_observation_links`).

## Environmental-context behavior

Zero changes. `_feature_environmental_period_comparison` composes onto
`comparison.pre_start`/`post_end`/`window_days` -- fields the (now
multi-view-aware) wildlife comparison already produces -- and has no
camera concept of its own to begin with. Proven directly by the
product-shaped scenario: a Feature with two linked cameras produces exactly
one `environmental_comparison` per change event, never duplicated per
view, using the identical "notably cooler" wording/thresholds this
codebase's existing weather-composition tests already establish.

## Local Only

Proven directly, not assumed: the product-shaped scenario patches
`socket.socket.connect` to raise for its entire duration (the same
"catches any HTTP client, not just one specific library" technique
Year-over-Year Seasonality's own scenario already established) and
completes successfully end to end, including the environmental-context
composition step.

## Performance

Measured with this codebase's own established `before_cursor_execute`
query-counting harness (`tests/test_year_over_year_comparison_repository.
py`'s `_count_queries` pattern), against a synthetic fixture of 8 Features
across 5 Sources, half of them linked to two views:

| Call | Before this milestone | After first pass | After redundant-fetch fix |
|---|---|---|---|
| `get_place_feature_detail` (1-link Feature) | 7 queries | 13 queries | **10 queries** |
| `get_place_feature_detail` (2-link Feature) | n/a (unsupported) | 16 queries | 13 queries |
| `list_place_features()` across 8 Features | 1 query | 3 queries | 3 queries |
| `get_place_features_summary()` across 8 Features | 27 queries | 59 queries | **45 queries** |

`list_place_features()` stays at exactly 3 bounded queries regardless of
Feature or link count (one links query, one Sources query, one Zones
query) -- proven, not merely designed: `_place_feature_observation_link_
context` batches every Feature's own links, then every referenced
Source/Zone, in one call each, never once per Feature (avoiding the
Feature-count × link-count × Source/Zone-count multiplication the
governing brief explicitly warns against).

The first implementation pass measured a real, avoidable inefficiency: a
Feature's own (unchanging) link rows were being re-fetched once per change
event inside `_compute_feature_change_event_comparison`'s own call chain,
compounding with change-event count, not just link count. Found by this
milestone's own measurement discipline, not assumed acceptable --
`_feature_observation_scopes`/`_feature_monitoring_stream_ids`/
`_feature_scoped_visit_facts`/`_feature_yield_summary`/
`_compute_feature_change_event_comparison`/`_place_feature_response` all
gained an optional `links` parameter so a caller that already has the
Feature's link rows (`get_place_feature_detail`, `get_place_features_
summary`, `_place_story_feature_events`) fetches them exactly once and
threads them through, rather than re-querying per event or per Feature.
This closed roughly half the newly-introduced query overhead (`detail`:
13→10; `summary` across 8 Features: 59→45) with zero behavior change --
confirmed by the full `test_place_feature.py`/scenario-test suite passing
identically before and after this refactor. The remaining increase over
baseline is the proportionate, expected cost of a normalized relation
existing at all (one extra links query per Feature-detail bundle) and of
genuinely more links existing to resolve (`get_place_features_summary`'s
higher count reflects 12 total links across 8 Features, versus the
baseline's 8) -- proportionate to real complexity added, never a
cross-multiplication.

## Product-shaped proof

`tests/test_multi_camera_place_feature_linking_scenario.py` -- one
continuous, real, executable scenario matching the governing brief's own
worked example almost exactly: Place "Back Yard," Feature "Bird Bath,"
linked to Patio Camera / Bird Bath Zone and (added afterward, via the new
endpoint) Garden Camera / Pond Edge Zone. In one continuous test, proves:
one canonical Feature with two observation links; a confirmed cross-camera
cardinal pair collapsing to one counted encounter; two independent,
simultaneous chickadees remaining two; a real elapsed-time coverage union
(not a sum); a coherent "more common after" before/after comparison and
matching recent-yield snapshot spanning both cameras; exactly one Place
Story `feature_change` entry and exactly one `comparison_insight` entry
(never one per camera); a real "notably cooler" environmental-context
sentence, emitted once; Patio Camera renamed mid-scenario with the link
surviving untouched; Garden Camera archived after its historical window
closes, with that window's own comparison/yield numbers unchanged and the
link visibly marked archived; and a Reviewed species correction
(`carolina_chickadee` → `blue_jay`) propagating through cross-view yield
immediately, with the independent-encounter count unaffected and the
distinct-taxon count updated correctly. All under an enforced Local Only
guarantee (any network-socket attempt fails the test immediately).

## Validation

**Tier 1 (focused):** `tests/test_place_feature.py` grew from 50 to 86
tests (36 new: observation-link CRUD, duplicate prevention including the
NULL-zone-id edge case, cross-view dedup/coverage/comparison, archived-
camera reachability, Zone-deletion guard, HTTP surface for the two new
routes), all passing. New `tests/test_multi_camera_place_feature_linking_
scenario.py` (1 comprehensive product-shaped test), passing. New
`tests/test_persistence.py::test_schema_58_upgrades_to_current_with_
place_feature_observation_links`, passing.

**Tier 2 (directly-affected subsystems):** `tests/test_place_feature.py`,
`tests/test_multi_camera_place_feature_linking_scenario.py`,
`tests/test_camera_source_creation.py`, `tests/test_habitat_association.py`,
`tests/test_habitat_phenology.py`,
`tests/test_multi_camera_place_experience_scenario.py`,
`tests/test_place_activity_report.py`,
`tests/test_place_activity_report_repository.py`, `tests/test_place_story.py`,
`tests/test_place_story_repository.py`, `tests/test_source_activity.py`,
`tests/test_year_over_year_comparison.py`,
`tests/test_year_over_year_comparison_repository.py`,
`tests/test_year_over_year_product_shaped_scenario.py`,
`tests/test_zone_insights.py`, `tests/test_environmental_period_comparison.py`
-- **421 passed, 0 failed** (re-run again after the performance-refactor
pass, together with the full `tests/test_persistence.py` migration suite --
see "Final validation" below for the combined re-run result).

`ruff check` on every touched Python file, twice (once after the initial
implementation, once after the performance-refactor pass): **zero new
findings** both times, proven by a message-level (rule + text, not merely
line-number, which shifts) diff against a `git stash push -u`-isolated
clean baseline -- one pre-existing finding (`tests/test_place_feature.py`'s
own `sqlalchemy.select` import, previously unused) is now legitimately used
by this milestone's own new tests, and disappears from the findings list as
a side effect; nothing else changed.

Frontend: `tsc --noEmit` clean; `vite build` clean (105 modules, normal
chunked bundle, no size regression); `npm run test:e2e -- place-features` --
**12/12 passed** (7 pre-existing + 5 new: multi-view Observed-by
rendering with archived-suffix, zero-link honest state, the add-view
picker's accessible structure, multi-camera Place Report rendering);
directly-adjacent e2e (`today-report`, `place-activity-report`,
`biodiversity-summary`, `place-story`, `year-over-year`,
`mobile-viewport-audit` -- the full matrix, since `DashboardPage.tsx` and
`PlaceFeaturesCard.tsx` both changed) -- **68/68 passed**.

**Final validation (Tier 3):** given the schema bump plus the genuinely
cross-cutting surface touched (`models.py`/`database.py`/
`product_repository.py`/`main.py`/`schemas.py`), full Core
(`scripts/verify_core.py`) was run, matching every prior schema-bump
milestone's own justification for doing so: **5,854 passed / 1 failed / 3
skipped / 23 deselected (slow-marked) / 11 xfailed (57m23s)**. The one
failure, `test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields` (`'insufficient_recent_coverage' ==
'higher_recent_presence'`), is a new sighting of the same already-documented
class of pre-existing flakiness this codebase's last several milestones'
own validation baselines record for its sibling file
(`test_place_biodiversity_summary_repository.py`) -- a fixed test-fixture
date constant drifting against the real historical-baseline coverage
window as real wall-clock time continues to advance, unrelated to anything
this milestone touches (neither `place_change_summary.py` nor
`historical_baseline.py` were changed). Directly re-confirmed, not merely
assumed: a `git stash push -u` bisection ran this exact test against the
clean, unmodified `2771d4c` baseline and reproduced the byte-identical
failure and assertion text -- conclusive proof this milestone introduces
no regression here. Because this Tier 3 run's own test collection happened
at process start (before this milestone's own later performance-refactor
pass, described above, and before the product-shaped scenario test file
existed), the directly-affected subsystem sweep was independently re-run
in full afterward, against the truly final code (including the
performance refactor and the new scenario test): **462 passed, 0 failed**
(`test_place_feature.py`, the new scenario test, `test_persistence.py`'s
complete migration suite, and every other directly-adjacent file listed
above, together in one run) -- the combination of these two runs covers
both the full, unmodified-elsewhere Core surface and the truly final
Feature-linking-specific code with no gap.

`git diff --check`: clean (no whitespace errors).

## New defects found/fixed

Three real, pre-existing defects were found during this milestone's own
archaeology/implementation and fixed as part of it, none shipped
separately:

1. **Archived-Source Feature-association inconsistency.** A bare-Source
   (no Zone) Feature association went silently, completely quiet the
   instant its one camera was archived, while an otherwise-identical
   Zone-linked Feature's association stayed reachable -- contradicting the
   accepted "archiving preserves history" doctrine. Fixed by removing the
   archived-Source exclusion from Feature-association scope resolution
   entirely (an archived Source contributes zero live monitoring anyway,
   so including it is harmless for current-window yield and *necessary*
   for historical comparison correctness).
2. **`delete_zone`'s reference guard had no check for a Place-Feature-linked
   Zone at all** (not even the pre-existing singular association) -- a Zone
   referenced only by a Feature's observation link could be silently
   hard-deleted, leaving a dangling reference. Fixed by adding a fifth
   reference check against `place_feature_observation_links.zone_id`,
   reusing the existing `zone_has_review_context` vocabulary.
3. **A real, avoidable N+1-shaped re-fetch of a Feature's own link rows**
   once per change event inside the before/after comparison call chain,
   found by this milestone's own query-count measurement discipline (see
   "Performance," above) rather than assumed acceptable. Fixed by threading
   one up-front link fetch through the whole detail-bundle computation.

## Explicit non-goals / deferred opportunities

Everything the governing brief's own section 31 named as out of scope was
in fact not built: no broad multi-site; no camera calibration/homography/3D
geometry; no automatic cross-camera physical-object matching (a human
always decides one Feature; this milestone remembers it, nothing more); no
map/GIS UI; no Feature/Zone spatial topology engine; no ranked Feature
comparison; no Feature-specific year-over-year; no notification-level
cross-camera grouping; no consolidation of the ~6 independently-implemented
camera-filter UI controls elsewhere in the product (this milestone's own
new picker is a new, seventh, deliberately narrow instance -- an "add a
view" control, not a filter control, so it does not attempt to unify with
those); no GPU concurrency work; no multi-hour soak; no legacy 2-Stream
motion-pipeline expansion.

Also explicitly deferred, recorded rather than built by adjacency: a
dedicated "Feature detail" page/route (still folded into the existing
inline expand, unchanged by this milestone); representative evidence
selection inside Feature detail (Gate C's existing selector is still not
wired to "the best recent photo from this Feature's own linked views" --
unaffected, unattempted here); a ranked side-by-side Feature-comparison
view; Place Story's own still-unpopulated `source_id` for wildlife-kind
events (a separate, larger, previously-disclosed data-modeling exercise,
correctly out of this milestone's bounded scope per the governing brief's
own instruction not to reopen it); consolidating the frontend's ~6
camera-filter controls into one canonical component.

## Feature-freeze impact

This milestone closes exactly the one named product opportunity it was
authorized for. It does not touch, weaken, or reopen: Lane P (License,
`CLOSED`, untouched); Lane R (Complete Field Acceptance / true-latency-tail
evidence, `OPEN -- RELEASE-CRITICAL`, untouched -- no code in this
milestone's scope intersects the Observation Engine's admission/timing
path at all); BirdNET's commercial-adjacent legal posture (untouched,
unrelated); External Pre-Release Acceptance or Final Release Hardening
(not authorized by this milestone, not self-authorized here).

## Decision

**A**

A complete, cleanly-scoped, fully-proven closure of a long-named,
well-understood gap -- not a partial or hedged one. Every hard correctness
requirement the governing brief demanded (duplicate safety, coverage union,
backward-compatible migration, Reviewed truth, archived-camera
reachability, Local Only) is proven directly with real seeded data and a
comprehensive product-shaped scenario, not merely designed or asserted.
The schema/migration decision deliberately deviated from the brief's own
literal candidate shape after real repository-convention research, with a
concrete, migration-safety-driven justification, rather than mechanically
copying it. Two genuine, previously-undetected defects (archived-Source
association inconsistency; a real dangling-reference gap in `delete_zone`)
were found and fixed along the way, beyond what the milestone strictly
required. Performance was measured, not assumed, and a real, avoidable
inefficiency this milestone's own measurement surfaced was fixed before
shipping, confirmed safe by an identical-behavior re-run. Validation is
exhaustive and honest: 36 new focused tests plus one full product-shaped
scenario plus one schema-migration proof, zero new lint findings (verified
twice via baseline bisection), a clean frontend build, 12/12 new e2e plus
68/68 directly-adjacent e2e, a full 462/462 re-run of every directly-
affected subsystem against the truly final code, and a full Core run
(5,854/5,855, the one failure independently proven pre-existing and
unrelated via bisection) -- with the one honest gap in that evidence (Tier
3's own test-collection timing relative to a later, behavior-preserving
refactor) explicitly disclosed and closed by the separate, complete
Tier-2 re-run rather than glossed over. Nothing the brief actually asked
for was left undone or deferred; every deferred item is a genuine,
explicitly-scoped non-goal.

## Preserved files

Confirmed present, untouched, and byte-identical at both the start and the
close of this milestone (`git status --short`, both times, matched
exactly):

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
?? docs/multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md
?? docs/wildlife-detector-training-contract.md.orig
?? scripts/evaluate_small_bird_detector.py
?? scripts/materialize_wildlife_stage2.py.orig
?? scripts/train_wildlife_stage2_rfdetr.py.orig
?? src/mockingbird/detectors/small_bird_benchmark.py
?? src/mockingbird/training/wildlife.py.orig
?? tests/test_small_bird_benchmark.py
```
