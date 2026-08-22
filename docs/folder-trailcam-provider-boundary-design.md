# Folder / Trail-cam Provider Boundary Design

## Purpose

The folder/trail-cam provider exists for users who already have outdoor media in
local folders: trail-camera SD-card dumps, NAS folders, exported image batches,
or hand-curated backyard wildlife folders.

This is a real outdoor/wildlife Source path without live camera complexity. It
can feed MockingBird's existing Source, Stream, Zone, review, correction,
analytics, export, and classifier-readiness flow while staying explicit and
local-first.

The provider must not accidentally become a hidden watcher, background import
loop, continuous poller, live playback path, model runner, or media deletion
tool.

Phase 13C adds the source-scoped folder import preview API for
`folder_import_future`. It scans only when the explicit preview route is called,
reports relative candidate/skipped paths, and still does not import files or
create media/evidence/truth.
Phase 13D adds explicit source-scoped folder import to local MediaAssets only.
It copies supported selected/candidate files into MockingBird-managed local
media storage and still creates no MotionEvidence, Events, Visits, labels, or
truth.
Phase 13E exposes those explicit preview/import actions in the Streams page UI.
The backend boundary remains unchanged: preview is dry-run only, and import
creates MediaAssets only.
Phase 13F designs the future explicit handoff from folder-imported MediaAssets
to pending MotionEvidence. It adds no implementation; imported MediaAssets
remain media context, not evidence or truth. See
[folder-import-evidence-handoff-design.md](folder-import-evidence-handoff-design.md).
Phase 13G implements the single-media version of that handoff: one explicit
user action can create one pending MotionEvidence from one folder-imported
MediaAsset. Folder import itself still creates MediaAssets only.
Phase 13H adds a batch evidence handoff dry-run/report for already-imported
folder MediaAssets. It creates no MotionEvidence, Events, Visits, labels, or
truth, and it does not scan folders, import media, decode media, or call model
runtimes.
Phase 13I adds confirmed batch creation of pending MotionEvidence from eligible
folder-imported MediaAssets. It still creates no Events, Visits, labels, or
truth, and it does not scan folders, import media, decode media, or call model
runtimes.
Phase 13J polishes the review/promote UI so folder-imported media evidence has
clear provenance, attached media context, status, and correction truth
boundaries.
Phase 14A adds automated smoke coverage for the implemented folder path:
configured Source/status, explicit preview, explicit MediaAsset-only import,
single and batch pending MotionEvidence handoff, explicit promotion, and
correction truth. See
[source-provider-smoke-flow-hardening.md](source-provider-smoke-flow-hardening.md).
Phase 14B lets dashboard/source status point configured folder Sources toward
explicit folder preview/import. It must not imply live playback, a watcher,
polling, background import, or automatic evidence/truth creation.
Phase 15A includes Folder / trail-cam import in the MVP readiness overview as
explicit preview/import -> MediaAsset -> pending evidence -> review/correction
truth. The overview does not scan folders or create media/evidence.

Offline / Recorded Observation Ingest v1 adds an explicit, separate action
("Analyze imported media") that decodes an already-imported *video*
MediaAsset through the ordinary Observation Engine seam -- the same
detector/tracker/Visit-assembly/admission stack a live Camera Node uses --
producing ordinary needs-review candidate Events/Visits/Evidence. This is
additive to, not a replacement for, the MotionEvidence handoff path above
(which still applies to still images and remains unchanged); a video
MediaAsset can use either path. See
[offline-recorded-media-observation-contract.md](offline-recorded-media-observation-contract.md)
for the full contract -- folder import itself still only ever creates
MediaAssets, never Events/Visits/evidence/truth by itself.

## Product Flow

folder/trail-cam Source setup -> explicit folder selection/config metadata ->
explicit dry-run preview -> candidate/skipped file report -> explicit import ->
MediaAssets -> optional batch evidence dry-run -> optional explicit
single-media or confirmed batch pending MotionEvidence handoff -> explicit
promotion -> review/correction -> analytics/exports/classifier readiness.

## Provider Definition

Recommended canonical provider key: `folder_import_future`.

Recommended display name: Folder / trail-cam import.

This provider is for local folder batch import, SD-card/trail-cam dump review,
NAS folder review, and exported image batches. It is not live playback, a
folder watcher, continuous polling, cloud sync, or a camera-brand-specific
workflow.

Use `folder_import_future` rather than introducing a second
`folder_trailcam_future` key unless a future implementation phase explicitly
scopes a migration. The user-facing display name should carry the trail-cam
language.

## Configuration Fields

Future metadata fields:

- `folder_path`: required, sensitive local path.
- `display_name`: optional user-facing label.
- `recursive`: optional boolean, default `false`.
- `allowed_extensions`: optional list, initially `jpg`, `jpeg`, `png`, `webp`.
- `default_stream_id`: optional related Stream context.
- `default_zone_id`: optional related Zone context.
- `import_mode`: optional future mode such as `media_only` or
  `create_review_visits`.
- `notes`: optional local setup context.

`folder_path` should be treated as sensitive local data and should not be
exposed in API responses or UI. It can be used internally by the explicit
source-scoped preview route. Status/setup/playback routes must not scan folders,
read files, import media, or imply any background watcher.

In Phase 13B, the provider definition is represented in
`GET /api/source-provider-definitions`. Because the current provider field
schema is string-based, `recursive` and `allowed_extensions` are stored as
metadata strings. Phase 13C parses those values for explicit preview; Phase 13D
also uses them for explicit import. `folder_path` is redacted to a
configured/not-configured marker in normal responses.

## Source Connection Status Relationship

Source connection status should treat this provider as import readiness, not
camera connectivity.

- Missing `folder_path` reports `not_configured`.
- Configured folder metadata reports metadata configured/future adapter required.
- Status copy should point to explicit preview/import planning without claiming
  live playback or automatic import.
- `supports_live_playback` remains `false`.
- `supports_zone_editing` can remain `true` for related Stream context.

Connection status must not scan the folder, check the path, inspect media,
create records, or start any provider runtime.

## Stream Playback Relationship

Folder/trail-cam import does not provide live playback. Stream playback remains
placeholder or media-context only.

Phase 13C keeps explicitly configured folder/trail-cam Streams on placeholder
playback with no preview URL, no MediaAsset reference, and no live playback
claim.
Phase 13D folder import can create MediaAssets linked to a Source/Stream, but
it still does not turn folder imports into live playback or change Stream
playback status.

Imported MediaAssets can later provide review context for a Stream. Zone editing
remains useful because users can classify imported media, MotionEvidence, or
reviewable Events/Visits against feeder, birdbath, yard, privacy, or ignore
zones. No status surface should claim a live stream for this provider.

## Import Planning Design

Phase 13C preview route:

```text
POST /api/sources/{source_id}/folder-import/preview
```

The source-scoped route is preferred because folder/trail-cam import should stay
under Source setup and Stream context. A generic `POST /api/folder-import/preview`
route can remain a later helper only if it still requires explicit Source
context.

Behavior:

- explicit user-triggered action
- scans only the configured folder within safe limits
- request may override `recursive`, `allowed_extensions`, `max_files`, and
  `max_depth`
- reports candidate files and skipped files with relative paths only
- estimates candidate count, skipped count, and known bytes
- writes nothing
- creates no MediaAssets, MotionEvidence, Events, Visits, ReviewLabels,
  DatasetExports, SpeciesSuggestions, DetectionProposals, or truth
- performs no media decoding
- does not recurse unless configured
- skips symlink paths
- does not start a watcher or background job

## Import Implementation Design

Phase 13D import route:

```text
POST /api/sources/{source_id}/folder-import
```

Behavior:

- explicit user-triggered action
- imports selected relative paths or current preview candidates
- copies supported files to MockingBird-managed local media storage
- creates MediaAssets only
- creates no MotionEvidence, Events, Visits, ReviewLabels, SpeciesSuggestions,
  DetectionProposals, DatasetExports, or truth
- respects Source, Stream, and optional Zone context
- records safe provenance
- writes only into ignored local data/media paths
- reports already-imported files using safe relative path, size, and modified
  time provenance

## Reference Vs Copy Policy

Two possible modes:

- `reference_only`: keep files in the original folder and store references.
- `copy_to_media_root`: copy files into ignored MockingBird local media storage.

Current implementation: `copy_to_media_root`.

Copying is safer for app-managed storage, retention, repeatable review, and
provenance because MockingBird controls the imported file location after the
explicit import. It can duplicate large files, so preview planning should show
estimated counts and bytes before import.

`reference_only` avoids duplication but risks stale paths, moved SD-card files,
missing NAS mounts, and accidental disclosure of sensitive local paths. It can
be a later explicit mode, not the default.

Both modes must be explicit and local-first. Neither mode may silently copy,
move, or delete source files.

## Supported Media Policy

Initial supported media:

- `image/jpeg`
- `image/png`
- `image/webp`

`video/mp4`, `.mov`, `.avi`, `.mkv`, `.m4v` are supported but opt-in
(`folder_import_preview.SUPPORTED_EXTENSIONS` includes them;
`DEFAULT_ALLOWED_EXTENSIONS` does not, so an existing caller that never
explicitly asks for video extensions keeps its exact original image-only
behavior) -- see "v0.1 Acquisition/Ingest Interoperability Closure v1" in
[roadmap.md](roadmap.md). EXIF capture-timestamp and container
`creation_time` extraction, and content-hash duplicate detection, are
likewise implemented (`mockingbird.source_providers.media_provenance`).

Still deferred:

- RAW formats
- HEIC
- ZIP archives
- thumbnails/crops

The first metadata/import pass does not require decoding beyond the bounded
EXIF/ffprobe metadata reads above. Content type is inferred conservatively
from extension; stronger validation can be a future phase. Folder import
itself still never decodes a video's *frames* -- per-frame decode into the
Observation Engine is a separate, later, explicit action (see "Offline /
Recorded Observation Ingest v1" above).

## Duplicate Handling

Future import planning should not create duplicate records silently.

- Same file path/import fingerprint should report already imported or skipped.
- Hash-based duplicate detection is useful but can be expensive.
- First pass can use path, size, and modified timestamp if documented.
- Duplicate handling must not delete or clean source files.

## Provenance Policy

Imported MediaAssets record safe provenance:

- `provider_key`
- `source_id`
- `stream_id`
- original file name
- safe original relative path or redacted path summary
- `imported_at`
- file size
- modified time if available
- import batch ID if future
- reference/copy mode
- optional user note
- no secrets

Absolute paths should be avoided in normal API/UI responses. If a local path is
needed for support/debug views, it should be explicitly scoped and redacted where
possible.

## Privacy/Ignore Policy

Folder import can include sensitive outdoor media. Import must be explicit, and
users control local folders.

Privacy and ignore zones should affect evidence/review behavior, not silently
delete source files. Future automation must prove privacy/ignore handling before
creating evidence automatically. No cloud upload happens by default.

## Evidence/Event Boundary

Folder import creates MediaAssets at most by default. MediaAssets are local
media context; they are not evidence or truth by themselves.

Optional MotionEvidence creation must be explicit. Optional Event/Visit creation
must be explicit and separately designed. ReviewLabel correction remains truth,
and classifier/export readiness depends on reviewed corrections.

The folder-import evidence handoff design defines the path:
folder-imported MediaAsset -> explicit pending MotionEvidence -> explicit
promotion -> Event/Visit review -> correction truth. Folder import itself still
does not create evidence or truth.

Phase 13G implements the single MediaAsset -> pending MotionEvidence handoff
through the shared media evidence route. It remains explicit, one item at a
time, and still creates no Event, Visit, ReviewLabel, or truth.

## Storage/Retention Boundary

Folder imports can create many files. Import preview should estimate counts and
bytes before any import.

Copy mode should use ignored local media paths. Reference mode must handle stale
files safely. Retention report and cleanup concepts should apply to copied
folder media only after separate design. Folder import must never delete original
folder files.

## Security/Path Safety Boundary

Folder paths are sensitive local data.

Future implementation must avoid path traversal, importing outside the selected
folder, symlink traversal unless explicitly designed, recursion by default, and
casual absolute path exposure. NAS and mounted folders need careful stale-path
and permission handling.

## UI Design

Future UI should provide:

- Source setup provider: Folder / trail-cam import
- configured folder path with safe/redacted display
- preview import button
- candidate count, skipped count, and estimated bytes
- explicit import button
- import results with MediaAsset links
- clear copy that no labels or truth were created
- links to MotionEvidence/manual review paths

The UI should not imply live playback, continuous watching, automatic import, or
camera-brand-specific behavior.

Phase 13E implements the first compact UI surface for this contract on the
Streams page. It previews candidates/skips on request, imports previewed
relative paths as MediaAssets on request, hides the raw folder path, and keeps
MotionEvidence/Event/Visit/review truth as a later explicit handoff.
Phase 13J makes that later handoff easier to review: Motion Evidence and
promoted Event/Visit detail can show folder-imported media provenance while
correction remains truth.

## Testing Expectations

Preview tests should prove:

- missing `folder_path` reports `not_configured`
- preview scans only within the allowed folder
- no symlink or path traversal
- `recursive=false` does not scan subfolders
- unsupported extensions are skipped
- preview writes no files or records
- preview returns relative paths only and redacts the configured root path
- status/setup/playback routes do not scan folders

Future import tests should prove:

- import creates MediaAssets only
- no MotionEvidence
- no Events/Visits
- no ReviewLabels or truth
- duplicate files are skipped or reported
- no model/runtime calls
- no media deletion
- no source files are moved or deleted
- copied files are under ignored local media storage

## Relationship To Existing Manual Media Import

Manual import is user-selected file upload/import. Folder/trail-cam import is a
batch/source-level import path.

Both should feed MediaAssets and review flows. Neither creates truth without
correction. Folder/trail-cam import can reuse manual import concepts, but it
must not be framed as the whole product.

## Relationship To External URL Provider

`external_url` fetches one still-image preview explicitly. Folder/trail-cam
imports local batch media explicitly.

Both produce MediaAssets before evidence/review, avoid live playback and workers
initially, and must preserve retention, provenance, and truth boundaries.

## Recommended Future Phases

- Phase 13B: folder/trail-cam provider configuration UI/status contract.
- Phase 13C: folder import preview API, dry-run only.
- Phase 13D: folder import implementation to MediaAssets only.
- Phase 13E: folder import UI preview/import.
- Phase 13F: folder media to MotionEvidence handoff design.
- Phase 13G: single folder-imported MediaAsset to pending MotionEvidence, no
  Event/Visit/truth.
- Phase 13H: batch folder media evidence handoff dry-run.
- Phase 13I: batch folder media evidence creation, pending MotionEvidence only.
- Phase 13J: folder media review/promote UI polish.
- Phase 14A: consolidated provider smoke coverage with `external_url`.
- Next likely: Phase 13K folder import retention/report design, Phase 14B
  source/provider status polish, or Phase 14C next provider boundary decision.

## Explicit Non-Goals

- No watcher.
- No polling.
- No automatic MotionEvidence creation.
- No media deletion.
- No Event/Visit creation.
- No ReviewLabel/truth.
- No live playback.
- No video decoding (still true of folder import itself; per-frame video
  decode is a separate, later, explicit action -- see "Offline / Recorded
  Observation Ingest v1" above).
- No model/training work.
