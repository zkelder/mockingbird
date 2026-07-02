# Model Adapter Guardrails

## Purpose

These guardrails protect MockingBird's product loop as real local model adapters are introduced. A model adapter may generate useful evidence, but it must stay underneath the product experience.

## Product Doctrine Reminder

MockingBird is a local-first outdoor video intelligence platform. Streams, zones, events, visits, review, corrections, exports, analytics, and adapter evaluation are the product loop. Future source adapters remain underneath the product, not the product center.

## Truth Boundary

Detector adapters produce `DetectionProposal` evidence only. They never create reviewed truth, never mark a label export-ready, and never bypass Review Queue or Visit Detail correction.

User corrections remain dataset truth. Exports use reviewed and corrected labels. Raw detector labels remain evidence even when they are useful.

Species classifier outputs are `SpeciesSuggestion` evidence only. They must not create reviewed labels, dataset coverage truth, export truth, analytics truth, or reviewed Visit/Event state without explicit user correction.

SpeciesNet or any other species classifier runtime must follow
[speciesnet-runtime-investigation.md](speciesnet-runtime-investigation.md)
before dependencies, model files, download behavior, or classifier calls are
added. Its outputs must create `SpeciesSuggestion` evidence only.

The SpeciesNet source review in
[speciesnet-source-review.md](speciesnet-source-review.md) requires optional
dependency, lazy import, explicit local model path/configuration, no automatic
downloads, and mocked runtime-output tests before any real adapter work.

The SpeciesNet boundary plan in
[speciesnet-adapter-boundary-plan.md](speciesnet-adapter-boundary-plan.md)
must be followed before runtime work. Any future SpeciesNet adapter must keep
the dependency optional, import lazily, require explicit local model paths,
avoid automatic downloads, start safely when unavailable, and write
`SpeciesSuggestion` evidence only.

Species suggestion UI actions such as accept, reject, and supersede update
evidence workflow state only. They must not imply model truth or write reviewed
corrections by themselves.

Any future "use as correction" behavior must enter truth through the existing
review/correction path. See
[species-suggestion-correction-flow.md](species-suggestion-correction-flow.md).
Frontend prefill from a suggestion is allowed only as review assistance; the
correction submit remains the truth boundary.

Post-correction SpeciesSuggestion status updates are evidence workflow metadata.
They may run only after correction submit succeeds and must not create reviewed
truth, mark Visits reviewed, update exports, or update analytics by themselves.

Showing SpeciesSuggestion evidence inside Visit Detail, Review Queue, or Event
Detail must stay display/prefill-only. Model or suggestion output enters dataset
truth only when the user submits the existing correction flow.

Suggestion UI must visually and textually distinguish evidence status from
reviewed truth. "Use as correction" may prefill a correction form, but must not
auto-submit, mark records reviewed, or update exports/analytics by itself.

Mock species suggestion adapters are demo/testing tools. They may create
pending `SpeciesSuggestion` evidence for review, but they must follow the same
truth boundary as real model suggestions.

Custom bird classifier and training work must follow
[custom-bird-classifier-dataset-plan.md](custom-bird-classifier-dataset-plan.md)
and
[classifier-training-manifest-design.md](classifier-training-manifest-design.md).
Training data may use reviewed exports only; classifier dataset exports and
training must not make model output truth. Classifier outputs must enter
`SpeciesSuggestion` only and must not write `ReviewLabel`, export truth,
dataset coverage truth, analytics truth, or reviewed Visit/Event state.

Classifier readiness and export-planning reports are read-only signals. They
may summarize reviewed local data, but they must not run classifiers, generate
datasets, or turn model/suggestion output into truth.

Classifier readiness UI is also read-only. It may show reviewed-data readiness,
skip reasons, and warnings, but it must not create exports, labels, datasets,
or classifier suggestions.

Classifier training manifest preview is read-only structured data. It may
package reviewed media-backed correction truth and skip reasons for inspection,
but it must not copy media, write manifest files, train, run classifier runtime,
create labels, or treat `SpeciesSuggestion`, `MotionEvidence`, or
`DetectionProposal` as truth.

Classifier manifest UI/download preview is also read-only. Browser-side JSON
copy/download may use the already-loaded preview response, but it must not call
server-side file generation, copy media, create exports, train, or write
classifier suggestions.

Generated classifier manifest/export files require explicit export scope and
must follow
[classifier-manifest-file-export-design.md](classifier-manifest-file-export-design.md).
They must live under ignored local data/export paths, must not include model
files or copied media unless a later phase explicitly scopes that behavior, and
must never create reviewed truth or make model output truth.

## Adapter Input Contract

Adapters must accept product-level inputs, not adapter-specific workflows:

- A local `MediaAsset` reference.
- Stream and zone context when available.
- Requested or supported labels when the adapter contract allows them.
- Local configuration that is explicit and visible through adapter status.

The first real local detector remains scoped to imported image media unless a later task explicitly changes that scope.

## Adapter Output Contract

Detector adapter outputs must flow through existing `DetectionRun` and `DetectionProposal` records.

Each proposal should include:

- label
- confidence
- optional bounding box
- stream and zone context when known
- suggested event type such as `animal_visit`
- suggested subject/species fields when the adapter can safely provide them

Detector adapters must not create `Event`, `Visit`, `ReviewLabel`, dataset export records, coverage truth, or analytics truth directly.

Species suggestion adapters are a separate future adapter class. They should follow [species-suggestion-adapter-design.md](species-suggestion-adapter-design.md) and keep classifier output below review/correction truth.

Species suggestion adapter output must enter `SpeciesSuggestion`, not
`ReviewLabel`, even when the suggested label is high confidence.

## Runtime Safety

Runtime work must be explicitly triggered. It must not run during app startup, local data status checks, page load, or export generation.

The app must start when a model is not configured. Missing optional runtime packages, unreadable local files, unsupported outputs, and low-confidence results must fail as local adapter status or run errors, not as product data corruption.

## Model File Safety

Model files are local user configuration. They must not be committed, generated into the repo, or downloaded automatically by MockingBird.

Model paths may be configured with environment variables such as `MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH`. Prefer boolean configuration status in API responses over verbose path display.

## Error Handling

Errors should be clear and product-safe:

- not configured: explain the local model path setting
- missing file: explain the local model or media file cannot be found
- missing runtime: name the optional runtime dependency area
- unsupported media: list supported imported media types
- unsupported output: explain that the detector output shape is not supported by this spike

Errors must not create partial truth records.

## Evaluation and Rollback

Adapter evaluation compares proposal evidence to reviewed correction truth. Match rate is a readiness signal, not a deployment score.

Rollback must be simple:

- disable or unconfigure the adapter
- keep existing proposals as evidence
- keep user corrections as truth
- do not delete reviewed data just because an adapter is noisy
- use dataset coverage and dataset QA to decide whether the adapter is helping

## What Adapters Must Never Do

- create reviewed truth directly
- create species truth from classifier suggestions alone
- bypass Review Queue or Visit Detail correction
- mark exports, coverage, QA, or analytics truth from raw detector labels
- require cloud services for the local product loop
- download or commit model weights automatically
- reshape MockingBird around a single adapter or runtime
- replace source, stream, zone, event, visit, review, correction, export, or analytics concepts with adapter-specific objects
