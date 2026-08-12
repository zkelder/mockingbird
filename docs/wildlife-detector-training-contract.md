# Wildlife Detector Training Contract

Status: Stage-1 implementation, version 0.1 (2026-08-11)

This contract governs detector-training inputs and experiments. It does not
grant Observation truth, change deployed detector authority, or redefine the
product's broad class. The detector target remains `animal`; source taxa are
metadata used for coverage accounting.

## Source and truth gate

Every candidate source belongs in
`src/mockingbird/training/wildlife_source_registry_v0_1.json` before pixels
are selected. Materialization is fail-closed unless the registry establishes:

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

## Evaluation and decision

Threshold selection uses Stage validation only. Report precision, recall, F1,
IoU localization, false detections per curated-negative frame, source-pixel
size recall, and source taxon recall. Then apply the frozen threshold unchanged
to the frozen MockingBird benchmark and compare with production MDv5 at its
unchanged 0.1 operating point. Agent-reviewed diagnostic birds remain outside
population denominators.

The Stage-1 decision vocabulary is:

- `PIPELINE_FAILED`: corpus or training integration is invalid;
- `PIPELINE_PROVEN_MODEL_WEAK`: the pipeline works but the candidate lacks
  useful target-domain signal; or
- `PIPELINE_PROVEN_PROMISING`: valid training shows meaningful target-domain
  improvement worth scaling.

No Stage-1 result changes production. Promotion still requires the repository's
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
