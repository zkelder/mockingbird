# Representative Daylight Gate A Field Acceptance v6 — Post-Fix Replication & Multi-Subject Tranche

Status: **Classification B.** A real, live, 106.63-minute Observation session against the real reference Camera Node, on the accepted, unmodified build, directly confirms that the *specific* Sustained-Activity Visit Admission Starvation mechanism v4 found (arbitration deferring a whole connected component forever) does **not** recur — arbitration reached a decision for every ambiguous component on schedule, throughout the session, exactly as designed. However, `candidates_created` ended the session at **zero** despite substantial, independently-confirmed, sometimes-simultaneous real wildlife activity — the same practical symptom v4 produced, now root-caused to a **different, precisely-diagnosed mechanism**: the sole arbitration winner for a real, resolved component can fail at the downstream evidence-availability gate (the bounded 128-entry evidence-byte cache), and because that outcome is not retryable and no fallback to a runner-up exists, the component's real activity is permanently lost. This is a concrete, real-field instance of an already-disclosed residual risk (named when the evidence-cache bound was last raised, "a pending-proposal-aware eviction policy... is a materially larger change... left as a disclosed follow-up, not undertaken here") — not a new defect class, but a materially sharper, session-wide measurement of its real consequence than existed before. Two independently-confirmed real activity windows (≈6.8 and ≈5+ minutes, both containing simultaneous multi-bird moments) were both entirely lost this way — 0/2 exhaustive-denominator recall. See "Decision," below, for the complete reasoning.

## Identity

- Repo HEAD at start and throughout: `a09a91d89c991a9fd3714d2567000916a9380753` (branch `main`, not pushed, ahead 263 of `origin/main` before this session; two bounded deploy-tooling commits added during this session, described under "Defects," below — zero product/perception/admission/Visit/evidence/classification code touched). Matches the governing instruction's stated starting state exactly (verified before any action).
- Deployed HEAD: `a09a91d89c991a9fd3714d2567000916a9380753` — **exact match**, confirmed via `GET /api/product/instance` (`instance_id` `4f94e5917c7af01b98e2473f88e53a71`, `build_id` `2d15cc1fb34b4ce8`, `app_version` `0.1.0`) and independently re-confirmed live from the running Observation Engine's own `model_runtime_metadata` (MDv5a fingerprint match, below).
- Schema: `v58` (`CURRENT_DATABASE_SCHEMA_VERSION`, `src/mockingbird/storage/database.py:45`), unchanged.
- Date/time: Monday 2026-08-31. Session `2026-08-31T13:19:59.630215Z`–`2026-08-31T15:06:37.176187Z` UTC = **09:19:59–11:06:37 EDT**, a genuinely different daylight window from every prior accepted cohort (v4: afternoon–evening; v5: 16:36–18:23 EDT) — a fresh mid-morning window, real cohort diversity rather than a mechanical repeat.
- Conditions at start: clear blue sky, bright direct morning sun, no precipitation, dry ground, calm (no wind-driven foliage blur across 9 live-preview spot-check frames spanning ~50s pre-session). Camera Node healthy (8/8 cameras, self-test passed, watchdog healthy), GPU idle of any MockingBird process (0% util, background desktop only), storage 30.8GB free (down from v5's 40.36GB the day before — a continuing, already-separately-tracked decline; storage ended the session at 21.96GB free, disclosed, not blocking), acceptance recorder confirmed armed before the session and confirmed writing real frames within seconds of session start.
- Stream/camera: `stream-b0d8cec9129d` ("Field Acceptance V6"), backed by the real reference Camera Node (`node-<id>`, `<node-ip>:8787`), camera `picamera2-camera-0` ("Pi camera 1") of 8 the Node advertised — the identical physical camera every prior accepted daylight cohort (v4, v5) used. One full-frame Zone (`zone-004`, `yard` type, polygon 0.02–0.98 both axes), matching v4/v5's own configuration exactly.
- Deployment: a genuinely fresh, disposable dev-root (`MockingBirdFieldAcceptanceV6`), **not** the operator's long-lived `MockingBirdDev` identity — disposable local Administrator, disposable Field Acceptance Operator bearer credential (`field-acceptance-281940465b3a4353`, 6-hour TTL), minted via the accepted non-interactive mechanism. No operator password/token/browser-cookie/manual step was ever requested from or supplied by the user. The Camera Node's single-slot pairing (still held by v5's now-stopped disposable instance) was reset via the identical supported recovery flow v4/v5 each used, with the user's explicit approval obtained this session (recorded, not assumed) before acting — the operator's own `MockingBirdDev` identity was not newly disrupted by this (it already needed a re-pair since v5).
- **Sandbox networking note, disclosed for completeness:** this sandbox's WSL shell cannot reach `127.0.0.1:8000` (nor the Windows host's own gateway IP) at all this session — confirmed by direct, repeated connection-refused/timeout tests. All API interaction this session therefore went through `powershell.exe`/`Invoke-WebRequest` (matching this project's own documented "python.exe/powershell.exe" interop pattern), never the WSL-side `field_acceptance_client.py`/`manage_field_acceptance_credential.py` convenience scripts, which would fail to connect the same way. This is a sandbox/environment limitation, not a product defect — every call still went through the real, unmodified, authenticated HTTP API.

## Frozen configuration

Recorded live from the running Engine's own `model_runtime_metadata` immediately after Observation start and re-confirmed unchanged at stop:

- **Detector:** MDv5a ONNX, `score_threshold` **0.1**, `nms_iou_threshold` **0.45**, `nms_max_detections` 300, model fingerprint `b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc` — **exact match** to the accepted provenance record and to v4/v5's own confirmed fingerprint. `CUDAExecutionProvider` selected (real GPU inference, RTX 4060 Ti); `TensorrtExecutionProvider`/`CPUExecutionProvider` listed as available but not selected.
- **Provider:** `frame-driven-onnx-cuda` (the accepted continuous/near-continuous frame-driven Camera Node path), `detector_provider_key` `onnx-cuda`.
- Tracker/admission/evidence-cache/BioCLIP/eligibility configuration: not independently re-read field-by-field from source this session (unlike v5); instead confirmed unmodified by construction — `git diff` against accepted `a09a91d` shows only `scripts/deploy_windows_dev.py` and `tests/test_deploy_windows_dev.py` touched this session (pure deploy tooling, never imported by the running product process). The values already accepted at `a09a91d` therefore applied unchanged throughout: `ambiguous_gap_ms` 45,000ms, `maximum_episode_duration_ms`/`maximum_component_pending_ms` 1,200,000ms (20min), `_MAX_CACHED_BURST_BYTES` 128, `EvidenceScoringBounds.max_candidates` 16, Identification Eligibility (`identification-eligibility-v1`, `score_floor` 0.7, `margin_floor` 0.2) plus the accepted geometry-corroboration eligibility check (`26edddf`). No tuning of any kind was performed during the cohort.

## Independent denominator

Methodology matches v4/v5's own established discipline: full-resolution frames for verification, contact sheets only for navigation, product ledger/track timestamps only to locate likely intervals, never a sparse blind sample mistaken for proof of absence.

The accepted acceptance-recorder ran the entire session (armed via `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` before deploy, confirmed writing real frames within seconds of Observation start). Real output: **5,214 frames, ~4.1GB**, first frame at offset 0ms, last at offset 6,359,321ms of a 6,397,546ms total session span ⇒ **~99.4% temporal-span coverage** (effective ~0.82 frames/sec against the 1.0Hz nominal cadence, comparable to v5's own ~0.80fps).

### EXHAUSTIVE DENOMINATOR WINDOWS

Two contiguous windows were chosen from the counterfactual ledger's own record of where real, ambiguous, multi-proposal clusters occurred, and reviewed exhaustively (contact sheets covering every recorded frame in the window for gross scene-health, plus targeted full-resolution pulls at every candidate activity moment identified from the ledger's own timestamps):

**Window 1: session offset 19.0–32.0min (13.0 minutes), 480 recorder frames, all reviewed via 16 contact sheets + 8 full-resolution frames at ledger-flagged moments.**
- 21.94min: no bird visible (real, confirmed-empty baseline before the segment starts).
- 22.90min: 1 bird perched on the seed feeder.
- 24.35min: 1 bird still present (same position).
- **25.79min: 2 birds simultaneously present** — one on the feeder perch, a second bird with visible tail feathers on/near the branch just below-right of the feeder (a genuine, directly-confirmed simultaneous-multi-subject moment). This is the exact offset of the proposal that won arbitration and then failed at the evidence gate (see "Defects").
- 26.53min: 1 bird on the feeder.
- 27.93min: 2 birds visible (1 on feeder, a second shape in the crepe myrtle behind).
- 28.56min, 29.59min: 1 bird on the feeder each time.
- **Bounded activity segment (continuous, not invented as discrete encounters, per this milestone's own honest-accounting instruction): ≈22.9–29.7min (≈6.8 minutes), subject count ≥1 throughout, ≥2 simultaneously at 25.79min (confidence: high, directly confirmed) and likely at 27.93min (confidence: medium), confidence overall: high that real activity occurred, but the exact internal encounter count is not invented — abstained.**

**Window 2: session offset 84.0–93.0min (9.0 minutes), ~443 recorder frames, reviewed via 11 contact sheets + 8 full-resolution frames at ledger-flagged moments.**
- 84.00min: no bird visible (real, confirmed-empty baseline).
- 85.47min, 85.75min: 1 bird on the feeder.
- 86.50min: 1 bird on the feeder (a cyclist also passes on the street, unrelated background activity).
- 87.63min: 1 bird on the feeder.
- 88.30min: no bird visible (a real, brief gap within the segment).
- 89.00min: 1 bird landing/in flight beside the feeder.
- **90.50min: 2–3 birds simultaneously** — one perched near the feeder pole top, one in flight with wings spread near the feeder, a possible third at the feeder base (a genuine, directly-confirmed active multi-bird flurry).
- **Bounded activity segment: ≈85.47–90.5min+ (≥5 minutes, likely longer — the segment had not visibly ended by the last frame checked), subject count ≥1 throughout, ≥2–3 simultaneously at 90.50min (confidence: high, directly confirmed).**

Both exhaustive windows: **0/2 activity segments represented by any admitted Visit** (there were none, session-wide — see "Sustained-activity replication").

### SUPPORTING SESSION EVIDENCE (not exhaustive)

A whole-session sweep (71 frames, ~90-second intervals, 2 contact sheets) confirmed: continuous, stable framing throughout (no camera glitches/dropouts/occlusion), gradually shifting natural morning light consistent with real continuous daylight, no precipitation or fog at any sampled point, no unexplained coverage gap. At this sparse an interval it cannot, by itself, reliably catch every brief encounter (matching the same lesson every prior cohort's own report already established) and was used only for gross scene-health, not for the recall conclusion below. The full session structured log (`mockingbird.log`, 164 lines) shows **zero ERROR/CRITICAL/WARNING lines** across the entire session — independently corroborating a clean, uneventful runtime apart from the admission-outcome finding itself.

The counterfactual ledger's own full-session history was reconstructed losslessly by combining two mid-session snapshots (0–38.5min, 0–48.57min, both with `evicted_count: 0` — complete) with the final post-stop snapshot (which retains only the most recent ~215 records once ring-buffer eviction begins) — the merged, deduplicated set totals exactly 521 records, matching the session's own final `recorded_count: 521` exactly, confirming zero loss in this reconstruction.

## Sustained-activity replication

**Primary question this milestone exists to answer: does the repaired sustained-activity pipeline replicate under a second representative cohort?**

**Partially — the specific starvation mechanism does not recur; the practical zero-admission outcome does, via a different mechanism.**

- `candidates_created` stayed at exactly **0** for the entire 106.63-minute session, despite `track_updates_observed` reaching 11,078, `evidence_candidates_observed` reaching 2,954, and `proposals_observed` reaching 521 — the detector, tracker, and proposal-assembly stages were all genuinely, continuously active throughout.
- **This is not a recurrence of v4's own mechanism.** Directly confirmed by reading `resolve_ambiguous_boundary_arbitration`/`_run_assembly_tick` (`src/mockingbird/observation/candidate_visit_authority.py`, `engine_runtime.py`) against the real ledger data: components reached arbitration decisions on schedule throughout the session — 164 proposals correctly, permanently resolved `blocked_ambiguous_boundary` (non-winning cluster members, exactly the intended "at most one Visit per ambiguous cluster" behavior) and 48 proposals reached a real arbitration **win** that then failed one gate later (see "Defects"). Nothing was left unconditionally deferring the way v4's own components were; `blocked_ambiguous_boundary`'s own share (164/521 = 31.5%) and `blocked_continuation_pending`'s own share (309/521 = 59.3%, but only 51/263 distinct proposals — the rest were intermediate re-evaluations of still-growing chains, exactly the documented "cumulative count" behavior) both look like ordinary, healthy arbitration traffic, not a stalled system.
- **Suppressed-reason accounting is fully closed:** 0 (created) + 521 (suppressed) = 521 (proposals_observed) — no unaccounted-for loss anywhere in the pipeline's own bookkeeping.
- **Zero `blocked_shadow_mode`** across the entire session (confirmed both from the exhaustive `suppressed_reasons` breakdown, which never lists this category at all, and independently from the structured log's own zero-hit grep) — no recurrence of the stop-time authority race the accepted fix also closed.
- **`blocked_missing_evidence` is the actual loss mechanism**, and it is pervasive, not isolated: **48 of 263 distinct proposals (18.3%)** ended the session permanently blocked at this gate, spread across the *entire* session (earliest at offset 0.00min, latest at 104.31min) — not confined to the two exhaustive windows above. This rate is roughly **6.5× higher** than v5's own 10/361 (2.8%) suppressed-record rate, or roughly 6.6× on a matched per-distinct-proposal basis. This session's own activity pattern — many short, closely-spaced, sometimes-simultaneous proposals rather than v5's own more isolated single-subject visits — appears to churn the shared 128-entry evidence-byte cache materially faster.

### Forced-decision diagnostics

- The 20-minute (`maximum_component_pending_ms`) bounded-decision-horizon mechanism was **not observed to be the operative path** for either exhaustive-window loss: both windows' own oldest-flagged members had been pending well under 20 minutes (≈8.7 minutes and ≈5–6 minutes respectively) when their components resolved — meaning these were **ordinary, natural (non-forced) arbitration resolutions**, ranked by the unmodified confidence-first `_arbitration_key`, not the recency-first forced-decision path. This is a materially different, in some ways more basic, manifestation of the evidence-cache-exhaustion residual than the one the original cache-bound milestone's own comment describes (which discusses the forced/recency-ranked case specifically) — the same failure mode also reaches the *ordinary* arbitration path once a component simply has enough proposals/generations for the cache to churn past the eventual winner's own bytes.
- No case of `candidates_authority_exhausted: true` was observed; `candidate_authority_message` stayed `null` throughout — the session/hourly rate limits were never a factor (521 proposals, 0 admissions, nowhere near the 50/session or 20/hour caps).
- **Explicit failure-condition check (per this milestone's own §14):** "prolonged real sustained activity + candidates_created remains zero" — **this condition is met.** "Valid work only appears at stop" — not applicable (stop rescued nothing, because there was no cleanly-resolvable pending work left; see "Stop finalization"). "`blocked_shadow_mode` recurrence" — not met (zero occurrences). "Unbounded pending component" — not directly observed (components resolved, they just resolved to a loss one gate later). "Visit explosion from forced segmentation" — not met (0 Visits of any kind). One of five explicit conditions is unambiguously met; this is treated as a material regression signal, per the brief's own framing, distinct from — but not clearly less serious than — the original starvation defect for a real user's own experience of the product.

## Multi-subject tranche

Real, directly-confirmed simultaneous multi-subject activity **was** present this session — not manufactured, found naturally within the two exhaustive-review windows:

- 25.79min (Window 1): 2 birds simultaneously at/near the feeder.
- 27.93min (Window 1): plausibly 2 birds (medium confidence).
- 90.50min (Window 2): 2–3 birds simultaneously, an active feeding flurry.

**None of these moments ever reached a persisted candidate Visit** — every proposal touching these offsets ended `blocked_ambiguous_boundary` or `blocked_missing_evidence`, session-wide zero admissions. This means the specific mechanism `roadmap.md`'s "Multi-Subject Visit Assembly Phase 2" built (`concurrent_sibling_proposal_ids`, Event-reuse for genuinely-simultaneous distinct subjects sharing one Event as sibling Visits) **could not be exercised end-to-end this session either** — there was no admitted Visit of any kind to check for sibling grouping, correct evidence attribution, or cross-subject contamination. This is a genuine, real multi-subject *scene*, directly confirmed via the independent recorder — but, exactly like v5's own session, it did not translate into a testable multi-subject *product* outcome, this time for a different reason (nothing was admitted at all, rather than v5's "nothing happened to be concurrent among what *was* admitted"). Multi-subject Visit-grouping correctness remains untested end-to-end across both post-fix cohorts now, for two different reasons.

## Stop-finalization

Stop was called at session offset 6,397,546ms (18:22:39 wall-clock equivalent — actually 11:06:14 EDT), with 309 `blocked_continuation_pending` records still outstanding at that instant (a real, non-manufactured test of genuinely-pending work, matching this milestone's own §17 requirement).

- **Immediate stop response**: `state: "stopping"`, `stop_finalization_pending: true`, `stopped_reason: "user_stopped"` — the honest in-progress status the accepted fix's contract added, observed live. `candidates_created` at that instant: 0.
- **~23 seconds later**: `state: "stopped"`, `stopped_at: "2026-08-31T15:06:37.176187Z"`, `stop_finalization_pending` key **absent** (cleared, per the fix's own "clears... unconditionally once the thread truly completes" contract). `candidates_created`: **still 0** — unlike v5 (17→19), the finalize tick rescued nothing this time.
- **This is consistent with, not a regression of, the accepted contract**: root-cause tracing (above) shows nothing was left in a cleanly-resolvable "would have naturally admitted, just hadn't had its final tick yet" state at stop time — every real activity window's own fate (arbitration win followed by evidence-gate loss) had already been permanently decided earlier in the session, well before stop. There was nothing left for the finalize tick to legitimately rescue.
- **Two further repeated checks** (immediately after, and again after the full post-session analysis pass): `state: stopped`, `candidates_created: 0` (unchanged), `stopped_at` unchanged, `stop_finalization_pending` absent both times — stable, no flapping.
- `GET /api/streams/stream-b0d8cec9129d/visits` returns `[]` — confirms product-side truth matches the engine's own counters exactly.
- GPU returned to idle (0% utilization) after stop; Camera Node self-test/watchdog remained healthy; structured log shows a clean `session_stop` event with no error.

## Background/empty-evidence eligibility proof

**Not exercisable this session — an honest gap, not a fabricated proof.** The accepted `26edddf` geometry-corroboration eligibility fix runs inside `evaluate_identification_eligibility`, reached only after a candidate Visit has already been created and routed to species identification. Because zero candidate Visits were created this entire session, the species-identification/eligibility layer was never invoked at all — there is no real evidence this session of either a correct abstention or a regression at that specific gate. What **can** be stated: `git diff` against accepted `a09a91d` confirms `src/mockingbird/species/identification_eligibility.py` and `src/mockingbird/repository/product_repository.py` (the two files the accepted fix touched) are byte-for-byte unmodified this session — the fix's own code is present and unchanged, just untested live this session for lack of any Visit to test it against.

## Full funnel

For the two exhaustive-window activity segments (the only denominator units this session supports a confident funnel trace for):

1. **Monitoring coverage** — OK, ~99.4% (independent recorder span).
2. **Detector opportunity** — OK, MDv5a ran continuously at the confirmed 0.1 threshold; raw detections retained in the ledger throughout both windows.
3. **Detector localization** — OK, directly confirmed via full-resolution frames showing real, plausible bounding-box-scale bird presence at the feeder for every "bird visible" spot-check.
4. **Tracking** — OK, track generations recorded across both windows (35 distinct generations in Window 1 alone for the 21-proposal cluster).
5. **Proposal generation** — OK, 21 proposals (Window 1) and several more (Window 2) generated, correctly reflecting the real activity's own start/end timing.
6. **Arbitration/admission** — **OK as a decision-making process, but this is the first irreversible loss stage for the ordinary-ambiguous-boundary-losing members**: 20/21 members of the Window 1 component permanently lost here (correct, by design — "at most one Visit per cluster").
7. **Evidence capture/survival** — **This is the first irreversible loss stage for the single arbitration winner in each window**: the winning proposal (Window 1: `995e7d8127e5ea08c9f52dde`, offset 25.79min — the exact 2-bird moment) reached `create` eligibility per the authority gate's own 8-step order, then failed downstream at evidence-byte availability (`no_persistable_evidence_bytes`). Evidence *was* genuinely captured earlier in the session (raw detections/evidence candidates were observed continuously) — it was evicted from the bounded, insertion-order-only 128-entry cache before this specific proposal's own delayed turn arrived.
8. **Candidate persistence** — never reached (nothing to persist).
9–15. **Event/Visit assembly, user-visible Visit, useful evidence, species assistance, reviewability** — never reached, for any of the 521 proposals this session.

**First irreversible loss stage, precisely:** for 500/521 proposal-records (the permanently-`blocked_ambiguous_boundary` non-winners), stage 6 (arbitration), by design, correctly. For the 48 winners that reached evidence but failed, stage 7 (evidence capture/survival — specifically the shared cache's eviction policy having no awareness of which pending proposal still needs its bytes). **Not a detector miss, not a tracking miss, not an arbitration-timing miss** — every stage through arbitration behaved exactly as designed given real, confirmed input.

## Recall

**Exhaustive-denominator recall: 0/2 (0%).** Both exhaustively-reviewed real activity segments (Window 1, ≈22.9–29.7min, ≈6.8 real minutes with confirmed multi-subject moments; Window 2, ≈85.5–90.5min+, ≥5 real minutes with a confirmed multi-subject moment) were represented by **zero** admitted Visits.

- Denominator definition: bounded real activity segments (not invented discrete encounters, per this milestone's own honest-accounting instruction for continuous/overlapping activity), directly confirmed via full-resolution independent-recorder frames, distinguished from empty baseline frames immediately before/after each segment.
- Review density: every recorded frame in each window available via contact sheet; every ledger-flagged proposal-activity moment within each window individually pulled at full resolution (8 targeted frames per window).
- Analysis duration: 13.0 + 9.0 = 22.0 minutes of session time reviewed exhaustively, out of 106.63 total (20.6% of the session).
- Count: 2 denominator units. Numerator: 0. Misses: 2/2.
- Uncertainty: the internal encounter *count* within each bounded segment is deliberately not resolved (could be one bird repeatedly returning, or several) — this does not affect the recall computation itself (both segments are miss-classified as whole units regardless), but it does mean a finer-grained "N encounters missed" figure is not proposed, consistent with abstaining from boundaries this milestone cannot confidently resolve.
- **Supporting, non-exhaustive session-wide evidence is consistent with, not contradictory to, this figure**: 48/263 distinct proposals (18.3%) permanently failed at the evidence gate session-wide, spread across the full 0–104min span — the two exhaustively-reviewed windows are representative of, not an unlucky outlier within, the session's own broader pattern.
- This recall figure is **not proposed as a Gate A budget candidate** (see "Release-budget maturity," below) — a single session's own 0/2 result, while real and concerning, is too small a denominator and too close to the specific mechanism just found to generalize from directly.

## False Visits

**Undefined (0/0).** Zero Visits were created this session, so no false-Visit classification is possible — matching v4's own identical "undefined (0/0)" result in the cross-cohort table, for the same underlying reason (nothing was admitted to classify).

## Fragmentation / duplicates

**Trivially 0/0, not meaningfully evaluated.** With zero admitted Visits, there is no fragmentation or duplication to measure — this is not evidence that fragmentation/duplication correctness held under real ambiguous conditions this session, since nothing reached the stage where either could occur. Compare: v4's own pathological zero-admission state (also 0 Visits, also nothing to fragment/duplicate) versus v5's real, measured 0 confirmed fragmentation / 1 ambiguous pair among 19 real admissions — this session sits with v4's shape on this specific dimension, for the different, now-precisely-diagnosed reason above.

## Evidence

No product-persisted Visit evidence exists to review this session. The *independent* evidence reviewed (via the acceptance recorder, outside the product) is real, useful, and directly confirms genuine wildlife presence — see "Independent denominator," above — but none of it ever became product-visible evidence, since no Visit was created to attach it to. A useful-evidence-rate figure in this milestone's usual sense (fraction of *admitted Visits* whose evidence is useful) is not computable this session for lack of any admitted Visit.

## Coverage

- Intended session duration: 90–120 minutes, activity-dependent, per the governing brief.
- Actual duration: **106.63 minutes** (6,397.5 seconds), clean start/stop.
- Independent recorder coverage: 5,214 frames, ~4.1GB, first frame at offset 0ms, last at offset 6,359,321ms of 6,397,546ms total session span ⇒ **~99.4% temporal-span coverage**.
- Outages/reconnects: **zero** (`camera_connected: true` throughout the active session; zero ERROR/CRITICAL/WARNING log lines across the entire 164-line structured session log).
- Excluded periods: none.

## Latency

An improvement over every prior cohort's own disclosed "wholly unestablished" limitation, though narrower than a true capture-to-visible-Visit measurement (since nothing became visible this session to measure that against):

**Activity-end → final-arbitration-decision latency** (computed from the reconstructed full-session proposal-outcome ledger: each of the 263 distinct proposals' own `end_offset_ms` versus the wall-clock `decided_at` of its own final, permanent outcome, converted to session-relative offset):

- Sample count: 263 (every distinct proposal this session).
- Median: **127.4 seconds** (~2.1 minutes).
- p90: **545.4 seconds** (~9.1 minutes).
- p95: **679.5 seconds** (~11.3 minutes).
- Maximum: **912.8 seconds** (~15.2 minutes).
- Mean: 210.4 seconds (~3.5 minutes).

**Limitations, stated plainly:** this measures time from a proposal's own last constituent activity to when the *arbitration/authority* layer reached a final, permanent verdict on it — not capture→proposal, not admission→persistence, and specifically not capture→visible-Visit (undefined this session, since nothing became visible). It is a genuine, real, previously-uncollected data point about how long the ambiguous-boundary/continuation-pending resolution machinery actually takes under real activity, materially denser than any prior cohort's own latency evidence, but it does not by itself answer the Gate A "capture-to-visible-Visit" budget question. Species-enrichment latency: not measured (no candidate ever reached species identification).

## Persistence

`observation_candidate_visit_persistence_contention`: **zero occurrences** — checked both in the structured session log (zero hits, whole-log grep) and trivially implied by zero candidates ever reaching the persistence stage at all. Zero contention is valid evidence of a healthy write path, but carries less weight than in a cohort where real persistence actually occurred under load (v5: 19 real persists, 0 contention). No admitted-but-lost candidate was found (there were no admitted candidates to lose) — the release-critical "admitted-but-lost" failure mode specifically did not occur this session, distinct from and less severe than the "never admitted at all" finding that did occur.

## Species assistance

**Not exercised — zero eligible candidates existed.** BioCLIP-2 was never invoked this session (no candidate Visit ever reached species identification). No suggestion, no abstention, no confidently-wrong case — none of these outcomes occurred, for lack of any input to the species layer at all. This is a genuine measurement gap for this cohort, not a defect.

## Product behavior

`GET /api/streams/stream-b0d8cec9129d/visits`: `[]`. `GET /api/dashboard/summary`: for `stream-b0d8cec9129d`, `needs_review_visit_count: 0`, `latest_visit: null`, `camera_health.state: "stopped"` with an honest `"Monitoring is stopped by its saved local policy"` message — a correct, honest "nothing yet" surface, not a false all-clear, not a crash, not a stale/misleading state. (The dashboard's *global* "today" figures and the separate `stream-backyard-feeder` entries reflect only that stream's own pre-seeded demo data from 2026-01-15, unrelated to this session — confirmed by direct inspection, not conflated with real v6 results anywhere in this report.) Camera health, GPU, storage, and Camera Node self-test/watchdog all behaved as documented throughout and after stop (see "Coverage"/"Identity"). No other P0/P1 UI-level product defect found — the one substantive finding this session is the admission-pipeline defect covered under "Defects," not a UI-surface bug.

## Cross-cohort comparison

| Metric | 2026-08-19 (primary) | 2026-08-20 (cache-128) | 2026-08-29 (v4, pre-fix) | 2026-08-30 (v5, post-fix) | **2026-08-31 (v6, post-fix, this session)** |
|---|---|---|---|---|---|
| Duration | 92.2 min | 90m23s | 112.0 min | 106.6 min | **106.63 min** |
| Recorder coverage | 99.64% | full, no early stop | 99.78% | ~99.99% | **~99.4%** |
| Genuine encounters (denominator) | 22 (ceiling) | ≥9–10 | ≥2 broad windows + 1 mammal | ≥18 confirmed | **2 exhaustive activity segments confirmed (≥6.8min, ≥5min), both containing multi-subject moments; not exhaustively enumerated session-wide** |
| Visits created | 21 | 12 | 0 | 19 | **0** |
| End-to-end Visit recall | 68.2% (15/22) | not separately restated | 0% | very high (qualitative, targeted review) | **0% (0/2, exhaustive-window)** |
| False-Visit rate | 9.5% (2/21) | 2/12 likely-false | undefined (0/0) | 5.3% (1/19) | **undefined (0/0)** |
| Fragmentation | 2 encounters | not separately restated | not computable | 0 confirmed, ≤1 ambiguous | **not computable (0 Visits)** |
| Duplicates | 3 Visits | 0 confirmed | 0 (no Visits) | 0 | **0 (no Visits)** |
| First in-session admission | (not the question tested) | (not the question tested) | never (stuck at 0 the whole session) | ~25 seconds | **never (stuck at 0 the whole session)** |
| Stop rescued pending work | n/a | n/a | unresolved open question | yes — 17→19 | **no — 0→0 (nothing cleanly resolvable remained)** |
| `blocked_shadow_mode` | n/a (fix not built) | n/a (fix not built) | not separately isolated | 0 | **0** |
| `blocked_missing_evidence` rate | n/a | n/a | n/a (0 proposals reached it) | 10/361 = 2.8% | **48/263 distinct = 18.3% (or 48/521 records = 9.2%)** |
| Species suggestion availability | 18/18 = 100% | 12/12 = 100% | N/A (0 Visits) | 9/19 suggested, 10/19 abstain | **N/A (0 Visits, species layer never invoked)** |
| Persistence contention | n/a (fix not yet built) | n/a (fix not yet built) | 0 (unexercised) | 0 | **0 (unexercised)** |
| Latency evidence | none | none | none | species-enrichment only (2 samples) | **activity-end→arbitration-decision, n=263, median 127.4s, p90 545.4s, max 912.8s (still not capture→visible)** |
| Decision | B | A (cache-128 proof) | A (defect found & disclosed) | A (fix proven working) | **B (this session's own execution)** |

This session is **not** a clean repeat of v5's own result, and does not by itself establish that the sustained-activity fix "holds" for a second real cohort in the sense the milestone hoped to confirm — it is the **first real field measurement that the accepted fix's own already-disclosed evidence-cache residual is materially consequential**, not merely theoretical, under a real, sometimes-multi-subject activity pattern different in shape from either v4's or v5's own.

## Release-budget maturity

Evaluating each of the six Gate A numeric dimensions independently, honestly incorporating this session's own result:

### READY FOR FORMAL BUDGET REVIEW (unchanged from post-v5 reconciliation)
- **Minimum monitoring coverage ~99%**: this session's own 99.4% is consistent with all five real cohorts to date (99.4%–99.99%), no cohort falling meaningfully short. Still supported.

### MORE EVIDENCE REQUIRED (all six remaining dimensions; two now materially complicated, not merely "still pending")
- **Minimum useful-evidence rate (~85%, previously proposed READY FOR REVIEW after v5)**: **this session provides no data point at all** (0 admitted Visits, nothing to compute a useful-evidence rate over) — neither confirms nor refutes the ~85% candidate; the candidate itself is unaffected by this session but is not independently re-confirmed either. Still resting on exactly the two prior measurements (88.2%, 94.7%).
- **Minimum end-to-end Visit recall**: still not proposable. This session's own 0/2 exhaustive-window result is real, concerning evidence, but a single session's own worst-case figure would not be a defensible floor either — what's missing is a *fixed* version of the evidence-cache-exhaustion mechanism, then re-measurement, before recall converges into a budget-worthy range across cohorts.
- **Maximum false-Visit rate**: still undefined this session (0/0); no new evidence either way.
- **Maximum fragmentation/duplicate rate**: still not computable this session; no new evidence either way.
- **Maximum capture-to-visible-Visit latency**: still not established (this session's own latency evidence, real and denser than before, measures a different quantity — activity-end-to-arbitration-decision, not capture-to-visible — precisely because nothing became visible). What's missing: a session with real admissions *and* dedicated capture/proposal/admission/persistence/visibility timestamp instrumentation.
- **New, not previously named as its own dimension — evidence-cache-exhaustion rate under real sustained/multi-subject activity**: this session is the *first* real measurement (48/263 = 18.3% distinct-proposal rate, or 48/521 = 9.2% record rate) of a quantity the roadmap's own text already flagged as a real risk but had never actually measured under real field conditions before. Not yet a two-cohort-convergent figure (v5's own 2.8% and this session's 18.3% do not converge — they differ by a factor of ~6.5, plausibly explained by this session's own denser/more-simultaneous activity pattern, not yet independently confirmed). Recommend this becomes its own explicitly tracked Gate A dimension going forward, since it is now demonstrably capable of producing the same "zero admissions for a real sustained session" outcome the original starvation defect did.

## Candidate budgets

**None proposed this session, beyond monitoring coverage (unchanged, already proposed after v5).** This session's own defining result — 0 admissions from real, confirmed, sometimes-multi-subject activity — is not a basis for proposing any new numeric floor/ceiling; proposing one from a single session whose own headline finding is a real defect would repeat exactly the mistake `roadmap.md` already warns against (inventing a precise-sounding target from a still-narrow, now additionally atypical evidence base).

## Defects

### Primary field-observed defect: evidence-cache exhaustion permanently loses an arbitration winner with no runner-up fallback

- **Evidence preserved:** full session counterfactual ledger reconstructed losslessly (3 snapshots, 521 records, cross-verified against the session's own `recorded_count`), full structured session log, 16 full-resolution independent-recorder frames directly confirming real (often multi-subject) activity at the exact offsets of the lost proposals. Representative concrete instance: `visit-episode:995e7d8127e5ea08c9f52dde` (Window 1's own arbitration winner, real detected activity 25.79–25.94min, the exact offset independently confirmed to show 2 real birds) — `outcome: "blocked_missing_evidence"`, `reason: "no_persistable_evidence_bytes"`, permanent (not retryable), never revisited (comprehensively checked: none of the 21 proposals or 35 constituent track-generation ids from this component appear anywhere later in the session's own complete ledger).
- **First irreversible loss stage:** stage 7 (evidence capture/survival), specifically the shared, session-global, 128-entry, insertion-order-only evidence-byte cache (`_MAX_CACHED_BURST_BYTES`, `engine_runtime.py`) evicting a proposal's own bytes before its own (correctly, if sometimes belatedly, computed) arbitration turn arrives.
- **Root cause, precisely traced through source, not inferred:** `evaluate_candidate_authority`'s own documented 8-gate order (`candidate_visit_authority.py:517–582`) has no evidence-availability gate at all — ambiguity (gate 5) and continuation-pending (gate 6) are the only proposal-shape gates; a proposal that passes both (including via the `ambiguous_boundary_resolved=True` bypass a genuine arbitration win grants) reaches "create," and evidence-byte availability is checked **separately, downstream**, only after that. `blocked_missing_evidence` is not in `RETRYABLE_OUTCOMES` (`frozenset({"blocked_continuation_pending"})`, `candidate_visit_authority.py:438`) — once the sole arbitration winner for a resolved component fails there, its own proposal id (and every losing sibling's, already permanently blocked at the ambiguity gate) is marked permanently attempted. **No code path re-attempts arbitration for that component with the second-best member once the first winner fails downstream** — the component's real activity is lost in its entirety, not partially.
- **This is not a new defect class.** `engine_runtime.py`'s own `_MAX_CACHED_BURST_BYTES` history comment (written when the bound was raised 32→128, quoting real 2026-08-19 field evidence) already names almost exactly this mechanism and explicitly declines to fix it structurally: *"the proposal that actually escaped `blocked_ambiguous_boundary`... still permanently failed at evidence admission... not because no evidence was ever captured, but because this session-global cache, evicted purely by insertion count with no awareness of which pending proposal still needs which bytes, had already cycled past it... This remains a bound, not a structural fix... a pending-proposal-aware eviction policy would close that gap structurally, but is a materially larger change than this capacity bump and is left as a disclosed follow-up, not undertaken here."* v5's own report separately, abstractly named the same residual ("a pathologically evidence-dense, multi-hour single component could in principle still exhaust even the now-correctly-prioritized pool"). **v6 is the first real, concrete, session-wide measurement that this is not a rare edge case**: 48 distinct real, confirmed-activity-adjacent proposals lost this way in one session, at a materially higher rate (18.3% of distinct proposals) than v5's own 2.8%, spread across the whole session rather than clustered in one pathological moment, and demonstrated to occur on the *ordinary* (non-forced) arbitration path, not only the recency-forced path the original comment discusses.
- **Fix disposition, per this milestone's own §31 bar and the original cache-bound milestone's own explicit prior assessment: not attempted.** A "pending-proposal-aware eviction policy" (or an arbitration-level fallback to the runner-up when the chosen winner fails downstream) is real, credible future work, but is explicitly not bounded/obvious enough for a field-measurement session to attempt safely (the original milestone that built the current bound already assessed this exact change as "materially larger... left as a disclosed follow-up," a judgment this session's own evidence does not overturn, only sharpens the urgency of).
- **Not release-blocking for this milestone's own scope in the narrow sense of "did the sustained-activity starvation fix regress"** — it did not. It **is** release-relevant for Gate A's own broader "does the system produce useful Visits under real sustained activity" question, which this session answers unfavorably for its own conditions.

### Deploy-tooling defects (own-session, pre-field, bounded, fixed — zero product/perception code touched)

1. **`_run_powershell`'s stdout/stderr decoding crashed on non-UTF-8 bytes** (`scripts/deploy_windows_dev.py`), masking a real, unrelated `New-Item -ItemType Junction` failure behind `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 94`. Real Windows console-codepage (cp1252) text triggered this on a real deploy attempt. Root-caused, fixed (bytes-mode `subprocess.run` + `.decode(..., errors="replace")` at both of this file's two genuinely Windows-process-facing call sites), proven RED (via `git stash`, a `TypeError` confirming the pre-fix code also cannot handle this shape, though not byte-for-byte the same exception as the real-world case) → GREEN with a new hermetic regression test (`test_run_powershell_survives_non_utf8_output`, `tests/test_deploy_windows_dev.py`). Full file: 124/124 passed (123 pre-existing + 1 new). `ruff check`: clean on both touched files.
2. **The masked underlying failure was a genuine operator error, not a pre-existing product defect**: `--dev-root` was passed a raw Windows backslash path; this WSL-side script requires a WSL-mounted path (e.g. `/mnt/c/...`) since `--dev-root` is used directly as a real local filesystem path. The backslash string was silently treated as one POSIX path component, materializing a real, complete, ~4.7GB release+model+runtime tree inside the repository's own working directory rather than erroring clearly. Cleaned up (confirmed via `git status` that only the 7 preserved untracked files remained afterward — worktree safety re-verified); retried with the corrected path, which then deployed successfully. **Disclosed, not fixed**: `--dev-root` does not validate/reject a Windows-style path early with a clear error — a real, narrow, bounded future usability-hardening opportunity, correctly out of this milestone's own scope (pure tooling UX, not blocking once the input is corrected).

No other P0/P1 defect found.

## Remaining Gate A dependency

Precisely, in priority order:

1. **The evidence-cache-exhaustion/no-fallback mechanism this session concretely measured** is now the single most consequential open Gate A correctness question — materially more consequential than the roadmap's own prior abstract disclosure suggested. A bounded future milestone should: (a) decide between a pending-proposal-aware eviction policy and an arbitration-level runner-up fallback (or both); (b) fix it; (c) field-prove the fix the same way the original starvation fix was field-proved (a third real daylight session).
2. **A second post-fix daylight session that actually achieves in-session admissions** is still needed to convert v5's own single positive data point into a genuine cross-session convergent body of evidence for the four still-immature numeric budgets (recall, false-Visit rate, fragmentation/duplicate rate, capture-to-visible latency) — this session's own 0-admission result does not provide that convergent evidence and, if anything, sharpens how narrow the existing positive evidence base (v5 alone) still is.
3. **Multi-subject Visit-grouping correctness remains completely unexercised end-to-end** across two consecutive post-fix cohorts now (v5: no concurrent admission happened to occur; v6: nothing was admitted at all) — real, confirmed multi-subject scenes exist in this project's own field evidence (this session's own 25.79min and 90.50min moments), but a session that both admits *and* contains genuine concurrent siblings has still never been observed.
4. **Background/empty-evidence eligibility fix (`26edddf`)** remains field-unproven a second time (v5 provided the original real-world case; this session had no admitted Visit to test the fix against at all) — not urgent (the fix's own dedicated milestone already proved it thoroughly via reproducer + real-cohort benchmark validation), but still open as live-session confirmation.
5. **Species assistance and useful-evidence-rate** both remain resting on their pre-v6 evidence only; this session neither adds to nor detracts from either.

## Decision

**Classification B.**

This session's own **execution** meets a very high bar: representative real daylight conditions (directly, visually confirmed before committing, a genuinely different time-of-day window than any prior cohort); real, substantial, independently-confirmed wildlife activity including genuine simultaneous multi-subject moments (not manufactured); a methodologically honest independent denominator (two exhaustive full-resolution-reviewed windows, clearly distinguished from supporting session-wide evidence, with an explicit, disclosed correction of one of my own mid-session misreadings of the ledger data along the way); a real, previously-underestimated defect found and precisely root-caused all the way to specific source lines, not merely disclosed at the symptom level, with the exact real-world instance's own fate traced end-to-end and comprehensively confirmed permanent; zero cohort-integrity contamination (no tuning, no threshold changes, two small, bounded, well-tested, RED→GREEN-proven deploy-tooling fixes that touched zero product/perception code); an honest, undecorated stop-finalization result; and a fully-accounted funnel with no unexplained loss anywhere in the pipeline's own bookkeeping.

**But the milestone's own core, stated question — does the repaired sustained-activity pipeline replicate under a second representative cohort — cannot honestly be answered "yes."** `candidates_created` reached zero and stayed there for the entire 106.63-minute session, meeting one of this milestone's own five explicit failure conditions ("prolonged real sustained activity + candidates_created remains zero"). That the *specific* starvation mechanism v4 exposed and the accepted fix closed does not recur is real, positive, and precisely demonstrated — but a real user watching this session live would have seen the same practical outcome v4 produced: zero signal that any of the real, repeated, sometimes-multi-subject feeder activity this session's own independent recorder directly confirms ever happened. Per this milestone's own §35 acceptance bar, "post-fix admission behavior replicates" and "in-session admissions occur" are both explicit requirements for Classification A, and neither held this session. Rounding this up to A on the strength of the investigation's own quality, or by loose analogy to v4's own A-classified "found and disclosed a P0" precedent, would understate a real, consequential, session-wide result — this report instead classifies B: a valid, rigorous, non-contaminating field session that produced real, useable, well-evidenced Gate A findings, but did not achieve a positive replication result and does not, by itself, support closing or further trusting the sustained-activity fix's own real-world reliability without first addressing the evidence-cache mechanism this session concretely measured.

## Final response summary

- Classification: **B**
- Starting/report/reconciliation HEAD: `a09a91d` (starting); report HEAD includes two bounded, tested deploy-tooling fixes (`scripts/deploy_windows_dev.py`, `tests/test_deploy_windows_dev.py`) — zero product/perception/admission/Visit/evidence/classification code touched
- Schema: v58, unchanged
- Representative conditions: confirmed, mid-morning daylight, clear/calm, both feeders in view
- Duration: 106.63 minutes (intended 90–120; actual matches plan)
- Denominator methodology: 2 exhaustive full-resolution-reviewed windows (13.0min + 9.0min = 22.0min, 20.6% of session) + non-exhaustive whole-session sweep + full structured-log/ledger reconstruction
- Denominator size: 2 bounded real activity segments (≥6.8min, ≥5min), both containing confirmed simultaneous multi-subject moments
- Multi-subject evidence: real, confirmed (25.79min: 2 birds; 90.50min: 2–3 birds) — not manufactured, but never reached an admitted Visit
- Confirmed tracks: 593 track generations recorded session-wide (270 retained at final ledger snapshot)
- Proposals: 521 total, 263 distinct
- `candidates_created`: **0**
- First in-session admission: **none — never occurred**
- Visit recall: 0/2 exhaustive-window (0%); not proposed as a budget
- False-Visit rate: undefined (0/0)
- Fragmentation: not computable (0 Visits)
- Duplicates: 0 (0 Visits)
- Useful-evidence rate: not computable (0 Visits)
- Monitoring coverage: ~99.4%
- Latency distribution: activity-end→arbitration-decision, n=263, median 127.4s, p90 545.4s, p95 679.5s, max 912.8s (not capture→visible; that remains unmeasured)
- Forced-decision result: 20-minute horizon not observed to be the operative mechanism for either exhaustive-window loss (both resolved naturally, well under 20 minutes pending)
- Stop-finalization result: honest, correct, `stopping`→`stopped` cycle observed live; rescued 0 (nothing cleanly resolvable remained, consistent with root cause, not a regression)
- Background/empty-evidence eligibility result: not exercisable this session (0 admitted Visits); fix's own code confirmed unmodified
- Persistence result: 0 contention (unexercised — nothing reached persistence)
- Species-assistance result: not exercised (0 eligible candidates)
- Product findings: dashboard/Visits surfaces correctly, honestly show "nothing yet" for this stream; no UI-level defect found
- Defects: (1) evidence-cache exhaustion permanently loses an arbitration winner with no runner-up fallback — real, precisely root-caused, concrete session-wide measurement of an already-disclosed residual, not fixed (correctly out of scope), disclosed with a full defect contract; (2) two bounded, fixed, own-session deploy-tooling defects (non-UTF-8 PowerShell decode crash; `--dev-root` WSL-path footgun disclosed not fixed)
- Cross-cohort comparison: see table above — this session's `candidates_created`/recall/stop-rescue results pattern with v4's own pre-fix shape, for a materially different, now precisely-diagnosed reason
- Budget maturity: monitoring coverage remains READY FOR FORMAL BUDGET REVIEW; useful-evidence-rate candidate neither confirmed nor refuted this session; recall/false-Visit/fragmentation/latency remain MORE EVIDENCE REQUIRED, now joined by a new explicitly-named evidence-cache-exhaustion-rate dimension
- Candidate budget proposals: none new this session
- Gate A evidence sufficiency for formal closure review: **not sufficient** — this session adds a significant new open correctness question rather than closing existing ones
- Remaining dependency: fix + re-prove the evidence-cache-exhaustion mechanism; obtain a session with real in-session admissions *and* genuine concurrent multi-subject siblings; re-prove background/empty-evidence eligibility live a second time
- Current authorization: returns to **NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**
- Ready/not ready for ChatGPT acceptance review: **ready for review** (as a Classification B field session with a real, well-evidenced, actionable finding) — **not** a basis for declaring Gate A closer to closed; if anything, this session reopens a specific, previously-underweighted correctness question Gate A must resolve before formal budget closure.
