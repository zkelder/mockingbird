# Model Adapter Guardrails

## Purpose

These guardrails protect MockingBird's product loop as real local model adapters are introduced. A model adapter may generate useful evidence, but it must stay underneath the product experience.

## Product Doctrine Reminder

MockingBird is a local-first outdoor video intelligence platform. Streams, zones, events, visits, review, corrections, exports, analytics, and adapter evaluation are the product loop. Future source adapters remain underneath the product, not the product center.

## Truth Boundary

Detector adapters produce `DetectionProposal` evidence only. They never create reviewed truth, never mark a label export-ready, and never bypass Review Queue or Visit Detail correction.

User corrections remain dataset truth. Exports use reviewed and corrected labels. Raw detector labels remain evidence even when they are useful.

Species classifier outputs are `SpeciesSuggestion` evidence only. They must not create reviewed labels, dataset coverage truth, export truth, analytics truth, or reviewed Visit/Event state without explicit user correction.

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
