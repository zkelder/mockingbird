# Release Reliability & First-Run Recovery v1

**Type:** Bounded release-readiness milestone under the durable feature
freeze, authorized by the external (ChatGPT) global-roadmap reconciliation
following its review of the read-only reconciliation performed at HEAD
`d58569f`. Does not reopen Gate A, start Gate G (External Pre-Release
Acceptance) or Final Release Hardening, recruit a participant, distribute a
build, or change production detector/identification policy.

**Classification: A** -- see "Classification," at the end.

---

## 0. Executive summary

Closed three small, disclosed, non-blocking gaps named across recent
acceptance work: Doctor's Storage-check false-`FAIL` on a normal pre-wizard
instance (disclosed in *External Pre-Release Acceptance -- Private Cohort
v1*, §3.7); the lack of any real graceful-stop mechanism, which made every
documented stop method report "did not shut down cleanly" even for an
entirely deliberate stop; and Gate E's own two named "open, not yet built"
Camera Node visibility gaps -- no check of the Node's own storage/free-space
health, and no undervoltage/throttling/temperature telemetry.

**Verified the expected baseline exactly** (§1): HEAD `d58569f`, schema
v59, worktree clean except the seven preserved untracked detector files, no
active competing writer.

**Item 1 (Storage false-`FAIL`), fixed** (§2): root cause confirmed exactly
as previously disclosed -- `_interpret_storage`'s informational-PASS branch
was gated on raw database-file existence, but the database file is created
at server-process startup itself, before the first-run wizard ever reaches
its Storage step. Fixed by additionally checking whether any real Source has
ever been configured (a cheap existence query against the same `Engine`
`_gather_camera_node` already uses -- no new database dependency). Found and
worked around a real, previously-unknown wrinkle during implementation: a
bare `ProductRepository()` construction seeds one walkthrough demo Source by
design (`source-backyard-demo`) -- naively counting it would have made this
check report "established" on every fresh install, defeating its own
purpose; the fix explicitly excludes it, mirroring `remove_sample_data`'s
own identical exclusion.

**Item 2 (graceful-stop / shutdown-status UX), implemented** (§3): a new,
Administrator-authenticated `POST /api/product/shutdown` lets a user stop
MockingBird from *inside* the still-running process, flipping the real
`uvicorn.Server.should_exit` flag `runtime.py` now publishes on
`app.state` -- uvicorn's own documented in-process stop mechanism, driving
the exact same graceful shutdown sequence (including the pre-existing,
unmodified `mark_clean_shutdown()` call) an interactive terminal's Ctrl+C
already triggers. A new "Shut Down MockingBird" control on the Local
Data/Settings page calls it. Neither of the product's own two prior stop
methods was changed or removed; both remain available and, being genuine
external terminations, honestly continue to report "did not shut down
cleanly" -- this milestone adds a real graceful alternative rather than
reinterpreting what an external kill actually is.

**Item 3 (Camera Node storage/hardware-quality visibility), implemented**
(§4): new `mockingbird_node/hardware_health.py` -- disk free-space health
(reusing the Host's own already-accepted graduated tier thresholds,
duplicated per this package's established cross-boundary convention) and
`vcgencmd`-based undervoltage/throttling/temperature facts, capability-gated
to `None` off Raspberry Pi. Both are exposed as new, freshly-probed
`/node/v1/health` fields and degrade `run_startup_self_test`'s own result
when critical -- the same already-product-visible mechanism a missing
camera already uses, not a new alerting channel.

**Two real, previously-unknown defects were found and fixed by this
milestone's own validation, not shipped**: (a) `runtime.py`'s switch from
`uvicorn.run(...)` to an explicit `Config`+`Server` construction silently
broke two existing tests' `uvicorn.run` mocks, which would have made a real
`uvicorn.Server` actually bind a socket and block forever inside a test
process -- caught live when the Fast gate itself hung; fixed by updating
both mocks to the equivalent `Server.run` no-op. (b) The new
`hardware_health.py` module was omitted from `NODE_FILES`, the Camera Node
artifact builder's explicit file manifest -- a real packaged Node would have
raised `ModuleNotFoundError` at startup, the identical class of gap this
exact manifest has now caught a third time (see the dated code comment).
Both are disclosed in full below, not merely fixed silently.

**Real hardware verification performed, not simulated** (§5): items 1-2
proven end-to-end on real native-Windows hardware (a hot-patched, disposable
copy of an existing verified dev-deployment release, never the real user
data path) -- Doctor's Storage check reads `PASS` on a genuinely fresh,
zero-camera instance; the new shutdown endpoint was called over real HTTP,
the real OS process exited on its own, and `runtime_state.json` read
`{"state": "clean"}` immediately after, confirmed again by a second real
Doctor run reporting `Application: PASS`. Item 3's parsing was verified
directly against the real reference Camera Node (Raspberry Pi) over SSH,
both before writing the parser (capturing real `vcgencmd` output) and after
(running the actual new module against real hardware). All real-hardware
artifacts were cleaned up; the reference Pi's installed service and the
Windows dev-deployment release were both restored to their exact prior
state.

**Validation** (§6): Fast gate 1801/1801 passed (0 failed); Core gate 5969
passed / 4 failed / 4 skipped / 35 deselected / 11 xfailed -- all four
failures independently confirmed to be the identical, long-standing,
real-wall-clock-date/load-timing-sensitive flakes this project has recorded
across at least nine prior milestone checkpoints, in files this milestone
never touched. `ruff` clean and frontend `tsc`/`vite build` clean on every
changed file.

**No product/schema/detector/identification-policy change.** Schema
unchanged (v59). No push. All seven preserved untracked detector files
confirmed present, untracked, and byte-identical before and after this
milestone.

---

## 1. Verified baseline

| Fact | Expected | Verified |
|---|---|---|
| Branch | `main` | `main` |
| HEAD | `d58569f` | `d58569f18f04d5f338710370d6561f96dca09928` (`git rev-parse HEAD`) |
| Schema | v59 | `CURRENT_DATABASE_SCHEMA_VERSION = 59` (`src/mockingbird/storage/database.py:46`) |
| Latest accepted milestone | External Pre-Release Acceptance -- Private Cohort v1 | Confirmed -- `d58569f` is that milestone's own reconciliation commit |
| Current authorization (going in) | `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED` | Confirmed, then explicitly superseded by this milestone's own governing directive |
| Worktree | Clean except the seven preserved files | Confirmed byte-identical to the list below, both at the start and immediately before this report's own publication |
| Active writers | None expected | No `mockingbird`/`uvicorn`/`camera_node`/`deploy_windows_dev`/`build_local_product`/`pytest` process running at start; `git stash list` empty |
| Push state | Not pushed | Unchanged by this milestone |

**The seven preserved untracked detector files** (confirmed present,
untracked, and byte-hash-identical at the start, throughout -- including
across every real-hardware verification step -- and immediately before this
report's own publication):

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

No discrepancy was found between the governing directive's expected
baseline and repository evidence.

---

## 2. Item 1: Doctor Storage false-`FAIL` during normal first-run setup

### 2.1 Root cause

`_interpret_storage` (`src/mockingbird/diagnostics/doctor.py`) has a
deliberate "nothing is wrong yet" informational-`PASS` branch for a missing
media root, but it was gated only on `database_exists` -- a raw
`sqlite_database_path(...).is_file()` check. The database file is created
the moment the server process starts (`runtime_state.prepare_runtime_state`
writes it before anything else), which happens well before a user reaches
the first-run wizard's Storage step, let alone finishes it. Any participant
who ran `doctor` mid-setup -- exactly what this product's own onboarding and
Gate G participant materials ask them to do -- saw an alarming `FAIL`/
`BLOCKING` "genuine problem" message during entirely normal first-run setup.

### 2.2 Fix

Added `_gather_has_any_source_configured` (`doctor.py`): a cheap
`SELECT ... LIMIT 1` against `CameraSourceModel`, reusing the same already-
open `Engine` the Camera Node check already reads from -- no new database
dependency, consistent with Doctor's own "read-only, never construct a
`ProductRepository`" design invariant. `_interpret_storage`'s branch now
reads informational-`PASS` when *either* the database does not exist yet
*or* no real Source has ever been configured -- both honestly mean "nothing
has ever had a reason to write to the media root yet." `None` (no engine
reachable at all) degrades the same way as `False` -- never escalate to
`BLOCKING` on a fact this check could not actually confirm.

**A real wrinkle found during implementation, not assumed:** a bare
`ProductRepository(db_url=..., media_root=...)` construction seeds one
walkthrough demo Source (`source-backyard-demo`) by design -- confirmed
directly (a standalone, non-pytest script) before writing the exclusion, not
inferred. Counting it would have defeated this fix's own purpose (it would
report "established" on literally every fresh install). Excluded by id,
mirroring `remove_sample_data`'s own identical, already-accepted exclusion
of the same id.

### 2.3 What did not change

The genuine-problem case is unaffected: once a real Source is configured and
the media root is still missing, `_interpret_storage` still reports `FAIL`/
`BLOCKING`, unchanged. No other Storage tier (`getting_low`/
`action_recommended`/`critical`) or export-root logic was touched.

---

## 3. Item 2: Graceful-stop and shutdown-status UX contract

### 3.1 Investigation

MockingBird's packaged Windows product has exactly two documented stop
methods: closing the browser tab (never reaches the backend process --
confirmed by inspection, not assumed) and ending `pythonw.exe`/`python.exe`
in Task Manager. The latter is an external OS-level termination; Windows
offers no reliable way for a windowless (`pythonw.exe`) process to intercept
it gracefully, and this project's own prior real-hardware acceptance already
confirmed both existing methods leave the next launch reporting "did not
shut down cleanly" (*External Pre-Release Acceptance -- Private Cohort v1*
§3.6). The existing `_app_lifespan` teardown (`api/main.py`) already ends
correctly, with `mark_clean_shutdown()` called last -- the gap was never in
that teardown logic; it was that nothing could ever reach it under either
documented stop method.

### 3.2 Contract

The smallest coherent fix is a real, in-app way to trigger that *same*
existing teardown from *inside* the running process, where it can actually
run:

- `runtime.py`'s `run()` now constructs `uvicorn.Config`+`uvicorn.Server`
  explicitly (previously the `uvicorn.run(...)` convenience wrapper, which
  never exposes the `Server` it builds internally) and publishes the real
  `Server` on `app.state.uvicorn_server` -- mirroring exactly how
  `bind_host`/`bind_port`/`network_access_allowed` are already published
  from the one place that actually knows them.
- New `POST /api/product/shutdown` (Administrator-tier, registered in
  `auth.py` alongside the other camera/storage operational controls) sets
  `uvicorn_server.should_exit = True` -- uvicorn's own documented in-process
  stop signal, noticed by its main loop on its very next iteration, driving
  the identical graceful shutdown sequence a terminal's Ctrl+C already
  triggers. Never calls `mark_clean_shutdown()` directly: if any step of the
  existing teardown were to fail or hang, the run must still, correctly, not
  be marked clean. `accepted=false` (never a crash) when no real `Server` is
  published -- the same honest degrade `ProductInstanceIdentity`/
  `ProductConnectionInfo` already use for their own launch-only facts.
- A new "Shut Down MockingBird" control on the Local Data/Settings page
  (`LocalDataPage.tsx`), matching the existing "Reset Demo Data" confirm-
  then-act pattern exactly, calls it.

### 3.3 What did not change

Neither prior stop method was altered, and neither is expected to newly
report clean -- an external kill genuinely is what it is, and this product's
own doctrine (never fabricate certainty) argues against trying to make that
read as "clean" by relaxing the marker's own meaning. This milestone adds a
real alternative rather than reinterpreting the existing one.

---

## 4. Item 3: Camera Node storage/media-health and hardware-quality visibility

### 4.1 Scope, per Gate E's own named gaps

`release-execution-state.md`'s Gate E field-failure matrix named two
concrete, still-open items: "nothing today checks the node's own free
space, write pressure, or... filesystem/storage health," and no
undervoltage/throttling/CPU-temperature telemetry existed at all.

### 4.2 Implementation

New `mockingbird_node/hardware_health.py`, mirroring `identity.py`'s own
"read-only, best-effort, never fabricate a value the real platform cannot
confirm" shape:

- `read_storage_health(directory)`: reuses the Host's own already-accepted
  graduated healthy/getting_low/action_recommended/critical tier thresholds
  (`mockingbird.storage.database`) -- duplicated, not imported (this
  package is a separate, deliberately slim installable and must not depend
  on the main `mockingbird` package; matches `doctor.py`'s own identical
  `_DOCTOR_NODE_API_VERSION` duplication precedent). Probes the Node's own
  pairing/config state directory -- the one local storage consumer every
  supported install has, regardless of whether the opt-in transport spool
  (which already has its own independent, already-accepted `min_free_bytes`
  guard) is configured.
- `read_hardware_quality()`: `vcgencmd get_throttled`/`measure_temp`,
  capability-gated on `shutil.which("vcgencmd")` -- `None` entirely off
  Raspberry Pi. Distinguishes a *currently* active undervoltage/throttling
  condition from one that merely *occurred* at some point since boot; only
  the former marks the Node degraded. Parsing verified directly against
  real captured reference-hardware output (`throttled=0x0`, `temp=47.7'C`)
  before being written.
- `run_startup_self_test` (`selftest.py`) now optionally takes
  `storage_directory` and unconditionally checks hardware quality, adding
  `storage_critically_low`/`hardware_quality_critical` reason codes to its
  existing `degraded` mechanism -- the same one a missing camera already
  uses.
- `/node/v1/health` gains two new, additive, freshly-probed-per-request
  fields, `storage` and `hardware` -- unlike `self_test` (a one-time startup
  snapshot), these change over a Node's uptime and are read fresh on every
  request, matching how `os_uptime_seconds`/`cameras` already work.

### 4.3 Bounded, actionable storage-pressure response

The golden-path Camera Node has no local storage consumer of its own beyond
pairing/config state and optional logs -- the actionable response this
milestone builds is visibility through the already-established self-test/
health-degradation mechanism, not a new alerting channel or a schema change.

### 4.4 Deliberately not built

Persisting these facts durably on the Host (`CameraSourceModel`'s own
checkpointed boot-identity columns): confirmed directly that the Host's
Camera Node Doctor check (`_gather_camera_node`) reads only the database,
never a live `/node/v1/health` poll -- adding a new checkpoint cadence plus
a schema migration for two visibility facts was judged materially larger
than this milestone's own bounded scope. Recorded as open follow-up, not
silently dropped -- see "Remaining limitations," below.

---

## 5. Real hardware verification

### 5.1 Native Windows (items 1-2)

Hot-patched the five changed backend files into a copy of an existing,
already-verified Windows dev-deployment release
(`%LOCALAPPDATA%\MockingBirdDev\releases\6045228`, from a real prior
accepted milestone), backing up the originals first; launched against a
disposable `MOCKINGBIRD_HOME` (`C:\Temp\mb-verify-home`), never the real
data path.

- `python.exe -m mockingbird doctor` against the fresh, zero-camera
  instance: **`Storage: PASS`** (previously the disclosed `FAIL`/
  `BLOCKING`). `Application: WARN` on this same run is expected -- the
  server was still running at the time Doctor read the marker, an inherent,
  pre-existing property of the marker mechanism when Doctor and the server
  run concurrently, not a defect this milestone introduces.
- Bootstrapped a real administrator over HTTP, called
  `POST /api/product/shutdown`: `{"accepted":true,"message":"MockingBird is
  shutting down. It's safe to close this tab now."}`. The real OS process
  (confirmed by PID) exited within seconds, with no external signal. Read
  `runtime_state.json` immediately after: **`{"state": "clean"}`**.
- Re-ran `doctor` against the same disposable home: **`Application: PASS`**.

Originals restored; the disposable data home and all temporary logs
deleted; the dev-deployment release folder confirmed to match its pre-test
state.

### 5.2 Reference Camera Node / Raspberry Pi (item 3)

Copied only `hardware_health.py` (a standalone module -- no other
`mockingbird_node` imports) to a temporary path over SSH and ran it
directly against the real reference Pi, without touching the installed
service:

```
HardwareQuality(undervoltage_active=False, throttled_active=False,
  undervoltage_occurred=False, throttled_occurred=False,
  temperature_celsius=43.8)
StorageHealth(total_bytes=125467754496, free_bytes=114373689344,
  storage_health_tier='healthy')
```

Confirmed the parser handles genuine hardware output correctly (both the
clean bill of health above, and the earlier capture of the exact
`vcgencmd` output shape used to write the parser in the first place), and
that a non-existent probe directory correctly falls back to its parent's
real stats. Temporary file removed afterward; the installed service was
never stopped, restarted, or reconfigured.

---

## 6. Validation

**Tier 1 (focused, during implementation):** RED/GREEN on each new/changed
test file individually before broader validation -- `tests/test_doctor.py`,
`tests/test_camera_node_hardware_health.py` (new),
`tests/test_camera_node_boot_identity.py`, `tests/test_product_shutdown.py`
(new), `tests/test_camera_node_packaging.py`.

**Fast gate** (`scripts/verify_fast.py`): **1801 passed, 0 failed** (182.7s).
First attempt hung (see "Regressions found and fixed," below); clean after
the fix.

**Core gate** (`scripts/verify_core.py`, `pytest -m "not slow"`): **5969
passed, 4 failed, 4 skipped, 35 deselected, 11 xfailed** (2321.6s -- this
sandbox was measurably slower than its own documented ~9-minute baseline
this session; not a product concern). The four failures:

| Test | Disposition |
|---|---|
| `test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary` | Pre-existing, long-documented real-wall-clock-date-sensitive fixture flake -- recorded as recurring across at least nine prior milestone checkpoints in `release-execution-state.md` §14. This milestone never touched this file. |
| `test_place_biodiversity_summary_repository.py::test_human_correction_updates_place_biodiversity_intelligence_correctly` | Same family, same disposition. |
| `test_place_change_summary_repository.py::test_api_round_trip_exposes_change_detection_fields` | Same underlying date-sensitivity class, independently documented recurring across multiple prior checkpoints. Not touched by this milestone. |
| `test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success` | Previously documented load-induced timing flake (Calm Attention & Notifications v1, Mobile & Remote Experience v1 checkpoints). Not touched by this milestone. |

Re-confirmed each of the two ambiguous full-suite-only signals independently
before accepting them: `test_camera_node_packaging.py`'s failure (a first
Core attempt, before the `NODE_FILES` fix) reproduced deterministically in
isolation and is a genuine defect, fixed (§4.4 note in
`build_camera_node_artifact.py`); `test_observation_camera_node_live.py`'s
single failed test in that same first attempt did **not** reproduce in
isolation (53/53 passed) and did **not** reproduce in a second, complete
Core run (53/53 passed again, alongside the four flakes above) -- confirmed
a genuine, non-reproducible, load-dependent flake, not a regression.

**Frontend:** `tsc --noEmit` clean; `vite build` clean (`page-LocalDataPage`
chunk rebuilt correctly).

**`ruff check`** clean on every changed Python file, including the two
regression-fix files and the `NODE_FILES` fix.

### Regressions found and fixed by this milestone's own validation

1. **A real test-suite hang**, caught live (the Fast gate itself hung
   mid-run; diagnosed via the stalled process's own open sockets and
   `epoll_wait` block state, not guessed). `runtime.py`'s switch from
   `uvicorn.run(...)` to an explicit `Config`+`Server` construction (§3.2)
   silently bypassed two existing tests'
   `monkeypatch.setattr(runtime_module.uvicorn, "run", ...)` mocks
   (`test_windows_launcher_instance_identity.py`,
   `test_single_app_runtime.py`) -- with the mock bypassed, a real
   `uvicorn.Server` bound a real socket and blocked forever inside the test
   process. Fixed by updating both mocks to
   `monkeypatch.setattr(runtime_module.uvicorn.Server, "run", lambda self: None)`,
   the equivalent no-op for the new shape. Confirmed fixed: both files pass
   in 5.3s with no hang; the full Fast gate then passed clean.
2. **A real packaging omission**, caught by Core (`test_camera_node_
   packaging.py::test_node_files_cover_the_real_internal_import_closure`,
   itself deliberately built to catch exactly this class of gap after two
   prior real occurrences). `NODE_FILES` (`scripts/build_camera_node_
   artifact.py`) did not list the new `hardware_health.py`, imported by
   `app.py`/`selftest.py` -- a real packaged Camera Node artifact built from
   this milestone's own code would have raised `ModuleNotFoundError` at
   `python -m mockingbird_node` startup, the identical failure mode
   documented twice before for this same manifest. Fixed by adding the
   missing entry; confirmed fixed in isolation (13/13 passed) and in the
   full Core run.

Neither regression reached this report undisclosed; both are recorded here
exactly as found, per this project's own established transparency
convention.

---

## 7. Remaining limitations, disclosed

- **Doctor's `Application` check can still read `WARN` while MockingBird is
  still running** (the marker legitimately still says "starting" until the
  currently-live process actually reaches its own shutdown code) -- an
  inherent property of running Doctor concurrently with a live instance,
  observed directly during real-hardware verification (§5.1), not a new
  defect and not addressed by this milestone (out of its own bounded scope:
  Doctor must stay read-only and side-effect-free).
- **Host-side durable surfacing of Camera Node storage/hardware facts was
  not built** (§4.4) -- visibility today is live-only, via `/node/v1/
  health` and self-test degradation, not checkpointed to `CameraSourceModel`
  the way `boot_id`/`last_seen_at` are. A future need for durable Host-side
  history of these two facts specifically remains open, evidence-gated
  follow-up.
- **The reused Host storage-tier threshold values were not re-derived for
  Pi-scale SD cards** -- a deliberate, disclosed reuse of an existing,
  already-accepted judgment call (no Node-specific field evidence exists to
  derive a second one from yet), not a claim that these exact numbers are
  independently validated for this hardware class.
- **No Playwright e2e spec was added** for the new "Shut Down MockingBird"
  UI control -- validated instead via `tsc`/`vite build`, the underlying
  endpoint's own test coverage, and direct real-hardware HTTP verification
  (§5.1). Judged proportionate to a single, isolated, already-established-
  pattern UI addition; not escalated to a new e2e surface for a bounded
  milestone.
- **This sandbox's Fast/Core gate runtimes were measurably slower than
  their own documented baselines this session** (Fast ~183s vs. ~147s
  measured; Core ~38.7min vs. ~9min measured) -- confirmed environmental
  (system load average 4.5+ observed directly, no memory pressure), not a
  product regression; a second complete Core run reproduced the same slow
  pace with an otherwise clean, consistent result.

---

## 8. Files changed

**Production code:**
- `src/mockingbird/diagnostics/doctor.py` -- `_gather_has_any_source_
  configured`, `_gather_storage`/`_interpret_storage` updated (item 1).
- `src/mockingbird/runtime.py` -- explicit `Config`+`Server`, publishes
  `app.state.uvicorn_server` (item 2).
- `src/mockingbird/api/main.py` -- `POST /api/product/shutdown` (item 2).
- `src/mockingbird/api/schemas.py` -- `ProductShutdownResponse` (item 2).
- `src/mockingbird/api/auth.py` -- Administrator-tier registration for the
  new route (item 2).
- `src/mockingbird_node/hardware_health.py` -- new (item 3).
- `src/mockingbird_node/selftest.py` -- storage/hardware-quality
  degradation (item 3).
- `src/mockingbird_node/app.py` -- new `/node/v1/health` fields (item 3).
- `scripts/build_camera_node_artifact.py` -- `NODE_FILES` fix (regression
  2, §6).
- `web/src/api/types.ts`, `web/src/api/client.ts`,
  `web/src/pages/LocalDataPage.tsx` -- shutdown UI (item 2).

**Tests:**
- `tests/test_doctor.py` -- new/updated Storage tests (item 1).
- `tests/test_camera_node_hardware_health.py` -- new (item 3).
- `tests/test_camera_node_boot_identity.py` -- new self-test/health tests
  (item 3).
- `tests/test_product_shutdown.py` -- new (item 2).
- `tests/test_windows_launcher_instance_identity.py`,
  `tests/test_single_app_runtime.py` -- mock fix (regression 1, §6).

**Documentation:**
- `docs/camera-node-installer-design.md` -- new dated section (item 3).
- `docs/release-reliability-first-run-recovery-v1-report.md` -- this
  report.
- `docs/release-execution-state.md` -- dated, additive entries recording
  this milestone (top-of-file `CURRENT PHASE`; §3), matching this file's
  own established three-place convention. No historical text edited or
  removed.
- `docs/roadmap.md` -- a dated, additive correction to Gate E's "Field-
  failure acceptance matrix," closing the two named storage/hardware-
  quality-visibility cases this milestone addresses. No historical text
  edited or removed.

**Not changed:** any product/schema/detector/identification-policy code;
`README.md`; `THIRD_PARTY_NOTICES.md`. Schema unchanged (v59).

---

## 9. Classification

**A** -- a complete, bounded milestone with no residual gap in its own
authorized scope. All three scope items are implemented, tested, and
independently verified against real hardware rather than asserted: item 1
proven on real native-Windows hardware to close the exact disclosed defect;
item 2 proven end-to-end on real native-Windows hardware, including a real
process actually exiting and the real marker file reading clean immediately
after; item 3's parsing proven directly against the real reference Camera
Node before and after being written. Two real, previously-unknown
regressions were found by this milestone's own validation discipline (not
shipped, not glossed over) and are disclosed in full alongside their fixes.
Fast gate 1801/1801 clean; Core gate's four failures are all independently
confirmed pre-existing, long-documented, environment-sensitive flakes
unrelated to any file this milestone touched. `ruff`/`tsc`/`vite build`
clean. No product, schema, detector, or identification-policy change. All
seven preserved untracked detector files remain untouched. No push.

**At closure:**

**FEATURE FREEZE -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING**

**Current authorization: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED`**, returned exactly as required, for the next external (ChatGPT)
acceptance review to act on. This milestone does not self-authorize a
subsequent milestone, reopen Gate A, or start Gate G/Final Release
Hardening.

---

*Prepared as a bounded release-readiness milestone. No product, schema, or
identification-policy code was changed. No participant was contacted or
recruited. No build was distributed. No push was made.*
