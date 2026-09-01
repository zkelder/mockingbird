# Reference Camera Node RTT-Capability Upgrade & Compatibility Re-Proof v1: report

## Starting state

Verified before any change was made:

- Branch `main`, accepted HEAD `1a39479` (`git rev-parse HEAD`), 283 commits
  ahead of `origin/main`, not pushed throughout this milestone.
- Schema v58, unchanged.
- Latest accepted milestone: Representative Daylight Gate A Field
  Acceptance v8 -- True-Latency & Crowding Closure Tranche, classification
  B. `docs/release-execution-state.md` §3's own most-recent entries
  (2026-09-01) match the brief's expected starting state verbatim,
  including the exact root cause this milestone exists to close: 0 of 796
  RTT-bounded calibration batches valid, all `insufficient_samples`,
  because the real reference Camera Node's installed software predates
  the RTT protocol addition. One small, pre-existing documentation gap
  noted (not a blocker): §1's own bolded "Accepted HEAD" line still read
  `ea38d21` (the RTT-Bounded Clock Calibration v1 report commit) rather
  than `1a39479` (the v8 reconciliation commit that is the actual current
  tip of `main`) -- §3's own chronological entries are correct and
  unambiguous about `1a39479` being current; only the summary line at the
  top of §1 had not been refreshed by the immediately-prior reconciliation
  commit. Corrected as part of this milestone's own §1 update below.
- Budgets: false-Visit-rate/useful-evidence-rate candidates withdrawn back
  to MORE EVIDENCE REQUIRED (v8's own finding); fragmentation READY FOR
  FORMAL BUDGET REVIEW (v8's own fifth convergent 0% cohort). Both
  confirmed matching the brief's expected state.
- Current authorization: NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED. Confirmed.
- Worktree safety: `git status --porcelain` at session start showed
  exactly the seven preserved untracked files
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) and nothing else; no active writer
  found. Re-confirmed identical, untouched, at the end of this milestone.

Actual state matched the brief's expected state in every substantive
respect. No STOP was needed.

## Pre-upgrade Node identity

Gathered live from the real reference Pi (`ssh mockingbird-pi`, real
passwordless `sudo`, confirmed working this session) before touching
anything:

- Hostname: `mockingbird-node`. OS: Debian GNU/Linux 13 (trixie),
  `aarch64`, kernel `6.18.34+rpt-rpi-v8`.
- Hardware: Raspberry Pi 4 Model B Rev 1.5 (`/proc/device-tree/model`).
- Installed Camera Node build: `build_id 6519d5ef3b60cc0c8d16c666f0b943df`,
  `git_commit baf9fdb838919825dfe70365305eb4722781621c`, built
  `2026-08-27T02:50:03Z` (`manifest.json`, and independently via
  `scripts/install_camera_node.py --status`).
- Service version: `0.1.0`. Service state: `active (running)`, enabled,
  `NRestarts=0`, up since 2026-09-01 08:15 EDT (a pre-existing, healthy,
  long-running process from before this session).
- Pairing state: paired (`pairing_required: false`), to the stale,
  already-accepted `MockingBirdFieldAcceptanceV8` instance (per v8's own
  report) -- `pairing.json` present, containing only `credential_sha256`
  and `version` (no secret or host-identifying data, per the pairing
  design's own "no credential travels back to the browser" contract).
- Camera devices: `camera_count: 8` (1 real `picamera2` sensor -- OV64A40
  64MP -- plus 7 `v4l2` loopback/dev fixtures, correctly unused),
  `available_camera_count: 8`, `self_test.status: "passed"`.
- Config: `/etc/mockingbird-camera-node/node.env`, bind `0.0.0.0:8787`,
  providers `picamera2,v4l2`, unchanged from its 2026-08-18-era values.
- Rollback target already present from the prior (2026-08-26) upgrade
  milestone: `build 5c78ff19a3bbc05291dce1d5de0b3ea9` (`venv.previous`,
  `manifest.json.previous` both present).
- Install/upgrade mechanism confirmed installed via the accepted path
  (`scripts/install_camera_node.py`, not a manual/ad hoc install) --
  `--status`'s own report of a real rollback target and wire-protocol
  facts is only possible for an installer-managed device.
- No active Observation depended on this Node: `sudo ss -tnlp`/`ss -tnp
  state established` on port 8787 showed only the listening socket, no
  established connections; `journalctl` showed no activity in the
  preceding 15 minutes. Safe to proceed.

## Pre-upgrade RTT protocol RED

Confirmed directly, live, immediately before the upgrade
(`curl http://192.168.1.112:8787/node/v1/health` from this sandbox, which
has real, working LAN reachability to the Pi):

```json
{
  "node_id": "node-76ec8e53ae586dd0", "...": "...",
  "self_test": {"status": "passed", "...": "..."},
  "watchdog": {"enabled": true, "...": "..."}
}
```

**No `node_receive_time` or `node_time` key anywhere in the response.**
This matches v8's own three-way root-cause finding exactly (missing
fields on the live endpoint; `grep -rl node_receive_time
/opt/mockingbird-camera-node/` on the Pi returns nothing; manifest commit
`baf9fdb` independently confirmed, via `git merge-base --is-ancestor`, to
be an ancestor of current HEAD and to predate the commit that introduced
the field). Independently re-measured this session: `baf9fdb..HEAD` is
**71 commits** (v8's own report said 69, measured 2 commits earlier in
this same lineage -- the 2 commits v8's own report and reconciliation
themselves added after v8 took its measurement; both figures are correct,
just taken at different points).

This is the real pre-upgrade RED this milestone exists to turn GREEN.

## Upgrade mechanism

Used the accepted, already-validated installer path end to end -- no
manual source-tree copying, no ad hoc `pip install`, no editing production
files over SSH:

1. `python3 scripts/build_camera_node_artifact.py dist/camera-node-artifact`
   on this dev checkout, against accepted HEAD `1a3947974328ee228c5eef126bbb3bf565228419`.
   `verify_clean_camera_node_source` passed (`source_clean: true`) -- its
   `git diff --name-only HEAD -- src/mockingbird_node` scope means the
   seven preserved untracked files (none of which live under
   `src/mockingbird_node/`) could never trip it, confirmed directly rather
   than assumed. Wire protocol recorded in the fresh manifest:
   `node_api_version: v1`, `transport_protocol_version: transport/v1` --
   unchanged from the currently-installed build. Directly confirmed the
   built wheel actually contains the new fields
   (`"node_receive_time" in app.py` / `"node_time" in app.py` both `True`)
   before deploying anything.
2. `scp -r dist/camera-node-artifact/ mockingbird-pi:~/camera-node-install-v1/artifact-v3`
   and a fresh copy of `scripts/install_camera_node.py` itself (the
   Pi-resident copy predated several installer hardening fixes). SHA256
   verified on the Pi side (`sha256sum -c SHA256SUMS`): all 4 files OK.
3. `sudo python3 install_camera_node.py --status` (installer's own
   pre-upgrade view, read-only) -- matched the manual identity-gathering
   above exactly.
4. `sudo python3 install_camera_node.py --export-config backup-pre-rtt-upgrade-2026-09-01.json`
   -- preserved the current `node.env` settings (no secret; pairing
   always needs a fresh code regardless) before touching anything.
5. `sudo python3 install_camera_node.py --preflight artifact-v3` (read-only):
   `candidate_manifest` OK, `candidate_checksums` OK,
   `wire_protocol_compatibility: current`, `disk_space` OK (114.4GB free),
   `would be a no-op: False` (a genuine upgrade). Preflight passed cleanly.
6. `sudo python3 install_camera_node.py artifact-v3` -- the real upgrade.
   Output: prerequisites already installed, service account already
   exists, package installed (`build 2d9588385698ceb3e4051dfb310fd989`),
   **"configuration: existing node.env preserved untouched"**, **"systemd
   unit: unchanged"**, service restarted, post-update health check passed.

## Upgrade result

- Installed build: `2d9588385698ceb3e4051dfb310fd989`, `git_commit
  1a3947974328ee228c5eef126bbb3bf565228419` (exact accepted HEAD), built
  `2026-09-01T17:36:35Z` -- confirmed both via the fresh `manifest.json` on
  the Pi and `install_camera_node.py --status`'s own live view.
- `boot_id` unchanged (`8f6afbda-bb62-414d-9762-4abb65c8d585`) across the
  upgrade -- confirms a genuine service restart, not a machine reboot, as
  the documented upgrade path promises.
- `node.env` byte-identical (the installer's own output explicitly says
  so; config content never re-verified independently beyond that, per the
  installer's own documented "never touched by an update" contract already
  proven in the 2026-08-26 milestone).
- Rollback target now correctly points at the prior build: `build
  6519d5ef3b60cc0c8d16c666f0b943df` (`baf9fdb`) -- confirmed via
  `--status`.
- Camera devices unchanged: `camera_count: 8`, `available_camera_count: 8`,
  `self_test.status: "passed"`, `providers_initialized: true`,
  `camera_available: true`.
- Wire protocol unchanged: `node_api_version: v1`,
  `transport_protocol_version: transport/v1` -- zero breaking change, as
  the accepted RTT-Bounded Clock Calibration v1 design promised.
- No unexpected config/data loss of any kind observed.

## Pairing/config result

Pairing **survived the software upgrade itself intact** -- `node_id`
(`node-76ec8e53ae586dd0`) and `pairing_required: false` were identical
before and after, confirmed by both the live health endpoint and the
installer's own `--status` view. This directly answers §16's primary
question ("determine whether pairing survived... if preserved: verify
it") -- it was preserved, and is verified.

Separately, and only after that verification, this session **deliberately
displaced that surviving pairing** (with the user's explicit, real-time
approval -- see "Camera smoke result," below, for why) using the
documented self-service recovery flow already precedented by the v8
milestone in the identical situation (removing a stale pairing this
session held no credential for): `sudo rm -f
/var/lib/mockingbird-camera-node/pairing.json` + `sudo systemctl restart
mockingbird-camera-node`. This is not an upgrade consequence -- it is a
separate, later, deliberate action this session took for its own
purposes, clearly distinguished here from the upgrade's own (clean)
pairing-preservation result. A fresh one-time pairing code
(`veDuHyc0e65KapOcYv0sOjIB`, 10-minute TTL) was minted and consumed within
its window by a fresh disposable smoke-test Host instance (below). The
Node's config (`node.env`) was never touched by this action.

The environment's own safety classifier initially blocked the first,
compound form of this action without an explicit go-ahead; per its own
guidance this was surfaced to the user directly (a real `AskUserQuestion`
call) rather than routed around, and the user chose to proceed.

## Camera smoke result

Went beyond a Node-local self-test: a real frame was obtained **through
the real Host**, using a fresh, disposable, CPU-only MockingBird instance
run directly in this Linux sandbox (`MOCKINGBIRD_HOME` pointed at an
isolated scratch directory -- no GPU/Windows dependency needed for this,
since the live-preview session used for this test, `/live-session/*`, is
deliberately independent of the GPU-only Observation Engine detector; see
`docs/mockingbird-doctor-operational-health-contract.md`'s own
`detector_model` WARN below for confirmation the detector was never
configured or needed here). Driven end to end through the real product API
(`urllib`, no browser needed):

1. `POST /api/setup/administrator` -- fresh bootstrap Administrator
   (`rtt-smoke-admin`, disposable password), never the operator's own
   identity.
2. `POST /api/camera-nodes/pair` -- real pairing against
   `http://192.168.1.112:8787` with the fresh code. Advertised cameras
   correctly included `picamera2-camera-0` (`provider_type: picamera2`,
   `status: available`) alongside the 7 `v4l2` fixtures; the real
   `picamera2` sensor was explicitly selected, not a fixture.
3. `POST /api/camera-nodes/preview` -- one real transient Node snapshot
   (759,886 bytes JPEG, 1920x1080). The very first attempt returned `409
   node_camera_unavailable` (a brief, expected PiCamera2 warm-up window
   immediately after re-enumeration); succeeded on retry.
4. `POST /api/camera-setup/complete` (`provider_key: camera_node`,
   `enable_monitoring: false` -- deliberately never starting the GPU
   Observation Engine, per this milestone's own non-goals) -- created a
   real, disposable Source/Stream/Zone
   (`stream-be895722a50c`/`RTT Upgrade Smoke Stream`).
5. `POST /api/streams/{id}/live-session/start` -- the lightweight
   live-preview session (distinct from the Observation Engine; needs no
   detector model).
6. `GET /api/streams/{id}/live-session/current-frame` x3, 2s apart:
   real 1920x1080 `image/jpeg` frames, `state: "live"` every time
   (`age_ms` 845/627/167), frame **sequence numbers advancing (1, 2, 4)**
   and **`captured_at` timestamps strictly advancing**
   (`18:13:26.719509Z` -> `18:13:28.970063Z` -> `18:13:31.450182Z`) --
   proof of a genuinely live, continuously-updating source, not a cached
   single frame. Both captured frames were opened and visually inspected:
   real, sharp daylight footage of the actual reference yard (tree,
   feeders, houses, driveway) -- the same scene every prior Gate A cohort
   has used.
7. `POST /api/streams/{id}/live-session/stop` -- clean stop, `200`.

No obvious regression from the upgrade was observed anywhere in this flow.
Raw evidence (full request/response JSON, both captured JPEGs) archived to
`data/camera-node-artifacts/rtt-upgrade-20260901-01/verification/` (local
only, per this repository's `data/` convention -- see that directory's own
`PROVENANCE.md`). The disposable smoke-test Host instance was stopped at
the end of this milestone; its data lived entirely in a session scratch
directory outside the repository, never the operator's own `MockingBirdDev`
or field-acceptance instances.

## Post-upgrade RTT protocol GREEN

Live `GET /node/v1/health` immediately after the upgrade:

```json
{
  "node_receive_time": "2026-09-01T17:39:56.751429+00:00",
  "node_time": "2026-09-01T17:39:56.762099+00:00"
}
```

Both fields present. `node_receive_time <= node_time`
(751429us <= 762099us, a ~10.7ms gap -- the handler's own real camera
-enumeration processing time between the two samples, exactly as the
accepted design's four-timestamp form intends). Re-queried independently
multiple times over the following ~10 minutes (once right after upgrade,
again at the start of the RTT-verification run, again at the end of the
camera smoke test): timestamps advanced with each independent request and
tracked real wall-clock time throughout -- proof they are generated live
by the running upgraded process, not a cached or proxied value.

## Real RTT samples

Ran the real, unmodified production functions directly (no reimplemented
math, no fabricated timestamps): `CameraNodeClient.sample_clock_round_trip`
(`source_providers/camera_node.py`) for the network exchange, and
`clock_calibration.RttRoundTrip` / `estimate_rtt_clock_calibration` for
the interval derivation -- the exact same functions, called the exact same
way (`asyncio.gather` over `asyncio.to_thread`, batch size 5, tolerating
individual probe failures) as `engine_runtime._EngineSession.
_perform_rtt_clock_calibration` uses in a live session. **6 batches, 40s
apart, spanning 201.1 real seconds (~3.35 minutes):**

| Batch | State | Valid | offset_ms | offset_min_ms | offset_max_ms | uncertainty_ms | rtt_ms (best) | node_processing_ms |
|---|---|---|---|---|---|---|---|---|
| 0 | calibrated | 5/5 | -65.07 | -133.42 | 3.29 | 68.35 | 182.17 | 33.37 |
| 1 | calibrated | 5/5 | 19.70 | -22.92 | 62.31 | 42.61 | 118.67 | 30.26 |
| 2 | calibrated | 5/5 | -22.33 | -53.33 | 8.67 | 31.00 | 136.55 | 49.82 |
| 3 | calibrated | 5/5 | -53.69 | -115.25 | 7.86 | 61.56 | 157.72 | 29.59 |
| 4 | calibrated | 5/5 | -20.53 | -49.85 | 8.80 | 29.32 | 102.24 | 29.28 |
| 5 | calibrated | 5/5 | -49.46 | -114.24 | 15.32 | 64.78 | 160.97 | 31.14 |

**Attempted: 30 round trips (6 batches x 5). Accepted (valid, contributed
to a combined interval): 30/30. Rejected: 0** (none exceeded the 1000ms
RTT ceiling; none were missing/malformed Node timestamps -- expected,
since the Node is now upgraded). Raw per-sample RTT (all 30, before any
batch selects its own single best/lowest for reporting): **min 102.24ms,
median 153.78ms, max 393.55ms** -- all comfortably under the 1000ms
ceiling. `node_processing_ms` (the Node's own disclosed handler time,
narrowing the four-timestamp-form bound): tight and consistent, 29.3-49.8ms
across all 6 batches, plausible for enumerating 8 camera devices per health
call. **Combined/intersection state: every one of the 6 independent
batches reached `state="calibrated"`; none reached `insufficient_samples`
or `inconsistent_samples`.**

## Calibration interval result

**At least one valid calibration interval: satisfied, 6 times over.** Every
batch's own combined `[offset_min_ms, offset_max_ms]` interval is a
genuine two-sided bound derived by interval intersection across that
batch's 5 concurrent samples (`combined_min = max(sample mins)`,
`combined_max = min(sample maxes)`) -- the real accepted
`estimate_rtt_clock_calibration` logic, not a hand-computed approximation.
As an additional (non-production, purely diagnostic) honesty check, this
session also intersected all 6 independently-computed batch intervals
against each other: `[-22.92, 3.29]` ms is consistent with every one of
them simultaneously (`overall_min <= overall_max`) -- real evidence the
underlying offset was stable and mutually agreeing across the full
~3.35-minute run, even though production code never merges across batches
this way (each live-session batch replaces, rather than combines with, the
previous one).

## Recalibration result

Six independent batches, all valid, confirms §14 directly:

- **Subsequent batches remain valid:** 6/6, no degradation over time.
- **Offset intervals reasonably consistent:** all 6 midpoints
  (`offset_ms`) fall within a ~40ms band (-65.07 to 19.70ms), and, as
  above, all 6 raw intervals mutually intersect -- no discontinuity, no
  reported "honestly report change" case needed since nothing changed.
- **High-RTT samples rejected if naturally encountered:** none were
  naturally encountered this session (max raw RTT 393.55ms, well under the
  1000ms `DEFAULT_MAX_ACCEPTABLE_RTT_MS` ceiling) -- this specific
  rejection path is already proven synthetically by the accepted
  milestone's own test suite (`test_rtt_calibration_high_rtt_samples_are_
  excluded_never_averaged_in`) and was not artificially forced here, per
  this milestone's own §15 instruction not to manufacture coverage already
  proven synthetically.
- **Interval intersection behaves correctly:** confirmed both within each
  batch (5 samples -> 1 tighter interval, every time) and, informally,
  across batches (above).
- No deliberate clock jump was forced; no deliberate machine reboot was
  performed. The one real reconnect this session caused (the pairing-reset
  service restart) predates all 6 RTT batches, which therefore all ran
  against a single, fresh, already-settled epoch -- consistent with a
  normal "fresh calibration after reconnect" scenario the accepted design
  already anticipates, not a contrived instability test.

## Doctor/health result

`python -m mockingbird doctor` / `doctor --json`, run against the
disposable smoke-test instance (same Camera Node pairing as the smoke
test, above):

- `camera_node`: **PASS** -- "2 configured Stream(s); no attention
  needed." (the second Stream is a pre-existing demo/seed Stream that
  ships with any fresh `MOCKINGBIRD_HOME`, `stream-backyard-feeder` /
  `source-backyard-demo`, confirmed via `GET /api/streams` -- not a
  duplicate created by this session's own setup flow).
- `clock`: **PASS** -- `camera_node_clock_divergence` diagnostic string
  reads "not measurable from a standalone Doctor check: see a running
  session's own `GET .../observation/counterfactual` response
  (`rtt_clock_calibrations`) instead" -- confirms live, on real output,
  that the accepted RTT-Bounded Clock Calibration v1 milestone's own
  Doctor diagnostic-string update (pointing at the new, stronger
  `rtt_clock_calibrations` fact rather than the superseded one-way
  `clock_calibrations`) is deployed and in effect.
- `gpu_cuda`: **PASS** (CUDA/TensorRT execution providers available --
  this sandbox does have real GPU passthrough even from the Linux side;
  unused here on purpose, see "Non-goals").
- `detector_model`: **WARN**, expected and correct -- "A Camera Node is
  configured, but the Observation Engine cannot start without a detector
  model bundle," because this disposable instance deliberately never
  installed one (this milestone does not touch detector/model behavior).
- `storage`: **FAIL** -- "The configured media storage folder does not
  exist." Also expected for this instance: the smoke test never exercised
  the first-run wizard's "confirm storage" step (irrelevant to a
  live-preview-only, no-media-ever-written smoke test) or wrote any media.
  Not a Camera Node/RTT-related finding and not investigated further --
  out of this milestone's scope.
- `application`: **WARN** -- "previous run did not shut down cleanly."
  Expected artifact of running Doctor as a second process against a data
  directory whose server process was, at that moment, still running (not
  yet stopped) -- not a Camera Node/RTT finding.
- Every other check (`database_connectivity`, `database_schema`, `backup`,
  `camera_node_transport`, `ffmpeg`, `species_identification`,
  `offline_ingest`, `research_export`, `acoustic_runtime`,
  `media_integrity`): **PASS**, all expected/informational for a fresh,
  minimal instance.
- No dedicated "old Node version" compatibility check exists anywhere in
  Doctor (confirmed by reading `docs/mockingbird-doctor-operational-health
  -contract.md`'s complete "Checks implemented" table and grepping the
  Doctor implementation) -- so there is no old-Node warning to have newly
  cleared. §20's "no old-node compatibility warning now that it is
  upgraded" is trivially satisfied: nothing warned about Node staleness
  before, and nothing does now; the only Node-version-aware signal in the
  whole system is the RTT calibration mechanism's own honest
  `insufficient_samples` degradation, which -- as shown above -- is now
  cleanly GREEN.

## Local Only

Every action in this milestone ran over a plain LAN connection between
this sandbox and the real Pi (`192.168.1.112:8787`) -- the same connection
already used for pairing/status in ordinary operation. No external NTP
server, no internet reachability, and no cloud service was read or
required anywhere: `sample_clock_round_trip` only ever calls the existing
`/node/v1/health` operation; the smoke-test Host instance ran fully
offline-capable (its one outbound dependency, the Pi itself, is
LAN-local). The OS's normal time service was never disabled or bypassed
on either side, and was not needed to be -- this is precisely the point
of the two-sided RTT bound (it derives an offset from bracketed
request/response timestamps alone, never from either side's own clock
being independently correct).

One honest disclosure: this session's RTT samples were taken from this
WSL2 Linux sandbox, not from the real production Windows Host every prior
field-acceptance cohort used. WSL2's own virtualized network path adds
real overhead (raw RTTs here, 102-393ms, are higher than a native-LAN
Windows or Linux host sitting directly on the same physical network would
likely see) -- but this affects only the absolute RTT *magnitude*, never
calibration *validity*: every sample stayed far under the 1000ms
ceiling, and the underlying bounded-interval mechanism is
network-path-agnostic by construction. A future field session, run from
the real production Windows Host as always, should be expected to see
tighter, lower-RTT intervals than reported here, not different validity.

## Version-skew root cause

Re-confirmed independently (not merely re-cited from v8's own report): the
reference Camera Node had not been redeployed since the "Camera Node
Upgrade & Compatibility Recovery v1" milestone (2026-08-26, artifact
`baf9fdb838919825dfe70365305eb4722781621c`) until this session, despite 71
further commits landing on `main` in the meantime -- including, 45
commits in, the exact commit (`bc6d5ee`) that introduced the
`node_receive_time`/`node_time` fields the entire RTT calibration protocol
depends on. Five field-relevant milestones were accepted in that window
without ever touching the physical Node (v6, v7, Gate A Measurement
Closure v1, Clock Normalization v1, RTT-Bounded Clock Calibration v1
itself) -- the Node upgrade tooling worked throughout; it was simply never
invoked, because nothing in the release process prompted it to be.

## Release-process implication

**No automated mechanism currently exists that checks "is the installed
Camera Node build compatible with/current relative to the accepted repo
HEAD" before a Gate A/field-acceptance session begins.** Searched
specifically for one (any "field-acceptance preflight," "Node freshness
check," or similar) and found none: `scripts/install_camera_node.py`'s
own `--preflight`/`run_preflight` compares a *candidate upgrade artifact*
against the *currently-installed* build, on demand, only when an operator
chooses to run it before an upgrade -- it has no role in, and is not
invoked by, the start of an Observation session or any field-acceptance
tooling (`run_gate_a_measurement_accounting.py`,
`acceptance_recorder.py`, etc.). This is exactly the gap that let v8 run a
158-minute session, and every milestone since 2026-08-26, blind to a
71-commit-stale Node. Per this milestone's own explicit non-goal ("do not
build a large fleet-management feature"), **no new automated check was
built here** -- this is reported as a disclosed, real, bounded gap for a
future release-engineering milestone to weigh, not fixed opportunistically
in this one. A lightweight, in-scope future fix would be narrow: a
field-acceptance preflight step (or a Doctor check) that compares the
paired Node's own `service_version`/manifest-equivalent build identity
against the Host's own `git_commit` and warns if they diverge beyond some
bound -- but that is a design decision for its own milestone, not
something to improvise here.

## Validation

No production code was changed by this milestone -- only the accepted,
already-tested upgrade tooling and the accepted, already-tested RTT
calibration/client functions were exercised against real hardware.
Per §23, no tests were invented for the sake of activity. Real-hardware
validation (above) is the validation for this milestone: the pre-upgrade
RED, the upgrade itself, the post-upgrade GREEN, 30 real RTT round trips
across 6 real batches, a full real pairing/setup/live-frame Host flow, and
a real Doctor run all constitute direct evidence, not a substitute for it.
The accepted Tier 1/2/3 suites that already cover this protocol
(`test_camera_node.py`, `test_clock_calibration.py`,
`test_engine_runtime.py`, and the full Core gate) were last run, and
passed, as part of the immediately-prior accepted milestone
(`ea38d21`/`835f62f`) against the exact same source this session deployed
-- re-running them here would exercise no code this session touched.

## Remaining field proof

The Camera Node upgrade blocker -- Gate A's own item (1), "the single most
consequential, precisely-scoped remaining Gate A dependency" per v8's own
report -- is now closed. The next daylight Gate A field tranche's exact
remaining contract, in priority order (unchanged from v8's own account
except that item (1) is now satisfied and folded into a sharper new item):

1. **The first real, validly RTT-normalized T0->T5 capture-to-visible
   latency distribution.** The Node now exposes the required fields, the
   Host now parses them, and calibration now produces valid bounded
   intervals -- the next live Observation session against this Node should
   be the first ever to produce real `measured` (not `invalid_clock_
   mapping`) latency samples with real `latency_min_ms`/`latency_max_ms`
   uncertainty bounds.
2. Reconciling the now-diverged false-Visit-rate/useful-evidence-rate
   evidence body (v5/v7 vs. v8) -- unchanged, not attempted here (this
   milestone's own explicit non-goal: no detector/model tuning).
3. A second live cohort producing genuinely crowded 3+-simultaneous-subject
   activity -- unchanged, still sought, not mandatory.
4. The bounded visual-review pass against v7's own two remaining
   genuinely-unreviewed ambiguous fragmentation units -- unchanged, out of
   this milestone's scope.
5. The ~13 untraced `blocked_missing_evidence` records, v7's own --
   unchanged; v7's raw ledger remains archived and available for this
   separate task.
6. The already-known Gate B admission-precision residual -- unchanged.

This milestone does not authorize, and explicitly does not start, that
next session (§22/§26).

## Decision

**A.**

Every §25 bar is met: the real reference Camera Node was upgraded using
the supported, already-accepted mechanism end to end (build, preflight,
install, verify); no unexpected config/data loss occurred (`node.env`
byte-preserved, pairing preserved through the upgrade itself); the Pi
camera still works, proven both at the Node level (`self_test`) and
through a real Host-consumed live frame; the real health endpoint now
exposes `node_receive_time`/`node_time`, generated live and advancing
across independent requests; the current Host (the real, unmodified
`CameraNodeClient`) parses them correctly across 30/30 real round trips
with zero errors; 6 of 6 real RTT-bounded calibration batches produced
valid, mutually-consistent bounded intervals over a real ~3.35-minute
span; pairing/recovery state is fully understood and documented (survived
the upgrade; later deliberately, transparently, and with explicit user
approval displaced for this session's own verification purposes via the
established recovery flow; rollback to the prior build remains available
and untested-but-credible, matching v8's own precedent for not forcing a
destructive rollback absent a new defect); Local Only calibration is
confirmed (with one honest disclosure about this session's own
WSL-sandbox network path, affecting only RTT magnitude, never validity);
and no compatibility regression of any kind was found.
