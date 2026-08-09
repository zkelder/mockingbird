# Unified Observation panel contract

Status: MockingBird Unified Observation Experience v1. This wraps the
accepted Observation Engine control described in
[observation-engine-product-control-contract.md](observation-engine-product-control-contract.md)
and the existing durable monitoring/Snapshot monitor paths described in
[durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md);
it composes those unchanged runtimes behind one product-facing panel and
adds no new detector, tracker, candidate-authority, or evidence-quality
threshold.

## Problem

Product Vertical Slice v1 made Start/Stop observing reachable from the app
for paired Camera Node Streams only. Every other currently-supported Stream
type (RTSP and other `external_url` live-video kinds, Linux local USB,
Windows DirectShow, and `external_url` still-image Snapshot monitoring)
still showed the Camera-Node-specific Observation panel next to two more
panels covering the same ground ("Camera health", "Monitoring continuity"),
and pressing Start on a non-Camera-Node Stream reported a confusing
"isn't a paired Camera Node yet" message. A normal user should not need to
know which runtime is underneath to answer "is this camera watching for
wildlife right now."

## Lane resolution

`mockingbird.observation.unified_status.resolve_observation_runtime` picks
one existing runtime per Stream, using only already-configured product
metadata (no network probe):

| Stream configuration | Lane | Existing runtime reused |
| --- | --- | --- |
| Source provider `camera_node` | `camera_node_engine` | `engine_runtime.ObservationEngineSessionManager` (Stage 5/7 frame-driven engine), unchanged |
| `live_stream_type` is `rtsp`, `local_usb`, or `windows_dshow` | `live_monitoring` | Durable `StreamMonitoringPolicy` + `DurableMonitoringSupervisor` + `LiveCameraSessionManager`, unchanged |
| Remaining Source provider `external_url` | `snapshot_monitor` | `SourceMonitorManager` (wrapped as `SnapshotObservationProvider`), unchanged |
| Everything else (demo, manual media, folder/webhook import, or a not-yet-implemented future adapter) | `unavailable` | none |

A Camera Node Stream always uses the accepted engine even though
`LiveCameraSessionManager` could technically also monitor it (Camera Node is
in its `SUPPORTED_SESSION_TYPES` for the older motion-evidence path); the
hard architecture rule is not to force every camera type through the
frame-driven engine, not to keep the engine's own intended type off it.
`external_url` is dual-purpose: a Stream configured with a live-video
`live_stream_type` (RTSP today) lands on `live_monitoring`, and a plain
still-image URL lands on `snapshot_monitor`, exactly matching each existing
route's own established acceptance boundary (`/live-session/*` versus
`/monitor/*`).

## Unified contract

`GET/POST /api/streams/{id}/observation/status|start|stop` is the same
route family Product Vertical Slice v1 already established; it is now
lane-aware instead of Camera-Node-only. `ObservationSessionStatusResponse`
gained fields additively (`runtime_available`, `last_useful_frame_at`,
`setup_action`, `retry_action`); no existing field was removed, and
`state`'s wire vocabulary moved from the engine-internal `error` value to
the product-level `needs_attention` value used by every lane.

- `state`: `stopped | starting | observing | stopping | needs_attention`.
- `observing`: basic boolean the panel's title/pill are driven from.
- `message` / `camera_message` / `engine_message`: plain-language, already
  sanitized by the existing per-lane runtime (`CameraHealthSummary`'s
  established narrative for `live_monitoring`, the Snapshot monitor's own
  `_monitor_status_message` for `snapshot_monitor`, the accepted engine's
  own sanitized text for `camera_node_engine`).
- `runtime_available`: false only for the `unavailable` lane -- an honest
  "no runtime here" signal instead of a Start button that would only fail.
- `setup_action`: `"edit_camera_setup"` when the one relevant existing setup
  action (Guided Camera Editing, `get_camera_configuration_edit`'s existing
  editable-provider set) would plausibly help.
- `retry_action`: true only for the `live_monitoring` lane's own bounded
  `POST .../runtime/retry`, reused unchanged.
- `last_useful_frame_at`: best-effort per lane (`CameraHealthSummary.
  last_good_frame_at` for `live_monitoring`, the Snapshot monitor's last
  successful tick for `snapshot_monitor`); absent for `camera_node_engine`,
  which does not currently track this fact -- reported as missing rather
  than invented.
- `counts` / `advanced`: unchanged shape. `advanced.runtime_kind` names the
  resolved lane for diagnostics; it is never surfaced in a basic field.

## Start behavior per lane

- `camera_node_engine`: unchanged call into
  `ObservationEngineSessionManager.start`, already idempotent (an active
  session is returned as-is).
- `live_monitoring`: validates readiness through the existing, already
  side-effect-free `StreamPlaybackStatus` contract first (RTSP bridge/local
  device/DirectShow checks it already performs); only when
  `status == live_ready` does it call the existing
  `PUT .../monitoring-policy` handler with `enabled=true` -- the same action
  "Enable monitoring" already performs, reusing `set_stream_monitoring_
  enabled`'s own idempotent semantics. An unready Stream never gets armed.
- `snapshot_monitor`: calls the existing `POST .../monitor/start` handler
  unchanged, including its own idempotent "already starting/monitoring"
  short-circuit and its existing storage-guardrail/missing-URL rejections,
  translated into the unified `needs_attention` shape instead of a raw 400.
- `unavailable`: a side-effect-free no-op; reports the honest unavailable
  status.

Start is always HTTP 200 with an honest status -- never a 500, never a
silent fallback to a runtime this Stream doesn't use, and never a raw
validation exception for a mis-configured Stream.

## Stop behavior per lane

- `camera_node_engine`: unchanged kill switch (candidate authority always
  reverts to `shadow`).
- `live_monitoring`: calls the existing policy handler with `enabled=false`
  -- the same action "Disable monitoring" already performs.
- `snapshot_monitor`: calls the existing `POST .../monitor/stop` handler
  unchanged.
- `unavailable`: a side-effect-free no-op.

Stop never deletes evidence, never touches an already-created candidate or
reviewed Visit, and never changes monitoring configuration beyond disarming
the one action Start just armed.

## Product support matrix

`mockingbird.observation.unified_status.PROVIDER_SUPPORT_MATRIX` grounds
this table in the actual provider registry
([source-provider-configuration-contract.md](source-provider-configuration-contract.md)):

| Source provider | Support level | Notes |
| --- | --- | --- |
| `camera_node` | Observation supported | Frame-driven engine; needs pairing plus a local model bundle |
| `local_usb` | Observation supported | Linux V4L2 or Windows DirectShow, chosen by `live_stream_type` |
| `external_url` | Observation supported | RTSP live-video kinds use `live_monitoring`; a plain still-image URL uses `snapshot_monitor` |
| `demo` | Development-only | Seeded local demo Stream, not a real camera |
| `manual_media` | Observation unavailable | Import-only; no live camera to observe |
| `folder_import_future` | Observation unavailable | Import-only; no live camera to observe |
| `webhook_future` | Observation unavailable | External event data only; no live camera to observe |
| `rtsp_future` | Observation unavailable | Registered as a future Add Camera contract only; a real RTSP Stream is actually configured through `external_url` above |
| `esp32_future`, `browser_camera_future` | Observation unavailable | Not yet implemented |

## Basic versus advanced

Basic fields (`message`, `camera_message`, `engine_message`) never contain
`SnapshotObservationProvider`, `frame-driven-onnx-cuda`, `provider
generation`, `ONNX Runtime`/`CUDA`, `policy_revision`, or a runtime-kind
name -- only plain language: Observing, Not observing, Camera unavailable,
Camera needs setup, Couldn't get a usable image, Observation stopped
unexpectedly. That vocabulary, provider ids, `runtime_kind`, desired/actual
runtime state, and failure codes live only inside `advanced` and the Stream
Detail panel's collapsed "Advanced diagnostics" `<details>`, closed by
default.

## Stream Detail

Stream Detail shows exactly one `Observation` panel
(`web/src/components/ObservationControlPanel.tsx`), replacing the separate
"Camera health" and "Monitoring continuity" sections for every Stream type.
Its three basic layouts:

```text
Observation                          Observation                          Observation
Camera: Healthy                      Observing                            Needs attention

[ Start observing ]                  Last activity ...                    <plain-language reason>
                                      [ Stop observing ]                   [ relevant existing setup action ]
```

A Stream with no integrated runtime (`runtime_available: false`) shows a
calm, honest "not available" message instead of either layout -- never a
Start button that would only fail, and never an alarming "Needs attention"
framing for something that was never going to work. The full
`/camera-health`, `/camera-health/incidents`, and `/runtime-status` data
this replaces remains available through its existing routes; this panel
does not remove that capability, only the competing default Stream Detail
surface for it.

## What stays unchanged

- Existing Snapshot monitoring policy, Source/Stream configuration, Zones,
  Privacy/Ignore, retained Visits, and Review Queue.
- Camera Node's Stage 7 candidate-Visit authority and candidate-quality
  admission boundary -- unified routing decides which runtime to call, not
  what authority that runtime has.
- `live_monitoring`'s existing Visit behavior through the legacy
  motion-evidence path (`auto_create_review_candidates`), unaffected by
  which button armed the policy.
- Today in Your Yard and Review Queue's existing reviewed-truth derivation;
  no Stream in any lane gains a new way to write a `ReviewLabel`.

## Testing expectations

- Lane resolution matches actual repository capability for every currently
  supported and currently unsupported provider key.
- Status/Start/Stop are covered per lane, including duplicate Start/Stop
  idempotency, an unconfigured provider's honest `needs_attention`/
  unavailable state, and a Stream with no runtime never touching Stage 7
  authority or the durable monitoring policy.
- Camera Node's own existing behavior (`test_engine_runtime.py`) is
  untouched; this contract only changes which Streams reach it.
- Stream Detail renders exactly one `Observation` panel, with Advanced
  diagnostics collapsed by default and no forbidden vocabulary visible
  outside it.
