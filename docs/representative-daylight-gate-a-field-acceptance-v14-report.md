# Representative Daylight Gate A Field Acceptance v14 — Corrected Evidence-Path Re-Proof & Budget Convergence

RELEASE-CRITICAL Lane R / Gate A real-field milestone. Follows accepted
Representative Daylight Gate A Field Acceptance v13, Camera Node
Evidence-Capture Profile Validity & Failure Observability Correctness v1,
Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness v1,
All-Alternate Subject Evidence Recall Correctness v1, and Ambiguous-Boundary
Real-Subject Recall Correctness v1. Evaluates the corrected accepted release
configuration in a representative daylight cohort. This is an EVIDENCE
milestone; no new product-code hypothesis was pursued.

## Starting state

Verified directly (git, HTTP, filesystem) before any deployment:

- Branch `main`, HEAD `1904421` (`190442112556853ddd1295aab23f1844dc3f71f5`) — matches expected exactly.
- `git status`: only the 7 explicitly-preserved untracked files (confirmed present, non-zero size, untouched — see "Worktree safety").
- Schema v58 (confirmed live via `GET /api/product/health` after deploy: `database_schema_version: 58`).
- Latest accepted milestone: Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness v1 (classification A, 2026-09-05).
- `docs/release-execution-state.md` §3 confirms, verbatim: evidence-capture profile validity/failure observability **CLOSED / READY FOR REPRESENTATIVE FIELD RE-PROOF**; proposal_outcomes reconciliation **CLOSED / READY FOR REPRESENTATIVE FIELD RE-PROOF**; recall and evidence survival **REOPENED / WAITING FOR FIELD RE-PROOF**; current authorization **NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**.
- §1's top "Accepted HEAD" bullet remains a pre-existing, already-disclosed staleness (still reads `e57c911`, flagged in the v13 reconciliation commit as a documentation-only lag, not a state-tracking authority — §3/§6.R are this file's own authoritative "what's current" record per established project convention). Not corrected here — out of this milestone's own bounded scope, same discipline v13 itself followed.
- Not pushed (`main` ahead of `origin/main` by 338 commits at session start).

## Conditions

- Genuine representative daylight: session start 2026-09-05 13:51:55 EDT (Saturday), clear sky, full sun — confirmed both by system clock cross-check (WSL/Windows-host times agreed) and by direct visual inspection of an early independent-recorder frame (bright daylight feeder/yard scene, consistent with every prior accepted cohort's view).
- Reference Camera Node reachable: LAN ping + SSH + HTTP health all confirmed (`node-76ec8e53ae586dd0`, `boot_id 4239527b-5622-425c-bed1-ae3074e191dd`, `self_test: passed`, `camera_available: true`, `pairing_required: true` i.e. no stale pairing owner).
- Physical camera available: real `picamera2` `ov64a40` sensor detected (`rpicam-hello --list-cameras`), 47.2°C, `throttled=0x0` (no thermal issue), 107GB free on the Pi.
- Accepted Node build installed: manifest `git_commit 4c1be355386c4a38c130f2f9d0204a5447a5166b` confirmed an ancestor of accepted HEAD with **zero** `src/mockingbird_node/` commits landed since — current, accepted build.
- Native-Windows Host available: `powershell.exe` interop smoke-tested working; Windows build 10.0.19045.
- GPU/detector available: RTX 4060 Ti, 8188MiB total, CUDA driver 610.62, confirmed live in Observation's own `advanced` payload (`cuda_available: true`, `CUDAExecutionProvider` selected).
- Windows storage headroom: C: drive 29.9GB free at preflight time (`getting_low` tier, `sufficient: true` against a 6.0GB recorder+reserve budget).
- Correct Windows filesystem identity measured: storage preflight resolved to the real `C:\Users\zachk\AppData\Local` root (the corrected, WSL-path-based invocation convention — not the historical v12 wrong-filesystem defect).
- Lifecycle tooling ready: `field_acceptance_instance_lifecycle.py` fully exercised (`preflight`, `init`); one prior instance (`MockingBirdFieldAcceptanceV13`) freshly re-verified `SAFE_TO_RECLAIM` but its destructive `cleanup --destroy` was blocked by the session's own permission classifier — left alone (not required; storage was already sufficient).
- Independent recorder ready: confirmed writing real JPEG frames within 8 seconds of Observation start (see "Independent recorder").
- No conflicting Observation: fresh disposable instance, zero pre-existing Streams beyond the seeded demo (ignored per established precedent).
- No unsafe pairing owner: Node's own `pairing_required: true` at session start (nothing paired) — the pairing-code refresh needed only a routine service restart, not a destructive pairing-state removal.
- No active writer: confirmed no other MockingBird process (WSL or Windows) running against this repo/instance at session start.

## Build / compatibility / RTT

- Deploy: `scripts/deploy_windows_dev.py --dev-root /mnt/c/Users/zachk/AppData/Local/MockingBirdFieldAcceptanceV14` (no skip flags — full GPU+BioCLIP closure), with `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`/`_INTERVAL_MS=1000`/`_MAX_FRAMES=7200`/`_MAX_BYTES=4500000000` set from the first attempt (matching v13's own established recorder cadence exactly, for direct cross-cohort comparability). Deploy log: `DEPLOYED 1904421`.
- `field_acceptance_instance_lifecycle.py init`: `created_by_commit: 190442112556853ddd1295aab23f1844dc3f71f5`, `created_by_build_id: 0aab7627e3a0bb2a`.
- `GET /api/product/instance`: `git_commit: 190442112556853ddd1295aab23f1844dc3f71f5` — **exact accepted-HEAD match**, the authoritative identity check per standing project convention. `GET /api/product/health`: `database_schema_version: 58`, `ready: true`.
- `check_camera_node_compatibility.py --profile ordinary_monitoring`: `state: compatible`, `camera_available: true`.
- `check_camera_node_compatibility.py --profile field_acceptance`: `state: compatible`; **real RTT-bounded calibration reached `calibrated`**: 5/5 valid samples, `offset_ms -101.931 [-106.797, -97.065]`, `uncertainty_ms 4.866`, `rtt_ms 13.569`, `node_processing_ms 3.837`, `clock_jump_detected: false`.
- Real production stack confirmed live in `observation/status`'s own advanced payload at Observation start: `provider_key: frame-driven-onnx-cuda`, `detector_provider_key: onnx-cuda`, `cuda_available: true`, `selected_execution_providers: [CUDAExecutionProvider, CPUExecutionProvider]`, model `md-v5a` / `MDv5a.0.1-onnx-opset18`, `score_threshold: 0.1`, `nms_iou_threshold: 0.45` — byte-identical to accepted production configuration.
- **New evidence-capture diagnostics confirmed present and live** (Camera Node Evidence-Capture Profile Validity & Failure Observability Correctness v1's own additive fields): `evidence_burst_requests`, `evidence_burst_captures`, `evidence_burst_failures`, `evidence_burst_stale`, `evidence_profile_reconciliation_count` all reachable in `observation/status`, all `0` at session start (correct baseline).

## Field lifecycle

- `preflight` → `deploy` → `init` → pair/configure → Observation, executed via the accepted tooling (`field_acceptance_instance_lifecycle.py`, `deploy_windows_dev.py`, `field_acceptance_client.py`-equivalent driver, `manage_field_acceptance_credential.py`, `check_camera_node_compatibility.py`) — no ad hoc bypass. (Note: the tool itself requires `deploy` before `init` — it validates the manifest against an already-existing `deployments.json` — so the literal call order is `preflight` → `deploy` → `init`, not `init` → `deploy`; this is the tool's own enforced order, not a deviation from accepted practice.)
- Node pairing-code refresh (non-destructive, routine): the Node was already unpaired (`pairing_required: true`) at session start, so no existing pairing needed to be removed — a plain `sudo systemctl restart mockingbird-camera-node.service` was sufficient to obtain a fresh, unexpired one-time code (the previously-shown code had already expired ~15 hours earlier). `boot_id` (`4239527b-5622-425c-bed1-ae3074e191dd`) unchanged across the restart. Fresh code consumed well within its 10-minute TTL.
- Administrator bootstrapped via `POST /api/setup/administrator` (`field-acceptance-v14-admin`, locally-generated 24-character password, never user-supplied, discarded with the instance). Field Acceptance Operator credential minted via `POST /api/admin/field-acceptance-credentials` (`field-acceptance-240a794f37504afb`, 6h TTL) and used for `observation/start`/`stop`/status/counterfactual reads per the credential's own least-privilege allowlist.
- Pairing: `POST /api/camera-nodes/pair` → `POST /api/camera-setup/complete` (real `picamera2-camera-0`, one "Yard" Zone covering the full frame, every monitoring-policy field left at its inherited default — activity sensitivity `low`, `minimum_sustained_activity_seconds: 8`, `quiet_period_seconds: 60`, `maximum_visit_duration_seconds: 480`, `maximum_evidence_frames: 2` — nothing tuned, matching v13's own precedent exactly). Resulting Stream: `stream-34ebfc662499` ("Reference Pi Camera V14"), Source: `source-34ebfc662499`.
- Node credential read once, directly, from the fresh instance's own local SQLite `source_provider_configurations` table (`config_json -> node_credential`) for the `check_camera_node_compatibility.py` diagnostic run only — never persisted beyond a session-local, restrictive-permission scratch file; discarded with the instance.
- Storage reclamation: `MockingBirdFieldAcceptanceV13` freshly re-verified `SAFE_TO_RECLAIM` (9.42GB) but its `cleanup --destroy` call was blocked by this session's own permission classifier (a real, working safety gate on a destructive action) — left archived and untouched; not required, since preflight already confirmed sufficient headroom (29.9GB free) without it.
- **One real field-tooling defect found and fixed during setup** (isolated, non-production, does not touch admission/perception/evidence code — see "Reproduced defects"): a locally-written orchestration helper (`run_on_windows.py`/`start_detached.py`, session-scratch only, never committed) initially (a) embedded a stray CRLF from PowerShell's own line-ending convention into an extracted bearer token, producing `ValueError: Invalid header value` on first use, and (b) passed a `--output-dir` argument through to a Windows-native process without translating it from a WSL path to its Windows/UNC form. Both were caught immediately (before any real session time was spent — the misconfigured ledger-collect process was stopped within ~90 seconds, before its first 300-second checkpoint would have fired) and fixed by (a) explicitly stripping `\r`/`\n` from PowerShell-sourced values before use, and (b) pre-translating every path-like argument via the project's own established `wslpath -w` convention. Neither defect touched any file this project tracks in git.

## Session duration

- Observation started `2026-09-05T17:51:55.058176Z` (13:51:55 EDT), stopped `2026-09-05T19:34:35.661887Z` (15:34:35 EDT) — **102.68 minutes** (`session_last_offset_ms: 6,132,233`), within the 90-105 minute target band.
- `stopped_reason: "user_stopped"`, a deliberate operator decision at the target duration — not cut short by any fault, and not extended to manufacture activity (substantial real activity was already present throughout — see Recall).
- `stop_finalization_pending: true` observed immediately after the stop call, resolved to `state: "stopped"`, `observing: false` within ~4 seconds — clean stop-finalization, no residue.
- Real production stack confirmed live throughout: `md-v5a` / `MDv5a.0.1-onnx-opset18`, `score_threshold: 0.1`, `nms_iou_threshold: 0.45`, `onnx-cuda`/CUDA — byte-identical to doctrine, untouched throughout (confirmed at start and again in the final pre-stop status check).

## Independent recorder

- Confirmed writing real JPEG frames within 8 seconds of Observation start (10 frames on first check; 77-78 frames by T+88s) — satisfies the "verify actual frames are being written immediately" requirement before trusting any denominator work.
- Cadence/bounds matched to v13 exactly: `sample_interval_ms=1000`, `max_frames=7200`, `max_total_bytes=4500000000`.
- Early frame visually confirmed: bright, genuine daylight, clear feeder/hummingbird-feeder scene, consistent framing with prior accepted cohorts.
- **Final: 5,182 frames, 4.096GB, span 0ms-6,132,233ms** (exactly matching the ledger's own `session_last_offset_ms` — the recorder covered the entire session with no truncation against either the `max_frames` (7,200) or `max_total_bytes` (4.5GB) bounds).
- Gap statistics: median 1.11s, p95 1.66s, **max gap 5.80s, exactly 3 gaps >5s (5.30s, 5.48s, 5.80s), zero gaps >10s**. Coverage (1 − Σ(gaps>5s)/span): **99.73%**. Slightly more jitter than v13's own tightest-ever 3.68s max, but comfortably within the healthy band every prior cohort has shown (97.5%-99.99%).

## Ledger completeness

**All three ledger artifacts reconcile `COMPLETE` — 100%, zero gaps** (`field_acceptance_ledger_snapshot.py reconcile` against 22 periodic checkpoints at `--interval-seconds 300` plus one final corrective fetch, `start_offset_ms=0, end_offset_ms=8000000`, taken live seconds before the stop call):

| artifact | recovered | final `recorded_count` | completeness | status | distinct entities |
|---|---|---|---|---|---|
| `raw_detections` | 22,260 | 22,260 | **100.0%** | `COMPLETE`, zero gaps | n/a |
| `track_generations` | 218 | 218 | **100.0%** | `COMPLETE`, zero gaps | n/a |
| `proposal_outcomes` | 191 | 191 | **100.0%** | `COMPLETE`, zero gaps | 90 distinct `proposal_id`s |

`overall_status: COMPLETE`. This is not only better than v13 (which had trivial sub-second tail-window `PARTIAL` flags on the first two artifacts) but the cleanest ledger-completeness result of any cohort to date — genuinely zero gaps anywhere, not merely a disclosed-and-accepted trivial residual.

## Proposal-outcome event completeness

**Primary v14 objective — met in full.** 191 total proposal decision-events written and recovered (100%), spanning 90 distinct `proposal_id`s. Repeated-decision proposals: of 90 distinct proposals, a subset legitimately cycled through multiple decision events (the `blocked_continuation_pending` retry pattern the fix's own contract describes) — decision-event outcomes break down as: `blocked_continuation_pending` 110, `blocked_ambiguous_boundary` 55, `blocked_missing_evidence` 8, `reject_insufficient_detector_corroboration` 4, `created` 14 (= 191 total). Maximum decisions observed for one proposal_id: at least 4 (visit-006's own eventually-admitted proposal cycled through continuation-pending states before its dead-anchor promotion; several suppressed proposals show 2-4 decision events each in the raw ledger). Retained/evicted state at end of session: `raw_detections` retained 12,000/evicted 10,260 (of 22,260 recorded); `track_generations` retained 125/evicted 93 (of 218); `proposal_outcomes` retained 103/evicted 88 (of 191) — all evictions are retention-boundary housekeeping on data the periodic-snapshot pipeline had already durably captured before eviction, not data loss. **Reconciliation status: `proposal_outcomes = COMPLETE`** — no partial result, no immaterial-gap caveat needed. Exact interval gaps: none (`gaps_ms: []`).

## Evidence-capture profile recovery

**Primary v14 objective — met in full, and the v13 pathology did not recur.** Across the full session: `evidence_burst_requests: 204`, `evidence_burst_captures: 204`, `evidence_burst_failures: 0`, `evidence_burst_stale: 0`, `evidence_profile_reconciliation_count: 1`. The one reconciliation matches the root-caused mechanism exactly (the Node's async warm-proof promotion retiring the cold `reconfiguration_required` evidence profile in favor of `warm_concurrent` a few seconds after pairing) — after that single self-heal, all 203 subsequent bursts captured directly with no further reconciliation needed. `evidence_harvest_misses: 0` throughout. **Every evidence burst this session succeeded; none were classified `node_capture_profile_unavailable` and left unhealed.** No systematic evidence-burst failure surfaced at any point (verified continuously via the 10-minute health-check monitor throughout the live session, not only at the end).

## Evidence survival

- Proposals requesting evidence: all 191 decision events implicitly pass through the evidence-capture path (204 burst requests against 191 proposal decisions reflects proposals requesting more than one burst across retries).
- Proposals obtaining persistable evidence: effectively all — `evidence_burst_failures: 0`.
- `blocked_missing_evidence`: **8 of 191 decision events (4.2%)** — a dramatic reversal from v13's defect-driven 88.5%, and now squarely inside the historical pre-defect v6-v12 band (4.6%-18.3%), in fact at its low end. Every one of these 8 carries the specific reason `no_persistable_evidence_bytes` (not a burst failure — see "Recall-miss causal breakdown" for individual disposition).
- `no_persistable_evidence_bytes` where distinguishable: all 8 `blocked_missing_evidence` records carry this exact reason.
- Fallback attempts: `fallback_attempted_count: 3`, `fallback_admitted_count: 2`, `fallback_exhausted_count: 1` — real, natural exercise of the fallback-chain/dead-anchor mechanism this session (see "Dead-anchor field re-proof" and "classifier_same_frame field re-proof").
- `EvidenceCandidate` creation / actual media files persisted: **34 real JPEG files, 59MB, under `userdata/data/media/imports/`**, timestamped throughout the live session window (14:10-14:52 EDT, consistent with session activity, not stale/seeded data). One file (`media-candidate-005.jpg`) visually spot-checked: real 3840×2160 evidence-burst capture of the feeder scene, confirming the `picamera2-evidence-3840x2160` profile was actually exercised end to end.
- Direct comparison with v13's pathological regime: v13 had **zero** `EvidenceCandidate`s of any role, **zero** files ever written, **100%** of proposals dying at the evidence-existence gate before any precision mechanism could engage. This session shows the opposite: real evidence flowing normally, precision mechanisms (`blocked_ambiguous_boundary`, `reject_insufficient_detector_corroboration`) engaging exactly as designed on genuinely marginal/ambiguous cases, not on every proposal indiscriminately.

## Denominator methodology

Per the governing instructions, denominator construction began from the independent recorder, not from MockingBird's own Visits. Method: (1) full-session contact sheets generated from all 5,182 independent-recorder frames (every 15th frame, ~17s cadence, 12 sheets covering the complete 0-6,132,233ms span); (2) every one of the 14 admitted-Visit windows, all 11 "silent" (no-nearby-admission) `blocked_ambiguous_boundary` windows, all 8 `blocked_missing_evidence` windows, and all 4 `reject_insufficient_detector_corroboration` windows individually cross-checked against 2-6 full-resolution frames spanning their start/end offsets (not single-frame spot checks — 87 distinct frames viewed across these 27 windows alone); (3) a systematic scan of all 12 contact sheets for activity not already covered above; (4) a further 6 personal spot-checks of additional automated-clustering "weak_confidence" unadmitted clusters the encounter-accounting tool identified but that fell outside the ledger-derived window set (all 6 confirmed no visible animal). This directly implements "primary denominator construction must begin from independent recorder review" and "do not discover the denominator from MockingBird Visits first."

**Segmentation rule**: confirmed real-animal-present timestamps were merged into a single encounter-period whenever consecutive confirmed-present samples were separated by less than ~60 seconds (matching the product's own `quiet_period_seconds: 60` config as a natural, non-arbitrary break threshold), and split into separate encounter-periods across any larger gap. This is necessarily approximate — frames were sampled discretely (roughly every 1.1-35s depending on the check), not exhaustively at 100% per-frame coverage — and is disclosed as such rather than presented as exact-to-the-second.

One extended, busy bout (4921-5294s, encompassing visit-014, visit-015, and ~310 continuous seconds of confirmed activity between them including simultaneous 2-bird moments) resists clean segmentation under this rule (internal gaps of ~22-31s, all individually under the 60s threshold) — per product doctrine's own explicit caution ("do not assume... every occurrence can be accurately counted"), this is conservatively treated as **one** encounter-period for denominator purposes, while flagged separately that it plausibly contains multiple real distinct sub-encounters beyond the two admitted slivers.

## Conservative denominator

**17 distinct real encounter-periods** confirmed by direct visual inspection (offsets in seconds, `[V]` = has ≥1 admitted Visit, `[MISS]` = zero admission):

| # | offset range | admitted Visit(s) | disposition |
|---|---|---|---|
| 1 | 769.1-1059.5 (~290s) | visit-003 (857.4-866.2, 8.9s) | **[V]** — partial coverage: an 8.9s Visit for a ~290s real bout |
| 2 | 1125.7-1284.6 (~159s) | visit-004 (1183.3-1284.6) | **[V]** — good coverage |
| 3 | 1418.9-1424.0 | visit-005 | **[V]** — full coverage |
| 4 | 1467.0-1512.3 | none | **[MISS]** |
| 5 | 1718.5-2034.5 (~316s) | visit-006 (1975.9-2034.5, dead-anchor) | **[V]** — partial coverage: 58.6s Visit for a ~316s real bout |
| 6 | 2827.6 (instant flyby) | visit-007 | **[V]** — real bird, but visible only in the window's first frame |
| 7 | 3378.9-3453.1 | none | **[MISS]** |
| 8 | 3483.5-3567.9 (~85s) | visit-008 (3483.5-3545.1) | **[V]** — good coverage |
| — | 4079.4-4089.5 | visit-009 | **excluded — confirmed FALSE, no animal visible in any of 10 frames spanning the full window** (see "False Visits") |
| 9 | 4443.3-4456.1 | visit-010 + visit-011 (confirmed simultaneous pair) | **[V]** — full coverage, correct multi-subject handling |
| 10 | 4496.7-4539.1 | none | **[MISS]** |
| 11 | 4686.9-4688.6 | visit-012 (4676.8-4688.6) | **[V]** — real bird visible only in the window's final ~1.7s |
| 12 | 4759.4-4765.0 | visit-013 | **[V]** — full coverage |
| 13 | 4788.2-4842.8 | none | **[MISS]** |
| 14 | 4921.0-5294.1 (~373s complex) | visit-014 (4921.0-4927.1) + visit-015 (5288.1-5294.1) | **[V] partial** — two 6s slivers out of a ~373s bout; ~310 continuous seconds in between (including simultaneous 2-bird moments) received zero admission |
| 15 | 5325.7-5334.8 | none | **[MISS]** |
| 16 | 5415.3-5445.9 | visit-016 | **[V]** — full coverage (brief internal absences, same bird) |
| 17 | 5988.2-5996.7 | none | **[MISS]** |

**11 of 17 encounter-periods have at least one admitted Visit; 6 have zero.**

## Broader denominator

Conservative (17) plus **1 additional low-confidence candidate**: an indistinct pale/vertical shape near background shrubbery at ~5992.7s, noted by the visual reviewer as "too small and ambiguous to confirm" — could be a distant animal or could be a yard object/shadow. **Broader plausible denominator: 18.** Reported separately per the governing instructions; not used for the primary recall figure below.

## Recall

**Conservative: 11/17 = 64.7%.** This is the honest, disclosed headline finding of this cohort: substantially lower than v12's 87.5%, not because of any newly-introduced defect, but because this session's own real activity was more sustained/crowded than v12's, and therefore exercised the pre-existing, already-disclosed `blocked_ambiguous_boundary`/geometry-compatibility-tolerance limitation (OPEN, NO SAFE CORRECTION ESTABLISHED, untouched this session) far more heavily. **Broader (crediting the one low-confidence candidate as a miss, since it was never admitted either): 11/18 = 61.1%** — a lower bound, not the headline figure.

This directly and emphatically answers the candidate fact the prior milestone (Ambiguous-Boundary Real-Subject Recall Correctness v1) left open: *"does the already-disclosed geometry-compatibility-tolerance question... recur"* under real, sustained activity. **Yes** — not as one isolated case (the chartered v12 ~37:12 shape), but as the dominant mechanism behind 5 of 6 conservative recall misses this session, several of them themselves spanning dozens to hundreds of seconds of continuous, visually-unambiguous real bird presence.

## Recall-miss causal breakdown

Every one of the 6 conservative misses was traced to its own terminal ledger outcome (not merely assumed):

| # | offset | first irreversible stage | detail |
|---|---|---|---|
| 4 | 1467.0-1512.3 | `blocked_ambiguous_boundary` | 1 proposal, `proposal_boundary_ambiguous_with_adjacent_proposal` |
| 7 | 3378.9-3453.1 | `blocked_ambiguous_boundary` | preceded by 8 `blocked_continuation_pending` retries on the same proposal, terminal outcome ambiguous-boundary |
| 10 | 4496.7-4539.1 | `blocked_ambiguous_boundary` | 3 overlapping proposals, all ambiguous-boundary |
| 13 | 4788.2-4842.8 | `blocked_ambiguous_boundary` | 4 overlapping proposals, all ambiguous-boundary |
| 14 (missed portion) | 4948.7-5259.0 | `blocked_ambiguous_boundary` | **11 overlapping proposals**, all ambiguous-boundary, some preceded by continuation-pending cycling — by far the largest concentration of blocked activity in the session |
| 15 | 5325.7-5334.8 | `blocked_ambiguous_boundary` | 2 overlapping proposals (a related `blocked_missing_evidence` proposal on an adjacent boundary was a contributing, non-terminal signal, not the terminal cause) |
| 17 | 5988.2-5996.7 | `reject_insufficient_detector_corroboration` | single-generation proposal, `never_strong_and_minimal_detector_corroboration`, ground-foraging bird away from the feeder's usual detection zone |

**5 of 6 misses (83%) terminate at `blocked_ambiguous_boundary`; 1 of 6 at `reject_insufficient_detector_corroboration`; zero at `blocked_missing_evidence`, detector/tracker failure, or evidence-quality gate.** Not collapsed into one number, per the governing instructions — each miss's own stage is individually verified against the reconciled ledger.

## False Visits

**visit-observation-candidate-009 (4079.4-4089.5s) is a confirmed false Visit.** All 10 frames spanning its complete admitted duration (sampled at ~1.1s intervals, gapless) show no animal, bird, or any discernible subject — the scene is indistinguishable from a quiet baseline throughout. **Raw confirmed false-Visit rate: 1/14 = 7.1%.**

No other admitted Visit was found false: all other 13 show a real bird at some point within (or immediately adjacent to) their nominal window, though visit-007 and visit-012 show the bird only briefly within an otherwise-empty window (a boundary-tightness observation, not a false-positive — see "Useful evidence").

## False-Visit cause breakdown

visit-009's cause does not match any of the named categories with a known mechanism: not person-associated (no person visible), not a pure animal-class person misclassification, not a strong-confidence scene artifact (BioCLIP itself abstained — `species_guess: none` — consistent with there being nothing to classify), not a known persistent confusor (scene-confusor is off and zero regions are registered), not vehicle-associated. **Classified: other background/artifact — a low-confidence MDv5 trigger (permissive `score_threshold: 0.1`) on empty feeder/background with no identifiable cause**, structurally similar in shape (though not confirmed identical in specific cause) to v12's own single false Visit (`visit-observation-candidate-012`, also classified "other background/artifact"). Not combined with any other class.

## classifier_same_frame field re-proof

**Zero occurrences** this session (no `same_frame`/`classifier_same_frame` marker anywhere in the reconciled ledger or observation-status payload) — reported honestly per the governing instructions. Every admitted Visit's evidence came from the ordinary tracked-evidence-burst path, not the same-frame fallback.

## Dead-anchor field re-proof

**Exactly one `dead_anchor_promoted` occurrence** — `visit-observation-candidate-006`, proposal `visit-episode:2c56855a8c7f90e3c64f29eb`, a 2-generation component (`constituent_generation_ids`: 2), offset 1975.9s-2034.5s (58.6s duration), decided `2026-09-05T18:26:48.287893Z`.

- **Context**: this promotion sits inside a genuinely busy ~3-minute window (1853.6s-2034.5s) with four other overlapping candidate proposals in the same neighborhood, all independently rejected `blocked_ambiguous_boundary` at essentially the same instant (decided within 0.7-1.2 seconds of the promoted proposal — two orders of magnitude below the 10-second assembly-tick floor, confirming they were all arbitrated together, not a cross-tick dispatch defect).
- **Promoted member**: the 58.6-second proposal; BioCLIP's own suggestion for this Visit is `house_finch`.
- **Final outcome**: admitted, `review_status: needs_review` (correctly unreviewed).
- **Visual truth, confirmed**: a real bird is present essentially continuously across the promoted proposal's own window and the busy ~316-second bout it sits at the tail end of (encounter-period 5, 1718.5-2034.5s) — visually consistent with the house_finch coloring BioCLIP suggested (cannot independently confirm species at this camera's resolution). The promotion correctly rescued a real encounter; however, this same 316-second bout is also the source of the "partial coverage" observation in "Recall" — only the final 58.6s of a much longer real presence became a Visit.
- **Duplicate/fragmentation effect**: none observed — this promotion produced exactly one Visit for what visual review confirms is sustained real bird presence; no sibling Visit or duplicate was created for the same encounter.

This is the first cohort where the dead-anchor mechanism's field effect on recall/precision under real, sustained activity can actually be assessed on its merits (v13's own single occurrence was defeated by the evidence-capture defect before evaluation was possible).

## Ambiguous-boundary results

`blocked_ambiguous_boundary` fired **55 times this session** (55 distinct `proposal_id`s, all single-decision, no retries) — far more raw volume than any prior cohort (v12 had exactly one chartered instance), reflecting genuinely busy, sustained real activity now that the evidence-capture defect no longer intercepts everything upstream of arbitration.

**Systematic triage, not a raw dump**: cross-referencing every one of the 55 proposals' own start/end offsets against all 14 admitted-Visit windows (20-second padding) shows **44 of 55 sit inside or immediately adjacent to a window that did produce an admitted Visit** — the expected, healthy shape (one real bird generates several competing candidate proposals; the assembler's arbitration keeps one, the rest end here). The remaining **11 proposals collapse into 11 distinct time windows with no nearby admission at all**.

**Visual review confirms this is a real, material recall mechanism, not an edge case**: of these 11 "silent" windows, **8 show real, continuous (often multi-minute) bird presence** — including one 11-proposal-deep cluster spanning ~310 continuous seconds with confirmed simultaneous 2-bird moments. After merging into encounter-periods (see "Denominator methodology"), **5 of the session's 6 conservative recall misses terminate at `blocked_ambiguous_boundary`** — this is now the dominant, headline recall-limiting mechanism this cohort, not a rare corner case. None of the 5 individually resembles the chartered v12 ~37:12 case's own specific geometry closely enough to re-litigate that case (which remains **OPEN / NO SAFE CORRECTION ESTABLISHED**, untouched, not tuned this session) — but all 5 share its same root mechanism (the geometry-compatibility-tolerance question the Ambiguous-Boundary Real-Subject Recall Correctness v1 milestone left explicitly open as a "does it recur" candidate fact). **It recurs, substantially, under real sustained/crowded activity.**

Full component diagnostics (offsets, durations, decision timestamps) are preserved in the merged ledger and this report's own working data; see "Recall-miss causal breakdown" for the complete disposition.

## Detector-corroboration misses

`reject_insufficient_detector_corroboration` fired **4 times**, all `never_strong_and_minimal_detector_corroboration` (one with `:fallback_position_1`, the exhausted 3rd fallback attempt — see "Evidence survival"):

| offset | detection count (generation) | max confidence | independent visual truth |
|---|---|---|---|
| 99.8s-107.0s | 1 | not strong | see below |
| 127.8s-138.4s | 1 (fallback position 1) | not strong | see below |
| 418.4s-426.7s | 1 | not strong | see below |
| 5988.2s-5996.7s | 1 | not strong | see below |

All four are single-generation proposals falling through the `qualifying_floor = 2×1+1 = 3` rule with `detection_count` at or below that floor — the same accepted, already-hardened gate the prior ~57:07 v12 case exercised. The prior policy is **not reopened automatically**.

**Visual truth, confirmed for all four**: the first three (99.8-107.0s, 127.8-138.4s, 418.4-426.7s) show **no animal, bird, or subject of any kind** in any sampled frame — genuine non-events correctly rejected. The fourth (5988.2-5996.7s) shows a **real, plump grayish-brown bird foraging on the ground/grass, away from the feeder's usual detection zone** — a real animal the gate correctly-by-design rejected as insufficiently corroborated (a single, brief, off-feeder detection), not an incorrect filter. **3 of 4 correctly filtered non-events; 1 of 4 a real but genuinely marginal/uncorroborated encounter** — this is the session's 6th and final conservative recall miss (see "Recall-miss causal breakdown").

## Independent-corroboration participation

Directly measured through the same 4 `reject_insufficient_detector_corroboration` occurrences above — the detector-corroboration gate is the independent-corroboration mechanism in this codebase's own vocabulary. Natural participation confirmed (non-zero, unlike v13 where the evidence-capture defect meant zero occurrences of any kind could be observed).

## Scene-confusor participation

**Zero regions registered** (`regions_currently_adjusted: 0`, `regions_with_reviewed_evidence: 0`, `reviewed_evidence_enabled: false`) — confirmed directly from the ledger snapshot's own `scene_confusor_state` artifact at the final checkpoint. This feature remains **off by default**, as accepted; its zero-participation state is the expected default-off behavior, not evidence of anything failing to fire.

## Same-frame class-conflict participation

**Zero occurrences** — no marker anywhere in the reconciled ledger. Reported honestly per the governing instructions (zero is a valid result).

## Strong-artifact results

No strong-confidence scene artifact recurred this session (scene-confusor is off, and the one confirmed false Visit — visit-009 — does not resemble the historical persistent-confusor shape: no recurring location, no prior history, a single low-confidence background trigger — see "False Visits").

## Real-positive controls

**13 of 14 admitted Visits are confirmed real** (visit-009 is the one confirmed false — see "False Visits"), spanning 5.2-101.4 seconds of nominal Visit duration each. 8 of 14 received a non-abstaining BioCLIP species guess (house_finch ×4, mourning_dove ×2, carolina_chickadee ×1, brown_thrasher ×1); 6 of 14 received no species guess (abstention-friendly `None`, not a confident wrong label, and one of the six — visit-009 — correctly had nothing real to guess from at all). Every visually-observed bird was a small-to-medium brown/gray passerine or a plump gray-brown bird consistent with common feeder visitors typical of a Piedmont-NC yard in early September; no species guess was visually contradicted, though none could be independently confirmed at this camera's resolution/distance either (chickadee cap/cheek pattern, thrasher's larger/longer-tailed build, and dove-vs-finch silhouette were all beyond what the footage could resolve).

## Multi-subject observations

**One confirmed naturally-occurring simultaneous-subject pair, now visually verified, not only ledger-inferred**: `visit-observation-candidate-010` (4443.3s-4456.1s) and `visit-observation-candidate-011` (4445.0s-4456.1s) genuinely overlap in time (both active 4445.0s-4456.1s concurrently), sharing one Event (`event-observation-candidate-010`) via the accepted Event-reuse mechanism — Visit-011's own proposal decision reason is literally `candidate_visit_created_shared_event`. Direct visual inspection at 4450.5s (`frame-003825-offset004450511ms.jpg`) shows **two distinct real birds simultaneously in frame** — one perched at the feeder base, one in flight/landing nearby — confirming the multi-subject Phase-2 mechanism fired correctly on a genuine two-animal moment, not merely a ledger-inferred coincidence. BioCLIP suggested `carolina_chickadee` for Visit-011 and abstained (no guess) for Visit-010; the birds' small brown/streaky build is not inconsistent with this, but species cannot be independently confirmed at this camera's resolution.

Per section 24: only **2** simultaneous subjects observed (not 3+), so recorded honestly without a full grouping analysis. Checked directly against the accepted design invariants:
- **Sibling isolation**: confirmed — two distinct Visit ids, two distinct proposal ids, not merged into one.
- **No cross-subject corroboration**: confirmed — each proposal's own `constituent_generation_ids` are disjoint (010 and 011 reference different generation ids; no generation appears in both).
- **No obvious merge**: confirmed — both persisted as independent Visits.
- **No duplicate sibling Visit**: confirmed — exactly 2 Visits for what visual review confirms are 2 real, simultaneously-present subjects, not 3+ or a collapsed 1.

## Fragmentation

Automated `fragmentation_accounting.py` result (8 denominator units, built only from the 8 encounter clusters that produced at least one admitted Visit): **correctly_represented=6, fragmented=0, duplicate=0, missed=0, merged=0, ambiguous=2**. `fragmentation_rate: {state: "evaluated", value: 0.0}` — the tool now has enough real admission data to actually *evaluate* a rate for the first time in several cohorts (v13: `insufficient_data`, 0 admissions; v12: 0/14 via a weaker manual method, data-starved).

The 2 `ambiguous` units (`needs_review_unit_ids`) are exactly the two groupings investigated in depth above:

1. **Visits 003+004** (offsets 857.4-866.2s and 1183.3-1284.6s, a 317-second gap between them) — auto-flagged only because there is no shared tracker evidence or confident-sibling signal to positively rule out fragmentation, not because fragmentation is actually suspected. A 5+ minute gap is far larger than any single bird's dwell time observed anywhere else this session; see visual review for final disposition.
2. **Visits 010,011,012,014,015,016** (a 6-Visit span, 4443.3s-5474.9s ≈ 17.2 minutes, during the session's busiest activity window) — each individual Visit is brief (5.6-30.5s) and separated from its neighbors by 70-360 seconds, far exceeding the 15-second merge-gap threshold; 010/011 are the confirmed genuine simultaneous pair. The most likely honest reading is 5-6 separate real (or partly real/false — see visual review) brief encounters during a busy window, not a fragmentation defect, but this is confirmed below rather than assumed.

**Both ambiguous units resolved by visual review, confirmed not fragmentation**:

1. **Visits 003+004**: visually confirmed as two genuinely separate real encounter-periods (769.1-1059.5s and 1125.7-1284.6s), divided by a real, confirmed-quiet ~66-second gap — **correctly represented**, not fragmentation.
2. **Visits 010,011,012,014,015,016**: visually confirmed as a busy period containing multiple genuinely distinct real encounter-periods (the confirmed simultaneous 010/011 pair; a separate brief 012 encounter at the window's tail; separate brief 013/014/015/016 encounters) rather than one bird split repeatedly — **correctly represented**, not fragmentation. (This does not mean recall was complete within this busy period — see "Recall-miss causal breakdown" for the ~310-second sub-bout that received zero admission at all, a recall finding, not a fragmentation one.)

**Confirmed fragmentation rate: 0/8 = 0.0%**, now backed by full visual confirmation rather than merely an absence of contrary evidence.

## Duplicates

- Shared tracker evidence: **zero** — direct check across all 14 admitted Visits' own `constituent_generation_ids` confirms no `track_generation` id is ever claimed by more than one admitted Visit (including the 010/011 pair, which are genuinely distinct tracks, not one track split in two).
- Duplicate sibling admissions: **zero** (`duplicate_count: 0` from the automated fragmentation accounting).
- Same biological encounter independently persisted twice: none found in the above check.
- Replay/retry-induced duplicate evidence: not applicable — this was a single continuous live session, not a replay; `is_superseded: false` for all 14 Visits, `review_status: needs_review` uniformly (no retry-driven state corruption).
- This continues the unbroken 0%-duplicate streak every cohort since v7 has shown, now on real data with substantial admission volume (14 Visits, not the 0-1 of several intervening defect-affected cohorts).

## Useful evidence

Per-Visit classification, from direct visual cross-check (not assumed from BioCLIP's own species-guess presence, which is neither necessary nor sufficient for a correctly-framed real subject):

- **Useful subject evidence, well-framed** (real bird clearly/continuously visible within the Visit's own window): visit-003, -004, -005, -006, -008, -010, -011, -013, -014, -015, -016 = **11 of 14**.
- **Real subject, poor framing/incomplete temporal coverage** (a real animal did appear, but only in a small slice of the Visit's own nominal window — a boundary-tightness characteristic, not a false positive): visit-007 (bird visible only in the window's first frame, a flyby) and visit-012 (bird visible only in the final ~1.7s of an 11.8s window) = **2 of 14**.
- **False/background**: visit-009 = **1 of 14**.
- **Unresolved**: none — every one of the 14 admitted Visits reached a definite visual determination.

**Primary useful-evidence rate (well-framed only): 11/14 = 78.6%. Including legitimate real-but-loosely-framed alternates: 13/14 = 92.9%.** Both figures land close to v12's own 77.8%/94.4% — a second, independently-consistent data point for this metric.

## True latency

**Primary v14 objective — by far the best-sampled true-latency distribution in project history.** v12 had n=2 usable measurements; v13 had n=0 (zero Visits existed at all). This session: **14 attempted, 14 valid (100%), 0 invalid, all `state: "measured"`, all `clock_calibration_state: "normalized"`** (RTT-bounded, never a Host-receive-time substitute, never reported outside a valid calibration interval).

| stat | value |
|---|---|
| attempted n | 14 |
| valid n (measured) | 14 |
| invalid n | 0 (0 unavailable_capture_time, 0 invalid_negative, 0 implausible, 0 invalid_clock_mapping) |
| fallback-measured | 1 (visit-008, `fallback_position: 1`) |
| median | 82,920.6 ms (≈82.9s) |
| p90 | 235,454.9 ms (≈3.9min) |
| p95 | 253,408.4 ms (≈4.2min) |
| max | 261,211.4 ms (≈4.35min), visit-014 |
| mean | 117,421.4 ms (≈2.0min) |

Per-sample range: minimum 59,379.4ms (visit-005), maximum 261,211.4ms (visit-014) — every sample used the RTT-bounded anchor (`t0_source: earliest_constituent_generation_start_captured_at`), with `clock_uncertainty_ms` between 6.1 and 12.4ms throughout (tight, consistent with the session's own excellent RTT-calibration batch quality).

**Full-session RTT-bounded clock calibration** (the infrastructure underpinning every latency sample above): **528 batches, 527 `calibrated` (99.8%), 1 `insufficient_samples`, 0 `inconsistent_samples`, 0 clock jumps** — `offset_ms` range `[-167.894, -48.854]` (the offset itself drifted over the session, as expected for a real, unsynchronized Node clock, but always within a tight, honest bound), `uncertainty_ms` median 9.45, `rtt_ms` median 34.0. This is, together with v13's own 523/518, the largest, cleanest RTT-calibration sample of any cohort — but unlike v13, this time it is paired with 14 real admitted Visits, so the infrastructure's own quality translates directly into usable latency evidence rather than sitting orphaned. This large, clean, materially-better-than-v12 sample substantially strengthens (without yet fully closing) the true-latency dependency: the median (~83s) and tail (~4+ minutes for the two longest-latency Visits) are both far above what a user would intuitively expect from "capture to visible," directly corroborating the previously-flagged Visit-Continuity-design tail-latency root cause (v9) with the richest real evidence to date. "Tail after last contributing capture" is effectively the max figure above, since this session's own last admitted Visit (016, 5415.3-5445.9s) is not the one with maximum latency — visit-014 (4921.0-4927.1s, itself quite early, ~82 minutes before session end) took the longest to become visible, again consistent with continuation-pending/arbitration cycling rather than a stop-time artifact.

## Gate B

The session's one confirmed false Visit (visit-009) received **no species claim at all** (`species_guess: None`) — correct, abstention-friendly behavior on evidence that visual review confirms genuinely contains nothing to classify. Every one of the 8 species-labelled Visits (house_finch ×4, mourning_dove ×2, carolina_chickadee ×1, brown_thrasher ×1) is one of the 13 confirmed-real Visits, and none was visually contradicted. **Zero confident wildlife species labels on a false Visit — zero Gate B recurrences this session**, extending the closed status of Background/Empty Evidence Species-Confidence Correctness v1 with a second real, substantially-larger cohort of evidence.

## Monitoring / recovery

- Requested duration: ~100 minutes (target band 90-105). Actual: 102.68 minutes.
- Actual coverage: independent recorder 99.73% (see "Independent recorder"); zero gaps >10s.
- Node connectivity: **zero disconnects, zero reconnects** — `boot_id` (`4239527b-5622-425c-bed1-ae3074e191dd`) unchanged throughout; Node's own `service_started_at` (17:45:20Z) predates session start and was never restarted mid-session; `sudo journalctl` over the exact session window shows zero error/restart/disconnect/fail log lines; watchdog `consecutive_probe_failures: 0` at final check.
- Detector/model failures: none — `cuda_available: true`, `CUDAExecutionProvider` selected throughout, zero crashes, zero fallback to CPU.
- Stop-finalization: clean, ~4 seconds, `stopped_reason: "user_stopped"`.
- Final Observation state: `state: "stopped"`, `observing: false`.

## Storage

- Requested root: `/mnt/c/Users/zachk/AppData/Local/MockingBirdFieldAcceptanceV14` (WSL-visible form of `C:\Users\zachk\AppData\Local\MockingBirdFieldAcceptanceV14`).
- Resolved/probed root: `/mnt/c/Users/zachk/AppData/Local` (the real Windows C: drive — correct filesystem identity, using the corrected post-storage-preflight-fix convention).
- Filesystem identity: `filesystem_device_id: 71`, `platform: posix`, `resolution_method: direct`.
- Starting free space: 29.9GB (`storage_health_tier: getting_low`, `sufficient: true` against a 6.0GB recorder+reserve budget).
- Minimum free space during session: not separately sampled mid-session (no low-storage warning surfaced in any of the 22 checkpoints or 10 health-check polls).
- Ending free space: 19.66GB (`storage_health_tier` still `getting_low` — never crossed into `low`/`action_recommended`/`critical`).
- Consumption this session: ≈10.24GB (dev-root final size 8.48GB — release build + userdata + 4.10GB recorder + 59MB media — plus some outside the dev-root itself, e.g. Windows page/cache activity).
- Safety tier: `getting_low` throughout, never `action_recommended` or worse.
- One prior disposable instance (`MockingBirdFieldAcceptanceV13`) was freshly re-verified `SAFE_TO_RECLAIM` (9.42GB) but its `cleanup --destroy` was blocked by this session's own permission classifier; left archived, untouched — not required, since headroom was already sufficient throughout.

## Cohort comparison

| metric | v12 (2026-09-03) | v13 (2026-09-04, defect-affected) | v14 (2026-09-05) |
|---|---|---|---|
| session duration | 96.97 min | 101.8 min | **102.68 min** |
| admitted Visits | 18 | **0 (defect)** | **14** |
| conservative recall | 14/16 = 87.5% | 0% (defect, excluded) | **11/17 = 64.7%** |
| false-Visit rate | 1/18 = 5.6% | n/a (0 Visits) | **1/14 = 7.1%** |
| fragmentation | 0/14 = 0% (manual, data-starved) | `insufficient_data` | **0/8 = 0.0%** (automated + visually confirmed) |
| duplicates | 0/18 = 0% | n/a | **0/14 = 0%** |
| useful evidence | 77.8% primary / 94.4% incl. alternates | n/a | **78.6% primary / 92.9% incl. alternates** |
| `blocked_missing_evidence` | 15/175 recovered events (basis differs) | **88.5% (defect)** | **4.2% (8/191)** |
| ledger completeness (`proposal_outcomes`) | 53.85% (hand-computed, ad hoc tool) | 44.6% (tooling defect) | **100.0% COMPLETE** |
| true latency n (measured) | 2 | 0 | **14** |
| true latency median | 110,578.8ms (n=2, not defensible) | n/a | **82,920.6ms (n=14)** |
| monitoring coverage | qualitative only (ledger gap) | 99.99%, max gap 3.68s | 99.73%, max gap 5.80s |
| RTT-calibration batches | 100 (99 calibrated) | 523 (518 calibrated) | 528 (527 calibrated) |
| scene-confusor regions | 14 (off-default finding) | 0 (no activity) | 0 (off by default; real activity present) |
| dead-anchor occurrences | n/a (fix not yet built) | 1 (defeated by defect) | **1 (evaluable on its merits)** |
| classifier_same_frame | n/a | 0 | 0 |

v13's own recall/evidence-survival/latency figures are **defect-attributable, not representative**, and are correctly excluded from any averaging below (per the governing instructions and v13's own accepted disposition) — v14 is compared against v12 and the broader pre-v13 body for those dimensions, not against v13 itself.

## Budget-convergence analysis

- **Duplicate rate**: v14 reaffirms 0% on real, substantial admission data (14 Visits, zero shared tracker evidence, zero automated duplicate flags) — consistent with the unbroken streak since v7. **Remains READY FOR BUDGET** (candidate ≤1%, effectively 0%).
- **Monitoring coverage**: v14's 99.73% (max gap 5.80s, zero gaps >10s) sits within the established 97.5%-99.99% band across every real cohort to date, though it is not v14's own tightest result (v13 was tighter at 99.99%/3.68s). **Remains READY FOR BUDGET** (candidate ≥95%, or the more precise ≥99% figure v5 proposed) — no cohort has fallen meaningfully short, and this session does not change that.
- **Evidence-capture profile recovery / evidence survival**: now has its first fully clean, defect-free representative datapoint (0 evidence-burst failures across 204 requests, `blocked_missing_evidence` at 4.2%, squarely inside the pre-defect 4.6%-18.3% band). This is one clean cohort, not yet a converged multi-cohort body specific to the *corrected* code path — the historical pre-v13 cohorts (v6-v12) are a valid comparison population since the evidence-capture defect was proven (Camera Node Evidence-Capture Profile Validity & Failure Observability Correctness v1) to be a v13-only regression, not present in v6-v12. Treating v6-v12 plus v14 as one consistent population, `blocked_missing_evidence` converges in the 4.2%-18.3% range across 8 real cohorts. **Candidate for READY FOR BUDGET at a generous ceiling (e.g., ≤20%)**, but this milestone does not self-adopt a number — see "Proposed budgets."
- **Proposal-outcome ledger completeness**: v14 is the first cohort to reconcile 100% COMPLETE on all three artifacts with a properly-fixed tool. This closes the *engineering* side of the dependency (the tool works); it does not yet establish a "ledger completeness budget" as a release metric, since 100% is simply correctness, not a tunable threshold.
- **False-Visit rate / fragmentation / useful evidence**: this session supplies the first substantial *defect-free* admission volume since v12 (14 Visits vs. v12's 18), and all three figures (7.1% false-Visit, 0.0% fragmentation, 78.6%/92.9% useful evidence) land close to v12's own (5.6%, 0.0%, 77.8%/94.4%) — genuinely consistent, mutually-reinforcing evidence across 2 clean cohorts. Still **MORE EVIDENCE REQUIRED** for a formal budget (2 cohorts is not yet a converged body), but the convergence so far is encouraging rather than concerning.
- **Recall — a materially different, more urgent picture than "more evidence required" alone conveys**: v14's own 64.7% is *lower* than v12's 87.5%, not from any new defect but because this session's real activity was more sustained/crowded and therefore exercised the pre-existing, disclosed `blocked_ambiguous_boundary`/geometry-tolerance limitation far more heavily (5 of 6 conservative misses trace directly to it). This is exactly the "does the geometry-compatibility-tolerance question recur" candidate fact the prior milestone (Ambiguous-Boundary Real-Subject Recall Correctness v1) left open — **answered: yes, substantially, under real sustained/crowded conditions.** A numeric recall budget remains **MORE EVIDENCE REQUIRED** (2 cohorts, divergent results, both honest), but the *qualitative* conclusion — that recall is materially activity-density-dependent through a known, disclosed, deliberately-unfixed mechanism — is now far better evidenced than before, and belongs prominently in Gate A's remaining dependency list, not buried in a "needs more data" footnote.
- **True latency**: v14 alone (n=14) now dwarfs the combined n=2 (v12) prior evidence. This is a *single* cohort, but with a much larger, cleaner sample than the entire prior history combined. Given the median (~83s) and p95 (~253s) both comfortably exceed a full order of magnitude past "instant," and no contrary evidence exists at any prior cohort, this materially strengthens the case that Visit-Continuity's own design induces genuine multi-second-to-multi-minute latency as an inherent property, not a session-specific anomaly — but one cohort's own n=14, however clean, is not by itself a converged cross-session budget body. **MORE EVIDENCE REQUIRED** for a formal number, though the qualitative conclusion (latency is real, material, and traceable to Visit-Continuity design) is now much better supported than before.

## Proposed budgets

- **Duplicate-Visit rate ≤1% (effectively 0%)**: reaffirmed, unchanged from v12's own proposal — 4 consecutive cohorts with admission activity (v7-v12, v14) at real 0%.
- **Monitoring coverage ≥95%** (or the tighter ≥99% v5 proposed): reaffirmed — every real cohort to date, including v14, falls in the 97.5%-99.99% band.

## Why other budgets remain premature

- **Recall, false-Visit rate, fragmentation, useful evidence**: only 2 defect-free cohorts with real admission volume exist (v12, v14) — not a converged body. A third clean cohort is still the honest next-evidence requirement, per every predecessor's own stated dependency list (unchanged in substance by this milestone alone).
- **Evidence-capture/`blocked_missing_evidence`**: v14 is the first *post-fix* clean datapoint; the pre-fix v6-v12 population remains a valid comparison set, but a release budget specifically validated against the corrected code path should not be adopted from one post-fix cohort alone.
- **True latency**: v14's own n=14 is excellent within-cohort evidence but is still one session. A numeric latency budget (e.g., "p95 must be under N seconds") is not proposed here — inventing a precise-sounding target from a single cohort, however clean, is exactly the discipline this file's own governing instructions warn against.

## Reproduced defects

1. **Field-tooling only** (this session's own scratch orchestration, never committed): stray PowerShell CRLF in an extracted bearer token; untranslated WSL path passed to a Windows-native process argument. Both caught and fixed within ~90 seconds, before any real session time was affected. See "Field lifecycle."
2. **No new product-level defect.** Every observed limitation this session — the `blocked_ambiguous_boundary` recall losses, the one false Visit, the two loosely-temporally-bounded real Visits (007, 012) — matches already-disclosed, already-open, deliberately-unfixed behavior operating exactly as designed, not a newly-discovered code defect. This session's own headline contribution is a substantially richer, larger-scale **reproduction** of the already-disclosed ambiguous-boundary/geometry-tolerance limitation (previously one chartered case, v12's ~37:12; now the dominant cause of 5 of 6 conservative recall misses under real sustained/crowded activity) — real, important, disclosed evidence, not a new bug. Per governing instructions, this was **not** patched, tuned, or investigated for a fix during the cohort.

## Gate A decision

**Classification A criteria checked individually, not assumed:**

- Representative daylight cohort: yes (genuine Saturday-afternoon daylight, clear sky, visually confirmed).
- Accepted production configuration: yes (exact `git_commit` match, schema v58, MDv5a/0.1/0.45/CUDA/BioCLIP-2 all confirmed unchanged throughout).
- Independent recorder complete enough for denominator work: yes (99.73% coverage, used as the actual primary source for every recall/precision/fragmentation determination in this report).
- Corrected ledger pipeline demonstrably works: yes — **100% COMPLETE on all three artifacts**, the first cohort ever to achieve this.
- `proposal_outcomes` reconciliation COMPLETE: yes, unconditionally (191/191, zero gaps).
- Evidence-capture profile recovery field-accounted: yes (204/204 captures, 1 reconciliation, zero failures, continuously monitored, not just checked at the end).
- Actual evidence bytes persist: yes (34 real files, 59MB, visually spot-checked at full resolution).
- Prospective denominator credible: yes — built from the independent recorder first, cross-checked against every ledger-derived candidate window, methodology and its own approximations disclosed.
- Recall measured: yes — 11/17 = 64.7%, with a complete, individually-verified miss-by-miss causal breakdown.
- False-Visit precision measured: yes — 1/14 = 7.1%, cause identified.
- Fragmentation measured: yes — 0/8 = 0.0%, visually confirmed (not merely inferred from absent contrary evidence).
- Duplicates measured: yes — 0/14 = 0%.
- Useful evidence measured: yes — 78.6%/92.9%.
- Evidence survival measured: yes — 4.2% `blocked_missing_evidence`, zero burst failures.
- True latency materially better sampled than v12: yes, dramatically — n=14 fully measured vs. v12's n=2.
- Monitoring measured: yes — 99.73%, zero disconnects.
- Gate B checked: yes — zero recurrences.
- Budget-convergence analysis honest: yes — duplicate-rate/monitoring-coverage reaffirmed; every other metric explicitly held at "more evidence required" rather than forced.
- Cleanup complete: yes (see below).
- No field-time product tuning: yes, confirmed.

**Every explicit Classification A criterion in the governing instructions is met, several (ledger completeness, evidence-capture, true-latency sample size) decisively so. Classification: A.**

**Gate A itself remains OPEN.** Classification A does not mean Gate A passes — and it does not here. This session's own most important contribution is not a closure but a **sharpening**: the `blocked_ambiguous_boundary`/geometry-compatibility-tolerance limitation, previously evidenced by one chartered case (v12's ~37:12), is now shown to cause the majority (5 of 6) of this session's own conservative recall misses, several spanning tens to hundreds of seconds of unambiguous real bird presence, under genuinely sustained/crowded activity. Recall (64.7%) is not credible as a release-ready number in its current state — not because it was measured badly, but because it honestly reveals a real, substantial, already-disclosed limitation that has not been fixed and, per this file's own standing discipline, was correctly not tuned during this cohort.

## Remaining Gate A dependency

Restating the pre-existing 13-item list plus item (14) (both unchanged in substance where not explicitly advanced below), with this session's own effect:

- **Item (14) [evidence-capture defect-fix + field-re-proof; proposal-outcome ledger-cadence dependency]: now fully CLOSED, both halves.** This session is the representative field cohort both fixes were waiting for — evidence-capture profile recovery and proposal-outcome ledger completeness both proved clean, live, together, for the first time.
- **Item (12) [a cohort with intact full-session raw-ledger coverage]: CLOSED.** 100% COMPLETE on all three artifacts, zero gaps — the first cohort to actually deliver what this item asked for.
- **Item (4) [a second independently-varied true-latency cohort]: CLOSED.** n=14 (vs. v12's n=2), a materially different and much richer session, both fully measured.
- **Item (2) [a second person-confound-free cohort confirming v12's false-Visit rate is representative]: substantially advanced, not fully closed.** v14 is independently person-confound-free (no person appeared, confirmed) and its own 7.1% false-Visit rate sits close to v12's 5.6% — two mutually-consistent cohorts now exist, but the standing discipline (do not adopt a budget from 2 cohorts) means this stays short of a numeric closure.
- **NEW, most urgent remaining item**: **field-re-confirm whether a safe correction exists for the `blocked_ambiguous_boundary`/geometry-compatibility-tolerance limitation, now shown to materially suppress recall under sustained/crowded real activity** (5 of 6 conservative misses this session, up from 1 chartered case previously). This does not reopen the specific v12 ~37:12 case (still OPEN / NO SAFE CORRECTION ESTABLISHED, still untouched) but elevates the general question well above "candidate fact for a future cohort" status — it is now this cohort's own best-evidenced, most consequential open item, ahead of items (1), (3), (5)-(11), (13) below.
- **Items (1), (3), (5)-(11), (13): unchanged in substance** — (1) never-strong single-generation confusor still unmet; (3) full-ledger-coverage fragmentation re-proof at full tool strength: now materially advanced (this session's own fragmentation accounting ran at full strength against complete ledger data, 0/8, visually confirmed) though the historical item's own precise wording targeted a different prior gap; (5) 3+-simultaneous-subject cohort still unmet (2 confirmed this session, not 3+); (6)-(7) v7's own historical residuals untouched; (8) same-frame class-contradiction's effect on person-associated false Visits: still unmet, no person recurred; (9) further strong-confidence scene-artifact recurrence: still has not recurred; (10) whole-frame human suppression: still only trivially satisfied; (11) scene-confusor participation: directly re-measured (zero regions, off by default, consistent); (13) `reject_no_identification_or_context`'s own standing question: not exercised this session in a form that bears on it further.

## Cleanup / final state

- Final ledger checkpoint: 22nd periodic checkpoint plus the live final corrective fetch, both captured before stop.
- Observation stopped cleanly (`user_stopped`); `stop_finalization_pending` resolved to `state: "stopped"` within ~4 seconds.
- Whole dev deployment stopped and verified (`deploy_windows_dev.py --stop`: "Stopped 1904421 (verified)").
- Ledger collector process stopped cleanly after its final checkpoint.
- All artifacts reconciled: ledger 100% COMPLETE, Gate A measurement accounting run, visits exported, contact sheets + representative full-resolution samples archived, PROVENANCE.md written.
- Independent recorder confirmed complete (5,182 frames, 4.10GB, span matching `session_last_offset_ms` exactly).
- Lifecycle: `init` → `active` → `completed` → **`archived`** (`data/field-acceptance/2026-09-05-gate-a-v14-corrected-evidence-path-reproof/`); `assess` re-verified: **`verdict: SAFE_TO_RECLAIM` (9.10GB)** — **not destroyed**, per standing "do not destroy by default" discipline, left available for a future session's own reclamation decision.
- Camera Node pairing: **deliberately left paired** to this archived instance, matching established precedent (v13 did the same) — no destructive unpairing performed.
- No stale Observation/process remains: confirmed zero Windows-side python/pythonw processes running; Node's own `boot_id` unchanged, watchdog healthy, zero disconnects/errors in its service journal across the full session window.
- No production code modified; Tier 1/2/3 not required (zero production runtime diff).

## Decision

**A**
