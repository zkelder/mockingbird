# Field Acceptance Tooling Correctness & Preflight Closure v1

Bounded RELEASE-CRITICAL tooling-correctness milestone, directly authorized
outside this file. Closes five concrete procedural gaps *Representative
Daylight True-Latency Tail Convergence v3* exposed in the field-acceptance
tooling itself -- never a field session, never a deployment, never a
product/perception/schema change.

**Outcome: all five gaps closed with deterministic tests. Two are real
defects with confirmed root causes, fixed with the smallest precedented
change (both reusing an already-accepted primitive from elsewhere in this
same tooling family, never a second implementation). Two are new, bounded,
independently-testable tools that did not exist before this milestone
(recorder readiness gate; session stop/finalization driver). One is a
reporting/test-contract clarification over already-correct logic, per this
milestone's own explicit "if already correct, improve only the reporting"
instruction. Classification: A.**

## 1. Starting state

Verified directly, in the order the governing directive required, before
any other action:

- Repository: `/home/<user>/projects/mockingbird-active`; branch `main`.
- Starting HEAD: `4e46952` -- matches the directive's expected baseline
  exactly.
- Schema: `CURRENT_DATABASE_SCHEMA_VERSION = 59` (unchanged, matches).
- `docs/release-execution-state.md` top-of-file phase section: Lane P
  `CLOSED`; Lane R `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
  REMAINS`; current authorization at start `NONE`. Matches the directive's
  stated baseline exactly.
- Governing sources read in the directive's own required order:
  `docs/release-execution-state.md` (top-of-file phase + targeted §1/§3/§6.R
  history), `docs/product-doctrine.md` (full), `docs/roadmap.md` (targeted:
  "Numeric release budgets," Gate A), then
  `docs/representative-daylight-true-latency-tail-convergence-v3-report.md`
  (full -- the primary source of every concrete defect this milestone
  closes), `docs/global-product-release-readiness-reconciliation-v2-report.md`
  §10 (the closest thing to a standing Lane R field contract), and the two
  most relevant existing tooling reports (`field-acceptance-instance-
  lifecycle-storage-safety-v1-report.md`,
  `field-acceptance-evidence-integrity-storage-preflight-correctness-v1-report.md`).
- Worktree safety: no `.git/*.lock`; no stale MockingBird/uvicorn/vite
  process running in the sandbox. The seven preserved untracked detector
  files (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) were confirmed present and
  unmodified at start and again at the end of this milestone.
- No push, no history rewrite, no deploy, no field session, no physical
  hardware touched anywhere in this milestone -- confirmed by construction
  (no `deploy_windows_dev.py`/Camera-Node/pairing call appears anywhere in
  this milestone's own work).

## 2. Exact v3 defects and root causes

Two defects were real, reproduced, and root-caused directly in
*Representative Daylight True-Latency Tail Convergence v3*'s own report;
three more procedural gaps (C, D, E below) were named by this milestone's
own governing directive as concrete risks the *next* session must not
repeat, investigated fresh against the current tooling.

**A -- `field_acceptance_instance_lifecycle.py init` path-format
inconsistency (v3 Defect #2).** `init`'s `--dev-root` went straight to
`Path(dev_root).resolve()` (`_resolve`), while the sibling `preflight`
command had, minutes earlier in the *same* session, correctly accepted and
translated the identical Windows-style string via `deploy_windows_dev.
resolve_dev_root_path`. On POSIX, `Path("C:\Users\...").resolve()` treats
the whole backslash string as one opaque relative path segment and
CWD-anchors it -- producing the "garbled error concatenating the WSL cwd
with the raw backslash string" v3's own report describes. Root cause:
`preflight` was fixed for this exact class of bug by *Field Acceptance
Evidence Integrity & Storage Preflight Correctness v1*; that fix was never
propagated to any of this tool's other five commands.

**B -- independent acceptance-frame recorder never activated (v3 Defect
#3).** The operator passed a Windows-style path to
`MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`. `deploy_windows_dev.py`'s own
`launch_release` unconditionally ran that value through
`windows_host.to_windows_path` (real `wslpath -w`), which expects
WSL-style input -- given an already-Windows-style string, `wslpath -w`
silently strips the backslashes and returns a garbage relative filename,
**exit code 0, no error**. `BoundedFrameSampleRecorder` only skips
recording when the env var is unset *entirely*, so the recorder believed
it was enabled and produced no usable directory all session. No
independent visual-evidence frames were available to resolve that
session's own two ambiguous samples.

**C -- no hard, tested session-duration enforcement.** Investigated fresh:
no `fa_driver.py`-equivalent, or any other session-stop-timing script,
exists anywhere in this repository. v3's own report confirms this
indirectly -- its §1 records cleaning up a leftover, unattended
`fa_driver.py` polling-driver *process* left over from an *earlier*
milestone, never a tracked, tested file. Every real field session
(v4-v14, v3) has driven the 45-minute-minimum/75-minute-maximum/
>=12-sample-target stop decision by an operator watching a ~5-minute
status-report cadence and issuing `stop_observation` by eye -- v3's own
§8 explicitly calls its 75.2-minute wall-clock stop "at, not over" the
maximum, a judgment call, not an enforced deadline.

**D -- no enforced post-stop-finalization ledger-capture ordering.**
Investigated fresh: `field_acceptance_ledger_snapshot.py reconcile
--final-snapshot <path>` accepts any single operator-supplied JSON with no
verification of *when* it was fetched relative to stop-finalization
settling. v3's own §7/§8 narrates the correct sequence being followed only
because the operator personally noticed a first corrective fetch (taken
live, pre-stop) predated a candidate (candidate-012) rescued *during*
stop-finalization, and manually took a second, post-settlement fetch --
vigilance-dependent, not tool-enforced.

**E -- `fallback_measured` terminology risk.** Investigated fresh, per the
directive's own explicit "if the current classification is already
correct, improve only the reporting" instruction:
`capture_to_visible_latency.build_latency_summary`'s `fallback_measured_
count` is a strict, already-correct *subset* of `measured_count` -- it
means "this admitted candidate won an ambiguous-boundary arbitration
contest as a non-top-ranked member" (`LatencySample.is_fallback`, read
from `outcome.reason`'s own `:fallback_position_N` suffix), **never** a
degraded/approximate timestamp source. Every `fallback_measured` sample
runs through the exact same `_resolve_t0`/`_normalize_t0`/
`_resolve_latency` path as any other sample, off the *admitted* member's
own capture facts. The classification itself was already correct (and
already explained once, correctly, in
`representative-daylight-gate-a-field-acceptance-v9-report.md`); this
milestone's own concern -- that a future reader could misread "fallback"
as "fallback timestamp" -- is a real, disclosed reporting-clarity risk,
not a logic defect.

## 3. Implementation contract

Locked before implementation, per the directive's own "root-cause it; stop
at the appropriate boundary; report the smallest necessary corrective
scope":

- **A**: one canonical `--dev-root` resolution boundary
  (`_resolve_dev_root`) reused by every subcommand of
  `field_acceptance_instance_lifecycle.py`, delegating to the same
  already-tested `deploy_windows_dev.resolve_dev_root_path` `preflight`
  already used -- never a second, independently-drifting translation.
- **B (path)**: `launch_release` detects an already-Windows-style
  `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` value and uses it verbatim
  (never re-translated through `wslpath -w`, which is what mangled it);
  a genuinely WSL-style value is translated exactly as before, unchanged.
- **B (hard gate)**: a new, bounded, independently-testable tool
  (`field_acceptance_recorder_readiness.py`) that polls for real,
  advancing frame evidence -- directory exists, is writable, real files
  appear, timestamps/sizes advance, correspond to the intended Stream --
  within a bounded timeout, and fails closed (`STOP BEFORE OBSERVATION`,
  exit 1) otherwise. A process-liveness check is available (`--dev-root`,
  reusing `field_acceptance_instance_lifecycle.py`'s own process probe)
  but is never treated as sufficient on its own.
- **C**: a pure, clock-free `decide_stop` function encodes the entire
  45-min-minimum/75-min-maximum/>=12-sample-target contract; a thin,
  monotonic-clock-driven polling loop (`run_stop_timing_loop`) drives it
  on its own bounded cadence, independent of any status-report tick, and
  never overshoots the maximum deadline.
- **D**: `stop_and_capture_final_snapshot` enforces Observation stop ->
  poll `observation_status` until it genuinely settles to `state ==
  "stopped"` -> exactly one authenticated raw-ledger fetch, strictly in
  that order, every time -- never a snapshot at all if settlement times
  out. The existing `reconcile_ledger` completeness logic (already
  interval-gap-based, not count-based) is locked in with a new regression
  test rather than changed.
- **E**: docstring and stdout clarification only, plus one new
  summary-level regression test proving a fallback-admitted sample is
  never silently promoted or demoted in its own clock-calibration state --
  zero logic change, per the directive's own instruction for an
  already-correct classification.

No detector, classifier, threshold, tracker, admission, Visit-assembly,
schema, T0/T5 definition, or clock-calibration-algorithm change anywhere.

## 4. Files changed

**Modified (8):**

| File | Change |
|---|---|
| [scripts/field_acceptance_instance_lifecycle.py](../scripts/field_acceptance_instance_lifecycle.py) | New `_resolve_dev_root`; `init_instance`/`assess_instance`/`complete_instance`/`mark_archived`/`plan_cleanup`/`execute_cleanup`/`status_report` now resolve `--dev-root` through it; docstring "`--dev-root` path convention" section added. |
| [scripts/deploy_windows_dev.py](../scripts/deploy_windows_dev.py) | `launch_release`'s `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` handling detects an already-Windows-style value and uses it verbatim; WSL-style path unchanged. |
| [scripts/run_gate_a_measurement_accounting.py](../scripts/run_gate_a_measurement_accounting.py) | One clarifying stdout line next to `fallback_measured=`. |
| [src/mockingbird/observation/capture_to_visible_latency.py](../src/mockingbird/observation/capture_to_visible_latency.py) | `build_latency_summary` docstring: explicit "fallback = admission arbitration, never timestamp" disambiguation. No logic change. |
| tests/test_field_acceptance_instance_lifecycle.py | +5 tests (Windows-style `init`, fail-closed, spaces, idempotency across spellings, tool-wide consistency). |
| tests/test_deploy_windows_dev.py | +1 test (Windows-style recording-dir accepted verbatim, proven with a deliberately corrupting fake `to_windows_path`). |
| tests/test_field_acceptance_ledger_snapshot.py | +1 test (equal recovered/recorded counts, real interval gap, still PARTIAL). |
| tests/test_capture_to_visible_latency.py | +1 test (`fallback_measured_count` subset semantics at the summary level). |

**New (4):**

| File | Purpose |
|---|---|
| [scripts/field_acceptance_recorder_readiness.py](../scripts/field_acceptance_recorder_readiness.py) | Independent, bounded pre-Observation recorder readiness gate (governing brief §4). |
| [scripts/field_acceptance_session_driver.py](../scripts/field_acceptance_session_driver.py) | Session stop-timing loop + post-finalization ledger-capture driver (governing brief §5/§6). |
| tests/test_field_acceptance_recorder_readiness.py | 13 tests. |
| tests/test_field_acceptance_session_driver.py | 23 tests. |

Net: `8 files changed, 464 insertions(+), 29 deletions(-)` (tracked
modifications) + 2 new scripts (422 + 480 lines) + 2 new test files
(308 + 343 lines). The seven protected untracked detector files are
untouched (re-verified byte-identical-by-presence at the end of this
milestone, same as at the start).

## 5. Recorder readiness proof (item B)

**Path fix.** `test_launch_release_accepts_a_windows_style_acceptance_
recording_dir_verbatim` (new) reproduces the exact v3 failure shape with a
fake `to_windows_path` that mirrors real `wslpath -w`'s confirmed
backslash-stripping behavior on Windows-style input, and proves
`launch_release` now bypasses that seam entirely for an already-Windows-style
value. The three pre-existing recording-dir tests (default-off,
WSL-style-forwards, WSL-style-goes-through-`to_windows_path`) all still
pass unchanged -- zero regression to the working WSL-style path.

**Readiness gate.** `check_recorder_readiness` (new module) was exercised
against 13 deterministic scenarios (fake monotonic clock, real `tmp_path`
filesystem, no real sleep): ready on genuine advancement (manifest growth
or a newer/updated frame file); not ready when the session directory never
appears, when it exists but stays empty, when it exists but writes stall,
when the confirmed-alive process still has non-advancing evidence
("a process existing is not sufficient proof," governing brief §4, directly
tested), and when the process is confirmed dead (fails before any
polling); correctly re-resolves the newest correctly-named session
directory on every poll rather than latching onto a stale prior session's
own static leftover; correctly isolates by Stream (a different Stream's
real, advancing evidence never satisfies this Stream's check); reports
directory writability; and respects a bounded timeout with the expected
overshoot (never more than one `poll_interval_seconds` beyond the
deadline, confirmed exactly: `timeout=12s, poll=5s` -> 4 polls, `elapsed
=15.0s`, never unbounded).

**Real subprocess dry-run** (not merely the hermetic unit tests above --
see governing brief §9's own "may use a disposable simulated/fake service
or existing test fixture"): the actual CLI, with real `time.sleep`/`time.
monotonic` (no fakes), against a real `/tmp` fixture:

```
$ python scripts/field_acceptance_recorder_readiness.py --recording-root ... --stream-id stream-dryrun-1 --timeout-seconds 15 --poll-interval-seconds 2 --json
```

A second real frame file was written from a separate shell ~1s into the
run (simulating the recorder actively writing). Result: `ready: true`
after 4 real polls (6.0s elapsed), correctly showing `first_snapshot`
(1 frame) versus `last_snapshot` (2 frames, later mtime). A second run
against a directory that never appears (`--timeout-seconds 3`) exited `1`
with `STOP BEFORE OBSERVATION -- recorder readiness could not be
confirmed.` on stderr and `reason: recorder_session_directory_not_found
...` -- exactly the fail-closed contract governing brief §4 requires.

## 6. Hard-stop proof (item C)

`decide_stop` (pure, no I/O) was tested against every literal requirement
in governing brief §5: continues past the minimum even with the sample
target already met from `t=0`; fires exactly at the minimum once the
target is met; continues past the minimum (to the maximum) when the
target is never met; fires at the exact maximum regardless of sample
count; the maximum wins even if the target is *also* met at that instant;
an explicit early-stop reason (daylight/safety) wins immediately, even
before the minimum.

`run_stop_timing_loop` (fake monotonic clock, no real sleep) was then
tested end-to-end: continues to the minimum before stopping on an early
target (`elapsed_seconds == 120.0` exactly, not a moment before); runs to
the maximum when the target is never reached (`elapsed_seconds == 300.0`);
**hits the exact deadline with zero polling overshoot for a
non-dividing poll interval** (`min=max=100s, poll=37s` -> `elapsed_seconds
== 100.0`, never `111.0` -- proves the loop clamps every sleep to never
carry `elapsed_seconds` past the maximum, the literal "it does not wait
for the next five-minute status tick" requirement, generalized to any
interval); an injected `early_stop_check_fn` stops immediately, mid-run,
before the minimum; `Ctrl+C` (`sleep_fn` raising `KeyboardInterrupt`, the
same convention `field_acceptance_ledger_snapshot.run_periodic_collection`
already established) is treated as a graceful early-stop signal that
still returns normally rather than crashing, so the caller's own
stop-and-finalize sequence always still runs. `SessionDriverConfig`'s
`__post_init__` rejects every invalid bound (non-positive durations,
negative target, maximum before minimum) at construction time.

## 7. Finalization/ledger proof (item D)

`wait_for_stop_settlement` polls `observation_status`'s own
`state: Literal["stopped", "starting", "observing", "stopping", "needs_
attention"]` field until it genuinely reads `"stopped"` -- proven against
a scripted `"stopping" -> "stopping" -> "stopped"` sequence (settles on
the third poll, never mistaking the transient `"stopping"` state for
settled) and against a session that never settles (times out at the
configured bound, `settled=False`, never raises).

`stop_and_capture_final_snapshot` was proven to enforce the exact required
ordering (**Observation stop -> finalization settled -> final
authenticated raw-ledger snapshot**):
`test_stop_and_capture_final_snapshot_orders_stop_then_settle_then_
snapshot` uses a scripted ledger payload containing a candidate whose own
`decided_at` postdates the stop request -- the literal shape of v3's own
rescued candidate-012 -- and confirms exactly one ledger fetch is made,
only after settlement, and that fetch correctly contains the rescued
candidate. `test_stop_and_capture_final_snapshot_never_fetches_when_
settlement_times_out` confirms the inverse: when settlement times out,
`client.observation_counterfactual` is **never called at all**
(`snapshot_calls == []`) and the result is honestly `ready=False` --
never a pre-settlement fetch silently substituted as final.

**Completeness verdict already correct, now regression-locked.**
`test_reconcile_ledger_equal_recovered_and_recorded_counts_still_reports_
partial_when_a_real_gap_exists` (new) constructs two payloads whose
combined *unique record count* exactly equals the session's own true
final total (5 == 5, a naive count-equality check would call this
COMPLETE) but whose own reported retained-offset windows leave a real,
unproven 200ms gap between them, with the `_accumulate_artifact`
two-independent-payloads-corroboration shortcut deliberately *not*
triggered (the two payloads' own `recorded_count` values, 3 and 5,
disagree, so the shortcut correctly stays off). Result: `PARTIAL`,
`gaps_ms == [(400, 600)]` -- confirming the pre-existing
`reconcile_ledger` logic already implements "explicit completeness
verdict based on actual snapshot coverage, not merely equal record
counts" correctly; nothing was changed, only locked in.

## 8. Timestamp/fallback accounting (item E)

No classification changed. `capture_to_visible_latency.
build_latency_summary`'s own `LatencyState` partition already, correctly,
distinguishes every category governing brief §7 asks for: `"measured"`
(valid, RTT-normalized when a Camera Node is in the loop, or already
Host-compatible when not), `"unavailable_capture_time"` (missing
timestamp), `"invalid_clock_mapping"` (invalid clock mapping -- no
trustworthy RTT-bounded anchor covers this sample), `"invalid_negative"`/
`"implausible"` (timestamp artifact / other invalid reasons). This
codebase has no "fallback timestamp" concept anywhere -- `fallback_
measured_count` is a strict, additive *subset annotation* of `measured_
count` (an admission-arbitration fact, `is_fallback`), documented as such
now, both in the module's own docstring and in the CLI's stdout output.
`test_summary_fallback_measured_count_is_a_subset_of_measured_never_a_
lesser_calibration_state` (new) proves this at the `LatencySummary` level:
one ordinary and one fallback-admitted sample, both under real RTT-bounded
calibration, both count as `measured`; only the fallback one counts
toward `fallback_measured_count`; the fallback sample's own `clock_
calibration_state` is genuinely `"normalized"`, never a lesser/uncalibrated
state. Never silently promoted; never conflated with a different
category.

## 9. Deterministic validation

**Tier 1 (focused tooling tests), run individually and together:**

| File | Result |
|---|---|
| `test_field_acceptance_instance_lifecycle.py` | 46 passed (41 pre-existing + 5 new) |
| `test_deploy_windows_dev.py` | 145 passed (144 pre-existing + 1 new) |
| `test_field_acceptance_recorder_readiness.py` | 13 passed (all new) |
| `test_field_acceptance_session_driver.py` | 23 passed (all new) |
| `test_field_acceptance_ledger_snapshot.py` | 35 passed (34 pre-existing + 1 new) |
| `test_capture_to_visible_latency.py` | 25 passed (24 pre-existing + 1 new) |
| `test_run_gate_a_measurement_accounting.py` | 5 passed (unchanged) |
| `test_field_acceptance_client.py` / `test_field_acceptance_authentication.py` | pass, unmodified (no code touched) |

Combined focused run: **321 passed, 0 failed** (29.9s).

**Tier 2 (affected field-tooling/packaging/lifecycle, including the
real-`pip install` packaging suite):** the same set plus
`test_local_product_packaging.py` -- **404 passed, 0 failed** (6m57s; the
packaging suite's own real wheel-assembly step dominates the wall-clock
time and is unrelated to anything this milestone touched -- confirmed
unmodified, `build_local_product.py` was never edited).

**Tier 3:** not run. No cross-cutting production dependency was exposed --
every change is confined to `scripts/` tooling plus one docstring-and-test
addition in `capture_to_visible_latency.py` with zero logic change. Full
Core was not run, per the directive's own explicit instruction.

**Lint:** `ruff check` clean across every touched and new file (12 files),
confirmed in the same pass as the final test run.

**Real subprocess dry-run proof:** see §5, above -- the recorder-readiness
CLI's actual argparse/`main()` entry point, with real `time.sleep`, was
run twice against a real filesystem fixture (`ready`/exit 0, and
`not ready`/exit 1), plus `--help` smoke tests for both new CLI entry
points. No live product instance, Camera Node, or physical hardware was
used anywhere in this validation.

## 10. Remaining limitations (disclosed, not fixed -- out of this
milestone's own bounded scope)

- **`field_acceptance_session_driver.py run` was never dry-run against a
  live (even disposable-simulated) HTTP server** -- only its underlying
  functions (`run_stop_timing_loop`, `wait_for_stop_settlement`,
  `stop_and_capture_final_snapshot`), which the CLI's own `main()` calls
  as thin, unmodified wiring, were exercised (23 tests, a fake client).
  Standing up a fake HTTP server was judged out of scope given the
  directive's own "may use ... existing test fixture" wording already
  permits function-level fakes, and given "do not deploy the real product"
  -- the CLI layer itself was, however, smoke-tested for `--help`/argparse
  correctness via a real subprocess.
- **`--dev-root` process-liveness wiring in the recorder-readiness CLI was
  only proven for the "not running" (no `current.json`) short-circuit** --
  hermetically safe (zero real Windows/PowerShell I/O by construction, per
  `_probe_running`'s own documented short-circuit), but the "genuinely
  running" branch (which would exercise `windows_host.http_get`/
  `port_owner_pid` against a real port) was not separately proven here,
  since doing so would require either a real Windows host or a third fake
  -host fixture duplicated from `test_deploy_windows_dev.py`'s own
  established one -- judged unnecessary scope for this milestone, since
  that branch's own correctness is already covered by
  `field_acceptance_instance_lifecycle.py`'s own existing, passing test
  suite (46 tests), which this milestone did not need to re-prove.
- **The session driver's `sample_count_fn` default (`candidates_created`)
  remains an explicitly-documented progress proxy, not the final
  procedurally-valid sample count** -- unchanged from every prior field
  session's own established convention (the true valid/invalid split is
  computed after the fact by `run_gate_a_measurement_accounting.py`
  against the reconciled ledger); this milestone does not, and was not
  asked to, change that two-stage measurement architecture.
- **None of these four new/changed tools has yet been exercised together,
  end-to-end, in a real field session** -- this milestone is tooling
  correctness only; the next Lane R field tranche (not authorized by this
  milestone) is the first opportunity to prove the complete, integrated
  procedure live.

## 11. Decision

**A**

Every one of the five named procedural gaps is closed with deterministic,
hermetic tests (42 new tests across 6 files, all passing; zero
regressions across 404 directly-affected tests including the real
packaging-assembly suite); two are real, root-caused, precedented-fix
defects; two are new, independently-testable, bounded tools that close a
genuine "this has never been tracked or tested" gap; one is a
reporting/documentation clarification over already-correct logic, exactly
as the directive's own "improve only the reporting" instruction asked
for. No product, perception, classifier, schema, or T0/T5-contract change
anywhere. No push. No field session run. No hardware touched.
