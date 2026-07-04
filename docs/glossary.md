# MockingBird Glossary

## Camera

A user-facing outdoor camera concept.

## Source

An adapter-backed input that can provide video, images, clips, or stream data.

## Source Provider Configuration

Safe metadata describing the intended provider contract for a Source. It is not a
provider implementation, connection attempt, evidence, or reviewed truth.

## Manual Media Source

A Source/provider path for explicit local media import into Stream and Zone
context. Imports can create reviewable Events/Visits, but corrections remain the
source of truth.

## Folder / Trail-cam Import Provider

A Source provider configuration/status contract for future explicit local
folder, SD-card dump, NAS folder, or exported image batch import. The current
implementation stores redacted setup intent and supports an explicit dry-run
preview plus explicit import to MediaAssets only. It is not live playback, a
watcher, polling loop, evidence, Events/Visits, or reviewed truth.

## Folder Import MediaAsset

A supported image copied from a configured folder/trail-cam Source into local
MockingBird media storage through explicit user action. It has safe relative
source provenance and Stream context, but it is not MotionEvidence, an
Event/Visit, or reviewed truth.

## Folder Import UI

The Streams page surface for explicitly previewing configured folder candidates
and importing previewed files as MediaAssets only, dry-running evidence handoff
for imported items, and confirming eligible pending-evidence creation. It does
not watch folders, provide live playback, create Events/Visits, or create
reviewed truth.

## Folder Import Evidence Handoff

An explicit action that can turn one folder-imported MediaAsset into pending
MotionEvidence with attached media context. It does not create Events, Visits,
ReviewLabels, or reviewed truth.

## Folder Import Batch Evidence Dry-run

A read-only report over already-imported folder MediaAssets that shows which
items would be eligible for pending MotionEvidence and which would be skipped.
It creates no MotionEvidence, Events, Visits, labels, or reviewed truth.

## Batch Folder Evidence Creation

A confirmed action that creates pending MotionEvidence for eligible
folder-imported MediaAssets from the batch dry-run boundary. It creates no
Events, Visits, ReviewLabels, reviewed status, or truth.

## Folder Import Evidence

Pending MotionEvidence created from one folder-imported MediaAsset or a
confirmed eligible batch. It points to the imported MediaAsset as
`snapshot_media_asset_id`, can show safe folder-import provenance and attached
media in review UI, and remains evidence until explicit promotion and later
review/correction.

## Source Connection Status

A read-only product contract describing Source provider readiness and related
Streams. It is not a provider implementation, evidence, or reviewed truth.

## Source Adapter Boundary

The design boundary that keeps real provider code underneath Source connection
and Stream playback contracts. It prevents adapters from creating truth,
skipping review, leaking secrets, or redefining the product flow.

## Provider Smoke Flow

Automated backend validation that an implemented provider path stays under the
Source/Stream contract: status routes are read-only, provider work requires
explicit user action, MediaAssets and MotionEvidence are evidence/context only,
and ReviewLabel correction is the first reviewed truth write.

## Provider Workflow

A Source/provider path shown as setup readiness, playback honesty, zone-editing
availability, and the next explicit user action. It is product status, not
provider execution.

## Next Action Cue

A read-only UI prompt that sends the user to an explicit workflow such as
Streams, Import Media, Motion Evidence, Retention, or Review. It does not run
providers, create evidence, or create reviewed truth.

## External URL Still-image Provider

An `external_url` Source provider contract for explicit HTTP still-image
preview/status. It is not RTSP, continuous video, a worker, evidence, or reviewed
truth.

## Generic Webhook Provider

A Source provider configuration/status contract for local systems that may
submit media or event candidates into MockingBird later through
`webhook_future`. The current layer stores metadata and redacted shared-secret
readiness, explicit payload validation/dry-run, and confirmed metadata motion
payloads to pending MotionEvidence only. It has no media ingest endpoint, no
real auth/token generation, creates no Events/Visits or truth, and must not
treat incoming labels, detections, or events as reviewed truth.

## Webhook Payload Validation

An explicit dry-run API for `webhook_future` Sources that checks generic payload
shape and Source/Stream/Zone context. It can report candidate mappings such as
heartbeat, motion event, object detection, species suggestion, or media
reference, but it creates no records, fetches no media, authenticates no
payloads, and writes no reviewed truth.

## Webhook Motion Evidence

Pending MotionEvidence created from an explicit confirmed metadata-only webhook
motion payload. It preserves safe webhook provenance and Stream/Zone context,
but creates no MediaAsset, Event, Visit, ReviewLabel, or reviewed truth.

## Still-image Preview

A transient, explicit image preview fetched from an `external_url` Source. It is
not saved media, live playback, evidence, an Event/Visit, or reviewed truth.

## Saved Preview MediaAsset

An explicitly saved still-image preview linked to Source/Stream context. It is
local media context, not MotionEvidence, an Event/Visit, or reviewed truth.

## Saved Preview Evidence Handoff

An explicit action that turns a saved preview MediaAsset into pending
MotionEvidence. The Motion Evidence UI can show its attached saved media and
safe provenance, but it does not create Events, Visits, ReviewLabels, or truth.

## Saved Preview Retention

The future policy/reporting layer for deciding how saved preview MediaAssets are
kept, archived, or cleaned up without silently deleting reviewed truth or
breaking MotionEvidence/Event/Visit provenance.

## Retention Report

A read-only saved media summary that lists saved preview MediaAssets, linkage,
size metadata, warnings, and cleanup risk. It does not delete files, delete
records, fetch URLs, create evidence, or mutate truth.

## Cleanup Dry Run

A read-only preview of what a future cleanup action might affect. It reports
candidate files or records and protected skips, but deletes nothing and changes
no review truth.

## Saved Media Retention UI

A frontend view of saved preview media retention status, risk levels, warnings,
cleanup dry-run results, and confirmed low-risk file cleanup. It must not delete
records or reviewed truth.

## File-only Cleanup

An explicit local storage action that deletes an eligible saved preview media
file while leaving the MediaAsset record, evidence, Events, Visits, labels,
exports, and reviewed truth intact.

## Retention Risk Level

A cleanup classification for saved media, such as low, medium, high, or
protected, based on whether the MediaAsset is unlinked, attached to evidence,
promoted into Event/Visit context, or linked to reviewed correction truth.

## Source Setup Review

A read-only product summary of provider configuration, Source connection
readiness, and related Stream playback readiness. It does not connect, capture,
decode, create evidence, or write reviewed truth.

## Readiness Level

A user-facing setup state such as demo ready, metadata ready, needs setup, future
adapter required, or unavailable.

## Stream

The central video experience shown in the app.

## Stream Playback Status

A read-only product contract describing whether a stream can show a demo panel,
placeholder, preview, or future playback surface. It is not evidence or reviewed
truth.

## Zone

A user-drawn area on a stream that gives outdoor activity context.

## Feeder Zone

A zone around a bird feeder.

## Birdbath Zone

A zone around a birdbath or water source.

## Privacy Zone

A zone where detection, storage, or review should be limited or disabled.

## Ignore Zone

A zone where activity should not create normal review events.

## Event

A meaningful outdoor activity record.

## Visit

A reviewable animal-centered event, especially around feeders, birdbaths, perches, or yard zones.

## Detection

A machine-generated observation that may be right or wrong.

## Motion Candidate

A debounced motion signal from scored frame differences in a stream zone.

## Best Frame

The candidate frame most useful for review context or later species suggestion; it is evidence context, not truth.

## Local Frame Artifact

A future local visual evidence reference for a selected frame; it is distinct from frame planes and is not truth.

## Sampled Frame

A lightweight local representation of a stream or media moment that can become a frame plane for motion scoring; it is not reviewed truth.

## Frame Plane

A rectangular 2D array of numeric grayscale values used for zone-aware motion scoring.

## Sampler

A local component that can produce frame planes from configured stream or media context; it is not a source adapter, detector, or truth source.

## Motion Evidence

Local evidence that a motion candidate occurred in a stream zone; it is not reviewed truth.

## Motion Evidence Promotion

An explicit action that turns pending Motion Evidence into unreviewed Event/Visit evidence; it does not create reviewed truth.

## Promoted Saved Preview Evidence

Reviewable Event/Visit context created by explicitly promoting MotionEvidence
that was linked to saved preview media. It can show saved local media provenance,
but correction remains truth.

## SpeciesSuggestion

Local classifier evidence that a media item or crop may contain a species or taxon; its pending/accepted/rejected/superseded status is not reviewed truth.

## SpeciesSuggestionAdapter

A local optional adapter that creates SpeciesSuggestion evidence from media-backed Event/Visit context without creating labels, exports, or dataset truth.

## Apply Suggestion As Correction

A future explicit user action that pre-fills the existing correction flow from a SpeciesSuggestion; truth is created only when the correction is submitted.

## Review

The user process of confirming, correcting, merging, hiding, or rejecting events.

## Correction

A user-provided truth label that improves the local dataset.

## Dataset Export

A local export of reviewed media, labels, corrections, and metadata.

## Analytics

Local summaries of outdoor activity over time.
