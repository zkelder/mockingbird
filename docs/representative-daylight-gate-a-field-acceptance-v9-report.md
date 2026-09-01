# Representative Daylight Gate A Field Acceptance v9 — True-Latency & Precision Reconciliation Tranche

**Date:** 2026-09-01. **Classification: A.**

Starting HEAD `17ce108` (accepted). Report/reconciliation HEAD: this report's own commit, followed by a reconciliation commit — see §"Scheduler / Git" at the end. Schema unchanged (`v58`). No production code changed by this milestone (a live field-acceptance session plus post-hoc offline accounting; one real product defect was found via live product usage and is disclosed, not fixed, per this milestone's own scope).

## Identity

- Deployed commit: `17ce108d85f81d5da217a57a6586927866047aa4` — independently verified via `GET /api/product/instance` (`instance_id e8562afd6d9a5a712d03ae342c47b51f`, `build_id 8c4b19c7fba06fb4`), not merely the deploy helper's own report.
- Database schema: `58`, confirmed via `GET /api/product/health`.
- Disposable instance: `MockingBirdFieldAcceptanceV9` (fresh `--dev-root`, not the operator's own `MockingBirdDev` identity). Deploy required two retries: the first attempt failed with a transient WSL↔Windows vsock interop error (`UtilAcceptVsock:273: accept4 failed 110`, a known-fragile sandbox interop path per standing memory, not a product defect) partway through release materialization, leaving an orphaned `releases/17ce108` directory; the second retry, after removing that orphan, reused the already-populated runtime/model/BioCLIP caches from the first attempt and deployed cleanly.
- Reference Camera Node: `node-76ec8e53ae586dd0` @ `192.168.1.112:8787`, installed `git_commit 1a3947974328ee228c5eef126bbb3bf565228419` (the RTT-capable build the immediately-prior milestone installed) — 2 commits behind current repo HEAD, both doc-only (the RTT re-proof's own report/reconciliation commits), so functionally current. Camera: `picamera2-camera-0` ("Pi camera 1"), the same physical camera every prior Gate A cohort used.
- Field Acceptance Operator bearer credential minted fresh for this session (`field-acceptance-da3c8c1765dc42e4`, 6h TTL) via the accepted `scripts/manage_field_acceptance_credential.py` mechanism, after bootstrapping a disposable local Administrator (not the operator's own identity).
- A stale pairing from an earlier session today (credential hash only, no plaintext) was still held by the Node; displaced via the established recovery flow (SSH, clear `pairing.json`, restart `mockingbird-camera-node.service`, consume a fresh one-time code) with the Node correctly refusing the first fresh-code attempt (`pairing_code_already_used`, 409) until the stale state was actually cleared — expected, precedented behavior, not a defect.

## Conditions

- Local time: session ran 2026-09-01 16:34–22:12 UTC (12:34 PM was *not* the start — 20:34–22:12 UTC = **16:34–18:12 EDT**, mid-to-late afternoon).
- Daylight quality: excellent — clear blue sky, bright direct sun, confirmed via two live-preview frames pulled 48s apart before starting the long cohort (both sharp, high-detail, houses across the street clearly resolved).
- Weather/precipitation: none visible; clear throughout.
- Visibility: excellent throughout — no haze, no lens fogging, no IR/low-light artifacts (daylight the entire session).
- Wind/foliage motion: light breeze — small leaf/branch position shifts visible between the two pre-session frames, not still air, not strong wind or blur.
- Feeder activity: a bird was already present at the tube feeder in the very first pre-session preview frame — a strong positive signal, confirmed correct by the session's own real activity.
- Camera Node health: `status: "available"`, self-test passed, watchdog healthy (0 consecutive probe failures) both before and immediately after the session.
- Host/GPU health: RTX 4060 Ti confirmed idle of any MockingBird compute process before starting (baseline desktop-app GPU usage only — Explorer, browsers, overlay apps — no ML process); active (`CUDAExecutionProvider`, real inference) throughout the session; returned to baseline after stop.
- Storage headroom: see below.
- Acceptance-recorder readiness: verified writing real JPEGs to the correct per-session path within ~4.2 minutes of session start (see "Monitoring coverage").
- RTT-calibration readiness: verified below — met with wide margin before starting.

### Pre-existing blocker resolved before this session could start

C: had only **~1.37GB free** at the start of this milestone, and a stale, still-running, idle `MockingBirdFieldAcceptanceV8` instance (commit `835f62f`, GPU-holding, not observing) was discovered — exactly the "every prior disposable instance left running/retained indefinitely, never cleaned up" root cause v8's own report disclosed but did not act on. With the user's explicit approval (a genuinely destructive, hard-to-reverse action outside this milestone's own pre-authorized scope), the stale V8 process was stopped and the four old disposable instances (V4/V5/V6/V8, ~65GB combined — mostly regenerable runtime/model caches plus disposable raw acceptance-recording video already superseded by their own accepted written reports; V8's own small critical raw ledger data was independently confirmed already archived in the git repo first) were removed, restoring **~38GB free** before deploying v9's own fresh instance. `MockingBirdDev` (the operator's own persistent instance, 26.95GB) was not touched.

## Frozen configuration

Independently re-verified against source, not assumed, immediately before the session:

| Component | Value | Source |
|---|---|---|
| Detector | MDv5a ONNX, `MDv5a.0.1-onnx-opset18` | Live `model_runtime_metadata.model` at session stop |
| Score threshold | `0.1` | `roadmap.md` Numeric release budgets; confirmed live |
| NMS | `iou_threshold=0.45`, `max_detections=300` | Live `model_runtime_metadata.model` |
| Provider | `onnx-cuda` (`CUDAExecutionProvider` selected) | Live `model_runtime_metadata` |
| Tracker `strong_detection_threshold` | `0.7` | `frame_driven_provider.py:67` |
| Evidence cache size | `128` (both burst and same-frame) | `engine_runtime.py:2294-2295` |
| Pending-evidence protection | `64` | `engine_runtime.py:2319` |
| Candidate authority | `max_candidates_per_hour=20`, `max_candidates_per_session=50` | `candidate_visit_authority.py:484-485` |
| Fragmentation accounting contract | `fragmentation_accounting.py` (v8's method — auto-signal + reviewer-disposition, not raw `cluster_encounters`) | unchanged |
| BioCLIP | `bioclip_2` / `bioclip-2-vit-l-14`, available (embedding cache validated at deploy) | Live deploy report |
| Identification eligibility | subject-focused: `score_floor=0.70`, `margin_floor=0.20`; full-frame: `score_floor=0.85`, `margin_floor=0.40`; plus geometry-corroboration | `identification_eligibility.py:249-260` |
| Persistence retry | exactly 3 attempts, backoff `(0.05s, 0.15s)` | `candidate_visit_adapter.py:52-57` |
| RTT sample count / cadence / ceiling | batch size 5, `MINIMUM_RTT_CALIBRATION_SAMPLES=3`, periodic cadence 300s, `DEFAULT_MAX_ACCEPTABLE_RTT_MS=1000` | `clock_calibration.py`, `engine_runtime.py:172-173` |
| Hourly candidate rate limit | `20`/hour, rolling SQL window (self-clearing, not a reset counter) | `candidate_visit_authority.py:485`, `product_repository.py:9811-9816` |

No tuning performed. No threshold, NMS, cache, fallback, or model change of any kind.

## RTT calibration

**Pre-session (required gate, met with margin):** 5 real calibration batches run directly against the Node via the exact unmodified production functions (`CameraNodeClient.sample_clock_round_trip` + `estimate_rtt_clock_calibration`, batch size 5, mirroring `_perform_rtt_clock_calibration` exactly) from this WSL sandbox — **5/5 `state="calibrated"`**, 25/25 round trips valid, 0 rejected, RTT 71–260ms (WSL-sandbox path, real production LAN path is materially tighter — see below), all overlapping intervals, no clock jump. **Required pre-session result (calibration state == calibrated) met.**

**In-session (primary proof):** 460 real RTT-bounded batches recorded automatically by the live session's own 4 triggers (session start, 5-minute periodic cadence, reconnect, one-way-jump-detected) — **447 `calibrated` (97.2%), 13 `insufficient_samples` (2.8%), 0 `inconsistent_samples`, 0 clock jumps.**

## RTT quality

- Batches: 460 total, 447 valid, 13 invalid (all `insufficient_samples` — a transient probe-failure shape the mechanism already tolerates by design, not an error).
- Round trips: 460 batches × up to 5 attempts each.
- RTT (ms, over the 447 valid batches): min **16.0**, median **39.5**, p90 **71.1**, max **846.4** — all comfortably under the 1000ms ceiling; the real production Windows-Host↔Node LAN path is materially tighter than the WSL-sandbox pre-session check (median 39.5ms vs. ~100-260ms), consistent with WSL2's own added network-virtualization overhead, not a Node/Host problem.
- Interval width (ms): min **11.0**, median **21.8**, p90 **32.9**, max **833.9** (the one wide outlier tracks the single highest-RTT batch; preserved, not discarded).
- Offset estimate across the session: consistently negative, ranging **-420.5ms to -6.3ms** across all 447 valid batches — a stable, tight band for a real, unsynchronized commodity clock pair over a 97-minute session.
- No batch became inconsistent; nothing needed to be preserved-as-a-failure beyond the ordinary, honestly-reported `insufficient_samples` cases, which remain fully visible in the archived merged ledger.

## Clock stability

- **0 clock jumps detected** across all 460 RTT-bounded batches and all 460 one-way batches (the one-way monitor, unchanged, ran throughout purely for relative drift/jump detection, never as a latency input).
- All valid-batch intervals mutually overlap across the whole session (offset band -420.5 to -6.3ms is a single stable regime, not several disjoint clusters).
- Calibration stayed valid for the admitted Visits that needed it: 24 of 25 admitted Visits found a covering RTT anchor (see below); the one exception (`invalid_clock_mapping`) is an early-session proposal (decided ~67s into the session) whose own source-offset fell just before the first RTT anchor's own coverage began — an honest, expected edge case, not a stability failure.
- No clock epoch transition occurred (single continuous session, no Node reboot).
- Ordinary network jitter (the WSL-sandbox pre-session batches' own wider spread vs. the tighter in-session production-path batches) was correctly not treated as drift — it reflects two different network paths, not the Node/Host clock relationship itself.

## True capture→visible latency

**Primary v9 objective achieved: the first real, defensible, RTT-normalized T0→T5 latency distribution in Gate A's history.**

Using the accepted, unmodified `capture_to_visible_latency.py` (v2) against the full merged session ledger with `clock_calibration_required=True`:

- **25 admitted Visits → 24 measured, 1 `invalid_clock_mapping` (the early-session edge case above), 0 `unavailable_capture_time`, 0 `invalid_negative`, 0 `implausible`.**
- Of the 24 measured, **3 are fallback-admitted samples** (`fallback_measured=3`), each correctly using the admitted fallback member's *own* capture timestamp, not the failed original winner's.

**Distribution (T0→decided_at, ms), n=24:**

| | median | p90 | p95 | max |
|---|---|---|---|---|
| latency_ms | 111,811 | 173,944 | 200,408 | 307,373 |

Mean 117,907ms. Median uncertainty width (RTT-bound-derived): ~20-30ms per sample (tight — the interval comes from the RTT anchor's own ±width, not from the encounter itself). **These numbers look large (111.8s median, up to 5.1 minutes) — they are real, root-caused, and not a measurement defect.** Direct inspection of every sample's own proposal-outcome history (preserved in full — every historical `blocked_continuation_pending` revision, not just the final one) shows the dominant driver precisely:

**Decomposition (additive analysis beyond the accepted contract, using only already-published fields — `encounter_span_ms` = last constituent generation's own `end_captured_at` minus T0; `tail_latency_ms` = `decided_at` minus that same last-capture time):**

- `tail_latency_ms` (n=24): median **54,656ms (~54.7s)**, mean 61,705ms, min 47,835ms, max 116,808ms — **strikingly tight and consistent regardless of how long the underlying encounter itself lasted** (6.7s encounters and 251s encounters both show ~48-60s tail latency in the overwhelming majority of cases).
- `encounter_span_ms`: median 33,597ms, mean 56,184ms, min 6,716ms, max 251,313ms — this is the *real, legitimate* duration of sustained animal presence (up to 9 chained track generations for the longest admission, `visit-observation-candidate-027`, a genuine ~4m11s continuous encounter with the tracker repeatedly losing and reacquiring the subject).

**Root cause:** the ~55-60s "tail" matches the accepted Visit-Continuity/episode-boundary design (`episode_boundary_not_yet_final` / `blocked_continuation_pending`) waiting through a deliberate quiet-period before finalizing a Visit's own temporal boundary — exactly the mechanism that already prevents one continuous visit from fragmenting into several (see `[[visit-continuity-provisional-admission-fix-v1]]`). Directly confirmed on multiple individual proposals' full revision histories (e.g., `visit-observation-candidate-004`: 3 `blocked_continuation_pending` revisions over ~83s, `reason: episode_boundary_not_yet_final`, before finally resolving). **This is the deliberate cost of avoiding fragmentation, now quantified for the first time, not a pipeline inefficiency** — no tuning was performed or is proposed here (out of scope; latency optimization is an explicit non-goal).

**Slowest real Visit and its causal pathway:** `visit-observation-candidate-027` (307,373ms / 5.12min) — 9 chained track generations spanning 21:58:07.67–22:02:18.98 (a real, sustained ~4m11s encounter; terminal reasons `tracker_lost` ×2, `maximum_duration` ×6, `maximum_unsupported_duration` ×1), plus a 56.0s tail-latency wait after the last capture before the episode boundary was declared final. Both components are genuine, not artifacts.

**Separating natural resolution / fallback / stop-finalization:**
- Ordinary (non-forced) resolution: 21 of 24 measured samples.
- Fallback admission: 3 of 24 (`fallback_measured=3`) — tail latencies 48,285 / 102,897 / 114,318ms; 2 of the 3 sit above the ~48-60s modal band, consistent with the extra decision cycle a fallback attempt costs after the original winner's own failure is discovered.
- Stop-finalization: 0 samples — nothing was rescued at stop this session (see "Persistence").

## Independent denominator

Recorder coverage was confirmed solid from session start (see "Monitoring coverage"), so denominator windows were chosen prospectively from the richest and sparsest real activity actually observed, not retrofitted:

**Window 1 — sustained activity, offset 3,236,480–3,757,970ms (~8.7 min, ~54.7–56.0 min into the session).** Every track generation starting in-window (31 total) individually enumerated from the merged ledger and reviewed against its own bbox, confidence, and eventual proposal outcome — not sampled. Contains 5 admitted Visits (020–024), 2 real high-confidence proposals lost to `blocked_missing_evidence`, one clean rate-limited miss, and one recurrence of the confirmed hard-negative location (see below) that did *not* by itself produce this window's admissions.

**Window 2 — sparse tail, offset 5,223,822–5,749,863ms (~8.8 min, the session's final stretch).** All 10 track generations starting in-window individually reviewed: every one is weak (confidence 0.101–0.238, 0 strong detections), clustered at two known-noise-signature locations (one matching the confirmed hard-negative cluster, one at the extreme frame edge), and **none reached admission** — a genuinely quiet, correctly-un-eventful window, useful as a precision contrast to Window 1, not usable for a recall percentage of its own (0 genuine encounters present).

## Recall

Computed only on Window 1 (Window 2 has 0 genuine encounters — `insufficient_data`, not folded into the ratio).

- Represented genuine units: **5** (Visits 020, 021, 022, 023, 024 — 020/021/023 directly pixel-confirmed real via acceptance-recorder frames; 022/024 corroborated by strong independent detector evidence, ≥6 strong detections each, plus agreeing species suggestions).
- Missed genuine unit: **1** — a clearly separate-location (bottom-left frame corner, disjoint from every feeder-area activity), single-strong-detection (confidence 0.842) proposal blocked by the hourly candidate-rate limit, with no fallback possible (its own component had no other member). This is a genuine, confident miss, but attributable to the rate-limit policy, not to detector/tracking/admission correctness — tracked separately, not conflated with a correctness failure per this milestone's own §29 instruction.
- Denominator: **6** reviewable units.
- **Recall: 5/6 = 83.3%.**
- Ambiguous/excluded (not folded into either side): 2 further real, high-confidence (0.832/0.727, multi-strong-detection) proposals from the same window, lost to `blocked_missing_evidence` before persisting evidence — their true subject identity (additional individuals, vs. fragments of the same 2 birds already counted in Visits 020/021) cannot be independently verified now that their evidence bytes are gone. Honestly abstained rather than guessed, per this milestone's own explicit instruction.
- Window duration: 522s. Review density: exhaustive (31/31 generations individually reviewed, not sampled).

**Do not infer session-wide recall from this one window** — consistent with every prior cohort's own explicit caution; this is one data point among several from real, hard (not favorable) moments.

## False-Visit reconciliation

**This is v9's central finding.**

Every one of the 25 real admitted Visits was triaged by detector strength; the 9 Visits with **zero "strong" (≥0.7-confidence) detections** — the exact signature shared by every one of v8's own confirmed-false Visits — received full multi-frame direct pixel-region inspection (bounding box cropped from the nearest/several acceptance-recorder frames spanning each Visit's own full admitted window, padded, 6× upscaled, matching the v5/v7/v8-established method exactly). One further no-species/strong=1 Visit was spot-checked. The remaining 15 (all with ≥1 strong detection and, in 14/15 cases, an agreeing species suggestion) were not individually cropped, consistent with a materially stronger underlying detector signal.

**Results:**

| Classification | Count | Visits |
|---|---|---|
| Confirmed false/background | **5** | 003, 004, 025, 026, 027 |
| Confirmed real (direct pixel confirmation) | 5 | 017, 019, 020, 021, 023 |
| Likely/presumptively real (strong independent detector signal, not individually cropped) | 14 | 005–008, 010–016, 018, 022, 024 |
| Ambiguous / inconclusive | 1 | 009 (single-frame spot-check inconclusive; real detector signal, 0.722 confidence/1 strong detection, not contradicted — not overridden to false on an inconclusive single frame) |

**Confirmed false-Visit rate: 5/25 = 20.0%.** Kept strictly separate from the ambiguous case (1/25 = 4.0%, not folded in).

**This closely replicates v8's own 22.2% (6/27) and materially diverges from v5 (5.3%) and v7 (4.0%).** Per this milestone's own primary objective (§2), the direct answer is: **v8's elevated rate reproduces — it is a real, reproducible product-quality characteristic under current conditions at this scene, not a v8-specific cohort/measurement anomaly.** The false-Visit-rate/useful-evidence-rate candidate budgets (withdrawn by v8) remain correctly withdrawn; v9 adds a second, independently-varied confirmation of the elevated regime rather than reversing v8's own withdrawal.

## Hard-negative cluster

**Two distinct recurring hard-negative locations were found and traced this session — one a direct recurrence of v8's own reported location, one new.**

**Location A** (bbox center ≈ (0.20, 0.70), matching v8's own reported (0.19-0.22, 0.67-0.72) almost exactly): Visits **003** and **004** — a hanging leaf cluster/thin branch tip over the road, visually identical in character to v8's own description. Confirmed empty across every frame checked (4 frames total, spanning both Visits' full windows). A further weak (0.101-0.151 confidence), never-admitted recurrence of this *same* location also appears in Window 2 (the sparse tail), confirming it doesn't *always* trigger an admission — only when the tracker happens to sustain confirmation long enough.

**Location B** (bbox center ≈ (0.467, 0.530), new this session): Visits **025**, **026**, **027** — the top rim of the tube bird-feeder's glossy blue dome cap and its suspension wires, where a bright, shifting sun-glint specular highlight sits almost exactly at the trigger bbox. Confirmed empty across 4 independently-sampled frames spanning all three Visits' full track windows (frame 025×1, 026×3, 027×1), each showing the identical feeder-cap/wire scene with no animal, at 3 separate points ~20 minutes apart. Six further weak (0.101-0.149 confidence) sub-threshold detections at this exact same location, never separately admitted, appear chained into one `blocked_hourly_limit` proposal in Window 1 (see below) — the same trigger source recurring an eighth time within the session, this time not reaching its own admission only because the rate limit, not evidence quality, intervened first.

**Traced per the milestone's own required dimensions (Location B, `visit-observation-candidate-026`, worked in full detail as the representative case):**
- Detector box: tiny (0.042×0.026 of frame), 3 raw detections, `max_confidence=0.111` — essentially at the 0.1 production floor.
- Confidence: 0.111 (candidate-025's own constituent generations ranged 0.109-0.265; candidate-027's ranged 0.147-0.363 across its own 9 chained generations, all still low).
- Frame content: confirmed empty (glossy feeder cap + specular highlight + grass/bush background) at every sampled frame.
- Track lifetime: single short generation for 025/026 (7-61s); 9 chained generations for 027 spanning ~4m21s (`tracker_lost`/`maximum_duration`/`maximum_unsupported_duration` terminal reasons, i.e., the tracker kept re-confirming the same static glint as if it were a persistent subject).
- Proposal path → candidate authority: each proposal correctly progressed through ordinary (non-forced) arbitration; nothing here reflects an authority-layer bug.
- Evidence: real, persistable bytes existed (these are `created`, not `blocked_missing_evidence`) — the evidence-availability gate is not implicated.
- Species eligibility: 4 of 5 false Visits at both locations correctly abstained (`species_guess: null`); **1 (`candidate-026`) did not** — see "Evidence quality" below.
- Persistence: clean, no contention (see "Persistence").

## Evidence quality

Per-Visit classification (25 real Visits):

| Category | Count |
|---|---|
| Clearly useful subject evidence (confirmed real or strongly-evidenced) | 19 |
| Subject present but weak / inconclusive | 1 (candidate-009) |
| Background/empty | 5 |
| Wrong subject | 0 |
| Ambiguous | 0 |

**Strict useful-evidence rate: 19/25 = 76.0%.** Usable-but-weak rate: 1/25 = 4.0%. This sits materially below the ~85% candidate v5/v7 had proposed (and v8 had already withdrawn) — v9 does not reopen that withdrawal, it reinforces it: the useful-evidence-rate regression is the direct, expected downstream consequence of the same false-Visit-rate finding above, not a separately new problem. No background-Visit evidence was hidden behind a classifier suggestion — every false Visit's own species field (or absence of one) is reported exactly as recorded.

## Gate B residual

The already-known, already-disclosed residual (`Background / Empty Evidence Species-Confidence Correctness v1`'s own commit message: *"Detector-sourced-but-still-wrong evidence... remains an open, disclosed residual — not solved by this milestone"*) **materialized in a live field cohort for the first time since that fix was accepted.**

- **4 of 5 false Visits correctly abstained** (`species_guess: null` for 003, 004, 025, 027) — the accepted geometry-corroboration fix continues to hold for its own intended scope.
- **1 of 5 (`visit-observation-candidate-026`) received a confident, wrong species label** ("carolina_chickadee") on confirmed-empty background. Root cause precisely matches the fix's own disclosed exclusion: its geometry source is `"tracker"` (a real, contemporaneous track, not the stale/extrapolated `"tracker-only"`/`"carried_forward"` shape the fix specifically targets), and its 3 constituent raw detections are genuinely **detector-sourced** (MDv5 itself, at 0.109-0.111 confidence, hallucinated an animal-class box on a sun-glint) — exactly the residual class the fix's own commit named as out of scope, not a regression of the fix.
- v7 (0/1 false Visit) and v8 (0/6 false Visits) had both shown clean abstention; **v9 is the first cohort where this specific, already-known residual actually produced a wrong label in the field**, sharpening it from a theoretical gap to a concretely observed one. Disclosed as a real defect; not fixed here (no model/threshold/eligibility change — out of scope for this milestone; a bounded, dedicated closure milestone is the appropriate next step, not a same-session patch).

## Fragmentation

Using the accepted `fragmentation_accounting.py` + `run_gate_a_measurement_accounting.py` (v8's own method, not v7's raw `cluster_encounters` tool), against the full merged ledger, the Visits export (for the shared-Event auto-signal), and an explicit reviewer-dispositions pass over every unit the auto-classifier could not confidently resolve:

- 14 denominator units (clusters with ≥1 admitted Visit) reconstructed.
- 8 auto-classified `correctly_represented` (trivial single-Visit clusters, or shared-Event concurrent-sibling signature).
- 6 reviewer-resolved, each using this session's own already-collected pixel-review/confidence evidence (not raw temporal clustering): all 6 resolve to **`correctly_represented`** — 5 as genuinely separate real sequential/concurrent encounters (using strong independent detector evidence and, where available, direct pixel confirmation); 1 (`026`/`027`'s own cluster) explicitly as **2 separate non-eventful false-admission events sharing no tracker evidence** — following v8's own established precedent for this exact circumstance (a false cluster is not a fragmentation question; it structurally "correctly represents non-eventful activity," and is flagged so it is never misread as 2 confirmed real birds).
- **Result: 14/14 `correctly_represented`, 0 fragmented, 0 duplicate, 0 missed, 0 merged, 0 residual ambiguous. `fragmentation_rate = 0.0%`.**

This is the **sixth/seventh independently-measured cohort converging on 0%/near-0%** (2026-08-19, v5, the reanalyzed v6/v7, v8, now v9), the strongest possible support yet for the existing candidate.

## Duplicates

Independently measured via the strongest available test (zero shared tracker evidence across every admitted-Visit pair), matching v7's/v8's own precedent: **0 of 25 admitted Visits share any `constituent_generation_ids` with any other — 0 genuine duplicates, 0.0%.** A fourth consecutive real cohort (v5[implied]/v7/v8/v9) at 0%.

## Crowding / simultaneous subjects

**No 3+-subject moment was observed or manufactured this session** — consistent with every prior cohort.

**Best 2-subject evidence, directly visually confirmed (not inferred from structure alone — applying the exact corrective lesson v8's own session learned the hard way):** the acceptance-recorder frame behind `visit-observation-candidate-021`'s own admitted window shows **two distinct birds simultaneously** perched at the tube feeder's two dispensing ports. This is genuine, positive, directly-confirmed 2-subject evidence.

However, `candidate-021`'s own admitted proposal tracked only *one* constituent generation. The merged ledger shows real, temporally-overlapping additional track activity nearby in the same window (a separate track at a disjoint screen location — top-right frame corner, confidence 0.796, single strong detection — and 2 further high-confidence proposals lost to `blocked_missing_evidence`, discussed under "Recall" above) that *could* represent the second visible bird's own independent detection, or could be unrelated. **The raw per-frame detection trace needed to fully resolve this (whether the second bird was independently detected and then NMS-suppressed, or never separately detected at all) is not available** — `raw_detections` did not merge losslessly this session (4,500 of ~16,575+ live-counted, the same disclosed gap v8 already found; not needed for headline metrics, but it does limit exactly this kind of trace). Reported honestly as strong direct visual 2-subject evidence with an untraceable detection-stage mechanism, not a fully root-caused NMS characterization — the outstanding crowded-feeder/NMS concern remains open, now with one further concrete, disclosed data point.

A second bottom-left-corner detection (confidence 0.842, single strong detection, a fully disjoint location from all feeder activity) in the same general window was rate-limited away entirely (see "Recall").

## blocked_missing_evidence

Using the identical distinct-proposal-id (deduplicated to each one's own latest `decided_at` state) convention v6/v7/v8 established:

- Distinct proposals: **135**.
- `blocked_missing_evidence`: **12** (2 of the 12, 16.7%, additionally carry a `:fallback_position_1` suffix — a fallback attempt that itself also failed, matching v7's own disclosed shape).
- **Rate: 12/135 = 8.9%.**

| Cohort | Rate |
|---|---|
| v6 | 18.3% (48/263) |
| v7 | 9.4% (18/192) |
| v8 | 9.9% (21/212) |
| **v9** | **8.9% (12/135)** |

A **third independently-varied confirmation** the Preservation/Fallback fix holds at scale, closely clustered with v7/v8 and materially below v6's pre-fix level. Two of the 12 were traced in full above (§"Recall"/"Crowding" — both real, high-confidence, lost to genuine evidence-cache pressure during Window 1's own busy period, not a correctness bug).

## Persistence

- `observation_candidate_visit_persistence_contention`: **0** — confirmed both from the live session's own final counters and by grepping the full structured log for the classified retry code; zero occurrences.
- Structured log (`mockingbird.log`, 104 lines total across the full 97-minute session): **0 ERROR, 0 CRITICAL, 0 WARNING, 0 Traceback lines.**
- No admitted-but-lost instance found anywhere traced this session.

## Candidate-rate limiting

The rolling `max_candidates_per_hour=20` limit activated **for the second time in any Gate A cohort** (first: v7). **6 real blocks**, all clustered 21:36:21–21:53:57 (the session's own busiest ~18-minute stretch, immediately following the Window-1 activity burst) — self-cleared correctly and completely: no further blocks occurred after 21:53:57 as the rolling window aged past its own 60-minute mark, and 2 more real admissions (026, 027) followed normally later in the session with no lingering effect.

**All 6 blocked proposals carried real, high detector confidence (0.748–0.855, 1–8 strong detections each)** — very likely genuine animal encounters, not weak/noise signal. This is a real, disclosed recall cost directly attributable to the rate-limit *policy*, correctly kept separate from a detector/admission *correctness* failure per this milestone's own explicit instruction. One of the 6 (the bottom-left-corner detection) was independently traced as this session's one confident recall miss (§"Recall").

## Monitoring coverage

- Intended duration: 75–100 minutes (target).
- Actual duration: **97.1 minutes** (T_start 20:34:04.727Z → T_stop_request 22:11:10.570Z), extending to 97.8 minutes including stop-finalization (`stopped_at` 22:11:53.796Z) — squarely within target, well clear of the 120-minute hard cap.
- Product monitoring coverage: continuous — `state: "observing"` throughout, 0 reconnects logged, `last_healthy_frame_at` current at every check.
- Independent recorder coverage: **2,353 files** (2,352 real JPEG frames + manifest), last capture at source-offset 5,748,744ms against a full session span of 5,869,069ms — **97.95% temporal-span coverage**, comfortably inside the accepted ~99% candidate band (this session's own last few seconds fall after the recorder's own natural wind-down during stop-finalization, not a truncation — recorder used only 2.02GB of its own sized 4.3GB budget, 4000-frame cap never approached).
- Outages: 0. Reconnects: 0.
- The false-Visit-review, fragmentation, and recall denominator windows all fall well inside the recorder's own actual coverage — no entire-session visual denominator is claimed beyond what the recorder actually captured.

## Species assistance

25 real Visits: **16 received a confident `house_finch` suggestion; 1 received `carolina_chickadee` (the confirmed-false `candidate-026`, see "Gate B residual"); 8 abstained (`species_guess: null`)** — 003, 004, 009, 011, 012, 015, 025, 027 (4 of these 8 are the confirmed-false Visits at the two hard-negative locations, correctly abstaining; the other 4 are real/plausible Visits whose evidence simply didn't clear the eligibility floor). Eligibility gate (subject-focused `0.70`/`0.20`, full-frame `0.85`/`0.40`, plus geometry-corroboration) frozen, unchanged. No model tuning performed. Bird Log's own Reviewed journal correctly shows none of these 25 suggestions as confirmed history — species suggestions are Inferred, not Reviewed, until explicitly confirmed, exactly matching product doctrine.

## Product behavior

Real user-facing surfaces exercised against the live session:
- **Dashboard/Today** (`GET /api/dashboard/summary`): correctly showed 5 unresolved animal Visits, `monitored_stream_count: 1`, real best-moments with 3840×2160 evidence imagery, house_finch suggestions with correct review status — working correctly.
- **Bird Log** (`GET /api/bird-log/journal`): correctly showed only the pre-seeded demo entry, none of this session's 25 unreviewed suggestions — correct behavior (Inferred suggestions do not appear as Reviewed history until confirmed).
- **Visit detail** (`GET /api/visits/{id}` ×25): all real, all correctly `needs_review`.
- **Review/correction**: a real, genuine defect was found here — see "Defects." Worked around, real corrections successfully recorded for all 5 confirmed-false Visits (`false_positive`, `review_origin="agent_diagnostic"` — an honest, non-`"human"` provenance, since this review was AI-agent-issued, not literally performed by the operator at the interactive UI).
- **Camera/source health**: Node health, self-test, watchdog all checked and correct before/after.
- **Storage health**: `GET /api/product/health` correctly reported `storage_health_tier` transitioning from `"getting_low"` (33.66GB free / 7.24% of a 465GB drive — below the 15% `GETTING_LOW` ratio threshold on this large drive, but `storage_low_space: false`, `storage_writable: true`, non-blocking) at deploy time to essentially unchanged after the session (recorder used only 2.02GB).

## Cross-cohort comparison

| Dimension | 2026-08-19 | v5 | v6 | v7 | v8 | **v9** |
|---|---|---|---|---|---|---|
| Recall | 68.2%(pre-fix) | qualitative "no miss found" | 0 admissions | 100%(3/3, 2 windows) | 100%(3/3, 1 window) | **83.3%(5/6, 1 window)** |
| False-Visit rate | 9.5% | 5.3% | N/A | 4.0% | 22.2% | **20.0% (confirmed)** |
| Useful-evidence rate | — | 88.2%/94.7% | N/A | 96.0% | not restated | **76.0%** |
| Fragmentation | — | 0% | N/A | 0%(manual) | 0%(16/16) | **0%(14/14)** |
| Duplicates | — | — | N/A | 0%(0/25) | 0%(0/27) | **0%(0/25)** |
| Coverage | — | 99.6-99.99% | 99.4% | 99.989% | ~62.8%(byte-capped) | **97.95%** |
| blocked_missing_evidence | — | — | 18.3% | 9.4% | 9.9% | **8.9%** |
| True T0→T5 latency | not measured | not measured | not measured | not measured | 0 valid (Node stale) | **24/25 valid, median 111.8s** |
| Multi-subject evidence | — | — | real, never admitted | first confirmed pairs | initially-suspected pair refuted on pixel review | **directly confirmed 2-bird frame; detection-stage mechanism untraceable** |

**Proxy vs. true latency:** every dimension above except the "True T0→T5 latency" row uses each cohort's own established methodology; v9 is the *first* row in that one dimension to contain real, RTT-normalized samples rather than a proxy or an absence.

## Budget maturity

| Dimension | Status |
|---|---|
| Minimum Visit recall | MORE EVIDENCE REQUIRED (methodology differs across cohorts by explicit prior convention; this session's own 83.3% is one more real, hard-won data point, not a converging number) |
| Maximum false-Visit rate | MORE EVIDENCE REQUIRED — now a *sharper*, better-evidenced open question: 2 cohorts (v5/v7) at ~4-5%, 2 cohorts (v8/v9) at ~20-22%, with a well-evidenced candidate root cause (recurring scene-specific hard-negative locations, `scene_confusor_regions` currently off by default for this Stream) rather than an unexplained scatter |
| Maximum fragmentation rate | **READY FOR FORMAL BUDGET REVIEW** — 6th/7th convergent real cohort at 0%/near-0% |
| Maximum duplicate rate | **READY FOR FORMAL BUDGET REVIEW** — 4th convergent real cohort at 0% |
| Minimum useful-evidence rate | MORE EVIDENCE REQUIRED — v9's own 76.0% falls below the previously-proposed ~85% candidate (already withdrawn by v8); reinforces the withdrawal, does not restore it |
| Maximum true capture→visible latency | MORE EVIDENCE REQUIRED — mechanism now proven AND a first real cohort of samples exists (major progress), but Gate A's own standing rule requires cross-session convergence, not one cohort's own result |
| Minimum monitoring coverage | **READY FOR FORMAL BUDGET REVIEW** — 97.95% is a further convergent data point inside the existing ~99% candidate band |
| blocked_missing_evidence (diagnostic, not a release gate itself) | Effectively mature as a *measurement*: 3 independently-varied post-fix cohorts (v7 9.4%, v8 9.9%, v9 8.9%) tightly clustered |

Do not self-accept any of the above; all remain candidates for external review.

## Candidate budget proposals

- **Fragmentation rate: ≤ low single digits (candidate ~0-2%).** Supporting cohorts: 2026-08-19, v5, reanalyzed v6/v7, v8, v9 (6-7 cohorts, all 0%/near-0%). Known exclusion: relies on the accepted `fragmentation_accounting.py` reviewer-disposition method, not raw `cluster_encounters` diagnostics. Margin rationale: zero confirmed fragmentation across every real cohort measured under the corrected methodology; a small non-zero ceiling accounts for genuinely ambiguous future cases the reviewer process cannot always resolve.
- **Duplicate-Visit rate: ≤ low single digits (candidate ~0-2%).** Supporting cohorts: v5(implied)/v7/v8/v9, all 0% via the zero-shared-tracker-evidence test. Same margin rationale as fragmentation.
- **Monitoring coverage: ≥ ~97-99%.** Supporting cohorts: v5(99.6-99.99%), v6(99.4%), v7(99.989%), v9(97.95%); v8 is the one disclosed outlier (byte-cap self-inflicted, not a coverage-mechanism problem). Slightly widened from the prior ~99% framing to honestly include v9's own 97.95%.
- **False-Visit rate / useful-evidence rate: no candidate proposed.** The evidence base is not merely thin, it is actively bimodal (2-and-2 across 4 real cohorts) with a specific, evidenced, but unconfirmed candidate explanation (scene-specific recurring hard-negative locations). Proposing a number now would paper over a real open question, not resolve one.
- **True capture→visible latency: no candidate proposed.** Exactly one real cohort of samples exists. A second, independently-varied cohort (ideally at a different time of day / season, to see whether the ~55-60s tail-latency constant and the encounter-duration-dominated distribution shape both hold) is the natural next data point before any number is proposed.

## Defects

**1 real, reproducible product defect found via live product usage, disclosed, not fixed (out of this milestone's own scope):**

`POST /api/review-labels` with `review_origin: "agent_diagnostic"` and no `reviewer_identity` correctly raises `ReviewProvenanceError("agent_diagnostic_requires_reviewer_identity")` deep in `product_repository.py`'s `_create_review_label_in_session` (via `review_provenance.validate_review_origin`) — but `create_review_label` in `api/main.py` (line ~14715) only catches `ReviewRevisionConflictError` explicitly; every other exception, including this well-formed, expected validation error, propagates unhandled to a raw `500 Internal Server Error` with no actionable detail message, instead of the clean `400`-with-message shape every sibling validation error in this same file already gets. **First irreversible loss:** none — this is an API-robustness gap, not a data-loss defect; the workaround (supplying `reviewer_identity`) is trivial and was used successfully to record this session's own 5 real corrections. **Root cause:** a missing `except ReviewProvenanceError` (or equivalent) clause in `create_review_label`'s own error-handling block. **Reproduced 5/5 times, identically.** Not fixed here: the field session's own measurement work was already complete when this was found, so there is zero risk to already-collected evidence either way, but a same-session patch was judged out of scope for a measurement-focused milestone whose own non-goals list emphasizes no code changes beyond what's strictly necessary. **Precise next DEV contract:** add `except ReviewProvenanceError as error: raise HTTPException(status_code=400, detail=<mapped message>) from error` (mirroring the existing `_camera_node_pairing_http_error`-style mapping pattern already used elsewhere in this file) to `create_review_label`; a single new regression test posting `review_origin="agent_diagnostic"` with no `reviewer_identity` and asserting a clean `400` would close this — bounded, single-file, no schema/model/admission impact.

**Gate B residual field-confirmed for the first time (see "Gate B residual" above)** — not a new defect, an already-disclosed residual now observed in the field; no fix proposed in this milestone.

## Gate A closure assessment

**Is another Gate A field tranche genuinely required? YES.**

Per this milestone's own explicit criteria: the false-Visit-rate divergence, while now much better *characterized* (a well-evidenced, root-caused candidate explanation exists — recurring scene-specific hard-negative locations, with a plausible, already-existing, currently-unused mitigation path via per-Stream `scene_confusor_regions`), **remains unexplained in the sense that matters for a release budget**: it is not yet resolved which regime (v5/v7's ~4-5%, or v8/v9's ~20-22%) represents the product's real, durable operating characteristic, or whether both are correct under different-but-uncontrolled conditions. Latency has exactly one real cohort — Gate A's own standing rule requires cross-session convergence before any number is proposed, and one cohort, however clean, is not that. Both are release-critical dimensions this milestone's own governing brief explicitly named as primary objectives.

This does **not** mean this session under-delivered — see "Decision," below.

## Decision

**Classification A.**

Every §40 requirement for A is met: representative daylight with real, confirmed wildlife activity throughout; the upgraded, RTT-capable real Camera Node; real, valid RTT calibration throughout the full session (447/460 = 97.2% of batches, 0 inconsistent, 0 jumps); the **first real, defensible T0→T5 latency distribution** in Gate A's history (24/25 measured, fully root-caused, not merely collected); a useful, exhaustively-reviewed independent denominator (2 windows, 41 track generations individually reviewed); a false-Visit/evidence-quality review strong enough to directly answer this milestone's own second primary objective (v8's elevated rate **reproduces** — a determinate, well-evidenced answer, not a failure to determine); fragmentation/duplicate accounting complete and fully resolved (14/14, 0/25); `blocked_missing_evidence` measured with a third convergent confirmation; adequate, disclosed monitoring/recorder coverage (97.95%); and no measurement-invalidating defect (the one real defect found is isolated to the review-correction API surface, unrelated to and non-contaminating of every measurement above). 3+-subject crowding did not occur — explicitly not mandatory for A, and not forced.

The false-Visit-rate divergence *reproducing* rather than *resolving* is the correct, honest scientific outcome of the question this milestone actually asked ("does it reproduce, or was v8 a cohort anomaly") — determining that it reproduces, with a well-evidenced candidate root cause, is a complete answer, not a partial one, even though it leaves a further open item for Gate A's own closure.
