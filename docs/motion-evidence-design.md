# Motion Evidence Design

## Purpose

Motion Evidence exists between raw motion scores and reviewable visits/events.

The scoring core can say that a zone changed across a candidate frame window. That is useful, but it is still too early to create product truth. Motion Evidence gives MockingBird a local product concept for preserving that signal, attaching later media context, and deciding whether the activity should become reviewable Event/Visit evidence.

## Product Flow

Planned flow:

stream/frame sample -> zone-aware motion score -> debounced motion candidate -> Motion Evidence record -> optional snapshot/best-frame attachment -> later promotion to Event/Visit -> review/correction -> dataset/export truth.

The Motion Evidence step protects the product loop by keeping motion as evidence until explicit promotion and user correction happen.

## Motion Evidence Definition

Motion Evidence is local product evidence that motion was detected in a stream zone over a candidate frame window.

It is:

- evidence for later review or promotion
- tied to source, stream, zone, frame/time window, and scoring context
- allowed to carry a best-frame or media reference later
- useful for noise handling and future adapter evaluation

It is not:

- a species label
- a reviewed observation
- export-ready truth
- a replacement for Event, Visit, ReviewLabel, DatasetExport, or Analytics truth

## Suggested Future Fields

Likely future fields, for design only:

- `id`
- `source_id`
- `stream_id`
- `zone_id`
- `start_frame_index` or `start_time`
- `end_frame_index` or `end_time`
- `best_frame_index` or `best_frame_time`
- `peak_changed_ratio`
- `triggered_frame_count`
- `scoring_config` summary
- `snapshot/media_asset_id` nullable
- `status`: `pending`, `promoted`, or `ignored`
- `promoted_event_id` nullable
- `promoted_visit_id` nullable
- `created_at`
- `notes/debug_summary` optional, user-facing safe

These fields should stay product-shaped and avoid leaking adapter or worker internals into the user experience.

## Status Lifecycle

`pending` means motion was detected and retained, but no Event or Visit has been created from it.

`promoted` means future product logic converted the evidence into reviewable Event/Visit evidence.

`ignored` means a user or product rule dismissed the evidence as noise. Ignored evidence remains separate from truth and should not affect exports, coverage, or analytics truth.

## Promotion Rules

Future promotion should:

- create reviewable Event/Visit evidence only after explicit product logic
- attach zone context and a snapshot/media reference if available
- keep source and stream context visible
- preserve the original Motion Evidence record as evidence
- leave review status as needing review

Future promotion must not:

- create reviewed labels
- create species labels
- mark records dataset-ready or export-ready
- bypass Review Queue or detail-page correction
- treat motion as truth without user correction

## Relationship To DetectionProposal

`DetectionProposal` is model or detector evidence, such as a MegaDetector-family output or a future species suggestion.

Motion Evidence is lightweight trigger evidence from frame differences in user-drawn zones.

A future Event or Visit can reference both Motion Evidence and detector/species suggestions. Motion Evidence might explain why the moment was captured; a DetectionProposal might suggest what appeared in the frame. Neither is truth until user review/correction.

## Relationship To SpeciesNet/Species Suggestions

Motion Evidence may provide the best frame or zone crop later.

SpeciesNet or another species classifier remains a separate adapter. It should receive explicit local media context from a later phase and return species suggestions as evidence only.

User correction remains the truth for dataset/export use.

## Failure/Noise Handling

Expected noise cases include:

- wind/leaves
- lighting shifts
- feeder swing
- rain
- shadows
- camera shake
- tiny far-away birds
- zone misconfiguration

Pending and ignored statuses are necessary because motion is noisy. MockingBird should preserve enough context to explain why a candidate exists while allowing noisy evidence to be ignored without changing truth.

## Privacy/Ignore Zones

Privacy and ignore zones should suppress or avoid promotion depending on future policy.

Feeder, birdbath, ground, perch, yard, or driveway zones may be eligible for promotion when product rules say the evidence is useful. Privacy and ignore behavior must be explicit and tested in the implementation phase.

## API And Persistence Plan

Phase 8C is design only.

Likely future phases:

- Phase 8D introduces MotionEvidence schemas and repository behavior, either in-memory first or persistent depending on the task packet.
- Phase 8E wires Motion Evidence promotion into Event/Visit creation while preserving review/correction truth.
- Stream sampler and media capture work comes later.

No API, persistence, event creation, media capture, stream sampling, or worker implementation is added in this phase.

## Test Plan For Future Implementation

Future implementation tests should prove:

- pending Motion Evidence can be created from a candidate
- creation writes no Event, Visit, ReviewLabel, DatasetExport, DatasetCoverage, or analytics truth
- promotion creates Event/Visit evidence but no ReviewLabel
- ignored evidence cannot be promoted accidentally
- privacy and ignore zones suppress promotion
- snapshot/media reference is optional
- user correction remains export truth
- evidence follows local persistence and reset rules

## Explicit Non-Goals

- no species classification
- no production detection claims
- no model runtime
- no camera adapter
- no video decoder
- no background worker
- no automatic event truth
- no reviewed labels from motion alone
- no dataset/export truth from motion alone
