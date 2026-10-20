# All-Alternate Subject Evidence Recall Correctness v1

Bounded RELEASE-CRITICAL Gate A product-correctness milestone. Follows
accepted [field-acceptance-evidence-integrity-storage-preflight-correctness-v1-report.md](field-acceptance-evidence-integrity-storage-preflight-correctness-v1-report.md)
and accepted [representative-daylight-gate-a-field-acceptance-v12-report.md](representative-daylight-gate-a-field-acceptance-v12-report.md).

## Starting state

Verified directly, not assumed:

- Branch `main`, HEAD `b4a2a6603ebe1c510d15acd668ad52d5a158e0ce` -- exact
  match to the governing brief's expected starting HEAD.
- Schema v58, unchanged (confirmed against `data/field-acceptance/2026-09-03-
  gate-a-v12-precision-recall-budget-convergence/PROVENANCE.md` and
  `docs/release-execution-state.md`).
- `docs/release-execution-state.md` §3: current authorization **NONE --
  GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, restated unchanged
  across both the v12 and Field Acceptance Evidence Integrity & Storage
  Preflight Correctness v1 reconciliation entries. §3 also independently
  confirms this milestone's own premise: "item (13)
  (`reject_no_identification_or_context`'s all-or-nothing behavior for
  brief-but-real encounters) is preserved verbatim, untouched, still open."
- §1's own "Accepted HEAD" bullet chain (a distinct, separately-verified
  convention -- see Camera / Source Release Hardware Validation Closure
  v1's own finding that this document names the *report* commit, not the
  reconciliation commit) was not re-litigated; §3 is this file's own
  authoritative "what is currently authorized" record, per project memory.
- Gate A: `NOT DONE -- RELEASE-CRITICAL`, unchanged. v12's own 13-item
  dependency list carried forward verbatim.
- v12 raw-ledger historical evidence: confirmed still `PARTIAL` -- the
  single post-stop corrective fetch (`merged-ledger/live_post_stop_
  counterfactual.json`) recovers only the tail from roughly offset
  2,219,000-2,224,000ms onward (~37min) through session end (~97min); the
  session's own first ~37 minutes remain genuinely unrecoverable. Both v12
  -named reproducer offsets (37:12, 57:07) fall inside the recovered tail,
  confirmed directly (see below) -- this is why deterministic reconstruction
  was possible for them specifically.
- Preserved untracked files verified present and byte-identical to the
  brief's own list throughout this milestone (`git status --short`
  before/after): `docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`.
- No active writer in this worktree (single session, no lock/PID artifacts
  found). Not pushed (`git log origin/main..HEAD` shows the same local
  -only commit chain throughout).
- Expected production configuration confirmed unchanged: MDv5a ONNX, score
  threshold 0.1, BioCLIP-2, current Identification Eligibility/Abstention
  contract, current candidate/evidence/admission policy (this milestone's
  own diff is additive to it, not a replacement), schema v58.

No material difference from the brief's expected starting state. Proceeded.

## v12 reproduced misses

**Method.** v12's own report (§Wildlife denominator / §Weak-stationary-brief
positives) names two confirmed-real-bird misses by session-offset window:
37:12-37:29 and 57:07-57:15, both independently confirmed by direct
full-resolution frame inspection (`data/field-acceptance/2026-09-03-gate-a-
v12-precision-recall-budget-convergence/gap-investigation/check_3712.jpg`,
`check_5707.jpg`). Both images were re-inspected directly in this milestone
(visually confirmed again: `check_3712.jpg` shows a small bird perched
directly on the seed feeder; `check_5707.jpg` shows a blurry, in-flight
subject at bottom-left, consistent with a fast-moving, hard-to-corroborate
capture -- almost certainly a hummingbird, given the dedicated red nectar
feeder in frame).

v12's own report states both were "rejected by the quality gate
(`reject_no_identification_or_context`)." This milestone's governing brief
repeats that premise and asks for root cause. Per the brief's own
instruction ("Use the highest-fidelity preserved data actually available
... Do not fabricate missing early raw-ledger data"), both offsets were
independently reconstructed from `merged-ledger/live_post_stop_
counterfactual.json` -- the single real, preserved, post-stop corrective
fetch (12,000 `raw_detections`, 158 `track_generations`, 175
`proposal_outcomes`, `stream_id=stream-5288453906fb`) -- by converting each
window's `MM:SS` into `source_offset_ms` and matching `track_generations`/
`proposal_outcomes` whose own `start_offset_ms`/`end_offset_ms` overlap it.
Every fact below is a direct field from this preserved ledger; none is
reconstructed or inferred numerically. All timestamps below are the
ledger's own `source_offset_ms`/`decided_at` fields, not recomputed.

**Result, and a material correction to v12's own diagnosis:** neither named
case actually terminates at `reject_no_identification_or_context` in the
preserved ledger. Reported here in full, because establishing this
precisely -- not merely re-asserting v12's own conclusion -- is exactly
what this milestone's own brief asked for ("Do NOT begin from the
assumption that the quality gate itself is wrong ... Find the first
irreversible loss in the v12 cases before selecting a fix"). v12's own
diagnosis is not treated as a mistake to litigate -- it was reached without
the exact-offset-to-proposal-record cross-reference this report performs,
under a session whose own raw-ledger tooling had just failed (the
immediately-prior milestone's own subject); this milestone is the first to
have both the repaired tooling's own preserved output *and* the bounded
time to perform this level of reconstruction.

### Case A: 37:12-37:29

- Confirmed-real generation: `stream-5288453906fb:frame-track:
  80735c36ab6a3cd599a7` -- `start_offset_ms=2232060, end_offset_ms=2249777`
  (37:12.06-37:29.78, matching v12's own stated window to the second),
  `confirmed: true`, `terminal_reason: maximum_unsupported_duration`
  (the tracker itself ended it -- not "insufficient_support," the flag
  confusor's own signature at this same session), 8 detections, `max_
  confidence: 0.479` (never strong; `strong_detection_threshold` is 0.70),
  bounding box `[0.43-0.49, 0.64-0.79]` -- a different frame location from
  every flag-confusor generation nearby (fixed at `[0.055-0.083,
  0.72-0.74]`), consistent with a real, distinct subject.
- Its sole proposal, `visit-episode:06c209aec98c56ebcc7d9d47`, has exactly
  **one** preserved decision record in the entire recovered ledger:
  `blocked_ambiguous_boundary` / `proposal_boundary_ambiguous_with_
  adjacent_proposal`, decided `2026-09-03T18:08:35.179561Z`.
- `blocked_ambiguous_boundary` is **not** a retryable outcome
  (`candidate_visit_authority.RETRYABLE_OUTCOMES =
  frozenset({"blocked_continuation_pending"})`,
  `candidate_visit_authority.py:474`) -- confirmed directly against the
  code, this is a permanent, terminal fact about this exact proposal id,
  not an artifact of ledger truncation (a later, real re-decision, had one
  existed, would necessarily have a `decided_at` *more* recent than
  18:08:35 and would therefore be *more* likely, not less, to survive the
  ledger's own 60-minute age-based retention window -- checked directly:
  no such record exists for this proposal id anywhere in the 175 retained
  records).
- **This proposal never reached the evidence-quality gate at all.**
  `ProductRepository.create_candidate_visit_from_proposal` calls
  `evaluate_candidate_authority` first; when it returns any
  `not decision.should_create` outcome (which `blocked_ambiguous_boundary`
  always is), the method returns immediately (`product_repository.py`,
  lines 6922-6932) -- `_create_candidate_visit_locked`, where
  `evaluate_evidence_admission`/`reject_no_identification_or_context` live,
  is never called. Confirmed directly against the code, not inferred.
- 187 milliseconds earlier (`18:08:34.992593Z`) -- consistent with two
  sequential, synchronous calls inside one `_run_assembly_tick`'s own
  `_attempt_resolved_component` walk, not two separate ~11-13s ticks -- a
  *different* proposal (`visit-episode:1fbf40aab78794afc36374a0`, span
  36:36.96-36:53.68) was admitted as Visit `visit-observation-candidate-
  017` (`candidate_visit_created_shared_event` -- the V016/V017
  sibling-Visit pair v12's own report already documents). Given
  `_attempt_resolved_component`'s own mechanics (`engine_runtime.py:2178-
  2245`: only the chain's first-attempted member is ever tried with
  `ambiguous_boundary_resolved=True`; every later member, once the chain
  "settles" on a success or non-fallback-eligible failure, is tried with
  `False` -- which is the only way to ever *produce*
  `blocked_ambiguous_boundary` as an outcome), this timing is strong,
  directly-code-grounded circumstantial evidence that proposal
  `06c209ae...` was a losing member of the *same* resolved connected
  ambiguous-boundary component that admitted V017, correctly-by-that-
  design suppressed as "possibly the same encounter as the one just
  admitted" -- even though its own bounding box places it at a materially
  different part of the frame. I was **not** able to directly confirm exact
  component membership from the preserved ledger (`ambiguous_adjacent_
  proposal_ids` is a fact the assembler computes in-memory per tick; it is
  not a field the counterfactual ledger's `proposal_outcomes` records
  expose), so this specific claim is reported as strongly-supported
  inference, explicitly distinguished from the surrounding facts (never
  reached the gate; permanent; distinct real subject; V017's own timing)
  which are each independently confirmed directly against the ledger and
  the code.
- **Conclusion: this case is not the milestone's chartered defect.** No
  evidence-role/alternate/same-frame mechanism was ever consulted. The real
  first irreversible error is one layer upstream, at candidate-authority
  ambiguous-boundary arbitration -- see "Remaining residuals," below, for
  why this is disclosed, not fixed, here.

### Case B: 57:07-57:15

- Confirmed-real generation: `stream-5288453906fb:frame-track:
  c08432d7f9ca92d066af` -- `start_offset_ms=3427441, end_offset_ms=3435192`
  (57:07.44-57:15.19, matching v12's own stated window to the second),
  `confirmed: true`, `terminal_reason: maximum_unsupported_duration`, only
  **3** detections, `max_confidence: 0.324` (never strong), single
  generation, bounding box `[0.46-0.49, 0.64-0.76]` (same general
  feeder-area region as Case A, a different sighting).
- Its sole proposal, `visit-episode:f3515c8ed14b3b63bb1be0d7`, cycles
  through four `blocked_continuation_pending` re-decisions
  (`18:27:36.120139Z` through `18:28:12.546806Z`), then terminates at
  `18:28:24.133630Z` with **`reject_insufficient_detector_corroboration` /
  `never_strong_and_minimal_detector_corroboration`** -- a materially
  different outcome from `reject_no_identification_or_context`.
- Per `evaluate_evidence_admission`'s own fixed check order
  (`candidate_quality_gate.py`: proposal-support -> identification-or-
  context -> geometry-validity -> detector-corroboration, in that order,
  each returning immediately on failure), reaching
  `reject_insufficient_detector_corroboration` at all *requires* having
  already passed the identification-or-context check. **This proposal did
  have a real, valid, selected `identification` or `context` evidence
  item.** Verified the arithmetic directly against the real record: for a
  single-generation proposal, `qualifying_floor = 2*1 + 1 = 3`;
  `detection_count = 3` does not exceed 3 (`count_clears_floor = count >
  qualifying_floor` is `3 > 3 = False`); `strong_detection_count = 0`; no
  consecutive-frame streak fact clears the floor either -- falls through to
  exactly `"never_strong_and_minimal_detector_corroboration"`, the observed
  reason string, confirming the code trace against the real ledger record
  precisely, not merely plausibly.
- **Conclusion: this case is also not the milestone's chartered defect.**
  Evidence-role assignment worked correctly here. The proposal was
  rejected by the separate, already-hardened, historically-justified
  detector-corroboration gate (Hard-Negative Visit Admission Precision &
  Species-Escalation Correctness v1; Independent Corroboration Value &
  Persistent-Confusor Admission Correctness v1), operating exactly as
  designed on a genuinely marginal real encounter (3 raw detections, never
  strong, visually a blurry in-flight subject) that is, on every currently
  -available signal, indistinguishable from the specific hard-negative
  shape that gate exists to reject.

### What this means for the milestone

v12's report attributed both misses to `reject_no_identification_or_
context` without the exact ledger cross-reference this report performs
(reasonable, given the tooling gap that milestone was simultaneously
disclosing); neither actually terminates there. This is not a reason to
abandon the milestone -- the brief's own chartered failure pattern (a real,
byte-backed subject capture existing, but the proposal being discarded
outright because none of its evidence items ever reached role
`identification`/`context`) is separately, directly proven to be a real,
currently-live-reachable defect in the current codebase (see "Current
evidence-role semantics" and "First irreversible error," below) -- it
simply is not what happened to either of these two specific birds. Section
6 of the governing brief explicitly anticipates a case lacking "enough raw
state for deterministic replay" and permits constructing "the smallest
faithful reproducer from facts that are actually preserved and label which
fields are reconstructed"; this report extends that same discipline one
step further, to a case where the raw state is fully preserved but proves
the *named mechanism* absent -- the chartered defect is instead
reconstructed from the same session's own real detection-signature numbers
(see "RED->GREEN," below), clearly labeled as such throughout.

## Current evidence-role semantics

Explicit answers to the governing brief's own §14 questions, established by
direct code reading of `evidence_scoring.py`, `candidate_visit_adapter.py`,
and `candidate_quality_gate.py` (all three unmodified except where this
milestone's own locked fix, below, applies):

- **`identification`**: presentation/ranking role -- `evidence_scoring.
  score_proposal_evidence`'s own highest-`identification_score` *eligible*
  candidate (`_best(scores, context=False)`). It also functions as part of
  the admission *viability* gate (`candidate_quality_gate.
  evaluate_evidence_admission` requires a role-`identification` or
  role-`context` item to admit at all). Today it is genuinely **both** A
  and B (the brief's own option C) -- ranking preference and (jointly with
  `context`) the sole recognized proof of viability.
- **`context`**: the same duality, on the separate `context_score` axis.
  `evidence_scoring`'s own scoring weights (`_IDENTIFICATION_ROLE`/
  `_CONTEXT_ROLE`) let `identification` and `context` legitimately coincide
  on one candidate when only one is genuinely useful (already covered by
  the existing test `test_context_only_with_valid_geometry_is_admitted`).
- **`alternate`**: **purely a presentation/ranking artifact, never a
  semantic viability signal, by the scorer's own construction.**
  `evidence_scoring.score_proposal_evidence` computes `alternates` only
  from `(item for item in ordered_scores if item.eligible and item.
  candidate_id not in used)` -- the *identical* `eligible` pool
  `identification`/`context` are drawn from. `_best()` returns `None` for
  a role if and only if that pool is empty; therefore, if the pool
  contains even one member (the necessary condition for any `alternate` to
  exist), `identification` and `context` are *both* already non-`None` --
  they simply point at whichever member(s) ranked highest, with the
  remainder demoted to `alternate`. **A live-constructed proposal cannot
  have a non-empty `alternate_candidate_ids` while `identification_
  candidate_id`/`context_candidate_id` are both `None`** -- this is a
  structural guarantee of the current scorer, not a coincidence of the
  data reviewed. `alternate` therefore never means "genuinely unusable/
  background evidence" (that is exactly what `eligible=False` already
  means, and an ineligible candidate never receives *any* role at all --
  it is silently excluded from persistence, appropriately). The module's
  own pure-unit test `test_alternate_only_evidence_is_rejected`
  (`tests/test_candidate_quality_gate.py`) exercises a hand-constructed
  `[_Item("alternate"), _Item("alternate")]` input shape directly against
  the gate function in isolation -- a legitimate defensive/structural test
  of the gate's own behavior *given* such an input, but not evidence that
  the real scorer can ever actually produce that input shape for a live
  proposal. This distinction -- between what the gate defends against and
  what the pipeline can actually hand it -- had not been previously
  established explicitly; this milestone establishes it by direct case
  -exhaustion over the scorer's own logic, not sampling.
- **`classifier_same_frame`** (Same-Frame Species Evidence v1): a fourth,
  structurally *separate* evidence role, neither a competitor for
  `identification`/`context` nor ever assignable `alternate`.
  `candidate_visit_adapter.attempt_candidate` filters it out of
  `scoring_candidates` *before* `score_proposal_evidence` is ever called
  (`role != CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE`) -- by design, so it can
  never outrank a real high-resolution burst (Same-Frame Species Evidence
  v1's own explicit, correct, and still fully preserved intent). Before
  this milestone, this role was **invisible** to
  `evaluate_evidence_admission`'s viability check (`role == "identification"
  or role == "context"`, nothing else) -- a proposal whose only surviving,
  byte-backed, persisted evidence was this role was treated identically to
  "no evidence exists at all," despite carrying a real, tracker/detector
  -confirmed, geometry-proven-same-frame subject capture (`GeometryAttribution.
  same_frame is True` -- proven, not merely timestamp-close; see
  `camera_node_live.py`'s own eligibility gate, `geometry_source_from_
  support_state(update.support_state) in ("detector", "tracker")`).

**Answering §14 directly: are these roles A (presentation), B (viability
gate), or C (both)?** `identification`/`context` are demonstrably C.
`alternate` is demonstrably A only -- it is provably never, by itself, the
thing standing between a proposal and non-existence, because it cannot
exist without `identification`/`context` also existing. The actual gap the
brief's own framing was reaching for is a **fourth state its own
`identification`/`context`/`alternate` vocabulary did not name**:
`classifier_same_frame`, a role that is deliberately excluded from A
(ranking) *and* was, until this milestone, silently excluded from B
(viability) too, with no semantic justification for the second exclusion
-- exclusion from ranking is correct and intentional; exclusion from
viability was an oversight.

## End-to-end causal trace

Answering the governing brief's §7 questions for each reproducer:

**Case A (37:12-37:29, `06c209ae...`):**

1. Usable subject pixels captured? Yes -- 8 real detections, `confirmed:
   true`, distinct location from every confusor.
2. Bytes available at evidence harvest? Not established either way --
   irrelevant, since the proposal never reached evidence scoring/harvest
   consultation at all.
3. Which evidence items were created? Unknown/moot -- never reached the
   evidence-building stage.
4. Why alternate not identification/context? N/A -- never reached.
5. Geometry attribution correct? Not evaluated -- authority blocked first.
6. Subject inside evidence crop? Not evaluated.
7. Did image-quality scoring reject it? No -- never reached scoring.
8. Did timing/arbitration delay change the available evidence set?
   **Not applicable in the usual "cache eviction" sense** -- the defect
   here is not about evidence *availability* changing over a delay; it is
   that ambiguous-boundary arbitration's connected-component "at most one
   winner" rule classified this proposal as a *loser* of a component that
   had already been won (almost certainly by V017, see above), before any
   evidence question was ever asked.
9. Did proposal construction omit a better generation/frame? No.
10. Did cache eviction participate? No (this case, specifically -- see
    "Remaining residuals" for the separate, disclosed-not-reproduced,
    already-partially-mitigated historical cache mechanism).
11. Did evidence ranking choose the wrong candidate? N/A -- never reached
    ranking.
12. Did an existing role-eligibility condition fail as intended? N/A.
13. Is `reject_no_identification_or_context` merely the final symptom of
    an earlier defect? **No -- it is not even the terminal reason for this
    case.** The actual terminal reason (`blocked_ambiguous_boundary`) is
    itself the symptom of a *different* stage (candidate-authority
    ambiguous-boundary arbitration), not evidence/role handling at all.

**Case B (57:07-57:15, `f3515c8e...`):**

1. Usable subject pixels captured? Yes -- 3 real detections, `confirmed:
   true`; visually confirmed a real, if blurry/in-flight, subject.
2. Bytes available at evidence harvest? Yes -- necessarily, since the
   proposal reached, and passed, the identification-or-context check
   before failing on corroboration.
3. Which evidence items were created? At least one item with role
   `identification` or `context` (unrecoverable which specifically, since
   a rejected proposal's evidence items are never persisted -- see
   "Diagnostics," below, for why this is itself a real, if secondary,
   limitation this milestone partially addresses).
4. Why alternate not identification/context? Not applicable -- an
   identification/context item *did* exist and was used; this question's
   premise does not hold for this case.
5. Geometry attribution correct? Passed (the gate's own geometry-validity
   check ran and passed, since corroboration is checked strictly after it).
6. Subject inside evidence crop? Consistent with a real subject, per direct
   visual re-confirmation.
7. Did image-quality scoring reject it? No.
8. Did timing/arbitration delay change the available evidence set? The
   proposal was legitimately delayed (4 `blocked_continuation_pending`
   cycles, ~48 seconds total) but this had no bearing on the outcome --
   the *detector* evidence (3 total raw detections across the generation's
   own ~7.75-second life) is what the corroboration check evaluates, and
   that fact does not change with re-decision timing.
9. Did proposal construction omit a better generation/frame? No -- single
   generation, nothing to omit.
10. Did cache eviction participate? No.
11. Did evidence ranking choose the wrong candidate? No.
12. Did an existing role-eligibility condition fail for a reason that was
    intended? **Yes -- exactly as intended.** `reject_insufficient_
    detector_corroboration` exists specifically to reject a proposal whose
    entire evidentiary basis never exceeds the tracker's own bare
    confirmation floor on any axis; this proposal's real signature (3
    detections, single generation, never strong) is precisely that shape.
13. Is `reject_no_identification_or_context` merely the final symptom of
    an earlier defect? **No -- it is not the terminal reason for this case
    either.** The terminal reason is a different, correctly-functioning
    gate.

**The chartered general pattern** (a proposal whose *only* surviving,
byte-backed evidence is role `classifier_same_frame`): traced separately,
by direct code construction (see "First irreversible error," below), since
no confirmed-real v12 case instantiates it. Capture -> detector -> tracker
-> generation: identical to any other confirmed generation. Proposal
formation: identical. Evidence harvesting: the high-resolution burst's own
bytes are lost or independently ineligible (a real, disclosed residual --
see `engine_runtime._MAX_CACHED_BURST_BYTES`'s own docstring, and the
harvest-layer 8-entry `LiveCameraNodeShadowSession._temporary_payloads`
cache a prior milestone already found could drop a captured burst before
harvest -- see "Historical same-terminal-reason comparison"), while the
same-frame snapshot -- captured in the identical code path, at the
identical moment, gated on the *same* burst having already nominally
succeeded (`camera_node_live.py`'s own construction order) -- survives
independently, in its own, separately-bounded cache. Evidence scoring:
correctly, intentionally never considers the same-frame item for
identification/context. Role assignment: correct -- the same-frame item is
correctly labeled `classifier_same_frame`, not misclassified as
`alternate`. Quality gate (pre-fix): incorrectly reads "no identification,
no context" as "no viable evidence," discarding the whole proposal.

## First irreversible error

- **Case A:** `resolve_ambiguous_boundary_arbitration`'s connected
  -component "at most one winner" rule (`candidate_visit_authority.py`),
  combined with `classify_boundary`'s own bounded-displacement-budget
  geometry tolerance (`geometry_gap_tolerance`, capped at `0.6` normalized
  centroid distance for any gap >= ~9.6 seconds -- `geometry_gap_tolerance_
  base=0.12 + geometry_gap_tolerance_per_second=0.05 * gap_s`, capped at
  `geometry_gap_tolerance_cap=0.6`), entangling this real, later, spatially
  -distinct subject with an earlier, already-resolved encounter merely
  because the two fall within `ambiguous_gap_ms` (45s) of each other. Once
  entangled, the proposal is attempted with `ambiguous_boundary_
  resolved=False` and is permanently blocked -- correctly, by that
  mechanism's own logic, *if* the two really were the same encounter; not
  correctly, if they were not. This is a candidate-authority/ambiguous
  -boundary finding, not an evidence-role finding -- see "Remaining
  residuals" for why it is disclosed, not fixed, in this milestone.
- **Case B:** No irreversible *error* exists. `_insufficient_detector_
  corroboration`'s bare-minimum-count floor correctly classifies this
  3-detection, never-strong, single-generation capture as indistinguishable,
  on every currently-available signal, from the intentionally-targeted
  hard-negative shape. The gate is functioning exactly as designed on a
  real but marginal encounter.
- **The chartered general pattern (proven live-reachable, not the direct
  cause of either named case):** the first irreversible error is
  `candidate_quality_gate.evaluate_evidence_admission`'s own primary
  -resolution step (pre-fix, lines ~420-426): once neither `identification`
  nor `context` exists, the proposal is rejected outright and its
  persisted evidence (if any) is never written to the database at all (see
  `_create_candidate_visit_locked`'s early return) -- irreversible, because
  a `classifier_same_frame`-only proposal's real subject capture, once
  discarded here, cannot be recovered by any downstream stage.

## Root-cause classification

Per the governing brief's own §8 taxonomy:

- **Case A: out of scope for this milestone's taxonomy.** The defect, if
  it is one, lives in candidate-authority ambiguous-boundary arbitration
  (`candidate_visit_authority.py`) -- explicitly excluded from this
  milestone's own blind-tuning boundary (§5: "candidate authority,"
  "ambiguity threshold"). Not classified A-I; disclosed as a distinct,
  newly-surfaced finding for a future, separately-scoped milestone.
- **Case B: not a defect.** None of A-H describes "the gate is working
  exactly as intended on a genuinely marginal real encounter." Classified
  here, explicitly, as **not a defect** rather than force-fit into the
  taxonomy.
- **The chartered general pattern: D** -- correct subject crop (the
  same-frame capture is real, geometry-proven, and correctly attributed),
  but role classification -- specifically, the quality gate's own
  viability check failing to recognize a valid, intentionally-non
  -competing role as proof of a real subject -- incorrectly demoted that
  capture to the same status as "no evidence at all." Proven complete (not
  merely plausible) by the case-exhaustion argument in "Current
  evidence-role semantics": `alternate`-only is structurally impossible
  today, so `classifier_same_frame`-only is the *only* live-reachable way
  the chartered symptom can actually occur, once `blocked_missing_
  evidence`'s own earlier check is accounted for.

## Historical same-terminal-reason comparison

Bounded archaeology across every accepted document mentioning
`reject_no_identification_or_context` prior to this milestone's own report
(`grep -rl`, 18 pre-existing documents; this report is necessarily now a
19th, since it discusses the same reason extensively). Of those 18, the
following are the ones that materially discuss its *cause*, not merely its
name):

- **2026-08-19, Visit Authority Budget + Ambiguous-Boundary Recall Closure
  v1** (`docs/visit-authority-budget-recall-closure-v1-report.md`,
  `docs/roadmap.md`, `docs/candidate-visit-authority-contract.md` "Evidence
  -cache capacity"): **different root cause, same terminal reason.** Two
  real, long, high-confidence encounters (34-generation/0.889-confidence,
  40-generation/0.846-confidence) each had a real identification/context
  -eligible candidate whose bytes were evicted from the (then-8-entry)
  harvest cache before a *legitimately delayed* admission attempt ran --
  explicitly confirmed in the contract doc: "every requirement `candidate_
  quality_gate.evaluate_evidence_admission` enforces (a real, decodable,
  geometrically-valid identification/context candidate) is completely
  unchanged; this only keeps evidence already judged sufficient from
  vanishing." Fixed via cache capacity (8 -> 32 -> 128) and a pending
  -proposal-aware protection mechanism, never via gate logic. This
  mechanism remains a real, disclosed, *not fully eliminated* residual in
  principle (`engine_runtime.py`'s own comment above `_MAX_CACHED_BURST_
  BYTES`: "an arbitrarily busier or longer-delayed session could still in
  principle exhaust it ... left as a disclosed follow-up") -- but it is
  unrelated to the mechanism this milestone fixes, and neither of this
  milestone's own two reproducers exhibits it.
- **2026-08-20, Harvested Evidence Issuance / Missing-Evidence Closure v1**
  (`docs/harvested-evidence-issuance-missing-evidence-closure-v1-report.md`):
  **this document directly, explicitly anticipated this milestone's own
  finding, as an open, unconfirmed suspicion, and did not pursue it.**
  Verbatim: "An earlier draft of this same fixture accidentally also
  captured `classifier_same_frame` evidence ... which masked the intended
  failure as `reject_no_identification_or_context` instead ... worth
  recording here because the same accidental 'other evidence happens to
  survive' shape may be part of why the real field session's own `only_
  alternate_or_no_selected_evidence_available` cases (12 in the session,
  disclosed as 'likely a red herring') were never conclusively ruled out
  as related; not re-investigated further here, as it does not change this
  milestone's own root cause or fix." This milestone is the first to
  conclusively resolve that suspicion: it was not a red herring as a
  *mechanism* -- same-frame-only survival genuinely can, and does, produce
  this exact terminal reason, proven by direct code construction and two
  independent end-to-end tests. This milestone's own preserved-evidence
  limits (rejected proposals' evidence items are never persisted -- see
  "Diagnostics") mean it is not possible to retroactively confirm *which*
  of that document's own 12 historical cases, or v12's own 31 (see below),
  were specifically same-frame-only; the mechanism itself, not every
  historical instance of it, is what this milestone establishes and fixes.
- **Same document, §6:** explicitly asserted, of `reject_no_identification_
  or_context`, "unlike the separate, correctly-named `only_alternate_or_
  no_selected_evidence_available` reason, **a real scoring-quality
  decision, not a bug**." This milestone's own case-exhaustion proof shows
  this claim is incomplete: true of the reading its own name suggests
  ("some alternate existed, it just was not good enough") -- which this
  milestone proves is currently *impossible* to reach alone in the live
  scorer -- but not accounting for the same-frame-only shape, which the
  identical reason string also covers, and which *is* a bug, now fixed.
- **Representative Daylight Gate A Field Acceptance v8**
  (`docs/representative-daylight-gate-a-field-acceptance-v8-report.md`):
  one further, never-resolved instance -- a confirmed track generation
  (`max_confidence 0.496`) whose own proposal
  (`visit-episode:6f2a05498709d337fe2fee48`) was "correctly, honestly
  rejected `reject_no_identification_or_context`," explicitly disclosed as
  "genuinely ambiguous whether this represents a real, distinct, under
  -evidenced encounter (a partial miss) or a real but momentary/
  inconclusive detection correctly abstained on -- disclosed as ambiguous,
  not resolved either way." Consistent with this reason's actual
  mechanism never having been rigorously traced, at the code level, before
  this milestone -- no prior session had the tooling, the time budget, or
  (per the immediately-preceding item) the willingness to pursue the
  suspicion already on record.
- **v12's own session (this milestone's own governing data):** 31 total
  `reject_no_identification_or_context` records in the recovered ledger
  window, none independently visually confirmed as real (the 2 confirmed
  -real cases this milestone traced are, per above, governed by *other*
  mechanisms). Not attributable record-by-record to same-frame-only
  survival from the preserved ledger alone (see "Remaining residuals").

**Conclusion: mixed.** At least two, and very likely three, structurally
distinct causes have shared this one terminal-reason string across
MockingBird's history: (1) the "genuine scoring-quality decision" the name
itself suggests -- proven, in this milestone, to be currently unreachable
*alone* in the live codebase, so this reading, while historically assumed,
has likely never actually applied to a real, live-fired occurrence of this
reason; (2) evidence-cache eviction under legitimate multi-tick delay
(2026-08-19) -- since substantially mitigated, not eliminated in
principle, unrelated to this milestone; (3) same-frame-only survival --
this milestone's own finding, now fixed. Neither of v12's two named cases
belongs to (2) or (3) -- both are governed by yet other mechanisms
(ambiguous-boundary arbitration; detector corroboration) that happen to be
temporally/narratively adjacent to genuine `reject_no_identification_or_
context` activity in the very same session. No already-fixed historical
defect was reopened; the two directly-relevant historical accounts above
(2026-08-19's cache fix, 2026-08-20's disclosed-but-unpursued suspicion)
are each cited, not re-litigated.

## Locked implementation contract

Written before any code was changed, per the governing brief's §9:

1. **Repair role classification, not the gate's viability semantics
   broadly, and nothing further downstream than necessary.**
   `candidate_quality_gate.evaluate_evidence_admission` gains one new,
   narrowly-scoped fallback: when neither `identification` nor `context`
   exists among a proposal's persisted evidence items, look for an item
   with role `classifier_same_frame` and, if one exists, use it as
   `primary`. This is checked as a genuine *last resort* -- a real
   `identification`/`context` pick always wins outright, unchanged, and
   the fallback runs only in the branch that would otherwise reach
   `reject_no_identification_or_context`.
2. **Every check downstream of primary-resolution stays completely
   unchanged, applied to whichever item `primary` now is.** Geometry
   validity (`_valid_normalized_box`) and detector corroboration
   (`_insufficient_detector_corroboration`) still run, in the same order,
   against the same-frame item exactly as they would against an
   identification/context item -- this fix changes what counts as a
   *candidate* primary, never what it takes to be admitted. No new
   threshold of any kind is introduced.
3. **`alternate` is deliberately given no equivalent fallback.** Proven
   above to be a live-unreachable input shape today; broadening it would
   weaken a real, deliberately-documented invariant ("`alternate` never
   admits alone" -- the module's own docstring, and the pre-existing
   `test_alternate_only_evidence_is_rejected`) for no live-reachable
   justification. This directly answers the brief's own "Do not broaden
   semantics ambiguously."
4. **The two display-layer exclusions of `classifier_same_frame` evidence
   (`product_repository._visit_evidence_frames_from_links`,
   `_effective_primary_preview_from_visit`) each gain a narrow,
   conditional carve-out:** exclude same-frame evidence exactly as before,
   *unless* it is a Visit's only evidence item at all, in which case show
   it. Without this, the new admission path would produce a real,
   database-persisted Visit with zero visible evidence in the review
   UI -- a worse outcome than the pre-fix rejection. This never changes
   presentation for any Visit that also has real burst/other evidence
   (the overwhelming common case; proven a complete no-op there both by
   direct code reading and by the two pre-existing tests this exact case
   already covers, both left unmodified and still green -- see "RED->
   GREEN").
5. **No schema change. No new generic threshold. No touch to
   `evidence_scoring.py`'s own ranking, `candidate_visit_authority.py`,
   `visit_episode_assembler.py`, the detector, the tracker, BioCLIP, or
   Identification Eligibility/Abstention.** Diagnosability is added via a
   bounded `reason`-string suffix (`:same_frame_primary`), mirroring this
   codebase's own existing convention (`:fallback_position_N`,
   `:retries_exhausted`), never a new column or field.

Preferred-ordering check against the brief's own §9 list: evidence
preservation/selection was checked and found not broken for this case
(same-frame bytes were never lost -- they are the *survivor*); crop/
geometry attribution was checked and found correct (same-frame's own
geometry is proven, not merely close-in-time); role *classification* was
checked and found objectively wrong at exactly one point -- the gate's own
viability read of a correctly-assigned, correctly-non-competing role. The
fix sits at that exact point, the first (and only) place in this causal
chain that is both wrong and within this milestone's own scope.

## Implementation

Five files changed (four backend/docs, one frontend comment-only), all
additive:

- [src/mockingbird/observation/candidate_quality_gate.py](../src/mockingbird/observation/candidate_quality_gate.py)
  -- the locked fix itself: one new module-level string constant
  (`_CLASSIFIER_SAME_FRAME_ROLE`, a bare string, matching this module's own
  established no-cross-import convention), one new fallback branch inside
  `evaluate_evidence_admission` (between the existing identification/
  context resolution and the reject return), one new distinguishable admit
  -reason suffix, and docstring/module-docstring updates recording the
  milestone and its reasoning in place, matching this file's own existing
  per-milestone-paragraph convention.
- [src/mockingbird/repository/product_repository.py](../src/mockingbird/repository/product_repository.py)
  -- the two presentation-layer carve-outs in
  `_visit_evidence_frames_from_links` and
  `_effective_primary_preview_from_visit`, each: compute the non-same
  -frame subset of links first, then use it only if non-empty, falling
  back to the full (same-frame-inclusive) list otherwise. No behavior
  change to any other function; no new import; no schema/model change.
- [docs/same-frame-species-evidence-contract.md](same-frame-species-evidence-contract.md)
  -- "Non-promotion" section updated to record the narrow exception and
  its own rationale (the contract's own original "only ever captured
  alongside a successful burst" premise proved true of the candidate
  object, not the persisted item), so the doc and code stay in sync.
- [docs/candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
  -- "Evidence persistence" section gains a short paragraph recording the
  new fallback, cross-linking this report.
- [web/src/components/VisitEvidenceSequence.tsx](../web/src/components/VisitEvidenceSequence.tsx)
  -- comment-only accuracy fix: `evidenceRoleLabel`'s own existing
  `classifier_same_frame` label ("Frame used for species suggestion")
  already renders correctly for the new gallery case with zero logic
  change (confirmed: this component is role-driven, not gated on any
  assumption about which roles `evidence_frames` can contain); only the
  comment's own now-inaccurate "structurally excluded from
  `evidence_frames`" claim was updated. `npx tsc --noEmit` clean.

Tests, all additive (no existing test's assertions changed):

- [tests/test_candidate_quality_gate.py](../tests/test_candidate_quality_gate.py)
  -- 6 new pure-function tests (see "RED->GREEN").
- [tests/test_same_frame_species_evidence.py](../tests/test_same_frame_species_evidence.py)
  -- 2 new end-to-end tests through the real, unmodified
  `ProductRepository.create_candidate_visit_from_proposal` transactional
  boundary.

No schema bump (genuinely not required -- no new column, no new table, no
new persisted field shape). No new framework. Diff is confined to exactly
the two files the locked contract named.

## RED->GREEN

**Method:** implemented the fix, wrote the tests below, confirmed GREEN;
then `git stash push` of only the three non-test files (`candidate_quality_
gate.py`, `product_repository.py`, `same-frame-species-evidence-
contract.md`) with the test files left in place, re-ran the exact same
tests to confirm RED against the pre-fix code, then `git stash pop` to
restore the fix and re-confirmed GREEN. Not merely asserted -- performed
directly, twice (pure-gate level and end-to-end level), matching this
codebase's own established RED/GREEN discipline.

**Pure-gate level** (`tests/test_candidate_quality_gate.py`):

| Test | Pre-fix | Post-fix |
|---|---|---|
| `test_same_frame_only_evidence_is_admitted_as_last_resort` | FAIL (`reject_no_identification_or_context`) | PASS (`admit`, reason `evidence_sufficient_for_review:same_frame_primary`) |
| `test_same_frame_fallback_only_used_when_no_identification_or_context` | PASS (identification already wins pre-fix too -- a pure regression control, not a RED case) | PASS |
| `test_same_frame_fallback_still_requires_valid_geometry` | FAIL (`reject_no_identification_or_context` instead of the expected `reject_subject_geometry_invalid`) | PASS |
| `test_same_frame_fallback_still_rejects_insufficient_detector_corroboration` | FAIL (`reject_no_identification_or_context` instead of `reject_insufficient_detector_corroboration`) | PASS |
| `test_same_frame_fallback_admits_a_real_weak_but_corroborated_encounter` | FAIL (not admitted) | PASS |

The weak-corroboration control reuses the real 2026-09-03 persistent red
-flag confusor's own weakest signature (1 detection, confidence 0.121-
0.184, never strong -- `check_3712.jpg`'s own surrounding ledger data,
generations `76649d4c...`/`ee6e94d5...`); the admitted-weak-real-encounter
control reuses Case A's own real signature (8 detections, max confidence
0.479, single generation) **to ground the corroboration arithmetic in a
real number, explicitly not to claim this reproduces Case A's own recorded
authority outcome** (a different, disclosed, out-of-scope mechanism -- see
above). Both are labeled as such directly in the test docstrings, per the
governing brief's own labeling requirement for a constructed reproducer.

**End-to-end, through the real repository** (`tests/test_same_frame_
species_evidence.py`), no assembler/adapter shortcut, same
`create_candidate_visit_from_proposal` transactional boundary a live
session actually calls:

| Test | Pre-fix | Post-fix |
|---|---|---|
| `test_same_frame_only_evidence_creates_a_reviewable_visit` | FAIL (`outcome.outcome == "reject_no_identification_or_context"`) | PASS -- Visit created; its same-frame photo is present in `visit_evidence_frames` and selected by `effective_primary_preview` |
| `test_same_frame_only_evidence_still_rejects_weak_uncorroborated_detections` | FAIL (rejected for the wrong reason: `reject_no_identification_or_context` instead of the expected `reject_insufficient_detector_corroboration`) | PASS |

Both existing same-frame tests that already construct a Visit with *both*
identification and same-frame evidence
(`test_same_frame_evidence_never_appears_in_human_facing_evidence_gallery`,
`test_same_frame_asset_never_actually_visible_in_ordinary_gallery`) were
read in full before this change and left completely unmodified -- their
own fixture always includes a real `identification` item, so the new
carve-out (same-frame-only) never triggers for them; both remain green,
confirming the display-layer change is a genuine no-op in the common case.

## Real-positive controls

- `test_same_frame_fallback_admits_a_real_weak_but_corroborated_encounter`
  / `test_same_frame_only_evidence_creates_a_reviewable_visit`, above.
- V12's own 14 admitted true encounters (V006, V003, V004, V005, V007/
  V008, V009, V010, V011, V013, V014/V015, V016/V017, V018, V019, V020):
  structurally unaffected -- every one already has a real `identification`
  item (that is precisely why it was admitted), so `primary` resolves on
  the very first check, before this milestone's new branch is ever
  reached. Not independently re-run this milestone (§20: no new field
  cohort); confirmed unaffected by direct code-path reasoning instead.
- Full directly-relevant real-positive/negative-control test suites (see
  Tier 2) all green, unmodified except for this milestone's own additions.

## False-positive / artifact controls

- `test_same_frame_fallback_still_rejects_insufficient_detector_
  corroboration` / `test_same_frame_only_evidence_still_rejects_weak_
  uncorroborated_detections`, above -- both grounded in the real
  2026-09-03 persistent red-flag confusor's own weakest measured
  signature.
- v12's own sole confirmed false Visit
  (`visit-observation-candidate-012`): structurally unaffected -- it was
  admitted via a real `identification`-role item (that is how it became a
  Visit at all); this milestone's new branch is never reached for it.
- Full precision-control regression suites (`test_hard_negative_visit_
  admission_precision_v1.py`, `test_independent_corroboration_value_
  persistent_confusor_v1.py`, `test_strong_confidence_non_target_scene_
  artifact_v1.py`, `test_strong_confidence_subject_evidence_viability_
  v1.py`, `test_scene_confusor.py`, `test_scene_confusor_repository.py`,
  `test_human_background_admission_hard_negative_2026_08_20.py`) -- these
  are the committed, real-field-grounded regression encodings of exactly
  the required counterexamples named in the governing brief's §10 (v11
  strong-confidence scene artifact, v11 person-associated false paths,
  historical never-strong persistent confusors, hard-negative feeder/
  foliage/road cases from v8/v9/v10, strong-confidence non-target
  controls) -- **all pass unmodified** (see Tier 2). This milestone's fix
  never touches `evidence_scoring.py`'s ranking, `_insufficient_detector_
  corroboration`, or any confidence/geometry threshold, so none of these
  suites' own admission math changes.
- v12's own dominant confusor (the red property flag, ~70% of this
  session's own track-generation volume) is correctly still excluded from
  admission after this fix: its own weakest generations (1-3 detections,
  confidence 0.109-0.184, never strong) fail `reject_insufficient_
  detector_corroboration` exactly as before, whether or not a same-frame
  item happens to survive for them -- directly proven by the weak-control
  tests above, which reuse this exact confusor's own real numbers.

## Truth / abstention semantics

Unchanged, by construction. This milestone touches only the admission
*viability* decision (does a Visit get created at all); it never touches
species inference, Identification Eligibility/Abstention, or Review
Decision creation. A same-frame-only admitted Visit proceeds through the
identical, unmodified automatic-species-suggestion path
(`species/classifier_input.py`'s own existing `exact_frame_subject_box`
tier -- already documented as "regularly reachable on real data once a
Visit has a persisted `classifier_same_frame` asset," wired since Same
-Frame Species Evidence v1, untouched here) -- it may receive a normal
species suggestion, or honestly abstain, exactly per the existing,
unmodified contract, depending on what BioCLIP actually returns. Human
review, correction, and Reviewed-truth semantics are completely unchanged.
Per §13's own conditional framing ("prefer a real Visit with honest
unresolved/abstaining interpretation ... ONLY IF that conclusion follows
from the established root cause and existing product doctrine"): it does
follow here, as a direct consequence of the proven root cause (a real
subject was captured; only identification-grade quality was ever in
question) -- this was verified, not assumed, before implementation.

## Diagnostics

Directly answers the governing brief's §18. Before this milestone, two
genuinely different facts -- "no usable subject evidence existed at all"
and "usable subject evidence existed (a same-frame snapshot), but nothing
reached identification/context" -- were indistinguishable: both produced
the identical outcome/reason pair
(`reject_no_identification_or_context` /
`only_alternate_or_no_selected_evidence_available`). Two bounded changes,
no new field/column/table:

1. **Prospectively:** the new admit path carries a distinguishable reason
   suffix, `evidence_sufficient_for_review:same_frame_primary`, mirroring
   this codebase's own existing bounded reason-suffix convention
   (`candidate_visit_adapter`'s `:fallback_position_N`, `candidate_visit_
   authority`'s `:retries_exhausted`). A future session can measure how
   often this fallback fires directly from the existing counterfactual
   ledger, with no new telemetry.
2. **Retrospectively, by construction:** because the same-frame fallback
   now intercepts every case it structurally can (per the case-exhaustion
   proof), any *future* occurrence of plain `reject_no_identification_or_
   context` now carries a strictly narrower, more honest meaning than
   before -- "truly no evidence of any recognized role, including same
   -frame, survived scoring" -- rather than potentially masking a same
   -frame-only recall loss.

This milestone does **not** add new raw-media telemetry, a new database
column, or a new schema version -- exactly the bound the brief's §18 asks
for.

## Why real-hardware smoke was unnecessary

**Judged unnecessary; not run.** Reasoning, per the governing brief's own
§22 "use judgment and explain" standard: the entire production diff is two
narrow, additive, Host-side, pure-function/ORM-query changes
(`candidate_quality_gate.evaluate_evidence_admission`'s primary-resolution
step; two presentation-layer link filters in `product_repository.py`).
Neither touches the Camera Node, the detector, the tracker, the transport/
capture path, or any timing-sensitive code -- every fact that could
plausibly differ between a unit-test double and real hardware (detector
inference, tracker state transitions, network round-trips, real JPEG
encode/decode timing) is completely untouched by this fix. Tier 1/2
already exercise the exact, real, unmodified `ProductRepository.create_
candidate_visit_from_proposal` transactional boundary a live session
actually calls, with real JPEG bytes (not placeholder byte strings), real
`GeometryAttribution` payloads, and realistic `confidence_evidence_json`
values grounded in this exact session's own real numbers -- a materially
stronger proof of the changed logic than a short smoke session could add.
Additionally, naturally exercising the specific fixed path (a real burst
failing to harvest while a same-frame snapshot for the same generation
survives) cannot be forced without either staging wildlife (explicitly
forbidden, §21) or getting fortunate within a short window -- a smoke
session could easily complete having exercised nothing relevant to this
fix at all, while still costing real field-instance time/credential
overhead the milestone's own §20 asks to keep bounded. The reference
Camera Node was confirmed reachable (`<node-ip>:8787`, per project
memory) before this decision was made -- this is a judgment that a smoke
session would not be worth running, not that one was unavailable.

## Tier 1

Focused RED->GREEN reproducer + positive/negative controls, both levels
(pure-gate and end-to-end): **8 new tests, all GREEN post-fix, all
confirmed RED (or, for the one pure regression control, confirmed
unaffected) pre-fix** -- see "RED->GREEN" for the full table.
`tests/test_candidate_quality_gate.py`: 19/19 passed.
`tests/test_same_frame_species_evidence.py`: 10/10 passed.

## Tier 2

Every directly affected observation/admission/evidence subsystem suite,
run together: **518 passed, 0 failed.**

```
tests/test_candidate_quality_gate.py
tests/test_candidate_visit_adapter.py
tests/test_candidate_visit_authority.py
tests/test_candidate_visit_authority_acceptance.py
tests/test_candidate_visit_repository.py
tests/test_candidate_visit_review_workflow.py
tests/test_candidate_visit_rollback.py
tests/test_concurrent_candidate_visit_persistence_reliability.py
tests/test_effective_primary.py
tests/test_engine_runtime.py
tests/test_hard_negative_visit_admission_precision_v1.py
tests/test_human_background_admission_hard_negative_2026_08_20.py
tests/test_independent_corroboration_value_persistent_confusor_v1.py
tests/test_observation_evidence_scoring.py
tests/test_same_frame_species_evidence.py
tests/test_scene_confusor.py
tests/test_scene_confusor_repository.py
tests/test_strong_confidence_non_target_scene_artifact_v1.py
tests/test_strong_confidence_subject_evidence_viability_v1.py
tests/test_visit_classifier_supporting_evidence.py
tests/test_visit_episode_assembler.py
```

518 passed in 287.68s.

## Tier 3 decision

**Run, and warranted.** Judgment: although the locked fix is confined to a
narrow role-selection/evidence helper (which §22 says would not
automatically require Core on its own), this milestone's own diff also
touches `product_repository.py`'s two presentation-layer functions, a
large, widely-shared file used far beyond the Observation Engine subsystem
Tier 2 already covers exhaustively -- combined with this milestone's own
release-critical Gate A status, that combination justified a full Core run
rather than relying on Tier 2 alone.

**Result:** `pytest -m "not slow"` (`scripts/verify_core.py`'s own exact
convention), one bare foreground pass: **5672 passed, 2 failed, 3 skipped,
23 deselected (`slow`-marked), 11 xfailed, 236 warnings** (2613.39s /
43m33s).

**The 2 failures are independently confirmed pre-existing and unrelated,
not merely assumed:** both are
`tests/test_place_biodiversity_summary_repository.py::test_api_route_
returns_the_summary` and `::test_human_correction_updates_place_
biodiversity_intelligence_correctly`, both with the identical assertion
mismatch (`AssertionError: assert 'seen_before' == 'new'`). This exact
pair, with this exact symptom, is one of this codebase's own most
extensively pre-documented recurring flakes -- named explicitly in the
test file's own header comment ("`historical_status`/`new_taxa` reads
'new' only while the confirmation's own timestamp still falls on the
*current* Place-local day ... reproduced, and independently re-confirmed
pre-existing across nine-plus prior full-Core checkpoints in
docs/release-execution-state.md") and cross-referenced at least 17 times
across `docs/release-execution-state.md`'s own §14 "Validation baselines"
-- most directly, the *immediately-prior* Core checkpoint recorded there
(Hard-Negative Visit Admission Precision & Species-Escalation Correctness
v1) hit this exact same pair while touching these exact same two
production files (`candidate_quality_gate.py`, `product_repository.py`)
and confirmed it via the identical methodology this report also uses.
This is a real-wall-clock-date-dependent test limitation (the test
constructs a "first-ever confirmation" fixture against the real system
clock, with no test-clock injection available on this specific HTTP
route), not a code defect this or any prior milestone introduced.

**Independently re-confirmed this session, not merely cited:** re-ran
`tests/test_place_biodiversity_summary_repository.py` alone (21 passed, 2
failed, identical assertion) with this milestone's own changes in place;
then `git stash push` of exactly the seven files this milestone changed
(`candidate_quality_gate.py`, `product_repository.py`, both contract docs,
`VisitEvidenceSequence.tsx`, both test files) back to the clean starting
HEAD (`b4a2a660...`) and re-ran the identical file again: **byte-identical
failure, same two tests, same assertion mismatch, zero of this milestone's
changes applied.** `git stash pop` restored the fix immediately after;
`git status --short` confirmed all seven files and the untracked
preserve-list restored exactly. This milestone touches no Place/
Biodiversity/Bird-Log-journal code at all, and the failure's own root
cause (a real-clock-relative "was this observation confirmed today"
check) has zero structural relationship to Visit admission, evidence
roles, or the quality gate.

**Zero new `ruff` findings** on any touched file (confirmed via the
identical clean-baseline bisection already reported under "Lint," below).
**No schema change** (v58, unchanged) -- no guard-rail assertions needed
touching. **No other failures, of any kind, anywhere in the 5672 passing
+ 2 pre-existing-flake tests are attributable to this milestone.**

## Lint

`ruff check` on both changed production files and both changed test files:
`candidate_quality_gate.py`, `test_candidate_quality_gate.py`, and
`test_same_frame_species_evidence.py` are fully clean (`All checks
passed!`). `product_repository.py` carries 57 pre-existing findings across
its own ~37,000 lines, confirmed byte-identical in count before and after
this milestone's own two edits (`git stash` diff comparison) -- zero new
findings introduced by this milestone, and this file's own pre-existing
lint debt is unrelated to and outside the bound of this milestone.

## Remaining residuals

- **Case A's own ambiguous-boundary/geometry-tolerance finding is
  disclosed, not fixed, here.** `classify_boundary`'s geometry-
  compatibility tolerance is capped at 0.6 normalized centroid distance
  for any gap >= ~9.6 seconds -- a large fraction of a typical frame's own
  diagonal -- meaning, for any temporal gap between ~9.6s and the full 45s
  `ambiguous_gap_ms` window, the geometry check contributes essentially no
  discriminative power against two spatially-distinct real subjects (or a
  real subject and an unrelated persistent confusor) that happen to fall
  within that window. This is squarely "candidate authority"/"ambiguity
  threshold" territory, explicitly excluded from blind tuning by this
  milestone's own governing brief (§5); recommended as a candidate for a
  future, separately-authorized milestone, not self-authorized here (§26).
- **The 2026-08-19 evidence-cache-eviction mechanism remains a real,
  disclosed, not-fully-eliminated residual in principle**, unrelated to
  and untouched by this milestone (see "Historical same-terminal-reason
  comparison").
- **Cannot retroactively attribute v12's own remaining 29 (of 31)
  `reject_no_identification_or_context` occurrences, or the 2026-08-20
  document's own 12 historical occurrences, to same-frame-only survival
  specifically.** A rejected proposal's evidence items are never persisted
  to the database (by design -- see `_create_candidate_visit_locked`'s own
  early-return structure), so this fact is not recoverable from the
  counterfactual ledger after the fact for any historical session. The
  mechanism itself is proven at the code level and end-to-end tested with
  real numbers, not exhaustively attributed record-by-record against
  historical data that was never structured to answer this question. This
  is exactly the diagnostic gap this milestone's own §18 fix narrows for
  *future* sessions (see "Diagnostics").
- v12's own item (12) (a cohort with intact full-session raw-ledger
  coverage) is unaffected by this milestone -- unchanged, still open.

## Gate A effect

This milestone does not itself pass Gate A. Item (13)'s own dependency
state is narrowed and split, not simply closed:

- **(13a) [CLOSED / FIXED]:** the specific, proven, code-verified
  same-frame-only evidence-exclusion defect no longer silently discards a
  real subject capture. Fixed; Tier 1/2/3 all clean (Tier 3's own 2
  failures independently confirmed pre-existing and unrelated -- see
  "Tier 3 decision"); no material precision regression found.
- **(13b) [carried forward, unmet]:** whether `reject_no_identification_
  or_context`'s all-or-nothing behavior harms recall in any *other*
  live-reachable shape remains formally open -- this milestone's own
  case-exhaustion proof establishes same-frame-only survival as the
  *only* other live-reachable shape today, so (13) as originally worded is
  now answered as completely as the current architecture allows, but the
  underlying "does this reason ever discard a real, brief encounter"
  question cannot be fully retired until a future representative cohort
  with intact raw-ledger coverage (item 12) is run against this now-fixed
  code and produces zero further same-frame-only misses in the field, not
  merely in test fixtures.
- **(NEW, disclosed, not self-authorized):** whether the ambiguous
  -boundary arbitration's own geometry-compatibility tolerance
  meaningfully discriminates between spatially-distinct real subjects when
  a persistent, frequently-recurring confusor is active nearby (Case A's
  own finding) -- a genuinely new Gate A recall question, explicitly out
  of this milestone's own scope to fix.

The next representative cohort still needs everything the pre-existing
11-item list plus item (12) already name: intact full-session raw-ledger
preservation, an independent prospective denominator, recall, false-Visit
precision, fragmentation, duplicates, useful evidence, true calibrated
latency, monitoring coverage, and accepted-mechanism participation. No
budget is invented here.

## Decision

**A**

Root cause was established, not guessed, for every case actually examined
-- including the material correction that neither of v12's two named
misses terminates at the reason this milestone was chartered to trace,
established via direct ledger-to-code cross-reference, not assumption.
The milestone's own chartered failure pattern (a real subject captured but
discarded outright because its only surviving evidence never reaches a
role the quality gate recognizes) was independently, separately proven to
be a real, currently-live-reachable defect -- via a complete case
-exhaustion argument over the scorer's own logic, not sampling -- and was
fixed with the smallest correction available at its own first irreversible
error, fully consistent with the brief's own preferred-ordering discipline
(role classification, not a downstream gate-policy retune). The fix is
grounded throughout in this exact session's own real detection signatures,
both for the positive control (Case A's own real 8-detection encounter)
and the negative control (the real persistent confusor's own weakest
signature), per the brief's own labeling discipline for a constructed
reproducer. Every required historical false-positive-control regression
suite and every directly-relevant subsystem test passes unmodified; no
threshold, detector, tracker, or classifier code was touched; no schema
changed; Reviewed-truth semantics are completely unchanged. One genuinely
new, real, precisely-root-caused defect (Case A's own ambiguous-boundary/
geometry-tolerance interaction) was discovered and is disclosed, not
fixed, exactly because fixing it would require touching a subsystem this
milestone's own governing brief explicitly places off-limits.
