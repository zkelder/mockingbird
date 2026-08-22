# Detection & Species Model Benchmark / Promotion v1 — Report

Date: 2026-08-22
Starting HEAD: `cb6eb20c7d95ebe6cd2fc573d69348cb2793842a` ("Pre-Freeze Operability
Gap Closure v1"). Starting schema: 42 (unchanged by this milestone — no
migration needed).

This is the deliberately-last pre-v0.1 milestone: determine, from governed
real MockingBird evidence, which detector + species-identification
configuration should ship in public v0.1.

## Decision

**D — INCUMBENTS RETAINED AFTER BENCHMARK; READY FOR FEATURE FREEZE.**

Production MDv5a (ONNX, threshold 0.1) and production BioCLIP-2 (with the
2026-08-21 Identification Eligibility + Abstention v1 policy) both remain the
strongest supported choice. Seven real detector candidates and three real
species candidates were benchmarked against governed real MockingBird
evidence; none earned promotion. One species candidate — BioCLIP 2.5
(ViT-H/14) — produced genuinely promising, real, evidence-backed results and
is recorded as the strongest lead for a future, dedicated calibration
milestone, but its own calibration is measurably unresolved (see §C7) and it
is **not** promoted in this milestone. No release-blocking perception defect
was found. **v0.1 feature freeze is now declared** (§ Release state, and
`docs/roadmap.md`).

---

## Part A — Benchmark contract and incumbents

### A2. Exact production incumbents

**Detector**: MegaDetector v5a (`MDv5a.0.1`), YOLOv5-family, ONNX opset 18,
raw pre-NMS decode (`megadetector_v5_yolov5_raw_v1`). Weights SHA-256
`b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc` (source
PyTorch checkpoint SHA-256
`fe3e90e4b1955821ab7c1f88b446dc0c8cb25e109fdd1872916a55305294a5ef`), pinned
in `scripts/build_local_product.py` and verified fail-closed at load
(`OnnxModelBundle.load`, `mockingbird/observation/onnx_provider.py`). MIT
license. Input 1280×1280, letterbox, RGB, scale-only normalization
(1/255). Score threshold **0.1**, NMS IoU 0.45, max 300 detections. Runtime:
ONNX Runtime GPU 1.28.0, **CUDA-only, no CPU fallback** (`disable_cpu_ep_fallback=1`,
post-hoc execution-provider verification). 3 broad classes: animal/person/vehicle
— no species/bird-specific logic. Feeds tracking via
`FrameDrivenObservationProvider.observe_live_frame` →
`CandidateVisitAuthorityAdapter.attempt_candidate` → the authority gate →
`ProductRepository.create_candidate_visit_from_proposal`.

**Species**: BioCLIP 2 (Imageomics `imageomics/bioclip-2`, HF revision
`2957b322090f9cb17ae72c71981c7218a28d81e0`, MIT), ViT-L-14, weights SHA-256
`b7b2bf6fbc95799e42630e394cf95803892ab447c1a8ab629dbc82fbeaf7dfef` (re-verified
directly this session — matches). Hand-built `open_clip` adapter
(`mockingbird/species/bioclip_adapter.py`), **CPU-only enforced**
(`BioClipConfigurationError` if `device != "cpu"`). Closed 14-species
"Backyard Core v1" candidate pack (Northern Mockingbird, Carolina Wren,
Mourning Dove, American Robin, Northern Cardinal, Blue Jay, Tufted Titmouse,
Carolina Chickadee, House Finch, Eastern Bluebird, Red-bellied Woodpecker,
Downy Woodpecker, Brown Thrasher, Gray Catbird) — real, structural, bird-only,
no 15th "none of these" class. Score kind: `candidate_relative_softmax`
(uncalibrated). Crop resolver (`species/classifier_input.py`) prefers, in
order: persisted subject crop → native-resolution (`resolution_provenance
== "synchronized"`) subject box → exact-same-frame subject box → full-frame
fallback. Current calibration: **Identification Eligibility + Abstention v1**
(accepted 2026-08-21, Decision A) — `subject_focused` tier score_floor=0.70/
margin_floor=0.20; `full_frame` tier score_floor=0.85/margin_floor=0.40;
evidence-eligibility floor 32px. Re-ran `scripts/benchmark_identification_
eligibility.py` fresh this session: **all mandatory cases still pass** (exit
0), confirming no drift since acceptance.

Both incumbent facts were independently re-verified this session (hash
recomputation, fresh benchmark reruns), not taken on faith from prior
documentation.

### A3/A4. Benchmark governance and evidence used

No public benchmark corpus exists (`docs/public-benchmark-governance.md`:
"Status: Governance only. No public benchmark or training corpus has been
released under this document" — reconfirmed accurate this session; not
changed, see Part G). All evidence below is governed, real, local, gitignored
`data/` material:

- The 70-frame reviewed detector-calibration cohort (`data/benchmarks/
  detector-calibration/`, manifest fingerprint
  `f9a589b203258dd4dff765124232e7e00fab0a1e580740699141c95ff5a88199`) — 28
  scorable positive, 36 scorable negative, 6 ambiguous, prohibited from
  training use.
- The 75-image Detection/Localization Model Benchmark v1 corpus
  (`data/evaluations/detector-promotion-v1/corpus-manifest.json`, semantic
  fingerprint `24bef2dabb37cff8dd4ae984135721aa90647294e2bded0a6e7f83fbdf6bacec`)
  and its 2026-08-11 report (already-closed prior evidence, reused not
  re-litigated where nothing changed).
- The real archived 2026-08-11 "apparent nuthatch" cohort (Visits
  011–018, `data/field-acceptance/2026-08-14-subject-centric-species-crop/`)
  — real images, independently re-viewed by this session (not merely cited),
  correcting one filename↔Visit-ID mapping error made mid-session before any
  score was recorded (see §C1).
- Visits 139/140 (real person+dog admission false positive), real images at
  `data/media/imports/media-asset-{139,140}-live-motion-best-frame.jpg`.
- The real, live local product database (`data/mockingbird.sqlite3`, schema
  42): 235 Visits, 58 human-reviewed, spanning real field capture
  2026-07-15 through 2026-08-08 (2 earlier 2026-01-15 rows are bundled
  demo/seed fixtures, excluded).
- A second, independent, fresher real database (a read-only copy of the
  live Windows dev-deployment DB, schema 35, 190 Visits, 452/460 media
  assets carrying real `geometry_attribution_json`) — used only for the
  structural multi-frame-candidate-availability question in §C3, where its
  richer, more current attribution data is the more informative source; never
  opened with the schema-aware `ProductRepository` (would have attempted a
  35→42 migration on a real product database copy), only raw read-only SQL.
- The real, governed Stage 6.2/6.3 detector-calibration/candidate-comparison
  pipeline (`mockingbird.observation.detector_benchmark`/`detector_comparison`)
  and the detector-promotion-v1 pipeline (`detector_promotion.py` +
  `scripts/run_detector_candidate_benchmark.py`) — both reused unmodified.

Contamination: the 75-image and 70-image corpora are the existing frozen
holdouts; nothing was trained or tuned against them this session. The
Stage-3 wildlife local-correction tranche (700 frames) explicitly excludes
all frozen-benchmark-contaminated frames (0 exact, 0 near-duplicate on
re-verification, per the existing Stage-3 report).

---

## Part B — Detector benchmark

### B1/B2. Candidates and results

Seven real candidates evaluated against the incumbent on the same reviewed
cohorts, across two runs (2026-08-05/08-11 prior work, reused where nothing
changed since; new 2026-08-22 work this session for redwood + a fresh
reproducibility pass):

| Candidate | Architecture / license | Precision | Recall | FP/negative frame | Verdict |
|---|---|---:|---:|---:|---|
| **MDv5a (incumbent)** | YOLOv5, ONNX, MIT | 0.270 | 0.357 | 0.278 | — |
| MDv1000-spruce | YOLOv5s-compact, ONNX, GPL-3.0 | 0.097 | 0.107 | 0.611 | worse (recall/precision/FP all worse); rejected 2026-08-05 |
| MDV6-apa-rtdetr-c | RT-DETRv2 R18, Apache-2.0 | 0.111 | 0.179 | 0.417 | worse; no threshold dominates MDv5 |
| MDV6-apa-rtdetr-e | RT-DETRv2 R101, Apache-2.0 | 0.051 | 0.071 | 0.583 | worse |
| RF-DETR Small (generic) | RF-DETR, Apache-2.0 | 0.333 | 0.036 | 0.028 | precise only because it largely abstains; misses nearly every real bird |
| RF-DETR Stage-1 (wildlife-tuned) | RF-DETR, local fine-tune | 0.500 | 0.071 | 0.028 | `PIPELINE_PROVEN_MODEL_WEAK`; F1 0.125 vs MDv5's 0.308 |
| RF-DETR Stage-2 (wildlife-tuned, corrected) | RF-DETR, local fine-tune | 0.041 | 0.107 | **0.861** (31× Stage-1) | `PIPELINE_PROVEN_MODEL_WEAK`; precision collapse, real-camera domain gap |
| **MDv1000-redwood (new, this session)** | YOLOv5x6, ONNX opset 18 (dynamo exporter), GPL-3.0 | **0.400** | **0.071** | **0.028** | mixed: better precision/FP, far worse recall (89.3% total miss rate vs MDv5's 46.4%); no threshold dominates |

Redwood detail (new real evidence this session): 140,054,656 parameters,
575 layers, 208.8 GFLOPs, stride 64, image size 1280 — a genuinely different,
much larger architecture than spruce (not a simple rescale). ONNX export
(opset 18) required adding `onnxscript` to `.venv` (torch 2.13's dynamo
exporter default — a real, disclosed, environment-only fix, not a
redwood-specific defect). Parity check passed: max abs diff 0.00177, mean
abs diff 1.05e-5 (same order as spruce's own 0.0012/6.9e-6). License:
independently re-verified via the real official release-notes table
(`agentmorris/MegaDetector` `docs/release-notes/mdv1000-release.md`) —
`YOLOv1000-redwood | YOLOv5x6 | ... | GPL` — GPL-3.0, same restricted class
as spruce (local shadow evaluation only, not redistributable).
`final_recommendation: continue_candidate_shadow_evaluation` (mixed
evidence) from the real Stage 6.3 comparison tool — not `retain_mdv5_baseline`
(both-worse) and not a shadow-ready verdict either, exactly reflecting the
precision-up/recall-down tradeoff. Full 9-point threshold sweep confirms
redwood's ceiling recall across every tested threshold is 0.107 — never
approaches MDv5's 0.357 recall at any operating point.

Static-scene (shepherd's-hook) hard negative: redwood is the only tested
candidate with **zero** clustering false positives of any kind (vs. MDv5's 4
hook-affected frames) — a genuine, real strength, but it comes at the cost of
missing 25/28 reviewed real animals outright.

### B3. Product-level replay

Not run for a new candidate this session. Every detector challenger already
loses decisively at the raw-detection stage (recall is the harder,
higher-priority v0.1 gate per product doctrine); a weaker detector cannot
produce better downstream Visits than a stronger one feeds it, so a full
funnel replay would not change the verdict and was not worth the engineering
cost of wiring a new candidate provider into the replay harness for this
milestone. The existing, extensive real field record (15+ field-acceptance
milestones, most recently the 2026-08-19/20 cache-128 and end-to-end-recall
closures) already documents MDv5's real product-level Visit-creation/FP-burden
behavior in the full pipeline; that evidence stands unchanged.

A real, previously-undiscovered defect was found and fixed while preparing to
use this harness: `mockingbird.observation.perception_regression_cli` had no
`if __name__ == "__main__":` guard, so the exact invocation
`docs/perception-replay-regression-harness-contract.md`'s own "Commands"
section documents (`python -m mockingbird.observation.perception_regression_cli
run ...`) silently imported the module and exited 0 without running anything.
Fixed with a two-line guard; a new subprocess-based regression test
(`test_module_invocation_matches_documented_usage`) proves the documented
command now genuinely works end to end. The already-deliberate absence of a
top-level `python -m mockingbird` subcommand for this harness (a separate,
explicitly-deferred decision recorded in the same contract) was left
untouched — not this milestone's to relitigate.

### B4. Threshold/calibration sweep

Every candidate's full threshold grid was already swept (spruce: 9 points;
MDV6-C/E, RF-DETR-S: bounded sweeps in the 2026-08-11 report; redwood: 9
points, new this session). No candidate has an operating point that
dominates MDv5's 0.1 (precision 0.270, recall 0.357) on precision AND recall
AND FP-burden together. Example: MDV6-C at 0.30 reaches precision 0.400/
recall 0.143/FP-per-negative 0.111, while MDv5 at 0.40 reaches the same
precision and FP-burden at recall 0.214 — MDv5 still wins.

### B5/Part F. Hard-negative preservation and training correction

The accumulated hard-negative corpus (feeder hardware, branches/bark,
vegetation, shepherd's-hook, night/glare) is preserved unchanged in the 70/75
reviewed corpora. **No new training was performed.** The one real,
diagnosed local-domain weakness (RF-DETR Stage-2's 31× false-positive
regression on real MockingBird footage despite strong camera-trap-style
generalization) already has a bounded correction tranche built and staged
(Stage-3 Tranche A, 700 frames, `data/training/wildlife-stage3/`) — but it
has **0/700 named human reviews** completed. Per this repository's own truth
boundary (`docs/product-doctrine.md`: "Human correction remains the truth
boundary"; Stage-3's own contract: "no agent- or model-generated label may
enter this truth"), an AI agent reviewing these frames itself would not
produce legitimate training truth. Training correction is therefore **not
earned this milestone** — not for lack of a plan, but because the
prerequisite human review genuinely has not happened, and manufacturing it
would violate the exact doctrine this benchmark is required to respect. This
is unchanged from the Stage-3 report's own "exact next milestone."

---

## Part C — Species model benchmark

### C1. Candidates

Three real candidates evaluated against the incumbent (BioCLIP-2):

1. **SpeciesNet v4.0.3a** (`google/speciesnet`, Apache-2.0 — resolved this
   session, see below) — real, classifier-only component.
2. **BioCLIP 2.5 (ViT-H/14)** (`imageomics/bioclip-2.5-vith14`, MIT,
   released February 2026 per direct web search — a materially newer/larger
   BioCLIP-family release than the incumbent, confirmed not assumed) —
   downloaded and run for real this session.
3. Custom backyard classifier: not evaluated — none exists yet
   (`custom-bird-classifier-dataset-plan.md` remains a future path, no
   trained artifact to benchmark).

**SpeciesNet's licensing blocker is resolved.** `docs/speciesnet-source-review.md`
previously stalled on "model-weight license unresolved... not confirmed from
static Kaggle access." The real downloaded artifact
(`~/.cache/kagglehub/models/google/speciesnet/pyTorch/v4.0.3a/1/README.md`)
carries an explicit frontmatter declaration: `license: apache-2.0` —
independently verified this session, not assumed from the earlier
uncertainty.

### C2/C5. SpeciesNet result (real evidence, including the nuthatch cohort)

Built `src/mockingbird/species/speciesnet_candidate.py` (pure, 29 new tests)
+ `scripts/benchmark_speciesnet_candidate.py` (real inference runner) and ran
SpeciesNet's real classifier component
(`always_crop_99710272_22x8_v12_epoch_00148.pt`, 2,498-class open taxonomy)
against the exact real evidence already used to accept BioCLIP-2's
eligibility/abstention policy: the 8-Visit "apparent nuthatch" full-frame
cohort (Visits 011–018), its 4-Visit subject-crop supplement, one real
same-frame House Finch positive control (Visit 019), and Visits 139/140.

**Two real, methodologically important findings before scoring:**

- Feeding SpeciesNet a raw full frame with `bboxes=None` (matching BioCLIP's
  own honest full-frame fallback) makes it call **"blank" at 92–100%
  confidence on every case**, including frames with a real, visible bird —
  because this checkpoint's `always_crop` architecture is co-designed with
  its *own* bundled MegaDetector-cropping stage and effectively never sees a
  legible subject in an un-cropped 3840×2160 frame. Re-running with
  MockingBird's own real MDv5 detector box supplied (`normalized_track_box`,
  independently extracted per-Visit from real geometry-inventory data) did
  not materially change this — SpeciesNet still called "blank" on 6/8 boxed
  full-frame cases.
- On the **fair, product-realistic comparison** (MockingBird's own real
  padded subject crop — the same evidence tier BioCLIP-2 actually uses in
  production): SpeciesNet's best answer was a generic, correctly-class-level
  but non-actionable **"bird"** (`aves;;;;;bird`, 26–55% confidence, real
  species like `house finch` not even reaching its own top-5) on all 4 real
  House Finch crops, where BioCLIP-2 correctly and confidently named the
  species (92.5–99.9%).

Real tally (17 scored cases across both full-frame variants + crops + the
Visit-019 control): **SpeciesNet correct on 0/17; BioCLIP-2 correct on 5/17**
(every case where a real bird was clearly evidenced). SpeciesNet never beat
BioCLIP-2 on a single scored case.

Genuine SpeciesNet structural advantages, disclosed honestly: a real open
taxonomy including non-bird classes BioCLIP-2 structurally lacks (`human`,
`domestic dog`, `vehicle`, `blank`) and an inherent graceful-abstention
class (`blank`) — but on this real backyard-camera cohort that produced
"correctly declines to guess" rather than "correctly identifies," which
BioCLIP-2 + its already-accepted abstention policy already achieves *while
also* retaining real correct identifications. On Visits 139/140, SpeciesNet
also called "blank" (87.7%/89.5%) rather than a false-confident bird name —
a real safety property, but one BioCLIP-2's abstention policy already
matches in production outcome (both suggest nothing).

**Nuthatch/difficult-case result (C5), directly answered**: The literal
string "nuthatch" does not appear in any recoverable MockingBird evidence for
this cohort (an informal narrative label in later docs, not a
system-recorded observation) — likely because "nuthatch" is not one of
BioCLIP-2's 14 candidate labels at all, so the model was structurally
guaranteed to never say it even if right; SpeciesNet's real taxonomy *does*
carry real nuthatch species rows (`red-breasted nuthatch`, `white-breasted
nuthatch`), but SpeciesNet never surfaced them on any of these real photos —
its top-5 never came close. Per the milestone's own framing ("correct
suggestion OR principled abstention is acceptable"): **the currently-shipped
policy already achieves the acceptable outcome** — both archived hard cases
(Visits 011, 014) correctly abstain today, confirmed by a fresh rerun of
`scripts/benchmark_identification_eligibility.py` this session (exit 0, all
mandatory cases pass). Neither challenger model does better on this specific
real evidence; BioCLIP 2.5 (below) is the one candidate that materially
improves on it.

**Also worth taking one taxonomy nuance seriously, disclosed not glossed
over**: SpeciesNet's real 2,498-class taxonomy has no exact species-level row
for Carolina Wren either (only a genus-level `thryothorus species` rollup) —
its much larger label space is not a strict superset of MockingBird's 14
species; the two models have differently-shaped coverage gaps, not a
strictly-bigger-is-more-complete relationship.

**Verdict: SpeciesNet not promoted.** No case where it out-performed the
incumbent; its real, useful, structural non-bird/blank vocabulary does not
translate into better outcomes on MockingBird's actual real evidence.

### C1/C7. BioCLIP 2.5 (ViT-H/14) result — the genuinely new finding

Downloaded the real artifact (`open_clip_model.safetensors`, SHA-256
`ac2e37c2f89ef8e6b889176a9a3f418970ad9db15a218bd29e3321e95c46ae97`, MIT
license — confirmed via the real model card), built
`scripts/benchmark_bioclip25_candidate.py` (reuses the existing, tested
`identification_eligibility.evaluate_classification_abstention` directly,
since BioCLIP 2.5 shares the identical closed-set candidate-relative-softmax
convention — no new comparison module needed), and ran it against the same
real evidence: 5 subject-crop cases, 8 full-frame cases, 2 hard-negative
diagnostic cases (139/140).

**Real result, positive**: on the 4 real full-frame photos that produced the
"RBW-bias" nuthatch-difficulty cohort (Visits 013/014/016 — 3 of 4;
017 scored correctly but below even the (unvalidated) reused abstention
floor), BioCLIP 2.5 **correctly identifies House Finch without any subject
crop at all** (0.9893–0.9994 confidence) — cases the incumbent scored wrong
(0.369–0.645, `red_bellied_woodpecker`/`tufted_titmouse`) and could only
handle by abstaining. On the 5 subject-crop cases, both models are correct;
BioCLIP 2.5's scores saturate at 1.0000 (see calibration caveat below).
Real tally: **8/11 scored cases correct for BioCLIP 2.5 vs. 5/11 for
BioCLIP-2, 3 clear BioCLIP-2.5 wins, zero BioCLIP-2 wins.** Same MIT license
family as the incumbent — no new legal blocker. Real measured CPU latency
(the actual production deployment constraint — BioCLIP's adapter is CPU-only
enforced): **~1.11–1.17s/image vs. the incumbent's ~0.70–0.74s/image on the
same host (~1.5–1.6× slower)**; 986M parameters vs. the incumbent's 428M
(~2.3× larger, 3.94GB vs. 1.71GB on disk) — real, non-trivial but not
prohibitive costs (well inside the existing 120s per-attempt timeout budget).

**Real result, a genuine caveat that blocks promotion this session**: on the
same full-frame cohort, two visits with **no bird at all** (015, 018 —
independently re-confirmed by direct visual inspection, not merely cited)
produced a confident **wrong** bird name from BioCLIP 2.5 — `carolina_chickadee`
at **0.9975/0.9603 margin** and **0.9793/0.9603 margin** respectively. These
scores and margins are **not separable** from the real true-positive
full-frame scores (0.9893–0.9994, margin 0.979–0.999) — score and margin
both land in the same narrow, saturated band regardless of whether a bird is
actually present. This is a measurably *worse* calibration property at the
full-frame tier than the incumbent, whose real wrong full-frame answers
topped out at 0.817 — comfortably separated from where a genuine positive
would plausibly land. The crop-tier scores are also suspiciously saturated
at exactly 1.0000/0.0000 (likely softmax numerical saturation from a much
higher-dimensional, more separated embedding space rather than literal
100.00% certainty) — a real open question this session's evidence cannot
resolve either way.

**Verdict: BioCLIP 2.5 not promoted this milestone**, per Part E4's own
rule: reusing the incumbent's thresholds was an explicit *diagnostic*
reference only, never a real calibration, and the one real signal available
about what BioCLIP 2.5's *own* calibration would need to look like (full-frame
score/margin cannot separate true from false positives) shows that a
promotion would ship materially *under*-calibrated relative to the
incumbent, not merely un-calibrated. This is a genuinely strong,
real, evidence-backed lead — not a rejection on novelty or a forced
non-promotion — and is recorded as the concrete next candidate for the
already-planned, explicitly non-blocking "Species Classification
Re-evaluation / Promotion v2" milestone in `docs/roadmap.md`, with its own
proper full-cohort calibration study (mirroring the incumbent's own 36-case
Identification Eligibility + Abstention v1 study) and Windows/CPU packaging
validation before any real promotion decision.

### C3. Multi-frame candidate availability — re-checked with fresh data

Ran the real, existing, side-effect-free
`ProductRepository.species_multi_frame_candidate_plans` against every one of
235 real Visits in the current-schema (42) local database: **0/235 have any
candidate plan at all** (this specific database's real capture data — through
2026-08-08 — predates Same-Frame Species Evidence v1, landed 2026-08-14).
Cross-checked with a raw, read-only SQL query (deliberately not opened with
the schema-aware repository, to avoid attempting a migration on a real,
actively-used product database copy) against a materially fresher, richer
real database (schema 35, 190 Visits, captured through today): **171/190
Visits have exactly one real, proven same-frame candidate; 0/190 have two or
more.** This is a stronger, more current result than the prior "0/98"
finding, and it still points the same direction, for a now-confirmed
structural reason rather than an accumulation-rate guess:
`species_multi_frame_candidate_plans`'s own docstring states a real Visit can
supply "at most one same-frame asset" by Same-Frame Species Evidence v1's
explicit design — this is a single-frame architectural cap, not a
data-volume problem that more field time would fix. **Multi-frame consensus
remains correctly unpromoted** (`evaluate_multi_frame_consensus` stays
tested-but-unwired); promoting it would require a capture-architecture
change, which is out of this milestone's scope and not evidenced as needed.

### C4/C6. Species metrics, stratification, open-set behavior

Covered above per-cohort (clean/close via crop-tier; small/far — no new real
case exercises the resolution floor, unchanged limitation already disclosed
in the accepted eligibility report; native-resolution — the classifier input
resolver's tier order is unchanged and unmodified; difficult taxa — the
nuthatch/RBW-bias cohort above; hard negatives/non-bird — Visits 139/140,
both cohorts). Calibration/reliability: BioCLIP-family softmax remains
explicitly uncalibrated, candidate-bank-relative evidence, never presented as
probability — unchanged, reconfirmed for both BioCLIP-2 and 2.5. No model's
raw score was treated as calibrated confidence without real supporting data.

---

## Part D — Joint system evaluation

No combination search beyond incumbent+incumbent was run. Every detector
challenger (7) lost decisively at the raw-detection stage independent of any
species-side choice; every species challenger either lost decisively
(SpeciesNet) or is not yet safely calibrated (BioCLIP 2.5). Since neither
side has an individually-earned promotion, no combination of a
non-promoted detector with a non-promoted species model could be a defensible
joint choice — evaluating e.g. "redwood + BioCLIP 2.5" would test two
independently-unproven components against each other for no decision this
milestone could act on. Incumbent+incumbent (MDv5 + BioCLIP-2 with its
accepted eligibility/abstention policy) remains the only combination with a
real, extensive, positive field record (235 real Visits, 58 reviewed, the
full chain of 2026-08 field-acceptance milestones) and is retained.

Product-level outcomes (already governed, reconfirmed not re-derived this
session): real wildlife encounters do surface (58 reviewed Visits, real
species named); false-Visit burden is governed by Scene Confusor Suppression
v1 + Visit Authority Budget + the admission chain, already field-validated;
evidence contains the real subject (source-resolution/same-frame contracts
unchanged); species assistance makes honest suggestions and abstains
correctly on the nuthatch cohort (reconfirmed fresh this session); human
review remains fully authoritative and untouched by every benchmark run in
this milestone (all benchmark scripts are read-only/no-DB-write by
construction — verified structurally for the new `speciesnet_candidate.py`
module via an import-boundary test, and by direct code reading for the
BioCLIP 2.5 runner).

---

## Part E — Promotion policy applied

No artifact was promoted, so no rollback metadata needed to be created —
the existing incumbent artifacts, thresholds, and rollback path
(`docs/model-adapter-guardrails.md`: unset config, keep proposals as
evidence, preserve reviewed truth) are unchanged and remain valid. Every
non-promoted candidate's real artifact/config/benchmark report remains
retrievable under gitignored `data/` for a future session (never committed,
matching the existing convention for every prior candidate in this
repository).

---

## Part F — status

Covered in Part B5 above: Stage-3 correction tranche exists, is not human-reviewed,
and this milestone correctly declines to force it.

---

## Part G — Public benchmark governance

`docs/public-benchmark-governance.md` is reconfirmed accurate and current
(re-read in full this session): a complete, real 9-item governance doctrine
exists, and it explicitly states no public corpus has ever been released
under it. This milestone does **not** publish one — doing so would require
real per-item consent/license work (Privacy-Zone exclusion review,
per-image release-basis confirmation) that is out of scope for a benchmark
milestone and cannot be manufactured. No public-corpus performance claim is
made anywhere in this report; every number above is explicitly scoped to
MockingBird's own private, real field evidence.

---

## Part H — Deterministic regressions

New, real tests added this session (all passing):

- `tests/test_speciesnet_candidate.py` (29 tests, new): taxonomy parsing
  fail-closed on malformed input, taxonomic-agreement cascade (exact
  species/genus/family/order/different — including the real empty-species
  rollup edge case this session's own real SpeciesNet output exercised),
  case comparison verdicts, order-independent tallying, and a structural
  import-boundary test proving the module can never reach the product
  database/filesystem/model runtime (mirroring `test_acceptance_recorder.py`'s
  own established pattern for the same guarantee).
- `tests/test_perception_regression_cli.py::test_module_invocation_matches_documented_usage`
  (new): a real subprocess proof that the harness contract's documented
  `python -m mockingbird.observation.perception_regression_cli run ...`
  invocation now genuinely works (see §B3).

Existing coverage reused, not duplicated, for the rest of the 20-item list
this milestone's instructions named: incumbent config reconstructibility
(`OnnxModelBundle.load` fingerprint checks, `test_onnx_provider.py`),
benchmark dataset fingerprint determinism (`test_detector_calibration_
benchmark.py`, `test_detector_promotion.py`), contamination checks
(`wildlife.verify_frozen_benchmark`/`check_frozen_contamination`,
`test_wildlife_training.py`, `test_wildlife_stage3_tranche.py`), reviewed-
truth-only ground truth and provisional-suggestion-cannot-become-truth
(`review_provenance.is_authority_eligible`, `test_review_provenance.py`,
`EvaluationExample` governance, `test_evaluation_governance.py`), threshold-sweep
and false-positive-accounting determinism (`test_detector_calibration_
benchmark.py`), native-resolution-vs-analysis-fallback distinction and
no-interpolation-as-native (`test_native_resolution_species_evidence.py`,
`test_same_frame_species_evidence.py`), multi-frame candidate ordering and
consensus-disagreement-abstains (`evaluate_multi_frame_consensus`'s own
existing tests in `test_identification_eligibility.py`), model-specific
calibration versioning (`IDENTIFICATION_ELIGIBILITY_POLICY_VERSION`,
`identification_policy` provenance), comparison-ordering independence
(`detector_comparison.py`'s sorted-label-order guarantee, plus this
session's own new `test_tally_is_order_independent`), public/private
separation (no code path exists to promote a private artifact to public
status), hard-negative partitioning (Stage-2/3 contamination tests), no
benchmark mutates reviewed truth (every script this session is read-only by
construction, verified structurally), and model-unavailability failing
cleanly (`--skip-missing` graceful degradation with explicit non-zero exit
codes on missing prerequisites in both new benchmark scripts; the redwood
ONNX-export pipeline failed loudly and was fixed rather than silently
degrading when `onnxscript` was initially missing).

---

## Part I — Validation

Focused: `pytest tests/test_speciesnet_candidate.py tests/test_perception_regression_cli.py -q`
→ **36 passed**.

Tier-2 and Core gate: see the final chat report (run after this document was
written, so its exact pass/fail counts are not duplicated here to avoid a
stale copy — the chat report is authoritative for the exact numbers).

Benchmark reproducibility: fresh MDv5 rerun against the canonical 70-image
corpus this session reproduced the exact same semantic fingerprint as the
2026-08-05 historical run
(`4c58c1dda695200345cb5aa21446d658f170631971bde9602013f7c7e9d77201`) —
byte-for-byte, confirming the Stage 6.2 benchmark pipeline is genuinely
deterministic, not merely documented as such.

---

## Release state

**v0.1 feature freeze is now active** — declared in `docs/roadmap.md`
alongside this report. No release-blocking perception-quality defect was
found. From this point forward, only defect fixes, reliability, performance,
UX/accessibility polish, packaging, security, documentation, compatibility,
storage/recovery, field acceptance, clean-install/upgrade, and release
presentation work is permitted before v0.1, per the milestone's own
instructions — Gate F implementation is explicitly not started in this
session.

Preserved, not started: acoustic/BirdNET multimodal observation; LTE/
intermittent-WAN remote field capability (both explicitly named
post-v0.1/pre-v1 items in the governing instructions, untouched here).

Recommended next milestone (not started): Gate F (OSS/security/compat/
packaging readiness) is the roadmap's own next explicitly-open gate. A
second, smaller, clearly-optional candidate item — a bounded BioCLIP 2.5
calibration study, mirroring the existing 36-case Identification Eligibility
+ Abstention v1 methodology, informed by this session's real but partial
evidence — is recorded as the concrete lead for the already-planned "Species
Classification Re-evaluation / Promotion v2" milestone.
