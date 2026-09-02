# Host ↔ Camera Node compatibility preflight

Answers one bounded question before an expensive Host operation begins:
**is this Host and this paired Camera Node compatible for the capability
this operation needs, right now?** Built after Representative Daylight
Gate A Field Acceptance v8 ran a full 158-minute field session against a
real reference Camera Node whose installed software predated the accepted
RTT-Bounded Clock Calibration v1 protocol -- 796 calibration attempts, 0
valid samples, discovered only after the session had already run. See
[host-camera-node-release-compatibility-preflight-v1-report.md](host-camera-node-release-compatibility-preflight-v1-report.md)
for the full implementation record; this document is the durable
reference for what the contract means going forward.

## What compatibility means

Compatibility is **capability-based**, evaluated per Host operation, never
a single yes/no fact about a Camera Node in isolation. The same Node can
be compatible for one operation and incompatible for another, and that is
the expected, correct outcome -- not a defect.

`mockingbird.observation.node_compatibility` is the one implementation:
`classify_node_compatibility` is the pure decision table; `probe_node_
compatibility` is the live orchestration (fetch health, optionally confirm
the expected camera, optionally run a real bounded RTT batch). Both Doctor
and the field-acceptance enforcement inside `start_stream_observation`
answer from this one place -- there is no second, parallel compatibility
implementation anywhere in the codebase.

## Why exact commit equality is not required

MockingBird does **not** require `Host git commit == Node git commit`.
Exact revision equality is brittle and does not express product
capability: a Node several commits behind Host HEAD is routinely,
correctly, compatible for ordinary use, and a Node on the *same* commit
could still fail a capability check if its process state, camera, or
network path is degraded. The existing `api_version` exact-match gate
(`CameraNodeClient.pair`, `camera_node_transport.TRANSPORT_PROTOCOL_
VERSION`) already protects wire-protocol-*shape* compatibility at
pairing/transport time; this preflight answers the narrower, additive
question a Node that already passed that gate can still fail: does it
support the specific capabilities one particular Host operation requires.

The Camera Node's `/node/v1/health` response has never exposed a live
`git_commit` at all (only a package `service_version`, which this
codebase does not currently bump per commit -- both `mockingbird` and
`mockingbird_node` are pinned at `0.1.0` today). No wire-protocol change
was made to add one: the existing `api_version`/`service_version`/
`node_receive_time`/`node_time` fields are sufficient to answer every
question this contract asks. Differing build identity is reported as
informational `version_skew_detected` diagnostics (Host `git_commit`
next to Node `service_version`) -- it is **never** by itself a reason to
fail compatibility.

## Profiles

- **`ordinary_monitoring`** -- everyday product use. Requires only that
  the Node's health protocol answers at all (`health_protocol`). An old,
  pre-RTT Node is correctly compatible here; RTT-bounded clock calibration
  is an optional diagnostic capability for this profile, never a blocker.
- **`field_acceptance`** -- a Representative Daylight Gate A / true-latency
  acceptance session. Requires:
  - `health_protocol` -- the Node reachable and its health response shaped
    as expected;
  - `expected_camera_available` -- the specific camera this Stream is
    configured to use is live-confirmed present and `"available"`;
  - `rtt_timestamp_fields` -- the health response actually carries
    `node_receive_time`/`node_time` (the exact fields v8's Node lacked);
  - `bounded_rtt_clock_calibration` -- a real bounded RTT-bounded
    calibration batch (`clock_calibration.estimate_rtt_clock_calibration`,
    the accepted production function, never a second implementation)
    actually reaches `state == "calibrated"`. Advertising the timestamp
    fields is not enough by itself -- a real probe must also succeed.

Reuse these two profiles rather than adding a third without a concrete,
already-identified Host requirement behind it.

## What an old Node can still do

An old Node -- v8's own Node, or any Node predating RTT-Bounded Clock
Calibration v1 -- remains fully usable for **ordinary product monitoring**:
Start observing, live preview, Visit/evidence capture, review, and
history all continue to work exactly as before. Nothing about this
preflight changes behavior for a signed-in human user's own Start
observing; the stricter `field_acceptance` profile only ever evaluates
when the caller authenticates with a Field Acceptance Operator credential
(see `request.state.field_acceptance_principal` in
`api/auth.install_authorization`) -- the same narrow, already-accepted
mechanism Representative Daylight sessions already use to start and stop
Observation non-interactively.

## How to resolve incompatibility

1. Run `python scripts/check_camera_node_compatibility.py --base-address
   <node address> --profile field_acceptance [--credential ... --camera-id
   ...]` to get a live, actionable verdict and the specific
   `missing_capabilities`.
2. If the result is `incompatible_missing_capability` (the v8 case):
   upgrade the Camera Node via the existing, already-accepted
   `scripts/install_camera_node.py` mechanism, then rerun the preflight.
3. If the result is `calibration_failed` (capability advertised but a real
   probe failed): check network conditions between the Host and the
   Camera Node, then rerun.
4. If the result is `camera_unavailable` or `node_unreachable`: check the
   Camera Node's power, network connection, and the specific camera's
   connection.
5. A field-acceptance session's own `POST .../observation/start` enforces
   this automatically and fails closed (an honest `needs_attention`
   status, never a stack trace) before any Observation session, recorder
   allocation, or GPU/model resource commitment -- upgrading/recovering
   the Node and rerunning the preflight is the only supported path back to
   `compatible`. Nothing in this preflight mutates Camera Node state,
   SSHes into it, or upgrades it automatically.

## Local Only

Every check in this contract runs over the existing local Host↔Camera
Node LAN protocol only (`CameraNodeClient`, unauthenticated `/node/v1/
health` for reachability/RTT, authenticated `/node/v1/cameras` for camera
availability). No cloud registry, no internet version service, and no
GitHub check participates in this decision at runtime.
