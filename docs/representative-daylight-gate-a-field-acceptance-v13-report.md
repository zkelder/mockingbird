# Representative Daylight Gate A Field Acceptance v13: Intact-Ledger Re-Proof & Budget Convergence

Session date: 2026-09-04. Branch `main`. Starting HEAD `39a8fdc` (git HEAD;
release-execution-state.md's own internal "Accepted HEAD" bullet was found
stale at `e57c911` — see "Starting state" below). Schema v58 (unchanged).

## Starting state

Verified against `docs/release-execution-state.md`, `docs/product-doctrine.md`,
and `docs/roadmap.md` before any action:

- Branch `main`, git HEAD `39a8fdcc87a2c7d5e8b3307b8933c4eac893fb55` — matched
  exactly (`git rev-parse HEAD`).
- Schema v58 (`CURRENT_DATABASE_SCHEMA_VERSION` in
  `src/mockingbird/storage/database.py`) — matched.
- Latest accepted milestone: Ambiguous-Boundary Real-Subject Recall
  Correctness v1, classification **B** — matched (§3 top entry, §6 Lane R
  tail entry).
- Lane G: `CLOSED — RELEASE-CRITICAL` — matched (§1 lines 68–70).
- Lane K: `DECISION CLOSED — DEDICATED PROVIDER INTEGRATIONS DEFERRED
  PENDING EVIDENCE; NOT REQUIRED FOR LAUNCH` — matched (§1 lines 110–112).
- Lane R / Gate A: **OPEN** — matched, reconfirmed by every entry through
  the Ambiguous-Boundary Real-Subject Recall Correctness v1 closure.
- Current authorization: `NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED` — matched (§3, restated after every subsequent entry). This
  milestone's own governing brief is the external reconciliation that
  authorizes this specific session.
- Not pushed — confirmed (`git log origin/main..HEAD`, +330 ahead, matches
  the brief's expectation).
- **One documentation-currency discrepancy found, not a state mismatch**:
  §1's own top-of-section "**Accepted HEAD:**" bullet (line 27) still reads
  `e57c911` (Authenticated Camera Node Golden-Path Capture & Preview
  Acceptance v1) — three further commits that changed production code
  (`3600e98` storage-preflight fix, `e672c87` all-alternate fix, `14322b3`
  dead-anchor fix) were never reflected there; each of those milestones was
  instead recorded only in §3/§6.R's own narrative chain. Every field the
  brief actually asked to verify (branch/HEAD/schema/milestone/
  classification/lane states/authorization/push-state) checks out exactly
  against git and against §3/§6/§13 directly, so this is not treated as a
  blocking discrepancy — corrected as part of this milestone's own §39
  reconciliation instead.

Gate A's real remaining dependency, reconstructed from §6.R (13-item list,
narrowed twice by the two most recent accepted fixes) plus the new
disclosed candidate fact from Ambiguous-Boundary Real-Subject Recall
Correctness v1: (1) never-strong single-generation confusor clearing
`blocked_ambiguous_boundary` then reaching the quality gate repeatedly; (2)
a second person-confound-free cohort confirming v12's 5.6% false-Visit
rate; (3) full-ledger-coverage automated fragmentation re-proof; (4) a
second independently-varied true-latency cohort; (5) a 3+-simultaneous
-subject cohort; (6) v7's two remaining ambiguous fragmentation units; (7)
the ~13 untraced v7 `blocked_missing_evidence` records; (8) same-frame
class-contradiction field effect on person-associated false Visits; (9)
further strong-confidence scene-artifact recurrence; (10) no whole-frame
human suppression of real birds; (11) scene-confusor participation incl.
corroboration-rejected counts; (12) [narrowed] a cohort with intact
full-session raw-ledger coverage — the tooling defect is fixed, this
evidence itself is still needed; (13) [narrowed] whether
`reject_no_identification_or_context`'s "vanish entirely" behavior for
brief-but-real encounters should be revisited — the one proven
same-frame-only-evidence mechanism behind it is fixed, but neither of
v12's own two named misses (37:12, 57:07) traced to that mechanism, so
full field re-confirmation still awaits this cohort. Plus the new
candidate fact: does the dead-anchor-promotion fix measurably change
recall/precision under real sustained activity, and does the
geometry-compatibility-tolerance question (v12's ~37:12 case's real,
unresolved cause) recur.

## Conditions

Checked before allocating a field instance, all confirmed real:

- **Daylight**: session start 15:25 EDT (2026-09-04); early-September Eastern
  sunset is comfortably after 19:00 EDT — hours of margin, no time pressure.
- **Reference Camera Node reachable**: `192.168.1.112:8787` healthy,
  `available_camera_count: 1` of `camera_count: 2`, `self_test.status:
  passed`, watchdog `consecutive_probe_failures: 0`.
- **Physical camera available**: `picamera2-camera-0`, `status: available`,
  evidence profiles up to 9248×6944.
- **Accepted Node build present**: unchanged from the prior accepted
  hardware-validation milestone; only the pairing state was touched this
  session (see below), never the Node's own software.
- **Native-Windows Host available**: `powershell.exe` smoke test passed.
- **GPU/detector available**: RTX 4060 Ti visible via `nvidia-smi.exe`
  (3358MiB/8188MiB used, 26% utilization baseline from ordinary desktop
  apps — this is the user's real daily-use machine, matching every prior
  cohort's own disclosed baseline).
- **Storage headroom**: see "Storage" section below.
- **No conflicting Observation**: nothing listening on port 8000, no
  `python*` process running, before this session's own deploy.
- **No unsafe pairing owner**: the Node's pairing was held by a stopped,
  credential-less leftover instance (`MockingBirdSnapshotToolingSmokeV1`,
  from the prior storage-preflight milestone's own real-hardware smoke
  proof) — resolved via the twice-precedented manual Node-side reset (see
  "Field lifecycle," below), with explicit user authorization sought and
  granted first, matching both prior precedents' own requirement for
  operator sign-off on this exact class of action.
- **No active writer**: confirmed at session start; unchanged throughout.

## Worktree safety

All 7 preserved untracked detector files reconfirmed present, byte-for-byte
matching `docs/release-execution-state.md` §13's own list, untouched:
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`. No other writer found in this
worktree.

## Build / compatibility / RTT

- Deployed fresh via `scripts/deploy_windows_dev.py --dev-root
  .../MockingBirdFieldAcceptanceV13` (no skip flags — full GPU+BioCLIP),
  with the independent acceptance recorder explicitly enabled via the
  dev-shell opt-in variables (`MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`,
  `_INTERVAL_MS=1000`, `_MAX_FRAMES=7200`, `_MAX_BYTES=4500000000`) —
  corrected mid-flight: the first deploy attempt was started without these
  set and was killed and restarted clean before any real session time was
  spent, once the gap was noticed. Deploy log: `DEPLOYED 39a8fdc`. BioCLIP
  species suggestions available.
- `field_acceptance_instance_lifecycle.py init`: `created_by_commit:
  39a8fdcc87a2c7d5e8b3307b8933c4eac893fb55`, `created_by_build_id:
  c78f052d48627f73`.
- `GET /api/product/instance`: `git_commit:
  39a8fdcc87a2c7d5e8b3307b8933c4eac893fb55` (exact accepted-HEAD match —
  the authoritative identity check, per standing project convention that
  this beats any deploy helper's own report). `GET /api/product/health`:
  `database_schema_version: 58`, `ready: true`.
- `check_camera_node_compatibility.py --profile ordinary_monitoring`:
  `state: compatible`, `camera_available: true`.
- `check_camera_node_compatibility.py --profile field_acceptance`: `state:
  compatible`; **real RTT-bounded calibration reached `calibrated`**: 5/5
  valid samples, `offset_ms 6.744 [1.107, 12.38]`, `uncertainty_ms 5.637`,
  `rtt_ms 15.154`, `node_processing_ms 3.875`, `clock_jump_detected:
  false`. (One real credential-plumbing correction along the way: the
  `pair` response's own `pairing_token` field is a Host-side setup-flow
  handoff token, not the Node's actual persisted authentication credential
  — the real `node_credential` had to be read once, directly, from the
  fresh instance's own local SQLite `source_provider_configurations` table,
  matching the exact precedented pattern the Authenticated Camera Node
  Golden-Path Capture & Preview Acceptance v1 report's own "Credential
  safety" section already documents: read once into a short-lived local
  variable, used, never persisted beyond this session's own scratch
  files.)
- Real production stack confirmed live in `observation/status`'s own
  advanced payload at Observation start: `provider_key:
  frame-driven-onnx-cuda`, `detector_provider_key: onnx-cuda`,
  `cuda_available: true`, `selected_execution_providers:
  [CUDAExecutionProvider, CPUExecutionProvider]`, model `md-v5a` /
  `MDv5a.0.1-onnx-opset18`, `score_threshold: 0.1`, `nms_iou_threshold:
  0.45` — byte-identical to the accepted production configuration.

## Field lifecycle

- `init` → `preflight` → `deploy` → `run` executed via the accepted
  tooling (`field_acceptance_instance_lifecycle.py`,
  `deploy_windows_dev.py`, `field_acceptance_client.py`,
  `manage_field_acceptance_credential.py`) — no ad hoc bypass.
- **Node pairing reset (user-authorized, twice-precedented, non-destructive).**
  The Node's pairing was held by `MockingBirdSnapshotToolingSmokeV1`, a
  stopped instance whose Administrator credential was never retained (by
  design — locally generated, discarded with the instance). With explicit
  user authorization: backed up `pairing.json` →
  `pairing.json.pre-v13-reset.bak` on the Node, stopped
  `mockingbird-camera-node.service`, removed `pairing.json`, restarted.
  `boot_id` (`4239527b-5622-425c-bed1-ae3074e191dd`) unchanged across the
  reset, confirming it touched only pairing/Host-binding state. Fresh
  one-time code consumed within its 10-minute TTL.
- Administrator bootstrapped via `POST /api/setup/administrator`
  (`field-acceptance-v13-admin`, locally-generated password, never
  user-supplied). Field Acceptance Operator credential minted via `POST
  /api/admin/field-acceptance-credentials` (6h TTL) and used for
  `observation/start` per the credential's own least-privilege allowlist.
- Pairing: `POST /api/camera-nodes/pair` → `POST /api/camera-setup/complete`
  (real `picamera2-camera-0`, one "Yard" Zone covering the full frame,
  every monitoring-policy field left at its inherited default — activity
  sensitivity `low`, `minimum_sustained_activity_seconds: 8`,
  `quiet_period_seconds: 60`, `maximum_visit_duration_seconds: 480`,
  `maximum_evidence_frames: 2` — nothing tuned). Resulting Stream:
  `stream-9766fe6bf0b0` ("Reference Pi Camera V13"), Source:
  `source-9766fe6bf0b0`.
- `GET /api/streams` confirmed exactly 2 Streams: the real one above, plus
  the unrelated seeded demo Stream (`stream-backyard-feeder` /
  `source-backyard-demo`) — ignored throughout, matching every prior
  cohort's own precedent.
- Storage reclamation (user-approved): two prior disposable instances,
  independently confirmed `SAFE_TO_RECLAIM` by the lifecycle tool's own
  fresh re-verification (`MockingBirdFieldAcceptanceV12`, 8.8GB — evidence
  already archived into
  `data/field-acceptance/2026-09-03-gate-a-v12-precision-recall-budget-convergence/`,
  verified present before reclaiming; `MockingBirdSnapshotToolingSmokeV1`,
  4.4GB — same, archived into
  `data/field-acceptance/2026-09-04-evidence-integrity-storage-preflight-correctness-v1-smoke-proof/`),
  reclaimed via `cleanup --destroy`, raising free space from ~11.3GB to
  ~25.7GB before deploying.

## Session duration

- Observation started `2026-09-04T19:25:22.687238Z` (15:25:22 EDT), stopped
  `2026-09-04T21:07:10.994446Z` (17:07:10 EDT) — **101.8 minutes**
  (`session_last_offset_ms: 6,081,819`), within the 90–105 minute target
  band. `stopped_reason: "user_stopped"`, at a deliberate operator decision
  once the target duration was reached — not cut short by any fault, and
  not extended to manufacture an encounter (none was needed; real activity
  was already substantial — see Recall, below).
- `stop_finalization_pending: true` observed immediately after the stop
  call, resolved to `state: "stopped"`, `observing: false` within ~2.3
  seconds — clean stop-finalization, no residue, matching the accepted
  contract.
- Real production stack confirmed live throughout (see Build/compatibility/RTT):
  `md-v5a` / `MDv5a.0.1-onnx-opset18`, `score_threshold: 0.1`,
  `nms_iou_threshold: 0.45`, `onnx-cuda`/CUDA, byte-identical to doctrine —
  untouched throughout, confirmed unchanged at every health checkpoint.

## Ledger integrity

**This cohort used the accepted committed snapshot tooling throughout —
no ad hoc per-session script.** `field_acceptance_ledger_snapshot.py
collect` ran detached (`Start-Process`, immune to any of my own WSL-side
tool timeouts) for the full session at `--interval-seconds 300`,
producing 21 checkpoints (`checkpoint-0000.json` … `checkpoint-0020.json`,
the last one landing exactly at the stop moment), plus one final
corrective `observation_counterfactual(start_offset_ms=0,
end_offset_ms=8000000)` fetch taken while the engine was still live,
seconds before the stop call — matching the v9–v12 precedent exactly.
`reconcile` was then run against all 21 checkpoints plus the final fetch.

Per-artifact reconciliation result:

| artifact | earliest recovered offset | latest recovered offset | unique recovered | final `recorded_count` | completeness | status |
|---|---|---|---|---|---|---|
| `raw_detections` | 0ms | 6,081,263ms | 35,518 | 35,518 | **100.0%** | `PARTIAL` — one real but trivial ~556ms uncovered tail window (`[6081263, 6081819]`), zero records actually missing |
| `track_generations` | 0ms (23,813ms first real track) | 6,081,263ms | 434 | 434 | **100.0%** | `PARTIAL` — same trivial tail window plus a `[0, 28883]` window with no real activity in it (0ms→23,813ms genuinely predates the first track), zero records actually missing |
| `proposal_outcomes` | 117,398ms | 5,980,520ms | 156 | 350 (decision-events; 156 unique `proposal_id`s reach a terminal-or-pending state at all) | **44.6%** by raw decision-event count | `PARTIAL` |

**The first two rows are effectively COMPLETE** — the tool's own
interval-coverage check (never rubber-stamping `COMPLETE` merely because
counts match) correctly flagged a technically-uncovered window, but the
record count itself is exact (0 missing) and the uncovered window is a
sub-second-to-single-digit-second artifact of exactly the kind the
Field Acceptance Evidence Integrity & Storage Preflight Correctness v1
smoke proof already characterized and disclosed as an accepted, harmless
edge case (`session_last_offset_ms` advancing slightly past the last
individually-recorded event between the final fetch and session-state
serialization) — not a real gap, and not this cohort's own governing
concern.

**The third row is real and requires honest analysis, not
hand-waving.** 194 of 350 raw `proposal_outcome` decision-events were
never captured by any periodic snapshot or the final fetch. Investigated
directly, not assumed: every one of the 156 recovered records is a
**distinct `proposal_id`** — zero proposals have more than one recovered
decision-event. Cross-referencing against the live session's own final
cumulative counters (`proposals_observed: 350`, exactly matching
`recorded_count` above) confirms the ledger's own proposal-outcome
retention evicts *by count* well before 60 minutes elapse under this
session's own decision-event volume (350 distinct-`(proposal_id,
decided_at)` events, versus v12's 325 over a similar duration) — a
5-minute snapshot cadence is not, on its own, guaranteed to outrun this
particular artifact's eviction rate when the proposal-outcome
decision-event rate itself is this high. **What is and is not affected**:
every recovered proposal's *own* history is exactly one record — meaning
this reconciliation gap is a genuine loss of *some `blocked_continuation_
pending` intermediate re-decisions and some terminal decisions for
proposals whose eventual outcome was never captured before eviction* —
not a loss of Visit-admission truth (see Recall, below: `candidates_
created: 0` is independently confirmed three ways — the live
`observation/status` counter throughout the session, the final
corrective fetch, and the merged ledger's own zero `outcome: "created"`
records — so this specific, most release-critical fact is not at risk
from this gap). Declared honestly: **this cohort's raw-ledger coverage is
COMPLETE for `raw_detections`/`track_generations` (for all metrics that
depend on them: recall-cluster reconstruction, geometry, confidence,
duration) and PARTIAL for the full decision-event history of
`proposal_outcomes`** (block-by-block causal attribution for every one of
the 194 uncaptured decision-events is not possible) — Gate A dependency
item (12) is **materially advanced, not fully closed**: the tooling
itself worked exactly as designed and caught its own gap precisely,
naming it by artifact and by record count, which is the entire point of
this milestone's own intact-ledger requirement — but a real, disclosed
residual limitation (proposal-outcome decision-event retention can
outpace a 5-minute cadence under high proposal churn) is newly identified
for a future session to consider tightening further (e.g.
`--interval-seconds 120` under similarly high-churn conditions).
- `scene_confusor_state`, `monitoring_status`: succeeded on every one of
  21 checkpoints, zero errors — unaffected by the above (separate code
  paths, matching v9–v12 precedent).
- **Independent recorder**: fully intact — 5,013 JPEG frames, manifest
  losslessly indexes every frame (sequence, offset, hash, captured_at).
  Frame-to-frame gap analysis below (see Monitoring).

## Independent denominator methodology

The reference Stream frames a residential front-yard view: a large tree
hosting a hanging blue tube feeder and a red hummingbird-style feeder,
with a street, driveways, and houses in the background — the same general
scene shape as prior cohorts, a new camera placement.

**Primary, fully independent pass**: geometric clustering of every raw
animal-class detection's bounding-box center (2,293 raw animal-class
detections, independent of any admission decision) identified two
persistent, session-long, low-confidence (max 0.1–0.19) static signatures
— one at frame-relative `(0.97, 0.52)` (169 detections, span 899.7s→6,027.8s)
and the existing person-class analogue at `(0.06, 0.48)` (147
person-class detections, span 591.7s→6,078.4s) — both excluded from the
wildlife denominator as static background objects, matching the
established pattern from v9/v12's own "second small static object"
findings; neither was staged. This pass also surfaced 33,003 vehicle-class
detections (92.9% of all raw detections) — real, distant, legitimately
parked/passing vehicles visible in the background streetscape, correctly
never treated as animal activity.

**Targeted expansion, guided by system telemetry** (both admitted *and*
rejected system proposals — not admitted-Visit timestamps, since there
were none): all 434 recovered animal-class `track_generations` were
clustered by a 60-second quiet-period rule (10 coarse clusters, several
spanning 15+ minutes of near-continuous activity) and, for finer
resolution, a 20-second quiet-period rule after excluding the one static
`(0.97, 0.52)` cluster (46 distinct visit-clusters; 23 reach ≥0.5
max-confidence, 23 reach the tracker's own ≥0.7 strong-detection
threshold at some point). The accepted automated tool
(`encounter_accounting.py`, via `run_gate_a_measurement_accounting.py`)
independently reconstructed **48 encounter clusters** from the same raw
ledger using its own methodology — closely corroborating the manual
46-cluster count.

**Visual ground truth**: 11 full-resolution independent-recorder frames
were inspected at representative offsets spanning the session (100s,
500s, 900s, 1500s, 2800–2819s [a 30s, 16-strong-detection track,
end-to-end confirmed], 3499s, 4200s, 4695s, 5300s, 5900s) — a real bird
is clearly, unambiguously visible at the feeder in the large majority of
these (6 of 10 sampled moments show a bird directly; the others fall in
lower-confidence or between-visit windows, consistent with the
recorder's own ~1.1–1.2s actual cadence sometimes missing a brief
perch). This is a genuinely active feeder session, not a quiet one and
not dominated by a static confusor at the real-activity location.

**Methodological caveat, disclosed rather than assumed away**: given the
density of activity (up to 154 track generations in one 60-second-rule
cluster), an exhaustive human review of every one of the 46–48
encounter-clusters' full frame spans was not performed within this
milestone's bounded effort — 11 representative timestamps were visually
confirmed, not all 46–48. The cluster-based counts below are therefore a
**methodologically-grounded but not exhaustively-verified** encounter
count, most likely an *undercount* of true individual bird visits (a
single quiet-period cluster spanning several minutes plausibly contains
more than one physical visit), consistent with this document's own
instruction not to manufacture false precision.

## Conservative denominator

**48 confirmed real-encounter clusters** (accepted automated tool's own
`encounter_accounting.py` reconstruction), of which **23 reach the
tracker's own strong-detection confidence threshold (≥0.7) or the tool's
own independent "strong_confidence"/"moderate_confidence" plausibility
classification** (15 strong + 4 moderate = 19 by the tool's own
plausibility field; 23 by `clusters_with_confirmed_tracking`) and were,
in addition, independently visually confirmed as real at every sampled
timestamp. The remaining ~25–29 clusters are weaker (never-confirmed
tracking, `plausibility: weak_confidence`) and are not force-classified
as confirmed real without their own visual check — reported honestly as
part of the broader denominator instead (below), not silently folded into
the conservative figure.

**Conservative confirmed denominator: 19 clusters** (the tool's own
`strong_confidence` + `moderate_confidence` plausibility buckets — the
most defensible subset given bounded-effort visual sampling directly
confirmed several of them and found no contrary evidence for any).

## Broader denominator

**Broader plausible/unconfirmed denominator: 48 clusters** (the accepted
tool's own full encounter-cluster reconstruction, including the 29
`weak_confidence` clusters not individually visually confirmed this
session). Never silently merged with the conservative figure above.

## Recall

Against the conservative confirmed denominator (19): **0/19 = 0.0%.**
Against the broader denominator (48): **0/48 = 0.0%.**
Against the accepted tool's own `admission_recall` field: **0.0%**
(`clusters_with_visit: 0` of `total_encounter_clusters: 48`).
`tracking_recall` (fraction of encounter clusters that ever reached a
*confirmed* track): **47.9%** (23/48). `proposal_recall` (fraction of
confirmed-tracking clusters that went on to form a viable proposal at
all): **100.0%** (23/23) — proposal *formation* was never the bottleneck.

**This is the worst recall result of any Gate A cohort to date, and it is
not ambiguous**: zero Visits were created this session
(`candidates_created: 0` throughout, confirmed identically by the live
session counter, the final corrective ledger fetch, and the merged
ledger's own zero `outcome: "created"` records), against a session this
report independently confirms — by direct visual inspection of the
fully-independent acceptance-recorder frames, not merely by trusting the
detector's own telemetry — was genuinely, substantially active with real
wildlife. See Reproduced defects, below, for the single, precisely
identified mechanism responsible.

## False Visits

**Not applicable — 0 Visits were admitted this session.** There is
nothing to review; the false-Visit-rate metric is undefined (0/0), not
0%. Do not read this as "perfect precision" — precision cannot be
evaluated at all when nothing was ever admitted.

## False-Visit cause breakdown

Not applicable, per the above — no admitted Visit exists in any cause
bucket.

## classifier_same_frame field re-proof

**Zero occurrences.** `reason: "...:same_frame_primary"` never appears
anywhere in the 156 recovered proposal-outcome records (grepped
exhaustively across the full merged ledger). Same-frame-only evidence
never became relevant this session because no proposal this session ever
progressed as far as the identification/context-evidence-role check the
fix touches — every one of them was intercepted earlier, at the
evidence-*existence* gate (see Reproduced defects). Per §13's own
instruction: reporting zero, honestly, not staged or manufactured. This
field re-proof therefore remains open for a future cohort whose proposals
reach the classifier-evidence stage at all.

## Dead-anchor field re-proof

**Exactly one `dead_anchor_promoted` occurrence.** `proposal_id
"visit-episode:73e776ed43ed3eede282def6"`, decided
`2026-09-04T21:03:24.915048Z` (offset 5,729,373–5,802,850ms, ~95.5–96.7
minutes in), promoting a 3-track-generation component
(`constituent_generation_ids`: 3 distinct `frame-track` generations).
**Outcome**: `blocked_missing_evidence` / `no_persistable_evidence_bytes`
— the promoted candidate was itself defeated by the same session-wide
evidence-persistence mechanism (see Reproduced defects) before its own
promotion could be evaluated on the merits. This means: the fix correctly
engaged (a real 3-member ambiguous component was resolved to a single
live chain rather than starving), but **this occurrence cannot answer
whether promotion recovers a genuine encounter, nor whether it risks
duplicate/fragmented Visits** — both questions are moot when the
promoted candidate never had a chance to be admitted for an unrelated
reason. Fallback-counter coherence: `fallback_attempted_count` (16) and
`fallback_exhausted_count` (16) are exactly equal throughout the session
(`fallback_admitted_count: 0`) — internally consistent, no orphaned or
double-counted chain.

## Ambiguous-boundary results

**Zero `blocked_ambiguous_boundary` outcomes recorded this session** —
a materially different shape from every prior cohort with this mechanism
in its own history. Investigated directly in the raw ledger: 16 distinct
ambiguous-component fallback chains were attempted this session (matching
`fallback_attempted_count`), spanning fallback positions 1 through 27 (one
chain alone tried at least 27 ranked members) — but *every* individual
member-admission attempt within every chain failed with `no_persistable_
evidence_bytes`, never with `blocked_ambiguous_boundary` itself. This is a
genuinely different failure shape from the v12 ~37:12 case (which was
blocked *at* arbitration, before any member was ever attempted): this
session's own arbitration mechanism *did* select and attempt real members,
walking the whole fallback chain each time — it is the shared,
session-wide evidence-persistence gap (see Reproduced defects) that
defeated every attempt regardless of rank. **The v12 ~37:12
geometry-compatibility-tolerance question did not recur in a form this
session can evaluate** — no candidate ever reached a state where that
specific tolerance could be the deciding factor, since none survived far
enough to be evaluated on geometry compatibility at all. No component
this session shows a genuinely-real subject being lost specifically to
the geometry-tolerance mechanism itself; preserved as evidence rather than
adjudicated further, per §15.

## Detector-corroboration misses

**Zero `reject_insufficient_detector_corroboration` occurrences this
session** — the mechanism never engaged, for the same reason as above:
every proposal died at the evidence-existence gate before reaching the
quality gate's corroboration check. No natural example of this specific
rejection reason exists this session to measure detection
count/confidence/generations against. Not reopened, per §16 — this is an
honest zero, not a defect in the corroboration rule itself.

## Independent-corroboration participation

Zero — see Detector-corroboration misses, above; the mechanism never had
an opportunity to fire.

## Scene-confusor participation

**Zero regions registered this session** (`regions_currently_adjusted:
0`, confirmed at every one of 21 checkpoints and at final stop) — the
first cohort in this project's history with a completely empty
scene-confusor table. Root cause, precisely: the scene-confusor touch
call fires only `on admit` and `on reject_insufficient_detector_
corroboration` (per the accepted mechanism's own documented contract, see
v12's own "Scene-confusor participation" section) — neither outcome ever
occurred this session (0 admits, 0 corroboration-rejections), so the
touch point structurally could not be reached, for any region, real or
confusor. This is category **D (never eligible to reach it)** for the
*entire session's* activity, not merely one novel location — a more
extreme instance of the same category v12 first documented for its own
"flag confusor," now applying session-wide because the upstream
evidence-existence gate intercepts everything even earlier than a
short/weak track's own `maximum_unsupported_duration` termination did in
v12.

## Same-frame class-conflict participation

No genuine human presence occurred this session in a way that could test
this — the only person-class detections (147, at the persistent static
`(0.06, 0.48)` location, confidence ≤0.348) never coincided spatially
with any animal-class detection above the mechanism's own overlap
threshold, and never reached a track generation. Zero same-frame
class-conflict exclusions fired; zero opportunity existed for one to be
needed.

## Strong-artifact results

**Did not recur.** No scene-confusor region reached the "strong-confidence
scene artifact" shape from prior cohorts (there are zero registered
regions at all, see above). The one persistent static signature this
session (`(0.97, 0.52)`) stayed uniformly low-confidence (max 0.19)
throughout — not a strong-confidence artifact.

## Real-positive controls

Despite zero admissions, the *tracking* layer itself provides clean,
naturally-occurring real-positive examples, independently visually
confirmed:

- **Strong, well-supported, sustained bird**: the offset 2,800,487–
  2,830,494ms track (30.0s, 16 strong detections, `max_confidence: 0.834`,
  terminal `maximum_duration`) — visually confirmed arriving in flight and
  then perched on the tube feeder across two sampled frames 19 seconds
  apart.
- **Brief/fast visits**: the large majority of the 46 finer-grained
  visit-clusters are short (median cluster span ~35s, many single-track
  clusters under 5s) — consistent with ordinary brief feeder touch-downs.
- **Feeder-adjacent activity**: essentially all real activity is
  concentrated at the tube-feeder/hanging-feeder apparatus itself,
  matching the classic feeder-camera shape from every prior cohort.
- **Weak/distant**: 29 of 46 finer clusters never reach
  `plausibility: strong_confidence` or a confirmed track — present in the
  raw ledger but not independently visually confirmed this session
  (bounded-effort disclosure, see Independent denominator methodology).
- No multi-generation *admitted* encounter exists (nothing was admitted);
  several individual *tracks* do span multiple confidence generations
  internally (`detection_count` up to 19 for the 30s example above).

## Multi-subject observations

Not evaluable in the usual sense — multi-subject *Visit* handling
(sibling isolation, cross-subject corroboration, duplicate-sibling
checks) requires at least one admitted Visit, and there are none. At the
*raw-track* level, several of the dense 60-second-rule clusters (up to
154 track generations in one ~25-minute window) plausibly include
temporally-overlapping distinct individuals, but this was not
specifically disambiguated this session (bounded scope) and is reported
honestly as unresolved rather than guessed.

## Fragmentation

**Insufficient data — not 0%.** The accepted automated tool
(`fragmentation_accounting.py`) reports `total_units: 0`,
`fragmentation_rate: {"state": "insufficient_data", "value": null}` —
correctly: fragmentation (one real encounter split across *multiple
admitted* Visits) cannot be assessed when zero Visits were ever admitted.
Do not read the prior 9-cohort 0% streak as continuing or as broken by
this session — it is neither; this session contributes no fragmentation
evidence at all.

## Duplicates

**Insufficient data — not 0%.** Same reasoning as Fragmentation, above:
`duplicate_count: 0` out of `total_units: 0` is a vacuous true, not a
9th/10th confirming data point for the existing 0%-duplicate streak. Not
counted toward that streak.

## Useful evidence

**Not applicable — 0 admitted Visits, 0 evidence items ever reached
persisted content.** Independently confirmed by direct filesystem
inspection: zero media files exist anywhere under the deployed instance's
`userdata` directory at session end. This is not a "0% useful evidence"
result (which would imply Visits existed but were poor quality) — it is
the complete absence of the denominator itself.

## Evidence survival / blocked_missing_evidence

**138 of 156 recovered terminal/pending decision-events (88.5%)
resolved `blocked_missing_evidence` / `no_persistable_evidence_bytes`** —
by a wide margin the dominant outcome of the entire session, and,
uniquely among every prior cohort, effectively the *only* outcome
(the remaining 18 recovered records are `blocked_continuation_pending`,
a pending, non-terminal state, not a competing terminal reason). Every
prior cohort's own `blocked_missing_evidence` rate (v6 18.3% → v7 9.4% →
v8 9.9% → v9 8.9% → v10 6.7% → v11 9.29% → v12 ~4.6% of decision-events,
not directly comparable basis) sits in the single-digit-to-teens percent
range, describing a small minority of genuinely brief, isolated
detections that never produced a savable frame — consistent with
product doctrine's own framing of this as an occasional, expected
outcome for weak signals. **This session's own ~88–100% rate for
*every* proposal, including a 30-second/16-strong-detection track, is a
qualitatively different, session-wide pattern, not a heavier instance of
the same expected noise** — see Reproduced defects, below.

## True latency

**Mechanism proven, samples unobtainable this session — a real,
substantial contribution to the RTT-calibration evidence body, but zero
capture-to-visible samples.** `check_camera_node_compatibility.py
--profile field_acceptance` reached `calibrated` at Observation start
(5/5 samples, `offset_ms 6.744 [1.107, 12.38]`, `rtt_ms 15.154`). Across
the full live session, the accepted RTT-bounded clock-calibration
mechanism recorded **523 batches, 518 `calibrated` (99.04%), 5
`insufficient_samples`, 0 `inconsistent_samples`, 0 clock jumps** —
`offset_ms` range `[-55.772, 110.616]`, `uncertainty_ms` median 9.409,
`rtt_ms` median 38.248. This is the **largest real RTT-calibration batch
count of any cohort to date** (v9 ~24–25, v12 100), a genuine, positive
contribution to dependency item #4's own infrastructure half.

**Latency itself: 0 samples attempted-and-measurable.**
`capture_to_visible_latency.py` (via `run_gate_a_measurement_accounting.py`)
reports `sample_count: 0` — `measured/unavailable_capture_time/
invalid_negative/implausible/invalid_clock_mapping/fallback_measured` all
0, because latency is only defined for an *admitted* Visit's own T5
(user-visible availability), and none exists. Median/p90/p95/max/mean are
all `None` — not zero, not a small number, genuinely undefined. Dependency
item #4 (a second, independently-varied, full-coverage true-latency
cohort) **remains open** — this session, despite excellent
RTT-infrastructure evidence, adds no new latency *sample* to the existing
v9/v10 distributions.

## Gate B

**Not applicable — 0 admitted Visits, so 0 species guesses of any
kind.** No confident-species-on-false-Visit recurrence is possible this
session; there is also no positive Gate B evidence (no correct
abstention-on-true-encounter to report either, since nothing was ever
even offered a species suggestion).

## Monitoring / recovery

- Requested duration: 90–105 minutes. Actual: **101.8 minutes.**
- **Zero Node disconnects, zero reconnects, zero Host failures, zero
  detector/model failures.** Node `boot_id`
  (`4239527b-5622-425c-bed1-ae3074e191dd`) unchanged from before the
  session to well after it ended; watchdog `consecutive_probe_failures:
  0` at every health check (start, four ~20-minute checkpoints, and
  final). `self_test.status: passed` and `camera_available: true`
  throughout.
- **Independent-recorder-based coverage** (the most direct, product-independent
  evidence): 5,013 frames spanning offset 0→6,081,263ms of a
  6,081,819ms session (**99.99% span coverage**); frame-to-frame gap
  analysis: median 1.12s, p95 1.70s, **max 3.68s, zero gaps over 5s** —
  no stall, no reconnect-driven hole, anywhere in the session. This is
  the tightest (lowest-max-gap) recorder-coverage result of any cohort to
  date (v12's own otherwise-excellent session still had a 6.79s max gap).
- Stop-finalization: clean, `stop_finalization_pending` resolved within
  ~2.3 seconds, matching the accepted contract's own expected behavior.
- Final Observation state: `state: "stopped"`, `observing: false`,
  `stopped_reason: "user_stopped"` — no stale Observation remains.

## Storage

- Requested root: `C:\Users\zachk\AppData\Local\MockingBirdFieldAcceptanceV13`
  (native Windows form, passed as-is per the corrected storage-preflight
  contract).
- Resolved/probed root (via the corrected `resolve_dev_root_path`/
  `resolve_storage_probe_target`, which now correctly detects and
  translates a Windows-style path from WSL rather than silently
  CWD-anchoring it): `/mnt/c/Users/zachk/AppData/Local/
  MockingBirdFieldAcceptanceV13` — **the report explicitly proves which
  filesystem was measured**: `resolution_method: "direct"`,
  `filesystem_device_id: 71`, `platform: "posix"` (WSL-side probe of the
  real Windows C: drive via its `/mnt/c` mount), `total_bytes:
  499,556,818,944` (the real ~499.6GB C: drive, confirmed identical
  across every preflight call this session).
- Starting free space (pre-reclaim): 12,141,772,800 bytes (~11.3GB),
  tier `action_recommended`.
- After user-approved reclamation of two confirmed-`SAFE_TO_RECLAIM`
  prior instances (~13.2GB): 25,717,661,696 bytes (~25.7GB), tier
  `getting_low`, `sufficient: true`.
- Minimum observed free space during the session: not separately
  polled below the periodic-checkpoint cadence, but monotonically
  declining and never re-measured below **16,288,514,048 bytes
  (~16.29GB)**, the final measurement — no safety-tier crossing, no
  storage-triggered stop.
- Ending free space: ~16.29GB, tier `action_recommended` (this
  machine's own consistently-tight tier ladder for its general disk,
  matching every prior cohort's own disclosed characteristic — not a
  new finding).
- Safety tier: never approached `critical`; no cleanup/stop forced by
  storage. Total session consumption ≈9.4GB, consistent with the
  independent recorder's own 4.48GB plus ledger snapshots (~40MB) plus
  ordinary runtime/model-cache footprint.

## Cohort comparison

| Metric | v9 | v10 | v11 | v12 | **v13** |
|---|---|---|---|---|---|
| Duration (min) | ~92 | 90.2 | 101.8 | 96.97 | **101.8** |
| Recall | — | 4/5=80% | 100%/70% | 87.5%/58.3% | **0/19=0.0% (cons.) / 0/48=0.0% (broader) — REOPENED BY DEFECT** |
| False-Visit rate | 20.0% | 36.4% | 44.4% | 5.6% | **undefined (0 admitted Visits)** |
| Fragmentation | 0% (6th/7th) | 1/5=20% | 1/7=14.3% | 0/14=0% | **insufficient_data (0 admitted Visits)** |
| Duplicates | 0% (4th) | 0% (6th/7th) | 0% (8th/9th) | 0% (9th) | **insufficient_data — not a 10th data point, existing streak unaffected** |
| Useful evidence | 76.0% | 54.5% | 43.5%/62.5% | 77.8%/94.4% | **not applicable (0 admitted Visits, 0 persisted evidence bytes)** |
| blocked_missing_evidence | 8.9% | 6.7% (best) | 9.29% | ~4.6% (basis differs) | **88.5% of decision-events (138/156) — REOPENED BY DEFECT** |
| Latency median/p90 | 111.8s/173.9s | 103.9s/183.3s | not re-derived | 110.6s/145.2s (n=2) | **undefined, n=0 (RTT infra: 523 batches, best of any cohort)** |
| Monitoring coverage | 99%+ | 99.99% | 97.5% | continuous, qualitative | **99.99% span, max gap 3.68s — best (tightest) of any cohort** |
| Scene-confusor registered | — | — | 14 regions | 14 regions | **0 regions — touch point never reached (session-wide category D)** |
| RTT calibration batches | ~24-25 | ~11 | not re-derived | 100 | **523 — largest to date** |

## Budget-convergence analysis

Combining v13 with the valid prior representative cohorts, per metric —
**v13's own recall and evidence-survival numbers are excluded from
convergence judgment for those two metrics specifically**, because this
session's own root-caused defect (see Reproduced defects, below) is the
proximate cause of both, not a representative sample of ordinary product
behavior; including a defect-driven 0% in an average would corrupt the
budget rather than inform it. v13 is fully included for every metric it
*can* speak to (monitoring coverage, RTT-infrastructure scale, duplicates/
fragmentation non-contradiction).

- **Recall**: v10 (80%), v11 (100%/70%), v12 (87.5%/58.3%), **v13 (0%,
  defect-attributable, excluded from averaging)**. Prior convergence
  judgment (MORE EVIDENCE REQUIRED, no consistent methodology across
  cohorts) is **unchanged by v13's own number** — but Gate A now also
  requires the newly-identified defect to be fixed and field-re-proved
  before any *future* recall cohort can be trusted at face value. **MORE
  EVIDENCE REQUIRED**, and additionally **REOPENED BY DEFECT** pending a
  fix.
- **False-Visit rate**: v12 (5.6%, clean, unconfounded) remains the only
  clean data point; v13 contributes nothing (no denominator). **MORE
  EVIDENCE REQUIRED** — unchanged from v12's own dependency item #2 (a
  second person-confound-free cohort still needed), now also gated on the
  evidence-persistence fix (a cohort where nothing is ever admitted
  cannot supply this evidence either).
- **Fragmentation**: v12 (0/14, own weaker manual method) remains the
  most recent measurement; v13 contributes `insufficient_data`, not a
  reconfirmation or a regression. **MORE EVIDENCE REQUIRED** — unchanged.
- **Duplicates**: 9 consecutive cohorts at a real, measured 0% through
  v12. v13 neither adds a 10th confirming point nor contradicts the
  existing streak — it simply has no denominator. **READY FOR BUDGET**
  status is **preserved, not re-earned and not weakened**, per §32's own
  instruction not to automatically discard or lock prior readiness.
- **Useful evidence**: v12 (77.8%/94.4%, unconfounded) remains the most
  recent real measurement; v13 contributes nothing. **MORE EVIDENCE
  REQUIRED** — unchanged.
- **blocked_missing_evidence / evidence survival**: v6 through v12 all
  sit in a 4.6%–18.3% band, describing a small minority of genuinely
  brief/isolated detections. **v13's own 88.5% rate is not a data point
  for that same distribution — it is evidence of a different,
  newly-identified failure mode** (see Reproduced defects). **REOPENED BY
  DEFECT** — evidence-survival cannot be considered converged, or even
  provisionally healthy, until this session's own root cause is fixed and
  a follow-up cohort shows the historical single-digit-to-teens rate
  again.
- **Capture-to-visible latency**: v9/v10 remain the only two real,
  defensible sample distributions to date; v13 adds zero samples but
  does substantially strengthen the *RTT-calibration infrastructure*
  evidence (523 batches, 99.04% calibrated, 0 clock jumps — the largest,
  cleanest calibration dataset of any cohort). **MORE EVIDENCE REQUIRED**
  for latency *samples* specifically — dependency item #4 remains open;
  the infrastructure itself is now about as proven as it can be without
  an admitted Visit to attach a T5 to.
- **Monitoring coverage**: v13 (99.99% span, max gap 3.68s) is the
  *tightest* result of any cohort to date, squarely inside and
  strengthening the existing 97.5–99.99% band. **READY FOR BUDGET** —
  reconfirmed, not weakened.

## Proposed budgets

- **Duplicate-Visit rate: ≤ 1% (effectively 0%).** Unchanged from v12.
  Supported by 9 consecutive cohorts (v7 through v12) at a real, measured
  0%; v13 neither adds nor subtracts evidence. **READY FOR BUDGET**
  (reaffirmed, not newly earned this session).
- **Monitoring coverage: ≥ 95%.** Unchanged from v12, now further
  strengthened. Supported by 6 cohorts (v5, v9, v10, v11, v12, v13), all
  in the 97.5–99.99% band, v13 the tightest yet. **READY FOR BUDGET**
  (reaffirmed and strengthened).

Every other metric remains **MORE EVIDENCE REQUIRED**, per metric above.
Two metrics are additionally **REOPENED BY DEFECT** this session: **Visit
recall** and **evidence survival / `blocked_missing_evidence`** — see
Reproduced defects, below, for the full account. Neither can be
considered for a release budget until the underlying defect is fixed and
field-re-proved.

## Reproduced defects

**A genuine, previously-undiscovered, release-critical product defect in
the automatic Observation Engine's own evidence-capture path — precisely
root-caused via full code tracing, not inferred from symptoms alone.**

**First irreversible error, stated as a bounded contract**: the Host
persists a Camera-Node evidence `profile_id`
(`node_evidence_profile_id`, e.g. `picamera2-evidence-3840x2160`) at
camera-setup time and **never re-validates it against the Node's live
advertised profile set** before issuing an automatic evidence-burst
request against it. `CameraNodeHttpTransport.request_evidence_burst()`
(`src/mockingbird/observation/camera_node_live.py:551-621`, the
Observation Engine's own automatic evidence path — a *different* code
path from the manual/legacy `CameraNodeClient.capture()` this milestone
initially suspected) issues `POST /node/v1/cameras/{camera_id}/
evidence-burst`; any failure at all — a `409 profile_not_advertised`,
a `503` session failure, a raw socket timeout, a connection reset —
collapses into one identical generic `failure_code:
"evidence_burst_unavailable"` (lines 583-584, 617-618), with **zero
logging anywhere in this file** (confirmed: no `logger`/`logging` import
or call exists in it at all). The caller
(`LiveCameraNodeShadowSession._process_frame`, same file, lines 916-920)
increments a private `_burst_failures` counter and continues — by
design, confirmed by its own test
(`tests/test_observation_camera_node_live.py:585-606`,
`test_burst_failure_or_stale_generation_does_not_stop_analysis`) — but
that counter, and the richer `LiveShadowStatus` it feeds
(`burst_requests`/`burst_captures`/`burst_failures`/`stale_bursts`,
lines 676-694), is **never read by `engine_runtime.py`** and never
reaches the `observation/status` API's own `advanced` payload —
confirmed structurally invisible in production, exercised only in test
fixtures. No `EvidenceCandidate` of any role is ever created for a
failed burst (`candidate_visit_adapter.py:357-359` explicitly never
fabricates a content-less item), so every downstream proposal reaches
`product_repository.py:7035-7039`'s `items_with_content` check empty,
and is rejected `blocked_missing_evidence` / `no_persistable_evidence_
bytes` — **before any file write is ever attempted** (confirmed:
matches this session's own zero files under `userdata`, and rules out
the storage-tightness red herring).

**Two concrete, code-grounded candidate triggers for why every single
burst request actually failed this session** (both real, both fully
consistent with every observed symptom; which one, or both, actually
fired requires live Node inspection this investigation could not
perform after the fact):

1. **Silent profile renaming via the Node's own async warm-proof
   promotion.** `PiCamera2Provider.capture_profiles()`
   (`src/mockingbird_node/providers.py:560-650`) initially advertises
   `picamera2-evidence-3840x2160` as `capture_class:
   "reconfiguration_required"`, then starts a background thread
   (`_schedule_warm_proof`) that — specifically for `same_fov: true`
   evidence profiles, exactly this one's own advertised shape — can
   promote it to a *differently-named* `warm_concurrent` profile
   (`picamera2-warm-evidence-3840x2160`) and **remove the original
   profile_id from the Node's advertised list entirely**
   (`providers.py:773-833`). If this promotion completed any time after
   this session's own camera-setup persisted the original profile_id,
   every subsequent evidence-burst request names a profile the Node no
   longer recognizes, producing a deterministic `409
   profile_not_advertised` (`src/mockingbird_node/app.py:401-416`,
   directly tested for the sibling `/capture` endpoint at
   `tests/test_camera_node.py:1664-1725`) on every attempt.
2. **Reconfiguration latency at or beyond the Host's own fixed
   timeout under real concurrent load.** A still-`reconfiguration_
   required` capture serializes reset→re-init (bounded 4.0s)→capture
   (bounded 4.0s)→re-init back to monitoring resolution (bounded
   4.0s)→encode, all under one process-wide capture lock the
   concurrently-running live monitoring stream also contends for every
   frame (`providers.py:1163-1322`, `src/mockingbird_node/app.py:481-536`,
   the latter carrying its own comment acknowledging this exact
   contention). Worst case, this can require ~12+ real seconds — at or
   above the Host's own fixed ~12-second total budget (`response_
   timeout_seconds=10.0` plus `connect_timeout_seconds=2.0`,
   `camera_node_live.py:470,563`) — systematically, not occasionally.

**Independently ruled out**: the already-fixed 2026-08-20 harvest-cache
timing race (Harvested Evidence Issuance / Missing-Evidence Closure v1)
— that defect's own governing contract states its `evidence_harvest_
misses` counter is "always a genuine captured-then-lost-before-harvest
fact, never never-captured"; this session's own counter stayed at
**0** for the entire 101.8 minutes, which — per that same contract —
proves nothing was ever successfully captured in the first place,
cleanly distinguishing this from that prior, already-closed defect
rather than being a recurrence of it.

**A precise contrast makes the gap actionable**: the legacy/manual
capture path's own `_high_resolution_capture_claim_profile_lineage`
(`src/mockingbird/api/main.py:1128-1181`) *does* detect and honestly
report this exact class of profile/Node mismatch as `node_capture_
profile_unavailable`. The modern automatic path's own
`_default_capture_profile_alignment` (`engine_runtime.py:288-364`)
already fetches the Node's live profile list at every session start —
but **silently discards** any mismatch rather than surfacing or
self-healing it. The newer, primary production path has strictly less
observability for the identical failure class than the older path it
was meant to replace.

**Not fixed during this cohort, per §34/§8** — this is core
admission/evidence-path product code, explicitly off-limits during
field collection; no attempt was made to reproduce, patch, or work
around it live. Bounded future contract (diagnosis only, not a
commitment): (a) re-validate `node_evidence_profile_id` against the
Node's live profile set at Observation start and self-heal or fail
loudly rather than silently degrading; (b) surface `burst_failures`/
`burst_requests`/`stale_bursts` in the `observation/status` `advanced`
payload so this class of failure is visible without requiring a
research-grade code trace; (c) parse `X-MockingBird-Node-Error` in
`request_evidence_burst()` the same way `CameraNodeClient.capture()`/
`.snapshot()` already do, so `409 profile_not_advertised` is
distinguishable from a genuine timeout in the failure_code itself;
(d) consider whether the reconfiguration-path timeout budget needs
headroom relative to the Node's own worst-case latency under real
concurrent monitoring-stream load.

## Gate A decision

**Gate A remains OPEN — this session's own evidence, while excellent in
rigor, is release-critical-defect-gated, not merely incomplete.**
Representative daylight ✓; accepted production configuration ✓
(confirmed byte-identical throughout); prospective independent
denominator ✓ (recorder-first methodology, visually cross-validated);
recall/false-Visit/fragmentation/duplicates/useful-evidence/evidence-
survival/monitoring-coverage all honestly measured (several as
"undefined"/"insufficient_data" rather than a misleading number);
`classifier_same_frame` and dead-anchor fixes both honestly field-
accounted (zero and one occurrence respectively, both correctly
disclosed as inconclusive given the shared root cause); Gate B checked
(N/A); budget-convergence analysis completed; clean shutdown/archive; no
field-time product tuning. **The one release-critical fact overriding
all of this**: a newly-identified, precisely root-caused defect in the
Observation Engine's own automatic evidence-capture path caused complete
(0%) recall against a genuinely, substantially active real session — no
release budget for recall or evidence-survival can be responsibly
proposed while this stands, and no future field cohort's own recall
number can be trusted at face value until it is fixed and field-re-proved.

## Remaining Gate A dependency

The pre-existing 13-item list (as narrowed through Ambiguous-Boundary
Real-Subject Recall Correctness v1) is **not closed by this session**;
v13's own contribution to each item, plus one new release-critical item,
follows:

1. Never-strong single-generation confusor clearing `blocked_ambiguous_
   boundary` then reaching the quality gate repeatedly — **unmet**; this
   session's own dominant activity never reached `blocked_ambiguous_
   boundary` as an outcome at all (see Ambiguous-boundary results).
2. Unconfounded false-Visit-rate/useful-evidence cohort confirming v12's
   5.6% — **unmet**; this session has no denominator (0 admitted Visits).
3. Full-ledger-coverage automated fragmentation re-proof — **unmet**;
   this session's own ledger is highly complete for
   `raw_detections`/`track_generations` but there are 0 admitted Visits
   to fragment.
4. Second independently-varied true-latency cohort — **unmet**; 0
   samples (worse than v12's own n=2), though RTT-calibration
   *infrastructure* evidence is now the strongest of any cohort (523
   batches, 99.04% calibrated).
5. 3+-simultaneous-subject cohort — **unmet**; not evaluable without
   admitted Visits.
6. v7's two remaining ambiguous fragmentation units — not investigated
   this session (out of bounded scope).
7. The ~13 untraced v7 `blocked_missing_evidence` records — not
   investigated this session.
8. Same-frame class-contradiction field effect on person-associated
   false Visits — **unmet**; no genuine human presence, no admitted
   Visits either way.
9. Further strong-confidence scene-artifact recurrence — did not recur
   (negative result; scene-confusor's own touch point was never reached
   at all this session).
10. No whole-frame human suppression of real birds — still only
    trivially satisfiable (no coincidence occurred, and no admissions
    exist regardless).
11. Scene-confusor participation incl. corroboration-rejected counts —
    **directly measured**: zero regions registered, zero touch-point
    reaches, root-caused precisely (category D, session-wide).
12. Intact full-session ledger coverage — **materially advanced**:
    `raw_detections`/`track_generations` fully complete by record count;
    `proposal_outcomes` decision-event coverage newly identified as
    capable of falling short of a 5-minute cadence under high proposal
    churn (44.6% this session) — a real, disclosed residual tooling
    limitation for a future session to consider tightening.
13. `reject_no_identification_or_context` "vanish entirely" behavior —
    **unmet, and now structurally unreachable to test further**: no
    proposal this session ever survived far enough to reach that
    specific quality-gate check at all.

**New, release-critical item added by this session**: (14) **fix the
Observation Engine's automatic evidence-capture profile-staleness/
silent-failure defect** (see Reproduced defects), then field-re-prove
recall against a representative cohort with the fix in place. This item
is more urgent than the pre-existing 13 — until it is closed, no
future field cohort's own recall/evidence-survival measurement can be
trusted at face value, and Gate A cannot responsibly move toward
closure regardless of how the other 13 items resolve.

## Cleanup / final state

- Observation stopped cleanly (`user_stopped`); stop-finalization
  confirmed complete within ~2.3 seconds (`state: "stopped"`, `observing:
  false`, no `stop_finalization_pending` residue).
- Final ledger snapshot taken: the corrective live fetch
  (`counterfactual-final.json`) captured seconds before stop, plus the
  ledger collector's own 21st checkpoint landing at the stop moment
  itself.
- Ledger reconciled: `raw_detections`/`track_generations` complete by
  record count; `proposal_outcomes` decision-event coverage 44.6%,
  disclosed precisely (see Ledger integrity).
- Whole Host process stopped (`deploy_windows_dev.py --stop`, verified).
- Lifecycle: `init` → `active` → `completed` → **`archived`** (evidence
  archive path:
  `data/field-acceptance/2026-09-04-gate-a-v13-intact-ledger-budget-convergence/`).
  `assess` re-verified fresh: `verdict: SAFE_TO_RECLAIM` (9.42GB) — **not
  destroyed**, per standing policy; left for a future operator decision.
- Node pairing: deliberately **left paired** to this session's own
  archived instance, matching the established v12 convention (an
  archived-not-destroyed instance's own pairing record stays internally
  consistent; a future session picking up the reference Node should
  expect `pairing_required: false` against this instance's own
  credential, and should either reuse this archived instance or perform
  a fresh revoke/re-pair as documented precedent describes).
- Field-acceptance credential and local disposable Administrator account
  are local to this disposable instance only; both are destroyed along
  with the instance at eventual reclaim (no separate revocation needed
  beyond the instance's own lifecycle) — no credential secret is
  reproduced anywhere in this report or its archive.
- No stale Observation remains active anywhere (confirmed via
  `observation_status` and the Host process itself being stopped).
- No production code was modified during this cohort. No Tier 3 run
  required (§35 — zero production diff); field evidence is the
  validation.

## Decision

**B**

Classification B, not A, for one explicit, named, mechanical reason: this
milestone's own acceptance bar requires true latency to be "materially
better sampled than v12" (§38); v12 measured n=2 real latency samples,
this session measured **n=0** — fewer, not more, despite RTT-calibration
*infrastructure* evidence being the strongest of any cohort to date (523
batches). The `proposal_outcomes` ledger artifact also reconciled to only
44.6% decision-event completeness (a real, precisely disclosed gap, not
a rounding matter), short of "full/credible ledger preservation" at full
strength for that one artifact.

This is not, however, a weak or low-value session. Execution rigor was
high across every other dimension this document tracks: representative
daylight, accepted configuration, a genuinely independent prospective
denominator built and visually cross-validated before consulting any
admitted-Visit timestamp (of which there were none), honest measurement
of every metric (several correctly reported as "undefined"/
"insufficient_data" rather than a misleading number), both accepted
fixes field-accounted precisely, and — the milestone's own single most
significant substantive outcome — a genuine, previously-undiscovered,
release-critical product defect in the Observation Engine's own automatic
evidence-capture path, root-caused to a bounded, code-grounded, testable
contract via full tracing rather than inferred from symptoms, with zero
field-time product tuning and a clean shutdown/archive. Classification B
reflects the milestone's own technical-completeness bar, not the value of
what it found.

**Gate A remains OPEN**, now carrying one new release-critical dependency
item (14) ahead of the pre-existing 13.





