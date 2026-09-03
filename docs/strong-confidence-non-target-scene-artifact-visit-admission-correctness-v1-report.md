# Strong-Confidence Non-Target & Scene-Artifact Visit Admission Correctness v1: Report

**Date:** 2026-09-02. **Classification: B.**

A real Gate-A correctness investigation and fix, reopened by Representative Daylight Gate A Field Acceptance v11's own field evidence: 8/18 confirmed-false Visits (44.4%), all admitted via the *strong-detection bypass* -- a mechanism no prior milestone had directly examined. Two genuinely distinct false subclasses were separated, deterministically reproduced against the real, unmodified production path, and investigated to their first irreversible product decision. One subclass (a real person's presence spatially contradicted, same-frame, by the detector's own contradicting class output) is now measurably closed by a new, bounded, class-semantics-preserving check in the tracker. The other (a recurring hard-negative location's own historical weakness never reaching scene-confusor because corroboration-rejected occurrences left no trace) is genuinely improved by a bookkeeping fix, but the milestone's own investigation proves -- numerically, against the real mechanism, not by assertion -- that this does **not** flip v11's own Visit 018 outcome: scene-confusor's two independent confidence escapes are, by original design, unconditional on the *current* candidate's own strength, and both are required by the real, field-proven feeder-pole stationary-real-bird control. That residual is reported honestly, not concealed. No MDv5/NMS/BioCLIP threshold changed. No whole-frame human veto. No spatial blacklist. See "Decision," below, for the complete accounting.

## Starting state

Verified before any change:

- Repository/branch: `/home/zkelder/projects/mockingbird-active`, `main`.
- Accepted HEAD at session start: `fbfac71` (the reconciliation commit recording Representative Daylight Gate A Field Acceptance v11) -- exact match to the milestone brief's expected state.
- Schema: v58, unchanged throughout this milestone (no migration; both fixes are additive logic changes over already-existing tables/facts).
- Latest accepted milestone: Representative Daylight Gate A Field Acceptance v11 (classification B).
- Gate A / Lane R: OPEN.
- Current authorization at start: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED` -- this milestone's own governing brief is the explicit authorization for this specific correctness work, consistent with every prior milestone in this sequence.
- Not pushed (306 commits ahead of `origin/main` at session start).
- Worktree safety: `git status` showed exactly the seven expected preserved untracked files, untouched, and no other diff. Two peer sessions in this same working directory (`mockingbird-active-16`, interactive; and one other `ccd-cli` process) were checked via `/proc/<pid>/cwd`; neither showed any file-modification activity in the 10 minutes preceding this session's first edit, and no `.git/*.lock` file existed. All seven preserved files (`docs/wildlife-detector-training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`, `scripts/materialize_wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`, `src/mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`, `tests/test_small_bird_benchmark.py`) are confirmed byte-identical/untouched at report time.

## V11 field evidence

Directly re-read from `docs/representative-daylight-gate-a-field-acceptance-v11-report.md` ("False Visits," "Useful evidence," "Scene-confusor field proof," "Mechanism composition"):

- 8/18 confirmed-false Visits (44.4%), all admitted via `candidate_quality_gate._insufficient_detector_corroboration`'s own `strong_detection_count > 0` bypass -- a proposal with even one clean, confident (>=0.70) detection skips the count/concentration corroboration check entirely, by design, before this milestone.
- 7 of the 8: a real utility/landscaping worker in-frame, "correctly detected as MDv5's own `animal`-class false positive at genuinely high confidence (up to 0.858)" -- explicitly named as matching "the already-accepted, out-of-scope Person-Background-False-Positive residual class from v9's own Visits 139/140."
- 1 of the 8 (Visit 018): "a leaf/branch cluster at the classic Location-A geometry that happened to clear the strong-detection threshold 6 times in this one occurrence" -- the exact v8/v9/v10/v11-recurring foliage/branch-tip coordinates (bbox center (0.202, 0.691)), previously always weak/never-strong and always correctly rejected.
- Useful-evidence rate: 43.5% raw / 62.5% excluding the person confound -- both below the v5/v7 94-96% band.
- Zero confirmed-false Visits received a species guess (`species_guess is None` for all 8, directly confirmed from the `visits` table) -- Gate B's own abstention safety held completely.
- Scene-confusor was directly queried (not inferred): 14 regions tracked, `occurrence_count` 1-5, `suspected_count = 0` for every region -- every region crossing the suspicion threshold held genuinely strong detections and was correctly, by design, never suspected (this is the mechanism this milestone investigates in depth, below).

## Failure subclasses

Per the governing brief's own required decomposition (§5), the two v11 false subclasses have **distinct root causes and distinct fixes**, confirmed by direct code tracing, not assumed:

- **A. Real person/human-associated detector activity (7 Visits).** Root cause: the raw MDv5 detector's own class output was wrong for these specific detections (`is_animal=True`, `label="animal"`), not a MockingBird mapping/logic defect -- confirmed by direct code inspection (see "Detector-semantic analysis," below) and matching the already-investigated, already-accepted 2026-08-20 precedent (`docs/person-background-false-positive-attribution-v1-report.md`) exactly.
- **C. Strong-confidence scene artifact (1 Visit, 018).** Root cause: a recurring, always-weak hard-negative geometry ("Location A") happened, for the first time, to clear `strong_detection_threshold` on 6 detections in one occurrence -- and because every one of its *prior* weak occurrences had been rejected by corroboration *before* scene-confusor's own bookkeeping call was ever reached, the region carried zero recorded history at the moment it most needed it.
- **B. Real non-target animal, if present:** not present in v11's own 8 confirmed-false Visits (no dog/domestic-animal confound this cohort, unlike the 2026-08-20 precedent's own person-with-a-dog case) -- addressed structurally below under "Existing product policy," not fabricated as a new finding.
- **D. Genuine target wildlife:** the 10 confirmed-real Visits, used throughout as positive controls.

These two root causes are **not the same mechanism wearing two faces**: A is a wrong upstream *class label*; C is a wrong upstream *history availability*. No single rule was force-fit across both; each got its own investigation and (where safe) its own fix.

## Person-associated reproducer

Built forward from v11's own disclosed facts (bbox-scale numbers were not individually published per-Visit, so a realistic, disclosed, field-consistent sequence was constructed -- see "Self-review" for exactly what this reproducer does and does not prove) and driven through the real, unmodified production path: `ProviderNeutralFrameTracker.observe()` -> `build_tracklets`/`assemble_visit_episodes` -> `CandidateVisitAuthorityAdapter.attempt_candidate` -> a real, isolated `ProductRepository` (identical methodology to `tests/test_independent_corroboration_value_persistent_confusor_v1.py` and the 2026-08-20 precedent's own `tests/test_human_background_admission_hard_negative_2026_08_20.py`).

Sequence (`tests/test_strong_confidence_non_target_scene_artifact_v1.py::TestPersonAssociatedFalseVisit`, `_person_confound_ticks`): two genuine, untainted `animal`-class detections (0.30, 0.35 -- a new subject's own first, uncertain appearance) bracketing six frames where an `animal`-class detection (0.78-0.86, matching v11's "up to 0.858") and a same-geometry `person`-class detection *both* appear on the same frame -- the architecturally-grounded shape MDv5's own per-candidate-argmax-then-per-class-NMS decode pipeline can legitimately produce for one real, torn-between-classes object (confirmed directly from `mdv5_decoder.decode_md_v5_raw`: each raw candidate box gets its own single best-scoring class via `argmax` *before* NMS, and NMS then runs *separately within each class* -- never across classes -- so two different raw candidates covering the same real object can each win a different class).

**Pre-fix (verified via `git stash push -- src/mockingbird/observation/frame_tracker.py`, real pytest run, not asserted):** `outcome.outcome == "created"` -- reproducing v11's own admitted false Visit shape exactly (all 8 genuine+tainted detections counted, `strong_detection_count > 0` bypasses corroboration trivially).

**Post-fix:** `outcome.outcome == "reject_insufficient_detector_corroboration"`, `reason == "never_strong_and_minimal_detector_corroboration"` -- the six tainted frames' `animal` detections are excluded from ever corroborating the track; only the two genuine, untainted, never-strong detections remain, which are neither consecutive (each isolated between excluded frames, so `max_consecutive_detector_confirmed_frames = 1`) nor sufficient in count (`2` does not exceed `2*1+1=3`).

An isolation control (`test_isolation_control_without_cooccurring_person_detection_still_admits`) proves the mechanism, not an artifact of the synthetic sequence: the *identical* confidence/timing pattern with every `person`-class detection removed still reaches `created` on current (fixed) code -- confirming it is specifically the co-occurring non-animal evidence, not some other property of the sequence, that changes the outcome.

## Strong-artifact reproducer

Built directly from v11's own disclosed Location-A confidence values (0.131, 0.372) and Visit 018's own disclosed shape ("cleared the strong-detection threshold 6 times in this one occurrence"), reusing the exact `_LOCATION_A_BOX` coordinates the sibling `test_independent_corroboration_value_persistent_confusor_v1.py` already established for this identical, real, cross-cohort-recurring geometry. Four sequential single-generation proposals against one shared, isolated repository (`TestStrongSceneArtifactAtLocationA`), simulating recurrence across a realistic continued-deployment window (see "Remaining risk" for why one bounded field-acceptance session's own fresh-per-cohort database cannot itself demonstrate more than 1-2 real occurrences of this exact location -- Location A is documented recurring across v8/v9/v10/v11, four *separate* disposable databases, not one continuous one):

1-3. Weak, single-generation, 2-detection occurrences (0.12-0.37, never strong) -- each independently rejected: `reject_insufficient_detector_corroboration` / `never_strong_and_minimal_detector_corroboration`.
4. Six detections, all >=0.70 (0.72-0.78) -- Visit 018's own exact shape.

**Pre-fix (verified via `git stash push -- src/mockingbird/repository/product_repository.py`):** occurrences 1-3 leave **zero** trace in `scene_confusor_regions` (`len(regions) == 0` after all three) -- `_touch_scene_confusor_region` was reachable only once `evaluate_evidence_admission` already returned `admit`. Occurrence 4 is then evaluated against a *blank* region history, `find_matching_region` correctly (but unhelpfully) reports "no recurring geometry match," and the proposal is `created` -- the exact real v11 outcome.

**Post-fix:** occurrences 1-3 still return the identical outcome/reason (bookkeeping only, never a behavior change for the rejected proposal itself) but now correctly build `occurrence_count = 3` in `scene_confusor_regions`. Occurrence 4 is now evaluated against real history -- and **is still `created`** (see "First irreversible error" and "Scene-confusor interaction," below, for the precise, numeric reason this specific shape is not closed by this fix). A companion reproducer with the identical three weak rejections but a 4th occurrence that clears the corroboration *count* axis (never strong -- 5 detections, max 0.48) rather than the strong-detection bypass **is** now correctly caught: `blocked_scene_confusor_suspected` / `recurring_static_scene_geometry` (pre-fix: `created`, confirmed via the same stash methodology). This is the fix's own real, proven, disclosed scope.

## Positive controls

All required by the governing brief, all passing on current (post-fix) code, driven through the same real production path:

- **Strong real bird:** admits unchanged (`TestStrongAndWeakRealBirdPreserved::test_strong_real_bird_admits_unchanged`).
- **Weak real bird:** admits via count-based corroboration, unchanged.
- **Stationary real bird:** 4 repeated strong admissions at one fixed location, all `created`, none suspected -- directly reproducing v11's own field-proven feeder-pole result under the new fix.
- **Bird while a person is also in frame, spatially separate:** `TestBirdPersonSpatialIndependence` -- a bird at one location and a person at a spatially distant one, same frames; the bird's own track and admission are completely unaffected (IoU between the two locations is 0, so the new same-frame exclusion never engages).
- **Real non-bird wildlife:** existing policy already covers this (see "Existing product policy," below) -- not newly built here, reused.
- **Simultaneous wildlife subjects:** unaffected by construction (neither fix touches multi-subject/Event-sharing logic); reconfirmed by the full, unmodified `test_independent_corroboration_value_persistent_confusor_v1.py`/`test_candidate_visit_authority*.py`/`test_admission_replay.py` suites passing unchanged (see "Validation").
- No control required inventing a new fixture pattern; all reuse the exact real-production-path methodology already established by the sibling 2026-09-02 milestones.

## First irreversible error

**Person subclass (fixable sub-case: co-occurring class contradiction).** The first point the product *already has enough information* is inside `ProviderNeutralFrameTracker.observe()`, at the same-frame detection set it already receives every frame (`frame_driven_provider._process_frame` never filters by class before calling `observe()`) -- specifically, the moment an `animal`-class detection is about to be treated as tracking-eligible evidence while a same-frame `person`/`vehicle`-class detection substantially coincides with it. Before this fix, that contradicting evidence was already present in the very same function call and was simply discarded without ever being consulted (`animals = tuple(item for item in detections if item.is_animal is True ...)`, with every `is_animal is False` item silently dropped). This is strictly earlier than proposal construction, candidate-quality admission, or evidence scoring -- by the time a proposal exists at all, the contradicting per-frame evidence has already been thrown away and can never be reconstructed.

**Person subclass (unfixable sub-case: pure single-class misclassification).** When MDv5's own raw output never emits a contradicting non-animal box anywhere near the same region -- the 2026-08-20 precedent's own Visits 139/140 shape, and plausibly some or all of v11's own 7 person Visits -- there is no first irreversible *MockingBird* error at all: the wrongness is the raw detector's own class output, upstream of every MockingBird stage. This matches, not merely echoes, the already-accepted 2026-08-20 finding.

**Artifact subclass.** The first point the product already has enough information, but does not yet act on it, is `product_repository.ProductRepository._create_candidate_visit_locked`'s own scene-confusor call -- but the investigation proves this is a *necessary, not sufficient* fix: `_touch_scene_confusor_region` being unreachable for a corroboration-rejected proposal is real and now closed, but the actual admission decision for a genuinely strong single occurrence is decided even earlier and independently of any region history, inside `scene_confusor.evaluate_scene_confusor_suspicion`'s own steps 5 ("materially stronger than this region's own history") and 6 ("independently strong, unconditionally") -- both deliberately history-independent by original design. There is no available downstream stage (evidence scoring, species eligibility, Visit assembly) with a *different* signal about this same fact; every one of them already runs, correctly, on the same wrong upstream "this is a confident subject" belief.

## Existing product policy

Searched `docs/product-doctrine.md`, `docs/roadmap.md`, and code before inventing anything (per the brief's own §15 instruction):

- **Person detections:** already excluded from ever starting or extending a wildlife track, categorically, since before this milestone (`frame_tracker`'s own `is_animal is True` gate at the very first line of `observe()`'s detection filter) -- confirmed still true at this milestone's starting HEAD by direct code read and by the 2026-08-20 report's own identical finding ("a real `person`-class MDv5 output could never have reached tracking at all"). **Reused, not reinvented.**
- **Domestic / non-target animal treatment:** `product-doctrine.md`'s own "Review Decision" vocabulary explicitly lists `squirrel` and `cat` alongside `northern_cardinal`/`blue_jay` as first-class correction labels, and Broader Wildlife Maturity v1 (2026-08-24, already accepted) explicitly extended evidence-scoring/taxonomy to large mammals as legitimate wildlife subjects. MDv5 itself has no domestic-vs-wild class distinction -- every non-human, non-vehicle detection is uniformly `broad_class="animal"`, whether a wild bird, a squirrel, a deer, or a neighbor's cat. **Existing, already-settled policy: a genuine animal-class detection (domestic or wild) legitimately becomes a Visit; the wild/domestic/species distinction is a Review Decision, made by a human at correction time, never an admission-time exclusion.** This directly answers §14: v11's own 8 confirmed-false Visits involved no dog/domestic-animal confound (unlike the 2026-08-20 precedent), so no new domestic-animal policy question was actually live this milestone -- and where it is live (a real dog/cat), the existing, already-accepted policy already covers it. Nothing was invented; no `STOP` was required.
- **Person-Background-False-Positive residual:** already investigated in full (`docs/person-background-false-positive-attribution-v1-report.md`, Decision B, 2026-08-20) and already, correctly, marked out-of-scope for a Gate-A confidence/count/geometry fix -- "no threshold clears both conditions" was proven with real numbers (a real false Visit's own `max_confidence` exceeded every real bird that session). **Reused, not re-litigated**, for the sub-case this milestone also cannot close (see "Person result," below).
- **BioCLIP is not a validity gate:** already product doctrine ("Product promise," "The truth boundary") and already the exact design Identification Eligibility & Abstention v1 implements; this milestone adds nothing here and changes nothing about when species inference runs -- it only prevents some proposals from ever reaching Visit creation in the first place.

## Detector-semantic analysis

Traced precisely, at the code level, not assumed:

- MDv5's ONNX decode path (`onnx_provider._decode`/`_observation`, `mdv5_decoder.decode_md_v5_raw`) already decodes and returns **every** class MDv5's raw output head reports per frame (`broad_classes = ("animal", "person", "vehicle")`), each carrying its own `is_animal` fact (`is_animal = label in bundle.animal_classes`, `animal_classes == ("animal",)` for the MDv5 decoder, strictly validated by `OnnxModelBundle.load`).
- Class assignment happens **before** non-max suppression: `class_scores.argmax(axis=1)` picks each raw candidate's own single best class first; NMS then runs **separately within each class** (`for class_index in range(MDV5_CLASS_COUNT): ... _class_nms(...)`), never across classes. This means a single real-world object can legitimately decode as two overlapping boxes on the same frame, one per class, when the model is genuinely torn between them -- confirmed as an architectural possibility of this exact decoder, not a MockingBird adapter bug (the identical "no off-by-one/mislabeling bug" conclusion the 2026-08-20 report already reached for the *animal*-class-output side of this same question).
- `frame_tracker.observe()` receives this full multi-class tuple every single frame, unfiltered by the caller (`frame_driven_provider._process_frame` passes the detector's raw output straight through, minus only privacy/ignore-zone exclusion) -- so the co-occurring class information was always present at the tracker's own doorstep. Before this milestone, it was discarded unconditionally and unconsulted.
- Downstream of the tracker, `broad_class` (the resolved class label) *is* already threaded end-to-end without loss -- through `TrackUpdate`, `Tracklet`, `AssembledVisitProposal`, all the way to `candidate_quality_gate`'s own `ProposalSupportFacts.broad_class` and `scene_confusor`'s own per-class region keying. It was never lost; it was simply never *cross-checked against a same-frame contradiction* before admission.
- `candidate_quality_gate.evaluate_evidence_admission` reads `broad_class` only to confirm it is non-empty (a defense-in-depth structural check) -- it never branches on its *value*. This confirms the class distinction that exists is not consulted for admission purposes anywhere downstream of the tracker.

## Evidence-quality analysis

`evidence_scoring.score_proposal_evidence`/`_score` was read in full: it computes genuinely useful, already-existing signals -- subject containment/edge-clipping, subject-area-ratio/pixel-detail, sharpness (`ImageFilter.FIND_EDGES` RMS), exposure, temporal alignment, track-support facts. None of these are *content/semantic* signals (none ask "does this look like an animal"), and none distinguish a well-lit, sharp, fully-contained crop of a leaf/branch cluster from an equally well-lit, sharp, fully-contained crop of a real bird -- confirmed directly: Visit 018's own evidence already passed every one of these checks (it has a valid `identification`/`context` pick with real geometry, exactly what let it reach the corroboration check at all). **No already-computed evidence-quality signal in this codebase distinguishes the strong-artifact subclass from a genuine strong sighting** -- consistent with, not contradicting, this milestone's own non-goal of not adding new ML to manufacture one.

## Scene-confusor interaction

Investigated in full, against the real mechanism (`scene_confusor.evaluate_scene_confusor_suspicion`'s own seven-step decision order), not by inspection alone:

1. **Confirmed defect (fixed):** `_touch_scene_confusor_region` in `product_repository.py` was reachable only from the branch already following `if not quality.admitted: return ...` -- i.e., only once `evaluate_evidence_admission` already said `admit`. A location whose *every* occurrence to date failed corroboration (this milestone's own reproduced Location-A shape) left **zero** trace in `scene_confusor_regions`, no matter how many times it recurred within one session, because it was never once admitted before the occurrence that finally bypassed corroboration outright.
2. **Confirmed, but insufficient alone (not fixed -- disclosed):** even with real, accumulated history (`occurrence_count = 3`, tight `centroid_spread`, well under `geometry_spread_ceiling`), a genuinely strong (>=0.70) 4th occurrence still escapes suspicion, because `evaluate_scene_confusor_suspicion`'s own step 5 ("this candidate's own confidence is materially [>= 0.15] higher than anything this region has ever produced") and step 6 ("this candidate's own confidence independently clears `strong_detection_threshold`, regardless of this region's own history") are both checked **unconditionally on the current candidate's own confidence alone** -- neither considers `occurrence_count`, `centroid_spread`, or anything else about the region's history once triggered. Both were deliberately designed this way, and both are load-bearing for the real, field-proven feeder-pole positive control: `docs/scene-confusor-suspicion-contract.md`'s own design rationale states a real popular feeder-perch's own geometry spread measurably exceeds `geometry_spread_ceiling` by its 3rd occurrence, and step 6's own docstring states a static/hardware confusor's confidence "essentially never reaches this bar at all" (0.417 measured maximum in that milestone's own real cohort) -- an empirical assumption v11's own Visit 018 now directly falsifies for *this* location, but which this milestone cannot safely disprove in general without the exact real spread/confidence-history numbers a live field session would produce (explicitly out of scope, "Do not run v12" -- see "Remaining risk").
3. **What the fix *does* newly close:** a recurring, never-strong location that eventually clears the corroboration *count* axis honestly (many individually-insufficient but genuinely accumulating weak detections, never touching the strong-detection bypass) is now correctly caught by scene-confusor's own unmodified logic, because its own weak-vs-weak confidence delta does not trigger either escape. This is a real, materially-different, and still-relevant shape (the exact one the accepted Independent Corroboration Value v1 milestone's own within-proposal fix does not cover for a *single*-generation proposal, and the exact shape the original v10 persistent-confusor report itself first named).

Given both escapes are load-bearing for an accepted, field-proven positive control, and given no real field data exists in this sandbox to safely re-derive either constant or add a history-conditioned carve-out to them, **this milestone leaves `scene_confusor.evaluate_scene_confusor_suspicion` itself completely unmodified** (per the brief's own explicit permission, §19: "If the correct fix belongs elsewhere: leave scene-confusor untouched"). The fix applied is entirely in `product_repository.py`'s own call-site ordering, not in the pure decision module.

## Locked contract

Implemented, and only what the reproducers above prove:

1. **Same-frame class-contradiction exclusion (tracker level).** An animal-class detection that substantially (`IoU >= 0.3`, reusing `scene_confusor.GEOMETRY_IOU_THRESHOLD`'s own already-field-justified same-region-coincidence bar, not the tracker's own looser cross-frame-motion-tolerance thresholds) coincides, on the *same frame*, with an explicitly non-animal (`person`/`vehicle`) detection is treated as absent evidence for that frame -- never as corroborating support for a wildlife track. Scoped to same-frame, same-location coincidence only: no whole-frame veto, no cross-frame history, no new confidence threshold.
2. **Scene-confusor bookkeeping on corroboration-reject.** A proposal rejected specifically via `reject_insufficient_detector_corroboration` (and only that outcome -- every other reject outcome lacks a guaranteed-valid geometry pick) now also touches this Stream's scene-confusor region history, exactly as an admitted proposal already did -- bookkeeping only; the rejected proposal's own outcome/reason is never changed by this.

Both are additive, bounded, reuse only already-established constants/conventions, and change zero MDv5/NMS/BioCLIP/eligibility thresholds.

## Implementation

- `src/mockingbird/observation/frame_tracker.py`: new module constant `_SAME_FRAME_NON_ANIMAL_OVERLAP_IOU` (0.3, reused from `scene_confusor.GEOMETRY_IOU_THRESHOLD`, duplicated per this codebase's own established "each pure module stays self-contained" convention); `observe()` now computes this frame's own `non_animal_boxes` and excludes any `animal`-class detection overlapping one from the `animals` tuple used for both track-starting and track-continuation; new helper `_overlaps_non_animal_class`; a new bounded, purely additive diagnostic counter (`TrackerStep.same_frame_class_conflict_exclusions`, folded into `frame_driven_provider`'s existing facts dict exactly like `confidence_dip_bridges` already is) -- observable, never a raw per-detection/per-frame record.
- `src/mockingbird/repository/product_repository.py`: `_create_candidate_visit_locked` now runs the scene-confusor touch (bookkeeping) for `reject_insufficient_detector_corroboration` too, not only for an admitted proposal; the rejected proposal's own returned outcome/reason is unchanged (still exactly `quality.outcome`/`quality.reason`); `evaluate_scene_confusor_suspicion` itself untouched.
- `tests/test_strong_confidence_non_target_scene_artifact_v1.py` (new): 11 tests, both reproducers, both fixes' before/after proof (via `git stash`), and every required positive control.
- No schema change. No new numeric constant beyond the one explicitly-reused, already-established 0.3 IoU bar. No MDv5/NMS/BioCLIP/eligibility threshold touched -- confirmed by `grep` across both diffs.

## Person result

**Partially closed.** The co-occurring same-frame class-contradiction shape is now measurably prevented (deterministic RED->GREEN, above). The pure single-class-misclassification shape (MDv5 itself never emits a contradicting box anywhere near the false region) remains exactly the already-accepted, already-investigated 2026-08-20 residual -- unchanged, not newly discovered, not silently reopened. Whether v11's own specific 7 Visits fall into the closed or open sub-case cannot be determined from this sandbox (the original per-detection ledger lives on a disposable field-acceptance instance this milestone was explicitly not authorized to re-run or query); the fix is real and correctly targets the mechanism regardless of which sub-case any individual v11 Visit turns out to have been.

## Strong-artifact result

**Not closed for the field-observed shape.** Visit 018's own exact "recurring-weak-then-suddenly-strong, single occurrence" pattern is proven, numerically, to still admit post-fix (see "Strong-artifact reproducer"). A real, adjacent, and now-fixed gap (a weak-but-eventually-count-corroborated recurring confusor) is closed. Scene-confusor's own historical bookkeeping is now honest and complete for every occurrence that reaches it, which the milestone's own diagnostics/observability goals value independent of whether it flips this one case.

## Bird-plus-person result

Preserved, directly tested: a bird and a person in the same frames, spatially separate, produce an unaffected bird admission (IoU between the two locations is 0; the new exclusion never engages). No whole-frame suppression implemented or risked.

## Strong-real result

Preserved, directly tested and via the full unmodified sibling/hard-negative suites: a strong, confident real bird still admits via the unmodified strong-detection bypass.

## Weak/stationary-real result

Preserved, directly tested: a weak/small/distant bird still admits via count-based corroboration; a stationary bird repeatedly re-admitted at one fixed location is never suspected by scene-confusor, both before and after this milestone's own bookkeeping fix (the fix only ever adds history for *rejected* occurrences -- an admitted stationary bird's own code path is untouched).

## Multi-subject result

Unaffected by construction: neither fix touches `visit_episode_assembler`'s Event-sharing/multi-subject logic, `candidate_visit_authority`'s ambiguous-boundary arbitration, or any shared mutable state between independent `_Track` instances (each track's own confidence/detection accounting is private to that track; the tracker has no code path where one track's evidence can contribute to another's). Confirmed by the full, unmodified multi-subject-relevant suites (`test_independent_corroboration_value_persistent_confusor_v1.py`, `test_candidate_visit_authority*.py`, `test_admission_replay.py`) passing unchanged.

## Existing-hard-negative regression result

All prior accepted hard-negative/corroboration/scene-confusor mechanisms verified unchanged: the full `test_hard_negative_visit_admission_precision_v1.py` (bare-minimum single-generation chains, still rejected) and `test_independent_corroboration_value_persistent_confusor_v1.py` (concentrated-multi-generation chains, still rejected; the scene-confusor composition test at line 830, `test_repeated_single_generation_never_strong_occurrences_compose_with_scene_confusor`, still produces the identical `["created", "created", "created", "blocked_scene_confusor_suspected"]` sequence) suites pass unchanged, 0 failures.

## Species result

Re-proven directly: every proposal rejected by either mechanism never creates an `observation_candidate_visits`/`VisitModel` row at all (`outcome.visit_id is None`, `outcome.event_id is None`, asserted explicitly in `test_rejected_confusor_history_does_not_grant_species_inference_any_input`) -- automatic species inference has no input to run against, by construction, not by a separate gate that could itself have a gap.

## Reviewed-truth result

Preserved by construction: neither diff touches any `ReviewLabel`/review-correction/`reviewed_real_count`/`reviewed_false_count` code path. `_touch_scene_confusor_region`'s new additional call site updates only `occurrence_count`/`max_confidence_observed`/centroid bounds -- the same fields an admitted proposal already updated -- never `reviewed_real_count`/`reviewed_false_count`, which remain exclusively human-review-driven.

## Privacy result

Not worsened. No new person crop, person track, face/identity feature, or long-lived per-person record is created or retained. The one new state is a purely aggregate, bounded, per-Stream integer counter (`same_frame_class_conflict_exclusions`) mirroring an existing counter's own convention exactly; the same-frame overlap check itself is stateless (computed fresh each frame from data the pipeline already held, discarded immediately after).

## V11-shaped replay

Assembled from the required v11-shaped case list, each driven through the real production path (not manufactured as an aggregate score -- see per-case results above and the actual test file for exact assertions): person-associated false Visit (fixed sub-case) admits pre-fix, rejects post-fix; strong scene-artifact false Visit still admits both before and after (disclosed); strong real bird admits; weak real bird admits; stationary real bird admits, never suspected; bird with person concurrently present admits, person does not; existing weak-confusor mechanisms (bare-minimum chains, concentrated-chain rejection, scene-confusor composition) unchanged. Sustained-activity/fallback/stop-finalization and true-latency/RTT mechanisms are untouched by either diff and were not re-exercised (bounded archaeology; no code path this milestone touched intersects them).

## Diagnostics

The person-subclass fix exposes a new, bounded, aggregate `same_frame_class_conflict_exclusions` fact (mirroring `confidence_dip_bridges`'s own established convention) -- observable via the same live `observation/status` facts surface every other tracker counter already uses, with zero raw per-detection/per-frame surveillance detail. The artifact-subclass fix does not introduce a new rejection reason: a corroboration-rejected proposal still returns exactly `reject_insufficient_detector_corroboration`/`never_strong_and_minimal_detector_corroboration` (unchanged) -- only the durable region bookkeeping behind it changes, which is already exposed via the existing `scene_confusor_regions` diagnostic surface v11's own report used directly.

## Rate-limit interaction

Unaffected. `evaluate_candidate_authority` (including `max_candidates_per_session`/`max_candidates_per_hour`) runs, and any capacity slot is consumed, entirely *before* `_create_candidate_visit_locked` is ever called (confirmed by that function's own docstring: "Called only from inside `create_candidate_visit_from_proposal`'s own transaction, only after the gate already returned `create`" -- referring to the authority gate). Neither fix changes this ordering. The person-subclass fix can, if anything, *reduce* wasted capacity consumption in the fixed sub-case: a proposal that never accumulates enough untainted evidence to confirm a track at all never reaches authority/rate-limiting in the first place, rather than consuming a slot only to be rejected later.

## Performance

No new expensive ML, no new network dependency, no unbounded per-frame history. The same-frame overlap check is `O(animal detections this frame x non-animal detections this frame)` -- both counts are already bounded by `OnnxModelBundle.max_observations_per_frame`/`MAX_DECODE_ROWS`, and in real deployment are single-digit per frame. The scene-confusor bookkeeping fix adds exactly one already-existing, already-bounded DB read+write per corroboration-rejected proposal (previously zero) -- the identical cost an admitted proposal already paid.

## Self-review

Attacked each listed concern directly:

- **Whole-frame person veto:** not implemented. The exclusion requires spatial coincidence (`IoU >= 0.3`) with the specific animal-class box under consideration; a person anywhere else in frame has zero effect (directly tested).
- **Domestic animal policy invented accidentally:** not invented -- existing doctrine/precedent found and reused (see "Existing product policy"); no new taxonomy rule added anywhere.
- **Strong real birds rejected:** not observed; directly tested (strong/weak/stationary real bird, all preserved) and reconfirmed by the full existing regression suite.
- **Person+bystander scenes suppressing real wildlife:** not observed; directly tested (`TestBirdPersonSpatialIndependence`).
- **Detector class lost/incorrectly mapped:** investigated in depth (see "Detector-semantic analysis") -- class semantics were never lost downstream of the tracker; they were simply never cross-checked for same-frame contradiction before this fix, which is exactly what was added, nothing more.
- **Scene artifact fixed via a confidence threshold:** explicitly avoided -- the fix touches only *when* bookkeeping happens, never a confidence comparison; `scene_confusor.py` itself has zero lines changed.
- **Scene-specific coordinate overfit:** zero coordinate literals read or written by either fix (both operate purely on IoU/class-label facts); `_LOCATION_A_BOX`/`_PERSON_REGION_BOX` exist only in the new test file as reproducer geometry, never in production code.
- **Privacy regression / person data retention growth:** addressed above -- none.
- **Sibling semantic contamination:** addressed above ("Multi-subject result") -- no shared mutable state between tracks exists in this architecture.
- **Previous corroboration regressions:** the full `test_independent_corroboration_value_persistent_confusor_v1.py`/`test_hard_negative_visit_admission_precision_v1.py` suites re-run unchanged, 0 failures.
- **Unexpected species path:** addressed above ("Species result") -- rejected proposals create no Visit row, by construction.

No finding required a code change beyond the two already described; nothing found and left unfixed was silently dropped -- every open item is named in "Remaining risk," below.

## Validation

### Tier 1

The new `tests/test_strong_confidence_non_target_scene_artifact_v1.py`: **11/11 passed.** Before/after (`git stash`) proof for both mechanisms confirmed the predicted pre-fix behavior in every case (2 tests flip outcome for the artifact fix; 1 test flips outcome for the person fix; every other test -- including the deliberately-still-open Visit-018-shaped one -- is confirmed identical pre/post, proving the fixes are precisely scoped, not incidentally broader).

### Tier 2

28 directly-affected-subsystem test files (MDv5/ONNX output adaptation, detector class mapping, tracker, proposal assembly, candidate-quality gate, scene-confusor + its repository layer, evidence scoring, candidate authority (+ acceptance), Visit assembly, admission replay, the 2026-08-20 human-background hard-negative fixture, perception-replay regression (module/CLI/IO), counterfactual lineage, detection-quality accounting, admission policy, frame-driven provider (+ CLI), candidate-visit repository/adapter, identification eligibility (+ its own regression fixture), reviewed-observation revision, reviewed-replay lineage), run together with the new file:

**705 passed, 0 failed.**

`ruff check` on both touched production files: identical finding count and identical finding *codes* before and after this milestone's diff (57, all pre-existing in `product_repository.py`'s own already-known backlog -- confirmed via a `git stash`-isolated baseline comparison, every diff line a pure line-number shift, zero new finding); the new test file: 0 findings.

### Tier 3

One full authoritative Core run (`python scripts/verify_core.py`, the whole backend suite except `slow`-marked tests, run as one bare foreground/background process, not chunked):

**5610 passed / 2 failed / 3 skipped / 23 deselected / 11 xfailed (1928.46s / 32m08s).**

The 2 failures (`tests/test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary`, `::test_human_correction_updates_place_biodiversity_intelligence_correctly`) are independently confirmed pre-existing and unrelated, not merely assumed: every file this milestone touched (`frame_tracker.py`, `frame_driven_provider.py`, `product_repository.py`) was `git stash`-isolated back to the exact starting HEAD (`fbfac71`), and the identical two tests re-run in isolation fail identically on that clean baseline, with the exact same assertion mismatch (`historical_status`: `'seen_before'` vs expected `'new'` -- Place Intelligence biodiversity-taxonomy-history logic, zero code-dependency relationship to Visit admission/tracker/quality-gate/scene-confusor code this milestone touched). This is the same already-repeatedly-documented pair `docs/release-execution-state.md` §14 names recurring across numerous earlier Core checkpoints, including the immediately-prior Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1 checkpoint, which touched the same two production files (`candidate_quality_gate.py`/`product_repository.py`) this milestone's own `product_repository.py` change also touches, and reached the identical independent conclusion.

## Remaining risk

- **The field-observed strong-artifact shape (Visit 018) itself remains open.** No existing, safe-to-reuse Gate-A signal separates it from a real bird's own first strong sighting at any location (see "Scene-confusor interaction"); closing it would require either new evidence-quality/content signals (explicitly out of scope -- Gate-B/new-ML territory) or real field data on genuine repeat-wildlife confidence-history/geometry-spread patterns this sandbox cannot safely produce without a live session.
- **The pure single-class person-misclassification shape remains open**, matching the already-accepted 2026-08-20 precedent exactly -- unchanged, not reopened, not newly discovered.
- **Whether v11's own specific 7 person Visits and Visit 018 individually fall on the closed or open side of either fix cannot be confirmed** without the original per-detection ledger, which lived on a disposable field-acceptance instance this milestone was not authorized to re-run or query.
- The new same-frame exclusion has one disclosed, narrow, honestly-named edge case: a real bird landing directly on/against a person (e.g. hand-feeding) at IoU >= 0.3 could, in principle, have that one frame's contribution excluded too -- rare, and not one of the milestone's required positive controls, but named rather than hidden.
- Cross-occurrence scene-confusor history still cannot see anything blocked upstream by `blocked_ambiguous_boundary` (authority-level, before the quality gate) -- this milestone's own fix closes only the quality-gate-level corroboration-reject gap, not the authority-level one (a materially larger, separately-scoped change, deliberately not attempted here).

## Next field proof

Not self-authorized (per the brief's own explicit instruction). If this milestone is accepted, a future, separately-authorized daylight tranche should specifically seek to measure:

- whether the same-frame class-contradiction fix materially reduces person-associated false Visits in a cohort with a real, extended human presence (ideally one where the person is visible long enough for MDv5's own class output to genuinely vary frame-to-frame);
- whether any further strong-confidence scene-artifact false Visit recurs, and if so, whether it shows the same "weak-history-then-sudden-strong" shape this milestone could not close, or a materially different one;
- no whole-frame human suppression of real birds (direct visual review of every Visit in any session with a person present);
- weak/stationary bird recall preserved (unchanged from v7-v11's own convergent recall methodology);
- independent-corroboration field efficacy (still not directly re-tested against its own targeted single-generation persistent-confusor shape -- an existing, unmet Gate A dependency this milestone did not touch);
- scene-confusor participation, now also measuring corroboration-rejected occurrence counts directly (newly possible with this milestone's own fix);
- useful-evidence-rate recovery;
- false-Visit rate materially below the v8-v11 regime;
- fragmentation re-measured (a second consecutive non-zero cohort, unchanged, unrelated to this milestone);
- RTT true latency re-derived (unchanged, unrelated to this milestone);
- multi-subject evidence where naturally available.

## Decision

**B.**

Two genuinely distinct, real, field-evidenced false-Visit subclasses were separated (not lumped), deterministically reproduced against the real, unmodified production admission path (not a synthetic straw-man), and investigated to their first irreversible product decision. One subclass is now measurably, narrowly, and safely closed by a small, class-semantics-preserving check that reuses an already-established geometry-coincidence bar and changes zero detector/classifier thresholds. A second, adjacent gap in the scene-confusor mechanism (historical bookkeeping silently dropped for every corroboration-rejected occurrence) is genuinely fixed and proven to help a real, materially different recurring-confusor shape. The milestone's own investigation additionally proves, numerically and against the real mechanism rather than by assertion, that this bookkeeping fix does **not** close v11's own headline Visit-018 shape, and explains precisely why closing it further is not safe to attempt without new evidence-quality signals or real field data this sandbox cannot produce -- reported honestly per "Do not force A." Every required positive control passed; the full directly-affected regression suite (705 tests) and the new reproducer suite (11 tests) pass with zero failures; the authoritative full-Core run (5610 passed) shows exactly the same 2 pre-existing, independently-reconfirmed, unrelated failures this codebase's own validation history already documents repeatedly. No MDv5/NMS/BioCLIP threshold changed. No whole-frame human veto. No spatial blacklist. No new surveillance data retained.
