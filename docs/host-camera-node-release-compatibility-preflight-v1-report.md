# Host ↔ Camera Node Release-Compatibility Preflight v1: report

## Starting state

Verified before any implementation work: branch `main`, HEAD `da1d05e`
(the reconciliation commit accepting Review Provenance Validation & API
Error Semantics v1), schema v58 (`CURRENT_DATABASE_SCHEMA_VERSION` in
`storage/database.py`), current authorization **NONE — GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED** (`docs/release-execution-
state.md` §3) — all matching the governing brief's expected starting
state exactly. The hard-negative admission fix and the reference Camera
Node upgrade were both confirmed accepted per §1/§3/§6.R; Gate A/Lane R
remained OPEN; no existing Host↔Node compatibility mechanism existed
anywhere (confirmed below). Not pushed.

Two other Claude Code sessions shared this repository as their working
directory (confirmed via `/proc/<pid>/cwd`); no file in the repository
had changed in the prior 30 minutes and no `.git/index.lock` existed, so
no active writer was found. The seven preserved untracked detector files
were confirmed present, byte-intact (non-empty, zero merge-conflict
markers), and untouched throughout — a `git stash` mishap mid-session
(a misplaced `-m` flag) briefly raised a false alarm; the stash was
inspected (`git diff stash@{0}` against the working tree: empty output,
byte-identical) and found to contain only this milestone's own four
files before being safely dropped.

## V8 failure reproduction

The exact root cause, re-confirmed by reading the real reports rather
than re-deriving it: Representative Daylight Gate A Field Acceptance v8
ran 796 RTT-bounded calibration batches against the real reference Camera
Node — 0 valid, all `insufficient_samples` — because the Node's live
`GET /node/v1/health` response (installed software 69 commits behind,
`git_commit baf9fdb`) contained neither `node_receive_time` nor
`node_time`, the two additive fields RTT-Bounded Clock Calibration v1
added. Ordinary health remained fine throughout; the gap was only
discovered after a 158-minute session had already run. The Reference
Camera Node RTT-Capability Upgrade & Compatibility Re-Proof v1 report
independently confirmed the release-process gap directly: *"No automated
mechanism currently exists that checks 'is the installed Camera Node
build compatible with/current relative to the accepted repo HEAD' before
a Gate A/field-acceptance session begins."*

Reproduced deterministically in `tests/test_node_compatibility.py` and
`tests/test_node_compatibility_api.py` using the exact real v8 payload
shape (`node_id`/`display_name`/`api_version` present, `node_receive_
time`/`node_time` absent) served over the same `CameraNodeClient
(requester=...)` fake-transport seam `test_camera_node.py` already
established and trusts for this exact client — never a second HTTP
testing methodology. Pre-fix equivalent behavior (no preflight at all)
was confirmed by grep: before this milestone, `get_observation_engine_
session_manager().start(...)` was reachable with no compatibility check
of any kind, for any caller, at any time.

## Existing metadata

Investigated before writing any new code (two parallel read-only research
agents plus direct reads):

- **Node health (`/node/v1/health`)** already carries `node_id`,
  `api_version`, `status`, `camera_count`/`available_camera_count`,
  `pairing_required`, `boot_id`, `os_uptime_seconds`, `service_uptime_
  seconds`, `service_version`, `self_test`, `watchdog`, and (since RTT-
  Bounded Clock Calibration v1) `node_receive_time`/`node_time`. It does
  **not** carry `git_commit` (that only exists in the Node's on-disk
  build manifest, `manifest.json`, never over the wire) or `transport_
  protocol_version` (that lives on the separate `/node/v1/transport/
  status` endpoint).
- **`CameraNodeClient`** (`source_providers/camera_node.py`) already has
  `health()` and `sample_clock_round_trip()` (both unauthenticated),
  `cameras()` (authenticated, returns live per-camera `status`), and one
  existing hard version gate — `pair()` raises `node_api_unsupported` on
  any `api_version` mismatch, exact-match only. No existing method
  compares health/capability facts against anything.
- **RTT-bounded clock calibration** (`observation/clock_calibration.py`)
  already has everything needed: `RttRoundTrip`, `RttClockCalibration
  Record` (`state`: `calibrated`/`insufficient_samples`/`inconsistent_
  samples`), and `estimate_rtt_clock_calibration` — a pure function, never
  raises on a structurally invalid batch, `source_offset_ms` a pure
  passthrough/record field never affecting the interval math.
- **`scripts/install_camera_node.py`**'s own `--preflight` already
  classifies `NodeUpgradeCompatibility` (`current`/`incompatible`/
  `unknown`), but only as a **static, offline, manifest-vs-manifest**
  diff (candidate artifact vs. currently-installed build) — it has no
  configured Host address or credential, so it can never determine live
  compatibility with whatever Host a Node is actually paired to. Its own
  comment already disclosed this scope limit explicitly.
- **Doctor** (`diagnostics/doctor.py`) already gathers `camera_node_
  service_version`/`camera_node_boot_id` per Source via direct, raw
  SQLAlchemy column queries (`_gather_camera_node`) — never constructing
  a `ProductRepository`, never touching `secret=True`-flagged provider
  configuration, and never making a live network call to the Node. Its
  `clock` check already has direct precedent for this milestone's exact
  shape of problem: it reports `camera_node_clock_divergence` as *"not
  measurable from a standalone Doctor check: see a running session's own
  `GET .../observation/counterfactual` response instead"* rather than
  probing live. No "old Node version" warning existed anywhere in Doctor
  (independently confirmed twice, by this milestone and by the RTT-reproof
  report before it).
- **No profile/mode concept** distinguishing "ordinary monitoring" from
  "field acceptance" existed anywhere. The one existing mechanism that
  *does* already distinguish "this caller is running a field-acceptance
  session" is `request.state.field_acceptance_principal` — resolved
  unconditionally on every request by `auth.install_authorization`,
  non-`None` only for the narrow, already-accepted, bearer-token Field
  Acceptance Operator credential that Representative Daylight sessions
  already use to start/stop Observation non-interactively.
- **The Host's own build identity** is already resolvable via `runtime_
  state.resolve_build_identity()` (`git_commit`/`build_id`, `(None,
  None)` for a bare dev checkout — the same conservative "never guess"
  default `resolve_instance_id` already uses) and `mockingbird.
  __version__`/`APP_VERSION` — both already used by `GET /api/product/
  instance`, reused here unchanged rather than building a second
  resolver.

## Compatibility contract

`mockingbird.observation.node_compatibility` (new, pure-decision-module
style matching `provider_compatibility.py`/`clock_calibration.py`'s own
established convention):

- `CompatibilityProfile = Literal["ordinary_monitoring", "field_
  acceptance"]`.
- `NodeCompatibilityState` — six actionable states: `compatible`,
  `incompatible_missing_capability`, `incompatible_protocol`,
  `calibration_failed`, `node_unreachable`, `camera_unavailable`. Never a
  generic "Camera Node unhealthy" bucket.
- `REQUIRED_CAPABILITIES` — a curated `{profile: (capability_name, ...)}`
  dict: `ordinary_monitoring` requires only `health_protocol`;
  `field_acceptance` requires `health_protocol`, `expected_camera_
  available`, `rtt_timestamp_fields`, `bounded_rtt_clock_calibration`. A
  capability absent from a profile's tuple is OPTIONAL for that profile —
  its absence never fails that profile.
- `classify_node_compatibility(...)` — the pure decision table: given
  already-resolved facts (`reachable`, `protocol_valid`, `camera_checked`/
  `camera_available`, `rtt_fields_present`, `rtt_calibration`), returns
  `(state, reasons, missing_capabilities)`. No network, no database —
  directly unit-testable with plain fixtures.
- `probe_node_compatibility(...)` — the live orchestration: fetches real
  health, optionally confirms the expected camera is live-`"available"`,
  and — only once every cheaper prerequisite already looks satisfiable,
  keeping an already-known-incompatible Node's check cheap — runs one
  real bounded batch of `CameraNodeClient.sample_clock_round_trip` calls
  and feeds them through the *exact* accepted `estimate_rtt_clock_
  calibration` (converting `CameraNodeRoundTripSample` → `RttRoundTrip`
  identically to `engine_runtime._perform_rtt_clock_calibration`'s own
  field mapping) before calling the pure classifier once.
- `NodeCompatibilityResult` — a JSON-serialization-friendly frozen
  dataclass: `profile`, `state`, `compatible`, `node_reachable`,
  `required_capabilities`, `observed_capabilities`, `missing_
  capabilities`, `host_app_version`, `host_git_commit`, `node_api_
  version`, `node_service_version`, `camera_available` (`None` when not
  checked, never conflated with "checked and absent"), `rtt_calibration`
  (the real `RttClockCalibrationRecord`, not a re-derived summary),
  `version_skew_detected`, `reasons`, `message`.

Deliberately **not** built: any comparison of `git_commit` values (the
Node has never exposed one live — see "Version-skew behavior" below), any
third profile, any capability not directly tied to an already-identified
Host requirement, and no wire-protocol change of any kind — every fact
this contract needs was already present on the wire. No multi-Node
concept, no fleet inventory, no bulk operation, and no persistence/schema
change anywhere in this module — a self-review check against "overbuilt
into fleet management" (Section 30) found nothing to fix: the entire
contract is two `Literal` values, four capability names, and two
functions.

## Profiles

- **`ordinary_monitoring`** — everyday product use. Requires only that
  the Node answer its health endpoint at all. An old, pre-RTT Node (v8's
  own Node, byte-for-byte) is correctly `compatible` here.
- **`field_acceptance`** — a Representative Daylight Gate A / true-latency
  acceptance session. Requires the expected camera live-confirmed
  available, the RTT timestamp fields present, *and* a real bounded RTT
  probe to actually reach `state == "calibrated"` — advertising the
  fields is necessary but not sufficient.

## Implementation

Four files touched, one new module, one new script, three new/extended
test files — see the implementation commit (`2e84227`) for the complete
diff. Summary:

- `observation/node_compatibility.py` (new) — the contract above.
- `api/main.py` — `start_stream_observation`'s `camera_node` lane gains
  one new conditional block, inserted before the existing `regions = ...`/
  `.start(...)` call: when `request.state.field_acceptance_principal is
  not None` **and** the Stream is already fully paired (mirrors
  `unified_status._camera_node_paired`'s own four-field check exactly, so
  an unpaired Stream is left to its existing "not paired yet" message,
  never a new, less-specific "unreachable" result), run `probe_node_
  compatibility` (wrapped in `asyncio.to_thread`, matching `engine_
  runtime`'s own convention for this exact blocking client) at the
  `field_acceptance` profile. If incompatible, return the existing 200-
  with-honest-status contract (via one new `unified_status.camera_node_
  incompatible_facts` builder) instead of calling `.start(...)` at all.
  An ordinary signed-in user's Start observing never reaches this branch.
- `observation/unified_status.py` — one new pure function, `camera_node_
  incompatible_facts`, matching this module's own explicit "every function
  here is pure" invariant.
- `diagnostics/doctor.py` — one new informational `diagnostic_context` key
  on the existing `camera_node` check's terminal PASS branch (only when a
  camera_node Source is configured), pointing at the new script for a
  live verdict. No new check, no status/recoverability change, no live
  network call — Doctor's own documented read-only invariant is
  unmodified.
- `scripts/check_camera_node_compatibility.py` (new) — a standalone CLI
  wrapping `probe_node_compatibility`, formalizing what every prior
  field-acceptance report has so far done by hand. Exit code 0 for
  `compatible`, 1 otherwise.

## Old-Node result

`tests/test_node_compatibility.py::test_probe_v8_reproducer_old_node_
fails_field_acceptance_before_any_session` and `tests/test_node_
compatibility_api.py::test_field_acceptance_start_is_blocked_by_the_v8_
class_old_node`: a Node serving the exact real v8 health shape returns
`incompatible_missing_capability` for `field_acceptance` — no RTT batch
is even attempted (`rtt_calibration is None`, confirming the "cheap
before expensive" ordering) — with the message *"Camera Node software is
too old for bounded clock calibration required by this acceptance run.
Upgrade the Camera Node before continuing."* The identical response
parses cleanly with no exception anywhere in the chain (`node_api_
version`/`node_service_version` both correctly resolved). The same Node,
same response, evaluated at `ordinary_monitoring`, returns `compatible` —
confirmed both at the pure-classifier level and end-to-end through real
HTTP (`POST /api/streams/{id}/observation/start` returns its ordinary
200 with no compatibility-gate involvement at all when the caller is an
ordinary signed-in Administrator, regardless of the Node's RTT capability).

## Current-Node result

Against a fake current-shape response (fields present, real timing):
`compatible`, `rtt_calibration.state == "calibrated"`,
`missing_capabilities == ()`. Against the **real, live, already-upgraded
reference Camera Node** (`<node-ip>:8787`, LAN-reachable, confirmed
via TCP connect before probing): both profiles return `compatible` (see
"RTT probe result" below for the real numbers). `test_node_compatibility_
api.py::test_field_acceptance_start_proceeds_past_the_gate_for_a_current_
node` confirms the same result through the real `observation/start` route
end to end: the response never carries this milestone's own `node_
compatibility_state` key, proving the gate is not what would block this
attempt (a real detector-model-dependent downstream engine outcome is out
of this milestone's scope, per its own explicit non-goals).

## RTT probe result

Real, live, unauthenticated (`/node/v1/health` needs no credential — see
"Existing metadata") probe against the real reference Camera Node via
`scripts/check_camera_node_compatibility.py --base-address http://
<node-ip>:8787 --profile field_acceptance --json`:

```
state: compatible
rtt_calibration: state=calibrated, valid_sample_count=5/5
  offset_ms=73.1 [66.7, 79.5]  rtt_ms=22.65  node_processing_ms=7.24
```

The first real RTT-bounded calibration evidence collected *by this
milestone's own new tool*, distinct from (and consistent with) the
Reference Camera Node RTT-Capability Upgrade & Compatibility Re-Proof
v1's own 6/6-batch real-hardware proof — this confirms the mechanism
still works against that same upgraded Node today, from this sandbox's
own network path (tighter here, 22.65ms vs. that milestone's own
102-393ms WSL2 measurement — expected variance in the LAN path, not a
validity concern per that report's own disclosed caveat). `--camera-id`/
`--credential` were deliberately not exercised against the real device:
doing so would require a fresh re-pair (a state-changing action on real
hardware, explicitly out of this milestone's non-goals), and the identical
camera-availability code path is already fully exercised, both directions,
by the fake-transport unit tests and the real-HTTP pairing-flow API tests.

## Ordinary monitoring compatibility

Confirmed at every layer: the pure classifier (`test_ordinary_monitoring_
ignores_missing_rtt_capability`, `test_ordinary_monitoring_ignores_
camera_unavailability`), the live orchestration against the real v8-shape
response (`test_probe_v8_reproducer_old_node_still_passes_ordinary_
monitoring`), and real HTTP (`test_ordinary_signed_in_session_is_never_
blocked_by_the_compatibility_gate` — an Administrator's own Start
observing against the identical old-Node response never carries any
`node_compatibility_state` marker and is never blocked). The live gate in
`api/main.py` additionally guarantees this structurally, not just by
classifier behavior: it is wrapped in `if request.state.field_acceptance_
principal is not None`, so for any ordinary signed-in session this new
code path — and its network calls — never executes at all.

## Field-acceptance enforcement

Wired into the one and only call site: `grep -rn "get_observation_engine_
session_manager().start("` across `src/` returns exactly one match,
`api/main.py`'s `start_stream_observation`, immediately after this
milestone's own new gate. There is no alternate path anywhere in the
codebase that starts a camera_node Observation Engine session. Confirmed
fail-closed end to end: `test_field_acceptance_start_is_blocked_by_the_
v8_class_old_node` asserts both the honest `needs_attention` response
*and* (via a follow-up `GET .../observation/status` inside the same
authenticated session) that `observing` remains `False` — no Observation
Engine session, no acceptance-recorder allocation, no GPU/model resource
commitment ever began. The check happens strictly before the existing
`regions = repository.stream_privacy_ignore_regions(...)` / `.start(...)`
line.

## Doctor result

`_interpret_camera_node`'s terminal PASS branch now additionally carries
`diagnostic_context["field_acceptance_compatibility_check"]` — a static
pointer string — whenever a camera_node Source is configured; absent
otherwise (`test_interpret_camera_node_omits_the_preflight_pointer_when_
no_camera_node_is_configured`). No existing check's status, summary, or
recoverability changed. `tests/test_doctor.py` (109 tests, including the
two new ones), `test_doctor_cli.py`, and `test_doctor_camera_node_
transport.py` (127 tests total across the three files) all pass with zero
regressions. Doctor's own documented read-only, no-live-network-probe
design invariant is unmodified — this addition reads only already-
gathered, already-cached facts.

## Windows result

Deployed to a fresh native-Windows dev instance via the existing, accepted
`scripts/deploy_windows_dev.py` (`--skip-gpu-runtime --skip-bioclip-
runtime`, since this check needs no detector/species inference). One
honest disclosure: the deploy was kicked off in the background before a
later `git commit --amend` (folding in one small, cosmetic CLI-warning
addition to `check_camera_node_compatibility.py` — see below), so the
deployed/verified commit is `6045228`, not the final `2e84227` this
report otherwise cites throughout. `git diff 6045228 2e84227 --stat`
confirms the only difference is those same 8 added lines in the
standalone script — `node_compatibility.py`, `api/main.py`,
`unified_status.py`, and `doctor.py` (every file this Windows
verification actually needs to exercise) are byte-identical between the
two commits.

- **App boot, independently verified** (not merely trusting the deploy
  helper's own report, per this repository's own standing practice):
  `GET /api/product/instance` over real HTTP via `powershell.exe`
  (WSL cannot reach the Windows-side loopback directly — a known,
  previously-documented environment fact, not a new finding) returned
  `git_commit: "60452283566206e0a53410c0d5633957b54addad"`, an exact
  match for the deployed commit. The FastAPI app — including this
  milestone's own new `node_compatibility` import and the new gate inside
  `start_stream_observation` — imported and started cleanly on native
  Windows.
- **The new module, exercised directly under native `python.exe`**
  (`C:\...\releases\6045228\python\python.exe`, the exact interpreter
  this deployed release actually runs): `import mockingbird.observation.
  node_compatibility` succeeded; `probe_node_compatibility` against an
  unreachable address returned the correct `node_unreachable` result with
  the correct message; against the **real reference Camera Node**
  (`<node-ip>:8787`, reachable from this real Windows Host on the
  same LAN) returned `compatible`, a real **5/5 valid RTT-bounded
  calibration** (`rtt_ms=24.0`), closely matching this same milestone's
  own earlier WSL-side measurement (22.65ms) and the Reference Camera
  Node RTT-Capability Upgrade & Compatibility Re-Proof v1's own real-
  hardware proof — this is, in fact, the more representative of the two
  RTT measurements this milestone collected, since native Windows is the
  actual Gate A Host platform, not the WSL2 sandbox.
- **No new shell assumption introduced:** neither `node_compatibility.py`
  nor `check_camera_node_compatibility.py` contains any OS-specific path,
  subprocess, or shell logic — both ran unmodified, using the same
  cross-platform `CameraNodeClient`/`resolve_build_identity`/`APP_VERSION`
  every prior Windows-verified milestone already relies on.
- **One incidental, pre-existing, unrelated finding, disclosed not
  fixed:** this persistent dev-data directory's database schema predates
  what this build expects (Doctor's own `database_schema` check correctly
  and honestly reports `WARN`: *"The database schema is older than this
  MockingBird version expects"*) — as a direct consequence, Doctor's
  `camera_node` check itself raised a raw `OperationalError` (`no such
  column: camera_sources.camera_node_last_seen_at`) rather than
  gracefully short-circuiting on a stale schema, so this milestone's own
  new `field_acceptance_compatibility_check` context key could not be
  observed live on *this specific* long-lived Windows dev directory.
  This is unrelated to this milestone (`storage/models.py` was not
  touched here; the column in question was added by Camera Node Boot
  Identity + Autonomous Recovery v1, schema 37) and is not a defect this
  milestone introduced — the identical code path is already directly
  covered, and passing, by two dedicated Linux-side unit tests
  (`test_interpret_camera_node_points_at_the_live_compatibility_preflight_
  tool`, `test_interpret_camera_node_omits_the_preflight_pointer_when_no_
  camera_node_is_configured`) against a correctly-migrated schema. Left
  disclosed for a future, separately-scoped Doctor/migration-robustness
  milestone to weigh, not opportunistically fixed here.
- The disposable instance was left deployed and running (matching this
  tool's own established, repeatedly-confirmed-correct resting state
  across every prior milestone that has used it — the accumulation
  concern earlier reports disclosed was about *retained release
  directories* never being cleaned up, not about the currently-active one
  running; `--cleanup`/`--keep` remain available and untouched, out of
  this milestone's own scope).

## Local Only

Every new code path talks only to the already-configured Camera Node over
the existing local LAN protocol (`CameraNodeClient`'s existing HTTP
methods, all already scoped to private/loopback/link-local addresses
only, per the existing `normalize_camera_node_address` boundary). No new
outbound host, no cloud registry, no internet version service, no GitHub
check participates in the compatibility decision at runtime. The real
end-to-end RTT probe against the reference Node ("RTT probe result",
above) ran over a plain LAN connection, the same one already used for
ordinary pairing/status.

Confirmed no mutation is hidden inside the check, by direct code reading
of every call `probe_node_compatibility` makes: `client.health(...)`
(`GET /node/v1/health`), `client.cameras(...)` (`GET /node/v1/cameras`),
`client.sample_clock_round_trip(...)` (also `GET /node/v1/health`,
bracketed). All three are pre-existing, already-accepted, read-only GET
operations — zero POST/PUT/DELETE call anywhere in this milestone's own
code. Nothing SSHes into the Node, installs software, resets pairing, or
otherwise mutates Node state merely because a compatibility check ran
(Section 16) — upgrade remains a separate, explicit, operator-initiated
action via the already-accepted `scripts/install_camera_node.py`.

## Version-skew behavior

`version_skew_detected` is computed from `node_service_version` vs.
`host_app_version` and reported purely as an informational field — it
never participates in the `compatible`/`incompatible` decision
(`test_probe_flags_version_skew_only_as_informational_never_as_a_
failure` constructs a synthetic Node reporting `service_version:
"9.9.9"` against Host `"0.1.0"`: `version_skew_detected` is `True`,
`compatible` remains `True`). Disclosed honestly, not overclaimed: this
signal is real and correctly wired, but currently weak in practice —
neither `mockingbird` nor `mockingbird_node` bumps its package version
per commit (both are pinned at `"0.1.0"` today), and the Camera Node has
never exposed a live `git_commit` at all (only the on-disk build
manifest has one). Exact commit equality was deliberately **not**
implemented as the compatibility authority anywhere: the one place a
real version mismatch is already meaningfully comparable — `api_version`
— is already hard-gated to exact-match at pairing time
(`CameraNodeClient.pair`), so by the time a Stream reaches this
preflight, that axis has already either passed or the Stream was never
pairable at all.

## Performance

Bounded by construction: one `/node/v1/health` GET for reachability/
protocol/RTT-field-presence, at most one `/node/v1/cameras` GET for
camera availability, and — only when every cheaper check already looks
satisfiable — one bounded batch of `DEFAULT_FIELD_ACCEPTANCE_RTT_PROBE_
BATCH_SIZE = 5` sequential `sample_clock_round_trip` calls (mirroring
`engine_runtime`'s own already-accepted batch size), fed through the
existing pure `estimate_rtt_clock_calibration`. No polling loop, no
retry-with-backoff, no recurring timer. The real end-to-end probe against
the reference Node (health + cameras skipped + 5-sample RTT batch)
completed in a few seconds. No new database writes, no schema migration,
no new background task.

## Validation

**Tier 1** (this milestone's own new/changed files): `tests/test_node_
compatibility.py` (20 tests: the full pure-classifier state matrix plus
`probe_node_compatibility` against the fake-transport seam — v8
reproducer, current-Node success, advertised-but-broken calibration
failure, node-unreachable, camera-unavailable, malformed-protocol,
credential-less reachability-only check, version-skew informational-only)
and `tests/test_node_compatibility_api.py` (3 tests: real HTTP through
the real pairing/setup/observation-start path) — 23/23 passed, confirmed
non-flaky across 5 consecutive runs. Plus 2 new tests added to
`tests/test_doctor.py` for the new diagnostic context key — 25/25 new
tests total across this milestone, all passing.

**Tier 2** (every directly-affected subsystem named in this milestone's
own governing brief): `test_node_compatibility.py`, `test_node_
compatibility_api.py`, `test_camera_node.py`, `test_camera_node_response_
parsing.py`, `test_clock_calibration.py`, `test_engine_runtime.py`,
`test_doctor.py`, `test_doctor_cli.py`, `test_doctor_camera_node_
transport.py`, `test_field_acceptance_authentication.py`, `test_install_
camera_node.py`, `test_api.py`, `test_observation_camera_node_live.py` —
**582 passed, 0 failed** (477 + 105 across the two sweeps), plus a
full-app import/boot smoke test (`mockingbird.api.main`, `mockingbird_
node.app`, `diagnostics.doctor`, `observation.unified_status`/`node_
compatibility` — 335 FastAPI routes registered with zero import error).
Zero new `ruff` findings across every touched/new file (a `git stash`-
isolated baseline comparison on `api/main.py` — the only file with any
pre-existing findings, 26, all pre-existing `E701` violations unrelated
to this milestone's own lines, identical count before and after; every
other touched file is clean both before and after).

**Tier 3 decision: not run**, per this milestone's own explicit §29
carve-out ("If enforcement is limited to acceptance/Doctor surfaces,
Tier 2 may be sufficient"), which matches this diff precisely: the new
`api/main.py` behavior is conditionally gated on `request.state.field_
acceptance_principal is not None` and only ever executes for an already-
paired Stream (confirmed by direct code reading, not assumed); the
`unified_status.py` change is one new, additive function touching no
existing one; the `doctor.py` change is one new informational context
key inside an already-existing branch, changing no status/recoverability
anywhere. Combined with the 582-test Tier 2 sweep (which specifically
includes the broadest relevant file, `test_api.py`, in full) and the
full-app import/boot smoke test, this is judged sufficient without the
~19–31 minute full Core run.

## Remaining release-engineering gaps

- No Host-side surface (Doctor or otherwise) can report a Node's *live*
  RTT capability without an actual network probe — by design (Doctor's
  own read-only invariant), but this means an operator must run `scripts/
  check_camera_node_compatibility.py` explicitly rather than seeing it
  surface passively. A future milestone could persist a durable "last
  known RTT-capability" fact (mirroring `camera_node_service_version`'s
  own persistence) the *next* time a live probe runs, letting Doctor
  report a last-known verdict without probing itself — not attempted
  here, to avoid a new schema/persistence surface not required by this
  milestone's own acceptance bar.
- `version_skew_detected` remains a currently-weak signal in practice
  (see "Version-skew behavior") until this codebase's own package-
  versioning practice changes, or until a future milestone judges a live
  `git_commit` wire field genuinely necessary — deliberately not added
  here (Section 18: only if existing fields are insufficient, and they
  are sufficient for every question this contract currently needs to
  answer).
- No dedicated single-command field-session launcher exists yet (an
  already-disclosed, separately-scoped gap from Non-Interactive Field
  Acceptance Authentication & Session Access v1) — this milestone's new
  script is a discrete verification step an operator (or a future
  launcher) can call, not a replacement for that broader gap.

## Decision

**A.** Every classification-A bar item (Section 32 of the governing
brief) is met with direct, reproduced evidence, not assumption: the v8
capability-skew class is reproduced at three layers (pure classifier, live
orchestration against a fake transport, and real HTTP through the real
pairing/observation-start path); compatibility is capability-based
throughout, with exact git-commit equality never implemented as an
authority anywhere (the Node has never even exposed one live); an old
Node's health response remains byte-for-byte backward-compatible and
`ordinary_monitoring`-compatible; ordinary product operation is
structurally — not just behaviorally — unaffected (the new code path
only ever executes for a field-acceptance credential); field acceptance
fails closed before any Observation session, confirmed via a same-session
follow-up status check; the current, real, already-upgraded reference
Camera Node passes on both profiles from two independent network paths
(this sandbox and, more representatively, the real native-Windows Host);
a real bounded RTT probe — the exact accepted production function,
never a second implementation — is what the `field_acceptance` profile's
compatibility decision actually depends on; six distinct, actionable
states replace what was previously no check at all; every check is
Local Only; zero mutation of Node state anywhere; Tier 1 (25/25) and
Tier 2 (582/582) are clean, and the Tier 3 non-run decision is
specifically justified against this exact diff, not merely asserted.
The one incidental finding (a pre-existing, unrelated stale-schema
condition on one persistent Windows dev directory) is honestly disclosed,
confirmed unrelated to this milestone's own changes, and already covered
by passing tests against a correctly-migrated schema — not a reason to
withhold classification A.
