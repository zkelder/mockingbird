# Gate A True-Latency Tail Closure & Final Lane R Decision v1

Bounded RELEASE-CRITICAL Lane R field-measurement and final Gate A decision
milestone. Follows accepted Gate A Whole-Scene Budget & Remaining-Evidence
Correction v1 (`bf7ee89`).

## Starting state

Verified before any change:

- Branch: `main`.
- HEAD: `bf7ee89` (Reconcile release-execution-state.md: correct Gate A
  Release-Budget & Evidence-Sufficiency Reconciliation v1 (NOT ACCEPTED) via
  Gate A Whole-Scene Budget & Remaining-Evidence Correction v1).
- Schema: `CURRENT_DATABASE_SCHEMA_VERSION = 58` (`src/mockingbird/storage/database.py:45`).
- Not pushed: 346 commits ahead of `origin/main`.
- Untracked preserved files, all present and untouched at start: `docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`, `tests/test_small_bird_benchmark.py`.
- Latest accepted milestone per `docs/release-execution-state.md` §3: Gate A
  Whole-Scene Budget & Remaining-Evidence Correction v1, which corrected the
  immediately-prior (unaccepted) Gate A Release-Budget & Evidence-Sufficiency
  Reconciliation v1 back to **Gate A OPEN -- RELEASE DECISION REQUIRED**
  (recall) with true latency **MORE EVIDENCE REQUIRED** (tail unconverged:
  four sized RTT-normalized cohorts span a max of 261.2s-865.2s).
- Current authorization: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`.
- Worktree safety: one peer session (`mockingbird-active-ba`) was listed
  "interactive" at session start; no file writes, no `git` HEAD movement,
  and no MockingBird/Windows/GPU process activity attributable to it were
  observed at any point during this session (see "Regression sanity,"
  below, for the live-session confirmation).

This matches the milestone's expected starting state exactly; no
discrepancy requiring a stop-and-report was found.

## Global recall release decision

Carried forward verbatim from this milestone's own governing authorization
(a global release-authority decision already made outside this repository,
not re-derived here):

**WHOLE-SCENE RECALL: ACCEPTED KNOWN LIMITATION -- NO NUMERIC RECALL FLOOR
YET.**

- The sustained/crowded ambiguous-boundary recall behavior is accepted for
  launch as a disclosed product limitation.
- This does not remove ambiguous-boundary misses from recall denominators,
  does not claim v14 had better than 64.7% conservative whole-scene recall,
  does not invent a numeric recall floor, does not claim the ambiguity
  mechanism is fixed, and does not authorize further ambiguous-boundary
  tuning.
- Observed whole-scene evidence remains fully visible and undiminished:
  v12 conservative 14/16 = 87.5%; v14 conservative 11/17 = 64.7%; v14
  broader 11/18 = 61.1%.
- Rationale (unchanged from the authorization): two bounded engineering
  investigations (Ambiguous-Boundary Real-Subject Recall Correctness v1;
  Sustained / Crowded Ambiguous-Boundary Recall Correctness v2) found no
  safe discriminator; the failure direction is always omission/abstention,
  never fabricated continuity or corrupted Reviewed truth; MockingBird is
  an ecosystem observatory, not a surveillance recorder; the limitation
  must be disclosed honestly; no threshold was selected merely to pass
  existing evidence.

Verified against `docs/release-execution-state.md` §3 and `docs/roadmap.md`
"Numeric release budgets": as of this milestone's start, both documents
still recorded recall as **RELEASE DECISION REQUIRED** (an open question for
the release authority), not yet reconciled with this now-supplied decision.
This milestone is the first to carry the decision into those two documents
(see "Scheduler / roadmap" reconciliation, below) -- the accepted scheduler
had **not** already incorporated it.

## Conditions

Checked directly against real hardware before starting the live tranche:

| Condition | Status |
|---|---|
| Reference Camera Node reachable | Yes -- LAN TCP to `192.168.1.112:8787`, SSH (`mockingbird-pi` alias), and `/node/v1/health` all confirmed. `node_id=node-76ec8e53ae586dd0`, `boot_id=4239527b-5622-425c-bed1-ae3074e191dd`, `self_test: passed`, `camera_available: true`. |
| Native Windows Host | Yes -- `DESKTOP-VENHFGI`, reachable via `powershell.exe`. |
| Accepted build identity | Yes -- see "Build identity," below. |
| GPU/detector healthy | Yes -- NVIDIA GeForce RTX 4060 Ti; no MockingBird/Python process was already using it (only ordinary desktop apps); post-deploy Observation status confirmed `CUDAExecutionProvider` active, MDv5a loaded, `score_threshold: 0.1` (unchanged). |
| Sufficient storage | Yes, with a disclosed caveat -- see "Storage" below. |
| Independent recorder ready | Yes -- the built-in `AcceptanceRecorder` (`MOCKINGBIRD_ACCEPTANCE_RECORDING_*` env vars), same mechanism v13/v14 used, confirmed producing frames within 2 minutes of session start (101 frames at ~1.2s intervals against a nominal 1000ms cadence). |
| Field ledger collector ready | Yes -- `scripts/field_acceptance_ledger_snapshot.py collect`, same tool used since the Field Acceptance Evidence Integrity & Storage Preflight Correctness v1 milestone. |
| No conflicting Observation | Yes -- `Get-Process`/`Get-NetTCPConnection` on the Windows Host found no MockingBird/uvicorn process and no listener on 8000/5173 before deploy. |
| No unsafe pairing owner | Resolved -- see "Camera Node pairing," below. |

### Storage

`C:` had 19.77GB free at session start (445GB used on a large system drive).
`field_acceptance_instance_lifecycle.py`'s own `assess` found **two
archived, already-evidence-extracted, `SAFE_TO_RECLAIM` dev-roots** (v13,
9.42GB; v14, 9.10GB; 18.5GB combined) it recommended reclaiming
(`storage_health_tier: "action_recommended"`). Reclaiming them was
attempted but the destructive `cleanup --destroy` action was refused by
this session's own permission classifier; rather than force it, this
milestone proceeded without cleanup because the tool's own `preflight`
check independently confirmed sufficiency for a fresh session
(`sufficient: true`, `21.1GB free >= 6.0GB required`, i.e. the acceptance
recorder's 5GB hard ceiling plus a 1GB reserve), and v14's own precedent
consumed ~10.24GB total for a comparable session -- leaving a real, if
tighter-than-ideal, margin. **The 18.5GB reclaim opportunity remains
available and undone**; a future session should run
`field_acceptance_instance_lifecycle.py cleanup --dev-root <v13-or-v14-path> --destroy`
with explicit interactive approval.

### Camera Node pairing

The Node's pairing was held by the archived Representative Daylight Gate A
Field Acceptance v14 instance (`pairing_required: false` at session start;
v14's own report: "Camera Node pairing: deliberately left paired to this
archived instance ... no destructive unpairing performed"). Resetting it to
pair a fresh disposable instance is the same non-destructive,
multiply-precedented operation v9/v10/v13 each performed (backup
`pairing.json` → stop `mockingbird-camera-node.service` → remove
`pairing.json` → restart), and every one of those precedents obtained
**separate, explicit user authorization** each time rather than treating a
milestone brief's general "pair/configure" instruction as sufficient on its
own. This milestone did the same: explicit user authorization was obtained
before touching the Node. `boot_id` (`4239527b-5622-425c-bed1-ae3074e191dd`)
was confirmed unchanged across the reset, confirming it touched only
pairing/Host-binding state, not the physical device. Backup preserved at
`/var/lib/mockingbird-camera-node/pairing.json.pre-gate-a-latency-tail-v1-reset.bak`
on the Node.

## Build identity

Deployed via `scripts/deploy_windows_dev.py --dev-root
C:\Users\zachk\AppData\Local\MockingBirdGateALatencyTailV1 --commit bf7ee89`
(full GPU + BioCLIP closure, no skip flags), with the built-in acceptance
recorder enabled via `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`/
`_INTERVAL_MS=1000`/`_MAX_FRAMES=7200`/`_MAX_BYTES=4500000000` (matching
v13/v14's own established cadence for direct cross-cohort comparability).

Confirmed via a real HTTP call to the deployed instance itself (`GET
/api/product/instance`), the one authoritative source per this repository's
own standing rule that this endpoint's report beats any deploy helper's own
claim:

```json
{"instance_id":"19e5fbd4945e7bb26abc88dc5ebc626f","app_version":"0.1.0","git_commit":"bf7ee8908678c5d478a2fa719c5ff208ce29ac85","build_id":"3b623fc13cc65fdd"}
```

`git_commit` matches the accepted HEAD exactly. `database_schema_version:
58` (via `product-health`), matching the accepted schema.

Lifecycle: `preflight` -> `deploy` -> `init` (manifest `lifecycle_state:
active`, `created_by_commit: bf7ee89...`) -> pair/configure -> compatibility
-> RTT preflight -> Observation, using the accepted tooling
(`field_acceptance_instance_lifecycle.py`, `deploy_windows_dev.py`, a
Windows-native driver over `field_acceptance_client.py`,
`manage_field_acceptance_credential.py`, `check_camera_node_compatibility.py`)
-- no ad hoc bypass of any of them. Administrator bootstrapped via `POST
/api/setup/administrator` (`field-acceptance-gate-a-latency-v1`,
locally-generated 24-character password, never user-supplied, discarded
with the instance). Field Acceptance Operator credential minted via `POST
/api/admin/field-acceptance-credentials` (`field-acceptance-bcdc26a323784d84`,
4h TTL). Camera paired (`picamera2-camera-0`) and one full-frame `yard`
zone created via `POST /api/camera-setup/complete`
(`source-92151f510f5a`/`stream-92151f510f5a`), monitoring left off at setup
time (the modern Observation Engine path is started explicitly, separately,
below -- this does not arm the legacy snapshot-monitoring pipeline).

**Sandbox note (confirmed, matching prior sessions' own disclosed
fragility):** WSL cannot reach the Windows-hosted instance's
`127.0.0.1:8000` directly (`curl` from WSL: connection refused). Every call
against the product's own HTTP API in this session therefore ran through
`powershell.exe` invoking the native Windows Python
(`C:\Users\zachk\AppData\Local\Programs\Python\Python312\python.exe`,
stdlib-`urllib`-only, matching `field_acceptance_client.py`'s own zero-
third-party-dependency design) against copies of the accepted tooling
placed directly on `C:`, with `WSLENV` used to propagate secrets
(admin password, bearer token) across the WSL/Windows process boundary
without writing them to a file Windows would read. Calls to the Camera
Node's own API (`192.168.1.112:8787`) ran directly from WSL without this
workaround, since the Node is a separate LAN device reachable normally.

## RTT preflight

Run via `scripts/check_camera_node_compatibility.py --profile
field_acceptance` (the real, unmodified `probe_node_compatibility`),
directly from WSL against the Node:

```json
{
  "state": "compatible",
  "camera_available": true,
  "rtt_calibration": {
    "sample_count": 5,
    "valid_sample_count": 5,
    "state": "calibrated",
    "offset_ms": -26.664,
    "offset_min_ms": -32.25,
    "offset_max_ms": -21.078,
    "uncertainty_ms": 5.586,
    "rtt_ms": 17.406,
    "node_processing_ms": 6.003,
    "clock_jump_detected": false
  },
  "version_skew_detected": false
}
```

Boot identity: `4239527b-5622-425c-bed1-ae3074e191dd` (unchanged across the
pairing reset, above). Valid RTT-bounded calibration established before the
timed Observation began, per this milestone's own §11 requirement.

## Latency contract (re-established, unchanged)

Per `docs/gate-a-measurement-closure-fragmentation-latency-v1-report.md`
"T0-T5 timeline" (its authoritative table, quoted verbatim):

| Stage | Value | Clock domain |
|---|---|---|
| T0 (source capture) | `TrackGenerationRecord.start_captured_at`/`end_captured_at` | Node |
| T3 (candidate admission) | `ProposalOutcomeRecord.decided_at` | Host |
| T4 (Visit persistence commit) | Same T3 value | Host |
| T5 (query-visible) | ≡ T4 | Host |

**T0:** Camera Node source-capture timestamp, normalized to Host time using
valid RTT-bounded calibration (`camera-node-host-rtt-bounded-clock-
calibration-v1-report.md`'s two-sided interval, which superseded the
earlier, structurally-insufficient one-way estimator -- this does not
change the T0/T5 definition itself, only how T0's cross-domain value is
computed).

**T5 ≡ T4, reconfirmed, not re-litigated:** proven by a live regression
test (`tests/test_candidate_visit_repository.py::test_a_freshly_created_
candidate_visit_is_immediately_query_visible_through_the_same_repository_
read_path`) that a freshly created candidate Visit is immediately visible
through the same read path `GET /api/visits` uses -- no cache, no
materialized view, no poll cycle. Every reported "T0→T5" figure in every
cohort (this one included) is mechanically `T0 → decided_at`. This
milestone does not re-derive or re-test this equivalence; it remains the
accepted contract.

Only measurements inside a valid RTT calibration interval count (never a
Host-receive-time substitute, track-creation time, proposal time,
persistence-start time, or a browser-clock timestamp from a different
clock domain) -- enforced mechanically by `capture_to_visible_latency.py`'s
own `clock_calibration_state` gate, unchanged in this milestone.

## Existing intact latency evidence

Confirmed directly from each cohort's own original accepted report (exact
figures, re-verified from source, not from a later summary):

| Cohort | Valid n | Median | p90 | p95 | Max | Live-measured? |
|---|---|---|---|---|---|---|
| v9 (2026-09-01) | 24 of 25 (1 `invalid_clock_mapping`) | 111,811ms (111.8s) | 173,944ms (173.9s) | 200,408ms (200.4s) | 307,373ms (307.4s) | Yes -- v9's own original report |
| v10 (2026-09-01) | 11 of 11 (no exclusions stated) | 103,900ms (103.9s) | 183,300ms (183.3s) | not stated by v10 itself | **742,300ms (742.3s / 12.37min)** | Yes -- v10's own original report, full 11-row raw table published |
| v14 (2026-09-05) | 14 of 14 (100%, 0 invalid) | 82,920.6ms (82.9s) | 235,454.9ms (235.5s) | 253,408.4ms (253.4s) | 261,211.4ms (261.2s) | Yes -- v14's own original report |

v9's raw per-Visit values are not fully published (aggregate + named
examples only: max = `visit-observation-candidate-027` at 307,373ms, 9
chained track generations). v10 published its complete 11-row raw table
(reproduced in full below, "Cross-cohort latency comparison"). v14
published its aggregate table plus named min (visit-005, 59,379.4ms) and
max (visit-014, 261,211.4ms).

**v10's disclosed outlier, root-caused not assumed** (v10's own report):
candidate-010's tail latency (681.3s of its 742.3s total) traces to a
second, separate, visually-confirmed genuine bird encounter at the same
feeder beginning ~350s after candidate-010's own track ends and not
resolving until candidate-010's own `decided_at` -- the accepted
Visit-Continuity quiet-period/episode-boundary design extending one
Visit's decision horizon while nearby, potentially-related activity is
still being arbitrated. Not a new defect; the same mechanism v9 already
named as the deliberate cost of avoiding fragmentation, observed here
stretching into minutes because two encounters happened to be temporally
close at the same physical location.

## Supporting reconstructed evidence

**v11 (2026-09-02) -- SUPPORTING / RECONSTRUCTED, not equivalent to an
intact originally-measured cohort.** v11's own original accepted report
explicitly declined to compute true latency at all ("bounded archaeology
... preserved in the merged ledger for a future pass"). The figures below
exist only because Gate A Whole-Scene Budget & Remaining-Evidence
Correction v1 (2026-09-05) later performed an **offline scratch
reanalysis** of v11's already-archived raw ledger: a dropped
`clock_calibration_required` metadata flag (an artifact of v11's own ad
hoc pre-standard-tooling merge script) was restored **in a scratch working
copy only** -- the committed archive under `data/field-acceptance/` was
never modified, and no production code changed -- and the same unmodified
`run_gate_a_measurement_accounting.py` was re-run against it:

| Cohort | Valid n | Median | p90 | p95 | Max | Status |
|---|---|---|---|---|---|---|
| v11 (reconstructed) | 23 | 115,699ms (115.7s) | 318,469ms (318.5s) | 524,369ms (524.4s) | **865,199ms (865.2s / 14.42min)** | Newly recovered by the correction milestone, not part of v11's own original accepted findings |

This is explicitly disclosed, by the correction milestone itself, as
**not independently visually re-verified against footage** the way v11's
own original live findings were -- carried forward here with the identical
caveat, not upgraded to intact-cohort status by repetition. v11's 865.2s
max has no individually-named causal trace (unlike v9's candidate-027 or
v10's candidate-010) -- only the same general Visit-Continuity/episode-
boundary mechanism attribution, without identifying which of the 23
admitted Visits produced it. A real, unreconciled minor discrepancy exists
in v11's own source report (its "True latency" paragraph says "24
candidate-visit `decided_at` timestamps" while every other count in the
same report, including its own False-Visits table, is 23) -- noted here,
not silently smoothed over; the correction's n=23 matches the
23-count used everywhere else in v11's report.

No cohort anywhere (intact or reconstructed) reports p75/IQR.

**Minimum sample-size/stopping-rule precedent, checked:** no prior Gate A
milestone states a numeric minimum valid-sample count or stopping rule
anywhere in the archaeology (only the qualitative, unquantified "Gate A's
own standing rule requires cross-session convergence"). The correction
milestone's own "smallest sufficient remaining Gate A proof" section
recommends "a single additional representative daylight session of
ordinary length ... since a materially shorter session risks too few
admitted Visits" -- directionally consistent with, but not identical to,
this milestone's own governing brief's ≥12-samples/≥45-minutes default,
which is therefore used as specified (no better-justified numeric prior
exists to substitute).

## Live tranche duration / stopping rule

**Session:** `stream-92151f510f5a`, started `2026-09-05T23:42:59.005556Z`,
`user_stopped` at `2026-09-06T00:26:41Z` (stop-finalization confirmed
settled by `2026-09-06T00:27:00Z`, no additional candidate rescued).
**Duration: 43.7 minutes** (2,619 real seconds; the counterfactual ledger's
own `session_last_offset_ms: 2,610,761` = 43.5 minutes independently
confirms this).

**Why this stopped before the preferred 45-minute floor, and before the
75-minute maximum, classified honestly as a deliberate early stop for
non-representative conditions, not a premature abandonment:** the session
was started at dusk (19:42 EDT) rather than midday -- a real session
-timing gap, the same category of gap prior Gate A cohorts (2026-08-19,
2026-08-20, the 2026-08-26 multi-camera attempt) have each independently
hit and disclosed, never a product defect. Bucketed raw-detection counts
from this session's own merged ledger make the light-driven collapse
directly visible and quantified, not merely asserted (both `vehicle`- and
`animal`-class raw detections collapse together, confirming a lighting
effect on the whole scene, not a wildlife-specific change):

| Window | `vehicle` detections | `animal` detections |
|---|---|---|
| 0-3min | 889 | 2 |
| 3-6min | 869 | 8 |
| 6-9min | 887 | 23 |
| 9-12min | 822 | 59 |
| 12-15min | 731 | 85 |
| 15-18min | 450 | 4 |
| 18-21min | 218 | 5 |
| 21-24min | 12 | 1 |

By minute ~24 the scene was, in the user's own real-time confirmation
mid-session, fully dark. The one admission (below) landed at minute ~14,
inside the pre-collapse window; no further admission occurred across the
next ~29.7 minutes of monitoring despite continued, real (if sparse)
tracked activity (see "Regression sanity," below, for the full
`candidates_suppressed` breakdown). Given (a) the light-driven collapse
was already complete and quantitatively confirmed by minute ~24, (b) the
user directly confirmed full darkness in real time, and (c) grinding
through the remaining ~20-51 minutes to reach the 45- or 75-minute
thresholds would monitor night conditions Gate A's own accepted evidence
body has never treated as representative (every accepted daylight cohort
to date -- v5 through v14 -- ran during actual daylight), continuing was
judged not to serve the bounded question this tranche exists to answer.
This is judged equivalent in substance to "conditions are not
representative: do readiness only and stop Classification B" (§9 of the
governing brief) applied mid-session rather than only as a pre-session
gate, not a deviation from it.

**Valid latency samples obtained: n=1** (see "Raw latency samples,"
below) -- short of the ≥12 threshold by a wide margin. Per the governing
brief's own stopping rule, this is an honest **Classification B:
insufficient natural activity**, root-caused precisely (session-start
timing relative to sunset), not a product defect and not evidence that
the true-latency mechanism itself is unhealthy (RTT calibration, ledger
completeness, and the one sample actually obtained are all fully valid --
see below).

## Ledger completeness

`field_acceptance_ledger_snapshot.py reconcile` (5 periodic checkpoints at
the established 600s/10min cadence, plus one final corrective fetch taken
with the engine still live immediately pre-stop, matching the standing
convention since v9):

| Artifact | Status | Completeness | Detail |
|---|---|---|---|
| `raw_detections` | **COMPLETE** | 100% | 6,317/6,317 unique records, zero gaps |
| `track_generations` | **COMPLETE** | 100% | 50/50 unique records, zero gaps |
| `proposal_outcomes` | **COMPLETE** | 100% | 31/31 unique decision events (11 distinct proposals), zero gaps |

`overall_status: COMPLETE`. No silent partial reconciliation anywhere in
this session's own ledger.

## Raw latency samples

Computed by the unmodified `run_gate_a_measurement_accounting.py` against
the reconciled merged ledger (`data/field-acceptance/2026-09-05-gate-a-true-latency-tail-closure-v1/accounting/latency-report.json`):

| Visit | Proposal | T0 (normalized) | T5 (`decided_at`) | Latency | Clock state | Fallback |
|---|---|---|---|---|---|---|
| `visit-observation-candidate-003` | `visit-episode:23a157444501262b098ed805` | `2026-09-05 23:52:30.576495Z` (±8.7ms) | `2026-09-05 23:56:59.867651Z` | **269,291.156ms (269.29s)** | `normalized` (RTT-bounded) | No |

That is the complete sample set (n=1). `clock_calibration_state:
"normalized"` throughout the session (238/238 RTT-bounded batches
calibrated, 0 `insufficient_samples`, 0 `inconsistent_samples`, 0 clock
jumps) -- the calibration mechanism itself performed perfectly; the
shortfall is exclusively in the count of qualifying real-world encounters,
not measurement validity.

## Distribution

With n=1, no median/p90/IQR distribution can be honestly computed or is
reported -- median = p90 = p95 = max = mean = 269,291.156ms is a
mechanical artifact of n=1, not a real distribution, and must not be read
as a 5th converging data point. Attempted n (candidate visits created):
1. Valid n: 1. Invalid n: 0. No exclusion reasons apply because nothing
was excluded -- the single sample is itself the entire admitted-Visit
population this session produced.

## Slow-tail root-cause analysis

269.29s does not cross this milestone's own ">300 seconds" deep-trace
threshold, but was traced anyway since it is this session's only sample.
T0 (`23:52:30.58Z`) exactly matches the start of a chain of consecutive,
low-confidence (`max_confidence` 0.10-0.29 throughout, never reaching the
tracker's own 0.7 "strong" threshold) track generations at one fixed
image-space location (bounding box centered ~[0.43-0.47, 0.52-0.54]),
continuously re-triggering (`maximum_unsupported_duration`/
`insufficient_support` terminal reasons chaining directly into the next
generation's start) from `23:52:30` through past `23:58:00` -- the
Visit-Continuity design correctly treated this as one sustained episode
rather than fragmenting it, and `decided_at` (`23:56:59.87`) lands within
that continuous window, consistent with the same quiet-period/decision
-horizon mechanism v9/v10/v11 each already named, not a new mechanism.

**Independent-recorder cross-check (the more important finding):** three
frames spanning this exact tracked window (offsets 595s, 618s, 710s --
`data/field-acceptance/2026-09-05-gate-a-true-latency-tail-closure-v1/evidence-frames/`)
were cropped to the tracked bounding box's own image region. All three
show an identical, unmoving dark shape at the same feeder perch position
-- no visible postural change, head movement, or departure across a
~2-minute span of an episode that itself lasted 5+ minutes. A live bird
would not be expected to hold one exact pixel position that long. This is
most consistent with a **static feeder component** (a perch bar or
feeding-port fitting) being marginally, intermittently misclassified as
`animal` under difficult dusk lighting, not a real bird -- disclosed
honestly rather than counted as a clean encounter.

This is not a new correctness defect and is not being "fixed" here
(no-product-changes scope, §4 of the governing brief): production
admission is confidence-blind by prior, measured, accepted decision (see
`roadmap.md` "Numeric release budgets" -- confidence-gated admission was
swept and explicitly not adopted, because no threshold value clears both
false-positive-rejection and real-animal-recall together), so admitting a
low-confidence, sustained detection here is existing, unchanged, accepted
behavior meeting a genuinely hard low-light input, not a new bug. The
system did **not** compound this with a confidently wrong species label:
`automatic_identification` returned `{"status": "no_result", "message":
"Automatic identification completed without a suggestion."}` -- correct,
doctrine-consistent abstention (see "Measured, Inferred, and Reviewed" in
`product-doctrine.md`) even on a likely-false Visit.

**Classification (per §16's taxonomy): B -- known bounded product
behavior** (confidence-blind admission, an already-measured and accepted
design point, operating at its known edge under unusually low light) for
the admission itself; the tail *latency* mechanism's own delay is **A --
expected biological/session-assembly behavior** (the same Visit
-Continuity quiet-period/decision-horizon design already named by every
prior cohort). Neither is **C -- pathological correctness defect**: this
is a hard-input edge case of intentional, already-accepted design
choices, not new broken code, and Gate A does not move to `OPEN --
CORRECTNESS DEFECT` on the strength of it. It is disclosed as a real,
concrete instance worth remembering (a static-object low-light false
-Visit is a genuinely new failure shape not previously named in this
project's own false-Visit taxonomy), not swept aside because this
milestone's scope is measurement, not fixing.

## Cross-cohort latency comparison

| Cohort | n | Median | p90 | Max | Status |
|---|---|---|---|---|---|
| v9 | 24 | 111.8s | 173.9s | 307.4s | Intact, live-measured |
| v10 | 11 | 103.9s | 183.3s | **742.3s** | Intact, live-measured |
| v11 | 23 | 115.7s | 318.5s | **865.2s** | Supporting/reconstructed (offline scratch reanalysis, not visually re-verified) |
| v14 | 14 | 82.9s | 235.5s | 261.2s | Intact, live-measured |
| **This milestone** | **1** | -- | -- | 269.3s | **Insufficient (n=1), likely-false-Visit sample -- not a qualifying data point** |

This milestone's single sample's raw latency value (269.3s) happens to
fall inside the already-established tail range (261.2s-865.2s) and close
to v14's own max -- mildly consistent with, not contradictory to, prior
evidence -- but n=1 cannot move the convergence question in either
direction, and the sample's own doubtful biological validity means it
should not be blended into the accepted 4-cohort body above even as a
labeled fifth point. **The tail remains exactly as unconverged as Gate A
Whole-Scene Budget & Remaining-Evidence Correction v1 left it**: four
sized cohorts, maxima spanning 261.2-865.2 seconds, no fifth qualifying
sample added by this milestone.

## Proposed latency budget

**MORE EVIDENCE REQUIRED -- unchanged from the accepted pre-milestone
state.** This milestone does not add a qualifying sample to the tail
distribution and therefore cannot responsibly move median/p90/max
readiness in either direction. Per the governing brief's own explicit
instruction ("Do not ask: what number lets everything pass?"), no budget
is adopted on the strength of a single doubtful sample. The
already-accepted framing stands: median is informative and reasonably
stable across four cohorts (~83-116s), while the tail (four sized maxima,
261.2-865.2s, no fifth added) remains a genuine, unresolved measurement
gap -- not a non-blocking footnote, and not yet supportive of a hard
maximum, a p90 budget, or a "median-only" release posture.

## Regression sanity

Not a full Gate A campaign; the following were checked directly against
this session's own real evidence:

- **Visits are being admitted:** yes -- 1 of 1 encounter clusters with any
  admission (see the encounter-funnel report); the admission pathway
  itself is confirmed live and functional on this exact build.
- **No evidence-capture regression:** confirmed -- `evidence_burst_requests:
  59`, `evidence_burst_captures: 59`, `evidence_burst_failures: 0`,
  `evidence_burst_stale: 0`, `evidence_profile_reconciliation_count: 1`
  (the same benign warm-promotion self-heal v14 documented, immediately
  after pairing, zero unhealed failures afterward).
- **No proposal ledger regression:** confirmed -- 100%/100%/100%
  reconciliation across all three artifact types (see "Ledger
  completeness," above).
- **Zero obvious duplicate storm:** confirmed -- `duplicate_visit_cluster_
  count=0`; fragmentation accounting reports 1 denominator unit,
  `correctly_represented=1`, `fragmented=0`, `duplicate=0`,
  `needs_review_unit_ids: 0`.
- **No obvious false-Visit flood:** no flood -- exactly one admitted
  Visit total, itself disclosed above as likely-false rather than hidden;
  one questionable Visit in a 43.7-minute session is not a flood by any
  reading, though its likely falseness is itself a real, disclosed
  finding (see "Slow-tail root-cause analysis," above).
- **Monitoring healthy:** confirmed throughout -- `state: "observing"`
  from `23:43:01Z` to the user-initiated stop, camera connected the whole
  time, `last_healthy_frame_at` current at the moment of stop, RTT
  calibration 238/238 batches valid with zero clock jumps across the full
  session.
- **Clean stop:** confirmed -- `user_stopped`, `stop_finalization_pending`
  observed `true` then settled `false`/absent with zero additional
  candidates rescued (an honest outcome of the mechanism, not a failure
  of it), process verified actually stopped by
  `deploy_windows_dev.py --stop` and `field_acceptance_instance_lifecycle.py
  complete`.

No major correctness defect was found. The one notable finding (a static
-object low-light false-Visit, above) is disclosed as a real observation,
not a pathological defect -- Gate A does not move to `OPEN --
CORRECTNESS DEFECT` on its strength (see "Slow-tail root-cause analysis"
for the full reasoning). Nothing here was patched live, per the governing
brief's own instruction.

**Worktree safety, reconfirmed at session close:** `git log -1` still
reports `bf7ee89`, unmoved, throughout this entire live session; the only
working-tree changes present are this milestone's own (the report file,
the `using-mockingbird.md` limitation-disclosure edit, and the
already-explained recurring untracked `uv.lock` side effect of `uv run`
invocations in this shared worktree -- removed before commit, per
standing practice). The one peer session listed "interactive" at this
milestone's own start produced no observable write in this repository at
any point across the full session.

## Recall limitation disclosure

Carried forward exactly as supplied by this milestone's own governing
authorization (see "Global recall release decision," above) -- not
re-derived, re-litigated, or tightened:

**WHOLE-SCENE RECALL: ACCEPTED KNOWN LIMITATION -- NO NUMERIC RECALL
FLOOR YET.** v12 87.5% conservative; v14 64.7% conservative; v14 61.1%
broader. The ambiguous-boundary sustained/crowded mechanism remains fully
disclosed, unremoved from the denominator, and this milestone's own live
session directly observed the identical mechanism firing twice in real
time (`visit-episode:6d939d3196636bce7f1d2e74` and
`visit-episode:9ab3923349e8d3452dcccf62`, both `blocked_ambiguous_
boundary`) -- a live, current-build reconfirmation that the mechanism is
still exactly as previously characterized, not a new or different
behavior.

## User-facing limitation truth

Checked `docs/using-mockingbird.md` directly: it did not yet convey the
ambiguous-boundary/crowded-activity limitation anywhere (confirmed by a
direct text search before editing). Added a short, factual paragraph to
its existing "Review" section (the natural place a user already learns
how a Visit is created and reviewed), in the same plain, non-alarming,
explain-why tone the document's existing BirdNET-licensing disclosure
already uses:

> During an unusually busy, continuous stretch of activity -- several
> birds arriving at the same spot in close succession -- MockingBird can
> sometimes miss creating a separate Visit for every individual involved.
> It would rather quietly skip one than guess at where one bird ends and
> another begins and risk stitching two different birds together into one
> wrong Visit. This only affects unusually crowded moments at a single
> spot; ordinary, everyday activity is unaffected.

No internal terms (`blocked_ambiguous_boundary`, "arbitration,"
"denominator") appear in the user-facing text. This is the only content
change this milestone makes to product documentation; no application code
changed.

## Eight-metric Gate A final state

| # | Metric | State | Budget |
|---|---|---|---|
| 1 | End-to-end Visit recall | **ACCEPTED KNOWN LIMITATION -- resolved this milestone** (no longer "release decision required": the decision has been made) | No numeric floor; v12 87.5% / v14 64.7% conservative, v14 61.1% broader remain the honest reported range |
| 2 | Ambiguous-boundary sustained/crowded mechanism | Root-caused, safe (omission-only), disclosed launch limitation | N/A (not a separate budget; its cost stays inside #1) |
| 3 | Maximum confirmed false-Visit rate (ordinary scenes) | READY FOR RELEASE BUDGET, unchanged | ≤15% |
| 4 | Maximum confirmed fragmentation rate | READY FOR RELEASE BUDGET, unchanged | ≤5% |
| 5 | Maximum confirmed duplicate-Visit rate | READY FOR RELEASE BUDGET, unchanged | ≤2% |
| 6 | Minimum useful-evidence rate | READY FOR RELEASE BUDGET, unchanged | ≥85% |
| 7 | Maximum evidence-loss (distinct-proposal basis) | READY FOR RELEASE BUDGET, unchanged (closed by the immediately-prior milestone) | ≤15% |
| 8 | True capture-to-visible latency | **MORE EVIDENCE REQUIRED, unchanged** -- this milestone's own live tranche did not add a qualifying sample | No budget adopted; median informative (~83-116s), tail unconverged (261.2-865.2s across 4 sized cohorts) |
| 9 | Minimum monitoring coverage | READY FOR RELEASE BUDGET, unchanged | ≥97% |

(Nine rows because recall's decision and its ambiguous-boundary mechanism
are listed separately, matching how the immediately-prior correction
milestone itself separated them; the "eight-metric" framing in the
governing brief treats #1/#2 as one dimension, consistent with "six of
eight release dimensions... plus recall plus latency" arithmetic used
throughout this record.)

## Gate A decision

**Gate A = OPEN -- TRUE LATENCY TAIL EVIDENCE REMAINS.**

Recall's release-decision blocker is now reconciled (accepted known
limitation, no numeric floor required). Six of the eight/nine dimensions
remain genuinely ready for a release budget. **The sole remaining Gate A
blocker is true capture-to-visible latency's own unconverged tail** --
exactly the gap this milestone was chartered to close, and exactly the
gap it did not close: the live tranche's own natural activity fell short
of the sample threshold (n=1 of a needed ≥12) for a fully disclosed,
honestly root-caused reason (a dusk-timed session start), and the one
sample obtained is itself of doubtful biological validity and is not
counted toward convergence. Gate A does not pass on six of eight ready
dimensions alone when the governing brief's own explicit central task
(the latency tail) remains unresolved.

## Lane R state

**Lane R: OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS**
(narrowed from the immediately-prior "OPEN -- RELEASE-CRITICAL -- RELEASE
DECISION REQUIRED": the release-decision half is now resolved by this
milestone's own carried-forward global authorization; only the
latency-tail half remains open).

## Remaining global release queue

Carried forward, not re-opened or re-litigated, per the governing brief's
own explicit instruction not to resurrect historical OPEN states already
closed by later accepted work, and not to self-authorize the items below:

- **Source-code `LICENSE` owner decision** -- still genuinely open (Lane
  P); MIT recommended, two alternatives named, one exact owner-facing
  question, unresolved by any engineering milestone including this one.
- **BirdNET commercial-adjacent legal review** -- still genuinely
  unresolved (§2): whether an individual user's private, non-commercial
  MockingBird+BirdNET use could ever be implicated merely because the
  surrounding open-source project accepts donations or sells optional
  paid support. Acoustic itself remains ACCEPTED -- RELEASE-READY
  OPTIONAL regardless; this caveat does not block that status, only a
  future commercial-adjacent distribution decision.
- **Gate G -- External Pre-Release Acceptance** -- not started, not
  scoped; not authorized by this milestone.
- **Lane S -- Actual Final Release Hardening** -- comes after Gate G;
  not started; not authorized by this milestone.
- **Lane B -- Remote / Intermittent-WAN Field Productization** -- PARTIAL,
  after-release unless a new core dependency appears; not a release
  blocker; unchanged by this milestone.
- **Lane K -- Ecosystem / Provider Integrations** -- DECISION CLOSED
  (2026-09-03): dedicated provider integrations deferred pending evidence,
  not required for launch. Cited for completeness per its latest accepted
  scheduler state, not reopened.
- **True capture-to-visible latency tail** -- the one Gate A-blocking
  item this milestone leaves open (see "Gate A decision," above). The
  smallest sufficient next step, per the immediately-prior correction
  milestone's own still-valid reasoning (not re-derived here, since this
  milestone found no new information changing it): one more
  already-otherwise-motivated representative *daylight* session (not a
  latency-dedicated cohort) run for its own reasons would add a genuine
  5th qualifying sample; a session deliberately scheduled to start with
  at least ~75 minutes of remaining daylight would avoid repeating this
  milestone's own dusk-timing gap.

This milestone does not authorize any of the above, does not select a
next development milestone, and returns authorization to **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**.

## Cleanup

- Live Observation session stopped (`user_stopped`), stop-finalization
  settled, zero residual pending work.
- Windows-hosted process verified stopped (`deploy_windows_dev.py
  --dev-root ... --stop`: "Stopped bf7ee89 (verified)").
- Instance lifecycle: `active` -> `completed` -> `archived` against the
  evidence bundle at
  `data/field-acceptance/2026-09-05-gate-a-true-latency-tail-closure-v1/`
  (merged ledger, accounting reports, final status snapshot, evidence
  frames, README). **Not destroyed**, per standing practice (disposable
  but retained, matching every prior cohort's own disposition).
- Camera Node pairing: left paired to this archived instance (matching
  v13/v14's own established precedent) -- no destructive unpairing
  performed. Backup of the pre-reset pairing state preserved on the Node
  at `pairing.json.pre-gate-a-latency-tail-v1-reset.bak`.
- Field-acceptance bearer credential and locally-generated Administrator
  password: not explicitly revoked (the instance itself is stopped, not
  running, so neither is currently exercisable); the credential's own 4h
  TTL expires it automatically. Local plaintext copies of both, and of
  the one-time Camera Node credential read from the instance database for
  the compatibility check, were deleted from this session's own scratch
  directory at cleanup.
- **Not done, disclosed rather than silently skipped:** the 18.5GB
  disk-reclaim opportunity identified at session start (two already
  -archived, `SAFE_TO_RECLAIM` dev-roots, v13 and v14) remains unreclaimed
  -- the destructive cleanup action was refused by this session's own
  permission classifier and was not essential to proceed, so it was left
  for an operator to run explicitly:
  `field_acceptance_instance_lifecycle.py cleanup --dev-root <path> --destroy`.
- Working tree: `uv.lock` (the established recurring `uv run` side effect)
  removed before commit; the seven preserved untracked files reconfirmed
  present and untouched; only this milestone's own report and
  `using-mockingbird.md` edit committed.
- No production code changed. No Core run required or performed (docs
  -only change, per the governing brief's own §23).

## Decision

**B**

Real, honest field evidence was collected end-to-end with a fully valid
RTT-calibration and ledger-completeness chain, but the live tranche itself
produced only n=1 candidate latency sample (of a required ≥12) for a
disclosed, root-caused, non-defect reason (a dusk-timed session start
overtaken by real darkness, confirmed in real time), and that one sample
is independently judged likely-not-a-real-bird on direct visual review --
so it is correctly not counted toward tail convergence. The true-latency
tail therefore remains exactly where the prior milestone left it: **MORE
EVIDENCE REQUIRED**, unconverged across four sized cohorts (261.2-865.2s).
The recall side of Gate A **is** resolved this milestone (the supplied
global decision is now carried into the scheduler), narrowing Gate A's
remaining blocker to latency alone -- real, if partial, progress -- but
this milestone's own central chartered task (closing the latency-tail
gap) was not achieved, and no amount of correct process executes around
that fact. No correctness defect was found; no production code changed;
the one live-tranche finding (a static-object low-light false-Visit) is
disclosed as new information, not hidden and not treated as
release-blocking on its own.
