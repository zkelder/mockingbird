# Representative Daylight Gate A Field Acceptance v10 — Admission-Precision Re-Proof & Gate A Closure Tranche

## Identity

- Repository accepted HEAD at session start: `b7e9724` (full `b7e972440b48c63b7a7161cf2ea1ee70859b4676`), the reconciliation commit accepting Field-Acceptance Instance Lifecycle & Storage Safety v1. Schema v58.
- Deployed Host build verified via `GET /api/product/instance`: `git_commit: b7e972440b48c63b7a7161cf2ea1ee70859b4676`, `app_version: 0.1.0`, `build_id: 9f7b97b05aa45a8e` — exact match, not inferred.
- Disposable dev-root: `%LOCALAPPDATA%\MockingBirdFieldAcceptanceV10`, a fresh instance created specifically for this milestone (not a reuse of any prior cohort's root).
- Field-acceptance instance lifecycle manifest: `init`-ed at `2026-09-02T11:39:39.523177Z`, `lifecycle_state: active`, `created_by_commit` matches accepted HEAD exactly. This is the first real field session to use the newly-accepted lifecycle tool end-to-end.
- Field Acceptance Operator credential: `field-acceptance-0d817e5bad064b69`, 4h TTL, minted via `POST /api/admin/field-acceptance-credentials` after bootstrapping a disposable local Administrator (`field-acceptance-v10`) via `POST /api/setup/administrator` with a locally-generated, never-reused, never-user-supplied password (per standing policy: never ask the user for live credentials).
- Reference Camera Node: `node-76ec8e53ae586dd0` ("Pi Camera Node"), camera `picamera2-camera-0` (1920×1080 monitoring profile). Paired fresh for this session.
- Source/Stream via `POST /api/camera-setup/complete`: `source-a7339d605dca` / `stream-a7339d605dca` ("Reference Camera Node"), one full-frame "Yard" zone (zones are not a crop boundary per doctrine; created only to satisfy the setup wizard's ≥1-zone requirement).

### Operational note: Camera Node pairing-slot contention (disclosed, user-authorized)

The reference Camera Node allows exactly one live paired credential at a time (`_PairingState`, `src/mockingbird_node/app.py`). At session setup, that slot was held by the now-dormant `MockingBirdFieldAcceptanceV9` instance (confirmed via matching `boot_id` and a `source_provider_configurations.updated_at` timestamp landing within seconds of v9's own recorded session-start time) — a stale hold with no live consumer: v9's evidence is already durably captured in its accepted report, and the other running instance found at session start (`MockingBirdDev`, holding an orphaned, non-branch-reachable commit `6045228`) was independently confirmed idle since 2026-08-18 (recorder untouched since 2026-08-21, database untouched since 2026-08-29) and was cleanly stopped via the accepted `deploy_windows_dev.py --stop`, which was also required to free the hard-coded port 8000 the packaged launcher requires (confirmed live: it takes no arguments and cannot bind elsewhere).

Freeing the Node's pairing slot for v10 required resetting its persisted `pairing.json` over SSH. The Claude Code auto-mode permission classifier correctly declined this on the first attempt (and a subsequent non-destructive-backup-only attempt) as a consequential remote-infrastructure action; the user was asked explicitly via `AskUserQuestion` and chose "Reset Node pairing now." Executed exactly as authorized: back up `pairing.json` → stop `mockingbird-camera-node.service` → remove `pairing.json` → restart service → capture the fresh pairing code from `journalctl` → pair the new v10 instance within the code's 10-minute TTL. Confirmed via `boot_id` continuity (`8f6afbda-bb62-414d-9762-4abb65c8d585`, unchanged across the reset) that this was a credential-state reset only, never a physical device change. The backup (`pairing.json.pre-v10-reset.bak`) is retained on the Node for audit purposes; the practical effect is that any Host still holding the old (v9) credential would need to re-pair to reconnect live — none currently does.

## Conditions

- Local time at session start: **2026-09-02 07:39:59 EDT** (`2026-09-02T11:39:59.933647Z`), stop at **09:11:12 EDT** (`2026-09-02T13:11:12.926088Z`). Duration: **90.2 minutes**.
- A real current frame was pulled directly from the Camera Node (`CameraNodeClient.snapshot`) before committing to the session: bright, real morning daylight (sun low, visible through light haze), good visibility, dry ground, ordinary residential-yard scene, both the seed (tube) feeder and the red hummingbird feeder clearly visible in frame.
- Reference Camera Node health: `status: available`, `self_test: passed`, `camera_available: true`, watchdog healthy, 0 consecutive probe failures throughout.
- Host/GPU health: RTX 4060 Ti, CUDA available, `CUDAExecutionProvider` selected, engine load 10.0s.
- Storage: 26.6GB free at deploy time, 15.6GB free at report time (`storage_health_tier` moved from `getting_low` to `low` over the session — disclosed below, not treated as a failure since it stayed comfortably above the 1GB/200MB hard thresholds throughout).
- Wind/foliage: not independently instrumented; recorder frames across the session show a stationary camera and generally calm foliage, with no session-invalidating weather change observed.

## Frozen configuration

Recorded before the session; confirmed unchanged throughout via the stop-time status snapshot (identical `model` block to the start-time snapshot):

- Detector: MDv5a ONNX (`md-v5a`, `MDv5a.0.1-onnx-opset18`), `score_threshold: 0.1`, `nms_iou_threshold: 0.45`, `nms_max_detections: 300`, fingerprint `b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc`.
- Provider: `frame-driven-onnx-cuda` / `onnx-cuda`, GPU (CUDA), not CPU fallback.
- Tracker `strong_detection_threshold`: 0.70.
- Hard-negative admission rule (`candidate_quality_gate.py`): `reject_insufficient_detector_corroboration` — rejects only when `strong_detection_count == 0` AND `detection_count <= 2 * constituent_generation_count + 1` AND `max_consecutive_detector_confirmed_frames <= 1`.
- Evidence cache: `_MAX_CACHED_BURST_BYTES = 128`, `_MAX_CACHED_SAME_FRAME_BYTES = 128`. Pending protection: `_MAX_PROTECTED_EVIDENCE_IDS = 64`.
- Candidate authority rate limits (per-Stream): `max_candidates_per_session: 50`, `max_candidates_per_hour: 20`.
- Species: BioCLIP-2 (`adapter_id=bioclip_2`) + Identification Eligibility/Abstention v1.
- RTT calibration: `clock_calibration.estimate_rtt_clock_calibration`, unchanged.
- Acceptance recorder (independent denominator): `sample_interval_ms=1000`, `max_frames=6500`, `max_total_bytes=5,000,000,000` (matching v9's denser ~1s cadence for methodological comparability).

No tuning performed during the cohort.

## Compatibility / storage preflight

- Storage preflight (`field_acceptance_instance_lifecycle.py preflight`): `free_bytes: 26,634,301,440`; `required_bytes: 6,000,000,000` (5GB recorder ceiling + 1GB reserve); `sufficient: true`; `storage_health_tier: getting_low`; `known_reclaimable_instances: []` (see Defects — real reclaimable instances exist but predate the manifest tool and are structurally invisible to it).
- Compatibility (`scripts/check_camera_node_compatibility.py`, run via the deployed instance's own bundled interpreter):
  - `ordinary_monitoring` profile: `state: compatible`, `host_git_commit` exact match, `node_reachable: true`.
  - `field_acceptance` profile: `state: compatible`, all four required capabilities (`health_protocol`, `expected_camera_available`, `rtt_timestamp_fields`, `bounded_rtt_clock_calibration`) observed, `missing_capabilities: []`, `camera_available: true`, `version_skew_detected: false`.

Both required gates (§4: `field-acceptance compatibility == compatible`, `RTT calibration == calibrated`) satisfied before Observation start.

## RTT calibration

Pre-session standalone probe: `state: calibrated`, 4/5 valid samples, `offset_ms: 7.08 [0.81, 13.36]`, `rtt_ms: 17.19`, `node_processing_ms: 3.96`, `clock_jump_detected: false`.

In-session (merged across periodic full-window snapshots — see "Independent denominator" for why periodic snapshotting was necessary): **445 distinct RTT-bounded calibration batches**, **440 `calibrated` (98.9%)**, 5 `insufficient_samples` (1.1%), **0 `inconsistent_samples`, 0 clock jumps** across the full 90.2-minute session. RTT distribution across valid batches: median **39.9ms**, mean 48.9ms, max 246.5ms (one transient network spike, still comfortably under the 1000ms acceptance ceiling). Median offset uncertainty (interval half-width): 10.8ms. This is a further convergent, healthy data point alongside v9's own 447/460 = 97.2% calibrated rate — the RTT protocol continues to work reliably in the field.

## True latency

Computed using the same additive decomposition v9 introduced (T0 = first constituent generation's `start_captured_at`, RTT-offset-normalized; "tail" = last capture → `decided_at`), against all 11 admitted Visits:

| Visit | Encounter span | Tail latency | Full T0→T5 |
|---|---|---|---|
| candidate-003 | 19.8s | 56.7s | 76.5s |
| candidate-004 | 27.4s | 57.9s | 85.2s |
| candidate-005 | 48.8s | 134.5s | 183.3s |
| candidate-006 | 53.4s | 50.5s | 103.9s |
| candidate-007 | 29.4s | 50.0s | 79.4s |
| candidate-008 | 65.2s | 49.6s | 114.8s |
| candidate-009 | 51.6s | 149.8s | 201.5s |
| candidate-010 | 61.0s | **681.3s** | **742.3s** |
| candidate-011 | 18.1s | 51.1s | 69.3s |
| candidate-012 | 11.3s | 63.4s | 74.7s |
| candidate-013 | 61.8s | 76.8s | 138.7s |

**Full T0→T5: median 103.9s, p90 183.3s** (n=11) — closely matching v9's own median 111.8s / p90 173.9s. **Tail latency: median 57.9s** — matching v9's own tightly-clustered ~48-60s tail-latency finding for 10 of 11 Visits. **The accepted RTT-normalized latency behavior remains stable, a second real cohort confirming it.**

One disclosed outlier: **candidate-010's tail latency is 681.3s (~11.4 minutes)**, far outside the otherwise-tight cluster. Root cause, traced not assumed: candidate-010's own track ends at session offset 3384378ms; a separate, visually-confirmed genuine bird encounter at the same feeder begins only ~350s later (offset 3733985ms, see "Recall," below) and itself does not resolve until offset 3884687ms. Candidate-010's own finalization (`decided_at` 12:48:16Z) lands after that subsequent encounter fully resolves — consistent with the accepted Visit-Continuity quiet-period/episode-boundary design extending one Visit's own decision horizon while nearby, potentially-related activity is still being arbitrated, not a new defect. This is the same *mechanism* v9's report already named as the deliberate cost of avoiding fragmentation; v10 is the first cohort to observe it stretch into minutes rather than seconds, because v10 happened to have two temporally-close encounters at the same physical location.

## Independent denominator

Acceptance recorder active throughout: `sample_interval_ms=1000`, writing to `{dev_root}/acceptance-recordings/stream-a7339d605dca/20260902T113959Z/`. **4,296 frames** captured, first at offset 0ms, last at offset 5,409,601ms against a session span of 5,410,199ms — **99.99% temporal-span coverage**, no truncation (well under both the 6,500-frame and 5GB configured ceilings).

**Methodological note, disclosed as a new finding for future cohorts:** the counterfactual ledger's own age-eviction bound (`CounterfactualRetentionConfig.max_age_ms = 3,600,000`, i.e. 60 minutes) is *shorter* than this milestone's own 75–100 minute target session length. A single end-of-session read would have silently lost the earliest ~46 minutes of `raw_detections`/`track_generations`/`proposal_outcomes` — confirmed directly: the final read showed 6,465 of 13,965 raw detections (46.3%) and 89 of 196 proposal-outcome events (45.4%) already evicted. This was worked around by snapshotting the full window (`start_offset_ms=0`) every 12 minutes throughout the session (well under the 60-minute bound, guaranteeing overlap) and merging post-hoc by record ID — recovering **13,965/13,965 raw detections and 278/278 track generations exactly (0% loss)**, and all distinct proposals reachable through the merged history. This is new guidance for any future session expected to run past ~50 minutes, not a defect in an already-accepted contract.

**Denominator construction** used two methods in combination, deliberately not derived solely from the product's own Visit list (per the standing rule):
1. A full recorder-frame contact-sheet sweep (34 frames at 15s cadence, before consulting the Visit list) of two windows: a late high-activity window (offset 4,900,000–5,410,000ms) and an earlier sparser window (1,140,000–1,650,000ms) — confirmed overall scene/camera stability and no missed large-scale activity at the resolution a wide contact sheet supports.
2. Direct visual + numerical (bounding-box trajectory) inspection of **every one of the 90 distinct proposals** the merged counterfactual ledger recorded this session (complete, not sampled, since the raw/track ledgers were recovered at 100%) — the same finer-grained, structurally-complete record the acceptance-recorder tee exists to make possible, cross-checked against real recorder-frame crops for every proposal with `max_confidence` or `constituent_generation_count` high enough to plausibly be a genuine encounter (all 11 admitted, all 3 hard-negative rejections, and the 4 highest-confidence `blocked_ambiguous_boundary` proposals out of 20).

## Recall

**Genuine denominator units identified** (temporal bounds, subject, confirmation basis):

| # | Offset window | Subject | Confirmation | Represented as |
|---|---|---|---|---|
| 1 | 328,006–372,278ms | Small pale bird (mockingbird), distant sapling | Visual (2 crops, distinct plumage) + species guess `northern_mockingbird` | **Fragmented** into candidate-003 + candidate-004 (windows overlap by 2.9s — see Fragmentation) |
| 2 | 1,128,484–1,181,803ms | Same sapling, same species profile | Visual | candidate-006 (represented) |
| 3 | 3,323,434–3,384,378ms | House finch at tube feeder | Visual (clear bird in 2 crops) + `house_finch` | candidate-010 (represented) |
| 4 | 3,733,985–3,884,687ms | Bird at tube feeder (same location as #3) | Visual (clear bird in 2 crops) | **Not represented** — resolved `blocked_ambiguous_boundary`, no Visit created |
| 5 | 5,077,523–5,095,389ms | Dog on leash + walker on the road | Visual (wide-context frame) + raw-detection trajectory (continuous left-to-right movement, ~0.03→0.49 x, paired "person" track) | candidate-011 (represented, but real-non-wildlife — see "Weak-real-bird preservation") |
| 6 | 5,245,438–5,357,889ms | House finch at tube feeder (one sustained or two closely-spaced visits) | Visual (clear bird in 2 crops) + `house_finch` ×2 | candidate-012 + candidate-013 (both represented) |

**Reviewable genuine bird-or-wildlife denominator units: 5** (units 1–4, 6; unit 5 is a real animal but not wildlife-subject, tracked separately, not double-counted here). **Represented: 4/5 = 80%** (units 1, 2, 3, 6). **Missed: 1/5** (unit 4).

The one miss (unit 4) is **not attributable to the new hard-negative admission rule** — it resolved via the pre-existing `blocked_ambiguous_boundary` arbitration mechanism, unrelated to `reject_insufficient_detector_corroboration`. It is a genuine, disclosed recall gap worth naming precisely: a real, visually-clear bird visit at the tube feeder, occurring ~5.8 minutes after an already-admitted Visit at the same physical location, never became its own Visit.

This is a bounded, targeted-window denominator (two prospectively-chosen windows plus complete coverage of every proposal the ledger ever recorded), not an exhaustive frame-by-frame review of the full 90-minute session — smaller and more tightly reasoned than v9's own two-window denominator (6 genuine units), and should be read with the same conservative caveat v9's own report used: this is one more real, hard-won data point, not a session large enough to move the standing "MORE EVIDENCE REQUIRED" recall-budget classification on its own.

## Admission-precision field proof

All 11 admitted Visits and all 3 `reject_insufficient_detector_corroboration` rejections were directly reviewed: visually (padded, 6×-upscaled crops from the acceptance-recorder's own frames, at each proposal's actual raw-detection offsets, not arbitrary samples) and numerically (full raw-detection bounding-box trajectory across each proposal's window).

**The new rule fired correctly against its own target signature 3 times**, each with the exact profile the accepted fix's own report described (single generation, `detection_count == 3` at the scaled floor for `constituent_generation_count == 1`, `strong_detection_count == 0`, `terminal_reason: maximum_unsupported_duration`):

1. Offset 3,201,232–3,209,645ms, bbox center ≈(0.198, 0.694) — **visually confirmed empty**: a hanging leaf cluster over grass/driveway, matching v8's own "Location A" foliage-cluster coordinates (0.19–0.22, 0.67–0.72) almost exactly.
2. Offset 3,317,229–3,329,204ms, bbox center ≈(0.50, 0.41) — a low-confidence (max 0.433), monotonically-fading detection near a shepherd's-hook garden ornament; a genuinely-real, much stronger, sustained bird sequence begins at a nearby-but-distinct location only ~1s later (becoming candidate-010). Classified **likely correctly rejected** (confidence-decay pattern argues against a real animal sitting motionless that long) but disclosed as the least visually-certain of the three, not overclaimed.
3. Offset 4,669,221–4,680,550ms, bbox center ≈(0.468, 0.53) — **visually confirmed empty**: the blue tube feeder itself, no bird, at the *exact* recurring weak-signal location analyzed in depth below.

## Hard-negative recurrence

**The known Location A (foliage) hard-negative recurred and was correctly rejected once** (rejection #1, above) — a genuine field confirmation of the fix's own target case.

**A recurring hard-negative location was also identified at the blue tube feeder itself** (bbox center ≈(0.468, 0.53), a *different* location from v9's own "Location B" sun-glint coordinates (0.467, 0.530 — coincidentally close in x but not the same physical feature; v9's Location B was never independently re-confirmed this session). Across the full session this location produced:
- 1 correctly-rejected proposal via the new rule (rejection #3, above);
- **4 admitted Visits (candidates 005, 007, 008, and — at a matching location — candidate-009's own "Location A" recurrence) that direct visual inspection (all sampled frames, including each proposal's own peak-confidence moment) confirms show no bird**, combined with a numerical signature (bbox invariant to within 1–2 pixels across 9–33 repeated detections spanning up to 51 seconds, confidence fluctuating noisily between 0.10–0.73 with no directional trend) that is not physically consistent with a live animal;
- **15 of 20 `blocked_ambiguous_boundary` proposals** (spanning offsets 634,062–4,271,408ms — nearly the entire session) at the same bbox, none ever reaching `strong`, confirming this is a near-continuous low-level background confusor, not an intermittent one.

**This is the concrete negative field result this milestone's own governing dependency explicitly asked to be checked for**, and it reproduces: *"a hypothetical real bird at the exact same corroboration floor as the traced false cluster is not distinguishable by corroboration structure alone"* (Hard-Negative Visit Admission Precision v1's own disclosed residual). The fix closes the exact bare-minimum, single-generation shape it targeted (3/3 for-cause rejections this session, one at each of two distinct hard-negative locations) — but the **same underlying confusor defeats the rule's own count-based axis** whenever a proposal accumulates enough *individually-insufficient* low-confidence detections within one continuation window to clear `2 × constituent_generation_count + 1` without ever going strong. Candidates 005/007/008/009 each did exactly that. **Desired field result was: known hard-negative chain → `reject_insufficient_detector_corroboration` → no user-visible Visit. That result held for the classic single-generation shape 3/3 times, and failed to hold for the count-accumulation shape 4/8 times** (4 admitted vs. 1 rejected vs. 15 correctly-never-admitted-but-not-cleanly-resolved-either at the tube-feeder location alone; 1 admitted vs. 1 rejected at the foliage location).

## Weak-real-bird preservation

**Preserved, with one clean example:** candidates 003/004/006 — a small, pale, distant bird (matching `northern_mockingbird`, visually confirmed perched atop a sparse sapling well across the driveway from the camera) — never reached `strong_detection_count > 0` (max confidence 0.384/0.265/0.248) and was admitted purely via count-based corroboration (13–18 detections per proposal). This is exactly the "small/distant subject" and "low confidence" weak-real-bird class the fix's own report named as a positive control, now independently reproduced with a genuinely new, real encounter.

**Determined whether the new admission rule rejected any genuine denominator unit: no.** All three `reject_insufficient_detector_corroboration` rejections were independently classified false or likely-false above; none corresponds to a visually-confirmed genuine bird. The one real recall miss found this session (the tube-feeder bird at offset 3,733,985–3,884,687ms) was rejected by the *pre-existing* `blocked_ambiguous_boundary` mechanism, not by this milestone's own new rule — traced explicitly, not assumed, by confirming its own `outcome` field and cross-checking that `reject_insufficient_detector_corroboration`'s own three conditions do not appear anywhere in its resolution history. **No recall loss is hidden behind the precision result** — see "False Visits," below, for the concrete precision cost that recall preservation came alongside.

## False Visits

Direct review of every admitted Visit (11/11, 100%), classified with visual + numerical evidence as described above:

| Classification | Count | Visits |
|---|---|---|
| Confirmed real wildlife | **6** | 003, 004, 006, 010, 012, 013 |
| Confirmed false/background (admitted) | **4** | 005, 007, 008, 009 |
| Real animal, non-wildlife subject | **1** | 011 (dog on leash + walker) |
| Ambiguous | 0 | — |

**Primary false-Visit rate (confirmed false / total admitted): 4/11 = 36.4%.** Treating candidate-011 (a real, correctly-detected, but non-wildlife-target animal) as a separate category rather than folding it into either bucket, per product doctrine's own explicit "Cat crossed yard"/"Squirrel entered feeder zone" precedent for legitimate non-bird Activity Sessions. If instead conservatively counted as not-useful-wildlife-evidence, the rate rises to 5/11 = 45.5%.

**This is materially worse than both v8 (22.2%) and v9 (20.0%), not materially better** — the opposite of this milestone's own primary governing question. All four confirmed-false admissions trace to the single recurring tube-feeder/foliage confusor class analyzed in "Hard-negative recurrence," above, not to four independent causes — a narrow, well-understood, precisely-located root cause, not a diffuse regression.

## Useful evidence

Using the same classification: clearly useful (6 confirmed-real Visits with a real, identifiable subject) / background-empty (4 confirmed-false Visits) / wrong-subject (1, the dog). **Strict useful-evidence rate: 6/11 = 54.5%** — well below v9's own 76.0% (already below the previously-withdrawn ~85% candidate) and below every prior cohort in the comparison table.

## Species / Gate B

**No confident wrong species label appeared on any confirmed-false or wrong-subject Visit** — checked directly via `GET /api/visits/{id}` for all 11 admitted Visits: candidates 005, 007, 008, 009 (confirmed false) and 011 (the dog) all show `species_guess: null`. Only the 6 confirmed-real Visits received a species guess (`northern_mockingbird` for 004; `house_finch` for 010, 012, 013; null for 003/006 despite being visually the same subject as 004 — consistent with per-frame eligibility gating, not a defect).

**The v9 field-proven failure class — false Visit → confident wrong species — does not recur.** Gate B's own Identification Eligibility/Abstention mechanism is holding correctly even in exactly the cases where Gate A's admission layer let a false Visit through. This is a genuine, disclosed positive result standing alongside the false-Visit-rate finding above: the admission-precision regression is real, but it has not produced a new Gate-B-hard-negative-species-escalation instance.

## Fragmentation

**One real, confirmed fragmentation case**, breaking the "0% fragmentation, converged across 6–7 cohorts" streak: candidates 003 and 004 — same location (bbox ≈(0.85, 0.49–0.56)), same visual subject (matching pale/mockingbird profile), **temporally overlapping windows** (328,006–347,835ms and 344,947–372,278ms, a 2,888ms overlap) with distinct constituent generations — one continuous real bird presence, interrupted by a brief tracker loss, resolved as two separate admitted Visits instead of one continuous one.

Denominator units reviewed for fragmentation (the 5 genuine wildlife/animal units from "Recall," above): 1 fragmented (unit 1 → candidates 003+004), 4 correctly represented as a single Visit each (unit 2 → 006; unit 3 → 010; unit 6 → 012+013, judged correctly-represented as two Visits given a genuine ~5.8-minute observed gap in raw detections between them rather than a continuous interrupted presence — see raw-detection data). **Fragmentation rate: 1/5 = 20%**, a real, disclosed departure from the prior convergent ~0% result, on a single-cohort, small-denominator basis.

## Duplicates

**0/11 admitted Visits share any constituent generation ID** (checked directly, not inferred) — the 6th/7th convergent 0%-duplicate-rate cohort, unchanged and reaffirmed.

## Multi-subject

**No genuinely simultaneous multi-bird activity occurred this session** — today's activity was sparser than v5–v9's own cohorts (11 admitted vs. 19–27), and no window reviewed showed two distinct bird subjects in the same frame at the same time. One incidental concurrent-but-different-class pairing was observed and traced (a "person" track and an "animal" track — the dog — moving in parallel, candidate-011's own window), confirming the multi-track/multi-class machinery itself continues to work correctly, but this is not wildlife multi-subject evidence. **Target not met this session** — a real, disclosed gap in the standing Gate A dependency list, unrelated to this milestone's own precision work.

## blocked_missing_evidence

Using the same distinct-proposal semantics as prior cohorts: **6 of 90 distinct proposals (6.7%)** — better than v6 (18.3%), v7 (9.4%), v8 (9.9%), and v9 (8.9%). A further convergent, healthy data point; no regression, no reason to reopen the preservation/cache milestone.

## Fallback

`fallback_attempted_count: 3`, `fallback_admitted_count: 2`, `fallback_exhausted_count: 1` (from the final session status). The same-component fallback path activated a modest 3 times this session and behaved as designed (2/3 successfully rescued evidence into an admission; 1/3 correctly exhausted rather than looping).

## Rate limiting

**Never activated.** `candidate_authority_exhausted: false` throughout; 11 admissions is well under both `max_candidates_per_session: 50` and `max_candidates_per_hour: 20` for a 90-minute session. No rate-limit/admission-rule recall interaction to separate out this session.

## Persistence

`analysis_stream_failure_class: "timeout"`, `analysis_stream_consecutive_failures: 1`, `analysis_stream_reconnect_recoveries: 2` — the `AnalysisStreamRetryPolicy` (max 6) activated twice during the session and recovered cleanly both times, well within its accepted bound; never approached exhaustion. No `observation_candidate_visit_persistence_contention` or unexpected ERROR/CRITICAL observed in the session's own status/counterfactual surfaces.

## Stop-finalization

`POST .../observation/stop` returned `stop_finalization_pending: true` immediately, then resolved cleanly: a follow-up status check (~6 seconds later) showed `state: stopped`, `finalization_pending` cleared, and **one additional candidate rescued** (`candidates_created` 10→11, `visit-observation-candidate-011` — the dog — being the one finalized after stop) plus 4 additional proposals resolved into `suppressed` outcomes. This is the accepted stop-finalization mechanism (v5's own fix) working correctly in the wild a second time, on a different Stream/session.

## Monitoring / recorder coverage

**99.99% temporal-span coverage** (4,296 frames, first-to-last offset spanning 5,409,601 of 5,410,199 session-ms) — a further convergent data point inside the existing ~99% candidate band, and higher than v9's own 97.95%.

## Product behavior

Spot-checked via the real API (not a full UI walkthrough, given the volume of precision/recall work this session's own governing brief prioritized): `GET /api/review-queue` correctly lists the most recent admitted Visit (`review-queue-visit-observation-candidate-013`) with a sensible title/type; `GET /api/camera-health` correctly reports the Stream as `stopped` post-session with an accurate message. `GET /api/product/instance` confirmed exact build identity (see "Identity"). No live UI screenshot pass was performed this session; the previously-accepted review-provenance 500 fix (`ReviewProvenanceError` → HTTP 400) was not independently re-exercised, since no code on that path changed since its own acceptance and no review-label mutation occurred this session — disclosed as untested rather than assumed passing.

## Cross-cohort comparison

| Metric | v5 | v7 | v8 | v9 | **v10** |
|---|---|---|---|---|---|
| False-Visit rate | 5.3% | 4.0% | 22.2% | 20.0% | **36.4%** (confirmed false only) |
| Useful-evidence rate | 94.7% | 96.0% | 77.8% | 76.0% | **54.5%** |
| Recall | qualitative, no missed encounter (targeted review) | 100% (2 exhaustive windows) | 100% (1 exhaustive window) | 83.3% (Window 1 only) | **80%** (4/5 genuine wildlife units) |
| Fragmentation | 0% confirmed | 0% (reanalyzed) | 0% | 0% | **20%** (1/5 units) |
| Duplicates | 0% | 0% | 0% | 0% | **0%** |
| blocked_missing_evidence | not reported | 9.4% | 9.9% | 8.9% | **6.7%** |
| RTT-normalized latency (T0→T5 median) | n/a (pre-RTT) | n/a (pre-RTT) | invalid (Node predated protocol) | 111.8s | **103.9s** |
| Monitoring coverage | ~99.6-99.99% (band) | 99.989% | shortfall (self-inflicted byte budget) | 97.95% | **99.99%** |
| Multi-subject evidence | none this cohort | 2 real pairs | none confirmed | 2 birds, 1 frame | **none this cohort** |

**Primary question: did v10 materially exit the v8/v9 ~20% false-Visit regime? No — it materially worsened within the same underlying failure class.** The hard-negative fix demonstrably works against the exact bare-minimum shape it targeted (3/3 clean rejections, including a precise re-confirmation of v8's own foliage location), but the same physical confusor location defeated the fix's count-based axis 4 times this session, on a smaller total-admission base (11 vs. 25-27) than v8/v9 — meaning the *rate* moved further in the wrong direction even though the *absolute* false-admission count (4) is similar in scale to v8's (6) and v9's (5).

## Budget maturity

| Dimension | Status | Basis |
|---|---|---|
| Minimum Visit recall | MORE EVIDENCE REQUIRED | v10's own 80% (4/5, small denominator) is one more real data point, not a converging cross-session number; methodology continues to differ across cohorts by explicit prior convention |
| Maximum false-Visit rate | MORE EVIDENCE REQUIRED — **the hard-negative fix's own field-proof did not succeed**, and the evidence body now shows 3 cohorts (v8, v9, v10) all materially above the 2 early cohorts (v5, v7), with a well-evidenced, narrow, single-location root cause rather than a diffuse one | This session's own precise, three-pronged (visual + trajectory + cross-referenced-with-rejection) evidence |
| Maximum fragmentation rate | MORE EVIDENCE REQUIRED — **the prior 6th/7th-convergent 0% streak is broken** by one real, confirmed case this session | candidates 003/004 |
| Maximum duplicate rate | READY FOR FORMAL BUDGET REVIEW (reaffirmed) — 6th/7th convergent 0% cohort | direct check, 0/11 |
| Minimum useful-evidence rate | MORE EVIDENCE REQUIRED — v10's own 54.5% falls well below the already-withdrawn ~85% candidate and below v9's own 76.0% | direct classification |
| Maximum true capture→visible latency | MORE EVIDENCE REQUIRED — a second real cohort's worth of samples now exists (median/p90 closely matching v9), genuine progress, but Gate A's own standing rule requires cross-session convergence on an accepted number, not two cohorts' own agreement plus one large disclosed outlier | this session's own latency table |
| Minimum monitoring coverage | READY FOR FORMAL BUDGET REVIEW (reaffirmed) — 99.99% is a further convergent data point inside the ~99% candidate band | direct measurement |

Do not self-accept any of the above; all remain candidates for external review.

## Gate A closure assessment

**Is Gate A ready for formal closure review? No.**

**The one concrete blocker, named precisely:** the Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1 fix's own field-proof criterion — *"the v8/v9 false-Visit rate (20-22.2%) materially reduced"* — **did not hold**. v10's own confirmed false-Visit rate (36.4%) is higher than both v8 and v9, driven by a specific, well-understood, disclosed mechanism the fix's own report already anticipated as a residual risk: a single recurring background confusor location clearing the rule's count-based corroboration axis by accumulating enough individually-insufficient detections within one continuation window, without ever needing a strong detection. This is not a diffuse regression across many causes — it is one precisely-located, now-concretely-reproduced gap, which materially changes what the next fix needs to target (the count-accumulation path specifically, not the admission rule's overall design) versus reopening the whole admission question.

No other release-critical correctness blocker was found this session: duplicates remain at 0%, `blocked_missing_evidence` improved further, RTT/latency behavior remains stable and comparable to v9, stop-finalization and persistence-retry both worked correctly, and — importantly — the specific Gate B failure class v9 field-proved (false Visit → confident wrong species) did not recur even on this session's own 4 confirmed-false admissions.

## Defects

### 1. Hard-negative admission rule's count-based axis has a demonstrated, concrete field failure mode (release-relevant, not fixed here)

See "Hard-negative recurrence" and "False Visits," above, for the complete evidence chain. First irreversible loss: each of candidates 005, 007, 008, 009 became a durable `VisitModel` row (and, being confirmed false, contributes false history) the moment its own admission decision resolved (`decided_at` timestamps: 11:54:29Z, 12:08:01Z, 12:14:42Z, 12:21:03Z respectively) — irreversible in the sense that reviewed correction remains the only path back to accurate history for these four rows, exactly as doctrine intends, but they were never rejectable upstream once admitted. Root cause: `2 * constituent_generation_count + 1` scales with generation count, but a *single* long-lived, low-confidence, unmoving generation with enough repeated raw detections (9–33 observed this session) satisfies `detection_count > floor` without ever approaching `strong_detection_count > 0` — the axis the fix relies on when corroboration-by-count clears but strength never does. Not fixed here, per this milestone's own explicit instruction not to tune the admission rule during measurement; a precise DEV contract candidate: bound corroboration credit by *distinct* detection value/variance (e.g. requiring some minimum bounding-box or confidence movement across repeated detections within one generation), not raw count alone, so a physically static confusor cannot out-accumulate a floor scaled only by generation count.

### 2. Three real, disk-space-consuming legacy field-acceptance dev-roots are invisible to the new lifecycle tool because they predate it

`MockingBirdFieldAcceptanceV9` (6.8GB), `MockingBirdFirstHourAcceptance` (2.4GB), and the default `MockingBirdDev` (multiple retained releases plus the now-stopped stale instance). `field_acceptance_instance_lifecycle.py status/assess` correctly refuses to treat any of them as reclaimable (`NOT_RECLAIMABLE_UNKNOWN_INSTANCE`) since none was ever `init`-ed under the new tool — a real gap in `preflight`'s own `known_reclaimable_bytes` accounting (it can only ever see manifested instances), not a bug in the manifest safety design. Not fixed here; a future milestone should decide whether to retroactively `init` legacy roots or add a separate "unmanifested MockingBird-prefixed directory" advisory report.

### 3. The Camera Node's single-slot pairing credential has no supported multi-instance handoff

Confirmed directly this session (see "Operational note," above) and already documented as by-design in `docs/camera-node-reprovision-recovery-design.md`. Every fresh disposable field-acceptance instance (the standing policy) will contend with whichever prior instance last held the Node's one credential slot, requiring either a still-live prior Host to revoke cleanly through the API or an operator-authorized Node-side pairing reset. Worth naming explicitly as a recurring, expected cost of the fresh-instance policy.

### 4. The counterfactual ledger's 60-minute age-eviction bound is shorter than this milestone's own 75–100 minute session target

See "Independent denominator," above. Worked around via periodic full-window snapshots (every 12 minutes) merged post-hoc, recovering 100% of the raw/track ledgers and RTT-calibration ledger despite mid-session eviction of up to 46% of the live-queryable window at any single point in time. A future milestone could raise `CounterfactualRetentionConfig.max_age_ms` for sessions expected to run past an hour, or simply adopt the periodic-snapshot procedure as standing acceptance methodology (recommended, since it is non-invasive, already proven, and needs no product code change).

### 5. Fragmentation and useful-evidence-rate budgets both regressed this session (see Budget maturity)

Not new defects distinct from #1 above — both trace to the same root cause (the recurring confusor inflating false-Visit count, and the one genuine tracker-interruption fragmentation case at the sapling location) — listed here only to make clear neither is a separate, unexplained regression.

## Decision

**A**

Every element of the classification-A bar (§28) is met, literally, not stretched: representative real daylight, real bird activity, current accepted Host build, compatible real Node, valid RTT calibration, the accepted hard-negative admission fix active, enough reviewed Visits to interpret precision (11/11, 100%), a real independent denominator, the known hard-negative class field-tested (3/3 clean rejections across two distinct locations), genuine weak-bird safety directly assessed, useful-evidence rate measured, RTT-normalized latency measured, fragmentation/duplicates measured, monitoring/recorder coverage adequate (99.99%), and no defect that invalidates the *measurement itself* — the session ran cleanly end to end, and every metric in this report rests on direct, traceable, cross-checked evidence (visual crops at each proposal's own real detection offsets, raw bounding-box trajectories, a merged complete ledger, an independently-built denominator), not inference from the product's own summary counts alone.

Classification A is about whether this session is complete, representative, and produced trustworthy, fully-interpretable real-field evidence — not whether the hypothesis under test succeeded. It did not: the hard-negative fix's own stated field-proof criterion failed a fair, rigorous test, and that is the headline finding this report delivers, precisely traced to one well-understood root cause rather than left as a vague regression. A real, well-executed field session that finds a genuine problem is exactly what Gate A field acceptance exists to produce — smoothing this into a lower letter to soften the finding would be the wrong instinct. Do not read A here as "the fix worked;" read the "Gate A closure assessment," above, for that answer, which is unambiguously no.
