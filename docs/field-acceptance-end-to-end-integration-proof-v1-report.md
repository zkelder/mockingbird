# Field Acceptance End-to-End Integration Proof v1

Bounded RELEASE-CRITICAL validation-and-correctness milestone, directly
authorized outside this file. Closes the three accepted integration
limitations *Field Acceptance Tooling Correctness & Preflight Closure v1*
itself named as out of its own bounded scope (its own §10, "Remaining
limitations") -- never a field session, never a deployment, never a
product/perception/schema change.

**Outcome: all three limitations closed with real, passing, repeatable
proofs against the actual, unmodified accepted tooling. No integration
defect was found or reproduced in production code -- every proof passed
cleanly against real, unmodified `scripts/field_acceptance_session_
driver.py`, `scripts/field_acceptance_recorder_readiness.py`,
`scripts/field_acceptance_instance_lifecycle.py`,
`scripts/field_acceptance_ledger_snapshot.py`,
`scripts/field_acceptance_client.py`, and
`scripts/run_gate_a_measurement_accounting.py`. Classification: A.**

## 1. Starting state

Verified directly, in the order the governing directive required, before
any other action:

- Repository: `/home/zkelder/projects/mockingbird-active`; branch `main`.
- Starting HEAD: `2e7e8e0` -- matches the directive's expected baseline
  exactly.
- Schema: `CURRENT_DATABASE_SCHEMA_VERSION = 59`
  (`src/mockingbird/storage/database.py:46`) -- matches.
- `docs/release-execution-state.md` `## CURRENT PHASE` section: `FEATURE
  FREEZE -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING`; §3's own bold line:
  `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`; Lane R (§6.R):
  `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS`. All
  match the directive's stated baseline exactly.
- Governing sources read in the directive's own required order:
  `docs/release-execution-state.md` (top-of-file phase section; targeted
  §1/§3 history spanning the full Gate A/Lane R evidence chain back through
  the 2026-08-19 primary cohort; §13/"Preserved untracked detector files";
  §16 -- confirmed by the file's own text to be stale, 2026-08-26-dated,
  narrative only), `docs/product-doctrine.md` (full), `docs/roadmap.md`
  (targeted: not required further once §1/§3's own restated "Numeric
  release budgets"/Gate A accounting was confirmed current), then
  `docs/field-acceptance-tooling-correctness-preflight-closure-v1-report.md`
  (full -- the direct source of the three limitations this milestone
  closes), `docs/representative-daylight-true-latency-tail-convergence-v3-report.md`
  (full -- the field session whose own procedural gaps motivated the prior
  milestone), and `docs/non-interactive-field-acceptance-authentication-
  session-access-v1-contract.md` (full -- "the accepted current field
  contract": the bearer-token authentication model and exact endpoint/
  permission matrix the fake HTTP service in this milestone mirrors).
- Directly affected code read in full before writing any test:
  `scripts/field_acceptance_session_driver.py`,
  `scripts/field_acceptance_recorder_readiness.py`,
  `scripts/field_acceptance_instance_lifecycle.py` (in full),
  `scripts/field_acceptance_ledger_snapshot.py` (in full),
  `scripts/field_acceptance_client.py`,
  `scripts/run_gate_a_measurement_accounting.py`,
  `scripts/deploy_windows_dev.py` (`WindowsHost`, `probe_port`,
  `verified_owning_release`, `real_windows_host`, `resolve_dev_root_path`,
  the real `_http_get_real`/`_port_owner_pid_real` PowerShell
  implementations), `src/mockingbird/observation/
  capture_to_visible_latency.py`, `src/mockingbird/observation/
  clock_calibration.py` (RTT-bounded epoch selection), and every existing
  test file for the above (`tests/test_field_acceptance_session_driver.py`,
  `tests/test_field_acceptance_recorder_readiness.py`,
  `tests/test_field_acceptance_instance_lifecycle.py`,
  `tests/test_deploy_windows_dev.py`, `tests/test_field_acceptance_client.py`)
  -- to reuse this project's own established real-subprocess/real-socket
  test conventions (`tests/_transport_fault_injection.py`,
  `tests/test_camera_node_real_process.py`) rather than inventing new ones.
- Worktree safety: no `.git/*.lock`; no stale MockingBird/uvicorn/vite
  process running in the sandbox (re-confirmed again at close). The seven
  preserved untracked detector files (`docs/wildlife-detector-training-
  contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) were confirmed present and
  unmodified at start and again at the end of this milestone.
- No push, no history rewrite, no real deploy, no field session, no
  physical hardware (Camera Node included) touched anywhere in this
  milestone -- confirmed by construction (no `deploy_windows_dev.py
  deploy`/Camera-Node/pairing call appears anywhere in this milestone's own
  work; every "deployed process" this milestone reasons about is the real,
  disposable local fake HTTP service described in §2, below).

## 2. The fake HTTP service (governing brief §3's exact requirement)

One real, disposable, stdlib-only `http.server.ThreadingHTTPServer` on a
real socket in a background daemon thread
(`tests/_field_acceptance_fake_service.py`) -- mirroring this repository's
own established precedent for a shared, non-`test_`-prefixed real-HTTP/
real-process test helper (`tests/_transport_fault_injection.py`,
`tests/test_camera_node_real_process.py`), never a monkeypatch of
`urllib.request.urlopen` (which the *existing* hermetic client tests
already use, and which cannot be reached by a real `subprocess`). Answers
exactly the accepted endpoint contracts
(docs/non-interactive-field-acceptance-authentication-session-access-v1-contract.md),
never a parallel production API:

| Route | Auth | Purpose |
|---|---|---|
| `GET /health` | public | `deploy_windows_dev.probe_port`'s own real liveness check (never sends a bearer token) |
| `GET /api/product/instance` | public | `probe_port`'s own real identity check -- `instance_id`/`git_commit`/`build_id`/`app_version` |
| `GET /api/product/health` | public | `field_acceptance_client.product_health` |
| `POST /api/streams/{id}/observation/start` | bearer | starts the fake Observation session |
| `POST /api/streams/{id}/observation/stop` | bearer | begins finalization (`state` -> `"stopping"`) |
| `GET /api/streams/{id}/observation/status` | bearer | `state`/`counts.candidates_created` -- see progression model, below |
| `GET /api/streams/{id}/observation/counterfactual` | bearer | the raw ledger -- see §6, below |
| `GET /api/streams/{id}/observation/scene-confusor-learning` | bearer | `field_acceptance_ledger_snapshot`'s own auxiliary artifact |

**Authenticated requests**, modeled exactly like the real product's own
`resolve_field_acceptance_token`: every protected route requires
`Authorization: Bearer <token>` matching the service's own configured
token, else `401`; the three public routes never check it at all (matching
`probe_port`'s own real behavior, which never sends the header, and
`field_acceptance_client.product_health`'s own "public, unauthenticated"
docstring).

**Observation start/status/stop, candidate-count progression,
stop-finalization pending -> settled**: `FakeObservationState.phase`
genuinely transitions `not_started -> observing -> stopping -> stopped`;
`status()` increments `counts.candidates_created` on every poll (a real,
live-progressing counter, exactly the shape the session driver's own
`_default_sample_count_fn` reads) and only settles `stopping -> stopped`
after a configurable number of distinct status polls (default 2) --
reporting the transient `"stopping"` state faithfully in between, the
exact state `wait_for_stop_settlement` must not mistake for settled.

**Raw-ledger snapshots, a candidate rescued during finalization, and
clock/latency data sufficient for accounting**: `counterfactual()` returns
a `CounterfactualWindowResponse`-shaped payload with two track generations
and two ordinary admitted proposal outcomes present from the start, plus a
**third**, `proposal-3-rescued`, that only appears once `phase == "stopped"`
-- reusing generation-1 and an ambiguous-boundary-arbitration fallback
`reason` suffix (`:fallback_position_2`), the exact shape *Representative
Daylight True-Latency Tail Convergence v3*'s own candidate-012 established
(`decided_at` after the stop request). One of the two ordinary generations
(`generation-2`) deliberately carries no `start_captured_at` at all -- a
real, accepted "this predates capture" shape
(`capture_to_visible_latency._resolve_t0`'s own docstring) -- so its own
proposal resolves honestly to `unavailable_capture_time`, never a crash.
Every timestamp fact is computed exactly once (construction time, or the
instant settlement genuinely occurs) and never re-derived on a later
fetch, matching `field_acceptance_ledger_snapshot`'s own `(proposal_id,
decided_at)` deduplication identity for `proposal_outcomes` -- a per-fetch
-recomputed timestamp would silently defeat that identity instead of
modeling a stable decision fact. `coverage` per artifact is reported
honestly (the real `oldest`/`newest_retained_offset_ms` bounds of whatever
records that fetch actually contains, never a "proven from session start"
shortcut invented for convenience) -- see §7, below, for why this produces
a genuine, structurally-unavoidable `PARTIAL` reconciliation, the same
honest shape the real product's own v3 field report recorded.

`write_fake_dev_root()` builds the minimal, real `releases/deployments.json`
(`deploy_windows_dev.ReleaseRecord.as_dict()`-shaped) and `releases/
current.json` (`CurrentPointer.as_dict()`-shaped) files
`field_acceptance_instance_lifecycle.py`'s own `_probe_running`/
`init_instance` read directly from disk -- built by hand, never through a
real multi-gigabyte `deploy_windows_dev.py deploy`, per this milestone's
own "do not deploy the real product" bound.

## 3. Real CLI / fake HTTP proof (governing brief §3)

`tests/test_field_acceptance_session_driver_real_cli.py` -- six tests, all
exercising the actual `field_acceptance_session_driver.py run` entry point
through a real `subprocess.run([sys.executable, ...])`, never only the
function-level calls the pre-existing 23-test hermetic suite already
covers:

- **Target reached, finalization settles, a rescued candidate is
  captured**: tiny-but-real `--minimum-duration-seconds
  1 --target-sample-count 2 --poll-interval-seconds 1`. Exit `0`; stdout
  shows `Stop decision: target_reached_after_minimum_duration` then
  `Finalization: settled_before_snapshot`; both output JSON files are
  written; the final snapshot's own `proposal_outcomes` contains
  `proposal-3-rescued`.
- **The hard maximum fires when the target is never reached**:
  `--target-sample-count 999 --maximum-duration-seconds 3`. Exit `0`;
  stdout shows `Stop decision: maximum_duration_reached`.
- **A genuine settlement timeout is an honest, non-zero-exit outcome**: a
  second fake-service instance configured to never settle
  (`stopping_polls_to_settle=1_000_000`) with
  `--stop-settlement-timeout-seconds 3`. Exit `1`; stdout contains
  `stop_settlement_timed_out`; the finalization-report file is still
  written (unconditionally), but the final-snapshot file is **not** --
  proving a pre-settlement fetch is never substituted as final, exercised
  through the real CLI's own file-writing logic, not merely the function
  -level `FinalizationResult` this milestone's predecessor already tested.
- **Authenticated requests, both failure shapes, through the real exit
  status**: a wrong bearer token (`MOCKINGBIRD_ACCEPTANCE_TOKEN` set,
  server genuinely returns `401`) and no token configured at all (the
  local, pre-network `FieldAcceptanceCredentialMissingError`) both exit
  `1` with a clear `ERROR:` line on stderr -- the real client's own error
  taxonomy, surfaced through the real CLI's own top-level exception
  handling, never a raw traceback.
- **`--help` stays a real, zero-dependency argparse smoke path.**

All six pass; `MOCKINGBIRD_ACCEPTANCE_TOKEN`/`--stream-id`/`--base-url`
plumbing, real `time.sleep`/`time.monotonic`, real JSON file output, and
real process exit status are all exercised end to end. 15.2s wall-clock
for all six (real HTTP round trips only -- no test waits anywhere near the
production 45/75-minute contract; see §5 for how the full-scale contract
is proven without a real wait).

## 4. Process-liveness proof (governing brief §4)

`tests/test_field_acceptance_recorder_readiness_process_liveness.py` --
four tests proving `field_acceptance_recorder_readiness.py`'s `--dev-root`
process-liveness branch through the real, **unmodified**
`deploy_windows_dev.real_windows_host()` -- real `powershell.exe`, never a
fake/mocked `WindowsHost` (the pre-existing 46-test hermetic suite already
covers that fake-host path exhaustively; this closes exactly the one gap
the prior milestone's own §10 disclosed: "the 'genuinely running' branch
... was not separately proven here").

**Empirical prerequisite, confirmed directly before writing any test**: a
plain WSL-side Python `http.server` bound to `127.0.0.1:<port>` **is**
reachable from the real native Windows host in this sandbox --
`Invoke-WebRequest -Uri http://127.0.0.1:<port>/health` returns `200`, and
`Get-NetTCPConnection -LocalPort <port> -State Listen` reports a real
owning process -- via WSL2's own live localhost-forwarding. This is the
empirical fact that makes "a genuinely running disposable process" mean
"the real fake HTTP service," with zero need to deploy anything onto the
Windows side directly.

- **Positive liveness, correct process identification, correct intended
  instance**: the fake service's own `(git_commit, build_id)` pair is
  recorded in the dev-root's own `deployments.json`, and `current.json`
  points at its real port. Combined with real, concurrently-written
  advancing frame evidence (a real background thread), the CLI reports
  `process_alive: true` **and** `ready: true`. Exit `0`.
- **Absent/stopped process fails closed, no polling attempted**: the
  service is genuinely stopped before the CLI ever runs. `process_alive:
  false`, `reason` starts with `recorder_process_not_alive`, `poll_count
  == 0` -- the recording-root is never even consulted (never created).
  Exit `1`.
- **No false success from a stale pointer / unrelated process**: a
  *second* dev-root's own `deployments.json` records a **different**,
  non-matching `(git_commit, build_id)` pair while its `current.json`
  points at the **same** real, genuinely-running port as the first dev
  -root -- the precise "a stale `current.json` reused by an unrelated
  instance after a restart" shape. `process_alive: false`, `poll_count ==
  0`. Exit `1`. The real process is never mistaken for this dev-root's own,
  even though it genuinely answers the port.
- **No recorded launch pointer at all**: the pre-existing hermetic
  short-circuit, re-confirmed here through the real CLI/subprocess
  boundary (not only the direct function call the existing 13-test suite
  already covers).

All four pass; cleanup is explicit and verified in every test (the fake
service's own background thread joined/stopped, the frame-writer thread
joined) -- no orphaned process anywhere. 17.5s wall-clock for all four
(dominated by real `powershell.exe` process-spawn overhead, ~2-4s per
liveness check -- consistent with this project's own standing
"fragile, re-smoke-test each session" note on real Windows interop; no
flake was observed across repeated runs during this milestone).

## 5. Complete integration sequence (governing brief §5)

`tests/test_field_acceptance_end_to_end_integration.py` -- two tests. No
single existing orchestration entry point runs this whole sequence, so
(per the governing brief's own explicit allowance) this file *is* the
small test harness: it composes the real, accepted tools directly --
real `subprocess` calls for the steps that are fast regardless
(`init`/`complete`/`mark-archived`/`cleanup`, ledger reconciliation,
latency accounting), and the real, unmodified driver/collector functions
directly, with a fake monotonic clock standing in for the 45/75-minute
Observation contract (per the governing brief's own explicit "use fake
time ... so the test does not consume a real field window") -- while every
HTTP call underneath is still genuinely made, over a real socket, to the
same fake service.

**`test_recorder_failure_prevents_observation_start`**: an empty
recording-root, a 2-second real readiness timeout -- the CLI genuinely
fails (`ready: false`, exit `1`). The harness's own gate (mirroring the
"STOP BEFORE OBSERVATION" contract every real field procedure already
follows by hand) is proven, not merely asserted: `state.phase` on the fake
service is confirmed still `"not_started"` afterward -- `start_observation`
was never called. No production code enforces this ordering automatically
(the readiness check is a deliberately independent tool); this proves the
accepted *procedure* holds end to end.

**`test_complete_field_acceptance_sequence_end_to_end`** runs the full
chain once:

1. **lifecycle init** -- real subprocess
   (`field_acceptance_instance_lifecycle.py init --dev-root ...`) against
   a hand-built `deployments.json`/`current.json` pointing at the real
   fake service. `lifecycle_state: "active"`.
2. **recorder setup/readiness** -- real subprocess, with a real background
   thread writing 20 real advancing frame files (0.5s cadence) into the
   real `--dev-root`'s process-liveness branch (§4's own mechanism) --
   `ready: true`, `process_alive: true`. Real advancing frame files permit
   the next step; the writer thread is joined and confirmed stopped
   immediately after.
3. **authenticated Observation start** -- the real `FieldAcceptanceClient`
   class, a real HTTP `POST`. `state.phase == "observing"` confirmed.
4. **monotonic session driver, at the real, unmodified
   `SessionDriverConfig()` defaults** (45-minute minimum / 75-minute
   maximum / 12-sample target), with `poll_interval_seconds` deliberately
   overridden to `37` (a value that does **not** evenly divide either
   bound) so the timing proofs below are meaningful, not incidental:
   - **early sample quota does not bypass the minimum duration**: with
     `sample_count_fn` returning `999` (target already met from `t=0`,`
     on an isolated throwaway clock), the loop still runs to (and only
     stops at the first poll at-or-after) the real 45-minute minimum --
     never before it. Unlike the maximum, the minimum is a floor with no
     exact-landing guarantee of its own (only the maximum's own deadline
     is clamped to land exactly, per `run_stop_timing_loop`'s own
     documented contract) -- confirmed as existing, intentional,
     accepted behavior, not a defect.
   - **the 75-minute deadline does not wait for a polling tick**: with
     `sample_count_fn` returning `0` (target never reached), `timing.
     elapsed_seconds == 4500.0` **exactly** -- even at the deliberately
     non-dividing 37-second poll interval, confirming the existing
     "clamp every sleep to never carry elapsed_seconds past the maximum"
     logic holds at real production-scale numbers, not only the smaller
     values the pre-existing unit test already used for this exact
     property.
5. **stop -> 6. finalization settled -> 7. final raw-ledger snapshot**:
   `stop_and_capture_final_snapshot`, same fake clock. `finalization.ready
   is True`; settlement genuinely settled; the final snapshot's own
   `proposal_outcomes` contains `proposal-3-rescued`.
   **Finalization does not extend Observation duration**: `finalization.
   settlement.elapsed_seconds` is reported entirely separately from (and
   is far smaller than) `timing.elapsed_seconds`, which is asserted
   unchanged (`== 4500.0`) after finalization completes -- the two timing
   loops share no combined "total session duration" accumulator by
   construction.
8. **collector shutdown**: `run_periodic_collection(..., max_checkpoints=2)`
   -- called *while* still observing (matching `field_acceptance_ledger_
   snapshot.py`'s own documented real-session sequence: collect
   throughout, one corrective fetch after stop), a clean, bounded stop at
   exactly 2 checkpoints, each containing only the two *ordinary*
   candidates (never the one only created during finalization, which
   hadn't happened yet).
9. **reconciliation** -- real subprocess
   (`field_acceptance_ledger_snapshot.py reconcile --snapshot-dir ...
   --final-snapshot ... --merged-output ...`). **Incomplete coverage
   remains honestly `PARTIAL`**: `overall_status: "PARTIAL"` (exit `1`,
   matching the tool's own "0 only when every artifact reconciles
   COMPLETE" contract) -- `track_generations` and `raw_detections`
   reconcile `COMPLETE` (the former via the tool's own real, pre-existing
   "two independent payloads corroborate an unchanged final count"
   shortcut; the latter a genuine zero), while `proposal_outcomes` shows a
   real, structurally-unavoidable gap (nothing proven before the first
   decision, nothing after the last, up to the session's own reported
   duration) -- the same honest shape the real product's own v3 field
   report recorded, never an invented defect.
10. **latency accounting** -- real subprocess
    (`run_gate_a_measurement_accounting.py --input <merged ledger>`), fed
    directly with the exact merged-ledger file step 9 just produced (never
    a second, hand-built input). **Invalid/fallback timestamps remain
    honestly classified**: `measured_count: 2`, `unavailable_capture_time_
    count: 1` (the deliberately-anchor-less `proposal-2`, correctly
    classified, never crashed on), `fallback_measured_count: 1`
    (`proposal-3-rescued`, correctly counted as a *subset* of `measured`,
    per `capture_to_visible_latency.build_latency_summary`'s own already
    -correct, unmodified semantics -- not re-derived or re-tested here,
    only proven to survive intact through this whole real pipeline).
11. **cleanup** -- real subprocess. The deployed process is genuinely
    stopped first (`service.stop()`, mirroring the accepted
    `deploy_windows_dev.py --dev-root <root> --stop` convention this
    milestone's fake service stands in for) -- `complete` correctly
    refuses otherwise, per the tool's own accepted contract, and is not
    exercised in the refused state here (that path is already covered by
    the pre-existing 46-test lifecycle suite). `complete ->
    lifecycle_state: "completed"`; `mark-archived` against a real,
    contract-satisfying evidence archive (one `.md` report, one raw JSON
    data file) `-> lifecycle_state: "archived"`. **Cleanup is idempotent**:
    a dry-run `cleanup` (no `--destroy`) run twice in a row reports
    `blocked: false` and byte-identical `will_remove` plans both times,
    and never removes anything (`dev_root` still exists afterward) --
    see §8's "Remaining limitations" for why this milestone deliberately
    stopped short of the real destructive `--destroy` path specifically.
    **No orphaned processes**: the fake service's own background thread
    and the frame-writer thread are both explicitly confirmed stopped/
    joined before the test ends.

Both tests pass. 24.7s wall-clock for the full sequence (dominated by the
~195 real-but-fast HTTP round trips the 37-second-poll-interval timing
loops make against the fake service, plus five real `powershell.exe`
-touching subprocess calls in steps 1/2/11).

## 6. Timing/deadline proof

Covered directly in §5, item 4, above (the two properties governing brief
§9 names -- early-quota-does-not-bypass-minimum,
maximum-fires-exactly-never-late -- both proven at the real, unmodified
`SessionDriverConfig()` production defaults, not scaled-down substitutes).

## 7. Recorder and ledger completeness proof

Covered directly in §5, items 2 and 9, above.

## 8. Timestamp accounting

Covered directly in §5, item 10, above.

## 9. Reproduced defects and fixes

**None in production code.** Every one of the three named integration
limitations closed cleanly against real, unmodified accepted code on the
first genuine end-to-end attempt. The only bugs found and fixed during
this milestone were in this milestone's own new test code, all caught and
corrected before any test was reported as passing:

- An initial assumption that `field_acceptance_ledger_snapshot.py
  reconcile --json --merged-output <path>`'s stdout is pure JSON --
  it is the JSON report followed by one additional plain "Wrote merged
  ledger ..." line (`_cmd_reconcile`'s own, correct, pre-existing
  behavior). Fixed in the test only, using `json.JSONDecoder().raw_decode`
  to read just the leading JSON value.
- An initial test scenario passed `sample_count_fn=lambda: 999_999`
  intending to prove the 75-minute-maximum path, which instead correctly
  exercised the 45-minute-minimum path (`decide_stop` checks the maximum
  before the minimum/target combination, but an *already-met* target still
  fires at the minimum, not the maximum -- exactly as documented). Fixed
  by splitting into two distinct scenarios (an isolated early-quota check
  and a separate never-reached-target check), which also improved the
  proof's own clarity.
- An initial assertion expected `early_quota_timing.elapsed_seconds ==
  2700.0` exactly at a deliberately non-dividing 37-second poll interval
  -- only the *maximum* deadline is clamped to land exactly; the minimum
  is a floor the loop can (correctly, per its own documented contract)
  overshoot by up to one poll interval. Fixed by asserting the correct,
  weaker, still-meaningful bound (`>= minimum`, `< minimum +
  poll_interval`).

No detector, classifier, threshold, tracker, admission, Visit-assembly,
T0/T5-definition, clock-calibration-algorithm, evidence-selection, schema,
or production-configuration file was read for the purpose of changing it,
and none was changed.

## 10. Validation

**Tier 1 (focused new integration tests):**

| File | Result |
|---|---|
| `tests/test_field_acceptance_session_driver_real_cli.py` | 6 passed |
| `tests/test_field_acceptance_recorder_readiness_process_liveness.py` | 4 passed |
| `tests/test_field_acceptance_end_to_end_integration.py` | 2 passed |

12 new tests total, all passing, stable across every repeated run during
this milestone's own development and final validation (no flake
observed). All three files are `pytest.mark.slow` (real subprocess/real
-socket/real-`powershell.exe` coverage -- Tier C per
docs/test-suite-validation-tiers-contract.md), confirmed correctly
excluded from a `pytest -m "not slow"` run (`12 deselected, 0 selected`),
so the Fast (`verify_fast.py`) and Core (`verify_core.py`) gates are
unaffected.

**Tier 2 (affected field-tooling/lifecycle/packaging tests -- regression
check against the pre-existing suite this milestone's new tests sit
beside):**

```
tests/test_field_acceptance_instance_lifecycle.py
tests/test_deploy_windows_dev.py
tests/test_field_acceptance_recorder_readiness.py
tests/test_field_acceptance_session_driver.py
tests/test_field_acceptance_ledger_snapshot.py
tests/test_capture_to_visible_latency.py
tests/test_run_gate_a_measurement_accounting.py
tests/test_field_acceptance_client.py
tests/test_field_acceptance_authentication.py
+ this milestone's own 3 new files
```

**333 passed, 0 failed** (94-98s across repeated runs). Zero regressions.

**Tier 3:** not run. No production code was changed anywhere in this
milestone -- no cross-cutting production dependency was introduced, per
the governing directive's own instruction ("No full Core unless an actual
cross-cutting production dependency is introduced").

**Lint:** `ruff check` clean across all four new files.

**Worktree:** the seven preserved untracked detector files reconfirmed
present and byte-identical-by-presence at the end of this milestone; `git
status` shows exactly this milestone's own four new untracked files
(`tests/_field_acceptance_fake_service.py` and the three `test_field_
acceptance_*` files above) alongside the seven preserved files -- nothing
else. HEAD unchanged at the start of this milestone's own commit(s)
(`2e7e8e0`).

## 11. Remaining limitations (disclosed, not fixed -- out of this
milestone's own bounded scope)

- **`cleanup --destroy`'s real, destructive Windows-native removal
  mechanics (`cmd.exe /c rmdir /s /q` against a translated UNC path) were
  not exercised in this milestone's own complete-sequence proof** -- only
  the non-destructive dry-run path. The dev-root used throughout this
  milestone is a plain WSL-native `tmp_path` directory, not a real
  `/mnt/c/...` Windows path; routing a real destructive removal through
  `wslpath -w`/a `\\wsl.localhost\...` UNC share for a directory this
  milestone's own fake harness created was judged a real, unnecessary risk
  for this proof's own marginal benefit -- `execute_cleanup`'s real
  destructive-removal logic is already thoroughly covered by
  `tests/test_field_acceptance_instance_lifecycle.py`'s own 46 tests
  (against a fake `WindowsHost`), which this milestone did not need to
  re-prove. "Cleanup leaves no orphaned processes" (the literal governing
  requirement) is proven directly instead: the fake service's own
  background thread and every frame-writer thread are explicitly
  confirmed stopped in every test.
- **`complete`'s own refusal-while-still-running branch was not
  separately re-proven here** -- already covered by the pre-existing
  lifecycle test suite; this milestone's own sequence stops the fake
  service before calling `complete`, matching the accepted real-world
  order of operations rather than deliberately testing the refusal a
  second time.
- **The three-candidate raw-ledger shape this milestone's fake service
  produces is deliberately minimal** (two ordinary admissions plus one
  rescued), not a full recreation of the ~250-2,300-event volume a real
  75-minute field session produces. This is appropriate for an
  *integration* proof (proving the pieces connect and pass real data
  correctly to one another) and is not intended to, and does not, add any
  new evidence toward Lane R's own true-latency-tail convergence question
  -- that remains exactly as `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY
  TAIL EVIDENCE REMAINS` as it was before this milestone, unmoved by
  anything in this report.
- **No real field session, real Camera Node, or real deployed product
  instance was used anywhere in this milestone** -- by design, per the
  governing directive's own explicit bound. The next genuine daylight Lane
  R tranche remains the only way to add real evidence toward that specific
  question; this milestone closes tooling-integration confidence ahead of
  it, nothing more.

## 12. Decision

**A**

All three integration limitations *Field Acceptance Tooling Correctness &
Preflight Closure v1* named as out of its own scope are closed with real,
repeatable, passing proofs against the actual, unmodified accepted tooling
-- 12 new tests, zero regressions across 333 directly-affected tests, zero
production code changed, zero defects found needing correction. This
closure does **not** declare Gate A passed, does **not** close Lane R
(unchanged: `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
REMAINS`), and does **not** authorize the next Representative Field
Acceptance tranche, External Pre-Release Acceptance, or Final Release
Hardening. No push. No field session run. No hardware touched.
