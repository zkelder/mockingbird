# Sampled Frame Ingestion Design

## Purpose

Sampled-frame ingestion is the boundary between streams visible in MockingBird and motion evaluation.

The app experience stays centered on sources, streams, zones, reviewable events/visits, corrections, exports, and analytics. A future sampler should translate stream moments into small frame planes that the existing motion API can evaluate without making source adapters, media decoding, or background workers the product center.

## Product Flow

source/stream visible in MockingBird -> future sampler captures sampled frames -> frames become small grayscale frame planes -> user-drawn zones are applied -> `/api/motion/evaluate-sequence` evaluates motion -> optional pending MotionEvidence records are created -> user reviews, ignores, or promotes evidence -> Event/Visit review and correction create truth.

## Sampled Frame Definition

A Sampled Frame is a lightweight representation of a moment from a stream or imported media.

It is not necessarily the full media file. It can carry a `frame_index` or timestamp, may gain a media reference later, and can be converted into a grayscale frame plane for motion scoring. A Sampled Frame is not reviewed truth.

## Frame Plane Definition

A frame plane is a rectangular 2D array of numeric grayscale values.

It should be downscaled or normalized enough for motion scoring, and it does not need image metadata. The current backend contract already accepts synthetic or manual frame planes. A future sampler should produce this shape before calling `/api/motion/evaluate-sequence`.

## Future Sampled Frame Fields

Likely future fields, for design only:

- `source_id`
- `stream_id`
- `sample_id`
- `frame_index`
- `sampled_at`
- `width`
- `height`
- `grayscale_plane`
- `media_asset_id` nullable
- `zone_context` optional
- `sampling_config` summary
- `created_at`

## Sampling Strategy

Future sampling should favor low FPS sampling rather than every full-resolution frame.

The sampler should downscale before scoring, evaluate configured zones only, and keep a short in-memory ring buffer for best-frame selection later. Expensive work should wait until motion evidence warrants it. The full stream view remains central in the app; sampling is an underneath-the-product support layer.

## Relationship To Zones

Zones determine which parts of frame planes are scored.

Feeder, birdbath, and ground zones may create MotionEvidence when product rules allow it. Privacy and ignore zones should suppress or block evidence creation and promotion according to existing policy. Zone changes affect future scoring; historical evidence should not be reinterpreted unless a later explicit reprocessing flow is designed.

## Relationship To `/api/motion/evaluate-sequence`

`/api/motion/evaluate-sequence` is the current backend contract for sampled frame planes.

A future sampler should call it with frames, zones, source/stream context, thresholds, and the `create_motion_evidence` flag. The route creates pending MotionEvidence only when explicitly requested. It still does not create Event, Visit, ReviewLabel, export, dataset coverage, or correction truth.

## MotionEvidence Creation Policy

Pending MotionEvidence is the product-facing result of sampled-frame motion.

MotionEvidence can be ignored or promoted. Promotion creates unreviewed Event/Visit evidence only. Review and correction remain the source of dataset/export truth.

## Best-Frame And Media Attachment Policy

This phase does not capture or attach media.

A future sampler may attach a best-frame MediaAsset. Best-frame selection should use the candidate peak frame plus quality heuristics from a short buffer. Media attachment is evidence and context, not truth.

## Failure And Noise Cases

Expected noise cases include:

- wind/leaves
- shadows and lighting changes
- feeder swing
- camera shake
- rain
- tiny distant birds
- bad zone placement
- low light or night mode
- duplicate triggers

Debounce, cooldown, pending/ignored status, and the review surface exist because motion is noisy. Noise should not create reviewed labels, export readiness, or analytics truth.

## Privacy And Local-First Constraints

Sampling stays local.

Future implementation should not require cloud upload. Privacy and ignore zones must be respected before saving or promoting evidence, and implementation should avoid writing unnecessary frames from privacy zones. The local user remains in control of what is reviewed, promoted, corrected, and exported.

## Phase 8K Status

Phase 8K adds a browser harness on the Motion Evidence page for supplied synthetic frame planes.

The harness calls `/api/motion/evaluate-sequence`, shows frame score/candidate results, and can optionally create pending MotionEvidence records. It does not sample real streams, decode media, run models, attach media, create labels, create reviewed observations, or write export-ready truth.

## Phase 8L Status

Phase 8L defines the lightweight sampler abstraction that will eventually produce frame planes from already-configured source/stream/media context.

At that phase, sampler implementation remained future work and the system still used manual or harness-supplied frame planes. See [lightweight-sampler-abstraction.md](lightweight-sampler-abstraction.md).

## Phase 8M Status

Phase 8M adds backend sampler code for supplied in-memory frame planes.

`/api/motion/evaluate-sequence` now uses the sampler service to evaluate consecutive frame pairs, extract zone-local motion candidates, and optionally create pending MotionEvidence. This still does not sample real streams, decode media, attach media, run models, create Event/Visit records, or write review/export truth.

## Future Implementation Plan

Tentative future phases:

- Phase 8N: sampled-frame source contract for already-available stream/import frames.
- Phase 8O: optional best-frame MediaAsset attachment.
- Phase 8P: controlled local stream sampling.

Each phase should stay product-first: visible stream, configured zones, pending evidence, review/promotion, then correction truth.

## Test Plan For Future Implementation

Future tests should prove:

- sampled frames convert to valid frame planes
- zones are passed correctly to `/api/motion/evaluate-sequence`
- privacy and ignore zones suppress evidence creation
- `create_motion_evidence=false` creates no evidence
- `create_motion_evidence=true` creates pending evidence only
- no Event, Visit, ReviewLabel, Export, or dataset coverage truth is written
- sampler respects configured thresholds
- sampler handles empty or invalid frames safely
- duplicate/cooldown behavior prevents repeated evidence spam
- media attachment is optional
- local data remains resettable/exportable according to existing rules

## Explicit Non-Goals

- no live camera adapter
- no video decoder
- no background worker in this design phase
- no SpeciesNet call
- no MegaDetector call
- no automatic species label
- no reviewed truth
- no cloud upload
- no production detection claims
