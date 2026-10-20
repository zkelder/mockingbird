# 24/7 Field Reliability Corrections v1 -- closure report

Status: bounded reopening of the frozen Candidate Field Endurance & Accuracy
v1 candidate, authorized directly against three concrete operational
defects exposed by a real multi-day endurance run. Not a broad reliability
audit, not feature development, does not reopen accepted perception/model
work.

Starting HEAD `cbebf39` (schema v59, release version 0.1.0, the accepted
Frozen Candidate baseline). Preserves all seven protected untracked
detector files unmodified throughout (hash/identity re-verified at
closure).

## 1. Visit-cap original intent and root cause

`AuthorityLimits.max_candidates_per_session` (default 50) was designed for
Stage 7's original **bounded controlled trial**
(`candidate-authority-trial` CLI, hard-capped at 600 real seconds and, in
its own mandated configuration, 3 candidates) and generalized afterward
into "generous defaults ... for general operation" (see
docs/candidate-visit-authority-contract.md, "Limits"). "Session" was
always defined as "since this Stream's own `activation_boundary_at`" --
the moment authority last transitioned `shadow -> candidate_visit` -- and
that boundary only ever advances on a genuinely new Start (`fresh_session
=True`, exactly once per real "Start observing" action). No accepted
roadmap milestone ever intended this to be a lifetime-of-uptime ceiling:
every real reference to it (the contract doc, the Visit Authority Budget +
Ambiguous-Boundary Recall Closure v1 report) discusses a bounded trial or
a session eventually ending, never an unattended process that legitimately
keeps a single activation alive for days or weeks.

The sibling `max_candidates_per_hour` (default 20) was already a genuine
**rolling** window (`created_at >= observed_at - timedelta(hours=1)`) --
it naturally self-recovers as old candidates age out, and already served
the "bound a runaway/noisy scene" role on an ongoing basis. The session
cap, by contrast, was a **monotonic, non-decaying** count with no reset
mechanism short of Stop/Start -- appropriate for a short bounded trial,
fatal for continuous unattended production operation once a single Start
can legitimately run indefinitely. Real field evidence: a production
session hit the 50-candidate default after ~7.5 hours, then permanently
suppressed every further legitimate Visit as `blocked_session_limit` for
the remaining ~34 hours of an otherwise-healthy session -- exactly this
structural gap, not a wrong threshold value.

## 2. New continuous-operation budget/guard contract

`ProductRepository._authority_state` now bounds the session count to a
trailing rolling window (`_SESSION_BUDGET_WINDOW = timedelta(hours=24)`,
`product_repository.py`) rather than an unbounded count since activation --
the identical rolling-window pattern the hourly limit already used, just
at a longer horizon, so the *volume* budget also decays instead of
accumulating for the entire lifetime of one activation.
`activation_boundary_at` remains an unconditional floor on the window's
start (`max(activation_boundary_at, observed_at - _SESSION_BUDGET_WINDOW)`):
a fresh Start can never inherit a stale prior activation's own count, and
"no backlog replay into authority" is completely unaffected.

The window length is a hardcoded module constant, not a new per-Stream
configurable column -- mirroring how the hourly window's own one-hour
lookback has never been independently configurable either (only its
*count*, `max_candidates_per_hour`, is). `max_candidates_per_session`
itself is unchanged (still 50 by default, still caller-configurable per
Stream) -- this milestone corrected the budget's *time semantics*, not its
numeric tuning, which is explicitly out of scope here.

**Observability and honesty, not just mechanics:**
- `GET`-style authority-status reads (`ProductRepository.
  get_observation_authority_state`) report `candidates_created_in_session`
  as a live, genuinely-decreasing-over-time count -- an operator watching
  it will see it recover on its own, the same way `candidates_created_in_
  trailing_hour` already does.
- `_EngineSession.candidate_authority_exhausted` (the truthful,
  plain-language "hit the limit" fact surfaced on `GET .../observation/
  status` and the Observation panel) is **no longer permanently sticky for
  the rest of the session**. It still latches `True` the first time a
  running session observes `blocked_session_limit` (so hitting the guard
  never silently looks like normal successful observation), but now
  clears back to `False` the next time this session actually creates a
  candidate -- concrete, `evaluate_candidate_authority`-verified proof the
  budget currently has headroom, not a guess or a timer of its own. The
  user-facing message no longer says "Stop and start observation again"
  (actively wrong advice for a self-recovering rolling window); it now
  says creation will resume automatically as the window rolls forward.
- The runaway/noisy-scene guard itself is **not weakened**: a genuinely
  sustained high-rate scene still hits `blocked_session_limit` and stays
  blocked until the rolling window frees capacity, exactly the "guard must
  remain effective" half of this fix.

Also fixed in passing: `ProductRepository.get_observation_authority_state`
had no way to inject a caller-supplied `now` at all (it read the real wall
clock unconditionally) -- harmless when the session count was unbounded,
but it would have made this fix's own regression tests non-deterministic
(a fixed historical `NOW` fixture, read back against literal real time,
would silently roll out of any finite window depending on what day the
suite happens to run). Added an optional `now: datetime | None = None`
parameter, mirroring `set_observation_authority_mode`'s own existing
convention -- zero behavior change for every production caller, which
never passes it.

## 3. Proof legitimate Visits continue past the old 50-Visit boundary

Real, unmocked local check (`ProductRepository` against a real throwaway
SQLite file, zero mocking, real production defaults -- 50/session,
20/hour, nothing overridden):

1. 50 legitimate, well-separated candidates created successfully (spaced
   4 minutes apart to clear the unrelated hourly limiter) -- all 50
   `created`.
2. A 51st, still within the same activation (no Stop/Start), correctly
   `blocked_session_limit`. `activation_boundary_at` confirmed unchanged.
3. Time advanced (via the same `observed_at`/`now` parameters the real
   product code already treats as authoritative -- never a real 24-hour
   sleep) to just past the rolling window relative to the last-created
   candidate. `candidates_created_in_session` at that moment: **0**.
4. A new legitimate candidate at that later moment: **`created`** -- Visit
   creation continued past the old 50-Visit boundary with zero Stop/Start
   and zero code/config change mid-run.
5. 51 more rapid attempts in the new window: 49 `created` (reaching the
   50-total cap again from the 1 already in-window), the remaining 2
   correctly `blocked_session_limit` -- the guard is still effective.

Full transcript in this repository's session record; reproducible via
`tests/test_candidate_visit_repository.py::
test_session_budget_recovers_across_the_rolling_window_without_a_restart`
(same proof, pytest-orchestrated) and
`tests/test_engine_runtime.py::
test_candidate_authority_exhausted_flag_is_truthful_and_recovers` (the
`_EngineSession`-level truthful-flag proof).

## 4. Camera outage/recovery root cause

The reference Camera Node suffered a real network-level outage.
`engine_runtime._EngineSession`'s own bounded `AnalysisStreamRetryPolicy`
(Observation Engine Session-Renewal Continuity v1) worked exactly as
designed: it retried the interruption, then correctly gave up once its
bounded budget was exhausted and ended the session with `stopped_reason=
"camera_unavailable"`. The Host process stayed healthy throughout.

Root cause of "observation did not automatically resume": **nothing was
missing inside session lifecycle handling -- a supervision layer above it
simply did not exist.** `ObservationEngineSessionManager.start()` already
works correctly if called again (it is exactly what a user's manual
"Start observing" click does, and it is safely idempotent against an
already-active session). But once a session ends with `camera_unavailable`,
the whole `_EngineSession` object is gone and nothing in the product ever
calls `.start()` again on its own. This is a different, narrower gap than
either of the two existing mechanisms that look superficially similar:
- `AnalysisStreamRetryPolicy` bounds retries *while a session still holds
  camera ownership*, and deliberately gives up -- it has no business
  retrying forever from inside an active session.
- `monitoring.durable_supervisor.DurableMonitoringSupervisor` already
  implements exactly this "reconcile desired state, bounded backoff,
  resume automatically" pattern -- but only for the legacy `live_monitoring`
  lane (RTSP/local USB/Windows DirectShow Streams via `StreamMonitoringPolicy`),
  a structurally different runtime from the Camera Node engine lane (see
  docs/runtime-map.md). It was never wired to `ObservationEngineSession
  Manager` at all.

## 5. New auto-recovery behavior

New module `src/mockingbird/observation/camera_node_recovery.py`:
`CameraNodeRecoverySupervisor`, mirroring `DurableMonitoringSupervisor`'s
proven bounded-backoff/reconcile-loop shape (a `reconcile_once` pass that
is unit-testable independent of its background thread, `wake()`/
`shutdown()`) without touching that class, its store protocol, or the
legacy lane at all -- a small, focused addition, not a new framework.

- Every reconcile pass re-derives eligible Streams fresh from the
  repository: a configured Camera Node Stream whose most recent
  Observation Engine session is currently `state == "stopped"` with
  `stopped_reason == "camera_unavailable"`.
- Eligibility is an **allow-list** of that one recoverable reason, never a
  deny-list -- `user_stopped`, `app_shutdown`, and any other/future
  `stopped_reason` are safely excluded by construction, never auto-resumed.
- Health is probed via the Node's own existing unauthenticated
  `GET /node/v1/health` (`source_providers.camera_node.CameraNodeClient
  .health`, already used elsewhere for compatibility preflight/RTT
  calibration) -- no new Node-side capability.
- Once healthy, it calls `ObservationEngineSessionManager.start()` again
  with a **freshly re-read** `StreamLivePlaybackConfig` and privacy/ignore
  regions -- a Source reconfigured while the Node was down is picked up
  automatically, never a stale rebuild.
- A final, cheap, in-memory status re-check happens immediately before
  the `.start()` call, narrowing the window in which a user's own
  just-issued Stop could otherwise be raced by a recovery attempt.
- Backoff is bounded and capped-and-repeating (30s/60s/120s/300s/600s by
  default), never a busy loop -- but it never permanently gives up either:
  unlike the in-session retry policy, this supervisor holds no camera
  resource while waiting, and a real outage's duration is unknown in
  advance (the reference outage in this milestone's own field evidence
  never resolved for the rest of a multi-day run).
- Duplication is prevented by the pre-existing, unmodified
  `ObservationEngineSessionManager.start()`'s own lock-protected
  idempotency (an already-active session short-circuits a second
  concurrent `.start()`), not by new locking of my own.
- Wired into the app exactly like the durable monitoring supervisor and
  acoustic runtime service: started in `_app_lifespan`, shut down early in
  `_stop_runtime_activity` (before `ObservationEngineSessionManager.
  stop_all`, so it can never keep ticking against a manager/repository
  that is concurrently being torn down -- for example during a local
  backup restore).

## 6. Doctor media-integrity fix and arbitrary-CWD proof

Root cause (as diagnosed and handed off): `_gather_media_integrity` called
`Path(local_path).stat()` directly. `MediaAssetModel.local_path` is stored
**absolute** for most write paths (`ProductRepository._copy_media_file`)
but **relative to the runtime's own media root** for others (manual/folder
import -- the exact ambiguity `ProductRepository._storage_managed_media_
path` already resolves correctly elsewhere in the product). A bare
`Path(local_path).stat()` on a relative path silently depends on the
process's current working directory, contradicting `DoctorEnvironment`'s
own documented "must work from any starting directory" contract.

Fix: `_gather_media_integrity(engine, *, media_root: Path)` now resolves
each sampled path via a new `_resolve_media_asset_path` helper -- absolute
paths pass through unchanged (preserving existing behavior exactly);
relative paths are joined against `DoctorEnvironment.media_root` (the same
root `_gather_storage` already receives this way). Genuine
missing/truncated media is still WARN/FAIL exactly as before -- nothing
about corruption detection was touched or suppressed.

**Real CLI proof (RED -> GREEN), not just a unit test:** seeded a real,
throwaway `MOCKINGBIRD_HOME` with one genuinely intact media asset stored
via a relative `local_path`, then ran the actual `python -m mockingbird
doctor --json` from a working directory with no relationship to that home
at all.

- Pre-fix (`git stash` of only `doctor.py`, single tracked file, the seven
  protected untracked files untouched throughout): **WARN**, "1 of the
  last 1 retained media file(s) look incomplete or missing" -- the exact
  reported defect, reproduced live.
- Post-fix (stash popped, fix restored): **PASS**, "The last 1 retained
  media file(s) checked out (present, correctly sized)."

Automated regression coverage added to `tests/test_doctor.py`:
intact-relative-path resolution, a genuinely-missing relative path (still
correctly flagged), and an explicit same-result-regardless-of-cwd
assertion (`monkeypatch.chdir` to two different unrelated directories,
identical gathered result both times).

## 7. Validation

- **Tier 1 / focused, during implementation:** every new/modified test run
  in isolation while writing each fix (see file-by-file results below).
- **Tier 2, affected subsystems:**
  - `tests/test_candidate_visit_repository.py`,
    `tests/test_candidate_visit_authority.py`,
    `tests/test_candidate_visit_authority_acceptance.py`: 119 passed (one
    pre-existing test depended on the real wall clock relative to a fixed
    historical `NOW` fixture in a way the old unbounded session count
    happened to hide -- fixed by threading the fixture's own `now` through
    the one status read that needed it; not a product defect).
  - `tests/test_engine_runtime.py` (full file): 121 passed.
  - `tests/test_camera_node_recovery.py` (new): 18 passed.
  - `tests/test_camera_health.py`,
    `tests/test_unified_observation_status.py`,
    `tests/test_durable_monitoring_supervisor.py`,
    `tests/test_camera_node_boot_identity.py`,
    `tests/test_camera_node_pairing_persistence.py`,
    `tests/test_camera_node_repair_pairing.py`,
    `tests/test_dashboard_observation_engine_truth.py`: 128 passed.
  - `tests/test_doctor.py` (full file): 120 passed.
  - Frontend: `tsc --noEmit` clean; `vite build` clean.
- **Tier 3, full Core gate** (`scripts/verify_core.py`, `pytest -m "not
  slow"`): **6 failed, 6041 passed, 4 skipped, 35 deselected, 11 xfailed**
  (52m21s). All 6 failures independently re-confirmed via direct `git
  stash` bisection this same session (only the four modified tracked
  source files stashed -- `api/main.py`, `diagnostics/doctor.py`,
  `observation/engine_runtime.py`, `repository/product_repository.py`;
  the seven protected untracked files were never touched at any point):
  - **4 of 6 match this repository's own documented, currently-accepted
    baseline exactly** (docs/release-execution-state.md §14, "Latest
    accepted Core checkpoint"): `test_place_biodiversity_summary_
    repository.py::test_api_route_returns_the_summary` and `::test_human_
    correction_updates_place_biodiversity_intelligence_correctly` (the
    documented "own pair"), `test_place_change_summary_repository.py::
    test_api_round_trip_exposes_change_detection_fields` (documented
    date-sensitive fixture flake). (The fourth documented baseline flake,
    `test_transport_worker.py`'s load-induced timing test, did not fire
    this run -- consistent with its own already-documented
    non-reproducible-in-isolation nature.)
  - **2 of 6 are newly-observed, but independently confirmed 100%
    pre-existing and unrelated** (reproduce identically against the
    stashed, unmodified baseline; this milestone's diff touches neither
    file at all):
    - `test_doctor_camera_node_transport.py::test_interpret_no_transport_
      configured_anywhere_is_pass` and `::test_interpret_ignores_sources_
      without_transport_configured` -- a real, separate, pre-existing copy
      -text/test mismatch: commit `4ec0702` ("Product Polish & UX
      Refinement v1: navigation consistency, density fixes, copy cleanup")
      reworded `_interpret_camera_node_transport`'s detail text from "...is
      available but not in use." to "...is available, but not currently
      in use." without updating these two tests' `assert "not in use" in
      result.detail` -- "not currently in use" does not contain "not in
      use" as a contiguous substring. Confirmed via `git log -p` on
      `doctor.py`; zero relation to `_gather_media_integrity`/this
      milestone's own Doctor fix. **Not fixed here** (out of this
      milestone's explicit narrow scope -- "do not expand beyond [the
      three authorized issues] without a concrete dependency"); flagged
      for a future session.
    - `test_environmental_context.py::test_temperature_band_established_
      once_enough_days_are_cached` -- the same *class* of pre-existing
      defect this milestone's own item 2 fix independently ran into and
      had to work around in its own test suite (see "Also fixed in
      passing," above): a fixed historical `now` (`2026-06-21`) seeds a
      temperature baseline, then reads `get_place_environmental_context_
      today()` with no `now` override, which resolves against the real
      wall clock -- today, real-world time has moved far enough past that
      fixed date that "today" no longer falls inside the seeded baseline
      window, so no baseline is established (`temperature_band=None`
      instead of `"typical"`). Confirmed pre-existing via the same stash
      bisection; zero relation to `mockingbird.environment`/weather code,
      which this milestone never touched. **Not fixed here**, same
      reasoning as above.
  - No schema change (v59, unchanged); `ruff check` clean on every file
    this milestone actually touched (verified individually, not a
    full-repo sweep -- the existing, separately-tracked full-repo backlog
    is unrelated to this diff).

## 8. Real hardware evidence

- **Visit-cap (item 3):** real, unmocked `ProductRepository` against a
  real SQLite file at real production default limits -- see above. Not
  simulated/mocked at any layer other than time itself (accelerated via
  the same caller-supplied `observed_at`/`now` the real product already
  treats as authoritative).
- **Doctor (item 6):** real `python -m mockingbird doctor` CLI invocation,
  real throwaway `MOCKINGBIRD_HOME`, real unrelated working directory --
  see above.
- **Camera Node recovery (item 5):** the reference Camera Node
  (`<node-ip>:8787`, prior sessions' documented reachable address) was
  checked for reachability this session (both an unauthenticated HTTP
  health probe and the documented `ssh mockingbird-pi` alias) and found
  **genuinely unreachable** ("No route to host" on both, a real
  network-level condition in this sandbox session, not an application
  failure). Per this milestone's own explicit instruction, this is
  reported honestly as **UNVERIFIED**, not fabricated as a pass. Code-level
  validation for this fix rests on the comprehensive simulation/unit
  coverage in `tests/test_camera_node_recovery.py` (18 tests: reachable ->
  unavailable context, unavailable -> reachable, observation resumes,
  bounded backoff, repeated flap without duplication, every non-recoverable
  stop reason excluded, a narrow user-Stop race, shutdown respected, plus
  two tests against a genuinely real `ProductRepository` proving the
  repository-facing half of the wiring).

## 9. Current HEAD/schema/version

- Schema: **v59, unchanged** -- no migration was needed for any of the
  three fixes (the session-budget fix is a query-scope change, not a
  schema change; the recovery supervisor and Doctor fix touch no
  persisted schema at all).
- Release version: **0.1.0, unchanged**.
- HEAD: **`2468b91`** -- committed by a dedicated closure session,
  explicitly authorized to commit (distinct from this report's own
  original authorization, which covered the implementation work only).
  That session re-verified the diff's scope, schema (v59), version
  (0.1.0), and that all seven protected untracked detector files were
  unaffected before committing. Not pushed. See §12 for what changed
  after this report's original writing.

## 10. Remaining 24/7 blockers

- **Camera Node real-hardware disconnect/reconnect proof remains
  UNVERIFIED** -- the reference Pi was unreachable from this sandbox this
  session. This is the one item this milestone could not close with real
  hardware evidence; simulation/unit coverage is thorough, but a genuine
  live proof is still owed before treating Lane G / Camera Node recovery
  as hardware-validated for this specific fix.
- Everything else this milestone was authorized to touch is closed:
  Visit-cap contract fixed and proven at production defaults; Doctor
  media-integrity fixed and proven via the real CLI from an arbitrary
  working directory.
- Explicitly **not** addressed (out of scope by this milestone's own
  charge, not overlooked): identification/species-classification policy
  (BioCLIP-2, eligibility thresholds, abstention) is unchanged -- see the
  Appendix below, preserved for the next accuracy campaign, not acted on
  here.

## 11. Verdict (as originally written by the implementation session; superseded -- see §12)

**FURTHER 24/7 CORRECTNESS WORK REQUIRED** -- narrowly, for exactly one
reason: the Camera Node auto-recovery fix has strong simulation/unit
coverage but no real-hardware disconnect/reconnect proof yet (the
reference Pi was unreachable this session). The Visit-cap and Doctor fixes
are both closed with real, unmocked local evidence. Recommend: a short
follow-up session (or this same milestone resumed) that confirms Pi
reachability and performs the one bounded real disconnect/reconnect test
this milestone's own instructions call for, before authorizing the next
72-hour-to-7-day endurance run. If the owner/ChatGPT judges the
simulation/unit coverage sufficient on its own to proceed without that
proof, that is their call to make, not a self-authorization by this
session.

## 12. Closure addendum (2026-09-16, dedicated closure session, HEAD `2468b91`)

A separate, explicitly-authorized closure session committed this
milestone's implementation exactly as this report originally described it
(no code changes) and, per its own explicit instructions, made one fresh,
independent, bounded reachability check against the reference Camera Node
before treating §11's verdict as final -- rather than reusing this report's
existing finding untested. Result: **still genuinely unreachable**, and by
a wider margin than the original check -- `ping` (`Destination Host
Unreachable`), the HTTP health probe (`curl: (7) Couldn't connect to
server`), and `ssh mockingbird-pi` (`No route to host`) all failed
identically. This is a second, independent same-day confirmation of a
real network-level condition external to this repository, not a retry of
the same stale finding.

No real disconnect/reconnect test (closure step 2, sub-steps A-G) could be
performed as a result -- there is no reachable Node to interrupt. No code
was changed as a result, per that session's own explicit instruction: an
unreachable reference Pi is an evidence-gathering limitation, not a
reproduced software defect, and does not retroactively call the
implementation itself into question. Simulation/unit coverage
(`tests/test_camera_node_recovery.py`, 18 tests, unchanged) remains the
only evidence for the recovery supervisor's own control-flow correctness;
real-hardware disconnect/reconnect proof is still owed before the *next*
72-hour-to-7-day endurance run, not before this closure.

**Final verdict, superseding §11: READY FOR REPEAT ENDURANCE RUN --
CAMERA RECOVERY HARDWARE PROOF PENDING.** The implementation (all three
fixes) is accepted; Visit-cap and Doctor are fully real-hardware/real-CLI
proven; Camera Node auto-resume is accepted at the simulation/test level
with real-hardware proof of the disconnect/reconnect path still
outstanding, tracked as a named risk for the next endurance run rather
than as a blocking defect in this one.

---

## Appendix: field evidence preserved for the next accuracy campaign (item 4, not acted on)

The 13-Visit endurance sample found one confidently wrong species call,
one likely wrong call, one call on weak evidence, and several reasonable
abstentions. This sample size is real field evidence but is explicitly
not sufficient to change BioCLIP-2, eligibility thresholds, abstention
policy, or model selection -- consistent with the standing, frozen
decision from Species Classification Re-evaluation & Promotion v2
(2026-08-24: BioCLIP 2.5 rejected, "Frozen: no re-promotion"). Recorded
here, not acted on, per this milestone's own explicit instruction not to
reopen identification policy.
