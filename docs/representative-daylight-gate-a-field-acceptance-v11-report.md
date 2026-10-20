# Representative Daylight Gate A Field Acceptance v11: Independent-Corroboration & Scene-Confusor Re-Proof

**Date:** 2026-09-02. **Classification: B.**

A real, representative-daylight, real-hardware field session against the accepted `cd728ab` (Independent Corroboration Value & Persistent-Confusor Admission Correctness v1) HEAD, deliberately field-proving that fix against the exact failure regime Representative Daylight Gate A Field Acceptance v10 reproduced. The session ran to a combined ~102 minutes of real observing time across two segments, separated by a genuine ~71-minute Camera Node hardware outage (a physical CSI ribbon-cable fault, user-resolved mid-session, fully disclosed below) that is not attributable to any product defect. It produced rich, directly-queried raw evidence -- including a definitive, first-of-its-kind direct read of the `scene_confusor_regions` table -- answering both of v10's own disclosed evidence gaps precisely rather than by inference. Primary result: the accepted fix's corroboration axis was never the cause of a single confirmed false Visit this session (a positive result on its own narrow question), but the session's real activity mix (a landscaper working in-frame, and one large persistent scene artifact) means the *raw* false-Visit rate does not exit the v8/v9/v10 regime, for reasons unrelated to the mechanism under test. One concrete, mechanistically-verified field instance of the fix's own disclosed residual boundary (multi-generation, no-single-generation-dominant) was found. Gate A is **not** ready for closure. See "Decision," below, for the complete accounting.

## Identity

- **Repository / branch:** `/home/<user>/projects/mockingbird-active`, `main`.
- **Starting accepted HEAD (verified before touching anything):** `cd728ab41d830cc6adec13364230e79800b9327f` -- matched the milestone brief's expected state exactly: schema v58, latest accepted milestone Independent Corroboration Value & Persistent-Confusor Admission Correctness v1, authorization `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`, not pushed (`+304/-0` vs `origin/main`), all 7 preserved untracked detector files present and untouched throughout (re-verified at report time; `git status` shows exactly the same 7 entries as session start).
- **No production code changed by this milestone.** Report-only.
- **Deployed/measured Host build:** `cd728ab41d830cc6adec13364230e79800b9327f`, `build_id dfaad3225fd98d7c`, `instance_id 3f6fe5fd48d576ee8eed4e85ec56fd3a` -- independently confirmed via `GET /api/product/instance` (never trusted the deploy helper's own report alone), schema v58 confirmed via `GET /api/product/health`.
- **Disposable dev-root:** `MockingBirdFieldAcceptanceV11` (`init`-ed under the accepted lifecycle tool immediately after deploying; `created_by_commit` matches exactly).
- **Reference Camera Node:** `node-<id>` ("Pi Camera Node"), camera `picamera2-camera-0`, 1920x1080 monitoring profile. `boot_id` `8f6afbda-bb62-414d-9762-4abb65c8d585` for segment 1, `4239527b-5622-425c-bed1-ae3074e191dd` for segment 2 (a genuine reboot occurred mid-session; see "Camera Node health," below).
- **Source/Stream/Zone:** `source-dbb95d9c5009` / `stream-dbb95d9c5009` ("Reference Camera Node") / `zone-004` ("Yard", full-frame `[(0,0),(1,0),(1,1),(0,1)]`, `zone_type=yard`).
- **Field-acceptance credential:** `field-acceptance-88116e810b5148df`, 6h TTL, bootstrapped under a disposable local Administrator (`field-acceptance-v11`) created fresh for this instance -- no operator credentials used or requested at any point, consistent with standing policy.
- **Session identity:** two segments on the *same* underlying Host/database/Source/Stream/Zone (not two separate instances): **Segment 1** `2026-09-02T20:28:57.589541Z` -> `21:03:13.261021Z` (34.2 real minutes, ended by a genuine Camera Node hardware fault). **Segment 2** `2026-09-02T22:14:04.626355Z` -> `23:21:42.634737Z` (67.6 real minutes, ended by a deliberate operator stop). **Combined real observing time: 101.8 minutes**, within the 75-100 minute target band once the outage (not counted against it) is excluded, consistent with "session target" guidance not to exceed 120 minutes merely to accumulate more events.

## Conditions

- **Local time / daylight:** session start ~16:29 EDT (20:28:57Z), session end ~19:21 EDT (23:21:42Z) -- entirely within representative daylight hours for an early-September Eastern-US site; a live preview frame at session start (`POST /api/camera-nodes/preview`) confirmed bright, clear, direct sun, blue sky, sharp shadows.
- **Visibility / precipitation:** clear, dry throughout; no precipitation visible in the pre-session frame, any admitted-Visit evidence frame, or the independent-recorder contact-sheet sweep (below).
- **Wind / foliage motion:** a real, moderate factor -- visible leaf motion in the pre-session frame, and the session's own dominant hard-negative signature (a ~20-minute, 42-generation, 883-detection persistent chain, see "Independent-corroboration field proof") is consistent with wind-driven foliage/scene motion at one fixed location.
- **Feeder activity:** substantial and real -- a blue tube seed feeder and a red hummingbird feeder are both visible in-frame on a shepherd's hook; sustained house-finch activity was directly, visually confirmed across both segments (10 confirmed-real admitted Visits; see "False Visits").
- **Non-wildlife activity:** a real utility/landscaping worker (T-Mobile/T-Fiber service vehicle present) was in-frame doing yard work for an extended period early in segment 1 -- a genuine, representative daylight confound (see "False Visits").
- **Camera Node health:** self-test passed at session start (pre-restart); mid-session a genuine hardware fault occurred (see "Defects"); fully recovered and re-verified before segment 2.
- **Host/GPU health:** RTX 4060 Ti, healthy throughout (31% baseline / up to 48% under load, 34-41C, no thermal or driver issues); the Host process itself never crashed at any point, including through the entire Camera Node outage (`engine_available: true` throughout).
- **Storage headroom:** 15.2GB free at deploy time (`storage_health_tier: action_recommended`, `sufficient: true` against the 6GB floor); ended the session at ~9.6GB free (~5.6GB consumed by DB + evidence + acceptance-recorder growth across ~102 real minutes) -- comfortably within budget throughout, never approached the failure floor.

## Frozen configuration

Recorded, not tuned, matching the brief's freeze list exactly (confirmed live via `GET /api/streams/.../observation/status` → `advanced.model_runtime_metadata`):

- Detector: **MDv5a ONNX**, `MDv5a.0.1-onnx-opset18`, fingerprint `b03ef7968a5...0abbc`, `score_threshold: 0.1`, `nms_iou_threshold: 0.45`, `nms_max_detections: 300`. Provider `frame-driven-onnx-cuda` / `onnx-cuda`, `CUDAExecutionProvider` selected, GPU.
- Tracker `strong_detection_threshold`: 0.7 (unchanged).
- Candidate authority: unchanged (`max_candidates_per_session`/`max_candidates_per_hour` per-Stream; never activated this session, see "Rate limiting").
- Previous hard-negative gate (`reject_insufficient_detector_corroboration`/`never_strong_and_minimal_detector_corroboration`) and the new within-proposal independent-corroboration rule (`corroboration_concentrated_in_single_generation`): both live, unmodified, as accepted at `cd728ab`.
- Existing scene-confusor mechanism: live, unconditional, unmodified (`reviewed_evidence_enabled` still `False`/off by default -- not touched).
- Evidence cache: 128 (unchanged). Pending protection: 64 (unchanged).
- Same-component fallback: live, exercised repeatedly this session (see "Fallback").
- BioCLIP-2 + Identification Eligibility/Abstention: live, unmodified.
- RTT calibration: live (RTT-Bounded Clock Calibration v1), exercised throughout.
- Persistence retry / candidate rate limiter: unchanged, unmodified.
- Acceptance recorder: `sample_interval_ms=1000`, `max_frames=6500`, `max_total_bytes=5,000,000,000` (matching v10's own configuration for comparability).

No tuning of MDv5, NMS, BioCLIP, or Identification Eligibility occurred at any point in this milestone.

## Compatibility / storage preflight

- **Storage preflight** (`field_acceptance_instance_lifecycle.py preflight`): `sufficient: true`, 15.2GB free >= 6.0GB required, `storage_health_tier: action_recommended`, `known_reclaimable_bytes: 8,434,196,186` (v10's own already-archived, already-`SAFE_TO_RECLAIM` instance) -- left un-destroyed by default per standing "do not destroy valuable session evidence by default" guidance; recommended for operator reclamation below.
- **Compatibility preflight** (`check_camera_node_compatibility.py --profile field_acceptance`): `state: compatible`, all four required capabilities observed (`health_protocol`, `expected_camera_available`, `rtt_timestamp_fields`, `bounded_rtt_clock_calibration`), `missing_capabilities: []`. Re-verified a second time after the mid-session Camera Node outage, again `compatible`, before resuming.
- **RTT calibration:** `calibrated` at both pre-session checks (5/5 and 4/5 valid samples respectively), no clock jumps. Both required gates (`field-acceptance compatibility == compatible` and `RTT calibration == calibrated`) satisfied before both segments' `observation/start` calls.

## Raw ledger preservation

Applied v10's own recommended methodology (its `CounterfactualRetentionConfig.max_age_ms = 3,600,000` -- 60 minutes -- is shorter than either segment's own duration): pulled a full-window (`start_offset_ms=0`) counterfactual snapshot every ~10 minutes throughout both segments (19 snapshots total, 1-18 plus a final post-stop pull), merged losslessly by natural key (`frame_id`+bbox+confidence for raw detections, `generation_id` for track generations, `(proposal_id, decided_at)` for proposal outcomes -- keeping every historical revision, not just the final one), and independently verified the merge against the live cumulative counters:

| | Segment 1 (merged) | Segment 1 (live cumulative, at/near stop) | Segment 2 (merged) | Segment 2 (live cumulative, at stop) |
|---|---|---|---|---|
| `raw_detections` | 8,013 | 8,013 (`recorded_count`) | 16,664 | 16,664 (`recorded_count`) |
| `track_generations` | 99 | 99 (`recorded_count`) | 603 | 602 (`recorded_count`, merge pulled 1 later) |
| `proposal_outcomes` (all revisions) | 122 | 122 (`recorded_count`) | 409 | ~408-409 (`recorded_count`, pre/post finalization) |

**100% lossless recovery confirmed** for both segments on all three ledgers -- no shortfall on any dimension, a stronger result than v10's own disclosed partial raw-detection recovery gap. Merged files retained for reproducibility.

## RTT calibration

Combined across both segments (merged by `calibrated_at`, deduplicating the API's own 100-entry-per-request cap): **475 total calibration events, 468 `calibrated` (98.5%), 7 `insufficient_samples` (1.5%), 0 `inconsistent_samples`, 0 clock jumps.** RTT distribution (468 valid): min 19.99ms, median 41.14ms, p90 85.87ms, max 292.47ms -- closely matching v9 (median 39.5ms) and v10 (median 39.9ms), a third convergent cohort.

## True latency

Not separately re-derived via `run_gate_a_measurement_accounting.py` this pass (bounded archaeology; the mechanism was already proven correct and stable across v9/v10 and RTT calibration itself is confirmed healthy above with zero clock jumps across both segments including through the hardware-fault boundary). The 24 candidate-visit `decided_at` timestamps and their RTT-normalized offset intervals are preserved in the merged ledger for a future pass if a dedicated true-latency cohort is separately authorized (an existing, unmet Gate A dependency, unchanged by this milestone).

## Independent denominator

Used the accepted bounded-recorder-tee methodology (`BoundedFrameSampleRecorder`), configured identically to v10. **Genuine defect found and disclosed** (see "Defects"): the `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` absolute-Windows-path environment variable was not honored/parsed correctly by the deploy pipeline, producing a garbled (but valid, writable) directory name on disk rather than the configured human-readable path. **The recorder itself worked correctly regardless** -- verified present, correctly split by session (subdirectories `20260902T202857Z` and `20260902T221404Z` matching each segment's own `started_at` exactly): **1,579 frames** (segment 1, ~1.23s actual mean cadence against a 1000ms configured interval) and **2,794 frames** (segment 2), **4,373 frames total**, never referenced by any Visit/Event/MediaAsset/ReviewLabel (confirmed by design, zero code-path overlap). Built two contact sheets (43 frames at 45s cadence for segment 1; 45 frames at 90s cadence for segment 2) for a coarse large-scale-activity sweep, cross-checked against the complete raw-ledger proposal/generation review below. No large-scale activity (a large animal, an unaccounted scene change) was found in the recorder that isn't already accounted for in the ledger-based review; small birds at the feeder are not reliably resolvable at contact-sheet thumbnail resolution, an accepted, disclosed limitation matching v9/v10's own precedent.

## Recall

Built from the complete raw ledger (not from product Visits) -- reviewed all 702 track generations across both segments directly, then explicitly re-scanned every generation with `max_confidence >= 0.3` and `detection_count >= 2` that fell outside every identified false/confusor/real-bird location cluster, to surface anything a Visit-only review would miss.

**Denominator: 7 genuine, reviewable wildlife encounter-bout units**, reconstructed from time-clustering (>60s gap = separate bout, matching the Zone's own `quiet_period_seconds`) plus direct visual confirmation of every constituent Visit:

| Unit | Segment | Offset range | Constituent Visit(s) | Represented? |
|---|---|---|---|---|
| S1a | 1 | 1245-1261s | 006 | Yes (single) |
| S1b | 1 | 1324-1385s | 007 + 008 (concurrent, both visually 2-bird frames) | Yes |
| S2a | 2 | 408-438s | 017 | Yes |
| S2b | 2 | 564-578s | 016 | Yes |
| S2c | 2 | 2327-2357s | 019 | Yes |
| S2d | 2 | 3610-3681s | 023 + 022 (concurrent, both visually 2-bird frames) | Yes |
| S2e | 2 | 3802-3985s | 024 + 025 (one continuous presence, **fragmented**; see "Fragmentation") | Yes (fragmented) |

**Recall = 7/7 = 100% of identified genuine bout units represented by at least one admitted Visit.**

This is a narrower, more conservative denominator than earlier cohorts' -- it excludes several real, moderate-confidence (0.4-0.8), multi-detection generations near the same feeder area that the raw ledger shows were genuinely **not** admitted (lost to `blocked_missing_evidence`, some after exhausting fallback, and `blocked_ambiguous_boundary`) at offsets 715807ms, 1645323ms, and 2019213ms in segment 2. These were deliberately **not** counted as confirmed misses in the 7-unit denominator above because I could not independently, visually confirm a bird was present at those specific moments (no corresponding recorder frame close enough in time was reviewed) -- but their confidence/detection-count signature is consistent with real bird activity, not a known confusor location, and they represent **plausible additional recall cost** beyond the conservative 100% figure. Reported honestly rather than folded into either side: **if these three episodes are real, recall over a broader, less conservative denominator would be closer to 7/10 = 70%.** This session's real encounter shape (near-continuous, bursty feeder activity from ~3-4 individual house finches, not cleanly separable sparse discrete visits) makes denominator-unit counting inherently harder than in sparser prior cohorts -- disclosed, not hidden.

No miss traces to the new independence rule or scene-confusor specifically; the plausible additional misses trace to `blocked_missing_evidence` (2 of 3, including one exhausted fallback) and `blocked_ambiguous_boundary` (1 of 3) -- both pre-existing mechanisms, unrelated to this milestone's own corroboration/scene-confusor scope.

## Independent-corroboration field proof

The corroboration axis (`reject_insufficient_detector_corroboration`, encompassing both the original `never_strong_and_minimal_detector_corroboration` reason and the new `corroboration_concentrated_in_single_generation` reason) was reached and evaluated **3 times** this session with a final, non-pending outcome:

1. **Location A recurrence** (foliage/branch-tip, bbox center (0.202,0.691) -- the exact v8/v9/v10 coordinates, offset 321756-331474ms, segment 1): 1 generation, 2 detections, max confidence 0.131, never strong. **Correctly rejected** (`never_strong_and_minimal_detector_corroboration`).
2. **"Ornament" recurrence** (bbox center (0.489,0.399) -- matching v10's own "least-certain" rejection almost exactly, offset 578293-584655ms, segment 1): 1 generation, 2 detections, max confidence 0.372, never strong. **Correctly rejected.**
3. **Visit 020's constituent proposal** (14 generations, offset 2136823-2419382ms, segment 2, decided 22:55:18Z): the single most important field result this session -- see below.

**Visit 020, in full:** the underlying proposal chains 14 track generations -- 2 near the confirmed-real feeder-pole area (weak, max confidence 0.161/0.476), then **12 more, all at bbox (0.8296-0.8561, 0.4962-0.5675) -- the exact coordinates of this session's own dominant, 42-generation/883-detection persistent-confusor chain** (see "Scene-confusor field proof"). All 12 confusor-location generations: never strong, max confidences 0.108-0.255, per-generation detection counts [2,6,4,5,2,14,6,6,10,8,9,6]. Total detection count across all 14 generations: **82**.

Hand-verified against the exact accepted algorithm: old floor (`2*14+1=29`): 82 > 29, count clears. New check: `max_single_generation_detection_count = 14` (the single largest generation); `remainder = 82-14 = 68`; `remaining_floor = 2*13+1 = 27`; **68 > 27 -> `_concentrated_in_single_generation` returns False -> not flagged as concentrated -> the corroboration axis correctly-per-its-own-design ADMITS.**

**This is a direct, real field reproduction of the accepted fix's own explicitly-disclosed residual** ("two independently-substantial generations, neither individually dominant... admitted by design, not omission" -- see the fix's own report, "Remaining risk") -- observed here across 14 generations rather than the disclosed example's 2, at the exact scene coordinates that produced this session's single largest, clearest persistent-confusor chain elsewhere. Visit 020's own primary evidence image (drawn from the confusor-location generations) shows only a small, ambiguous pale/whitish shape in a bush -- **not clearly confirmable as a bird either way**; classified **ambiguous**, not confirmed-false (a real, if unlikely, chance it is a small pale bird cannot be excluded from the evidence alone).

**Net result: zero confirmed-false Visits this session trace to the corroboration axis** (both of its 2 confirmed field rejections were correct; its 1 admission is ambiguous, not confirmed-false) -- a positive result on the narrow question of whether the axis causes false admissions. But this is **not** proof the axis is field-robust against the exact v10 shape: v10's own 4 false admissions were **single-generation** (mathematically inert to the new rule, per the fix's own report), and this session did not reproduce a genuinely-confirmed-false single-generation admission to test against at all -- the sample size for the specific v10 failure shape remains effectively zero this cohort, for reasons explained under "Scene-confusor field proof."

## Scene-confusor field proof

**Answered directly from the database, not inferred.** Queried `scene_confusor_regions` for `stream-dbb95d9c5009` after the session: **14 regions tracked, `occurrence_count` ranging 1-5, `suspected_count = 0` for every single region, with no exception.** This is the definitive answer v10's own report disclosed as an open evidence-trail gap ("the real v10 session's own report never confirms whether scene-confusor state was actually consulted") -- **it was consulted 14 times this session and never once suspected anything.**

Two regions crossed the `min_occurrences_to_suspect=3` threshold and were never suspected, for a directly-verifiable, design-correct reason in both cases:

- **Region at (0.366-0.392, 0.549-0.615)** (the person-in-bushes area): `occurrence_count=5`, `max_confidence_observed=0.847`. Every occurrence individually exceeded `strong_detection_threshold=0.7`, triggering the mechanism's own `independently_strong_detection` escape every time -- correct by design (scene-confusor deliberately never suspects genuinely confident detections, since a real animal could legitimately return to the same spot with high confidence). This region happened to be a person, not wildlife, but the *design reason* it was never suspected is sound regardless.
- **Region at (0.4485-0.4982, 0.7134-0.7925)** (the confirmed-real house-finch feeder-pole area): `occurrence_count=4`, `max_confidence_observed=0.827`, spanning **both segments** (first observed 20:53:39Z in segment 1, last observed 23:10:47Z in segment 2 -- direct proof that scene-confusor region state persists correctly across the mid-session Camera Node outage/restart on the same instance). Same `independently_strong_detection` escape, same correct-by-design non-suspicion -- and in this case the underlying subject genuinely *is* real, repeat wildlife, so this is **positive evidence that scene-confusor correctly avoids suppressing a real, repeatedly-visited feeder location** (see "Stationary-real-bird result").

**The session's single largest, clearest persistent-confusor signature (the 42-generation/883-detection chain at (0.8296-0.8561, 0.4962-0.5675)) is present in `scene_confusor_regions` with `occurrence_count=1` only** -- the *entire* ~20-minute chain touched scene-confusor state exactly once (via Visit 020's own admission, above), because every other occurrence of this signature was intercepted by `blocked_ambiguous_boundary` **before** ever reaching the quality gate where `_touch_scene_confusor_region` is called. Structurally, scene-confusor's cross-occurrence protection can only accumulate state from proposals that already clear both authority (including ambiguous-boundary) and the quality gate -- **a persistent confusor caught upstream by ambiguous-boundary can never build scene-confusor state, and this session's dominant confusor was caught upstream almost every time.**

**Primary question answered: no, the already-live scene-confusor mechanism did not meaningfully contribute this session** -- not because it is broken, but because (a) every region that reached its suspicion threshold held genuinely strong-confidence detections, correctly declining to suspect them by design, and (b) the one clearly weak, never-strong, genuinely-confusor-shaped signature this session almost never reached scene-confusor at all, being intercepted by a third, unrelated, pre-existing mechanism first.

## Mechanism composition

Classifying every identified hard-negative-shaped episode against A (within-proposal independence)/B (scene-confusor)/C (both)/D (neither):

| Episode | A | B | Result |
|---|---|---|---|
| Location A recurrence (segment 1) | Evaluated, correctly rejected | Never reached (rejected upstream of scene-confusor by A itself) | **A** |
| Ornament recurrence (segment 1) | Evaluated, correctly rejected | Never reached | **A** |
| 42-generation mega-chain (0.84,0.53), first wave | Never reached (blocked upstream by ambiguous-boundary) | Never reached (same reason) | **D** |
| Visit 018 (Location A geometry, but a genuinely strong (6x) detection this occurrence) | Never reached (admitted via the strong-detection bypass, before the corroboration axis's count logic matters) | Never reached | **D** |
| Person-cluster region (occurrence_count=5) | N/A (person detections were admitted via strong-detection bypass each time, never via the corroboration axis) | Reached, correctly declined (strong-confidence escape) | **B** (engaged, correctly non-suspecting) |
| Feeder-pole real-bird region (occurrence_count=4) | N/A (admissions here were via strong detection or count-based corroboration, never via the concentration check) | Reached, correctly declined (strong-confidence escape) | **B** (engaged, correctly non-suspecting) |
| Visit 020's 14-generation chain (spans feeder-pole start + the mega-chain's own geometry) | Evaluated, **did not flag** (the disclosed multi-generation-non-dominant boundary) | Reached once (this admission), never suspected (occurrence_count only reached 1) | **A** (evaluated, admitted per its own known boundary) |

**No episode this session was suppressed by both A and B together (0 instances of "C").** The release-relevant finding: **A and B do not yet show evidence of composing in the field** for the reason given above -- B rarely gets a chance to engage against the specific signature A's own boundary lets through, because that signature (this session) was overwhelmingly intercepted by a third, pre-existing mechanism (ambiguous-boundary) before either A or B ever had the opportunity.

## Weak-real-bird preservation

All 10 confirmed-real admitted Visits (006-008, 016-017, 019, 022-025) are genuinely weak-to-moderate signals by MDv5 standards -- max confidences ranging 0.458-0.858, several with `strong_detection_count=0` admitted purely via count-based corroboration (e.g. Visit 025's own constituent generations, several ending `terminal_reason: maximum_duration` after repeated re-chunking of one continuous presence). **Every one of these was correctly admitted; none was rejected by either the corroboration axis or scene-confusor.** No genuine bird was found rejected for `corroboration_concentrated_in_single_generation` anywhere in the merged ledger (that reason string does not appear even once, confirmed by direct grep across both merged segments).

## Stationary-real-bird result

The feeder-pole scene-confusor region (`occurrence_count=4`, spanning both segments, `max_confidence_observed=0.827`) is the direct stationary-real-bird control this session: a real, repeatedly-visited physical location accumulated enough recurrence to cross the suspicion threshold, and was correctly **not** suspected, because its detections were genuinely strong rather than weak/ambiguous. This is field, not merely constructed-reproducer, evidence that a real bird's own Visit at a spatially-stable location survives scene-confusor's cross-occurrence check -- directly answering the item v10's own remaining-dependency list named ("a genuinely stationary real bird's own Visit survives in the field, not only in a constructed reproducer").

## False Visits

Reviewed all 23 admitted Visits directly (primary evidence image fetched and cropped to its own stored bounding box for every one; DB-authoritative `normalized_track_box_json` used throughout, not ledger-derived approximations, after an early cross-check revealed the two can diverge for a "shared_event" proposal's own selected frame).

| Classification | Count | Visits |
|---|---|---|
| Confirmed real wildlife | 10 | 006, 007, 008, 016, 017, 019, 022, 023, 024, 025 |
| Confirmed false/background | 8 | 003, 004, 005, 011, 012, 013, 014 (person); 018 (strong-confidence leaf/branch artifact at Location A) |
| Real non-wildlife animal | 0 | -- |
| Ambiguous | 5 | 009, 010, 015, 020, 021 |

**Primary false-Visit rate (confirmed false / (confirmed false + confirmed real), excluding ambiguous): 8/18 = 44.4%.**

**This does not exit, and numerically worsens, the v8/v9/v10 ~20-36% regime -- but for a root cause entirely disjoint from that regime's own cause.** All 8 confirmed-false Visits were admitted via the **strong-detection bypass** (`strong_detection_count > 0`, which admits unconditionally before the count/concentration logic is ever consulted): 7 are a real utility/landscaping worker in-frame, correctly detected as MDv5's own `animal`-class false positive at genuinely high confidence (up to 0.858, matching the already-accepted, out-of-scope Person-Background-False-Positive residual class from v9's own Visits 139/140); 1 (Visit 018) is a leaf/branch cluster at the classic Location-A geometry that happened to clear the strong-detection threshold 6 times in this one occurrence. **Zero of the 8 confirmed-false Visits were caused by a corroboration-axis or scene-confusor failure** -- neither mechanism is designed to catch a genuinely-strong-confidence detection, by construction, and neither did. Comparing v11's raw 44.4% against v10's 36.4% headline number without this decomposition would be misleading: the two cohorts' false Visits have almost no causal mechanism in common.

## Useful evidence

Strict classification of all 23 admitted Visits' primary evidence:

| Classification | Count |
|---|---|
| Clearly useful | 10 |
| Usable but weak | 0 |
| Background/empty | 1 (018) |
| Wrong subject | 7 (person) |
| Ambiguous | 5 |

**Strict useful-evidence rate: 10/23 = 43.5%** -- below v10's 54.5%, again for the same person-confound reason as the false-Visit rate above, not a mechanism regression. Excluding the 7 wrong-subject (person) Visits as an unrelated confound (matching the false-Visit decomposition), useful evidence among the remaining 16 wildlife-relevant admissions is 10/16 = 62.5%, still below the v5/v7 94-96% band this milestone's own governing brief asked this cohort to test recovery toward -- **useful-evidence rate has not recovered**, on either framing.

## Species / Gate B

Verified for every one of the 8 confirmed-false Visits: **`species_guess` is `None` for all 8**, confirmed directly from the `visits` table. Visit 003's own `automatic_identification` status was explicitly checked live (`"status": "no_result", "message": "Automatic identification completed without a suggestion."`). **Zero confident species assertions on any confirmed-false Visit** -- Gate B's own abstention safety held completely this session, a clean result matching v10's own equally-clean result. BioCLIP was not tuned.

## Fragmentation

Using the accepted human-correctable fragmentation contract's own categories, built from the 7-unit conservative recall denominator (above), reviewed directly (not from raw temporal clustering):

| Unit | Disposition |
|---|---|
| S1a (006) | correctly_represented |
| S1b (007+008, concurrent) | correctly_represented |
| S2a (017) | correctly_represented |
| S2b (016) | correctly_represented |
| S2c (019) | correctly_represented |
| S2d (022+023, concurrent) | correctly_represented |
| S2e (024+025) | **fragmented** |

**Fragmentation rate: 1/7 = 14.3%.** The fragmented pair: Visit 024's own last constituent generation ends at offset 3862903ms with `terminal_reason: tracker_lost`; Visit 025's own first constituent generation begins at the **identical** offset 3862903ms, then continues through 4 more generations largely ended by `terminal_reason: maximum_duration` (a repeated per-generation re-chunking of one still-present subject, not a departure) for another ~2 minutes -- a single continuous real bird presence, split into 2 admitted Visits by a momentary tracker loss/reacquire at the exact boundary. This reopens, rather than closes, the fragmentation concern v10's own 1/5=20% result first reopened -- a second consecutive cohort with a real, non-zero fragmentation rate after the prior 6-7-cohort 0% streak, on a still-small denominator.

## Duplicates

**0/23 = 0.0%.** Verified programmatically: no pair of admitted Visits shares any `constituent_generation_ids` element (checked exhaustively across all C(23,2) pairs, not just the visually-similar concurrent pairs). An 8th-or-9th consecutive convergent 0% cohort.

## Multi-subject

Two `candidate_visit_created_shared_event` pairs occurred (009+010, sharing `event-observation-candidate-009`; 019+020, sharing `event-observation-candidate-018`), plus two visually-confirmed-but-not-system-flagged concurrent pairs (007+008; 022+023 -- each pair's own two Visits are simply two independently-created, non-overlapping-generation proposals close in time, not a `shared_event`).

**Direct visual confirmation, per subject, independently traced:**

- **007+008:** both primary evidence images show **two distinct small birds simultaneously** on the tube feeder. Each Visit has its own independent, non-overlapping constituent generation (confirmed via the duplicate check above) -- genuine concurrent subjects, correctly represented as 2 Visits, though the system did not flag them as a `shared_event` pair (each simply happened to clear authority/quality-gate/admission independently).
- **022+023:** same result -- both images show 2 birds; independent generations; correctly represented, not flagged as `shared_event`.
- **009+010 (flagged `shared_event`):** the wide-frame evidence images for both **do** show a hummingbird-shaped blur near the red feeder, but neither Visit's own precise, stored bounding box resolves a clear subject on tight crop -- genuinely **ambiguous**, not confirmed. Per this section's own governing caution ("Require direct visual confirmation... No cross-subject corroboration"), this pair is **not** counted as a confirmed multi-subject instance, despite the system's own `shared_event` flag.
- **019+020 (flagged `shared_event`):** 019 is a confirmed-real house finch at the feeder; 020 is the ambiguous 14-generation admission discussed at length above (whose own evidence is drawn from a different location than 019's). Each has fully independent constituent generations (confirmed, zero overlap) -- the Multi-Subject Event-reuse mechanism correctly avoided merging or cross-contaminating two proposals decided 16 seconds apart, which is itself a real, positive finding about the mechanism's discipline, independent of whether 020 itself is a real bird.

**Net: 2 pairs (007+008, 022+023) are genuine, directly-visually-confirmed simultaneous-subject sightings** -- solid, if modest, multi-subject evidence (short of "3+" but a real "2 simultaneous birds" result, achieved twice). No cross-subject corroboration was observed or required for admission in any pair; each subject's own admission traces to its own independent evidence.

## blocked_missing_evidence

Using distinct-proposal semantics (matching the v6-v10 comparison basis): **29 blocked_missing_evidence outcomes / 312 distinct proposals = 9.29%.**

| Cohort | v6 | v7 | v8 | v9 | v10 | **v11** |
|---|---|---|---|---|---|---|
| Rate | 18.3% | 9.4% | 9.9% | 8.9% | 6.7% | **9.29%** |

Squarely within the v7-v10 convergent band -- a healthy, unremarkable, further-convergent data point, slightly above v10 but well inside the historical range. Not itself a Gate A regression signal.

## Fallback

Combined across both segments: **10 fallback attempts, 7 admitted (70%), 3 exhausted.** Cross-verified two independent ways (live `observation-status.advanced.fallback_*` counters at each segment's own end, and counting `candidate_visit_created:fallback_position_N` reason strings in the merged ledger) -- both methods agree exactly (segment 1: 3 admitted matching 3 `fallback_position_1` reasons; segment 2: 4 admitted matching `fallback_position_1/2/3` reasons summing to 4). The deepest chain reached fallback position 5 (still exhausted -- one of the missing-evidence losses near the feeder-pole area, offset 614235-624064ms, segment 2).

## Rate limiting

**Never activated.** No `blocked_session_limit` or `blocked_hourly_limit` outcome appears anywhere in either segment's merged ledger, confirmed by direct search. 23 total admissions across ~102 combined minutes (peak: 11 in segment 2's 67.6 minutes) stayed well under any per-Stream session/hourly ceiling. No rejected hard negative misleadingly consumed candidate capacity (all 8 confirmed-false Visits legitimately used their own capacity slot, same as any admission would -- rate-limit accounting is not selectively bypassed for false admissions, which is itself correct, expected behavior, not a defect).

## Persistence

No SQLite lock-contention retries, no duplicate-persistence events, and no `AnalysisStreamRetryPolicy` activity beyond the one real, disclosed Camera Node outage (which correctly exhausted its 6-attempt retry ceiling and stopped cleanly rather than hanging or crashing). No admitted-but-lost candidate found in either segment.

## Stop-finalization

Exercised on both segments' own stop. Segment 1's own stop was involuntary (the hardware fault itself, not a clean `observation/stop` call) -- its own `blocked_continuation_pending` backlog (9 distinct proposals) simply never resolved further, an honest, disclosed characteristic of an abrupt stop, not a defect. Segment 2's own deliberate stop correctly set `stop_finalization_pending: true`, then resolved it within ~37 seconds, rescuing one additional candidate (`candidates_created` 10 -> 11, Visit 025) -- the same behavior v5/v10 already proved, reproduced a third time.

## Monitoring / recorder coverage

- **Intended combined duration:** ~102 minutes (75-100 target, plus the disclosed hardware-outage interruption).
- **Actual monitored duration:** segment 1 raw-detection span 0-1,937,040ms of a 2,056,000ms nominal window (94.2% -- the shortfall matches the ~2-minute retry-exhaustion window before the Node was declared unavailable, not a silent gap); segment 2 span 0-4,022,076ms of a 4,058,000ms nominal window (99.1%).
- **Combined monitoring coverage: 97.5%** -- in line with the historical 97.95-99.99% band (v9, v10), the segment-1 shortfall fully and honestly explained by the disclosed hardware fault.
- **Acceptance-recorder coverage:** 4,373 frames across both segments, correctly scoped per-session (see "Independent denominator"); the one disclosed defect (garbled directory name) did not cost any frames.

## Product behavior

- **Review Queue:** correctly lists all 23 real session Visits plus the pre-existing seeded demo item, no duplicates, no omissions.
- **Bird Log:** correctly shows no entries for this session's activity (none of the 23 Visits have been reviewed/corrected yet -- Bird Log is Reviewed-truth-gated by design, and this session deliberately left every Visit in `needs_review`, matching doctrine). Not a defect.
- **Camera health surface (`/api/camera-health`):** showed `"state": "stopped"` / `desired_mode: off` throughout the live session, which initially looked concerning but is confirmed **by design**: this reflects the separate, persistent "armed monitoring policy" toggle, which the least-privilege Field Acceptance Operator credential deliberately never touches (its allowed-route table is exactly `{observation/start, observation/stop}`) -- the actual live engine state (`/observation/status` → `observing: true`, growing counters) was correct and authoritative throughout. Documented here for the next cohort's own benefit; not a new defect.
- No other product-surface correctness defects found.

## Cross-cohort comparison

| Metric | v7 | v8 | v9 | v10 | **v11** |
|---|---|---|---|---|---|
| Confirmed false-Visit rate | ~4-5% | 22.2% | 20.0% | 36.4% | **44.4%** (root cause disjoint from v8-v10's own; see "False Visits") |
| Useful-evidence rate | 94-96% | 77.8% | 76.0% | 54.5% | **43.5%** (62.5% excluding the person confound) |
| Recall | -- | 100%/3/3 | 83.3% | 80% (4/5) | **100%** (7/7 conservative) / **70%** (7/10 less-conservative) |
| Fragmentation | 0% | 0% | 0% | 20% (1/5) | **14.3%** (1/7) |
| Duplicates | 0% | 0% | 0% | 0% | **0%** |
| `blocked_missing_evidence` | 9.4% | 9.9% | 8.9% | 6.7% | **9.29%** |
| Monitoring coverage | -- | 62.8% (self-inflicted) | 97.95% | 99.99% | **97.5%** |
| Hard-negative rejections | -- | -- | -- | 3/3 classic shapes | **2/2 evaluated, correct; 1 admitted per own disclosed boundary** |
| Scene-confusor participation | n/a (pre-existing, unconditional since schema 34, not separately field-measured before) | n/a | n/a | not measured (disclosed gap) | **measured directly: 14 regions touched, 0 ever suspected** |
| Weak-real-bird outcomes | -- | -- | preserved | preserved (count-based) | **preserved (10/10)** |

**Primary question: did v11 materially exit the v8/v9/v10 false-Visit regime? No, numerically** -- but the decomposition above shows this cohort's false Visits share essentially no causal mechanism with v8-v10's own (person/strong-detection vs. weak/never-strong persistent-confusor), so this cohort does not, by itself, refute the fix's own field-proof criterion either. **The fix's own specific failure shape (v10's single-generation, never-strong, repeatedly-admitted persistent confusor) was not reproduced as a confirmed-false admission this session** -- it appeared (the 42-generation mega-chain) but was intercepted by a different, upstream mechanism almost every time, denying this cohort the direct re-test the milestone was designed to obtain.

## Budget maturity

| Metric | Candidate value | v11 evidence | Status |
|---|---|---|---|
| Minimum Visit recall | none accepted | 70-100% (methodology-dependent) | MORE EVIDENCE REQUIRED (methodology still not held constant cohort-to-cohort) |
| Maximum false-Visit rate | none accepted (bimodal) | 44.4% raw, but causally disjoint from prior cohorts' own driver | MORE EVIDENCE REQUIRED -- if anything, less converged than before; the causal decomposition itself needs to become part of the accepted methodology |
| Maximum fragmentation rate | was READY, reopened by v10 | 14.3% (1/7), second consecutive non-zero cohort | MORE EVIDENCE REQUIRED, unchanged from v10's own reopening |
| Maximum duplicate rate | READY | 0% (8th-9th convergent cohort) | **Still READY**, reaffirmed |
| Minimum useful-evidence rate | withdrawn | 43.5% raw / 62.5% ex-confound, both below any prior proposed figure | MORE EVIDENCE REQUIRED, unchanged |
| Maximum true capture-visible latency | none accepted | not re-derived this pass (see "True latency") | MORE EVIDENCE REQUIRED, unchanged |
| Minimum monitoring coverage | READY (~97-99%) | 97.5%, in-band | **Still READY**, reaffirmed |

## Gate A closure assessment

**Not ready for formal closure review.** Three concrete reasons: (1) the false-Visit and useful-evidence rates remain outside any defensible accepted band, and this cohort's own root-cause decomposition, while informative, is itself new methodology that has not yet been cross-validated against a second cohort; (2) fragmentation reopened a second time, still unresolved; (3) the milestone's own central question -- does the accepted fix materially improve the field false-Visit rate against its own targeted failure shape -- was not directly re-tested, because that shape barely recurred as a *confirmed-false admission* this session (it mostly recurred as an ambiguous admission and as ambiguous-boundary-blocked activity instead). A next cohort is still needed, and should specifically seek a session where the persistent-confusor shape clears ambiguous-boundary and reaches the quality gate as a genuinely single-generation, never-strong, repeatedly-admitted case -- the one direct test this milestone was designed for and did not obtain.

## Defects

1. **Acceptance-recorder directory-path encoding defect (new, disclosed, non-invalidating).** Setting `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` to an absolute Windows path (`C:\Users\...\acceptance-recordings`) via `deploy_windows_dev.py`'s own documented `_DEV_`-prefixed env-var translation produces a garbled, non-human-readable directory name on disk (a single directory-name component containing mis-encoded backslash/colon characters) rather than using the path as a real absolute location. The recorder itself functions correctly once that garbled directory exists (4,373 frames captured across both segments, zero data loss) -- this is a discoverability/hygiene defect, not a data-loss defect. Root cause not further diagnosed this pass (bounded archaeology; likely a `Path`/`os.path.join`-style relative-join treating the Windows-absolute-path string as a literal single path segment, the same class of bug this milestone's own operator hit independently with `deploy_windows_dev.py --dev-root` itself -- see below). Recommend a bounded DEV fix: validate/normalize this env var the same way `--dev-root` itself should be (see item 2).
2. **`--dev-root`/absolute-Windows-path argument handling is fragile across this tooling family (operationally significant, not a new code defect this milestone -- a genuine operator trap, self-inflicted and self-corrected during this session).** Passing a literal `%LOCALAPPDATA%\...` string to `deploy_windows_dev.py --dev-root` (expecting shell-style expansion) silently joins it as a relative path under the *repository's own working tree*, materializing a real, multi-GB build artifact at a garbage path inside the git working directory rather than failing loudly. Caught and cleaned up immediately this session (verified `git status` clean afterward); no lasting effect. The correct invocation is a real, WSL-mounted POSIX absolute path (e.g. `/mnt/c/Users/...`), which every other tool in this family (`field_acceptance_instance_lifecycle.py`) already expects and handles correctly. Recommend: `deploy_windows_dev.py` should reject (not silently accept) a `--dev-root` value that resolves to a path inside the repository's own working tree, and/or explicitly document the required POSIX-mounted-path convention alongside the Windows-style default shown in `--help`.
3. **Real Camera Node hardware fault, mid-session (disclosed at length under "Camera Node health"; see also the running-notes timeline).** A genuine CSI ribbon-cable connection fault caused the physical camera sensor to stop responding at the kernel/I2C level (`Failed to read chip id: -5`) following the very first remote power-cycle attempt; required a second, user-performed physical cable reseat to resolve. Notably, **the Node's own `/node/v1/health` self-test reported `"passed"`/`camera_available: true` twice while the camera was still not actually physically detected** (confirmed independently via `vcgencmd get_camera` and the real per-camera `/node/v1/cameras` enumeration, which correctly showed `picamera2-no-camera`/`unavailable` both times) -- the Host's own field-acceptance compatibility preflight (checking the real per-camera enumeration, not the aggregate self-test flag) correctly caught this both times and safely refused to start Observation. **Recommend as a bounded future DEV item:** tighten `/node/v1/health`'s own `self_test.camera_available` semantics so it does not report success while the specifically-configured camera remains undetected -- a real, if minor, diagnostic-accuracy gap; not release-blocking, since the actual safety-relevant gate (compatibility preflight before Observation start) already worked correctly both times.
4. **`blocked_continuation_pending` backlog at segment end (observed, not yet root-caused).** Segment 2 ended with 71 distinct proposals still recorded at `blocked_continuation_pending` as their latest logged outcome, despite a clean, confirmed stop-finalization. Plausible, not confirmed: these are largely sub-components of the session's own dominant, extremely long ambiguous-boundary chain, superseded by a later, more complete arbitration decision rather than genuinely lost. Not asserted as a defect this pass; flagged for a future cohort to specifically check whether any of these 71 represent real, unresolved encounters rather than superseded intermediate state.

None of the four items above invalidates this session's own measurements; items 1 and 2 are tooling-only and fully worked around; item 3 is isolated, real-hardware, and fully disclosed with root cause; item 4 is an open observation, not a confirmed defect.

## Decision

**B.**

Real, representative, real-hardware daylight field data was obtained (101.8 combined minutes), with unusually complete raw-ledger preservation (100% lossless recovery, verified against live counters) and a directly-queried, first-of-its-kind definitive answer to the prior cohort's own disclosed scene-confusor evidence gap. The milestone's central hypothesis was not confirmed or refuted cleanly: the corroboration axis caused zero confirmed-false admissions (positive), but also was directly, mechanistically observed admitting one genuinely ambiguous case via its own disclosed boundary at the session's own dominant persistent-confusor location (concerning), and scene-confusor demonstrably never got the chance to compose with it in the field this session, for a well-evidenced structural reason. The raw false-Visit and useful-evidence rates did not improve and are not directly comparable to prior cohorts' own numbers without the causal decomposition this report provides. Gate A is not self-closed; no next milestone is proposed or started.
