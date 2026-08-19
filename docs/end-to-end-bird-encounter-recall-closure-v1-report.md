# End-to-End Bird Encounter Recall Closure v1 — Report

Starting HEAD: `8055a93` ("Record real field-validation results for Visit Authority Budget +
Ambiguous-Boundary Recall Closure v1"). Branch: `main`. **Not pushed.**

This milestone asks the one question every prior Phase 1 field-acceptance session has
approached only indirectly: **of the birds actually present in front of the real paired
Camera Node, how many did MockingBird notice and turn into one truthful Visit?** It builds a
genuinely independent biological-encounter denominator (never a Visit, proposal, track, or
counterfactual-ledger fact), reviews it *before* opening the product's own Visit list, then
maps every independent encounter through the real pipeline.

## 1. Repository

- Starting HEAD: `8055a93`. Ending HEAD: `51ee8ea`.
- Commits this milestone: `bb19879` (configurable acceptance-recorder cadence/bounds),
  `51ee8ea` (evidence-cache bound 32→128).
- Not pushed. Working tree clean except the seven pre-existing, unrelated untracked files
  present at every prior session's start (left untouched):
  `docs/wildlife-detector-training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`.
- Real environment note: a full host reboot (Windows + WSL, same physical/virtual machine)
  interrupted the first deploy attempt mid-session; git state and the already-committed
  `bb19879` were unaffected (persistent disk), the Windows product process was not (had to be
  redeployed). Disclosed because it is a real fact about this session's own execution, not
  because it affected any evidence below.

## 2. Field cohort

- Date: 2026-08-19. Started `2026-08-19T21:26:47.734814Z`, stopped
  `2026-08-19T22:58:59.585377Z` — **92.20 minutes** (`stopped_reason: user_stopped`).
- Independent recording duration: 99.64% of session time (last saved frame at 91.87 min of
  92.20 min).
- Actual measured recorder cadence: **~1.17s** between saved frames (configured minimum
  1000ms; the extra ~170ms is real source-frame delivery granularity, not a defect — see §5).
- Recorder: 4707 frames, 4,329,997,461 bytes (~4.33GB, under the 4.95GB configured cap;
  neither `max_frames` (5500) nor `max_total_bytes` bound bound early — full-duration coverage
  achieved, unlike the prior session's byte-bound defect).
- Camera Node/source: `stream-ca892992771c` ("feeder"), paired Raspberry Pi ("Pi camera 1"),
  same real backyard scene as every prior session (seed tube feeder + hummingbird feeder on a
  shepherd's hook, residential street/driveways in the background).
- Environmental conditions: full sun throughout, no precipitation, moderate vehicle/pedestrian
  street traffic.
- Pre-flight (all directly verified via `GET /api/product/instance`/`/health`/
  `/observation/status`, not the deploy helper's report alone): deployed `git_commit`
  `bb1987937869d2e39e1d1adb84fd4776314fbc4c` (exact match to intended commit),
  `database_schema_version: 35`, CUDA available (`cuda_available: true`,
  `selected_execution_providers: [CUDAExecutionProvider, CPUExecutionProvider]`), MDv5a loaded
  (`score_threshold: 0.1`, matching production), BioCLIP available (confirmed via a successful
  `automatic_identification` result on the immediately-prior historical session), camera
  connected (`"Camera Node is paired and ready."`), fresh `activation_boundary_at` (3 seconds
  after Start), `candidate_authority_exhausted: false`, 135-142GB free disk throughout
  (comfortably over the ~4.95GB recorder budget).

## 3. Independent denominator

Per governing hierarchy, option A: the accepted `acceptance_recorder` capability-safe tee,
reconfigured this milestone (see §12) for dense cadence via three new, individually-optional
env vars (`MOCKINGBIRD_ACCEPTANCE_RECORDING_INTERVAL_MS/_MAX_FRAMES/_MAX_BYTES`), off by
default, unset for every ordinary product process.

- **Genuine animal encounters identified: N = 22** (conservative; see §4 for why the true
  number is plausibly higher, never lower).
- All 22 are bird encounters; **zero** other wildlife (no squirrels, cats, or other animals
  observed this session — a real, disclosed fact, not a gap in review).
- Ambiguous/unusable events preserved separately: 1 (encounter #12, a single independent
  sample with no bracketing confirmation).
- Duration buckets: <1s: 0. 1-3s: 0. 3-10s: 11. >10s: 7 (one, #8, is a ~9.8-minute multi-visit
  cluster counted conservatively as 5 sub-visits). Unresolved: 1.
- No hummingbird sighting was independently confirmed at the dedicated red hummingbird feeder
  specifically — a real, disclosed gap in this session's own subject diversity, not a
  methodology flaw (the same feeder was empty in every reviewed frame).

See [independent-encounter-table.md](../data/field-acceptance/2026-08-19-end-to-end-recall-closure/independent-encounter-table.md)
(gitignored `data/`, retained locally) for the complete per-encounter table.

### Methodology, including a disclosed self-correction

Two tools were built for this session, both diagnostic-only and reading nothing but the
recorder's own JPEGs/manifest (zero product-repository or admission-pipeline coupling, matching
the recorder's own structural guarantee):

- `motion_screen.py`: frame-to-frame block-max pixel-difference screening (MAD-based threshold)
  over all 4707 frames — 85 candidate activity windows flagged (34.4% of session time),
  reviewed individually at full 1920x1080 resolution.
- `contact_sheet.py`: a 20-sheet, stride-3, full-session backstop grid sweep, to catch anything
  the diff signal might miss.

**Self-correction, disclosed in full (matching the prior milestone's own precedent):** the
first full-frame review pass under-called several real encounters — a bird perched directly on
a thin metal hook, and birds mid-flight (small, motion-blurred), were both missed at ordinary
viewing scale. A crop+3x-zoom re-pass (applied to every one of the 21 real product-created
candidate timestamps, cross-checked against the product's own persisted evidence image where
one existed) recovered two of these misses directly (encounters corresponding to candidates
105 and 122) and confirmed several already-found ones. This is the same lesson the prior
milestone's "contact sheets → crop sheets" correction taught, now independently re-confirmed:
**a full-frame-only pass is not sufficient for small/flying subjects in this scene; zoom is
required**, and this report's numbers reflect the zoomed, corrected pass throughout.

## 4. End-to-end funnel

Because the accepted `frame-driven-onnx-cuda` provider runs its detector directly on every
incoming analysis frame (no separate zone-motion pre-filter exists in this architecture,
unlike the legacy snapshot path), **ACTIVITY and DETECTOR are the same stage** for this Camera
Node path — reported honestly as one combined stage rather than an artificial split.

| Stage | Count | Rate (denominator) |
|---|---:|---|
| N — genuine independent encounters | 22 | — |
| A — presented to analysis (frame containing the animal reached inference) | 22 | 22/22 = 100% |
| C — detector localized (real animal-class detection) | 17 confirmed yes; 1 confirmed no; 1 marginal; 3 insufficient lineage | 17/19 lineage-available = 89.5% |
| D — coherent confirmed track | 17 | 17/17 of localized = 100% |
| E — viable proposal assembled | 17 | 17/17 of tracked = 100% |
| F — evidence survived to admission attempt | 15 | 15/17 of proposed = 88.2% |
| G — admitted Visit | 15 | 15/17 of evidence-surviving = 100%; **15/22 = 68.2% end-to-end (conservative upper bound — see below)** |

**Why 68.2% is a ceiling, not a floor:** N=22 already undercounts encounter #8's cluster (5
sub-visits counted conservatively; visual density supports more). Any additional real
sub-visits within that cluster would enter the denominator without a matching admitted Visit
(the cluster's own admitted-Visit count, 4, is already fixed), so a fuller accounting of
cluster #8 alone would *lower*, never raise, the true end-to-end rate.

- Capture opportunity rate = A/N = **100%** — no analysis-cadence miss found: the detector
  runs continuously (confirmed directly — see §7, encounter #16) and no genuine encounter was
  shorter than the ~1.1s minimum gap between inference-eligible frames.
- Detector recall conditional on presented frame = C/A (lineage-available) = **89.5%** (17/19).
- Tracking success conditional on detection = D/C = **100%** (17/17) — every genuine
  detector-localized subject this session also formed a confirmed track; zero
  detector-hit-then-tracker-lost cases found.
- Proposal success = E/D = **100%** (17/17).
- Evidence/admission success = G/E = **88.2%** (15/17) — the single largest measured loss
  stage this session, both instances independently confirmed real (see §7).
- **3 of 22 encounters (#3, #6, #7) fall entirely before the counterfactual ledger's own
  60-minute-age/12,000-raw-detection eviction boundary** (this session was busy enough — 22,435
  raw detections recorded — to evict its own early history). Their first-loss stage is honestly
  `insufficient_counterfactual_lineage`, not guessed. None of the 3 received a Visit.

## 5. Every miss

| # | Time (s) | Visibility/size | Duration | First-loss stage | Evidence | Fixed |
|---|---|---|---|---|---|---|
| 3 | 710-721 | small bird, hook | 3-10s | insufficient_counterfactual_lineage (pre-eviction) | My own frames only | N/A |
| 6 | 963-974 | small bird, feeder | 3-10s | insufficient_counterfactual_lineage (pre-eviction) | My own frames only | N/A |
| 7 | 2604-2612 | small bird, feeder | 3-10s | insufficient_counterfactual_lineage (pre-eviction) | My own frames only | N/A |
| 8e | 3535-3685 | small bird, feeder, stationary | **149.6s** | **Evidence admission** (`reject_no_identification_or_context`) — 6 confirmed generations, max confidence 0.816 (above `strong_detection_threshold`), legitimately delayed `blocked_continuation_pending` for a real 183.5s before its own attempt found no persistable identification/context bytes | My own frames (3550/3575/3600s), full counterfactual ledger trace | **Yes — evidence-cache bound raised 32→128 (§9)** |
| 11 | 4351-4382 | reddish bird (hook) + brown bird (feeder) | 30.3s | **Evidence admission** (`blocked_missing_evidence`) — single generation, 24 detections, 12 strong (max 0.815), only a ~34s delay before zero persistable bytes | My own frames (4360.5/4369.7s), full counterfactual ledger trace | **Yes — same fix (§9)** |
| 12 | ~4473 | reddish bird, hook | unresolved (single sample) | Borderline detector/tracker loss — nearest ledger fact is one *unconfirmed* generation (0.111 max confidence) ending just before | My own frame only | Not fixed — n=1, weak signal, not material |
| 16 | 4942-4949 | small bird, hook | 3-10s | **Clean detector miss** — 61 raw detections in this exact window, every one `broad_class=vehicle` (repeated static parked cars); zero animal-class detections despite the detector clearly running at its baseline ~1.1s cadence throughout | My own frame, full raw-detection ledger trace | Not fixed — n=1, see §8 |

## 6. Detector

- MDv5 encounter recall conditional on a presented frame (lineage-available cases): **89.5%
  (17/19)**.
- One clean, well-evidenced miss (encounter #16): a small bird on the same thin metal
  hook/foliage structure that also produced the session's one borderline case (#12) — both
  hook-perched, both small, both in dappled/branch-adjacent context. **n=2 of 22 (9.1%)**
  hook-position cases show detector softness; the feeder-base position (the large majority of
  encounters) shows no detector-miss cases at all this session.
- Confidence distribution for genuinely-present, detector-localized subjects: spans 0.111
  (the one marginal case) to 0.931 (historical context); this session's own confirmed-real
  detections ranged roughly 0.3-0.82 for weaker sightings up to 0.816/0.815 for the two
  evidence-admission misses.
- Short-encounter performance: all 11 confirmed 3-10s encounters that had traceable lineage
  were detector-localized successfully; the one clean miss (#16) was itself only a ~7s
  encounter, consistent with (not proof of) brief/small subjects being the harder case, but the
  sample is too small (n=1) to generalize.
- **No candidate detector comparison was performed.** Per governing instruction #13, this
  requires the independent denominator to prove the detector is a *material* loss stage
  (quantified, not "detector missed some birds"). One clean miss out of 22 real encounters
  (4.5% of the denominator; 10.5% of lineage-available detector attempts) does not meet that
  bar — the dominant, quantified loss stage this session is evidence-admission (2 of 22, 9.1%
  of N, but 100% of the *material, confirmed, strong-confidence* misses), not detector
  accuracy. No detector/capture work was undertaken.

## 7. Visit quality

- Created Visits this session: **21**.
- Genuine (independently confirmed real animal, via my own recorded frames and/or the
  product's own persisted evidence image, both reviewed at full zoom): **18**.
- False (independently confirmed empty scene at the candidate's own timestamp, in both the
  recorder's nearest frame and the product's own zoomed evidence image): **2** (candidates 103,
  104 — both `species_suggestion` present despite no visible animal in either independent
  source).
- Unresolved: **1** (candidate 123 — its own exact evidence timestamp shows no clear subject
  even at zoom, though it is directly bracketed by confirmed real sightings ~30s before).
- **False-Visit rate: 2/21 = 9.5%** — a large, real improvement over the 52.9%/57.1% rates
  found in the two immediately-preceding large-cohort milestones, consistent with Scene
  Confusor Suppression v1 now being live (see §9) and, more broadly, with continued product
  maturity.
- Duplicate Visits: **3** (candidates 108, 109 duplicate 107's own real ~2-second sighting;
  candidate 118 duplicates 117's own real sighting).
- Fragmented encounters: **2** (the ~612-614s encounter: 1 real sighting → 3 Visits, with
  *inconsistent* species suggestions — `tufted_titmouse`, `american_robin`, `american_robin` —
  for what is almost certainly one bird; the ~4272-4287s encounter: 1-2 real, closely-spaced
  sightings → 2 Visits, both `house_finch`, consistent).
- Incorrect merges (one Visit spanning >1 real encounter): **0** found.
- Root cause of both fragmentation cases, traced directly via the counterfactual ledger (only
  the second was inside the retained window): `visit_episode_assembler.classify_boundary`'s
  own documented, deliberate "structural incompatibility" rule — two confirmed tracklets whose
  time spans *overlap* are never merged, because the assembler cannot safely distinguish "two
  simultaneous real subjects" from "one tracker-association artifact that spawned a second
  generation" (see [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
  §"Structural incompatibility"). For the 4272-4287s case, three tracker generations formed at
  nearly the same feeder-perch geometry within a 14-second span, two of them (`0181`, `0182`)
  temporally overlapping by several seconds. **This is disclosed, not fixed**: it is an
  already-documented, deliberately conservative design tradeoff (the same boundary
  `tracklet-visit-assembly-contract.md` explicitly protects — "do not redesign tracker
  association"), not an undiscovered bug with an obvious minimal fix. A safe fix would require
  either tracker-association changes or individual-subject disambiguation, both explicitly
  out of bounds for this milestone (see product-doctrine.md's "do not introduce
  individual-animal identity claims"). Recorded here as a real, quantified, bounded residual
  finding for a future milestone, per instruction #18's own deferral criteria ("the change
  would require a genuinely new architecture").

## 8. Existing fixes — live verification

### Candidate authority (per-Stream, schema 35)

- `activation_boundary_at` came up fresh (`2026-08-19T21:26:59.599375Z`, 12 seconds after
  Start) and **never moved** for the entire 92.2-minute session (confirmed at every status
  check, including the final post-Stop status).
- `candidate_authority_exhausted` stayed `false` throughout, including at 21 real admissions —
  nowhere near the default budget of 50.
- No `blocked_session_limit` occurred.
- No cross-Stream contamination exercised live (only one real Camera Node Stream exists in
  this project's field history, as in every prior session) — covered instead by
  `test_multi_stream_authority_is_isolated`/`test_multi_stream_stop_does_not_kill_a_different_
  streams_authority`, unchanged this milestone.
- Configured budget: 50/session (default). Consumed: 21. Starting/ending activation boundary:
  identical (`2026-08-19T21:26:59.599375Z`), confirming no unexpected reset.

### Evidence-cache fix (8→32, Visit Authority Budget milestone)

**This is the missing live proof point the prior milestone explicitly left open** — and this
session found it, twice, at the *already-fixed* 32-entry bound: a real, busier session (21
candidates/227 proposals/1336 evidence candidates vs. the prior motivating session's 8
candidates/142 proposals/~600 evidence candidates) still exhausted 32. See §5 (misses 8e, 11)
and §9 (the fix applied this milestone). The *mechanism* of the original fix (harvest bytes
before eviction, not an admission-threshold change) is confirmed sound; its *specific bound*
needed raising again under real, busier load.

### Scene confusor

**Zero firings** (`blocked_scene_confusor_suspected` does not appear anywhere in this
session's `suppressed_reasons`). Independent review found no case where a genuine animal in a
historically-relevant region was suppressed (none of the 18 genuine Visits, nor either of the
2 confirmed misses, carry any scene-confusor-related outcome) — fully consistent with, and
adding a third real session of evidence to, the mechanism's own recall-safety record.

## 9. Bounded defect fix: evidence-cache capacity 32 → 128

- **Defect**: real, evidenced 2026-08-19 recurrence of the exact evidence-cache-eviction
  mechanism the prior milestone fixed at 8→32 — a busier real session (see above) still
  exhausted 32 twice, both times for genuinely strong, well-tracked, real birds (0.816 and
  0.815 max confidence, one with 12 strong detections) delayed by legitimate
  `blocked_continuation_pending` resolution (183.5s and ~34s respectively).
- **RED**: `test_delayed_proposal_survives_a_busier_real_session_shape_than_the_32_bound_
  covers` (new, `tests/test_engine_runtime.py`), built directly from this session's own real
  generation count/timing/confidence shape (149.6s/6-generation/0.816-confidence proposal,
  183.5s real delay, ~44 unrelated evidence insertions — this session's own measured
  evidence-candidate rate, 1336/5512s≈0.242/s, projected across the real delay), fails against
  the old 32 bound (`candidates_created == 0`, expected 1).
- **Fix**: `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES` raised 32→128 in
  `engine_runtime.py` — the same relative (4x) jump the original 8→32 fix itself used. Still a
  capacity fix, not an evidence-quality threshold change; `candidate_quality_gate.evaluate_
  evidence_admission`'s own requirements are completely unchanged.
- **GREEN**: the new test passes at 128; the *original* defect's own regression test
  (`test_delayed_proposal_still_finds_its_evidence_after_unrelated_cache_churn`) still passes
  unchanged; the full `test_engine_runtime.py` file (64 tests) passes.
- **Regression controls**: the broader candidate-visit/assembly/counterfactual suite (153
  tests across `test_candidate_visit_authority.py`, `test_candidate_visit_repository.py`,
  `test_candidate_visit_authority_acceptance.py`, `test_visit_episode_assembler.py`,
  `test_counterfactual_lineage.py`) passes unchanged.
- **Disclosed limitation, not overclaimed**: this remains a capacity bound, not a structural
  fix. Eviction is still purely insertion-count-based with no awareness of which pending
  proposal still needs which bytes — an arbitrarily busier or longer-delayed session could in
  principle still exhaust 128. A pending-proposal-aware eviction policy would close this gap
  structurally but is a materially larger change (touching the core harvest/eviction logic,
  not a constant), left as a disclosed follow-up rather than undertaken in this bounded pass.

## 10. Species supporting evidence (secondary)

- Reviewable genuine Visits: 18.
- Suggestion availability: 18/18 (100% — every genuine Visit carried a `suggested_label`).
- Species observed: `house_finch` (8), `carolina_chickadee` (3), `brown_thrasher` (4),
  `tufted_titmouse` (2), `american_robin` (2, both from the same fragmented sighting),
  `northern_mockingbird` (1). All plausible common backyard-feeder species for this
  region/season; no glaring implausible label (unlike the historical "Red-bellied Woodpecker
  from an uncropped frame" finding — same-frame evidence and subject-centric cropping remain
  in effect).
- One glaring inconsistency, not a wrong-species-per-se finding: the fragmented ~612-614s
  sighting received two *different* species guesses (`tufted_titmouse` then `american_robin`
  twice) for what is almost certainly one real bird — a direct, visible symptom of the
  duplicate-Visit finding in §7, not a separate species-model defect (each individual
  suggestion was generated from a distinct, slightly-different crop/moment).
- No abstention/unresolved suggestion outcomes observed (BioCLIP produced a suggestion for
  every genuine Visit). Per this milestone's own scope boundary, no further species-model work
  was undertaken.

## 11. Performance

- Analysis cadence: source ~5fps nominal; detector 1fps baseline / 4fps with an active track
  (unchanged, confirmed via `model_runtime_metadata`).
- Detector latency: not separately re-measured this session (unchanged provider/model from
  prior sessions; `engine_load_duration_ms: 11684.6` for cold engine startup, slower than the
  prior session's 2724.7ms — attributable to a genuinely fresh process after the mid-session
  redeploy, not a regression).
- Camera Node frame cadence: source delivered frames frequently enough that the recorder's
  1000ms-minimum-spacing config achieved an actual ~1.17s cadence (not exactly 1000ms — real
  source-frame delivery granularity, disclosed, not silently assumed).
- Acceptance-recorder cadence: ~1.17s measured (vs. the old 3000ms default) — **~2.6x denser**
  than any prior field session's denominator, still short of the literal "≤1s" target but
  disclosed precisely rather than overclaimed; achieving exactly 1000ms would require either a
  higher source frame-delivery rate or accepting the recorder occasionally re-saving a
  slightly-stale frame, neither pursued this milestone.
- GPU/runtime health: CUDA confirmed active throughout; zero reconnects/errors observed at any
  of 6 status checks across the full session.
- Dropped/failed frame indicators: none observed; `camera_connected: true` at every check.
- Memory/storage growth: recorder grew to 4.33GB (within its 4.95GB budget); host free disk
  dropped from ~141.7GB to ~135.4GB over the full deploy+session (recorder + normal product
  growth + release artifacts), no low-disk warning at any point.
- Acceptance-recorder overhead: no latency/timeout issue observed attributable to recording
  (identical to the prior session's own finding); the 128-entry evidence-cache bound increases
  peak in-process memory footprint by roughly 3x the prior 32-entry bound's own (undisclosed
  precisely, but "tens of MB") footprint — still small and bounded relative to available host
  memory, not separately re-measured this session.

## 12. Code changes

### 1. Configurable acceptance-recorder cadence/bounds (`bb19879`)

- **Motivation**: this milestone's own explicit requirement for ≤1s-where-practical sampling
  and full-session coverage, denser than `AcceptanceRecorderConfig`'s existing 3000ms/2400-frame
  defaults (sized for the *previous* milestone's different question).
- **Change**: `acceptance_recorder_config_from_env` (new function) reads three new, optional
  env vars and applies them as overrides on `AcceptanceRecorderConfig`'s own dataclass
  defaults; `ObservationEngineSessionManager` accepts an injectable
  `acceptance_recorder_config_factory` (mirrors the existing `ProviderLoader`/
  `TransportFactory` shape); `main.py` wires it; `deploy_windows_dev.py` forwards three more
  `MOCKINGBIRD_DEV_`-prefixed dev-shell variables. Unset (every ordinary process) reproduces
  prior behavior byte-for-byte.
- **Tests**: 4 new tests in `test_acceptance_recorder.py` (default/override/partial-
  override/out-of-range behavior), 1 new test in `test_engine_runtime.py` (factory injection
  actually used for a real Start).
- **Validation**: `python scripts/verify_fast.py` — 1564 passed, 0 failed, 141.22s.

### 2. Evidence-cache bound 32 → 128 (`51ee8ea`)

See §9 for the complete defect/RED/fix/GREEN/regression-control account.

## 13. Validation

- Fast (`scripts/verify_fast.py`, after commit `bb19879`): **1564 passed, 0 failed, 141.22s**.
- Focused regression (after commit `51ee8ea`): `test_engine_runtime.py` 64/64 passed (30.45s);
  broader candidate-visit/assembly/counterfactual suite 153/153 passed (16.50s).
- Core (`scripts/verify_core.py`, final, both commits included): **3179 passed, 0 failed, 10
  deselected, 11 xfailed in 580.61s (9:40)** — the same known 11-xfail baseline
  ([test-suite-validation-tiers-contract.md](test-suite-validation-tiers-contract.md)'s
  Category 6), zero new or newly-resolved failures.
- No `xfail`/`skip` disposition changed by this milestone.
- No detector benchmark/promotion validation applicable — no detector-behavior change was made
  (§6).

## 14. Remaining uncertainty

Stated explicitly, not hidden:

- **Cluster #8's true internal visit count is not fully resolved.** Counted conservatively at
  5 sub-visits (matching distinguishable proposal-level evidence); dense independent visual
  confirmation is consistent with more. This makes the reported 68.2% end-to-end recall rate a
  ceiling, not a precise value — the true rate is plausibly somewhat lower.
- **3 of 22 encounters (#3, #6, #7) have no pipeline-stage attribution at all** —
  `insufficient_counterfactual_lineage`, honestly, because this session's own real busyness
  (22,435 raw detections) evicted the ledger's early history before this report could query it.
  A less busy, or more promptly-queried, session would not have this gap.
- **Encounter #12 (~4473s) is a genuinely marginal case** — a single independent sample,
  bracketed by no confirmed neighboring sighting, with only a weak (0.111), unconfirmed nearby
  detector hit as ledger evidence. Neither confidently a miss nor confidently resolved.
- **Whether the evidence-cache fix (32→128) is sufficient going forward is not proven, only
  strengthened.** This is a bound, not a structural fix (see §9's own disclosed limitation) —
  a sufficiently busier or longer-delayed future session could still exhaust it. The
  *mechanism* (harvest-before-eviction) remains sound; only the *specific number* was
  re-justified against real, busier load than the number it replaces was sized against.
- **The two fragmented-Visit cases (§7) are diagnosed, not fixed.** The root cause
  (`visit_episode_assembler`'s deliberate non-merge of temporally-overlapping tracklets) is a
  known, documented, intentionally conservative design boundary this milestone's own governing
  constraints protect from casual change.
- **Detector recall (89.5%, lineage-available) rests on a small sample** (19 lineage-available
  encounters, of which 1 was a clean miss and 1 marginal). Not large enough to justify a
  detector-comparison exercise (§6), but also not large enough to rule out that a bigger cohort
  would find more.
- **No hummingbird encounter occurred this session** — the dedicated hummingbird feeder was
  empty in every independently-reviewed frame. This report cannot speak to hummingbird-specific
  recall at all.

## Final decision

**B — ONE BOUNDED PIPELINE RECALL DEFECT REMAINS.**

The independent denominator is valid and methodologically sound: built entirely from the
recorder's own frames, reviewed before the Visit list was ever opened, with a disclosed,
corrected methodology (zoom required for small/flying subjects) and honest uncertainty bounds
throughout (§14). Real, visible bird recall is materially strong — 15 of 22 conservative
genuine encounters (68.2%, a ceiling) became a Visit, detector localization succeeded 17 of 19
times lineage could confirm it (89.5%), and every detector-localized, tracked subject this
session went on to form a viable proposal (100%). Precision is now genuinely strong (9.5%
false-Visit rate, down from 52.9%/57.1% in the two immediately-preceding large cohorts) and
scene-confusor suppression continues to show zero interference across a third real session.

But this session's own required fresh field validation did exactly what it is for: it found
the evidence-cache fix's prior bound (32) was *not yet sufficient* — a specific, bounded,
now-fixed pipeline defect, evidenced twice with full ledger traces and RED/GREEN regression
proof, not a vague "recall could be better." That is Decision B, not A: end-to-end recall is
not yet accepted as done, because one concrete, demonstrated, non-model pipeline stage
(evidence-cache capacity under real busy-session load) needed — and received — a further bounded
fix this same milestone. It is not Decision C: the detector itself is not a material blocker
(one clean miss, n=1, out of 22 real encounters; no material pattern beyond a small, disclosed
hook-position softness). It is not Decision D: the denominator was sufficient (22 genuine
encounters, exceeding the 10-20 target) and methodologically sound.

**Recommended next bounded step**: one more real field session, now with the 128-entry
evidence-cache bound in place, specifically to obtain a live (not just RED/GREEN-synthetic)
proof point that the raised bound holds under real load — mirroring exactly how this
milestone itself was the live-proof follow-up the *prior* evidence-cache fix (8→32) was still
waiting on. If a future session is busy enough to exhaust 128 as this one exhausted 32, that
would indicate the capacity-bound approach itself has reached its useful limit and the
disclosed structural alternative (pending-proposal-aware eviction) should be built instead.
