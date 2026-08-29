# Retention Correctness & Bounded Cleanup Closure v1

## Identity

- **Starting HEAD:** `8572308` (branch `main`) — verified against
  `docs/release-execution-state.md` §1/§3 before any change; matched
  exactly (accepted milestone: Storage / Retention / Disk-Pressure &
  Recovery Closure v1, classification B; authorization before this
  instruction: `NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`;
  Lane M "materially closed," open pending exactly these three
  corectness fixes).
- **Schema:** `v58`, unchanged. Every fix in this milestone reuses
  existing columns (`VisitModel.is_superseded`,
  `VisitModel.representative_media_path`, `MediaAssetModel.created_at`,
  `StorageCleanupBatchModel`/`StorageCleanupItemModel`'s existing state
  columns) — no new table, no new column. See "Schema discipline," below.
- **Worktree safety:** confirmed at start — `git status` showed only the
  seven preserved untracked detector files (all present, untouched
  throughout this session) plus, later, this milestone's own two modified
  files. No `.git/*.lock` files. Four other `ccd-cli` processes had this
  exact working tree as their `cwd`, but all were long-lived, low-CPU
  (1.9–4.1%) idle sessions with no files modified in this tree in the 15
  minutes before work began and no `pytest`/`uvicorn`/`mockingbird`
  process bound to it — confirmed not active writers. `uv run` created one
  incidental, harmless, untracked `uv.lock` (this repo previously had
  none committed) as a side effect of dependency resolution; left as-is,
  not part of this milestone's deliverable.
- **Governing sources read:** `docs/release-execution-state.md` (§1, §3,
  §6 Lane M, §13 preserved-files list), `docs/product-doctrine.md` (full),
  `docs/roadmap.md` (targeted, Lane M / storage sections),
  `docs/storage-retention-disk-pressure-recovery-closure-v1-report.md`
  (full — the prior milestone's own precise root-cause diagnosis for all
  three defects), `docs/appliance-storage-privacy-recovery-v1-contract.md`
  (the governing retention contract, `create_media_import`/
  `import_folder_media`/`_create_media_product_records`, the full cleanup
  batch state machine, `storage_cleanup_history`, and the existing
  `tests/test_storage_retention.py` suite (1137 lines pre-change) for
  established conventions.

## Contract

### 1. Imported-media retention rule

`docs/appliance-storage-privacy-recovery-v1-contract.md:159-163` (accepted
2026-08-23) is explicit: imported originals are "subject to the same
active/superseded/reviewed rules as any other Visit-linked evidence — no
separate contract... confirmed intentional simplicity ... not an
oversight." Tracing the real code against that claim:

- `create_media_import`/`import_folder_media` both funnel through
  `_create_media_product_records`, which creates exactly **one**
  `MediaAssetModel` per import and sets `VisitModel.representative_
  media_path` — and, confirmed by grep, **never** creates a
  `VisitEvidenceLinkModel` row. There is no separate "derived" or
  "canonical" evidence asset for an import; the one asset created **is**
  the evidence, playing the same role a linked primary frame plays for a
  camera-captured Visit. This answers the brief's "can the model
  distinguish original vs. derived evidence" question directly: there is
  nothing to distinguish — an import has exactly one asset, so the
  question does not present a real contract gap here.
- `_storage_retention_evaluation`'s `legacy_representative_evidence`
  bucket is what actually governs this asset (any `VisitModel.
  representative_media_path` match with no materialized link). Pre-fix,
  it protected unconditionally, forever, regardless of the owning Visit's
  `is_superseded`/review state/age.
- For ordinary **linked** evidence, the equivalent primary frame
  (`active_visit_primary_evidence`) is *also* protected forever while its
  Visit is active (`is_superseded is False`), independent of review
  state — matching the doctrine's own rule that reviewed truth protects
  its evidence, not that only reviewed evidence is protected. Once **every**
  Visit referencing a linked asset is superseded, it becomes eligible
  after `superseded_evidence_age_days` (default 90d) as
  `superseded_only_evidence` — the identical protection lifecycle,
  applied at the Visit level rather than the review level.

**Answers to the governing questions:**

1. **Retainable indefinitely:** imported media whose owning Visit(s)
   remain active (`is_superseded is False`) — reviewed or not, corrected
   or not; identical to a linked primary frame.
2. **Eligible under ordinary retention:** imported media whose *every*
   owning Visit has been superseded, once `superseded_evidence_age_days`
   has elapsed since the asset's own `created_at` — the same clock and
   threshold `superseded_only_evidence` already uses for linked evidence.
3. **Reviewed truth implies:** product truth preservation (the Visit/
   Event/`ReviewLabel` rows, forever), not automatic indefinite evidence
   preservation independent of supersession — exactly the existing rule
   for a linked primary frame. Being reviewed is not what protects the
   file; being the representative evidence of a still-active Visit is.
4. **Originals vs. derived evidence:** not distinguished in the data
   model for imports, because there is nothing to distinguish — confirmed
   by code tracing, not assumed.
5. **Explicitly contradicted by existing docs/tests:** yes — the accepted
   contract's own "no separate contract" claim, and zero pre-existing
   test coverage of retention behavior for `create_media_import`/
   `import_folder_media` (confirmed by grep before this milestone;
   the prior milestone's report states this explicitly).

### 2. Staging-batch state-machine rule

The batch states are `previewed → staging → {quarantined, failed} →
{restored, restore_conflict, purged}`. `"staging"` is used at two related
moments:

- **Immediately**, right after a preview is confirmed (`execute_storage_
  cleanup` sets `batch.state = "staging"` before its per-item loop even
  starts) — genuinely transient in the common case.
- **As a resting state**, if the per-item loop's own final reconciliation
  pass finds at least one item still `staged`/`moving` whose file was
  nonetheless **confirmed physically moved** to
  `.recovery/<batch_id>/...` on disk (`_storage_item_has_recovery_file`).
  This happens because the filesystem `rename()` and the DB commit that
  records it are two separate operations — a crash, kill, or raised
  exception strictly between them leaves a real file in quarantine with
  its owning `StorageCleanupItemModel` row still reading `staged`/
  `moving` and its `VisitEvidenceLinkModel` rows (if any) still intact.
  This is a real, reproducible interruption shape, not hypothetical —
  `tests/test_storage_retention.py::test_interrupted_move_remains_
  recoverable_without_removing_links` (pre-existing, unmodified by this
  milestone) already demonstrates it deterministically via a monkeypatch
  that performs the real move and then raises.

**Why purge, not just restore, was blocked.** `purge_storage_cleanup_
batch`'s own item query is `where(state == "quarantined")` — a `staging`
batch's items are never `"quarantined"` (that transition only happens at
the tail of the per-item loop, which is exactly what got interrupted), so
purge found nothing to do and the top-level state guard rejected
`"staging"` outright, at any time, even manually past the 14-day recovery
deadline. Restore worked because `_restore_storage_item_from_recovery`
only needs the file to exist in quarantine — it never depended on the
item having reached `"quarantined"`. Abandoned `staging` batches can
accumulate indefinitely: they hold **real disk space** (the moved file,
still charged against the managed media root's `.recovery/` subtree) and
a durable DB row, forever, with no terminal path except restore. No DB
corruption, no data loss (restore always worked) — a genuine, bounded
storage-reclamation gap.

### 3. Cleanup-history bound

`MAX_STORAGE_CLEANUP_HISTORY_ITEMS = 30` is a pure count. Pre-fix it
appeared in exactly two places, neither of which deletes a row:
`storage_cleanup_history()`'s own read-page `.limit(...)`, and a
`batch_ids[:MAX_STORAGE_CLEANUP_HISTORY_ITEMS]` chunk-size slice inside
`purge_expired_storage_recovery`'s automatic sweep (an unrelated
per-invocation work-batching bound, not a history bound). The intended
enforcement — the constant's own name — is: the `storage_cleanup_batches`
table (what `storage_cleanup_history` reads, filtered to `state !=
"previewed"`) should never hold more than the newest 30 **fully-resolved**
entries. The fix enforces this **on completion** of every write path that
can produce a newly-eligible row (`execute_storage_cleanup`,
`restore_storage_cleanup_batch`, `purge_storage_cleanup_batch`) — not on
insert (a fresh batch is never itself prunable), not at startup, and not
via a new scheduled job (the existing daily/weekly automatic pass and any
manual action already call these same paths).

## Fixes

### Defect 1 — imported/folder-imported media over-retention

**Reproducer (RED, pre-fix).** `tests/test_storage_retention.py::test_
superseded_imported_media_becomes_eligible_and_purges_with_no_dangling_
reference` — imports media through the real `create_media_import` path,
backdates the asset to 365 days, marks the owning Visit `is_superseded =
True`, sets a 30-day `superseded_evidence_age_days` threshold, and asserts
`preview.eligible_media_count == 1`. Pre-fix this reads `0` — the asset
is unconditionally protected forever.

**Root cause.** `_storage_retention_evaluation`'s `legacy_representative_
evidence` branch (`src/mockingbird/repository/product_repository.py`)
protected any asset with a `representative_media_path` match and no
`VisitEvidenceLinkModel` row, full stop — never consulting
`is_superseded` or age at all, unlike every other evidence bucket in the
same function.

**Fix.** [product_repository.py](../src/mockingbird/repository/product_repository.py)
— inside the `legacy_representative_visits and not links` branch: if
*every* Visit referencing the asset is superseded, apply the identical
age-gated eligibility `superseded_only_evidence` already uses (same
`settings.superseded_evidence_age_days` threshold, same candidate
category — deliberately reused, not a new category, since the underlying
rule is now literally the same rule); otherwise (any Visit still active),
keep the existing unconditional protection unchanged. ~20 lines changed,
confined to one existing function; no new state, no new category besides
reusing `superseded_evidence_too_recent` for the not-yet-old-enough case.

**RED → GREEN evidence.** `git stash push -u -- src/mockingbird/repository/product_repository.py`
(keeping the new tests) reproduced exactly the expected RED set:
`test_superseded_imported_media_protected_before_age_threshold`,
`test_superseded_imported_media_becomes_eligible_and_purges_with_no_
dangling_reference`, and `test_legacy_representative_media_shared_by_two_
visits_protected_until_all_superseded` failed; the four "still active/
protected" tests (manual import, folder import, reviewed, corrected)
correctly **passed both before and after** — they test behavior that was
never broken (the bug was only "never becomes eligible even once
superseded," not "insufficiently protected while active"). `git stash
pop` restored the fix; full green confirmed again (39/39 in
`test_storage_retention.py`).

### Defect 2 — `"staging"` cleanup-batch terminal-resolution gap

**Reproducer (RED, pre-fix).** `test_staging_batch_purge_completes_
interrupted_move_and_removes_file` — reuses the exact, pre-existing
interruption technique (`_move_storage_item_to_recovery` really moves the
file, then raises) to produce a genuine `staging` batch, advances past the
14-day recovery deadline, and asserts a subsequent `purge_storage_cleanup_
batch` call actually reaches `"purged"` and removes the file. Pre-fix,
this call always raised `storage_cleanup_purge_unavailable`.

**Root cause.** `purge_storage_cleanup_batch` accepted only `{"quarantined",
"restore_conflict"}` as a starting state, and its own purge query only
ever considered items already durably `"quarantined"` — a state an
interrupted item can structurally never reach on its own.

**Fix.** [product_repository.py](../src/mockingbird/repository/product_repository.py)
adds `_resolve_staging_batch_for_purge`, called from `purge_storage_
cleanup_batch` only when `batch.state == "staging"`, before its existing,
unmodified purge logic runs. It reuses — does not duplicate — the exact
reconciliation `execute_storage_cleanup` already performs at the end of a
clean run: two small helpers, `_storage_cleanup_finish_recoverable_item`
(completes the interrupted `staged→quarantined` transition for an item
whose file is confirmed already moved) and `_storage_cleanup_reconcile_
batch` (the one canonical `moved/recoverable/failed` count formula, now
shared by both the first-attempt and resume paths instead of being
inlined twice). Both `execute_storage_cleanup`'s own per-item loop and
tail were refactored to call these same helpers — one implementation of
this transition and this formula, not two, closing the "second cleanup
state machine" risk the brief explicitly warned against.

Outcome shape, matching the required properties exactly:

- **Idempotent / repeated invocation safe:** `last_purge_idempotency_key`
  reuse (the existing mechanism, unchanged) covers every branch, including
  the new "nothing to purge" terminal outcome.
- **Safe after interruption:** per-item transactions, unchanged pattern;
  a crash mid-resolution leaves the batch exactly where any other
  interruption at that point already leaves it (`staging`, still
  resolvable) — proven directly by `test_history_prune_failure_leaves_
  batch_safely_recoverable_not_corrupted`.
- **No deletion of files still owned by live product records:** an item
  is only finished to `"quarantined"` when its live `VisitEvidenceLink`
  snapshot still matches what was true at preview time; a mismatch
  restores the file back instead of deleting anything.
- **No resurrection of already-finalized records:** the helper only ever
  touches items in `{"staged", "moving"}` inside a batch already `staging`
  — `"quarantined"`, `"purged"`, `"restored"`, `"failed"` items are never
  revisited.
- **Explicit observable outcome:** three real terminal shapes — full
  purge (`"purged"`), a genuinely-empty batch resolves to the existing,
  correct `"failed"` vocabulary rather than a misleading `"purged"` with
  zero items actually removed (`test_staging_batch_with_all_items_
  restored_during_reconciliation_resolves_to_failed`), and a batch that
  remains genuinely ambiguous even after a real reconciliation attempt
  (its file cannot be restored back either) is left at `"staging"` and
  purge correctly raises `storage_cleanup_purge_unavailable`
  (`test_staging_batch_still_ambiguous_after_reconciliation_rejects_
  purge` — this milestone's "invalid transition rejected" case).
- **Failure case:** a real deletion (permission) failure during the
  actual unlink step leaves the item `"quarantined"` (untouched, still
  restorable) and the batch `"restore_conflict"`, never a false
  `"purged"` (`test_staging_batch_purge_survives_deletion_permission_
  failure`).

**RED → GREEN evidence.** All five new staging-purge tests failed
pre-fix with `storage_cleanup_purge_unavailable` (or, for the
idempotent-repeat test, on its first assertion); all five pass post-fix.
Restore-from-staging (the pre-existing, unmodified path) continues to
pass unchanged, confirmed by the full pre-existing suite.

### Defect 3 — `storage_cleanup_history` unbounded table

**Reproducer (RED, pre-fix).** `test_cleanup_history_is_bounded_after_a_
real_execute_pass` — seeds `MAX_STORAGE_CLEANUP_HISTORY_ITEMS + 5` (35)
directly-constructed `"purged"`-state batch rows, then runs one real,
ordinary `execute_storage_cleanup` pass (an unrelated orphaned-media
cleanup) and asserts the **raw table row count** (not the read API, which
was already artificially bounded and would have masked the defect) is
`<= 31`. Pre-fix this reads `35` — unchanged, no pruning occurred.
`test_cleanup_history_table_row_count_exceeds_bound_before_any_pruning_
runs` isolates the premise (seeding alone, no write path invoked,
correctly exceeds the bound both before and after the fix — it is not
itself a regression test, it establishes that the table does not
self-bound on insert).

**Root cause.** No code path anywhere ever issued a `DELETE` against
`storage_cleanup_batches`; `MAX_STORAGE_CLEANUP_HISTORY_ITEMS` only ever
bounded a read-page size and an unrelated chunk-processing size.

**Fix.** [product_repository.py](../src/mockingbird/repository/product_repository.py)
adds `_prune_storage_cleanup_history(session, *, keep=MAX_STORAGE_
CLEANUP_HISTORY_ITEMS)`: deletes the oldest rows beyond the newest `keep`
**among batches in a terminal, disk-safe state** (`purged`, `restored`,
`failed`) only — a batch still holding live `.recovery/<batch_id>/` files
(`staging`, `quarantined`, `restore_conflict`) is never counted or
touched, regardless of age, so a row is never deleted while it remains
the only durable reference to real bytes still on disk (proven directly
by `test_cleanup_history_pruning_never_removes_a_batch_with_live_
recovery_files`, which seeds 400-day-old `quarantined` and 35 newer
`purged` rows and confirms the old-but-live one survives). Called, in
the same transaction as the batch's own terminal-state write, at the tail
of `execute_storage_cleanup`, `restore_storage_cleanup_batch`, and
`purge_storage_cleanup_batch` — the three moments a batch can newly become
eligible. `StorageCleanupItemModel` rows for a pruned batch are deleted
first (no `ON DELETE CASCADE` is configured on that foreign key, and
SQLite FK enforcement is off in this codebase — confirmed by grep — so
this ordering is required, not incidental, to avoid leaving orphaned item
rows referencing a deleted batch id).

**RED → GREEN evidence.** `test_cleanup_history_is_bounded_after_a_real_
execute_pass`, `test_cleanup_history_pruning_never_removes_a_batch_with_
live_recovery_files`, and `test_history_prune_failure_leaves_batch_
safely_recoverable_not_corrupted` all failed pre-fix (the first two on
the row-count/survival assertions directly; the third because, with no
prune call anywhere, the injected `RuntimeError` monkeypatch target
`ProductRepository._prune_storage_cleanup_history` didn't exist as an
attribute reachable the same way pre-fix — confirmed it fails for the
right reason, an `AttributeError`-shaped setup failure, not a false
green); all three pass post-fix.

## Reviewed truth safety

Explicit result: **safe, unaffected.** Tested directly for all five
required cases:

- **Reviewed Visit with imported media** — `test_reviewed_imported_
  visit_media_stays_protected_indefinitely`: reviewed, 10 years old,
  `retain_reviewed_bird_wildlife_evidence` disabled, `reviewed_non_bird_
  age_days` lowered to its minimum (30) — still fully protected, because
  it is never superseded. Reviewed truth's evidence stays exactly as
  protected as before this milestone.
- **Corrected Visit with imported media** — `test_corrected_imported_
  visit_media_stays_protected`: `reviewed_label` changed after an initial
  review (a correction); `is_superseded` is never touched by a correction
  (confirmed by tracing every `is_superseded = True` assignment site in
  the codebase — both are part of the Visit split/merge curation
  machinery, unrelated to review/correction) — media stays protected.
- **Unreviewed imported Visit** — `test_manual_imported_media_is_
  protected_while_visit_is_active` — protected (unchanged behavior, no
  age-out lever exists or was added for the unreviewed case, matching the
  existing `unresolved_visit_evidence` precedent for linked evidence).
- **Folder-imported Visit** — `test_folder_imported_media_is_protected_
  while_visit_is_active` — identical code path
  (`_create_media_product_records`), identical (now-fixed) behavior,
  proven independently through the real `import_folder_media` entry
  point, not assumed from the manual-import case.
- **Ordinary camera-captured Visit** — exercised throughout the
  pre-existing 349-test suite (unmodified, all still green) and directly
  in the new integrated test's "ineligible Reviewed evidence" leg.

No new age-out lever was invented for reviewed-but-not-superseded
imported media — evidence can age out only once its owning Visit is
superseded, a pre-existing, doctrine-governed transition this milestone
does not create or trigger (see "Imports and provenance," below). The
brief's own conditional — "if evidence can legitimately age out while
Reviewed truth remains, the UI/data contract must already support that" —
applies here exactly as it already does for ordinary linked evidence: a
superseded Visit's own row, and any `ReviewLabel` history, is never
deleted; only its evidence *file* can eventually go, and every
media-serving read path already treats a missing file as a clean 404 (the
same, already-accepted, already-tested contract every other purged
evidence category relies on) — verified directly for this new case by
`test_superseded_imported_media_becomes_eligible_and_purges_with_no_
dangling_reference`, which reads the Visit/Event/`ReviewLabel` state back
after a real purge and confirms it is completely intact.

## DB/media coherence

**DB → media (no surviving DB reference should unexpectedly point to a
file the new behavior deleted).** Verified directly:
`VisitModel.representative_media_path` on a purged, superseded imported
Visit is left exactly as it always was for the equivalent linked-evidence
case (the field is a plain string, never nulled by any cleanup path in
this codebase — confirmed by grep, unchanged by this milestone) —
pointing at a path whose file is now gone. This is not a new class of
dangling reference: `MediaAssetModel` rows are already, deliberately, kept
forever as an audit trail after any purge (the accepted, tested contract
for every other category — "the file is gone, the row is kept forever...
every media-serving read path already handles a missing file as a clean
404"), and this fix makes imported media follow that identical, already-
proven-safe convention rather than inventing a new one. Proven directly,
not assumed, by reading the `MediaAssetModel`/`VisitModel`/`EventModel`
rows back after a real purge in
`test_superseded_imported_media_becomes_eligible_and_purges_with_no_
dangling_reference`.

**Media → DB (the new behavior must not create additional orphan files).**
Verified for all three fixes: Defect 1 only ever *removes* a file through
the existing, unmodified, already-transactional move→quarantine→purge
pipeline — it adds no new file-write path. Defect 2's reconciliation
never writes or moves a file itself; it only ever completes DB bookkeeping
for a move that already, verifiably (via `_storage_item_has_recovery_
file`'s on-disk check), happened, or restores a file back — it can prevent
an orphan (a file stuck in quarantine forever, unreferenced by any
resolvable DB path) but cannot create one. Defect 3 only ever deletes
`StorageCleanupBatchModel`/`StorageCleanupItemModel` **rows**, and only
for batches already proven to hold no live files
(`test_cleanup_history_pruning_never_removes_a_batch_with_live_recovery_
files`) — it never touches a `MediaAssetModel` row or a file on disk.

**The pre-existing, already-disclosed orphan-media gap (no code scans the
media directory and cross-references it against the DB — "media → no
database owner") is unaffected by this milestone and is left exactly as
it was.** None of the three fixes reproduces or touches it; per the
brief, it is not reopened here.

## Integrated cleanup acceptance

`test_integrated_cleanup_pass_resolves_all_three_defects_correctly` runs
one product-shaped scenario containing all four required elements plus
history overflow, in a single pass:

**Before:** 32 pre-existing resolved (`"purged"`) history rows (already
over the 30-row bound); one Reviewed, camera-captured Visit with linked
primary evidence (10 years old); one ordinary orphaned asset that gets
interrupted mid-cleanup into a genuine `"staging"` batch; one manually-
imported Visit, later marked superseded and backdated to 365 days
(`superseded_evidence_age_days = 30`).

**Actions:** the staging batch is resolved via the fixed `purge_storage_
cleanup_batch` (Defect 2); the superseded imported asset is found eligible
and cleaned through one ordinary `preview → execute` pass (Defect 1),
which as a side effect prunes history (Defect 3).

**After, all asserted directly, not inferred:**

- Correct files retained: the Reviewed evidence file still exists.
- Correct files removed: the superseded imported asset's file is gone;
  the staging batch's quarantined file is gone (real purge, not restore).
- Cleanup batches in valid terminal states: the staging batch reads
  `"purged"`; the ordinary cleanup batch reads `"quarantined"` (correctly
  not yet purged — recovery window still open, untouched by this pass).
- History within bound: raw table row count `<= MAX_STORAGE_CLEANUP_
  HISTORY_ITEMS + 3` (30 pruning survivors + the two batches this same
  pass just created, neither yet prunable).
- DB/media coherence intact: the Reviewed Visit's `reviewed_label` is
  unchanged; the superseded imported Visit's `is_superseded` remains
  `True` and its `MediaAssetModel` row is retained (audit trail).

## Imports and provenance

Confirmed unchanged by every new/modified code path: no test or
production line in this milestone writes `VisitModel.event_type`,
`review_status`, `reviewed_label`, or any source-attribution field for an
imported Visit. `event.event_type == "manual_media_import"` is asserted,
unchanged, in `test_superseded_imported_media_becomes_eligible_and_
purges_with_no_dangling_reference` after a full supersede→purge cycle.
Nothing in this milestone rewrites an imported Visit as camera-captured,
changes its truth class, or touches review state — this is storage
correctness only, exactly as scoped.

## Schema discipline

No schema change. All three fixes reuse existing columns and existing
states (`is_superseded`, `representative_media_path`,
`StorageCleanupBatchModel`/`ItemModel`'s existing state vocabulary,
`MAX_STORAGE_CLEANUP_HISTORY_ITEMS`) — the current data model already
fully supported the documented/intended behavior in all three cases; the
gap was in code, not in the schema. Schema remains `v58`.

## Validation

**Tier 1 (focused).** 17 new tests added to
[tests/test_storage_retention.py](../tests/test_storage_retention.py) (7
imported/folder retention, 5 staging cleanup batch, 4 cleanup history, 1
integrated). Full file: **39 passed, 0 failed.** RED confirmed via `git
stash push -u -- src/mockingbird/repository/product_repository.py`
(production fix removed, new tests kept): exactly the 12 tests targeting
the actual defects failed (3 Defect 1, 5 Defect 2, 3 Defect 3, 1
integrated); the 5 tests proving pre-existing "still protected while
active" behavior correctly passed in both states. `git stash pop`
restored the fix; GREEN reconfirmed (39/39).

**Tier 2 (affected subsystem).** Ran together: `test_cross_install_
backup_restore.py`, `test_doctor.py`, `test_doctor_camera_node_
transport.py`, `test_doctor_cli.py`, `test_folder_import.py`,
`test_folder_import_evidence_batch_create.py`,
`test_folder_import_evidence_batch_dry_run.py`,
`test_folder_import_media_assets.py`, `test_folder_import_motion_
evidence.py`, `test_folder_import_preview.py`, `test_folder_import_
provenance.py`, `test_local_backup_recovery.py`, `test_media_import.py`,
`test_motion_saved_media_api.py`, `test_review_queue_product_mode.py`,
`test_saved_media_bulk_evidence_creation.py`, `test_saved_media_
cleanup.py`, `test_saved_media_retention_report.py`, `test_storage_
retention.py`, `test_storage_retention_api.py`, `test_storage_retention_
service.py`, `test_storage_status_disk.py`, `test_visit_curation.py` —
**329 passed, 0 failed**, 124s. `ruff check` on both changed files: zero
findings, confirmed by direct clean-baseline bisection (`git stash` of
`product_repository.py` alone reproduces the identical 57 pre-existing,
unrelated findings this 42,600+-line file already carries — matching this
codebase's own established convention for this exact file).

**Tier 3 (full Core).** Run in full — this milestone's changes sit in
core retention/persistence logic (`product_repository.py`), not isolated
dev tooling, unlike the immediately-prior milestone's own Tier-3-omission
precedent, so the higher-confidence full run was warranted rather than
justified away. `scripts/verify_core.py` (`pytest -m "not slow"`): **5213
passed, 3 failed, 3 skipped, 23 deselected, 11 xfailed**, 2352s (39m12s).
All 3 failures independently confirmed unrelated to this milestone, not
merely assumed from precedent:

- `test_camera_node.py::test_picamera2_restoration_failure_keeps_
  evidence_and_lazily_recovers_monitoring` — passes cleanly both in
  isolation (1 passed) and as part of its full own file (39/39 passed,
  32s) — a full-suite-only flake (cross-file interference across 5000+
  tests), not deterministic, not reproducible standalone. This file does
  import `ProductRepository` (as almost every persistence test in this
  codebase does), so this was verified directly rather than dismissed by
  import-graph absence alone.
- `test_place_biodiversity_summary_repository.py::test_api_route_
  returns_the_summary` and `::test_human_correction_updates_place_
  biodiversity_intelligence_correctly` — fail **deterministically**, in
  isolation, with the identical assertion
  (`assert journal_b["historical_status"] == "new"` → actual
  `"seen_before"`) both with this milestone's fix applied and with it
  removed: the production file was temporarily swapped for the exact
  pre-fix (`8572308`) blob via `git show 8572308:...` (not `git stash`,
  since the fix is already committed), the two tests re-run identically
  failing, the post-fix file restored, and `git diff` confirmed a
  byte-exact restore (empty diff against `HEAD`) with the full
  `test_storage_retention.py` suite re-confirmed green (39/39)
  immediately after. A bird-species historical-status classification
  defect with zero code-path relationship to this milestone's own
  changes — the identical pair independently documented as pre-existing
  in at least two prior milestones' own Tier 3 runs (Non-Interactive
  Field Acceptance Authentication & Session Access v1; Concurrent
  Candidate Visit Persistence Reliability v1).

**Zero regressions attributable to this milestone**, confirmed directly,
not inferred from precedent alone.

**Precise sequencing note.** Tier 3's pytest process started at 21:47
and, as one long-running process, imported `product_repository.py`
exactly once at that time; a small, purely cosmetic cleanup a few
minutes later (removing an unused `now` keyword parameter from
`_storage_cleanup_finish_recoverable_item` -- present in the code Tier 3
was already running against, never read inside the function body in
either version, zero behavioral difference) landed in the 21:55:40
implementation commit Tier 3's own already-running process could not see.
That specific incremental change was independently re-verified separately
and faster instead of re-running the full 39-minute Tier 3 a second time
for a provably zero-risk difference (matching this milestone's own "do
not run duplicate long validation jobs" instruction): the full
`test_storage_retention.py` suite (39/39) and an 11-file, 226-test Tier 2
subset both re-run clean against the exact final, committed code
immediately after the cleanup, and `ruff check` reconfirmed zero new
findings.

## Remaining risks (concrete only)

- The pre-existing, already-disclosed structural gap — no code anywhere
  scans the media directory and cross-references it against the DB (a
  file with no DB owner is permanently invisible to every existing
  integrity/retention check) — is unaffected by this milestone, exactly
  as instructed. Not reopened.
- `restore_storage_cleanup_batch`'s own conflict-counting can label a
  `staging` item that was never actually moved (nothing to restore, no
  harm) as a "conflict" alongside genuine restore conflicts, landing the
  batch at `"restore_conflict"` instead of the more accurate `"restored"`
  — noticed during this investigation, cosmetic/accounting-only (no data
  loss, no lost file, purge already remains available from
  `"restore_conflict"` unchanged), pre-existing, untouched by this
  milestone, and not one of the three named defects — left exactly as it
  was, not fixed here.
- Abandoned `"previewed"`-state batches (a preview created but never
  executed or allowed to expire) are not addressed by the new history
  prune (by design — `storage_cleanup_history` itself already excludes
  `"previewed"` rows, matching the term's own established meaning in this
  codebase) and are not counted as part of Defect 3's own reproduced
  scope; a real, but separate and much smaller, potential future
  follow-on if ever shown to accumulate materially in practice.

## Decision: **A**

All three reproduced defects are closed: imported/folder-imported media
now follows the same documented active/superseded/reviewed contract as
any other Visit-linked evidence; abandoned `"staging"` cleanup batches
have a real, safe, idempotent, observable terminal-resolution path via
purge (restore remains available unchanged); `storage_cleanup_history`'s
underlying table is actually bounded, provably, at the exact points the
contract implies. Reviewed truth is unaffected. DB/media coherence holds
in both directions. Cleanup remains idempotent throughout, including every
new code path. The integrated, product-shaped scenario passes cleanly. No
schema change was needed. Tier 3 (full Core) confirms zero regressions
attributable to this milestone, directly verified rather than assumed.
