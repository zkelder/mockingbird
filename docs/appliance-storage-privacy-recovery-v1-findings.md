# Appliance / Storage / Privacy / Recovery v1 — Phase A findings

Bounded archaeology, branch `main`, starting HEAD `f97598e`, DB schema v47. This
document is the required Phase A output: concrete findings only, grouped
P0/P1/P2, not a general wishlist. Six parallel read-only archaeology passes
covered storage/retention/low-space, backup/restore/clean-install, Camera Node
replacement + remote-transport host lifecycle, privacy/mask/export/
contribution, Doctor/support-bundle/versioning, and frontend settings/health
surfaces.

## Headline

This installation already has substantially more appliance maturity than a
cold read of the milestone brief implies: a full `.mbbackup` ZIP backup/restore
system with pre-restore safety backups, verified atomic swap, and a *tested,
real* `rebind_managed_storage` cross-install restore path; a disabled-by-default
recoverable Storage & Retention quarantine system (14-day recovery window,
~20 existing tests); a mature Doctor with 15 checks including low-space,
backup-staleness, and Camera-Node restart-instability; and an honestly
documented Privacy Zone contract (trigger-level exclusion only, already
disclosed as not pixel-redaction, and confirmed by fresh code-reading to have
**no** live path where masked content becomes ordinary evidence). This shifts
the milestone's center of gravity toward reconciliation and gap-closing, with
one genuine greenfield deliverable: the remote-transport host-file consumer
lifecycle (Phase E), which is a real, confirmed, ~0%-built gap.

## P0 — data-loss / privacy / corruption / unbounded-growth risk

1. **No host-side consumer exists for completed remote-transport items.**
   `TransportLedger.complete()` (`storage/camera_node_transport_ledger.py:256-281`)
   promotes a verified blob to `<root>/<node_id>/completed/<item_id>.bin` and
   stops — nothing anywhere reads it back into a `MediaAsset`, and the Camera
   Node deletes its own spooled copy immediately on ack
   (`mockingbird_node/transport_worker.py:131-132`), making the host's
   `completed/` blob the **sole surviving copy** of that evidence with no
   consumer and no retention/cleanup policy. This is the milestone's own named
   standing gap (Phase E) and the largest concrete deliverable in this pass.
2. **`linked_evidence_or_analysis` media (rejected/suppressed detections with
   a file on disk but no Visit link) is retained forever with no age-out lever
   and is invisible in `StorageSummary`** (`product_repository.py:16507-16510`;
   absent from `api/schemas.py:5976-5999`). Unbounded, invisible, and
   unreclaimable by any existing setting — likely the largest steady-state
   disk consumer over an install's life and in tension with "do not silently
   retain unlimited raw media."

## P1 — major appliance/recovery usability gap

Storage/retention:

3. `storage_summary()` (hit by `/api/product/health` on every Dashboard mount)
   is an unbounded per-`MediaAsset`-row Python loop with N+1 queries (stat +
   symlink walk + Visit/VisitEvidenceLink lookups per row) — the "expensive
   scan on every page load" the milestone wants avoided, even though it is a
   DB scan rather than a filesystem walk.
4. Disk-space health is binary (one `<1GB or <5%` threshold) — no
   healthy/getting-low/action-recommended/critical ladder.
5. `WorkerStatusPage` hardcodes "Saved media retention" as `implemented=False`
   even though a real, working, opt-in pipeline exists under a different name
   (`workers/registry.py:65-77`) — actively misleading.

Backup/restore (mechanism itself has **no P0** — genuinely solid: verified
temp-then-atomic-rename creation, two-phase confirmed transactional restore
with pre-restore safety backup and rollback-on-exception, tested cross-install
`rebind_managed_storage`):

6. `last_backup_verified` is **structurally always `False`**, even seconds
   after a real verified create/import/verify (`storage/backup.py:870`,
   asserted as current behavior by `tests/test_local_backup_recovery.py:358`) —
   surfaces as a false "unverified" claim in two UI surfaces.
7. 37 distinct internal backup/restore failure codes collapse into one
   generic HTTP message (`api/main.py:1522-1526`) — not diagnosable.
8. A hard interruption during backup create/import leaves an orphaned
   `.creating-*`/`.import-*` temp file that permanently inflates
   `unreadable_backup_count` with no cleanup path anywhere.
9. `replace_live_files`'s live swap is three sequential `os.replace` calls
   with no on-disk transaction marker — a killed *process* (not a raised
   exception, which is already well-handled) mid-swap leaves a mismatched
   DB/media pair with nothing to detect it at next startup.

Remote transport / Camera Node replacement:

10. `revoke_camera_node_pairing` pops `node_credential` but never
    `node_transport_credential` (`product_repository.py:8768-8794`), and
    `resolve_camera_node_transport_source` never checks `node_pairing_state`
    — a revoked node's transport credential keeps working indefinitely.
11. Pending transport backlog on a node being replaced is neither drained nor
    disclosed — evidence can silently become permanently undeliverable.
12. No explicit lifecycle state distinguishes "transport-completed" from
    "ingested" — without one, any future consumer risks double-ingestion on
    its own crash/restart.

Doctor / support bundle / compatibility:

13. `_interpret_backup` never branches on `unreadable_backup_count` — an
    install where every backup is corrupt reads as calm "no backups yet."
14. No Doctor check for incomplete/corrupt media (only free-space/writability
    is checked; no file-level check exists at all).
15. Backup format version, Camera Node API version, and transport protocol
    version are each enforced in code but surfaced on **no** diagnostic/status
    endpoint or support bundle — schema version and app version/build *are*
    already well surfaced (good precedent to extend).
16. Support bundle includes local absolute filesystem paths (which typically
    embed the OS username) via `manifest.json.database_path` and the embedded
    Doctor report, but the bundle's own user-facing description promises only
    "no passwords, tokens, or media" — silent on paths.

Frontend:

17. Backend already has a complete structured-error foundation
    (`diagnostics/error_taxonomy.py`: component/recoverability/retryable/
    bounded `diagnostic`) wired into exactly one exception handler
    (`api/main.py:656-689`, DB failures only) — the frontend's shared
    `request()` reads only `body.detail` and discards `body.error` entirely.
    This is the mechanism Phase M's "recovery UX" doctrine wants and it's
    half-built and being thrown away client-side.
18. Place Activity Report has a complete, additive, already-shipped backend
    Source filter (`PlaceActivityReportRequest.source_ids`) with **zero**
    frontend surface — confirmed exactly as the milestone's own named
    Camera/Source carry-forward item.
19. Provider compatibility is a bare "Name — Label" string in two dropdowns;
    real capability booleans exist nearby but are never shown together at the
    point of choosing a provider — confirmed exactly as the milestone's other
    named carry-forward item.
20. No single storage-health surface is both simple and complete:
    `ProductHealthPanel` is simple but sparse; `LocalDataPage` is complete but
    reads as an administrator console.
21. A stale alert action ("Open Storage & Retention") navigates to the
    superseded `SavedMediaRetentionPage` instead of Local Data's real section.

Privacy (mechanism itself has **no P0** — confirmed no live path from any
capture/import/webhook/replay/multimodal path lets privacy-zone-only content
become a detection, track, Visit, Observation, or export row):

22. The counterfactual/rejected-evidence ledger never exposes pixels, but it
    durably records real geometry/timing/confidence for detections rejected
    as `blocked_privacy_zone` — a user who drew a Privacy Zone to leave *no
    trace* of that area's activity would reasonably want this disclosed;
    no existing doc addresses it.

## P2 — bounded polish / deferred

- `frame_driven_provider.py`'s own exclusion filter is center-point-only
  (weaker than true pixel masking) and today only "works" because it sits
  downstream of a detector that already blacks out pixels — latent/
  theoretical, no evidence of live impact; documented, not fixed.
- Free-text-shaped export fields (`reviewed_by`, `zone_name`, `stream_name`,
  `curator_identity`) are unscrutinized against a future Derived Data
  Contribution boundary — no live exposure today (no contribution backend
  exists to consume them); a note for whoever designs that feature, not a fix.
- No backup auto-pruning — **confirmed intentional**, an explicit non-goal in
  `local-backup-recovery-design.md`; not a gap, left as-is.
- No on-disk thumbnail artifacts exist in the live product runtime today
  (only in-memory resize + an offline dev tool) — "thumbnails" as an
  accounting category is not applicable yet; reported honestly rather than
  fabricated.
- `classifier_manifest_export_root` excluded from backup scope and not named
  in the design doc's enumeration — low severity (regenerable exports).
- Real on-disk backups are 24-43 migrations old and never re-proven through
  the *current* full migration chain — worth a future periodic check, out of
  bounded scope to build a scheduled job for here.
- No standalone backup/restore CLI (API/UI-only) — consistent with existing
  precedent (Doctor/support-bundle are the only CLI-first diagnostics).
- Old-node-reconnect-after-replacement is correct only incidentally
  (orphaned-credential 401) and untested — add a regression test, no behavior
  change needed.
- Transport-backlog UI messaging exists only on Dashboard/LiveCameraOverview
  and doesn't distinguish "draining" from "stuck" — minor.
- "Settings" nav item leads to a page titled "Local Data" — naming only.
- Onboarding wizard shows a raw folder path outside advanced-diagnostics
  gating — arguably intentional local-first transparency per product
  doctrine ("a user should be able to tell where media lives"); left as a
  disclosed judgment call.
- No in-product Doctor/support-bundle UI action (CLI-only) — net-new surface,
  out of bounded scope.
- Single physical disk holds live DB, media, and all local backups together —
  explicitly an accepted non-goal (no cloud/remote storage in this phase).

## Scope decision for this milestone

Implementing: P0 #1-2 in full; P1 #3 (via a bounded TTL cache, not a
storage-optimizer rewrite), #4, #6-13, #15-21 in full; #5, #14, #22 via the
cheapest correct fix (see contract docs for exact shape). Deferring every P2
above and the narrower P1 sub-cases called out inline (full media-content
integrity decoding, historical backup re-verification job, general
error-taxonomy sweep beyond this milestone's own new failure modes, full
provider capability-matrix rebuild) to "Known bounded gaps" in the final
report, consistent with "fix concrete gaps only" / "do not build a general
wishlist."

## Addendum — found during Phase G validation, not Phase A archaeology

A real (not synthetic-fixture) cross-install restore acceptance run against
this project's own actual development database found one more genuine, real
P1: a dangling foreign key (`observation_authority_settings` referencing a
deleted `streams` row) that made a real restore-with-rebind attempt fail.
Root-caused to `ProductRepository._delete_sample_graph` missing three of
five Stream-scoped tables from its demo-data-removal cleanup. Fixed at the
source (all three tables), the one pre-existing real orphan row was
repaired directly, and Doctor's Database check gained a new, non-blocking
`PRAGMA foreign_key_check` signal so a future occurrence is visible before
it can block a real restore again. See "Bounded update-readiness review
(Phase O)" in
[appliance-storage-privacy-recovery-v1-contract.md](appliance-storage-privacy-recovery-v1-contract.md)
for the full account. This is exactly the kind of finding bounded Phase A
archaeology (reading code) cannot surface but real end-to-end acceptance
testing (Phase G) can -- recorded here for traceability, not reclassified
as if it had been found earlier.
