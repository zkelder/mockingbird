# First-Run & Pairing Reliability v1

**Product flow improved:** pair a Camera Node once -> refresh, close, or
restart MockingBird at any point -> resume exactly where setup left off ->
finish setup at your own pace -> restart MockingBird -> the camera is still
configured. No SSH, no deleting `pairing.json`, no racing a ten-minute timer.

**Why this is next:** a real first-run attempt against the packaged Windows
build and a real Raspberry Pi Camera Node proved the underlying pairing
protocol, camera enumeration, validation, and preview all work -- but the
*setup flow around them* was fragile enough to make refresh/retry tempting
and, once tempted, unrecoverable without local device access. Those are
product defects in how a successful pairing was held, not acceptance-test
inconveniences. This phase does not touch the Observation Engine, detectors,
trackers, candidate authority, or reviewed/species truth.

## Root cause

Camera Node pairing had two independent handoffs, and only the wrong one was
durable:

- The Node's own one-time pairing code is deliberately short-lived and
  single-use (`mockingbird_node/app.py`'s `_PairingState`) -- correct, and
  unchanged. Once accepted, the Node durably remembers the resulting
  credential's hash in its own `pairing.json`, independent of MockingBird.
- The *main application's* copy of that same credential, however, lived only
  in `CameraNodePairingStore`: an in-process Python dict with its own
  10-minute TTL, never written to disk. A browser refresh, a closed tab, an
  application restart, or simply taking longer than 10 minutes to finish
  choosing a camera/Zone all destroyed the only copy the main app had --
  while the Node remained genuinely paired and unable to mint a new code
  without a local restart.

Compounding this: the Camera name field's placeholder text visually looked
like a completed value while the underlying state was empty, Finish
disabled itself with no visible reason, and the packaged Windows launcher
ran the embedded runtime through `pythonw.exe`, which has no console --
`sys.stdout`/`stderr` are `None` there, so the very first `print()` in the
existing startup path crashed the process before it ever bound a port, with
nothing anywhere to show why.

## Core design correction

The one-time *pairing code* remains short-lived. The *successful pairing* no
longer is. `POST /api/camera-nodes/pair` durably persists the accepted
credential -- in a new `camera_node_pending_setups` table (schema version
30, `CameraNodePendingSetupModel`) -- before the response is even built. The
browser receives only an opaque `pairing_token`; the Node address and
credential never travel back to it, exactly like a completed Source's saved
configuration already never re-exposes them. The record has no expiry field
of its own: only an explicit forget-this-Node revocation, a genuine
Node-side credential rejection, or a completed setup (which copies the
credential into `SourceProviderConfigurationModel` and deletes the now-
redundant pending row, same transaction) ends it.

`CameraNodePairingStore`/`CameraNodePairingSession` (the previous in-memory,
TTL-based handoff) are removed outright; `ProductRepository` owns pairing
persistence directly, consistent with how it already owns every other piece
of Camera Node configuration.

## Pairing semantics and resume behavior

- `GET /api/camera-nodes/pending-setup` resumes the most recently touched
  not-yet-completed pairing with no token of its own required from the
  browser -- a reload, a relaunched application, or a fresh tab all recover
  the same way, purely from durable server state.
- `PATCH /api/camera-nodes/pending-setup/{token}` persists already-entered
  draft fields (camera name, view name, Zone, sensitivity, selected camera)
  so *those* also survive a refresh or restart, independent of re-pairing.
- Validate/Preview/Complete all resolve the durable credential through
  `ProductRepository.resolve_camera_node_pending_pairing`; an actual
  `authentication_rejected` response from the Node (never a mere read)
  marks the record `needs_renewal` via `mark_camera_node_pending_setup_
  needs_renewal`, surfaced as "Pairing needs to be renewed" with one
  recovery action, not "enter another pairing code" framed as a first ask.
- Renewing carries the stale record's draft fields onto the new one
  (`create_camera_node_pending_setup(..., renews_pairing_token=...)`, same
  transaction, stale row retired) -- already-entered setup is never thrown
  away merely because the credential needed refreshing.
- Cancellation is explicit and asymmetric by design: leaving the wizard,
  refreshing, or "Do this later" all **preserve** the pending pairing
  (resumable later); only "Forget this Camera Node"
  (`POST /api/camera-nodes/pending-setup/revoke`) actually revokes it, using
  the same authenticated Node revoke call an already-completed camera's
  repair flow already used.
- The Camera Node pairing code's TTL still governs only how long a human has
  to *redeem* the code in MockingBird; once accepted, nothing about
  finishing setup races a clock.

## Required-field UX and Finish

Camera name now starts as an actual, editable default ("My camera", or the
paired camera's own advertised name once one is selected) held in state --
never an empty required field wearing placeholder text as a disguise. Finish
computes and displays every current blocking reason next to itself (pair the
Node, choose a camera, renew pairing, enter a camera/Zone name, validate
first) rather than sitting gray with no explanation.

## Windows launcher defects

- `_ensure_console_streams()` (`runtime.py`) detects `pythonw.exe`'s absent
  console and gives every stream a safe sink before anything else runs, so
  the crash this milestone traced can no longer happen; `_alert_failure`
  additionally pops one native `MessageBoxW` dialog when there was no
  console to show a failure in (never for the ordinary success path).
- `resolve_instance_id`/`instance_identity.json` (`runtime_state.py`) give
  each local data directory a stable, random identity, exposed read-only via
  `GET /api/product/instance`. The launcher's already-running-instance check
  now requires a *matching* identity, not merely a healthy `/health` --
  exactly what a WSL-forwarded or otherwise different MockingBird install
  answering the same port could previously satisfy by accident. A confirmed
  mismatch (or an unconfirmable remote, e.g. an older build without the
  endpoint) is reported as a port conflict and explained; MockingBird never
  kills or otherwise touches the other process.
- `Start MockingBird.vbs` gained one `fso.FileExists` guard with a plain
  message before attempting to launch a missing/corrupt bundle.

## Files touched

- `src/mockingbird/storage/models.py`, `storage/database.py` (schema 30,
  `CameraNodePendingSetupModel`);
- `src/mockingbird/repository/product_repository.py` (pending-setup
  persistence/resume/renewal, `SourceProviderConfigurationModel`/`apply_
  camera_configuration` cleanup on promotion);
- `src/mockingbird/api/schemas.py`, `api/main.py` (pending-setup routes,
  `/api/product/instance`);
- `src/mockingbird/source_providers/camera_node.py` (removed the ephemeral
  `CameraNodePairingStore`/`CameraNodePairingSession`);
- `src/mockingbird/runtime.py`, `runtime_state.py` (console safety, instance
  identity, reuse-vs-conflict decision);
- `scripts/build_local_product.py` (launcher/README);
- `web/src/pages/CameraSetupPage.tsx`, `api/client.ts`, `api/types.ts`,
  `utils.ts` (resumable pairing UX, bounded network-action timeouts);
- tests, and this document.

## Non-goals

- Observation Engine, detector, tracker, or candidate-authority changes;
- reviewed/species truth changes;
- Node auto-discovery;
- a broad `dashboard_summary`/product-health performance rewrite (see the
  milestone report's performance section -- one real, measured redundant-
  computation finding was deliberately left as follow-up rather than
  restructured under this bounded investigation);
- a general frontend redesign beyond onboarding's own language and this
  flow's resume/Finish/progress behavior.

## Validation tier

Tier 3 -- full backend suite, frontend type-check/production build, focused
new backend coverage for persistence/resume/expiry/security/idempotency and
for launcher console-safety/instance-identity, and an isolated onboarding
Playwright pass covering camera-name default, Finish-blocker visibility, and
reload/renewal resume (Camera Node network calls mocked at the browser
boundary there; the real pairing protocol is exercised directly in the
backend suite). The final native-Windows and real-Pi bounded acceptance pass
is handed off -- see the milestone report for exactly what remains and why.
