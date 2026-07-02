# Best-Frame Media Attachment Design

## Purpose

MotionEvidence already knows which frame window produced motion, including a `best_frame_index`. Future review and species-suggestion workflows need visible evidence media for that moment, but media attachment must not become truth by itself.

Best-frame media attachment exists to connect a motion candidate to optional local review context before any Event, Visit, ReviewLabel, export, or species truth is created.

## Product Flow

sampler evaluates supplied/sampled frame sequence -> motion candidate identifies start/end/best frame -> future best-frame selection chooses reviewable media -> future MediaAsset is attached as `snapshot_media_asset_id` -> pending MotionEvidence shows media context -> promotion carries media context to Event/Visit evidence -> review/correction creates truth.

## Best-Frame Definition

A best frame is the frame in a candidate window most useful for review or later species suggestion.

Initially, the best frame should come from `candidate.best_frame_index`, which is based on the peak motion score in the candidate window. Later phases may add deterministic image-quality heuristics.

The best frame is evidence context only. It is not a species label, not a reviewed observation, and not dataset/export truth.

## Current State

- Phase 8M sampler output includes `best_frame_index` on each `MotionCandidate`.
- MotionEvidence already has nullable `snapshot_media_asset_id`.
- Manual and `/api/motion/evaluate-sequence` flows can create MotionEvidence without media.
- Phase 8O confirms MotionEvidence create/list/detail/ignore/promote responses preserve `snapshot_media_asset_id`.
- Promotion can attach or preserve `snapshot_media_asset_id`; when a Visit is created, the current Visit model exposes the media through `representative_media_path`, and Event/Visit detail responses can expose the linked MediaAsset.
- Phase 8Q adds the ability to attach, replace, or clear an existing MediaAsset reference on pending MotionEvidence.
- Phase 8R makes attached media easier to review in the Motion Evidence UI by showing the reference, existing media-file access, and preview when the current MediaAsset preview path supports it.
- Phase 8S lets pending MotionEvidence be created with an existing MediaAsset already attached.
- Event-only promotion does not have a direct Event media field yet, so the media reference remains on MotionEvidence until a future propagation phase.
- No media capture, image parsing, video parsing, decoding, or thumbnail generation is implemented yet.

## Future Best-Frame Selection Policy

The first policy should start with `candidate.best_frame_index`.

Future selection should:

- avoid frames from privacy or ignore zones
- prefer frames inside feeder, birdbath, or ground zones when configured
- avoid frames that are too dark or overexposed
- avoid full-frame lighting changes when a better zone-local frame exists
- avoid obvious camera shake when a better candidate frame exists
- avoid frames where subject/motion is only on the edge of a zone
- stay deterministic and testable

The policy should be tunable by product concepts such as stream, zone, frame index, and scoring config, not by adapter internals.

## MediaAsset Attachment Policy

`snapshot_media_asset_id` links MotionEvidence to an existing or future MediaAsset.

Attachment is optional. MotionEvidence can exist without media, and missing media should not block evidence review or ignore actions.

The media reference is evidence/context only. It must not create labels, reviewed status, species truth, export readiness, dataset coverage truth, or analytics truth.

When supported, promotion should carry or link the media context to created Event/Visit evidence while keeping those records unreviewed.

The future local frame artifact concept defines the product boundary between motion candidate frame indexes and stored visual review context. See [local-frame-artifact-design.md](local-frame-artifact-design.md).

## Relationship To Sampler

The sampler outputs frame indexes/timestamps and motion candidates. It does not own review decisions, export decisions, species truth, or dataset readiness.

A future media-capable sampler may request or produce a best-frame MediaAsset, but it must stay local, bounded, and explicitly configured. It should not become a source adapter, background worker, detector runtime, or product center.

## Relationship To Event/Visit Promotion

Promotion can carry `snapshot_media_asset_id` into Event/Visit evidence when the product model supports that link.

Phase 8O confirms the current Visit model can expose the promoted media context through `representative_media_path`, and Event/Visit detail responses can expose the linked MediaAsset when a Visit is created. A direct Event media field is not added in this phase.

Promoted Event/Visit records remain unreviewed. Promotion must not create a ReviewLabel, mark records reviewed, or write export-ready truth. Review and correction remain the dataset/export truth boundary.

## Relationship To SpeciesNet/Species Suggestions

Best-frame media can later become input to SpeciesNet or another species classifier.

Classifier output must remain suggestion/evidence only until the user reviews or corrects it. No classifier is called in this phase.

## Privacy And Ignore Policy

Privacy zones should suppress media attachment by default.

Ignore zones should suppress evidence creation or promotion according to existing policy. Implementation must avoid saving unnecessary frames from privacy areas. User-controlled zones remain central to whether media can be retained.

## Failure And Noise Cases

Expected cases:

- blurry best frame
- bird leaves before the best frame
- lighting spike produces peak motion
- feeder swing dominates the candidate
- rain or leaves dominate the candidate
- tiny bird is far away
- no media is available

These cases should leave evidence reviewable, ignorable, or promotable without creating truth. Missing or weak media should fail safely and visibly.

## Implementation Plan

Recommended future phases:

- Phase 8O: best-frame attachment schema/API compatibility review.
- Phase 8P: local frame artifact design.
- Phase 8Q: attach existing MediaAsset to pending MotionEvidence.
- Phase 8R: Motion Evidence media preview polish for existing MediaAsset references.
- Phase 8S: media-backed MotionEvidence creation from existing MediaAsset.
- Phase 8T: local frame artifact creation from existing imported media or controlled frame capture design.

## Phase 8O Status

Phase 8O reviews and tests the existing compatibility path.

Supported now:

- MotionEvidence can be created without media.
- MotionEvidence can be created with `snapshot_media_asset_id` that points to an existing MediaAsset on the same stream.
- MotionEvidence create/list/detail/ignore/promote responses expose and preserve `snapshot_media_asset_id`.
- Promotion preserves the MotionEvidence media reference.
- Promotion with a Visit carries the MediaAsset context through the Visit's `representative_media_path`, and Event/Visit detail responses expose the linked MediaAsset.

Deferred:

- direct Event-only media propagation
- best-frame extraction
- media capture or decoding
- thumbnails
- stream sampling/media capture
- species/model calls

## Phase 8P Status

Phase 8P defines local frame artifacts as the design bridge from frame-plane scoring to optional visual evidence.

This is design-only. No artifact creation, media capture, decoding, thumbnailing, stream sampling, or model call is implemented. See [local-frame-artifact-design.md](local-frame-artifact-design.md).

## Phase 8Q Status

Phase 8Q implements attachment of existing MediaAsset references to pending MotionEvidence.

This proves the reference path without creating media: no capture, decoding, thumbnailing, stream sampling, source adapter, model call, or truth write is added. Promotion keeps the reference as evidence context.

## Phase 8R Status

Phase 8R polishes the review surface for attached existing media.

Motion Evidence now exposes attached MediaAsset context more clearly in the UI, including the current ID, existing file link, and reusable media preview where available. The attachment remains evidence only and still does not create labels, reviewed status, export readiness, dataset coverage truth, model output, or species truth.

## Phase 8S Status

Phase 8S allows media to be present at MotionEvidence creation time, not only attached afterward.

Manual creation can include an existing MediaAsset as `snapshot_media_asset_id`; the backend validates that the asset exists and belongs to the same stream. The created record remains pending evidence only and can still be ignored or promoted through the existing review surface. No media files are opened, decoded, thumbnailed, generated, or treated as truth.

## Test Plan For Future Implementation

Future tests should prove:

- MotionEvidence can be created without media
- MotionEvidence can be created with `snapshot_media_asset_id`
- promoted Event/Visit preserves media reference if supported
- privacy/ignore zones suppress media attachment
- `best_frame_index` maps to the expected candidate frame
- missing media reference fails safely
- media attachment does not create ReviewLabel
- media attachment does not mark records reviewed
- media attachment does not create export/dataset truth
- SpeciesNet/model calls are not made

## Explicit Non-Goals

- no media decoding
- no thumbnail generation
- no stream capture
- no camera adapter
- no background worker
- no SpeciesNet call
- no MegaDetector call
- no automatic species truth
- no reviewed labels from media alone
- no cloud upload
- no production detection claims
