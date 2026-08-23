# Multimodal Observation & Soundscape v1

Status: implemented. Makes visual and acoustic evidence behave as coherent
evidence about wildlife activity at a place, rather than two unrelated
sensing systems -- see [roadmap.md](roadmap.md) "Post-v0.1 lanes" > "Audio",
which named this exact fusion work as deliberately deferred until now.
Builds additively on
[acoustic-birdnet-observation-foundation-v1-contract.md](acoustic-birdnet-observation-foundation-v1-contract.md)
(the independent acoustic path this milestone links to the visual one) and
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
(the multi-subject sibling-Visit mechanism this milestone's own multi-
subject handling reuses the philosophy of, never the mechanism itself --
audio is never merged into a visual Event the way two visual tracklets can
be).

## Governing doctrine (recap)

- Human-reviewed Observation remains authoritative. Models never vote truth
  into existence.
- Agreement between a visual and an acoustic suggestion is useful evidence,
  never automatic confirmation.
- Conflict between them is evidence uncertainty to represent honestly, never
  an error to hide.
- Audio-only and visual-only activity both remain fully valid, unchanged.
- Multiple subjects/species must not be collapsed merely because they occur
  near one another in time.

## Architecture decisions

**Association owner.** No new "MultimodalObservation" truth object.
`ProductRepository` owns a bounded, deterministic association step wired
into the three existing candidate-Visit creation paths
(`create_acoustic_candidate_visit`, `extend_acoustic_candidate_visit`,
`_create_candidate_visit_locked`). Both original Visits/Events remain
independently reviewable; nothing here ever sets `reviewed_label`/
`review_status`, mints a `ReviewLabel`, or merges an acoustic Visit's
evidence into a visual Event's `event_id` (that Event-sharing mechanism
stays reserved for genuinely simultaneous visual siblings -- see
`tracklet-visit-assembly-contract.md`; audio has no geometry, so folding it
into that mechanism would risk exactly the "fabricate a box that was never
observed" trap the acoustic foundation contract already refused).

**Persistence.** A new additive table, `visit_associations`
(`VisitAssociationModel`, `src/mockingbird/repository/product_repository.py`),
schema 46. One row per `(visual_visit_id, acoustic_visit_id)` pair judged
`"associated"` or `"possible"`. There is deliberately no `"independent"`
row -- a pair outside the association window simply has no row, matching
this codebase's "never fabricate a relationship that was never found"
convention (`SceneConfusorRegionModel`'s identical precedent). Rows are
upserted, not append-only: `ProductRepository._reconcile_multimodal_
association_for_event` always recomputes every row for a visual Event's
*current* full sibling set from scratch, so a Visit uniquely `"associated"`
with one acoustic Visit correctly downgrades to `"possible"` the moment a
second visual sibling later makes the acoustic evidence genuinely
ambiguous -- proven directly by `test_scenario_6b_late_arriving_sibling_
downgrades_a_stale_associated_row` in
`tests/test_multimodal_observation_acceptance.py`.

**Temporal model.** `src/mockingbird/observation/temporal_evidence.py`
(pure, dependency-free): `event_evidence_interval` normalizes any already-
persisted `EventModel.started_at`/`ended_at` (both visual and acoustic
Events already store correctly-anchored absolute instants there -- see
"Acoustic idempotency" below for the acoustic anchor); `acoustic_window_
interval` independently re-derives an absolute interval from a raw BirdNET
window (`MediaAssetModel.captured_at` + `window_start_ms`/`window_end_ms`),
proven equal to `acoustic_ingest.py`'s own `observed_at` computation by
`test_acoustic_window_interval_matches_acoustic_ingest_observed_at_formula`
in `tests/test_temporal_evidence.py`, so the two paths cannot silently
diverge. Never reads analysis time, DB-insertion time, or UI-render time.
`EvidenceInterval.clock_provenance` records which of these facts actually
backed a given interval (`visual_event_range` / `acoustic_event_range` /
`acoustic_window_media_captured_at` / `acoustic_window_epoch_anchor_
fallback`), so an epoch-anchor fallback is always honestly distinguishable
from a real timestamp.

**Association engine.** `src/mockingbird/observation/multimodal_
association.py::evaluate_temporal_association` (pure, deterministic,
direction-agnostic): given one `subject` interval and a list of opposite-
modality `candidates`, returns a decision per candidate still in range.
Explicit fixed thresholds, not a probabilistic fusion framework:

| Constant | Value | Meaning |
| --- | --- | --- |
| `STRICT_WINDOW_MS` | 15,000 ms | Overlap or gap within this -> eligible for the confident tier |
| `POSSIBLE_WINDOW_MS` | 60,000 ms | Overlap or gap within this -> eligible for the coincident tier; beyond it, dropped entirely (independent) |

Tiers:

- `"associated"`: exactly one opposite-modality candidate in range at all,
  and it is within the strict window.
- `"possible"`: more than one candidate competes for the same subject
  (Phase H's multi-subject/multi-species conservatism), or the sole match
  is only within the wider window.

Species/taxon suggestions are never an input to this decision -- reused
only afterward, at read time, as a *separate* agreement signal (see
"Agreement/conflict," below). Not yet field-tuned: no real colocated
camera+microphone timing measurement exists yet (see "Hardware-deferred
acceptance").

**Multi-subject handling.** Every visual sibling under one Event shares
that Event's own `started_at`/`ended_at` (`VisitModel` carries no per-
sibling timestamp of its own in the current schema -- see "Known
limitations"), so every sibling's interval is necessarily identical for
association purposes. When 2+ siblings are in range of one acoustic
candidate, `evaluate_temporal_association`'s own "more than one candidate"
rule makes all of them `"possible"`, never `"associated"` -- the acoustic
evidence is never blindly assigned to one arbitrarily-chosen subject.

**Idempotency.** The lookback+upsert in `_reconcile_multimodal_association_
for_event` is a full recomputation guarded by `VisitAssociationModel`'s own
`uq_visit_association_pair` unique constraint, so re-running it after
restart/reprocessing (Scenario 9) never creates a duplicate row and always
converges to the same deterministic tier -- see
`test_scenario_9_reassociation_after_restart_is_deterministic_and_creates_
no_duplicates`.

## Acoustic idempotency (Phase B) -- reproduced and closed

The suspected gap was real. `create_acoustic_candidate_visit`/`extend_
acoustic_candidate_visit`'s idempotency key was `(media_asset_id,
window_start_ms, window_end_ms, adapter_id)` -- species was never part of
it. Two distinct species detected in the identical merged BirdNET window
(plausible: two birds calling at once, both merged to the same start/end by
`acoustic_ingest._merge_same_species_detections`) collided: the second
species' insert matched the first species' already-persisted row and was
silently returned as `"idempotent_repeat"` -- no second Visit, no Event, no
error, no log. This directly contradicted the acoustic foundation
contract's own claim that two different species always become two
independent candidates.

Fix: `suggested_label` (the taxonomy-resolved species key) is now part of
the idempotency filter in both methods (species resolved *before* the
idempotency check, not after, so the check itself can use it). Backed by a
new DB-level unique index, `ux_species_suggestions_acoustic_idempotency`
(schema 45, `SpeciesSuggestionModel.__table_args__` +
`_migrate_to_acoustic_species_scoped_idempotency`), scoped to
`window_start_ms IS NOT NULL` so no image-backed suggestion is affected.
Provably safe to add on any pre-existing real database without a defensive
cleanup pass: the *old* 4-column key already guaranteed at most one row per
that 4-tuple regardless of species, so no two rows can already share the
*stricter* 5-column key either -- see the migration's own docstring for the
full proof.

Regression tests: `tests/test_acoustic_species_idempotency.py` (four
focused tests -- the core collision, same-species-retry-still-idempotent,
the `extend` path, and the DB-level index itself) and
`test_schema_44_upgrades_to_current_with_acoustic_species_scoped_
idempotency` in `tests/test_persistence.py`.

## Same-encounter, agreement, and conflict semantics (Phases E/F/G)

Both original Visits/Events are always preserved -- never merged, never
one erased. Correction of either Visit's own `reviewed_label` is
completely independent of the other; nothing in this milestone ever writes
one Visit's review state from the other's. `taxon_agreement` (`"agrees"` /
`"differs"` / `"not_comparable"`) is computed fresh at *read* time
(`ProductRepository._effective_taxon_label` -- confirmed always outranks
provisional, exact case/whitespace-normalized string match, no fuzzy
matching, no synthetic fused confidence value), never stored, so a later
re-suggestion or correction can never leave a stale agreement/conflict fact
behind. A visual and an acoustic suggestion agreeing is surfaced as
"independent evidence agrees," never as "species confirmed" -- reviewed
human confirmation remains the only state transition that matters for
truth. A conflict is retained and surfaced exactly like agreement, never
hidden or arbitrarily resolved; human review picks (or overrides) the
authoritative taxon through the completely unmodified `ReviewLabel`/
`POST /api/review-labels` path.

## Multi-subject and multi-species correctness (Phase H)

Both mandatory combined cases are proven directly in
`tests/test_multimodal_observation_acceptance.py`:
`test_scenario_6_acoustic_evidence_not_blindly_assigned_to_every_visual_
subject` (two visual siblings, one acoustic detection -> both `"possible"`,
never `"associated"`) and `test_scenario_7_two_acoustic_species_in_one_
window_both_survive_and_associate` (two acoustic species in one window,
one visual subject -> both survive independently post-Phase-B-fix and both
correctly associate). `test_scenario_6b_late_arriving_sibling_downgrades_a_
stale_associated_row` proves the harder ordering (acoustic detection
arrives *between* two siblings' own creation) is also handled correctly via
full recomputation, not just the easier ordering.

## Review/evidence UI (Phase I)

`VisitDetail.multimodal_associations` (new field, `api/schemas.py`) exposes
every association touching a Visit, each carrying the full opposite `Visit`
object (mirrors `sibling_visits`' own "return the real Visit, not a
summary" precedent) plus `tier`/`taxon_agreement`. `VisitDetailPage.tsx`
renders one panel per association using only plain wording -- "Also heard
nearby" / "Also seen nearby", "Evidence agrees" / "Evidence differs",
"Needs review" for the `"possible"` tier, "Likely the same encounter" /
"Possibly related -- not confirmed as the same encounter." -- never
"BioCLIP", "BirdNET", logits, or window offsets. No major UI redesign; the
panel mirrors the existing sibling-Visits banner's exact shape and styling.

## Today / Bird Log integration (Phase J) -- bounded, with an explicit gap

Audio Visits already appeared correctly in Today/Bird Log before this
milestone (Acoustic Foundation's own "no backend changes required" result)
with an existing "🔊 Heard" treatment (`DashboardPage.tsx`'s `VisitPreview`,
`BirdLogPage.tsx`'s `JournalThumbnail`). This milestone adds the richer
per-Visit association view at the Visit Detail level (Phase I, above),
reachable by opening either Visit of an associated pair from Today or Bird
Log exactly as today.

**Update (Everyday Discovery / Product Experience v2, 2026-08-23):** the
list-level deduplication this section originally disclosed as not-yet-
implemented was completed by that later milestone, using exactly the
presentation-layer approach this section predicted -- `_collapse_associated_
multimodal_pairs`/`_collapse_associated_multimodal_journal_observations`
now collapse a confidently-`"associated"` pair into one row inside
`dashboard_summary`'s `recent_activity`/`best_moments` and the wildlife-
journal gallery, reusing the already-computed `multimodal_association` tier
fact this section named -- no new association logic, matching the bounded
scope this contract called for. Left in place as historical record of the
original, deliberate deferral rather than deleted, per this doc's own
convention elsewhere of recording what a milestone chose not to do and why.

## Soundscape foundation (Phase K)

`src/mockingbird/analytics/soundscape.py` (pure, mirrors `place_activity_
report.py`'s computation style) answers exactly the bounded questions
named: species heard, acoustic encounter count, hourly acoustic activity,
and the visual-only/acoustic-only/multimodal breakdown, for an explicit
period. `ProductRepository.soundscape_summary` builds its input facts
through the identical canonical resolver `place_activity_report` already
uses (`_stream_visit_summary_from_models` + `visit_fact_from_stream_visit_
summary`), so truth precedence cannot diverge between the two reports.
Exposed read-only at `POST /api/analytics/soundscape-summary`. No raw
inference dump, no spectrogram, no ecological claim beyond the observed/
reviewed data -- no dedicated frontend page was built (matching "no large
soundscape analytics product"); the API is the bounded, queryable
foundation the phase calls for.

## Research/export representation (Phase L)

Two new fields on the generic export row (`ResearchObservation` in
`src/mockingbird/research/research_export.py`, and the matching JSON/CSV
shapes): `evidence_modality` (`"visual"` / `"acoustic"`, from `EventModel.
event_type`) and `multimodal_association` (`"none"` / `"possible"` /
`"associated"`, the Visit's own strongest tier). Orthogonal to
`acquisition_type` (capture *path*: live/offline), never conflated with it.
Model agreement never becomes observational authority in an export: these
are honest provenance/relationship facts alongside the completely
unchanged reviewed-truth eligibility gate
(`evaluate_research_export_eligibility`), which already applied to acoustic
Visits automatically (no `event_type` filter on the underlying Visit
query) before this milestone touched anything. Camtrap DP's own fixed
external row shape (v1.0.2) was deliberately left unextended -- adding a
non-spec field would risk external-validator conformance for a fact the
generic CSV/JSON export already carries honestly.

## Multimodal acceptance corpus (Phase M)

`tests/test_multimodal_observation_acceptance.py` exercises the real,
unmodified production repository paths (never a reimplemented shadow
pipeline) against an isolated `tmp_path` SQLite database. One real audio
fixture is reused for provenance where it materially matches a scenario:
`tests/fixtures/acoustic/overlapping_cardinal_chickadee_48k_mono_derived.wav`
(already present in the repository from the Acoustic Runtime milestone) for
Scenario 7's two-species-in-one-window case. Every other timing
relationship is synthesized deterministically via explicit `observed_at`
values -- BirdNET/MDv5 inference itself is out of scope (already proven
elsewhere: `tests/test_birdnet_adapter.py`,
`tests/test_acoustic_ingest_real_model.py`,
`tests/test_candidate_visit_repository.py`); this corpus proves what
happens *after* a detection already exists, which is what the association
engine actually reasons about. This is an acceptance corpus, not a
research-grade multimodal benchmark.

Covers, at minimum: matching visual+acoustic species with strong overlap;
conflicting visual/acoustic species; visual-only; audio-only; two visual
subjects; two acoustic species (reusing the real overlapping-species
fixture); temporally-near-but-independent timing (plus two explicit
threshold-boundary sub-cases); and restart/idempotency.

## Schema

`CURRENT_DATABASE_SCHEMA_VERSION`: 44 -> 46.

- **45** (`_migrate_to_acoustic_species_scoped_idempotency`): one new
  partial unique index on the existing `species_suggestions` table. No data
  written, no data at risk (see "Acoustic idempotency," above, for the
  safety proof). Guarded by `inspect(connection).has_table(...)`, matching
  `_migrate_to_acoustic_runtime_queue`'s own precedent, for the narrow
  minimal-ad-hoc-schema migration-path tests that do not construct every
  product table.
- **46** (`_migrate_to_visit_multimodal_association`): one new, empty,
  additive table (`visit_associations`). No backfill -- an upgraded
  installation's association history starts exactly as cold as a brand-new
  one, mirroring `_migrate_to_scene_confusor_regions`'s identical
  precedent.

Both proven via dedicated upgrade-in-place tests in `tests/test_
persistence.py` (`test_schema_44_upgrades_to_current_with_acoustic_
species_scoped_idempotency`, `test_schema_45_upgrades_to_current_with_
visit_multimodal_association`) and via ordinary fresh-database creation
(every other passing test in the suite). Eight pre-existing hardcoded
`CURRENT_DATABASE_SCHEMA_VERSION == 44` sentinel assertions (each one's own
comment already documented it as "tracks whatever the latest schema version
is") were bumped to 46 across `tests/test_candidate_visit_repository.py`,
`tests/test_camera_health.py`, `tests/test_camera_node.py`,
`tests/test_species_candidate_packs.py`, `tests/test_visit_collections.py`,
`tests/test_yard_map.py`, and `tests/test_visit_tags.py`.

## Known limitations

- **Per-sibling sub-interval timing.** A multi-subject Event's sibling
  Visits all share the Event's own `started_at`/`ended_at` range; there is
  no schema field recording when *within* that shared range one specific
  sibling was actually present. This is exactly why the association engine
  correctly cannot distinguish which of several simultaneous subjects an
  acoustic detection belongs to -- it is an honest limitation of currently-
  available data, not a defect in the association logic itself.
- **Place is the whole install.** There is no first-class `Place` entity
  yet (`place_activity_report.py`'s own documented boundary). Association
  scope is therefore "the same local install," not a real per-Place/per-
  Source-proximity boundary -- correct and sufficient for today's single-
  camera/single-microphone common case, but a future multi-camera,
  multi-microphone, large-property installation could see association
  candidates considered across Sources that are not actually physically
  near each other. `Source`/`Stream` identity is available on every
  association's underlying Visits for a future stricter policy to consume;
  it does not gate the v1 decision.
- **Today/Bird Log list-level dedup** is not implemented -- see Phase J,
  above.
- Real BirdNET model licensing, real microphone hardware validation, real
  LTE/remote-field validation, and the completed-host-transport-file
  consumer/retention lifecycle all remain exactly as previously disclosed
  and are unaffected by this milestone.

## Hardware-deferred acceptance

`STRICT_WINDOW_MS`/`POSSIBLE_WINDOW_MS` are disclosed, reasonable, but not
field-tuned constants. Validating them requires a real Camera Node camera
and a real colocated microphone capturing a genuine shared encounter, then
measuring actual clock alignment/vocalization-to-visibility offset in the
field -- no such hardware exists in this environment. This milestone's own
acceptance corpus proves the *mechanism* (deterministic tiering, upsert
idempotency, multi-subject/multi-species conservatism) is correct against
synthesized timing; it does not and cannot establish that 15s/60s are the
right real-world thresholds. Treat both constants as an explicit future
field-calibration target, not a finished number.
