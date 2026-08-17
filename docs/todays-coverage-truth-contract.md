# Today Coverage Truth contract

Status: Today Coverage Truth / Observation Engine Integration v1 engineering-
workflow contract, extending
[place-activity-report-contract.md](place-activity-report-contract.md)'s
"Monitoring coverage" section and
[observation-session-renewal-continuity-contract.md](observation-session-renewal-continuity-contract.md).

## Problem

The 2026-08-16 real backyard field-acceptance run (~97.5 cumulative real
Observation Engine minutes, 5 real Visits) found that the Today / Place
Activity Report's coverage figure read `coverage.coverage_ratio: 0.0` for
the entire session, and the frontend could render "MockingBird was actively
monitoring about 0% of today so far" -- directly contradicting substantial,
real, successful monitoring that had just happened.

Traced end to end (not assumed): `ProductRepository._place_activity_
coverage_summary`/`compute_coverage_summary` (`place_activity_report.py`)
read exclusively from `MonitoringExposureIntervalModel`, a durable,
bounded, healthy-frame interval ledger. Every writer of that table --
`mark_monitoring_running`/`mark_monitoring_backoff`/`mark_monitoring_
blocked`/`mark_monitoring_stopped`/`prepare_for_supervision` -- is reachable
only from `DurableMonitoringSupervisor`'s own reconciliation lifecycle (the
*legacy* durable-monitoring-supervisor path,
`monitoring/durable_supervisor.py`). "Camera Node Legacy-Monitoring Backend
Guard v1" (commit `fa7a099`) deliberately, correctly forbids a `camera_node`
Stream from ever being armed for that legacy path -- Observation Engine is
its documented canonical replacement (see `docs/runtime-map.md`'s "Camera
Node: Observation Engine = canonical monitoring; legacy durable monitoring
= forbidden"). But `ObservationEngineSessionManager`/`_EngineSession`
(`observation/engine_runtime.py`) never wrote to `MonitoringExposureInterval
Model`, or any exposure/coverage table, at all. The two facts compose into a
structural gap, not an occasional bug: **a Place monitored exclusively
through "Start observing" can never accumulate durable coverage history, no
matter how much real, successful Observation Engine activity occurs.**

`b8c6766` ("Fix Today report coverage pill") already fixed the *frontend's*
misreading of a real `0.0` as "Fully observed" -- necessary, but it could
only make the number honest once it existed; it could not manufacture the
number. This contract is the data-source fix that number needed.

## Canonical coverage definition (unchanged)

Coverage means "time during which MockingBird was actually observing this
Place through at least one applicable Stream" -- an honest union over raw,
durably-recorded intervals, never inferred from armed policy, runtime
checkpoints, Camera Health, or the calendar. 100% Place coverage means at
least one applicable camera was observing for the full interval, not that
every configured camera/zone was. This was already true and already
correctly implemented in `compute_coverage_summary`/`_place_activity_
coverage_summary` before this contract -- see "Monitoring coverage" and
"Place-wide coverage policy" in place-activity-report-contract.md, both
unchanged by this work. The defect was entirely on the *write* side.

## One canonical ledger, no new table

`MonitoringExposureIntervalModel` (schema v27, `storage/models.py`) is
confirmed the canonical coverage ledger -- `zone_insights` and
`place_activity_report` both already read only this table, and its shape
(bounded interval, `started_at`/`last_confirmed_fresh_at`/`ended_at`/
`close_reason`/`runtime_generation_id`, a partial-unique index enforcing at
most one open interval per Stream) is already fully general -- nothing
about it is legacy-specific. Observation Engine is wired into this exact
table. No migration, no schema change, no second competing definition of
coverage.

### Provider-agnostic write core

The legacy writer coupled its checkpoint/open logic to `StreamRuntime
CheckpointModel` only to persist `runtime_generation_id` onto that
checkpoint row as a side effect -- Observation Engine sessions have no such
row (armed `StreamMonitoringPolicyModel`/`StreamRuntimeCheckpointModel` are
legacy-only, per the Backend Guard above). `ProductRepository._record_
monitoring_exposure_frame` (the legacy entry point) is now a thin wrapper:
it mints/persists a `runtime_generation_id` onto the checkpoint exactly as
before, then delegates to a new, extracted, provider-agnostic core,
`_checkpoint_monitoring_exposure_interval(stream_id, runtime_generation_id,
healthy_at, now)`, which does 100% of the actual open/checkpoint/rotate
logic, unchanged, and takes `runtime_generation_id` directly rather than a
checkpoint row. This is a pure extract-method refactor -- `_record_
monitoring_exposure_frame`'s observable behavior for the legacy path is
byte-for-byte unchanged (proven by the full pre-existing test suite passing
unmodified).

Two new public `ProductRepository` methods are Observation Engine's own
entry points, each a thin session/transaction wrapper around the shared
core and the pre-existing `_close_open_monitoring_exposure` closer:

- `record_observation_exposure_frame(stream_id, runtime_generation_id,
  healthy_at, now)` -- checkpoint a healthy batch.
- `close_observation_exposure(stream_id, close_reason, now,
  last_healthy_at=None)` -- close any open interval; a safe no-op if none
  is open.

Both reuse the identical closing rule the legacy path already relies on:
close at durable fresh-frame evidence (`last_healthy_at` if newer, else the
interval's own last checkpoint), never at an assumed outage boundary. A
single first checkpoint that closes before ever reaching a second one
becomes a zero-length interval and is deleted, not persisted -- this is
pre-existing, intentional behavior
(`test_zero_length_interval_is_not_preserved...`), inherited unchanged: a
monitoring episode shorter than one checkpoint cadence (45s,
`DURABLE_EXPOSURE_CHECKPOINT_INTERVAL`) contributes no measurable, durable
coverage either way.

## Observation Engine lifecycle integration

`_EngineSession` (`engine_runtime.py`) now:

- Mints one stable `runtime_generation_id` (a fresh `uuid4`) in
  `__init__`, mirroring the legacy checkpoint's own convention. A fresh
  `_EngineSession` object is constructed on every "Start observing"
  (`ObservationEngineSessionManager.start`), so a new generation id here
  always correctly rotates past -- and closes, as
  `runtime_generation_replaced` -- any interval a prior, abandoned session
  left open.
- Checkpoints once per successful `session.run()` batch (`_run_async`'s
  main loop, right after a batch is confirmed non-empty and any reconnect-
  recovery bookkeeping settles) -- never once per frame. This is already
  far coarser than per-frame (a batch is ~20 frames/~10 seconds); the
  durable model itself further throttles actual writes to the same 45-
  second cadence the legacy path already uses.
- Closes its own open interval unconditionally in `_run_async`'s outer
  `finally` block -- the exact same place, and the same "whenever this
  session's own loop ends, for *any* reason" idiom, `_resume_live_camera_
  session`/the authority-revert-to-shadow call already use. `close_reason`
  is derived from `self._stopped_reason` through the existing shared
  `exposure_close_reason_for_transition` (see below); `last_healthy_at` is
  the best in-memory known-good frame time (`_last_healthy_frame_at`,
  updated on every checkpoint) -- finer-grained than the durable
  checkpoint's own bounded cadence, so a clean Stop closes at the true
  observed boundary, not one artificially truncated to the last persisted
  checkpoint.

### Close-reason mapping

`exposure_close_reason_for_transition` (`monitoring/exposure_history.py`)
was already a shared, generic mapping from short runtime-transition reasons
to the small `close_reason` vocabulary the `MonitoringExposureIntervalModel`
CHECK constraint enforces. Observation Engine's own `_stopped_reason`
vocabulary needed exactly one new entry:

| `_stopped_reason` | Meaning | Mapped `close_reason` |
| --- | --- | --- |
| `"user_stopped"` | Explicit Stop | `"session_stopped"` (existing default) |
| `"repository_reconfigured"` | App re-pointed at a different DB | `"application_shutdown"` (existing key, shared with the legacy path's own identical reason string) |
| `"local_backup_restore"` | Backup restore in progress | `"application_shutdown"` (existing key) |
| `"camera_unavailable"` | Bounded reconnect budget exhausted, or an immediately-terminal node-identity rejection | `"provider_failure"` (**new key added**) |
| anything else/unset (defensive) | An unanticipated crash before `_stopped_reason` was set | `"provider_failure"` (via the `or "camera_unavailable"` fallback at the call site) |

No new `close_reason` values were added to the model/CHECK constraint --
every mapped value already existed.

## Reconnect semantics: no regression to renewal continuity

`AnalysisStreamRetryPolicy`/`_await_transport_retry`
(Observation Engine Session-Renewal Continuity v1, commit `49e3182`)
already never touches `_state`/`observing` during a bounded, recoverable
reconnect -- "Observation stays logically active the whole time." This
contract's checkpoint call only ever runs after a batch is confirmed
**non-empty** (a real frame arrived); the retry/backoff path
(`_await_transport_retry`) never calls it, and the interval-close call only
runs once `_run_async`'s main loop has actually exited (`finally`), which
never happens during a bounded reconnect. So a recoverable interruption:

- never closes the open interval (the `finally` block is not reached),
- never opens a second, fragmented interval (the same `runtime_generation_
  id` is reused for the whole session's lifetime, so `_checkpoint_
  monitoring_exposure_interval` keeps extending the one open interval once
  frames resume),
- simply leaves the interval's `last_confirmed_fresh_at` checkpoint where it
  was until the next real frame lands -- exactly the same "coverage
  tolerates a bounded gap without misrepresenting it" shape the legacy
  path's own `DURABLE_EXPOSURE_FRESHNESS_LIMIT`/checkpoint cadence already
  provides.

Proven directly in `tests/test_engine_runtime.py::test_recoverable_
reconnect_does_not_fragment_or_prematurely_close_monitoring_exposure`,
reusing the exact `_RenewingTransport` fixture Session-Renewal Continuity
v1's own tests use.

A **terminal** interruption (retry budget exhausted, or an immediately-
terminal node-identity rejection) does still close the interval, honestly,
as `provider_failure` -- "genuine terminal camera failure should stop or
gap coverage honestly" is a different case from a recoverable one, and was
never in tension with the renewal-continuity fix (which only ever concerned
itself with *recoverable* interruptions).

## Unclean process death and application shutdown

No new code was needed for either case -- both are already covered by
existing, generic, provider-agnostic mechanisms:

- **Unclean process death** (the process is killed; no code gets a chance
  to run `_EngineSession.stop()`/`_close_observation_exposure`): `Product
  Repository.prepare_for_supervision`, already called unconditionally at
  every app boot (`DurableMonitoringSupervisor.start()` -> `store.prepare_
  for_supervision(...)`, itself started in `_app_lifespan`), closes **any**
  open `MonitoringExposureIntervalModel` row as `unclean_restart` --
  querying `MonitoringExposureIntervalModel.ended_at.is_(None)` globally,
  with no filter on which writer opened it. This already ran before this
  contract and needed no change. Proven directly in
  `tests/test_monitoring_exposure_history.py::test_unclean_restart_
  cleanup_also_closes_an_abandoned_observation_exposure`.
- **A second "Start observing" after an abandoned session** (the more
  likely real-world shape -- a user restarts Observation without the app
  itself restarting): the fresh `_EngineSession`'s new `runtime_generation_
  id` differs from the abandoned interval's, so `_checkpoint_monitoring_
  exposure_interval`'s existing rotation logic closes the stale interval as
  `runtime_generation_replaced` before opening the new one -- the same
  mechanism the legacy path already relies on for the identical scenario.
  Proven directly in `tests/test_monitoring_exposure_history.py::test_
  observation_exposure_rotates_on_a_new_runtime_generation`.

**Known adjacent gap, not fixed here:** `api/main.py`'s `_app_lifespan`
graceful-shutdown `finally` block calls `_live_camera_session_manager.
stop_all(reason="api_shutdown")` but does **not** call `_observation_
engine_session_manager.stop_all(...)` (unlike `_stop_runtime_activity`,
which does call it, but is itself only invoked for `repository_
reconfigured`/`local_backup_restore`, not a real process shutdown). This
appears to be a pre-existing, unrelated lifecycle-completeness gap. It does
**not** compromise coverage truth specifically: an Observation Engine
session abandoned by a graceful-but-unstopped shutdown leaves its interval
open with a real, honest `last_confirmed_fresh_at` checkpoint, which
`_place_activity_coverage_summary`'s read query already bounds an *open*
interval's effective end at (`coalesce(ended_at, last_confirmed_fresh_at)`)
-- so the reported coverage number is still truthful even without an
explicit close, and the interval is cleanly closed as `unclean_restart` (or
rotated) the moment the app or Observation next starts, per the two
mechanisms above. Flagged for a dedicated session, mirroring how Session-
Renewal Continuity v1 flagged its own adjacent gaps, per this milestone's
explicit "if already represented" scope boundary (see docs/observation-
session-renewal-continuity-contract.md's "Known adjacent gaps").

## Historical backfill

None was performed, deliberately. Pre-fix Observation Engine sessions left
no per-frame timestamp trail durable enough to reconstruct real intervals
from (only the Visits/Events they produced, which are sparse, not a
continuous exposure record) -- fabricating one would violate the same
"never inferred... from... the calendar" discipline this whole feature
exists to enforce. Historical days before this fix remain honestly
incomplete (`coverage_ratio` withheld or artificially low for camera_node-
only Places, exactly as before). New Observation Engine sessions from this
commit forward are correct.

## Tests

- `tests/test_monitoring_exposure_history.py` -- ledger-level: opens/
  checkpoints with zero legacy state involved, close-reason/boundary
  correctness, safe no-op when nothing is open, generation rotation, and
  unclean-restart cleanup closing an abandoned Observation Engine interval.
- `tests/test_engine_runtime.py` -- session-lifecycle-level: a healthy
  multi-batch run records a correctly-attributed interval with no legacy
  state; a clean Stop closes as `session_stopped`; a bounded recoverable
  reconnect (the Session-Renewal Continuity v1 fixture) neither fragments
  nor prematurely closes coverage; retry-budget exhaustion closes as
  `provider_failure`; an immediately-terminal failure before any real frame
  records nothing; an idle, never-started Stream records nothing. A new
  `_EngineSession`/`ObservationEngineSessionManager` `clock` parameter
  (test-only override, mirroring `DurableMonitoringSupervisor`'s own
  `clock`, defaulting to the real wall clock) makes these deterministic and
  fast without a real multi-minute wait.
- `tests/test_place_activity_report_repository.py` -- full report-level
  acceptance, driving the real writers (not raw row seeding): ~60 minutes
  observed reports ~60 minutes of coverage against a genuinely partial
  elapsed window; Stop halts further accrual; two Streams with partial
  time overlap union correctly (not summed); an idle configured Stream
  contributes zero; a Stream with real history from an earlier day but no
  overlap with the queried window reports a true `0.0` (not `None`,
  and the exact numeric shape of the original field defect, now via an
  honest cause); coverage is present with zero legacy supervisor state at
  any point.
- The complete pre-existing test suites for the legacy path (`test_
  monitoring_exposure_history.py`'s original tests, `test_engine_runtime
  .py`'s original tests, `test_durable_monitoring_supervisor.py`, `test_
  place_activity_report_repository.py`'s original tests, `test_zone_
  insights.py`, `test_stream_monitoring_contract.py`, `test_camera_health
  .py`, `test_persistence.py`, `test_local_backup_recovery.py`) all pass
  unmodified, confirming the extract-method refactor and shared-mapping
  addition are fully behavior-preserving for the legacy path.

## Scope boundary

This contract's fix is scoped to `engine_runtime.py` (`_EngineSession`/
`ObservationEngineSessionManager`), `product_repository.py`'s exposure
writers, and `monitoring/exposure_history.py`'s shared reason mapping. It
does not modify `compute_coverage_summary`/`_place_activity_coverage_
summary`/the Place-wide union policy (already correct), `durable_
supervisor.py` (the legacy path is unchanged and still the sole writer for
non-camera_node Streams), any frontend code (`TodayReportPanel.tsx`'s
materiality judgment already correctly consumes `coverage_ratio`, per
commit `b8c6766`), or the Dashboard.
