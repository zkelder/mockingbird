# Custom Bird Classifier Dataset Plan

## Purpose

MockingBird can eventually use reviewed local observations and attached media to
train or evaluate a backyard-focused bird classifier. That classifier should be
grounded in clean reviewed data, not raw suggestions or unreviewed events.

This plan defines dataset and training-readiness boundaries before any training,
runtime, dependency, model-file, or export implementation work.

Phase 9N expands the future export manifest contract in
[classifier-training-manifest-design.md](classifier-training-manifest-design.md).
That document remains the manifest shape contract. Phase 9Q implements the
read-only preview and Phase 9T implements metadata-only backend file export.

Phase 9O adds a read-only classifier readiness report before manifest export
implementation. The report summarizes reviewed media-backed examples, label
coverage, skip reasons, and warnings; it does not generate datasets.

Phase 9P surfaces that readiness report in the frontend so users can inspect
species coverage, skip reasons, and warnings before any manifest export work.
There is still no manifest export or training in this phase.

Phase 9Q adds a read-only backend classifier training manifest response. It
returns structured example, skip, taxonomy, split, and provenance data in memory
only; it does not write manifest files, copy media, generate datasets, train, or
run classifier runtime.

Phase 9R adds a frontend manifest preview. Users can inspect summary counts,
examples, skipped records, taxonomy, warnings, and copy/download the loaded JSON
in the browser only. It still does not create server-side export files, copy
media, generate datasets, train, or run classifier runtime.

Phase 9S documents the future backend manifest file export policy in
[classifier-manifest-file-export-design.md](classifier-manifest-file-export-design.md).
Media copying remains a separate future phase.

Phase 9T implements backend manifest metadata file export only. It writes local
manifest files under an ignored export path, but it does not copy media, create
training folders, train models, or run classifier runtime.

Phase 9U adds frontend dry-run and metadata export status controls for that
backend route. External training, media copying, and classifier runtime remain
future work.

Phase 9V documents the external training workflow boundary in
[external-training-workflow.md](external-training-workflow.md). Training remains
outside core MockingBird, and model artifacts remain ignored local files.

Phase 9W documents future optional media-copy export in
[media-copy-export-design.md](media-copy-export-design.md). Media-copy export
remains separate from metadata export and is not implemented in this phase.
Phase 9X adds copy-media dry-run planning only. It can report planned local
media paths, skips, and byte estimates, but it does not create datasets or copy
media.
Phase 9Y adds
[external-training-workspace-checklist.md](external-training-workspace-checklist.md)
before media-copy or training implementation.
Phase 9Z adds
[external-training-workspace-template.md](external-training-workspace-template.md)
as documentation only; it does not implement training.

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

Phase 9O implements these as a backend report only. Phase 9P makes the report
visible in the UI. Phase 9Q adds the read-only manifest preview response.
Phase 9R makes that response visible and downloadable as browser-side JSON
only. None of these phases copies media, writes server-side manifest files,
trains classifiers, or creates truth.
Phase 9S defines the local file policy for a later metadata-only export without
implementing it.
Phase 9T implements the metadata-only file export path. Media copying,
training folders, classifier runtime, and model artifacts remain out of scope.
Phase 9U makes that metadata export path visible in the UI without changing the
training/runtime boundary.
Phase 9V defines how exported metadata can feed an external workspace while
training, copied media datasets, and runtime adapters remain separate future
phases.
Phase 9W defines the copied-media boundary without generating datasets, copying
media, training, or adding runtime behavior.
Phase 9X implements dry-run copied-media planning without creating datasets,
copying media, training, or adding runtime behavior.
Phase 9Y documents external workspace readiness without creating datasets,
copying media, training, or adding runtime behavior.
Phase 9Z documents a recommended external workspace layout without creating
folders, datasets, media bundles, model files, or training behavior.

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
and split policy. Phase 9Q returns this shape as structured API data only; file
exports and media-copy policies remain future work.
See [classifier-manifest-file-export-design.md](classifier-manifest-file-export-design.md)
for the Phase 9S/9T server-side metadata file export boundary.
See [external-training-workflow.md](external-training-workflow.md) for the
Phase 9V external workspace and training boundary.
See [media-copy-export-design.md](media-copy-export-design.md) for the Phase 9W
future optional copied-media bundle policy.
See [external-training-workspace-checklist.md](external-training-workspace-checklist.md)
for the Phase 9Y operator checklist before media-copy or training work.
See [external-training-workspace-template.md](external-training-workspace-template.md)
for the Phase 9Z recommended external workspace layout.

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
- Phase 9O: classifier-readiness report/API.
- Phase 9P: classifier readiness UI surface.
- Phase 9Q: classifier training manifest preview/API implementation foundation.
- Phase 9R: classifier manifest UI/download preview.
- Phase 9S: classifier manifest file export design.
- Phase 9T: manifest file export backend implementation, metadata files only.
- Phase 9U: classifier manifest export UI/status.
- Phase 9V: external training workflow documentation.
- Phase 9W: media-copy export design.
- Phase 9X: media-copy export dry-run implementation.
- Phase 9Y: external training workspace checklist.
- Phase 9Z: external training workspace template docs.
- Phase 10A: return to stream/source playback contract.

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
