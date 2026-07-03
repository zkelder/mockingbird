# Folder Import Evidence Handoff Design

## Purpose

Phase 13D imports folder/trail-cam files as local MediaAssets only. Phase 13E
exposes explicit preview/import UI for those files.

Folder-imported MediaAssets are local media context. They are not evidence,
Events, Visits, labels, classifier examples, analytics truth, export truth, or
reviewed truth by themselves.

Users may later want to review imported trail-cam media as possible outdoor
activity. This design defines the future handoff from folder-imported
MediaAssets into pending MotionEvidence while keeping review, promotion,
correction, and truth separate.

## Product Flow

folder_import_future Source setup -> folder import preview -> explicit import
to MediaAssets -> user reviews imported media -> optional future "create
MotionEvidence from folder media" -> pending MotionEvidence -> explicit ignore
or promote -> Event/Visit review -> user correction -> ReviewLabel truth ->
analytics/exports/classifier readiness.

## Current Behavior After Phase 13E

- Folder preview is an explicit dry run.
- Folder import is explicit.
- Import copies supported files to the local media root.
- Import creates MediaAssets only.
- No MotionEvidence is created.
- No Event is created.
- No Visit is created.
- No ReviewLabel is created.
- No reviewed truth is created.
- No watcher or polling behavior exists.

## Recommended Handoff Path

Recommended path:

folder-imported MediaAsset -> explicit "Create pending evidence from imported
media" -> pending MotionEvidence with `snapshot_media_asset_id` -> user reviews
MotionEvidence -> explicit promote to Event/Visit -> Visit correction ->
ReviewLabel truth.

MotionEvidence is the right first handoff because it already represents evidence
before Event/Visit context, already has pending/ignored/promoted lifecycle,
already supports media attachment, keeps imported media from becoming Event/Visit
automatically, and mirrors the saved external URL preview handoff pattern.

## Alternative Paths Considered

- Direct folder import to Event/Visit by default: rejected because it is too
  strong and risks false activity records.
- Direct folder import to ReviewLabel: invalid because labels require reviewed
  Visit/Event context.
- Direct folder import to classifier training: invalid because training truth
  requires reviewed correction.
- Automatic evidence creation for every imported image: deferred because it
  needs separate automation, privacy, duplicate, and storage design.
- Model classification during import: deferred because suggestions must remain
  evidence only and never create truth during import.

## Future Explicit Action Design

Future implementation can use:

```text
POST /api/media/{media_asset_id}/create-motion-evidence
```

If the existing saved-media handoff route is generic enough, reuse it instead of
creating a folder-specific duplicate route.

The future action should:

- require explicit user action
- validate the MediaAsset exists
- validate MediaAsset provenance/context
- allow folder-imported media as an eligible source
- infer Source/Stream where available
- optionally accept `zone_id`
- reject Privacy Zone and Ignore Zone by default
- create pending MotionEvidence only
- set `snapshot_media_asset_id`
- create no Event/Visit
- create no ReviewLabel
- create no truth

## Eligibility Policy

Eligible media:

- MediaAssets created by `folder_import_future`
- MediaAssets with Source/Stream context
- supported still-image media
- local files that still exist

Ineligible or warning cases:

- stale or missing media files
- media without Stream context unless the user supplies one
- media already linked to pending/promoted evidence, unless duplicate creation
  is explicitly allowed later
- Privacy Zone or Ignore Zone context
- unsupported media types
- media already tied to reviewed truth, unless creating another evidence record
  is clearly justified

## Request Fields

Possible future request:

- `media_asset_id` path parameter
- `stream_id`, optional if inferable
- `zone_id`, optional
- `note`, optional
- `reason`, optional
- `batch_id`, optional for future folder batches
- `duplicate_policy`, optional, such as `skip_existing` or `allow_duplicate`

No model inference happens here. No species label is accepted as truth. Zone
context is context only, not label truth.

## Response Fields

Possible future response:

- `motion_evidence_id`
- `media_asset_id`
- `source_id`
- `stream_id`
- `zone_id`
- `status`: `pending`
- `creates_event`: false
- `creates_visit`: false
- `creates_truth`: false
- `duplicate_skipped`: bool
- `message`
- `warnings`

## Source/Stream/Zone Relationship

Folder-import provenance should preserve Source/Stream context. Stream context
makes zone review possible. Zone context can be user-selected during handoff.

Privacy Zones should block evidence creation by default. Ignore Zones should
skip evidence creation by default. Zone context is not activity truth, species
truth, or reviewed truth.

## Batch Handoff Design

Folder imports can include many files, so future batch handoff should be a
separate explicit workflow.

Future batch options:

- create pending evidence for selected imported MediaAssets
- dry-run batch evidence creation first
- skip existing evidence by default
- show counts and skipped reasons
- create no Event/Visit automatically
- create no labels automatically
- include max batch size safeguards

This phase does not implement batch handoff.

## Duplicate Evidence Policy

If a MediaAsset already has pending or promoted MotionEvidence, default behavior
should skip it. A future explicit duplicate override can exist only with clear
warnings.

Duplicate MotionEvidence can confuse review queues, duplicate promotion, and make
cleanup risk harder to understand. Skipped duplicates should be reported with
clear MediaAsset ids and reasons.

## Privacy/Ignore Boundary

Imported folder media may include sensitive outdoor imagery. Evidence creation
must be explicit.

Privacy Zones block by default. Ignore Zones skip by default. Future automation
must separately prove privacy and ignore handling before it can create evidence
from folder media. No cloud upload happens by default.

## Evidence/Event Boundary

MotionEvidence is evidence, not truth. Pending MotionEvidence is not Event or
Visit. Promotion creates Event/Visit context only through the explicit promote
route.

Event/Visit records still require review and correction. ReviewLabel remains
truth. Analytics, exports, and classifier readiness use reviewed corrections,
not raw folder-imported media.

## Relationship To Folder Import Retention/Cleanup

Imported folder media can accumulate. Cleanup/retention policy should apply to
folder-imported MediaAssets in a later phase.

Media linked to evidence should become medium or high risk. Media linked to
reviewed truth should be protected. MockingBird cleanup must not delete original
source folder files.

## Relationship To Saved External URL Previews

An `external_url` saved preview is one fetched still image saved as a MediaAsset.
Folder import is a batch of local files copied as MediaAssets.

Both require explicit handoff to MotionEvidence, both use
`snapshot_media_asset_id`, and both preserve correction as the truth boundary.

## Relationship To Classifier/Export Pipeline

- Folder-imported MediaAssets are not classifier examples by themselves.
- MotionEvidence is not classifier truth.
- Event/Visit without correction is not classifier truth.
- Reviewed media-backed corrections are training/export truth.
- SpeciesSuggestion remains model evidence only.

## UI Design

Future UI can show "Create pending evidence from imported media" after folder
import results.

Recommended behavior:

- allow selected files or all newly imported files
- run a dry-run first for batch actions
- show evidence creation preview counts
- show skipped duplicates and privacy/ignore skips
- link to the Motion Evidence page after creation
- use copy such as "Pending evidence only. No Events, Visits, labels, or truth
  created."

Avoid product copy that implies automatic detection, confirmed visits, training,
watching folders, polling, stream recording, or adapter/debug internals.

## Testing Expectations For Future Implementation

Future tests should prove:

- explicit handoff creates pending MotionEvidence only
- MediaAsset must exist
- folder-import provenance is preserved
- missing/stale media is skipped
- duplicate evidence is skipped by default
- stream and zone validation work
- privacy/ignore zones are rejected
- batch dry-run creates nothing
- batch create creates only MotionEvidence
- no Events/Visits are created
- no ReviewLabels/truth are created
- classifier readiness/export is unchanged
- no model/detector runtime is called
- no source folder files are deleted
- no network fetch occurs

## Recommended Future Phases

- Phase 13G: implement single folder-imported MediaAsset to pending
  MotionEvidence, no Event/Visit/truth.
- Phase 13H: batch folder media evidence handoff dry-run.
- Phase 13I: batch folder media evidence creation, no Event/Visit/truth.
- Phase 13J: folder media review/promote UI polish.
- Later: automated folder scoring/design, if ever.

## Explicit Non-Goals

- No implementation in this phase.
- No MotionEvidence creation.
- No Events/Visits.
- No ReviewLabels.
- No truth creation.
- No batch automation.
- No folder watcher.
- No polling.
- No media deletion.
- No live playback.
- No video decoding.
- No model/training work.
