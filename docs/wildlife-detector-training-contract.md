# Wildlife Detector Training Contract

Status: Multi-Scene Backyard Domain Acquisition + Holdout v2 implementation, version 0.4 (2026-08-12)

This contract governs detector-training inputs and experiments. It does not
grant Observation truth, change deployed detector authority, or redefine the
product's broad class. The detector target remains `animal`; source taxa are
metadata used for coverage accounting.

## Source and truth gate

Every candidate source belongs in the versioned wildlife source registry
before pixels are selected. Stage 1 is preserved in
`src/mockingbird/training/wildlife_source_registry_v0_1.json`; Stage 2 is
governed by `src/mockingbird/training/wildlife_source_registry_v0_2.json`.
Materialization is fail-closed unless the active registry establishes:

- a canonical source and immutable version;
- compatible image and annotation rights;
- stable source and parent/sequence/camera identity;
- human localization boxes for positives, or curated empty-image truth for
  negatives; and
- a documented download mechanism.

Model- or agent-generated boxes are suggestions only. Image-label-only
positives go to human localization review and remain training-ineligible until
review is complete. A product Visit false-positive label is not whole-frame
negative truth. Unknown licensing, ambiguous annotation authority, and missing
lineage each block the source rather than weakening the manifest.

The Stage-1 accepted sources are Caltech Camera Traps 20200316/20210113
(CDLA-Permissive-2.0) and a per-image-license-filtered COCO 2017 subset
(CC BY 4.0 annotations). COCO geography is unknown/mixed and must never be
reported as North American provenance.

Stage 2 accepts Oregon Critters, Channel Islands Camera Traps, ENA24-detection,
the human-corrected NACTI boxed subset, Caltech Camera Traps, and independently
human-reviewed local empties. COCO is `transfer_only`, train-only, capped at
0.25 sampling weight, and excluded from the canonical Stage-2 materialization.
Missouri Camera Traps remains rejected because its available boxes and
geographic/taxonomic coverage do not establish the requested target-domain
corpus; other sources remain rejected when box authority, rights, download
coverage, or lineage is insufficient. Technical inconvenience alone is not a
license rejection.

## Pixel, size, and split semantics

Boxes use source-pixel geometry. Size buckets are computed before any training
resize from box width and height: `very_small` below 32×32-equivalent area,
`small` below 96×96, `medium` below 256×256, and `large` otherwise.

The strongest available lineage controls splitting:

1. sequence;
2. camera/site;
3. source identity; then
4. individual image identity when no stronger lineage exists.

Neighboring camera frames may not be randomly split. Caltech uses its official
camera-level train/validation partition. COCO retains its official split and
records that site lineage is unavailable. Corpus and split projections each
receive independent SHA-256 semantic fingerprints.

Stage 2 derives deterministic unseen-site/camera validation for Oregon and
Channel Islands and preserves the official location-grouped Caltech split.
ENA24 and NACTI boxes are train-only because their published bbox subsets do
not expose sufficiently complete camera/sequence lineage for an independent
validation claim. Context crops inherit their source identity and strongest
group, are train-only, and never replace the full-scene example.

## Leakage and frozen evaluation

Before training, the materializer must compare every selected example against
both corpus partitions and the frozen MockingBird benchmark using:

- exact SHA-256;
- source and derivative/parent identity;
- sequence, camera, and site lineage; and
- perceptual similarity.

An exact or lineage collision fails. A near-duplicate is reported only when
both dHash and pHash corroborate it; a coarse single-hash match is insufficient.
The frozen 75-image benchmark may never participate in selection, training,
threshold choice, augmentation, or early stopping. Its manifest and semantic
fingerprints are verified before use.

The frozen-75 remains valuable for regression and historical comparison
against every prior stage's own reported numbers, and its checksum/
fingerprint verification (`wildlife.verify_frozen_benchmark`) is unchanged
by this section. It is, however, heavily connected to the current field
environment -- the Stage-3 Tranche A build confirmed a real 200-frame
dual-hash near-duplicate rate between it and the local correction queue
(see "Stage-3 correction Tranche A," below) -- so repeated experimentation
and scene similarity limit its ability to prove broad generalization on its
own. Holdout v2 (see "Holdout v2 scene/session governance," below) is
required for any future promotion-quality generalization claim; nothing
here invalidates or deletes the frozen-75's historical results, and it
remains the sole frozen legacy/local regression benchmark until Holdout v2
has real scenes of its own.

## Experiment and checkpoint identity

An experiment identity binds the corpus and split fingerprints, architecture,
upstream weight identity and SHA-256, package version and artifact SHA-256,
resolution, batch and accumulation, optimizer, learning rates, scheduler,
precision, seed, and augmentation policy. A change creates a new identity.

Resumable checkpoints must preserve optimizer, scheduler, scaler, epoch, and
step state. Resume proof requires restoring one such checkpoint and completing
an additional optimization epoch. Model-only checkpoints are evaluation or
deployment candidates, not resume proof.

All training artifacts stay under ignored `data/training/`; only contracts,
registries, scripts, tests, and reports enter version control.

Stage-2 RF-DETR Small runs for at least ten completed epochs. Early stopping
may operate only after that floor and only on EMA Stage-2-validation metrics.
The required proof first completes epoch 0, then resumes the optimizer-bearing
`checkpoint_0.ckpt`. Best EMA and total checkpoints are retained, and the
metrics CSV is checksum-bound in evaluation evidence.

## Evaluation and decision

Threshold selection uses Stage validation only. Report precision, recall, F1,
IoU localization, false detections per curated-negative frame, source-pixel
size recall, and source taxon recall. Then apply the frozen threshold unchanged
to the frozen MockingBird benchmark and compare with production MDv5 at its
unchanged 0.1 operating point. Agent-reviewed diagnostic birds remain outside
population denominators.

The Stage-2 decision vocabulary is exactly:

- `PIPELINE_PROVEN_MODEL_WEAK`: target-domain training still lacks useful
  target-domain recall;
- `DOMAIN_TRAINING_PROMISING`: improvement over Stage 1 is large and credible,
  but more corpus or reviewed-local work is required; or
- `SHADOW_VALIDATION_READY`: the candidate beats MDv5 across enough supported
  target-domain, small-animal, and hard-negative strata to justify a bounded
  shadow validation, never direct promotion.

No training result changes production. Promotion still requires the repository's
detector-promotion contract and a larger, independently reviewed corpus.

## Exact-frame and localization-review boundary

`temporal-capture --retain-exact-analysis` is an explicit, default-off local
diagnostic option. For each retained analysis JPEG it binds exact bytes and
SHA-256 to provider outputs at the capture threshold, normalized detections,
model provenance, Geometry Attribution, and Counterfactual Lineage. The bounded
envelope states `creates_truth=false` and `creates_product_record=false`.
High-resolution burst evidence is kept separate and cannot carry this envelope.

`temporal-review-build` produces a self-contained page showing the untouched
retained image and a separate non-authoritative suggestion overlay. A named
human reviewer can mark Animal, No animal, or Ambiguous and draw broad-animal
boxes. The downloaded annotation records `full_frame_inspection` provenance and
must pass `temporal-review-validate`. This workflow intentionally has no species
review.

The deterministic Stage-2 local-correction queue is prioritization only. It
may use model outputs and agent diagnostics to rank exact local frames, but
those signals never become labels. Only named human full-frame review can add
positive boxes or whole-frame negative truth to a future materialization.

## Stage-3 correction Tranche A

`scripts/build_wildlife_stage3_correction_tranche.py`
(`mockingbird.training.wildlife_stage3_tranche`) selects a ~700-frame,
non-redundant, contamination-checked subset of the existing 2,000-frame
Stage-2 local-correction queue for the first high-information human review
pass. Like the Stage-2 queue itself, this is prioritization only: every
selected row keeps `review_status: "unreviewed"`/`training_eligible: False`
until a named human completes full-frame review.

**Lanes and priority tiers.** Three target lanes -- `small_far_positive_
opportunity` (~325), `local_hard_negative_confusor` (~275), `night_weather_
edge_condition` (~100) -- are filled from nine task-specified priority
categories, honestly merged to seven tiers where this queue's own metadata
cannot distinguish two categories from each other (see the module docstring
and `PRIORITY_TIER_ORDER`): a raw detector-miss/off-target-localization
signal is approximated from agent full-frame diagnostic review plus
detector engagement, since no frame in the current queue was ever retained
with `--retain-exact-analysis`'s Geometry Attribution/Counterfactual
Lineage envelope; branches/vegetation and shadows/pavement confusors are
not machine-distinguishable and are left to the human reviewer's own
difficulty tags. These are disclosed proxies, never claimed as pixel-verified
fact -- see docs/localization-attribution-contract.md and
docs/rejected-detection-attribution-contract.md for what a real envelope
would add automatically, with no caller change, once a future capture
retains one.

**Redundancy reduction.** Two layers, both bounded by each lane's own
target (`deduplicate`'s `min_keep`, never removing a real, distinct example
merely to reach a nominal count): same-session/same-time-bucket collapse
(cheap, catches the dominant "50 neighboring frames of one encounter" case),
then a dual-hash (dHash+pHash) near-duplicate pass strict enough not to
merge visually distinct frames that merely share a background (calibrated
against this real corpus: the frozen-benchmark contamination thresholds
below are deliberately looser and would over-merge here -- see
`INTRA_CORPUS_NEAR_DUPLICATE_DHASH_DISTANCE`'s docstring).

**Contamination.** Because the frozen 75-image benchmark and this local
queue share the same physical camera/scene, a real (not merely coincidental)
near-duplicate rate exists between them -- confirmed by direct visual
inspection, not assumed. `frozen_contamination_content_hashes` excludes any
exact or dual-hash near-duplicate match against the real, checksum-verified
frozen benchmark (`wildlife.verify_frozen_benchmark`) *before*
prioritization, so an excluded lane slot naturally backfills from the
next-best real candidate; `check_frozen_contamination` re-verifies the
final selection as an honest proof step. The frozen 75 remain evaluation-
only, exactly as every earlier stage requires.

**Split.** Selected frames are assigned `local_train_candidate`/
`local_validation_candidate` at whole-`capture_session_id` granularity
(never frame-randomized within a session), searching every possible
whole-session grouping for the one closest to the 75/25 target when the
session count is small enough to search exhaustively
(`_EXHAUSTIVE_SPLIT_SEARCH_SESSION_LIMIT`). This local validation split is
separate from, and never a substitute for, the frozen 75-image benchmark.

**Holdout v2 groundwork.** `temporal-capture --capture-purpose
holdout_v2_candidate` (the explicit-purpose successor to this milestone's
original boolean `--holdout-v2-session` flag -- see "Scene identity and
multi-scene acquisition," below) marks every frame a capture session
retains with `RetainedFrameRecord.holdout_v2_candidate=True`; `select_
tranche` excludes any such frame from Tranche A before prioritization. This
milestone only added the capability and its downstream guard -- no Holdout
v2 corpus was collected here; see "Holdout v2 scene/session governance,"
below, for the scene/session-level rules a real Holdout v2 corpus must
follow once one exists.

**Reviewer.** `stage3-tranche-review-build --tranche <tranche.json> --output
<dir>` builds a self-contained review packet reusing the exact same
`AnnotationSet`/`FrameAnnotation`/`validate_annotations` truth schema and
`temporal-review-validate` command the single-session Stage 6.6 reviewer
already uses -- not a second review system. The rendered page adds one-
frame-focused navigation, a progress count, an optional non-authoritative
suggestion-overlay toggle, per-box select+delete, optional difficulty tags
(`temporal_annotation.DIFFICULTY_TAGS`; frame-level, localization-only,
never a species taxonomy), and localStorage-based autosave/resume plus an
explicit fingerprint-checked "Load annotation.json" import, on top of the
original download-based export. `scripts/report_wildlife_stage3_
readiness.py` is a read-only accounting report that derives a Stage-3
readiness recommendation from the tranche's own lane/split composition,
never from a bare total-review count.

## Scene identity and multi-scene acquisition

Motivated by the Stage-3 Tranche A report's own disclosed limitation: the
existing 2,000-frame local-correction queue and frozen-75 benchmark come
primarily from one physical feeder/camera environment, so neither can prove
broad North-American backyard/outdoor-camera generalization on its own.

`temporal-capture` now requires `--scene-id` (a stable physical-scene
identity -- one materially distinct camera view/environment, e.g.
`feeder-close`, `lawn-north`, `woods-tree-line`, `deck-patio`, `driveway`,
`fence-garden`, `ground-level`; lowercase letters/digits/hyphens only,
never inferred from a small camera nudge) and accepts `--capture-purpose
{training_candidate,holdout_v2_candidate}` (default `training_candidate`),
the explicit-purpose successor to the prior `--holdout-v2-session` boolean,
reusing the identical underlying mechanism (`RetainedFrameRecord.
holdout_v2_candidate`). Both are recorded at the session level
(`CaptureSessionConfig.scene_id`/`capture_purpose`, so a session that
retains zero frames -- a genuinely quiet scene, still a useful signal --
never loses which scene was checked) and at the per-frame level
(`RetainedFrameRecord.scene_id`, mirroring `holdout_v2_candidate`'s own
existing per-frame-inherited-from-session pattern; `SCENE_ID_PATTERN`
governs both). `CaptureSessionManifest.__post_init__` cross-checks both for
internal consistency, failing closed on a hand-built manifest that
disagrees with itself (`scene_id_mismatch_between_config_and_frame`/
`capture_purpose_mismatch_between_config_and_frame`).

A running capture also now stops early and finalizes its manifest cleanly
(`stop_condition="manual_stop"`, the pre-existing but previously-unwired
`STOP_MANUAL`) on one Ctrl-C (SIGINT) or SIGTERM, in addition to its
`--duration`/resource bounds -- an operator covering several scenes in one
field visit no longer has to wait out a full bound once a scene is covered,
and no longer loses the whole session's manifest to an uncaught
`KeyboardInterrupt` doing so (`_CaptureLoop.request_stop`, wired via
`asyncio.get_running_loop().add_signal_handler` where the platform/event
loop supports it; falls back to duration/resource bounds only elsewhere).

`mockingbird.training.wildlife_multiscene.SceneFrameProvenance`/
`scan_scene_manifests` read this new per-frame provenance back from real
capture manifests -- source/camera (`stream_id`), scene ID, session,
capture time, exact frame SHA-256, dimensions, capture purpose (training/
holdout eligibility), and, when an already-loaded review `AnnotationSet` is
supplied, review provenance (reviewer, reviewed-at, positive/negative/
ambiguous outcome) -- satisfying the task's exact required-fields list.
Only frames carrying a non-empty, explicitly operator-set `scene_id` are
represented; a capture predating this field contributes nothing here,
honestly (see "Feeder correction subset v1," below, for how the
pre-existing single-scene corpus is separately, explicitly accounted for
instead of backfilled onto real capture manifests it never appeared on).

## Feeder correction subset v1

`mockingbird.training.wildlife_multiscene.select_feeder_correction_subset`
(`scripts/select_wildlife_feeder_correction_subset.py`) selects a
deterministic ~200-frame high-information subset of the existing 700-frame
Stage-3 Tranche A -- ~100 small/far-or-known-animal-opportunity, ~70 hard
local confusors/negatives, ~30 difficult lighting/weather/edge cases,
mapped directly onto Tranche A's own three existing lanes (no new lane
vocabulary) -- so the *default* Stage-3 domain-correction plan no longer
leans on the other ~500 feeder frames Tranche A also selected. It reuses
Tranche A's own already-calibrated priority order and `deduplicate`
redundancy reduction unchanged: a stricter `min_keep` against the smaller
target is "prefer non-redundant encounters," not a new redundancy rule.
It never mutates `review_status`/`training_eligible` and fails closed if
any candidate row is not already unreviewed/training-ineligible
(`feeder_subset_source_row_not_unreviewed`) -- creating no human truth is
enforced, not merely intended. Every selected row is tagged
`feeder_subset_scene_id=LEGACY_FEEDER_SCENE_ID` -- a disclosed backfilled
accounting label applied only by this function's own output, never a
literal captured `scene_id` (this corpus predates that field and was never
written back with one). The remaining ~500 Tranche A frames stay available
(the 700-frame tranche, its review packet, and `stage3-tranche-review-build`
are all unchanged and untouched) but are not automatically training-eligible
for the default Stage-3 plan.

Run against the real local 700-frame Tranche A on 2026-08-12: 200 frames
selected (100/70/30 exactly against target), drawn from 10 of Tranche A's
11 sessions; the most-concentrated single session contributed 54/200 (27%)
-- see docs/wildlife-detector-multi-scene-domain-acquisition-v1.md for the
full composition and every lane's dedup accounting.

## Holdout v2 scene/session governance

Holdout v2 must be genuinely independent from the current feeder-heavy
development benchmark, defined at the scene/session level *before* model
evaluation -- not derived after the fact from which frames happened to be
left over.

A scene or session is Holdout v2 the moment every capture ever taken for it
used `--capture-purpose holdout_v2_candidate`
(`mockingbird.training.wildlife_multiscene.holdout_v2_scene_ids`, derived
from real captured provenance, not a separately maintained registry an
operator could forget to update). A scene ever captured under *both*
purposes is a real, surfaced conflict (`conflicting_purpose_scene_ids`/
`assert_no_scene_purpose_conflict`), never silently resolved by picking one.

Once a scene/session is marked Holdout v2:

- `assert_scene_session_holdout_isolation` fails closed the moment any
  candidate row's own `scene_id`/`capture_session_id` matches a declared
  Holdout v2 scene/session -- independent of, and in addition to, that
  row's own per-row `holdout_v2_candidate` flag (the existing frame-level
  guard `wildlife_stage3_tranche.select_tranche`/`holdout_v2_content_hashes`
  already enforces). A second, coarser-grained layer a row cannot
  misreport as easily as one boolean, protecting a future ingestion path
  that copies frame bytes/metadata without faithfully carrying the
  per-frame flag forward.
- `holdout_v2_records` builds the same `HoldoutRecord` shape `wildlife.
  verify_frozen_benchmark` already returns for the frozen-75, so the
  already-tested `wildlife.contamination_report` -- exact SHA-256,
  source/parent identity, site/camera/sequence lineage, and dual-hash
  near-duplicate -- protects a captured Holdout v2 scene with zero new
  contamination logic. `camera_id` carries the scene id and `sequence_id`
  the capture session id: a neighboring burst/sequence frame from the same
  session is caught by the lineage-group match even when its own pixels
  differ enough to dodge the hash checks (proven directly, not merely
  claimed -- see `test_holdout_v2_records_catch_a_neighboring_sequence_
  frame_via_lineage`). A derived crop is caught the same way once crop
  generation exists (give the crop's `parent_identity` its source frame's
  own `source_identity`, already produced by `holdout_v2_records`) -- no
  local crop-generation step exists yet in this milestone.
- No threshold tuning or early stopping may read a Holdout v2 scene/session.
  This is a process discipline this milestone documents; nothing in the
  current threshold-selection/training pipeline reads per-scene local data
  at all yet, so there is no additional code path to guard beyond the
  isolation check above.

The frozen-75 remains a separate, already-governed holdout (`wildlife.
verify_frozen_benchmark`, contamination-checked independently by
`wildlife_stage3_tranche.frozen_contamination_content_hashes`); Holdout v2
is additive to it, never a replacement for it.

## Scene diversity accounting

`mockingbird.training.wildlife_multiscene.scene_diversity_report`
(`scripts/report_wildlife_scene_diversity.py`) is a read-only report over
the legacy feeder subset (if built) and any newly scanned multi-scene
manifests: total/training/holdout scenes, sessions per scene, exact
retained frames, human-reviewed positives/negatives, ambiguous frames,
animal boxes, size buckets (`mockingbird.training.wildlife.source_pixel_
size_bucket`, the same buckets Stage 1-3 already use, never a new bucketing
scheme), and scene concentration. Concentration is a visibility heuristic
only (`SCENE_CONCENTRATION_WARNING_FRACTION=0.5`, computed only across
*training*-purpose scenes so a Holdout v2 scene can never inflate or
deflate it): flagged, never enforced -- nothing in this pipeline blocks
selection, review, or training because of it. Run against the real local
corpus on 2026-08-12: 1 scene (the legacy feeder, 100% training-scene
concentration, honestly flagged), 0 of the 5-8/3-5/2+ first multi-scene
targets met yet (see "A practical first multi-scene target," below).

## A practical first multi-scene target

Not thousands of random frames: approximately 5-8 materially distinct
physical scenes, at least 3-5 training/domain-correction scenes and 2+
Holdout-v2-only scenes (`FIRST_MULTISCENE_TARGET_TOTAL_SCENES=5`/
`_TRAINING_SCENES=3`/`_HOLDOUT_SCENES=2` are the lower-bound readiness bar
`scene_diversity_report`'s own `first_multiscene_target` checks; the fuller
5-8/3-5/2+ range is a human judgment call the report's raw counts support
but do not themselves gate). No scene is required to contain an animal
before the workflow is useful -- empty frames, vegetation motion, branches/
bark, shadows, fences, pavement, and different lighting/weather are all
explicitly acceptable, and expected, training-scene content. Wildlife is
never manufactured or placed artificially; a scene with genuinely nothing
observed is still a useful negative-domain signal once captured honestly.

Proposed first scenes (physically practical with the existing hardware --
see docs/wildlife-detector-multi-scene-domain-acquisition-v1.md "Operator
instructions" for exact commands):

| Scene id | Purpose | Why |
| --- | --- | --- |
| `feeder-close` | training | Continuity check against the legacy corpus's own dominant view; confirms the workflow itself before spending capture time on new ground. |
| `lawn-open` | training | Open-ground small/far bird and squirrel opportunity; vegetation motion, no feeder clutter. |
| `deck-patio` | training | Pavement/hardscape confusors, different lighting geometry, a common real backyard vantage. |
| `fence-garden` | training | Fence-line confusors, dense vegetation/shadow texture distinct from the feeder scene. |
| `woods-tree-line` | holdout v2 | Materially distinct camera position (tree line, not feeder-adjacent); branch/bark/dappled-shadow confusors the frozen-75 already shows are a recurring failure family, captured somewhere the model has never trained on. |
| `driveway-or-ground-level` | holdout v2 | A structurally different vantage (pavement-dominant or ground-level), maximizing independence from every training-purpose scene above. |

Four training scenes and two Holdout-v2 scenes meets the lower-bound bar
(5 total/3 training/2 holdout) at six scenes total, inside the 5-8 target
range; `feeder-close` intentionally continues the existing corpus rather
than replacing it, since "adapt style, do not redefine the detector as a
feeder detector" (see "Stage-3 future corpus policy," below) still needs
feeder-scene coverage -- just no longer *disproportionate* coverage.

## Stage-3 future corpus policy

Materialize Stage 3 (not in this milestone) as five distinct, explicitly
governed layers, never blended without lineage:

A. **Sealed broad North-American public Stage-2 corpus** -- the existing
   Stage-2 source registry (`wildlife_source_registry_v0_2.json`) and its
   already-accepted sources, unchanged.
B. **Human-reviewed local correction data from MULTIPLE scenes** -- the
   primary purpose of the multi-scene acquisition workflow this milestone
   adds: adapt camera/home-scene style, never redefine the detector as a
   feeder detector.
C. **The current feeder correction subset, deliberately capped** -- the
   ~200-frame subset above, never the full ~700/2,000-frame feeder pool, so
   one physical environment cannot dominate the local-correction mass.
D. **Separate unseen local validation scenes** -- distinct training-purpose
   scenes/sessions reserved for model selection/calibration, disjoint by
   whole scene/session from both training (B/C) and final holdout (E).
E. **Completely isolated Holdout v2** -- scenes/sessions captured
   exclusively under `--capture-purpose holdout_v2_candidate`, never
   touched by training, validation, or tuning at any point (see "Holdout v2
   scene/session governance," above).

The broad public corpus (A) remains the foundation; B/C exist to adapt
style, not redefine the target class. No Stage-3 corpus is materialized or
trained in this milestone.

## Future split policy

Local data must split by complete scene/session groups -- never neighboring
frames or the same physical scene on both sides merely to hit a numerical
75/25 ratio (the same whole-group discipline `wildlife_stage3_tranche.
assign_local_split`/`assert_no_split_leakage` already enforce at the
session level for Tranche A; a future multi-scene split adds the *scene*
level on top of that, never relaxes the session level).

Stage-3 training should eventually use: public anti-leakage training data
(A) plus local correction training scenes (B/C). Model selection/
calibration should use separate local validation scenes (D) only. Final
comparison should use the legacy frozen-75 regression benchmark plus the
new Holdout v2 (E) -- never (D) or any training-side data. No tuning
against Holdout v2, ever.
