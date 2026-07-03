# Local Frame Artifact Design

## Purpose

Local frame artifacts exist because sampled frame planes are lightweight scoring inputs, while review and later species-suggestion workflows eventually need local visual evidence tied to MotionEvidence.

The artifact concept bridges `best_frame_index` to an optional MediaAsset reference without requiring media capture, decoding, thumbnails, stream sampling, or truth creation.

Phase 8Q implements the first small slice of this path: pending MotionEvidence can attach, replace, or clear an existing MediaAsset reference through `snapshot_media_asset_id`. Phase 8R improves how that existing reference is shown in the Motion Evidence review UI. Phase 8S allows manual pending MotionEvidence creation with an existing MediaAsset already attached. Phase 8T polishes the local demo loop around those existing references. These phases do not create frame artifacts yet.

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

Saved external URL preview MediaAssets are different from local frame artifacts:
they are fetched still images saved from a Source preview, not derived artifacts
from sampled frame indexes. They can still use the same MediaAsset attachment
path into MotionEvidence through the explicit Phase 11G handoff.
Folder/trail-cam imported MediaAssets are also different from local frame
artifacts: they are user-selected batch media from local folders, not generated
best-frame artifacts from sampler output. Phase 13G lets one imported
MediaAsset attach to pending MotionEvidence through explicit review/evidence
action.
Phase 13H adds a dry-run/report for multiple folder-imported MediaAssets before
any batch evidence creation path. It does not generate frame artifacts, decode
media, call models, or create truth.
Phase 13F keeps that distinction explicit: folder-imported MediaAssets can
become `snapshot_media_asset_id` context for pending MotionEvidence, but they
are not sampled-frame artifacts and do not create truth by being imported.
Phase 11I keeps that distinction visible after promotion: saved external URL
preview media can appear as Event/Visit review context, but it is still not a
sampled-frame artifact and does not create truth.
Phase 12C designs cleanup policy for saved external_url media separately from
future local frame artifact cleanup:
[external-url-saved-media-retention-design.md](external-url-saved-media-retention-design.md).
Phase 12D implements the saved external_url retention report and cleanup dry-run
only for saved preview MediaAssets. Future local frame artifact retention still
needs separate scope before implementation.

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

Saved external_url media retention is a separate policy from future local frame
artifact cleanup. Both should protect reviewed truth and avoid silent provenance
loss.

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
- Phase 8R: Motion Evidence media preview polish for existing MediaAsset references.
- Phase 8S: media-backed MotionEvidence creation from existing MediaAsset.
- Phase 8T: end-to-end motion/media review demo polish.
- Phase 8U: local frame artifact creation from existing imported media or controlled frame capture design.

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
- automated stream/frame capture
- direct Event-only media propagation if needed

## Phase 8R Status

Phase 8R improves Motion Evidence media visibility for existing MediaAsset references.

The Motion Evidence UI now shows attached visual evidence context, the attached MediaAsset ID, existing media-file access, and inline preview when the already-supported MediaAsset preview path can render it. This adds no media capture, decoding, thumbnail generation, artifact creation, stream sampling, source adapter, model call, or truth write.

## Phase 8S Status

Phase 8S lets manual pending MotionEvidence be created with an existing MediaAsset already attached.

This uses existing local MediaAsset records only. Create-time attachment validates the MediaAsset reference and stream match, then stores `snapshot_media_asset_id` on pending evidence. It adds no media capture, decoding, thumbnail generation, artifact creation, stream sampling, source adapter, model call, reviewed label, export truth, dataset coverage truth, or species truth.

## Phase 8T Status

Phase 8T polishes the current local demo loop without creating artifacts.

Imported MediaAssets are easier to reuse as MotionEvidence context, MotionEvidence makes promotion and review next steps clearer, and promoted Event/Visit detail pages identify Motion Evidence provenance. Local frame artifact creation, media capture, decoding, thumbnails, source adapters, model calls, and truth writes remain deferred.

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
