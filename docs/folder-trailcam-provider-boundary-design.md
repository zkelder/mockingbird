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

## Product Flow

folder/trail-cam Source setup -> explicit folder selection/config metadata ->
explicit dry-run preview -> candidate/skipped file report -> explicit import
action later -> MediaAssets -> optional MotionEvidence or Event/Visit creation
depending on future route -> review/correction -> analytics/exports/classifier
readiness.

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
metadata strings. Phase 13C parses those values only for explicit preview.
`folder_path` is redacted to a configured/not-configured marker in normal
responses.

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

Future import route, not implemented in this phase:

```text
POST /api/sources/{source_id}/folder-import
```

Future behavior:

- explicit user-triggered action
- imports selected or planned files
- creates MediaAssets
- creates reviewable Events/Visits only if a later route explicitly requests and
  designs that behavior
- creates no ReviewLabels or truth
- respects Source, Stream, and optional Zone context
- records safe provenance
- writes only into ignored local data/media paths if copying
- stores references only if an explicit reference-only policy is chosen

## Reference Vs Copy Policy

Two possible modes:

- `reference_only`: keep files in the original folder and store references.
- `copy_to_media_root`: copy files into ignored MockingBird local media storage.

Recommended first implementation: `copy_to_media_root`.

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

Defer:

- videos
- RAW formats
- HEIC
- ZIP archives
- metadata extraction/EXIF parsing
- thumbnails/crops

The first metadata/import pass should not require decoding. Content type may be
inferred conservatively from extension at first; stronger validation can be a
future phase.

## Duplicate Handling

Future import planning should not create duplicate records silently.

- Same file path/import fingerprint should report already imported or skipped.
- Hash-based duplicate detection is useful but can be expensive.
- First pass can use path, size, and modified timestamp if documented.
- Duplicate handling must not delete or clean source files.

## Provenance Policy

Future imported MediaAssets should record safe provenance:

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

- import creates MediaAssets only by default
- no Events/Visits unless explicitly requested
- no ReviewLabels or truth
- duplicate files are skipped or reported
- stale reference behavior is safe
- no model/runtime calls
- no media deletion
- no source files are moved or deleted

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
- Phase 13E: folder import UI polish.
- Later: folder media to MotionEvidence/Event review workflow.

## Explicit Non-Goals

- No import implementation in this phase.
- No watcher.
- No polling.
- No media import.
- No MediaAsset creation.
- No MotionEvidence creation.
- No media deletion.
- No Event/Visit creation.
- No ReviewLabel/truth.
- No live playback.
- No video decoding.
- No model/training work.
