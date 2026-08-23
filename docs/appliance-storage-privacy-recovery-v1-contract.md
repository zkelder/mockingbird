# Appliance / Storage / Privacy / Recovery v1 Contract

**Roadmap phase:** Phase 4 -- Install / Recovery / Appliance Experience
("storage management as product-managed behavior rather than developer
tooling," named as still-`Remains` in [roadmap.md](roadmap.md)).

**Product flow improved:** a working MockingBird installation running for
weeks/months can answer, without SSH or database archaeology: is it
healthy, how much storage is it using, what happens as storage fills up,
what evidence is retained and why, can it be backed up and recovered, can
hardware be replaced without losing history, and what leaves the machine.

**Why this is next:** Phase A archaeology (see
[appliance-storage-privacy-recovery-v1-findings.md](appliance-storage-privacy-recovery-v1-findings.md))
found this installation already has substantially more appliance maturity
than a cold read of the milestone brief implied -- a full verified backup/
restore system, a disabled-by-default recoverable storage-retention
quarantine system, a 15-check Doctor, and an honestly-documented Privacy
Zone contract. This milestone is therefore reconciliation and gap-closing
against that existing foundation, with one genuine greenfield deliverable:
the remote-transport host-file consumer lifecycle (Phase E), a standing gap
explicitly named in the milestone brief itself.

## Storage accounting (Phase B)

`ProductRepository.storage_summary()` (`StorageSummary`, `GET
/api/settings/storage-retention/summary` and embedded in `/api/product/
health`) is the one canonical view. Accounted categories: database
(`approximate_database_bytes`), managed media total, active/superseded/
orphaned/unresolved/reviewed-wildlife/reviewed-other media, and (new this
milestone) `linked_evidence_or_analysis` -- see "Retention contract,"
below. Host disk total/free/writability is a separate, already-existing
fact on the same response (`disk_total_bytes`/`disk_free_bytes`/
`is_writable`), reused rather than re-derived from managed-media
accounting.

Categories intentionally *not* separately broken out, with the honest
reason:

- **Video/audio/thumbnail sub-breakdown of managed media**: not built.
  Managed media is currently one pool; splitting it by `media_type` would
  be a bounded future addition if a real need appears, not fabricated here
  from "the milestone brief listed it" alone.
- **Thumbnails/derived-media as a distinct category**: confirmed there are
  no persisted thumbnail artifacts in the live product runtime today (only
  an in-memory PIL resize used for scoring, and an offline dev tool that
  never opens the product database) -- reported honestly as not applicable
  rather than inventing an empty category.
- **Temporary/working media**: acoustic working segments are the one real
  instance (`MediaAssetModel.acoustic_working_segment`), already covered by
  their own dedicated, already-working retention sweep (see "Retention
  contract"). Backup/restore temporary artifacts are covered separately
  under "Backup contract."
- **Camera Node/remote-transport completed host files** and **transport
  partial files**: now accounted for via Doctor's new host-side scan (see
  "Remote transport consumer," below) -- deliberately a Doctor-surfaced
  fact, not folded into `StorageSummary` itself, since it is a filesystem
  category orthogonal to `MediaAssetModel` accounting (a transport item is
  either not yet a MediaAsset, or already one and no longer transport
  state at all).
- **Logs**: already self-bounding (`RotatingFileHandler`, 5 MB x 3 backups,
  confirmed ~464 KB on a real, actively-used checkout) -- not a growth
  risk, not separately surfaced.
- **Backups**: `data/backups/` is user-visible via the existing Local Data
  backup library listing (file sizes per backup already shown); not
  duplicated into `StorageSummary`.

**Cost discipline**: `storage_summary()` was a full `MediaAssetModel`-table
scan with several queries per row -- exactly the "expensive scan on every
page load" this milestone wants avoided, since `/api/product/health` calls
it on every Dashboard mount. Fixed with a short (30s) in-process TTL cache
plus explicit invalidation at the points that already exist for this exact
purpose (`_sync_storage_alert`, called after every cleanup/restore/purge/
settings-update) and at the transport consumer's own successful-ingestion
point -- not a SQL-aggregate rewrite of the underlying, well-tested (~20
existing tests) per-asset classification logic, which stays byte-identical.
No eligibility/cleanup decision is ever served from this cache: `_storage_
retention_evaluation` (used by preview/execute) always recomputes fresh,
immediately before a destructive action.

**Missing/inaccessible paths**: already handled safely before this
milestone -- `_storage_managed_media_path` returns `None` for an asset
whose file cannot be resolved, and the scan skips it rather than raising.

**No double-counting**: enforced structurally -- each `MediaAssetModel` row
is classified into exactly one mutually-exclusive category per the
existing `if/elif` ladder (now including the new `linked_evidence_or_
analysis` branch), and the transport-ledger accounting (Doctor's new scan)
counts only files still present in `completed/`, which by construction
never overlaps `MediaAssetModel` rows (a transport item's blob is deleted
in the same operation that creates its corresponding MediaAsset row -- see
"Remote transport consumer").

## Low-space behavior (Phase C)

`storage.database.LocalStorageDiskStatus.storage_health_tier` is a new,
graduated `healthy` / `getting_low` / `action_recommended` / `critical`
ladder (additive; `is_low_space` keeps its exact existing meaning and
trigger point -- `action_recommended`-or-worse -- so no existing caller's
behavior changed). Thresholds (disclosed judgment calls, matching
`BACKUP_STALE_AFTER_DAYS`'s own precedent -- no prior canonical policy
existed for either new tier):

| Tier | Free bytes | Free ratio |
| --- | --- | --- |
| `healthy` | \>= 5 GB | \>= 15% |
| `getting_low` | \< 5 GB or \< 15% | |
| `action_recommended` (existing threshold, unchanged) | \< 1 GB or \< 5% | |
| `critical` | \< 200 MB or \< 1% | |

Surfaced on `StorageSummary.storage_health_tier`, `ProductHealthStatus.
storage_health_tier`, and Doctor's Storage check (a distinct, more urgent
"critically low -- new evidence may soon fail to save" message at
`critical`, still `WARN`/`DEGRADED` never `BLOCKING` -- the install can
still write; `FAIL`/`BLOCKING` remains reserved for the storage root being
missing or genuinely unwritable, matching Doctor's own existing severity
doctrine). `getting_low` is a calm, informational early notice.

Existing monitoring cannot itself corrupt data from a low-space condition:
capture/write paths already fail closed (an `OSError` on write is not
silently swallowed anywhere in the media-write paths touched by this
milestone). No new "critical" auto-cleanup was built -- the milestone
brief explicitly warns against inventing a storage optimizer or silently
purging authoritative evidence; the tiered warning gives the user
information and time, not an automatic destructive action.

## Retention contract (Phase D)

Reconciled, not rebuilt -- ~20 existing tests already proved most of this
before this milestone:

1. **Authoritative/reviewed evidence** (`active_visit_primary_evidence`,
   `reviewed_bird_wildlife_evidence` when the setting is on): protected
   forever by default.
2. **Unresolved candidate evidence** (`unresolved_visit_evidence`):
   protected forever, not user-configurable to relax (a deliberate product
   protection, not an operator tradeoff -- `retain_unresolved_visit_
   evidence` is accepted but always coerced `true`).
3. **Rejected/non-wildlife evidence where retained** -- two distinct
   sub-cases: (a) `reviewed_non_bird_secondary`/`reviewed_bird_wildlife_
   secondary` (a *secondary*, non-primary frame on an already-reviewed
   Visit) already ages out after `reviewed_non_bird_age_days` (default 180
   days); (b) `linked_evidence_or_analysis` -- a file referenced only by a
   rejected/suppressed detection/analysis record, *never* linked to any
   Visit at all -- was previously protected forever with **no lever and no
   visibility in `StorageSummary` at all** (a real P0 finding: unbounded,
   invisible growth). This milestone adds both: visibility (`StorageSummary.
   linked_evidence_or_analysis_count`/`_bytes`) and one new, opt-in,
   default-`None`-(protected-forever) age lever (`StorageRetentionSettings.
   rejected_analysis_media_age_days`, schema 49) -- every existing
   installation's behavior is unchanged until a user explicitly configures
   it.
4. **Temporary runtime media** -- acoustic working segments
   (`MediaAssetModel.acoustic_working_segment`): already a real, working,
   independently-gated TTL sweep (`run_working_audio_retention_sweep`),
   file-then-row deletion, deliberately not gated by `automatic_cleanup_
   enabled` (a temp file, not evidence). Now also the deliberate model for
   the transport-consumer cleanup ordering (see below).
5. **Imported originals**: subject to the same active/superseded/reviewed
   rules as any other Visit-linked evidence -- no separate contract; this
   is confirmed intentional simplicity (Phase D explicitly wants "a small
   number of meaningful retention choices," not a rule per acquisition
   path), not an oversight.
6. **Derived thumbnails/previews**: not applicable today (see "Storage
   accounting," above) -- `derived_media_reference`/`crop_revision_history`
   remain protected categories for the one real derived-asset shape that
   does exist (activity/refined crops).
7. **Acoustic working segments**: see (4).
8. **Remote-transport delivery artifacts**: see "Remote transport
   consumer," below -- a distinct lifecycle from `MediaAssetModel`
   accounting entirely (a transport item is either not yet evidence, or
   already converted and no longer a transport artifact).

**What cleanup never touches automatically**: reviewed truth
(`ReviewLabel`s), Visit/Event/Observation records, export manifests
(`DatasetExportModel`), backups (explicit non-goal, confirmed intentional
in `local-backup-recovery-design.md`), and any category this document
marks protected-by-default. Cleanup execution remains file-move-to-a-
14-day-recoverable-quarantine-first, never delete-then-fail-orphaned
(unchanged from the existing, already-tested contract).

## Remote transport consumer (Phase E)

**Before this milestone**: a transport item's lifecycle had exactly two
states, `in_progress`/`completed` (`TransportLedger`). Reaching `completed`
was a dead end -- nothing read it back, and the Camera Node deletes its own
spooled copy immediately on ack, making the host's `completed/` blob the
*sole* surviving copy of that evidence with no consumer and no cleanup.
This was the milestone's own explicitly named standing gap.

**Closed this milestone.** New durable, idempotent state (schema 49 -- see
below) plus:

- `TransportLedger` gained `list_node_ids`/`list_completed_item_ids`/
  `completed_item_metadata`/`completed_blob_path`/`delete_completed_item` --
  pure filesystem operations, no new dependency, matching the module's
  existing "no SQL, no HTTP" design boundary.
- `ProductRepository.resolve_camera_node_source_id_for_node(node_id)` maps
  a transport item's `node_id` back to its owning Source, checking the
  *current* `node_id` first and falling back to `camera_node_prior_node_id`
  (Camera Node Reprovision / Replacement Recovery v1) -- so a completed-
  but-unconsumed item surviving a hardware replacement still attributes
  correctly to the same logical Source/Stream/history, exactly as that
  prior milestone's own doctrine requires. Bounded to the single most
  recent prior identity, matching that column's own documented scope.
- `ProductRepository.consume_camera_node_transport_item(node_id, item_id)`
  reuses the *existing* Source Folder Import hash/dedup/provenance/
  MediaAsset-construction contract (not a new, second Evidence/Observation
  authority path) to turn one completed item into a `MediaAssetModel` row,
  then cleans up the ledger's blob. Content-hash dedup first (an item
  already imported through another path, or re-processed by a retried
  sweep, never creates a second MediaAsset). An unrecognized wire media
  type, a missing blob, or an unattributable `node_id` all fail the item
  into a retried `status="failed"` row rather than ever promoting
  incomplete/uninterpretable content as evidence.
- **Two-phase commit ordering is the whole safety property**: phase 1
  commits the MediaAsset + ingestion row to the database *without ever
  touching the transport ledger's filesystem*; phase 2 deletes the ledger's
  completed blob only *after* that commit is durable. A process killed
  between the two phases leaves a row with `status="ingested"` and
  `blob_deleted_at IS NULL` -- the next call for the same `(node_id,
  item_id)` sees that state and only finishes the delete, never
  re-ingesting. This is why cleanup can never delete unconsumed data: the
  blob is only ever removed after the product has durably recorded what it
  means.
- **Wired synchronously**: `POST .../complete`'s router now takes an
  `on_item_completed(node_id, item_id)` callback (`None` by default,
  preserving every existing router test's behavior unchanged), invoked
  right after the ledger durably completes the item, best-effort (any
  exception is logged, never surfaced to the Node -- the Node has already
  deleted its own copy the instant it sees the 200 response, so a
  consumption failure must be recovered by the host's own later sweep,
  never by asking the Node to resend bytes it no longer has).
- **Restart-safe sweep**: `consume_pending_camera_node_transport_backlog()`
  runs once at application startup (mirroring the existing durable-
  supervisor startup-reconciliation precedent), bounded (500 items/call),
  cheap when nothing is pending (a bounded set of directory listings).
- **Doctor visibility**: the existing Camera Node Transport check now also
  reports host-side unconsumed backlog (count/bytes/oldest-age across every
  node's `completed/` directory, regardless of current Source
  configuration -- so an unattributed item is never silently invisible
  just because no Source currently claims its `node_id`), `WARN`ing only
  when something has sat unconsumed for over an hour (consumption is
  normally synchronous/immediate, so that long a wait means genuinely
  stuck, not merely pending).

**No orphaned indefinitely-growing directory**: every completed item is
either consumed-and-deleted promptly, or retried indefinitely with Doctor
visibility -- never silently accumulating with no signal.

## Backup contract (Phase F)

Mechanism confirmed genuinely solid, no P0: full, unselective physical
copy (SQLite online-backup API + managed-media tree) in a verified
`.mbbackup` ZIP; built under a hidden temp name, independently re-verified
(hash + `PRAGMA quick_check` + schema check), only atomically promoted
after verification passes. **Scope**: DB/config, reviewed truth, source/
camera config, taxonomy/user corrections, research collections, retained
evidence/media, and (being DB-resident) transport-ingestion/acoustic-queue
pending state are all included automatically, since they live in the one
physical file that gets copied wholesale. Privacy settings (Zone
`zone_type`) are ordinary DB rows, included the same way. **Not included**:
files outside the configured `media_root` (external-reference provider
configs preserved as references only, never copied), and
`classifier_manifest_export_root` (a separate, regenerable export tree,
disclosed here as a low-severity scope gap rather than fixed).

**Fixed this milestone** (all four are trust-signal/diagnosability issues,
not correctness bugs -- the mechanism itself never mislabeled a partial
backup successful):

1. `last_backup_verified` was **structurally always `False`** --
   `list_backups()` hardcoded `"not_checked"` even seconds after `create_
   backup`'s own internal, real, full verification succeeded. Fixed with a
   small sidecar marker (`<backup_id>.verified.json`, written once inside
   `verify_archive()` -- the single function every create/import/explicit-
   verify path funnels through -- so it applies uniformly with no
   re-hashing cost on ordinary `list_backups()` calls, preserving Doctor's
   own disclosed "prefer the cheap check" precedent).
2. 37 distinct internal failure codes collapsed into one generic HTTP
   message. Fixed: the specific code now always appears in the response
   `detail` (e.g. "Backup verification failed (backup_database_hash_
   mismatch). No product data was changed."), for every one of the three
   generic-message branches.
3. A hard process kill during `create_backup`/`import_backup` left an
   orphaned `.creating-*`/`.import-*` temp file that `list_backups()`'s own
   glob (`Path.glob`, unlike `glob.glob()`, does not exclude dotfiles)
   picked up, failed to parse, and counted as "unreadable" forever, with no
   distinction from a genuinely corrupted real backup. Fixed:
   `list_backups()` now recognizes and excludes the five known temporary-
   artifact name patterns from both counts entirely, and a new
   `cleanup_orphaned_temporary_artifacts()` (age-gated, 1 hour -- far
   longer than any real operation takes, so it can never race a genuinely
   in-progress one) reclaims the disk space, called once at application
   startup.
4. `replace_live_files`'s three-sequential-`os.replace` live swap had no
   on-disk transaction marker -- a raised Python exception mid-swap was
   already well-handled (`RestoreFileTransaction.rollback()`), but a hard
   process kill between two of the `os.replace` calls was not detectable at
   all. Fixed with a restore-in-progress sentinel (written before the first
   mutation, cleared only after the last succeeds *or* after a triggered
   rollback genuinely completes) -- see "Recovery," below.

**Compatibility metadata**: `BACKUP_FORMAT_VERSION` (already enforced at
read/restore time) is now also surfaced on `/api/product/health` and
Doctor's Application check, alongside the already-solid `database_schema_
version`/`git_commit`/`build_id` -- see "Compatibility" below.

## Recovery / restore validation (Phase G)

Two-phase confirmed transactional restore (plan -> execute with an
automatic pre-restore safety backup, runtime stop, atomic swap, rollback-
on-exception) confirmed already solid and real-tested, including a genuine
cross-install `rebind_managed_storage` path (not aspirational -- proven by
`tests/test_cross_install_backup_restore.py`'s dry-run/rebind/Windows-
path-identity/missing-archive-identity/symlink-rejection tests, all
passing before this milestone). Unsupported/newer backup format, missing
media, and a raised-exception-mid-restore were all already provably safe
(`assert_restore_compatible`, member/hash validation before any live file
is touched, `RestoreFileTransaction.rollback()`).

**Closed this milestone**: the one real gap -- a hard process kill (not a
raised exception) between two of `replace_live_files`'s several `os.
replace` calls was previously undetectable. The new sentinel (see "Backup
contract" #4) is written before the first live-file mutation and read by
Doctor's Backup check (`LocalBackupManager.detect_interrupted_restore()`,
a plain, side-effect-free file read -- no repository, matching every other
Doctor free-function) as a distinct, more urgent signal than ordinary
backup staleness: *"A previous restore did not finish... Nothing was
deleted -- the files from just before the restore are still on disk."*
Verified via two injected-failure tests: one where the subsequent rollback
succeeds (sentinel correctly clears -- the common recoverable case) and one
where rollback itself also fails (sentinel correctly survives, carrying the
recorded rollback paths a support conversation would need -- the
genuinely-unrecoverable case, which must never read as a silent, ordinary
healthy install).

**Original backup artifact remains intact** in every path: restore only
ever opens the `.mbbackup` archive in read mode.

## Host-machine replacement readiness (Phase H)

Durable identity assumptions confirmed:

- **Source/Camera IDs**: primary keys, never regenerated by backup/restore
  or by rebinding managed storage.
- **Reviewed Observations/evidence relationships**: restored as ordinary DB
  rows; `rebind_managed_storage` rewrites only managed-media *path* columns,
  never row identities, and explicitly asserts `source_provider_
  configurations` is byte-identical before/after.
- **Camera Node pairings/credentials**: DB-resident (`node_credential`/
  `node_transport_credential` inside `source_provider_configurations.
  config_json`) and therefore restored *as data* onto a new host machine --
  a Camera Node whose physical hardware is unchanged will still
  authenticate against a restored backup on new host hardware, since these
  are compared values, not host-machine-bound secrets. **Deliberately not**
  re-derived or invalidated by a host move by itself.
- **Configuration/retention/privacy policy**: ordinary DB rows, restored
  automatically.

**What is not safely portable, and the required repair path**: nothing
host-machine-local is deliberately excluded from backup today (unlike
Camera Node secrets, which are Node-local files -- see "Camera Node
replacement," below) -- the open question for a genuine host move is
whether the *same physical Camera Node* can still reach the *new* host
machine's network address/port, which is an infrastructure/networking fact
outside this product's own control. If the Node cannot reach the new host
at all, the existing Guided Camera Editing repair-pairing flow (same
`node_id`, no confirmation needed) is the documented, already-built repair
path -- no new mechanism required. A genuine hardware failure on the
Camera Node side during the same window is the separate "Camera Node
replacement" case below, not conflated with a host move.

## Camera Node replacement/recovery closure (Phase I)

Built on the already-accepted Camera Node Reprovision / Replacement
Recovery v1 foundation (config export/import, `node_id`-match guard with an
explicit `confirm_node_identity_change` override, provenance columns,
Doctor's 7-day post-replacement Zones-review reminder). Bounded gaps
closed this milestone:

1. **Credential revocation was incomplete.** `revoke_camera_node_pairing`
   (the ordinary, non-replacement manual revoke action) popped
   `node_credential` but never `node_transport_credential` --
   `resolve_camera_node_transport_source` matches on the credential value
   alone and never checked `node_pairing_state`, so a revoked Node's
   transport credential kept working indefinitely. Fixed: revoke now pops
   both keys, and `resolve_camera_node_transport_source` gained an
   independent defense-in-depth check against `node_pairing_state ==
   "revoked"`. (Confirmed replacement's own existing full-config-overwrite
   already orphaned the old credential correctly -- this fix was
   specifically for the separate ordinary-revoke path.)
2. **Pending transport backlog at replacement time was neither drained nor
   disclosed.** Fixed: the replacement preview now reads the old node's
   last-known self-reported backlog (the same fact Doctor's own transport
   check already reads -- no new drain mechanism, no new network call) and
   discloses it plainly when non-zero: *"The previous Node last reported N
   item(s) still waiting to be delivered -- these will not be deliverable
   once you confirm this replacement."*
3. **Old-node-reconnect-after-replacement was untested.** The actual
   behavior (a 401 via the now-orphaned credential) was already correct,
   but only incidentally -- confirmed by a new regression test
   (`test_old_node_transport_credential_stops_resolving_after_a_config_
   overwrite`) locking in that a config overwrite (which replacement always
   performs) makes the old credential stop resolving while the new one
   resolves correctly.

Camera/Source logical history preservation and post-replacement
diagnostics were already fully built and tested; not reopened.

## Privacy contract (Phase J)

Masking enforcement re-verified, not rebuilt: pixel-level, pre-inference,
in three independent code paths (ONNX detector, live object-detector
monitoring frame, MOG2 motion tracker), with real repository-layer defense
in depth (10+ distinct guard sites) refusing a privacy/ignore-zone-only
candidate before any MediaAsset write. Fresh code-tracing this milestone
found **no** live path -- across live capture, offline import, webhook
ingestion, same-frame classifier evidence, or multimodal/cross-camera
association -- where content whose only location is inside a Privacy/
Ignore Zone becomes an ordinary detection, track, Visit, Observation,
review-queue item, or export row. The product's own documented limitation
(a legitimately-triggered-elsewhere frame can still visually contain
Privacy Zone pixels -- see
[privacy-ignore-zone-contract.md](privacy-ignore-zone-contract.md)) remains
accurate and was not weakened or strengthened.

**One real, narrow gap disclosed, not fixed**: the counterfactual/rejected-
evidence diagnostic ledger never exposes pixels, but durably records real
geometry/timing/confidence for detections rejected specifically as
`blocked_privacy_zone` -- a caller with diagnostic-API access can learn
that *something* moved in a Privacy Zone, roughly where/when. Documented in
[privacy-ignore-zone-contract.md](privacy-ignore-zone-contract.md)'s new
"Diagnostic metadata exposure" section rather than narrowing the ledger
(which would weaken a separate, already-accepted diagnostic capability) --
per this milestone's own "expose the actual limitation rather than
pretending" doctrine.

**Support bundle** (Journey 11): confirmed safe on raw media (never
included), Source credentials/provider config (never included, test-
proven), and whole-bundle credential-shaped text (test-proven). **Fixed**:
local absolute filesystem paths (which can embed the OS username) were
included with no disclosure -- the CLI's own description promised only "no
passwords, tokens, or media," silent on paths. Fixed with an accurate
description, plus a new opt-in `--no-local-paths` flag that redacts the
bundle's own `manifest.json.database_path` field -- honestly scoped: it
does **not** attempt to scrub every path that could appear inside the
reused `doctor_report.json`'s diagnostic context (doing so safely would
require a second, necessarily-incomplete parallel path-detection pass over
Doctor's own structured facts, which this module's "never a second,
parallel health computation" design invariant already rules out) -- both
the CLI help text and the module docstring say so plainly.

## Contribution/sharing model consistency (Phase K)

New document, [contribution-sharing-model-contract.md](contribution-sharing-model-contract.md),
establishes the three-level doctrine (Local Only / Derived Data
Contribution / Media Contribution) as a standing boundary for whenever
either optional level is eventually built. Confirmed by comprehensive
search: **no cloud contribution backend exists anywhere in this codebase
today** -- this is closure/consistency documentation, not new service
development, per the milestone's own explicit instruction. The closest
existing analog (generic research export) is already metadata-only by
construction and is flagged, not fixed, for two free-text fields
(`reviewed_by`/`curator_identity`) that a future Level 2 payload must not
reuse uncritically.

## Storage/recovery UX (Phase L/M)

`ProductHealthPanel.tsx` (Dashboard, unchanged location -- still below
wildlife content per product doctrine) now takes an optional `storageSummary`
prop (threaded from `DashboardPage.tsx`'s own already-fetched state, no new
network call) and shows: total usage (managed media + database bytes, via
the existing `formatBytes` helper), the graduated `storage_health_tier`
label (Healthy/Getting low/Action recommended/Critically low) replacing the
old binary writable/low-space line -- "Not writable" stays a distinct,
never-masked override, since it is a permissions fact orthogonal to the
disk-space ladder -- and one plain-language category line (bytes in active
use, confirmed-wildlife photos kept, bytes eligible for cleanup). Backup
format/Camera Node API/transport protocol versions were added to the
existing collapsed "Advanced diagnostics" disclosure. Still a compact
panel; Local Data remains the one detailed surface, unchanged in shape.

The stale `open_storage_retention` alert action (`App.tsx`) now opens Local
Data instead of the superseded Saved Media Retention page -- confirmed no
anchor-scroll convention exists anywhere in this codebase, so this is a
plain page navigation, not a new scroll mechanism.

Structured-error surfacing: `StructuredError`/`ErrorComponent`/
`ErrorRecoverability`/`ErrorCorrelation` are now typed in `types.ts` and
`ApiError` (`client.ts`) carries an optional `structuredError` field,
defensively parsed and backward-compatible (every existing `.message`-only
call site is unaffected). Wired into `LocalDataPage.tsx`'s 9 backup/
storage-retention operations (the ones this milestone's own new failure
modes actually touch) via one shared `applyError` helper: the calm primary
message stays exactly as before; a new collapsed "Advanced details"
disclosure shows the failure code/recoverability/diagnostic only when the
backend actually attached one (today: database-write failures). Raw
exceptions remain confined to that collapsed, advanced-only disclosure
throughout, never the primary shown message. Doctor/health messages for
the specific recoverable-failure scenarios this milestone closed
(interrupted restore, critical storage, unattributed/stuck transport
backlog, every-backup-unreadable, a dangling internal reference) are all
plain-language, state what happened, whether history is affected (never,
in every one of these cases), and what to do next.

Camera/Source carry-forward, folded in here since both touch these same
settings/camera surfaces: a Place Activity Report Source-filter checkbox
group (`PlaceActivityReportPage.tsx`, wired to the already-complete backend
`source_ids` field, sources threaded from `App.tsx`'s already-loaded list);
small provider-capability badges at the Add Camera (`CameraSetupPage.tsx`)
and Streams-page provider-edit (`StreamsPage.tsx`) decision points, reusing
existing `supports_live_playback`/`supports_zone_editing` booleans -- no
new backend fields, no capability-matrix page.

Verified: `tsc --noEmit` clean; production build succeeds; full Playwright
suite 73/74 passing, the one failure (`reviewed-product-loop.spec.ts`)
independently confirmed via a real git-worktree baseline comparison against
the unmodified starting HEAD to be pre-existing and unrelated to this
milestone (reproduces identically with zero code changes applied).

## Configuration/version compatibility (Phase N)

Previously scattered: `BACKUP_FORMAT_VERSION`, `NODE_API_VERSION`
("v1"), and `TRANSPORT_PROTOCOL_VERSION` ("transport/v1") were each real,
enforced constants but surfaced on **no** diagnostic/status endpoint at
all -- a recovery/support conversation had no way to see a mismatch
without attempting the actual operation and hitting its error. Schema
version and app version/build were already well-surfaced (good precedent,
extended rather than rebuilt). Fixed: all three now appear on `/api/
product/health` and Doctor's Application check, as fixed local constants
(never a live re-check of what a specific paired Node or a specific backup
archive actually speaks/declares -- that remains each specific operation's
own job, e.g. `verify_archive`'s schema check, `declare_item`'s protocol
check). No new "compatibility" service was built; this is visibility of
facts the code already enforces.

## Bounded update-readiness review (Phase O)

No general managed-upgrade system was built (explicitly out of scope).
Reviewed the concrete future blockers to `update -> restart -> migration ->
health check -> rollback/recovery`:

- **Migration correctness under a hard kill**: already covered by the
  existing transactional-DDL hardening (`_run_migrations_with_transactional_
  DDL`, a dedicated short-lived engine with explicit `BEGIN`, proven by
  `test_a_mid_chain_migration_failure_rolls_back_every_step_not_only_its_
  own`) -- no blocker found.
- **Restore/live-file-swap correctness under a hard kill**: **was** a real,
  small, concrete blocker (the exact gap this milestone's own Phase G
  closes with the sentinel above) -- fixed, not merely documented, per the
  milestone's own instruction to fix a genuine small correctness blocker
  when found rather than only recording it.
- **A real, live cross-install restore acceptance run against this
  project's own actual development database (not a synthetic fixture)
  found a second genuine, small, concrete blocker**: `PRAGMA foreign_key_
  check` on the real database found one dangling foreign key
  (`observation_authority_settings` referencing a `streams.id` that no
  longer existed), which made `replace_live_files`'s rebind path correctly
  refuse the restore (`restore_database_foreign_keys_failed`) -- a real
  install could hit this exact refusal during a genuine host-replacement
  attempt. Root-caused to `ProductRepository._delete_sample_graph` (used
  by both `reset_demo_data`/`remove_sample_data`): it already cleaned up
  two of five tables that key directly on `stream_id` as their own primary
  key when deleting the demo/sample Stream, but missed the other three
  (`observation_authority_settings`, `StreamSpeciesCandidatePackSelectionModel`,
  `YardMapStreamPlacementModel` -- all three lazily created on first use,
  never pre-seeded, so a demo Stream that had ever touched any of them
  before being removed left an orphan). Fixed at the source for all three;
  the one already-existing real orphan row on this project's own database
  was repaired directly (a one-time data fix, not a schema change), and the
  same real backup/restore-with-rebind run was re-proven clean afterward
  (see Journey 6/8 in the final report). Doctor's Database check also
  gained a new, additive, non-blocking signal for this exact class of issue
  (`PRAGMA foreign_key_check`, reusing the already-open connection) so a
  future occurrence on any installation is visible *before* it surfaces as
  a confusing restore refusal, not only during an actual restore attempt.
- **Rollback for a future managed upgrade** would need: a pre-upgrade
  backup trigger (the existing `create_backup(kind="manual"|"pre_restore")`
  primitive already supports a third `kind` value cheaply if ever needed),
  a health check *after* migration but *before* declaring the upgrade
  successful (Doctor's existing bounded, read-only, no-`ProductRepository`-
  construction design is already exactly shaped for this), and a documented
  decision on what "rollback" means for a schema that has already migrated
  forward (SQLite has no cheap down-migration story in this codebase today
  -- restoring the pre-upgrade backup is the only real rollback path, which
  is why the sentinel/interrupted-restore work above is a direct
  prerequisite, not a tangent). This remains future work, correctly scoped
  as its own future milestone, not started here.

## Camera/Source bounded carry-forward

Both items named in the milestone brief as cheap-if-touching-the-same-
surfaces closures:

1. **Provider compatibility capability list**: previously a bare
   `compatibility_label` string at the point of choosing a provider;
   existing-but-unused capability booleans (`supports_live_playback`/
   `supports_zone_editing`/`supports_streams`) are now shown alongside it
   at that same decision point. Not a full capability-matrix rebuild.
2. **Place Activity Report Source filter**: the backend field
   (`PlaceActivityReportRequest.source_ids`) was already complete and
   tested; the frontend now has a filter control wired to it, reusing the
   app's already-loaded Source list.

## Schema

v47 (accepted starting point) -> v49, two additive migrations:

- **v48** (`_migrate_to_camera_node_transport_ingestion`): new, empty
  `camera_node_transport_ingestions` table -- the transport-consumer
  idempotency/lifecycle state existing structures could not represent
  (Phase E).
- **v49** (`_migrate_to_rejected_analysis_media_retention`): one new,
  nullable `rejected_analysis_media_age_days` column on the existing
  `storage_retention_settings` table -- retention state existing structures
  could not represent (Phase D). `None` for every existing row; behavior
  unchanged for every installation until explicitly configured.

Both mirror this codebase's own established migration idioms exactly
(`Base.metadata.tables[...].create(bind=connection, checkfirst=True)` for
the new table; `ALTER TABLE ... ADD COLUMN` guarded by an `inspect()`
column check for the new column), no backfill, no seeded row. Verified:
v47->v49 upgrade (via two dedicated migration tests mirroring this
codebase's own rebuild-in-place proof pattern), clean creation at v49
directly, and representative existing data (Source counts, settings
values) survives both migrations unchanged.

## Core gate closure

The first full Core run at closure found exactly 10 failures, all of the
same known, expected shape this codebase has hit before when a milestone
bumps the schema version (see "Multi-Subject Visit Assembly Phase 2"'s own
"Core gate caught 6 hardcoded schema-sentinel regressions" precedent): a
hardcoded `assert CURRENT_DATABASE_SCHEMA_VERSION == 47` sentinel in 10 test
functions across 7 files (`test_camera_health.py`, `test_camera_node.py`,
`test_candidate_visit_repository.py` (4 tests), `test_species_candidate_
packs.py`, `test_visit_collections.py`, `test_visit_tags.py`, `test_yard_
map.py`). Each sentinel exists deliberately, to force a conscious update
whenever a new migration is added rather than let a schema-version test
silently stop testing what it claims to. Updated all 14 occurrences (some
tests assert it twice) to `49`; a 15th superficially similar line
(`test_local_backup_recovery.py`'s `restored["duration_ms"] == 47`, a
timing assertion that coincidentally also compares to the literal 47) was
correctly left untouched. Confirmed no other test anywhere in the suite
still hardcodes the old version. Focused regression across all 7 files
(128 tests) passed clean; Core was re-run once in full afterward, per
doctrine: 4,391 passed, 1 failed (`test_transport_worker.py::test_sticky_
diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success`).
Investigated rather than assumed: `src/mockingbird_node/` (the module this
test covers) has zero diff anywhere in this milestone; the test passed in
isolation and in two of three repeated full-file runs with byte-identical
code, confirming genuine non-deterministic flakiness (a captured log line,
`"next_attempt_in_seconds": -0.0`, points at the same class of tight
wall-clock timing budget this codebase has already documented and fixed
once before for an unrelated Camera Node test -- see "Order/flakiness
finding" in
[test-suite-validation-tiers-contract.md](test-suite-validation-tiers-contract.md)).
Not a milestone-caused defect, so not fixed here and Core was not run a
third time, per "no audit-of-an-audit" -- disclosed plainly rather than
silently re-run until green.

## Known bounded gaps (deferred, not silently dropped)

- Full media-content-decode integrity checking (Doctor's new check is
  cheap and stat-only -- missing/truncated/zero-byte files only, never a
  claim about whether a file actually decodes).
- A periodic re-verification job for real, aging backups (the three real
  on-disk backups on this checkout are 24-43 migrations old and have never
  been re-proven through the *current* full migration chain by an
  automated job -- each individual migration step is tested, but no
  scheduled task exists to periodically re-run `verify_backup` against
  old real archives).
- `classifier_manifest_export_root` remains excluded from backup scope and
  undocumented in the backup design doc's own enumeration (low severity --
  regenerable export artifacts).
- `frame_driven_provider.py`'s own exclusion filter (center-point-only) is
  architecturally weaker than the pixel-level masking it currently rides on
  top of -- latent/theoretical, no evidence of live impact, documented as a
  fragility for a future detector-provider change, not fixed.
- A general frontend structured-error-taxonomy sweep beyond this
  milestone's own new failure surfaces (backup/restore/storage) -- the
  plumbing (`StructuredError`, `ErrorComponent`, `ErrorRecoverability`) is
  now typed and wired frontend-side, ready for a future pass to extend to
  more `ErrorComponent` values backend-side.
- A full provider capability-matrix page (only a bounded inline summary at
  the point of choosing a provider was built).
- NAS/external-storage migration, mobile/PWA, a full update-manager,
  release packaging -- explicitly out of this milestone's scope per the
  brief's own exclusion list.
