# Stream Motion Trigger Plan

## Purpose

This plan defines the next active event-trigger path for MockingBird:

stream visible in app -> sample frames locally -> evaluate user-drawn zones -> score motion inside feeder/birdbath/ground/etc. zones -> debounce motion across multiple sampled frames -> save candidate snapshot evidence -> create reviewable visit/event evidence -> later SpeciesNet/species classifier receives best frame or zone crop -> user correction is dataset/export truth.

This is not a permanent replacement for MegaDetector. It is the first lightweight event trigger that protects the product loop while heavier detectors remain optional enrichment.

## Phase 8A Status

Phase 8A implements the pure deterministic scoring foundation for caller-provided grayscale frame planes.

The foundation scores user-drawn normalized zones, reports changed pixels/ratios, picks the strongest zone for a frame, and debounces triggered frame scores into candidate windows with a best frame index. It does not sample streams, decode media, save evidence, create events or visits, classify species, or write review truth.

Later phases can connect this scoring core to stream sampling, media references, reviewable candidate creation, and species suggestions.

## Phase 8B Status

Phase 8B exposes the scoring foundation through a narrow backend API contract for synthetic/manual frame-plane evaluation.

The API accepts caller-provided previous/current frame planes plus normalized zones, returns per-zone motion scores, and extracts debounced candidate windows from supplied frame scores. It does not decode media, connect to streams, run a stream worker, create events or visits, write review labels, create exports, or identify species.

Future phases can connect sampled frames from visible streams to this contract and then design motion-to-evidence creation without changing the truth boundary.

## Phase 8C Status

Phase 8C defines Motion Evidence as the planned product bridge between debounced motion candidates and later Event/Visit evidence.

Motion Evidence is not implemented yet. It remains a design checkpoint for local evidence status, promotion rules, noise handling, optional best-frame/media references, and the truth boundary. See [motion-evidence-design.md](motion-evidence-design.md).

## Phase 8D Status

Phase 8D adds the MotionEvidence schema/repository/API foundation.

MotionEvidence can now be explicitly created from candidate output and ignored as noise. Stream sampling, media capture, and promotion to Event/Visit evidence remain deferred.

## Phase 8E Status

Phase 8E defines the planned promotion bridge from pending MotionEvidence to unreviewed Event/Visit evidence. It is design only: stream sampling, media capture, media decoding, and promotion implementation remain deferred. See [motion-evidence-promotion-design.md](motion-evidence-promotion-design.md).

## Phase 8F Status

Phase 8F implements MotionEvidence promotion as a backend API/repository foundation. Pending evidence can be explicitly promoted into unreviewed Event/Visit evidence, while ReviewLabel, export, dataset coverage truth, stream sampling, media capture, and media decoding remain deferred.

## Phase 8G Status

Phase 8G adds the Motion Evidence review surface before stream sampling automation.

Users can review explicitly created MotionEvidence, ignore noise, or promote valid evidence into unreviewed Event/Visit context. Stream sampling, media capture, and media decoding remain later work.

## Phase 8H Status

Phase 8H adds manual MotionEvidence creation in the app before automated frame sampling.

The manual surface lets users create pending MotionEvidence from product fields such as zone, frame range, peak change, triggered frame count, scoring context, and notes. It exists to exercise the evidence review loop; stream sampling, media capture, and media decoding remain later work.

## Phase 8I Status

Phase 8I adds a backend frame sequence evaluation contract for already-sampled grayscale frame planes.

The API scores consecutive frame pairs, debounces zone-local motion candidates, and can optionally create pending MotionEvidence records from those candidates. It does not decode media, connect to streams, sample frames, run workers, call model runtimes, create Event/Visit records, or write review/export truth.

Real stream sampling and media capture remain deferred to a later boundary.

## Phase 8J Status

Phase 8J defines the sampled-frame ingestion boundary. Sampled frames are the planned bridge between visible streams and `/api/motion/evaluate-sequence`; they become small grayscale frame planes before zone-aware motion evaluation.

Implementation remains deferred: no media decoding, stream worker, source adapter, model runtime, or automatic truth creation is added in this phase. See [sampled-frame-ingestion-design.md](sampled-frame-ingestion-design.md).

## Phase 8K Status

Phase 8K adds a browser harness for supplied tiny frame planes on the Motion Evidence page.

The harness exercises `/api/motion/evaluate-sequence`, shows frame-score and candidate results, and can optionally create pending MotionEvidence. It still does not sample real streams, decode media, run models, create labels, or create reviewed/export-ready truth.

## Phase 8L Status

Phase 8L defines the lightweight sampler abstraction that will later bridge visible streams/imported media to low-resolution frame planes.

The current system still uses manual and harness-supplied frames. No real stream sampling, media decoding, worker, source adapter, model runtime, or truth creation is added in this phase. See [lightweight-sampler-abstraction.md](lightweight-sampler-abstraction.md).

## Phase 8M Status

Phase 8M implements the backend sampler abstraction for supplied in-memory frame planes.

The sampler evaluates supplied frame sequences, extracts debounced zone-local candidates, and can create pending MotionEvidence only when explicitly configured. It still does not sample real streams, decode media, attach media, run model runtimes, create reviewed labels, or create export-ready truth.

## Phase 8N Status

Phase 8N defines best-frame media attachment before implementation.

The design explains how `best_frame_index` can later become optional `snapshot_media_asset_id` context on pending MotionEvidence and promoted Event/Visit evidence. It adds no media capture, decoding, stream sampling, endpoints, workers, model calls, or truth writes. See [best-frame-media-attachment-design.md](best-frame-media-attachment-design.md).

## Phase 8O Status

Phase 8O reviews and tests best-frame media attachment schema/API compatibility.

MotionEvidence can preserve optional `snapshot_media_asset_id` through create, list, detail, ignore, and promote paths. Promotion with a Visit can expose linked MediaAsset context through existing Visit/detail media fields. Capture, decoding, stream sampling, thumbnails, model calls, and truth writes remain deferred.

## Phase 8P Status

Phase 8P defines local frame artifacts before implementation.

Local frame artifacts are future local visual evidence references that can link a motion candidate's best frame to a MediaAsset and `MotionEvidence.snapshot_media_asset_id`. This is design-only: no artifact creation, media capture, decoding, thumbnails, stream sampling, source adapter, model call, or truth write is added. See [local-frame-artifact-design.md](local-frame-artifact-design.md).

## Phase 8Q Status

Phase 8Q implements attachment of existing MediaAsset records to pending MotionEvidence.

This gives reviewers optional visual evidence context from already-local media while automated artifact creation remains deferred. Attachment does not capture frames, decode media, generate thumbnails, sample streams, call models, create reviewed labels, or create export-ready truth.

## Phase 8R Status

Phase 8R polishes Motion Evidence media visibility.

Attached existing MediaAsset references are easier to see and open from the Motion Evidence review surface, with preview when the current MediaAsset preview path supports it. Automated capture, media decoding, thumbnail generation, source adapters, stream workers, model calls, and truth writes remain deferred.

## Phase 8S Status

Phase 8S adds media-backed manual MotionEvidence creation.

Users can create pending MotionEvidence with an existing imported/local MediaAsset already attached as visual evidence context. Automated capture, media decoding, thumbnail generation, source adapters, stream workers, model calls, and truth writes remain deferred.

## Phase 8T Status

Phase 8T polishes the end-to-end local motion/media review demo loop.

The UI now better guides users through importing local media, creating media-backed MotionEvidence, previewing attached media, promoting useful evidence into unreviewed Event/Visit records, and saving review corrections as dataset/export truth. Automated capture, media decoding, thumbnail generation, source adapters, stream workers, SpeciesNet, MegaDetector, and truth writes from MotionEvidence remain deferred.

## Product Flow

The product should stay centered on streams, zones, reviewable events/visits, corrections, exports, and analytics.

Motion trigger flow:

1. User views a stream in the app.
2. User draws zones such as feeder, birdbath, ground, perch, yard, driveway, privacy, or ignore.
3. MockingBird samples local frames from the stream.
4. Motion is scored inside relevant zones.
5. A debounced trigger creates candidate snapshot evidence.
6. MotionEvidence is explicitly promoted into reviewable visit/event evidence.
7. A later species suggestion adapter can inspect the best frame or zone crop.
8. User correction becomes dataset/export truth.

## Why Motion Trigger First

Motion is a smaller, clearer first event trigger than a heavy detector runtime.

It can use product-owned context: streams and user-drawn zones. It can create reviewable evidence before species classification exists. It also gives later detector adapters better inputs: candidate frames, zone context, and a review path.

## What The MVP Detects

The MVP detects zone-local activity changes that are likely worth review.

Initial useful cases:

- feeder activity
- birdbath activity
- ground activity near feeder/birdbath
- driveway/person/vehicle activity candidates
- privacy/ignore zone suppression

## What The MVP Does Not Detect

The MVP does not identify species.

It does not classify animal type, create final labels, infer bounding boxes, inspect every full-resolution frame by default, or decide dataset truth.

It does not replace MegaDetector forever. MegaDetector, ONNX detectors, or another local detector can later improve boxes, blank filtering, and proposal quality.

## Zone-Aware Scoring

Motion should be scored per active zone, not as a whole-frame product concept.

Zone scoring should consider:

- zone type
- zone polygon
- whether the zone is active
- privacy or ignore zone suppression
- motion amount inside the zone
- motion persistence across sampled frames

The MVP should prefer low-resolution or downsampled scoring. It should not run motion detection on every full-resolution frame by default.

## Debounce/Cooldown Behavior

Motion should be debounced across multiple sampled frames before a candidate is created.

Cooldown should avoid repeated duplicate visits for the same ongoing activity. A candidate should represent a meaningful review case, not every flicker.

Future tuning can separate feeder, birdbath, ground, driveway, privacy, and ignore zone behavior.

## Ring Buffer / Best-Frame Selection

The stream processor should keep a short local ring buffer of sampled frames or frame references.

When motion is debounced, the best frame should be selected from the recent window. Best-frame selection can use zone motion score, sharpness, brightness, or future detector feedback.

The saved evidence should stay local and should be linked to the reviewable event/visit candidate.

## Snapshot And Visit Evidence Creation

The MVP should save candidate snapshot evidence only after debounce/cooldown rules pass.

It should create reviewable event/visit evidence with stream, zone, timestamp, and media reference context. These records are not reviewed truth.

Review Queue and detail pages remain the place where the user accepts, corrects, rejects, or refines the event meaning.

## Species Suggestion Handoff

SpeciesNet or another species classifier is a separate future suggestion adapter.

It should receive a best frame or zone crop only after the motion trigger has produced a review candidate. Species suggestions remain evidence until user correction.

Detection and species suggestion should stay separate so MockingBird can improve each without changing the product truth model.

## Truth Boundary

Motion output is evidence only.

It must not create reviewed labels, mark visits/events reviewed, bypass review, or write export-ready truth. User correction remains dataset/export truth.

Exports, coverage, QA, analytics, and adapter evaluation use reviewed/corrected labels as truth.

## Failure/Noise Cases

Expected noise cases:

- wind moving branches
- lighting changes
- rain/snow
- insects near the lens
- shadows
- repeated activity during cooldown
- activity split across zones
- privacy or ignore zone overlap

Failures should create no truth writes. Noisy candidates should be rejectable and should improve future tuning.

## Test Plan

Implementation tests should prove:

- zone polygons are respected
- privacy/ignore zones suppress normal review candidates
- debounce prevents one-frame flicker candidates
- cooldown prevents duplicate visits for continuous motion
- best-frame selection chooses from the local window
- candidate creation stores local media reference context
- no reviewed truth is written without user correction
- rejected/corrected review flow still works
- exports use corrected truth, not raw trigger evidence

## Future Detector Enrichment

MegaDetector or an ONNX/local-weight-only detector can later enrich motion candidates with boxes, blank filtering, or proposal confidence.

SpeciesNet or another species classifier can later suggest species from the best frame or zone crop.

These remain adapters underneath the product. They should enrich review evidence without replacing streams, zones, visits/events, corrections, exports, or analytics.

## Explicit Non-Goals

- no MegaDetector implementation in this plan
- no SpeciesNet implementation in this plan
- no species classifier in the motion MVP
- no camera/source adapter work
- no live video playback implementation
- no frame extraction worker
- no background scheduler
- no model downloads
- no production ML accuracy claims
- no truth without review
