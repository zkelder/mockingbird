# Camera Node Connectivity & Recovery Diagnosis v1 -- report

Focused Gate D/E reliability diagnosis triggered by the failed 2026-08-20
daylight cache-128 acceptance (see
[cache-128-live-proof-blocked-camera-node-2026-08-20.md context, and]
`data/field-acceptance/2026-08-20-cache-128-live-proof/field-session-plan.md`,
gitignored). The evidence-cache fix itself (`51ee8ea`) was explicitly out of
scope and was not touched.

## 1. Base HEAD / branch

- Base: `080affa2410033c1d2017e2699db898c8867cf55` ("Add MockingBird Doctor /
  Operational Health v1"), verified via `git rev-parse HEAD` at session
  start; repository root confirmed native WSL (not `/mnt/c`).
- Isolated worktree: `../mockingbird-camera-node-connectivity-recovery-v1`,
  branch `feature/camera-node-connectivity-recovery-v1`, created with
  `git worktree add -b feature/camera-node-connectivity-recovery-v1
  ../mockingbird-camera-node-connectivity-recovery-v1 080affa...` (branched
  from the exact local HEAD, not `origin/main`, which was 125 commits
  behind). The main checkout's 7 pre-existing untracked superseded files
  were re-verified present and unchanged both before and after this
  session's work; no other worktree was touched.

## 2. Incident timeline (from the prior session's own field-session-plan.md;
no timestamp below is inferred beyond what that log recorded)

All times UTC; EDT = UTC-4.

| Event | UTC | Local (EDT) |
| --- | --- | --- |
| First Start | 11:47:18.94 | 07:47:18 |
| First real frame / immediate activity | ~11:47:21 | ~07:47:21 |
| Last recorder frame (session 1) | ~11:49:56 | ~07:49:56 |
| `analysis_stream_unavailable` first seen; reconnect attempts 1-6 | 11:49:56 -- 11:51:23 | 07:49:56 -- 07:51:23 |
| Session 1 terminal (`stopped_reason: camera_unavailable`) | 11:51:23.57 | 07:51:23 |
| Second Start (organic retry) | 11:52:55.59 | 07:52:55 | 
| Second session exhausted (attempt 1 failed immediately, retried to 6) | ~11:54:2x | ~07:54:2x |
| Terminal fallback state showed bare `onnx_cuda_verification_insufficient` | ~11:54:2x | ~07:54:2x |
| Third Start (after 3 min deliberate settle) | 12:02:16.37 | 08:02:16 |
| Fourth Start (after 10 min deliberate settle) | 12:17:17.21 | 08:17:17 |
| All of sessions 2-4: identical signature, 0 frames each | -- | -- |
| Explicit final Stop | after session 4's own exhaustion | -- |

Session 1 was genuinely healthy and busy for **4.08 minutes**: 30 track
generations, 20 proposal outcomes, 1 real admission
(`visit-observation-candidate-124`, independently photo-verified), 19
suppressions (`blocked_ambiguous_boundary` x11, `blocked_continuation_
pending` x8). Sessions 2-4 recorded **zero** frames each, across ~30 minutes
of wall-clock time with escalating settle windows (90s/180s/600s) that made
no observable difference to onset or outcome.

## 3. `analysis_stream_unavailable` -- exact code path

Raised only in `CameraNodeHttpTransport.iter_analysis_frames`
([camera_node_live.py](src/mockingbird/observation/camera_node_live.py)):

- a non-200 HTTP status, or a 200 with the wrong `Content-Type` (not
  `multipart/x-mixed-replace`);
- any `socket.timeout` / `TimeoutError` / `OSError` raised anywhere in the
  connect-and-stream sequence (this parent class covers
  `ConnectionRefusedError`, `ConnectionResetError`, `socket.gaierror`, and
  every other OS-level connection failure).

Both shapes are indistinguishable from the caller's side before this fix --
see Section 10, below.

Transport facts confirmed by direct source reading:

- **A brand-new `HTTPConnection`/`HTTPSConnection` is opened on every single
  call** (`UrlLibCameraNodeRequester._connection`); nothing is pooled or
  reused across retries or across Starts. Stale-connection reuse is ruled
  out as an explanation.
- **Connect timeout is a fixed 2.0s**, consistent across pairing, health,
  snapshot, and analysis-stream calls; **response timeout defaults to
  10.0s**. Both are hard module constants, not extended dynamically.
- The transport's own `finally` unconditionally does `self._connection =
  None` and closes the connection object -- teardown of the transport
  object itself is clean.
- The retry state machine (`AnalysisStreamRetryPolicy` /
  `_await_transport_retry` in
  [engine_runtime.py](src/mockingbird/observation/engine_runtime.py)) is
  bounded (6 attempts, 12.0s backoff by default), Stop-responsive
  (`Event.wait` returns immediately on an explicit Stop), and correctly
  distinguishes only `authentication_rejected`/`node_redirect_rejected` as
  immediately terminal -- `analysis_stream_unavailable` is always
  bounded-recoverable, never a reason to give up early.
- On exhaustion, `_camera_message` is correctly set to `"Camera Node
  connection stopped: analysis_stream_unavailable."` and `_stopped_reason`
  to `"camera_unavailable"` -- this is the *correct*, honest diagnosis. (Its
  later corruption is Section 4/7, below.)

**Conclusion:** nothing in this path is a host-side defect. A real TCP
connection was attempted fresh every time, with a consistent, reasonable
timeout, and consistently failed for ~30 minutes regardless of how long the
session waited between attempts. This is the behavioral signature of a real
Camera Node (Raspberry Pi)-side or network-side outage, not a client bug.

## 4. `onnx_cuda_verification_insufficient` -- exact code path (root cause
found and fixed this session)

The prior field session traced this as far as `OnnxCudaObservationProvider.
_verify_cuda_execution()` but explicitly left the *remaining* path to the
bare, unprefixed terminal string unresolved. This session traced and closed
that gap completely:

1. `_verify_cuda_execution()` is called **only** from `finalize_replay()`,
   which is called from `FrameDrivenObservationProvider.stop_live()` --
   itself called from `LiveCameraNodeShadowSession.stop()` -- **on every
   session teardown**, healthy or not. It is never on the live per-frame
   path.
2. `_verify_cuda_execution()` reads `execution_assignment()` from the real
   ONNX Runtime session wrapper (`_ProfiledOrtSession`), which classifies
   nodes from the session's own **execution profiling trace** -- a real
   record of what actually ran, not a static graph property. If
   `session.run()` was never called even once, the profile is empty and
   every provider's node count is genuinely `0`.
3. Before this fix, `cuda_executed_nodes == 0` fell through to the same
   `raise ReplayValidationError("onnx_cuda_verification_insufficient")` a
   *real* CUDA execution failure raises -- there was no way for the function
   to tell "nothing ran" apart from "something ran but not verifiably on
   CUDA."
4. In sessions 2-4, the analysis-stream connection failed on attempt 1 of 6,
   every time, before a single frame ever arrived -- so `detector.
   infer_frame()` was never called, and the detector session (loaded
   successfully, independent of the camera connection) had zero real
   inferences to its name by the time `session.stop()` ran on retry
   exhaustion.
5. Before this fix, `_run_async`'s teardown (`finally: final_results =
   session.stop()`) had **no exception handling at all**. The
   `onnx_cuda_verification_insufficient` raised inside `finalize_replay()`
   propagated: (a) straight out of the `finally` block, **skipping** the
   finalize assembly tick and `provider.close()` entirely; (b) out of
   `_run_async()`; (c) into `_run()`'s generic `except Exception as error:
   self._camera_message = _sanitized(error)` -- which **unconditionally
   overwrote** the already-correct `"Camera Node connection stopped:
   analysis_stream_unavailable."` message with the bare CUDA string.
6. `ObservationEngineSessionManager` never prunes a terminal `_EngineSession`
   from its registry until the *next* Start replaces it -- confirmed by
   direct reading of `start`/`stop`/`status`. So every `status()` call
   between session 2's exhaustion and session 3's Start returned that
   poisoned `session_status` via `unified_status.camera_node_facts`'s
   *first* branch (`session_status is not None`), not the `playback`-based
   fallback branch the prior session's own investigation had already,
   correctly, ruled out (`GET .../playback` showing `live_ready` was real
   and irrelevant -- a coincidence, not evidence about which branch fired).

**This closes the prior session's open question completely and
definitively**, independent of live hardware: reproduced deterministically
in `tests/test_observation_onnx_cuda.py::
test_finalize_replay_does_not_misreport_zero_inference_as_a_cuda_failure`
(RED against the unmodified provider, GREEN after the fix).

## 5. Do the two messages share a cause?

Partially, and precisely: **`analysis_stream_unavailable`'s own root cause
(why the Pi stopped responding) is not a CUDA problem and remains unproven
without Pi-side access** (see Section 6). But **`onnx_cuda_verification_
insufficient`'s appearance as the terminal message was a deterministic,
100%-reproducible downstream consequence of that same connectivity failure**
-- specifically, of zero frames ever reaching the detector before teardown.
It was never an independent GPU/CUDA fault; it was a misclassification bug
that made a connectivity problem look like a GPU problem. GPU health was
independently confirmed clean via `nvidia-smi` during the original incident
(no contention, sole compute process was MockingBird's own) -- consistent
with, not contradicting, this finding.

## 6. Camera Node-side evidence

**None available.** No SSH, no direct Pi log access, and no additional
Camera Node health/status API beyond what the paired Windows host already
exposes was reachable from this sandbox, exactly as the prior session
disclosed. This remains an observability gap (see Section 12/Doctor below
for the one host-side mitigation this session could add).

## 7. Host-side evidence (this session)

The shared Windows dev instance (`http://localhost:8000` from the
PowerShell/GPU-interop path used by prior sessions) was probed read-only
this session (`GET /api/product/health`) and returned **"Unable to connect
to the remote server"** -- the product process itself is not currently
running, consistent with the mid-session Windows host reboot reported
during this diagnostic session. No deploy, restart, or configuration change
was performed; this was a single bounded, read-only probe answering exactly
one question ("is anything reachable right now"). This independently
corroborates that the environment, not this session's code, is the current
blocker to any further live verification -- see Section 14.

## 8. Root cause

- **`analysis_stream_unavailable` (the real outage):** consistent in every
  observable respect with a genuine Camera Node (Raspberry Pi)-side or
  network-side outage, external to MockingBird. No product-side defect was
  found or reproduced in the connection-establishment/retry path itself.
- **`onnx_cuda_verification_insufficient` (the misleading terminal
  message):** a confirmed, reproduced MockingBird diagnostic-classification
  defect, now fixed (Section 9-10).
- **A related, independently real defect** was found while tracing the
  above: `_run_async`'s teardown had no exception safety at all, so *any*
  exception from `session.stop()` (not just this one) silently skipped
  `provider.close()` (a resource leak -- the CUDA session/profiling
  directory was never released) and the finalize assembly tick. Also fixed.

## 9. RED reproduction

`tests/test_observation_onnx_cuda.py::
test_finalize_replay_does_not_misreport_zero_inference_as_a_cuda_failure`:
constructed a real `OnnxCudaObservationProvider` (the actual product class,
only the underlying ORT session faked, matching this file's existing
`FakeRuntime`/`FakeSession` convention) whose fake session reports zero
nodes executed on every provider -- the exact shape a session with no real
inferences produces. Verified RED against the unmodified `onnx_provider.py`
via `git stash` (raised `ReplayValidationError:
onnx_cuda_verification_insufficient`, matching the real incident's terminal
string exactly), then GREEN after the fix.

## 10. Fixes

All four are additive, bounded, and preserve every existing error code/
retry-control string unchanged.

**A -- `onnx_provider.py::_verify_cuda_execution`** (the root fix): when
every provider's executed-node count is genuinely zero (no inference ever
ran), record an honest `CUDA_EXECUTION_NOT_ATTEMPTED` classification and
return normally, instead of raising the same code a real CUDA failure
raises. Any node that *did* execute is still verified exactly as strictly
as before -- proven by a companion regression test covering both the
"ran but unverifiable" and "ran partly on CPU" real-failure shapes.

**B -- `engine_runtime.py::_run_async`'s teardown** (recovery-state-machine
hardening): `session.stop()` is now wrapped so a teardown-time exception (1)
can never skip the finalize assembly tick or `provider.close()`, (2) is
recorded as auxiliary diagnostic detail (`advanced.
analysis_stream_teardown_error`), and (3) can never overwrite an
already-diagnosed `stopped_reason == "camera_unavailable"` (the
retry-exhaustion/terminal-error-code reason) -- while leaving every other
case (an ordinary clean stop, or a session with no prior camera diagnosis)
exactly as before: a genuine teardown-time failure still becomes the
primary camera-facing reason, because it is the only diagnosis available.

**C -- diagnostic classification (Section 10 of the milestone)**:
`CameraNodeClientError` gained an optional `failure_class` attribute
(default `None`, fully backward compatible). `camera_node_live.py`'s
`analysis_stream_unavailable` raise sites now classify into a bounded, safe
vocabulary (`connect_refused`, `connection_reset`, `timeout`,
`dns_unresolved`, `http_status`, `content_type_mismatch`, `os_error`) --
never raw host/port/message text -- surfaced into
`advanced.analysis_stream_failure_class`. The primary retry-controlling
`code` string is unchanged. `advanced.last_healthy_frame_at` is also now
exposed in the session status snapshot.

**D -- Doctor (Section 12)**: the accepted `camera_node` Observation Engine
lane never writes `StreamRuntimeCheckpointModel` (confirmed: `engine_
runtime.py` has zero references to that model) -- that table belongs
exclusively to the legacy `live_monitoring` lane. Doctor's Camera Node check
was therefore structurally blind to this lane's own runtime health; a
Stream could be stuck exactly like this incident and Doctor would still
report a bland PASS. That lane *does* already checkpoint
`MonitoringExposureIntervalModel.last_confirmed_fresh_at` on every healthy
batch (Today Coverage Truth v1, pre-existing, unmodified). `_gather_camera_
node` now also reads the single stalest still-open `camera_node`-sourced
interval; `_interpret_camera_node` WARNs with `"Camera Node unavailable --
last frame ~N minute(s) ago."` once staleness exceeds 300s (comfortably
longer than both the ~45s normal checkpoint cadence and the ~72s default
reconnect budget, so an ordinary recovering reconnect never trips it).
Read-only; never initiates, arms, or otherwise touches monitoring. **Honest
scope note:** this WARN fires on a currently-*open* exposure interval that
has gone stale -- a session still nominally observing but not producing
fresh frames (a chronically flapping connection is the clearest real
example: individual frames trickle in often enough that the bounded retry
budget never fully exhausts, so the session never gives up, but productive
throughput is effectively dead). It does **not** cover the gap between a
session giving up entirely (which promptly closes its own exposure
interval, per the pre-existing, unmodified `_close_observation_exposure`)
and the next Start -- during that gap there is no open interval left to
check, exactly the window the real 2026-08-20 incident spent most of its
time in between Start attempts. Extending Doctor to also look at recently-
closed intervals with an unhealthy `close_reason` would close that second
gap, but was judged a larger, separate change than this milestone's "one
very small integration" instruction, and is named here rather than done.
Known, disclosed v1 scope limit: if both lanes need attention simultaneously, only
one WARN surfaces per Doctor run (matching how every other Doctor check
already reports one status per component) -- not solved here, by design,
per the milestone's "do not turn this into Doctor v2" instruction.

## 11. Diagnostic changes

Covered in C and D above. No credentials, raw URLs, or private data are
exposed by either change.

## 12. Tests added

- `tests/test_observation_onnx_cuda.py`: `test_finalize_replay_does_not_
  misreport_zero_inference_as_a_cuda_failure` (RED/GREEN for Fix A),
  `test_finalize_replay_still_raises_for_real_verification_failures`
  (regression guard: real mixed-execution and real unverifiable-execution
  failures still raise correctly).
- `tests/test_engine_runtime.py`: `test_teardown_failure_after_retry_
  exhaustion_preserves_the_diagnosed_reason_and_still_cleans_up` (end-to-end
  proof of the real incident shape, using a detector double whose
  `finalize_replay` raises -- the exact real interaction no prior test in
  this module could catch, since the existing fixture detector's
  `finalize_replay` is a no-op), `test_teardown_failure_with_no_prior_
  camera_diagnosis_is_still_reported_honestly` (regression guard: an
  ordinary clean stop with a genuine teardown failure is unaffected),
  `test_analysis_stream_failure_class_is_surfaced_for_diagnosis` (Fix C
  threading).
- `tests/test_observation_camera_node_live.py`:
  `test_transport_error_classification_is_a_bounded_safe_vocabulary` (pure
  function, every branch), `test_real_connection_refused_is_classified_and_
  never_leaks_raw_text` (a *real* OS-level `ConnectionRefusedError` against
  the real `CameraNodeHttpTransport`, via a genuinely unbound local port --
  not a mock).
- `tests/test_doctor.py`: updated the three existing `_interpret_camera_
  node` call sites for the new `now` parameter; added
  `test_interpret_camera_node_stale_freshness_warns_with_last_frame_minutes`
  and `test_interpret_camera_node_recent_freshness_is_pass` (Fix D).

Explicitly not added: a new "no duplicate background reader after
reconnect" test. `LiveCameraNodeShadowSession.run()`'s receiver-thread
lifecycle was not touched by any fix in this session, and is already
exercised across many repeated reconnects by the pre-existing `test_
repeated_bounded_renewals_all_recover_one_encounter_one_visit` and siblings
without any thread-leak/hang symptom; adding a redundant test for an
unmodified, already-covered path was judged out of "smallest complete
capability" scope.

## 13. Validation

- Every new/modified test file run directly: 192 passed (0 failed) across
  `test_observation_onnx_cuda.py`, `test_engine_runtime.py`, `test_
  observation_camera_node_live.py`, `test_doctor.py`.
- A wider sweep of every file touching the shared surfaces this session
  modified (`CameraNodeClientError`, Doctor's `_interpret_camera_node`
  signature): 330 passed, 11 xfailed (pre-existing, unrelated), 0 failed,
  across `test_camera_node*.py`, `test_install_camera_node.py`, `test_
  doctor_cli.py`, `test_observation_md_v5_onnx.py`, `test_candidate_visit_
  repository.py`, `test_dashboard_observation_engine_truth.py`, `test_
  monitoring_exposure_history.py`, `test_stream_playback_contract.py`.
- Core gate (`python scripts/verify_core.py`, the whole backend suite minus
  `slow`): **3281 passed, 12 skipped, 10 deselected, 11 xfailed, 0 failed**
  in 455.13s (7m35s).

## 14. Real bounded acceptance

**Not performed this session.** The shared Windows dev instance is
currently unreachable (Section 7) -- independently confirming the reported
mid-session host reboot. Testing this session's specific code changes for
real would additionally require building and deploying a fresh Windows
instance with this branch's fix, a materially larger and more invasive
action than this diagnostic milestone's explicit worktree-isolated-code
scope, and one that would affect a shared resource other concurrent
sessions depend on -- not undertaken without the user's explicit direction.
This is disclosed honestly rather than skipped silently or forced.

## 15. Decision

**D -- DIAGNOSTIC DEFECT ONLY**, with one additional confirmed and fixed
recovery-state-machine robustness gap (Fix B) found in the course of
diagnosing it.

The bounded reconnect/retry recovery logic itself (`AnalysisStreamRetryPolicy`,
`_await_transport_retry`, the fresh-connection-per-attempt transport) is
correct and was not the cause of the outage. `analysis_stream_unavailable`
itself is consistent with a genuine, external Camera Node/network outage
(Decision A-shaped for that specific message) -- but the terminal
`onnx_cuda_verification_insufficient` message that made this incident
confusing and sent the prior field session down a GPU-investigation path
was a real, reproduced, now-fixed MockingBird diagnostic-classification
defect that materially obscured the true root cause, exactly matching
Decision D's definition. This is not forced: Decision A alone would have
been dishonest given the reproduced defect; Decision C does not apply (no
Camera Node/provider software was touched or found defective); Decision E
does not apply (the two messages' relationship was fully resolved from
source, independent of live hardware).

## 16. Commit(s)

Two commits on `feature/camera-node-connectivity-recovery-v1`, branched
from `080affa` -- matching the same implementation-then-report two-commit
shape used by prior field-validation milestones (e.g. `417d642`/`8b196bb`).
Not pushed.

- `a3c64b3` -- "Fix onnx_cuda_verification_insufficient misclassifying a
  Camera Node outage" (implementation + tests).
- This commit -- "Record Camera Node Connectivity & Recovery Diagnosis v1
  findings" (this report; its own SHA is necessarily unknown to itself at
  write time -- see `git log` on this branch).

## 17. Final worktree status

Clean after commit; the isolated worktree is left in place (per this
session's own dirty-worktree-preservation default) for the user to inspect,
merge, or remove. The main checkout (`mockingbird-active`) and every other
existing worktree were never touched.

## 18. Can another daylight cache-128 acceptance run safely now?

See the final answer at the end of this report and the accompanying
response to the user.
