# External URL Saved Media Retention Design

## Purpose

Explicit external_url preview saves can create local MediaAssets. Those saved
still images may remain unlinked, or they may later become MotionEvidence
context, promoted Event/Visit context, and reviewed correction context.

Retention design is needed because saved media can accumulate over time, while
cleanup must preserve review provenance and truth boundaries. Deletion behavior
needs a clear product policy before any implementation so MockingBird never
silently deletes reviewed truth, breaks evidence context, or surprises users.

Phase 12C was design only. Phase 12D implements the first read-only retention
report and cleanup dry-run planning API. It still adds no cleanup
implementation, retention job, UI, generated media, record deletion, file
deletion, or truth mutation.
Phase 12E adds the frontend Saved Media Retention page for viewing that report
and running dry-run cleanup previews. It still adds no actual cleanup
implementation, media deletion, record deletion, generated media, or truth
mutation.
Phase 12F implements the first destructive action: an explicit, confirmed,
file-only cleanup route for low-risk unlinked saved preview media. It deletes no
MediaAsset records, MotionEvidence, Events, Visits, ReviewLabels,
DatasetExports, or truth.

## Product Flow Covered

external_url Source setup -> explicit preview fetch -> explicit save as
MediaAsset -> optional pending MotionEvidence handoff -> optional explicit
promotion to Event/Visit -> optional correction/review truth ->
retention/cleanup decision.

## Current Behavior

- Preview fetch is transient.
- Save creates one local MediaAsset.
- Media-to-evidence creates pending MotionEvidence only.
- Promotion creates Event/Visit only through the explicit route.
- Correction creates ReviewLabel truth.
- Confirmed low-risk file cleanup can delete only an unlinked saved preview file.
- Record deletion, protected cleanup, background cleanup, and bulk destructive
  cleanup remain future work.
- Saved preview media lives under ignored local data/media storage.

## Retention Principles

- Local-first by default.
- User-controlled cleanup.
- No automatic deletion before explicit design and implementation.
- No cloud upload by default.
- No deleting reviewed/truth-linked media without warnings.
- No silently breaking MotionEvidence, Event, or Visit provenance.
- Cleanup must distinguish file deletion from record deletion.

## Media States

- `saved_unlinked`: MediaAsset exists but is not linked to MotionEvidence,
  Event, or Visit context.
- `linked_pending_evidence`: MediaAsset is `snapshot_media_asset_id` for
  pending MotionEvidence.
- `linked_ignored_evidence`: MediaAsset is linked to ignored MotionEvidence.
- `linked_promoted_evidence`: MediaAsset is linked to promoted MotionEvidence.
- `linked_event_visit`: MediaAsset is linked to Event/Visit context, such as
  representative media on a promoted Visit.
- `reviewed_truth_context`: MediaAsset supports a reviewed Visit and ReviewLabel
  truth.
- `export_candidate`: reviewed media-backed correction may affect classifier or
  export readiness.

## Cleanup Risk Levels

- `low`: saved preview media is unlinked. Future cleanup UI/API can present this
  as the safest candidate for deletion or archive.
- `medium`: saved preview media is linked to ignored evidence or stale pending
  evidence. Future cleanup should warn that review context may be weakened.
- `high`: saved preview media is linked to promoted Event/Visit context. Future
  cleanup should avoid default deletion and require clear confirmation.
- `protected`: saved preview media is linked to reviewed correction, export, or
  classifier-readiness context. Future cleanup should skip these records by
  default and require a separate protected-media policy.

Risk levels should drive future UI badges, dry-run summaries, allowed actions,
and warnings.

## File Deletion Vs Record Deletion

Deleting a media file is different from deleting the MediaAsset record. Deleting
a MediaAsset record is different from deleting MotionEvidence, Event, or Visit
records. Deleting reviewed truth is separate again and should require much
stronger confirmation.

The first cleanup implementation should likely avoid deleting reviewed truth
records. A file-only action may leave provenance and review history intact while
making media unavailable. A record deletion may break references and should be
rarer, more explicit, and better protected.

## Recommended Future Cleanup Actions

Future implementation can consider:

- list saved preview media with linkage and risk summary
- delete unlinked saved preview media files
- detach or delete ignored-evidence media with warning
- archive or mark stale instead of delete
- bulk cleanup only for low-risk/unlinked media
- skip protected records by default

Phase 12F implements only explicit low-risk file deletion. Record deletion,
protected cleanup, and bulk destructive cleanup require separate future scope.

## Current Report API

Implemented in Phase 12D:

```text
GET /api/media/saved-preview-retention
```

Returns:

- `media_asset_id`
- `source_id`
- `stream_id`
- `file_name`
- `content_type`
- `size_bytes`
- `created_at` or `fetched_at`
- `provider_key`
- `provenance`
- `linked_motion_evidence_count`
- `linked_event_count`
- `linked_visit_count`
- `reviewed_truth_count`
- `risk_level`
- `media_state`
- `recommended_action`
- `warnings`

The report is read-only. It performs no URL fetch, media decoding, file
deletion, record deletion, evidence creation, Event/Visit creation, ReviewLabel
creation, export creation, or truth mutation.

## Current Dry-Run API

Implemented in Phase 12D:

```text
POST /api/media/saved-preview-retention/dry-run-cleanup
```

Request:

- `media_asset_ids`: optional list
- `risk_levels`: optional list
- `include_protected`: false by default
- `mode`: `delete_file_only`, `delete_media_asset`, or `archive`

Response:

- affected-item preview
- file/record deletion counts that would apply in a future implementation
- skipped/protected counts
- `warnings`
- `creates_truth`: false
- `deletes_truth`: false

If no filters are supplied, dry-run defaults to low-risk candidates only.
Protected media is skipped unless explicitly included, and even then this route
only reports what a future cleanup might affect.

## Current File-Only Cleanup API

Implemented in Phase 12F:

```text
POST /api/media/{media_asset_id}/cleanup-preview
```

Request:

- `mode`: must be `delete_file_only`
- `confirm`: must be `true`
- `reason`: optional local operator note for the request

The route is intentionally narrow:

- accepts only saved external_url preview MediaAssets
- allows only `risk_level=low` and `media_state=saved_unlinked`
- deletes only the local file after path safety checks
- rejects medium, high, protected, unknown, linked, reviewed, unsafe-path, and
  symlink media
- returns `already_missing` for a missing eligible file
- leaves the MediaAsset record and all product truth unchanged
- returns no absolute filesystem path

## Current UI

Implemented in Phase 12E and extended in Phase 12F, the Saved Media Retention
page shows:

- file size
- safe provenance
- linked evidence, Event, Visit, and review status
- clear risk badge
- dry-run cleanup filters for risk level and protected media
- dry-run totals and per-item skipped/planned effects
- warnings for linked, promoted, or reviewed media
- a confirmed `Delete local file` action only for low-risk `saved_unlinked`
  items
- clear file-only/no-record/no-truth boundary copy

The UI has no bulk cleanup button and no protected-media cleanup. It must never
hide truth implications.

## Dry-Run Cleanup Policy

Cleanup should have dry-run first.

Phase 12D dry-run:

- report files and records that would be affected
- write nothing
- delete nothing
- skip protected reviewed truth by default
- preserve ReviewLabel/Event/Visit truth
- be the first implementation phase before actual delete behavior

## Protected Media Policy

- Reviewed correction media is protected by default.
- Event/Visit representative media is high risk.
- Promoted MotionEvidence media is high risk.
- Pending evidence media is medium risk.
- Unlinked saved preview media is lowest risk.
- Classifier/export readiness can depend on reviewed media-backed corrections.

## Provenance Policy

Cleanup views should show safe provenance. Do not expose raw URL credentials.
Safe host/provenance text is okay if already stored.

Deleting media should not delete Source/provider configuration. Provenance
records may remain even if the file is removed, depending on future design.

## Storage Accounting Policy

- Saved preview media should report size where known.
- Retention report can group by Source/provider.
- Future UI should show total saved preview bytes.
- Storage estimates should not require decoding media.
- Missing file or stale reference should be reported safely.

## Privacy Policy

Saved preview media may contain sensitive outdoor imagery. Storage remains
local-only by default, and users control cleanup.

Privacy and ignore zone semantics should influence evidence/review behavior,
not silently delete files. Future cleanup should support removing sensitive
unreviewed media safely.

## Relationship To MotionEvidence

MotionEvidence may reference saved media via `snapshot_media_asset_id`. Deleting
media can weaken evidence review context even when reviewed truth is unchanged.

Ignored MotionEvidence may be a cleanup candidate. Pending and promoted
MotionEvidence should show warnings. Promotion and correction truth remain
separate from media cleanup.

## Relationship To Analytics, Exports, And Classifier Readiness

Saved preview media is not classifier truth. Reviewed corrections are truth.

Deleting media backing reviewed corrections can affect export/readiness quality,
even when ReviewLabels remain. Future cleanup must warn before affecting
reviewed media-backed examples. DatasetExport records should not be deleted by
media cleanup unless separately designed.

## Testing Expectations For Future Implementation

Future tests should prove:

- retention report classifies unlinked media as low risk
- pending and ignored evidence media as medium risk
- promoted Event/Visit media as high risk
- reviewed correction media as protected
- dry-run deletes nothing
- dry-run skips protected media by default
- stale/missing files are reported safely
- no ReviewLabel/Event/Visit truth deletion
- no DatasetExport deletion
- no model/training dependencies
- no URL fetch required for cleanup
- no secret leakage

Phase 12F cleanup tests add coverage for confirmation, mode rejection, low-risk
file deletion, missing files, linked/protected rejection, unsafe paths, symlink
paths, no record deletion, no truth mutation, no URL fetch, and no detector or
model calls.

## Recommended Future Phases

- Phase 12D: saved media retention report/dry-run API, no deletion.
- Phase 12E: saved media retention UI, dry-run only.
- Phase 12F: low-risk unlinked saved media file cleanup implementation.
- Next likely Phase 12G: cleanup UI polish/audit trail design.
- Alternative next: Phase 13A next provider boundary design.
- Later: protected media/archive policy.

## Explicit Non-Goals

- No actual cleanup implementation in Phase 12D or Phase 12E.
- No medium, high, protected, or unknown-risk cleanup in Phase 12F.
- No record deletion.
- No background cleanup.
- No scheduled cleanup.
- No truth deletion.
- No export deletion.
- No model/training work.
- No live playback/provider changes.
