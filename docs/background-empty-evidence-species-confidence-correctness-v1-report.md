# Background / Empty Evidence Species-Confidence Correctness v1 — Report

## Starting state

Verified before any change:

- **Repository:** `/home/zkelder/projects/mockingbird-active`
- **Branch:** `main`
- **HEAD:** `428fcb3` (matches the brief's expected accepted HEAD exactly).
- **Schema:** `v58` (`CURRENT_DATABASE_SCHEMA_VERSION`, `src/mockingbird/storage/database.py:45`) — matches.
- **Gate A / Lane R:** open, as expected. Representative Daylight Gate A Field
  Acceptance v6 (Post-Fix Replication & Multi-Subject Tranche) is defined in
  `docs/release-execution-state.md` §3 but **not run** — confirmed, unchanged
  by this milestone.
- **v5 field defect (Gate B):** open, as expected — the "Brown Thrasher,"
  89.9%-confidence, wrong-species label on confirmed empty background
  (`visit-observation-candidate-021`), disclosed but not fixed by
  Representative Daylight Gate A Field Acceptance v5.
- **Current authorization before this instruction:** `NONE` — matches
  `docs/release-execution-state.md` §3's bold statement.
- **Push state:** local only, ahead of `origin/main` by 261 commits before
  this milestone's own commits; not pushed by this milestone either.
- **Worktree safety:** the seven preserved untracked files (listed in the
  governing brief) were confirmed present with identical mtime/size both
  before and after this milestone's work — untouched throughout.

## Reproducer

**Required RED case, built and run against the real, unmodified production
identification path** (`ProductRepository.identify_review_queue_item` →
`_review_species_run_context` → `_review_species_crop_context` →
`_credible_megadetector_animal_proposal` → `evaluate_identification_eligibility`
→ `_identify_review_queue_with_bioclip`; see
`tests/test_background_empty_evidence_species_confidence_correctness_v1.py::
TestBackgroundEmptyEvidenceRedToGreen`):

1. A real Visit is created via the ordinary media-import path, and a real
   `DetectionProposalModel` row is created via the production MegaDetector
   adapter-run endpoint (`/api/model-adapters/{id}/runs`) — an `animal`-class
   proposal at `confidence=0.704` (the v5 case's own real number), bounding
   box `x=0.8041, y=0.6731, width=0.15, height=0.15` (the v5 case's own real
   padded evidence region). This is the same `"megadetector"` crop tier
   `_review_species_crop_context` resolves to.
2. `MediaAssetModel.geometry_attribution_json` is seeded on the Visit's
   representative frame with `geometry_source="tracker"` — the one fact a
   real Observation Engine v2 tracker/burst session would have recorded for
   a track kept alive on tracker-only support past its last real detector
   confirmation (`terminal_reason: maximum_unsupported_duration`, the v5
   case's own real terminal reason; see "Root cause" below for why this
   specific fact, not a re-run of the real tracker, is what a fast
   regression test can seed).
3. BioCLIP is mocked to return exactly the v5 case's own real result:
   `brown_thrasher`, score `0.899`, no second candidate (margin defaults to
   the score itself, `0.899` ≥ the module's own `SUBJECT_FOCUSED_MARGIN_
   FLOOR` of `0.20` — the same conservative single-candidate substitution
   the original milestone's own benchmark script already uses for cohort
   C/D).
4. `POST /api/review-queue/visit/{id}/identify` is called — the real
   production endpoint both the automatic-identification scheduler and the
   manual "Identify" UI action use.

**Confirmed RED against the original, unmodified code** (`git stash push` on
just the two source files, tests kept in place, then run):

```
FAILED …TestBackgroundEmptyEvidenceRedToGreen::test_v5_pattern_tracker_sourced_geometry_produces_no_suggestion
FAILED …TestBackgroundEmptyEvidenceRedToGreen::test_carried_forward_geometry_also_produces_no_suggestion
FAILED …TestWrongSubjectSafety::test_uncorroborated_crop_does_not_confidently_claim_a_species
FAILED …TestPersistence::test_no_species_suggestion_row_is_created_for_ineligible_evidence
FAILED …TestPersistence::test_ineligible_attempt_is_still_durably_recorded
5 failed, 8 passed in 4.11s
```

Pre-fix, the harness directly observed: `result["identification"]["status"]
== "suggestion_created"`, `result["species_suggestion"]["confidence"] ==
0.899`, and a real `SpeciesSuggestionModel` row persisted for evidence whose
own geometry lineage never corresponded to a real, contemporaneous detector
observation — the exact defect class the brief names. (`git stash pop`
restored the fix immediately after this confirmation; the 7 preserved
untracked files were re-verified byte-for-byte unchanged afterward.)

This did **not** fake the bug by calling BioCLIP directly and asserting a
guess — every step above drives the real production endpoint, the real
`_credible_megadetector_animal_proposal`/`_review_species_crop_context`
selection logic, and the real `evaluate_identification_eligibility`/
`evaluate_classification_abstention` decision boundary; only the BioCLIP
model call itself and one upstream tracker fact are mocked/seeded (the same
convention every existing test in `test_review_identification.py` and
`test_identification_eligibility_regression_2026_08_21.py` already uses).

## Root cause

Traced through repository evidence and the real code (bounded archaeology,
not exhaustive detector/tracker re-derivation):

1. **Evidence asset selected:** `media-candidate-052`, the real Visit's own
   representative ("identification"-role) frame, a real, byte-backed,
   ordinary-sized crop (well above the 32px resolution floor).
2. **Why considered eligible:** `_credible_megadetector_animal_proposal`
   (`product_repository.py:29530`) treats *any* non-rejected, `animal`/
   `unknown_animal`-labeled MegaDetector proposal with `confidence >=
   MEGADETECTOR_DEFAULT_CONFIDENCE_THRESHOLD` (**0.1** — the same bare
   production detector floor, not a stricter species-crop-specific bar) and
   a syntactically valid bounding box as "credible" — a much weaker bar than
   the word implies. `0.704` clears it trivially.
3. **Did evidence scoring say wildlife was present?** No independent check
   ever asked. `mockingbird.observation.evidence_scoring.score_proposal_
   evidence` — a materially richer Stage-6.x scorer that already computes
   `subject_absent`/sharpness/exposure/containment/temporal-alignment facts
   from real decoded pixels — is used exclusively at Visit-assembly/
   admission time to choose which frame gets *persisted* as evidence at all
   (`candidate_visit_adapter.py:156`). A repository-wide search confirms
   **zero** references to it, or to any of its facts, anywhere in the
   species-identification code path (`product_repository.py`,
   `identification_eligibility.py`). These are two structurally disjoint
   systems today; this milestone does not merge them (see "Implementation").
4. **Did Identification Eligibility run?** Yes — `evaluate_identification_
   eligibility` ran, and returned `eligible=True`, because its only check
   (pre-fix) was crop pixel size (`>= 32×32`), which this crop clears by a
   wide margin (a padded ~576×340px region).
5. **Was eligibility bypassed?** No. It ran to completion; its *scope* was
   simply too narrow to ask the one question that mattered.
6. **Stale eligibility decision?** No — a fresh, first-time evaluation.
7. **Wrong crop/frame delivered to BioCLIP?** No — Localization Attribution
   / Detection Geometry Lineage v1 (already accepted, schema 33) already
   closed the class of bug where evidence bytes and box geometry disagree
   about which moment they represent; this is not that failure mode.
8. **Full-frame fallback treated as equivalent to subject evidence?**
   **No** — directly ruled out. The crop was a `"megadetector"`-tier
   (or, per further investigation below, possibly legacy `"activity"`-tier)
   *subject-focused* crop, not a full-frame fallback; `classifier_input_
   tier()` correctly assigned it the `subject_focused` tier, not `full_
   frame`.
9. **Was a low-quality suggestion promoted past abstention policy?** Yes,
   in the only sense possible: `evaluate_classification_abstention` checks
   only BioCLIP's own `score`/`margin` against a tier floor. **89.9%
   score / 0.857 margin clears even the module's own strictest existing
   floor** (`FULL_FRAME_SCORE_FLOOR=0.85`, `FULL_FRAME_MARGIN_FLOOR=0.40`) —
   proven directly by arithmetic, not assumption. This means **no
   score/margin/tier change of any kind, at any strictness, can catch this
   case** — the fix cannot live in the abstention layer's existing
   vocabulary at all.
10. **Evidence-selection, eligibility, or persistence?** **Eligibility's own
    scope**, specifically: it had no signal independent of BioCLIP's own
    output to ask "does this crop's own geometry still correspond to a
    real, contemporaneous subject observation" — the exact gap the v5
    report's own "Defects" section names verbatim: *"BioCLIP's own
    eligibility/abstention policy — which has no 'is a subject actually
    visible' check independent of its own species-level softmax
    confidence."*

**First incorrect decision, precisely:** inside `evaluate_identification_
eligibility` (`src/mockingbird/species/identification_eligibility.py`), the
decision that a crop is "worth attempting identification on" considered
*only* pixel dimensions — never any fact about whether the box the crop was
built from corresponds to a real, contemporaneous subject observation.
Everything upstream (localization, admission, evidence capture/survival)
and downstream (BioCLIP inference itself, persistence) behaved exactly as
designed given that input — this is not a detector bug, not a tracker bug,
not a geometry-lineage bug, and not a persistence bug.

### What was investigated and ruled out before implementing anything

Per the brief's own bar ("do not change code until the first incorrect
decision is proven"), several plausible mechanisms were tested against real
data and rejected before choosing the fix below — recorded here so a future
reader does not re-derive the same negative results:

- **Detector/track confidence, detection count, `strong_detection_count`,
  `max_consecutive_detector_confirmed_frames`:** already established as
  non-discriminating for *admission* by `detection-quality-accounting-
  contract.md`'s "Production authority gate" (a full sweep against 70 real
  reviewed Visits: no threshold clears both false-positive-rejection and
  real-animal-recall together). This milestone additionally, freshly
  re-tested `detection_count`/`strong_detection_count`/`max_consecutive_
  detector_confirmed_frames` directly against the same real, independently-
  adjudicated 70-Visit cohort (`data/evaluations/scene-confusor-suspicion-
  v1/`) for *identification-eligibility* purposes specifically (a different
  question from admission) — **also non-discriminating**: e.g.
  `strong_detection_count == 0` is shared identically by real positive
  controls (idx 23, 35, 37, 38 — all `GROUND_TRUTH=True`) and by real
  background Visits (idx 19, 22, 24, 26, 27… — all `GROUND_TRUTH=False`).
  Gating on it would suppress a large, unacceptable share of genuine
  suggestions (roughly half the cohort, both real and false, share
  `strong_detection_count == 0`).
- **Raising BioCLIP's own score/margin/tier floors:** mathematically
  impossible for this case (see point 9 above) without also excluding real
  positive controls that score as low as `0.784` (the cohort's own
  documented floor-defining case).
- **Bounding-box size/coverage:** already tried and rejected by the
  *original* Identification Eligibility v1 milestone (its own module
  docstring: "real field data… proved subject bbox coverage does not
  separate real animals from background/false-positive evidence").
- **Crop padding ratio:** reduces to the same bbox-size signal already
  rejected above (the padding algorithm expands small boxes proportionally
  more regardless of truthfulness, not selectively).

## Eligibility contract

The accepted `mockingbird.species.identification_eligibility` module (no
separate standalone contract doc exists; `docs/identification-eligibility-
abstention-v1-report.md` is the sole authoritative record) already
distinguished, and this milestone preserves unchanged:

- **Evidence eligibility** (pre-inference, structural floor: crop pixel
  size) vs. **classification abstention** (post-inference, BioCLIP's own
  score/margin against a tier-dependent floor) — two deliberately separate
  questions, never conflated.
- `subject_focused` vs. `full_frame` classifier-input tiers.
- Multi-frame consensus (defined, not production-wired — unaffected by this
  milestone).

This milestone adds one **new**, additive eligibility dimension to the
*first* of those two questions — "evidence outside accepted quality bounds"
per the brief's §7 vocabulary — without creating a second, parallel
eligibility system: the same module, the same `EligibilityDecision` type,
one new optional field and one new reason code.

Mapping onto the brief's required minimum classification (§7):

| Category | How this milestone's evidence maps |
|---|---|
| Useful subject evidence | `geometry_source="detector"` (or unknown, pre-schema-33) → eligible, unchanged |
| Background-only / empty evidence | `geometry_source ∈ {"tracker","carried_forward"}` at the megadetector/legacy-activity tier → **new**: ineligible |
| Wrong-subject evidence | Same mechanism — an uncorroborated box is not proven correspondence to *any* real-time subject, right or wrong (see "Wrong-subject result") |
| Unresolved evidence | Unchanged — handled elsewhere (zone suppression, adapter/media-type checks) |
| Evidence missing bytes | Unchanged — `missing_media_file`/`_load_bioclip_input_image`'s own typed error, untouched |
| Evidence outside accepted quality bounds | Unchanged existing floor (crop size) **plus** this milestone's new geometry-corroboration floor |

## Implementation

Two files, no schema change (the field this fix reads,
`MediaAssetModel.geometry_attribution_json`, already exists — schema 33,
Localization Attribution / Detection Geometry Lineage v1):

- **`src/mockingbird/species/identification_eligibility.py`** —
  `evaluate_identification_eligibility` gains one new optional keyword-only
  parameter, `geometry_source: Literal["detector","tracker","carried_
  forward"] | None = None`. A *known*, non-`"detector"` value is treated as
  ineligible (`reason_code="evidence_geometry_uncorroborated"`); `None`
  (unknown/not wired for this tier) degrades safely to "no opinion," mirroring
  the existing `classifier_input_width`/`height` `None` convention exactly.
  `EligibilityDecision` gains a matching `geometry_source` field for
  diagnostics (never silently discarded once known).
- **`src/mockingbird/repository/product_repository.py`** —
  `_review_species_run_context` reads `media_asset.geometry_attribution_json`
  (already loaded, no new query) via the pre-existing `geometry_attribution_
  from_json` helper (already imported, already used identically elsewhere in
  this same file — `_native_resolution_candidate_assets_for_visit`,
  `product_repository.py:29289`, checks a sibling field on the same object)
  and passes its `geometry_source` through, **scoped to exactly the two crop
  tiers with no other same-moment-correspondence guarantee of their own**:
  `crop.classifier_input_type is None and crop.source in {"megadetector",
  "activity"}`. This mirrors `classifier_input_tier()`'s own `classifier_
  input_type`-first check, because `source="activity"` is ambiguously reused
  for *both* the legacy focus-crop tier this milestone covers *and* the
  Same-Frame/Persisted-Crop/Native-Resolution override tiers, which already
  carry their own, stronger, separately-validated correspondence guarantees
  (`classifier_input_same_frame`/`resolution_provenance` — a `future shadow
  evaluation`-class use already established for the sibling field
  `resolution_provenance == "synchronized"` in this exact module) that this
  new check must not second-guess. The full-frame fallback tier is out of
  scope (already the strictest existing floor; not part of this signal's
  real-cohort validation).

`docs/localization-attribution-contract.md` is explicit that `GeometryAttribution`
is "diagnostic lineage, never observational truth" and must never be treated
as proof of a specific root cause without human confirmation. This fix
honors that boundary: it never asserts the evidence *is* background: it
withholds an *automatic* claim on evidence whose own correspondence to a
real captured moment the system cannot currently verify — the same
revisable, human-overridable abstention this module already applies for
every other reason, never a truth claim, never a Visit rejection.

Real-cohort validation (independent of the RED-case reproduction above; see
`scripts/benchmark_identification_eligibility.py`'s own cohort A–D and the
independently re-adjudicated `data/evaluations/scene-confusor-suspicion-v1/`
ground truth): non-`"detector"` geometry sources correctly separate **11/40**
real `GROUND_TRUTH=False` Visits (idx 24, 39, 41, 43, 44, 45, 49, 65, 68, 81,
85) — including idx=24, one of the original milestone's own disclosed
"still-suggests" cohort-D residual cases — while wrongly withholding only
**2/30** real `GROUND_TRUTH=True` Visits (idx 57, 73) in the same wider
cohort, and **zero** of the 7 specific real positive controls the original
benchmark script hard-asserts (idx 21, 23, 25, 33, 35, 37, 38).

## Background/empty result

**Fixed for the reproduced defect class.** Both RED-case scenarios
(tracker-sourced and carried-forward-sourced geometry, matching the v5
case's own real numbers and the same crop tier) now abstain before BioCLIP
is ever invoked — verified two ways: (1) `result["species_suggestion"] is
None` / `unavailable_reason == "bioclip_identification_evidence_ineligible"`,
and (2) the strongest available proof, the BioCLIP mock's own invocation
list is empty (`invocations == []`) — this is not "a suggestion was
discarded after the fact," the model call itself never happens.

**Honestly bounded, not oversold:** this closes the geometry-uncorroborated
slice of the disclosed Gate B residual, not the entire residual. A
detector-sourced-but-still-wrong crop (a static, recurring background region
that scores confidently and *is* backed by a genuine, contemporaneous
detector hit — e.g. idx=36 in the same real cohort, `mourning_dove` at
99.5%, already covered by `TestBackgroundEmptyEvidence::test_a_high_scoring_
real_background_visit_is_a_disclosed_residual`) remains exactly as
unclosed as before this milestone. See "Remaining risks."

## Wrong-subject result

Section 11's requirement is subject relevance, not individual-animal
identity/ReID, and this milestone does not attempt ReID. The same mechanism
that withholds a claim on background/empty evidence also withholds one when
the selected evidence's own geometry is not proven correspondence to a
real-time subject at all — proven directly (`TestWrongSubjectSafety::
test_uncorroborated_crop_does_not_confidently_claim_a_species`): even a
maximally confident-looking result (99.9% score) from an uncorroborated
crop produces no Visit-level species claim.

**Disclosed limitation:** a genuine detector-sourced box that is
well-formed but happens to be centered on the *wrong* one of several
real, simultaneously-present animals is not caught by this mechanism —
`geometry_source="detector"` alone does not distinguish "correct subject"
from "a different real subject in the same scene." This is a distinct,
narrower gap than the one this milestone closes and was not reproduced or
required by the governing brief's own RED case.

## Good-evidence result

Non-regression, verified both by direct tests and by the unmodified real
production/benchmark test suites:

- `TestGoodEvidenceNonRegression::test_detector_sourced_megadetector_crop_
  still_suggests` — a genuine, contemporaneous detector observation at the
  same crop tier still runs BioCLIP and persists a suggestion exactly as
  before.
- `TestGoodEvidenceNonRegression::test_unknown_geometry_attribution_still_
  suggests` — a Visit with no recorded geometry lineage at all (pre-schema-
  33 data, or a path that never computed it) is unaffected — the same
  "degrade safely on an absent fact" convention the pre-existing size check
  already established.
- `scripts/benchmark_identification_eligibility.py` re-run after the fix:
  identical results to before (cohort D still `n=13 suggested=7
  abstained=6`) — this script exercises `evaluate_classification_abstention`
  only, a layer this milestone does not touch, confirming no interaction.
- Every pre-existing identification/evidence test across the 19 pre-existing
  Tier 2 files (see "Validation," Tier 2) — passes unmodified.

## Abstention result

Unchanged and preserved: `TestAbstentionPrincipleFromEligibleEvidence::
test_eligible_evidence_with_weak_score_still_abstains` proves eligible
(detector-sourced) evidence with a weak BioCLIP score still abstains via the
*existing*, untouched score/margin mechanism — and, critically, that BioCLIP
*was* actually invoked in that case (`len(invocations) == 1`), distinguishing
"abstained after a real result" from this milestone's new "never asked at
all" pre-inference gate. No forced species label is manufactured for either
reason; both surface as the same existing `identification_uncertain`/
honest-absence product behavior.

## Reviewed-truth result

Unaffected. `TestReviewedTruthPreserved::test_reviewed_correction_survives_
a_later_ineligible_reattempt` proves: a human correction remains
authoritative after it is made, and — because a reviewed Visit is no longer
a review candidate at all (pre-existing, unchanged behavior) — a later
identification attempt never even reaches either eligibility check again,
reporting `missing_review_candidate` instead. This milestone did not touch
`_apply_species_guess_from_suggestion`'s own reviewed-truth guard.

## Persistence result

- `TestPersistence::test_no_species_suggestion_row_is_created_for_
  ineligible_evidence` — no `SpeciesSuggestionModel` row is created for a
  withheld attempt, confirmed via `GET /api/species-suggestions`.
- `TestPersistence::test_ineligible_attempt_is_still_durably_recorded` — the
  attempt itself is still recorded in the pre-existing durable ledger
  (`bioclip_identification_attempts`, `outcome="unsupported"`,
  `error_stage="crop_preparation"`, `resulting_species_suggestion_id=None`)
  — the same, already-established persistence path the pre-existing
  resolution-floor reason already used; this milestone adds a second reason
  into that path, not a new mechanism.
- **No migration performed and none required.** This fix reads an
  already-existing, already-migrated column (schema 33); it introduces no
  new table/column. Per the brief's own §14: a database cleanup campaign for
  already-persisted, pre-existing bad suggestions (including the original,
  historical Visit-021 row itself, which this sandbox has no access to —
  `data/` is gitignored and that field session's own database was never
  part of this repository checkout) is not attempted, and is not required:
  this is unchanged, pre-existing behavior identical to how the original
  `evidence_below_resolution_floor` reason already behaves on re-
  identification (neither reason retroactively supersedes a prior
  suggestion; both share the exact same, unmodified code path). Nothing in
  this milestone's own investigation found evidence that a currently-
  persisted invalid suggestion can violate Reviewed/current truth — Reviewed
  truth is never overwritten by any automatic identification outcome,
  confirmed above.

## Validation

**Tier 1 — new eligibility/background-evidence tests (82 tests, all
passing post-fix):**

```
pytest tests/test_background_empty_evidence_species_confidence_correctness_v1.py \
       tests/test_identification_eligibility.py \
       tests/test_identification_eligibility_regression_2026_08_21.py -q
82 passed in 12.81s
```

15 new end-to-end/wiring tests (background/empty RED→GREEN ×2 on the
`"megadetector"` tier plus ×2 more on the legacy `"activity"` tier — the
more realistic default automatic-identification path per this milestone's
own investigation, since an ordinary Observation Engine v2 candidate Visit
typically has no `DetectionProposalModel` row at all — , wrong-subject ×1,
good-evidence non-regression ×2, abstention-preserved ×1, reviewed-truth
×1, persistence ×2, override-tier-scoping ×4) plus 6 new pure decision-
function tests extending the existing `TestEvidenceEligibility`/new
`TestGeometryCorroborationEligibility` in `test_identification_eligibility.py`
(48 → 54 tests in that file).

RED confirmed separately (see "Reproducer"): the same defect-class tests
(5 on the `"megadetector"` tier, 1 more on the `"activity"` tier, confirmed
in a second, later stash/pop cycle) fail against the original, unmodified
code when the two source-file changes are reverted (tests kept in place
via `git stash push` on just the source files).

**Tier 2 — affected identification/evidence subsystem (456 tests, all
passing):**

```
pytest tests/test_automatic_review_identification.py tests/test_bioclip_adapter.py \
       tests/test_bioclip_field_evaluation.py tests/test_bioclip_runtime.py \
       tests/test_candidate_visit_adapter.py tests/test_classifier_input.py \
       tests/test_human_background_admission_hard_negative_2026_08_20.py \
       tests/test_identification_assistant.py tests/test_identification_eligibility.py \
       tests/test_identification_eligibility_regression_2026_08_21.py \
       tests/test_localization_attribution.py tests/test_observation_evidence_scoring.py \
       tests/test_review_identification.py tests/test_review_queue_bioclip_status_performance.py \
       tests/test_review_queue_species_suggestion_batch.py tests/test_species_suggestions.py \
       tests/test_same_frame_species_evidence.py tests/test_native_resolution_species_evidence.py \
       tests/test_visit_classifier_supporting_evidence.py tests/test_source_resolution_species_benchmark.py \
       tests/test_background_empty_evidence_species_confidence_correctness_v1.py -q
456 passed in 140.09s
```

Covers: evidence scoring (`test_observation_evidence_scoring.py`,
`test_candidate_visit_adapter.py` — confirms the Stage-6.x scorer this
milestone deliberately does not touch is unaffected), identification
eligibility (both new and pre-existing), automatic identification scheduling
(`test_automatic_review_identification.py`, `test_identification_
assistant.py`), species suggestion persistence (`test_species_suggestions.py`,
`test_review_queue_species_suggestion_batch.py`), Review/Reviewed-truth
interaction (`test_review_identification.py`), the geometry-lineage source
module itself (`test_localization_attribution.py`), and the hard-negative
regression this module's own docstring cites
(`test_human_background_admission_hard_negative_2026_08_20.py`).

**Tier 3 — one full Core run (warranted per the brief's §19: an epistemic
correctness boundary, exposed by real field evidence):**

```
python scripts/verify_core.py
```

```
FAILED tests/test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary
FAILED tests/test_place_biodiversity_summary_repository.py::test_human_correction_updates_place_biodiversity_intelligence_correctly
2 failed, 5335 passed, 3 skipped, 23 deselected, 11 xfailed, 228 warnings in 1620.20s (0:27:00)
```

The 2 failures are **pre-existing and independently verified unrelated** —
not assumed, checked directly: `git stash push` on both changed source
files (`identification_eligibility.py`, `product_repository.py`, keeping
every test file in place), re-running `tests/test_place_biodiversity_
summary_repository.py` alone against genuinely unmodified HEAD (`428fcb3`)
reproduces the **identical** two failures, byte-for-byte the same assertion
(`'seen_before' == 'new'`, a real-wall-clock-date-sensitive historical
"new vs. seen-before" species-status boundary — `test_human_correction_
updates_place_biodiversity_intelligence_correctly`/`test_api_route_returns_
the_summary`, both driven by the same `NOW`/`observed_at`/`historical_
status` fixture). Stash restored immediately after (`git stash pop`).
Neither failing test touches species identification, eligibility,
abstention, evidence, or BioCLIP in any way — this is the same class of
already-documented, already-disclosed date-boundary-sensitive Core flake
multiple prior milestones in this repository have independently found and
recorded (e.g. `test_stream_playback_contract.py`'s own "today" count
flake, and the Habitat & Phenology Foundation v1 milestone's own "genuine
pre-existing Core flakiness (~2/4500/run)" finding). Zero failures in any
species/review/evidence-adjacent module — every file this milestone
touches or lists in Tier 2 passed cleanly inside this same full run
(directly confirmed by grepping the log for each Tier-2 file name: all
show only `.` outcomes, no `F`).

## Remaining risks

- **Detector-sourced-but-still-wrong residual, undisclosed no longer but
  unclosed:** a static, recurring background region backed by a genuine,
  repeated, contemporaneous detector hit (idx=36-class) is not caught by
  this mechanism, exactly as before. This remains open Gate B work — the
  original milestone's own recommended follow-up (Scene Confusor
  Suppression v1, already shipped) targets *recurring* geometry across
  sessions specifically; a genuinely novel, first-occurrence, detector-
  sourced-but-wrong detection (unlike v5's own tracker-plausible case) would
  be caught by neither mechanism.
- **Wrong-subject-among-several-real-subjects** is not addressed (see
  "Wrong-subject result").
- **2/30 real Visits in the wider (non-hard-asserted) ground-truth cohort
  would now be wrongly withheld** an automatic suggestion (idx 57, 73) —
  a real, bounded, disclosed cost, consistent with this product's own
  abstention-friendly doctrine ("no confident species suggestion is better
  than a plausible-looking wrong species"). Both remain fully human-
  reviewable; neither Visit itself is affected, only the automatic
  suggestion.
- **The literal historical Visit-021 row's own `geometry_source` could not
  be independently confirmed** — the 2026-08-30 field session's own database
  was never part of this repository checkout (`data/` is gitignored,
  session-local). This milestone's RED case faithfully reproduces the same
  real numbers (confidence, bounding box, BioCLIP score/margin, terminal
  reason) and the single most plausible geometry-lineage explanation for a
  `maximum_unsupported_duration`-terminated track (tracker-only
  extrapolation past the last real detector confirmation, consistent with
  `roadmap.md`'s own documented "evidence captured after, not at, the
  triggering detection" mechanism) — not a byte-for-byte replay of the
  original database row.
- **`evidence_scoring.py`'s richer Stage-6.x facts remain unreachable at
  species-identification time** — this milestone did not merge the two
  systems (out of scope; would require new persistence/schema, not proven
  necessary by the reproduced defect). A future milestone could evaluate
  whether propagating those facts forward closes more of the residual above,
  but real, held-out validation data for that specific extension does not
  currently exist in this repository.

## Gate B disposition

The specific, reproduced v5 defect class (a real-bytes, ordinary-sized,
subject-focused crop whose own geometry never corresponds to a real,
contemporaneous detector observation, confidently mislabeled by BioCLIP) is
now closed: it cannot produce an automatic species suggestion. The broader
"background/empty evidence → confident species label" regression class
`roadmap.md` names remains partially open — the detector-sourced-but-wrong
sub-class (idx=36-class) is unchanged, exactly as disclosed above, not
hidden. Gate A/Lane R remains open and unaffected by this milestone (no
admission/detection/Visit-assembly code was touched).

## Decision

**A — REAL v5 DEFECT CLASS REPRODUCED AND FIXED, HONESTLY BOUNDED.**

Per the governing brief's §22 bar:

- Real v5 defect class reproduced deterministically through the real,
  unmodified production `identify_review_queue_item` path — not a
  synthetic BioCLIP-only repro.
- First incorrect boundary proven (`evaluate_identification_eligibility`'s
  scope) before any code changed, with several plausible alternative
  mechanisms tested against real data and rejected first.
- Background/empty evidence matching the v5 pattern cannot produce a
  confident species suggestion (proven RED→GREEN, on both plausible crop
  tiers).
- Wrong-subject evidence (uncorroborated geometry) cannot produce a
  confident Visit species suggestion, by the same mechanism.
- Eligible good evidence still works (extensive non-regression proof, real
  benchmark re-run, 0/7 mandatory real positive controls affected).
- Abstention policy preserved exactly (untouched code path, proven still
  reachable and still functioning).
- Reviewed truth preserved (untouched code path, proven directly).
- Stale invalid inference does not survive *incorrectly*: no new ineligible
  suggestion can ever be created; pre-existing suggestions behave exactly
  as the already-accepted `evidence_below_resolution_floor` reason already
  did (no retroactive supersession, by unchanged design, not a new gap).
- Tier 1 clean (82/82). Tier 2 clean (456/456). Tier 3 clean apart from 2
  independently proven, pre-existing, unrelated failures (see "Validation").

Not forced: the honestly disclosed residual (a detector-sourced-but-
still-wrong crop, and wrong-subject-among-several-real-subjects) remains
real, quantified, and open — this milestone closes the reproduced defect
class and a real, validated slice of the broader named regression, not the
entirety of it, exactly as precedented by the original Identification
Eligibility v1 milestone's own Classification A alongside its own disclosed
54% cohort-D residual.
