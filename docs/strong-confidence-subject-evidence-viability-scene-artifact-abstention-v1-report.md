# Strong-Confidence Subject-Evidence Viability & Scene-Artifact Abstention v1: Report

**Date:** 2026-09-02. **Classification: B.**

A real Gate-A investigation, not a fix, into the exact defect the accepted Strong-Confidence Non-Target & Scene-Artifact Visit Admission Correctness v1 milestone left open at Classification B: Representative Daylight Gate A Field Acceptance v11's own Visit 018, a leaf/branch cluster at the recurring "Location A" foliage geometry that cleared MDv5's `strong_detection_threshold` (0.70) six times in one occurrence and was admitted as a user-visible Visit. This milestone reconstructs that exact shape faithfully (reusing, not duplicating, the predecessor's own already-field-grounded reproducer), builds every required positive control, and investigates every avenue the governing brief names -- detector geometry lineage, evidence scoring, scene-confusor, track-generation structure, evidence diversity, temporal consistency -- to find a safe, non-ML, non-confidence-magnitude, non-motion, non-spatial-blacklist fact that separates a strong scene artifact from a strong real (including stationary and brief) bird. **None exists in this codebase today.** Two new findings, both proven directly against real production code paths (not asserted from reading source), close off the two most promising remaining avenues: (1) the exact artifact shape and the exact accepted "strong real bird" positive control are structurally identical at every fact `candidate_quality_gate`/`scene_confusor` can read (one track generation, `strong_detection_count > 0` -- no count/generation threshold, for any constant, separates them without also catching one of them); (2) the accepted geometry-lineage signal (Localization Attribution / Detection Geometry Lineage v1, `geometry_source`), which the governing brief's §11 specifically asked this milestone to investigate as a candidate generalization, does **not** separate them either -- both classify identically as `geometry_source="detector"` / `detector_off_target`, because the artifact's own detector agreement is completely genuine and contemporaneous, six times over, not stale or tracker-extrapolated (the different defect class that signal already, correctly, closes elsewhere). Per the brief's own explicit instruction (§15, §17), no rule was invented to force a result: **zero production code changed.** Two new, real, executable proof tests were added; no schema change; no confidence retune; no spatial blacklist; no motion requirement; no BioCLIP gate.

## Starting state

Verified before any work, per the brief's own §2/§3:

- Repository/branch: `/home/<user>/projects/mockingbird-active`, `main`.
- Accepted HEAD at session start: `127edaf` -- exact match to the brief's expected state (`git rev-parse HEAD`).
- Schema: `v58` (`CURRENT_DATABASE_SCHEMA_VERSION`, `src/mockingbird/storage/database.py:45`), unchanged throughout -- matches.
- Latest accepted milestone: Strong-Confidence Non-Target & Scene-Artifact Visit Admission Correctness v1, Classification **B** -- directly re-read from `docs/strong-confidence-non-target-scene-artifact-visit-admission-correctness-v1-report.md` and `docs/release-execution-state.md` §1/§3 -- matches exactly, including: person dual-class same-frame contradiction fix accepted; scene-confusor rejection-history bookkeeping accepted; pure single-class person misclassification remains the already-accepted 2026-08-20 residual (open, unchanged); **the exact v11 Visit-018 strong-confidence scene-artifact shape explicitly, numerically proven not closed** by that milestone's own investigation.
- Gate A / Lane R: OPEN. Current authorization at start: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED` -- this milestone's own governing brief is the explicit authorization for this specific correctness investigation.
- Not pushed: 309 commits ahead of `origin/main` at session start (`git rev-list --count origin/main..HEAD`).
- Worktree safety: `git status` showed exactly the seven expected preserved untracked files, byte-identical (`md5sum`-verified against a pre-session baseline) both before and after this milestone's own work; the only running processes touching this session's own scratchpad were three read-only `tail -f` log-watchers from an unrelated, already-completed prior session (`6d33bd4f-...`), no writer. No `.git/*.lock` present at start or end.
- Production detector: **MDv5a ONNX, `score_threshold: 0.1`** -- confirmed unchanged from `docs/representative-daylight-gate-a-field-acceptance-v11-report.md`'s own frozen-configuration record and re-confirmed by this milestone's own investigation touching zero detector code. `strong_detection_threshold: 0.7` (tracker/`scene_confusor` default) likewise unchanged.

## Field defect

Directly re-read from `docs/representative-daylight-gate-a-field-acceptance-v11-report.md` ("False Visits") and `docs/strong-confidence-non-target-scene-artifact-visit-admission-correctness-v1-report.md` ("Strong-artifact reproducer", "Scene-confusor interaction"):

Visit 018 -- "a leaf/branch cluster at the classic Location-A geometry that happened to clear the strong-detection threshold 6 times in this one occurrence" -- the exact v8/v9/v10/v11-recurring foliage/branch-tip coordinates, bbox center (0.202, 0.691). Admitted via `candidate_quality_gate._insufficient_detector_corroboration`'s `strong_detection_count > 0` bypass; `scene_confusor.evaluate_scene_confusor_suspicion` never suspected it because its own step 6 ("independently strong, unconditionally," `max_confidence >= strong_detection_threshold`) is checked without reference to the region's accumulated history. The predecessor milestone directly, numerically proved -- not merely asserted -- that its own scene-confusor bookkeeping fix (recording history for corroboration-rejected occurrences too) does **not** flip this outcome: `test_sudden_strong_occurrence_after_weak_history_remains_open` in `tests/test_strong_confidence_non_target_scene_artifact_v1.py` shows a real, accumulated 3-occurrence weak history (`occurrence_count=3`) at Location A followed by a genuinely strong 4th occurrence still resolves `outcome_4.outcome == "created"`. **This milestone reused that exact reproducer verbatim** (see below) rather than reconstructing a new one, per the brief's own "reuse, do not invent" instruction and its own "do not substitute a weak-confidence artifact" bar -- the existing reproducer already faithfully matches every disclosed field number (Location-A box, 6 detections, confidences 0.72-0.78 falling inside v11's own disclosed range).

## Exact artifact reproducer

`tests/test_strong_confidence_non_target_scene_artifact_v1.py::TestStrongSceneArtifactAtLocationA::test_sudden_strong_occurrence_after_weak_history_remains_open` (unmodified, pre-existing, accepted) and this milestone's own `tests/test_strong_confidence_subject_evidence_viability_v1.py::TestStructuralShapeIndistinguishable`/`TestGeometryGroundingDoesNotSeparate` (new, additive, zero production dependency) reconstruct the identical shape: `_LOCATION_A_BOX = (0.16, 0.66, 0.24, 0.74)` (center (0.20, 0.70), matching v11's own disclosed center exactly), one continuous track generation, six alternating detection/gap ticks at confidences `[0.72, 0.75, 0.71, 0.78, 0.73, 0.76]` -- all clearing `strong_detection_threshold`, driven through the real, unmodified `ProviderNeutralFrameTracker.observe()` -> `build_tracklets`/`assemble_visit_episodes` path (never a fixture that simply declares a proposal false). `constituent_generation_ids` has length 1; `confidence_evidence.strong_detection_count == 6`, `detection_count == 6`.

## Stationary-real control

Two, both already-accepted and this milestone's own new proof file cross-checks the first directly:

- **Single-occurrence strong real bird** (the brief's §6 "most important control"): `TestStrongAndWeakRealBirdPreserved::test_strong_real_bird_admits_unchanged` -- `_FEEDER_BOX = (0.55, 0.40, 0.62, 0.48)`, three detections `[0.82, 0.85, 0.80]`, one generation, admits (`created`). This milestone's own `TestStructuralShapeIndistinguishable` reruns the identical construction directly (not merely citing the sibling file) and confirms `constituent_generation_ids` length 1, `strong_detection_count > 0` -- the same shape as the artifact above, differing only in confidence values and geometry.
- **Repeated-visit stationary real bird**: `TestStrongAndWeakRealBirdPreserved::test_stationary_real_bird_survives_repeated_strong_admission_at_the_same_spot` -- four separate strong occurrences at `_FEEDER_BOX` across a session, every one `created`, none suspected -- directly reproducing v11's own field-proven feeder-pole result (real `scene_confusor_regions` read: `occurrence_count=4`, `max_confidence_observed=0.827`, spanning both field segments, never suspected, escaping via `independently_strong_detection` every time).

## False-vs-real comparison

At every fact this codebase already computes and could, in principle, read at admission time, the artifact and the stationary/strong real bird are indistinguishable:

| Fact | Strong artifact (Visit 018 shape) | Strong real bird (feeder-pole shape) |
|---|---|---|
| `constituent_generation_ids` count | 1 | 1 |
| `strong_detection_count` | 6 (>0) | 3 (>0) -- *fewer*, not more |
| `max_consecutive_detector_confirmed_frames` | not consecutive (alternating ticks) | not consecutive (identical construction) |
| `geometry_source` of selected evidence | `"detector"` (proven, below) | `"detector"` (proven, below) |
| `evidence_scoring` containment/sharpness/exposure | passed every check (predecessor's real-crop trace) | passes every check |
| Region history (`scene_confusor_regions`) | 3 prior weak occurrences (real) | 3 prior strong occurrences (real, feeder-pole) |
| Region escape taken | `independently_strong_detection` (step 6) | `independently_strong_detection` (step 6), same region across the session |

The only differences are the confidence *values themselves* (already proven, by the predecessor, not to be safely thresholdable -- "Production authority gate" in `docs/detection-quality-accounting-contract.md`: no confidence floor clears both false-positive rejection and real-animal recall against 70 real reviewed Visits) and the *count* of detections (6 vs. 3 -- and the real bird's count is the *lower* of the two, so a stricter count floor would catch the real bird first, not the artifact).

## Separating evidence

**None found.** See "Geometry-grounding investigation," "Evidence-quality investigation," and "Scene-confusor analysis," below, for what was investigated and why each candidate fails.

## Non-separating evidence

Every fact investigated and explicitly ruled out, with the reason:

- **Detection count / generation count** (§5, §14): structurally identical shape between the artifact and the accepted strong-real-bird control (proven above); any threshold strict enough to reject 6 detections in 1 generation would also reject the real bird's own 3. This is a disguised confidence/count retune, explicitly forbidden (§9).
- **`geometry_source` / geometry-lineage grounding** (§11): both classify `"detector"` / `detector_off_target` -- proven directly, below.
- **Evidence photographic quality** (containment, edge-clipping, sharpness, exposure, subject-area-ratio -- `evidence_scoring.py`): already directly investigated by the predecessor milestone against Visit 018's own real, byte-backed crop (not a synthetic proxy) -- it passed every one of these checks, which is exactly what let it reach the corroboration gate as a valid `identification`/`context` pick in the first place. Re-confirmed by this milestone's own reading of `evidence_scoring._score` in full: none of its components are content/semantic signals (none ask "does this look like an animal"); all are photographic-quality signals a well-lit, sharp, well-framed photo of a leaf cluster satisfies exactly as well as one of a bird.
- **Intra-generation box/geometry variance across the 6 confirmed frames** (§13's "crop stability"): considered and rejected. This is a motion/stillness proxy in disguise (a real bird would need to move detectably between frames to produce variance; a truly still bird -- the stationary-real-bird control -- would not), and the brief explicitly forbids motion requirements (§13: "Do not implement motion requirements"). `scene_confusor.py`'s own docstring independently confirms the same conclusion at cross-occurrence granularity: "A static scene artifact... and a real bird perched motionless at the same spot for a whole visit produce structurally identical single-encounter evidence."
- **Encounter duration / detection temporal density** (§13): rejected for the same reason as detection count -- a genuine **brief** real bird sighting (a mandatory positive control, §6/§20/§28) can legitimately produce exactly as few detections in exactly as short a window as this artifact did; any duration/density floor strict enough to catch the artifact risks catching the brief-bird control.
- **Evidence-candidate diversity / distinct-frame count** (§12): the brief's own text preemptively rules this out as insufficient by itself ("a real perched bird may legitimately produce visually similar evidence repeatedly. Therefore repeated similarity alone is not sufficient") -- confirmed structurally: this reproducer's own evidence-candidate count (2 per generation, `high_resolution_burst`+`context`) is identical in shape for both the artifact and any single-generation real-bird control, and a brief real encounter would legitimately produce just as few distinct captured frames.
- **Scene-confusor cross-occurrence history** (§10): the predecessor's own investigation already, numerically, proved this insufficient (`test_sudden_strong_occurrence_after_weak_history_remains_open`) -- this milestone did not re-litigate that proof, but did directly re-verify (by reading `scene_confusor.py` in full) that both of its confidence escapes (steps 5 and 6) are checked **unconditionally on the current candidate's own confidence**, never on the region's own history, by original, documented design -- and are simultaneously the exact mechanism protecting the field-proven feeder-pole stationary-real-bird control. Weakening either escape without a new, independent, safe fact would risk that control directly; no such fact was found (see below), so this milestone leaves `scene_confusor.py` completely unmodified, per the brief's own explicit permission (§10).

## Geometry-grounding investigation

The governing brief's §11 asks specifically whether a generalized version of Background / Empty Evidence Species-Confidence Correctness v1's own "credible contemporaneous detector grounding" fact (`geometry_source`, read from `MediaAssetModel.geometry_attribution_json`, schema 33) already exists at species inference but is absent at Visit admission, and whether the same underlying fact can safely support Visit validity.

**Traced precisely, at the code level:**

1. `geometry_attribution_json` is already computed and persisted for **every** evidence item at Visit-*creation* time, not only at species-identification time -- `candidate_visit_adapter._build_evidence_items` (line ~380) already serializes `candidate.geometry_attribution` onto every `CandidateEvidenceItem` the instant a proposal is admitted, via the same `EvidenceCandidate.geometry_attribution` field the Background/Empty Evidence milestone later read. The fact this milestone's brief describes as "absent at Visit admission" is, in this narrow sense, already computed and stored there -- it is simply never *read* by `candidate_quality_gate.evaluate_evidence_admission`.
2. What `geometry_source` actually distinguishes: `"detector"` (a genuine matched detector observation, `TrackUpdate.support_state` was `strong_detector_supported`/`weak_detector_supported` at that exact moment), `"tracker"` (patch-match continuity, no detection this exact moment), `"carried_forward"` (a stale box, no fresh observation of any kind). The Background/Empty Evidence defect class was specifically a track kept alive on `"tracker"`/`"carried_forward"` support **past its last real detector confirmation** (`terminal_reason: maximum_unsupported_duration`) -- i.e. the detector had genuinely stopped agreeing with the box's own position by the time the evidence frame was captured.
3. Visit 018's own shape is the opposite case: MDv5 **genuinely, contemporaneously** detected the Location-A geometry six separate times, each at `>= 0.70` confidence. This milestone's own new proof test (`TestGeometryGroundingDoesNotSeparate::test_artifact_and_real_bird_both_show_genuine_contemporaneous_detector_grounding`) reconstructs the real `GeometryAttribution` for the exact `TrackUpdate` behind one of those six confirmed frames, using the real, unmodified `localization_attribution.geometry_attribution_for_update`, and directly asserts (not infers) `geometry_source == "detector"` and `classify_localization_attribution(...).attribution == "detector_off_target"` -- run identically for the accepted strong-real-bird control, with the identical result.
4. `classify_localization_attribution`'s own docstring already, explicitly names this exact limit for step 5 (`detector_off_target`, reached "by elimination"): *"If it still misses a visible subject, the raw detector output on that exact frame is the most defensible attribution available from lineage alone."* This is not a gap this milestone discovered by omission -- the module's own author already documented that a genuine, temporally-aligned, non-stale detector hit that still does not correspond to a real subject is, by construction, outside what geometry lineage alone can ever resolve.

**Conclusion: the existing geometry-grounding signal, even fully generalized to Visit admission, provides zero separation for this defect class.** It correctly closes a different, real defect (stale/tracker-extrapolated geometry with no contemporaneous detector agreement); Visit 018's defect is the opposite failure mode -- the detector really did fire, repeatedly, in real time, on real background structure. This directly answers §11: the underlying fact does *not* safely support Visit validity here, and this milestone does not "blindly copy species eligibility logic upstream" as explicitly warned against, because doing so would be a no-op for the reproduced defect (proven, not assumed) while still carrying the same real, disclosed cost the Background/Empty Evidence milestone itself already priced in for its own, narrower use (2/30 real Visits wrongly withheld an automatic suggestion in that milestone's own cohort) -- a cost this milestone would incur for zero benefit against the one shape it was asked to close.

## Evidence-quality investigation

Re-confirmed, not re-derived: `evidence_scoring.score_proposal_evidence`/`_score` (`src/mockingbird/observation/evidence_scoring.py`, read in full this milestone) computes exactly: subject containment/edge-clipping (`geometry` bounds only), subject-area-ratio/pixel-detail, track-support facts (`track_supported`, role-based continuity), temporal alignment (`aligned`/`rejected`/`uncertain`, from already-known facts, not recomputed pixel analysis), sharpness (`ImageFilter.FIND_EDGES` RMS threshold) and exposure (mean luminance) when real image bytes are supplied. None of these ask "does this look like an animal" -- confirmed directly by reading `_score`'s full body: every component is either a pure-geometry fact (independent of pixel content) or a low-level image-statistics fact (edge density, mean brightness) equally satisfiable by a well-lit, sharp, well-framed photograph of foliage as by one of a bird. The predecessor milestone already established, against Visit 018's own real byte-backed crop (not a synthetic proxy), that it passed every one of these checks -- this is exactly what let it reach `candidate_quality_gate` as a valid `identification`/`context` pick at all. This milestone's own new evidence-candidate diversity/temporal-spacing analysis (above) extends, rather than repeats, that conclusion.

## Scene-confusor analysis

Re-verified directly against `scene_confusor.py`'s full, current source (unmodified since the predecessor milestone, which itself left it untouched): `evaluate_scene_confusor_suspicion`'s seven-step decision order has exactly two confidence-based escapes -- step 5 (`stronger_confidence_than_region_history`, relative: current confidence exceeds the region's own historical max by `>= stronger_confidence_delta` (0.15)) and step 6 (`independently_strong_detection`, absolute: current confidence `>= strong_detection_threshold` (0.7), unconditional on history). Both are checked strictly after the recurrence-count gate (step 3) and geometry-spread gate (step 4), meaning **history is consulted first and still cannot stop a sufficiently strong single occurrence** -- both remaining escapes are, by explicit original design (documented in the module's own constant-level comments, `DEFAULT_STRONGER_CONFIDENCE_DELTA`/`DEFAULT_STRONG_DETECTION_THRESHOLD`), unconditional on the region's own accumulated history. This module's own docstring names exactly why: a static artifact and a real bird perched motionless at the same spot produce structurally identical single-encounter evidence, so occurrence-count/geometry-spread history is the *only* safe cross-occurrence signal this module already established -- and it was already, separately, real-cohort-validated (the module's own cited grid search against a real 70-Visit cohort) specifically *not* to use confidence magnitude as a suspicion trigger, only as an escape. Both escapes are simultaneously required for the real, field-proven feeder-pole stationary-real-bird control (`occurrence_count=4`, `max_confidence_observed=0.827`, escaping via step 6 every time, spanning both v11 field segments). This milestone's own investigation found no new, independent, safe fact (see "Non-separating evidence," above) that could condition either escape without risking that control -- so, per the brief's own explicit instruction (§10), `scene_confusor.py` remains completely unmodified.

## First irreversible error

Re-evaluated across the full pipeline the brief names (detector adaptation, tracker, proposal assembly, candidate-quality admission, evidence selection, Visit assembly), extending rather than repeating the predecessor's own tracing:

The earliest point the system currently has *any* candidate fact bearing on this question is unchanged from the predecessor's own finding: `scene_confusor.evaluate_scene_confusor_suspicion`'s steps 5/6, and `candidate_quality_gate._insufficient_detector_corroboration`'s `strong_detection_count > 0` bypass. This milestone's own investigation adds: there is **no** point *earlier* in the pipeline (detector decode, tracker association, proposal assembly) where a new, safe, non-motion, non-ML fact becomes available that is not already summarized, unchanged, into `ConfidenceEvidenceSummary`/`GeometryAttribution` by the time either of those two decision points runs -- `ConfidenceEvidenceSummary`'s own full field list (`detection_count`, `strong_detection_count`, `weak_detection_count`, `max_consecutive_detector_confirmed_frames`, `max_single_generation_detection_count`, `first_detection_offset_ms`/`last_detection_offset_ms`, bounded per-detection `samples` with `bounding_box`) and `GeometryAttribution`'s own full field list (`geometry_source`, `same_frame`, `geometry_evidence_gap_ms`, `resolution_provenance`) were read in full (`src/mockingbird/observation/contracts.py`) specifically to check for an unexamined fact; none was found that survives the "Non-separating evidence" analysis above. **There is currently no point in the pipeline where the system has enough information to safely abstain from this specific artifact class while preserving the stationary/brief-real-bird controls.**

## Locked contract

Per the brief's own §15 instruction, written before any implementation was attempted:

- **Exact artifact signature:** one track generation; `strong_detection_count > 0`; `geometry_source="detector"` on selected evidence; passes every `evidence_scoring` photographic check; region history may be empty, weak, or absent (does not matter -- steps 5/6 are unconditional).
- **Exact stationary-real signature:** structurally identical to the above on every currently-computed fact (see "False-vs-real comparison").
- **Separating evidence:** none found.
- **Non-separating evidence:** detection/generation count, `geometry_source`, evidence photographic quality, intra-generation geometry variance (motion-adjacent, forbidden), duration/temporal density (conflicts with the brief-real-bird control), evidence-candidate diversity (conflicts with the brief's own caveat), scene-confusor history (already proven insufficient by the predecessor, re-confirmed).
- **Unknown-evidence behavior:** moot -- no new check was added, so no new unknown-evidence case exists. `geometry_source=None` (a caller/record that predates schema 33) already, correctly, degrades to "no opinion" wherever it is read today (`identification_eligibility.py`'s own established convention); this milestone changes nothing about that.
- **Multi-subject behavior:** moot -- no new check was added; existing sibling-isolation guarantees (private per-`_Track` state, no shared mutable state between tracks) are unchanged, unread by this milestone's own zero-diff.
- **Sustained-activity behavior:** moot -- unchanged, unread.

**Conclusion of the lock: no safe separator exists. Per §15's own explicit instruction ("If no safe separator exists: DO NOT INVENT ONE"), none was invented.**

## Why no safe implementation exists

Restated plainly: every currently-available, already-computed, non-ML, non-motion fact this codebase has about a strong single occurrence is *identical in kind* between "a real bird just landed and was immediately, strongly detected" and "a leaf cluster was, on this one occurrence, strongly and repeatedly (mis)detected." The two cases differ only in the *semantic content* of the crop -- whether a subject is actually visible -- which no existing evidence-quality, geometry-lineage, or history-based signal in this codebase measures, and which the brief explicitly forbids solving with a new classifier (§18) or a retuned confidence/count number (§9). This is not a failure to look hard enough: it is the same conclusion the predecessor milestone's own "Remaining risk" section already reached ("closing it would require either new evidence-quality/content signals... or real field data... this sandbox cannot safely produce"), now extended with two new, code-proven negative results (structural-shape identity, geometry-grounding non-separation) that close off the two most concrete remaining hypotheses rather than leaving them as open questions for a future milestone to re-derive.

## Strong-artifact result

Unchanged: still admits (`created`), pre- and post- this milestone (zero production code changed; `test_sudden_strong_occurrence_after_weak_history_remains_open` was already, and remains, the accepted record of this exact fact).

## Stationary-real result

Unchanged, preserved: `test_stationary_real_bird_survives_repeated_strong_admission_at_the_same_spot` still passes, unmodified code. This milestone's own new proof file independently re-derives the same structural facts for the single-occurrence case directly (`TestStructuralShapeIndistinguishable`).

## Strong-real result

Unchanged, preserved: `test_strong_real_bird_admits_unchanged` still passes, unmodified code.

## Weak/brief result

Unchanged, preserved: `test_weak_real_bird_admits_via_count_based_corroboration_unchanged` still passes, unmodified code. No brief-bird-specific reproducer was newly required (unmodified code path; the "Non-separating evidence" analysis above explains *why* a brief-bird-safe rule could not be constructed, which is the more useful record for a future reader than a redundant pass/fail rerun).

## Multi-subject result

Unaffected by construction: zero production code changed; no shared-state path exists between independent `_Track`/proposal instances (re-confirmed by reading `frame_tracker.py`'s per-track accounting, unchanged since the predecessor's own identical conclusion).

## Existing-hard-negative regression

None possible (zero production diff). Directly re-run as a positive confirmation, not merely assumed: `tests/test_strong_confidence_non_target_scene_artifact_v1.py` (11/11), `tests/test_independent_corroboration_value_persistent_confusor_v1.py`, `tests/test_hard_negative_visit_admission_precision_v1.py`, `tests/test_localization_attribution.py`, `tests/test_observation_evidence_scoring.py`, and this milestone's own new `tests/test_strong_confidence_subject_evidence_viability_v1.py` -- **107 passed, 0 failed** (`ruff check` on the new file: 0 findings).

## Species result

Unaffected: zero production code changed; the existing `test_rejected_confusor_history_does_not_grant_species_inference_any_input` (unmodified) remains the accepted proof that any rejected proposal creates no Visit row for species inference to run against. Visit 018's own shape is **not** rejected (this milestone did not close it), so its species-non-escalation status is exactly what it already was: `species_guess is None` for every one of v11's 8 confirmed-false Visits including Visit 018, directly confirmed from the `visits` table by the v11 field report itself -- Gate B's own abstention safety held completely in the field, independent of this milestone.

## Reviewed-truth result

Unaffected: zero production code changed; no `ReviewLabel`/correction/`reviewed_real_count`/`reviewed_false_count` code path touched or read differently.

## Privacy result

Unaffected: zero production code changed; this milestone's own new test file adds no new persisted state, no new person/identity data, no new surveillance signal -- it is a pure, additive, offline proof harness with no product-facing effect.

## Performance

Unaffected: zero production code changed. The new test file runs in 0.36s standalone, adds no new runtime dependency, no new expensive computation, no O(n²) scan, no new ML.

## Self-review

Attacked each listed concern directly, against this milestone's own zero-diff:

- **Hidden confidence retune:** none -- no threshold of any kind was changed; the investigation explicitly rejected count/duration-based rules for being disguised retunes (see "Non-separating evidence").
- **Spatial blacklist:** none -- no coordinate literal was written to production code; the investigation's own comparison deliberately used two geometrically distant locations (Location A for the artifact, the feeder box for the real-bird control) specifically to keep the negative finding location-independent (see "Adversarial location swap," below, for why a literal swap test does not apply here).
- **Stationary-real-bird rejection:** not possible -- zero production diff; directly re-tested and passing.
- **Foliage-near-real-bird rejection:** not possible -- zero production diff; the existing `test_bird_still_admits_while_a_person_is_concurrently_present_elsewhere`-class controls (unmodified) remain the accepted record for spatially-adjacent-but-distinct subjects.
- **Motion-as-truth:** explicitly considered and rejected as a candidate (intra-generation box variance) precisely because it is a disguised motion/stillness requirement -- named, not implemented (see "Non-separating evidence").
- **Evidence-similarity-as-truth:** explicitly considered and rejected per the brief's own caveat (§12) that repeated similarity alone cannot be sufficient, since a real stationary bird produces the same shape.
- **Sibling contamination:** not possible -- zero production diff; no shared-track-state path exists (re-confirmed).
- **New ML disguised as scoring:** none -- both new tests call only existing, pure, deterministic, already-shipped decision functions (`geometry_attribution_for_update`, `classify_localization_attribution`); no model inference, no new heuristic score.
- **Scene-confusor strong-positive regression:** not possible -- `scene_confusor.py` has zero changed lines (matches the predecessor's own disclosure exactly; this milestone leaves it untouched for the same, now doubly-confirmed, reason).
- **Unknown-evidence rejection:** not possible -- no new check exists to mis-handle an unknown fact.
- **Privacy expansion:** none (see "Privacy result").
- **Species-side workaround:** none -- no species-eligibility code was touched; the brief's own §18/§25 prohibition was never approached.

## Adversarial location swap

Not directly applicable in its literal form (§21 -- "place the real-positive structural signature at the artifact's geometry... place the artifact structural signature at arbitrary geometry" -- presupposes a rule to test for spatial overfit; none was implemented). The investigation's own comparison structure already demonstrates the *substance* of what this section guards against: the artifact reproducer runs at Location A (0.16-0.24, 0.66-0.74) and the real-bird control runs at the geometrically distant Feeder Box (0.55-0.62, 0.40-0.48) -- both new proof tests (`TestStructuralShapeIndistinguishable`, `TestGeometryGroundingDoesNotSeparate`) find the identical structural/geometry-grounding result at *both* locations, confirming the negative finding is a property of the *shape* of the evidence (single generation, genuine contemporaneous strong detector agreement), not of either location specifically -- i.e., no spatial-blacklist-shaped rule could have been hiding inside this milestone's own conclusion.

## Validation

### Investigation-proof tests (new, additive, zero production dependency)

`tests/test_strong_confidence_subject_evidence_viability_v1.py`: **2/2 passed** -- directly proves (not merely documents) the two negative findings this report's own conclusion rests on, against real production code (`ProviderNeutralFrameTracker`, `build_tracklets`/`assemble_visit_episodes`, `localization_attribution.geometry_attribution_for_update`/`classify_localization_attribution`), not a synthetic assertion.

### Tier 1

Not applicable in the form the brief's §28 defines it (no implementation occurred, so there is no fix to prove pre-/post-). The directly-relevant existing reproducer/regression suites were re-run as a non-regression check on this milestone's own zero production diff (see below) -- all pass, confirming this investigation introduced no accidental change.

### Tier 2

Directly-relevant subsystem files re-run together with this milestone's own new file: `tests/test_strong_confidence_non_target_scene_artifact_v1.py`, `tests/test_independent_corroboration_value_persistent_confusor_v1.py`, `tests/test_hard_negative_visit_admission_precision_v1.py`, `tests/test_localization_attribution.py`, `tests/test_observation_evidence_scoring.py`, `tests/test_strong_confidence_subject_evidence_viability_v1.py`:

**107 passed, 0 failed.** `ruff check` on the new file: 0 findings.

### Tier 3

**Not run, by explicit decision** (per the brief's own §30: "If the milestone concludes investigation-only with no production change: do not run Core merely for ceremony. Document decision."). Zero production code was touched by this milestone (`git diff` against the starting HEAD across every `src/` file is empty); the one new file is a test-only, additive proof harness with no import/behavior surface any other test or production path depends on. A full Core run would re-verify facts this milestone never touched, at real cost (the predecessor's own most recent full Core run took 1928s), for zero incremental assurance -- consistent with the brief's own explicit instruction not to run it for ceremony.

## Remaining release defects

Carried forward, unchanged, not investigated or fixed by this milestone (per the brief's own §32/§33 explicit exclusion):

1. **Camera Node self-test diagnostic-truth gap** (v11, "Defects" item 3): `/node/v1/health`'s own `self_test.camera_available` can report success while the specifically-configured camera remains physically undetected. Real, disclosed, not release-blocking (the actual safety-relevant gate -- compatibility preflight before Observation start -- already catches it correctly). Not investigated this milestone; no dependency found between it and this milestone's own subject-evidence-viability investigation.
2. **Acceptance-recorder directory-path encoding defect** (v11, "Defects" item 1): `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` set to an absolute Windows path produces a garbled (but functional, data-intact) directory name. Real, disclosed, tooling-only. Not investigated this milestone; no dependency found.
3. **Pure single-class person misclassification** (already-accepted 2026-08-20 residual, reconfirmed open by the immediately-prior milestone): unchanged, not this milestone's scope.
4. **`blocked_continuation_pending` backlog observation** (v11, "Defects" item 4): open, unconfirmed either way; not this milestone's scope.

## Next field proof

Not self-authorized (per the brief's own explicit instruction, §37). If a future, separately-authorized milestone revisits this exact defect class, the next real, useful step is **not** another code investigation on this same sandbox's own already-exhausted evidence -- every available non-ML fact was checked and ruled out this session -- but one of:

- **Real field data on genuine repeat-wildlife confidence-history/geometry-spread patterns** at a *second*, independent recurring-artifact location (not Location A alone), to test whether `scene_confusor`'s existing `geometry_spread_ceiling`/history mechanism could ever safely condition its confidence escapes without a live-session-derived constant this sandbox cannot responsibly produce (explicitly out of scope here, per the predecessor's own identical disclosure).
- **A deliberately scoped, separately-authorized Gate-B/new-evidence-signal investigation** (content-aware evidence quality) -- explicitly out of scope for a Gate-A correctness milestone per this brief's own §18 (no BioCLIP gate) and general "no new ML" instruction, but named honestly as the only remaining category of fact that could, in principle, separate this defect class.
- Any future daylight field session's own standing measurement set (strong-artifact recurrence, person-associated false reduction, no suppression of real birds near human activity, stationary/weak-bird safety, independent-corroboration efficacy, scene-confusor participation, false-Visit rate, useful-evidence recovery, fragmentation, true RTT latency, multi-subject behavior) is unchanged and still pending a next authorized cohort -- this milestone adds nothing to and removes nothing from that list.

## Decision

**B.**

A real, thorough, faithfully-reconstructed investigation into the exact field-proven defect the predecessor milestone left open, covering every avenue the governing brief names (detector geometry lineage, crop containment/occupancy/consistency/stability, evidence diversity/temporal spacing, independent detector reacquisition, track-generation structure, evidence scoring, scene-confusor state, and a direct generalization test of the accepted geometry-grounding signal), producing two new, real, code-proven negative findings that were not established before this milestone (structural-shape identity between the artifact and the accepted strong-real-bird control; geometry-grounding non-separation, directly disproving the most concrete open hypothesis §11 posed) rather than merely re-asserting the predecessor's own already-disclosed residual. Per the brief's own explicit governing instruction (§15, §17: "If no safe separator exists: DO NOT INVENT ONE"), no confidence retune, spatial blacklist, motion requirement, BioCLIP gate, or new ML was introduced to force a result. Zero production code changed; two new, real, executable proof tests added (2/2 passing); the directly-relevant existing regression suite (107 tests) passes unchanged; zero new `ruff` findings. This does **not** close the field-observed Visit-018 defect -- it establishes, with new evidence, that closing it safely is not currently possible without either a genuinely new evidence-quality/content signal (explicitly out of scope for this milestone) or real field data this sandbox cannot responsibly produce, exactly the honest, bounded, non-forced outcome the governing brief's own acceptance bar (§36) anticipates for this case. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.
