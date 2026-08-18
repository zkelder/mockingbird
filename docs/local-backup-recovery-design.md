# Local Backup and Recovery Design

**Roadmap phase:** 24B — Local Backup and Recovery

**Product flow improved:** protect the local library → verify a backup → restore safely → continue reviewing visits and corrections.

## Why this is next

MockingBird already persists Sources, Streams, Zones, Events, Visits, detections,
review corrections, exports, and managed media locally. Before longer-running
camera, visual-model, or audio work is made durable, that local product history
needs a user-visible recovery path.

This phase extends the existing Local Data page. It does not add a separate
administration surface.

## Backup artifact

A MockingBird backup is a self-contained `.mbbackup` ZIP archive with:

- `manifest.json`, using a versioned format;
- `database.sqlite3`, produced with SQLite's online backup API so WAL-backed
  writes are captured consistently; and
- `media/`, containing regular files from the configured managed-media root.

The manifest records the MockingBird database schema version, creation time,
database and media sizes, file counts, and SHA-256 hashes. It contains no source
credentials beyond information already stored in the user's local database.
API responses never expose backup filesystem paths.

Only SQLite file databases are supported in this phase. In-memory SQLite and
other database engines fail closed with a clear message.

## Safety contract

Backup creation is explicit and local. Archives are written to a temporary file,
verified, and atomically renamed into the ignored backup directory only after all
checks pass. Managed-media symbolic links are rejected so a backup cannot escape
the configured media root.

Verification must complete before restore and checks:

1. the archive has only normalized, non-duplicated member paths;
2. required members and manifest format are valid;
3. all declared sizes and SHA-256 hashes match;
4. the database passes SQLite `quick_check`; and
5. its recorded schema version is compatible with the running app.

Restore is an explicit, confirmed action. Before changing live data, MockingBird:

1. stops process-owned camera sessions and source monitors;
2. creates and verifies an automatic pre-restore safety backup;
3. stages and verifies the selected backup away from live paths; and
4. closes the active database engine.

The staged database and managed-media directory then replace the live pair. If
the restored repository cannot initialize, MockingBird rolls both paths back to
their pre-restore state. A successful restore reopens the repository and leaves
the automatic safety backup available.

The initial restore target is the same MockingBird installation and configured
database/media layout. Restoring an artifact into a differently configured media
root is not promised by this phase; cross-install path migration requires its own
explicit design and tests.

## User workflow

The existing Local Data screen provides:

- **Create backup** — creates and verifies a complete local artifact;
- **Import backup** — copies a chosen artifact into MockingBird's local backup
  library only after verification;
- **Verify** — rechecks an existing artifact without changing product data;
- **Download** — lets the user copy an artifact off-device; and
- **Restore** — uses a two-step confirmation and explains the automatic safety
  backup and temporary camera stop.

Backup listing is read-only. There is no scheduled backup or cloud sync.
Storage & Retention maintenance is a separate, optional local service: it is
disabled by default, shares the backup/restore maintenance window, and skips a
run rather than overlapping a backup or restore.

## Post-restore monitoring hold (implemented, v0.1 Release Hardening v1)

Restore keeps a Stream's `StreamMonitoringPolicy` exactly as backed up --
that policy is restored durable truth, and this contract never rewrites it.
But `ProductRepository.apply_restore_hold()` (called from
`restore_local_backup` immediately after `prepare_for_supervision`)
separately persists `safety_hold_active=True`/`last_stop_reason=
"restore_hold"` on every currently-`armed` Stream's runtime checkpoint. This
is a genuine `RuntimeSafetyHold` (see
[durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md)),
not merely the incidental fact that restore stops the current process's
supervisor: because the hold is a persisted database row,
`DurableMonitoringSupervisor._reconcile_inactive` continues to refuse to
start a held Stream across every subsequent reconciliation pass, including
after the next full application restart -- an armed policy contained in a
restored backup cannot silently resume monitoring. Camera health reports
this plainly ("Monitoring was paused by a recent restore. Resume it here
when you're ready.") without alarming the aggregate Dashboard (the state
stays in the calm/OK bucket -- a deliberate, safe pause is not treated as a
malfunction). The user resumes explicitly through the existing "Retry"
action (`retry_stream_monitoring`, `POST /api/streams/{id}/runtime/retry`)
or by toggling monitoring off and back on -- both already clear
`safety_hold_active` for any reason, restore included.

**Scope note:** this durable-continuity supervisor, and therefore this
hold, applies only to the legacy backend-owned RTSP/local-USB/Windows-
DirectShow live-video path (`StreamMonitoringPolicy`). A paired Camera
Node's Observation Engine session
(`ObservationEngineSessionManager`/"Start observing") has no durable
auto-resume at application startup at all -- `_app_lifespan` starts only
the durable supervisor, never an Observation session, which is always a
fresh, explicit, per-launch user action reached through
`POST /api/streams/{id}/observation/start`. A restore therefore cannot
cause a Camera Node Stream to silently resume monitoring either, but for a
structurally different reason: there is nothing durable there to hold.

## Future durable-runtime coordination (remaining)

Backup creation still does not explicitly quiesce new evidence/media writes
or wait for an in-progress handoff before assembling an archive; it relies
on SQLite's online backup API for database-level write consistency during
capture. Closing this narrower gap (bounded quiesce plus deadline, matching
the restore-hold shape above) remains future work if a real race is ever
demonstrated; see
[durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md).

## Truth and product boundaries

Backup and restore preserve the product graph exactly. They do not create or
reinterpret Events, Visits, DetectionProposals, species suggestions, review
labels, analytics truth, classifier truth, or dataset exports. User corrections
remain the only dataset-grade truth.

The bundle includes the configured managed-media tree so unreferenced but still
locally managed files are not silently omitted. Files outside that root are not
copied or deleted.

Recoverable retention media stays inside that managed-media tree. A complete
backup therefore preserves both the local quarantine and its durable recovery
metadata; restore returns the same recovery window rather than silently
purging it. Automatic retention never runs while backup or restore holds the
local maintenance window.

## Files allowed

- local storage/runtime modules;
- existing Local Data API schemas and routes;
- existing Local Data frontend page, client, types, and focused styles;
- tests; and
- product/roadmap/development documentation.

## Non-goals

- a new admin panel;
- cloud accounts, sync, encryption/key management, or remote storage;
- scheduled backups, workers, polling, or automatic cleanup;
- backup deletion or retention policy;
- camera/audio capture, model inference, or source-provider changes;
- database migration across unsupported schema versions; and
- cross-install media-path rewriting.

## Validation tier

Tier 3 — focused service and API tests, corruption/path-traversal/rollback safety
tests, frontend typecheck/build, full backend suite, production launcher smoke,
and browser validation of create, verify, import, and confirmed restore.
