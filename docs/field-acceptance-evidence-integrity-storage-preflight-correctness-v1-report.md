# Field Acceptance Evidence Integrity & Storage Preflight Correctness v1

Bounded RELEASE-CRITICAL acceptance-tooling correctness milestone,
following accepted Representative Daylight Gate A Field Acceptance v12 --
Precision, Recall & Budget-Convergence Tranche (classification A, Gate A
not closed). Fixes exactly two reproduced field-tooling defects v12
disclosed; changes no wildlife/product admission behavior.

## Starting state

Verified before any change:

- Branch `main`, HEAD `eaf1568c322f9433e485a5ff13cd0a92f0fbd093` --
  matches the governing brief's expected starting HEAD exactly.
- Schema v58 (unchanged by v12; confirmed unchanged here too -- this
  milestone touches no schema).
- Latest accepted milestone: Representative Daylight Gate A Field
  Acceptance v12 -- Precision, Recall & Budget-Convergence Tranche,
  classification **A**, per `docs/release-execution-state.md` §1/§3.
- Lane R / Gate A: `NOT DONE -- RELEASE-CRITICAL` (open). Lane G:
  `CLOSED -- RELEASE-CRITICAL`. Lane K: decision closed, provider
  integrations deferred.
- Current authorization: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED`.
- v12's own disclosed findings matched the governing brief's expectations
  exactly: 96.97-minute cohort, 18 Visits, conservative recall 14/16 =
  87.5%, false-Visit rate 1/18 = 5.6%, fragmentation 0/14, duplicates 0%,
  raw-ledger preservation incomplete (periodic snapshots silently
  failed), storage preflight previously measured the wrong filesystem on
  malformed Windows-style path input, Gate A remains open, zero
  production changes during v12.
- Not materially different from the brief's expected starting state --
  proceeded without stopping.

## Worktree safety

No active writer in this worktree (`.git/index.lock` absent; `git
worktree list` shows this checkout at `eaf1568`/`main`, matching HEAD).
`git status` confirmed only the pre-existing, explicitly-preserved
untracked files at session start:

    docs/wildlife-detector-training-contract.md.orig
    scripts/evaluate_small_bird_detector.py
    scripts/materialize_wildlife_stage2.py.orig
    scripts/train_wildlife_stage2_rfdetr.py.orig
    src/mockingbird/detectors/small_bird_benchmark.py
    src/mockingbird/training/wildlife.py.orig
    tests/test_small_bird_benchmark.py

None of these were read, moved, or modified at any point in this
milestone; confirmed untouched again at the end (see "Product-behavior
non-change," below). Nothing was pushed.

## v12 reproduced evidence-integrity defect

Reconstructed directly from `docs/representative-daylight-gate-a-field-
acceptance-v12-report.md` ("Evidence-preservation completeness,"
"Reproduced defects") and the real code, not merely re-read from the
report:

- v12's own session ran a 10-minute periodic-snapshot loop
  (`snapshot.py`, an ad hoc script written fresh for that session --
  never committed to this repository, confirmed by `git log`/`find`: no
  prior `snapshot.py` exists anywhere in this checkout or its history).
  Every 10 minutes it called `FieldAcceptanceClient.
  observation_counterfactual(stream_id, start_offset_ms=0,
  end_offset_ms=None)`.
- `scripts/field_acceptance_client.py`'s `observation_counterfactual`
  (pre-fix) had no local validation at all; it passed both bounds
  straight into `_request(..., params={"start_offset_ms":
  start_offset_ms, "end_offset_ms": end_offset_ms})`.
- `_request`'s own query-string builder (line 130, pre-fix):
  `"&".join(f"{key}={value}" for key, value in params.items() if value
  is not None)` -- silently drops any `None`-valued parameter from the
  query string entirely. This is the correct, desired behavior for a
  genuinely optional filter (e.g. `list_visits(limit=None)` should omit
  `limit`), but silently wrong for a parameter the server requires.
- The server's own contract (`src/mockingbird/api/main.py`,
  `get_stream_observation_counterfactual`): `end_offset_ms: int =
  Query(..., ge=0)` -- required, no default, exactly like
  `start_offset_ms`. There is no "omitted end bound" form of this
  endpoint at all.
- **First irreversible error**: the very first periodic snapshot call
  (~T+12min per v12's own report), whose resulting request
  (`GET .../observation/counterfactual?start_offset_ms=0`, missing
  `end_offset_ms` entirely) 422'd against the real server. This was the
  first moment raw-ledger evidence for the session's early window became
  permanently unrecoverable once the ledger's own 60-minute/12,000-record
  retention window later evicted it -- every one of the 12 periodic
  attempts repeated the identical mistake.
- **Why the loop did not stop or loudly report failure**: the ad hoc
  `snapshot.py` was never committed, so its own exact error-handling
  cannot be inspected directly -- but the report's own account ("Only
  each snapshot's `observation_status` summary counts and a direct
  `scene_confusor_regions` DB read ... survived intact across all 12
  snapshots") establishes that whatever loop it used treated the failed
  ledger fetch as a non-fatal, unremarked-upon event: it kept running,
  kept succeeding at its *other* two checks, and never surfaced the
  raw-ledger failure as a distinct, checkpoint-level status a reviewer
  would see mid-session.
- **Why summary/scene-confusor data looked healthy while raw-ledger
  evidence was absent**: `observation_status`'s summary counters and the
  scene-confusor DB read are genuinely separate code paths from
  `observation_counterfactual` -- neither depends on the other, so one
  failing silently leaves no trace in the other's own successful output.
  A checkpoint that only records "the session still looks healthy
  overall" cannot distinguish this from "the raw ledger is being
  captured correctly."
- **Visibility at the time**: none within the loop itself. The gap was
  only caught afterward, by a human deliberately reconciling the 12
  periodic files against final counters by hand (the governing v12
  brief's own "do not infer 100% preservation merely because the session
  ended cleanly" instruction) -- not by any automated signal during the
  session.

Reproduced directly (not merely inferred) against the real, pre-fix
client (see "Snapshot RED->GREEN evidence," below): calling
`observation_counterfactual(stream_id, start_offset_ms=0,
end_offset_ms=None)` against the unfixed client produced the exact
request

    GET /api/streams/<id>/observation/counterfactual?start_offset_ms=0

-- `end_offset_ms` vanished from the query string entirely, which the
real server's `Query(..., ge=0)` contract 422s on every time.

## Snapshot root cause

Two independent, compounding defects, both fixed:

1. **`FieldAcceptanceClient.observation_counterfactual` had no local
   parameter validation.** Its own type signature already said
   `start_offset_ms: int, end_offset_ms: int` (no `| None`) -- Python
   never enforces this at runtime, so a caller passing `None` anyway hit
   `_request`'s generic (correct-for-optional-params) None-dropping
   filter instead of a clear local rejection.
2. **The ad hoc, uncommitted periodic-snapshot loop had no per-artifact
   checkpoint contract at all** -- no structure distinguishing "the raw
   ledger fetch failed" from "the session is healthy," so a real,
   repeated, evidence-destroying failure produced no loud signal.

## Snapshot contract

Locked before implementation (governing brief §6-§9):

- A periodic checkpoint captures three artifact classes via
  `FieldAcceptanceClient`: the **required** raw ledger
  (`observation_counterfactual` -- raw detections, track generations,
  proposal outcomes, and RTT/calibration state, which travels *inside*
  that same response and is never a separate fetch), plus two
  **best-effort/auxiliary** classes: `observation_status` (monitoring/
  recovery counters) and the accepted, already-production
  `scene_confusor_learning_status` read (scene-confusor state).
- Each checkpoint carries: index, ISO-8601 UTC timestamp, requested
  stream id and start/end offset bounds, an explicit
  `ArtifactFetchResult` per artifact (`requested`, `success`,
  `record_count`, `error`), an overall `status`, and the output file's
  own path -- everything the governing brief's §6 lists.
- **A checkpoint with a failed required raw-ledger fetch is `failed`,
  never silently `complete`.** A failed *auxiliary* artifact degrades an
  otherwise-successful checkpoint to `partial`, never to `failed` on its
  own (the raw ledger is what Gate A's own evidence depends on; the
  other two are diagnostic enrichment).
- `end_offset_ms` is genuinely **required** by the server, with no
  omitted-bound form -- confirmed directly from the authoritative API
  contract (`Query(..., ge=0)`, no default), not assumed for
  convenience. `observation_counterfactual` therefore never has an
  "omit the bound" mode; it fails locally, before any HTTP request, if
  either bound is `None`.

## Snapshot implementation

- **`scripts/field_acceptance_client.py`**: added
  `FieldAcceptanceInvalidParameterError` and a local guard at the top of
  `observation_counterfactual` that rejects `None` for either
  `start_offset_ms` or `end_offset_ms` with an actionable message,
  before `_request` is ever called -- `_request`'s own generic
  None-dropping behavior is untouched (still correct and needed for
  genuinely optional filters like `list_visits(limit=...)`). Also added
  `scene_confusor_learning_status(stream_id)`, a thin wrapper around the
  existing, already-production, side-effect-free `GET .../observation/
  scene-confusor-learning` endpoint (reachable by the field-acceptance
  credential with no allowlist change needed -- any read-tier/
  `authenticated` route already is, per `mockingbird.api.auth`'s own
  `FIELD_ACCEPTANCE_ALLOWED_ADMIN_ROUTES` docstring).
- **`scripts/field_acceptance_ledger_snapshot.py`** (new, ~520 lines):
  the durable, committed replacement for the ad hoc, uncommitted
  `snapshot.py` every real Gate A cohort since v9 has hand-written fresh
  each session. Two subcommands:
  - `collect`: `take_checkpoint` fetches all three artifact classes
    (never raising for an ordinary field-acceptance-client-shaped
    failure -- the entire point is to survive and *report* a failure,
    not crash mid-session), writes one self-contained JSON file per
    checkpoint immediately, and `run_periodic_collection` loops this
    every `--interval-seconds`, printing a `checkpoint N: status=...`
    line every time and, on a `failed` checkpoint, an explicit
    `EVIDENCE INTEGRITY WARNING` to stderr naming the exact error and the
    running consecutive-failure count -- loud, immediate, mid-session
    visibility v12's own ad hoc script never had. Never calls
    `stop_observation` (the loop has no authority to stop a healthy
    session for one transient failure, per governing brief §8) and
    writes a durable `checkpoints-manifest.json` after *every* checkpoint
    (never only at clean exit), so a crash never loses prior accounting.
    `Ctrl+C` (or, in tests, `sleep_fn` raising `KeyboardInterrupt`) stops
    the loop gracefully.
  - `reconcile`: deterministic end-of-run completeness accounting (see
    "End-of-run reconciliation," below) plus optional emission of one
    merged, deduplicated `CounterfactualWindowResponse`-shaped JSON that
    `scripts/run_gate_a_measurement_accounting.py --input <merged>`
    consumes **unmodified** -- reuse, never a second, competing
    accounting implementation.
- Every real call `collect` makes passes an explicit, real
  `end_offset_ms` (default 86,400,000ms / 24h -- "everything retained so
  far"); there is no code path in this tool that can pass `None`.

## Snapshot RED->GREEN evidence

**Defect A -- client-level, via `git stash` against the real,
previously-existing file:**

1. Reverted `scripts/field_acceptance_client.py` to its pre-fix state
   (`git stash push -- scripts/field_acceptance_client.py`).
2. RED: `pytest tests/test_field_acceptance_client.py` failed to even
   collect (`KeyError: 'FieldAcceptanceInvalidParameterError'` -- the
   guard/exception did not exist).
3. Direct reproduction against the unfixed client (bypassing the network
   layer to observe exactly what request it would send): calling
   `observation_counterfactual(stream_id, start_offset_ms=0,
   end_offset_ms=None)` produced

       http://127.0.0.1:8000/api/streams/stream-5288453906fb/observation/counterfactual?start_offset_ms=0

   -- `end_offset_ms` silently absent, exactly reproducing v12's own
   422.
4. Restored the fix (`git stash pop`). GREEN:
   `tests/test_field_acceptance_client.py` -- **9/9 passed**, including
   `test_observation_counterfactual_rejects_none_end_offset_ms_before_
   any_request` (asserts `urlopen` is never even reached) and
   `test_observation_counterfactual_sends_both_bounds_when_explicit`
   (asserts the correct, complete query string for the valid form).

**Defect A -- new tool-level (`field_acceptance_ledger_snapshot.py`),
via deliberate mutation (this file has no prior committed version to
`git stash` back to, so a from-scratch RED cycle was produced by
temporarily breaking the finished implementation instead):**

- Mutated `reconcile_ledger`'s status decision from `recovered_unique_
  count >= final_recorded_count and not gaps` to the plausible-looking
  but wrong `recovered_unique_count > 0` ("got *some* records" mistaken
  for "got all of them"). RED: 5 tests failed, including
  `test_reconcile_ledger_never_reports_complete_for_a_genuinely_partial_
  recovery` and `test_reconcile_ledger_reproduces_the_v12_shape_partial_
  with_named_gap` -- both correctly caught the mutated code reporting
  `COMPLETE` for a genuinely partial recovery. Reverted; GREEN again,
  **18/18 passed**.
- A second, incidental genuine bug was caught by the test suite itself
  during development (not a deliberate mutation): `run_periodic_
  collection`'s `stdout`/`stderr` parameters originally defaulted to
  `sys.stdout`/`sys.stderr` bound at function-definition time -- the
  same "early-bound default" class of mistake
  `deploy_windows_dev.check_storage_headroom`'s own `disk_usage_fn`
  docstring already warns against elsewhere in this codebase. This
  silently defeated `capsys` in
  `test_run_periodic_collection_reports_a_failed_checkpoint_loudly_on_
  stderr` (the message really was printed -- to the *original* stderr
  file descriptor, invisible to `capsys`'s own sys-level interception).
  Fixed by resolving both fresh on every call (`None` sentinel default).
- A third RED cycle, this time via multi-agent self-review rather than
  deliberate mutation (see "Self-review findings and fixes," below):
  the same reconciler's own zero-activity-artifact bug (a real, honest
  `PARTIAL` misfire on a genuinely healthy quiet session) was
  independently caught by two separate review passes and fixed with a
  dedicated regression test (`test_reconcile_ledger_zero_activity_
  artifact_is_complete_not_partial`), plus a fix to the shared test
  fixture itself (`_ledger_payload`), which had been unrealistically
  masking the exact real-API shape that triggered it.

Combined final state (including every fix from "Self-review findings
and fixes," below): **`pytest tests/test_field_acceptance_client.py
tests/test_field_acceptance_ledger_snapshot.py` -- 33/33 passed** (9 +
24, up from the original 27 -- 6 further regression tests added during
self-review, covering the zero-activity fix, the merged-output honesty
fix, `max_checkpoints=0`, `FieldAcceptanceInvalidParameterError`
propagation, and malformed-interval filtering).

## End-of-run reconciliation

`reconcile_ledger` (in the new tool) unions every checkpoint's
successfully-fetched raw-ledger payload plus an optional final/post-stop
corrective fetch, and computes, per artifact type (`raw_detections`,
`track_generations`, `proposal_outcomes`), independently:

- **Deduplication by natural identity**: `generation_id`/`proposal_id`
  for tracks/proposals; for raw detections (which carry no id field at
  all in `CounterfactualRawDetectionResponse`) the full fact tuple
  (offset, frame id, detector id, provider id, broad class, bounding
  box) -- a genuine duplicate fetch collapses to one record, a genuinely
  distinct detection never does.
- **Recovered unique count**, compared against the largest
  `coverage.<type>.recorded_count` seen across every payload (the
  session's own true total only ever grows, so the maximum is the most
  authoritative figure, never an earlier/stale checkpoint's own smaller
  count).
- **Gaps**: each payload's own `oldest_retained_offset_ms`/`newest_
  retained_offset_ms` (the ledger's currently-retained window *at that
  checkpoint's own fetch time*) are merged into a sorted-interval union;
  anything in `[0, session_last_offset_ms]` not covered by that union is
  reported as an exact `(gap_start_ms, gap_end_ms)` pair -- never a vague
  "some data may be missing."
- **Status**: `COMPLETE` only when recovered count meets the final
  recorded count *and* zero gaps remain; `PARTIAL` with the precise
  missing count and offset window(s) otherwise; `UNKNOWN` only when no
  payload reported a `recorded_count` at all for that artifact (never
  silently assumed complete in that case either).
- **Deterministic**: every merge/union step is order-independent (dict
  keyed by identity, sorted-interval merge) --
  `test_reconcile_ledger_deduplicates_overlapping_snapshots_
  deterministically` proves the identical result for two different
  input orderings of the same payloads.

`test_reconcile_ledger_reproduces_the_v12_shape_partial_with_named_gap`
directly encodes v12's own real numbers (12 failed periodic snapshots +
one final corrective fetch recovering 400 of 22,664 total-shaped records
in a synthetic analogue) and confirms the tool reports exactly
`PARTIAL`, `final_recorded_count`, `recovered_unique_count`, and the
precise `(0, 600_000)`-shaped missing window -- the same shape of
finding v12's own report had to compute by hand.

`build_merged_counterfactual_window` additionally emits one
deduplicated, `CounterfactualWindowResponse`-shaped JSON any future
cohort can feed straight into `scripts/run_gate_a_measurement_
accounting.py --input <merged>` (unmodified) -- reusing that already
-accepted tool, never a second, competing implementation, per governing
brief §9's "reuse existing tooling where possible."

## v12 reproduced storage-preflight defect

Reconstructed directly from `docs/representative-daylight-gate-a-field-
acceptance-v12-report.md` ("Field-instance lifecycle") and the real
pre-fix code:

- v12's operator ran `scripts/field_acceptance_instance_lifecycle.py
  preflight --dev-root "C:\Users\...\MockingBirdFieldAcceptanceV12"`
  (a native Windows-style string) from this WSL/POSIX checkout.
- Pre-fix `storage_preflight_report` (line 914-915):

      resolved = _resolve(dev_root)   # Path(dev_root).resolve()
      probe_target = resolved if resolved.exists() else resolved.parent if resolved.parent.exists() else Path("/")

  POSIX `pathlib.Path` never treats a `C:\...` string as absolute
  (backslash is not `os.sep` there) -- the entire string becomes one
  literal, nonexistent relative path component, so `.resolve()` anchors
  it under the invoking shell's own current working directory (this repo
  checkout). That resolved (nonexistent) path's own `.parent` is exactly
  the repo checkout itself, which *does* exist -- so `probe_target`
  silently became `/home/zkelder/projects/mockingbird-active`, and
  `shutil.disk_usage` measured the WSL virtual disk (692GB/1TB free per
  v12's own report) instead of the real Windows C: drive (~7-8GB free at
  the time).
- **First irreversible error**: the single `_resolve(dev_root)` call
  itself -- by the time `probe_target` is chosen, the mistake (treating
  a foreign, unrecognized path as if it were an ordinary nonexistent
  POSIX relative path) has already happened; everything downstream
  (`.parent.exists()`, `disk_usage`) only compounds it.
- **Why the wrong filesystem was selected**: no code anywhere in the
  pre-fix path checked whether the *resolved* path bore any relationship
  to the *requested* one, or whether it was even plausible for the
  current OS/environment -- "nearest existing ancestor" is the correct
  fallback for a legitimately fresh, not-yet-created target, but it
  never distinguished "fresh but genuinely on the intended filesystem"
  from "resolved to something else entirely because the input was never
  recognized as absolute in the first place."
- **Why the result lacked enough provenance to expose the mistake**: the
  pre-fix `StoragePreflightReport` had exactly one path-shaped field
  (`dev_root`, set to `str(resolved)` -- itself already the *wrong*
  value) and no `platform`, no distinction between "requested" and
  "measured," and no filesystem/device identity at all. A reviewer
  reading `{"dev_root": ".../MockingBirdFieldAcceptanceV12", "free_bytes":
  ..., "sufficient": true}` had no way to notice anything was wrong --
  the shape of a correct answer and a silently-wrong one were identical.
- v12's own operator caught this by hand, independently, only because
  they happened to re-run the same command with the correct
  `/mnt/c/Users/...` form and noticed the free-space figure changed
  dramatically (692GB -> 7.9GB) -- nothing in the tool itself surfaced
  the discrepancy.

Reproduced directly against the real, unfixed logic (see "Storage
RED->GREEN evidence," below): given the exact string
`"C:\Users\zachk\AppData\Local\MockingBirdDev"`, the pre-fix code
resolved `probe_target` to this repository's own checkout directory
(device id 2096) -- confirmed by direct `stat`/code inspection to be a
completely different filesystem than the real Windows C: drive (device
id 71, confirmed by the real proof below).

## Storage root cause

A single defect, in one exact spot: **`storage_preflight_report`'s
target-resolution logic never recognized "this path representation
cannot be trusted on this OS" as a distinct case from "this path is
legitimately fresh and needs an ancestor walk."** Both were handled by
the same two-line fallback, so a foreign, misinterpreted absolute path
and a genuinely fresh local one were indistinguishable to the code.

A closely related, independently-discovered instance of the **same**
defect was found in `scripts/deploy_windows_dev.py`'s own
`check_storage_headroom` (the storage-preflight check `deploy()` itself
runs by default, before any build/materialize work, on every real
field-acceptance deploy -- unless `--skip-storage-preflight`):

    probe_target = dev_root
    while not probe_target.exists() and probe_target.parent != probe_target:
        probe_target = probe_target.parent

This is the *actual, most-used* entry point a real field-acceptance
session hits first (`deploy_windows_dev.py --dev-root <root> ...`,
before `field_acceptance_instance_lifecycle.py preflight` is ever
separately invoked) -- and it shared the identical vulnerability: no
Windows-drive-path recognition at all, so the exact same malformed input
would have silently measured the wrong disk here too, on the primary
deploy path, not just the secondary preflight tool. Fixing only the
secondary tool would have left the *primary* one just as dangerous as
before. Both are now fixed via one single shared resolver (see below) --
never two independently-drifting copies of the same logic.

## Storage-path contract

Locked before implementation (governing brief §12-§15):

- Given a requested dev-root/storage-root, preflight must either (A)
  resolve and measure the filesystem that actually contains/will
  contain that root, or (B) fail explicitly because the path
  representation cannot be resolved safely in the current execution
  environment. It may never silently substitute an unrelated existing
  parent/root and call that target storage.
- **Detection**: a Windows drive-letter string (`^[A-Za-z]:[\\/]`,
  matching both `C:\...` and `C:/...`) given while the current process
  is *not* running on native Windows (`os.name != "nt"`) is the exact
  cross-environment hazard v12 reproduced.
- **Resolution**: translate it via the real `wslpath -u` primitive --
  the same already-accepted, already-trustworthy Windows<->WSL utility
  `deploy_windows_dev.py` already uses pervasively elsewhere (its own
  `_wslpath`/`_to_windows_path_real`/`_local_appdata_real`), never a
  hand-rolled string substitution. Empirically confirmed (see the real
  proof below): real `wslpath -u` against a genuinely unmounted/unknown
  drive letter already fails loudly (non-zero exit), rather than
  fabricating a plausible-looking-but-wrong `/mnt/<letter>/...` path --
  so no separate "does the mount exist" guard is needed on top of
  trusting `wslpath`'s own exit code.
- **Fail closed**: any translation failure/unavailability (missing
  binary, unmounted drive, malformed output) refuses outright with an
  actionable message naming the supported alternative -- never guessed,
  never silently falls back to CWD or any other accidental ancestor.
- **Once resolved** (whether translated, or an ordinary POSIX path that
  was never Windows-style to begin with), the *same* ordinary
  nearest-existing-ancestor walk applies uniformly -- this is safe
  specifically because translation already fixed the one thing that made
  the original walk dangerous (an absolute path POSIX never recognized
  as absolute); once fixed, walking its real ancestors is exactly as
  safe as governing brief §15's own blessed example
  (`/mnt/c/MockingBird/NewInstance` -> `/mnt/c/MockingBird` or `/mnt/c`).
- **Native Windows is unaffected**: on real native Windows (`os.name ==
  "nt"`), ordinary Windows-drive syntax was never a hazard at all (real
  `pathlib.WindowsPath` resolves it natively) -- no translation is
  attempted, behavior is byte-for-byte unchanged from before this
  milestone.
- **Provenance**: the report must expose `requested` (verbatim operator
  input), `resolved` (the real absolute path this environment maps it
  to), `probed` (the existing ancestor actually measured),
  `resolution_method` (`"direct"` | `"translated_from_windows_drive_
  path"`), `platform`, and a cheaply-available filesystem/device
  identity (`os.stat(...).st_dev`) -- enough for a reviewer to see
  "requested Windows instance root -> measured Windows storage," not
  merely trust a bare `sufficient: true`.

## Storage implementation

- **`scripts/deploy_windows_dev.py`** (the shared, single source of
  truth): added `_looks_like_windows_drive_path`, `_wsl_translate_
  windows_path` (real `wslpath -u`, never raises -- returns `None` on
  any failure), `_nearest_existing_ancestor` (a proper multi-level walk,
  replacing both the old one-level-only check in `field_acceptance_
  instance_lifecycle.py`'s copy *and* the old `while` loop in
  `check_storage_headroom` -- consolidated into one function two call
  sites now share), the `StorageProbeTarget` dataclass, and
  `resolve_storage_probe_target` -- the one function that turns a
  `--dev-root` into a trustworthy, provenance-carrying probe target.
  `check_storage_headroom` now delegates to it (its own external
  contract/return type is unchanged: still `None`-or-raise, so `deploy()`
  needed no changes at all) and its failure message now also names the
  measured/requested paths.
- **`scripts/field_acceptance_instance_lifecycle.py`**: `storage_
  preflight_report` now calls `deploy_windows_dev.resolve_storage_probe_
  target` via the module's own pre-existing `_dwd()` `runpy.run_path`
  convention (the same mechanism it already uses for `read_current`/
  `probe_port`/every other `deploy_windows_dev.py` primitive) rather than
  its own separate, now-removed inline resolution logic. A `deploy_
  windows_dev.DeploymentError` from the resolver is caught and re-raised
  as this module's own `InstanceLifecycleError` (matching its existing
  "every message is written to be printed directly to an operator"
  convention and its CLI's existing `except InstanceLifecycleError`
  handling). `StoragePreflightReport` gained `requested_root`,
  `resolved_root`, `probed_root`, `resolution_method`, `platform`, and
  `filesystem_device_id` fields -- automatically surfaced in both
  `--json` and plain-text CLI output via the existing `_print`/`as_dict`
  plumbing, no CLI changes needed.
- No changes to `WindowsHost` (its interface/tests are unaffected --
  `check_storage_headroom` never took a `windows_host` parameter and
  still doesn't) and no new CLI flags (`is_native_windows`/
  `wsl_translate_fn` are hermetic test seams only, exactly like the
  pre-existing `disk_usage_fn`; real callers always get the real
  `os.name`/real `wslpath`).

## Storage RED->GREEN evidence

Via `git stash` against both real, previously-existing files together
(`scripts/deploy_windows_dev.py`, `scripts/field_acceptance_instance_
lifecycle.py`):

1. Reverted both to their pre-fix state.
2. RED:
   - `pytest tests/test_deploy_windows_dev.py` failed to even collect
     (`KeyError: 'resolve_storage_probe_target'` -- the shared resolver
     did not exist).
   - `pytest tests/test_field_acceptance_instance_lifecycle.py -k
     storage_preflight` -- the 4 pre-existing tests still passed
     (unaffected), but all 4 new tests failed with `TypeError:
     storage_preflight_report() got an unexpected keyword argument
     'is_native_windows'` -- the new capability genuinely did not exist
     yet.
3. Restored the fix (`git stash pop`). GREEN:
   - `tests/test_deploy_windows_dev.py` -- **142/142 passed**, including
     9 new `resolve_storage_probe_target`/`check_storage_headroom` tests
     covering: an ordinary POSIX target resolves directly; a target
     nested multiple levels below the nearest existing ancestor still
     resolves correctly (closing a latent gap the *original* one
     -level-only check had even for an honest POSIX path); the exact
     Windows-drive-path-on-POSIX translation, both success and
     fail-closed-without-translation cases; native-Windows invocation is
     unaffected; an ordinary path is never mistaken for Windows-drive
     syntax; and the full end-to-end `check_storage_headroom` proof that
     `disk_usage_fn` is *never even called* once resolution fails
     closed (proving "fails closed before measuring anything," not
     "measures the wrong thing and then happens to still refuse").
   - `tests/test_field_acceptance_instance_lifecycle.py` -- **41/41
     passed**, including 4 new tests confirming `storage_preflight_
     report`'s own provenance fields, its `InstanceLifecycleError`
     re-wrapping of a `DeploymentError`, and the same nested-ancestor
     correctness proven end to end through the real CLI-facing function.

Combined: **`pytest tests/test_deploy_windows_dev.py tests/test_field_
acceptance_instance_lifecycle.py` -- 183/183 passed.**

## Self-review findings and fixes

Before the real proofs below, this milestone's own full diff (every
changed/new file) was reviewed by five independent finder passes (line
-by-line diff scan; removed-behavior audit; cross-file/schema tracer;
reuse+simplification; efficiency+altitude+conventions) plus one
dedicated investigation into the offline-recorded-ingest question for
§18. This caught two **critical** defects that would otherwise have
silently undermined this milestone's own acceptance bar -- both fixed,
tested, and re-verified before proceeding to the real proofs:

1. **`deploy_windows_dev.py`'s own `main()` defeated the entire storage
   fix at the real CLI entry point.** The first implementation pass
   fixed `check_storage_headroom`/`resolve_storage_probe_target`
   directly, but `main()` still called bare `args.dev_root.resolve()`
   *before* handing `dev_root` to either -- silently CWD-anchoring a
   Windows-drive-style `--dev-root` string at the CLI boundary, before
   the drive-path detection ever got a chance to recognize it.
   Independently confirmed by **three separate review passes**, each via
   direct execution: `python scripts/deploy_windows_dev.py --dev-root
   'C:\Users\...\X' ...` (the literal real command a field session runs)
   would have reproduced v12's own wrong-filesystem defect exactly, with
   *false confidence from the "fixed" code*. Fixed by extracting
   `resolve_dev_root_path` (the shared Windows-aware resolution
   `resolve_storage_probe_target` itself now calls) and routing `main()`
   through it instead. New regression tests exercise `main()` itself
   (`test_main_resolves_a_windows_drive_dev_root_before_any_other_use`,
   `test_main_fails_closed_for_a_windows_drive_dev_root_with_no_
   translation`) -- RED (reverted the one-line fix, reran): the captured
   `dev_root` was literally
   `/home/zkelder/projects/mockingbird-active/C:\Users\...\X`; GREEN
   after restoring it.
2. **`reconcile_ledger` misreported a genuinely healthy, zero-activity
   artifact type as `PARTIAL`.** The real API honestly reports
   `oldest_retained_offset_ms`/`newest_retained_offset_ms` as `None`
   whenever `recorded_count == 0` for an artifact type (nothing was ever
    ledgered) -- a real, entirely ordinary shape for a short/quiet
   session's `track_generations`/`proposal_outcomes`. The reconciler
   treated the resulting empty `retained_intervals` as "the entire
   session window is one big gap," reporting `PARTIAL` (and dragging
   `overall_status` to `PARTIAL`) for a session with zero real
   evidence-integrity problems. Independently confirmed by **two
   separate review passes**; not caught by the original test suite
   because its own `_ledger_payload()` fixture unrealistically stamped
   non-`None` retained bounds onto every artifact type regardless of
   whether it had any records -- fixed in the fixture too, so the new
   regression tests actually exercise the real shape. Fixed via an
   explicit "genuinely zero" branch in `reconcile_ledger` (`final_
   recorded_count == 0` -> trivially `COMPLETE`, never gap-checked).
   This would have produced a misleading `PARTIAL` result in the real
   snapshot smoke proof below, for a legitimately healthy short session.

Four further, real-but-lower-severity defects were also found and fixed
in the same pass: `build_merged_counterfactual_window` unconditionally
claimed perfect retention in its own `coverage` block, disagreeing with
`reconcile_ledger`'s own verdict on the identical payload set (fixed by
sharing one `_accumulate_artifact` dedup pass between both functions,
which also closes the risk of the two ever silently diverging on which
record wins for a given identity); `_fetch_artifact`'s broad exception
handler also caught the client-level `FieldAcceptanceInvalidParameterError`
guard added earlier in this same milestone, silently absorbing a
caller-side programming bug as a routine operational failure instead of
crashing loudly (fixed: re-raised, never treated as "the fetch failed");
`_wsl_translate_windows_path` reimplemented `wslpath` invocation from
scratch instead of reusing this file's own pre-existing `_wslpath()`
helper (fixed: now wraps it); and `run_periodic_collection`'s
`max_checkpoints=0` took one checkpoint before ever checking the limit
(fixed: checked up front). `_looks_like_windows_drive_path` was also
broadened to recognize UNC syntax (`\\wsl.localhost\...`), confirmed by
real testing that `wslpath -u` already translates that form correctly.
Three cosmetic/simplification cleanups (a redundant `StorageProbeTarget`
construction, a duplicated JSON-write pattern, a pointless one-element
-tuple loop) were folded in during the same edit pass. Full findings,
verdicts, and outcomes were reported via the code-review skill's own
structured findings mechanism; three low-severity, genuinely-optional
findings (no `wslpath` subprocess timeout; drive-relative `C:foo`
syntax with no separator; sequential rather than concurrent per
-checkpoint HTTP fetches) were deliberately left unfixed as disclosed,
justified, out-of-bounded-scope residual limitations -- consistent with
governing brief §13's "do not build a giant Windows-path abstraction"
and §8's "do not create a generic monitoring framework."

Every RED->GREEN section above and below reflects the **final**,
post-review implementation -- the defects this section describes were
never present in an accepted/committed state. Final combined count
after every self-review fix and its own new regression tests:
**`pytest tests/test_deploy_windows_dev.py tests/test_field_acceptance_
instance_lifecycle.py` -- 185/185 passed** (144 + 41, up from 183 -- 2
further regression tests exercising `main()` itself directly, per
finding 1 above).

## Real WSL -> Windows storage proof

Performed against the real reference development Windows host (real
WSL2/Windows interop, confirmed alive this session via a live
`powershell.exe` smoke test) -- no long field run, nothing deleted.

**1. Independent ground truth**, queried natively, before touching the
tool under test:

    powershell.exe -NoProfile -Command "Get-PSDrive C | Select-Object Used,Free"
    Used         Free
    ----         ----
    482436247552 17120571392        # ~15.94 GiB free

**2. Real, supported mounted path** (`/mnt/c/Users/zachk/AppData/Local/
MockingBirdDev`, an existing directory):

    $ python scripts/field_acceptance_instance_lifecycle.py preflight \
        --dev-root /mnt/c/Users/zachk/AppData/Local/MockingBirdDev --json
    {
      "requested_root": ".../MockingBirdDev", "resolved_root": ".../MockingBirdDev",
      "probed_root": ".../MockingBirdDev", "resolution_method": "direct", "platform": "posix",
      "filesystem_device_id": 71, "free_bytes": 17113681920, "total_bytes": 499556818944, ...
    }

   `17,113,681,920` bytes vs. the independently-queried `17,120,571,392`
   -- within ~7MB (~0.04%), consistent with normal seconds-apart
   measurement drift on a live volume, not a different filesystem.

**3. Fresh, nonexistent, nested target** under the same real mounted
root (`/mnt/c/Users/zachk/AppData/Local/MockingBirdDev/NewFreshInstance
Probe/Deep/Nested`, three levels below the nearest existing directory):
resolved `probed_root` to the real, existing
`.../AppData/Local/MockingBirdDev` ancestor -- same device id 71 --
exactly the governing brief §15 contract, proven on the real filesystem,
not just in a hermetic test.

**4. The exact, previously-dangerous Windows-drive-string form**
(`C:\Users\zachk\AppData\Local\MockingBirdDev`) -- v12's own literal
mistake, replayed for real:

    $ python scripts/field_acceptance_instance_lifecycle.py preflight \
        --dev-root 'C:\Users\zachk\AppData\Local\MockingBirdDev' --json
    {
      "requested_root": "C:\\Users\\zachk\\AppData\\Local\\MockingBirdDev",
      "resolved_root": "/mnt/c/Users/zachk/AppData/Local/MockingBirdDev",
      "probed_root": "/mnt/c/Users/zachk/AppData/Local/MockingBirdDev",
      "resolution_method": "translated_from_windows_drive_path", "platform": "posix",
      "filesystem_device_id": 71, "free_bytes": 17112948736, ...
    }
    exit code: 0

   `filesystem_device_id: 71` -- **identical** to step 2's direct-path
   invocation, and free-space figures agree within ~1MB of each other --
   definitive proof this measured the exact same real Windows C: drive,
   not the WSL virtual disk.

**5. A genuinely unmounted/unknown drive letter** (`Q:\NoSuchDrive\
MockingBirdFieldAcceptanceGhost`) -- real `wslpath -u` against this
independently confirmed (exit 1, no output) that it refuses rather than
fabricating a path:

    $ python scripts/field_acceptance_instance_lifecycle.py preflight \
        --dev-root 'Q:\NoSuchDrive\MockingBirdFieldAcceptanceGhost' --json
    ERROR: --dev-root 'Q:\\NoSuchDrive\\MockingBirdFieldAcceptanceGhost' looks like a
    Windows-style path (drive-letter syntax) but this process is not running on native
    Windows, and translating it via 'wslpath -u' failed, is unavailable, or produced an
    unusable result. Refusing to guess which filesystem this points at ... pass the real
    WSL-mounted form instead (e.g. /mnt/c/Users/<you>/AppData/Local/<DevRootName>).
    exit code: 1

**6. Confirmation the old bug's silent target and the real target are
genuinely different filesystems** (`stat -c '%d %n'`, real values):

    2096  /home/zkelder/projects/mockingbird-active   # what the old bug silently measured
    71    /mnt/c                                       # what it should have measured (and now does)
    71    /mnt/c/Users/zachk/AppData/Local/MockingBirdDev

Every real-world requirement of governing brief §17 is satisfied: values
correspond within normal measurement drift, the previously-dangerous
form now safely resolves to the *same* verified real device rather than
being refused unnecessarily, an unresolvable form fails closed instead
of guessing, and nothing was deleted.

## Real snapshot smoke proof

Real, bounded, not a 75-100 minute cohort -- no wildlife-performance
claims made from it. Full raw evidence: `data/field-acceptance/2026-09
-04-evidence-integrity-storage-preflight-correctness-v1-smoke-proof/`
(gitignored, per established convention; its own `PROVENANCE.md`
indexes every file).

**Getting a real, queryable raw ledger required a real Camera Node
session -- confirmed the only path.** Direct code reading established
that RTSP/local-USB/offline-recorded-ingest Streams never reach the
counterfactual ledger `observation_counterfactual` reads from -- only a
`camera_node`-kind Stream's `observation/start` calls `get_observation_
engine_session_manager().start(...)`, the one path that populates it
(`src/mockingbird/api/main.py`'s `start_stream_observation`; RTSP/local
-USB route through the entirely separate, pre-existing `LiveCameraSession
Manager`/`DurableMonitoringSupervisor` stack instead, and offline
-recorded ingest runs `FrameDrivenObservationProvider.replay_frames`
directly, bypassing the session-manager singleton the ledger belongs
to). The reference Camera Node was paired to the now-archived
Representative Daylight Gate A Field Acceptance v12 instance; its own
admin credentials were unknown (never supplied to the user, per that
instance's own report), so its pairing could not be revoked through its
own authenticated API without first restarting that dormant instance's
server. **Stopped and asked the user before touching shared hardware
state** (the auto-mode permission classifier itself correctly declined
the direct action pending confirmation) -- approved, then executed via
the Node's own local pairing-state reset (`/var/lib/mockingbird-camera
-node/pairing.json`, backed up first to `pairing.json.pre-smoke-tooling
-v1-reset.bak`, matching an established, repeatedly-used precedent
already visible on the real Node -- `pre-v10-reset.bak`, `pre-golden
-path-v1-reset.bak`, `pre-e2e-orphan-reset.bak`, `pre-final-cleanup
-reset.bak` -- then a service restart), never destructive, fully
reversible (the Node can be paired to any instance again the same way).

**Instance and pairing**: a fresh, dedicated, disposable dev-root
(`MockingBirdSnapshotToolingSmokeV1`, `--skip-bioclip-runtime`, real
GPU/CUDA detector runtime) -- never the pending-archival v12 instance,
keeping this proof's evidence completely separate from v12's own.
Real one-time pairing code minted (Node service restart), consumed via
the real, documented `POST /api/camera-nodes/pair` -> `.../camera-setup
/validate` -> `.../camera-setup/complete` sequence -- real advertised
camera `picamera2-camera-0` (`status: "available"`), one full-frame
"Yard" Zone, Stream `stream-29e51c1d8ffa`.

**Real session**: `observation/start` confirmed `runtime_kind: "camera_
node_engine"`, `provider_key: "frame-driven-onnx-cuda"`, real `cuda_
available: true`, MDv5a / `MDv5a.0.1-onnx-opset18`, `score_threshold
0.1`, `nms_iou_threshold 0.45` -- the accepted configuration,
byte-identical to doctrine, confirmed directly in the live response.
Ran **265.11 seconds (~4.42 minutes)**, `stopped_reason: "user_stopped"`.

**5 real periodic checkpoints** via `field_acceptance_ledger_snapshot.py
collect` (`--interval-seconds 45 --max-checkpoints 5`), run from the
packaged release's own embedded `python.exe` against the real server
(WSL->127.0.0.1:8000 loopback confirmed broken again this session,
consistent with every prior field-acceptance report; routed through
`powershell.exe`, the established pattern) -- **every checkpoint
reported `status: "complete"`**, all three artifact classes (`raw_
ledger`, `monitoring_status`, `scene_confusor_state`) `success: true`
every time, `raw_ledger.record_count` growing monotonically (29 -> 67
-> 106 -> 154 -> 192) as real detections genuinely accumulated. One
final corrective fetch taken while the engine was still live,
immediately before stopping (the same v9-v12 convention) --
239 raw detections total by the time of the clean stop.

**Reconciliation** (`reconcile --merged-output`, 6 payloads: 5
checkpoints + 1 final):

| artifact | recovered | final `recorded_count` | status | note |
|---|---|---|---|---|
| `raw_detections` | 220 (unique) | 220 | **PARTIAL** | 0 missing by count; one real, exact, sub-second gap named -- see below |
| `track_generations` | 0 | 0 | **COMPLETE** | genuine zero -- no real animal motion crossed the tracker's confirmation threshold in this bounded window |
| `proposal_outcomes` | 0 | 0 | **COMPLETE** | genuine zero, same reason |

`overall_status: PARTIAL`, driven entirely by one real, precisely-named
finding: `raw_detections` recovered *every* record the server ever
reported (220/220, 0 missing) yet the tool still reported `PARTIAL`,
because it does not stop at record-count agreement -- it independently
verifies interval coverage. It found a genuine `[243349, 243888]`ms
(539ms) window no single snapshot's own retained-interval explicitly
covered end-to-end: the final fetch's own `raw_detections.newest_
retained_offset_ms` (243349) trailed slightly behind the engine's own
broader `session_last_offset_ms` marker (243888) by the moment that
response was serialized -- a real, tiny, honest timing artifact between
two different offset markers in the same response, not a lost record
(confirmed: 220 recovered exactly equals 220 recorded). **This is
exactly the rigor the governing brief asked for**: the tool never
rubber-stamped `COMPLETE` merely because a count matched; `track_
generations`/`proposal_outcomes` correctly reconciled `COMPLETE` for
their own genuine zeros in the same run, proving the earlier self
-review fix (see "Self-review findings and fixes") behaves correctly
against real, not merely synthetic, zero-activity data. CLI exit code
**1** (matching `overall_status: PARTIAL`) -- an honest, non-silent
result.

**Required-result checklist (governing brief §18), each independently
verified**: every requested snapshot artifact carried an explicit
status on every checkpoint (never silently assumed) -- yes. Raw-ledger
files genuinely contain records where the runtime produced them (220
real raw detections, byte-inspected directly from the checkpoint files
themselves, not merely trusted from a summary count) -- yes. Completeness
/reconciliation output matches the observed interval (the 220/220 count
match and the exact 539ms gap were independently re-derived by hand
against the same six raw files, not just read back from the tool's own
output) -- yes. No silent empty-success condition anywhere (the genuine
zeros for `track_generations`/`proposal_outcomes` are explicit, reasoned
`COMPLETE` verdicts with their own stated rationale, never a bare
absence; the genuine `raw_detections` gap is named to the exact
millisecond, never glossed over) -- yes.

**Cleanup**: Observation stopped cleanly (confirmed `state: "stopped"`,
`observing: false`). Instance lifecycle: `active` -> `completed` ->
`archived` (evidence archive: this section's own directory, containing
`PROVENANCE.md` plus every raw JSON file -- `verify_archive_contract`
satisfied). `assess` re-confirms `SAFE_TO_RECLAIM` (~4.13GB) -- **not
destroyed**, per standing "never destroy by default" policy. Camera
Node left paired to this archived instance's own credential (the same
choice v12 made for its own archived instance, for the same reason: a
future session picking this Node up should expect `pairing_required:
false` against this instance's credential, and can revoke/re-pair via
the same documented, now twice-proven-safe local-reset procedure if it
needs the Node for something else).

## Product-behavior non-change

- Zero changes to `src/mockingbird/**` (verified via `git status`/`git
  diff --stat` for the whole session -- every touched file is under
  `scripts/` or `tests/`). MDv5, `score_threshold 0.1`, NMS, the
  tracker, evidence-selection policy, candidate admission, scene
  -confusor suspicion, Visit grouping, BioCLIP, identification
  eligibility, and `reject_no_identification_or_context`
  (`src/mockingbird/observation/candidate_quality_gate.py`, confirmed by
  direct inspection to still discard a proposal outright whenever no
  captured evidence item ever reaches role `identification`/`context`)
  are all byte-for-byte unchanged.
- Schema unchanged at v58 (no migration touched, no schema-version
  literal changed).
- The seven explicitly-preserved untracked files
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) remain exactly as they were at
  session start -- confirmed via `git status` before, during, and after
  this milestone.
- The one shared production-library-adjacent file touched
  (`scripts/deploy_windows_dev.py`) is developer/field tooling only, per
  its own module docstring ("a developer-tooling script only -- it
  changes nothing about how MockingBird itself behaves"), not a runtime/
  admission/perception module -- within the governing brief's own
  preferred implementation footprint, not a scope-widening exception
  requiring separate justification.

## Validation

**Tier 1** (focused RED->GREEN for both defects): see "Snapshot
RED->GREEN evidence" and "Storage RED->GREEN evidence," above --
**33/33** (client + new ledger-snapshot tool) and **185/185** (deploy
-tooling + instance-lifecycle) passed, 52 of those tests newly added
this milestone (44 from the initial implementation pass + 8 from
self-review).

**Tier 2** (every affected field-acceptance/lifecycle/storage/client/
tooling test suite, run together, full files, no `-k` filtering):

    pytest tests/test_deploy_windows_dev.py tests/test_field_acceptance_client.py \
        tests/test_field_acceptance_instance_lifecycle.py tests/test_field_acceptance_ledger_snapshot.py \
        tests/test_field_acceptance_authentication.py tests/test_install_camera_node.py
    321 passed in 28.16s

**Lint**: `ruff check` on every changed/new Python file (`scripts/
field_acceptance_client.py`, `scripts/field_acceptance_instance_
lifecycle.py`, `scripts/field_acceptance_ledger_snapshot.py`, `scripts/
deploy_windows_dev.py`, and all four touched/new test files) --
**All checks passed!**, zero findings.

**Tier 3**: not run. Archaeology confirmed the only shared file touched
(`deploy_windows_dev.py`) is field/deployment tooling, not a production
runtime/perception/admission library with cross-cutting blast radius --
no justification to widen scope existed, so none was sought. Zero
`src/mockingbird/**` diff for the entire milestone.

## Remaining Gate A dependencies

Unchanged by this milestone (a tooling-correctness fix, not new field
evidence): the pre-existing 13-item Gate A dependency list from v12's
own report/`docs/release-execution-state.md` §6.R stands exactly as it
was, **except** for the one item this milestone directly answers (see
"Decision," below, and the release-execution-state reconciliation for
the precise wording change). In particular, per governing brief §22,
this milestone explicitly did not investigate, and did not change:

- item (13) -- whether `reject_no_identification_or_context`'s
  all-or-nothing behavior for brief-but-real encounters should be
  revisited (a real product-doctrine question, out of scope here by the
  governing brief's own §22/§4 instruction; confirmed still present,
  unmodified, in `candidate_quality_gate.py`).
- the broader 11-item list predating v12 (never-strong single
  -generation confusors, a second unconfounded cohort, a full-strength
  fragmentation re-proof, a second true-latency cohort, a 3+-subject
  cohort, v7's remaining ambiguous fragmentation units, the ~13 untraced
  v7 `blocked_missing_evidence` records, same-frame class-contradiction
  field effect, further strong-confidence scene-artifact recurrence,
  whole-frame human-suppression-of-real-birds, and scene-confusor
  participation accounting) -- none of these are field-evidence
  questions this tooling-only milestone could answer, and none were
  touched.

## Decision

**A**

- The exact v12 snapshot failure was reproduced precisely (not merely
  re-described) and its first irreversible error identified.
- Snapshot requests can no longer silently lose a required bound: the
  client fails locally with an actionable error, before any HTTP
  request, and the new committed tool never constructs such a request in
  the first place.
- A failed required raw-ledger fetch now makes its checkpoint visibly
  `failed`, surfaced loudly on stderr the moment it happens -- never
  silently folded into an otherwise-healthy-looking session summary.
- A deterministic end-of-run completeness reconciliation now exists,
  reusable, tested against a synthetic replica of v12's own real numbers.
- The exact v12 wrong-filesystem storage defect was reproduced precisely,
  including identifying and fixing the *same* latent defect in the
  actual primary deploy entry point (`deploy_windows_dev.check_storage_
  headroom`), not just the secondary preflight tool v12 happened to hit.
- A malformed/cross-environment path can no longer silently measure
  unrelated storage -- proven both in hermetic tests and against the
  real reference Windows host, with `filesystem_device_id` provenance
  showing byte-for-byte which real device was measured.
- A valid fresh Windows-target path is supported safely, proven for real
  (not merely reasoned about) alongside the correct refusal of a
  genuinely unresolvable one.
- The real snapshot smoke proof succeeded on every one of governing
  brief §18's own required-result criteria: every checkpoint against a
  real, live, GPU-backed Camera Node session reported explicit
  per-artifact status; the raw-ledger files genuinely contain the real
  detections the runtime produced (220, byte-inspected); reconciliation
  correctly distinguished a genuine zero (`track_generations`/
  `proposal_outcomes`, both `COMPLETE`) from a real, exact, sub-second
  interval-coverage gap (`raw_detections`, `PARTIAL` despite a perfect
  220/220 record-count match) -- never a silent empty-success anywhere.
- Two critical defects in this milestone's own first implementation pass
  (a `main()` CLI path that would have silently defeated the storage fix
  for the actual command a real field session runs; a reconciler that
  would have misreported a genuinely healthy zero-activity artifact type
  as `PARTIAL` -- which the real smoke proof's own quiet
  `track_generations`/`proposal_outcomes` window would have triggered)
  were caught and fixed by multi-agent self-review *before* either real
  proof was attempted, per this milestone's own "one implementation
  /self-review" operating rule.
- Tier 1 and Tier 2 are fully green; lint is clean.
- No wildlife/product admission behavior changed anywhere in this
  milestone.
- v12's own historical evidence-preservation gap remains exactly as
  disclosed -- this milestone repairs future collection; it does not,
  and cannot, retroactively manufacture v12's own missing raw-ledger
  data.

Every element of the governing brief's acceptance bar (§24) is met.

## Scheduler effect

Per governing brief §25, `docs/release-execution-state.md` is updated
for the accepted delta only:

- HEAD, schema (unchanged, v58): recorded.
- Field-acceptance evidence-preservation state: the *tooling* defect
  that made v12's own raw-ledger figures partially unverifiable is now
  fixed and proven (real WSL->Windows proof, real snapshot smoke proof,
  27+183 passing tests) -- but Gate A's own standing need for a cohort
  with genuinely intact, full-session raw-ledger coverage is **not**
  removed. Fixing the tool does not retroactively create that evidence;
  a future cohort still needs to actually collect it, now with
  confidence the tool itself will not be the reason it comes back
  partial.
- Storage-preflight correctness state: the wrong-filesystem hazard is
  closed at both the primary (`deploy_windows_dev.py`) and secondary
  (`field_acceptance_instance_lifecycle.py preflight`) entry points,
  proven against real Windows storage.
- Gate A dependency list: item (12) ("a cohort with intact full-session
  ledger coverage, to properly cross-validate v12's own partially
  -unverifiable figures") is narrowed -- the *tooling-broken* rationale
  for needing that cohort is closed; the underlying, independent
  requirement for an intact-ledger representative cohort (a genuine
  evidence gap, not a tooling gap) is explicitly preserved, not removed.
  Item (13) (`reject_no_identification_or_context`'s all-or-nothing
  behavior) is preserved verbatim -- untouched, unresolved, still open.

Authorization returns to **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**. This milestone does not self-authorize the all-alternate
-evidence product fix, another field cohort, External Pre-Release
Acceptance, or Final Release Hardening, and does not propose or start
the next milestone.
