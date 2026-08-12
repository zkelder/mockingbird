# Wildlife Detector Training Contract

Status: Stage-3 tranche-construction implementation, version 0.3 (2026-08-12)

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

**Holdout v2 groundwork.** `temporal-capture --holdout-v2-session` marks
every frame a capture session retains with `RetainedFrameRecord.
holdout_v2_candidate=True`; `select_tranche` excludes any such frame from
Tranche A before prioritization. This milestone only adds the capability
and its downstream guard -- no Holdout v2 corpus is collected here.

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
