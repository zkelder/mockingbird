# Local Frame Artifact Design

## Purpose

Local frame artifacts exist because sampled frame planes are lightweight scoring inputs, while review and later species-suggestion workflows eventually need local visual evidence tied to MotionEvidence.

The artifact concept bridges `best_frame_index` to an optional MediaAsset reference without requiring media capture, decoding, thumbnails, stream sampling, or truth creation.

Phase 8Q implements the first small slice of this path: pending MotionEvidence can attach, replace, or clear an existing MediaAsset reference through `snapshot_media_asset_id`. It does not create frame artifacts yet.

## Product Flow

sampler evaluates frame planes -> motion candidate identifies `best_frame_index` -> future local frame artifact is created from an already-available frame source -> artifact becomes or links to a MediaAsset -> `MotionEvidence.snapshot_media_asset_id` stores the reference -> promotion carries context into Visit/Event evidence where supported -> user review/correction creates truth.

## Local Frame Artifact Definition

A local frame artifact is a local evidence image or frame reference representing a selected moment from a stream, import, or media context.

It is:

- review context for a MotionEvidence record
- optionally represented as a MediaAsset
- local-first evidence
- tied to a selected frame index or timestamp

It is not:

- a sampled frame plane
- a species label
- reviewed truth
- export-ready truth by itself
- a model output

## Difference From Frame Planes

Frame planes are small numeric grayscale arrays used for motion scoring.

Local frame artifacts are visual evidence for review. Frame planes may be discarded after scoring. Artifacts may be stored as local media references when useful, bounded, and privacy-safe.

Neither frame planes nor artifacts create labels, reviewed status, dataset coverage truth, or export-ready truth.

## Relationship To MediaAsset

MediaAsset is the existing/future local media reference concept.

Local frame artifacts should use MediaAsset where possible instead of inventing a parallel media object. `MotionEvidence.snapshot_media_asset_id` should point to that MediaAsset. Visit representative media can later expose it through existing review/detail surfaces.

Direct Event media propagation remains optional future work if the product model needs event-level media context without a Visit.

## Artifact Metadata Design

Likely future metadata, for design only:

- `media_asset_id`
- `source_id`
- `stream_id`
- `motion_evidence_id`
- `zone_id`
- `frame_index` or timestamp
- `derived_from_media_asset_id` nullable
- `file_path` or local reference
- `width` and `height` nullable
- `content_type`
- `created_at`
- `artifact_role`: `best_frame`
- `privacy_review_status` optional future field
- notes/provenance summary

This metadata should stay product-shaped and avoid exposing adapter, worker, or model internals as the user-facing product.

## Creation Policy

Future artifact creation should be explicit product logic.

Policy should:

- create artifacts only after a motion candidate warrants review
- avoid writing artifacts from privacy zones
- suppress artifact creation for ignore zones
- stay local-only by default
- be bounded and cleanup-aware
- avoid creating artifacts for every sampled frame
- preserve source, stream, zone, frame, and MotionEvidence context

Creation should happen because the product needs review context, not because an adapter or media source is the product center.

## Attachment Policy

MotionEvidence can exist without an artifact.

An artifact can attach later by setting `snapshot_media_asset_id`. Promotion should preserve that reference. Attachment must not create ReviewLabel, mark Event/Visit reviewed, create dataset/export truth, or call models.

Phase 8Q supports attaching an already-existing MediaAsset to pending MotionEvidence. Ignored and promoted MotionEvidence stay locked against media changes to avoid mutating dismissed noise or already-promoted review context.

## Relationship To Sampler

The sampler identifies candidate windows and `best_frame_index`.

The sampler should not own long-term media policy alone. A future artifact service can use sampler output plus available frame/media context to create or attach a local artifact. The sampler remains local, bounded, and evidence-only.

## Relationship To SpeciesNet/Species Suggestions

A local frame artifact may later be sent to SpeciesNet or another species classifier as input.

Classifier output remains suggestion/evidence only. User correction remains truth. No classifier is called in this phase.

## Privacy And Retention

Privacy zones should suppress artifact creation by default.

Users should be able to understand where local artifacts are stored. Future cleanup, reset, and export behavior must handle artifacts intentionally. Local-first means no cloud upload by default.

## Failure And Noise Cases

Expected cases:

- no artifact available
- artifact too blurry
- best frame misses the subject
- lighting spike selected
- privacy zone overlap
- storage full
- duplicate artifacts
- stale media reference
- derived artifact missing

These failures should keep MotionEvidence reviewable or ignorable without creating truth. Missing artifacts should fail safely.

## Implementation Plan

Recommended future phases:

- Phase 8Q: attach existing MediaAsset to pending MotionEvidence.
- Phase 8R: Motion Evidence media preview polish or local frame artifact creation from imported media.
- Phase 8S: artifact propagation to Visit detail if any gaps remain.
- Phase 8T: controlled local frame capture from already-configured streams/imported media.

These phases should stay product-first: stream, zone, MotionEvidence, review/promotion, correction truth.

## Phase 8Q Status

Phase 8Q implements existing MediaAsset attachment to pending MotionEvidence.

Supported now:

- pending MotionEvidence can attach or replace `snapshot_media_asset_id`
- pending MotionEvidence can clear `snapshot_media_asset_id`
- missing MediaAsset references fail safely
- ignored and promoted MotionEvidence reject attachment changes
- promotion preserves the attached media reference
- attachment writes no Event, Visit, ReviewLabel, export, dataset coverage truth, species truth, media files, thumbnails, or model output

Deferred:

- creating local frame artifacts
- deriving artifacts from imported media
- media preview polish beyond existing media-file links
- automated stream/frame capture
- direct Event-only media propagation if needed

## Test Plan For Future Implementation

Future tests should prove:

- MotionEvidence can exist without artifact
- artifact attachment updates `snapshot_media_asset_id` only
- artifact attachment does not create ReviewLabel
- artifact attachment does not mark reviewed
- artifact attachment does not create export/dataset truth
- privacy/ignore zones suppress artifact creation
- missing MediaAsset reference fails safely
- promotion preserves artifact reference
- Visit detail exposes representative media when supported
- reset/cleanup behavior handles artifacts safely
- no SpeciesNet/MegaDetector calls are made

## Explicit Non-Goals

- no media decoding
- no thumbnail generation
- no stream capture
- no camera adapter
- no background worker
- no SpeciesNet call
- no MegaDetector call
- no automatic species truth
- no reviewed labels from artifacts alone
- no cloud upload
- no production detection claims
