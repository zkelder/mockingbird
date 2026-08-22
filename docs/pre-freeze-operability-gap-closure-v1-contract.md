# Pre-Freeze Operability Gap Closure v1

**Roadmap phase:** Gate D/E (First-Hour Setup & Camera Node Golden Path /
Reliability-Recovery-Observability); closes the two concrete operability
gaps the accepted First-Hour Onboarding + Whole-Product Observability
Closure v1 milestone explicitly disclosed rather than silently left open --
see "Not yet covered" in
[observability-error-taxonomy-contract.md](observability-error-taxonomy-contract.md)
and the Manual RTSP configuration gap named in that same milestone's report.
This is a bounded closure milestone, not a second broad audit of either
area.

**Product flow improved:** (A) a frame-decode failure, a coverage-accounting
write failure, or a Camera Node health recovery no longer leaves zero
durable evidence behind -- each now produces one bounded, structured record.
(B) Manual RTSP camera setup can no longer report "ready" on URL syntax
alone; a real bounded live probe (connect, negotiate, decode one frame)
gates both Validate and Complete Setup.

## Scope boundary

Additive only, exactly like the milestone this one closes gaps for. Neither
part touches detector/tracker/authority/health-state-machine/admission
logic. Part A adds one structured-log call per already-identified gap, at
an existing decision point, using the existing `error_taxonomy`/
`structured_log` modules unmodified. Part B reuses the existing ffmpeg
RTSP-to-MJPEG bridge (`playback/rtsp_bridge.py`) with two small, additive
generalizations (an optional `on_chunk` hook, an optional `capture_stderr`
flag) -- never a second decoder, never a standing background monitoring
service.

## Part A -- structured operational evidence

### A1: frame-decode failures

Two canonical decode-failure decision points, one per acquisition surface
named in the prior milestone's own gap list:

- **RTSP/live playback/acquisition** -- `playback/live_camera_session.py`'s
  `_LiveCameraSession._reader_loop`. The sibling `except Exception` branch
  already logged (prior milestone); the "process ended on its own" branch
  -- reached when ffmpeg simply exits, no Python exception at all -- did
  not. Now emits `log_error_event("acquisition_provider",
  "live_stream_process_ended", code=<CAMERA_NODE_RUNTIME_FAILURE_CODES
  member, or "camera_process_ended">, stream_id=..., source_id=...)`.
  Structurally bounded to at most one event per session attempt --
  `_reader_loop` is the `target=` of a background thread this session
  starts exactly once -- so no suppression mechanism was needed.
- **Recorded/offline media** -- `observation/offline_ingest.py`'s
  `run_offline_video_ingest`, `except RecordedVideoDecodeError` branch.
  Reuses the already-registered `OFFLINE_INGEST` taxonomy codes
  (`media_file_invalid`/`unsupported_codec`/`decode_failed`/
  `ffmpeg_unavailable`) verbatim -- no new codes needed. One decode attempt
  per analysis run (idempotent, not a retry loop), so this can fire at most
  once per run too.

Neither site logs per-frame; both log one bounded event per genuinely
failed acquisition/decode attempt.

### A2: coverage-accounting failures

`observation/engine_runtime.py`'s `_EngineSession._checkpoint_observation_
exposure`/`_close_observation_exposure` already wrapped their
`ProductRepository.record_observation_exposure_frame`/
`close_observation_exposure` calls in a bare `except Exception: return`/
`pass` -- confirmed by this milestone's own investigation to produce zero
durable evidence of any kind before this change (the exact gap the prior
milestone's report disclosed). Both except blocks now additionally call
`log_error_event("observation_engine", "coverage_checkpoint_failed"` /
`"coverage_exposure_close_failed", code="storage_write_failed",
exception=error, stream_id=..., ...)` before their existing swallow/return
-- the swallow-and-continue control flow is byte-for-byte unchanged.

Observability cannot corrupt or fabricate coverage here by construction:
both repository methods write inside one `session.begin()` transaction,
which SQLAlchemy already rolls back cleanly on any exception -- a failed
checkpoint attempt leaves zero rows, never a partial or fabricated
`MonitoringExposureIntervalModel` row. `tests/test_engine_runtime.py::
test_coverage_checkpoint_failure_is_logged_without_corrupting_exposure_
history` forces every checkpoint in a real session to fail and asserts both
things: the structured record fires, and `MonitoringExposureIntervalModel`
stays empty for that Stream.

The legacy durable-monitoring-supervisor path
(`ProductRepository.mark_monitoring_running` ->
`_record_monitoring_exposure_frame`) was deliberately left untouched: it
has no equivalent silent-swallow bug (an exception there already propagates
normally to its own, pre-existing supervisor-level handling), so it was not
"the canonical... path" this gap was ever about.

### A3: Camera Node incident resolution

`repository/product_repository.py`'s `_resolve_camera_health_state` (both
call sites inside `_sync_camera_health_incident`: policy no longer armed,
and the incident-worthy condition genuinely clearing while armed) now emits
one `log_event("camera_node", "health_incident_resolved", stream_id=...,
incident_id=..., category=..., reason_code=..., resolved_health_state=...,
duration_seconds=...)` per incident actually transitioning to resolved --
before this change, only *opening* an incident was logged (see the prior
milestone's own disclosed gap).

`resolved_health_state` is never a blanket `"healthy"` literal reused for
every resolution: the armed/condition-cleared path reports the real,
freshly-computed `CameraHealthState` value (`healthy`, or another
non-incident-worthy state such as a brief `recovering`); the
policy-disarmed path honestly reports `"monitoring_disarmed"` (or
`"monitoring_unavailable"` for the defensive missing-stream/policy case)
rather than falsely implying the camera itself became healthy again.
`duration_seconds` is the real, non-negative elapsed time between the
incident's own `started_at` and this resolution.

Fires at most once per incident (its `resolved_at` is set unconditionally
in the same pass, so a later routine poll finds nothing left to resolve) --
never "healthy" logged on every poll.

### A4: host startup/shutdown

Deliberately not touched -- explicitly optional in this milestone's brief,
and the existing crash-marker mechanism already covers the dominant real
case. No new lifecycle complexity added for a nice-to-have.

## Part B -- Manual RTSP live setup validation

### Probe (`playback/rtsp_bridge.py`)

`probe_rtsp_stream(url, *, connect_timeout_seconds=4.0,
total_timeout_seconds=8.0, ffmpeg_binary="ffmpeg", popen_factory=...) ->
RtspProbeResult` -- a bounded, one-shot live probe built entirely from this
module's own existing primitives (`build_rtsp_mjpeg_command`/
`start_rtsp_mjpeg_process`/`iter_multipart_mjpeg`), generalized with two
small additive parameters:

- `start_rtsp_mjpeg_process(..., capture_stderr=False)` -- opt-in
  `stderr=PIPE` (every existing live-playback caller keeps the unchanged
  `DEVNULL` default) so a probe failure can be classified from ffmpeg's own
  evidence instead of guessed.
- `iter_multipart_mjpeg(..., on_chunk=None)` -- fires on any stdout bytes
  at all, before a full frame is necessarily assembled -- the probe's own
  "did the source respond at all" signal, distinct from (and earlier than)
  `on_frame`'s "one full usable frame decoded" signal.

Bounded by two independent wall-clock ceilings enforced by polling a
background reader thread (`_wait_until`) rather than `select()` on a pipe
(`select()` does not work for pipes on Windows, and this product runs on
both platforms): `connect_timeout_seconds` for the first byte of any kind
back from ffmpeg, `total_timeout_seconds` for the whole probe including
decoding one frame -- both comfortably under the frontend's own
`VALIDATE_TIMEOUT_MS` (10s, `CameraSetupPage.tsx`). Every exit path
(success, either timeout, or a clean ffmpeg exit) tears the process down
through the existing `_stop_process` terminate-then-kill discipline --
never a leaked/zombie decode process, never a standing background session.

Never downgrades `rtsps://` to `rtsp://` and never spawns a process for one
at all -- checked before the process-spawn call, mirroring
`RTSPS_TRANSPORT_SUPPORTED`'s existing defense-in-depth philosophy.

### Error distinctions (B4)

Classified from real ffmpeg evidence only where it exists
(`_classify_probe_failure`): `401`/`403`/"unauthorized"/"forbidden" in
stderr -> authentication failed; connection-refused/timed-out/unreachable
markers -> source unreachable; a `codec`+`not supported`/`unsupported`
pairing -> unsupported codec; `404`/"not found"/method-failed markers ->
negotiation failed. Absent any of those markers, the fallback is
evidence-driven rather than guessed: zero stdout bytes ever arrived ->
negotiation failed (never invented as "unreachable" or "authentication
failed" without evidence); real bytes arrived but no frame ever assembled
-> decode failed. A genuine connect-phase timeout (nothing responded at
all within `connect_timeout_seconds`) is its own distinct `unreachable`
code; a total-phase timeout (bytes were flowing but never completed) is
its own distinct `validation_timed_out` code.

Seven new `acquisition_provider` codes registered in
`diagnostics/error_taxonomy.py` (`camera_setup_rtsp_unreachable`/
`_authentication_failed`/`_negotiation_failed`/`_unsupported_codec`/
`_decode_failed`/`_validation_timed_out`/`_ffmpeg_unavailable`); the two
pre-existing structural codes (`camera_setup_invalid_url`,
`camera_setup_rtsps_unsupported`) are reused unchanged for their existing
cases.

### Credential safety (B6, mandatory)

`redact_credentials_in_text(text)` -- a new, independent helper from
`redact_url`/`_redact_url_credentials` (both of which require the *entire*
input to already be one clean URL): a regex-based scrubber for a
`scheme://user:pass@` substring appearing anywhere inside a longer text
blob, since ffmpeg's own RTSP I/O error paths sometimes echo the `-i` input
URL verbatim inside a longer diagnostic sentence -- a real, observed
behavior, not a hypothetical. Applied at the one place raw ffmpeg stderr is
ever read (`_redacted_stderr`, itself only ever called after the process is
confirmed stopped -- mirrors `recorded_video_source.sample_recorded_video_
frames`'s identical post-mortem-only stderr read) -- before that bounded,
already-truncated text becomes `RtspProbeResult.detail`, so every
downstream consumer inherits the redaction for free.

The user-facing response never carries `detail`/raw ffmpeg text at all,
redacted or not: `ProductRepository.validate_camera_setup`'s failure branch
always uses `error_taxonomy.resolve_error(code).message` -- the same fixed,
safe copy already used for every other taxonomy-backed message in this
product. `detail` reaches only the one new, bounded, advanced-log-only
`log_error_event("acquisition_provider", "rtsp_setup_probe_failed",
code=..., detail=...)` call.

The existing setup-preview redaction
(`_source_provider_configuration_from_config`'s `safe_config_preview`,
already applying `_redact_url_credentials` to every non-secret field since
v0.1 Acquisition/Ingest Interoperability Closure v1) is unmodified and
unaffected -- still the surface that protects a saved `live_stream_url`
from ever showing its embedded credential in the Camera Setup UI.

### Wiring (B7)

Extends the existing `ProductRepository.validate_camera_setup` --
`_rtsp_setup_probe_if_applicable(config)` returns `None` (unchanged prior
behavior) for every `external_url` shape except a genuinely
`live_stream_type="rtsp"` config with a non-empty `live_stream_url`; a
still-image-only or non-RTSP live-type `external_url` Source is never
probed (matching `live_stream_url`'s own "not fetched by the backend"
description for those types). No new endpoint, no new page:
`/api/camera-setup/validate` and `/api/camera-setup/complete` (which
already calls `validate_camera_setup` internally to gate its own writes)
both transparently gain the bounded live probe. A probe failure sets
`can_continue=False` on the *existing* `CameraSetupValidationResponse`
shape -- no schema change -- so `complete_camera_setup` is automatically
gated too, the same way a Camera Node's own `node_unavailable` already
gates completion. `validate_camera_setup` never persists anything on its
own (a `CameraSourceModel(id="camera-setup-draft", ...)` is built
in-memory only, never added to the session) -- a failed probe therefore
never leaves a Source to delete before a corrected retry.

The frontend needed no change at all: `CameraSetupPage.tsx` already renders
`validation.status`/`validation.message` generically (no hardcoded status
allowlist) and already gates Complete Setup on `validation.can_continue` --
confirmed by a clean `tsc --noEmit && vite build` with zero source changes
under `web/src/`.

## Files touched

- `src/mockingbird/diagnostics/error_taxonomy.py` (seven new
  `acquisition_provider` codes)
- `src/mockingbird/playback/rtsp_bridge.py` (`RtspProbeResult`,
  `probe_rtsp_stream`, `redact_credentials_in_text`, `_wait_until`,
  `_redacted_stderr`, `_classify_probe_failure`; `iter_multipart_mjpeg`
  gains `on_chunk`, `start_rtsp_mjpeg_process` gains `capture_stderr`)
- `src/mockingbird/repository/product_repository.py`
  (`_rtsp_setup_probe_if_applicable`, wired into `validate_camera_setup`'s
  `external_url` branch; `_resolve_camera_health_state` gains
  `resolved_health_state` and its own `log_event` call, both call sites in
  `_sync_camera_health_incident` updated)
- `src/mockingbird/observation/engine_runtime.py` (two additive
  `log_error_event` calls, see A2 above)
- `src/mockingbird/observation/offline_ingest.py` (one additive
  `log_error_event` call, see A1 above)
- `src/mockingbird/playback/live_camera_session.py` (one additive
  `log_error_event` call, see A1 above)
- `tests/test_rtsp_probe.py` (new), `tests/test_camera_setup.py`,
  `tests/test_camera_health.py`, `tests/test_engine_runtime.py`,
  `tests/test_live_camera_session.py`, `tests/test_offline_ingest.py`
- this document; "Not yet covered" in
  [observability-error-taxonomy-contract.md](observability-error-taxonomy-contract.md)
  updated to reflect this closure

## Non-goals

- A second RTSP decoder, a second ffmpeg wrapper, or a standing background
  monitoring service for setup validation (B2) -- the probe is one bounded,
  request-scoped call reusing existing primitives.
- Re-litigating RTSPS support (B5) -- still genuinely unsupported by this
  deployment's ffmpeg build; the probe adds a second, defense-in-depth
  refusal, never a downgrade path.
- Host startup/shutdown logging, a metrics endpoint, browser-tab-close
  draft persistence for non-Camera-Node setup, continuous Camera Node
  API-version revalidation, or a single end-to-end Observation-session
  correlation id -- all explicitly disclosed, non-blocking hardening items
  from the prior milestone, unchanged by this one.
- Evidence-persistence failures beyond the existing
  `CameraHealthIncidentCategory.evidence_persistence_degraded` durable
  fact -- still open, not part of this milestone's named three.

## Validation tier

Tier 2 (focused unit/integration): `tests/test_rtsp_probe.py` (bounded
probe boundary/timeout/classification/redaction, plus one real local
ffmpeg decode of genuine MJPEG output through the same frame parser);
`tests/test_camera_setup.py` (real HTTP round trip through
`/api/camera-setup/validate`, including the mandatory credential-leak
regression driving the *real* probe against a fake subprocess);
`tests/test_camera_health.py`/`tests/test_engine_runtime.py`/
`tests/test_live_camera_session.py`/`tests/test_offline_ingest.py` (Part A
structured-evidence regressions). Frontend: `tsc --noEmit && vite build`,
zero source changes. A full Core gate (`scripts/verify_core.py`) closes
this milestone.
