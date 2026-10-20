# Orphan Media Integrity & Recovery v1 -- Contract

Milestone 3 of the locked pre-1.0 queue. Closes the **file -> database**
direction of media integrity. It does not replace or modify the accepted
database -> file checks (Doctor's media-integrity sample, storage summary,
backup verification) or the accepted retention/recovery machinery.

Invariant: every managed media artifact either has a valid authoritative
owner, is a recognized temporary/system artifact, or is explicitly reported as
orphaned. Orphaned means *reported*, never *deleted*.

Implementation: [`mockingbird.storage.orphan_media`](../src/mockingbird/storage/orphan_media.py).
Surfaces: `POST /api/settings/storage-retention/orphan-media/{scan,quarantine}`,
`GET .../quarantine-history`, `POST .../quarantine-history/{batch_id}/restore`;
CLI `python -m mockingbird storage-integrity`; Local Data -> Storage &
Retention -> "Storage integrity".

## 1. Managed root

The only walked location is the configured `media_root`
(`MOCKINGBIRD_MEDIA_ROOT`, default `<home>/data/media/imports`). Evidence from
the repository:

- every real media write (`_write_media_file`/`_copy_media_file`, folder/manual
  import, Camera Node ingest, acoustic assets, external URL saves) stores
  `self.media_root / filename`;
- subdirectories actually created under it: `property-map/` (Yard Map
  background), `.recovery/` (retention staging), `audio_capture/<stream>/`
  (transient raw microphone segments), and this milestone's `.orphan-quarantine/`;
- *not* under it: the database, backups, research/classifier/ecological export
  roots, the Camera Node transport ledger, model caches. Those are out of scope.

## 2. Authoritative owners

A stored value claims a file. The complete set is read from:

| Source | Column |
| --- | --- |
| `media_assets` | `local_path` (all rows, any state) |
| `visits` | `representative_media_path` (legacy owner; some paths set it without a MediaAsset row) |
| `yard_maps` | `background_relative_path` |
| `storage_cleanup_items` | `original_local_path` while the item is not `restored`/`purged` (a pending restore target) |

Duplicate references to one file are legal (a Visit and its MediaAsset share a
path); ownership is a set. Values that are not filesystem references
(`demo://...`, empty, NUL-bearing) are counted, not resolved. Absolute values
outside the managed root claim nothing inside it (counted as
`references_outside_root`).

**Path resolution is lexical and ambiguity resolves toward "owned".** The
repository stores `media_root / filename`, which is cwd-relative when
`media_root` is, and older rows may be `media_root`-relative (the same
two-reading convention as `_storage_managed_media_path`). A relative value
claims *both* readings that fall inside the root. `..` is collapsed lexically
before the containment check, so a value that escapes the root claims nothing
inside it, and one that resolves back inside it correctly owns the file.

## 3. Exclusions (explicit rules)

Never classified as orphan media:

- top-level `.recovery/` (owned by retention's `StorageCleanupItem` rows),
  `.orphan-quarantine/` (this module's own manifests), `audio_capture/`
  (transient working segments the acoustic runtime deletes after copying);
- temporary artifacts: `*.tmp`, `*.part`, `.mockingbird-write-check-*`
  (temp files older than 24h are *counted* as `stale_temporary_count` for the
  operator, still never an orphan and never moved);
- system files: `.DS_Store`, `Thumbs.db`, `desktop.ini`;
- **recently written files** (mtime within 15 minutes). `_write_media_file`
  writes bytes before the owning row commits, so a young unowned file is
  "possibly mid-write". Such files are reported as `recently_written_count`
  and are never orphans and never movable.

## 4. Symlinks and traversal

Symlinks (file or directory) and special files inside the root are **never
followed** and never orphan candidates. They are reported as
`unsafe_entry` and left untouched; they do not make the scan incomplete. A
symlinked `media_root` (or quarantine root) is unsafe: the scan is
`incomplete(media_root_unsafe)` and quarantine refuses -- matching backup's
existing refusal. Requested quarantine paths must be managed-relative POSIX
paths: absolute paths, drive letters, backslashes, NUL, `.`/`..` segments and
excluded top-level directories are rejected as `unsafe_path`, and every
path component is re-checked for symlinks before any move.

## 5. Scan algorithm and completeness

1. Walk the filesystem (iterative `scandir`, no media bytes read, no symlink
   following), collecting `(relative path, size, mtime_ns)`.
2. *Then* read the complete owner set (streamed in chunks).
3. Classify: excluded artifact -> owned -> recently written -> **unowned**.

Walk-before-owners is deliberate: a file written and committed during the walk
is either unseen or owned; the only remaining window (bytes on disk before the
commit) is the recent-write grace.

Statuses: `clean`, `orphans_found`, `incomplete`. **Incomplete is never
clean**: unreadable directory/file, database unreadable (any query failure),
unsafe root, or exceeding the file bound (2,000,000) yields `incomplete` with
`incomplete_reasons` and **no orphan claim at all**. A missing `media_root` is
`clean` (nothing was ever written). Findings are sorted by relative path,
bounded to 200 (`findings_truncated`), counts are always totals. A scan writes
nothing, creates no directory, and creates no review truth.

## 6. Quarantine (implemented, bounded)

Existing retention recovery is keyed to `MediaAsset` rows (`StorageCleanupItem`
has a non-null `media_asset_id`), so orphans cannot reuse it. Quarantine needs
no schema change: a sidecar manifest on the managed filesystem carries the
restore/audit metadata, and **no database row is created, changed, or removed**
(an orphan is by definition not in the database).

- Explicit action only (`confirm: true` / `--yes`); 1-200 paths per request.
- The server performs its own revalidation -- it never trusts the caller's
  list: a fresh *complete* scan must still list each path as unowned; ownership
  is reloaded again immediately before the moves; each file's size and
  mtime must still match that scan. Skip reasons: `not_unowned`, `now_owned`,
  `already_missing`, `unsafe_path`; failure codes: `changed_since_scan`,
  `symlink_path`, `not_a_regular_file`, `destination_exists`, `move_failed`.
  An incomplete scan refuses the entire request.
- Destination: `<media_root>/.orphan-quarantine/<batch_id>/<original relative
  path>`, inside managed storage (and therefore inside backups). The batch
  directory is newly created (`exist_ok=False`, retried on id collision); the
  move is hard-link-then-unlink (never overwrites), falling back to
  exists-check + atomic rename; two live copies are never left behind.
- `manifest.json` is written before moving (`planned`) and after every item
  (`moved`/`failed`/`skipped`), atomically. It holds portable relative paths,
  size, mtime, SHA-256 (audit only; hashing happens at quarantine time, never
  during a scan), and state -- no absolute paths.
- Result `status`: `completed` only if every attempted item moved;
  `partial`/`failed` otherwise; the response and UI say so. Interrupted
  batches leave `planned` items that restore ignores safely.
- **Restore** moves `moved` items back to their original relative path, never
  overwriting: if something now occupies the name the item is a reported
  conflict and the quarantined copy is retained.
- **Deliberately absent:** purge/deletion of quarantined orphans. Deletion is
  not the recovery policy; an operator removes the folder manually if wanted.

## 7. Interactions

- **Retention:** `.recovery/` is excluded; a retention-staged asset still has
  its row, so it is owned. The routes take the same maintenance lock as backup,
  restore and cleanup, so a scan/move cannot overlap them.
- **Backup/restore:** quarantine lives under `media_root`, so backups include
  it and restore reinstates it; restore's media-root replacement is blocked by
  the shared lock while a scan or move runs.
- **Demo data:** `demo://` values are non-file references. Demo reset deletes
  rows but keeps files (existing behavior), so those files correctly surface as
  unowned and recoverable.
- **Imports / Camera Node ingest:** both land as MediaAssets; the recent-write
  grace covers the bytes-before-commit window. Offline-media provenance and
  monitoring-exposure accounting are untouched.
- **Exports:** export roots are outside `media_root` and not scanned.

## 8. Surfaces

Normal users see: "Storage integrity", *No unowned media found* /
*Unowned media found: N* / *Check could not finish*, "Review recovery
options" (two-step confirm), and a recovery list with "Move back". API
responses carry managed-relative paths and counts, never the absolute root;
raw reason codes sit behind a "Details" disclosure. The admin routes are
`administrator` tier. Not added to Doctor or Product Health (Doctor's
millisecond budget; no storage-management dashboard).

## 9. Bounded remaining limitations

- Stale `.tmp`/`.part` files are counted, never reported as orphans or moved.
- A `media_root` that is itself a symlink is refused rather than supported.
- Recent-write grace is time-based; a file legitimately older than 15 minutes
  whose owning commit is still pending would be a (revalidated) candidate --
  not reachable by current write paths.
- Quarantined orphans are never purged by the product.
- Windows case-insensitivity is handled by `normcase`; not exercised on Windows
  in this milestone (no hardware/OS validation was required).
