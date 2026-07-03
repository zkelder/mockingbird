# Motion Evidence Design

## Purpose

Motion Evidence exists between raw motion scores and reviewable visits/events.

The scoring core can say that a zone changed across a candidate frame window. That is useful, but it is still too early to create product truth. Motion Evidence gives MockingBird a local product concept for preserving that signal, attaching later media context, and deciding whether the activity should become reviewable Event/Visit evidence.

## Product Flow

Planned flow:

stream/frame sample -> zone-aware motion score -> debounced motion candidate -> Motion Evidence record -> optional snapshot/best-frame attachment -> later promotion to Event/Visit -> review/correction -> dataset/export truth.

The Motion Evidence step protects the product loop by keeping motion as evidence until explicit promotion and user correction happen.

Phase 8E defines promotion separately in [motion-evidence-promotion-design.md](motion-evidence-promotion-design.md). Phase 8F implements the API/repository foundation for promoting pending Motion Evidence into unreviewed Event/Visit evidence.

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

The existing `snapshot_media_asset_id` field remains optional evidence context. It may later point to a MediaAsset representing a local frame artifact. MotionEvidence can be created, listed, viewed, ignored, or promoted without media. Media attachment alone must not create labels, reviewed status, export truth, dataset coverage truth, or species truth.

Saved external URL preview MediaAssets are another explicit source for
`snapshot_media_asset_id`. Phase 11G lets them enter MotionEvidence through a
user action, not automatically when the preview is saved.

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

Phase 8C was design only.

Likely future phases:

- Phase 8D introduces MotionEvidence schemas and repository behavior, either in-memory first or persistent depending on the task packet.
- Phase 8E defines Motion Evidence promotion without adding an endpoint or repository method.
- Phase 8F wires Motion Evidence promotion into Event/Visit creation while preserving review/correction truth.
- Stream sampler and media capture work comes later.

No promotion API, event creation, media capture, stream sampling, or worker implementation is added in Phase 8E.

## Phase 8D Status

Phase 8D implements the MotionEvidence schema, repository, and narrow API foundation.

Motion Evidence can now be explicitly created as `pending`, listed, viewed by id, and marked `ignored`. Creation and ignore actions do not create Events, Visits, ReviewLabels, DatasetExports, DatasetCoverage, analytics truth, species labels, media files, stream samples, or detector output.

Promotion remains future work.

## Phase 8E Status

Phase 8E documents what promotion means before implementation. Promotion should convert pending Motion Evidence into unreviewed Event/Visit evidence, mark the evidence promoted, link created records, and preserve the truth boundary. See [motion-evidence-promotion-design.md](motion-evidence-promotion-design.md).

## Phase 8F Status

Phase 8F implements `POST /api/motion/evidence/{evidence_id}/promote`.

Pending Motion Evidence can now be promoted into unreviewed Event/Visit evidence. The original Motion Evidence remains queryable, is marked `promoted`, and links to created product records. Promotion rejects ignored, already promoted, privacy-zone, and ignore-zone evidence. It still does not create ReviewLabels, reviewed status, species truth, exports, dataset coverage truth, model output, media files, stream samples, or detector output.

## Phase 8G Status

Phase 8G adds a Motion Evidence review surface in the app.

Users can now see pending, promoted, and ignored Motion Evidence, inspect scoring context, ignore noise, and promote useful evidence into unreviewed Event/Visit context. The review surface does not create reviewed labels, species truth, exports, dataset coverage truth, stream samples, media files, or detector output.

## Phase 8H Status

Phase 8H adds a manual Motion Evidence creation surface inside the review page.

Manual creation is for exercising the local evidence loop before stream sampling is wired in. It creates pending Motion Evidence only, then the normal review surface can ignore or promote it. Manual creation does not create ReviewLabels, reviewed observations, exports, dataset coverage truth, stream samples, media files, detector output, or species truth.

## Phase 8I Status

Phase 8I adds frame sequence evaluation as another way to create pending MotionEvidence.

The backend accepts already-sampled grayscale frame planes, scores consecutive pairs, extracts debounced candidates, and can optionally save those candidates as pending MotionEvidence. This remains evidence only: it does not create Events, Visits, ReviewLabels, exports, dataset coverage truth, media files, stream samples, detector output, or species truth.

## Phase 8J Status

Phase 8J defines sampled-frame ingestion as the planned upstream source of pending MotionEvidence.

Sampled frames should bridge visible streams to frame-plane evaluation, then MotionEvidence review/promotion. The design keeps sampling, media attachment, and automation separate from reviewed labels, exports, dataset coverage truth, detector output, and species truth. See [sampled-frame-ingestion-design.md](sampled-frame-ingestion-design.md).

## Phase 8K Status

Phase 8K adds a browser harness that submits supplied tiny frame planes to the sequence evaluation API.

When requested, the harness creates pending MotionEvidence only. Users still ignore or promote evidence from the normal Motion Evidence surface, and correction remains the only dataset/export truth path.

## Phase 8L Status

Phase 8L defines the sampler as a future upstream source of pending MotionEvidence.

The sampler should produce frame planes from configured stream/media context and call the existing sequence evaluation contract. It should create pending MotionEvidence only when explicitly configured, and correction remains the only dataset/export truth path.

## Phase 8N Status

Phase 8N defines best-frame media attachment as design-only.

Best-frame media can later give MotionEvidence and promoted Event/Visit evidence visible context, but `snapshot_media_asset_id` remains nullable and optional. This phase adds no media capture, decoding, model calls, labels, reviewed status, exports, dataset coverage truth, or species truth. See [best-frame-media-attachment-design.md](best-frame-media-attachment-design.md).

## Phase 8O Status

Phase 8O confirms the existing schema/API path for optional best-frame media context.

MotionEvidence create, list, detail, ignore, and promote paths preserve `snapshot_media_asset_id`. Promotion with a created Visit can expose the linked MediaAsset through existing Visit media context. Direct Event-only media propagation remains future work. No media capture, decoding, labels, reviewed status, exports, dataset coverage truth, model output, or species truth is added.

## Phase 8P Status

Phase 8P defines local frame artifacts before implementation.

Local frame artifacts are future local visual evidence references that may become MediaAssets attached through `snapshot_media_asset_id`. They are separate from frame planes and remain evidence context only. No artifact creation, media capture, decoding, thumbnails, labels, exports, dataset coverage truth, model output, or species truth is added. See [local-frame-artifact-design.md](local-frame-artifact-design.md).

## Phase 8Q Status

Phase 8Q lets pending MotionEvidence attach, replace, or clear an existing MediaAsset reference through `snapshot_media_asset_id`.

The attachment is evidence context only. It does not create Event, Visit, ReviewLabel, export, dataset coverage truth, reviewed status, media files, thumbnails, model output, or species truth. Ignored and promoted evidence reject media attachment changes.

## Phase 8R Status

Phase 8R improves the Motion Evidence review surface for attached media context.

When `snapshot_media_asset_id` is present, the UI shows the attached visual evidence context, the MediaAsset ID, existing media-file access, and inline preview when the existing MediaAsset preview path supports it. Evidence without media remains reviewable, ignorable, and promotable. Media context does not create species labels, reviewed observations, exports, dataset coverage truth, or any other dataset truth.

## Phase 11F Relationship

Phase 11F designed saved preview MediaAsset -> pending MotionEvidence handoff as
an explicit action. It reuses MotionEvidence pending/ignored/promoted
lifecycle and keeps ReviewLabel correction as the truth boundary.

## Phase 11G Status

Phase 11G implements the saved preview MediaAsset -> pending MotionEvidence
handoff. The action stores the saved MediaAsset as `snapshot_media_asset_id`,
preserves Source/Stream/Zone context where available, and creates no Event,
Visit, ReviewLabel, export, dataset coverage truth, model output, or species
truth.

## Phase 11H Status

Phase 11H polishes the Motion Evidence review UI for saved-preview-origin
evidence. When attached saved media is present, the UI surfaces media preview/file
access, safe saved-local-media provenance, Source/Stream/Zone context, and clear
pending/ignored/promoted state. Ignore and promote remain explicit, and saved
media still creates no labels, reviewed status, exports, dataset coverage truth,
model output, or species truth.

## Phase 11I Status

Phase 11I keeps saved-preview-origin evidence understandable after explicit
promotion. Promoted MotionEvidence can link users to the reviewable Event/Visit,
and Event/Visit detail pages can show saved media provenance while correction
remains the only source of analytics/export truth.

## Phase 12A Status

Phase 12A adds source/stream smoke coverage around saved-preview-origin
MotionEvidence. The tests verify that MediaAsset -> pending MotionEvidence
handoff creates evidence only, MotionEvidence reads do not fetch external URLs,
promotion is explicit, and dataset/analytics truth changes only after
ReviewLabel correction.

## Phase 12B Status

Phase 12B adds a manual developer/browser checklist for validating the same
saved-preview-origin MotionEvidence path in the running app. See
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).

## Phase 12C Status

Phase 12C designs retention rules for saved preview media attached to
MotionEvidence. Attached media can be useful review context, so cleanup must
warn for pending/promoted evidence, protect reviewed truth by default, and avoid
silently weakening provenance. See
[external-url-saved-media-retention-design.md](external-url-saved-media-retention-design.md).

## Phase 12D Status

Phase 12D implements the saved-preview retention report and cleanup dry-run
planner. Pending and ignored MotionEvidence media is medium risk, promoted
Event/Visit media is high risk, reviewed correction media is protected, and the
routes delete nothing and create no truth.

## Phase 12E Status

Phase 12E surfaces attached saved-preview media retention risk in the Saved
Media Retention UI. The UI can run dry-run cleanup previews, but it deletes no
files, deletes no records, and creates no truth.

## Phase 12F Status

Phase 12F adds confirmed file-only cleanup for low-risk unlinked saved preview
media. Media attached to MotionEvidence is medium risk or higher and is
protected from this low-risk cleanup path.

## Phase 8S Status

Phase 8S lets pending MotionEvidence be created with optional `snapshot_media_asset_id`.

The media reference must point to an existing MediaAsset on the same stream. Media-backed creation still creates only pending evidence: no Event, Visit, ReviewLabel, export, dataset coverage truth, reviewed status, media file, thumbnail, model output, or species truth is created.

## Phase 8T Status

Phase 8T polishes the local media-backed MotionEvidence demo loop.

The Motion Evidence page now makes the workflow clearer: create or evaluate evidence, optionally attach existing imported media, preview that media, promote useful evidence into unreviewed Event/Visit records, then correct labels during review. Event and Visit detail pages identify promoted Motion Evidence using existing product fields. No stream capture, media decoding, thumbnail generation, source adapter, model call, ReviewLabel, export, dataset coverage truth, or species truth is created by this polish.

## Test Plan

Implementation tests should prove:

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
