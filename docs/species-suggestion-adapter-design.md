# Species Suggestion Adapter Design

## Purpose

Species suggestion exists so media-backed Events and Visits can offer helpful species or taxon candidates during review without creating truth.

MotionEvidence, Event, and Visit media may show an animal clearly enough for a classifier to suggest what species may be present. That suggestion is useful review evidence, but user correction remains the only dataset/export truth.

## Product Flow

media-backed Event/Visit -> species suggestion adapter receives image/media context -> adapter returns candidate labels/taxa/confidence -> suggestion is shown as evidence -> user accepts, corrects, or rejects during review -> reviewed correction becomes dataset/export truth.

The adapter assists the review loop. It does not replace it. Applying a
suggestion to reviewed truth must follow
[species-suggestion-correction-flow.md](species-suggestion-correction-flow.md).

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

## SpeciesSuggestion Fields

Phase 9B implements the schema/repository/API foundation for manual or mock suggestions with these product-shaped fields:

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

Fields stay product-shaped and do not leak model runtime internals into core review data.

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

Phase 9I records the runtime, dependency, licensing, model-file, and output
mapping questions in
[speciesnet-runtime-investigation.md](speciesnet-runtime-investigation.md).
SpeciesNet remains a future optional adapter only until that review is complete
and a later implementation phase explicitly scopes the runtime work.

Phase 9J adds the concrete source review in
[speciesnet-source-review.md](speciesnet-source-review.md). The recommendation
is to proceed only to an optional adapter boundary plan, with no dependency,
model-file, download, media-decoding, or runtime work yet.

Phase 9K defines that boundary in
[speciesnet-adapter-boundary-plan.md](speciesnet-adapter-boundary-plan.md).
SpeciesNet implementation remains future optional work and must stay
`SpeciesSuggestion` evidence only.

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
- `accepted`: user found it useful as review evidence.
- `rejected`: user dismissed it.
- `superseded`: a later correction or model result replaced it.

An accepted suggestion is still only evidence until explicit review/correction
behavior writes the reviewed label. "Use as correction" must remain a separate
user action that submits the existing correction flow.

Accepted status may be set after a successful correction as evidence workflow
metadata. That status still is not the reviewed label, export truth, dataset
coverage truth, or analytics truth.

Phase 9B status updates are evidence workflow only. Accepting, rejecting, or superseding a suggestion does not create a reviewed label, mark Event/Visit records reviewed, update exports, or change dataset coverage truth.

## UI Plan

Phase 9C adds a standalone Species Suggestions page for manual/mock suggestion
creation, list/filter/detail review, and status updates.

Future follow-on UI can also:

- show suggestions on Visit Detail, Event Detail, and Review Queue
- show confidence, rank, and provenance
- show manual/mock suggestion evidence before any classifier runtime exists
- prefill the existing correction form from eligible suggestions
- let the user reject or ignore a suggestion
- let the user mark suggestion evidence accepted or superseded
- always show reviewed truth separately from suggestions

Any suggestion UI must make it clear which text is model- or manually-suggested
evidence and which label is user-reviewed truth. Phase 9C does not apply
suggestions as corrections.

Phase 9G starts this review-context surface on Visit Detail by showing
Visit-linked suggestions near the existing correction form. This is still
manual/mock evidence UI and does not require runtime or model integration.

Phase 9H adds a mock species suggestion adapter action for existing Visits. It
creates realistic pending `SpeciesSuggestion` evidence for demo/testing without
running SpeciesNet, inspecting media, adding dependencies, or writing truth.

## API/Repository Plan

Recommended future phases:

- Phase 9B: `SpeciesSuggestion` schema/repository/API foundation.
- Phase 9C: species suggestion UI surface with manual or mock suggestions.
- Phase 9D: explicit correction-flow design for applying suggestion evidence.
- Phase 9E: frontend prefill/use-as-correction path.
- Phase 9F: post-correction accepted-status polish.
- Phase 9G: Visit Detail species suggestion review-context surface.
- Phase 9H: mock species suggestion adapter for demo/testing.
- Phase 9I: SpeciesNet runtime investigation docs.
- Phase 9J: SpeciesNet source/license/runtime review.
- Phase 9K: SpeciesNet optional adapter boundary plan.
- Later: review/species suggestion UI polish or custom bird classifier dataset plan.

Phase 9B stores manual/mock suggestions and proves they do not create truth. No real classifier runtime exists yet.

## Phase 9B Status

Phase 9B adds `SpeciesSuggestion` schemas, repository persistence, and API routes for creating pending suggestions, listing/filtering them, reading detail, and updating status to accepted, rejected, or superseded.

This foundation is manual/mock evidence only. It adds no SpeciesNet runtime, classifier dependency, model file, media decoding, training, Event/Visit creation, ReviewLabel creation, export truth, dataset coverage truth, or reviewed species truth.

## Phase 9C Status

Phase 9C adds the frontend Species Suggestions surface for creating manual/mock
suggestions, filtering/listing them, inspecting evidence context, and marking
pending suggestions accepted, rejected, or superseded.

These UI actions change suggestion evidence status only. They do not run
SpeciesNet or a custom classifier, inspect media, create `ReviewLabel`, mark
Event/Visit records reviewed, update dataset coverage, create exports, or write
reviewed species truth.

## Phase 9D Status

Phase 9D defines the explicit correction-flow boundary for using a suggestion as
review input. The recommended next implementation path is frontend prefill into
the existing Visit/Event correction form, so the existing correction endpoint
continues to be the only truth writer.

## Phase 9E Status

Phase 9E adds a frontend-only "Use as correction" path from Species Suggestions
to Visit Detail. Eligible pending or accepted suggestions with `visit_id` context
can prefill the existing correction form. The user can edit before submitting,
and no suggestion status update, `ReviewLabel`, reviewed Visit state, export
truth, dataset coverage truth, or analytics truth is created by navigation.

## Phase 9F Status

Phase 9F marks pending SpeciesSuggestion evidence accepted only after the
existing Visit correction submit succeeds. If the correction fails, status stays
unchanged. If the correction succeeds and the status update fails, the correction
remains the dataset/export truth and the failed status update is reported as
non-blocking evidence workflow metadata.

## Phase 9G Status

Phase 9G surfaces Visit-linked SpeciesSuggestion evidence on Visit Detail. The
reviewer can prefill the existing correction form from pending or accepted
suggestions, while rejected and superseded suggestions remain read-only context.
No SpeciesNet runtime, classifier dependency, media inspection, or automatic
truth write is added.

## Phase 9H Status

Phase 9H adds a mock species suggestion adapter route and Visit Detail action.
The mock adapter creates one pending SpeciesSuggestion for an existing Visit,
infers clean product context, and stays evidence-only. It does not inspect media,
run a classifier, create `ReviewLabel`, mark Visits reviewed, create exports, or
change dataset coverage truth.

## Phase 9I Status

Phase 9I adds the SpeciesNet runtime investigation record before any runtime
dependency, model file, classifier call, media decoding, or implementation work.
It keeps SpeciesNet as an optional future `SpeciesSuggestion` adapter and
preserves correction as dataset/export truth.

## Phase 9J Status

Phase 9J reviews official/public SpeciesNet sources and recommends the next
step as an optional adapter boundary plan. SpeciesNet stays evidence-only and
deferred from runtime implementation until model-weight terms, local model path
shape, dependency behavior, and taxonomy mapping are settled.

## Phase 9K Status

Phase 9K adds the SpeciesNet optional adapter boundary plan. It defines future
dependency, local model path, runtime config, input/output, API, status, test,
UI, and rollback boundaries without adding SpeciesNet runtime, dependencies,
model files, media decoding, or truth writes.

## Test Plan

Implementation tests should prove:

- pending `SpeciesSuggestion` can be created
- suggestions do not create `ReviewLabel`
- suggestions do not mark Visit reviewed
- accepted, rejected, and superseded status behavior is deterministic
- applying a suggestion requires the explicit correction/review path
- suggestion status changes after correction success do not create truth
- showing suggestions in review context does not create truth
- mock suggestions for existing Visits do not create truth
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
