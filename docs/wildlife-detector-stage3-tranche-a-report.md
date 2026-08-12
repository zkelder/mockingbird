# Wildlife Detector Stage-3 Correction Tranche A Report

Date: 2026-08-12
Decision: Tranche A built and ready for named human review; **no training run in this milestone**
Production authority changed: **no**

This report records construction of the first Stage-3 local domain-
correction tranche: a deterministic, deduplicated, contamination-checked
~700-frame subset of the existing 2,000-frame Stage-2 local-correction
queue, plus reviewer ergonomics and a readiness-accounting report. See
[wildlife-detector-training-contract.md](wildlife-detector-training-contract.md)
"Stage-3 correction Tranche A" for the governing contract this
implements, and [wildlife-detector-stage2-report.md](wildlife-detector-stage2-report.md)
Section 19 ("Exact next milestone") for the finding this responds to.

## 1. Starting point

Work started from committed baseline `20c665a0e40d0d764147a0481ee69113aedb9602`
("Complete Stage-2 wildlife detector training: resume, evaluate, decide
WEAK"). The existing 2,000-frame local-correction queue
(`data/training/wildlife-stage2/local-correction-queue.json`, queue id
`mockingbird-local-wildlife-correction-v0.2`, fingerprint
`93859bdb334cfaa8151e9c783492cd33e71282a36b994e9658b1205f00473b08`) was
consumed unchanged: 1,000 `likely_positive_requires_human_boxes`, 750
`static_clutter_negative_candidate`, 250 `weather_lighting_negative_candidate`.
The three pre-existing untracked small-bird-benchmark prototype files and
the four pre-existing `.orig` backup files were left byte-for-byte
untouched throughout.

## 2. Priority tiers actually populated

Counts below are *after* the frozen-contamination/Holdout-v2 pre-selection
exclusion (Section 5) -- the same candidate pool `select_tranche` actually
draws from, matching the `candidates_before_dedup` figures in Section 3.
Before any exclusion, the full 2,000-row queue classifies 43 (not 18) into
`known_detector_miss_or_localization_failure`, 957 (not 871) into
`small_far_opportunity`, 750 (not 679) into `feeder_hardware_confusor`,
and 250 (not 232) into `edge_condition`; `high_confidence_false_positive`
and `vegetation_or_shadow_confusor` are 0 both before and after. The gap
between each pre- and post-exclusion pair sums to exactly the 200 rows
Section 5 excludes.

| Priority tier | Rows classified (post-exclusion) | Feeds lane |
|---|---:|---|
| `known_detector_miss_or_localization_failure` | 18 | small/far positive |
| `small_far_opportunity` | 871 | small/far positive |
| `high_confidence_false_positive` | 0 (120 queue rows reach `max_animal_score >= 0.5`, but all 120 are already in the `likely_positive_requires_human_boxes` lane -- the source queue's own prioritization already routes high-confidence hits there; none land in either negative lane) | hard negative |
| `feeder_hardware_confusor` | 679 | hard negative |
| `vegetation_or_shadow_confusor` | 0 (every static-clutter row in this snapshot carries `recurring_static_geometry`) | hard negative |
| `edge_condition` | 232 | edge condition |
| `ordinary_negative_anchor` (backstop) | 0 (structurally unreachable -- every negative-lane row is already classified by the tiers above; kept as defense-in-depth, not exercised) | either negative lane |

Tiers 1+2 and 6+7 of the task's own nine-step list are honestly merged
(`known_detector_miss_or_localization_failure`, `vegetation_or_shadow_
confusor`) because this queue's rows carry no raw per-detection box
geometry -- see the contract's "Stage-3 correction Tranche A" section for
why, and `mockingbird.training.wildlife_stage3_tranche`'s module docstring
for the exact proxy used.

## 3. Redundancy reduction

Two-layer `deduplicate()`, bounded per lane by `min_keep=<lane target>` so
the perceptual layer can never remove more than the lane's own target
allows:

| Lane | Candidates before dedup | Removed: temporal cluster | Removed: perceptual similarity | Removed: above target | Selected |
|---|---:|---:|---:|---:|---:|
| `small_far_positive_opportunity` | 889 | 479 | 85 | 0 | 325 |
| `local_hard_negative_confusor` | 679 | 300 | 104 | 0 | 275 |
| `night_weather_edge_condition` | 232 | 85 | 47 | 0 | 100 |
| **Total** | **1,800** | **864** | **236** | **0** | **700** |

(Candidate pools already exclude 200 frozen-benchmark-contaminated and 0
Holdout-v2-reserved rows -- see Section 5 -- so the 1,800 above is smaller
than the full 2,000-row queue.)

The intra-corpus near-duplicate threshold (`dHash<=1`, `pHash<=2`) is
deliberately much stricter than the frozen-benchmark contamination
threshold (`dHash<=4`, `pHash<=6`): measured directly against this real
corpus, the looser threshold collapsed 1,000 positive-lane candidates to 34
by matching on "same static outdoor background" rather than genuine repeat
shots -- confirmed by direct visual inspection of matched image pairs, not
assumed. The temporal-cluster bucket width was calibrated the same way: an
initial, more conventional 10-second bucket left the positive lane short of
its 325 target by a real ~15% margin after correctly excluding frozen-
benchmark contamination; 5 seconds (still well under half the codebase's
own existing 30-second negative-sample spacing) resolved it with real
headroom.

## 4. Distinct sessions/encounters/scenes

**11 distinct capture sessions** are represented across the selected 700
frames (all 11 of the 12 sessions the source queue itself draws from; one
contributed nothing to any of the three lanes after exclusion/dedup):

| Frames | Split | Session |
|---:|---|---|
| 134 | train | `2026-08-07-representative-shadow-acceptance/session-02-attempt-3` |
| 140 | validation | `2026-08-07-representative-shadow-acceptance/session-02-attempt-2` |
| 93 | train | `2026-08-07-representative-shadow-acceptance/session-02-attempt-1` |
| 114 | train | `2026-08-06-daylight-temporal-collection/session-02` |
| 111 | train | `2026-08-06-stage6.10-representative-acceptance/session-03` |
| 74 | train | `2026-08-06-stage6.10-representative-acceptance/session-04` |
| 18 | validation | `2026-08-06-stage6.9-burst-scheduler-mechanics-smoke` |
| 13 | validation | `2026-08-06-stage6.10-representative-acceptance/smoke-test` |
| 1 | validation | `2026-08-06-daylight-temporal-collection/session-01` |
| 1 | validation | `2026-08-06-stage6.11b-live-reconnect-mechanics-smoke` |
| 1 | validation | `2026-08-06-stage6.12-fairness-mechanics-smoke` |

## 5. Contamination and Holdout v2

`frozen_contamination_content_hashes` scanned all 2,000 source-queue rows
against the real, checksum-verified 75-image frozen benchmark
(`wildlife.verify_frozen_benchmark`,
`data/evaluations/detector-promotion-v1/corpus-manifest.json`) **before**
selection: **0 exact matches, 200 dual-hash near-duplicate matches**
(the frozen benchmark and this local queue share the same physical
camera/scene, so a real, non-coincidental near-duplicate rate was expected
and confirmed by direct visual inspection -- not a hash-algorithm
artifact). All 200 were excluded from the eligible candidate pool
pre-selection; the final selected 700 were then independently re-verified
with `check_frozen_contamination`: **0 exact, 0 near-duplicate, 0 integrity
failures, `passed: true`.**

`holdout_v2_content_hashes` scanned every distinct capture manifest the
queue references for `holdout_v2_candidate=True`: **0 frames reserved**
(no manifest in this corpus predates or postdates the new field with it
set -- honest absence, not a fabricated zero). The capability itself
(`temporal-capture --holdout-v2-session` marking, `select_tranche`
excluding it) is implemented and unit-tested; no Holdout v2 corpus was
collected in this milestone.

## 6. Train/validation split

Whole-session, never frame-randomized. With 11 distinct sessions (within
the exhaustive-search bound), every one of the 2^11 possible whole-session
groupings was scored against the 25% target and the closest one selected
deterministically (seed `260812`):

- **train**: 526 frames (75.1%), 5 sessions
- **validation**: 174 frames (24.9%), 6 sessions

An earlier version of this split algorithm (closest whole-session *prefix*
of a seed-ordered walk, not the closest possible *subset*) landed at 18.4%
on this same selection; the exhaustive subset search was substituted after
measuring that gap -- see `assign_local_split`'s docstring.

## 7. Reviewer UX changes

`stage3-tranche-review-build --tranche <tranche.json> --output <dir>`
builds a self-contained review packet reusing the existing `AnnotationSet`/
`FrameAnnotation`/`validate_annotations` schema and `temporal-review-
validate` command unmodified (verified: `temporal-review-validate --review
data/training/wildlife-stage3/tranche-a-review` passes against the real
700-frame packet). `render_review_ui` (shared with the original single-
session reviewer, so that flow gains the same improvements) now provides:

- one-frame-focused navigation (Next/Previous, "jump to next unreviewed"),
  replacing the original all-frames-on-one-scrolling-page layout;
- a live progress count (`N / 700 reviewed`) and frame counter;
- an optional, explicit, non-authoritative suggestion-overlay toggle
  (header button + `o` shortcut) -- suggestions remain shown by default,
  matching the original layout, until a reviewer explicitly hides them;
- per-box select (click) + delete (button or Delete/Backspace), not only
  undo-last; a drag started on the currently-selected box replaces it in
  place (edit), a drag started elsewhere adds a new box and clears any
  stale selection;
- optional difficulty-tag quick-select chips (the 13 tags from Section 8);
- current tranche id / lane / priority tier / split candidate shown per
  frame, and the tranche id in the page header, whenever a frame record
  carries that context (silently absent for the original single-session
  flow, which is unaffected);
- localStorage-based autosave after every mutation, automatic resume on
  reload (preferring whichever of the browser cache and the on-disk
  packet has reviewed more frames, so neither can silently regress the
  other), and an explicit, fingerprint-checked, confirm-gated "Load
  annotation.json" file import;
- preloading of the next two frames' images on navigation.

The existing "Download annotation.json" button remains the one
authoritative hand-off into `temporal-review-validate`; nothing here
auto-submits a suggested box as human truth.

## 8. Keyboard shortcuts

`a`=Animal, `n`=No animal, `m`=Ambiguous, `ArrowRight`/`j`=next,
`ArrowLeft`/`k`=previous, `Enter`/`s`=persist and jump to next unreviewed,
`o`=toggle suggestion overlay, `Delete`/`Backspace`=delete the selected
box (or undo the most recent box if none is selected). Suppressed while
focus is inside a text input/textarea.

## 9. Review/provenance rules

Unchanged from the existing, already-tested `temporal_annotation` schema:
a positive requires explicit `whole_frame_truth="yes"` plus at least one
human box (`V_SCORABLE_YES_REQUIRES_BOX`); a negative requires explicit
`"no"`; `"ambiguous"` is recorded but training-ineligible
(`is_scorable`/readiness report both exclude it); every reviewed frame
carries `Provenance.reviewer`/`reviewed_at_iso`/`truth_source`. New,
additive `FrameAnnotation.difficulty_tags` (13 values: `very_small`,
`small`, `far`, `partial_occlusion`, `motion_blur`, `low_contrast`,
`difficult_lighting`, `night`, `weather`, `feeder_overlap`,
`branch_or_vegetation`, `static_clutter`, `other_confusor`) is optional,
frame-level, never required, never a species taxonomy. No old agent-
diagnostic label was or is converted into human truth anywhere in this
pipeline.

## 10. Interruption/resume proof

Verified directly against the real 700-frame packet, not only by unit
test: a partial review (40 frames: 16 positive-with-box, 16 negative, 8
ambiguous, two difficulty tags applied) was written to `annotation.json`,
`temporal-review-validate` passed and reported the correct counts, the
readiness report reflected them exactly, `stage3-tranche-review-build` was
re-run against the same output directory (simulating a restart), and the
40 reviewed frames were confirmed unchanged afterward. The review
directory was then reset to a clean, fully unreviewed state (0/700)
before this report and the commit -- no simulated review data ships in the
repository or the working tree's intended deliverable state.

## 11. Readiness command and current counts

`scripts/report_wildlife_stage3_readiness.py --tranche
data/training/wildlife-stage3/tranche-a.json --review
data/training/wildlife-stage3/tranche-a-review` (add `--json` for
machine-readable output). Current state: **0 / 700 reviewed, 700
remaining**; `STAGE3_TRAINING_READY=False` (expected -- review has not
started). Readiness is derived from tranche composition, never from a bare
review-count total: it requires each of the three lanes and both split
sides to independently reach 80% of its own real target usable-reviewed
count (≈260/220/80 per lane, ≈421/139 per split side -- summing to ≈560,
consistent with, but derived independently of, the task's own suggested
"around 500-600" default), on top of the existing generic dataset-
sufficiency floor (`temporal_annotation.classify_export_sufficiency`: ≥20
reviewed positive, ≥20 reviewed negative, ≥2 scene groups, ≥3 sequences).

## 12. Recommended minimum before Stage-3 training

Per Section 11's derived bars: **at least ≈260 usable-reviewed small/far
positives, ≈220 usable-reviewed hard negatives, ≈80 usable-reviewed edge-
condition negatives, ≈421 usable-reviewed on the train side, and ≈139 on
the validation side** (all independently, not merely summed) -- roughly
560 total usable reviews out of the 700-frame tranche, matching the task's
own suggested "around 500-600" ballpark from an independent, composition-
derived calculation.

## 13. Tests and validation

51 new focused tests: `tests/test_wildlife_stage3_tranche.py` (27:
deterministic prioritization, encounter/session dedup incl. a genuine
cross-bucket perceptual near-duplicate, `min_keep` bounding, lane-target
selection, holdout-v2/contamination exclusion, split isolation and
determinism, queue-identity/fingerprint rejection), `tests/test_wildlife_
stage3_readiness.py` (7: usable-count classification, ambiguous/
unscorable exclusion, the "never ready from total count alone" property,
difficulty-tag/box-distance aggregation, contamination-failure
propagation), plus additive coverage in `tests/test_temporal_annotation.py`
(difficulty-tag validation), `tests/test_temporal_capture.py`/`tests/
test_temporal_capture_cli.py` (`holdout_v2_candidate` default/round-trip/
CLI threading), and `tests/test_temporal_review_io.py` (Stage-3 packet
creation, resume-safety, validation through the *existing* unmodified
`temporal-review-validate` command, source-image integrity rejection,
absolute-path leakage rejection, and the new UI ergonomics rendering).

Full relevant existing suites run clean alongside the above: localization
review provenance (`test_temporal_annotation.py`, `test_temporal_review_io.py`),
exact-frame capture (`test_temporal_capture.py`, `test_temporal_capture_cli.py`,
`test_temporal_capture_io.py`), corpus governance (`test_wildlife_training.py`),
Geometry Attribution (`test_localization_attribution.py`), Counterfactual
Lineage (`test_counterfactual_lineage.py`), detector benchmark/promotion
(`test_detector_promotion.py`), and review-truth governance
(`test_evaluation_governance.py`): **329 passed, 0 failed** in one combined
run. Ruff is clean on every file this session touched. The real end-to-end
pipeline (2,000-row queue -> contamination pre-scan -> selection -> split
-> contamination re-verification -> review-packet build -> `temporal-
review-validate` -> readiness report) was run against real data, not
mocked, twice (the second run after fixing the split-search and dedup-
stats issues the first run's own honest numbers surfaced).

## 14. Commit

One coherent local commit contains the tranche-selection module, CLI
scripts, reviewer/annotation/capture schema changes, tests, and this
documentation. The generated tranche manifest, review packet, and copied
images remain under ignored `data/training/wildlife-stage3/` and are not
committed. The three pre-existing untracked small-bird-benchmark files and
four `.orig` backup files remain untouched and untracked. The exact commit
SHA is reported in the completion handoff; nothing is pushed.

## 15. Exact next milestone

Run `stage3-tranche-review-build` (Section 16 below) and complete named
human full-frame review of the 700-frame tranche, prioritizing the
`small_far_positive_opportunity` lane first (it carries the highest-
information categories: known detector misses/weak engagement, then
generic small/far opportunities). Once the Section 12 bars are met,
re-run the readiness report to confirm `STAGE3_TRAINING_READY=True`, then
materialize a Stage-3 corpus blending the newly-reviewed local set with
the sealed Stage-2 target-domain examples (holding whole sessions disjoint
from validation exactly as this tranche's own split already does), and
train a new RF-DETR Small experiment identity for at least 10 epochs with
early stopping -- requiring frozen recall and false-detection rate to both
improve over Stage-2 (recall > 0.1071, false detections/negative frame <
0.8611) before any shadow-deployment consideration, per docs/wildlife-
detector-stage2-report.md Section 19. No detector was trained in this
milestone.

## 16. Command to start the reviewer

```bash
.venv/bin/python -m mockingbird stage3-tranche-review-build \
  --tranche data/training/wildlife-stage3/tranche-a.json \
  --output data/training/wildlife-stage3/tranche-a-review
```

Then open `data/training/wildlife-stage3/tranche-a-review/index.html` in a
browser. Enter a reviewer name/initials once; it persists across the
session. Progress autosaves continuously; use "Download annotation.json"
periodically (and always at the end) and replace the packet's own
`annotation.json` with the downloaded file, then run:

```bash
.venv/bin/python -m mockingbird temporal-review-validate \
  --review data/training/wildlife-stage3/tranche-a-review
```

and

```bash
.venv/bin/python scripts/report_wildlife_stage3_readiness.py \
  --tranche data/training/wildlife-stage3/tranche-a.json \
  --review data/training/wildlife-stage3/tranche-a-review
```
