# Field-Acceptance Instance Lifecycle & Storage Safety v1: report

Classification: **A**

## Starting state

Verified before any work began:

- Branch: `main`.
- Accepted HEAD: `664bfbe` (the reconciliation commit accepting Host <->
  Camera Node Release-Compatibility Preflight v1; report commit `b39b414`,
  implementation commit `2e84227`) -- matches the governing brief's stated
  starting state exactly.
- Schema: `v58` (`CURRENT_DATABASE_SCHEMA_VERSION` in
  `src/mockingbird/storage/database.py`) -- unchanged by this milestone.
- `docs/release-execution-state.md` §3: **NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED** -- confirmed unchanged.
- `docs/release-execution-state.md` §6.R ("Complete Field Acceptance"):
  **NOT DONE -- RELEASE-CRITICAL** -- confirmed OPEN, matching the brief's
  "Gate A / Lane R: OPEN".
- §6.M ("Storage / Retention UX"): **CLOSED -- RELEASE-CRITICAL**
  (Storage / Retention / Disk-Pressure & Recovery Closure v1 +
  Retention Correctness & Bounded Cleanup Closure v1) -- confirmed
  accepted and frozen; not reopened by this milestone (see "Instance
  classification" below for the precise boundary this milestone respects).
- Not pushed (296 commits ahead of `origin/main` before this milestone's
  own commits).
- Worktree safety: the seven preserved untracked wildlife/training files
  named in the governing brief were confirmed present and untouched
  (identical mtimes) before and after this milestone's work; none were
  read, staged, or modified.

No discrepancy found -- proceeded as authorized.

## V8/V9 operational evidence

Direct quotes from the accepted record (see governing sources), establishing
the exact reproduced accumulation mechanism this milestone closes:

- Representative Daylight Gate A Field Acceptance v8 report: "storage
  headroom: materially constrained throughout... a previously-undiagnosed
  root cause of the 2026-08-28-disclosed storage decline... **every prior
  field-acceptance disposable instance was left running/retained
  indefinitely after acceptance, none ever cleaned up**... a final
  post-session state of **~3.5GB free** that needs attention before any
  near-term next session." Each of V4-V7 independently consumed
  ~8.0-8.7GB, "confirmed NOT shared across separate `--dev-root`
  instances, only across multiple releases *within* one instance."
- `docs/release-execution-state.md` (v8 reconciliation entry): "One real,
  previously-undiagnosed root cause was found for the storage decline...
  since 2026-08-28: every prior field-acceptance disposable instance was
  left running/retained indefinitely after acceptance, none ever cleaned
  up -- mitigated for this session via two user-approved decisions..."
- Representative Daylight Gate A Field Acceptance v9 report: "`C:` had only
  **~1.37GB free** at the start of this milestone, and a stale, still
  -running, idle `MockingBirdFieldAcceptanceV8` instance (commit
  `835f62f`, GPU-holding, not observing) was discovered -- exactly the
  'every prior disposable instance left running/retained indefinitely,
  never cleaned up' root cause v8's own report disclosed but did not act
  on." Resolved that session only via a manual, user-approved deletion of
  "four old disposable instances (V4/V5/V6/V8, ~65GB combined)."

This directly reproduces the milestone's own defect contract (§4): deploy
-> session completes -> evidence archived separately -> instance remains
-> next session hits severe storage pressure -> manual cleanup required
before the next run could safely start.

## Current lifecycle root cause

Traced by direct code reading (not assumed), across the two files that
govern the disposable-instance lifecycle:

1. **No standalone "stop" command existed.** `scripts/deploy_windows_dev.py`
   already had a safe, ownership-verified stop primitive,
   `stop_verified_deployment` (verifies the occupant of a port is a
   healthy MockingBird whose `git_commit`+`build_id` match an entry in
   *this* dev-root's own ledger before ever touching it), but it was only
   ever invoked *internally*, immediately before `deploy()`/`rollback()`
   launch a *different* release. There was no CLI path to just stop an
   instance and leave nothing running -- an operator's only options were
   "deploy something else on top" or "roll back to a previous release,"
   neither of which is "I am done with this session."
2. **No concept of "disposable" existed anywhere.** Confirmed by exhaustive
   grep: zero occurrences of `field_acceptance`/`disposable`-as-a-tracked
   -concept in `deploy_windows_dev.py` or its own design doc. The only
   Host-side "instance identity" concept in the whole codebase is
   `mockingbird.runtime_state.resolve_instance_id` -- a single random
   token per data directory, with no `purpose`, `created_at`, or
   `lifecycle_state` field at all (`ProductInstanceIdentity`:
   `instance_id`, `app_version`, `git_commit`, `build_id` only). Which
   `--dev-root` was "disposable" was pure, undocumented operator
   convention (a distinct directory name per field-acceptance session),
   invisible to any tool.
3. **No cross-instance cleanup existed.** `--cleanup`/`--keep`/`--gc-cache`
   (Storage / Retention / Disk-Pressure & Recovery Closure v1, already
   accepted and frozen) each operate on exactly *one* `--dev-root` at a
   time, trimming its own old release directories and unreferenced
   runtime/model/BioCLIP caches. Nothing anywhere enumerates or reasons
   about *multiple separate* disposable `--dev-root` directories --
   V4 through V9 were each an independent directory an operator chose ad
   hoc, and reclaiming a stale one required a human (or an agent acting
   for one) to manually stop the process and `rm -rf` the right directory
   by hand, with no tool-verified proof it was safe to do so.

Together, (1)+(2)+(3) are the complete, sufficient explanation for the
reproduced accumulation: nothing ever told an operator "this is a
disposable instance," nothing made stopping it a first-class action, and
nothing could safely tell them "this one is done with and safe to
delete" versus "this one still matters."

## Instance classification

Determined by direct reading, per the brief's §5:

- **Normal/persistent dev instance** (e.g. the operator's own
  `MockingBirdDev`): a `--dev-root` `deploy_windows_dev.py` has deployed
  into, *never* marked by this milestone's new manifest. Structurally
  indistinguishable from a disposable instance by directory shape alone
  (both have `releases/deployments.json`) -- the manifest is the only
  distinguishing fact, and its *absence* is itself meaningful: this tool
  never infers "disposable" from a directory name pattern (e.g. it does
  not treat `MockingBirdFieldAcceptanceV9` as disposable merely because of
  its name), matching the brief's explicit "do not infer 'disposable'
  merely from directory age or name pattern" instruction.
- **Disposable field-acceptance instance**: a `--dev-root` carrying a
  valid, self-identity-matching `field_acceptance_manifest.json` (new,
  this milestone).
- **Cached runtime/model assets**: `runtime/`, `models/`, `bioclip-models/`
  -- always nested *inside* one `dev_root`, confirmed (by direct code
  reading of `deploy()`, `scripts/deploy_windows_dev.py`) never shared
  *across* separate `--dev-root` directories, and confirmed by V8's own
  report ("NOT shared across separate `--dev-root` instances") to be real
  -world true, not merely a code-reading inference.
- **Acceptance evidence archive**: `data/field-acceptance/<date>-<slug>/`
  -- this repository's own established, gitignored convention (already in
  use for V4 through V9), external to any dev-root, populated entirely by
  hand/agent action today (no automated archival mechanism exists
  anywhere in the repo -- confirmed by grep).

No explicit distinction existed before this milestone; the smallest
release-tooling marker needed is exactly the new sidecar manifest below --
no SQL schema change, no product-code change.

## Lifecycle contract

Three durable states, stored in a new sidecar manifest
(`field_acceptance_manifest.json`, written by
`scripts/field_acceptance_instance_lifecycle.py`, sitting beside
`deploy_windows_dev.py`'s own `deployments.json`/`current.json` --
deliberately never a change to that file's own schema or code path):

```
active -> completed -> archived
```

- **active**: `init --dev-root <root>` creates the manifest right after a
  field-acceptance deploy. Refuses (i) a directory with no
  `deployments.json` (not a real deploy-tool root), (ii) the default,
  shared, persistent `%LOCALAPPDATA%\MockingBirdDev` root by name (an
  extra, redundant guard beyond the ledger check), and (iii) silently
  overwriting an existing manifest without an explicit `--force`.
- **completed**: `complete --dev-root <root>` transitions active ->
  completed *only* after a fresh, live re-probe (never a cached fact)
  confirms the deployed process is not running. Refuses otherwise, naming
  the exact command to run first (`deploy_windows_dev.py --dev-root
  <root> --stop`, new this milestone).
- **archived**: `mark-archived --dev-root <root> --evidence-archive
  <path>` transitions completed -> archived only after
  `verify_archive_contract` confirms the given path contains, recursively,
  at least one written report/provenance file (any `*.md`) and at least
  one raw evidence/accounting data file (any non-Markdown file) --
  refusing an empty or placeholder directory outright, never assuming one
  fixed filename (real archived tranches under `data/field-acceptance/`
  vary: `PROVENANCE.md` vs `*-report.md`, `counterfactual-FINAL.json` vs
  `v8-counterfactual-FINAL.json`, etc.).

`SAFE_TO_RECLAIM` is deliberately **not** a fourth stored state -- see
"Archive/reclaimability contract" below.

## Archive/reclaimability contract

**Critical invariant, upheld structurally, not merely by convention:**
"stopped" is never, by itself, treated as "safe to delete." A dry-run
assessment (`assess`) recomputes the verdict fresh every time from three
independently-checked facts -- manifest state, a live process re-probe,
and (best-effort) a live per-Stream Observation-active check -- never from
a cached/stored "reclaimable" flag. Verdicts:

- `NOT_RECLAIMABLE_UNKNOWN_INSTANCE`: no valid, self-identity-matching
  manifest here (covers an unmarked directory, a normal/persistent
  instance, and a manifest whose own recorded `dev_root` does not match
  where it is actually sitting -- e.g. a copied/relocated manifest).
- `NOT_RECLAIMABLE_ACTIVE`: the deployed process is still running (a live
  re-probe via the exact same ownership-verification `stop_verified_
  deployment` already trusts, `probe_port`+`verified_owning_release`),
  regardless of manifest state -- a manually-relaunched process after
  archiving is caught here, not assumed away.
- `NOT_RECLAIMABLE_UNARCHIVED`: not running, but the manifest is not yet
  `archived` -- with a reason string that distinguishes "never marked
  complete (possible crash/interruption)" from "completed, evidence not
  yet verified."
- `SAFE_TO_RECLAIM`: not running (re-verified just now) *and* archived
  (evidence-contract-verified at `mark-archived` time).

## Storage preflight

Two layers, deliberately not one duplicated implementation:

1. **`deploy_windows_dev.check_storage_headroom`** (new, additive):
   fires on *every* `deploy()` call (ordinary dev iteration included, not
   only a marked field-acceptance instance -- it has no knowledge of the
   manifest concept at all, by design, to avoid a circular dependency
   between the two sibling scripts). Placed at the exact same "fail fast
   before any build/materialize work" point as the pre-existing
   `_validate_host_port` immediately above it. Free bytes on the target
   volume vs. `acceptance_recorder_max_bytes` (conservatively defaults to
   the recorder's own hard 5GB ceiling -- see below) plus a reserve
   (mirrors the product's own already-accepted `action_recommended`
   1GB/5% boundary, `src/mockingbird/storage/database.py`, never a new
   arbitrary number). Skippable via `--skip-storage-preflight` for the
   rare case an operator wants to proceed anyway.
2. **`field_acceptance_instance_lifecycle.py preflight`** (new): the
   fuller report, additionally scanning sibling directories under
   `%LOCALAPPDATA%` for other marked, `SAFE_TO_RECLAIM` disposable
   instances and reporting their combined reclaimable bytes -- exactly
   the "Z GB safely reclaimable from completed disposable instances" field
   the brief's §17 example message names.

Both report free bytes **and** the graduated healthy/getting_low/
action_recommended/critical tier (mirroring `LocalStorageDiskStatus.
storage_health_tier` verbatim, never percentage-only -- the previous
sessions' own real evidence, `~1.37GB` on a large volume, is exactly the
"percentage can be misleading on large volumes" case the brief warns
about).

**Recorder budget:** `ACCEPTANCE_RECORDER_HARD_CEILING_BYTES = 5_000_000_000`
mirrors `AcceptanceRecorderConfig.__post_init__`'s own hard ceiling
(`src/mockingbird/observation/acceptance_recorder.py`) exactly, as a
literal (this script never imports `mockingbird`, matching
`deploy_windows_dev.py`'s own established convention) -- kept in sync by
comment, the same "duplicated as a literal" precedent `mockingbird.
runtime_state`'s own `BUILD_INFO_FILENAME` comment already establishes.
Both `check_storage_headroom` and `preflight` reject a requested
`--recorder-max-bytes`/`--acceptance-recorder-max-bytes` above this
ceiling outright (it would already be rejected at session-start time by
the recorder itself). No exact byte count is ever promised -- only a
conservative worst-case budget.

## Cleanup safety

`cleanup --dev-root <root>` is dry-run by *default*; `--destroy` is
required, explicitly, for removal. The dry-run plan and the destructive
path share the exact same underlying assessment (`plan_cleanup`), so a
dry-run can never under- or over-report relative to what `--destroy`
would actually do.

Immediately before the one and only destructive filesystem call in this
whole tool, `execute_cleanup` **redundantly re-verifies everything from
scratch** (never trusting the plan computed a moment earlier): the
deny-list/root-safety check, the ledger-file existence check, the
manifest identity match, a fresh not-running re-probe, and a bounded
top-level symlink/junction-escape scan. Only then does it call
`deploy_windows_dev.py`'s own already-hardened `WindowsHost.remove_tree`
(native `cmd.exe /c rmdir /s /q`, never a naive recursive Python delete or
PowerShell `Remove-Item -Recurse` -- reused, not reimplemented).

Refused, and tested (Tier 1, "Cleanup"/"Identification"):

- an unmarked/unknown directory (including a real, persistent instance
  with its own `deployments.json` but no manifest);
- a manifest whose recorded identity does not match its actual location;
- a running instance (including one that started running *again* after
  being archived -- a fresh re-probe, not the stored manifest, decides);
- a top-level symlink/junction pointing outside the target root;
- the filesystem root, the home directory, `%LOCALAPPDATA%` itself, the
  real production install root, and the shared persistent
  `MockingBirdDev` root, all by explicit deny-list, independent of
  whatever a manifest might claim.

Double-`--destroy` is idempotent and safe: the second call finds no
manifest (the directory is gone) and reports `NOT_RECLAIMABLE_UNKNOWN_
INSTANCE`, cleanly, with no exception and no effect on anything else.

## Cache behavior

This milestone's cleanup removes **only per-instance data**. Confirmed
structurally (direct reading of `deploy_windows_dev.deploy`):
`RUNTIME_CACHE_DIRNAME`/`MODEL_CACHE_DIRNAME`/`BIOCLIP_MODEL_CACHE_DIRNAME`
are always nested *inside* the `dev_root` being deployed to, never a path
outside it -- and confirmed by real field evidence (the V8 report's own
words: "confirmed NOT shared across separate `--dev-root` instances, only
across multiple releases *within* one instance") that no *other*
dev-root, and never the real production install, references them.
Removing one disposable instance's entire tree therefore never touches
any other instance's cache -- proven directly by a dedicated test
(sibling dev-roots, each with populated fake cache content; destroying one
leaves the other's cache files byte-for-byte intact) and by the real
-Windows proof below.

The pre-existing, already-accepted `deploy_windows_dev.py --cleanup
--keep`/`--gc-cache` remain the correct, unduplicated path for trimming an
*active/persistent* dev-root's own internal release history without
deleting the whole root -- this milestone's cleanup command is orthogonal
to, and does not reimplement, that logic.

## Interrupted-session behavior

A crash is handled correctly by construction, not by a special case: the
lifecycle-state machine has no transition that ever reaches `archived`
except through an operator's explicit `mark-archived` call, which itself
requires `completed`, which itself requires an operator's explicit
`complete` call after a verified stop. A process that simply disappears
(crash, forced kill, host power loss) leaves the manifest at whatever
state an operator last explicitly set it to -- `active`, if nothing had
happened yet. `assess` reports this precisely
(`NOT_RECLAIMABLE_UNARCHIVED`, reason: "this can mean a crash or an
interrupted session... stays non-reclaimable until an operator
deliberately resolves evidence disposition"), never silently promoting it
toward reclaimable.

## Windows proof

Real, end-to-end, against the actual reference native-Windows dev host
(the same box every prior Gate A field session used). Re-verified working
Windows/WSL interop first (`powershell.exe` reachable). Real state before
touching anything, via a native `Get-ChildItem -Recurse` byte-aggregation
(mirroring the storage-retention closure's own precedent method):
`MockingBird` (production) 1,189,192 bytes; `MockingBirdDev` (operator's
persistent instance) 29,197,155,789 bytes; `MockingBirdFieldAcceptanceV9`
7,284,287,354 bytes; `MockingBirdFirstHourAcceptance` 2,518,529,701 bytes;
26.8GB free on `C:` of a ~499GB volume -- a genuinely, currently
storage-constrained real machine, not a synthetic scenario. Port 8000 was
occupied by the operator's own `MockingBirdDev` (commit `6045228`,
confirmed by reading its own `current.json`) -- stopped safely via the
new `--stop` flag (`Stopped 6045228 (verified).`) before this proof, and
fully restored afterward (see below), following the exact stop-then
-restore choreography already established and repeatedly used by prior
accepted milestones against this same shared instance. Never touched: any
historical field-acceptance root's own evidence disposition (v9's root
was left completely alone throughout, per the brief's own explicit
instruction not to test deletion against it).

A fresh, purpose-created disposable instance
(`MockingBirdLifecycleProofV1`, `--skip-gpu-runtime --skip-bioclip-runtime`
for speed -- this proof is about lifecycle mechanics, not detection
quality, and no wildlife/Camera Node activity was involved anywhere in
this milestone) was deployed and driven through the complete lifecycle:

1. **Identify**: `init --dev-root ...` -- real manifest written with the
   real deployed commit (`664bfbedd5814b1ba9af2b24b712db5eb8c18c7d`,
   this milestone's own starting HEAD) and build id, read back correctly.
2. **Storage measure**: `assess` while running reported real, correct
   `size_on_disk_bytes: 2519387880` (matches a native
   `Get-ChildItem -Recurse` count of the same tree, `2519388357` bytes,
   to within a few hundred bytes of in-flight logging/manifest writes)
   and the correct `NOT_RECLAIMABLE_ACTIVE` verdict.
3. **Graceful stop**: `deploy_windows_dev.py --dev-root ... --stop`
   reported `Stopped 664bfbe (verified).`; a fresh `assess` immediately
   confirmed `process_running: false`.
4. **Reclaimability dry-run before archiving**: `assess` correctly
   reported `NOT_RECLAIMABLE_UNARCHIVED` ("never marked 'completed' --
   this can mean a crash or an interrupted session") -- proving the
   "stopped != safe to delete" invariant against a real stop performed
   outside this tool's own `complete` command, exactly the real-world
   sequence an operator might actually follow.
5. `complete` transitioned active -> completed (verified: the fresh
   re-probe genuinely found nothing running).
6. Minimal synthetic evidence (a `PROVENANCE.md` and a
   `counterfactual-FINAL.json`, explicitly marked synthetic/no real field
   session, per the brief's own "minimal synthetic acceptance evidence
   according to test contract" allowance) was written and
   `mark-archived --evidence-archive <path>` succeeded.
7. `assess` now reported `SAFE_TO_RECLAIM`, `reclaimable_bytes:
   2519388357` -- exactly matching the independent native
   `Get-ChildItem -Recurse` count for that same directory at that moment.
8. `cleanup` (dry-run, default) listed the exact six top-level entries
   (`bioclip-models`, `field_acceptance_manifest.json`, `models`,
   `releases`, `runtime`, `userdata`) and deleted nothing -- confirmed via
   a real `ls` immediately after.
9. `cleanup --destroy` actually removed the instance
   (`destroyed: true`) -- confirmed gone via a real `ls` (`No such file or
   directory`).
10. **Shared/sibling instances confirmed byte-for-byte untouched**, via
    the same native byte-aggregation re-run immediately after: `MockingBird`
    1,189,192 bytes (unchanged), `MockingBirdDev` 29,197,155,789 bytes
    (unchanged), `MockingBirdFieldAcceptanceV9` 7,284,287,354 bytes
    (unchanged), `MockingBirdFirstHourAcceptance` 2,518,529,701 bytes
    (unchanged). Real free space on `C:` rose from 24,460,832,768 to
    27,065,106,432 bytes -- a genuine ~2.43GB reclaimed, closely matching
    the tool's own reported `2,519,388,357`-byte figure (the small
    difference is ordinary filesystem allocation-unit/metadata overhead,
    not a discrepancy in what was removed).
11. **Idempotent double-cleanup**: a second `cleanup --destroy` against
    the now-gone root correctly reported `NOT_RECLAIMABLE_UNKNOWN_
    INSTANCE`, `destroyed: false`, exit code 1 -- no crash, no effect on
    anything else.
12. **Wrong-target refusal against a real, large, persistent instance**:
    `init --dev-root <MockingBirdDev>` was refused immediately by the
    explicit deny-list ("Refusing to operate on the shared persistent dev
    root... a disposable field-acceptance instance must use a distinct
    --dev-root"); `cleanup --destroy --dev-root <MockingBirdDev>` was
    refused too (`NOT_RECLAIMABLE_UNKNOWN_INSTANCE` -- no manifest there),
    and a direct read of `MockingBirdDev`'s own `releases/current.json`
    immediately after confirmed it was never touched.

**One real defect found and fixed by this exact proof, not by unit
testing** (unit-test fixtures are necessarily small, so this class of
issue could not have been found there): the wrong-target refusal in step
12 against the real, ~29GB, many-release `MockingBirdDev` initially took
**over two minutes** (the command was killed after exceeding a 120s bound,
confirmed via `ps` to still be in disk-wait, not hung/crashed) before it
would have eventually produced the correct refusal. Root cause: `assess_
instance` unconditionally computed a full recursive `directory_size_bytes`
walk *before* checking whether the manifest identity was even confirmed --
against a small disposable instance (a few thousand files) this is fast;
against a large, long-lived, many-release persistent dev-root's many tens
of thousands of files, accessed through the WSL<->Windows filesystem
bridge (already independently documented elsewhere in this codebase as
comparatively slow for this exact kind of cross-boundary access), it is
not. **Safety was never at risk** -- this code path was always going to
correctly refuse regardless of how long the walk took -- but a
correctness-preserving performance defect all the same. Fixed by
reordering: the identity check now runs strictly before any filesystem
walk, so an unrecognized/wrong-target directory gets an answer in
milliseconds regardless of its size. Re-verified against the same real
`MockingBirdDev` directory after the fix: **0.104 seconds**, identical
correct refusal. A regression test (`test_assess_never_walks_the_
filesystem_for_an_unrecognized_directory`) locks this in by asserting
`directory_size_bytes` is never even called on this path.

Finally, `MockingBirdDev` was restored to its exact original running
state -- not via a rebuild (which would have cost real time against this
milestone's own already-demonstrated storage constraints), but via a
direct call to `deploy_windows_dev.py`'s own already-materialized-release
`launch_release` primitive (no new mechanism; the release directory and
`userdata/` were never touched by anything in this proof). Verified
identical to the pre-proof state via a direct, authenticated-free
`GET /api/product/instance`: `instance_id` `19280dbc9f60ebf0cc8fc4425390b891`
(proves the *same* `userdata/` directory -- this token lives inside it and
is never regenerated for an existing installation), `git_commit`
`60452283566206e0a53410c0d5633957b54addad`, and `build_id`
`2e28160cefef4db6` -- all three exactly matching what was running before
this proof began.

## Local Only

No cloud service, remote registry, or telemetry dependency anywhere in
this milestone. Every lifecycle decision is made from local filesystem
state (the manifest sidecar file, the dev-root's own on-disk size) and, at
most, a local HTTP call to `127.0.0.1:<port>` for the best-effort
Observation-active enrichment -- confirmed by direct code reading: neither
`scripts/field_acceptance_instance_lifecycle.py` nor its one new addition
to `scripts/deploy_windows_dev.py` imports any network client other than
what `deploy_windows_dev.py`/`field_acceptance_client.py` already used
(both already-accepted, already-local-only).

## Security/path safety

Every destructive operation resolves the target path canonically
(`Path.resolve()`, following symlinks and normalizing `..`) before any
comparison or deletion, and defends against exactly the classes the brief
names:

- **`..`/relative-path tricks**: neutralized by `.resolve()` before any
  comparison.
- **Root-drive/parent-of-instance targeting**: an explicit deny-list
  (filesystem root, home directory, `%LOCALAPPDATA%` itself, the real
  production install root, the shared persistent dev root) checked before
  anything else, redundantly re-checked immediately before deletion.
- **Mismatched marker/root identity**: the manifest's own recorded
  `dev_root` field must equal the resolved target path exactly; a
  manifest copied from elsewhere, or read through a symlink pointing at a
  different real location, fails this check and is refused
  (`NOT_RECLAIMABLE_UNKNOWN_INSTANCE`).
- **Symlink/junction escape**: a bounded, top-level scan
  (`_find_escaping_links`) refuses to proceed if any direct child of the
  target root is a symlink/junction resolving outside it.
- **Delegated, not reimplemented, actual removal**: the one destructive
  filesystem call is `deploy_windows_dev.py`'s own already-hardened
  `WindowsHost.remove_tree` (native `cmd.exe /c rmdir /s /q`), never a
  second, independently-written recursive delete.

**Disclosed, not fully eliminated, residual risks** (both safe-direction,
neither found to be exploitable toward accidental deletion of the wrong
target):

- **Case-insensitive path comparison.** NTFS (accessed here via WSL's
  `/mnt/c/...` bridge) is case-insensitive but case-preserving; Python's
  `Path.resolve()` does not normalize casing to whatever is actually on
  disk. Two different-cased references to the same real directory can
  therefore produce two different resolved path *strings*, which would
  make the manifest-identity check fail closed (refuse, treating it as
  `NOT_RECLAIMABLE_UNKNOWN_INSTANCE`) rather than proceed -- the safe
  direction of failure, never the dangerous one (there is no path by
  which a casing difference could make two genuinely *different*
  directories compare as equal, since the manifest read back is always
  the one physically sitting at the resolved path itself).
- **WSL-side junction resolution.** `deploy_windows_dev.py`'s own
  `_remove_junction_real` docstring already documents that WSL-side path
  resolution can, in this exact environment, silently resolve *through* a
  real Windows reparse point. `_find_escaping_links`'s Python-level
  pre-scan is therefore a best-effort sanity check, not a guarantee for a
  real NTFS junction (as opposed to a POSIX symlink, which the pre-scan
  does correctly detect and was directly tested) -- the actual safety
  backstop is that the real deletion always delegates to the same
  already-hardened native `remove_tree` primitive `deploy_windows_dev.py`
  itself already trusts for this exact class of hazard, never a
  from-scratch implementation.

## Performance

No product-facing performance change (zero product code touched). The new
tooling's own operations are all either O(1) JSON reads/writes or a single
bounded filesystem walk (`directory_size_bytes`, `verify_archive_contract`)
of the one instance root/evidence archive being inspected -- never a
recursive scan of an unrelated tree. `preflight`'s sibling scan is
bounded to one directory level under `%LOCALAPPDATA%` and, deliberately,
skips the best-effort Observation-active HTTP enrichment for each sibling
(`check_observation=False`) to keep a preflight check fast and side
-effect-light; that enrichment only ever adds value for the *one* instance
an operator is actively assessing (`assess`/`status`), where it is on by
default.

## Validation

**Tier 1** (this milestone's own new/changed files): 170 tests, 0
failures --

- `tests/test_field_acceptance_instance_lifecycle.py`: 37 new tests
  (36 from initial design, plus one regression test added after the real
  -Windows proof found and fixed a performance defect -- see "Windows
  proof"), covering the full matrix the governing brief's §29 names:
  identification (marked/ordinary/unknown), lifecycle (active/completed/
  archived/interrupted), cleanup (dry-run/destroy/wrong-target/double
  -destroy/path-escape/deny-list), storage (sufficient/insufficient/
  reclaimable-bytes/recorder-ceiling), cache separation, the V8/V9
  accumulation reproducer (§26), and the stale-still-running reproducer
  (§27), plus a dedicated CLI-level (`main()`) section covering argument parsing,
  dispatch, and exit-code conventions.
- `tests/test_deploy_windows_dev.py`: 133 tests (125 pre-existing + 8 new),
  0 regressions -- new coverage for `--stop`'s CLI dispatch,
  `check_storage_headroom`'s pass/fail/ceiling-rejection/exact-message
  behavior, the real, previously-hit "early-bound default argument"
  gotcha (fixed and regression-tested: the default `disk_usage_fn` is now
  resolved fresh per call, so a real `monkeypatch.setattr(shutil,
  "disk_usage", ...)` on the actual stdlib module takes effect), and
  `deploy()`'s own fail-fast integration point (mocked at the seam, not
  re-deriving real disk pressure in a test).
- `ruff check` on every new/changed file: **zero findings** (not merely
  zero *new* findings relative to a baseline -- an absolute zero, a
  strictly stronger result).

**Tier 2** (directly relevant surface named in the brief's §30), run in
full, 0 regressions across 147 additional tests: `test_acceptance_
recorder.py`, `test_field_acceptance_authentication.py`, `test_storage_
retention.py`, `test_storage_retention_api.py`, `test_storage_retention_
service.py`, `test_storage_status_disk.py`, `test_node_compatibility.py`,
`test_node_compatibility_api.py` (113 tests), plus `test_observation_
session_api.py`/`test_observation_unified_api.py` (34 tests, covering the
`observation/status` endpoint this milestone's own best-effort
Observation-active check reads). None of these files were modified; each
was run to directly confirm the surface this milestone's new code *reads*
(recorder config bounds, storage-health thresholds, the Observation
-status API) is still exactly as this milestone's own mirrored constants
and best-effort HTTP client assume. Combined Tier 1 + Tier 2: **317 tests,
0 failures.**

**Tier 3**: correctly not run, per this milestone's own explicit §31
instruction and decision criterion. Zero `src/mockingbird/` files were
changed by this milestone -- confirmed by `git diff --stat` against the
starting HEAD, showing only `scripts/field_acceptance_instance_
lifecycle.py` (new), `scripts/deploy_windows_dev.py` (additive), two test
files, and documentation. No production runtime/storage behavior changed;
Tier 3 is not warranted.

## Remaining release-operational gaps

Disclosed, not fixed here (out of this milestone's bounded scope):

- No automated archival mechanism exists anywhere in the repo for the
  counterfactual-ledger/accounting/pixel-crop evidence a field report
  needs -- every real tranche under `data/field-acceptance/` today is
  assembled by hand/agent action. `mark-archived`'s own contract check is
  a verification gate over whatever an operator assembled, not a
  generator of the archive itself. A future milestone could bound this
  further (e.g. a single command that fetches/merges the counterfactual
  ledger and writes the PROVENANCE.md automatically) -- not attempted
  here, per the brief's own "do not build a general disk cleaner" and
  "narrow field-acceptance cleanup operation" scope.
- `main()`'s own `args.dev_root.resolve()` in `deploy_windows_dev.py`
  still performs no sanity check that the *deploy* target itself isn't a
  filesystem root/home directory/production install -- a real,
  pre-existing gap this milestone's own research surfaced but which is
  out of scope to fix (this milestone's own new path-safety hardening
  lives entirely in the *new* destructive-cleanup path, which is the
  actually dangerous operation; `deploy()`'s own existing operations are
  already narrowly scoped to specific named subdirectories, never a
  whole-root delete, so this is a lower-severity, disclosed-not-fixed
  observation, not a regression this milestone introduced).
- Case-insensitive path-identity comparison (see "Security/path safety")
  remains a known, safe-direction limitation.

## Decision

**A.**

- Repeated v8/v9 accumulation class reproduced (documented above with
  direct quotes) and its exact mechanism root-caused by code reading, not
  assumed.
- Explicit disposable-instance identity exists (`field_acceptance_
  manifest.json`), durable, self-verifying, and structurally incapable of
  being satisfied by an ordinary/unmarked/normal-product directory.
- Normal/persistent product instances cannot be reclaimed through this
  path -- tested directly, and independently reinforced by an explicit
  deny-list refusing the shared `MockingBirdDev` root and the real
  production install root by name.
- Active/running and unarchived instances fail closed -- tested for both
  the ordinary case and the "process relaunched after archiving" edge
  case.
- A stopped-and-archived disposable instance is correctly identified as
  reclaimable, with real reclaimable-byte accounting.
- Cleanup is explicit (`--destroy` required) and dry-run-capable by
  default, sharing one code path so the two can never diverge.
- Path safety is robust against every class the brief names, with two
  disclosed, safe-direction residual limitations (not exploitable toward
  wrong-target deletion).
- Shared caches are confirmed structurally per-instance (never actually
  shared across dev-roots); the pre-existing, accepted `--gc-cache`/
  `--cleanup` remain the correct, un-duplicated path for their own
  separate concern.
- Storage preflight accounts for the recorder/session budget using the
  product's own already-accepted thresholds, never invented numbers.
- Insufficient storage blocks *before* the expensive build/deploy step,
  integrated directly into `deploy()`'s own existing fail-fast pattern.
- Real native-Windows lifecycle proof succeeded end to end (see "Windows
  proof" above), including a real destructive cleanup against a
  purpose-created disposable instance with synthetic evidence, with the
  operator's own persistent instance and other historical instances
  confirmed byte-for-byte untouched, ~2.43GB of real disk space genuinely
  reclaimed, and the operator's environment fully restored afterward. The
  same real proof found and fixed one genuine defect a small-fixture unit
  test could not have surfaced (a multi-minute wrong-target refusal
  against a real 29GB persistent instance, fixed to 0.1 seconds, safety
  never at risk) -- exactly the kind of finding real-hardware acceptance
  is for, and now regression-tested.
- No ordinary product retention/disk-pressure behavior changed -- zero
  `src/mockingbird/` files touched.
- Tier 1 clean (170/170), Tier 2 clean (0 regressions across the directly
  relevant surface), Tier 3 correctly not run per this milestone's own
  documented decision criterion.
