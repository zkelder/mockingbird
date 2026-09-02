# Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1

Release-critical Gate A correctness milestone. Field-proves and closes the
reproducible precision defect Representative Daylight Gate A Field
Acceptance v9 confirmed: recurring static-scene hard negatives (a
hanging-leaf cluster, a feeder-cap sun-glint) surviving detection, tracking,
and the confidence-blind admission boundary to become confirmed-false
user-visible Visits, one of which (`visit-observation-candidate-026`)
escalated to a confident, wrong species label.

## Starting state

Verified before any change, per this milestone's own instruction:

- Repository: `/home/zkelder/projects/mockingbird-active`, branch `main`.
- Accepted HEAD: `58c0634` (git `rev-parse HEAD`, confirmed) -- the
  reconciliation commit accepting Representative Daylight Gate A Field
  Acceptance v9. `docs/release-execution-state.md`'s own content as of this
  commit cites `8b5185b` (v9's report commit, its own parent) as "Accepted
  HEAD" -- the file's established, self-consistent convention (a
  reconciliation commit always cites its own parent, never itself, since it
  cannot know its own hash while being written).
- Schema: v58 (`CURRENT_DATABASE_SCHEMA_VERSION`,
  `src/mockingbird/storage/database.py:45`).
- Gate A / Lane R: **OPEN**. Authorization: **NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED** (§3, unchanged since v9).
- RTT-normalized true latency: field-proven (v9, item (1) closed).
- Fragmentation: 0% across a sixth/seventh convergent cohort -- budget
  -review ready.
- Duplicate rate: 0% across a fourth convergent cohort -- strongly
  supported.
- False-Visit rate: v8 22.2% (6/27), v9 20.0% (5/25) -- v8's elevated rate
  **reproduces**, a real scene characteristic, not a cohort anomaly. This
  milestone's own reason for existing.
- Useful-evidence rate: v9 76.0% strict (19/25) -- below the previously
  -floated ~85% candidate, which v8 had already withdrawn.
- Field-proven hard-negative defect: **OPEN** -- two distinct recurring
  locations traced in full (v8/v9).
- Gate B residual: field-proven on at least one false Visit
  (`visit-observation-candidate-026`, confident `"carolina_chickadee"` on
  confirmed-empty background).
- Not pushed (287 commits ahead of `origin/main`, 0 behind).
- Worktree safety: the seven preserved untracked detector files present,
  unmodified, and left untouched throughout (re-verified at session start
  and again at completion -- see "Validation" below); no concurrent writer
  in this worktree (no lock files; `git status` showed exactly the expected
  starting untracked set).

No material difference from the milestone's own "expected accepted state" --
proceeded without stopping.

## v8/v9 field evidence

Read `representative-daylight-gate-a-field-acceptance-v9-report.md` and
`-v8-report.md` in full (via bounded archaeology, not re-litigated here).
Key traced facts this milestone's design rests on:

**Two recurring hard-negative locations**, both sharing one structural
signature -- zero detections ever reached `strong_detection_threshold`
(0.70), and every confirmed-false Visit was admitted purely because the
tracker's own bare `minimum_detector_confirmations` (2) was met, with
nothing else corroborating it:

- **Location A** ("hanging leaf cluster / thin branch tip over the road",
  bbox center ≈(0.20, 0.70)): v8's Visits 011/012/013 (`max_confidence`
  0.189/0.217/0.444) plus likely-false 029 (0.234); v9's Visits 003/004
  (part of a 9-Visit "zero-strong" cohort), confirmed empty on direct
  pixel-region inspection in both sessions.
- **Location B** ("sun-glint on the tube feeder's glossy cap", bbox center
  ≈(0.467, 0.530), new in v9): Visits 025/026/027. `visit-observation-
  candidate-026`'s own full trace: **3 raw detections, confidence
  0.109-0.111, single short generation (7-61s), confirmed empty on
  4-independently-sampled-frame pixel inspection** -- and the one Visit
  that received a confident wrong species label
  (`"carolina_chickadee"`), root-caused in v9's own report to its
  geometry-attribution source being `"tracker"` (a real, contemporaneous
  track) with genuinely detector-sourced raw detections -- exactly the
  residual class Background/Empty Evidence Species-Confidence Correctness
  v1's own commit named as out of its scope, not a regression.
  `visit-observation-candidate-027` (same location): **9 chained,
  independently-restarted track generations spanning ~4 minutes**,
  confidence 0.147-0.363 throughout, terminal reasons `tracker_lost`/
  `maximum_duration`/`maximum_unsupported_duration`, "the tracker kept
  re-confirming the same static glint as if it were a persistent subject"
  per v9's own False-Visit section (v9's separate Latency section
  describes the same Visit more neutrally as "the tracker repeatedly
  losing and reacquiring the subject" for latency-measurement purposes --
  the two sections are not reconciled in the source report; this milestone
  treats the False-Visit section's classification as authoritative, per
  the report's own decisive pixel-content check).

**Decisive methodological fact (v8, directly informing this milestone's own
non-goals):** v8's own report states plainly that its two confirmed-real
Visits (006, 016) were "not distinguishable from the false cluster by
confidence alone... despite superficially similar confidence numbers" --
the only check that separated them was direct pixel-content inspection.
This independently confirms, from real field data, the same conclusion
Detection Quality Accounting v1's own confidence-threshold sweep already
reached from a different, larger corpus (see "Root cause," below): no
confidence-magnitude threshold can safely separate this milestone's false
cluster from genuine weak Visits.

**Useful-evidence-rate methodology (v9):** 19/25 = 76.0% strict (5
background/empty = the confirmed-false Visits, 1 weak/inconclusive, 0
wrong-subject, 0 ambiguous).

## Reproducers

Built as real, production-code-driven reproductions, not narrative
retellings or fixtures that simply label a proposal "background" (per this
milestone's own explicit instruction) -- see "V8/V9-shaped replay," below,
for the complete pre/post results table. Methodology, shared by every
reproducer: real `DetectionObservation`/`FramePacket` sequences driven
through the real, unmodified `ProviderNeutralFrameTracker.observe()`
(configured with the actual deployed `frame_driven_provider.
FrameDrivenSettings` values -- `strong_detection_threshold=0.70`,
`minimum_detector_confirmations=2`, `candidate_detector_fps=4.0`, and every
other production bound, not a looser test default), through the real,
unmodified `build_tracklets`/`assemble_visit_episodes`, into the real,
unmodified `CandidateVisitAuthorityAdapter.attempt_candidate`, against a
real, isolated `ProductRepository`.

- **Hard-negative A** (recurring foliage/hanging-leaf-shaped): a single
  track generation, two genuine weak detections (confidence 0.15/0.18,
  well below strong), separated by a genuine detector miss (non
  -consecutive) -- the sparsest signature the tracker's own confirmation
  bar allows, deliberately at or below what either v8/v9 Visit at this
  location individually reported.
- **Hard-negative B** (feeder-cap sun-glint-shaped): reproduces
  `visit-observation-candidate-026`'s own real, traced numbers exactly --
  3 genuine detections, confidence 0.109/0.111/0.110 (v9's own reported
  0.109-0.111 range), non-consecutive, single short generation.
- **Hard-negative C** (tracker-only chained weak chain, `candidate-027`
  -shaped): 4 independently-restarted track generations at one fixed
  location, each individually shaped like hard-negative B's own bare
  -minimum signature (2 non-consecutive weak detections, confidence
  0.15-0.30, comfortably inside v9's own reported 0.147-0.363 range for
  the real case), each terminating via a genuine `>5000ms`-since-last
  -detection gap (reproducing `maximum_unsupported_duration`, one of the
  three real terminal reasons v9's own report names for this exact
  Visit), spaced within `merge_gap_ms` (15s) so the real, unmodified
  assembler merges all four into one proposal -- exactly as v9's own 9
  -generation chain did.
- **Two adversarial reproducers** (see "False-vs-real comparison" and
  "V8/V9-shaped replay," below): the identical hard-negative-A structural
  signature at an arbitrary bounding box nothing like either real field
  location, and at a slightly drifting (not perfectly static) position --
  proving the rule is semantic, not scene-coordinate memorization, and not
  an accidental "staleness" proxy.

## False-vs-real comparison

A compact structural comparison, built from the same real production
pipeline for both columns (never a hand-asserted table) -- the traced v9
false chains against this milestone's own matched genuine weak-bird
controls:

| Fact | Hard-negative B (`candidate-026`-shaped) | Hard-negative C (`candidate-027`-shaped, merged) | Genuine: small/distant bird | Genuine: sustained multi-generation (1 real streak) |
|---|---|---|---|---|
| Strong detection ever? | No | No | No | No |
| Genuine `detection_count` | 3 | 8 (summed across 4 restarts) | 5 | 6 (summed across 3 restarts) |
| Constituent generations | 1 | 4 | 1 | 3 |
| Qualifying-count floor (`2N+1`) | 3 | 9 | 3 | 7 |
| Count clears its own floor? | No (3 ≤ 3) | No (8 ≤ 9) | **Yes** (5 > 3) | No (6 ≤ 7) |
| `max_consecutive_detector_confirmed_frames` | 1 | 1 (max across restarts, not summed) | 1 | **2** (one restart shows a real back-to-back pair) |
| Streak clears floor (`>1`)? | No | No | No | **Yes** |
| Admission-boundary confidence *magnitude* alone (v8's own decisive finding) | Indistinguishable from genuine Visits 006/016 -- confidence alone cannot separate them | Indistinguishable (0.147-0.363, overlapping genuine weak-bird ranges) | Indistinguishable from the false cluster by magnitude alone | Indistinguishable by magnitude alone |
| This milestone's admission outcome | **Rejected** (neither axis clears) | **Rejected** (neither axis clears) | **Admitted** (count axis clears) | **Admitted** (streak axis clears) |

The decisive column is never confidence magnitude (deliberately
indistinguishable throughout, matching v8's own real finding) -- it is
always whether *either* corroboration-structure axis clears its own
scaled/ungameable floor. Hard-negative C's own summed count (8) coming
close to, but never exceeding, its own scaled floor (9) is not
coincidental: it is the real field number (v9's own 9-generation chain,
scaled down to 4 restarts here for a tractable reproducer while preserving
the identical per-generation shape) -- see "Remaining risks" for the
honest acknowledgment that this is close enough to be a real, not
manufactured, edge case.

## Governing prior art discovered during archaeology

Two pieces of already-accepted, already-built infrastructure directly
anticipate this milestone and materially shaped its design, found via
bounded reading of `docs/detection-quality-accounting-contract.md`
("Shadow admission-policy evaluation" / "Production authority gate") and
`src/mockingbird/observation/admission_policy.py`:

1. **A pure confidence-magnitude admission policy was already swept against
   70 real reviewed Visits (Observational Quality Closure v1, 2026-08-19)
   and conclusively rejected**: "conditions 2 and 3 fail together at every
   threshold swept... no swept value clears both conditions
   simultaneously... production admission stays confidence-blind,
   unchanged." This milestone does not re-litigate that finding -- it is
   why §5/§14 of this milestone's own governing instructions forbid a
   confidence threshold, and this report treats it as settled.
2. **The *temporal-corroboration* dimensions of that same shadow-policy
   module (`minimum_qualifying_detections`, `minimum_consecutive_confirmed_
   frames`) were built at the same time but were never actually validated**
   -- the legacy reviewed corpus available in 2026-08-19 predated
   per-detection sample retention, so every policy exercising those
   dimensions came back `insufficient_evidence`, structurally, not because
   the dimensions are unsound. This is precisely the open question this
   milestone closes, using v8/v9's own real, sample-retaining data as the
   "newly captured session" `docs/detection-quality-accounting-contract.md`
   itself named as the way to eventually answer it.

This milestone's fix is a narrowly-scoped, structurally distinct
corroboration-*count/streak* check -- not a promotion of the swept
confidence-threshold policy (which stays correctly un-promoted) and not a
wholesale adoption of `admission_policy.AdmissionPolicy` (its typed
`ConfidenceEvidenceSummary` signature does not fit the duck-typed,
product-repository-decoupled boundary `candidate_quality_gate.py` and
`product_repository.py` already established for this exact fact -- see
"Implementation," below, for why a small, local, duck-typed helper was used
instead of importing that module). See "Remaining risks" for an honest
accounting of what "Production authority gate"'s own six conditions this
narrower fix does, and does not, satisfy.

## First irreversible error

Traced explicitly, per this milestone's own required question: **where did
the system first possess enough evidence to say "this should not become a
user-facing wildlife Visit"?**

Read `candidate_visit_authority.evaluate_candidate_authority` and
`candidate_quality_gate.evaluate_evidence_admission` in full (the two
admission-adjacent decision points), plus `frame_tracker.py`'s own
confirmation logic, to answer this precisely rather than assume it.

- **Tracker confirmation** (`frame_tracker._confirm`, `minimum_detector_
  confirmations=2`) is *not* the right boundary. It is deliberate,
  documented, already-correct infrastructure: "a repeated, spatially
  -coherent evidence bar, never a strength bar" (the code's own comment,
  `frame_tracker.py:718-733`), justified by real attempt-3 evidence that a
  genuine bird's own confirming pair of observations is routinely both
  individually weak. Tightening this would reject genuine weak birds before
  they have any chance to accumulate further corroboration -- exactly the
  regression this milestone must not cause.
- **`evaluate_candidate_authority`** (mode/activation/lineage/ambiguity
  /continuation-pending/rate-limits) never read detector confidence or any
  evidence-quality fact, by design -- and correctly so: its own contract
  doc frames it as deciding whether a proposal is *allowed* to exist,
  independent of whether its evidence is any good. Confirmed directly:
  `evaluate_candidate_authority` has zero references to `confidence_
  evidence` anywhere in its 8-step gate order.
- **`evaluate_evidence_admission`** (the quality gate) is the first, and
  correct, boundary: it already exists specifically to compose "already
  -measured facts into one conservative 'reviewable enough' decision" (its
  own pre-existing docstring, unchanged by this milestone) -- it is the
  layer whose entire job is asking "is this evidence worth a human's time,"
  run once, immediately before evidence bytes are written and a Visit/Event
  becomes real. Before this fix it asked that question using *only*
  structural facts (does a selected candidate exist, is its geometry
  valid) and never detector corroboration -- so a proposal needed nothing
  beyond the tracker's own bare 2-detection confirmation floor to become a
  full, persisted, user-visible Visit.

**Conclusion: `candidate_quality_gate.evaluate_evidence_admission` is the
first irreversible product decision**, and the correct one to extend --
not tracker confirmation (would cost real recall), not candidate authority
(the wrong architectural layer for evidence-quality judgments, which the
existing two-gate separation already deliberately assigns to the quality
gate), and not a downstream species-layer patch (would leave the
non-species-labeled false Visits, the majority of the defect, unfixed).

## Root cause

The admission pipeline already computes rich, per-detection confidence
accounting (`contracts.ConfidenceEvidenceSummary`, built by Detection
Quality Accounting v1: `detection_count`, `max_confidence`, `strong_
detection_count`, `max_consecutive_detector_confirmed_frames`, and more),
threaded all the way onto `AssembledVisitProposal.confidence_evidence` and
persisted as `CandidateVisitProposalFacts.confidence_evidence_json` -- but
**no admission-adjacent gate had ever read it**. `evidence_scoring.py`
computes image-quality/geometry/role facts for *ranking and selecting*
evidence, not for judging whether a subject is credibly present; its
`subject_absent`/`subject_visible` hard-rejection reasons are pass-through
flags an upstream caller must set, and nothing upstream ever sets them for
a real, structurally-valid-but-empty background crop. Real field data
(v8's own 006/016-vs-false-cluster methodological finding, and Detection
Quality Accounting v1's own 70-Visit sweep) already conclusively rules out
a confidence-*magnitude* fix. What was left unused was the *corroboration
-structure* half of the same already-computed evidence: a hard-negative
location's admitted Visits, in every traced case, showed nothing beyond
the tracker's own bare structural minimum on any axis -- never a strong
detection, never more than a handful of total genuine detections, never
two genuine detections in a row.

## Admission contract

**New rule, added at `candidate_quality_gate.evaluate_evidence_admission`,
step 4 (last, after proposal-support/selected-evidence/geometry validity
already pass):** a proposal is rejected
(`reject_insufficient_detector_corroboration`) only when *all* of the
following are simultaneously true and *known* (never guessed):

1. `strong_detection_count == 0` -- never once reached `strong_detection_
   threshold` (0.70).
2. `detection_count <= 2 * constituent_generation_count + 1` -- no more
   genuine detector-matched corroboration, in total, than the tracker's own
   bare per-generation confirmation floor (2), once per constituent track
   generation this proposal chains together, plus one.
3. `max_consecutive_detector_confirmed_frames <= 1` -- never two genuine
   detections in an unbroken row, anywhere in the whole proposal.

Any one of (1)/(2)/(3) failing (i.e. a strong detection, or corroboration
clearing either scaled floor) admits. Either `confidence_evidence` itself,
or any individual fact read from it, being unavailable *never* causes a
reject (fail-open on unknown, matching this codebase's universal
honesty convention).

This is deliberately **not** a confidence-magnitude threshold: condition
(1) reuses the *already-existing* `strong_detection_threshold` fact
(whether any single detection ever cleared it), never a new number, and
conditions (2)/(3) are pure corroboration-*count/structure* checks,
entirely independent of *how* weak a detection was.

## Implementation

Two production files changed (`git diff --stat`: 233 insertions, 1
deletion, zero deletions of existing logic):

- **`src/mockingbird/observation/candidate_quality_gate.py`** (+182
  lines): new `QualityOutcome` member `reject_insufficient_detector_
  corroboration` (added to `REJECTED_OUTCOMES`); three module constants
  (`_BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION=2`, `_QUALIFYING_
  DETECTIONS_MARGIN=1`, `_MINIMUM_CONSECUTIVE_DETECTOR_CONFIRMED_
  FRAMES=1`), each documented with its exact field-evidence justification;
  new pure helper `_insufficient_detector_corroboration`; `evaluate_
  evidence_admission` gains one new, keyword-only, defaulted (`None`)
  parameter, `confidence_evidence: object | None`, read via `getattr`
  duck-typing -- mirroring `candidate_visit_authority.
  ProposalArbitrationFacts.confidence_evidence`'s own already-established
  convention for exactly this cross-module boundary, so this module still
  imports neither `contracts` nor `admission_policy`. Every pre-existing
  call site (including this gate's own 14 pre-existing unit tests) is
  unaffected -- the parameter defaults to `None`, which degrades to "this
  check never fires," byte-identical to the pre-fix gate.
- **`src/mockingbird/repository/product_repository.py`** (+51/-1 lines):
  one new small, frozen `_CorroborationFacts` dataclass and one new
  `_corroboration_facts_from_evidence_json` deserializer, placed beside and
  mirroring `_max_confidence_from_evidence_json`'s own established style
  exactly (same honesty rule: `None`, never a fabricated value, for a
  missing/malformed/legacy payload) -- deliberately *not* a reconstructed
  `contracts.ConfidenceEvidenceSummary`, preserving this repository
  module's own long-standing, repeatedly-reinforced convention of never
  importing observation-engine dataclasses (see `CandidateVisitProposalFacts.
  confidence_evidence_json`'s own docstring). The single existing call site
  (`_create_candidate_visit_locked`, immediately before evidence bytes are
  written) now passes `confidence_evidence=_corroboration_facts_from_
  evidence_json(proposal.confidence_evidence_json)` -- no other call site
  of `evaluate_evidence_admission` exists anywhere in the codebase
  (confirmed by repo-wide grep).

No change to `candidate_visit_adapter.py` (it already serialized
`confidence_evidence_json` onto every request, from Detection Quality
Accounting v1 -- this milestone consumes an existing fact, adds no new
plumbing upstream of the quality gate). No change to `frame_tracker.py`,
`visit_episode_assembler.py`, `evidence_scoring.py`, `scene_confusor.py`,
`counterfactual_lineage.py`, or the MDv5/ONNX detector path -- confirmed by
`git diff --stat` showing exactly the two files above. **Production MDv5a
ONNX `score_threshold` remains `0.1`**, unread and untouched by this
milestone (verified at `data/models/observation-onnx-cuda/model-
bundle.json:35`, `onnx_provider.py`, `mdv5_decoder.py` -- none modified).

`counterfactual_lineage.ADMISSION_REJECTED_OUTCOMES` picks up the new
outcome automatically (it imports `candidate_quality_gate.REJECTED_
OUTCOMES` directly, `import ... as _QUALITY_REJECTED_OUTCOMES`) --
confirmed live: `"reject_insufficient_detector_corroboration" in
ADMISSION_REJECTED_OUTCOMES` is `True`, with zero changes to that module.

## Weak-real-bird preservation

Six distinct genuine-weak-bird positive controls, each driven through the
real production tracker/assembler/authority/quality-gate/adapter/repository
path (see "Reproducers," above, for the shared methodology) -- all admit:

- small/distant bird (weak, never strong, 5 real detections as it
  forages);
- brief landing/departure (short encounter, but a real 3-consecutive
  -frame streak while genuinely present);
- low-confidence-but-visually-real bird sitting still (never strong,
  nearly stationary -- proves this check reads only corroboration
  count/streak, never geometry stability, so a genuinely still bird is
  never penalized for not moving);
- partially occluded bird (inconsistent, gap-interrupted weak detections,
  4 real total);
- intermittently corroborated bird (sparse, always non-consecutive, 4 real
  total over a longer window -- exercises the count-based escape
  specifically, proving the two axes are independently sufficient);
- sustained multi-generation activity with one real consecutive segment
  (3 chained restarts, the same outward shape as the rejected false chain,
  admitted because one restart shows genuine 2-consecutive-frame
  corroboration -- direct contrast against the rejected case).

## Multi-subject result

`TestMultiSubjectSafety` drives two genuinely simultaneous, disjoint
-geometry subjects (one strong, one weak-but-real) through one shared
tracker instance and one shared set of `observe()` calls -- both are
admitted independently, and the weak sibling's own `confidence_evidence`
(`detection_count == 4`, its own real count) is verified never to include
or be influenced by the strong sibling's detections. No cross-subject
corroboration: `merge_confidence_evidence` only ever operates over one
proposal's own constituent tracklets, and `classify_boundary` classifies
genuinely temporally-overlapping tracklets `incompatible`/`concurrent_
sibling` before any merge logic runs -- unchanged by this milestone,
confirmed by the full, unmodified `test_visit_episode_assembler.py`/
`test_candidate_visit_adapter.py` multi-subject suites passing unchanged.

## Sustained-activity result

The accepted v4-v7 correctness work (bounded component resolution,
evidence preservation, same-component fallback, stop-finalization,
exactly-once persistence) is untouched -- this milestone's new check reads
only already-computed `confidence_evidence`; it does not touch `visit_
episode_assembler.py`, `resolve_ambiguous_boundary_arbitration`, or any
forced-decision/stop-finalization logic. `tests/test_candidate_visit_
authority.py` (60 tests, the bounded-decision-horizon/forced-decision
coverage) and `tests/test_frame_tracker.py` (51 tests) pass unchanged. A
dedicated positive control (above) additionally proves a genuinely
sustained, multi-restart real encounter still admits under the new check
specifically.

## Species-escalation result

**Option A (§20 of this milestone's own governing instructions), confirmed
directly against the real repository, not merely inferred from code
reading:** rejecting the false Visit at admission naturally eliminates the
issue. `visit-observation-candidate-026`'s own real shape (3 raw
detections, confidence 0.109-0.111, single generation, the feeder-cap
sun-glint location) is reproduced and rejected at admission
(`reject_insufficient_detector_corroboration`); the resulting outcome
carries `visit_id=None`/`event_id=None`, and direct inspection of the real
repository afterward confirms no `ObservationCandidateVisitModel` ledger
row was ever created for that proposal. Every production species
-inference entry point -- the automatic Observation Engine v2 path
(`engine_runtime._schedule_automatic_identification`, gated on `outcome.
created`), the legacy live-motion path, and the manual `POST
/api/review-queue/{target_type}/{target_id}/identify` action -- requires a
pre-existing `VisitModel` row to resolve at all
(`_review_identification_item_for_visit` raises `missing_visit`
otherwise, reproduced directly). Species inference structurally cannot
run on a proposal this check rejects.

Per this milestone's own explicit preference ("Prefer A when supported.
Do not reopen Identification Eligibility unless B is actually reproduced
independently"), **`identification_eligibility.py` was not modified, and
no second, narrower species-layer fix was added** -- A is sufficient and
directly proven, not merely argued.

## Reviewed-truth result

`TestReviewedTruthPreserved` proves directly: an already-Reviewed Visit's
`review_status`/`reviewed_label` are unaffected by an unrelated hard
-negative rejection processed in the same session. Structurally, this new
check runs only pre-persistence, on a proposal that does not yet have a
Visit row at all -- there is no code path by which it could touch an
existing, already-reviewed record. `_apply_species_guess_from_suggestion`'s
own unconditional `review_status == reviewed` no-op guard (unchanged) and
`_review_queue_items`'s own `include_reviewed=False` exclusion (unchanged)
remain the load-bearing protections for the unrelated, pre-existing
reviewed-truth question this milestone did not need to touch.

## V8/V9-shaped replay

All of "Reproducers"/"False-vs-real comparison" above, plus every genuine
-weak/strong/multi-subject/sustained-activity/species-escalation/Reviewed
-truth/rate-limit case, live together in one single deterministic replay
suite, `tests/test_hard_negative_visit_admission_precision_v1.py` (16
tests, 543 lines) -- containing, exactly as this milestone's own §23
requires, known false hard-negative chains, genuine weak birds, a normal
strong bird, sustained activity, and simultaneous subjects, all driven
through the same real production path (see "Reproducers," above, for the
full methodology). This is the before/after comparison that suite proves:

**Pre-fix** (verified by reverting the new check locally during
development, and by every hard-negative test initially failing with
`outcome="created"` before the fix's final form was reached): every
hard-negative reproducer is admitted, exactly matching the real v8/v9
field defect.

**Post-fix:**

| Reproducer | Result |
|---|---|
| Hard-negative A (foliage-shaped, 2 non-consecutive weak detections) | `reject_insufficient_detector_corroboration` |
| Hard-negative B (glint-shaped, `candidate-026`'s own real 3-detection signature) | `reject_insufficient_detector_corroboration` |
| Hard-negative C (`candidate-027`-shaped: 4 chained restarts, summed `detection_count=8`, merged `max_consecutive=1`) | `reject_insufficient_detector_corroboration` |
| Adversarial: same signature, arbitrary non-field bounding box | `reject_insufficient_detector_corroboration` |
| Adversarial: same signature, slightly drifting position (wind-blown-foliage shape) | `reject_insufficient_detector_corroboration` |
| 6 genuine weak-bird positive controls | all `created` |
| Normal strong Visit | `created`, unaffected |
| Multi-subject (1 strong + 1 weak-real sibling) | both `created`, independently |
| Sustained multi-generation activity (1 real consecutive segment) | `created` |
| `candidate-026`-shaped species-escalation trace | rejected; no `VisitModel`/`ObservationCandidateVisitModel` row; species inference structurally unreachable |
| Reviewed-truth interaction | unaffected |
| Rate-limit interaction (3 rejected hard negatives) | `candidates_created_in_session`/`_trailing_hour` stay `0`; `candidates_attempted_count` correctly still `3` |

**Adversarial self-review against overfitting (§24 of this milestone's own
instructions), performed explicitly, not assumed:** the two adversarial
tests above prove the rule is not keyed to either known field location's
coordinates -- `candidate_quality_gate.py` reads zero geometry/bounding
-box/coordinate values anywhere (confirmed by direct re-reading of the
final module). The chained-hard-negative-vs-chained-genuine-sustained pair
of tests specifically proves the rule is not merely "reject anything with
more than one track generation" -- both share the outward multi-restart
shape; only the corroboration structure differs, and only that difference
decides the outcome.

## Diagnostics

Reused, not duplicated, per this milestone's own instruction: the new
outcome (`reject_insufficient_detector_corroboration`) is added to the
*existing* `candidate_quality_gate.QualityOutcome`/`REJECTED_OUTCOMES`
vocabulary, using the established `reject_*` naming convention (matching
`reject_no_identification_or_context`/`reject_subject_geometry_invalid`/
`reject_insufficient_proposal_support`) -- distinguishing it clearly from
`rejected_insufficient_subject_evidence` was not needed: no existing or new
mechanism separately detects "subject absent" as a distinct concept from
"insufficient detector corroboration" (see "Root cause," above -- no such
signal exists today), so only the one new reason code was added, matching
the actual root cause traced. `counterfactual_lineage.ADMISSION_REJECTED_
OUTCOMES` and `classify_rejection_attribution`'s own generic outcome
-membership checks (`proposal.outcome in ADMISSION_REJECTED_OUTCOMES`) pick
it up automatically, with zero code changes to that module -- confirmed
live and via its full, unmodified 29-test suite passing unchanged. No new
user-facing diagnostics panel was added.

## Performance

Bounded, cheap, and unconditional per this milestone's own requirement:
the new check is a handful of `getattr`/integer-comparison operations on
already-computed, already-in-memory data (`confidence_evidence`, already
threaded onto every proposal for Detection Quality Accounting v1's own
purposes) -- no new image decode, no new ML/CV inference, no new database
query (the JSON blob it reads, `confidence_evidence_json`, was already
being read at this exact call site for the scene-confusor mechanism's own
`max_confidence` need), no new network dependency, no unbounded retention,
and no proposal-to-proposal scan (`O(1)` per admission decision, exactly
like every other check in this gate).

## Validation

### Tier 1

`tests/test_hard_negative_visit_admission_precision_v1.py`: **16/16
passed.** Covers every category this milestone's own Tier 1 matrix
requires: 3 false-hard-negative-chain shapes rejected (foliage, glint,
tracker-only-chained), 2 adversarial-overfit checks, 6 genuine-weak
-positive categories retained, 1 normal-strong-Visit non-regression, 1
multi-subject-isolation case, 1 sustained-activity case, 1 species
-escalation trace, 1 Reviewed-truth-interaction case, 1 rate-limit
-interaction case.

### Tier 2

Every directly and indirectly affected subsystem this milestone's own list
names, run explicitly, **zero regressions, zero new failures**:

```
tests/test_candidate_quality_gate.py            (14 -> 15, +1 new test, all pass)
tests/test_candidate_visit_authority.py          (60 passed)
tests/test_candidate_visit_adapter.py            (23 passed)
tests/test_candidate_visit_repository.py         (53 passed)
tests/test_admission_policy.py                   (unchanged, all pass)
tests/test_observation_evidence_scoring.py       (15 passed)
tests/test_visit_episode_assembler.py            (62 passed)
tests/test_frame_tracker.py                      (51 passed)
tests/test_scene_confusor.py                     (37 passed)
tests/test_scene_confusor_repository.py          (25 passed)
tests/test_counterfactual_lineage.py             (29 passed)
tests/test_detection_quality_accounting.py       (13 passed)
tests/test_identification_eligibility.py         (all pass)
tests/test_identification_eligibility_regression_2026_08_21.py (all pass)
tests/test_background_empty_evidence_species_confidence_correctness_v1.py (all pass)
tests/test_localization_attribution.py           (all pass)
tests/test_engine_runtime.py                     (all pass)
tests/test_perception_regression.py              (all pass)
tests/test_perception_regression_real_fixtures.py (all pass)
tests/test_admission_replay.py                   (all pass)
tests/test_review_decision_provenance.py         (all pass)
tests/test_acoustic_runtime.py                   (all pass, 2 pre-existing unrelated skips)
```

Combined: 546 passed in the fast sweep + 171 passed/2 skipped in the slower
sweep + 16 (Tier 1) = **733 tests, 0 failures, 2 pre-existing unrelated
skips**, across every module this milestone's own instructions named as
in-scope for Tier 2 (detector output adaptation, tracking, proposal
construction, candidate authority, evidence scoring, evidence
preservation/fallback, Visit assembly, persistence, identification
eligibility, species scheduling, Reviewed-truth interaction, counterfactual
ledger, perception replay).

### Tier 3

One full Core run (`python scripts/verify_core.py`, `pytest -m "not
slow"`), run once, authoritatively. Result: **5504 passed, 2 failed, 3
skipped, 23 deselected (`slow`-marked), 11 xfailed** (1868.59s / ~31m08s).

The 2 failures (`tests/test_place_biodiversity_summary_repository.py::
test_api_route_returns_the_summary`,
`::test_human_correction_updates_place_biodiversity_intelligence_
correctly`) are **independently confirmed pre-existing and unrelated, not
merely assumed** -- per this milestone's own explicit instruction not to
normalize a recurring failure without baseline reproduction: both files
this milestone touched (`candidate_quality_gate.py`, `product_
repository.py`) were `git stash`-isolated back to the exact starting HEAD
(`58c0634`), and the identical two tests were re-run in isolation --
**both fail identically on the clean starting HEAD**, with the exact same
assertion mismatches (`new_taxa`/`historical_status` -- Place Intelligence
biodiversity-taxonomy-history logic, zero code-dependency relationship to
Visit admission/evidence/quality-gate code). This is also the *same*
already-repeatedly-documented pair `docs/release-execution-state.md` §14
names as recurring across numerous prior milestones' own Core checkpoints
("`test_place_biodiversity_summary_repository.py` pair... each time
independently re-confirmed pre-existing and each time correctly judged
unrelated"). Zero new `ruff` findings on either touched production file
(confirmed via the same `git stash`-isolated baseline-vs-changed
comparison: 57 pre-existing findings in `product_repository.py`, identical
count and content before and after this milestone's change; `candidate_
quality_gate.py` and the new test file both clean).

## Explicitly out of scope, confirmed unchanged

Per this milestone's own instructions:

- **`blocked_missing_evidence`** (~9%, stable across v7-v9): untouched.
  This milestone's new check is evaluated *after* `blocked_missing_evidence`'s
  own check in `_create_candidate_visit_locked` (a proposal with no
  persistable evidence bytes returns before the quality gate is even
  called at all) -- structurally impossible for the new check to affect
  or be conflated with that residual. No investigation found a shared root
  cause; none was expected, and the instruction not to touch it absent one
  was followed.
- **`POST /api/review-labels` 500** (v9's own disclosed, bounded defect):
  untouched, exactly as instructed -- not exercised by, or relevant to,
  this milestone's own testing (which never posts a `review_origin=
  agent_diagnostic` label). Remains recorded for later sequencing at
  `representative-daylight-gate-a-field-acceptance-v9-report.md`'s own
  "Defects" section.

## Remaining risks

Disclosed honestly, not hidden, matching this project's own established
convention:

1. **The hardest, structurally-irreducible residual**: a genuine, real bird
   whose *entire* encounter -- across every constituent track generation
   combined -- produces no strong detection, no more genuine detector
   corroboration than the scaled bare-restart floor, and never two
   consecutive genuine detections anywhere, is *not* distinguishable from
   this milestone's own traced hard negatives by corroboration structure
   alone, and would also be rejected. This is the same fundamental limit
   v8's own report already demonstrated for confidence *magnitude*
   (Visits 006/016 vs. the false cluster) applied to corroboration
   *structure* instead: at the very bottom of what the tracker itself
   requires to exist at all, corroboration-structure alone cannot always
   separate a real animal from a false trigger without pixel content,
   which this milestone's own non-goals correctly forbid adding (no new
   background classifier, no BioCLIP-as-validity-detector). Every
   positive control this milestone constructed was deliberately built to
   reflect a *realistically present* subject (more than the absolute
   minimum on at least one axis) rather than the theoretical floor case --
   a defensible, but real, judgment call, not a proof this exact floor
   case never occurs in the field.
2. **Not yet field-validated at scale.** This fix is grounded in v8/v9's
   own real, traced field data (two known locations, reconstructed as
   faithful production-code-driven reproducers) plus this milestone's own
   constructed positive controls -- not a large, multi-session, non
   -location-concentrated reviewed corpus. `docs/detection-quality-
   accounting-contract.md`'s own "Production authority gate" names
   exactly this condition ("reviewed truth is large and representative
   enough... not concentrated in one or two sessions/scenes") as one of
   six required before *any* admission-policy change is treated as fully
   settled; this milestone's own governing instructions correctly forbid
   running a new field cohort to close that gap here (§34/§37: field
   validation belongs to the next, separately-authorized daylight
   session). This residual is expected, not a defect -- it is exactly what
   "Next field proof," below, exists to close.
3. **`_QUALIFYING_DETECTIONS_MARGIN` (1) and `_MINIMUM_CONSECUTIVE_
   DETECTOR_CONFIRMED_FRAMES` (1) are each one small, explicitly-justified
   number**, not re-derived from a pre-existing constant the way `_BARE_
   DETECTOR_CONFIRMATIONS_PER_GENERATION` (2) is. Both are tied directly to
   a real, traced field number (`candidate-026`'s own exact 3-detection
   signature; "never even 2 genuine detections in a row") rather than
   intuition -- but any reader should know these are the two numbers in
   this fix closest to a judgment call, and a future cohort with a
   genuinely different false/real corroboration distribution could show
   they need revisiting.

## Next field proof

Per this milestone's own explicit instruction, not self-authorized: the
next Representative Daylight Gate A cohort (separately authorized, not by
this report) must prove:

- the v8/v9 false-Visit rate (20-22.2%) materially reduced, ideally toward
  v5/v7's own 4-5.3% range;
- the useful-evidence rate recovers materially above v9's own 76.0%;
- genuine low-confidence bird recall preserved -- specifically, no new
  class of "real weak bird missed" complaint that did not exist in v5/v7/
  v8/v9's own independent reviews;
- no recurrence of either specific known hard-negative cluster (Location A
  foliage, Location B glint) as an *admitted* Visit -- a recurrence as a
  correctly-rejected, diagnostically-visible non-admission (via the new
  `reject_insufficient_detector_corroboration` reason) would be a genuine
  confirmation, not a failure;
- true RTT-normalized latency remains stable (this milestone changed
  nothing latency-relevant);
- fragmentation/duplicate rates remain at their own already-converged 0%;
- a stronger, more representative recall denominator than any single prior
  session;
- real two-/three-simultaneous-subject evidence where the field session
  happens to produce it;
- the Gate B hard-negative species-escalation class (a confident wrong
  label on a rejected-shaped background) absent, now structurally expected
  given "Species-escalation result," above.

## Decision

**A.**

Every item in this milestone's own acceptance bar (§36) is met with direct,
reproducible evidence: the v8/v9 hard-negative class reproduced
deterministically through real production code (not a labeled-background
fake unit test); the first irreversible erroneous decision proven, not
assumed (candidate authority ruled out by its own contract, tracker
confirmation ruled out as the wrong layer for a recall-preserving fix); a
generalized, field-grounded, non-scene-coordinate fix (proven by two
explicit adversarial tests); production MDv5 threshold unchanged at `0.1`
(verified at its actual deployment-config source, not merely asserted);
known false hard negatives -- including the harder, chaining-resistant
`candidate-027`-shaped pattern -- no longer become user-visible Visits;
six distinct matched genuine weak-bird controls continue to admit; normal
Visits unaffected; multi-subject isolation preserved and directly tested;
sustained-activity/fallback/stop behavior preserved (both by construction
-- the fix touches none of that code -- and by a dedicated positive
control); the one real, traced false hard negative that escalated to a
confident species label (`candidate-026`) cannot reach species inference
at all under the fix, confirmed directly, not inferred; Reviewed truth
preserved and directly tested; Tier 1 clean (16/16); Tier 2 clean (733
tests, 0 failures) across every named affected subsystem; Tier 3 clean
apart from the two independently baseline-proven unrelated failures
(5504 passed / 2 pre-existing-and-unrelated failed / 3 skipped / 23
deselected / 11 xfailed). The one honest, disclosed residual -- a
hypothetical real bird at the exact same corroboration floor as the
traced false cluster -- is a structurally-irreducible limit shared with
the confidence-magnitude question this project already settled the same
way (disclose, do not force a perfect rule), not a defect this milestone
left unaddressed.

**Ready for ChatGPT acceptance review.**
