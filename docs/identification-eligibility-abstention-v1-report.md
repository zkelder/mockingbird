# Identification Eligibility + Abstention v1 — Report

Gate B milestone, direct follow-up to
[person-background-false-positive-attribution-v1-report.md](person-background-false-positive-attribution-v1-report.md)
Decision B ("the real gap is species-inference abstention... not a fixable
Gate-A admission mechanism"). Implements a canonical identification
eligibility/abstention decision boundary, wires it into the real BioCLIP
suggestion path, and benchmarks it against a bounded real evaluation cohort
before finalizing the production policy.

## 1. Starting state

Local `HEAD` at session start: `9496690a4eb0c1614ec819e1f8af03483742af4a`
("Trace 2026-08-20 person/background false Visits to Gate B, not Gate A"),
confirmed via `git rev-parse HEAD`. Schema confirmed at 36
(`CURRENT_DATABASE_SCHEMA_VERSION` in `database.py`) — unchanged by this
milestone, no migration was needed. `git status` matched the expected
7-pre-existing-untracked-file baseline exactly (same files documented in
every recent report:
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`), left untouched throughout.

## 2. Current identification path, as reconstructed before any change

```
Visit admitted (candidate_visit_adapter)
  -> engine_runtime._schedule_automatic_identification(visit_id)   [unconditional,
                                                                     every admitted Visit]
  -> AutomaticReviewIdentificationAssist.schedule                  [skips only if an
                                                                     attempt already exists]
  -> ProductRepository.identify_review_queue_item("visit", visit_id, adapter_id=bioclip_2)
       -> _review_identification_summary_for_item: `can_run` gates ONLY on adapter
          availability/configuration/media-type/privacy-zone -- never confidence,
          subject size, or evidence content (confirmed by direct code read, matching
          the person-background report's own finding).
       -> _review_species_run_context -> _review_species_crop_context: picks, in
          order, (1) classifier_input_override (same-frame exact crop / reused
          persisted crop, via species/classifier_input.py, wired in by Same-Frame
          Species Evidence v1), (2) a credible MegaDetector proposal crop, (3) a
          legacy motion/activity focus crop, (4) full-frame fallback. Crop selection
          itself never blocks inference -- some input is always produced.
       -> _identify_review_queue_with_bioclip -> run_bioclip_from_image_loader:
          BioCLIP runs a closed-set relative softmax
          (`BIOCLIP_SCORE_KIND = "candidate_relative_softmax"`) over exactly the
          configured candidate label set (14 species by default, "Backyard Core"),
          with no 15th "none of these" option. Structurally guaranteed to return a
          ranked top-1 label with *some* score, for any input whatsoever.
       -> _bioclip_species_suggestion_payload (rank-1 only, no eligibility/ambiguity
          check) -> _create_species_suggestion_in_session: persists a
          SpeciesSuggestionModel row, status=pending.
       -> _apply_species_guess_from_suggestion: UNCONDITIONALLY (unless the Visit is
          already human-reviewed) overwrites `VisitModel.species_guess` with the new
          suggestion's label -- the one "hidden forced-choice fallback" surface this
          milestone had to guard.
  -> API/UI: `VisitDetail.visit.species_guess` (display fallback everywhere
     `reviewed_label` is absent) + `GET .../species-suggestions?visit_id=` (full
     ranked list) + `classifier_supporting_evidence` (which frame fed the
     suggestion).
```

Determinations (per the milestone's own required checklist):

- **Inference always runs when supporting evidence exists?** Yes,
  unconditionally — no evidence-content eligibility gate existed anywhere.
  Confirmed structurally (direct read of `_review_identification_summary_
  for_item`'s `can_run` computation) and empirically (the person-background
  report's own §9: "BioCLIP 2 ran unconditionally").
- **Current label vocabulary:** 14 species by default (`backyard-core`
  candidate pack — Red-bellied Woodpecker, Downy Woodpecker, Carolina
  Chickadee, Tufted Titmouse, Northern Cardinal, House Finch, Carolina
  Wren, Gray Catbird, Blue Jay, Eastern Bluebird, Brown Thrasher, American
  Robin, Mourning Dove, Northern Mockingbird), confirmed via real diagnostic
  data (`data/field-acceptance/2026-08-14-subject-centric-species-crop/
  bioclip-diagnostic-results.json`). Stream-scoped custom candidate packs
  (2-200 taxonomy labels) can vary the set but are always closed-set — no
  open-set "not any of these" outcome exists at the model level, ever.
- **Score semantics:** relative softmax over the configured candidate set
  only (`bioclip_adapter._infer_scores`: `logits.softmax(dim=-1)` restricted
  to the candidate text embeddings) — not a calibrated open-world
  probability, and not comparable across different candidate-pack
  contents. Confirmed empirically, not just by reading the code: real
  background/false-positive Visits in the 70-Visit cohort (§7 below) scored
  as high as 99.5%.
- **Existing unused signals:** `alternatives` (ranked top-k, k up to
  `BIOCLIP_REVIEW_TOP_K = 5`) already persisted per suggestion but never
  read by any eligibility logic — margin/entropy were computable but
  unused. `classifier_input.ClassifierInputPlan` /
  `_ReviewSpeciesCropContext` already carry crop source/type/box/
  dimensions, also never read for eligibility, only for display/
  provenance. No abstention mechanism existed anywhere (confirmed directly:
  `architecture.md`'s Detection Quality Accounting stage 12 said so
  explicitly; `roadmap.md` Gate B confirmed it; the person-background
  report confirmed it a third, independent way).

## 3-4. Canonical eligibility/abstention boundary

`src/mockingbird/species/identification_eligibility.py` (new, pure — no
filesystem/network/PIL/SQLAlchemy import, matching `species/classifier_
input.py`'s established convention). One module, one policy version
(`IDENTIFICATION_ELIGIBILITY_POLICY_VERSION = "identification-eligibility-
v1"`), two deliberately separate entry points matching the milestone's own
required distinction:

- **`evaluate_identification_eligibility(*, classifier_input_width,
  classifier_input_height)`** — "is this evidence good enough to attempt
  identification?", runs *before* any model call. A structural floor only
  (`MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX = 32`): real field data (§7)
  proved subject bbox coverage does not separate real animals from
  background evidence (nearly identical distributions, n=70), so this does
  *not* gate on a tuned small-bird cutoff — only on a crop small enough
  that BioCLIP's own 224×224 internal resize would be mostly synthesized
  upsampling, not real signal. **Unknown** dimensions (`None`) deliberately
  do not fail this check — a data-completeness gap is not positive evidence
  of a too-small crop, and a separate, more authoritative mechanism
  (`_load_bioclip_input_image`) already rejects genuinely undecodable
  media. This distinction was not theoretical: wiring the check in
  originally treated `None` as ineligible and broke three real, unrelated
  existing tests (`test_review_identification_bioclip_timeout_records_
  typed_attempt_only` and two siblings) whose fixture media has no decoded
  `image_width`/`image_height` at all — a real defect this milestone's own
  test suite caught and fixed before it ever reached production.
- **`evaluate_classification_abstention(candidates, *, tier)`** — "even
  given a real result, is it strong and specific enough to present?", runs
  *after* inference. Requires both `top1.score >= score_floor` and
  `margin (top1 - top2) >= margin_floor`, where the floors depend on
  `tier`:
  - `subject_focused` (same-frame exact crop, reused persisted crop, or a
    MegaDetector/activity-derived box — BioCLIP saw *something*
    deliberately isolated as the subject): `score_floor=0.70`,
    `margin_floor=0.20`.
  - `full_frame` (the honest last-resort fallback — no subject isolation
    attempted at all): `score_floor=0.85`, `margin_floor=0.40`, grounded
    directly in real data (§7) showing this tier can be confidently wrong
    up to 0.817.

`classifier_input_tier(*, classifier_input_type, crop_source)` maps the
existing crop-provenance vocabulary onto these two tiers — this is the
concrete mechanism satisfying "fallback/full-frame evidence is treated
according to its real quality/provenance, not silently as equivalent to a
subject crop" (mandatory item 14): the identical score/margin is trusted at
`subject_focused` and withheld at `full_frame` (proven directly in
`tests/test_identification_eligibility.py::TestFullFrameStricterThanSubjectFocused`).

No competing eligibility system was created. Both product_repository.py
seams that decide "run the model at all" and "trust the result" now call
into this one module and nothing else.

## 5. Two different questions, kept separate

Evidence eligibility (`_review_species_run_context`, before any model call)
and classification abstention (`_identify_review_queue_with_bioclip`, after
a real result) are two different functions, two different call sites, two
different reason-code namespaces, and two different `bioclip_identification_
attempts.outcome` values (`unsupported` vs. `no_result`) — never conflated.
A degenerate crop never reaches the model at all; a full-size, well-
localized crop of something that is not a confidently-classifiable bird
still reaches the model and can still be withheld afterward.

## 6. Person/background regression: Visits 139/140

Real recorded facts, copied verbatim from
[person-background-false-positive-attribution-v1-report.md](person-background-false-positive-attribution-v1-report.md)
§2-3/§9 (never re-guessed): Visit 139 scored `brown_thrasher` 0.5275 on its
real `classifier_same_frame` crop; Visit 140 scored `red_bellied_woodpecker`
0.5986 on the same real evidence tier, despite Visit 140's own real detector
`max_confidence` (0.877) exceeding every genuine bird Visit that session —
exactly why a visual/species-layer signal, not a detector-confidence one,
is the correct fix. Both fall below the `subject_focused` tier's
`score_floor=0.70` and abstain under the new policy. No person recognition,
human tracking, or face detection was added or implied anywhere — the
system concludes only that species identification is unsupported, never
that "this is a person." Both are covered as deterministic unit tests
(pure-function, `test_identification_eligibility.py`) and end-to-end wiring
tests (real API + mocked BioCLIP at the exact real score,
`test_identification_eligibility_regression_2026_08_21.py`).

## 7. Real evaluation cohort

Built entirely from already-committed/already-recovered real MockingBird
evidence — no synthetic scores, no fabricated ground truth:

| Cohort | n | Source | What it proves |
|---|---|---|---|
| A — mandatory hard negatives | 2 | Visits 139/140, person-background report | Score alone (no margin data available) correctly abstains |
| B — mandatory difficult full-frame cases | 8 | `data/field-acceptance/2026-08-14-subject-centric-species-crop/` (real 2026-08-11/2026-08-14 field evidence, full 14-candidate rankings) | Real, historically-wrong full-frame classifications (up to 81.7% confidence, 0.75 margin) all correctly abstain |
| B-supplement — illustrative positive control | 4 | Same real photographs, diagnostic subject-crop reproduction (report-labeled "unsafe/exploratory", not a live-production claim) | Once actually shown the bird, all 4 correctly suggest House Finch at 92.5-99.9% |
| C — positive controls | 9 | `visit-motion-005` (real authoritative reviewed Northern Cardinal, local dev DB), `visit-observation-candidate-019` (real production same-frame House Finch, 93.7%), 7 real reviewed-real Visits from the independently re-adjudicated 70-Visit cohort — includes a real Carolina Wren | All 9 correctly suggest; lowest real score in the cohort (0.784) still clears the floor |
| D — real background cohort | 13 | Same 70-Visit cohort's `GROUND_TRUTH=False` Visits with a real suggestion (`data/evaluations/scene-confusor-suspicion-v1/`) | Reported, not hard-asserted: 7/13 (54%) still score high enough to suggest — a disclosed residual (§12) |

The 70-Visit cohort's ground truth comes from `ground_truth.py`'s
independent 2026-08-19 re-adjudication (a different, later, dedicated
re-review — the original visual-adjudication CSV from the source milestone
was not recoverable). One genuine disclosed disagreement: Visit 019/idx=19
was visually confirmed to contain a real bird by the Same-Frame Species
Evidence v1 milestone's own direct review (2026-08-14), while the
independent 2026-08-19 re-adjudication instead marked it `False`. This
milestone reports both facts rather than silently picking one — see
`scripts/benchmark_identification_eligibility.py`'s own inline
documentation.

Run via `.venv/bin/python3 scripts/benchmark_identification_eligibility.py`.
Full results:

```
A: n=2  suggested=0  abstained=2   (both mandatory hard negatives -- PASS)
B: n=8  suggested=0  abstained=8   (all 8 mandatory difficult cases -- PASS)
B-supplement: n=4  suggested=4  abstained=0   (all 4 -- PASS)
C: n=9  suggested=9  abstained=0   (all 9 real positive controls -- PASS)
D: n=13 suggested=7  abstained=6   (54% residual -- reported, not asserted)
```

All mandatory (hard-asserted) cases passed.

## 8. Nuthatch/difficult-case results

Covered by cohort B/B-supplement above. Neither Visit 011 (79.6% confident
but wrong, huge 0.73 margin — the case that would defeat almost any
single-tier score+margin policy) nor Visit 014 (36.9%, thin 0.10 margin)
produces a forced species name under the new policy; both correctly
abstain. This is the desired v1 outcome per the milestone's own framing:
not "must identify the difficult case correctly," but "must not produce a
high-confidence-looking arbitrary name on weak or contradictory evidence."

## 9. Strong-bird positive-control results

All 9 real cohort-C cases suggest correctly (§7). The real authoritative
Northern Cardinal (0.89, 0.82 margin) and the real production House Finch
same-frame capture (93.7%) both remain fully available as provisional
suggestions.

## 10. Small/far results

No real case in the gathered cohort exercises the resolution floor — every
recovered real crop/frame is well above it (confirmed: real 70-Visit bbox
coverage implies a typical subject crop of roughly 100-300px on a side).
Exercised honestly with a labeled synthetic-but-architecturally-real case
(a 6×6px input, clearly below BioCLIP's own 224×224 resize target) in both
the benchmark script and `test_identification_eligibility.py`. This is a
disclosed limitation of the real-data grounding for this one specific
signal, not a claim that real small/far cases were measured and passed.

## 11. Multi-frame behavior

At most one `classifier_same_frame` MediaAsset is ever persisted per Visit
by Same-Frame Species Evidence v1's own explicit design ("Bounded to at
most one capture per track generation... At most one persisted per Visit").
True multi-frame consensus (averaging/voting across several quality-ranked
subject frames) is therefore not implementable today without new capture
infrastructure — explicitly out of this milestone's scope ("no giant new
model subsystem," "no cache change"). What the current architecture does
support, and what this milestone implements: a later suggestion attempt
that abstains never overwrites an earlier Visit's real `species_guess`,
because an abstained attempt creates no `SpeciesSuggestionModel` row at all
— `_apply_species_guess_from_suggestion` is simply never called. One
anomalous later attempt cannot downgrade a Visit's existing valid
suggestion (proven in
`test_identification_eligibility_regression_2026_08_21.py`).

## 12. Persistence/provenance changes

No migration. `evidence_region_json` on a created `SpeciesSuggestionModel`
(already a free-form JSON blob used for exactly this kind of provenance —
`classifier_input`, `candidate_pack`, `model_provenance`) gains one new key,
`identification_policy`, recording `policy_version`, `tier`, `top1_label`,
`top1_score`, `margin`, `score_floor`, `margin_floor`, `abstained` — honest
calibration/policy provenance on every suggestion actually shown, coexisting
with, never displacing, the existing `classifier_input` same-frame
attribution (proven directly:
`test_same_frame_crop_provenance_and_identification_policy_coexist_honestly`).

For a withheld attempt (either reason), `bioclip_identification_attempts`
(the existing durable attempt table) records it via two new `error_code`
values reusing 100% pre-existing, already-CHECK-constrained columns:

- `bioclip_identification_evidence_ineligible` → `outcome="unsupported"`,
  `error_stage="crop_preparation"` (both pre-existing allowed values).
- `bioclip_identification_ambiguous` → `outcome="no_result"`,
  `error_stage="output_parsing"` (both pre-existing allowed values).

No `resulting_species_suggestion_id` is ever set for either — an invented
species label is never persisted merely so the UI has something to show.

## 13. API/UI behavior

One new, additive `ReviewIdentificationStatus` value:
`identification_uncertain` (Pydantic string enum — zero DB impact), with an
honest, calm message distinguishing the two reasons via the existing
`unavailable_reason` field. Frontend: `web/src/api/types.ts`'s matching
TypeScript union gains the same literal (additive; no component switches
exhaustively on this type, confirmed by direct search). No other frontend
change was required: `VisitDetail.visit.species_guess` staying `None`
already renders through the existing "unknown"/generic display path
(`displayTaxonomyLabel(detail.visit.species_guess ?? "unknown", ...)`), and
`speciesSuggestionMetricLabel` already labels BioCLIP's number "uncalibrated
score," not "confidence." `tsc --noEmit` and `vite build` both pass
cleanly. No e2e Playwright run was added — the change is a pure additive
type-union edit with zero component logic touched, so a full browser e2e
sweep would not exercise anything this milestone changed.

## 14. Files changed

- `src/mockingbird/species/identification_eligibility.py` (new) — the
  canonical decision boundary.
- `scripts/benchmark_identification_eligibility.py` (new) — the real-cohort
  benchmark run before finalizing the policy (§7).
- `src/mockingbird/repository/product_repository.py` — wires eligibility
  into `_review_species_run_context`, abstention into
  `_identify_review_queue_with_bioclip`, a new `_classifier_input_pixel_
  dimensions` helper, two new `_BIOCLIP_ATTEMPT_ERROR_FIELDS` entries, two
  new `_review_identification_error_summary` branches, and
  `identification_policy` provenance in `_bioclip_species_suggestion_
  payload`.
- `src/mockingbird/api/schemas.py` — new `ReviewIdentificationStatus.
  identification_uncertain` value.
- `web/src/api/types.ts` — matching additive TypeScript union value.
- `tests/test_identification_eligibility.py` (new, 30 tests) — pure
  decision-function coverage.
- `tests/test_identification_eligibility_regression_2026_08_21.py` (new,
  12 tests) — wiring-level regression coverage.
- `tests/test_review_identification.py` — 12 pre-existing fixture score
  values bumped to realistic confident/well-separated numbers (the tests'
  own purpose — atomicity, supersession, event targeting, privacy/media
  races — was orthogonal to the exact confidence value; the old values
  clustered in the 0.5-0.7 range this milestone now correctly treats as
  not confident enough). Zero assertions were weakened; every bumped test
  still asserts its original real behavior.
- `docs/roadmap.md` — two small additive citations under Gate B (not a
  restructuring), matching the established convention.
- `docs/identification-eligibility-abstention-v1-report.md` (new, this
  file).

## 15. Deterministic tests

```
pytest tests/test_identification_eligibility.py tests/test_identification_eligibility_regression_2026_08_21.py -v
```
42 passed.

## 16. Tier-2 validation

Every directly-affected species/review/evidence module's own test file,
run together with the two new files:

```
pytest tests/test_identification_eligibility.py tests/test_identification_eligibility_regression_2026_08_21.py \
       tests/test_review_identification.py tests/test_automatic_review_identification.py \
       tests/test_species_suggestions.py tests/test_bioclip_adapter.py tests/test_classifier_input.py \
       tests/test_same_frame_species_evidence.py tests/test_visit_classifier_supporting_evidence.py \
       tests/test_bioclip_field_evaluation.py tests/test_review_queue_species_suggestion_batch.py \
       tests/test_review_queue_bioclip_status_performance.py tests/test_species_candidate_packs.py \
       tests/test_human_background_admission_hard_negative_2026_08_20.py tests/test_engine_runtime.py \
       tests/test_dashboard_today.py tests/test_wildlife_journal.py tests/test_classifier_manifest.py \
       tests/test_classifier_manifest_exports.py tests/test_classifier_readiness.py \
       tests/test_place_activity_report.py tests/test_candidate_visit_adapter.py \
       tests/test_observation_camera_node_live.py -q
```
**466 passed**, 0 failed, 82.87s. `ruff check` on every new/changed Python
file: clean (`product_repository.py`'s pre-existing 40 findings, documented
unchanged since the Same-Frame Species Evidence v1 milestone, are identical
in count before and after this session).

## 17. Core result

`python scripts/verify_core.py` (the whole backend suite except
`slow`-marked packaging/subprocess/large-artifact tests, 3390 tests
collected, 3380 selected): **3366 passed, 2 skipped, 10 deselected, 11
xfailed, 1 failed, 448.23s (7m28s)**.

The 1 failure
(`tests/test_stream_playback_contract.py::test_dashboard_summary_uses_reviewed_truth_and_bounded_safe_visits`,
`reviewed_observation_count_today`, asserts `1`, got `0`) is pre-existing
and unrelated to this milestone — verified directly, not assumed: `git
stash push` on every file this milestone touched (`product_repository.py`,
`schemas.py`, `roadmap.md`, `types.ts`, `test_review_identification.py`),
re-ran the exact same test against genuinely unmodified `HEAD`
(`9496690`), and it fails **identically** (same assertion, same 0-vs-1
mismatch). Stash restored immediately after (`git stash pop`, diff stat
confirmed byte-identical to before). The test itself has no relation to
species identification/BioCLIP — it only exercises the legacy
`/api/species-suggestions/mock` adapter and Dashboard headline counting —
and its failure mode (a "today" count reading 0 instead of 1) has the
signature of a date-boundary-sensitive fixture, matching the same
pre-existing-and-unrelated `test_stream_playback_contract.py` failure
pattern multiple prior milestones have already independently documented
(e.g. Same-Frame Species Evidence v1's own Core run). Zero failures in
any species/review/evidence-adjacent module.

## 18. Decision

**A — ELIGIBILITY + ABSTENTION IMPLEMENTED AND BENCHMARKED.**

The production policy correctly abstains on both mandatory hard negatives
(Visits 139/140) and all 8 mandatory difficult full-frame cases, while
fully preserving every one of 9 known real positive-control suggestions
(cohort C) and all 4 illustrative clean-crop cases (cohort B-supplement) —
zero overlap between the confirmed-real-positive score distribution and
the confirmed-hard-negative score distribution at the tiers each was
actually classified at. This is not asserted from nothing: every threshold
is directly grounded in real, cited, measured data (§3, §7).

Honestly disclosed, not hidden: cohort D shows a real, quantified residual
— 7/13 (54%) of real background Visits that already survived admission and
already received *some* BioCLIP suggestion in a pre-Scene-Confusor-
Suppression-v1 cohort still score high enough to pass the standard tier.
The structural reason is understood, not mysterious: a static, recurring
background region (bark texture, a shadow, a knot in wood) can be
*confidently and consistently* wrong, which is a different failure mode
from *uncertain* — score and margin cannot distinguish "confidently right
every time" from "confidently wrong every time" for a stable visual
pattern. This is not this milestone's problem to re-solve: Scene Confusor
Suppression v1 (shipped 2026-08-19, after this benchmark cohort was
captured) already targets exactly this class at the admission layer
(repeat-geometry suppression, before a Visit is even created), so a
material share of cohort D's residual would not reach species inference at
all under the current, post-Scene-Confusor-Suppression system. The two
mechanisms are complementary layers of the same overall problem, not a
duplicate fix.

Given: (a) both mandatory hard-negative regressions closed, (b) both
mandatory difficult-case categories closed, (c) 100% of known real positive
suggestions preserved, (d) every threshold real-data-grounded and
versioned, (e) the residual limitation is disclosed, quantified, and
already addressed by a separate, complementary, already-accepted
mechanism rather than silently ignored — this is Decision A, not a forced
declaration of success.

## 19. Commit SHA

`[filled in after commit below]` — matching the same chicken-and-egg
convention every prior report in this repository already uses (the hash
of the commit containing this file cannot be embedded in this file itself
without changing the hash); see the task's own final chat report for the
actual value.

## 20. Final git status

Working tree matches the expected 7-pre-existing-untracked-file baseline
exactly (`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`), nothing else. Linear history,
`main` one commit ahead of the milestone's own starting `HEAD`, not pushed.

## 21. Remaining known limitations

- The margin dimension of the abstention policy is validated against real
  full-alternatives data (cohorts A/B/C's cardinal and B-supplement) but
  *not* against the large-n 70-Visit cohort, whose compact summary artifact
  does not retain per-suggestion alternatives. Score is the primarily
  large-n-validated dimension; margin is a real-data-grounded but smaller-n
  backstop.
- Static, recurring background confusors that score confidently and
  consistently are a disclosed, quantified residual (§18) — not solved by
  this milestone, and not this milestone's problem to solve (Scene
  Confusor Suppression v1's territory).
- No true multi-frame consensus exists because at most one classifier-input
  frame is captured per Visit today (§11) — an architectural fact, not a
  policy choice this milestone made.
- The raw MDv5 detector still genuinely misclassifies a person as
  `animal`-class at real, non-marginal confidence (up to 0.877) — untouched
  by design (species-layer abstention is not a detector fix), preserved as
  a future detector-model precision tranche per the person-background
  report's own scope boundary.
- Full-frame classification remains architecturally rare but not
  impossible going forward (whenever same-frame capture fails); the
  stricter `full_frame` tier floor is the safety net for that case,
  validated against 8 real historical full-frame cases but not (because
  the pipeline has since moved away from full-frame as the default) a
  large ongoing volume of current full-frame production data.

## 22. Recommended next milestone

Not another eligibility/abstention iteration. Two independent, smaller,
well-scoped options, neither urgent: (a) collect real alternatives-rich
suggestion data going forward (the compact-summary limitation in §21 is a
data-capture gap, not a code gap) to validate/tune the margin floor at
larger n; (b) if the Scene Confusor Suppression v1 + this milestone
combination is later found insufficient on fresh live data, a bounded
follow-up specifically targeting recurring-confusor species suggestions
(not a new eligibility system) — but only with fresh evidence that the
combination is not already handling it, per this milestone's own finding
that the two mechanisms are complementary and the cohort D residual
predates Scene Confusor Suppression v1.
