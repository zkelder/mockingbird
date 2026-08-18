# Observation Engine session-renewal continuity contract

Status: Observation Engine Session-Renewal Continuity v1 engineering-workflow
contract, extending [reconnect-continuity-contract.md](reconnect-continuity-contract.md)
and [observation-engine-product-control-contract.md](observation-engine-product-control-contract.md).

## Problem

The 2026-08-16 real backyard field-acceptance run (~97.5 cumulative real
observing minutes, 5 real Visits, 0 false positives, 0 fragmentation, Pi/
Camera Node flawless throughout) found that Observation silently and
permanently stopped mid-session, with `stopped_reason=camera_unavailable`,
requiring a manual "Start observing" to resume. The uvicorn access log from
that same deployment corroborates the exact fingerprint this contract fixes:
a `POST .../observation/start` immediately followed by a second
`POST .../observation/start` with **no intervening** `.../observation/stop`
call -- only possible if the session had already stopped *itself*, silently,
since `stop()` is a safe no-op once already stopped and the UI's only way to
know to offer "Start" again is `state` having already left `"observing"` on
its own.

Root cause, traced end to end through the real transport contract on both
sides of the wire (not assumed): `_EngineSession._run_async`'s outer loop
(`engine_runtime.py`) called `session.run()` in a bounded batch (20 frames,
~10 seconds at the Camera Node's 2fps nominal rate -- itself already the
*normal*, healthy shape of this loop; see reconnect-continuity-contract.md's
own measured "roughly one reconnect every ten seconds"). Before this
contract, *any* interruption of a single such batch -- a raised
`CameraNodeClientError`/`ValueError`, or a batch that completed with zero
frames and no exception at all -- triggered an unconditional `break`,
finalizing every in-flight track, reverting candidate authority to shadow,
and normalizing session state to `"stopped"` for good.

The dominant real-world trigger for exactly this shape is already
server-side, accepted, and deliberately tolerated behavior:
`mockingbird_node.app.analysis_parts` (Camera Node Capture Contention fix,
2026-08-16) already treats a single `camera_busy` capture attempt as an
expected, transient condition -- it misses that one frame and continues.
But if the physical-camera exclusive lock (`PiCamera2Provider._lock`,
`CAPTURE_LOCK_TIMEOUT_SECONDS=0.5`) stays held long enough (for example, a
concurrent evidence-burst-triggered warm-profile teardown/rebuild) to starve
*every* attempt across one whole ~10-second analysis-stream batch, the
Node's own `analysis_parts` generator completes cleanly -- HTTP 200, correct
multipart content-type, just zero image parts before the closing boundary.
This exact shape is already proven, by name, in the Node's own test suite:
`tests/test_camera_node_capture_contention.py::
test_analysis_stream_ends_cleanly_when_camera_never_recovers`, whose
docstring states the assumption this contract fixes explicitly: "so the
**client's existing reconnect logic can take over**". Before this contract,
no such client-side logic existed at the outer session-loop layer -- only
the *frame-level* reconnect bridge described below, which never gets a
chance to run because the outer loop had already discarded the whole
session first.

A live-side, code-grounded correction to an earlier working assumption: the
underlying trigger is **not** `LiveCameraSessionManager`'s own
`DEFAULT_MAX_RUNTIME_SECONDS=1800` (30-minute) renewal. That constant
governs only the legacy Live-view/monitoring child session
(`_LiveCameraSession`), which `_EngineSession._pause_live_camera_session`
fully stops (not idles) before Observation ever starts pulling frames, and
per docs/observation-engine-product-control-contract.md, "an app-started
[Observation] session has no wall-clock/candidate hard cap ... runs until
the user explicitly stops it." No renewal timer exists on the Camera Node
side either (`PiCamera2Provider`'s warm session resets only on events --
profile switches, permission errors, failed recovery -- never a clock). The
real renewal boundary is activity-driven (correlated with evidence bursts
during genuine wildlife encounters), not a fixed schedule.

## Architectural rule: a fourth bounded concept, distinct from the other three

docs/reconnect-continuity-contract.md already establishes three separate
concepts (transport connection segment, observation source generation,
track generation) at the *frame* level, inside one already-open live
session. This contract adds a fourth, one layer further out: **whether this
whole live session's `session.run()` call itself is currently succeeding at
all.** A `session.run()` interruption is not automatically a stopped
Observation Engine session, exactly as a transport connection segment
reconnecting is not automatically a new track generation. Collapsing this
into "any error ends the session" is exactly what produced the field defect.

- **`session.run()` attempt**: one bounded (~10-second) analysis-stream
  batch request/response cycle. May raise a `CameraNodeClientError`/
  `ValueError`, or complete with zero frames -- neither by itself proves the
  camera is gone, the pairing is invalid, or the session must end.
- **Recoverable interruption**: a bounded run of consecutive failed
  attempts, tracked only in-memory for the lifetime of one loop
  (`consecutive_transport_failures` in `_run_async`) -- never persisted,
  never affecting `all_track_updates`/`all_evidence_candidates`/the live
  `provider`'s own tracker generation, all of which keep accumulating
  exactly as they would across any ordinary reconnect.
- **Terminal interruption**: either a small, explicit vocabulary of
  `CameraNodeClientError` codes proven to mean "this will never resolve by
  retrying" (see "Terminal classification" below), or a recoverable
  interruption whose consecutive-failure run has exceeded its own bounded
  budget (`AnalysisStreamRetryPolicy.maximum_consecutive_failures`).

This layer never touches, reimplements, or competes with the existing
frame-level reconnect bridge (`reconnect_continuity.py`,
`ProviderNeutralFrameTracker.note_reconnect_boundary`) -- it only decides
whether `session.run()` keeps being called at all. Once frames resume
flowing, that existing, already-tested machinery is exactly what decides
whether the gap was small enough to bridge a still-active track or large
enough to cleanly reset to a fresh generation -- unchanged by this
contract.

## Terminal classification

`_TERMINAL_ANALYSIS_STREAM_ERROR_CODES` (`engine_runtime.py`) is the
complete, real vocabulary `session.run()`'s own call chain
(`CameraNodeHttpTransport.iter_analysis_frames`) can raise for a reason
retrying can never fix:

| Code | Meaning |
| --- | --- |
| `authentication_rejected` | The paired credential itself was rejected (HTTP 401) -- "node identity/pairing invalid." |
| `node_redirect_rejected` | The configured address answered with a redirect -- no longer behaving like this Camera Node's own paired endpoint. |

Every other code this call chain can raise (`analysis_stream_unavailable` --
non-200/wrong content-type, or a wrapped `socket.timeout`/`OSError`;
`analysis_stream_invalid` -- a malformed multipart part), a bare
`ValueError`, or a batch that completes with zero frames and no exception,
is treated as bounded-recoverable. This is deliberately not the same
vocabulary as `_MISSING_MODEL_OR_RUNTIME_CODES`/`_UNSUPPORTED_GPU_CODES`
(those classify a *Start*-time engine-load failure, a different subsystem)
or `CAMERA_NODE_RUNTIME_FAILURE_CODES` (the legacy live-view/monitoring
path's own, differently-scoped UI-health classification) -- this vocabulary
answers exactly one question: should the live analysis-stream loop keep
retrying `session.run()`?

## Bounded retry policy

`AnalysisStreamRetryPolicy` (`engine_runtime.py`, all fields bounded and
validated in `__post_init__`, mirroring `ReconnectBridgeConfig`'s own
convention):

| Field | Default | Meaning |
| --- | --- | --- |
| `maximum_consecutive_failures` | 6 | How many consecutive recoverable `session.run()` outcomes (raised or empty) in a row this session tolerates before giving up and treating the interruption as terminal. |
| `backoff_seconds` | 12.0 (raised from 2.0 -- see below) | Bounded, interruptible pause between consecutive retry attempts. |

Worst-case bounded patience before a persistently-failing connection is
declared terminal: roughly `maximum_consecutive_failures *
(one attempt's own duration + backoff_seconds)` -- on the order of a minute
for the production defaults, comfortably longer than a realistic
burst-triggered warm-profile teardown/rebuild, while still strictly bounded
(never an unbounded busy retry loop, never a stranded session).

**`backoff_seconds` raised from 2.0 to 12.0 (Camera Node Installer v1, real
reboot experiment).** The `~70-90s`/"on the order of a minute" language
above was this policy's original documented *intent*, but it implicitly
assumed each failed attempt takes close to its own ~10-second batch
duration before failing -- true for a *degraded* connection (camera
contention, a slow warm-profile rebuild) but not for a Camera Node that is
*completely unreachable*, the real shape of a device mid-reboot: a refused/
unroutable connection fails in about a second, not ten. A real reboot of
the reference Pi 4, with a live Observation session already running against
it, measured this gap directly: at the old `backoff_seconds=2.0`, the host
exhausted its six-attempt budget and gave up (`stopped_reason=
"camera_unavailable"`) after only **~20s** of real retrying (~38s total
session time from the interruption), while the same Pi took a measured
**~55s** to become genuinely healthy again after a normal reboot -- the
host gave up about 17 seconds before a perfectly healthy Node could have
reconnected. `12.0` restores the original ~70-90s intent (predicted
worst case: `6 * (12.0 + ~1-2s connect-failure overhead) ≈ 78-84s`) without
changing `maximum_consecutive_failures` or the bounded-retry shape at all.
The corrected value was re-validated against a second real reboot of the
same device with a live session running, which reconnected successfully
without exhausting the budget. See
[camera-node-installer-design.md](camera-node-installer-design.md) "Real
hardware acceptance findings" for the complete before/after measurement.

## Retry behavior

`_EngineSession._await_transport_retry` is called once per recoverable
`session.run()` outcome, with the current consecutive-failure count and a
short reason code. It:

- Marks `camera_connected=False` and sets an honest, attempt-numbered
  `camera_message` (`"Reconnecting to the Camera Node… (attempt N of M;
  last signal: …)"`) -- the existing "Camera health/status correction"
  honesty channel, not a new state model. `_state`/`observing` are never
  touched: Observation stays logically `"observing"` throughout a bounded
  reconnect, exactly as this contract requires.
- If the budget is already exhausted, sets the same terminal facts the
  pre-fix unconditional break already set (`stopped_reason=
  "camera_unavailable"`, a descriptive `camera_message`) and returns
  `False` -- the caller `break`s exactly like before this contract.
- Otherwise waits `backoff_seconds` via
  `asyncio.to_thread(self._stop_event.wait, backoff_seconds)` -- identical
  in shape to `session.run()`'s own `available.wait` pattern, so an
  explicit Stop requested mid-backoff is noticed immediately (proven in
  `test_user_stop_during_reconnect_backoff_is_prompt`), never waiting out
  the full backoff window.

The instant any subsequent attempt succeeds (at least one frame, or no
exception with real data), `camera_connected`/`camera_message` are restored
to healthy immediately and the consecutive-failure counter resets to zero --
"once recovered: state returns to observing, freshness resumes, no stale
terminal `stopped_reason` remains." A bounded, JSON-safe
`analysis_stream_consecutive_failures` (current run length) and
`analysis_stream_reconnect_recoveries` (lifetime count of healed runs) are
exposed in the session's existing `advanced` diagnostics dict -- reusing
that already-established free-form surface, not a new one.

## Visit/track continuity through a retry

Nothing about accumulated session state is touched while
`_await_transport_retry` is retrying: `all_track_updates`,
`all_evidence_candidates`, `attempted_proposal_ids`, the burst/same-frame
byte caches, and the live `provider`'s own tracker generation are all local
to `_run_async` and simply keep existing across the wait, exactly as they
would across any ordinary ~10-second reconnect this loop already survives
constantly. `session.stop()`/`_run_assembly_tick(..., finalize=True)` are
never called for a recoverable interruption -- only once the loop actually
exits (Stop, terminal classification, or budget exhaustion). This is why "a
transport/session renewal must not become a new biological encounter merely
because the camera connection rotated" holds structurally: there is no
intermediate finalize/reset step for this layer to introduce one. Once
frames resume, the existing, unmodified frame-level reconnect bridge and
Visit Continuity / Provisional Admission Fix v1 (`known_horizon_ms`/
`blocked_continuation_pending`) machinery are exactly what decide bridge vs.
reset and single- vs. multi-Visit outcomes, unchanged by this contract.

## Scope boundary

This contract's fix is scoped entirely to `_EngineSession._run_async`'s
outer `session.run()` loop and its new `AnalysisStreamRetryPolicy`/
`_await_transport_retry` in `engine_runtime.py`. It does not modify
`reconnect_continuity.py`, `frame_tracker.py`, `camera_node_live.py`,
`visit_episode_assembler.py`, `candidate_visit_authority.py`, the legacy
`live_camera_session.py`, or any Camera Node (`mockingbird_node`) code --
none of those needed to change for this fix, and none did.

## Known adjacent gaps (not fixed by this contract)

- **No timestamps in the packaged backend log.** `runtime_state.py`'s
  `uvicorn_log_config` wires the file handler to uvicorn's own `"default"`
  formatter (`"%(levelprefix)s %(message)s"`), which carries no `asctime`.
  Combined with `engine_runtime.py` (before and after this contract) never
  calling `logging`, a real renewal-boundary event is only ever visible in
  a live status *read* at the moment someone polls it -- never durably
  logged with a timestamp. This contract's own real-hardware acceptance
  run (see the milestone report) therefore documents wall-clock timing from
  direct observation, not from the packaged log. Fixing this is a
  logging-infrastructure change, out of this contract's scope.
- **`deploy_windows_dev.py`'s `current.json` pointer can go stale relative
  to the ledger of actual successful deploys** (`write_current` ordering,
  ~line 2044) -- found while investigating the real deployment during this
  work; the running process's own `release_info.json`/`build_info.json`
  remain the reliable source of truth regardless. Out of this contract's
  scope; flagged for a dedicated packaging session.
