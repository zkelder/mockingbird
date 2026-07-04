# Folder Import Evidence Handoff Design

## Purpose

Phase 13D imports folder/trail-cam files as local MediaAssets only. Phase 13E
exposes explicit preview/import UI for those files. Phase 13G adds explicit
single-media handoff to pending MotionEvidence. Phase 13H adds a batch dry-run
report before any future batch creation. Phase 13I adds confirmed batch
creation of pending MotionEvidence for eligible folder-imported MediaAssets.
Phase 13J polishes the review/promote UI so folder provenance, attached media,
pending/ignored/promoted state, and truth boundaries stay visible.

Folder-imported MediaAssets are local media context. They are not evidence,
Events, Visits, labels, classifier examples, analytics truth, export truth, or
reviewed truth by themselves.

Users can now review imported trail-cam media as possible outdoor activity by
explicitly creating one pending MotionEvidence record from one folder-imported
MediaAsset. They can also dry-run a batch handoff report for imported
MediaAssets and confirm batch creation for eligible items. This design records
those handoffs while keeping promotion, correction, and truth separate.
Folder-origin evidence remains evidence until explicit promote, and
review/correction remains the truth boundary.

## Product Flow

folder_import_future Source setup -> folder import preview -> explicit import
to MediaAssets -> optional batch evidence dry-run -> user chooses imported
media or confirms eligible batch -> explicit "create pending evidence" -> pending MotionEvidence ->
explicit ignore or promote -> Event/Visit review -> user correction -> ReviewLabel truth ->
analytics/exports/classifier readiness.

## Current Behavior After Phase 13J

- Folder preview is an explicit dry run.
- Folder import is explicit.
- Import copies supported files to the local media root.
- Import creates MediaAssets only.
- Folder import itself creates no MotionEvidence.
- One folder-imported MediaAsset can become one pending MotionEvidence only
  through explicit user action.
- Batch evidence handoff has a dry-run report and confirmed create action.
- The batch dry-run can report eligible, duplicate, skipped, privacy/ignore,
  missing-file, and context-mismatch cases.
- Confirmed batch creation can create pending MotionEvidence for eligible
  folder-imported MediaAssets only.
- Batch creation skips duplicates by default and reports skipped items.
- Motion Evidence review shows folder-imported media provenance and attached
  media context without exposing raw absolute folder paths.
- Promoted Event/Visit detail can show folder-imported media context while
  correction remains truth.
- Phase 14A smoke coverage proves single and batch handoff create pending
  MotionEvidence only, while promotion and correction remain explicit later
  actions.
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

## Implemented Explicit Action

Implemented single-media route:

```text
POST /api/media/{media_asset_id}/create-motion-evidence
```

The shared saved-media handoff route now supports folder-imported MediaAssets
instead of adding a folder-specific duplicate route. The action:

- require explicit user action
- validate the MediaAsset exists
- validate MediaAsset provenance/context
- allow folder-imported media as an eligible source
- infer Source/Stream where available
- optionally accept `zone_id`
- reject Privacy Zone and Ignore Zone by default
- create pending MotionEvidence only
- set `snapshot_media_asset_id`
- skip existing pending, promoted, or ignored evidence by default
- create no Event/Visit
- create no ReviewLabel
- create no truth

Implemented batch dry-run route:

```text
POST /api/folder-import/evidence/dry-run
```

The dry-run action:

- requires MediaAsset ids, Source, or Stream scope
- reads existing folder-imported MediaAssets only
- reports whether pending MotionEvidence would be created
- skips duplicates by default
- reports blocked Privacy Zone and Ignore Zone context
- reports stale or missing local files when detectable
- creates no MotionEvidence
- creates no Event/Visit
- creates no ReviewLabel
- creates no truth
- performs no folder scan, media import, decoding, or model runtime call

Implemented batch creation route:

```text
POST /api/folder-import/evidence/batch
```

The confirmed batch action:

- requires explicit confirmation
- reuses the batch dry-run eligibility rules
- creates pending MotionEvidence for eligible folder-imported MediaAssets only
- sets `snapshot_media_asset_id`
- preserves Source/Stream/Zone context
- skips duplicates by default
- reports skipped items with reasons
- creates no Event/Visit
- creates no ReviewLabel
- creates no truth
- performs no folder scan, media import, decoding, URL fetch, or model runtime call

## Eligibility Policy

Eligible media:

- MediaAssets created by `folder_import_future`
- MediaAssets with Source/Stream context
- supported still-image media
- local files that still exist

Ineligible or warning cases:

- stale or missing media files
- media without Stream context unless the user supplies one
- media already linked to pending/promoted/ignored evidence, unless duplicate
  creation is explicitly requested
- Privacy Zone or Ignore Zone context
- unsupported media types
- media already tied to reviewed truth, unless creating another evidence record
  is clearly justified

## Request Fields

Request:

- `media_asset_id` path parameter
- `stream_id`, optional if inferable
- `zone_id`, optional
- `note`, optional
- `reason`, optional
- `duplicate_policy`, optional, such as `skip_existing` or `allow_duplicate`

No model inference happens here. No species label is accepted as truth. Zone
context is context only, not label truth.

## Response Fields

Response:

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
- `existing_motion_evidence_id`, optional
- `provenance_kind`, such as `folder_import`
- `message`
- `warnings`

## Source/Stream/Zone Relationship

Folder-import provenance should preserve Source/Stream context. Stream context
makes zone review possible. Zone context can be user-selected during handoff.

Privacy Zones should block evidence creation by default. Ignore Zones should
skip evidence creation by default. Zone context is not activity truth, species
truth, or reviewed truth.

## Batch Handoff Design

Folder imports can include many files, so batch handoff remains a separate
explicit workflow.

Current Phase 13H behavior:

- dry-run selected imported MediaAssets, a Source, or a Stream
- report counts and skipped reasons
- skip existing evidence by default
- cap dry-run size
- create no product records

Current Phase 13I behavior:

- create pending evidence for selected imported MediaAssets
- require explicit confirmation
- reuse dry-run eligibility
- skip existing evidence by default
- show counts and skipped reasons
- create no Event/Visit automatically
- create no labels automatically
- include max batch size safeguards

Phase 13I implements batch creation of pending MotionEvidence only. Promotion,
Event/Visit creation, and ReviewLabel truth remain explicit later steps.

## Duplicate Evidence Policy

If a MediaAsset already has pending, promoted, or ignored MotionEvidence, default
behavior skips it and returns the existing evidence id. An explicit
`allow_duplicate` override exists for rare manual review cases.

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

The Streams page shows "Create pending evidence" on each imported MediaAsset
after folder import results.

Current behavior:

- acts on one imported MediaAsset at a time
- supports a dry-run and confirmed batch creation path for pending evidence
- reports duplicate skips and validation errors
- cues the user to open the Motion Evidence page after creation
- use copy such as "Pending evidence only. No Events, Visits, labels, or truth
  created."
- Motion Evidence shows folder-imported media, safe relative provenance,
  pending/ignored/promoted state, and explicit ignore/promote actions.
- Event/Visit detail can show promoted folder-origin media while keeping
  correction as the truth boundary.

Avoid product copy that implies automatic detection, confirmed visits, training,
watching folders, polling, stream recording, or adapter/debug internals.

## Testing Expectations

Tests prove:

- explicit handoff creates pending MotionEvidence only
- MediaAsset must exist
- folder-import provenance is preserved
- missing/stale media is rejected safely
- duplicate evidence is skipped by default
- stream and zone validation work
- privacy/ignore zones are rejected
- no Events/Visits are created
- no ReviewLabels/truth are created
- classifier readiness/export is unchanged
- no model/detector runtime is called
- no source folder files are deleted
- no network fetch occurs

Batch tests separately prove dry-run, confirmed creation, and selected-media
behavior.

## Recommended Future Phases

- Phase 13G: implemented single folder-imported MediaAsset to pending
  MotionEvidence, no Event/Visit/truth.
- Phase 13H: batch folder media evidence handoff dry-run.
- Phase 13I: batch folder media evidence creation, no Event/Visit/truth.
- Phase 13J: folder media review/promote UI polish.
- Phase 14A: consolidated provider smoke coverage with `external_url`.
- Next likely: Phase 13K folder import retention/report design, Phase 14B
  source/provider status polish, or Phase 14C next provider boundary decision.
- Later: automated folder scoring/design, if ever.

## Explicit Non-Goals

- No automatic MotionEvidence creation.
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
