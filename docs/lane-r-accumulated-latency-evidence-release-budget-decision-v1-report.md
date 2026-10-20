# Lane R Accumulated Latency Evidence & Release-Budget Decision v1

**Type:** Release-critical, read-only evidence and decision milestone. No product, schema, or tooling code changed. No field session run. No deployment. No push.

**Classification: A — READY FOR RELEASE BUDGET** (a specific, deliberately narrow, scoped recommendation — see §7). This is a recommendation for external release-authority acceptance, exactly as the recall decision required; it does **not** itself flip Lane R to closed.

---

## 0. Executive summary

Six independent real-field sessions (v9, v10, v11, v14, and Representative Daylight True-Latency Tail Convergence v3/v4) have now measured RTT-normalized capture-to-visible ("T0→T5") latency under the current, unchanged, accepted production stack, spanning six different calendar days (2026-09-01 through 2026-09-07). Pooling the five that are intact, live-measured, fully-procedural cohorts (v9, v10, v14, v3, v4 — v11 is reconstructed/supporting-only, see §2) yields **69 raw, independently-verified latency samples**. Recomputing statistics directly from raw per-sample data (not from prose summaries) confirms every prior report's own published numbers except one: **v10's own stated p90 (183.3s) does not match any standard percentile computation on its own 11 published per-sample values — the correct figure is 201.5s** (§4.3). This is a small, disclosed, non-material bookkeeping correction to a single report's prose, not a product defect.

A bootstrap resampling analysis (§5.2) shows that the per-cohort p90 scatter repeatedly cited as "non-convergence" (173.9s–385.1s across cohorts) is fully consistent with ordinary small-sample estimation noise around a single, stable underlying distribution — it is not, by itself, evidence that the tail is a moving target. The median is tightly, repeatedly convergent (pooled 103.9s, bootstrap 90% CI [80.3s, 114.8s]s). Every procedurally-valid sample exceeding 300 seconds across every cohort traces to one already-accepted, safe-by-design mechanism (Visit-Continuity/ambiguous-boundary episode-boundary arbitration) — no new or pathological cause exists anywhere in six cohorts' worth of evidence (§6).

The recurring "≥12-valid-sample target not met" finding is accurate for the two most recent individual sessions (v3: 9, v4: 11) but is not, and has never been, a statistically-derived minimum, a release-gate requirement, or a historical convention — it is a per-session procedural default literally hard-coded (`target_sample_count: int = 12`) into the field-acceptance session driver's own stopping logic (§5.1), and it was already independently satisfied by v14 (n=14) on 2026-09-05. The pooled cross-session evidence base (69 samples, six independent days) is far larger than any plausible reading of "12."

This report proposes a specific, narrow, defensible budget structure (§7.2): a tight numeric **typical-latency** figure from the median; an explicit, honest, **non-numeric tail disclosure** (not a p90/max SLA); and an **architectural, not statistically-fit, ceiling reference** (the 20-minute component-decision-horizon design bound). It explicitly does **not** repeat the rejected 2026-09-05 reconciliation's error (denominator manipulation, omitted data) — every known >300s sample, including v10's 742.3s and v11's reconstructed 865.2s, is disclosed and included.

---

## 1. Verified baseline

Verified directly, not assumed, at the start of this milestone:

- **HEAD:** `0a776c8` (`Representative Daylight True-Latency Tail Convergence v4: disclose and fix an orphaned-process cleanup gap found post-report`) — matches the expected baseline exactly.
- **Branch:** `main`. **Upstream:** `+377 -0` vs `origin/main` — not pushed, matching the directive.
- **Schema:** `CURRENT_DATABASE_SCHEMA_VERSION = 59` (`src/mockingbird/storage/database.py:46`) — matches.
- **Lane P:** `CLOSED` (real `LICENSE` file, MIT, confirmed on disk; `pyproject.toml`/`web/package.json` metadata corrected — per Global Product & Release Readiness Reconciliation v2).
- **Lane R:** `OPEN — RELEASE-CRITICAL — TRUE LATENCY TAIL EVIDENCE REMAINS`, per the top-of-file "CURRENT PHASE" narrative in `docs/release-execution-state.md` (its own most-recently-appended paragraph, Representative Daylight True-Latency Tail Convergence v4, 2026-09-07).
- **Current authorization at start:** `NONE` — matches.
- **Active writers:** none. `ps aux` found no running `mockingbird`/`uvicorn`/`camera_node`/`deploy_windows_dev` process in this sandbox at the start of this session.
- **The seven preserved untracked detector files:** present, untouched, and unmodified throughout this milestone (verified via `git status --porcelain` at start; nothing in this milestone's own read-only work could have touched them, and a final check below reconfirms this):
  - `docs/wildlife-detector-training-contract.md.orig`
  - `scripts/evaluate_small_bird_detector.py`
  - `scripts/materialize_wildlife_stage2.py.orig`
  - `scripts/train_wildlife_stage2_rfdetr.py.orig`
  - `src/mockingbird/detectors/small_bird_benchmark.py`
  - `src/mockingbird/training/wildlife.py.orig`
  - `tests/test_small_bird_benchmark.py`

No newer accepted evidence or materially different Lane R state was found than the directive's own "expected accepted baseline." The repository's history is, however, **substantially deeper than any single memory summary of it** — there are eleven numbered Representative Daylight Gate A Field Acceptance reports (v4 through v14, not only v9/v12), three "True-Latency Tail Convergence" reports (v2/v3/v4), and — critically — one full prior attempt to declare Gate A **PASS** and Lane R **CLOSED**, which was reviewed and explicitly rejected the same evening it was written. §2 and §3 below reconstruct this completely from primary sources.

---

## 2. Authoritative cohort inventory

All facts below were extracted directly from the named report files and, where noted, independently cross-verified against raw JSON ledger/calibration artifacts on disk (not assumed from prose summaries).

### 2.1 Cohorts contributing to the true (T0→T5, RTT-normalized) latency distribution

| Cohort | Date | Accepted HEAD | Site/duration | n admitted | n valid latency | Median | p75 | p90 | p95 | Max | Raw artifacts on disk? | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v9 | 2026-09-01 | `17ce108` | Reference Pi, ~97.1 min | 25 | **24** | 111.8s | 145.5s* | 173.9s | 200.4s | 307.4s | Yes — `data/field-acceptance/2026-09-01-.../accounting-with-reviewer-dispositions/latency-report.json` (read, verified) | Intact, live-measured |
| v10 | 2026-09-02 (AM) | `b7e9724` | Same Pi, 90.2 min | 11 | **11** | 103.9s | 161.0s* | **201.5s**† | — | 742.3s | No (no `data/field-acceptance/` directory for v10 exists; per-sample table published in the report's own text was used) | Intact, live-measured |
| v11 | 2026-09-02 (PM) | `cd728ab` | Same Pi, 101.8 min (2 segments) | 23 | 23 (**reconstructed, not live-computed**) | 115.7s | — | 318.5s | 524.4s | 865.2s | Partial — raw ledger archive exists (`data/field-acceptance/2026-09-02-gate-a-v11-.../`) but the latency reconstruction itself was performed in an undisclosed, unarchived scratch copy by a *later* report | **Supporting/reconstructed only** — not independently visually re-verified against footage |
| v12 | 2026-09-03 | `fa9c8f0` | Same Pi, 96.97 min | 18 | **2** (of 5 attempted; 2 `unavailable_capture_time`, 1 `invalid_clock_mapping`) | 110.6s (n=2, "not a defensible distribution") | — | 145.2s | — | 153.9s | Yes — `merged_ledger_summary.json` (read in full) | Excluded from the "sized cohort" body (n too small; own raw ledger permanently lost its first ~37 of 97 minutes) |
| v13 | 2026-09-04 | `39a8fdc` | Same Pi, 101.8 min | **0** (evidence-capture defect: every burst request failed) | **0** | undefined | undefined | undefined | undefined | undefined | Yes | Excluded — zero admissions |
| v14 | 2026-09-05 | `1904421` | Same Pi, 102.68 min | 14 | **14** (100%, 0 invalid) | 82.9s | 152.8s* | 235.5s | 253.4s | 261.2s | Yes — `gate-a-accounting/latency-report.json` (read, verified) | Intact, live-measured |
| Gate A True-Latency Tail Closure v1 (dusk session) | 2026-09-05/06 | `bf7ee89` | Same Pi, 43.7 min | 1 | **1** (procedurally valid; independently judged likely a static object, not a bird) | n/a | n/a | n/a | n/a | 269.3s | Yes — `accounting/latency-report.json` (read, verified) | Excluded from tail-convergence accounting by the project's own explicit judgment (see §4.4) |
| Convergence v2 | 2026-09-06 | `e103092` | — | 0 (blocked at hard daylight gate, night) | 0 | — | — | — | — | — | n/a | No deployment occurred |
| Convergence v3 | 2026-09-07 | `e031291`→`f222217` | Same Pi, 75.2 min to stop-request / 76.0 min recorder span | 10 | **9** | 112.2s | 297.8s* | 385.1s | 433.7s | 482.4s | Yes — `accounting/latency-report.json` (read, verified byte-for-byte against report) | Intact, live-measured |
| Convergence v4 | 2026-09-07 | `fcf236f` | Different Stream/Zone, same Pi, 75.0 min (driver-internal) | 11 | **11** (100%, 0 invalid) | 94.5s | 130.5s* | 258.7s | 344.0s | 429.4s | No (dev-root is Windows-host-only; see §3.4) | Intact, live-measured |

\* p75 is not published by this project's own accounting tool in **any** report anywhere in this corpus (confirmed by direct search across all reports and by the tail-closure-v1 report's own explicit statement, "No cohort anywhere (intact or reconstructed) reports p75/IQR"). The p75 values above are **independently computed by this milestone** from raw per-sample data, using standard linear-interpolation percentiles (`numpy`'s default method), verified to reproduce every published median/p90/p95/max exactly for the three cohorts (v9, v14, Convergence v3) where raw JSON was available in this repository.

† **Independently-discovered evidence-integrity finding, disclosed per §4.3, below:** every prior report and reconciliation (v10's own report, v11, both Gate A Whole-Scene Budget correction and Gate A True-Latency Tail Closure v1, Convergence v2/v3/v4, and `roadmap.md`'s own "Numeric release budgets") cites v10's p90 as **183.3s**. Recomputing directly from v10's own 11 published per-sample values, using seven different standard percentile conventions (`numpy`'s `linear`/`lower`/`higher`/`nearest`/`midpoint` methods), **all seven** independently yield **201.5s**, not 183.3s. 183.3s is actually candidate-005's own individual latency value in the same table — the most plausible explanation is a transcription slip in v10's own report prose (reading the wrong row of an unsorted table), never independently recomputed or caught by any of the five subsequent documents that repeated it. This does **not** change any conclusion in this report (§4.3 quantifies why) and is **not** a product defect — it is a field-acceptance report accounting slip, now disclosed and corrected here for the first time.

### 2.2 Why v6, v7, v8, and the 2026-08-19 primary cohort contribute **zero** samples to true latency

This matters directly for comparability (my directive's Section 4 explicitly requires establishing this, not assuming it):

- **2026-08-19 primary cohort, v6, v7:** all predate the T0→T5 instrumentation entirely (`capture_to_visible_latency.py`, accepted 2026-08-31 by Gate A Measurement Closure v1). Retroactively applying the real instrumentation to their own preserved raw ledgers (done by that same milestone) found **every single admitted proposal in all three cohorts reports `state: unavailable_capture_time`** — 12/12 (2026-08-19), 0/0 (v6, zero admissions), 25/25 (v7). Their own reports separately publish a **different, proxy metric** ("activity-end → arbitration-decision" latency, not capture→visible), which must never be pooled with the true T0→T5 figures used from v9 onward — doing so would silently mix two different measured quantities. v6's own proxy-metric "n=263" is not a latency-sample count at all; it is a count of *distinct blocked proposals*, since v6 had zero admissions to measure.
- **v8:** the reference Camera Node's installed software (69 commits behind, predating the RTT protocol) made **all 796 attempted RTT-calibration batches `insufficient_samples`** — 0/27 admitted candidates measured (`invalid_clock_mapping`, 27/27). This is an **infrastructure gap, already closed** (the Node was upgraded before v9 ran), not a recurring or unresolved concern.
- **v5:** 19 admissions, but latency was "not meaningfully instrumented this session" (predates the contract); its own raw ledger is separately confirmed permanently unrecoverable.
- **v4:** 0 admissions (the sustained-activity admission-starvation defect this session discovered and which was fixed immediately afterward) — no latency is computable from zero admissions.

None of this is a documentation gap this milestone needs to close — every one of these facts is already disclosed, in each report's own text, and independently reconfirmed here.

### 2.3 Per-cohort procedural validity, biological validity, and fallback participation

| Cohort | Fallback-admitted samples | Known biologically-questionable admitted sample(s) retained in the latency figures |
|---|---|---|
| v9 | 3 of 24 (`fallback_measured=3`) | 1 of 5 confirmed-false Visits carried a confident wrong species label (Gate B residual, unrelated to latency validity); its own latency value is retained unmodified |
| v10 | 2 of 11 rescued via fallback (fallback-chain counters: 3 attempted / 2 admitted / 1 exhausted) | none disclosed |
| v14 | 1 of 14 (`fallback_measured=1`) | 1 confirmed false Visit ("other background/artifact," 1/14); latency retained unmodified |
| Convergence v3 | 3 of 9 | none disclosed |
| Convergence v4 | 1 of 11 (candidate-008, position 1) | **candidate-005 (57.1s)** — on direct visual review, more likely a person and an accompanying small pet than a wild bird; the same already-documented person/pet confound class *Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1* and v9 already characterized. Latency retained unmodified, per this project's own abstention-over-fabrication discipline. |
| Dusk session (excluded) | 0 of 1 | the sole sample itself — independently judged likely a static, misclassified feeder component under fading light, **not a real subject of any kind** (not merely a non-target species) — the qualitatively different reason it is excluded from tail-convergence accounting rather than merely flagged (see §4.4) |

**Sensitivity check:** removing Convergence v4's candidate-005 (57.1s) from the pooled distribution changes nothing material — it sits well below the median and far from any percentile of interest (57.1s vs. a pooled median of 103.9s). The one dusk-session sample (269.3s) is already excluded from the pooled "intact" set in §2.1/§4 for the reason given above, not because it is inconvenient.

### 2.4 Comparability across cohorts — what is genuinely uniform and what is not

**Uniform across all six true-latency cohorts:** the same reference Camera Node hardware; the same accepted production stack (MDv5a ONNX @ `score_threshold: 0.1`, unchanged NMS/tracker/cache/eligibility configuration); the same RTT-bounded clock-calibration mechanism (proven method-correct and closed as of 2026-09-01, contributing a negligible ~9–15ms measurement-uncertainty budget against latency values in the tens-of-thousands-of-ms range — verified directly from raw JSON `mean_uncertainty_ms` fields: 11.1ms (v3), 15.2ms (v9), 9.3ms (v14)); the same T0→T5 definition (T0 = earliest constituent generation's RTT-normalized `start_captured_at`; T5 ≡ `decided_at`, per Gate A Measurement Closure v1's own proven T2–T5 collapse).

**Not uniform, disclosed here precisely rather than smoothed over:**
- **Session-stop procedure:** v9 through Convergence v3 all drove the accepted 45-min-minimum/75-min-maximum/≥12-sample-target stop contract **manually**, by an operator watching a ~5-minute status cadence and issuing `stop_observation` by eye (an explicit admission in *Field Acceptance Tooling Correctness & Preflight Closure v1*'s own report). **Convergence v4 is the first and only cohort to have used the fully-automated, tested `field_acceptance_session_driver.py`** (monotonic clock, exact deadline enforcement, proven not to overshoot). This is a real procedural non-uniformity across the pooled set — but it affects *when a session stopped*, not how any individual sample's own latency was measured, so it does not compromise the pooled distribution's validity; it does mean Convergence v4 is the only cohort with a fully mechanically-verified (rather than operator-attested) stop-timing record.
- **Ledger-reconciliation tooling generation:** v9/v10/v11 used early or ad hoc snapshot tooling; v12 used a never-committed script with a real defect (0/12 periodic snapshots recovered any counterfactual payload — recovered only via one live post-stop fetch); v13 used the newly-committed tool, which itself had two real, since-fixed defects (proposal-identity collapse, gap-coverage mis-scoring) that produced its own disclosed 44.6% `proposal_outcomes` completeness (a tooling artifact, not real data loss — later proven via full reconciliation of v13's own preserved 21-checkpoint archive: 350/350 recovered, zero real gaps); v14 and Convergence v3/v4 all ran under the fully-fixed tool, achieving 100% `COMPLETE` reconciliation on all three ledger artifacts with zero gaps. **This affects evidence-survival/recall accounting far more than latency accounting**, since a latency sample requires only that its own admitted-Visit record exist (which the Visit-level API always preserved, independent of the periodic-snapshot tool) — but it is disclosed here for completeness.
- **v11 is fundamentally different in kind, not merely degree:** it is the only cohort in the pooled set whose latency figures were never computed by the session itself, or by any committed tool, at all. They exist only because a later, separate correction report performed an **undisclosed, unarchived, scratch-copy offline reconstruction** (restoring one dropped clock-calibration metadata flag) and explicitly labeled the result "not independently visually re-verified against footage." v11's own source report additionally contains an unreconciled internal inconsistency (its own "True latency" paragraph cites "24" visits where every other count in the same report, including its own false-Visit table, says 23). For all of these reasons, this report treats v11 as **supporting evidence only** — its median is used as a secondary cross-check, and its own max (865.2s) is disclosed prominently in every tail characterization below, but it is excluded from the primary pooled bootstrap reconstruction in §4/§5, exactly as the project's own most recent reports (Convergence v2/v3/v4) already do ("five intact cohorts," explicitly distinct from "sized cohorts" including v11).

---

## 3. Resolution of the two explicit v4 acceptance qualifications

### 3.A — Observation duration: start/stop vs. finalization/reporting timestamps

Read directly from Convergence v4's own report (§8, "Session") and independently re-derived with exact datetime arithmetic (not eyeballed):

- **Observation started:** `2026-09-07T21:03:26.968622Z` (confirmed via the authenticated `observation/start` response's own `started_at` field).
- **Stop *decision***: the monotonic session driver fired at **exactly 75.000 minutes internally** (`elapsed_seconds: 4500.031`, i.e. 31 milliseconds past the 4500.000s deadline — the driver's own documented clamp precision, not an overshoot of substance).
- **Stop *request* actually dispatched to the Host:** `2026-09-07T22:19:31.019Z`. Independently computed: this is **4,564.05 seconds (76.07 minutes) after start** — about **64.02 seconds longer** than the driver's own internal monotonic accounting (4500.031s).
- **Settlement confirmed** (`state == "stopped"`): 6.719 seconds later, after 3 polls.
- **Final raw-ledger snapshot taken:** `2026-09-07T22:20:00.147Z` — **4,593.18 seconds (76.55 minutes) after start**.
- **Independent recorder's own manifest** (frame timestamps, computed independently of the driver): 1,335 frames spanning 0–4,559,369ms = **75.99 minutes** — sitting between the driver's internal clock and the wall-clock stop-request gap, consistent with frames continuing to be captured for the tens of seconds between the driver's internal deadline and the stop request actually reaching the engine.

**Verdict:** the accepted "75-minute" Observation duration is accurate for what the driver itself enforces and reports (75.000 minutes internally, to 31ms). The ~64-second gap between that internal deadline and the stop request actually landing at the Host is ordinary process/HTTP dispatch latency for a driver process issuing an outbound stop call — not a hidden extension of the Observation runtime itself, and not finalization/settlement time (which is the further, separately-and-honestly-reported 6.7 seconds). The **total wall-clock footprint** from start to final raw-ledger snapshot is 76.55 minutes; of that, only **75.00 minutes is Observation runtime proper**, and the remaining **~93 seconds is stop-dispatch + settlement + snapshot-fetch overhead**, correctly excluded from the reported "Observation duration" and correctly not conflated with it anywhere in the report's own text. There is no disclosed or discovered overshoot of the governing 75-minute maximum in the sense that matters (the driver's own enforced runtime); the small additional wall-clock tail is explained, benign, and of the same character across every session in this corpus (compare Convergence v3's own explicit disclosure of an analogous ~2-minute gap between its own driver-tracked figure and its raw retained-activity window, §2.1).

### 3.B — Recorder readiness proven before Observation start

**Yes, proven, for Convergence v4 specifically — the first cohort in this project's history to do so mechanically rather than by operator attestation.** Convergence v4 was the first real field session to use the hardened `scripts/field_acceptance_recorder_readiness.py` gate (built by *Field Acceptance Tooling Correctness & Preflight Closure v1* and separately proven, against a real running subprocess, by *Field Acceptance End-to-End Integration Proof v1* — both of which ran and were accepted before Convergence v4). Per the report's own §8/§12: the recorder-readiness gate confirmed genuine advancing frames before the session was allowed to continue, and the independent recorder then ran the entire session with zero gaps exceeding 10 seconds (max gap 7.47s, 1,335 frames).

There is **no protocol deviation to preserve for Convergence v4 on this specific point.** The deviation that existed was in every *earlier* cohort (v9 through Convergence v3), each of which relied on operator vigilance rather than an automated gate — Convergence v3's own report explicitly narrates the operator personally catching and correcting an ordering slip by hand. This is already fully disclosed in §2.4's comparability discussion above and does not need to be reopened or refixed here; it is exactly the historical gap the tooling-correctness milestone was chartered to close, and it is closed, proven, and now field-demonstrated.

### Cleanup follow-up and ledger-completeness verdict

The 2026-09-07 18:40 commit (`0a776c8`) disclosed and fixed a real, but narrow and benign, post-report finding: killing the WSL-side `powershell.exe` wrapper for the periodic ledger collector does not terminate the native-Windows `python.exe` child it spawns across the WSL↔Windows process boundary. Two orphaned collector processes were found still polling the (already-stopped) product API every 600 seconds — read-only GETs against a stopped engine, touching no product state — identified by exact command line, confirmed as this milestone's own, and terminated; a repeat sweep confirmed zero remaining Windows-side processes. This corrects an inaccurate "no orphaned process" claim in the original report text but **does not change the milestone's classification (B) or any finding**, and does not touch evidence validity. This is not reopened here — it is a fully-resolved, already-fixed, benign tooling gap, and reopening the tooling implementation without a reproduced defect is explicitly out of this milestone's scope.

**Ledger completeness verdict (Convergence v4):** per the report's own §9, all three artifacts (`raw_detections` 20,858/20,858; `track_generations` 200/200; `proposal_outcomes` 162/162, 91 distinct proposal IDs) are **100% `COMPLETE`, zero gaps** — the fourth consecutive cohort (after v14) to achieve this. **Disclosed limitation on this verdict:** Convergence v4's raw checkpoint/ledger JSON files reside only on the Windows dev host (`C:\Users\<user>\AppData\Local\MockingBirdLatencyConvergenceV4`), not mirrored into this Linux repository, unlike v3/v9/v14 (whose raw JSON I read and independently cross-verified in §4). This milestone was therefore **unable to independently cross-check Convergence v4's completeness verdict or per-sample latency table against raw JSON**, and relies on the report's own internally-consistent, already-committed figures — precisely the kind of raw-data-availability limitation this milestone's own governing brief asked to be disclosed rather than silently assumed away.

---

## 4. Reconstructed latency distributions

### 4.1 Per-cohort statistics (independently recomputed from raw data where available)

See the table in §2.1. Where raw JSON was available in this repository (v9, v14, Convergence v3), every published median/p90/p95/max was reproduced **exactly** by this milestone's own independent computation (linear-interpolation percentiles over the raw `state == "measured"` samples). Where only the report's own published per-sample table was available (v10, Convergence v4), this milestone recomputed statistics directly from that table; all figures matched except the single, disclosed v10 p90 correction in §2.1/§4.3.

### 4.2 Pooled distribution — five intact, live-measured cohorts (v9, v10, v14, Convergence v3, Convergence v4)

Unweighted pooling of all 69 individual raw samples (each sample carries equal weight; no cohort is up- or down-weighted, since each is an independent real encounter under the identical accepted production stack — see §2.4 for exactly what is and is not uniform across them):

| Statistic | Value |
|---|---|
| n | 69 |
| Median | 103.9s |
| p75 | 154.2s |
| p90 | 259.2s |
| p95 | 339.4s |
| Max | 742.3s (v10, candidate-010) |
| Mean | 138.4s |
| Samples >300s | 5 of 69 = 7.2% (v9's 307.4s; v10's 742.3s; Convergence v3's 360.8s and 482.4s; Convergence v4's 429.4s) |

**Every valid procedural sample is preserved in this pool, including the five >300s outliers** — none is removed because it worsens the picture, per the governing instruction. Adding v11's reconstructed n=23 as a sensitivity check (not as a primary pooled figure, per §2.4): the combined median moves only slightly (105.5s), the combined max becomes 865.2s (v11's own reconstructed value), and the p90 moves to 262.8s — none of these shifts changes any conclusion below.

### 4.3 The v10 p90 evidence-integrity finding, quantified

v10's own 11 published per-sample "Full T0→T5" values are: 76.5, 85.2, 183.3, 103.9, 79.4, 114.8, 201.5, 742.3, 69.3, 74.7, 138.7 (seconds). Sorted: 69.3, 74.7, 76.5, 79.4, 85.2, **103.9 (median, 6th of 11)**, 114.8, 138.7, 183.3, **201.5**, 742.3. The 90th percentile of 11 values, by every one of `numpy`'s seven percentile conventions (`linear`, `lower`, `higher`, `nearest`, `midpoint`, and the two rank-based variants), is unambiguously **201.5s** — the 10th of 11 sorted values, immediately below the maximum. **183.3s is candidate-005's own individual latency value**, not the 90th percentile of the set; no percentile convention this milestone tried produces 183.3s from these 11 numbers. The most plausible explanation is a transcription slip in v10's own report prose. This figure (183.3s) was then repeated, unquestioned, in v11's report, both Gate A correction reports, `roadmap.md`'s own "Numeric release budgets," and both Convergence v3 and v4's own cross-cohort tables — none of which recomputed it from v10's own already-published table.

**Materiality: none.** The corrected value (201.5s) still falls inside every previously-stated cross-cohort p90 band (173.9–318.5s pre-Convergence-v3; 173.9–385.1s including Convergence v3), so no prior band statement, budget discussion, or decision in this project's history was actually invalidated by the error — it simply went unverified for five consecutive documents. This is disclosed here as a concrete demonstration of exactly why raw-artifact verification matters, not as a correctness defect requiring further action.

### 4.4 Procedural vs. biological validity

Per §2.3: two samples in this project's history are procedurally valid (they passed the RTT-calibration/measurement pipeline correctly) but biologically questionable. Convergence v4's candidate-005 (person + pet, 57.1s) is retained unmodified in every statistic above, per this project's own consistent abstention-over-fabrication convention — its value is unremarkable (well below the median) and changes nothing. The separate dusk-session sample (269.3s, independently judged likely a static, misclassified object rather than any real subject) is excluded from the pooled "intact" set above, consistent with (not overriding) the project's own explicit prior judgment — the distinction the project draws is between "a real, moving, non-target subject" (retained, since a genuine detection-to-decision timing measurement occurred) and "most likely no real subject/event occurred at all" (excluded, since there is no real encounter whose latency is meaningfully being measured). This report preserves that distinction rather than second-guessing it, since it is well-reasoned and independently defensible on its own terms.

---

## 5. Statistical / release-budget contract

### 5.1 The ≥12-valid-sample criterion: origin, nature, and current status

Traced to its exact source, independently, three ways (report-text extraction, `release-execution-state.md` §3 extraction, and direct source-code inspection):

- **It is a per-session procedural stopping target, not a statistical minimum, not a release-gate requirement, and not a historical convention.** *Gate A True-Latency Tail Closure & Final Lane R Decision v1* (2026-09-05) states this explicitly and is the first document anywhere in this project's history to state a number at all: *"no prior Gate A milestone states a numeric minimum valid-sample count or stopping rule anywhere in the archaeology... this milestone's own governing brief's ≥12-samples/≥45-minutes default... is therefore used as specified (no better-justified numeric prior exists to substitute)."* No statistical power calculation, confidence-interval argument, or other derivation for the number 12 exists anywhere in this corpus.
- **Confirmed directly in code:** `scripts/field_acceptance_session_driver.py:124`, `target_sample_count: int = 12`, one field of `SessionDriverConfig`. Its role (`decide_stop`, line 163): a session may stop **before** the 75-minute maximum only if it has *already* run at least 45 minutes **and** accumulated 12 (live-proxy) samples; the 75-minute maximum always fires regardless of sample count. This is unambiguously a **session-length stopping heuristic**, not a pooled-evidence-sufficiency test.
- **The "12" tracked live during a session is a proxy** (`candidates_created`), not the final procedurally-valid count — the true valid/invalid split is only known after the fact, from offline accounting against the reconciled ledger. This is stated explicitly by *Field Acceptance Tooling Correctness & Preflight Closure v1*'s own report.
- **It has never been waived or silently reinterpreted.** Every session that fell short (Convergence v3: 9; Convergence v4: 11; the dusk session: 1) reports this honestly as an unmet target, at Classification B, without rounding up.
- **It has already been independently satisfied at the individual-session level.** *Representative Daylight Gate A Field Acceptance v14* (2026-09-05) produced **14** procedurally-valid samples (100% of 14 attempted, zero invalid) — a session that, on its own terms, already cleared this bar with a fully-`COMPLETE` ledger and zero disclosed defects. The subsequent narrative continued to cite "≥12 not yet met" **specifically with respect to each new individual session** (v3=9, v4=11), which is accurate for those two sessions in isolation, but this framing has never been reconciled against the fact that the target was already met once, nor against the much larger pooled evidence base.
- **This report's own reading, stated plainly, per the governing instruction not to silently reinterpret an accepted requirement:** the ≥12 figure remains a legitimate per-session procedural convention for how long any one field session should run, and it has not been met by the two most recent individual sessions. It is **not**, and should not be treated as, a statement that the accumulated cross-session evidence base is insufficient — that is a separate question this report answers directly in §5.2–§5.3 using the actual pooled sample count (69) and a transparent uncertainty method, not by asserting a number.

### 5.2 Quantifying uncertainty: is per-cohort p90 divergence real non-convergence, or expected sampling noise?

This is the central open statistical question left by every report since the 2026-09-05 correction, and no prior document in this project's history has actually quantified it — each treats "the p90 values differ across cohorts" as self-evidently meaning "the tail hasn't converged," without checking whether that much scatter is what ordinary small-sample percentile estimation looks like.

**Method:** treat the 69-sample pooled dataset (§4.2) as the current best estimate of the true underlying distribution. Bootstrap-resample (20,000 resamples, with replacement) at each individual cohort's own actual sample size, and ask: how much would a single cohort's own p90 estimate scatter, purely from sampling noise, if the true distribution were exactly this stable pooled one?

| Cohort n | Bootstrap 90% interval for that cohort's own p90 estimate | That cohort's own *actually observed* p90 |
|---|---|---|
| 9 (Convergence v3) | [123.8s, 440.0s] | 385.1s — **inside** |
| 11 (v10 / Convergence v4) | [128.7s, 429.4s] | 201.5s / 258.7s — **both inside** |
| 14 (v14) | [138.7s, 415.3s] | 235.5s — **inside** |
| 24 (v9) | [157.2s, 398.9s] | 173.9s — **inside** |

**Every single observed per-cohort p90 value falls comfortably within the range of pure sampling variability expected at that cohort's own sample size, if a single stable underlying distribution is assumed.** This is a materially important, previously unquantified finding: the repeated observation that "no two cohorts' p90 values agree" is not, by itself, evidence that the tail is an unconverged, moving target — it is close to what a right-skewed latency distribution's 90th percentile is *expected* to look like when estimated from samples of size 9–24. This does not mean the tail is now "solved" — the pooled estimate itself still carries real, honestly-quantifiable width: bootstrapping the pooled p90 directly gives a point estimate of 259.2s with a 90% CI of **[198.6s, 331.8s]** — a real, ~133-second-wide band of remaining uncertainty. The median, by contrast, is genuinely tight: pooled point estimate 103.9s, 90% CI **[80.3s, 114.8s]** — a 34.5-second-wide band, already smaller than any single cohort's own reported median-to-median spread.

**Answering the governing brief's explicit question directly: requiring each small cohort's own p90 to independently fall inside a tight band, before any latency evidence is treated as sufficient, is not statistically justified at these sample sizes.** The correct standard is the pooled distribution's own uncertainty (quantified above via bootstrap, a transparent, standard, appropriate method for exactly this kind of question), not agreement between individually-noisy small-sample estimates of the same underlying quantity. This is not a manufactured precision — the pooled p90's own honest uncertainty (±~65s around 259s) is real, disclosed, and still fairly wide; the finding is specifically that *inter-cohort disagreement is not additional evidence beyond that width*, not that the uncertainty has vanished.

### 5.3 Maximum / hard ceiling

No statistically-fit "maximum" is defensible from n=69 (or n=92 including v11) samples of what is evidently a moderately heavy-tailed distribution — a sample maximum is a biased, high-variance estimator of a true upper bound, and this report does not attempt to invent one. What **is** defensible, and disclosed rather than manufactured: every observed >300s sample (six of them, across all cohorts, including v11's reconstructed 865.2s) has been individually or mechanistically root-caused to the same accepted design (§6) — the architecture itself provides a **hard, by-design ceiling of 20 minutes (1,200 seconds)** (`maximum_component_pending_ms` / the bounded decision-horizon fix), beyond which a component's admission decision is forced. Every real observed maximum to date (742.3s / 12.4 min intact-live-measured; 865.2s / 14.4 min reconstructed-only) sits at 62–72% of that architectural ceiling, never beyond it. This is the honest, evidence-grounded "hard maximum" statement available: not a tight numeric SLA, but a real, architecturally-guaranteed worst case, with the actual observed range disclosed alongside it.

### 5.4 Comparability / pooling justification

Per §2.4: the five pooled cohorts share the identical production stack, detector, thresholds, clock-calibration mechanism, and latency definition; they differ in session-stop-timing tooling generation (manual through Convergence v3, automated for Convergence v4 only) and ledger-reconciliation tooling generation (three successive generations across v9–v14, all fully fixed by v14). None of these differences affects how any individual sample's own latency was computed. Pooling is therefore justified for characterizing the *distribution itself* (median, tail shape, presence/absence of a new causal mechanism); it would **not** be justified for metrics those tooling differences directly affect (e.g., cross-cohort evidence-survival percentages, which is why this report does not attempt to re-derive those and defers entirely to the already-accepted, already-harmonized figures in `roadmap.md`'s "Numeric release budgets").

---

## 6. Causal / correctness review of every >300-second case

Every procedurally-valid sample exceeding 300 seconds, across all six true-latency cohorts, is accounted for below. No new perception investigation was launched; this section reviews only already-accepted evidence.

| Cohort | Sample | Value | Cause (as already established, cross-checked here) |
|---|---|---|---|
| v9 | candidate-027 | 307.4s | 9 chained track generations over a genuine ~4m11s sustained encounter, plus a 56.0s tail-latency wait before the episode boundary was declared final — both components individually confirmed genuine (root-caused to the accepted Visit-Continuity/episode-boundary quiet-period design, which produces a tight ~48–60s "tail" *regardless of encounter length*). |
| v10 | candidate-010 | 742.3s | Track ends at session offset 3,384,378ms; a separate, visually-confirmed genuine bird encounter at the same feeder begins only ~350s later and does not itself resolve until offset 3,884,687ms; candidate-010's own finalization lands only after that *subsequent* encounter fully resolves. Same accepted mechanism, no new defect. |
| v11 (reconstructed) | (unidentified specific Visit) | 865.2s | Attributed at the mechanism level only (same Visit-Continuity/episode-boundary mechanism) — the reconstruction that recovered this value did not identify which of the 23 admitted Visits produced it. Disclosed here as a genuine, if narrower, limitation of this specific data point (consistent with its "supporting/reconstructed only" status throughout this report). |
| Convergence v3 | two samples | 360.8s, 482.4s | Both fully traced to the ledger's own arbitration/continuity records — no new mechanism, no correctness defect (per the report's own explicit causal classification). |
| Convergence v4 | one sample | 429.4s | Traced to a 69-generation, 32-proposal contested component — corroborated, for the first time alongside an intact live cohort, by real independent-recorder frames showing genuine activity at the scene's own feeder. Same mechanism. |

**Conclusion:** across every cohort, every long-tail sample is expected sustained-activity/continuity behavior — the deliberate, already-accepted design choice to prioritize never fabricating false continuity between separate animals over minimizing worst-case latency (the identical mechanism, and the identical trade-off, already accepted for the recall dimension — see §7.1). No unresolved pathological behavior, timestamp artifact, or false/static chain was found in any of the six cohorts reviewed here. This report does not reopen the accepted ambiguous-boundary or scene-confusor work, and finds no concrete new correctness defect to preserve a reproducer for.

---

## 7. Decision

### 7.1 Why this is not a repeat of the rejected 2026-09-05 PASS conclusion

The rejected reconciliation was invalidated for two specific, disqualifying reasons (independently reconstructed here from `git log` timestamps and the reports' own text, cross-verified three ways): (1) it silently excluded a known, disclosed, unfixed recall failure mode (`blocked_ambiguous_boundary`) from its own recall denominator and presented the resulting rosier number as the headline budget; (2) its own latency tail table **omitted** v10's already-accepted 742.3-second maximum. **This report does neither.** No denominator is redefined anywhere above; every sample, including every known outlier (v10's 742.3s, v11's reconstructed 865.2s, all five >300s samples in the primary pooled set), is disclosed and retained. The recall dimension is untouched here — it was properly, separately closed by an explicit external release-authority decision (`ACCEPTED KNOWN LIMITATION — NO NUMERIC RECALL FLOOR YET`, 2026-09-06), which this report defers to rather than re-litigates.

### 7.2 Proposed budget structure

This report proposes — as a recommendation for external release-authority acceptance, not a self-executed closure (see §7.3) — a deliberately narrow budget with three distinct parts, matching the shape the governing brief itself asked for (typical latency; upper-tail latency; whether a hard maximum is supportable; sustained/crowded behavior; known limitations):

1. **Typical latency (numeric, tight):** a MockingBird Visit typically becomes visible in **roughly 80–115 seconds** (pooled median 103.9s, bootstrap 90% CI [80.3s, 114.8s]) after the triggering activity is captured. This figure is well-supported: six independent real-world sessions across six different calendar days, using the unchanged accepted production stack, each independently measured a median within this same narrow band.
2. **Upper-tail behavior (qualitative, not a tight SLA):** roughly 1 in 10 Visits takes materially longer — observed cohort p90 values range 174–385 seconds (~3–6.4 minutes); §5.2's bootstrap analysis shows this scatter is consistent with normal small-sample estimation of a single stable distribution, not a moving target, but the pooled estimate itself still carries genuine width (90% CI 199–332s). This should be disclosed to users qualitatively ("most Visits appear within about two minutes; occasionally, especially during busy or sustained activity, it may take several minutes longer"), not as a committed number.
3. **Ceiling (architectural, not statistically-fit):** no numeric maximum/SLA is adopted. The architecture itself guarantees resolution within a hard 20-minute (1,200-second) decision horizon by design; real observed maxima to date (up to 742.3s intact-measured, 865.2s reconstructed-only) have never exceeded ~72% of that ceiling. This is the honest ceiling statement available and should be the one used in any release documentation, rather than a number fit to six sessions' worth of observed maxima.
4. **Sustained/crowded activity — disclosed together with recall, as one limitation, not two footnotes:** the identical mechanism (episode-boundary/ambiguous-boundary arbitration) that produces the accepted recall limitation (may not create a Visit for every bird during unusually busy, continuous activity) also produces the longest latency tails. Both costs are safe (omission or delay, never a false merge or fabricated continuation) and should be disclosed to users as one coherent product characteristic: *"during unusually busy, continuous activity, MockingBird may occasionally miss creating a separate Visit for a later arrival, or take noticeably longer to finalize one, rather than risk incorrectly merging two different animals."*
5. **Known limitations carried forward explicitly, per this report's own findings:** the ≥12-per-session target has not been independently re-met since v14 (Convergence v3: 9; Convergence v4: 11), though the pooled six-day, 69-sample evidence base is far larger than that figure in any aggregate sense (§5.1); v11's contribution is supporting/reconstructed evidence only, not independently re-verified; v10's own report's p90 figure is corrected from 183.3s to 201.5s with no material effect (§4.3); all sessions before Convergence v4 used manual, not automated, stop-timing (§2.4).

### 7.3 What this report does and does not decide

Consistent with how the recall dimension was properly closed (engineering characterizes the evidence; an external release authority makes the product-risk-tolerance call), this report **recommends** Classification A and the budget in §7.2 for the next external (ChatGPT) reconciliation to accept, correct, or reject — it does **not** itself flip Lane R to `CLOSED` or declare Gate A `PASS`. If the release authority instead wants a tighter numeric p90/maximum figure before accepting a budget, §9 names the smallest additional evidence that would actually inform that specific question (not "another identical session," which §5.2 shows would not, by itself, resolve anything the current pooled evidence does not already characterize).

---

## 8. Global release sequencing

Reconciled against `docs/release-execution-state.md` §5/§6 (every lane A–S), confirmed directly rather than assumed:

| Lane | Status |
|---|---|
| A. Acoustic/BirdNET | ACCEPTED — release-ready optional |
| B. Remote/Intermittent-WAN | PARTIAL — correctly deferred after release |
| C. Everyday Product/Discovery UX | Materially delivered, no known dev remains |
| D. Calm Notifications | Materially delivered |
| E. Mobile/Remote UX | Partial, materially advanced |
| F. Multi-Camera/Multi-Site | Materially advanced |
| G. Camera/Source Experience | CLOSED — release-critical |
| H. Site-Specific Learning | FROZEN |
| I. Broader Wildlife | FROZEN structurally |
| J. Ecological/External Workflows | Materially advanced |
| K. Ecosystem/Provider Integrations | DECISION CLOSED — deferred |
| L. Appliance/Update/Recovery | Materially closed — release-critical |
| M. Storage/Retention UX | CLOSED — release-critical |
| N. Privacy/Contribution | CLOSED — release-critical |
| O. Platform/Runtime Portability | CLOSED |
| P. Release Engineering/Distribution | CLOSED — release-critical (MIT, confirmed on disk) |
| Q. Whole-Product UI/Accessibility/Performance | CLOSED as an integrated pass |
| **R. Complete Field Acceptance** | **OPEN — subject of this report** |
| S. Actual Final Release Hardening | LAST — awaits R |

**Lane R is the sole remaining release-critical gate.** Every other lane is closed, frozen, or correctly deferred to after release, and the durable, evidence-based feature freeze (`docs/roadmap.md` "Release readiness vs. continued capability work," 2026-09-06 finding) is confirmed intact and is preserved by this report — nothing here reopens any deferred product-enrichment item.

**Sequencing implication of this report's own recommendation:** if the release authority accepts the §7.2 budget, the correct next lane is Gate G (External Pre-Release Acceptance), followed by Lane S (Final Release Hardening), followed by the one public launch — no separate beta, per the accepted one-release doctrine. **Comparison with the alternative named in this report's own directive:** bounded External Pre-Release Acceptance cohort/finding-intake *planning* (not execution) does not depend on daylight and could, in principle, be considered independently of Lane R's own remaining evidence question. This report does **not** authorize or begin that planning — it is named here only for the comparison the governing brief explicitly asked for. Given that this report's own recommendation is that Lane R's evidence is now sufficient for a scoped budget decision (not that more field evidence is the bottleneck), the stronger near-term action is the release authority's acceptance decision on §7.2, not parallel EPRA planning.

---

## 9. Smallest remaining evidence need, if the recommendation above is not accepted as-is

This report's own position (§7) is that no further field session is required to accept the proposed budget. If the release authority instead wants a **tighter numeric p90/maximum figure** (rather than the qualitative tail disclosure and architectural-ceiling reference proposed above), the smallest evidence that would actually inform that specific, narrower question — not "another identical 75–100 minute session," which §5.2 shows would only add another noise-consistent data point — would be:

- A session or reanalysis specifically targeting **sustained/crowded activity density** (the one condition every >300s sample in §6 shares), to characterize whether tail frequency/severity scales with activity density in a way six ordinary sessions cannot distinguish from baseline noise; and/or
- An offline pass (no new field time needed) applying this report's own bootstrap method to any additional cohort's raw ledger that becomes available for other reasons, to narrow the pooled p90's own 90% CI (currently ±~65s) further without requiring a dedicated Lane R session.

Neither is proposed as a requirement of this report's own recommendation; both are named only as the answer to "what would change the decision," per the governing brief's own instruction not to default to requesting another identical session.

---

## 10. Classification

**A — READY FOR RELEASE BUDGET**, specifically and only for the scoped, three-part structure in §7.2 (typical latency: numeric; upper-tail: qualitative; ceiling: architectural, not statistically-fit) — **not** a claim that Gate A is self-closed or that Lane R is closed by this report. Recall remains separately, already resolved (accepted known limitation, no numeric floor). No correctness defect blocks this recommendation (§6). The evidence-integrity finding in §4.3 (v10's own p90 correction) is disclosed and shown to be non-material.

---

*Prepared as a read-only evidence and decision milestone. No product, schema, or tooling code was changed. No field session was run. No deployment occurred. No push was made.*
