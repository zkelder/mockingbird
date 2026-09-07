# Representative Daylight True-Latency Tail Convergence v4

Bounded RELEASE-CRITICAL Lane R field-evidence milestone, directly authorized
outside this file. Follows *Representative Daylight True-Latency Tail
Convergence v3* (76-minute session, 9 procedurally valid samples, short of
the ≥12-sample target, p90 diverged to a new high), *Field Acceptance
Tooling Correctness & Preflight Closure v1* (fixed the recorder-readiness and
session-stop-timing gaps v3 exposed), and *Field Acceptance End-to-End
Integration Proof v1* (proved the fixed tooling correct end to end against a
real, disposable fake service).

**Outcome: a genuine 75-minute daylight session ran end-to-end, on the
accepted production stack, using the fully-hardened tooling chain for the
first time in a real field session, and produced 11 admitted candidates /
11 procedurally valid RTT-normalized latency samples — one short of the
≥12-sample target, but the cleanest evidence body of any Lane R cohort to
date (100% procedural validity, a fully COMPLETE ledger reconciliation, and
a genuinely working independent recorder throughout). No correctness defect
was found or reproduced. The median converges more tightly than ever across
five intact cohorts; this session's own p90 falls back inside the
pre-v3 band, easing (not resolving) v3's own divergence concern. One
concrete disclosed finding: one admitted candidate is, on direct visual
review of the independent recorder's own frames, more likely a person and
an accompanying small pet passing through frame than a wild bird — the
same already-documented person/domestic-pet confound class this project has
separately characterized, not a new mechanism. **Classification: B.
Decision: MORE EVIDENCE REQUIRED. Lane R remains OPEN.**

## 1. Starting state

Verified directly, in the order the governing directive required, before any
other action:

- Repository: `/home/zkelder/projects/mockingbird-active`; branch `main`.
- Starting HEAD: `fcf236f` — matches the directive's expected baseline
  exactly.
- Schema: `CURRENT_DATABASE_SCHEMA_VERSION = 59`
  (`src/mockingbird/storage/database.py:46`) — matches.
- `docs/release-execution-state.md` `CURRENT PHASE`/§3/§6.R: Lane P
  `CLOSED`; Lane R `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
  REMAINS`; latest accepted milestone *Field Acceptance End-to-End
  Integration Proof v1* (classification A, tooling-only, no field session);
  current authorization `NONE`. All match the directive's stated baseline
  exactly — no drift found.
- Governing sources read in the directive's own required order:
  `docs/release-execution-state.md` (top-of-file phase section; targeted
  §1/§3/§6.R history back through the standing Lane R evidence chain;
  §13 "Preserved untracked detector files"), `docs/product-doctrine.md`
  (full), `docs/roadmap.md` (targeted: Gate A section, "Numeric release
  budgets"), then `docs/field-acceptance-end-to-end-integration-proof-v1-report.md`
  (full), `docs/field-acceptance-tooling-correctness-preflight-closure-v1-report.md`
  (full), `docs/representative-daylight-true-latency-tail-convergence-v3-report.md`
  (full — the immediately-prior field session whose own procedural gaps the
  two tooling milestones above closed), and
  `docs/global-product-release-readiness-reconciliation-v2-report.md` §10/§11
  (the closest thing to a standing Lane R field contract). No newer accepted
  evidence or superseding field contract was found; the repository's own
  record matches the directive's stated baseline exactly, so execution
  proceeded per the directive's own instruction.
- Worktree safety: no `.git/*.lock`; no stale MockingBird/uvicorn/vite
  process running in the sandbox at start. The seven preserved untracked
  detector files (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) were confirmed present at start and
  reconfirmed byte-identical (`md5sum`) and untouched at the end of this
  milestone; `git status --porcelain=v2` shows exactly these seven `?`
  entries throughout, nothing else.

## 2. Daylight gate

**PASS.** Three independent clock sources, the same cross-check method this
project has used since v10/v14/v3:

- Sandbox (WSL) clock: `Mon Sep 7 16:17:37 EDT 2026`. `timedatectl`:
  `America/New_York (EDT, -0400)`, NTP synchronized.
- Native Windows host clock (via `powershell.exe Get-Date`): `Monday,
  September 7, 2026 4:18:19 PM`.
- The reference Camera Node's own `/node/v1/health.node_time`:
  `2026-09-07T20:18:21Z` = `16:18:21 EDT`.

All three agree within seconds. Gate check time (~16:18 EDT) was roughly
mid-to-late afternoon; this site's own established early-September dusk
estimate (used consistently since v2/v3's own reports) is ~19:45–19:55 EDT
— **~3.5 hours of remaining daylight**, vastly more than the 75-minute
maximum session length, with no plausible progression into dusk even at the
session's own latest possible end (a full 75-minute session starting at
17:03 EDT, the actual Observation-start time recorded below, ends at 18:18
EDT — still more than 1.5 hours before dusk). Real, sustained detector
activity within the first minutes of the live session (§8) independently
confirmed this was a genuinely bird-active scene, not merely a clock check.

## 3. Preflight

- Storage: `field_acceptance_instance_lifecycle.py preflight --no-scan-siblings`
  — `sufficient: true`, 27.1GB free ≥ 6.0GB required (`/mnt/c/Users/zachk/AppData/Local`).
  `storage_health_tier: "getting_low"` (accumulated archived dev-roots from
  prior cohorts) — disclosed, not actioned, matching this project's own
  repeated non-blocking judgment; a full sibling-reclaim scan was skipped
  after it stalled past two minutes on real per-sibling `powershell.exe`
  round-trips (a real, disclosed tooling-performance observation, not a
  defect — see §12).
- GPU: NVIDIA GeForce RTX 4060 Ti confirmed present via
  `Get-CimInstance Win32_VideoController`. No conflicting Windows process
  or listener on ports 8000/5173 before deploy.
- Reference Camera Node: reachable, `self_test: passed`,
  `camera_available: true`, `boot_id=4239527b-5622-425c-bed1-ae3074e191dd`,
  `pairing_required: false` (paired to a prior archived instance at preflight
  time — a routine reset was required, see §4).
- No stale field-acceptance driver/collector processes found in the sandbox
  or on the Windows host at start (contrast v3's own §1, which found and
  cleaned up a genuinely stale `fa_driver.py` process from an even-earlier
  milestone).

### Real-time protocol deviation, disclosed: WSL could not reach the deployed instance's own `127.0.0.1:8000` directly this session

Confirmed directly: `curl` from the sandbox to `127.0.0.1:8000`, to the WSL
vEthernet gateway address, and to the Windows host's own LAN IP all failed
to connect (`exit 7` / `000`), while `powershell.exe Invoke-WebRequest` to
the identical `127.0.0.1:8000` URL succeeded immediately and consistently
throughout the session. `netstat -ano` confirmed the deployed process
genuinely listens on `127.0.0.1:8000` only (as designed) — this is the
same environment-specific WSL↔Windows-loopback fragility this project's own
standing notes already flag ("fragile, re-smoke-test each session"), not a
product defect. **Workaround, zero code changes**: every field-acceptance
script needed for this session
(`field_acceptance_client.py`, `manage_field_acceptance_credential.py`,
`field_acceptance_session_driver.py`, `field_acceptance_ledger_snapshot.py
collect`) is confirmed stdlib-only (`urllib`/`argparse`/`json`/`runpy` —
no third-party import), so each was run **unmodified** via the real, native
Windows `python.exe` (`C:\Users\zachk\AppData\Local\Programs\Python\Python312\python.exe`,
confirmed independently installed, not the product's own bundled
interpreter) against the exact same script files over the
`\\wsl.localhost\Ubuntu\...` UNC path, with credentials passed via
`$env:` variables set in the same `powershell.exe` invocation. Purely
filesystem-based checks with no network component
(`field_acceptance_recorder_readiness.py`'s core frame-evidence check;
`field_acceptance_ledger_snapshot.py reconcile`; `run_gate_a_measurement_accounting.py`)
continued to run directly from the sandbox via `/mnt/c/...`, unaffected.
`check_camera_node_compatibility.py` (talks only to the Camera Node's own
LAN address, never the Host) also ran directly from the sandbox, unaffected.
This is an operational routing workaround only — no script, no production
code, and no field-acceptance contract was changed.

## 4. Camera Node pairing reset

The Node's `pairing_required: false` at preflight meant it was paired to a
different, prior archived instance. The already-precedented, non-destructive
procedure (identical to v3/v9/v10/v13/v14's own) ran via SSH
(`ssh mockingbird-pi`, confirmed working per this project's own standing
alias):

- Located the active pairing state at `/var/lib/mockingbird-camera-node/pairing.json`
  (confirmed via the systemd unit's own `StateDirectory=`/`WorkingDirectory=`,
  distinguishing it from a much older, unrelated leftover file at
  `/home/zkelder/.local/state/mockingbird-camera-node/pairing.json`, ~28.5
  days stale by `mtime` and not read by the running service).
- Backed up → `pairing.json.pre-latency-convergence-v4-reset.bak`.
- Stopped `mockingbird-camera-node.service`, removed `pairing.json`,
  restarted.
- `boot_id` **unchanged** (`4239527b-5622-425c-bed1-ae3074e191dd`) across the
  reset — confirms the same physical device, only pairing/Host-binding state
  touched.
- Fresh one-time pairing code obtained from the service's own journal
  (`Gq_BUzjHmS75sb8YJJw6otoD`, TTL to `2026-09-07T20:58:03Z`), consumed
  within ~4 minutes, well inside TTL.

This directive's own §4 explicitly pre-authorizes "ordinary Camera Node
re-pairing... under the accepted, reversible procedure" for this exact
milestone; the action was performed accordingly (backed up first, reversible,
same device, no personal credentials, no unrelated hardware state touched).

## 5. Build identity, credential, camera setup

Deployed via `deploy_windows_dev.py --dev-root
C:\Users\zachk\AppData\Local\MockingBirdLatencyConvergenceV4 --commit
fcf236f` (full GPU + BioCLIP closure, no skip flags).

**Operator-sequencing correction, disclosed**: the first deploy attempt did
not have `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` set (an omission on my
own part, not a tool defect), so the acceptance recorder would not have been
enabled — caught by re-checking the plan **before** starting Observation,
not after. The running instance was stopped
(`deploy_windows_dev.py --stop`, verified) and redeployed a second time,
this time with `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR=/mnt/c/Users/zachk/AppData/Local/MockingBirdLatencyConvergenceV4/acceptance-recording`
set in the deploying shell. This second deploy re-ran the full build (not a
cheap relaunch — the "reuse" path in `deploy_windows_dev.py` reuses the
populated GPU/BioCLIP wheel *caches*, not a pre-built release bundle for the
dev-root, so wall-clock cost was similar to the first attempt); **zero
Observation time or field-session time was lost**, since this happened
entirely before Observation was ever started. Confirmed identical build
identity across both deploys via a real HTTP call to the deployed instance
itself (through `powershell.exe`, per §3's disclosed connectivity
workaround) — the one authoritative source this repository's own standing
rule prefers over any deploy helper's own claim:

```json
{"instance_id":"93091cfdb4f500f79554882872f673f1","app_version":"0.1.0","git_commit":"fcf236fb08fae7d69b6909bdd36a60b1ec01ca58","build_id":"d6835a3432bcf069"}
```

`git_commit` matches this milestone's own accepted HEAD exactly.

Administrator bootstrapped via `POST /api/setup/administrator`
(`field-acceptance-latency-v4`, locally-generated 24-character password,
never user-supplied, held only in a `chmod 600` scratch file, deleted at
cleanup). Field Acceptance Operator credential minted via
`manage_field_acceptance_credential.py create --ttl-hours 4`
(`field-acceptance-7a1beea92fea4a6e`, expires `2026-09-08T00:49:48Z`, far
beyond the session's own actual duration). Camera Node paired via
`POST /api/camera-nodes/pair` (the same one-time code from §4) →
`picamera2-camera-0` (the only available camera, matching every prior
cohort's own choice), then `POST /api/camera-setup/complete`
(`source-67f3b1065454`/`stream-67f3b1065454`, `provider_key: "camera_node"`)
with one full-frame (`(0,0)-(1,1)`) `Observation Area` yard Zone, monitoring
(the legacy toggle) left off — the modern Observation Engine path started
explicitly and separately, matching precedent's own convention exactly.

**Frozen production stack confirmed live**, not merely configured, via
`observation/status`'s own `advanced.model_runtime_metadata`, read seconds
after Observation start:
`provider_key=frame-driven-onnx-cuda`, `detector_provider_key=onnx-cuda`,
`selected_execution_providers: [CUDAExecutionProvider, CPUExecutionProvider]`,
`cuda_available: true`, `device_type: "GPU"`, model `md-v5a` /
`MDv5a.0.1-onnx-opset18`, `score_threshold: 0.1`, `nms_iou_threshold: 0.45`
— exactly the values the governing directive's §3 requires, unchanged. No
detector, threshold, tracker, admission, Visit assembly, stop finalization,
evidence selection, arbitration, or schema change was made anywhere in this
milestone.

## 6. RTT-bounded clock calibration (valid, before Observation began)

`check_camera_node_compatibility.py --profile field_acceptance
--camera-id picamera2-camera-0 --stream-id stream-67f3b1065454`, run
directly from the sandbox against the Node (unaffected by §3's connectivity
workaround, since it never talks to the Host):

```json
{
  "state": "compatible", "camera_available": null,
  "rtt_calibration": {
    "sample_count": 5, "valid_sample_count": 5, "state": "calibrated",
    "offset_ms": 4.2025, "offset_min_ms": -1.388, "offset_max_ms": 9.793,
    "uncertainty_ms": 5.5905, "rtt_ms": 20.745, "node_processing_ms": 8.496,
    "clock_jump_detected": false
  },
  "version_skew_detected": false
}
```

(`camera_available: null` reflects only that this diagnostic tool was not
given a separate Node pairing credential to run its own optional camera
-availability sub-check — camera availability itself was independently and
affirmatively confirmed through the real Host-mediated pairing in §5.)
Valid RTT-bounded calibration established before the timed Observation
began, per the governing directive's §6 requirement — and, at 5.6ms
uncertainty and 20.7ms round-trip time, the tightest preflight calibration
of any Lane R cohort's own preflight check to date. Boot identity confirmed
unchanged across the pairing reset (§4).

## 7. Independent recording / ledgers

**Ledger collector**: `field_acceptance_ledger_snapshot.py collect
--stream-id stream-67f3b1065454 --interval-seconds 600` armed and
**verified writing before Observation started**: its first checkpoint
(`checkpoint-0000.json`) showed `status: "complete"`, all three artifacts
(`raw_ledger`, `monitoring_status`, `scene_confusor_state`) `success: true`,
`raw_detections record_count: 0` (correct baseline — Observation had not
yet started). Ran continuously throughout the session (9 checkpoints,
`checkpoint-0000` through `-0008`) and was stopped cleanly immediately after
Observation settled.

**Independent acceptance-frame recorder**: genuinely active and verified
**before committing to the full session**, closing exactly the gap that
undermined v3's own report (its Defect #3: the recorder was silently never
activated all session). Per
`field_acceptance_recorder_readiness.py`'s own documented usage (the
recording directory does not exist until Observation creates it, so the
tool's own contract is to run it immediately *after* triggering
`observation/start`, with the field procedure committing to the rest of the
session only once readiness is confirmed — "STOP BEFORE OBSERVATION" means
stop before the session is allowed to continue, not literally before the
API call that creates the directory this tool checks): run with
`--timeout-seconds 120 --poll-interval-seconds 5` immediately after
`observation/start`. Result: `ready: true` after 4 polls (15.0s), manifest
growing `0 → 4` lines, a real, growing frame file
(`frame-000003-offset000010713ms.jpg`, 950,070 bytes) — genuine, advancing
evidence, not a directory sitting empty. Had this failed, the accepted
procedure (and this milestone's own intent) was to stop Observation
immediately and report `STOP BEFORE OBSERVATION` per the governing
directive's §5 — not required this session.

**Recorder coverage across the full session** (verified after the fact
from the manifest's own frame timestamps): 1,335 frames spanning
0–4,559,369ms (76.0 minutes), mean inter-frame interval 3.42s, **maximum
gap 7.47s, zero gaps exceeding 10 seconds anywhere in the session** — the
cleanest, most complete independent-recorder coverage of any Lane R cohort
to date (v9 97.95%, v11 97.5%, v14 99.73% by comparison, though computed by
a slightly different method each time; this session had literally zero
gaps past 7.5 seconds).

## 8. Session

- Stream: `stream-67f3b1065454`.
- Started: `2026-09-07T21:03:26.968622Z` = **17:03:26.969 EDT** (confirmed
  via the authenticated `observation/start` response's own `started_at`).
- Driven by `field_acceptance_session_driver.py run` (the accepted CLI
  proven end to end by *Field Acceptance End-to-End Integration Proof v1*,
  used for the first time in a real field session) at the real, unmodified
  production defaults: `--minimum-duration-seconds 2700
  --maximum-duration-seconds 4500 --target-sample-count 12
  --poll-interval-seconds 37 --stop-settlement-timeout-seconds 120`.
- Stop decision: `maximum_duration_reached` at exactly **75.0 minutes**
  (`elapsed_seconds: 4500.031`, `poll_count: 123`, `sample_count_at_stop: 11`)
  — the driver's own monotonic clamp fired essentially exactly at the
  deadline (0.031s over), never waiting for a five-minute status tick, per
  the governing directive's own §7 requirement.
- Finalization: `settled_before_snapshot` — Observation stop requested
  `2026-09-07T22:19:31.019Z`; settlement confirmed `state == "stopped"`
  after 3 polls (6.719s); the final authenticated raw-ledger snapshot was
  taken *after* settlement (`2026-09-07T22:20:00.147Z`) — the exact
  Observation-stop → finalization-settled → final-snapshot ordering the
  governing directive's §8 requires, enforced by the driver itself this
  time rather than by operator vigilance (contrast v3's own §7/§8, which
  narrates the operator personally catching and correcting an ordering
  slip by hand). No candidate was rescued during this session's own
  finalization window (11 `created` both before and after settlement —
  contrast v3's own rescued candidate-012).
- Final counts at stop: `track_updates_observed` (not separately re-verified
  post-stop; see `finalization-report.json`), `candidates_created: 11`,
  151 suppressed (`blocked_continuation_pending` 74, `blocked_ambiguous_boundary`
  68 [pre-finalization snapshot], `blocked_missing_evidence` 5,
  `reject_insufficient_detector_corroboration` 4 — see §9's reconciled
  final-snapshot totals for the authoritative post-finalization figures).
- Camera Node health: `self_test: passed` throughout every ~2-minute
  monitoring check (see §12); zero disconnects; `boot_id` unchanged;
  watchdog `consecutive_probe_failures: 0` at every check.
- **Sample target: 11 valid, one short of ≥12.** Reported honestly, per the
  governing directive's own §9 instruction, rather than rounded up or
  minimized.

## 9. Ledger completeness verdict

`field_acceptance_ledger_snapshot.py reconcile --snapshot-dir
<9 periodic checkpoints> --final-snapshot <post-settlement snapshot>
--merged-output merged-ledger-v4.json`:

| Artifact | Status | Recovered / Recorded | Gaps |
|---|---|---|---|
| `raw_detections` | **COMPLETE** | 20,858 / 20,858 (100%) | none |
| `track_generations` | **COMPLETE** | 200 / 200 (100%) | none |
| `proposal_outcomes` | **COMPLETE** | 162 / 162 (100%, 91 distinct proposal IDs) | none |

**`overall_status: "COMPLETE"`** — every artifact reconciles with zero gaps
of any kind, not merely zero *known* missing records. This is a genuine
improvement over v3's own honestly-reported `PARTIAL` (small,
structurally-unavoidable boundary gaps) and is the first fully `COMPLETE`
reconciliation in this milestone family's own reporting history. The final
snapshot alone (taken after eviction had already claimed 8,858
`raw_detections`, 74 `track_generations`, and 8 `proposal_outcomes` records
from the live ledger's own bounded retention window) would **not** have
been sufficient by itself — the periodic collector armed in §7 is what
recovered every evicted record, exactly the methodology this project's own
tooling was built to provide.

## 10. Complete raw sample accounting

Computed by the unmodified `run_gate_a_measurement_accounting.py` against
the reconciled, `COMPLETE` merged ledger. **Attempted n = 11. Valid
(procedural) n = 11. Invalid n = 0** — the first Lane R cohort with zero
invalid samples of any kind (v3 had 1 `invalid_clock_mapping`; v9 excluded
one candidate for the same reason).

| Visit | T0 (captured, EDT) | T5 (`decided_at`, EDT) | Latency | Fallback | >300s |
|---|---|---|---|---|---|
| candidate-003 | 17:08:31.755 | 17:15:41.112 | **429,355.8ms (429.4s) — max** | Yes (pos 2) | **Yes — see §11** |
| candidate-004 | 17:18:34.800 | 17:20:09.268 | 94,466.8ms (94.5s) — **median** | No | No |
| candidate-005 | 17:29:35.274 | 17:30:32.325 | 57,050.0ms (57.1s) | No | No |
| candidate-006 | 17:29:57.055 | 17:30:55.430 | 58,373.1ms (58.4s) | No | No |
| candidate-007 | 17:40:44.197 | 17:41:39.992 | 55,793.5ms (55.8s) | No | No |
| candidate-008 | 17:37:45.013 | 17:42:03.703 | **258,686.7ms (258.7s) — p90** | Yes (pos 1) | No (just under) |
| candidate-009 | 17:45:36.203 | 17:48:10.431 | 154,225.0ms (154.2s) | No | No |
| candidate-010 | 17:48:33.722 | 17:50:20.534 | 106,810.8ms (106.8s) | No | No |
| candidate-011 | 17:51:30.153 | 17:52:27.408 | 57,250.1ms (57.3s) | No | No |
| candidate-012 | 17:56:18.600 | 17:57:22.907 | 64,305.5ms (64.3s) | No | No |
| candidate-013 | 18:09:58.191 | 18:11:39.534 | 101,338.7ms (101.3s) | No | No |

All 11 samples: `clock_calibration_state: "normalized"`; RTT-bounded
calibration ran 390 batches across the session (389 calibrated, 1
`insufficient_samples`, 0 `inconsistent_samples`, 0 clock jumps) — a single
early/late edge-case batch, not attached to any of the 11 admitted samples,
so it affected zero measurements.

### Procedural distribution (n=11)

**median = 94,466.767ms (94.5s); p90 = 258,686.743ms (258.7s); p95 =
344,021.291ms (344.0s); max = 429,355.839ms (429.4s); mean = 130,695.997ms
(130.7s).** `measured_count: 11` (100%); `fallback_measured_count: 2`
(candidates-003/008, each a *subset* of `measured` — an admitted
ambiguous-boundary-arbitration fallback member, never a degraded timestamp,
per `capture_to_visible_latency.build_latency_summary`'s own
already-correct, unmodified semantics); `unavailable_capture_time`,
`invalid_clock_mapping`, `invalid_negative`, `implausible` all **0**.

### Biological validity (raw ledger geometry/confidence **and**, for the first time in this milestone family alongside an intact live cohort, real independent-recorder visual cross-check)

| Visit | Detections | Max conf. | Strong | Moved | Assessment |
|---|---|---|---|---|---|
| candidate-003 | 8 | 0.863 | 5 | Yes | **Plausible/likely real** — high confidence, strongly corroborated, at the scene's own tube feeder |
| candidate-004 | 19 (2 gens) | 0.802 | 5 | — | **Plausible/likely real** |
| candidate-005 | 5 | 0.661 | 0 | Yes | **Uncertain — disclosed concern, see below** |
| candidate-006 | 1 | 0.840 | 1 | — | **Plausible** |
| candidate-007 | 1 | 0.796 | 1 | — | **Plausible** |
| candidate-008 | 6 | 0.740 | 1 | Yes | **Plausible/likely real** — same tube-feeder location as candidate-003 |
| candidate-009 | 11 | 0.851 | 2 | Yes | **Plausible/likely real** |
| candidate-010 | 23 (3 gens) | 0.492 | 0 | — | **Plausible/likely real — visually confirmed** (see below) despite low aggregate confidence |
| candidate-011 | 2 | 0.770 | 1 | Yes | **Plausible** |
| candidate-012 | 4 | 0.479 | 0 | Yes | **Plausible — visually confirmed** (see below) despite low confidence |
| candidate-013 | 31 (2 gens) | **0.189** | 0 | — | **Uncertain** — lowest confidence of the cohort; the one independent-recorder frame checked near T0 shows no clear subject |

**8 of 11 confidently plausible/likely real; 2 genuinely uncertain
(candidates-005, -013); 1 (candidate-005) a disclosed, evidence-supported
concern.** Consistent with this project's own abstention-over-fabrication
discipline, none is forced into "confirmed" or "false."

**Visual corroboration, a genuine capability improvement over v3 (which had
no working recorder at all):** independent-recorder frames near candidates
-010 and -012's own T0 moments each show a real, visually-identifiable
small bird at the scene's tube feeder (candidate-010's frame additionally
shows a second bird in flight in the same shot) — upgrading both from
"uncertain on confidence alone" to visually confirmed, real encounters.

**Disclosed finding, candidate-005**: the independent recorder's own frames
spanning this track's T0–T5 window show a person walking on the sidewalk,
accompanied by what appears to be a small pet on a leash, passing through
the same general frame region; the admitted track's own bounding-box
trajectory (entering at the frame's left edge, ending at
x≈0.26–0.29/y≈0.67–0.70) is spatially and temporally consistent with
following that pet rather than a bird at the feeder, and its own
`terminal_reason: "negative_interval_reentry"` /
`terminal_geometry_source: "carried_forward"` marks an irregular track
shape distinct from every other admitted track this session. This is
**not** a new mechanism: it is the same person/domestic-pet confound class
*Hard-Negative Visit Admission Precision & Species-Escalation Correctness
v1* and *Representative Daylight Gate A Field Acceptance v9* already
documented and characterized as a known, disclosed, non-blocking residual.
Per the governing directive's own explicit instruction ("Do not infer
biological identity from bounding-box movement alone... Do not discard
outliers or inconvenient samples"), this is disclosed as a genuine,
evidence-supported concern, not asserted as confirmed-false, and
candidate-005's own latency measurement (a genuine, valid procedural
sample regardless of the underlying subject's identity) is retained,
unmodified, in every statistic above.

## 11. >300-second causal classification

One sample exceeds 300 seconds this session (down from two in v3).
Investigated using both the raw ledger (track generations and proposal
outcomes across the sample's own T0–T5 window) and, for the first time in
this milestone family, real independent-recorder frames.

**candidate-003 (429.4s, session maximum) — Arbitration + sustained/crowded
activity (compound, fully evidence-supported).** The admitted track
(`fallback_position: 2`) belongs to a single connected contested component
containing **69 distinct track generations** and **32 proposal outcomes**
spanning an ~7.5-minute window (offsets ~299,000–748,000ms). All 32
proposals in the component were decided within one ~3.4-second burst
(21:15:41.11–21:15:44.14Z) — the accepted "bounded decision horizon for a
whole connected ambiguous component" mechanism firing once the entire
component's own boundary finally resolved, at which point every member —
including the one eventually admitted, whose own tracked window was only
~21 seconds long and ended at offset 320,005ms, 414 seconds before the
component-wide decision — was adjudicated together. Bounding-box centroids
across the 69 generations span nearly the full frame width (x: 0.021–0.978)
and a wide vertical band (y: 0.395–0.838), with 19/69 generations showing
at least one strong (≥0.7) detection — independently corroborating genuine,
widespread, sustained activity across the scene during this window, not a
single stuck or static detection. **Independent-recorder frames from
across this same window** (offsets ~322,000ms, ~503,000ms, ~703,000ms)
show the scene's own tube/hummingbird feeder stand, with at least one frame
(~503,000ms) showing a visually-identifiable bird at the tube feeder,
directly corroborating real activity at that location during the
contested window. This is the same already-accepted Visit-Continuity
quiet-period/episode-boundary and ambiguous-boundary-arbitration mechanism
v9/v10/v11/v14/v3 have each already named and this project's own two
dedicated ambiguous-boundary investigations have already characterized as
safe (omission-biased, never a false merge or corrupted truth record) and
accepted — not a new mechanism, not a defect, not reopened here.

No sample this session shows a false/static chain, a timestamp artifact, or
an unresolved/pathological pattern. (candidate-008, at 258.7s, sits just
under the 300-second threshold via a materially smaller version of the same
mechanism — a 4-proposal component spanning ~4.4 minutes, admitted as
`fallback_position: 1` at the same tube-feeder location as candidate-003 —
recorded here for completeness since it drives this session's own p90, not
because it crosses the directive's own 300-second bar.)

## 12. Recorder and Camera Node health monitoring during the session

A standalone, self-contained background monitor (not requiring continuous
operator polling) recorded Camera Node health and recorder frame
advancement every ~120 seconds for the full session duration. Across every
one of ~35 checks: `self_test.status: "passed"`, `camera_available: true`,
`boot_id` unchanged, `watchdog.consecutive_probe_failures: 0`,
`watchdog.last_probe_ok: true`, and the latest recorder frame's own
`mtime`/manifest line count advancing monotonically every check — zero
anomalies, zero disconnects, zero self-test failures observed at any point.
Independently, the Camera Node's own systemd journal for the exact session
window (`17:03:00`–`18:21:00` EDT) contains **zero** error/warning/
restart/traceback lines.

## 13. Comparison with accepted cohorts

| Cohort | Date | n | Median | p90 | Max | Status |
|---|---|---|---|---|---|---|
| v9 | 2026-09-01 | 24 | 111.8s | 173.9s | 307.4s | Intact, live-measured |
| v10 | 2026-09-01 | 11 | 103.9s | 183.3s | 742.3s | Intact, live-measured |
| v11 | 2026-09-02 | 23 | 115.7s | 318.5s | 865.2s | Supporting/reconstructed only |
| v14 | 2026-09-05 | 14 | 82.9s | 235.5s | 261.2s | Intact, live-measured |
| v3 | 2026-09-07 | 9 | 112.2s | 385.1s | 482.4s | Intact, live-measured |
| **v4 (this session)** | **2026-09-07** | **11** | **94.5s** | **258.7s** | **429.4s** | **Intact, live-measured** |

**Median: reinforced, tightly converged across five intact cohorts now**
(82.9s–115.7s span, unchanged bounds; this session's own 94.5s lands
comfortably mid-band). Five independent live sessions across a full week
now agree within a ~33-second band on the central tendency.

**p90: this session's own value falls back inside the pre-v3 band, easing
(not resolving) the divergence v3's own report raised.** Every intact
cohort *before* v3 fell in a 173.9s–235.5s band; v3's own 385.1s was a new
high outside it; this session's 258.7s sits between the two, inside the
*wider* 173.9s–385.1s range that now includes v3, but still above the
pre-v3 band on its own. Read plainly: v3's own outlier looks less likely to
be the start of a genuine widening trend now that a fifth intact cohort
lands back closer to the historical range, but the p90 figures across
these five cohorts (173.9, 183.3, 235.5, 258.7, 385.1) still span more than
2.2x and do not yet form a single tight band the way the medians do.

**Maximum: does not expand the already-established range**, for a second
consecutive session. 429.4s falls inside the existing 261.2s (v14)–742.3s
(v10) intact-cohort span, same qualitative result as v3's own 482.4s. Two
consecutive independent cohorts landing inside an already-established range
is a genuine, if modest, positive convergence signal on the maximum
specifically — the *span* itself (261.2s–742.3s, nearly 3x) has not
narrowed.

**Sample-count target: one short, for a second consecutive session** — v3
reached 9/12; this session reached 11/12. Both concrete blockers
`docs/release-execution-state.md` §6.R names for the next Lane R tranche
("the ≥12-sample threshold itself"; "the tail's upper-percentile region")
are narrower after this session than before it, but neither is fully
closed.

**Ledger-based fragmentation regression-sanity only** (not new Gate A
evidence — Fragmentation is an already-closed, `READY FOR RELEASE BUDGET`
dimension, not reopened here): 7 denominator units, 4 `correctly_represented`,
0 fragmented/duplicate/missed/merged, 3 `ambiguous` (needs_review, too few
for confident auto-classification) — consistent with, not contradicting,
the accepted ≤5% budget. A raw automated `admission_recall` figure
(58.3%) is reported by the same accounting tool from unreviewed encounter
clusters alone; per the governing directive's own instruction not to
reopen accepted perception work, and because no independent visual review
of the kind v12/v14 performed was undertaken this session, **this raw
figure is disclosed as unreviewed supporting context only, not treated as
a new whole-scene recall measurement, and does not revise the accepted
recall record.**

## 14. Release-budget decision

**None proposed — MORE EVIDENCE REQUIRED, consistent with the standing
position, narrowed rather than resolved.** Per the governing directive's own
explicit instruction not to invent a numeric release budget merely to close
Lane R:

1. **The ≥12-sample target was not met** (11 valid, procedural) — the same
   standard that kept v3 at `MORE EVIDENCE REQUIRED` applies symmetrically
   here.
2. **The tail's upper-percentile (p90) region is genuinely closer to
   convergence than v3 left it, but not yet converged.** Five p90 values
   spanning 173.9s–385.1s do not yet form a defensible band the way the
   five median values (82.9s–115.7s) do.

Both are evidence-based, neither invented. The median is now supported
across five independent, intact, live-measured cohorts spanning a full
week and is the strongest single number in Lane R's own evidence body, but
the governing directive's own §10 explicitly warns against treating a
stable median as proof the tail is resolved, and this milestone does not do
so.

## 15. Gate A / Lane R decision

**MORE EVIDENCE REQUIRED. Lane R remains OPEN — RELEASE-CRITICAL — TRUE
LATENCY TAIL EVIDENCE REMAINS.**

No correctness defect was found or reproduced anywhere in the product this
session. Whole-scene recall remains an accepted known limitation with no
invented numeric floor, unchanged and not revisited by this milestone
(§13's raw automated figure is explicitly disclosed as non-authoritative,
per above). The other seven/eight Gate A dimensions remain governed by
their own existing budgets and evidence, untouched here.

**This is real, additive progress, not a null result**: a fifth independent,
intact, live-measured daylight cohort now exists, with the cleanest evidence
quality of any cohort to date — the first fully `COMPLETE` ledger
reconciliation, zero invalid samples, zero recorder gaps past 7.5 seconds,
and the first genuine independent-recorder visual cross-check performed
alongside an intact live latency cohort (used here to upgrade two
low-confidence samples to visually-confirmed real encounters, and to
disclose one likely person/pet confound honestly rather than silently). The
median converges more tightly than ever; the sole >300-second sample was
fully, evidence-supported classified (both from the raw ledger and from
real visual frames) without inventing a cause; the sample-count shortfall
narrowed from 3-short to 1-short. What remains open is exactly the same two
items the repository's own standing record already named, each narrower
than before: (a) one additional valid sample (or more) to clear the
≥12-sample threshold; (b) enough further p90 observations to form a single
convergent band the way the medians already have.

## 16. Validation and field artifacts

- No full Core run performed — not warranted for a field session per the
  governing directive's own instruction, and zero production code was
  changed anywhere in this milestone.
- No accepted audit repeated; no perception/classifier work reopened.
- Evidence preserved and archived with the disposable instance (§17):
  merged ledger (`merged-ledger-v4.json`, 21,220 unique records), 9 periodic
  checkpoints, the post-settlement final snapshot, the session driver's own
  finalization report, the full Gate A measurement-accounting output
  (encounter-funnel/fragmentation-accounting/latency reports), the
  independent recorder's own 1,335 frames plus manifest, the health-monitor
  log, and this report itself.

## 17. Cleanup

- Live Observation session stopped by the accepted driver (`user_stopped`
  → `maximum_duration_reached`), finalization settled, zero pending work.
- Windows-hosted process verified stopped:
  `deploy_windows_dev.py --dev-root ... --stop` → `"Stopped fcf236f
  (verified)."`
- Periodic ledger collector and the health monitor were both stopped
  explicitly immediately after Observation settled. **Self-caught cleanup
  gap, disclosed and fixed**: killing the WSL-side `powershell.exe` wrapper
  process for the collector (both the discarded first attempt and the real
  one) did **not** terminate the actual native-Windows `python.exe` child
  process each had spawned across the WSL↔Windows process boundary — a
  final post-cleanup process sweep (`Get-CimInstance Win32_Process` on the
  Windows host) found **two** orphaned `field_acceptance_ledger_snapshot.py
  collect` processes still polling the (already-stopped) product API every
  600s. Both were identified by their exact command line, confirmed to be
  this milestone's own (no unrelated process touched), and terminated
  (`Stop-Process -Force`); a repeat sweep confirmed zero remaining
  Windows-side python/powershell processes and zero mockingbird-related
  processes of any kind. **Lesson for future field sessions using this same
  WSL→Windows-python routing**: terminating the WSL-side launcher process
  is not sufficient by itself to stop a spawned native-Windows child
  process; the actual Windows-side process must be independently confirmed
  stopped (e.g. via `Get-CimInstance Win32_Process`/`Stop-Process` on the
  Windows host), not merely the WSL-side wrapper.
- Instance lifecycle: `init` (run late, after deploy rather than
  immediately following it — a minor process-order slip on my own part,
  harmless since `init` has no ordering dependency on anything that
  happened before it) → `active` → `completed` → `archived` against the
  evidence bundle described in §16. **Not destroyed**, per standing
  practice (disposable but retained).

### New, minor, disclosed-not-fixed tooling gap: `mark-archived --evidence-archive` path resolution

`mark-archived --evidence-archive 'C:\Users\...\field-acceptance-evidence'`
(a Windows-style path, identical in shape to the `--dev-root` value the same
command accepts on the same line) failed:
`ERROR: /home/zkelder/projects/mockingbird-active/C:\Users\...
does not look like a complete evidence archive` — the Windows-style string
was silently treated as a relative path and CWD-anchored, exactly
`field_acceptance_instance_lifecycle.py init`'s own pre-Tooling-Correctness
-v1 Defect #2 shape, but on a *different* parameter
(`--evidence-archive`) the Tooling Correctness milestone's own new
canonical `_resolve_dev_root` fix does not cover (that fix resolves every
subcommand's own `--dev-root`, not the separate `--evidence-archive`
argument `mark-archived` alone accepts). **Workaround, no code change**:
the equivalent `/mnt/c/...` WSL-style path succeeded immediately. Non
-blocking — a workaround exists, evidence was archived successfully — and
not fixed here, per this milestone's own bounded field-evidence (not
tooling-campaign) scope; disclosed for a future tooling-correctness
milestone to close, the same way *Field Acceptance Tooling Correctness &
Preflight Closure v1* closed the analogous `init --dev-root` gap.
- Camera Node pairing: left paired to this archived instance, matching
  v9/v10/v13/v14/v3's own established precedent — no destructive unpairing
  performed. Pre-reset pairing state backed up on the Node (§4).
- Field-acceptance bearer credential and locally-generated Administrator
  password: not explicitly revoked (the instance is stopped, not running);
  the credential's own 4-hour TTL expires it automatically. Local plaintext
  copies were held only in this session's own restrictive-permission
  (`chmod 600`) scratch files, deleted at cleanup.
- **Not done, disclosed rather than silently skipped**: the growing
  `SAFE_TO_RECLAIM` disk-reclaim opportunity (§3) remains unreclaimed — left
  for an operator to run explicitly with interactive approval, per this
  project's own repeated non-blocking judgment.
- Working tree: seven preserved untracked files reconfirmed present,
  byte-identical (`md5sum`), and unmodified; only this milestone's own two
  commits (this report, and the `release-execution-state.md` reconciliation)
  touch tracked files.
- No push performed, per the governing directive.

## 18. Decision

**B**

A genuine 75-minute daylight session ran end-to-end, on the accepted
production stack, for the first time using the fully-hardened field
-acceptance tooling chain (recorder-readiness gate, monotonic session
driver, periodic ledger collector) together in a real field session. Every
piece of that tooling worked exactly as designed: the recorder-readiness
gate confirmed genuine advancing frames before the session was allowed to
continue; the session driver stopped at the exact 75-minute deadline and
enforced the correct stop → settle → snapshot ordering automatically; the
periodic collector, reconciled against the final snapshot, produced this
milestone family's first fully `COMPLETE` ledger reconciliation with zero
gaps of any kind. 11 procedurally valid samples (100% of 11 attempted, zero
invalid) were produced — real, additive progress, and the highest-quality
evidence body of any Lane R cohort to date — but one short of the governing
directive's own explicit ≥12-sample target, for the second consecutive
session. The median converges more tightly than ever across five intact
cohorts; the p90 divergence v3 raised is eased, not resolved. One
substantive finding (a likely person/domestic-pet admission) was
disclosed honestly rather than smoothed over, consistent with this
project's own abstention-over-fabrication discipline. No correctness
defect was found; no product behavior was changed; no budget was forced.
Lane R's central chartered question — a converged, defensible operational
latency envelope — remains open, narrower than it was before this
milestone.
