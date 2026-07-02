# Species Suggestion Adapter Design

## Purpose

Species suggestion exists so media-backed Events and Visits can offer helpful species or taxon candidates during review without creating truth.

MotionEvidence, Event, and Visit media may show an animal clearly enough for a classifier to suggest what species may be present. That suggestion is useful review evidence, but user correction remains the only dataset/export truth.

## Product Flow

media-backed Event/Visit -> species suggestion adapter receives image/media context -> adapter returns candidate labels/taxa/confidence -> suggestion is shown as evidence -> user accepts, corrects, or rejects during review -> reviewed correction becomes dataset/export truth.

The adapter assists the review loop. It does not replace it.

## Species Suggestion Definition

A `SpeciesSuggestion` is local evidence that a classifier thinks a media item or crop may contain a species or taxon.

It is:

- local suggestion evidence
- tied to media and optional Event/Visit/MotionEvidence context
- reviewable by a user
- allowed to include rank, confidence, alternatives, and provenance

It is not:

- a reviewed label
- export-ready truth
- dataset coverage truth
- an automatic correction
- a replacement for user review

## Adapter Roles

These layers stay separate:

- `MotionEvidence`: why a moment was captured.
- `DetectionProposal`: object or detector evidence, such as animal, person, or vehicle.
- `SpeciesSuggestion`: species or taxon label suggestion.
- `ReviewLabel` or user correction: truth.

A future Event or Visit can show several evidence layers together, but only explicit review/correction behavior creates truth.

## Suggested Future Fields

Design only, not implemented in this phase:

- `id`
- `source_id` nullable
- `stream_id` nullable
- `event_id` nullable
- `visit_id` nullable
- `media_asset_id` nullable
- `motion_evidence_id` nullable
- `adapter_id`
- `adapter_name`
- `suggested_label`
- `suggested_common_name` nullable
- `suggested_scientific_name` nullable
- `confidence` nullable
- `rank`
- `alternatives` list
- `evidence_region` or `bbox` nullable
- `status`: `pending`, `accepted`, `rejected`, `superseded`
- `created_at`
- `notes` or `provenance`

Fields should stay product-shaped and should not leak model runtime internals into core review data.

## Adapter Contract

Expected input:

- `MediaAsset` or local media reference
- optional Event/Visit context
- optional zone context
- optional crop or bbox from a future detector
- taxonomy target list
- adapter configuration

Expected output:

- ranked label suggestions
- confidence scores when available
- explicit unknown or uncertain handling
- provenance that identifies the adapter/configuration at a review-safe level
- no truth writes

Adapters must not create `ReviewLabel`, mark Event/Visit records reviewed, update dataset coverage, or make exports treat raw suggestions as labels.

## SpeciesNet As One Possible Adapter

SpeciesNet may be evaluated later as a species or taxon suggestion adapter.

It is not required for core MockingBird. It must remain optional, local, explicitly configured, and below the product review loop. No SpeciesNet dependency, runtime, model file, download behavior, or classifier call is added in this phase.

Before implementation, licensing, runtime behavior, model-file handling, supported taxa, local configuration, and failure behavior must be reviewed.

## Custom Backyard Bird Classifier Path

Reviewed MockingBird exports can later bootstrap a custom local bird classifier.

MockingBird already has a target taxonomy direction for backyard, Sandhills, and North Carolina species. A custom classifier can use reviewed exports as training or evaluation material in a future phase.

Custom classifier output still remains suggestion evidence only. User correction remains truth.

## Relationship To Taxonomy

Suggestions should map to known taxonomy labels where possible.

Unknown, uncertain, or out-of-taxonomy suggestions should remain reviewable rather than silently becoming truth. Freeform labels should help the reviewer choose or enter a correction; they must not bypass review or dataset-label policy.

Taxonomy suggestions should make the review UI faster and clearer, not replace it.

## Relationship To Media And Best-Frame Artifacts

Best-frame `MediaAsset` evidence can be input to a species suggestion adapter.

Future crops may improve classifier results when the subject is small or the frame contains multiple animals. Media or crop selection is evidence context only. Missing media should fail safely with no suggestion or a clear adapter error, and it must not alter review truth.

## Status Lifecycle

- `pending`: suggestion is shown but not used.
- `accepted`: user chose it as correction/review input.
- `rejected`: user dismissed it.
- `superseded`: a later correction or model result replaced it.

An accepted suggestion is still only evidence until explicit review/correction behavior writes the reviewed label.

## UI Plan

Future UI should:

- show suggestions on Visit Detail, Event Detail, and Review Queue
- show confidence, rank, and provenance
- let the user apply a suggestion as a correction input
- let the user reject or ignore a suggestion
- always show reviewed truth separately from suggestions

The UI should make it clear which text is model-suggested evidence and which label is user-reviewed truth.

## API/Repository Plan

Recommended future phases:

- Phase 9B: `SpeciesSuggestion` schema/repository foundation.
- Phase 9C: species suggestion UI surface with manual or mock suggestions.
- Phase 9D: SpeciesNet runtime investigation docs.
- Phase 9E: optional SpeciesNet adapter boundary.
- Phase 9F: custom bird classifier dataset plan.

The first implementation phase should store suggestions and prove they do not create truth.

## Test Plan

Future tests should prove:

- pending `SpeciesSuggestion` can be created
- suggestions do not create `ReviewLabel`
- suggestions do not mark Visit reviewed
- accepted, rejected, and superseded status behavior is deterministic
- applying a suggestion requires the explicit correction/review path
- dataset/export truth changes only after correction
- unknown and out-of-taxonomy suggestions remain reviewable
- missing media fails safely
- normal tests require no model runtime

## Explicit Non-Goals

- no SpeciesNet runtime
- no model dependency
- no model weights
- no training
- no automatic species truth
- no reviewed labels from suggestions alone
- no export truth from suggestions alone
- no stream capture
- no cloud upload
- no production accuracy claims
