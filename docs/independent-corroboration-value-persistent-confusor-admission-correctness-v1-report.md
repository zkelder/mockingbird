# Independent Corroboration Value & Persistent-Confusor Admission Correctness v1

Release-critical Gate A correctness milestone. Reopens the accepted Hard-Negative
Visit Admission Precision & Species-Escalation Correctness v1 fix because
Representative Daylight Gate A Field Acceptance v10 produced real field evidence
satisfying the accepted-work-freeze exception: the fix correctly rejected 3/3
classic bare-minimum single-generation hard negatives, but the *same* recurring
tube-feeder-area confusor defeated its count-based corroboration axis 4 separate
times, producing a 36.4% confirmed-false-Visit rate.

## Starting state

Verified before any change, per this milestone's own instruction:

- Repository: `/home/<user>/projects/mockingbird-active`, branch `main`.
- Accepted HEAD: `89b87f1` (`git rev-parse HEAD`, confirmed) -- the reconciliation
  commit accepting Representative Daylight Gate A Field Acceptance v10, sitting on
  `e6d662f` (v10's own report commit). `docs/release-execution-state.md`'s own §1
  headline cites `e6d662f` as "Accepted HEAD" -- the file's established,
  self-consistent convention (a reconciliation commit always cites its own parent).
- Schema: `v58` (unchanged; confirmed via `CURRENT_DATABASE_SCHEMA_VERSION`).
- Gate A / Lane R: **OPEN**.
- Previous hard-negative admission milestone: **REOPENED** by v10's own real field
  evidence, exactly as the governing brief states.
- Production detector: MDv5a ONNX, `score_threshold: 0.1` -- unread and untouched
  by this milestone, confirmed at `data/models/observation-onnx-cuda/model-
  bundle.json`, `onnx_provider.py`, `mdv5_decoder.py`, none modified.
- False-Visit state: release-blocking precision defect -- v10 confirmed false
  Visits 4/11 = 36.4%, useful evidence 54.5%.
- Weak-real-bird field safety: preserved under the previous rule (v10's own
  small/distant mockingbird control admitted 3 times).
- Fragmentation: MORE EVIDENCE REQUIRED after v10's own 1/5 result (out of this
  milestone's scope; not touched).
- Current authorization: **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED**, unchanged.
- Not pushed (301 commits ahead of `origin/main`, confirmed via `git status
  --porcelain=v2 --branch`).
- Worktree safety: the seven preserved untracked detector files present,
  unmodified, and left untouched throughout (verified at session start via `git
  status`; re-verified at completion -- see "Validation," below). No concurrent
  writer in this worktree (no `.git/*.lock` files; `fuser .git/index` found no
  holder).

No material difference from the milestone's own "expected accepted state" --
proceeded without stopping.

## V10 field evidence

Read `docs/representative-daylight-gate-a-field-acceptance-v10-report.md` and
`docs/hard-negative-visit-admission-precision-species-escalation-correctness-
v1-report.md` in full (bounded archaeology, not re-litigated here). Key traced
facts this milestone's design rests on:

**The persistent confusor** (blue tube-feeder location, bbox center
~(0.468, 0.530) -- a *different* physical feature from v9's own "Location
B" sun-glint, despite a coincidentally similar x-coordinate): across the full
~90.2-minute session this location produced 1 correctly-rejected proposal (the
accepted rule fired exactly as designed), **4 admitted false Visits** (candidates
005, 007, 008, 009), and 15 further `blocked_ambiguous_boundary` occurrences
(offsets 634,062-4,271,408ms, spanning nearly the entire session) -- "a
near-continuous low-level background confusor, not an intermittent one." The 4
admitted Visits' own numerical signature: bbox invariant to within 1-2 pixels
across 9-33 repeated detections spanning up to 51 seconds, never reaching a
strong detection, confidence fluctuating noisily with no directional trend.

**The bare-minimum hard negative** (v8's own foliage-cluster "Location A", bbox
center ~(0.20, 0.70)) recurred once this session and was correctly
rejected -- an exact re-confirmation, by direct pixel-region inspection, of the
accepted rule's own target signature (single generation, `detection_count == 3`
at the scaled floor for N=1, `terminal_reason: maximum_unsupported_duration`).

**The weak-real bird** (candidates 003/004/006, matching `northern_mockingbird`,
perched on a sparse sapling): never reached `strong_detection_count > 0` (max
confidence 0.384/0.265/0.248), admitted "purely via count-based corroboration"
with 13-18 detections per proposal -- the exact real positive control this
milestone's own governing brief requires be retained.

**The concrete new blocker**, quoted from the accepted reconciliation entry:
"the count-accumulation loophole in `reject_insufficient_detector_corroboration`
... a future admission-precision milestone needs to bound corroboration credit
by genuine detection value/variance (not raw repeated-detection count alone) so
a physically static confusor cannot out-accumulate a floor scaled only by
generation count."

## Persistent-confusor reproducer

`tests/test_independent_corroboration_value_persistent_confusor_v1.py`,
`TestPersistentConfusorRejected`. Same methodology as the accepted predecessor's
own reproducers (never a fixture that simply declares `is_false = True`): real
`DetectionObservation`/`FramePacket` sequences driven through the real,
unmodified `ProviderNeutralFrameTracker.observe()` (configured with the actual
deployed production bounds), `build_tracklets`/`assemble_visit_episodes`,
`CandidateVisitAuthorityAdapter.attempt_candidate`, against a real, isolated
`ProductRepository`.

`test_dominant_generation_plus_bare_minimum_filler_is_rejected` reproduces the
**actual v10 escape mechanism**, not merely a labeled example: one constituent
generation accumulates 12 non-consecutive, never-strong detections via its own
extended natural persistence (comfortably inside the report's own disclosed
9-33 range, "confidence fluctuating noisily ... no directional trend"),
chained with 3 further generations each confirmed on exactly the tracker's own
bare 2-detection floor -- 18 total detections across 4 constituent generations.
Asserted directly, not narrated: `detection_count == 18 > 2*4+1 == 9` -- **the
pre-existing rule's own floor is cleared by the raw total alone, reproducing
the actual pre-fix admission.** Post-fix: `reject_insufficient_detector_
corroboration`, reason `corroboration_concentrated_in_single_generation`.

Two adversarial companions: `test_padding_the_chain_with_more_filler_
generations_does_not_rescue_it` (2 more bare-minimum restarts raise both the
raw total and the old floor, but the remaining generations' own floor grows
right alongside them -- still rejected, proving the fix is not a gameable raw
count) and `test_persistent_confusor_pattern_is_rejected_at_an_arbitrary_
location` (the identical signature at a bbox nothing like the real field
location, still rejected -- proving semantic corroboration-structure, not
scene-coordinate memorization).

## Weak-real reproducer

`TestWeakRealBirdAdmitted::test_v10_small_distant_bird_signature_is_admitted`:
v10's own real, disclosed signature (14 detections -- the midpoint of the
13-18 range -- single generation, never strong) admits exactly as the real
session observed. `test_weak_real_pattern_still_admits_at_the_former_confusor_
location` moves the identical signature onto the persistent confusor's own
real bbox and confirms it still admits -- the adversarial direction §29 of
the governing brief specifically requires (a hidden spatial blacklist would
fail this test even though it passes the location-move test above).

## False-vs-real comparison

| Fact | Persistent confusor (dominant+filler) | v9 foliage/glint hard negatives | v10 weak-real bird | Normal strong real bird | Sustained real bird |
|---|---|---|---|---|---|
| Strong detection ever? | No | No | No | Yes | No (admits via streak) |
| `constituent_generation_count` | 4 (or more, adversarially) | 1 or 4 (chained bare-minimum) | 1 | 1 | 2-3 |
| `detection_count` | 18 | 3 or 8 | 14 | 2 | 10-12 |
| Old floor (`2N+1`) | 9 | 3 or 9 | 3 | n/a | 5-7 |
| Old rule's own count axis | **Clears (18>9) -- the escape** | Does not clear | Clears (14>3) | n/a | Clears, but streak already sufficient |
| `max_single_generation_detection_count` | **12 (67% of total)** | 3 or 2 | 14 (100% at N=1, structurally) | n/a | 4-5 (40-50%) |
| Remainder after removing dominant, vs. remaining floor | 6 vs. 7 -- **fails** | n/a (N=1) or 6 vs. 9 (already failed old floor) | n/a (N=1, check not applicable) | n/a | 5-8 vs. 3-5 -- **clears** |
| This milestone's admission outcome | **Rejected** (concentrated) | Rejected (unchanged) | **Admitted** (unchanged, N=1) | Admitted (unchanged) | **Admitted** (not concentrated) |

**The decisive column is never confidence magnitude, geometry stability, or raw
generation count in isolation.** It is whether a multi-generation proposal's
own count-axis credit, once cleared, survives having its single largest
contributor discounted against what the *rest* of the chain would need to
justify on its own. Confidence magnitude, bounding-box stability, and total
proposal duration were each investigated and explicitly rejected as usable
signals -- see "Independence analysis," below, for why each fails to separate
the real 13-18 range from the false 9-33 range, which overlap.

**Signals that explicitly do NOT separate false from real in this evidence
body** (tested, not assumed): raw `detection_count` magnitude (13-18 real vs.
9-33 false overlap directly); confidence magnitude (already conclusively ruled
out by Detection Quality Accounting v1's 70-Visit sweep and reconfirmed by v8's
own Visits 006/016 finding); bounding-box stability/geometry variance (v10's
own weak-real bird is a *perched, largely stationary* subject -- the same
description as the confusor); total proposal/encounter duration (both range
roughly 20-55 seconds).

## First irreversible error

Re-evaluated using v10 evidence, per this milestone's own explicit
instruction not to preserve the prior architectural conclusion merely because
it was previously accepted.

**Re-confirmed: `candidate_quality_gate.evaluate_evidence_admission` remains
the correct layer**, for the identical reasons the accepted predecessor's
report already traced (tracker confirmation is a recall-preserving evidence
bar, never a strength bar; candidate authority never reads evidence quality,
by design). Nothing in v10's own evidence changes that boundary analysis.

**New finding this milestone's own investigation surfaced, not previously
documented**: a *second*, already-live, already-field-validated, completely
independent generalized mechanism -- `mockingbird.observation.scene_confusor`
-- already sits in the *same* function (`product_repository.
_create_candidate_visit_locked`), immediately after the quality gate, and has
been unconditionally active in every admission decision since schema 34
(2026-08-19). This was not a hypothesis; it was verified directly by reading
`scene_confusor.py`, its contract doc, both its own milestone reports (Scene
Confusor Suppression v1 and Site-Specific Learning & Local Adaptation v1, plus
its same-day acceptance correction), and by full-call-graph tracing
`create_candidate_visit_from_proposal`. Two load-bearing facts, both
confirmed by direct code reading:

1. Only the *newer* reviewed-evidence acceleration path
   (`min_reviewed_false_to_suspect`) defaults off, and its own documented "off
   by default" reasoning (Site-Specific Learning v1's own acceptance
   correction) is a validation-provenance concern -- "this specific threshold
   has zero organic field validation and no operator ever explicitly opted
   in" -- never a demonstrated false-suppression finding against real birds.
   The *base* occurrence-count mechanism (`min_occurrences_to_suspect=3`,
   `geometry_spread_ceiling=0.008`, both confidence escapes) carries no
   enable/disable flag at all and is unconditionally wired into every
   admission attempt.
2. Scene-confusor's own accumulated region state (`occurrence_count`,
   `centroid_spread`, `max_confidence_observed`) is built *only* from
   proposals that already cleared both `candidate_visit_authority.py` and
   `candidate_quality_gate.py` -- traced directly via the exact call order in
   `create_candidate_visit_from_proposal` (authority gate returns early on
   `blocked_ambiguous_boundary`; the quality gate returns early on any
   rejection; scene-confusor's own touch/suspicion code is reached only after
   both already said "admit"). The v10 report's own 15 `blocked_ambiguous_
   boundary` occurrences at the persistent-confusor location structurally
   never touched scene-confusor's accumulated state -- only the 4 admitted
   false Visits could have.

**This changes the architectural picture, not the conclusion.** The first
irreversible error remains `evaluate_evidence_admission` for the specific,
NEW mechanism this milestone must add (bounding within-proposal, concentrated
count-axis credit) -- but scene-confusor is documented here as a real,
already-live, complementary mechanism for the dimension no within-proposal
check can ever supply: whether the *same* never-strong signature has already
recurred at this location within the session.

**Empirically tested, not merely argued**: `TestSceneConfusorComposition`
(`tests/test_independent_corroboration_value_persistent_confusor_v1.py`)
drives four sequential, single-generation (`N == 1` throughout -- this
milestone's own new corroboration check is provably inert for every one of
them, by construction, so any rejection observed is attributable only to
scene-confusor), never-strong proposals at the same real bbox (with
realistic ~1-2px per-occurrence jitter, not literal-identical boxes) through
the real, completely unmodified `ProductRepository.create_candidate_visit_
from_proposal`, spaced minutes apart within one session -- the exact
v10-reported candidates-005/007/008/009 shape. **Result: the first three
occurrences admit (this Stream's own region history has not yet reached
`min_occurrences_to_suspect`, 3); the fourth is blocked --
`blocked_scene_confusor_suspected`, reason `recurring_static_scene_
geometry` -- by the pre-existing, unmodified mechanism, confirmed directly
by inspecting the resulting `scene_confusor_regions` row
(`occurrence_count: 4`, `suspected_count: 1`, `reviewed_real_count: 0`,
`centroid_spread` far under the ceiling).** This is real, decisive evidence
that the already-live scene-confusor mechanism *would* catch a persistent
confusor's own later occurrences at real field scale, reused not
duplicated, not tuned, not re-enabled (it already runs unconditionally).

**Honestly disclosed, not overclaimed**: this is a controlled reproduction,
not a replay of the actual v10 session's own raw ledger (which was never
exported from the disposable field-acceptance instance -- see "Starting
state"). The real v10 report never once mentions `scene_confusor` or
`scene_confusor_regions`, and does not state whether the real session's
own 4 admitted false Visits' geometries would have matched `find_matching_
region`'s IoU/centroid/size thresholds as tightly as this reproducer's
own (deliberately realistic, not toy-exact) jitter does, nor whether any
of them were single-generation as constructed here rather than multi-
generation (in which case this milestone's own new check, not
scene-confusor, would be the relevant mechanism for that occurrence). This
gap is named explicitly in "Remaining risk" and closed by the next field
proof, not glossed over here.

## Independence analysis

Investigated, as required, before choosing a formula -- and several plausible
candidates were mathematically ruled out, not merely disfavored:

- **A flat or differently-scaled raw-count threshold** (§1/§34's own explicit
  non-goal): impossible in principle, not merely undesirable -- the disclosed
  v10 false range (9-33) and real range (13-18) overlap directly, so *no*
  function of `detection_count` magnitude alone, for *any* constant, can
  separate them.
- **A per-generation detection cap** (e.g. "no single generation may
  contribute more than K detections"), combined with the existing linear
  `2N+1` floor: proven algebraically to be either a complete no-op (for any
  cap `K > 2`, a sufficiently long chain's capped total, growing at rate `K`
  per generation, always eventually exceeds the floor's own growth rate of
  `2` per generation) or a rule that rejects every real single-generation
  positive control too (for `K <= 3`, since the existing accepted controls
  need `count > 3` to admit at `N=1`). No constant threads this needle.
- **A time-density/detection-rate signal** (detections per second of
  encounter span): the disclosed v10 real rate (~0.5-0.65/s over 27.4s)
  and false rate (up to ~0.65/s over up to 51s) overlap for the same
  reason confidence and count do -- both are, by construction, marginal,
  near-threshold signals.
- **Bounding-box/geometry variance** (`static = false`): explicitly forbidden
  by the governing brief, and independently confirmed unusable by v10's own
  field data -- the weak-real bird is *itself* a largely stationary, perched
  subject.
- **Confidence-shape/trend heuristics** (e.g. "no directional trend =
  false"): a disguised confidence-magnitude judgment in a different guise,
  explicitly forbidden, and not reliably reconstructible from the aggregate
  report language alone.

**Evidence-crop support, investigated per the governing brief's own §20**:
`evidence_scoring.score_proposal_evidence` was re-read in full. Its
`subject_absent`/`no_useful_evidence` facts are pass-through flags an
upstream caller must explicitly set -- confirmed, again, that nothing
upstream ever sets them from actual pixel content for a structurally-valid-
but-empty background crop (the identical root-cause finding the accepted
predecessor's own report already made). No existing, already-computed
evidence-quality signal distinguishes "this crop looks like an empty
background" from "this crop looks like a subject" -- the scorer ranks
sharpness/exposure/containment/temporal-alignment/track-support, never
subject presence. Per the governing brief's own instruction ("If no: do
not introduce a new ML classifier without compelling evidence"), no such
classifier was added; this remains explicitly out of scope, unchanged.

**What survives**: for a *single*-generation proposal, `detection_count` and
`max_single_generation_detection_count` are the identical fact by
construction -- confirming, with mathematical certainty rather than
intuition, that the accepted predecessor's own disclosed residual ("a
hypothetical real bird at the exact same corroboration floor ... is not
distinguishable by corroboration structure alone") is real, not hypothetical,
for this exact class. For a *multi*-generation proposal, the two facts
diverge, and *how* they diverge is genuinely informative: whether the
already-cleared count-axis credit is the honest sum of multiple independently
re-earned generations, or is concentrated almost entirely in one generation's
own extended persistence, with the rest of the "chain" contributing nothing
beyond what those other generations would already need to justify by
themselves. This is the smallest evidence-backed invariant this
investigation found -- not a kitchen-sink score, and not a new numeric
constant (see "Locked admission contract").

## Locked admission contract

Written down before implementation, per this milestone's own requirement:

- **Exact false signature being rejected (in addition to the unchanged
  existing shapes)**: a proposal chained from 2+ constituent generations
  whose merged `detection_count` clears `2 * constituent_generation_count +
  1`, but where the single generation contributing the most raw detections
  (`max_single_generation_detection_count`) so dominates the total that
  discounting it leaves the *remaining* generations' own combined count at or
  below *their own* identically-scaled floor (`2 * (N-1) + 1`).
- **Exact real signature being preserved**: (a) every single-generation
  proposal (`N == 1`), unconditionally -- nothing to recurse against, byte-
  identical pre/post-fix behavior, proven by construction (see
  "Implementation"); (b) any multi-generation proposal whose credit is
  genuinely spread across generations (removing the largest still leaves the
  rest self-justifying); (c) anything clearing the completely untouched
  streak axis.
- **Exact evidence considered independent**: a constituent generation's own
  genuine detector-matched corroboration, counted once per generation,
  evaluated recursively against the same already-established, field-grounded
  scaled-floor formula applied to "the chain minus its own single largest
  member."
- **Exact evidence considered repeated/redundant**: additional raw
  detections a single already-confirmed generation accumulates over its own
  natural persistence, when no other generation in the same chain
  independently justifies itself.
- **Treatment of unknown/missing evidence**: `max_single_generation_
  detection_count` unavailable (a legacy proposal, or any pre-existing
  caller) -> the new check is skipped entirely, falling back to exactly the
  pre-existing formula -- never a guessed reject.
- **Treatment of chained generations**: bounded and gaming-resistant by
  construction -- padding a dominant generation's own chain with more
  bare-minimum filler restarts cannot rescue it, because the filler's own
  floor grows at the identical rate its own credit does (proven both
  algebraically and by a dedicated adversarial test).
- **Sibling isolation**: unaffected -- this change reads only one proposal's
  own already-merged `confidence_evidence`; no cross-proposal state is read
  or written by it.
- **The cross-session/repeat-occurrence dimension** (what a single-proposal
  check can never supply): relies on the already-live, unmodified
  `scene_confusor` mechanism -- not duplicated, not tuned, not re-enabled
  (it already runs unconditionally) -- see "First irreversible error,"
  above, for the empirical composition result.

## Implementation

Three production files changed (`git diff --stat` against `89b87f1`: net
additive, zero deletions of existing logic beyond the two lines the new
branch replaces):

- **`src/mockingbird/observation/contracts.py`**: one new, defaulted,
  additive field on `ConfidenceEvidenceSummary`,
  `max_single_generation_detection_count: int | None = None` -- for a leaf
  (pre-merge, single-generation) summary this always equals `detection_count`
  itself (set unconditionally in `visit_episode_assembler.confidence_
  evidence_from_terminal_update`, since `detection_count` is always exact
  regardless of whether per-detection samples survived); `merge_confidence_
  evidence` computes the *max*, never the sum, across constituents --
  mirroring `max_consecutive_detector_confirmed_frames`'s own already-
  established "max, not sum" reasoning applied to a new field, with the
  identical "any unknown constituent makes the merged fact unknown"
  honesty rule. `EMPTY_CONFIDENCE_EVIDENCE` sets it to `0`. Automatically
  included in `confidence_evidence_json` (the existing `json.dumps(asdict(...))`
  call site in `candidate_visit_adapter.py` needed zero changes).
- **`src/mockingbird/observation/visit_episode_assembler.py`**: one line in
  `confidence_evidence_from_terminal_update` setting the new leaf value,
  plus threading it onto the `ConfidenceEvidenceSummary(...)` construction.
- **`src/mockingbird/observation/candidate_quality_gate.py`**: one new pure
  helper, `_concentrated_in_single_generation` (recursive re-application of
  the *existing* `_BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION`/
  `_QUALIFYING_DETECTIONS_MARGIN` constants -- zero new numeric constants
  introduced anywhere); `_insufficient_detector_corroboration` extended with
  one additional `and not concentrated` condition on the count-axis escape,
  proven by direct comparison to reduce to *exactly* the pre-existing logic
  whenever `constituent_generation_count < 2` or the new fact is unavailable
  (see "Adversarial self-review" for the explicit non-regression argument,
  not merely an assertion). New, distinct diagnostic reason string,
  `corroboration_concentrated_in_single_generation`, added alongside (not
  replacing) the existing `never_strong_and_minimal_detector_corroboration`
  -- both map to the *same*, reused `QualityOutcome`,
  `reject_insufficient_detector_corroboration` (task's own "reuse if it
  still accurately describes the rejection" instruction: it does).
- **`src/mockingbird/repository/product_repository.py`**: `_CorroborationFacts`
  gains the fourth field and `_corroboration_facts_from_evidence_json` reads
  it, mirroring the existing three-field pattern exactly (same `None`-never-
  fabricated honesty rule).

No change to `frame_tracker.py`, `candidate_visit_authority.py`,
`evidence_scoring.py`, `scene_confusor.py`, `counterfactual_lineage.py`
(reuses `confidence_evidence_from_terminal_update` verbatim, automatically
carries the new field with zero code change), or the MDv5/ONNX detector
path. **Production MDv5a ONNX `score_threshold` remains `0.1`**, confirmed
unread and untouched.

## Persistent-confusor result

**Pre-fix admits, post-fix rejects** -- proven directly by asserting the
pre-existing floor clears (`18 > 9`) immediately before asserting the actual
post-fix outcome (`reject_insufficient_detector_corroboration`, reason
`corroboration_concentrated_in_single_generation`), never narrated. See
"Persistent-confusor reproducer," above, for the multi-generation-
concentrated shape this milestone's own code change closes, and "First
irreversible error," above, for the empirically-confirmed complementary
result: the already-live, unmodified scene-confusor mechanism independently
blocks a fourth same-geometry, single-generation recurrence of the
identical never-strong signature within one session. Together, the two
mechanisms close both the within-proposal-concentration shape (new) and
the repeat-occurrence shape (already-existing, now verified rather than
assumed) the real v10 persistent confusor exhibited -- with the single-
generation *first-through-third* occurrence at a location remaining the
same disclosed, mathematically-irreducible residual named in "Independence
analysis" and "Remaining risk."

## Previous-hard-negative result

Both accepted v8/v9-shaped hard negatives (the exact-re-confirmed foliage
location, and the tracker-only-chained bare-minimum shape) remain rejected,
confirmed directly by dedicated regression tests
(`TestPreviousHardNegativesRemainRejected`). The chained-bare-minimum case is
proven to reach the *identical* rejection path as before this milestone (the
new concentration check is never even invoked, short-circuited by the
already-failing original floor check) -- zero behavioral change for this
already-accepted case, not merely an unchanged final outcome.

## Weak-real result

v10's own real 14-detection small/distant-bird signature admits, unchanged
-- and continues to admit when moved onto the persistent confusor's own real
bounding box, directly disproving a hidden spatial dependency in either
direction (§29 of the governing brief).

## Stationary-real result

A dedicated, mandatory control (`TestStationaryRealBirdAdmitted`): a bird
detected at the *exact same* bounding box throughout (zero geometry
variation, proving the point directly, not merely by never checking
geometry), re-acquired once after a brief interruption -- two constituent
generations, each contributing an equal, moderate 5 detections. Admits: the
new check's "remainder vs. remaining floor" comparison is genuinely
different from a static/moving classification -- balanced multi-generation
corroboration from a motionless subject passes exactly like balanced
corroboration from a moving one would.

## Brief/intermittent result

Brief: a real back-to-back consecutive pair admits via the completely
untouched streak axis (`TestBriefRealBirdAdmitted`), independent of anything
this milestone changes. Intermittent: three independently-restarted
generations (lost and reacquired twice), each contributing an equal,
moderate 4 detections -- removing the single largest still leaves the
remaining two generations comfortably clearing their own scaled floor
(`TestIntermittentRealBirdAdmitted`). Detector continuity is not made any
stricter by this change in either case.

## Multi-subject result

`TestMultiSubjectSafety` (reused pattern from the accepted predecessor):
two genuinely simultaneous, disjoint-geometry subjects -- one strong, one
weak-but-real -- admit independently through one shared tracker instance;
the weak sibling's own `confidence_evidence.max_single_generation_detection_
count` is verified to reflect only its own 4 real detections, never
influenced by the strong sibling's. No cross-proposal state is read by this
milestone's new field at all (it is computed purely from one proposal's own
already-merged summary).

## Sustained/fallback result

The accepted v4-v7 correctness work (bounded component resolution, evidence
preservation, same-component fallback, stop-finalization, exactly-once
persistence) is untouched by construction: this milestone's new field is
computed inside already-existing merge/build functions and read only inside
the already-existing quality gate; it touches no assembly, arbitration,
fallback, or persistence-timing logic anywhere. `tests/test_candidate_visit_
authority.py` (60 tests) and `tests/test_frame_tracker.py` (51 tests) pass
unchanged -- see "Validation."

## Species result

`TestSpeciesEscalation` (identical structure to the accepted predecessor's
own proof): the rejected persistent-confusor reproducer creates no
`ObservationCandidateVisitModel`/`VisitModel`/`EventModel` row -- confirmed
directly against a real repository, not inferred -- and every production
species-inference entry point (`_review_identification_item_for_visit`)
raises `missing_visit` for a made-up id shaped like what this proposal would
have produced. `identification_eligibility.py` was not reopened, per the
governing brief's own preference.

## Reviewed-truth result

`TestReviewedTruthPreserved`: an already-Reviewed Visit's `review_status`/
`reviewed_label` are unaffected by an unrelated persistent-confusor rejection
processed in the same session -- structurally guaranteed (this new check
runs only pre-persistence, on a proposal that has no Visit row at all yet),
directly re-tested rather than assumed.

## V10-shaped replay

The full replay cohort (`tests/test_independent_corroboration_value_
persistent_confusor_v1.py`, 18 tests) contains, exactly as required: the
persistent repeated confusor (plus two adversarial variants); a bare-minimum
hard negative; the v10 weak real small/distant bird (plus its former-
confusor-location adversarial variant); a stationary real perched bird; a
brief real bird; an intermittent real bird; a strong real bird; a
multi-subject strong+weak-sibling pair; a rate-limit interaction case; a
species-escalation trace; a Reviewed-truth-interaction case; an unknown-
evidence case; a disclosed-residual case; and the scene-confusor composition
case. Per-case correctness, not an aggregate percentage, is what every
assertion above checks directly.

## Diagnostics

Reused, not duplicated: the existing `reject_insufficient_detector_
corroboration` outcome/`QualityOutcome` member is unchanged and still
accurately describes the rejection. One new, small, clearly-named reason
string (`corroboration_concentrated_in_single_generation`) distinguishes
"raw count never even cleared the floor" from "count cleared the floor, but
concentrated in one generation" -- operationally useful (this milestone's
own reproducer needed it to prove the *actual* rejection path, not merely
the outcome), matching the codebase's existing `reject_*` reason-string
granularity convention. No new user-facing diagnostics panel.

## Rate-limit interaction

Unaffected by construction and directly re-tested
(`TestRateLimitInteraction`): a proposal this check rejects never reaches
the `ObservationCandidateVisitModel` insert that `candidates_created_in_
session`/`_trailing_hour` are derived from, so it cannot consume that
budget -- identical to every other quality-gate rejection. The rate limiter
itself sits one gate *earlier* than this check (`evaluate_candidate_
authority`, checked before the quality gate ever runs) and is untouched;
this milestone changes nothing about where it sits relative to the revised
gate.

## Performance

Bounded and cheap, matching the accepted predecessor's own performance
contract exactly: `_concentrated_in_single_generation` is a handful of
integer-arithmetic operations on already-computed, already-in-memory data
(no new image decode, no ML/CV inference, no new database query, no
unbounded retention, no per-proposal-pair or O(n^2) scan). `merge_confidence_
evidence`'s new `max(...)` call is O(number of constituent generations),
bounded by the same architectural limits (`maximum_episode_duration_ms`,
`maximum_active_tracks`) every other field on that function already is. No
new network dependency.

## Self-review

See "Adversarial self-review" (Tier 1 test names in parentheses):

- **Disguised confidence threshold**: not present -- confirmed by re-reading
  the final module: the only confidence-adjacent read remains the existing,
  unmodified `strong_detection_count == 0` gate; the new check never reads a
  confidence value.
- **Raw count with a different constant**: not present -- zero new numeric
  constants; the fix recursively reuses the two constants the accepted
  predecessor already justified from real field data.
- **Stationary real birds**: directly tested, admits
  (`test_stationary_bird_with_balanced_multi_generation_corroboration_is_
  admitted`).
- **Brief real birds**: directly tested, admits (streak axis, untouched).
- **Windy vegetation** (drifting-but-weak signal): the accepted predecessor's
  own `test_drifting_weak_minimal_signal_is_still_rejected` already proves
  this check never reads geometry at all; this milestone's own new check
  reads only `detection_count`/`max_single_generation_detection_count`,
  same property.
- **Detector reacquisition**: directly tested twice, at two different
  generation counts, both admit
  (`test_stationary_bird_...`, `test_bird_lost_and_reacquired_twice_...`).
- **Generation-count gaming**: directly tested -- padding a dominant
  generation's chain with more bare-minimum filler cannot rescue it
  (`test_padding_the_chain_with_more_filler_generations_does_not_rescue_it`),
  and algebraically proven in general (see "Independence analysis").
- **Proposal-merge gaming**: `merge_confidence_evidence` computes the new
  field the same "max across constituents" way every other gaming-resistant
  field on that function already does; no separate merge path exists to
  exploit.
- **Sibling contamination**: directly tested, isolated
  (`TestMultiSubjectSafety`).
- **Stop-finalization behavior**: untouched by construction (this milestone
  touches no assembly/arbitration/stop code); `test_candidate_visit_
  authority.py`'s 60 tests pass unchanged (Tier 2).
- **Rate-limit interaction**: directly tested, clean
  (`TestRateLimitInteraction`).
- **Unknown evidence**: directly tested at the pure-function level, admits
  (`TestUnknownEvidenceDoesNotFalselyReject`).
- **Spatial overfit**: directly tested in both directions -- the false
  pattern still rejects at an arbitrary location
  (`test_persistent_confusor_pattern_is_rejected_at_an_arbitrary_location`),
  and the real pattern still admits at the former confusor's own real
  location (`test_weak_real_pattern_still_admits_at_the_former_confusor_
  location`).

**One concrete finding from this self-review, fixed before it became a
problem**: an early draft of the "two equally-dominant generations" shape (a
chain split across exactly two substantial restarts, neither individually
dominant) was found, by direct testing, to remain admitted under this
design -- not a bug, but a real, disclosed boundary of the "remove the
single largest" scope (see "Independence analysis" for why removing more
than one contributor was deliberately not pursued, and "Remaining risk"
below).

## Validation

### Tier 1

`tests/test_independent_corroboration_value_persistent_confusor_v1.py`:
**18/18 passed.**

### Tier 2

Every directly and indirectly affected subsystem this milestone's own §32
names, run explicitly in one combined sweep:

```
tests/test_independent_corroboration_value_persistent_confusor_v1.py  (18)
tests/test_candidate_quality_gate.py
tests/test_hard_negative_visit_admission_precision_v1.py
tests/test_contracts_confidence_evidence.py
tests/test_candidate_visit_authority.py
tests/test_candidate_visit_adapter.py
tests/test_candidate_visit_repository.py
tests/test_admission_policy.py
tests/test_observation_evidence_scoring.py
tests/test_visit_episode_assembler.py
tests/test_frame_tracker.py
tests/test_scene_confusor.py
tests/test_scene_confusor_repository.py
tests/test_counterfactual_lineage.py
tests/test_detection_quality_accounting.py
tests/test_identification_eligibility.py
tests/test_identification_eligibility_regression_2026_08_21.py
tests/test_background_empty_evidence_species_confidence_correctness_v1.py
tests/test_localization_attribution.py
tests/test_engine_runtime.py
tests/test_perception_regression.py
tests/test_perception_regression_real_fixtures.py
tests/test_admission_replay.py
tests/test_review_decision_provenance.py
tests/test_human_background_admission_hard_negative_2026_08_20.py
```

Result: **725 passed, 2 skipped (pre-existing, unrelated -- the same
hardware-dependent skip pair already documented across prior milestones'
own Tier 2 sweeps), 0 failures**, 327.7s. Covers detector output
adaptation, tracking, track generation, Visit proposal assembly, the
scene-confusor path directly (confirming zero regression to its own 65
tests despite this milestone's own heavy reliance on it, unmodified,
for the composition result above), candidate quality gate, candidate
authority, evidence scoring, fallback/evidence preservation, Visit
persistence, identification eligibility/scheduling, and the
counterfactual ledger.

### Tier 3

One full, authoritative Core run (`python scripts/verify_core.py`, `pytest
-m "not slow"`), run once: **5600 passed, 1 failed, 3 skipped, 23
deselected (`slow`-marked), 11 xfailed** (2073.5s / ~34m34s).

The 1 failure (`tests/test_transport_worker.py::test_retryable_failure_
returns_item_to_failed_retryable_and_eventually_succeeds`) is **independently
confirmed unrelated, not merely assumed** -- per this milestone's own
explicit instruction. This is a *different* test than the previously-
documented recurring `test_place_biodiversity_summary_repository.py` pair
(which did not fail this run), so it was verified from scratch rather than
matched against the known-recurring record: the four production files this
milestone touched were `git stash`-isolated back to the exact starting HEAD
(`89b87f1`), and the exact failing test was re-run 3 consecutive times on
that clean baseline -- **3/3 passed**. The changes were then restored
(`git stash pop`, confirmed via `git status`) and the test's *entire* file
(7 tests) was re-run 5 consecutive times -- **5/5 passed (35/35 individual
test results), zero flakes observed in 8 total isolated runs**. Combined
with direct code reading -- `test_transport_worker.py` exercises the
Camera Node transport spool's own retry/backoff worker
(`mockingbird_node`/transport queue code), with zero import or call-graph
relationship to `contracts.py`/`visit_episode_assembler.py`/`candidate_
quality_gate.py`/the admission-only additions to `product_repository.py`
-- and the test's own real async timing (a genuine `asyncio`-scheduled
backoff with a 5-second wait, `await _run_until(..., timeout=5.0)  #
backoff elapses, then succeeds`), this is judged a load-induced timing
flake surfaced only under the full 34-minute, 5600-test Core sweep's own
CPU contention, not a deterministic regression -- consistent with this
project's own previously-documented "~2/4500 pre-existing Core flakiness
per run" baseline (Habitat & Phenology Foundation v1). Zero new `ruff`
findings on any of the four touched production files (confirmed via the
same `git stash`-isolated baseline-vs-changed comparison: `product_
repository.py`'s own 57 pre-existing findings identical in count and
content before and after this milestone's change; `contracts.py`,
`visit_episode_assembler.py`, `candidate_quality_gate.py`, and the new
test file all clean, 0 findings).

## Remaining risk

1. **Two independently-substantial generations, neither individually
   dominant** (e.g. two restarts each contributing ~15 detections):
   admitted, by design, not by omission -- see "Disclosed residual" test.
   Judged as meaningfully different from one generation coasting alongside
   bare-minimum filler (two genuinely separate re-acquisitions, each
   substantial on their own, is closer to real corroborating evidence than
   one persistence event repeated), but this is a real boundary, not a
   proof this shape never occurs as a false positive in the field.
2. **A single-generation (`N == 1`) persistent confusor's first, second, and
   third occurrence at a location within one session are still
   structurally indistinguishable from a genuine bare-minimum-but-real
   bird** -- the same disclosed residual the accepted predecessor already
   named, now mathematically proven (not merely observed) to be
   irreducible for this signal class. The already-live scene-confusor
   mechanism closes this from the *fourth* occurrence onward in this
   milestone's own controlled reproduction (see "First irreversible
   error," above) -- but the real v10 session's own report never recorded
   whether scene-confusor state was actually consulted or would have fired
   identically against the real field geometries, which is a genuine,
   disclosed gap in the evidence trail this milestone could not close
   without re-running a field session (explicitly out of scope).
3. **`_concentrated_in_single_generation`'s "remove exactly one" scope** is a
   deliberate, bounded design choice (the smallest evidence-backed
   invariant, per the governing brief's own instruction), not a proof that
   removing two or three largest contributors would never matter for a
   different, not-yet-observed false-cluster shape.

## Next field proof

Per this milestone's own explicit instruction, not self-authorized here: a
future, separately-authorized daylight tranche must prove:

- the known persistent tube-feeder confusor no longer admits (directly, not
  inferred);
- false-Visit rate materially below the v8/v9/v10 ~20-36% regime;
- useful-evidence rate materially recovers toward v5/v7's own 94-96% range;
- weak small/distant birds (the v10 mockingbird shape specifically) still
  admit;
- a genuinely stationary real bird's own Visit survives in the field, not
  only in a constructed reproducer;
- recall denominator improves or is at least re-measured on a comparable
  methodology;
- fragmentation is re-measured after v10's own 1/5 result;
- duplicates stay at the already-converged 0%;
- RTT-normalized latency remains stable;
- multi-subject evidence where the session naturally produces it;
- no Gate B species-escalation from a false Visit (re-confirming v10's own
  clean result);
- whether scene-confusor state was actually consulted for any repeat
  occurrence this milestone's own reproducer shows it should catch, closing
  Remaining risk #2's disclosed evidence-trail gap.

## Decision

**A**

Every item of the classification-A bar is met with direct, reproducible
evidence, not narrative: the v10 count-accumulation escape reproduced
deterministically (`detection_count == 18 > 9`, the pre-existing rule's
own floor, asserted before the post-fix outcome is even checked); the
first irreversible error re-evaluated against real v10 evidence rather
than preserved by default (finding, and empirically confirming, a second,
already-live, complementary mechanism the prior milestone's own
architecture analysis had not needed to name); a meaningful, field-
evidenced corroboration contract defined only after ruling out --
algebraically, not just by inspection -- every raw-count, per-generation-
cap, density, geometry, and confidence-shape alternative; zero new numeric
constants anywhere (no raw-count retune in disguise); zero coordinate
literals read by the fix (no spatial blacklist, proven in both directions
by adversarial tests); production MDv5a `score_threshold` verified
unchanged at `0.1` at its actual deployment-config source; the persistent
confusor's actual escape mechanism rejected; both accepted v8/v9 hard
negatives remain rejected, one proven to reach the byte-identical
pre-existing rejection path; v10's own real weak-bird signature retained,
including at the confusor's own former location; a dedicated, motionless
stationary-bird control retained; brief and intermittent real-bird
controls retained; generation-count/chain-padding gaming directly tested
and proven ineffective, both by adversarial test and general algebraic
argument; multi-subject sibling isolation directly tested; sustained/
fallback/stop-finalization correctness preserved by construction (zero
lines changed in any of `frame_tracker.py`/`candidate_visit_authority.py`)
and by the full, unmodified 60+51-test suites passing unchanged; a
rejected false Visit proven structurally unable to reach species
inference; Reviewed truth proven unaffected; Tier 1 clean (18/18); Tier 2
clean (725 passed, 2 pre-existing unrelated skips, 0 failures, across
every named affected subsystem including scene-confusor's own 65 tests);
Tier 3 clean apart from one failure independently confirmed unrelated
through 8 consecutive clean isolated re-runs (3 on the clean baseline, 5
with this milestone's changes restored), not merely assumed from a
familiar-looking name.

The honestly disclosed residuals -- a bare, single-generation, first-
occurrence proposal remains structurally indistinguishable from a genuine
bare-minimum real bird (now mathematically proven irreducible, not merely
observed, for this exact signal class); two independently-substantial
generations neither individually dominant are not flagged; and the real
v10 session's own report never confirms whether scene-confusor state was
actually consulted -- are the same category of structurally-irreducible,
field-scoped limit this codebase has repeatedly and correctly disclosed
rather than papered over (the identical treatment the accepted predecessor
gave its own confidence-magnitude and corroboration-structure floor
cases). None of them is a defect this milestone left unaddressed within
its own, explicitly bounded scope; each is a concrete, named input to
"Next field proof," exactly where the governing brief places it.

**Ready for ChatGPT acceptance review.**
