# Lightweight Sampler Abstraction

## Purpose

The sampler abstraction is the future boundary between visible streams or imported media and the existing motion evaluation contract.

It should let MockingBird turn already-configured source/stream/media context into low-resolution grayscale frame planes, then pass those planes to `/api/motion/evaluate-sequence`. The sampler keeps source adapters, media decoding, workers, detectors, and review/export decisions outside the core motion scoring contract.

## Product Flow

source/stream visible in MockingBird -> sampler selects a small frame sequence -> frames become low-resolution grayscale frame planes -> zones are applied -> `/api/motion/evaluate-sequence` evaluates motion -> optional pending MotionEvidence is created -> user reviews, ignores, or promotes -> correction creates truth.

## Sampler Definition

A sampler is a local component that produces frame planes from an already-configured source, stream, or media context.

It is not:

- a source adapter
- a detector
- a species classifier
- reviewed truth
- responsible for review/export decisions

The sampler exists underneath the product loop. Its output is evidence for review, not a final observation.

## Sampler Input Contract

Likely future inputs, for design only:

- `source_id`
- `stream_id`
- configured zones
- sampling cadence/config
- frame size target
- grayscale/downscale config
- motion thresholds
- `create_motion_evidence` flag
- optional privacy/ignore policy
- optional notes/context

The input contract should stay product-shaped: stream, zones, scoring config, and evidence policy.

## Sampler Output Contract

Likely future outputs:

- frame planes
- frame indexes or timestamps
- sampling config summary
- optional media references later
- `/api/motion/evaluate-sequence` request
- created pending MotionEvidence IDs when requested
- errors/warnings

The output should make it clear whether evidence was created. It must not imply reviewed labels, export readiness, or species truth.

## Zone And Privacy Behavior

The sampler evaluates only user-configured zones.

Privacy zones should not save frame data or create evidence. Ignore zones should suppress evidence creation. Feeder, birdbath, and ground zones are promotable when later product policy allows. Zone policy must be explicit and tested before implementation.

## Performance Policy

The sampler should use low-resolution frames for scoring.

It should not process every full-resolution frame by default. It should use short bounded frame windows, avoid unbounded background work, and keep streams central and responsive. Heavier detectors should remain deferred until MotionEvidence warrants enrichment.

## Relationship To `/api/motion/evaluate-sequence`

`/api/motion/evaluate-sequence` already accepts frame planes and can create pending MotionEvidence.

The sampler should call this contract instead of duplicating scoring logic. The evaluation route remains evidence-only: it does not create Event, Visit, ReviewLabel, export, dataset coverage, or correction truth.

## Relationship To MotionEvidence

Sampler-produced candidates become pending MotionEvidence only when explicitly configured.

The user can ignore or promote MotionEvidence. Promotion creates unreviewed Event/Visit evidence. User correction remains dataset/export truth.

## Relationship To Media Attachment

This design does not attach media.

A future sampler may attach a best-frame MediaAsset. Media attachment is evidence and context, not truth. Best-frame selection should use the candidate peak frame and simple quality heuristics later.

## Failure And Noise Handling

Expected failure and noise cases include:

- wind/leaves
- lighting shifts
- feeder swing
- camera shake
- rain
- night/IR mode
- duplicate triggers
- empty or bad frames
- zone misconfiguration

Failures should be safe, local, and reviewable. Bad input should fail without truth writes. Repeated motion should be controlled by debounce/cooldown behavior before evidence can pile up.

## Implementation Plan

Tentative future phases:

- Phase 8M: sampler abstraction code using supplied in-memory frame planes only.
- Phase 8N: sampled-frame source contract for already-available stream/import frames.
- Phase 8O: optional best-frame MediaAsset attachment.
- Phase 8P: controlled local stream sampling.

Each phase should preserve the stream -> zone -> pending evidence -> review/promotion -> correction truth path.

## Test Plan For Future Implementation

Future tests should prove:

- sampler builds a valid `/api/motion/evaluate-sequence` request
- sampler passes zones correctly
- privacy/ignore zones suppress evidence
- `create_motion_evidence=false` creates no evidence
- `create_motion_evidence=true` creates pending evidence only
- no Event, Visit, ReviewLabel, Export, or dataset coverage truth is written
- invalid frames fail safely
- frame windows are bounded
- duplicate/cooldown behavior prevents evidence spam
- no model/runtime calls happen

## Explicit Non-Goals

- no camera adapter
- no video decoder
- no background worker in this design phase
- no model runtime
- no SpeciesNet call
- no MegaDetector call
- no automatic species truth
- no cloud upload
- no production detection claims
