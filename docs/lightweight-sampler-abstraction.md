# Lightweight Sampler Abstraction

## Purpose

The sampler abstraction is the boundary between visible streams or imported media and the existing motion evaluation contract.

Phase 8M adds backend sampler code for supplied in-memory grayscale frame planes. Future stream or media producers can feed the same shape later, while source adapters, media decoding, workers, detectors, and review/export decisions stay outside the core motion scoring contract.

## Product Flow

source/stream visible in MockingBird -> supplied or future sampler-produced frame planes -> zones are applied -> `/api/motion/evaluate-sequence` evaluates motion through the sampler service -> optional pending MotionEvidence is created -> user reviews, ignores, or promotes -> correction creates truth.

## Sampler Definition

A sampler is a local component that evaluates frame planes from an already-configured source, stream, or media context.

The current implementation accepts already-supplied in-memory frame planes only. It does not connect to streams, read media, or produce frames from files.

It is not:

- a source adapter
- a detector
- a species classifier
- reviewed truth
- responsible for review/export decisions

The sampler exists underneath the product loop. Its output is evidence for review, not a final observation.

## Sampler Input Contract

Current Phase 8M inputs:

- supplied grayscale frame planes
- `SamplerZone` bounds
- `SamplerConfig` thresholds and candidate settings
- optional `SamplerContext` with source, stream, and notes for evidence creation

Likely future inputs:

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

Current Phase 8M outputs:

- frame scores
- motion candidates
- optional created pending MotionEvidence records from a separate helper
- warnings list, currently empty

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

`/api/motion/evaluate-sequence` accepts frame planes and can create pending MotionEvidence.

The route now uses the sampler service for supplied frame-plane evaluation instead of duplicating sequence scoring logic. The evaluation route remains evidence-only: it does not create Event, Visit, ReviewLabel, export, dataset coverage, or correction truth.

## Relationship To MotionEvidence

Sampler-produced candidates become pending MotionEvidence only when explicitly configured.

The user can ignore or promote MotionEvidence. Promotion creates unreviewed Event/Visit evidence. User correction remains dataset/export truth.

## Relationship To Media Attachment

This design does not attach media.

A future sampler may attach a best-frame MediaAsset. Media attachment is evidence and context, not truth. Best-frame selection should use the candidate peak frame and simple quality heuristics later. See [best-frame-media-attachment-design.md](best-frame-media-attachment-design.md).

Sampler output may feed future local frame artifact creation, but artifact retention and MediaAsset attachment should be explicit product logic outside the sampler scoring core. See [local-frame-artifact-design.md](local-frame-artifact-design.md).

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

## Phase 8M Status

Phase 8M implements the sampler abstraction for supplied in-memory frame planes.

The backend sampler evaluates consecutive frame pairs, extracts debounced motion candidates, and can create pending MotionEvidence when explicitly enabled. It does not create Event, Visit, ReviewLabel, export, dataset coverage, species truth, media files, source adapters, model runtime calls, workers, or stream connections.

## Implementation Plan

Tentative future phases:

- Phase 8N: best-frame media attachment design.
- Phase 8O: best-frame attachment schema/API compatibility review.
- Phase 8P: local frame artifact design.
- Phase 8Q: local frame artifact schema/API compatibility design or implementation.
- Phase 8R: attach existing MediaAsset to MotionEvidence from manual/imported media.
- Phase 8S: artifact propagation to Visit detail if any gaps remain.
- Phase 8T: controlled local frame capture from already-configured streams/imported media.

Each phase should preserve the stream -> zone -> pending evidence -> review/promotion -> correction truth path.

## Test Plan

Current and future tests should prove:

- sampler evaluates supplied frame planes deterministically
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
