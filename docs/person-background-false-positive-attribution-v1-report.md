# Person / Background False-Positive Attribution & Admission Precision v1 — Report

Field-forensics-and-regression-fixture milestone (no production code
modified). Direct follow-up to
[cache-128-live-daylight-acceptance-v1-report.md](cache-128-live-daylight-acceptance-v1-report.md)
S6/S9, which first flagged Visits 139/140 as likely-false but did not trace
the funnel or attempt a fix. Full raw evidence (recovered DB rows, both
Visits' real evidence images, the read-only recovery scripts) preserved
under this session's scratchpad; no new field-acceptance directory was
created since no live session ran.

## 1. Starting state

Local `HEAD` at session start: `75ec2d8925efbc238b3926417a777006197cf49b`
("Resolve ambiguous-cluster arbitration over the full connected component"),
confirmed via `git rev-parse HEAD`. `git status` matched the expected
7-pre-existing-untracked-file baseline exactly (`docs/wildlife-detector-
training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`), nothing else. Schema confirmed at 36
(`CURRENT_DATABASE_SCHEMA_VERSION` in `database.py`) in this checkout. The
deployed Windows product that actually produced Visits 139/140 was
independently confirmed still live at commit `bdb59f5`
(`GET /api/product/instance`, exact `git_commit` match), schema 35 — the
same build the cache-128 report itself used, predating Multi-Subject Phase 2
(schema 36, commit `5b04410`) and the ambiguous-boundary transitive closure
(`75ec2d8`). Neither of those two later fixes is implicated below.

## 2-3. Reconstruction of Visits 139 and 140

Recovered directly from the live deployed product's own SQLite database
(`C:\Users\<user>\AppData\Local\MockingBirdDev\userdata\data\mockingbird.sqlite3`,
read-only query via the packaged `python.exe`, plus `GET /api/media/{id}/preview`
for the real evidence images) — not inferred, not assumed. Every fact below
is a direct field read.

| Fact | Visit 139 | Visit 140 |
|---|---|---|
| `visit_id` | `visit-observation-candidate-139` | `visit-observation-candidate-140` |
| `proposal_id` | `visit-episode:c21ec095b00b179581146e96` | `visit-episode:dccd797355839764dfab6ca0` |
| `constituent_generation_id` | `stream-ca892992771c:frame-track:a1c04a60c009406ec260` | `stream-ca892992771c:frame-track:3ddb8f375c3d17e45232` |
| `constituent_track_id` | `frame-track-0280` | `frame-track-0281` |
| `event_id` (own, unshared) | `event-observation-candidate-139` (started 23:51:44.018937Z) | `event-observation-candidate-140` (started 23:52:06.572935Z) |
| `start_offset_ms`–`end_offset_ms` | 5,113,499–5,120,093 (6.59s span) | 5,119,540–5,140,928 (21.39s span) |
| `broad_class` / `VisitModel.subject_label` | `animal` | `animal` |
| Raw detections (`confidence_evidence_json`) | 2 (0.138 weak, 0.751 **strong**) | 11 (9 weak 0.107–0.509, 2 **strong** 0.814/0.877) |
| `max_confidence` | 0.751 | **0.877** (highest of any Visit, real or false, in the whole 90-min session) |
| `ambiguous_adjacent_proposal_ids` | `[]` | `[]` |
| `continuation_pending` outcome | admitted directly (no `blocked_continuation_pending`) | admitted directly |
| Selected identification evidence | `media-candidate-313` (full 3840×2160 frame) + `media-candidate-314` (`classifier_same_frame`, 1920×1080) | `media-candidate-316` (full frame) + `media-candidate-318` (`classifier_same_frame`) |
| `geometry_attribution` on the `classifier_same_frame` asset | `geometry_source="detector"`, `geometry_evidence_gap_ms=0`, `same_frame=true`, `geometry_source_confidence=0.751` | `geometry_source="detector"`, `geometry_evidence_gap_ms=0`, `same_frame=true`, `geometry_source_confidence=0.135` |
| BioCLIP suggestion | `brown_thrasher`, rank-1 score 0.5275 (relative-softmax over 14 forced bird labels) | `red_bellied_woodpecker`, rank-1 score 0.5986 (same 14-label forced set) |
| `review_status` / `reviewed_label` | `needs_review` / `None` (never reviewed) | `needs_review` / `None` |

**Direct visual re-confirmation this session** (not merely re-citing the
prior report): both `classifier_same_frame` evidence images
(`media-candidate-314`, `media-candidate-318`) were fetched via
`GET /api/media/{id}/preview` and viewed directly. `media-candidate-314`
unambiguously shows a woman walking a leashed dog across the street in the
far right of frame — no bird anywhere. `media-candidate-318` shows a
reddish/tan partial shape (consistent with a person's arm/torso, partially
occluded by the feeder tree's branches) at the same location the real-time
detector box for that frame reports — again no bird. Both images otherwise
show the identical static feeder-tree/yard/street scene as every real bird
Visit's own evidence in this session.

Not recoverable, and not guessed: the live session's in-memory
`CounterfactualLedger` (raw-detection/track-generation/proposal-outcome
lineage — see
[rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md))
does not survive past `session.stop()`, and this session's own Stop
happened hours before this investigation began — so no *other* nearby raw
detections, and no tracker `terminal_reason` for generations 280/281, could
be recovered. Everything durably persisted to `observation_candidate_visits`
(the authoritative lineage ledger) was recovered in full; nothing beyond
that is reported here as fact.

## 4. One fragmented real-world passage, or two independent events?

**Almost certainly one continuous real-world passage** (the person-and-dog
crossing), split across two tracker generations — not two independent
detector false positives, and not a duplicate/fragmentation *bug*:

- Both Visits' independently-reviewed timestamps (5113.5–5140.9s) fall
  entirely inside the cache-128 report's own blind-reviewed motion-screen
  window 37 (5132.5–5139.3s, logged "a person walking a dog on a leash").
- Track 281 (Visit 140) starts at 5,119,540ms — **553ms before** track 280
  (Visit 139) ends at 5,120,093ms. This is genuine temporal overlap, not a
  small gap.
- `visit_episode_assembler.classify_boundary`, run directly against both
  tracklets' real recovered facts (see the regression test below), returns
  `decision="incompatible"`, `reason="temporal_overlap"` — the tracker's
  own long-standing, deliberate rule (any temporal overlap between two
  confirmed tracklets is treated as "two simultaneous/crossing subjects, or
  a tracker-association artifact — not this layer's call," per
  [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
  "Structural incompatibility"). This is a *different* rule from the one
  the Ambiguous-Boundary Transitive Fragmentation Closure v1 milestone
  fixed (that rule handles a non-overlapping *gap*, `ambiguous_boundary`);
  it predates every 2026-08-19/08-20 multi-subject/ambiguity milestone and
  is explicitly reasoned in the contract as an accepted trade-off, "not,
  and has never been, an implementation bug."
- `ambiguous_adjacent_proposal_ids` is `[]` on both real persisted rows —
  confirming the assembler never even considered these two an *ambiguous*
  (gap-based) pair; they were classified `incompatible` outright, the
  entirely separate rule above.

**Conclusion:** one continuous real subject (a person, with a dog),
detected as `animal`-class twice by the raw detector as it crossed a brief
tracking gap (most plausibly momentary occlusion by the feeder tree's
trunk/branches, visible in both evidence images), correctly never merged
into one identity by the assembler's own deliberate, pre-existing
conservative rule. Two false Visits from one real passage is the expected,
already-understood consequence of that rule combined with the detector
event below — not a new fragmentation defect, and not attributable to any
2026-08-19/08-20 multi-subject/ambiguity work (none of it is even reachable
by this pair: `incompatible`/`temporal_overlap` is a different code path
from `ambiguous_boundary` arbitration, and the deployed build predates
Phase 2's Event-sharing consumption in any case).

## 5-6. First incorrect transition, and detector output

Traced through the full funnel (source frame → activity → animal presence
→ localization → track → evidence selection → broad-class → species
eligibility → species inference → admission → persistence) for both
Visits identically:

**The first incorrect transition is at "animal presence / detector
output"** — classification **A**: the raw MDv5 detector itself classified
a person's partial view as the `animal` class, at real, non-marginal
confidence (139: 0.751; 140: up to 0.877), not a marginal/borderline score.
Confirmed at the code level, not assumed:

- `onnx_provider._observation` sets `is_animal = label in bundle.
  animal_classes`, where `label = bundle.broad_classes[class_index]` comes
  directly from the raw decoded model output. `OnnxModelBundle.load`
  strictly validates `bundle.animal_classes == ("animal",)` and
  `bundle.broad_classes == ("animal", "person", "vehicle")` for the MDv5
  decoder — a `person`-class detection is structurally distinguishable from
  an `animal`-class one, and MockingBird's own adapter mapping is correct
  (no off-by-one/mislabeling bug — ruled out explicitly, since a mapping
  bug was one of the first hypotheses checked).
- `frame_tracker.ProviderNeutralFrameTracker._observe`/`_start` only ever
  form or extend a track from a detection with `is_animal is True`
  (`frame_tracker.py:434-447`) — a real `person`-class MDv5 output could
  never have reached tracking at all. For these two tracks to exist, the
  raw model's own class output for this region, on these frames, genuinely
  was index 0 (`animal`), not index 1 (`person`).
- Both peak confidences (0.751, 0.877) clear the tracker's own
  `strong_detection_threshold` (0.70, `frame_driven_provider.py:67`)
  comfortably — these were not weak/noise-floor detections the detector
  itself was unsure about.

Every downstream stage then operated correctly, faithfully, and as
designed on top of that one wrong upstream signal — see the per-stage
findings below. This is why classification is **A**, not **D** (a
non-animal candidate passing broad-class eligibility — ruled out: the
detector's own output *was* the `animal` class, correctly read) and not a
mapping/adapter bug.

## 7. Evidence geometry / lineage findings

No drift, no detachment (rules out classification **C**/**G**). Every
persisted evidence asset's `geometry_attribution_json` shows
`geometry_source="detector"`, `same_frame=true`, `geometry_evidence_gap_ms=0`
for the exact `classifier_same_frame` crop BioCLIP actually scored — the
evidence box is provably the same real-time detector-established box, at
zero time gap, not a later/stale/coasted box (the alternate mechanism
[localization-attribution-contract.md](localization-attribution-contract.md)
exists to catch). The "identification" full-frame assets carry a small,
honest gap (521-973ms, `geometry_source="tracker"` for 139's, i.e. a
short tracker-support interpolation, not a detection) but the box position
itself is consistent across all three evidence roles per Visit and matches
the same real screen region visually confirmed above. Localization itself
was accurate — the box genuinely bounds the real subject in frame; only its
*class label* was wrong.

## 8. Broad-class / eligibility findings

**No eligibility gap exists to close** (rules out classification **D**).
Read `candidate_quality_gate.evaluate_evidence_admission` directly: its
entire decision is (1) the proposal has constituent generations and a
`broad_class` string (defense-in-depth; already guaranteed upstream), (2)
an `identification`-or-`context`-role evidence pick exists, (3) that pick's
`subject_geometry` is a valid, non-degenerate normalized box. **No
confidence, count, or class-plausibility signal is read anywhere in this
function**, confirmed by its own docstring ("Decodability is intentionally
not re-checked here..."). `candidate_visit_authority.evaluate_candidate_
authority` (the sibling authority gate) separately checks mode/activation/
lineage/ambiguity/continuation/rate-budget — none of those are about
evidence *content* either. Both proposals here satisfy every one of these
structural checks genuinely and honestly (real constituent generation, real
`animal` broad_class as the detector itself reported it, a real
identification pick with a real, valid, geometrically-sane box) — there is
no "loophole" a non-animal candidate slipped through; the admission funnel
behaved exactly as every one of its own contracts documents it should.

## 9. Species-inference role

BioCLIP 2 ran unconditionally (no eligibility/gating call precedes it) on
the `classifier_same_frame` crop, through a **closed-set, forced-choice**
14-species backyard-bird label space (`candidate_pack: "Backyard Core"`,
`score_kind: "candidate_relative_softmax"` — scores are relative *among
these 14 labels only* and always sum to 1; there is no 15th "not a bird"/
open-set option anywhere in the call). Given any input whatsoever — a real
bird, a person's arm, a squirrel, a garden hose — this mechanism is
structurally guaranteed to return one of the 14 labels with some
"confident-looking" relative score. This is a real, but **already
documented, pre-existing, standing** Gate B regression class (roadmap.md
"Background/empty evidence → confident species label," previously
evidenced by 5/70 Visits in the 2026-08-18 Observational Quality Closure
cohort and 2/21 in the 2026-08-19 End-to-End session) — not newly
discovered here, and this milestone does not build a fix for it (see
Decision, below). Separately and incidentally observed, not itself a
defect: `VisitModel.species_guess` is auto-populated from the rank-1
suggestion for list-view display (matches the already-documented "the
product already treats the Visit's latest suggestion as *the*
suggestion" fact in roadmap.md's multi-subject section) — `reviewed_label`
correctly stayed `None` throughout; no reviewed truth was ever created.

Per the task's own explicit caution, species inference is **not** the
first wrong transition — it is a second, independent, already-tracked
defect that compounds the first (a wrong detector class) into a materially
more misleading artifact (a specific, confident, wrong bird name, rather
than an honest "unidentified animal").

## 10. Admission role

Admission is not at fault (rules out **F**): both proposals' own
`SpeciesSuggestionModel.created_at` (23:51:59, 23:52:21) is **strictly
after** their own Visit's `observation_candidate_visits.created_at`
(23:51:44, 23:52:06) — species suggestion runs as a separate, later,
post-admission step, never an input to the admission decision. Admission
correctly persisted exactly what the (mis-classified) upstream track
supported, with fully valid, undrifted, honestly-scored evidence — see §7
and §8. This is the funnel behaving exactly as its own contracts specify;
the wrongness entered one stage earlier.

## 11. Deterministic RED

Reproduced against the real, unmodified production code (not a synthetic
straw-man): `tests/test_human_background_admission_hard_negative_2026_08_20.py`,
two tests, built entirely from the real recovered facts in §2-3 (offsets,
per-detection confidence samples, bounding boxes, generation/track/proposal
ids — no fabrication):

1. `test_the_two_tracks_are_correctly_never_merged_as_one_visit` — feeds
   the real tracklet facts into the real, unmodified
   `visit_episode_assembler.classify_boundary`; asserts
   `decision == "incompatible"`, `reason == "temporal_overlap"` (§4's
   finding, machine-verified).
2. `test_both_proposals_reach_real_visit_creation_today` — feeds both real
   `AssembledVisitProposal`s (real `confidence_evidence`, real geometry,
   real offsets; zero private image bytes — only a small synthetic
   solid-color JPEG placeholder, per
   [public-benchmark-governance.md](public-benchmark-governance.md)'s
   consent boundary) through `admission_replay.evaluate_shadow_admission`
   — the real, unmodified `candidate_visit_authority`/
   `candidate_quality_gate`/`candidate_visit_adapter` stack, against a
   freshly isolated, disposable repository (never the real product
   database, per
   [perception-replay-regression-harness-contract.md](perception-replay-regression-harness-contract.md)).
   Asserts both proposals reach `outcome == "created"` — the deterministic
   reproduction of "human/background evidence currently reaches wildlife
   Visit creation," for the identical mechanism as the real Visits 139/140.

Both tests pass today (confirmed: `pytest ... -v` → 2 passed), which is
the *correct* RED/GREEN relationship for this milestone: the test proves
today's real, understood (not desired) behavior, serving as the durable
regression fixture the future Gate B milestone will need to flip, and as a
tripwire against any change that *accidentally* makes this worse in the
meantime. The module docstring says this explicitly so a future reader does
not mistake a passing test for "already fixed."

## 12. Root cause

The raw MDv5 detector genuinely, at real (non-marginal, `strong`-threshold-
clearing) confidence, assigned the `animal` class to a real person (with a
dog) crossing the yard/street. Every downstream MockingBird mechanism —
class-based tracking eligibility, tracklet boundary classification,
evidence-geometry lineage, the admission authority gate, and the evidence
quality gate — read that one signal correctly and behaved exactly as its
own governing contract specifies; none of them contain a fixable logic
defect. **No confidence, count, or consecutive-frame threshold could have
rejected this case without also rejecting real, same-session birds**:
Visit 140's `max_confidence` (0.877) exceeds every one of the ten genuine
bird Visits admitted in the same 90-minute session (highest real value:
0.828), and its `max_consecutive_detector_confirmed_frames` (4) ties the
session's own highest real-bird value — freshly reconfirming, with
independent 2026-08-20 data, the exact "no threshold clears both
conditions" finding
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)
"Production authority gate" already established from the 2026-08-19
cohort. The actual mechanism that turns this rare, real detector error into
a materially misleading product artifact — a confident, specific, wrong
bird species name rather than an honest "unidentified animal, needs review"
— is BioCLIP's complete lack of an abstention/open-set path (§9), which is
Gate B territory, already named in roadmap.md as a standing regression
class, not new.

## 13. Files changed

- `tests/test_human_background_admission_hard_negative_2026_08_20.py`
  (new) — the deterministic RED/regression fixture, §11.
- `docs/person-background-false-positive-attribution-v1-report.md` (new,
  this file).
- `docs/roadmap.md` — two small additive citations (not a restructuring):
  Gate A "Current disposition" item 3 and the Gate B "Background/empty
  evidence → confident species label" subsection each gain one sentence
  recording this milestone's fresh 2026-08-20 confirmation and naming the
  recommended next milestone; no gate, number, or section was reordered or
  rewritten.

No production module was modified (`src/mockingbird/observation/*.py`,
`src/mockingbird/repository/*.py` are byte-identical to `HEAD`) — matches
Decision B: no Gate-A code defect was found to fix.

## 14. Implementation

None beyond the test/report/doc changes in §13. No admission, tracker,
assembler, evidence-scoring, or species code was touched. No threshold was
raised. No person detector, person recognition, or feeder-specific rule was
added — none of the excluded techniques in the task's Scope Exclusions were
needed or used.

## 15. Negative / hard-negative fixture

`tests/test_human_background_admission_hard_negative_2026_08_20.py` itself
*is* the hard-negative fixture, in the smallest permissible form the task
asked for: bounded, real, session-derived metadata (confidence samples,
bounding boxes, offsets, ids) with **zero image bytes** and zero
personally-identifying content beyond an already-widely-used internal
Stream id. This deliberately does not stand up the full frames-directory
Perception Replay Harness CLI machinery (`perception_regression_cli.py`'s
`acceptance_recording`/`benchmark_manifest` input shapes) — those require
real frame image files, which would mean either copying real private field
photographs into the repository (governance-prohibited) or fabricating
synthetic frames unrelated to the real evidence (explicitly disallowed by
the task, "do not write a synthetic straw-man test"). Driving the funnel's
existing pure boundaries (`classify_boundary`, `evaluate_shadow_admission`)
directly with real recovered facts satisfies "existing detector/admission
pure boundaries" and "bounded session-derived metadata fixtures" from the
task's own preference list without either problem, and is the same pattern
`tests/test_admission_replay.py` already establishes for this exact layer.

## 16. Focused tests

```
pytest tests/test_human_background_admission_hard_negative_2026_08_20.py -v
```
2 passed (0.30s). See §11 for what each proves.

## 17. Tier-2 validation

Every directly-affected detector/evidence/admission/replay module's own
test file, run together with the new fixture:

```
pytest tests/test_human_background_admission_hard_negative_2026_08_20.py \
       tests/test_frame_tracker.py tests/test_visit_episode_assembler.py \
       tests/test_candidate_visit_authority.py tests/test_candidate_quality_gate.py \
       tests/test_admission_replay.py tests/test_perception_regression.py \
       tests/test_perception_regression_cli.py tests/test_perception_regression_io.py \
       tests/test_counterfactual_lineage.py tests/test_detection_quality_accounting.py \
       tests/test_admission_policy.py tests/test_observation_frame_driven.py \
       tests/test_candidate_visit_repository.py tests/test_candidate_visit_adapter.py -q
```
**385 passed**, 0 failed, 26.45s. No pre-existing test needed modification.

## 18. Core result

`python scripts/verify_core.py` (the whole backend suite except
`slow`-marked packaging/subprocess/large-artifact tests, 3338 tests
selected): **PASS — 3325 passed, 2 skipped, 11 xfailed, 0 failed, 437.75s
(7m17s)**. Skips/xfails are pre-existing (hardware/platform-dependent),
unrelated to this milestone; zero failures, zero flakes observed.

## 19. Decision

**B — ROOT CAUSE IS IDENTIFICATION ELIGIBILITY / ABSTENTION.**

Every Gate-A mechanism (class-based tracking eligibility, boundary
classification, evidence lineage, authority gate, quality gate) behaved
correctly on the evidence it was given; no confidence/count/geometry signal
already available to Gate A can separate this case from real same-session
birds without costing recall (§12, freshly demonstrated with concrete
numbers). Building a new Gate-A eligibility mechanism now would either (a)
not work (no available signal separates the cases) or (b) require a
genuinely new kind of signal (visual/content-based, not detector
confidence) that is exactly Gate B's "credible-animal gate, or classifier
abstention" territory, already scoped in roadmap.md. Recommended next
milestone: **Identification Eligibility + Abstention v1** (Gate B) — not a
competing Gate-A framework.

## 20. Commit SHA

`[filled in after commit below]`

## 21. Final git status

`[filled in after commit below]`

## 22. Next natural milestone

**Identification Eligibility + Abstention v1** (Gate B), per Decision B
above and roadmap.md's own already-scoped requirements list ("Requirements
the eventual abstention/eligibility mechanism must satisfy" under Gate B):
one canonical eligibility policy, machine-readable abstention reason codes,
a genuine open-set/null outcome (`bird_uncertain`/`animal_uncertain`)
distinct from a low-confidence guess, and evidence-quality gating on visual
signals BioCLIP's own crop actually carries (subject pixel size, blur,
occlusion, bounding-box completeness) — never a return to detector
confidence, which this milestone freshly proved does not separate this
class of case. Both Visits 139/140 (this milestone) and the preserved
nuthatch→Tufted-Titmouse/Red-bellied-Woodpecker misidentifications (2026-08-19,
explicitly not touched here) are concrete, real inputs that milestone should
use.

## Why did the same real-world person passage become two wildlife/bird Visits?

A real MDv5 detection error — not a MockingBird logic defect — classified a
person (walking a dog) as the `animal` class twice, at real, non-marginal
confidence, across a brief tracking gap most likely caused by momentary
occlusion behind the feeder tree. Every downstream MockingBird mechanism
(class-gated tracking, the tracklet-boundary rule that correctly refuses to
fabricate identity across a temporal overlap, evidence-geometry lineage,
and the admission authority/quality gates) then did exactly what it is
supposed to do with that one wrong signal, producing two well-evidenced,
undrifted, honestly-admitted `needs_review` Visits — the "two Visits"
outcome is the expected multiplication of one upstream error through
already-correct, already-deliberate downstream policy, not a new
duplication bug. The smallest safe correction that prevents this *class* of
false Visit without reducing real bird recall is **not** a Gate-A change at
all — this milestone proved no confidence/count/geometry signal already
available to Gate A can separate this case from real same-session birds
(Visit 140's own peak confidence exceeded every real bird that session). The
correct, safe fix is Gate B: give species inference a genuine abstention
path so a low-credibility, non-bird-shaped crop yields an honest "not
clearly a bird" instead of a confident, specific, wrong species name —
turning a rare, unavoidable detector miss into a low-cost "please review an
unidentified animal" instead of a misleading, specifically-named false
sighting. That is the next milestone this report recommends
(Identification Eligibility + Abstention v1), not a new admission
mechanism here.
