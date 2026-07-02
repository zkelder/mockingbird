# Custom Bird Classifier Dataset Plan

## Purpose

MockingBird can eventually use reviewed local observations and attached media to
train or evaluate a backyard-focused bird classifier. That classifier should be
grounded in clean reviewed data, not raw suggestions or unreviewed events.

This plan defines dataset and training-readiness boundaries before any training,
runtime, dependency, model-file, or export implementation work.

Phase 9N expands the future export manifest contract in
[classifier-training-manifest-design.md](classifier-training-manifest-design.md).
That document is still design-only; manifest export remains future
implementation work.

## Product Flow

media-backed Visit -> user correction/review -> reviewed label becomes dataset
truth -> dataset quality/coverage checks -> local dataset export -> future
classifier training/evaluation outside core app -> future classifier output
returns `SpeciesSuggestion` evidence -> user correction remains truth.

## Dataset Source Of Truth

- Only reviewed corrections and `ReviewLabel` records are truth.
- `SpeciesSuggestion` is not truth.
- `MotionEvidence` is not truth.
- `DetectionProposal` is not truth.
- Unreviewed Visit labels are not training truth.
- Accepted suggestion status is not training truth.

## Candidate Training Examples

A future training example may come from:

- media-backed Visit with reviewed species label
- optional `snapshot_media_asset_id` or representative media
- zone context
- source and stream context
- timestamp/date context when available
- taxonomy label
- correction history/provenance
- dataset-quality flags

## Exclusion Rules

Future classifier exports should exclude or flag:

- unreviewed visits
- `unknown_bird` or `unknown_animal`, unless intentionally training an unknown class
- `false_positive`, unless intentionally training negative examples
- missing media
- privacy or ignore zone evidence
- conflicting corrections
- out-of-taxonomy labels
- low-quality media when quality flags exist
- duplicate near-identical examples, if later detectable

## Label Policy

- The canonical training label is the MockingBird taxonomy label.
- Aliases and common names should map to taxonomy IDs where possible.
- Freeform labels require cleanup before training.
- Unknowns and false positives need explicit policies; they are not accidental
  species labels.
- User correction wins over any model suggestion.

## Media Policy

- Dataset export should reference local media paths or copied local files
  according to future export policy.
- No cloud upload by default.
- Privacy zones must be respected.
- Media artifacts remain local.
- Missing or stale media references should fail safely or be skipped with
  reasons.
- Crops may be added later, but full or zone media is acceptable initially.

## Dataset Split Policy

Future train/validation/test splits should avoid leakage:

- split by Visit, Event, time, or Source where possible
- avoid same burst or near-duplicate frames across train and validation
- keep small-class warnings
- preserve label distribution reports

## Coverage And Readiness Metrics

Readiness signals should include:

- reviewed examples per species
- target taxonomy species covered/missing
- unknown count
- false positive count
- media-backed reviewed examples
- per-zone and per-source coverage
- conflicting/freeform labels
- minimum examples per target class
- dataset quality flags

## Export Format Plan

Future classifier-training export manifests should include:

- `example_id`
- `visit_id`
- `event_id`
- `media_asset_id`
- `local_media_path` or `exported_file_path`
- `label`
- `taxonomy_id`
- `common_name`
- `scientific_name` when available
- `zone_id`
- `source_id`
- `stream_id`
- `reviewed_at` or `created_at` when available
- `split`
- `quality_flags`
- `provenance`

Possible layouts:

- manifest JSON/CSV
- image files grouped by label
- labels file
- taxonomy file

See [classifier-training-manifest-design.md](classifier-training-manifest-design.md)
for the Phase 9N manifest fields, skip reasons, quality flags, taxonomy export,
and split policy. This phase does not implement these exports.

## Training/Runtime Separation

- Training should happen outside the core app or behind explicit tooling later.
- The core app must not gain training dependencies by default.
- No PyTorch, TensorFlow, ONNX Runtime, OpenVINO, TFLite, SpeciesNet, or
  training stack should enter the core install from this plan.
- Trained classifier output must return `SpeciesSuggestion` evidence only.
- No model output becomes `ReviewLabel` directly.

## Relationship To SpeciesNet

SpeciesNet can provide bootstrap suggestions. A custom bird classifier can
specialize on local/backyard data. Both are future `SpeciesSuggestion` adapters,
and neither is truth.

SpeciesNet may help compare or seed candidate labels, but reviewed correction
remains truth.

## Relationship To Future Custom Classifier

- The first custom classifier can be small and local.
- Target species should align with existing MockingBird taxonomy.
- Training data should come from reviewed exports.
- Evaluation should report per-class performance.
- Runtime must follow optional, lazy, local model guardrails.

## Failure/Risk Cases

- too few examples
- class imbalance
- poor lighting
- feeder angle bias
- duplicate frames
- label noise
- seasonal or plumage differences
- species lookalikes
- local overfitting
- privacy/media retention issues

## Implementation Plan

Tentative future phases:

- Phase 9N: dataset export manifest design for classifier training.
- Phase 9O: classifier training manifest API/implementation foundation.
- Phase 9P: classifier-readiness report/API.
- Phase 9Q: reviewed media-backed example export.
- Phase 9R: external training workflow docs.
- Phase 9S: optional custom classifier adapter boundary.

Keep these phases product-first: reviewed local data, export clarity, and
truth-boundary tests come before runtime or training work.

## Test Plan For Future Implementation

Future tests should prove:

- only reviewed labels are included
- unreviewed suggestions are excluded
- accepted `SpeciesSuggestion` alone is excluded
- missing media is skipped with reason
- privacy/ignore zones are excluded
- unknown and `false_positive` policy is respected
- conflicting labels are flagged
- manifest contains required fields
- train/validation split avoids leakage
- no model runtime is needed for export tests

## Explicit Non-Goals

- no training in this phase
- no model dependencies
- no generated dataset
- no SpeciesNet runtime
- no custom classifier runtime
- no automatic labels
- no reviewed truth from suggestions
- no cloud upload
- no production accuracy claims
