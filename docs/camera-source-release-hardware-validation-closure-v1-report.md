# Camera / Source Release Hardware Validation Closure v1

Lane G validation milestone. Converts as much of Lane G's "MATERIALLY
CLOSED / VALIDATION REMAINS" state into real hardware evidence as tonight's
actual available hardware permits -- no new providers, no wildlife-
denominator field cohort. See the governing brief for the full mandate.

## Starting state

- Actual git HEAD at start: `20ac5ba4661abf0083bb05901f42da26d645243d` --
  matches the brief's expected value.
- Latest accepted milestone at start: Strong-Confidence Subject-Evidence
  Viability & Scene-Artifact Abstention v1 (classification B) -- matches.
- Schema at start: v58 -- matches (confirmed from `docs/release-execution-
  state.md` §1's own text: "schema unchanged (`v58`)").
- Untracked, preserved-on-purpose files (small-bird detector training
  material, see `docs/release-execution-state.md` §13 "Preserved untracked
  detector files"): all 7 present and confirmed byte-identical (`md5sum`)
  both before and after this milestone's work. Untouched.
- Worktree safety: no `.git/*.lock`. Three other `ccd-cli` processes had
  their cwd in this exact worktree (PIDs 126781, 863042, 879135, started
  14:56/20:01/22:04 today respectively -- this session is a separate PID,
  888186, started 23:08); all three were in kernel state `S` (sleeping),
  and a `find -newermt '30 minutes ago'` swept the whole tree immediately
  before starting substantive work, showing no file modified in that
  window beyond the 7 already-known preserved files. Read as idle/finished
  sessions from earlier tonight's milestones, not active writers.
  `git status` was re-checked clean immediately before every write this
  session.

## Scheduler headline reconciliation

**Determination: not a real stale-headline defect.** `docs/release-
execution-state.md` §1's "Accepted HEAD" field names `d1f4f18` (the
*report* commit for Strong-Confidence Subject-Evidence Viability &
Scene-Artifact Abstention v1), not `20ac5ba` (the *reconciliation* commit
that recorded its acceptance). This is the document's own established,
consistent convention, not staleness:

- The immediately-prior cycle shows the identical pattern: `d1f4f18`'s own
  predecessor entry, "Prior accepted HEAD," names `1465103` (the report
  commit for Strong-Confidence Non-Target & Scene-Artifact Visit Admission
  Correctness v1) -- never `127edaf`, the reconciliation commit that
  accepted *it*. That pattern held for the entire gap between `127edaf`
  landing and `20ac5ba` landing; nobody treated it as needing correction.
- `git show 20ac5ba`'s own diff confirms this was deliberate: the
  reconciliation commit's own message states "Updates §1 (accepted HEAD ->
  d1f4f18)" -- i.e. `20ac5ba` intentionally wrote the *report* commit's
  hash into "Accepted HEAD," exactly matching the established pattern, not
  a slip.
- §15 "Update protocol" frames a reconciliation commit as the *mechanism*
  that records milestone closure ("At each accepted milestone closure,
  update ... accepted HEAD"), not as the thing being recorded. A
  reconciliation commit's entire diff is bookkeeping on this one file; the
  "accepted state" it exists to describe is necessarily the commit
  *before* it.
- Neither `20ac5ba` nor `127edaf` (the two most recent reconciliation
  commits) appear anywhere in the document by hash yet -- consistent with
  every prior reconciliation commit's hash only getting cited later, as
  lineage context, in a *subsequent* milestone's own entry (e.g. "sits on
  top of `89b87f1` (the reconciliation commit accepting ...)" -- multiple
  such citations exist for older cycles).
- §5/§6 spot-checked Lane M/N/O/P/Q/L status lines against the brief's own
  headline claims (all closed/materially-closed as stated; Lane L's
  "specifically-named remaining item," the Camera Node upgrade workflow,
  is recorded closed by name); all matched exactly, and Lane G's own §6.G
  text matches the brief's "MATERIALLY CLOSED / VALIDATION REMAINS --
  RELEASE-CRITICAL" headline verbatim.

**Correction made: none.** The headline is accurate under this document's
own established meaning of "Accepted HEAD." No bookkeeping edit was made
for this item.

## Available hardware

| Candidate source | Reachable tonight? | Notes |
|---|---|---|
| Reference Camera Node (Pi, `192.168.1.112:8787`, `node-76ec8e53ae586dd0`) | **Yes** | Real Raspberry Pi, real `ov64a40` (64MP Arducam-family) CSI sensor, confirmed physically detected via `rpicam-hello --list-cameras` on the device. `ssh mockingbird-pi` / passwordless `sudo` both working. |
| RTSP endpoint | No | No device on the LAN answers port 554 (`192.168.1.1` gateway and `192.168.1.112` both refuse it); no other RTSP source known to this environment. |
| Local USB/V4L2 (Host-side `local_usb` provider) | No | `/dev/video*` does not exist in this WSL sandbox; `lsusb` (WSL) enumerates nothing. |
| Windows DirectShow | **Partially** | Native Windows host reachable via `powershell.exe` interop (Windows 10.0.19045). A real, previously-used USB webcam (`EMEET SmartCam S600`) is known to Windows (`Get-PnpDevice -Class Camera,Image` lists it, `Status: Unknown`) but is **not currently connected** -- `ffmpeg.exe -f dshow -list_devices true` enumerates 0 video devices (2 audio-only devices). |
| ONVIF device | No | No ONVIF-capable device on the LAN; no discovery library installed to probe further even if one existed. |

Declared-release source hardware physically available and exercisable
tonight: **the reference Camera Node only.** Windows DirectShow hardware
is registered but disconnected -- enumeration-level evidence only. No
hardware was fabricated to fill these gaps (Section 2).

## Declared support scope

Lane G's own text (`docs/release-execution-state.md` §6.G) and the
governing brief's Section 4 set the matrix this milestone validates
against: Camera Node (golden path), RTSP, ONVIF (converges into the RTSP
bridge), Local USB/V4L2, Windows DirectShow. No new provider was
implemented or considered (Frigate/Blue Iris/Scrypted/Home
Assistant/GenICam/GigE/USB3 Vision/new NVR integrations all explicitly out
of scope; Lane K remains a separate open decision, untouched).

## Camera Node result

Real, live evidence gathered against the reference Node this session:

- **Health** (`GET /node/v1/health`, unauthenticated): `status:
  "available"`, `camera_count: 8`, `available_camera_count: 8`,
  `pairing_required: false`, real `boot_id`/`os_uptime_seconds`/
  `service_version`, `self_test: {status: "passed", camera_available:
  true, providers_initialized: true, pairing_state_writable: true}`,
  `watchdog: {enabled: true, last_probe_ok: true}`.
- **Compatibility preflight**
  (`scripts/check_camera_node_compatibility.py`, the exact production
  `probe_node_compatibility` function, run twice tonight):
  - `ordinary_monitoring`: `state: "compatible"`, `compatible: true`.
  - `field_acceptance`: `state: "compatible"`, `compatible: true`, with a
    **real bounded RTT-clock-calibration batch** run live:
    `sample_count: 5`, `valid_sample_count: 5`, `state: "calibrated"`,
    `rtt_ms: 21.57`, `offset_ms: 0.38`, `uncertainty_ms: 6.06`,
    `clock_jump_detected: false`.
- **Observation start eligibility**: proven via the same compatibility
  preflight (the exact gate `start_stream_observation` enforces) rather
  than actually starting a session -- correctly per this milestone's own
  "no wildlife-denominator field cohort, nighttime work" constraint.
- **Pairing/setup honesty, real probe**: a live `POST /node/v1/pair` with
  a garbage code against this already-paired Node returned `409 {"detail":
  "Pairing code was already used."}` -- exactly the honest, harmless
  rejection the code predicts (`pairing.pair()` checks `pairing_code_used`
  before ever comparing the offered code, so this could not have disturbed
  or rate-limited whichever credential is genuinely active). Confirms the
  real Add-Camera pairing-conflict failure path end to end.
- **Recovery after a bounded interruption** (`sudo systemctl restart
  mockingbird-camera-node.service` on the real Pi): service came back
  healthy on the very first health poll (~2s). `service_uptime_seconds`
  reset to ~4.3s (a real restart, confirmed independently via `systemctl
  status`: new PID, new Invocation ID, "Active: active (running) ...
  2s ago") while `os_uptime_seconds` climbed continuously across the
  restart (only the service restarted, not the OS). `node_id` and
  `boot_id` were **unchanged** (correct: a service restart is not a
  reboot, and the boot-identity mechanism correctly did not treat it as
  one), `pairing_required` stayed `false` (the on-disk pairing survived,
  per `_PairingState`'s own persist-on-pair design), `camera_count`/
  `available_camera_count` unchanged (8/8), self-test ran fresh and again
  reported `passed`/`camera_available: true`. No duplicate Stream
  creation, no corrupted configuration, no lost credential, no stale
  permanent failure state, nothing needing deletion/recreation.
- **Live authenticated preview/snapshot: not exercised.** The only
  locally-known pairing credential (in this repo's own dev
  `data/mockingbird.sqlite3`, `source-0867dc0e0467`) is stale (`updated_at
  2026-08-09`) and its own stored `node_pairing_state` is `"revoked"`. The
  Node's pairing model is single-credential (`_PairingState` holds exactly
  one `_credential_digest`; a fresh pairing attempt against an
  already-paired Node fails, as directly confirmed above) and the currently-
  active credential is unknown to this session. Deliberately did **not**
  restart the Node a second time or otherwise force a fresh pairing merely
  to obtain one: this is a shared reference device other sessions rely on,
  and forcing a re-pair is a real, if small, disruption this
  validation-only milestone does not need. This is an honest,
  disclosed credential-availability limitation, not a code defect --
  matching the identical, already-disclosed gap in Camera Node Upgrade &
  Compatibility Recovery v1's own report ("A full authenticated snapshot
  capture through the paired credential was not exercised").

## Camera Node diagnostic-truth reproducer

**Reproduced, deterministically, against this exact reference Node's own
real device topology.**

Exact field(s) involved: `/node/v1/health`'s `self_test.camera_available`
(and, contributing to it, `camera_count`/`available_camera_count`),
computed by `run_startup_self_test()` in
[selftest.py](../src/mockingbird_node/selftest.py) from
`provider.cameras()` in
[providers.py](../src/mockingbird_node/providers.py).

**What `self_test.camera_available` actually measured (before this
fix):** `any(camera.status == "available" for camera in
provider.cameras())` -- true if *any* enumerated camera object, from *any*
enabled provider, claims availability. It has no concept of "the
specifically configured camera" at all, by original design: self-test
runs exactly once, at Node process startup
([selftest.py:1-16](../src/mockingbird_node/selftest.py)), before any
Host has ever paired or configured a Stream against this Node.

**What the Host compatibility preflight measures differently:**
`probe_node_compatibility()` in
[node_compatibility.py:272-281](../src/mockingbird/observation/node_compatibility.py)
fetches the *live* `/node/v1/cameras` list and checks `camera.camera_id ==
expected_camera_id and camera.status == "available"` for the *exact*
`camera_id` a Stream is paired to -- both because it runs per-operation,
long after pairing, and because it is a live, present-tense probe.
Self-test's result, by contrast, is computed once and then served on
*every* subsequent `/node/v1/health` response for the life of the process
([app.py:373-375](../src/mockingbird_node/app.py) calls it once at
app-factory time; the health handler serves the cached
`self_test_result.as_payload()` forever, while `cameras`/
`available_camera_count` in the same response are recomputed live on every
request). This staleness is a second, independent, already-disclosed
characteristic (self-test's own docstring: "never again on a timer") --
real, but out of this milestone's bounded fix (see below).

**Whether the configured provider/device is being checked:** no -- and,
architecturally, self-test cannot know it (no Stream/pairing exists yet
at Node startup). The compatibility preflight is the correct place for
that check, and it already does it correctly.

**Whether a stale/general camera-capability result is being mistaken for
configured-camera availability: yes, confirmed live.** This Node's real
config (`/etc/mockingbird-camera-node/node.env`:
`MOCKINGBIRD_NODE_PROVIDERS=picamera2,v4l2`) enables both providers.
`V4L2CameraProvider.cameras()`
([providers.py:298-301](../src/mockingbird_node/providers.py), before this
fix) unconditionally marked **every** enumerated `/dev/videoN` character
device `status="available"`, purely from path existence -- never checking
whether it actually opens. On this real Pi, `/dev/video0` (`unicam`, the
CSI sensor's own raw capture node -- libcamera-only, not directly
V4L2-openable) and `/dev/video10-23,31` (the Pi's internal
`bcm2835-codec-decode`/`bcm2835-isp`/`rpi-hevc-dec` ISP/codec/HEVC-decoder
pipeline stages -- kernel-driver infrastructure, never independent
cameras) all exist as real character devices *unconditionally*, whenever
the driver stack is loaded, regardless of whether any camera is attached.
Directly verified live against the Node's own installed OpenCV
(`/opt/mockingbird-camera-node/venv/bin/python3`, cv2 4.10.0): **none** of
`/dev/video0,10,13,19,31` opens via `cv2.VideoCapture(path,
cv2.CAP_V4L2).isOpened()` -- not even `/dev/video0`, the real sensor's own
node, since this Pi's CSI camera requires libcamera/picamera2, not plain
V4L2. `MAX_CAMERAS = 8` in `providers.py` is exactly why the live health
payload showed `camera_count: 8`/`available_camera_count: 8`: 8 of these
never-openable device nodes, truncated at the composite provider's own
`MAX_CAMERAS` bound, unconditionally counted as "available."

This reproduces Representative Daylight Gate A Field Acceptance v11's
exact real field shape verbatim: `picamera2` (the real camera provider)
correctly reported `picamera2-no-camera`/`unavailable` (confirmed there
via live `/node/v1/cameras` and `vcgencmd get_camera`) while self-test
*still* said `passed`/`camera_available: true`, twice, following a genuine
CSI ribbon-cable fault -- because a co-enabled `v4l2` provider's bogus
"available" entries kept the aggregate `any(status=="available")` true
regardless of the real camera's actual state. v11 also independently
confirms this is not a pure staleness artifact: the false-positive
recurred on a **fresh** self-test evaluation, run after a genuine
power-cycle, with the cable fault already present -- so the defect is in
what a live self-test computes, not merely in how long it is cached.

Root cause is bounded to Node-local source-health truth (one provider's
own definition of "available" inside `mockingbird_node`) -- no Camera
Node protocol/architecture change is implicated.

## Camera Node diagnostic fix

Fixed in [providers.py](../src/mockingbird_node/providers.py),
`V4L2CameraProvider`:

- Added `_is_capture_capable(runtime, path)`: a bounded (`_bounded_call`,
  the module's own existing wedged-driver-safe pattern, reused unmodified;
  new `V4L2_PROBE_TIMEOUT_SECONDS = 1.5`, well under the 3.0s full-capture
  timeout since this is open-only, no frame read), per-path-cached
  (device capture-vs-pipeline-stage capability is a static kernel-driver
  fact, not one that changes at runtime) probe that reuses the *exact*
  `VideoCapture(...).isOpened()` check `snapshot()` already trusted as
  ground truth for a live capture -- never a second, divergent
  openability signal, just performed once per path at enumeration time
  too, not only at actual-capture time.
- `cameras()` now excludes any device that fails this probe, rather than
  unconditionally marking it `"available"`. A Node with zero genuinely
  openable V4L2 devices correctly falls back to the existing
  `"v4l2-no-camera"`/`unavailable` sentinel -- exactly what this real
  reference Pi has right now (its only real camera is the CSI sensor,
  correctly owned by `picamera2`, not `v4l2`).
- Excluded (not merely marked unavailable) rather than listed alongside
  real cameras: these device nodes are permanently, structurally never
  going to become selectable cameras, and doctrine's own "debug internals"
  boundary argues against surfacing raw kernel pipeline-stage names like
  "Linux camera 11" in a real device picker.
- One disclosed, bounded residual: the per-path cache means a genuine
  camera that is only *transiently* busy at the exact moment of this
  provider's first-ever `cameras()` call could be under-cached as
  not-capture-capable for the rest of the process lifetime. Strictly
  better than the prior behavior (every path unconditionally "available"
  forever) and consistent with self-test's own already-accepted
  once-at-startup posture, but noted rather than hidden.
- **Not fixed, deliberately, as a disclosed out-of-scope item:**
  self-test's own once-at-startup, cached-forever posture (staleness). A
  live camera failure occurring *without* any Node restart (unlike v11's
  own actual scenario, which did include a power-cycle) would still read
  `self_test.camera_available: true` from Day-0 boot truth. Fixing this
  well means either re-running the bounded probe on every `/node/v1/
  health` call (a real behavior/latency trade-off against self-test's own
  explicit, deliberate "never again on a timer" design, chosen originally
  to keep health cheap) or restructuring how `/node/v1/health` mixes
  cached-at-startup and live fields -- a broader Camera Node health-model
  decision this milestone does not make. `self_test.camera_available` is
  not load-bearing for any safety decision today (the Host compatibility
  preflight never reads it; only the live per-camera-ID check gates
  Observation start), so this residual affects diagnostic honesty for a
  human/Doctor reader of a long-uptime Node, not release safety.
- **Not deployed to the live reference Pi.** The fix lives in this
  repository's source tree, proven against tests grounded in this exact
  Pi's real, live-captured device topology (not synthetic guesses); the
  Pi itself continues running its already-installed, pre-fix build. Per
  Section 19/28, deploying a Camera Node upgrade is out of this
  validation-only milestone's scope and would be an unnecessary mutation
  of a shared reference device.

## RTSP result

**UNAVAILABLE FOR ACCEPTANCE**, confirmed rather than assumed: a live
probe (`bash /dev/tcp` to port 554) against both the LAN gateway
(`192.168.1.1`) and the reference Pi (`192.168.1.112`) found nothing
listening; no other RTSP source is known to this environment. Consistent
with every prior camera-source milestone's own disclosed gap. No RTSP
setup/preview/monitoring/failure/reconnect exercise was possible tonight;
none was fabricated. Existing RTSP test coverage (setup validation,
credential redaction, ongoing-monitoring classification,
`test_rtsp_probe.py`, `test_ongoing_monitoring_failure_diagnostics.py`)
re-run clean this session (see Validation) but is unit/fixture-level, not
new live-hardware evidence.

## Local USB / V4L2 result

**UNAVAILABLE FOR ACCEPTANCE** for the Host-side `local_usb` Source
provider (`src/mockingbird/playback/local_camera_bridge.py`): no
`/dev/video*` device exists in this WSL sandbox, confirmed directly.
Distinct from, and not to be confused with, the Camera-Node-side
`V4L2CameraProvider` defect found and fixed above (a different code path,
`mockingbird_node.providers`, exercised against the reference Pi's own
device nodes, not the Host's). This gap is identical to the one Ongoing
Monitoring Failure Diagnostics v1 already disclosed and left open.

## Windows DirectShow result

**PARTIALLY VALIDATED.** Native Windows host reachable
(`powershell.exe` interop, Windows 10.0.19045); real `ffmpeg.exe`
present. Live evidence gathered tonight:

- `Get-PnpDevice -Class Camera,Image`: one known device, `EMEET SmartCam
  S600`, `Status: Unknown` (registered, not currently connected).
- `ffmpeg.exe -f dshow -list_devices true -i dummy`: 0 video devices, 2
  audio-only devices (`Microphone (2- Razer BlackShark V2 Pro)`,
  `Analogue 1 + 2 (3- Focusrite USB Audio)`) -- a genuinely empty-camera
  live state, not a fixture.
- Fed this **exact real captured output**, verbatim, into the real
  product parser, `parse_windows_dshow_video_devices()`
  (`src/mockingbird/playback/windows_camera_bridge.py:301`), run locally:
  correctly returns `[]` -- the two audio-only lines are correctly
  excluded (`_VIDEO_DEVICE_PATTERN` requires the literal `(video)`
  suffix, not `(audio)`). A real, live discovery-honesty proof, not merely
  a unit-test fixture string.
- No live capture/preview/monitoring was possible: the known camera is
  not physically connected tonight. This matches the exact residual
  Camera / Source Experience v1 already disclosed ("no local/USB camera
  device present in this sandbox or the connected Windows host").

## Setup / preview result

Not live-exercised for any provider tonight (no credentialed Camera Node
camera, no RTSP/USB/ONVIF endpoint, no connected Windows camera).
Verified instead at the code + already-green-test level: preview is
bounded (single frame, explicit timeout in every provider's capture
path), non-persisting (no MediaAsset/Visit created by any preview code
path), and reports unavailability honestly (`preview_available` computed,
never hardcoded, per Camera / Source Experience v1's own fix). Existing
preview-contract tests (`test_camera_setup.py`, `test_rtsp_probe.py`,
`test_external_url_preview.py`, `test_external_url_preview_save.py`,
`test_folder_import_preview.py`, `test_saved_preview_motion_evidence.py`)
all re-ran clean this session.

## Monitoring result

Not live-exercised (same hardware/credential gaps as Setup/preview).
`DurableMonitoringSupervisor`/`BoundedStderrDrain` code paths unchanged
this session; their own existing coverage (`test_durable_monitoring_
supervisor.py`, `test_ongoing_monitoring_failure_diagnostics.py`,
`test_stream_monitoring_contract.py`) re-ran clean.

## Failure diagnostics

Real, live failure evidence gathered tonight: the Camera Node pairing
conflict (`409 pairing_code_used`, see "Camera Node result," above) and
the v11 self-test diagnostic-truth defect (reproduced and fixed, see
above). RTSP/local-USB/Windows-DShow failure vocabulary
(`camera_setup_rtsp_*`, `camera_monitoring_local_usb_*`,
`camera_monitoring_windows_dshow_*`) is unchanged this session; it
remains exactly as evidence-backed (or honestly generic where unproven)
as Ongoing Monitoring Failure Diagnostics v1 left it -- no new specificity
invented tonight, consistent with Section 11's "unknown causes should
remain honest generic provider failure."

## Reconnect / recovery

Camera Node: real, live, clean bounded-interruption/recovery proof (see
"Camera Node result," above) -- healthy -> interrupted (service restart)
-> recovered, no duplicate Stream, no corrupted config, no lost
credential, no stale failure state, nothing to delete/recreate. Physical
unplug/replug of the CSI cable was not attempted (no hands-on physical
access to the reference Pi from this sandbox); Representative Daylight
Gate A Field Acceptance v11 already recorded a real physical
fault-and-reseat cycle historically, cited above, not re-performed
tonight. RTSP/local-USB/Windows-DShow/ONVIF: not exercisable, no hardware.

## Credential safety

Verified at the code level (no live credentialed traffic was captured
tonight to inspect, since no fresh pairing/preview ran):

- Camera Node bearer credential: minted once at pairing
  (`_PairingState.pair()`), persisted only as a SHA-256 digest
  (`credential_sha256`), compared via `hmac.compare_digest` -- the raw
  credential is never stored, logged, or re-returned after the one-time
  pair response.
- RTSP/URL-embedded credentials: `redact_credentials_in_text()`/
  `redact_url()` (`src/mockingbird/playback/rtsp_bridge.py:22,45`) scrub
  `scheme://user:pass@` wherever ffmpeg stderr might echo it back verbatim
  -- the one place raw subprocess output is read. `BoundedStderrDrain.
  latest_text()` always redacts before returning.
- No plaintext-at-rest camera credential policy change made or needed
  (none reproduced as a defect this session).
- Existing redaction tests (`test_rtsp_probe.py`'s
  `test_rtsp_setup_validation_never_leaks_credentials_in_response_or_logs`,
  `test_ongoing_monitoring_failure_diagnostics.py`'s
  `test_rtsp_ongoing_failure_never_leaks_credentials`, `test_support_
  bundle.py`) all re-ran clean this session.

## Capability reporting

Real sensor capability confirmed live: `rpicam-hello --list-cameras` on
the reference Pi reports `ov64a40 [9248x6944 10-bit RGGB]` with several
real supported modes (1920x1080 through 9248x6944). This independently
corroborates the local dev DB's own already-stored config for this exact
Node (`node_evidence_profile_id: "picamera2-warm-evidence-4624x3472"`,
`node_monitoring_profile_id: "picamera2-monitoring-1920x1440"` -- both
real modes from that same sensor's own real mode list). `PiCamera2Provider
._sensor_modes()` reads this directly from a live `Picamera2` instance's
`sensor_modes` attribute -- hardware-grounded, not guessed. No capability
mismatch was reproduced tonight; nothing to fix. No capability-UX redesign
attempted (out of scope regardless).

## Multi-source coexistence

**UNAVAILABLE FOR ACCEPTANCE.** Only one source was genuinely live
tonight (the reference Camera Node); Windows DirectShow's known camera is
disconnected, and no RTSP/USB/ONVIF device exists. A genuine two-live-
source concurrent exercise was not possible -- not fabricated.

## Product surfaces

Exercised at the API/protocol layer, matching what Doctor/Add-Camera/
Stream-detail/health surfaces are themselves built on: real `/node/v1/
health`, real compatibility preflight (both profiles), real `/node/v1/
pair` conflict response. Did not stand up a full local Host / click
through the Dashboard/Doctor/Add-Camera UI tonight: no pairing credential
existed to make a UI session materially more informative than the direct
API evidence already gathered, and Section 18 explicitly cautions against
reopening Whole-Product UI Closure absent a reproduced defect. Doctor's
own Camera Node check (`_gather_camera_node`/`_interpret_camera_node` in
`src/mockingbird/diagnostics/doctor.py`) reuses the identical health/
compatibility mechanics already exercised above; its own test coverage
(`test_doctor.py`, `test_doctor_cli.py`, `test_doctor_camera_node_
transport.py`) re-ran clean this session.

## Defects

**Found and fixed (1):** Camera Node `self_test.camera_available`
diagnostic-truth defect -- see "Camera Node diagnostic-truth reproducer"/
"fix," above. Bounded to `mockingbird_node.providers.V4L2CameraProvider`.

**Found, disclosed, deliberately not fixed (1):** self-test's
once-at-startup/cached-forever posture can independently make
`self_test.camera_available` stale for a long-uptime Node whose camera
fails without a restart -- see "Camera Node diagnostic fix," above, for
why this is out of bounded scope.

**No other new defects reproduced.** RTSP/local-USB/Windows-DShow gaps
found tonight are all hardware-availability limitations, already
disclosed by prior milestones, not new code defects.

## Validation

### Tier 1

Focused RED -> GREEN tests for the one production fix, all grounded in
this exact reference Pi's real device topology:

- `tests/test_camera_node.py::test_v4l2_enumeration_excludes_device_nodes_that_cannot_actually_open`
  (new) -- reproduces the defect directly: fed the Pi's own 6 real
  never-openable device paths (unicam + bcm2835-codec-decode/isp +
  rpi-hevc-dec), asserts only the `"v4l2-no-camera"` sentinel is returned.
- `tests/test_camera_node.py::test_v4l2_enumeration_still_reports_a_genuinely_openable_camera_available`
  (new) -- no-regression proof: a genuinely openable device among
  non-openable ones is still correctly reported available.
- `tests/test_camera_node.py::test_v4l2_enumeration_is_bounded_opaque_and_capture_releases_resources`
  (updated) -- pre-existing bounded/opaque/resource-release properties
  preserved; its `cv2.paths` assertion updated to reflect the new,
  legitimate per-candidate probe during enumeration.
- `tests/test_camera_node_boot_identity.py::test_self_test_not_fooled_by_non_capture_v4l2_device_nodes_when_real_camera_is_absent`
  (new) -- the end-to-end reproduction of v11's exact real shape: a real
  `V4L2CameraProvider` (not a fake) fed the Pi's own device topology,
  composed with a stub reporting no real camera (matching picamera2's
  correct behavior when the sensor is genuinely absent), through the real
  `run_startup_self_test()`. `camera_available` was `True` before the fix
  (RED, confirmed) and is `False` after it (GREEN, confirmed).

All 4 confirmed RED against the pre-fix code (`git`-tracked diff, not
`git stash` this time since the defect and fix were both authored in this
same session, so a plain before/after test run served the identical
verification purpose), then GREEN after the fix, in this session.

### Tier 2

Full affected-subsystem sweep, all passing, all this session:

```
tests/test_camera_node.py, test_camera_node_boot_identity.py,
test_camera_node_response_parsing.py, test_camera_node_real_process.py,
test_camera_node_capture_contention.py, test_node_compatibility.py,
test_node_compatibility_api.py, test_doctor.py, test_doctor_cli.py,
test_doctor_camera_node_transport.py, test_install_camera_node.py,
test_camera_node_packaging.py, test_camera_node_config_transport.py
  -> 359 passed, 0 failed

tests/test_rtsp_probe.py, test_camera_setup.py,
test_ongoing_monitoring_failure_diagnostics.py,
test_source_connection_contract.py, test_stream_monitoring_contract.py,
test_durable_monitoring_supervisor.py, test_stream_playback_contract.py,
test_onvif_client.py, test_support_bundle.py, test_camera_health.py,
test_camera_configuration_edit.py, test_camera_source_creation.py,
test_source_provider_configuration.py, test_cross_camera_association.py,
test_cross_camera_visit_association.py,
test_multi_camera_concurrent_runtime.py
  -> 372 passed, 11 xfailed (pre-existing), 0 failed
```

Total: **731 passed, 0 failed, 11 pre-existing xfailed.**

`ruff check` on both changed files: 0 new findings. `src/mockingbird_node/
providers.py` has 4 pre-existing `E701` findings, all in
`create_camera_provider()` (untouched by this fix, lines unchanged from
`git show HEAD:...`); `tests/test_camera_node.py` has 6 pre-existing
`E702` findings in unrelated pre-existing test bodies -- both counts
verified identical against the unmodified `HEAD` copy of each file.
`tests/test_camera_node_boot_identity.py`: 0 findings, clean.

### Tier 3 decision

**Not run -- documented, bounded blast radius, not ceremony.** The fix
touches only `src/mockingbird_node/providers.py` (the Camera Node
package). Directly verified zero import-time coupling in the direction
that would matter: `grep -rn "mockingbird_node" src/mockingbird/` finds
only comments/docstrings (module-path cross-references in prose), never
an actual `import`; `CameraNodeClient`
(`src/mockingbird/source_providers/camera_node.py`) is confirmed
stdlib-`http.client`-only. This is not incidental -- it is an already-
documented architectural invariant in this exact codebase:
`src/mockingbird/api/camera_node_transport.py:37-45` states outright,
"Duplicated (not imported) on purpose: `mockingbird_node` is a separate
[package] ... `src/mockingbird_node/` imports from the main `mockingbird`
package today [but not vice versa] ... not a shared import." The Host
process never executes a line of `mockingbird_node` code; it only ever
sees the Node over HTTP, and every Host-side test that depends on Node
behavior already mocks/fixtures that HTTP boundary independently (hence
Tier 2's `test_node_compatibility*.py` already covering the Host side of
this fully). A narrow Node-health truth fix, Tier 2 only, per Section 23's
own explicit allowance.

## Support classification table

| Path | Setup/discovery | Preview | Monitoring | Failure/recovery | Overall |
|---|---|---|---|---|---|
| Camera Node | VALIDATED (health, pairing-conflict honesty, compatibility preflight x2 profiles, real RTT batch) | STRUCTURALLY SUPPORTED (bounded/non-persisting by code + existing tests; no live frame captured -- no credential) | STRUCTURALLY SUPPORTED (unchanged; existing coverage only) | VALIDATED (real bounded service-restart recovery, clean) | **PARTIALLY VALIDATED** |
| RTSP | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | **UNAVAILABLE FOR ACCEPTANCE** |
| Local USB/V4L2 (Host) | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | **UNAVAILABLE FOR ACCEPTANCE** |
| Windows DirectShow | PARTIALLY VALIDATED (real live enumeration, real 0-device state, real product parser proven against it) | UNAVAILABLE FOR ACCEPTANCE (device disconnected) | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | **PARTIALLY VALIDATED** |
| ONVIF | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | UNAVAILABLE FOR ACCEPTANCE | **UNAVAILABLE FOR ACCEPTANCE** |
| Multi-source coexistence | -- | -- | -- | -- | **UNAVAILABLE FOR ACCEPTANCE** |

No STRUCTURALLY SUPPORTED result above is rounded up to VALIDATED.

## Lane G closure assessment

**No -- Lane G stays MATERIALLY CLOSED / VALIDATION REMAINS, not CLOSED.**
Real, meaningful progress happened: the reference Camera Node is proven
reachable, healthy, protocol-compatible (both profiles), clock-
calibratable, and recoverable from a bounded interruption for the first
time this milestone found record of (every prior session that reached
this point either found the Node unreachable or did not attempt this
depth); one real, previously-only-anecdotally-known diagnostic defect was
reproduced deterministically and fixed with full regression coverage.
But Lane G's own specifically-named remaining gap -- proving actual live
video decode/preview end-to-end for *any* real camera -- is **still
open** for every path tonight: Camera Node lacked a usable pairing
credential, and every non-Camera-Node hardware candidate remained
physically disconnected or absent. Per Section 25, "do not falsely close
based on unit tests alone" and "do not require unavailable optional
hardware" -- but the Camera Node *was* available, and its own live
image-capture path specifically remains unproven, which is exactly the
kind of remaining uncertainty Section 25 asks not to round past.

## Remaining release-critical dependencies

One concrete, precisely-scoped Lane G gap remains: **prove live
authenticated video capture/preview against the reference Camera Node
end to end** (obtain or mint a usable pairing credential for it, then
exercise `/node/v1/cameras`, snapshot, and a bounded preview through the
real product path). Everything else Lane G still lacks (RTSP/local-USB/
Windows-DShow/ONVIF live hardware acceptance) remains a hardware-
availability gap, not a release-blocking code defect, and stays exactly as
open as every prior session already, honestly, left it.

## Decision

**B** -- real, verified, evidence-backed progress and one genuine
defect reproduced and fixed with clean regression coverage, but the
milestone's own core named validation gap (live video capture/preview
proof) is not closed for any path tonight, for disclosed hardware/
credential-availability reasons rather than a code defect. Not force-
closed to A.
