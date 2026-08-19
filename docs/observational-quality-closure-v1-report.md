# v0.1 Observational Quality Closure v1 — Report

Starting HEAD: `797db8fb10bab75c41da4e1c8de415c287bc9f86` ("Test Suite Runtime & Baseline
Reliability v1")
Branch: `main`. Not pushed.

Working tree at completion: clean except the same seven pre-existing, unrelated untracked files
present at session start (left untouched throughout, per the established precedent recorded in
this project's own memory and every prior session's own final report):
`docs/wildlife-detector-training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`.

This milestone asked the question every prior Phase 1 field-acceptance session had left open:
not "do the Visits MockingBird creates look good" but **how often does MockingBird actually
notice a real animal, turn it into a usable Visit, provide useful evidence, and offer an
appropriately accurate (or abstaining) species suggestion.** It is a continuation of, not a
replacement for, the accepted Detection Quality Accounting / Rejected-Detection Attribution /
Localization Attribution / Admission Recall Investigation lineage — see
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md),
[rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md),
[localization-attribution-contract.md](localization-attribution-contract.md), and
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md).

## 1. Evidence sources and cohorts

Per the task's priority order, and following the doctrine that **system-created Visits are never
the denominator**:

1. **Fresh bounded field session (priority 1):** a real deploy-and-observe attempt against the
   real, currently-paired Camera Node on the Windows/GPU sandbox was made during this milestone,
   with genuine, disclosed effort across two attempts. See §9 for the full account and outcome.
2. **Existing recent source-resolution field evidence (priority 2, primary source used):** the
   real product's own live userdata database and media store
   (`%LOCALAPPDATA%\MockingBirdDev\userdata`), read directly and read-only throughout — **not**
   the WSL dev checkout's own separate `data/mockingbird.sqlite3` (a distinct, unrelated
   database). This contains every real candidate Visit the real paired Camera Node
   (`stream-ca892992771c`, "Pi Yard Camera" — a fixed view of a backyard tree with a seed feeder
   and a hummingbird feeder) has produced since 2026-08-14, across five real sessions
   (`monitoring_exposure_intervals`):
   - 2026-08-14 03:19 (~3min)
   - 2026-08-17 17:38–17:58 (~20min)
   - 2026-08-17 21:29–23:03 (~94min) — the already-accepted "Admission Recall Investigation" session
   - 2026-08-18 00:33–02:07 (~94min) — the already-accepted "fresh field acceptance" quiet session
   - **2026-08-18 12:00:09–17:27:31 (~5h27m) — previously unrecorded, discovered this milestone.**
     Ended via an unclean restart (a deploy-triggered process replacement during the same day's
     BioCLIP Review Queue Performance v1 acceptance work, not a newly-found crash defect;
     disclosed, not separately chased this milestone). Produced the large majority of the
     evidence used below.
   - Two short 08-18 11:34/11:45 sessions are deploy-retry noise, excluded from analysis.
3. **Governed frozen/private reviewed material (priority 3):** the existing checksum-verified
   75-image frozen benchmark (`data/evaluations/detector-promotion-v1/`) is used for detector
   evidence continuity (§5) but never as the encounter denominator, and was never touched for
   writing.

## 2. Biological-encounter adjudication method

**70 real admitted candidate Visits** (events `visit-observation-candidate-019` through `-088`,
2026-08-14 through 2026-08-18) were independently adjudicated by directly viewing each one's real
persisted evidence image, not its detector/species metadata. Method:
- Every Visit's real `identification`-role evidence image (native 3840×2160) was fetched from
  the live product's own media store and rendered as a padded, upscaled, box-annotated crop
  (2× the box dimension of padding each side, 3× Lanczos upscale) plus, for ambiguous/high-stakes
  cases, the full un-cropped frame with the exact persisted box drawn on it. **Every initial
  `ambiguous` call was deliberately re-examined a second time** with a sharper protocol (tighter
  1.3× padding, 5× Lanczos upscale, +30% contrast, +80% sharpness) before being finalized — the
  first-pass crop parameters proved too generous/soft to reliably resolve a small bird against
  the feeder's own texture, and every one of the 15 initial `ambiguous` calls was resolvable
  under the sharper recheck (13 to `false_positive`, 2 to `real_confirmed`) with zero cases
  remaining genuinely unresolvable. This correction is disclosed in full, not smoothed over: an
  earlier draft of this report undercounted the false-Visit rate because its first-pass crops
  were not sharp enough to safely call several of these — the numbers below are the corrected,
  final ones after that second pass.
- Each was classified `real_confirmed` (a real animal is clearly visible in/near the box),
  `real_plausible` (a bird-shaped form is visible but not unambiguous at available resolution),
  or `false_positive` (independently confirmed no animal anywhere near the box, including
  checking the full frame) — never forced to a guess where a second, sharper look still left
  genuine doubt (none did, after the recheck pass).
- This is **agent-diagnostic visual review**, explicitly disclosed as such, exactly the same
  methodology precedent this project's own prior sessions established (see
  `review_origin=agent_diagnostic` review-label precedent from 2026-08-10/11/13 sessions in the
  same database). It is not, and is never presented as, reviewed truth — see
  [review-decision-provenance-contract.md](review-decision-provenance-contract.md). Where a true
  human-reviewed `ReviewLabel` already existed (one case: `visit-observation-candidate-037`,
  human-reviewed `house_finch` by the product's real user), it is called out explicitly as ground
  truth, distinct from every other agent-diagnostic call.
- Full per-event record: `visual_adjudication.csv` (70 rows), reproduced in full in this
  report's evidence bundle referenced in §11.

**Result:**

| Adjudication | Count | % |
|---|---:|---:|
| real_confirmed | 17 | 24.3% |
| real_plausible | 16 | 22.9% |
| **real (either)** | **33** | **47.1%** |
| false_positive | 36 | 51.4% |
| false_positive (high-confidence species ID) | 1 | 1.4% |
| **false Visit (either)** | **37** | **52.9%** |

Zero cases remain genuinely ambiguous after the sharpened recheck pass (§2 above) — every one of
the 70 admitted Visits in this cohort was resolvable to `real` or `false_positive`.

By date (n≥6 only; 08-14's n=1 is too small to read): 08-16 = 33% false (n=6), 08-17 = 62% false
(n=13), 08-18 = 52% false (n=50) — **consistently over half of admitted Visits are false
positives on the two largest-sample days**, not a one-off.

## 3. Encounter-level funnel (stage-by-stage)

Two complementary, methodologically distinct measurements — the pre-admission counterfactual
ledger is per-process, in-memory-only and does not survive a process restart
(`rejected-detection-attribution-contract.md`), so it is only available for sessions whose
process never restarted before analysis began; the 5h27m 08-18 session's ledger did not survive
the subsequent redeploys, disclosed honestly rather than reconstructed.

**(a) Full pipeline funnel, from the existing 2026-08-17 ~94min accepted session** (already
computed by `mockingbird.observation.encounter_accounting`, reused unchanged, not re-derived —
see `data/field-acceptance/2026-08-17-admission-recall-investigation/FINAL-REPORT.md`):

```
genuine encounter clusters reconstructed: 16
  with confirmed tracking:  11   (tracking_recall = 68.75%)
  with a viable proposal:   11   (proposal_recall  = 100%)
  with an admitted Visit:    1   (admission_recall =  9.09%, BEFORE the ambiguous-boundary fix)
```
Caveat carried forward honestly: this session's own first ~32 minutes (including its first
admitted Visit) predate the ledger's retention window and are not reconstructable at
encounter-lineage detail.

**(b) Post-admission Visit-quality audit, from this milestone's own 70-event cohort** (§2): of
70 admitted Visits, 47.1% real, 52.9% false, 0% left ambiguous after the sharpened recheck pass.

Reading (a) and (b) together: the *recall* side of the funnel (does a real encounter reach
confirmed tracking → a viable proposal) was already measured as reasonably strong in prior work,
and the arbitration fix already closed one demonstrated, permanent admission-recall defect
(§4). What this milestone adds is the first *large, non-session-concentrated* measurement of the
*precision* side: **slightly over half of what actually gets admitted is not a real animal at
all** — missed by every prior session because no session before this one had a cohort large
enough (condition 1 of the Production authority gate, `detection-quality-accounting-contract.md`)
to measure it responsibly.

## 4. Re-testing the ambiguous-boundary admission fix

The arbitration fix (`candidate_visit_authority.resolve_ambiguous_boundary_arbitration`,
committed `d1e4903`) is the mechanism behind (a)'s admission-recall number moving from a
demonstrated 0% to 100% for the one directly-proven strong-signal case (real-data replay,
unchanged since that milestone — see `tracklet-visit-assembly-contract.md` "Ambiguous boundary
arbitration"). This milestone's own 70-Visit cohort is entirely POST-fix (all five real sessions
above postdate commit `d1e4903`) and provides an independent negative control: **zero duplicate
Visits and zero fragmented encounters were found** (§6) across a much larger real sample than the
fix's own original acceptance window — the fix has not introduced any new duplicate-admission
risk in five more real days of use. No new counterfactual evidence of a *further* deterministic
admission-lifecycle defect was found this milestone (the one real, material gap found — §5 — is a
precision/false-positive issue, mechanistically unrelated to the ambiguous-boundary/continuation
state machine). No admission-policy code was changed this milestone.

## 5. Real, quantified defect: admission-precision (false-Visit) gap

**First pipeline stage responsible:** none of the existing gates (`candidate_visit_authority`,
`candidate_quality_gate`) evaluate whether the tracked subject is actually an animal versus a
static scene feature — by design, confirmed by direct code reading (Detection Quality Accounting
v1's own finding, "detector confidence never being consulted by either admission gate," still
true today). A static, non-animal visual feature that clears the raw 0.1 detector decode floor
trivially satisfies `minimum_detector_confirmations=2` (it never moves, so it "confirms" every
frame it is detected in) and proceeds unchanged through tracking, evidence-scoring, and admission.

**Is this fixable by a confidence floor? No — tested directly, not assumed.** Swept the real
persisted `confidence_evidence_json.max_confidence` against the ground truth in §2:

| Threshold | Real animals kept | False positives rejected |
|---:|---:|---:|
| 0.1 (current) | 100% | 0% |
| 0.2 | 97% | 19% |
| 0.3 (prior smaller-cohort "best" point) | 82% | 27% |
| 0.4 | 76% | 38% |
| 0.5 | 73% | 51% |
| 0.6 | 64% | 65% |
| 0.7 | 58% | 70% |

No threshold clears both "materially improved false-positive rejection" and "real-animal recall
not materially degraded" together — this formally fails the Production authority gate's
conditions 2+3 (see the direct update now recorded in `detection-quality-accounting-contract.md`
itself, "Production authority gate"). **Production admission policy is retained unchanged; no
threshold was adopted.**

**What the false positives actually are:** geometric clustering of the 37 false-positive box
centroids (proximity <0.06 normalized) shows they are **not diffuse noise** — 28/37 (76%) fall
into just 6 recurring spatial hot spots:
1. n=8, ~(0.46, 0.53) — a static texture/shadow within/near the feeder's own silhouette itself;
   the single largest confusor, recurring across the whole 08-18 session
2. n=6, ~(0.30, 0.51) — a second feeder-adjacent spot, distinct enough by geometry not to merge
   with (1) — several were originally-high-confidence "House Finch" suggestions (§11)
3. n=6, ~(0.19, 0.69) — unidentified scene feature, recurs across the whole 08-18 session (>3h span)
4. n=4, ~(0.04, 0.64) — far-left frame edge (driveway/grass), 08-17
5. n=2, ~(0.06, 0.39) — **confirmed via full-frame inspection: the shadow cast by a roof/chimney vent**
6. n=2, ~(0.16, 0.86) — bottom-left grass

The remaining 9/37 are singletons (no other false positive within the proximity radius) — real,
if less concentrated, false-positive sources exist too, but the large majority of the volume is a
small, identifiable set of recurring spots, not diffuse sensor noise.

**No narrow, deterministic code fix was found or implemented this milestone.** A real fix would
require a new, persistent, cross-session, per-Stream capability (recurring-geometry memory,
analogous in shape to the existing bounded counterfactual ledger, but durable across restarts)
that does not exist today — a legitimate, scopeable next milestone, not a rushed policy patch
inside this one; see §16/roadmap. This is the one bounded observational defect this milestone's
decision rests on (§17).

### Size / time-of-day breakdown

| | n | mean box area (px²) | median | small (<12,000px²) | larger |
|---|---:|---:|---:|---:|---:|
| real | 33 | 15,336 | 14,262 | 11 (33%) | 22 (67%) |
| false_positive | 37 | 14,119 | 11,197 | 22 (59%) | 15 (41%) |

False positives skew smaller than confirmed-real detections (59% vs. 33% under the 12,000px²
split) — consistent with small/subtle, poorly-resolved detections being more likely spurious.
Not a clean separator on its own (41% of false positives are still "larger" — including several
of the feeder-silhouette confusor cluster, whose box sits on real feeder structure, not empty
background), so this does not change the confidence-threshold conclusion above, but is a real,
disclosed texture for future confusor-suppression work to use (e.g. weighting suppression
confidence by subject size).

Night/low-light: only **2 of 70 events** (21:57 and 22:43 on 08-17, both `real_confirmed`) fall
outside 07:00–20:00. **Genuinely insufficient data to characterize night behavior** — reported
honestly as unresolved rather than extrapolated from n=2. All other real activity in this cohort
is daylight (11:45–22:43, concentrated 12:00–17:00).

## 6. Duplicate Visits / fragmentation / incorrect merges

Applied `mockingbird.observation.visit_episode_assembler.boxes_geometry_compatible` — the exact
production tolerance formula, imported directly, not reimplemented — to all 70 admitted-Visit
boxes/timestamps, union-find clustered with the same permissive `ambiguous_gap_ms=45000` window
`encounter_accounting` itself uses.

**Result: 70 clusters for 70 Visits. Zero multi-Visit clusters.** Independently confirmed by the
database itself: `visit_relationships` has 0 rows; `visits.is_superseded=1` count is 0, DB-wide.

Several visually-eyeballed "tight time gap" candidates (e.g. `-059`/`-060`, 33.7s apart, both
showing similar-looking birds) were checked directly and do **not** hold up under the rigorous
geometric test: centroid distance was well within tolerance, but box area changed 139% (vs. a
65% maximum), correctly kept separate rather than risking a false merge of what could plausibly
be two different birds visiting close together. This is a positive finding: Visit Continuity v1
holds up cleanly on a real, five-session, 70-Visit sample. **No incorrect merges found.**

## 7. Evidence-quality audit

- `identification` (primary high-resolution) evidence: 70/70 present, real files, native
  3840×2160 confirmed by direct inspection (not a downscaled derivative silently mislabeled).
- `classifier_same_frame` supporting evidence: **69/70 (98.6%)** present — a strong, positive
  extension of the accepted Same-Frame Species Evidence v1 result into a much larger live sample.
- `alternate` (14) / `context` (5) evidence: spot-checked, all real files, correct dimensions,
  no corruption.
- **Confirmed evidence-quality failures, directly caused by §5's admission-precision gap rather
  than a separate bug**: five admitted Visits present a species identification at ≥0.9 confidence
  whose actual evidence image contains no animal at all (`-019` House Finch 0.94, `-022` House
  Finch 0.99, `-027` House Finch 0.95, `-032` House Finch 0.95, `-036` Mourning Dove 0.99 — the
  last independently confirmed via full-frame inspection showing bare shadowed grass; the other
  four sit on the same recurring feeder-silhouette confusor cluster identified in §5). This is
  real, disclosed "the best evidence does not actually contain the animal" per this milestone's
  own required check, at a materially higher rate than initially estimated — not hidden, not
  softened (see §2's disclosed recheck-pass correction for why the first-pass count was lower).
- No case was found of the UI silently displaying missing media as though evidence existed —
  every evidence file referenced actually exists and decodes.

## 8. Detector: retain production MDv5 (state A reconfirmed, two new independent evidence lines)

**Independent re-verification of existing evidence (unchanged, still valid):**
- `detector-promotion-benchmark-report.md` state A (MDv5 native retained): corpus manifest,
  production MDv5 weights, and the RF-DETR Stage-2 checkpoint were all independently
  re-hashed this session; every SHA-256 matches the documented value exactly. Nothing has drifted.
- `data/training/wildlife-stage2/evaluation-report.json`: RF-DETR Stage-2 on the frozen 75 —
  precision .0405, recall .107, FP 71, FP/negative-frame .861 vs. MDv5 native's .278 — decision
  `PIPELINE_PROVEN_MODEL_WEAK`, independently confirmed still valid.

**New evidence this milestone — fresh hard-negative/positive-control comparison** (real GPU
inference, both models re-run full-frame from scratch, `data/evaluations/observational-quality-closure-v1/hard-negative-comparison/`):
6 of this session's own freshly-confirmed real hard negatives (incl. the roof-shadow and
driveway-edge confusors) + 5 real positive controls.

| | MDv5 (production, thr 0.1) | RF-DETR Stage-2 (thr 0.3, checksum-verified checkpoint, correct resolution=768) |
|---|---:|---:|
| Hard negatives correctly rejected (no detection) | **5/6 (83%)** | 1/6 (17%) |
| Hard negatives that still fired somewhere in frame | 1/6 | 5/6 (83%) |
| Positive controls correctly detected at/near location | 1/5 | 1/5 |
| Positive controls detected elsewhere in frame | 3/5 | 2/5 |
| Positive controls missed entirely | 1/5 | 2/5 |

RF-DETR Stage-2 is worse than production MDv5 on both axes, on a completely fresh, independent
set of confusors from a different session/scene than either model's own training/tuning data.
Deeper visual verification found RF-DETR Stage-2's dominant false-positive mode here is a
**parked vehicle** in the driveway (8/9 of its false detections) — a different confusor family
than the ones causing the real production false positives, i.e. not a fix for §5's problem
either. **This is a second, independent line of evidence confirming state A.**

**Decision: RETAIN production MDv5 native at threshold 0.1. No promotion.** Neither the existing
frozen-75 comparison nor this milestone's fresh hard-negative comparison shows any evaluated
challenger dominating the incumbent. State A per `detector-promotion-benchmark-contract.md`.

## 9. Fresh field session (priority-1 evidence)

Attempted, per the task's explicit priority order, and given real, disclosed effort rather than a
token attempt — but **did not produce a completed fresh session within this milestone's practical
time bounds**, for a specific, diagnosed, dev-tooling-only reason distinct from anything this
report's conclusions rely on:

1. A background deploy of the exact starting HEAD (`797db8f`) to the Windows/GPU sandbox was
   started early in this milestone, intended to run a bounded ~90-minute Observation session in
   parallel with the rest of this investigation.
2. That attempt failed with: `797db8f already exists but does not match a ledger entry for
   commit ... -- refusing to overwrite another release directory` — a real, fail-closed dev-
   tooling safety check (`scripts/deploy_windows_dev.py`) correctly refusing to clobber an
   orphaned, partially-built release directory left over from the attempt's own earlier retry.
   Confirmed by direct inspection nothing was running from that stale directory (safe to remove:
   it contained only a partial `python/` subtree, no complete build).
3. Removed the stale directory and retried. The retry progressed cleanly past the point of the
   first failure (rebuilding the frontend, the wheel, and the full win_amd64 dependency closure
   including the ~1.7GB BioCLIP/torch/CUDA stack) but was still in a long, low-CPU disk-I/O-bound
   copy phase — consistent with a genuinely large cross-filesystem (WSL↔Windows) file copy, not a
   hang — when this report was finalized, without yet producing a running, verifiable instance.

This is a **developer-tooling-only** finding (`scripts/deploy_windows_dev.py` is explicitly
out-of-product-scope per `AGENTS.md`'s conditional-document router: "no product behavior
change"), not a product defect, and is unrelated to any conclusion in this report — every other
finding above rests on the extensive, real, already-existing priority-2 evidence (§1), which
proved sufficient on its own for a responsible, well-evidenced decision. Recorded honestly as an
incomplete attempt rather than silently dropped, with the exact diagnosed cause so a future
session does not have to re-discover it: a stale, unregistered release directory can block a
subsequent deploy of the same commit; `rm`/`Remove-Item` it first if `--status` shows the target
commit was never successfully registered as deployed.

## 10. Training decision

**No training performed or required this milestone.** The existing Stage-3 correction path
(`docs/wildlife-detector-training-contract.md` "Stage-3 correction Tranche A") remains exactly
where the 2026-08-12 Multi-Scene Backyard Domain Acquisition milestone left it: a real 700-frame
tranche is selected and ready, but genuinely 0/700 reviewed (verified this session — the review
packet's `annotation.json` is byte-identical to its documented clean-reset state), and the
multi-scene/Holdout-v2 capture plan requires physically relocating the camera — an operator
action, not something this or any automated session can or should fabricate. This milestone's own
evidence (§5, §8) does not change that calculus: the real defect found (admission-precision /
recurring static confusors) is **not a detector-recall problem a better-trained model would fix**
— it is an architecture/policy gap, independently confirmed by RF-DETR Stage-2 (already trained
on 8,000 target-domain images) performing *worse*, not better, on exactly these confusors (§8).
No case exists this milestone for prioritizing Stage-3 review/training over the confusor-suppression
work §5/§12 actually calls for.

## 11. Species suggestion quality

**Truth-set size is genuinely small: 1 human-reviewed case** (`visit-observation-candidate-037`,
`house_finch`, matches the system's own suggestion at 0.95 confidence — correct). This is an
honest, disclosed, real limitation this milestone did not solve (collecting genuine human review
requires the product's real user, not this investigation). Supplementary, explicitly
non-authoritative agent-diagnostic visual cross-checks (§2's same review) were used to
characterize behavior further, never as truth:

- 20/70 (29%) of Visits in the cohort have any automatic species suggestion at all — most
  (50/70) show `no_suggestion`; automatic identification is a bounded/rate-limited assist, not
  generated for every admitted Visit today (an honest "unavailable" outcome, not a bug this
  milestone found reason to change).
- Of the 20 with a suggestion, cross-referenced against the (corrected, §2) visual ground truth:
  **9 back a real animal, 11 back a false-positive Visit** — species suggestions are, if
  anything, slightly *more* likely to have been generated on a false Visit than a real one in
  this cohort (an artifact of which events happened to get suggestions, not a claim about
  suggestion accuracy itself).
- BioCLIP's own (explicitly uncalibrated) top-1 score: mean = **0.936** when backing a real,
  independently-confirmed animal; mean = **0.634** when backing a confirmed false positive. A
  real gap, but **much weaker and less clean than an earlier pass of this same analysis
  suggested** (initially 0.955 vs. 0.418, before the §2 recheck reclassified several
  high-confidence "House Finch" calls from ambiguous to confirmed-false) — correcting that
  overstatement plainly rather than keeping the more flattering number. **Five of the eleven
  false-positive suggestions sit at ≥0.9 confidence** (`-019` House Finch 0.94, `-022` House
  Finch 0.99, `-027` House Finch 0.95, `-032` House Finch 0.95, `-036` Mourning Dove 0.99) —
  species-suggestion confidence is a real but unreliable signal for "is this actually an animal,"
  not something safe to lean on for admission or filtering decisions without further work.
- Difficult sibling cases among the real suggestions: House Finch vs. Carolina Chickadee vs.
  Tufted Titmouse (all small, similarly-proportioned brown/grey backyard birds) account for most
  of the spread; consistent with the existing 14-species "Backyard Core" candidate pack's own
  known difficulty profile, not a new finding.
- Abstention: BioCLIP has no abstention path (architecture.md stage 12, still true) — it always
  returns a ranked top-k over its fixed candidate bank, even for an empty/no-animal crop, which
  is exactly how five separate empty-frame Visits each still received a specific, confident,
  wrong species name.

**Species-input decision:** unchanged. Truth-set is too small (n=1) to respectably validate
top-1/top-k accuracy at the confidence the milestone envisioned, and this remains open work
(consistent with the Phase 2 exit condition already on record: "the representative 30-100 example
species-level correction truth... never completed"). Flagged plainly, not glossed over.

## 12. Resolution-aware species inference (roadmap item, executed for the first time)

Real BioCLIP inference (not simulated) on 8 real crops spanning a size range (64×150px to
206×88px), comparing native highest-resolution crop (A), the genuinely-lower-native-resolution
same-moment `classifier_same_frame` crop (B), 2× Lanczos interpolation of B (C), and a synthetic
4×-degrade-then-4×-recover case (D):

1. **2× interpolation (C) never materially differs from its own un-interpolated base (B)** in any
   of 8 cases — confirms the expected null result: conservative interpolation adds no real
   information. Does not clear "must improve... without increasing confident false IDs" because
   it is a no-op, not an improvement. **Not adopted.**
2. **4× downsample-then-recover (D) is consistently worse** — flips to a different, usually
   lower-confidence or wrong label in 6/8 cases. Confirms real information loss cannot be
   recovered by interpolation. **Not adopted; validates existing doctrine ordering.**
3. **Genuinely surprising, disclosed finding:** for the one case with real human-reviewed ground
   truth (`-037`), the *native-highest-resolution* `identification`-burst crop gives the WRONG
   species (Carolina Chickadee, 0.56) while the lower-native-resolution `classifier_same_frame`
   crop gives the CORRECT one (House Finch, 0.97, matching the human reviewer). The same
   direction (same top label, much lower confidence from the higher-res asset) repeats for `-021`
   and `-026`. Most likely a capture-**timing**/pose-alignment effect — the `identification`
   burst is captured measurably later than the `classifier_same_frame` analysis frame (already
   documented in `same-frame-species-evidence-contract.md`) — rather than a pure resolution
   effect; three other cases (`-038`, `-059`, `-065`) show the reverse or genuine disagreement. n=8
   (n=1 ground truth) is too small to change the default classifier-input asset, but is recorded
   here as a specific, evidence-motivated lead for a future species-quality milestone, distinct
   from (and not resolved by) the interpolation question this experiment does answer.
4. **Multi-frame/burst reconstruction (E):** not attempted — no existing tooling makes this a
   bounded evaluation within this milestone's scope, and finding 3 above suggests any future work
   here should investigate frame *selection/alignment* before frame *fusion*.

**Final resolution-aware decision: native evidence remains canonical; no interpolation or SR
stage is added.** The one open, disclosed lead (finding 3) is a documentation/roadmap item, not
an implementation this milestone.

## 13. Place/report semantics

`mockingbird.analytics.place_activity_report` (the one deterministic computation path, confirmed
unchanged and still the sole path) has **no independent Visit-level deduplication of its own** —
it counts 1:1 from `VisitModel` rows via the same canonical resolver `zone_insights` already
uses. §6 found zero duplicates in this cohort, so duplication is not currently distorting counts.
§5's false-Visit rate, however, **is** a live, current, non-hypothetical distortion risk for any
Visit-count-derived report figure (confirmed/provisional/unresolved taxa counts, zone/hour
patterns) the moment species suggestions or reviews accumulate on a false-positive Visit — exactly
the downstream consequence of §5, not a separate defect. Coverage (`coverage_ratio`) is
structurally immune (computed purely from `MonitoringExposureIntervalModel` frame checkpoints,
never from Visit counts) — confirmed unaffected either way. No code change made; this is recorded
as a known, disclosed consequence of the still-open §5 finding.

## 14. Benchmark / holdout contamination check

- `data/evaluations/detector-promotion-v1/` (frozen 75) and `data/training/` (all wildlife-stage
  corpora): confirmed untouched by this milestone (`find ... -newer <session-start-marker>`
  returned nothing; `git status --short` unchanged from session start plus only this milestone's
  own doc/report edits).
- All new evidence this milestone (visual adjudication, hard-negative comparison, resolution
  experiment) was written under a new, clearly-separated, gitignored path
  (`data/evaluations/observational-quality-closure-v1/`) and a session scratchpad — never merged
  into any training or frozen-benchmark manifest, never presented as reviewed truth, never
  eligible for the classifier training manifest (§11's agent-diagnostic labels, even if any were
  written, cannot flip `review_status` — `review_provenance.is_authority_eligible("agent_diagnostic")
  == False`, verified directly in code this milestone).
- No private field evidence was published externally; this report and its linked data stay local,
  per the field-testing/publication doctrine.

## 15. Tests and validation

No source code was changed this milestone (documentation only: this report,
`docs/roadmap.md`, `docs/detection-quality-accounting-contract.md`). Per Tier 0 (docs/scope)
this needs only diff/link/terminology review, but per the milestone's own instruction the Core
gate was run anyway to confirm the repository baseline is healthy at closure:

**`python scripts/verify_core.py`: 3106 passed, 1 failed, 10 deselected, 11 xfailed in 571.72s
(~9.5 min)** — matches the documented ~9-minute Core baseline runtime closely.

**The one failure, root-caused, not hand-waved:**
`tests/test_stream_playback_contract.py::test_dashboard_summary_uses_reviewed_truth_and_bounded_safe_visits`.
Traced directly: its fixture, `add_dashboard_today_visits`, captures real wall-clock
`local_now = datetime.now().astimezone()` once and builds several visits at fixed
minutes-ago offsets (up to 45 minutes) before that instant, then asserts they all fall within
`dashboard_summary`'s `[local_day_start, next_local_day_start)` "today" window computed from
that same `local_now`. `dashboard_summary` itself was read directly and confirmed correct — it
consistently derives `local_now`/`day_start`/`day_end` from the one `now` parameter passed in,
never a second independent wall-clock call. The fixture, however, has a real, narrow blind spot:
if the suite happens to run within the first 45 minutes after **local** midnight, subtracting up
to 45 minutes from `local_now` pushes one or more of its "reviewed today" visits into the
*previous* calendar day, outside the very "today" window the test itself computes from the same
`local_now` — an honest test-fixture edge case, not a `dashboard_summary` bug. Confirmed directly,
not assumed: this run's real local time (`America/New_York`) was **00:29**, i.e. **29 minutes
after local midnight** — inside the fixture's own 45-minute vulnerable window, and the local
calendar date genuinely rolled over from 2026-08-18 to 2026-08-19 during this milestone's own
session. This is a real, pre-existing, extremely narrow (≤45-minutes-past-midnight,
local-timezone-dependent) test-fixture timing gap, coincidentally triggered by this session's own
real elapsed wall-clock time crossing midnight -- not a regression this milestone introduced (zero
source files changed) and not reproducible outside that narrow window. Left as a disclosed,
out-of-scope finding rather than "fixed" under this docs-only milestone's own change scope; a
future test-suite-hygiene pass should either freeze/inject `now` in this fixture or pad its
lookback bound, matching this project's own established "root-cause every failure, never assume
precedent" discipline (`test-suite-validation-tiers-contract.md`).

No model-specific benchmark/promotion acceptance run was required (no detector/species model
change was made — §8/§12 both concluded RETAIN with existing-plus-fresh diagnostic evidence, not
a new benchmark run against the governed corpus). `verify_full.py`/Tier 4 hardware acceptance were
not run — no production detector/species behavior, shared observation semantics, or
packaging/dependency-closure code changed this milestone, so Core is the correct, sufficient tier
per `development-workflow.md`'s escalation rules.

## 16. Roadmap update

See `roadmap.md` "Current status" (new bullet) and "Remains for this phase" / "Next recommended
implementation milestone" (updated). The full pre-v0.1 sequence is preserved unchanged:

1. Observational Quality Closure — this milestone
2. Report-First / Everyday Product Completion
3. Production Contracts Closure (observability/diagnostics, storage/retention, API/schema
   compatibility, critical accessibility/mobile, compatibility/support matrix)
4. RC / clean-machine / real-hardware acceptance
5. small invite beta
6. public OSS/release closure and v0.1

Retained (not forgotten): calm digests/notifications, visit stories, first-hour success, support
diagnostics, public release/CI/LICENSE/SECURITY work. Preserved as intentionally later unless
evidence changes: broad Place Intelligence, Place Journal, Year in Your Yard, audio/BirdNET,
eBird/iNaturalist, external NVR/home-automation adapters, edge inference, appliance image, Zero
2 W characterization.

## 17. Decision

**B — ONE BOUNDED OBSERVATIONAL DEFECT REMAINS.**

Genuine encounter recall (from the existing, still-valid Aug-17 funnel plus the already-closed
admission-recall fix) and Visit-continuity/duplicate correctness (§6, freshly and rigorously
re-verified at five sessions' scale) are in good, evidenced shape. Detector and resolution-aware
species decisions are both confirmed correct by fresh, independent evidence this milestone
specifically generated (§8, §12) — no model change is warranted or would help. But **Visit
quality is not yet strongly enough supported for external testing as-is**: on independent,
rigorously double-checked visual review, **slightly over half (52.9%, 37/70) of what the product
currently admits as a reviewable Visit is not a real animal**, concentrated in a small,
identifiable number (6, covering 76% of the false positives) of recurring static scene confusors,
and this milestone directly tested and ruled out the obvious fix (confidence gating, on both raw
detector confidence and species-suggestion confidence) rather than merely asserting it wouldn't
work. This is worse than this report's own first-pass estimate (34.3%) — the correction is
disclosed in full in §2 rather than quietly using the more flattering number, and it does not
change the qualitative diagnosis, only its severity: a specific, bounded, fixable stage defect
(admission has no static-confusor suppression capability) with a scoped, describable next
milestone (§5/§16 roadmap) — not a model problem, not an open-ended campaign, and not a reason to
withhold the encounter-recall and species-quality findings that ARE solid. Given the corrected
severity (a majority, not a third, of admitted Visits), this defect should be treated as a
**precondition** for broader external beta exposure, not a parallel-track follow-up — the rest of
this milestone's findings support proceeding once it is closed.
