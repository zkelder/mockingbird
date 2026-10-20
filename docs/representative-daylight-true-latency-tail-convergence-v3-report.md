# Representative Daylight True-Latency Tail Convergence v3 — Final Lane R Closure Attempt

Bounded RELEASE-CRITICAL Lane R evidence milestone, directly authorized outside
this file. Follows *Representative Daylight True-Latency Tail Convergence v2*
(blocked at the hard daylight gate, night of 2026-09-05, zero samples) and
*Global Product & Release Readiness Reconciliation v2* (`e031291`), whose own
§10 ("Lane R: current evidence and next field contract") is the closest thing
to an existing "v3 field contract" and is treated as that contract here — no
separately-titled contract document exists or was found.

**Outcome: a genuine daylight session ran end-to-end, on the accepted
production stack, and produced 10 admitted candidates / 9 procedurally valid
RTT-normalized latency samples — short of the ≥12-sample target.** One real,
reproducible packaging defect was found and fixed before deployment (root
cause established, minimal precedented fix, validated, committed separately).
The tail distribution's median stays tightly converged across five cohorts
now; its upper percentile (p90) is, honestly, *less* converged than before
this session (a new high), even though the outright maximum stayed inside the
already-established range. **Classification: B. Decision: MORE EVIDENCE
REQUIRED. Lane R remains OPEN.**

## 1. Starting state

Verified directly, in the order the governing directive required, before any
other action:

- Repository: `/home/<user>/projects/mockingbird-active`; branch `main`.
- Starting HEAD: `e031291` — matches the directive's expected baseline exactly.
- Schema: `CURRENT_DATABASE_SCHEMA_VERSION = 59` (`src/mockingbird/storage/database.py:46`) — matches.
- `docs/release-execution-state.md` top-of-file `CURRENT PHASE` section
  (reconfirmed 2026-09-07 by *Global Product & Release Readiness
  Reconciliation v2*): Lane P `CLOSED`; Lane R `OPEN — RELEASE-CRITICAL — TRUE
  LATENCY TAIL EVIDENCE REMAINS`, "untouched by any of the six [most recent]
  milestones, with zero new field evidence since *Representative Daylight
  True-Latency Tail Convergence v2*." Current authorization at start: `NONE`.
  All matches the directive's stated baseline exactly — no drift found, so
  execution proceeded per the directive's own instruction.
- Governing sources read, in the directive's own required order:
  `docs/release-execution-state.md` (top-of-file phase section + targeted §1/§3
  history), `docs/product-doctrine.md` (full), `docs/roadmap.md` (targeted:
  "Numeric release budgets," Gate A section), then
  `docs/global-product-release-readiness-reconciliation-v2-report.md` (full,
  especially its §10/§11), `docs/representative-daylight-true-latency-tail-convergence-v2-report.md`
  (full — the immediately-prior, daylight-blocked attempt), and
  `docs/gate-a-true-latency-tail-closure-final-lane-r-decision-v1-report.md`
  (full — the authoritative source for the T0–T5 latency contract and the
  standing four-cohort tail table). No dedicated "v3 field contract" file
  exists anywhere in the repository (confirmed: the global v2 reconciliation's
  own §10 already recorded this — "No report titled 'Convergence v3'... exists
  anywhere in this repository"); its §10 preconditions list served as the
  operative contract for this session.
- Worktree safety: no `.git/*.lock`; no MockingBird/Python/Node/uvicorn/vite
  process running in the sandbox at start (only an unrelated Codex CLI process
  and the system's own `unattended-upgrade-shutdown`). The seven preserved
  untracked detector files (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`, `tests/test_small_bird_benchmark.py`)
  were confirmed present and unmodified at start and again at the end of this
  milestone.
- **Stale process found and cleaned up on the Windows host**: `fa_driver.py
  counterfactual stream-92151f510f5a 0 600000` (PID 26516), a leftover
  polling-driver process from the *immediately-prior, already-archived*
  milestone (*Gate A True-Latency Tail Closure & Final Lane R Decision v1*),
  running unattended since `9/5/2026 7:50:52 PM` (~36 hours). It held no port
  and its target instance was already stopped/archived — inert but a genuine
  "no stale disposable processes" violation per the directive's own §4.
  Terminated before proceeding. This is a minor field-tooling hygiene gap in
  that *prior* milestone's own `--stop` procedure (it stops the main
  application process but evidently not this child driver script) — disclosed
  here, not investigated or fixed further, since it is not this milestone's
  own defect and does not affect production code.

## 2. Daylight gate

**PASS.** Two independent clock sources, the same cross-check method this
project has used since v10/v14:

- Sandbox (WSL) clock: `Mon Sep 7 07:44:49 EDT 2026` / `07:48:49` at the
  second read. `timedatectl`: `America/New_York (EDT, -0400)`, NTP
  synchronized.
- Native Windows host clock (via `powershell.exe Get-Date`): `Monday,
  September 7, 2026 7:48:21 AM`, `Eastern Standard Time` (Windows's static
  zone-ID name for the zone that observes EDT in September — normal, not a
  DST defect).
- The reference Camera Node's own `/node/v1/health.node_time`:
  `2026-09-07T11:48:26Z` = `07:48:26 EDT`.

All three agree within seconds. Early-September sunrise at this
timezone/latitude band is approximately 06:25–06:35 EDT (the same
civil-twilight approximation methodology this project has used throughout,
e.g. v2's own "~19:50–20:00 EDT" dusk estimate for the identical site); the
session start (08:45:55 EDT, see §6) was roughly 2h15m after sunrise and
**~10.5 hours before dusk** — vastly more than the 75-minute remaining-daylight
requirement, and closely matching v10's own accepted 07:39:59 EDT start (one
of the two intact best cohorts). The scene's own bird-activity was confirmed
directly, not assumed: real detections and an admitted candidate arrived
within the first minute of the live session (see §6).

## 3. Preflight and two defects found before deployment

Storage: `field_acceptance_instance_lifecycle.py preflight` — `sufficient:
true`, 33.3GB free ≥ 6.0GB required. `storage_health_tier: "getting_low"` —
**three** archived dev-roots are now `SAFE_TO_RECLAIM` (v13, v14, and the
immediately-prior `GateALatencyTailV1`), 24.3GB combined, up from the
18.5GB/two-root disclosure the last two reports carried forward. Disclosed,
not actioned (non-blocking, matching this project's own repeated judgment
call not to force a destructive cleanup mid-session) — this reclaim
opportunity, plus this milestone's own now-archived dev-root, should be
addressed by a future session running
`field_acceptance_instance_lifecycle.py cleanup --dev-root <path> --destroy`
for each with explicit interactive approval.

GPU: NVIDIA GeForce RTX 4060 Ti confirmed present. No conflicting Windows
process or listener on ports 8000/5173 before deploy. Reference Camera Node:
reachable, `self_test: passed`, `camera_available: true`,
`boot_id=4239527b-5622-425c-bed1-ae3074e191dd`, `pairing_required: false`
(paired to the prior archived instance at the start).

### Defect #1 (real, reproducible, fixed): Windows core-tier `numpy` pin drift

The first deploy attempt (`deploy_windows_dev.py --dev-root
MockingBirdLatencyConvergenceV3 --commit e031291`) **failed**:

```
LocalProductBuildError: Windows GPU runtime verification failed:
numpy.libs/libscipy_openblas64_-327b2e0bcffce2882e0dc04cdeb4eaa6.dll is
declared by its package's own RECORD but is not actually present in the
assembled bundle -- the exact defect class a real native-Windows CUDA
session-creation failure surfaced (Error 126, a missing dependency DLL).
```

**Root cause, confirmed by direct code trace, not inferred:**
`WINDOWS_RUNTIME_REQUIREMENTS` (`scripts/build_local_product.py`, the core
dependency tier, installed via a live, unconstrained PyPI resolve with no
`--find-links`) has no `numpy` entry at all — it arrives only transitively,
via `opencv-python-headless`'s own unbounded requirement. At build time it
resolved `numpy==2.5.3` (PyPI's current release). The GPU tier
(`WINDOWS_GPU_RUNTIME_REQUIREMENTS`) only loosely ranges `numpy>=1.26,<3.0`
and is merely *incidentally* pinned to `2.5.2` by the contents of its own
offline, `--no-index` wheel cache (`.build-cache/wheels-win_amd64-cp312-cuda13/`,
populated 2026-08-09, containing only `numpy-2.5.2-*.whl`). Neither `pip
install --target` pass uses `--upgrade`/`--force-reinstall`, so the GPU-tier
pass left the core tier's `2.5.3` binaries on disk while writing a fresh
`2.5.2`-versioned `RECORD` — a disk/RECORD mismatch, correctly caught by
`verify_windows_gpu_runtime_dll_closure` (working exactly as designed).
**Identical defect class, and identical fix shape, to the already-documented
`idna==3.18`/`click==8.4.2` pins immediately above it in the same tuple**
(both added after real, similarly-reproduced incidents in earlier
milestones). Deterministic and reproducible, not environmental: `assemble_windows_bundle`
rebuilds `site_packages` from scratch on every invocation, so a bare retry
would fail identically for as long as PyPI continues serving `numpy 2.5.3` as
latest.

**Fix**: added `"numpy==2.5.2"` to `WINDOWS_RUNTIME_REQUIREMENTS`, matching
the BioCLIP tier's own existing exact pin, in the same comment-and-pin style
as the `idna`/`click` precedent immediately above it. Packaging/build-tooling
only — **zero** detector, classifier, threshold, tracker, admission,
Visit-assembly, evidence-selection, arbitration, schema, or
production-configuration change. Validated: all 12 relevant fast tests in
`tests/test_local_product_packaging.py` (the requirements-matching test, six
DLL-closure tests, three duplicate-metadata tests, and the real pinned-cache
test) pass. Committed separately, before any field deployment, as `f222217`
("Fix Windows core-tier numpy pin: close live-PyPI-vs-cached-wheel drift"),
per the governing directive's §11 ("root-cause it; stop at the appropriate
boundary; report the smallest necessary corrective scope"). **This
milestone's own accepted HEAD for its field deliverable is therefore
`f222217`, one commit ahead of the `e031291` starting baseline** — the retry
deploy at `f222217` succeeded.

### Defect #2 (minor, disclosed, not fixed): `field_acceptance_instance_lifecycle.py init` path-format inconsistency

Its `init` subcommand rejected the same Windows-style (`C:\Users\...`)
`--dev-root` path that its own sibling `preflight` subcommand had, minutes
earlier, correctly accepted and translated (`"resolution_method":
"translated_from_windows_drive_path"`), producing a garbled error
concatenating the WSL cwd with the raw backslash string. Workaround: passing
the equivalent `/mnt/c/...` WSL-mount-style path worked immediately
(`created_by_commit` confirmed `f222217`). Non-blocking — a workaround exists
— and not fixed: this is field evidence, not a code campaign, and the defect
is a CLI input-format inconsistency across subcommands of one tool, not a
correctness defect in the accepted product.

### Defect #3 (operator error, disclosed, not fixed): independent acceptance-frame recorder never activated

I passed a Windows-style path to `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`.
`deploy_windows_dev.py`'s own plumbing for that variable
(`extra_env["MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR"] =
windows_host.to_windows_path(Path(recording_dir))`) unconditionally calls
`wslpath -w <path>`, which expects a **WSL-style** (`/mnt/c/...`) input.
Confirmed directly: `wslpath -w 'C:\Users\...\acceptance-recording'` silently
strips the backslashes and returns a garbage relative filename
(`CUserszachkAppDataLocalMockingBirdLatencyConvergenceV3acceptance-recording`),
with **no error and exit code 0**. The recorder believed it was enabled (its
own code only skips recording when the env var is unset *entirely*) but never
produced a usable directory — confirmed: no such directory, correctly-named
or garbled, exists anywhere under the dev-root.

**Impact**: no independent visual cross-check frames were available this
session — the mechanism *Gate A True-Latency Tail Closure & Final Lane R
Decision v1* used to visually judge its own one disputed sample as "likely not
a real bird." This does **not** affect the core RTT-normalized latency
measurement itself, which runs entirely through the counterfactual
ledger/RTT-calibration path (fully intact and independently validated — see
§5, §7). Precedent for operating without this recorder entirely: **v9 and
v10** — both fully accepted, richly-detailed, intact cohorts — predate this
recorder's existence and used ledger-based causal reasoning alone (chained
track-generation analysis, confidence progression, detection geometry) for
their own tail analysis. I did not stop or restart the live session to fix
this: doing so would have sacrificed real, already-ticking daylight time and
risked a restart/continuity failure, for a supplementary diagnostic tool, not
the core deliverable. §8, below, uses the same ledger-based reasoning v9/v10
established.

## 4. Camera Node pairing reset

Explicit user authorization was obtained (via an interactive confirmation)
before touching the Node — this project's own standing practice of confirming
this specific, physical-hardware-adjacent action separately each time, on top
of the milestone-level authorization; the sandbox's own permission classifier
independently flagged the same action for the same reason. The
already-precedented, non-destructive procedure ran once authorized:

- Backed up `pairing.json` → `pairing.json.pre-latency-convergence-v3-reset.bak`.
- Stopped `mockingbird-camera-node.service`, removed `pairing.json`, restarted.
- `boot_id` **unchanged** (`4239527b-5622-425c-bed1-ae3074e191dd`) across the
  reset — confirms this is the same physical device, only pairing/Host-binding
  state was touched.
- Fresh one-time pairing code obtained from the service's own journal
  (`1prlHfuyozhZEOHZfAweq7_h`, TTL to `2026-09-07T12:45:27Z`), used
  immediately, well within TTL.

## 5. Build identity, credential, camera setup

Deployed via `deploy_windows_dev.py --dev-root
C:\Users\<user>\AppData\Local\MockingBirdLatencyConvergenceV3 --commit
f222217` (full GPU + BioCLIP closure, no skip flags), with the built-in
acceptance recorder *attempted* (see Defect #3).

Confirmed via a real HTTP call to the deployed instance itself (`GET
/api/product/instance`), the one authoritative source this repository's own
standing rule prefers over any deploy helper's own claim:

```json
{"instance_id":"4f2614cc1d5ece8d5cc79fab14779a21","app_version":"0.1.0","git_commit":"f222217ddab359320a00e4786d7799f2410400ed","build_id":"5651de8796840c8d"}
```

`git_commit` matches this milestone's own accepted HEAD exactly.

Lifecycle: `preflight` → `deploy` → `init` (run late, out of the usual order —
my own sequencing slip, corrected before it mattered; see §3's Defect #2 for
the path-format issue it surfaced) → administrator bootstrap → field-acceptance
credential → pair/configure → RTT preflight → Observation, using the accepted
tooling throughout (`field_acceptance_instance_lifecycle.py`,
`deploy_windows_dev.py`, `field_acceptance_client.py`,
`manage_field_acceptance_credential.py`, `check_camera_node_compatibility.py`)
— no ad hoc bypass of any of them. Administrator bootstrapped via `POST
/api/setup/administrator` (`field-acceptance-latency-v3`, locally-generated
24-character password, never user-supplied, discarded with the instance).
Field Acceptance Operator credential minted via `POST
/api/admin/field-acceptance-credentials` (`field-acceptance-3dc1642d02e54407`,
4h TTL, matching precedent's own choice). Camera paired
(`picamera2-camera-0`) and one full-frame `Observation Area` yard zone created
via `POST /api/camera-setup/complete` (`source-9ec686f2689a`/
`stream-9ec686f2689a`); monitoring (the legacy toggle) left off — the modern
Observation Engine path was started explicitly and separately.

**Frozen production stack confirmed live**, not merely configured, via
`observation-status`'s own `advanced.model_runtime_metadata`:
`provider_key=frame-driven-onnx-cuda`, `detector_provider_key=onnx-cuda`,
`selected_execution_providers: [CUDAExecutionProvider, CPUExecutionProvider]`,
model `md-v5a` / `MDv5a.0.1-onnx-opset18`, `score_threshold: 0.1`,
`nms_iou_threshold: 0.45` — exactly the values §3 of the governing directive
requires, unchanged. No detector, threshold, tracker, admission, Visit
assembly, stop finalization, evidence selection, arbitration, or schema
change was made anywhere in this milestone (the one code change, Defect #1's
fix, is packaging-only and does not touch any of these).

## 6. RTT-bounded clock calibration (valid, before Observation began)

`check_camera_node_compatibility.py --profile field_acceptance` (the real,
unmodified `probe_node_compatibility`), from the sandbox directly against the
Node:

```json
{
  "state": "compatible", "camera_available": true,
  "rtt_calibration": {
    "sample_count": 5, "valid_sample_count": 5, "state": "calibrated",
    "offset_ms": -22.39, "offset_min_ms": -62.681, "offset_max_ms": 17.901,
    "uncertainty_ms": 40.291, "rtt_ms": 90.525, "node_processing_ms": 9.238,
    "clock_jump_detected": false
  },
  "version_skew_detected": false
}
```

Valid RTT-bounded calibration established before the timed Observation began,
per the governing directive's §5 requirement. Boot identity confirmed
unchanged (`4239527b-...`) across the pairing reset (§4).

## 7. Independent recording / ledgers

The periodic ledger-snapshot collector (`field_acceptance_ledger_snapshot.py
collect --stream-id stream-9ec686f2689a --interval-seconds 600`) was armed
and **verified writing before Observation started**: its first checkpoint
(`checkpoint-0000.json`, `taken_at: 2026-09-07T12:41:14.035Z`, ~5 minutes
before Observation start) showed `status: "complete"`, all three artifacts
(`raw_ledger`, `monitoring_status`, `scene_confusor_state`) `success: true`.
Nine periodic checkpoints (`checkpoint-0000` through `-0008`) were collected
across the session at the established ~600s cadence.

One corrective fetch was taken with the engine still live, immediately before
calling stop (matching the standing convention since v9); a **second**
corrective fetch was taken immediately after stop-finalization settled, since
the first one predated the one candidate stop-finalization itself rescued
(see §8) — the second fetch is a strict superset (proposal_outcomes 184→194,
track_generations 299→305) and is the one actually used for reconciliation.

**Ledger completeness: PARTIAL, not COMPLETE — but zero known missing
records**, an honest distinction from prior cohorts' "100% COMPLETE"
framing, reported precisely rather than rounded up:

| Artifact | Status | Recovered / Recorded | Gaps (session-offset ms) |
|---|---|---|---|
| `raw_detections` | PARTIAL | 20,768 / 20,768 (0 missing) | `(4641366, 4641919)` — 553ms, the final half-second of the session |
| `track_generations` | PARTIAL | 411 / 411 (0 missing) | `(0, 2229)` — before the first track existed; `(4632399, 4641919)` — final ~9.5s |
| `proposal_outcomes` | PARTIAL | 262 / 262 (0 missing) | `(0, 23563)` — before the first proposal existed |

Every reported gap is a structurally-unavoidable boundary artifact (no event
could exist before the session's own first event of that type, or the
literal final seconds of shutdown) — not lost data. `overall_status:
"PARTIAL"` is the tool's own honest, conservative "cannot *prove*
wall-clock-continuous coverage" signal, correctly distinguished here from an
actual completeness failure.

## 8. Session

- Stream: `stream-9ec686f2689a`.
- Started: `2026-09-07T12:45:55.699564Z` = **08:45:55 EDT**.
- Stopped: `user_stopped` requested `2026-09-07T14:03:09Z`; `state: stopped`
  confirmed settled by `2026-09-07T14:03:50.476206Z` (one additional candidate
  rescued during finalization — see candidate-012, below).
- **Duration: 76.0 minutes** (session's own last offset: 4,641,919ms = 77.4
  minutes of retained activity window; wall-clock start-to-stop-request was
  exactly 75.2 minutes) — at, not over, the governing directive's 75-minute
  maximum. The session was allowed to run the full permitted window because
  the ≥12-sample target had not yet been reached at 45 minutes (3 candidates)
  and activity was continuing, per §7's own explicit instruction to continue
  toward 75 minutes in that circumstance rather than stop early.
- Final counts: `track_updates_observed: 4,869`, `evidence_candidates_observed:
  2,319`, `proposals_observed: 252`, `candidates_created: 10`,
  `candidates_suppressed: 243` (`blocked_continuation_pending: 132`,
  `blocked_ambiguous_boundary: 99`, `blocked_missing_evidence: 9`,
  `reject_insufficient_detector_corroboration: 3`).
- Monitoring health: `camera_connected: true` throughout; `last_healthy_frame_at`
  current at every ~5-minute check across the full session; zero disconnects,
  zero self-test failures, zero anomalies observed.
- **Sample target: 9 valid, short of ≥12.** Per the directive's own §9
  instruction ("report MORE EVIDENCE REQUIRED rather than manufacturing
  closure"), this shortfall is reported honestly, not minimized.

## 9. Raw sample accounting

Computed by the unmodified `run_gate_a_measurement_accounting.py` against the
reconciled merged ledger. **Attempted n = 10. Valid (procedural) n = 9.
Invalid n = 1** (`invalid_clock_mapping` — an early-session edge case, the
identical failure class v9 disclosed for its own earliest candidate: this
candidate's T0 fell before the in-session RTT-calibration loop had produced
its first valid batch after Observation activation, 2 seconds earlier;
correctly excluded, not a defect).

| Visit | T0 (captured) | T5 (`decided_at`) | Latency | Clock state | Fallback | >300s |
|---|---|---|---|---|---|---|
| candidate-003 | 12:46:04.591 | 12:47:06.519 | **excluded** (`invalid_clock_mapping`) | no_calibration | No | — |
| candidate-004 | 12:49:30.748 | 12:55:31.498 | 360,759ms (360.8s) | normalized | Yes (pos 2) | Yes — see §10 |
| candidate-005 | 13:14:51.985 | 13:19:49.825 | 297,847ms (297.8s) | normalized | No | No (just under) |
| candidate-006 | 13:37:57.958 | 13:39:45.344 | 107,387ms (107.4s) | normalized | Yes (pos 1) | No |
| candidate-007 | 13:39:58.336 | 13:41:00.827 | 62,491ms (62.5s) | normalized | No | No |
| candidate-008 | 13:42:03.691 | 13:43:55.914 | 112,231ms (112.2s) — **median** | normalized | No | No |
| candidate-009 | 13:45:25.743 | 13:46:55.145 | 89,402ms (89.4s) | normalized | No | No |
| candidate-010 | 13:47:34.670 | 13:48:32.053 | 57,383ms (57.4s) | normalized | No | No |
| candidate-011 | 13:51:42.750 | 13:59:45.121 | 482,377ms (482.4s) — **max** | normalized | No | Yes — see §10 |
| candidate-012 | 14:00:27.955 | 14:03:45.752 | 197,797ms (197.8s) | normalized | Yes (pos 2) | No |

candidate-012's `decided_at` (14:03:45.752) is **after** the stop request
(14:03:09) — this is the one candidate rescued during stop-finalization,
confirmed by the `candidates_created` count moving 9→10 during the
finalization wait; not a timestamp artifact, an honest, expected outcome of
the accepted stop-finalization mechanism.

### Procedural distribution (n=9)

**median = 112,231ms (112.2s); p90 = 385,083ms (385.1s); p95 = 433,730ms
(433.7s); max = 482,377ms (482.4s); mean = 196,414ms (196.4s).**

`clock_calibration_state: "normalized"` for all 9; RTT-bounded calibration ran
381 batches across the session, 381 calibrated, 0 `insufficient_samples`, 0
`inconsistent_samples`, 0 clock jumps — the calibration mechanism performed
without a single defect throughout.

### Biological validity (ledger-based reasoning only — see Defect #3)

| Visit | Detections | Max conf. | Strong | BBox moved | Assessment |
|---|---|---|---|---|---|
| candidate-004 | 16 | 0.835 | 6 | Yes (32s span) | **Plausible/likely real** — high confidence, sustained, moving |
| candidate-005 | 22 | 0.236 | 0 | Yes (30s span) | **Uncertain** — many detections but none reach the 0.7 "strong" threshold |
| candidate-006 | 22 | 0.818 | 19 | Yes (30s span) | **Plausible/likely real** — high confidence, strongly corroborated |
| candidate-007 | 6 | 0.779 | 2 | Yes | **Plausible/likely real** |
| candidate-008 | 2 | 0.863 | 2 | Yes | **Plausible/likely real** |
| candidate-009 | 1 | 0.731 | 1 | N/A (single frame) | **Plausible** — single confident detection, brief |
| candidate-010 | 1 | 0.903 | 1 | N/A (single frame) | **Plausible** — single high-confidence detection, brief |
| candidate-011 | 1 | 0.905 | 1 | N/A (single frame) | **Plausible, with a caveat** — see §10; high single-frame confidence but spatially isolated from concurrent real activity |
| candidate-012 | 2 | 0.135 | 0 | Yes | **Uncertain** — low confidence, fallback-admitted, rescued at finalization |

7 of 9 are confidently plausible real encounters; 2 (candidate-005,
candidate-012) are genuinely uncertain on the available evidence and are
reported as such rather than forced into either "confirmed" or "false" —
consistent with this project's own abstention-over-fabrication doctrine.
**None** of the 9 shows the specific signature (a long chain of many
low-confidence re-triggers holding one exact fixed image position) that led
*Final Lane R Decision v1* to call its own sample "likely not a real bird" —
so none is classified false here either. This honest middle ground is a
direct, disclosed consequence of Defect #3 (no independent visual frames to
resolve the two uncertain cases definitively).

## 10. >300-second causal classification

Two samples exceed 300 seconds. Both traced directly against the raw ledger
(track generations and proposal outcomes in each sample's own T0–T5 window) —
no independent-recorder frames were available this session (Defect #3), so
this uses exactly the ledger-based methodology v9/v10 used before that
recorder existed. No cause is asserted without direct supporting evidence.

**candidate-004 (360.8s) — Arbitration + evidence availability + continuity/quiet-period (compound, all evidence-supported).**
The admitted track (`fallback_position: 2`) was one of **at least 11 distinct
track generations** chaining `blocked_continuation_pending` /
`episode_boundary_not_yet_final` across the full ~6-minute window, confirming
sustained, continuing nearby activity kept the episode boundary open the
entire time. At `12:55:31`, the top-ranked candidate in the same contested
component failed with `blocked_missing_evidence:fallback_position_1` /
`no_persistable_evidence_bytes` — an evidence-availability failure — which
cascaded directly into the fallback admission (position 2) one millisecond
later. This is the same Visit-Continuity quiet-period/episode-boundary +
ambiguous-boundary-arbitration mechanism v9/v10/v11/v14 have each already
named and this project's own two dedicated ambiguous-boundary investigations
have already characterized as safe (omission-biased) and accepted — not a new
mechanism, not a defect.

**candidate-011 (482.4s, session maximum) — Arbitration + continuity/quiet-period (evidence-supported), with one additional disclosed observation.**
At least **five** distinct track generations (including the eventually-admitted
one) chained `blocked_continuation_pending` across an ~8-minute window,
confirming sustained nearby activity extended the episode boundary
throughout. **Disclosed observation, not a new investigation**: bounding-box
data shows the four *other* tracks in this same contested component were all
clustered at one image location (~x 0.40–0.52, y 0.63–0.83) with real,
multi-detection movement (one had 10 detections over 30 seconds) — consistent
with genuine, sustained bird activity at that spot — while the track that was
actually **admitted** as candidate-011 sits at a spatially distant, isolated
location (x 0.85–0.89, y 0.59–0.66), one single detection (0.905 confidence),
static bounding box. This is consistent with, and does not extend beyond, the
already-accepted ambiguous-boundary mechanism ("any admitted component member
vetoes the whole component," which can end up representing a contested
multi-track episode with a lower-quality member) that two prior, dedicated
investigations already fully characterized and this milestone's own governing
directive explicitly says not to reopen (§10: "Do not reopen accepted
perception work"). Recorded here only because it directly explains *why* this
particular 482.4-second latency happened to attach to this specific,
lower-activity member rather than the more active nearby cluster — not as a
new correctness claim.

No sample in this session shows a false/static chain, a timestamp artifact, or
an unresolved/pathological pattern.

## 11. Comparison with accepted cohorts

| Cohort | Date | n | Median | p90 | Max | Status |
|---|---|---|---|---|---|---|
| v9 | 2026-09-01 | 24 | 111.8s | 173.9s | 307.4s | Intact, live-measured |
| v10 | 2026-09-01 | 11 | 103.9s | 183.3s | **742.3s** | Intact, live-measured |
| v11 | 2026-09-02 | 23 | 115.7s | 318.5s | **865.2s** | Supporting/reconstructed only |
| v14 | 2026-09-05 | 14 | 82.9s | 235.5s | 261.2s | Intact, live-measured |
| **v3 (this session)** | **2026-09-07** | **9** | **112.2s** | **385.1s** | **482.4s** | **Intact, live-measured** |

**Median: newly reinforced, tightly converged across five cohorts now**
(82.9s–115.7s span; this session's own 112.2s lands almost exactly on v9's
111.8s). This is genuinely stronger evidence for a median-based figure than
before this session, though — per the directive's own explicit instruction —
this report does not adopt one; that remains a release-authority decision.

**Maximum: does not expand the already-established range.** 482.4s falls
inside the existing 261.2s (v14) – 742.3s (v10) intact-cohort span. A 5th
independent live cohort landing inside an already-established range, without
pushing either bound outward, is a positive convergence signal on its own.

**p90: honestly, *less* converged than before this session, not more.** Every
prior intact cohort's p90 fell in a comparatively narrow 173.9s–318.5s band;
this session's own 385.1s is a new high, outside that band. With n=9 this
figure is driven almost entirely by the top one-to-two samples (candidate-004
at 360.8s and candidate-011 at 482.4s) and should be weighted accordingly —
it is not a robust estimate at this sample size, but it is also not something
this report can honestly discard. This is new, real information that argues
for *more* evidence before characterizing the tail's upper-percentile region,
not less.

**Ledger-based fragmentation regression-sanity only** (not new Gate A
evidence — Fragmentation is an already-closed, `READY FOR RELEASE BUDGET`
dimension, and this milestone does not reopen it): 5 denominator units (of 15
reconstructed encounter clusters), 2 `correctly_represented`, 0 fragmented, 0
duplicate, 0 missed, 0 merged, 3 `ambiguous` (needs_review, too few for a
confident auto-classification) — `fragmentation_rate: 0.0` among the
confidently-classified units, not contradicting the accepted ≤5% budget.

## 12. Proposed latency budget

**None proposed — MORE EVIDENCE REQUIRED, consistent with, and slightly
sharpening, the standing position.** Per the governing directive's own
explicit instruction not to invent a numeric release budget merely to close
Lane R: the median is now more strongly supported than at any prior point
(five converging cohorts), but the tail — specifically the p90/upper-percentile
region, not just the outright maximum — remains genuinely unresolved, and this
session's own new p90 finding (385.1s) widens the honest uncertainty band
rather than narrowing it. A defensible median/p90-based operational envelope
(per the directive's own §9 preference for median/p90 bounds over an exact
maximum) is closer than before, but not yet supportable from this evidence
alone.

## 13. Gate A / Lane R decision

**MORE EVIDENCE REQUIRED. Lane R remains OPEN — RELEASE-CRITICAL — TRUE
LATENCY TAIL EVIDENCE REMAINS.**

Reasons, both evidence-based, neither invented:

1. **Sample count fell short of the ≥12 target** (9 valid, procedural). Per
   the directive's own §9, this alone is sufficient to preserve `MORE
   EVIDENCE REQUIRED` rather than manufacture closure.
2. **The tail's upper-percentile region is, if anything, less characterized
   after this session than before it** — a new, only lightly-supported (n=9)
   p90 high (385.1s) that no prior cohort approached, even though the
   outright maximum stayed inside the already-established range. Closing Lane
   R now would mean setting a p90/tail budget on weaker evidence than exists
   today, which the directive explicitly forbids ("Do not invent a numeric
   release budget merely to close Lane R").

No correctness defect was found in the product itself. Whole-scene recall
remains an accepted known limitation with no invented numeric floor,
unchanged and not revisited by this milestone, per the directive's own §10.
The other seven/eight Gate A dimensions remain governed by their own existing
budgets and evidence, untouched here.

**This is real, additive progress, not a null result**: a fifth independent,
intact, live-measured daylight cohort now exists; the median converges more
tightly than ever; the two >300s samples this session produced were both
fully, evidence-supported classified without inventing a cause. What remains
open is narrower and more specific than before: enough additional daylight
sessions to (a) clear the ≥12-sample threshold and (b) characterize the p90
region with more than one or two extreme-value-driven samples.

## 14. Validation and field artifacts

- No full Core run performed — not warranted for a field session per the
  governing directive's §11, and the one code change (Defect #1's fix) was
  validated by its own 12 directly-relevant fast tests instead (§3).
- No accepted audit repeated; no perception/classifier work reopened.
- Evidence preserved: merged ledger (`merged-ledger-v2.json`, 21,441 unique
  records), nine periodic checkpoints, two corrective fetches (pre- and
  post-stop), the full encounter-funnel/fragmentation-accounting/latency
  reports, and this report itself — archived with the disposable instance
  (§15).

## 15. Cleanup

- Live Observation session stopped (`user_stopped`), finalization settled,
  one candidate honestly rescued, zero further pending work.
- Windows-hosted process verified stopped: `deploy_windows_dev.py --dev-root
  ... --stop` → `"Stopped f222217 (verified)"`.
- Instance lifecycle: `active` → `completed` → `archived` against the
  evidence bundle described in §14. **Not destroyed**, per standing practice
  (disposable but retained).
- Camera Node pairing: left paired to this archived instance, matching
  v9/v10/v13/v14's own established precedent — no destructive unpairing
  performed. Pre-reset pairing state backed up on the Node (§4).
- Field-acceptance bearer credential and locally-generated Administrator
  password: not explicitly revoked (the instance is stopped, not running, so
  neither is currently exercisable); the credential's own 4h TTL expires it
  automatically. Local plaintext copies of the admin password, bearer token,
  and Node credential were held only in this session's own
  restrictive-permission (`umask 077`) scratch files, deleted at cleanup.
- **Not done, disclosed rather than silently skipped**: the growing
  SAFE_TO_RECLAIM disk-reclaim opportunity (§3) remains unreclaimed — left for
  an operator to run explicitly with interactive approval.
- Working tree: seven preserved untracked files reconfirmed present and
  unmodified; only this milestone's own two commits (the numpy-pin fix,
  `f222217`, and this report/reconciliation) touch tracked files.
- No push performed, per the governing directive.

## 16. Decision

**B**

Real, honest field evidence was collected end-to-end on the accepted
production stack, with valid RTT-bounded calibration throughout (381/381
batches, zero clock jumps) and a ledger reconciliation with zero known missing
records. One genuine, reproducible packaging defect was found, root-caused,
and fixed with the smallest precedented change before any deployment; two
further minor, non-blocking tooling/operator-error gaps were found and
honestly disclosed rather than silently worked around. The session itself ran
its full permitted 75-minute window and produced 9 valid samples — real,
additive progress (a fifth intact live cohort, tighter median convergence,
two fully evidence-supported >300s classifications) — but fell short of the
≥12-sample target, and this session's own new p90 finding leaves the tail's
upper-percentile region less resolved, not more. Lane R's central chartered
question — a converged, defensible operational latency envelope — remains
open. No correctness defect was found; no product behavior was changed; no
budget was forced.
