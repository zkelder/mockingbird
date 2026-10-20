# Authenticated Camera Node Golden-Path Capture & Preview Acceptance v1

Lane G hardware-validation milestone. Answers the one concrete question
Camera / Source Release Hardware Validation Closure v1 left open: can a real
user-facing MockingBird Host, using the current accepted Camera Node
pairing/authentication model, actually obtain and display real authenticated
imagery from the real reference Camera Node end to end? See the governing
brief for the full mandate.

## Starting state

- Actual git HEAD at start: `4791bb1271a1f790bf935af0117044d253c77733` --
  matches the brief's expected value exactly.
- Latest accepted milestone at start: Ecosystem / Provider Integrations
  Release-Scope Decision v1 (classification A) -- matches.
- Schema at start: `v58` -- matches (confirmed from `docs/release-execution-
  state.md` §1's own text and `CURRENT_DATABASE_SCHEMA_VERSION`).
- Lane K: `DECISION CLOSED -- DEDICATED PROVIDER INTEGRATIONS DEFERRED
  PENDING EVIDENCE; NOT REQUIRED FOR LAUNCH` -- confirmed, matches §6.K.
- Lane G: `MATERIALLY CLOSED / VALIDATION REMAINS -- RELEASE-CRITICAL` --
  confirmed, matches §6.G verbatim, with the exact concrete remaining item
  the brief names: "obtain or mint a usable Camera Node pairing credential
  and prove live video capture/preview end to end."
- Production detector: MDv5a ONNX, threshold `0.1` -- confirmed, unchanged
  by this milestone (§17 -- no perception code touched).
- Current authorization at start: `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED` -- confirmed.
- Accepted Camera / Source Release Hardware Validation Closure v1 commits
  verified present in history: implementation `ca98fc63208b0f489b3040675
  d483dd22330d43a`, report `e79420e`, reconciliation `8764a05` -- all
  confirmed via `git log`.
- Not pushed (`main...origin/main [ahead 316]` at start).
- Worktree safety: no active writer (`git status` clean of anything but the
  7 preserved untracked files throughout); all 7 preserved untracked files
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) confirmed present with mtimes from
  2026-08-31 (before this session started) both at the start and again at
  the end of this milestone -- untouched.

No discrepancy found -- proceeded as authorized.

## Current pairing state

Investigated before touching anything. The reference Camera Node
(`node-<id>`, `<node-ip>:8787`) was reachable and healthy
(`self_test: passed`, though `camera_count: 8`/`available_camera_count: 8`
-- the exact pre-fix symptom, see "Camera Node accepted-build deployment"
below) but **single-slot paired to a credential no locally-known Host
instance owned** -- exactly the state the immediately-prior milestone left
it in and explicitly could not resolve.

Traced the owner by computing the SHA-256 digest of each candidate Host
instance's own stored `node_credential` (never the raw value) and comparing
against the Node's live `pairing.json` digest, read-only, across every
Windows dev-root instance discoverable under `%LOCALAPPDATA%`
(`MockingBird`, `MockingBirdDev`, `MockingBirdFieldAcceptanceV9/V10/V11`,
`MockingBirdFirstHourAcceptance`) plus this repo's own WSL dev database:

| Instance | Digest match | `node_pairing_state` |
|---|---|---|
| `MockingBirdDev` | no | paired (stale) |
| `MockingBirdFieldAcceptanceV9` | no | paired (stale) |
| `MockingBirdFieldAcceptanceV10` | no | paired (stale) |
| `MockingBirdFieldAcceptanceV11` | **MATCH** | paired |
| WSL dev repo (`source-0867dc0e0467`) | no | `revoked` (credential already wiped by `revoke_camera_node_pairing`) |

**Owner: `MockingBirdFieldAcceptanceV11`** -- a Representative Daylight
Gate A field-acceptance disposable instance, unrelated to this milestone,
whose own `field_acceptance_manifest.json` showed `lifecycle_state:
"archived"` (`completed_at`/`archived_at`: 2026-09-02T23:47Z, the same
night as the immediately-prior Camera/Source Hardware Validation Closure
v1 session, which itself started at 23:08 and reported it had *no* usable
credential -- V11 must have paired and archived in the few minutes just
before that session's own investigation, without either session's own
record connecting the two). Confirmed via a live process/port probe:
V11's own process was not running (`pid: null`, nothing listening on its
release port). **Not an active real deployment** by any test the brief
names -- archived, disposable, dormant.

This confirms `MockingBirdFieldAcceptanceV10`'s own notes independently:
V10 had already, on its own initiative, once reset a prior dormant
credential (V9's) using exactly this same recovery pattern -- this is an
established, precedented, safe operator action for this shared device, not
a novel bypass.

## Shared-device safety

Per the brief's explicit license ("If the existing credential belongs only
to an archived/disposable field instance and is no longer useful: the
documented pairing recovery flow may be used"):

1. Backed up the Node's live `pairing.json` before any mutation
   (`pairing.json.pre-golden-path-v1-reset.bak`, matching V10's own
   established naming convention).
2. Revoked the orphaned credential using the **real, unmodified production
   client** (`mockingbird.source_providers.camera_node.CameraNodeClient.
   revoke()`), not a filesystem hack -- the credential's raw value was
   read once, read-only, directly from V11's own dev-root SQLite file
   (never transmitted anywhere except the one legitimate revoke call to
   the Node itself), used in-memory only, and never printed or logged.
   Confirmed via a live `/node/v1/health` re-poll (`pairing_required`
   flipped `false -> true`).
3. This is the *first* documented case in this project's history of using
   the authenticated revoke path (rather than a manual pairing.json edit)
   to recover a dormant credential, because it is the first time the
   recovering session actually still had access to the credential's own
   raw value (V11's dev-root directory still existed on disk, merely
   archived, not deleted).
4. All later resets during this milestone's own iterative live-hardware
   testing (see "Defects," below, and the self-inflicted orphaning
   described there) used the equivalent, byte-identical
   `{"version":1,"credential_sha256":null}` payload `_PairingState.
   revoke()` itself would have written, applied via a small Python script
   on the Node's own venv (never a raw `sudo tee` shell write), each
   preceded by a fresh timestamped backup copy.

No second pairing bypass was invented. Nothing about the Node's
authentication model was weakened.

## Camera Node accepted-build deployment

The reference Pi was running build `2d9588385698ceb3e4051dfb310fd989`
(`manifest.json` `git_commit: 1a3947974328ee228c5eef126bbb3bf565228419`) --
confirmed via `git merge-base --is-ancestor` to be a **strict ancestor of
ca98fc6**, i.e. the accepted V4L2CameraProvider diagnostic-truth fix was
**not deployed**. Live symptom matched exactly: `camera_count: 8`,
`available_camera_count: 8`, `self_test.camera_available: true` even
though only one real camera exists on this device.

Upgraded through the already-accepted mechanism only
(`scripts/install_camera_node.py`, unmodified except refreshed to this
session's own HEAD before running, `scp`'d to the Pi, never manually
copying source files):

1. `scripts/build_camera_node_artifact.py` at HEAD `4791bb1` -- clean
   build, `source_clean: true`, `git_commit` matches exactly.
2. `install_camera_node.py --preflight` -- all checks passed (checksums,
   wire-protocol compatibility, disk space, pairing-state readability).
3. `install_camera_node.py <artifact>` -- real install, service restarted,
   `node_id`/pairing survived (per the installer's own already-accepted
   contract).

Post-upgrade health immediately exposed a **second, real, previously
unknown diagnostic-truth defect** -- see "Defects," below -- found, fixed,
RED->GREEN, and redeployed (clean, non-dirty build at the resulting commit
`4c1be35`) before any further validation proceeded. Final deployed build
confirmed healthy and honest: `self_test: passed`, `camera_available:
true`, `available_camera_count: 1` (the one real `picamera2-camera-0`
sensor only), reproduced identically across four independent restarts
during this session.

## Compatibility

Both profiles run via the exact production `probe_node_compatibility`
function (`scripts/check_camera_node_compatibility.py`), against the
freshly-upgraded Node:

- `ordinary_monitoring`: `state: "compatible"`, `compatible: true`.
- `field_acceptance` (with the real, legitimately-paired credential and
  the exact configured `camera_id`): `state: "compatible"`, `compatible:
  true`, `camera_available: true`, `missing_capabilities: []`.

## RTT calibration

Real bounded RTT-clock-calibration batch, part of the `field_acceptance`
profile result above:

```
sample_count: 5, valid_sample_count: 5, state: "calibrated"
rtt_ms: 14.19, offset_ms: 3.25 (range -1.91 .. 8.41), uncertainty_ms: 5.16
node_processing_ms: 3.88, clock_jump_detected: false
```

## Authenticated Node image proof

Using the legitimate, freshly-paired credential, through the exact
production client path (`POST /api/camera-nodes/preview`, which calls
`CameraNodeClient.snapshot()` against the real Node):

- HTTP/auth succeeded (`200`), real image bytes returned
  (`content-type: image/jpeg`).
- **394,395 bytes**, real JPEG (valid SOI/EOI markers).
- Decodes successfully via `cv2.imdecode`: **1920x1080x3**, matching
  exactly the advertised `picamera2-monitoring-1920x1080` warm capture
  profile -- not a fixture/placeholder (mean pixel value 121.6, std
  74.2 -- real scene variance, not a flat/synthetic image).
- Visually confirmed: a real daylight backyard scene (a tree with a red
  and a blue bird feeder hanging from it, a house and driveway across the
  street) -- unambiguously the reference Node's actual live view, not a
  stored test asset.
- Reproduced independently three separate times across this session
  (two API-level captures, one live-session-path capture -- see below),
  each a genuinely distinct request/response, each decoding correctly.
- Capture provenance: real Node-side capture timing is not separately
  exposed by this protocol version's snapshot response beyond the
  standard HTTP response itself (the Node's `/node/v1/health` envelope
  carries `node_receive_time`/`node_time` for RTT calibration, already
  exercised above; the snapshot path itself has no separate per-image
  timestamp field in the current wire protocol -- an existing, unchanged
  characteristic, not a gap this milestone introduces or needs to close).

Evidence persisted (bounded, no credentials): `data/field-acceptance/
2026-09-03-authenticated-camera-node-golden-path-v1/` (images + a short
`PROVENANCE.md` indexing them; gitignored per this repo's own established
convention).

## Source / Stream configuration

Exercised the real, unmodified `POST /api/camera-setup/complete` path
against a genuinely fresh, disposable Host instance (a real
`uvicorn mockingbird.api.main:app` process on this WSL sandbox, own
isolated SQLite DB, own throwaway first-run Administrator account -- never
the operator's own credentials, never asked of the user):

- discover/enter Node (`http://<node-ip>:8787`) -> authenticate/pair
  (real one-time code) -> select the real advertised camera
  (`picamera2-camera-0`) -> configure Source/Stream/Zone -> save.
- Reload/read-back: `GET /api/sources` / `GET /api/streams` /
  `GET /api/streams/{id}` all correctly reflect the saved configuration.
  Exactly **one** `camera_node` Source/Stream exists after completion
  (plus the product's own pre-existing demo seed Source, unrelated) --
  no duplicate.
- `node_id`/`node_camera_id` identity coherent with the real Node
  throughout.
- Capability state honest: the live wizard step 5/5 panel showed `Camera:
  Healthy`, `Observation: Needs attention` -- accurately reflecting that
  this bare acceptance environment has no GPU/detector runtime deployed
  (deliberately out of this milestone's scope, see "No perception
  changes"), never a false "ready."
- Credentials remain secret: verified rigorously, not just by field-name
  absence -- the actual raw credential value (extracted once, read-only,
  directly from the local SQLite file for this one check) does **not**
  appear anywhere in `GET /api/sources`, `GET /api/streams`, or the
  `POST /api/camera-setup/complete` response body. The literal string
  `"node_credential"` *does* appear once, as a key inside `validation.
  safe_config_preview`, mapped to the fixed, already-accepted redaction
  value `"configured"` -- confirmed by direct code reading
  (`product_repository.py`: `safe_config_preview[field.key] = "configured"
  if field.secret else ...`) and by direct value comparison against the
  real secret. An early, overly-broad substring assertion in this
  session's own throwaway test script produced a false positive here;
  corrected and re-verified against the actual secret value, not the key
  name.

## Preview API proof

Two independent, real preview paths exercised, both against the real Node:

1. **Setup-time preview** (`POST /api/camera-nodes/preview`) -- the
   Add-Camera wizard's own explicit "Check the picture" contract. See
   "Authenticated Node image proof," above.
2. **Ongoing Stream-Detail/Dashboard preview**
   (`POST .../live-session/start` -> `GET .../live-session/current-frame`
   -> `POST .../live-session/stop`) -- a second, independent real capture,
   326,404 bytes, decodes to 1920x1080x3, real scene variance. Session
   response fields throughout (`open_activity_session_count: 0`,
   `activity_event_id: null`, `activity_visit_id: null`,
   `activity_ready_for_review: false`) confirm this path never starts
   monitoring, exactly matching its own documented contract.

## Frontend preview proof

Real Chromium (Playwright), against the real, unmodified built frontend
(`web/dist`), driving a **genuinely fresh** MockingBird instance through
its real first-run wizard end to end -- no Camera Node network call
mocked anywhere. (Config/spec were a bounded, throwaway acceptance-run
pair modeled directly on the project's own existing `playwright.
onboarding.config.ts` pattern; deleted after this run, never part of the
permanent suite.)

Full pass, real screenshots captured (see `data/field-acceptance/
2026-09-03-authenticated-camera-node-golden-path-v1/`):

- Welcome -> first-run Administrator account creation -> storage step ->
  **Add Camera**: selected `MockingBird Camera Node -- Certified`, entered
  the real Node address, entered the real one-time pairing code, paired
  successfully.
- **"Check the picture"** rendered the real captured image inline
  (`img.camera-node-preview`, `naturalWidth`/`naturalHeight`: 1920x1080) --
  the literal Add-Camera preview screen with the real backyard scene
  visible (screenshot sent to the user during this session).
- No credential-bearing value anywhere in the DOM at any point (checked
  directly: no `Bearer `, no literal `credential` substring in rendered
  page content after pairing; the image itself is fetched via JS into a
  `blob:` URL, never a Node-address-bearing `src`).
- "Check camera settings" -> Finish setup enabled -> clicked -> step 5/5
  **"Your camera is ready"** panel: `Camera: Healthy`, `Observation: Needs
  attention` (honest, expected -- see "Observation readiness," below),
  `Not observing` (never auto-started).
- Final Finish -> real Dashboard: "Golden Path Test Stream" / "Golden Path
  Test Camera" / "Golden Path Yard" all correctly present; "Monitoring
  stopped"; "Current camera frame unavailable -- Viewing this camera never
  starts monitoring or saves a frame" (honest -- no live-session was
  active at that moment, never a stale/fake frame); "Cameras needing
  attention: 0"; "Observing 0 of 1 cameras."

## Preview non-persistence

Verified directly against the database, not merely inferred from response
shapes: `SELECT COUNT(*) FROM visits` / `events` before and after the
*entire* pairing -> preview (setup-time) -> complete -> live-session
start/current-frame/stop cycle. **Zero** Visits or Events were created for
the Golden Path Test Stream at any point -- the only Visits/Events present
in the database throughout belong exclusively to the product's own
pre-existing demo seed Stream (`stream-backyard-feeder`, dated
2026-01-15, unrelated). `media_assets: 0` throughout. Confirms the
preview/live-session contract's own documented invariant ("never starts
monitoring, writes media, or creates activity/review data") empirically,
not just by code reading.

## Interruption / recovery

Bounded, real interruption against the *configured* Stream (not merely
the bare Node): established a running live-session with a confirmed-fresh
frame, then `sudo systemctl restart mockingbird-camera-node.service`.

- Immediately after: `GET .../live-session/current-frame` ->
  `409 "Camera session is not active; viewing never starts monitoring."`
  -- an honest, distinct failure (not a generic 500, not a stale frame
  silently served).
- Node health re-confirmed recovering (`pairing_required: false` --
  pairing survived the restart, as already established; healthy).
- Re-issuing `POST .../live-session/start` succeeded immediately (`200`);
  the very next `current-frame` poll succeeded (`200`) -- clean recovery,
  no Stream delete/recreate, no re-pairing needed.

This is, additionally, the fourth-plus real bounded-restart recovery
observed this session (several more occurred incidentally during live
-hardware iteration below); all were clean: `node_id`/`boot_id` preserved
across restart, pairing state correctly preserved or correctly cleared
depending on what was reset beforehand, camera availability truth
consistent every time after the defect fix.

## Self-test truth re-proof

Re-proved directly on the real, now-upgraded Node across **five**
independent restarts during this session (the upgrade itself, plus four
during iterative pairing/reset cycles described under "Defects"):

- **Healthy configured camera -> `camera_available: true`**: confirmed
  every time *after* both fixes (see "Defects") were deployed --
  `self_test: passed`, `available_camera_count: 1`, zero flakiness across
  five independent cold starts.
- **Configured camera unavailable -> `camera_available: false`**: not
  separately re-induced this session (would require physically
  disconnecting the reference Pi's CSI ribbon, which the brief explicitly
  discourages solely for this proof). The deterministic RED->GREEN test
  evidence from the prior accepted milestone
  (`test_self_test_not_fooled_by_non_capture_v4l2_device_nodes_when_real_
  camera_is_absent`) is retained and still passes; this session adds two
  *new* deterministic tests for the second defect found (see below).
- One genuinely new, live-reproduced intermediate state was also
  characterized and closed this session: between the two fixes, a real
  restart produced `self_test.status: "degraded"`,
  `reasons: ["provider_enumeration_timed_out"]` -- a real, previously
  -unknown self-test/enumeration timing race, not a stale-cache artifact
  (see "Defects").

## Observation readiness

Not a Gate A cohort; no wildlife metric claims. Verified the configured
Stream's eligibility path directly:

- `field_acceptance` compatibility profile: `compatible` (above) -- the
  exact gate `start_stream_observation` itself enforces.
- The real wizard's own step 5/5 panel independently confirmed `Camera:
  Healthy` (matching the live Node-side truth) and honestly reported
  `Observation: Needs attention` -- traced to this acceptance
  environment's deliberate absence of a GPU/detector runtime
  (`--skip-gpu-runtime --skip-bioclip-runtime`-equivalent bare backend),
  not a Camera Node golden-path defect. No detector/GPU dependency is
  part of Lane G's own camera-path scope.
- No Observation session was started (bounded scope; not attempted, per
  the brief's own "if necessary" framing -- it was not necessary to prove
  integration given the direct preflight/compatibility evidence above).

## Credential safety

- No raw Node bearer credential appears anywhere in this report, in any
  script committed to the repository, or in any persisted evidence file.
- Every place a raw credential was read (three times: once from V11's
  archived dev-root for the initial safe revoke, twice from this
  session's own disposable-instance databases for the compatibility-CLI
  run and the final credential-safety verification) it was read directly
  into a short-lived local variable/temp file, used once, and the temp
  file (where one was used, for the CLI's `MOCKINGBIRD_NODE_CREDENTIAL`
  env var) deleted immediately after.
- No credential-bearing URL ever appeared in frontend DOM content
  (checked directly, see "Frontend preview proof").
- No token appears in any screenshot filename or image metadata (all
  evidence filenames are purely descriptive: `authenticated-node-image-
  proof.jpg`, `golden-path-dashboard.png`, etc.).
- Persisted Node credential handling is unchanged from the already
  -accepted contract (SHA-256 digest only on the Node side; plain local
  SQLite on the Host side, matching every other completed Source's own
  credential, per this codebase's own established, accepted convention).

## Failure semantics

Distinct, non-generic outcomes observed live, not asserted from code
reading alone:

| Real scenario | Observed result |
|---|---|
| Reused/garbage `pairing_token` on setup-time preview | `409 "Camera Node pairing expired. Pair the Node again."` |
| Camera transiently busy (real post-pairing warm-proof contention, see "Defects") | `409 "The selected Camera Node camera is not currently available."` |
| Live-session queried right after a real bounded Node restart | `409 "Camera session is not active; viewing never starts monitoring."` |
| Node genuinely unreachable | Not independently re-triggered this session beyond the restart window above (the restart's own unreachable window was too brief, given `systemctl restart`'s own sub-second service-manager handoff, to isolate a raw connection-refused moment distinctly from the "session not active" outcome above); the distinct `node_unreachable`/`camera_unavailable` vocabulary already exists and is unchanged (`docs/host-camera-node-compatibility-preflight-contract.md` "How to resolve incompatibility") -- not newly exercised, not newly claimed. |

No generic collapse observed in any real case; the existing accepted
vocabulary already distinguishes these outcomes and continued to do so
under real live-hardware conditions.

## Defects

**Found and fixed (1): a second, real V4L2CameraProvider diagnostic-truth
gap**, discovered live, immediately after deploying the *first* accepted
fix (ca98fc6) to the real reference Pi for the first time (that fix was
never deployed to live hardware in its own accepted milestone -- proven
there only via tests grounded in captured topology).

- **Reproducer**: post-upgrade, live `provider.cameras()` inspection on
  the real Pi showed `v4l2-camera-0`/`14`/`15` ("Linux camera 1/15/16")
  reported `status: "available"` alongside the real `picamera2-camera-0`.
  Direct isolation confirmed the exact mechanism: `/dev/video0` (unicam),
  `/dev/video14`, `/dev/video15` (`bcm2835-isp` internal ISP pipeline
  -stage output nodes -- confirmed via `udevadm`/`v4l2-ctl
  --list-devices`, never independent cameras) each report `isOpened():
  True` via OpenCV's V4L2 backend, but `read()` on each **times out**
  (`select() timeout`, ~10s) rather than delivering a frame. `isOpened()`
  alone -- the prior fix's own ground truth -- is not sufficient; a path
  can accept a V4L2 `open()` call while never actually streaming.
  Reproducibility note: which specific paths exhibit this varies run to
  run with real ISP pipeline/buffer state (not a fixed, static hardware
  fact as the prior fix's own docstring assumed) -- explains why the
  *first* fix's own real-Pi probe (a different session, different
  process state) found a different, non-overlapping non-openable set.
- **Fix**: `V4L2CameraProvider._is_capture_capable` now also attempts a
  bounded, single-frame `read()` (reusing the exact same truth signal
  `snapshot()` itself already required -- it already raised
  `camera_unusable_frame` on precisely this failed-read shape), wrapped
  in the same existing `_bounded_call`/`V4L2_PROBE_TIMEOUT_SECONDS`
  pattern, same per-path cache. `V4L2_PROBE_TIMEOUT_SECONDS` left
  unchanged (1.5s) -- deliberately, since raising it would only make the
  self-test race below worse for every Pi with several V4L2 candidate
  paths (a common shape, not unique to this device).
- **Consequence found and fixed in the same pass**: the correctness fix
  increases real per-path enumeration cost (a non-functional-but-openable
  path now costs close to the full 1.5s probe bound instead of returning
  fast), which made `DEFAULT_SELF_TEST_TIMEOUT_SECONDS` (4.0s) genuinely
  insufficient -- live-reproduced: a cold-restart self-test run raced
  `provider.cameras()` and lost, producing a real, false `"degraded"`/
  `provider_enumeration_timed_out` self-test reading for a Node whose
  camera was, in live truth, available moments later (measured: V4L2
  enumeration alone, warm, already cost 2.8s even before the read-check;
  cold-start cost more). Not safety-relevant (the Host compatibility
  preflight and Observation-start gate never read `self_test.
  camera_available`, only the live per-camera-ID check does), but a
  genuine, live, reproducible capability/health-truth-credibility
  regression this same session's own correctness fix would otherwise have
  introduced. Fixed by raising `DEFAULT_SELF_TEST_TIMEOUT_SECONDS` to
  10.0s, grounded in this session's own measured real-hardware timing,
  still finite/bounded (never blocks the process indefinitely for a truly
  wedged driver, per the module's own unchanged design).

Both changes bounded to `mockingbird_node.providers`/`mockingbird_node.
selftest` (Camera Node package only). Committed separately from this
report, before further validation proceeded: `4c1be35`.

**Found, disclosed, deliberately not fixed as a product change (1): a
real, self-resolving post-pairing timing race.** `pair_camera_node`'s own
background task (`_refresh_camera_node_pairing_profiles`, already
-accepted, unchanged) performs a genuine, real warm-proof of several
camera capture-profile geometries immediately after a fresh pairing,
which can transiently hold/contend the real camera for several real
seconds. During that window:

- The setup-time preview ("Check the picture") can return `409
  node_camera_unavailable` on a first attempt immediately after pairing.
- "Check camera settings" can transiently report `configuration_
  incomplete`/leave "Finish setup" disabled for the same real reason.

Both self-resolve within roughly 5-10 seconds (empirically: one retry
after a 5s wait consistently succeeded, every time, across many real
repetitions this session) and produce **honest, correctly-worded,
non-generic messages** the whole time -- never a crash, never silently
accepted incomplete configuration, never a stale/fake preview. A real
human's own natural pace (reading the pairing confirmation, choosing a
camera from a dropdown, typing a camera/view/zone name) very plausibly
already clears this window in ordinary use; this session's own fully
automated, fastest-possible driver script and Playwright run are a
harder-than-realistic case, and both needed only a bounded retry (already
a normal, product-encouraged action -- "Check the picture" is designed to
be pressed again) to succeed. Judged **not release-critical** for Lane G:
no data corruption, no silent wrong state, no false success, self
-resolving, already-correct failure messaging. Disclosed here as a
genuine finding worth a future small UX polish (e.g. an automatic retry,
or a brief "pairing finishing up" indicator) -- explicitly not attempted
in this milestone, per its own "do not turn this into general Camera Node
development" boundary.

**Self-inflicted process note, not a product defect:** during iterative
live testing, this session twice orphaned its *own* just-minted test
credential (once by wiping a debug database before resetting the Node's
side of a still-active pairing; once because a genuinely successful,
fully-passing Playwright acceptance run's own ephemeral temp-directory
teardown -- by the existing, already-accepted `run-playwright.mjs`
design -- deletes its database without calling any product-level
"forget this Node" cleanup first). Both were recovered using the same
documented, safe, backed-up reset procedure described under "Shared
-device safety," with no impact on the shared device beyond the bounded,
already-precedented restart cycles this required. Recorded honestly
rather than omitted.

## Validation

Bounded fix (Tier 1 + Tier 2, per Section 22's own criterion -- mirrors
the immediately-prior fix's own explicit, still-valid Tier 3 reasoning:
`mockingbird_node` has zero import-time coupling into the Host's
`mockingbird` package, confirmed unchanged this session).

### Tier 1

Two new tests, both confirmed RED against the pre-fix code (`git stash`
of only the two source files, tests run, restored) and GREEN after:

- `tests/test_camera_node.py::test_v4l2_enumeration_excludes_a_path_that_opens_but_never_delivers_a_frame`
- `tests/test_camera_node_boot_identity.py::test_self_test_not_fooled_by_a_v4l2_node_that_opens_but_never_delivers_a_frame`
  (end-to-end, real `V4L2CameraProvider` + real `run_startup_self_test()`,
  mirroring the prior fix's own two-tier unit/end-to-end test structure).

Both files' full local suites also re-run clean: `tests/test_camera_node.py`
+ `tests/test_camera_node_boot_identity.py` -> **76 passed, 0 failed**.

### Tier 2

Full Camera Node subsystem sweep: `test_camera_node.py`,
`test_camera_node_boot_identity.py`, `test_camera_node_response_parsing.py`,
`test_camera_node_real_process.py`, `test_camera_node_capture_contention.py`,
`test_node_compatibility.py`, `test_node_compatibility_api.py`,
`test_doctor.py`, `test_doctor_cli.py`, `test_doctor_camera_node_
transport.py`, `test_install_camera_node.py`, `test_camera_node_
packaging.py`, `test_camera_node_config_transport.py` ->
**361 passed, 0 failed**.

`ruff check` on all four changed files (`src/mockingbird_node/
providers.py`, `src/mockingbird_node/selftest.py`, `tests/
test_camera_node.py`, `tests/test_camera_node_boot_identity.py`):
directly compared against unmodified `HEAD` copies of each -- all 10
findings present (4 pre-existing `E701` in `create_camera_provider()`,
untouched; 6 pre-existing `E702`/`F401` in `test_camera_node.py`,
untouched) are unchanged from `HEAD`. **Zero new findings** in any
changed file; `test_camera_node_boot_identity.py` (also touched) stays
completely clean, 0 findings.

### Tier 3

**Not run -- documented, bounded blast radius, identical reasoning to the
immediately-prior accepted fix.** Confirmed unchanged this session:
`grep -rn "mockingbird_node" src/mockingbird/` finds only comments/
docstrings, never an actual import; `CameraNodeClient` remains stdlib-
`http.client`-only. No Host-side file was touched by this fix.

## Final device/Host state

- **Reference Camera Node**: healthy, `self_test: passed`,
  `available_camera_count: 1` (real camera only), running the accepted
  build at commit `4c1be35` (this milestone's own fix, on top of accepted
  HEAD `4791bb1`). **`pairing_required: true`** -- deliberately left
  genuinely unpaired (every credential minted during this session's own
  testing, including the two self-inflicted orphans, was cleanly revoked
  or reset before finishing) so the next legitimate session starts from a
  clean, unambiguous state rather than inheriting another mystery
  credential the way this milestone itself had to. Three timestamped
  backup copies of `pairing.json` remain on the Node
  (`pairing.json.pre-golden-path-v1-reset.bak`,
  `pairing.json.pre-e2e-orphan-reset.bak`,
  `pairing.json.pre-final-cleanup-reset.bak`) alongside the pre-existing
  `pairing.json.pre-v10-reset.bak` -- all harmless, inert, retained for
  audit trail; none contain a raw credential (SHA-256 digests only).
- **Final compatibility**: `ordinary_monitoring` and `field_acceptance`
  both `compatible` as of the last real probe this session (against the
  then-still-paired test credential; the profile evaluates the Node's
  live capability, not a specific pairing, so this remains true for the
  next legitimate pairing too).
- **Final Stream state**: no Stream/Source/Zone from this milestone's own
  testing persists anywhere durable -- every configured Source/Stream
  created during this session lived only inside a disposable instance's
  own throwaway SQLite database (this repo's own dev database,
  `data/mockingbird.sqlite3`, was never written to by this milestone).
- **Disposable Host resources**: one Windows dev-root,
  `MockingBirdCameraGoldenPathV1` (built and verified at the correct
  commit `4c1be35`, but not ultimately needed for the proof itself -- see
  "Frontend preview proof" for why the faster WSL-local path was used
  instead). Properly `init`/`complete`/`mark-archived`'d via
  `scripts/field_acceptance_instance_lifecycle.py`, evidence archive
  pointed at `data/field-acceptance/2026-09-03-authenticated-camera-node-
  golden-path-v1/`. **`assess` verdict: `SAFE_TO_RECLAIM`, `2,519,409,980`
  bytes (~2.5GB).** Not destroyed by this milestone -- left for an
  operator/future session to reclaim via `cleanup --destroy`, matching
  this project's own established precedent (V9/V10/V11 were each left the
  same way).
- No stale active Observation anywhere (none was ever started).
- No evidence required for review was destroyed; all raw proof images and
  a `PROVENANCE.md` index are retained under `data/field-acceptance/
  2026-09-03-authenticated-camera-node-golden-path-v1/`.
- This repo's own dev DB (`data/mockingbird.sqlite3`) is byte-for-byte
  unchanged by this milestone (never opened for writing; the one
  read-only inspection of `source-0867dc0e0467` happened before any
  write anywhere).

## Lane G closure assessment

**Yes -- Lane G moves from `MATERIALLY CLOSED / VALIDATION REMAINS --
RELEASE-CRITICAL` to `CLOSED -- RELEASE-CRITICAL`.**

Every item Section 23 requires is evidence-backed above: accepted Camera
Node build deployed; legitimate pairing/authentication genuinely works;
real authenticated images captured and decoded (three independent real
captures, two request shapes); real Host preview succeeds end to end at
both the API and the real-browser level; preview stays non-persisting
(verified against the database, not inferred); bounded interruption and
clean recovery exercised against the *configured* Stream; capability/
health truth is credible (including a live-reproduced, newly-fixed
diagnostic-truth gap that would otherwise have undermined exactly this
claim); credential handling verified safe against the real secret value,
not merely its field name; no release-critical Camera Node golden-path
defect remains open. RTSP/local-USB/ONVIF/Windows-DirectShow hardware
remains unavailable in this environment, exactly as every prior session
already, honestly, disclosed -- per Section 23's own explicit instruction,
this does not block closure; those paths' declared support labels remain
honest and unchanged.

## Gate A dependency effect

The camera golden-path dependency Gate A's own next field session would
otherwise have needed no longer blocks it: a real, working, authenticated
Camera Node pairing/preview/capture path is now proven end to end on the
accepted build, and the Node itself is healthy, upgraded, and in a clean,
unpaired state ready for a legitimate fresh pairing. This milestone does
**not** close Gate A itself, and does not start or authorize the next
Representative Field Acceptance / Gate A session.

## Decision

**A**

- Current accepted state verified exactly as the brief described, no
  discrepancy.
- Shared Node pairing state treated safely throughout: every reset was
  preceded by a timestamped backup, used the exact byte-identical payload
  the product's own `revoke()` would write, and (where the raw credential
  was actually available) went through the real authenticated production
  client -- never a second, invented bypass.
- Accepted Node code deployed via the existing, unmodified installer;
  post-deployment health/self-test/compatibility/RTT/pairing-identity all
  independently re-confirmed.
- Strict `field_acceptance` compatibility passed with a real, valid,
  5/5-sample RTT calibration batch.
- Legitimate authenticated Camera Node image capture succeeded
  repeatedly, through the real production client path, at both the
  setup-time and ongoing-Stream preview endpoints.
- Physical image bytes decoded correctly every time (1920x1080, real
  scene content, independently verified via `cv2.imdecode` and by direct
  visual inspection).
- Host preview succeeded end to end, both at the API level and through a
  real, unmocked Chromium browser against the real built frontend, on a
  genuinely fresh disposable instance -- full pass, real screenshots.
- Preview non-persistence verified directly against the database (zero
  Visits/Events/MediaAssets created), not merely asserted from response
  shapes.
- Interruption/recovery exercised against the configured Stream: honest
  distinct failure during the window, clean recovery immediately after,
  no Stream delete/recreate required.
- No credential leakage, verified against the real secret value in every
  response this milestone's own flow produces, in the rendered DOM, and
  in every log/screenshot/evidence file.
- One real, previously-unknown Camera Node diagnostic-truth defect was
  found live (a direct, foreseeable consequence of deploying the
  *previous* milestone's own fix to real hardware for the first time),
  root-caused, fixed, RED->GREEN, and the fix's own second-order
  consequence (a self-test timing regression) was found and fixed in the
  same pass rather than left to surface later. No release-critical
  Camera Node golden-path defect remains open.
- A second, real, live-reproduced finding (a self-resolving post-pairing
  UI timing race) was fully characterized, honestly disclosed, and judged
  correctly non-blocking rather than either ignored or force-fixed beyond
  this milestone's own bounded scope.
- Final device/Host state is safe, documented, and leaves the shared
  reference Node in a clean, unambiguous, unpaired state for the next
  legitimate session -- explicitly not repeating the "mystery orphaned
  credential" problem this milestone itself had to untangle at the start.

Not forced. The remaining declared-unavailable hardware paths
(RTSP/local-USB/ONVIF/Windows-DirectShow) are hardware-availability gaps
this environment has disclosed identically across every prior camera
-source milestone, explicitly excluded from the Lane G closure bar by
Section 23 itself.
