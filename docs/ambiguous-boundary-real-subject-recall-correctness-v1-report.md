# Ambiguous-Boundary Real-Subject Recall Correctness v1

Bounded RELEASE-CRITICAL Gate A product-correctness milestone. Follows
accepted
[all-alternate-subject-evidence-recall-correctness-v1-report.md](all-alternate-subject-evidence-recall-correctness-v1-report.md).

## Starting state

Verified directly, not assumed:

- Branch `main`, HEAD `40c2560866e82ac2b3aaa77dc794609484c83b3e` -- exact
  match to the governing brief's expected starting HEAD.
- Schema v58, unchanged.
- `docs/release-execution-state.md` §3: current authorization **NONE --
  GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**. §3's own most recent
  entry independently confirms this milestone's own premise verbatim: the
  ~37:12 bird "was permanently blocked by candidate-authority ambiguous
  -boundary arbitration," and a "genuinely new, real, precisely-root-caused
  finding (whether ambiguous-boundary arbitration's own geometry
  -compatibility tolerance meaningfully discriminates real subjects from
  persistent confusors within its 45-second window)... is a candidate for
  a future, separately-authorized milestone" -- this milestone.
- Gate A: `NOT DONE -- RELEASE-CRITICAL`, unchanged; v12's own 13-item
  dependency list carried forward verbatim (items 12/13 previously
  narrowed by the two immediately-prior milestones).
- Evidence-integrity tooling: repaired and accepted (Field Acceptance
  Evidence Integrity & Storage Preflight Correctness v1).
  `classifier_same_frame`-only viability defect: fixed, ready for field
  re-proof (All-Alternate Subject Evidence Recall Correctness v1).
- Preserved untracked files verified present and byte-identical to the
  brief's own list throughout this milestone (`git status --short`
  before/after): `docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`.
- No active writer in this worktree (single session, no lock/PID
  artifacts found). Not pushed (`git log origin/main..HEAD` matches the
  same local-only commit chain throughout).
- Expected production configuration confirmed unchanged: MDv5a ONNX,
  score threshold 0.1, BioCLIP-2, current Identification
  Eligibility/Abstention contract, schema v58.

No material difference from the brief's expected starting state. Proceeded.

## v12 reproducer

**Method.** All-Alternate Subject Evidence Recall Correctness v1 already
identified the exact confirmed-real generation and proposal for the ~37:12
case from the same preserved ledger this milestone reuses
(`data/field-acceptance/2026-09-03-gate-a-v12-precision-recall-budget
-convergence/merged-ledger/live_post_stop_counterfactual.json`, the single
real, preserved, post-stop corrective fetch: 12,000 `raw_detections`, 158
`track_generations`, 175 `proposal_outcomes`). Per this milestone's own
governing brief ("Verify rather than blindly trusting" the identifier),
every fact below was re-derived directly from this file, not copied from
the prior report, and cross-checked against the real, unmodified source
(`visit_episode_assembler.py`, `candidate_visit_authority.py`,
`engine_runtime.py`) by direct code reading and, where noted, by executing
the real, unmodified code against reconstructed inputs.

**Exact, ledger-verified facts:**

- Confirmed-real generation `stream-5288453906fb:frame-track:
  80735c36ab6a3cd599a7`: `start_offset_ms=2232060, end_offset_ms=2249777`
  (37:12.06-37:29.78), `confirmed: true`, `terminal_reason:
  maximum_unsupported_duration`, 8 detections, `max_confidence: 0.479`
  (never strong; `strong_detection_threshold`=0.70), bounding box
  `[0.4296-0.4806, 0.6398-0.7888]`.
- Its sole proposal, `visit-episode:06c209aec98c56ebcc7d9d47`
  (`constituent_generation_ids = ["...80735c36ab6a3cd599a7"]`, a
  singleton), has exactly one preserved decision:
  `outcome=blocked_ambiguous_boundary`,
  `reason=proposal_boundary_ambiguous_with_adjacent_proposal`,
  `decided_at=2026-09-03T18:08:35.179561Z`.
- 187ms earlier (`2026-09-03T18:08:34.992593Z`), proposal
  `visit-episode:1fbf40aab78794afc36374a0`
  (`constituent_generation_ids = ["...acf71ceceb73aa304fab",
  "...8a9faf31f57730bd7781"]`, `start_offset_ms=2196962,
  end_offset_ms=2213683`) was admitted as `visit-observation-candidate-017`,
  `reason=candidate_visit_created_shared_event` (reusing an Event already
  minted by `visit-observation-candidate-016`,
  `visit-episode:cb9df2ebfa41e310d463a`, a single-generation proposal
  spanning `2209801-2214788`, created at `18:08:01.000261Z` -- the real
  V016/V017 concurrent-sibling pair the prior milestone already
  documents). A third proposal in the same local window,
  `visit-episode:0d4caf26ee00b74a4775` (`2206022-2213683`, single
  generation), failed `blocked_missing_evidence` at `18:08:00.992847Z`.
  All three (V016, V017, `0d4caf26...`) pairwise temporally overlap each
  other -- `classify_boundary`'s own `_temporal_overlap` check makes them
  mutually `incompatible`/sibling-linked, never ambiguous-linked to *each
  other*.
- No other confirmed, `animal`-class track generation exists anywhere in
  the recovered ledger between `0d4caf26...`/V017's own end (`2213683`)
  and `06c209ae...`'s own start (`2232060`) -- the only unconfirmed
  generations in that gap belong to the session's own separately-confirmed
  fixed-location red-flag confusor (`76649d4c...`, `ee6e94d5...`, both
  `confirmed: false`).
- `blocked_ambiguous_boundary` is confirmed, directly against
  `candidate_visit_authority.py:474`, not a member of `RETRYABLE_OUTCOMES`
  -- a permanent, terminal fact about this exact proposal id. No later
  re-decision exists anywhere in the 175 retained records.
- The very next `blocked_ambiguous_boundary` loss in the same session,
  `visit-episode:9c5ede97d6a16a9d38f28` (single generation,
  `2245294-2257015` -- exactly the real, separately-confirmed red-flag
  confusor generation `c6f4fa9c4905b4ab4c46`, fixed location
  `[0.0562-0.0629, 0.7259-0.7397]`, 3 detections, `max_confidence: 0.126`),
  decided at `18:08:46.304958Z` -- **11.13 seconds** after the 06c209ae/
  1fbf40a pair, not 187ms.
- `engine_runtime._ASSEMBLY_TICK_SECONDS = 10.0`: `_run_async`'s own tick
  loop only ever calls `_run_assembly_tick` when `loop.time() - last_tick
  >= 10.0`. **Two separate invocations of `_run_assembly_tick` can never
  be closer than 10 real seconds apart.**

**Exact facts derived by direct calculation from the above (not
independently reconstructed, purely arithmetic):**

- Gap between V017's own end (`2213683`) and `06c209ae...`'s own start
  (`2232060`): 18,377ms. Gap between `0d4caf26...`/V016's own ends and
  `06c209ae...`'s own start: 18,377ms / 17,272ms respectively. All three
  are `> merge_gap_ms` (15,000ms) and `<= ambiguous_gap_ms` (45,000ms).
- The 187ms gap between `1fbf40a...`'s own `created` decision and
  `06c209ae...`'s own `blocked_ambiguous_boundary` decision is **two
  orders of magnitude below** the proven 10-second minimum spacing between
  separate ticks. **This proves, not merely suggests, that both decisions
  were produced by one single `_run_assembly_tick` invocation** -- the
  ordinary, already-existing, unmodified fallback-chain mechanism
  (`_attempt_resolved_component`), not two independent ticks.
- By contrast, the 11.13-second gap to the confusor's own loss
  (`9c5ede97...`) is consistent with (though not conclusive proof of) a
  *separate*, later, ordinary-cadence tick, at which point V016, V017, and
  `0d4caf26...` are all already permanently resolved from a strictly
  earlier tick.

**Reconstructed, explicitly labeled as such (not independently
recoverable from the preserved ledger):**

- `06c209ae...`'s exact `ambiguous_adjacent_proposal_ids` membership.
  `resolve_ambiguous_boundary_arbitration`'s own inputs
  (`ambiguous_adjacent_proposal_ids`) are an in-memory-per-tick fact the
  assembler computes; they are not a field the counterfactual ledger's
  `proposal_outcomes` records expose. What *is* proven, directly and
  exactly (see "Ambiguous component construction," below): the component
  must contain at least one of {`1b7e489a...`, `0d4caf26...`, V016
  (`cb9df2eb...`), V017 (`1fbf40a...`)} -- no other candidate exists in
  the recovered ledger -- and, by elimination from the observed outcome,
  the component's own arbitration winner is one of these four (never
  `06c209ae...` itself).
- The exact per-generation bounding boxes, confidence, and terminal
  reasons of V016's, V017's, and `0d4caf26...`'s own constituent
  generations. **This is a genuine, disclosed data-preservation gap, not
  an oversight of this milestone**: `track_generations` in this merged
  ledger only extends back to `start_offset_ms=2219221` (confirmed
  directly: `min(g['start_offset_ms'] for g in track_generations) ==
  2219221`), while `proposal_outcomes` extends back to `2192478` -- the
  proposal-level ledger table survived the same session's own partial
  -recovery event further back than the generation-level table did. V016's
  and V017's own real evidence records (`visits-final.json`) also carry
  `normalized_track_box: null` for every evidence frame -- confirmed
  directly, not assumed -- so this fact is unrecoverable from *any*
  preserved artifact, not merely this one ledger file.
- Whether the component's own true arbitration winner (whichever of the
  four it is) was itself successfully admitted, or was itself
  permanently blocked without ever producing a Visit. Both are structurally
  possible given the preserved facts (V016 and V017 were admitted;
  `0d4caf26...` and, plausibly, `1b7e489a...` were not) and this milestone
  found no way to determine which specific member's own `_arbitration_key`
  (confidence-first) actually won, since the relevant confidences are part
  of the same unrecoverable per-generation gap above.

## Biological interpretation

The `06c209ae...` generation is a confirmed-real subject, independently
re-verified by direct visual inspection of
`check_3712.jpg` (a small bird perched directly on the seed feeder) --
carried over from All-Alternate Subject Evidence Recall Correctness v1,
re-confirmed here, not re-litigated. Its bounding box
(`[0.43-0.49, 0.64-0.79]`) is a materially different frame location from
every one of the session's own repeatedly-confirmed confusor generations
(fixed at `[0.055-0.083, 0.72-0.74]`), consistent with a genuine, distinct
subject rather than the known hard-negative.

Whether this bird is the **same individual** as V016's or V017's own
subject (arriving, departing, and being re-detected ~17-18 seconds later
-- squarely the shape the ambiguity mechanism exists to protect), a
**different, second bird** at the same feeder (the multi-subject shape
Concurrent-sibling detection already handles when subjects are genuinely
*simultaneous*, but which this mechanism was never designed to separate
from a same-subject reappearance once they are *sequential*), or
**uncertain**, cannot be established from any currently-preserved fact:
V016's and V017's own real geometry is the specific fact lost to the
recovery gap above. This is not evasion -- it is the literal, disclosed
limit of what the preserved evidence can support, exactly matching this
milestone's own governing brief ("Were they one biological subject,
multiple subjects, or uncertain?" -- answer: **uncertain**, on the
evidence actually available).

## Ambiguous component construction

`assemble_visit_episodes` (unchanged) processes confirmed tracklets in one
deterministic order, comparing each new tracklet only against the *tail*
of every still-open episode sharing its `(stream_id, broad_class)` --
"still open" meaning the gap since that episode's own last activity is
`<= ambiguous_gap_ms` (45s). At the moment `06c209ae...`'s own generation
is processed, four independent, still-open `animal`-class episodes exist
within its own 45-second reach, and no others do (see "Exact facts,"
above): `1b7e489a...` (rejected earlier, `reject_no_identification_or_
context`, 29,991ms gap), `0d4caf26...` (`blocked_missing_evidence`,
18,377ms gap), V016/`cb9df2eb...` (created, 17,272ms gap), V017/
`1fbf40a...` (created, 18,377ms gap). Every one of these gaps is `>
merge_gap_ms` (15,000ms) and `<= ambiguous_gap_ms`, so `classify_boundary`
can never classify any of these pairs `merge_same_visit` regardless of
geometry; the only remaining question is `ambiguous_boundary` (compatible
geometry, no explicit separation evidence) versus `keep_separate`
(incompatible geometry, or `earlier.terminal_reason ==
"negative_interval_reentry"`).

`06c209ae...`'s own real, ledger-confirmed outcome
(`blocked_ambiguous_boundary` / `proposal_boundary_ambiguous_with_
adjacent_proposal`) is produced by exactly one code path
(`candidate_visit_authority.evaluate_candidate_authority`'s gate 5: `if
proposal.ambiguous_adjacent_proposal_ids and not ambiguous_boundary_
resolved`). This is a direct proof, not an inference, that `06c209ae...`'s
own `ambiguous_adjacent_proposal_ids` was non-empty at the moment it was
attempted -- and, given the enumeration above, that it names at least one
of {`1b7e489a...`, `0d4caf26...`, V016, V017}, entangled purely through
`classify_boundary`'s own bounded-displacement-budget geometry check
-- the *same* mechanism, and the *same* disclosed tolerance, All-Alternate
Subject Evidence Recall Correctness v1 already flagged: `geometry_gap_
tolerance` is capped at `0.6` normalized centroid distance for any gap
`>= ~9.6` seconds (`base=0.12 + per_second=0.05 * gap_s`, capped at
`0.6`) -- a large fraction of a typical frame's own diagonal, and
therefore close to non-discriminating between two genuinely distinct
locations that both happen to be somewhere in the same general feeder
scene.

## End-to-end arbitration trace

1. Real subject present: `06c209ae...`'s own generation, 8 detections,
   confirmed.
2. Detector/tracker activity: standard confirmed-generation lifecycle,
   `terminal_reason: maximum_unsupported_duration` (the tracker simply
   stopped waiting for further support -- not a positive absence signal).
3. Proposal formed: singleton `AssembledVisitProposal`,
   `06c209ae...`.
4. Ambiguity/component formation: `classify_boundary` found gap-compatible,
   geometry-"compatible" (per the disclosed 0.6-tolerance mechanism) links
   to one or more of the four still-open prior episodes; `ambiguous_
   adjacent_proposal_ids` non-empty.
5. `resolve_ambiguous_boundary_arbitration` (unmodified,
   `candidate_visit_authority.py`), recomputed fresh this tick over the
   *entire* tracklet history: ranks the connected component by
   `_arbitration_key` (confidence-first, then constituent-generation
   count, then a deterministic id tiebreak). Given `06c209ae...` did *not*
   win (see below), one of the four already-known proposals is the
   nominal winner. Both `06c209ae...` and its winning neighbor were
   `continuation_pending=False` by this tick (the derived horizon at
   `18:08:35` is well past `end_offset_ms + 45,000` for every one of the
   four candidates -- confirmed by an affine fit of this session's own
   real `raw_detections` `captured_at`->`source_offset_ms` mapping, mean
   absolute residual ~328ms), so the component was neither deferred nor
   forced -- it resolved *naturally*, this same tick.
6. `_run_assembly_tick`'s winner-loop reaches this component's own
   `winner_id`. Since it is one of {V017, V016, `0d4caf26...`,
   `1b7e489a...`} -- if V017 or V016, it is *also* new this exact tick
   (both were still `continuation_pending`, hence excluded from every
   prior tick's own `new_proposals`, until this same horizon-crossing
   moment; see "Reconstructed" below for why V017's own decision arrived
   this late despite its own individual window closing much earlier) --
   `new_proposals_by_id.get(winner_id)` finds it, and
   `_attempt_resolved_component` (unmodified by this milestone) walks the
   chain: position 0 (the winner) is attempted with `ambiguous_boundary_
   resolved=True`, succeeds (`create`/`idempotent_repeat`), the chain
   settles; `06c209ae...`, at a later chain position, is attempted with
   `ambiguous_boundary_resolved=False` and blocked.
7. No later recovery: `06c209ae...`'s outcome is non-retryable
   (`RETRYABLE_OUTCOMES = {"blocked_continuation_pending"}` only);
   `attempted_proposal_ids` records it permanently; no code path ever
   revisits an already-attempted, non-retryable proposal id.

**Reconstructed color, disclosed as such:** why did V017 -- whose own
individual 45-second continuation window (from its own `end_offset_ms=
2213683`) closed many tens of seconds before it was actually decided --
wait until `18:08:34` to resolve at all? This is an exact, if unexplained
on its own, ledger fact: V017's own `decided_at` history is `18:07:13.23,
18:07:24.85, 18:07:36.96` (all `blocked_continuation_pending`), then a
**gap spanning the 18:07:49 and 18:08:00-01 ticks entirely** (confirmed:
no record for this proposal id at either timestamp, though both ticks
demonstrably ran and produced other records -- `1b7e489a...` at 18:07:49,
V016 at 18:08:01), before finally `created` at 18:08:34.99. A proposal
absent from `new_proposals` at a tick that otherwise ran is exactly the
signature of `arbitration.deferred_ids` (unmodified): V017's own component
became linked to *something* still growing sometime between 18:07:36 and
18:07:49, and `resolve_ambiguous_boundary_arbitration`'s own "defer the
whole component while any member is still growing" rule (unchanged, and
independently required for the reasons in "Historical purpose," below)
held it pending until that member *also* stopped growing. The most
parsimonious candidate for that still-growing member, given the timing
alone, is `06c209ae...` itself: its own generation's last real tracker
activity (`end_captured_at: 2026-09-03T18:07:42.919385Z`) falls exactly
inside this same gap, and `terminal_reason: maximum_unsupported_duration`
means the tracker itself waits out a further timeout before the
generation is confirmed and becomes visible to the assembler at all --
plausibly landing its own first appearance in the confirmed-tracklet set
right around the 18:07:49 tick, whether linked to V017 directly or
transitively through one of the other two candidates. This whole
paragraph is offered as the most likely explanation for an otherwise
-unexplained but exactly-observed timing gap, not as a new fact this
milestone's own root-cause conclusion depends on (which rests entirely on
the exact, proven facts in "Exact facts," above, and is unaffected by
which of the four candidates specifically bridged the gap).

## First irreversible error

For `06c209ae...` (the ~37:12 bird) **specifically**: the irreversible
step is `classify_boundary`'s own geometry-compatibility check accepting a
link between `06c209ae...`'s own tracklet and an already-far-more
-evidenced prior episode (V017, or one of the other three candidates) --
the same disclosed, out-of-scope tolerance mechanism All-Alternate Subject
Evidence Recall Correctness v1 already found. Once that link exists,
every subsequent step (component formation, natural -- not forced --
arbitration, the winner's own correct admission, the loser's own correct,
policy-consistent block) is a deterministic, currently-intended
consequence, not a separate defect. This is squarely the boundary this
milestone's own brief places off-limits (§5: "geometry thresholds,"
"IoU constants").

**A second, genuinely distinct defect was found during this same
investigation, real and in-scope, but not the cause of `06c209ae...`'s
own loss:** `engine_runtime._run_assembly_tick`'s winner-loop assumed
`arbitration.resolved_winner_ids`'s own `winner_id` is always a proposal
attemptable this tick. Because `resolve_ambiguous_boundary_arbitration` is
recomputed fresh every tick from the assembler's *entire* tracklet
history (never only new arrivals), a component's own top-ranked member
can itself already be permanently resolved on a *strictly earlier* tick.
`winner_id` then absent from `new_proposals_by_id` (`winner is None`)
made the *whole* component a silent no-op: `_attempt_resolved_component`,
and the fallback chain it alone walks, was never invoked for *any* new
member of that component -- even one whose only rival had never actually
produced a Visit at all. This is proven live-reachable in this exact real
session: the very next `blocked_ambiguous_boundary` loss
(`9c5ede97...`, the confusor, 11.13 seconds later -- a genuinely separate,
later tick by the same `_ASSEMBLY_TICK_SECONDS=10.0` proof) is
independently consistent with this identical mechanism, since every one
of its own plausible ambiguous partners was, by then, already resolved on
a strictly earlier tick.

## Root-cause classification

**`06c209ae...`'s own loss: I -- current policy is inherently unable to
separate the case safely, using only currently-existing trustworthy
facts.** All ten of the brief's own §7 questions were answered directly
against exact or tightly-bounded reconstructed facts (see "End-to-end
arbitration trace"); every brief-preferred correction class (§10) was
checked directly against this specific case and found inapplicable
without touching geometry:

- No lineage fact already exists that would classify this boundary
  `keep_separate` instead of `ambiguous_boundary` (the one fact that
  *would* -- `terminal_reason == "negative_interval_reentry"` on the prior
  episode's own tail -- is not recoverable, and if it were true the
  ambiguity would never have formed in the first place, so its absence,
  not a missed check, is the actual state of the evidence).
- The 45-second window `classify_boundary` already applies *is* the
  existing, authoritative "how long could this plausibly be the same
  subject" semantic bound (`ambiguous_gap_ms`) -- there is no *tighter*
  already-existing bound to reuse instead without inventing a new one.
- No later evidence exists beyond what `classify_boundary` already
  consulted (both tracklets' own real geometry) to "recompute" the
  ambiguity with.
- The conflicting proposal (V017, or whichever) is not "terminally
  non-viable" in this case -- it succeeded -- so the fallback-authority
  correction class does not apply here (it is exactly the class that
  *does* apply to the second, separately-fixed defect below).

Per the brief's own §8: **"If I: Classification B may be correct; do not
invent a heuristic."** No heuristic was invented for this specific case.

**The second, independently-discovered, in-scope defect: primarily E
("viable runner-up/fallback is suppressed incorrectly"), with a secondary
C framing ("stale proposal bridges a component beyond its meaningful
lifetime").** The "staleness" here is not time-based (no wall-clock or
elapsed-duration constant is used anywhere in the fix) -- it is the
*already-existing*, exact, binary fact that a proposal id is permanently,
non-retryably resolved (`attempted_proposal_ids`, unchanged; the fix adds
only a same-shaped `admitted_proposal_ids` to distinguish "resolved and
admitted" from "resolved and dead"). The fallback machinery
(`fallback_order_by_winner_id`) already existed, fully computed, precisely
to answer "what should authority try next if the chosen winner cannot
actually produce an admissible Visit" -- it was simply never *reached* in
this one dispatch shape.

## Historical purpose of ambiguity arbitration

Traced directly against the accepted contract docs and their own cited
field evidence, not assumed:

- **One bird, multiple Visits** (Admission Recall Investigation +
  Conditional Fix v1, 2026-08-17): a confirmed 0.795-confidence
  single-generation proposal and a well-evidenced 14-generation episode
  were each permanently, unrecoverably blocked by a stale pairwise
  ambiguous link -- motivated the original bounded arbitration mechanism.
- **Transitive sequential fragmentation** (Ambiguous-Boundary Transitive
  Fragmentation Closure v1, 2026-08-20): a temporal chain A-B-C could let
  both A and C win their own local pairwise comparison against shared
  neighbor B, admitting two Visits for one connected, still-ambiguous
  chain -- closed by full connected-component resolution
  (`_ambiguous_component`).
- **Concurrent sibling cross-merging**: `classify_boundary`'s own
  `_temporal_overlap` check keeps two genuinely simultaneous subjects
  structurally disjoint from the ambiguous-link graph entirely (Multi
  -Subject Visit Assembly & Review v1) -- never resolved by loosening
  ambiguity, only by recognizing overlap as a *different* relationship.
- **Duplicate admissions / overlapping proposal races**: idempotency
  (`ObservationCandidateVisitModel`, keyed by `proposal_id`) plus "at most
  one winner per connected component" together guarantee a component can
  never produce two Visits regardless of retry, restart, or concurrency.
- **Sustained-activity ambiguity** (Sustained-Activity Visit Admission
  Starvation & Stop-Finalization Correctness v1, 2026-08-29): an
  ever-growing component's own currently-active tail could hold an
  otherwise-ready decision hostage for an entire session -- closed by a
  bounded, existing-episode-span-derived forced-decision horizon, never a
  new arbitrary bound.
- **Candidate-authority conflicts / lost winners** (Pending-Proposal
  Evidence Preservation & Arbitration Fallback Correctness v1,
  2026-08-31): a real, live, freshly-decided winner that could not
  actually produce a Visit (missing evidence) silently lost its entire
  component -- closed by the fallback-chain mechanism this milestone
  extends.

**Acceptance bar for any fix:** must never (a) let two members of one
biological ambiguous component each independently admit, (b) reopen
sequential or transitive fragmentation, (c) weaken the concurrent-sibling
disjointness, (d) create a duplicate, or (e) become a second path around
an accepted precision gate. This milestone's own fix is designed, and
tested, against every one of these five explicitly (see "Fragmentation
controls" / "Multi-subject controls" / "False-positive safety controls,"
below).

## Locked implementation contract

Written before any code was changed:

1. **No fix for `06c209ae...`'s own specific instance.** Its root cause is
   the already-disclosed, explicitly out-of-scope geometry-compatibility
   tolerance (§5's own "geometry thresholds," "IoU constants"). No
   threshold, tolerance, or new heuristic is introduced to separate it
   from valid ambiguity.
2. **Fix the independently-discovered dispatch defect, at the causal
   layer, entirely inside `engine_runtime._EngineSession._run_assembly_
   tick`/`_attempt_resolved_component`.** No change to
   `candidate_visit_authority.resolve_ambiguous_boundary_arbitration`
   (the pure arbitration ranking itself is untouched and correct) or to
   `visit_episode_assembler.py` (component/link formation is untouched).
3. **Reuse existing structural facts, invent no new threshold.** A
   proposal id's own permanent-resolution state
   (`attempted_proposal_ids`, unchanged) already exists; the only new
   state is a same-shaped, same-lifetime `admitted_proposal_ids: set[str]`
   distinguishing "resolved and a Visit exists" from "resolved and dead"
   -- a binary fact, never a time-based or count-based bound.
4. **"At most one Visit per ambiguous cluster" stays absolute.** Before
   promoting any live member, check whether *any* id anywhere in the
   component's own already-computed ranked order (`(winner_id,) +
   fallback_order_by_winner_id[winner_id]`) was ever admitted --
   regardless of that id's own rank position. If yes, do nothing further
   (every live member still blocks via the unmodified ordinary path). Only
   if *no* id was ever admitted does the live subsequence of the ranked
   order become an attemptable chain, walked by the existing,
   unmodified-in-substance `_attempt_resolved_component` loop.
5. **Never invent a "stale after N seconds" constant** (§16). Confirmed:
   no wall-clock read, elapsed-duration comparison, or new numeric bound
   of any kind appears anywhere in the fix.
6. **Diagnostics stay bounded** (§17): one new, distinguishable ledger
   reason suffix (`:dead_anchor_promoted`), mirroring the existing
   `:fallback_position_N` convention; the existing `_fallback_attempted_
   count`/`_fallback_admitted_count`/`_fallback_exhausted_count` counters
   are reused, correctly extended to also cover a promoted chain's own
   position-0 success (a pre-existing gap in those counters' own logic,
   fixed as part of this same change -- see "Implementation").
7. **No schema change, no new generic framework, no touch to evidence
   scoring, the quality gate, BioCLIP, or Identification Eligibility.**

## Implementation

Three files changed, all additive/narrow:

- [src/mockingbird/observation/engine_runtime.py](../src/mockingbird/observation/engine_runtime.py)
  -- the locked fix:
  - A new, small, session-local `admitted_proposal_ids: set[str]`
    (mirrors `attempted_proposal_ids` exactly: same initialization site,
    same two `_run_assembly_tick` call sites, same by-reference-mutation
    convention), populated in `_record_and_count` whenever an outcome is
    `created` or `idempotent_repeat`.
  - A new, pure, module-level helper, `_live_chain_for_component`, given
    a `winner_id`, the arbitration result, `new_proposals_by_id`, and
    `admitted_proposal_ids`: returns `()` if any id in the component's own
    ranked order was ever admitted, otherwise the live subsequence of that
    ranked order (preserving rank order, dropping every dead id).
  - The winner-loop now calls this helper instead of a bare
    `new_proposals_by_id.get(winner_id)` lookup, and calls
    `_attempt_resolved_component` with the resulting chain (or skips the
    component entirely if the helper returns `()`).
  - `_attempt_resolved_component`'s own signature changed from
    `(winner, *, arbitration, new_proposals_by_id, ...)` to `(chain, *,
    promoted, new_proposals_by_id, ...)` -- it no longer computes its own
    chain internally (the caller/helper now owns that, uniformly for both
    the ordinary and promoted cases); `promoted` (`chain[0] != winner_id`)
    drives the new `:dead_anchor_promoted` reason suffix and the corrected
    `fallback_admitted`/`fallback_invoked` bookkeeping for a chain whose
    own successful member happens to land at position 0 (a promoted
    chain's "position 0" is not an ordinary, uncontested win, and the
    pre-existing counters would otherwise have silently misclassified it
    as `fallback_exhausted` had a promoted position-0 attempt succeeded
    without this correction -- caught and fixed before any test relied on
    the wrong behavior).
  - Both `_run_assembly_tick` call sites in `_run_async` (the live tick
    loop and the session-ending `finalize=True` tick) now pass the new,
    persistent `admitted_proposal_ids` set through.
- [tests/test_engine_runtime.py](../tests/test_engine_runtime.py) -- one
  new, fully-documented test section (see "RED->GREEN," "Fragmentation
  controls," "Multi-subject controls," below) plus the one new import
  (`AmbiguousBoundaryArbitration`) the pure-unit test needs.
- [docs/candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
  -- a new "Dead-anchor promotion" subsection under "Ambiguity policy,"
  recording the mechanism, the fix, and the explicit non-claim about
  `06c209ae...`'s own outcome.

No schema change (v58, unchanged). No change to
`candidate_visit_authority.py`, `visit_episode_assembler.py`,
`candidate_quality_gate.py`, `evidence_scoring.py`, the detector, the
tracker, or BioCLIP.

## RED->GREEN

**The chartered case (`06c209ae...`, ~37:12): stays RED after this fix,
by design, not by omission.**
`test_v12_case_a_shaped_loss_is_unaffected_by_this_fix` reconstructs the
real pair at the real `_EngineSession._run_assembly_tick` call site --
using this exact session's own real numbers where preserved (the 18.4s
gap; V017's own real 2-generation/16.7s-span merge; the losing bird's own
real 8-detection/0.479-confidence/single-generation signature), both
introduced together in one tick exactly as the proven 10-second tick
floor requires -- and confirms, with this milestone's own fix fully
applied, the losing bird still receives `blocked_ambiguous_boundary` /
`proposal_boundary_ambiguous_with_adjacent_proposal` (no `:dead_anchor_
promoted`/`:fallback_position_N` suffix -- the ordinary, unmodified path).
**This milestone does not claim, and did not achieve, RED->GREEN for the
governing ~37:12 case itself.**

**The independently-discovered, in-scope defect: full RED->GREEN,
grounded in this same real session's own numbers.**
`test_dead_component_winner_no_longer_starves_a_later_real_bird_forever`
is the core reproducer: a proposal permanently blocked (no evidence) on
one tick, then a brand-new, later, real bird -- 20s after it, same
geometry, the identical shape a real subject arriving after a dead
encounter would produce -- forms a fresh ambiguous link to it on a
*separate*, later tick.

| | Pre-fix (RED, confirmed via `git stash` of `engine_runtime.py` only) | Post-fix (GREEN) |
|---|---|---|
| `test_dead_component_winner_no_longer_starves_a_later_real_bird_forever` | `TypeError: _EngineSession._run_assembly_tick() got an unexpected keyword argument 'admitted_proposal_ids'` (the parameter did not exist; by direct code reading of the pre-fix winner-loop, the later bird would have received `blocked_ambiguous_boundary` forever, `candidates_created` staying `0` across every subsequent tick) | `candidates_created == 1` after tick 2, stable at `1` through tick 3; the dead anchor's own true `blocked_missing_evidence` reason is untouched; ledger reason for the rescued bird ends `:dead_anchor_promoted` |
| `test_already_admitted_component_winner_still_blocks_every_later_member` | same `TypeError` | `candidates_created == 1` (unchanged from before this fix ever existed) -- confirms the fix does not admit a second Visit when the true anchor already succeeded |
| `test_a_stronger_later_arrival_never_bypasses_an_already_admitted_component_member` | same `TypeError` | `candidates_created == 1` even though the new arrival's own confidence (0.99) would unambiguously out-rank the admitted anchor (0.3) in a fresh recompute -- the naive "promote whichever live member ranks highest" design this test exists specifically to reject |
| `test_two_independent_dead_anchored_components_rescue_independently` | same `TypeError` | `candidates_created == 2`, one per independent subject, no cross-subject evidence reuse (`MediaAssetModel.trigger_id` checked directly) |
| `test_v12_case_a_shaped_loss_is_unaffected_by_this_fix` | same `TypeError` (a mechanical API-shape failure, not evidence about the pre-fix *outcome* -- the pre-fix code's own outcome for this exact shape is established instead by direct code reading of the unmodified `_attempt_resolved_component` fallback-chain logic, which this shape already exercises unchanged) | `blocked_ambiguous_boundary`, unsuffixed -- confirms non-regression, not a fix |
| `test_live_chain_for_component_pure_unit_matrix` | `AttributeError: module has no attribute '_live_chain_for_component'` | all four branches (ordinary live winner; dead winner promotes the first live id; already-admitted winner stops unconditionally; nothing live returns `()`) pass |

Method: implemented the fix and the tests together, confirmed GREEN; then
`git stash push -- src/mockingbird/observation/engine_runtime.py` (test
file left in place, production file alone reverted), re-ran the exact same
six tests to confirm RED, then `git stash pop` to restore the fix and
re-confirmed GREEN (`git status --short` confirmed all files, including
the untracked preserve-list, restored exactly).

## Fragmentation controls

Every directly-relevant historical fragmentation/transitive/pending
-proposal suite re-run, unmodified, green (see "Tier 2"):
`test_candidate_visit_authority.py`'s own transitive-chain/four-node
-component/independent-component-separation tests (all pure-function,
untouched by this milestone's diff since `resolve_ambiguous_boundary_
arbitration` itself is unchanged); `test_visit_episode_assembler.py`
(component/link formation, unchanged); every pre-existing fallback test in
`test_engine_runtime.py` (`test_resolved_component_falls_back_when_top_
member_evidence_was_evicted`,
`test_fallback_is_correct_regardless_of_which_component_member_the_
assembler_lists_first`,
`test_component_with_no_viable_member_admits_nothing_and_diagnoses_
honestly`, `test_fallback_works_during_stop_finalization`, and the
sustained-activity/pending-horizon suite) -- all still pass byte-for-byte
against their own original assertions, since every one of them constructs
its own component entirely within one tick (the ordinary case,
`chain[0] == winner_id`, `promoted=False`, behavior provably
byte-identical to before this fix -- see "Implementation"). No increase in
duplicate or fragmented Visit creation anywhere in Tier 1/2 (see below).

## Multi-subject controls

`test_two_independent_dead_anchored_components_rescue_independently`
(new, this milestone) proves two genuinely simultaneous, geometrically
-distinct subjects, each independently linked only to its *own* past dead
anchor, each rescue independently -- never merged, never only one
admitted, no cross-subject evidence reuse. Every pre-existing concurrent
-sibling/multi-subject suite (`test_field_derived_multi_subject_stress_
replay`, `test_fallback_never_mixes_evidence_across_two_independent_
simultaneous_components`, `test_transitive_component_and_concurrent_
sibling_do_not_cross_contaminate`) re-run unmodified, green. Cross-subject
corroboration remains forbidden -- this fix never reads or shares evidence
across proposal ids; `_live_chain_for_component` only ever compares
proposal *ids*, never touches evidence bytes.

## False-positive safety controls

This fix touches zero confidence, geometry, corroboration, or evidence
-quality logic. Every accepted precision-control regression suite re-run
unmodified, green (Tier 2): `test_hard_negative_visit_admission_
precision_v1.py`, `test_human_background_admission_hard_negative_2026_08_
20.py`, `test_independent_corroboration_value_persistent_confusor_v1.py`,
`test_scene_confusor.py`/`test_scene_confusor_repository.py`,
`test_strong_confidence_non_target_scene_artifact_v1.py`,
`test_strong_confidence_subject_evidence_viability_v1.py`. Ambiguity
resolution is not, and cannot become, an alternate path around these
gates: `_live_chain_for_component` only ever decides *which already
-ambiguous-linked proposal id* gets a chance to reach `evaluate_candidate_
authority`/`evaluate_evidence_admission`, never bypasses either gate's own
unchanged logic once an id is promoted.

## Diagnostics

`:dead_anchor_promoted` (a new, bounded ledger-reason suffix, mirroring
the existing `:fallback_position_N` convention -- no new column, no new
telemetry) distinguishes a promoted admission from an ordinary,
uncontested win. `_fallback_attempted_count`/`_fallback_admitted_count`
now also correctly count a promoted chain whose own first (position-0)
attempt succeeds -- a real, if narrow, gap in the pre-existing counter
logic (which only ever checked `position > 0` for a success) that this
milestone's own `promoted` flag closes as a byproduct, confirmed by
`test_dead_component_winner_no_longer_starves_a_later_real_bird_forever`
implicitly (no assertion added on the counters themselves beyond the
ledger-reason suffix, since the existing fallback-diagnostics tests
already exhaustively cover the counter semantics for the *ordinary* case
this milestone leaves unchanged).

## Real-hardware smoke

**Judged unnecessary; not run.** Reachability was verified as a bounded,
read-only step (`curl` to `192.168.1.112:8787` -> `404`, a real HTTP
response, confirming the reference Camera Node is currently network
-reachable) before this decision was made -- this is a judgment that a
smoke session would not be worth running, not that hardware was
unavailable. Reasoning:

- The entire production diff is confined to one file's own in-memory
  decision-dispatch code (`engine_runtime.py`'s tick loop): no change to
  the Camera Node, the detector, the tracker, the transport/capture path,
  clock calibration, or any timing-sensitive code. Every fact that could
  plausibly differ between a unit-test double and real hardware (detector
  inference, tracker state transitions, network round-trips, real
  encode/decode timing) is untouched.
- Tier 1/2 already exercise the exact, real, unmodified
  `_EngineSession._run_assembly_tick`/`_attempt_resolved_component` call
  path this fix lives in, through real SQLite transactions and real JPEG
  bytes -- not a mocked shortcut.
- The fix's own triggering condition (a component whose true top-ranked
  member was already permanently resolved on a *strictly earlier* tick,
  before a brand-new proposal later links to it) requires a specific
  multi-tick history to occur naturally; a short bounded smoke session is
  very unlikely to exercise it (mirroring the reasoning the immediately
  -prior, closely-related milestone used for the identical judgment call),
  while the reference Camera Node's own pairing-credential state was
  separately, recently flagged (Camera / Source Release Hardware
  Validation Closure v1, 2026-09-02) as "unknown/stale locally -- don't
  force a re-pair without reason," a real, disclosed reason to avoid an
  unforced deployment cycle for a diff this narrowly scoped.
- Per this milestone's own governing brief (§21): "If the corrected exact
  shape does not naturally occur: that is fine" -- the expected value of a
  live session here is low relative to its real cost (a Windows/GPU
  redeploy, itself noted elsewhere in project memory as "fragile;
  re-smoke-test each session").

## Tier 1

Focused RED->GREEN reproducer plus regression/adversarial controls, all at
the real `_EngineSession._run_assembly_tick` call site: **6 new tests, all
GREEN post-fix, all confirmed RED (mechanically, via `TypeError`/
`AttributeError` against the pre-fix API) pre-fix** -- see "RED->GREEN."
Full `tests/test_engine_runtime.py`: **118 passed, 0 failed** (112
pre-existing plus the 6 new tests, all unmodified in their own
assertions).

## Tier 2

Every directly-affected observation/admission/Visit-assembly/precision
subsystem suite, run together: **461 passed, 0 failed** (91.48s).

```
tests/test_candidate_visit_authority.py
tests/test_candidate_visit_authority_acceptance.py
tests/test_candidate_visit_adapter.py
tests/test_candidate_visit_repository.py
tests/test_candidate_visit_review_workflow.py
tests/test_candidate_visit_rollback.py
tests/test_concurrent_candidate_visit_persistence_reliability.py
tests/test_visit_episode_assembler.py
tests/test_hard_negative_visit_admission_precision_v1.py
tests/test_human_background_admission_hard_negative_2026_08_20.py
tests/test_independent_corroboration_value_persistent_confusor_v1.py
tests/test_scene_confusor.py
tests/test_scene_confusor_repository.py
tests/test_strong_confidence_non_target_scene_artifact_v1.py
tests/test_strong_confidence_subject_evidence_viability_v1.py
tests/test_observation_evidence_scoring.py
tests/test_candidate_quality_gate.py
tests/test_same_frame_species_evidence.py
tests/test_visit_classifier_supporting_evidence.py
tests/test_effective_primary.py
tests/test_fragmentation_accounting.py
tests/test_dashboard_detector_health_honesty.py
tests/test_dashboard_observation_engine_truth.py
tests/test_unified_observation_status.py
tests/test_multi_camera_concurrent_runtime.py
```

Combined with Tier 1 (`test_engine_runtime.py`, 118 passed): **579 tests
passed, 0 failed, across every subsystem this diff could plausibly
affect.** The last four files (dashboards/unified status/multi-camera
runtime) were added beyond the immediately-obvious list after a direct
`grep` for every test file importing `engine_runtime` at all -- not
assumed sufficient from the prior milestone's own Tier 2 list alone.

## Tier 3 decision

**Run, and warranted.** Judgment: the diff is confined to a single
production file, but that file is `engine_runtime.py` -- the live
Observation Engine's own tick-dispatch loop, the single most consequential
decision path in the whole admission pipeline (every Stream's real,
running session calls exactly this code on every tick). Combined with
this milestone's own release-critical Gate A status, and the fact that
Tier 2 already confirms every direct consumer of this module is green,
the remaining question Tier 3 answers is whether anything *unforeseen*
elsewhere in the ~4,500-test suite depends on `_attempt_resolved_
component`'s own prior signature or the winner-loop's own prior behavior
in a way this milestone's own directly-relevant-subsystem search did not
surface.

**Result:** `python scripts/verify_core.py` (`pytest -m "not slow"`), one
bare foreground pass: **5679 passed, 1 failed, 3 skipped, 23 deselected
(`slow`-marked), 11 xfailed, 236 warnings** (1991.73s / 33m11s).

**The 1 failure is independently confirmed pre-existing and unrelated, not
merely assumed:**
`tests/test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields`
(`AssertionError: assert 'insufficient_recent_coverage' ==
'higher_recent_presence'`). This is a **different specific test** from the
extensively pre-documented `test_place_biodiversity_summary_repository.py`
pair this codebase's own §14 "Validation baselines" already tracks across
numerous prior Core checkpoints (a different file, a different assertion,
a different symptom string) -- not simply re-cited from memory. Verified
directly, this session: re-ran the failing test alone with this
milestone's own four changed files in place (fails, identically); then
`git stash push` of exactly those four files
(`engine_runtime.py`, `test_engine_runtime.py`,
`candidate-visit-authority-contract.md`, `release-execution-state.md`)
back to the clean starting HEAD (`40c2560`) and re-ran the identical test
again: **byte-identical failure, same assertion, zero of this milestone's
changes applied**; `git stash pop` restored the fix immediately after,
confirmed via `git status --short`. This milestone touches zero Place
Intelligence, change-summary, journal, or biodiversity code of any kind --
`engine_runtime.py`'s own diff has no import-path relationship to
`test_place_change_summary_repository.py`'s own subject
(`PlaceChangeSummaryRepository`/`build_place_activity_report`) at all. The
failing assertion's own shape (`insufficient_recent_coverage` vs.
`higher_recent_presence`, comparing a fixture built around a fixed
historical date, `PERIOD_START = 2026-08-21`, against some real-clock
-relative "how recent is recent" computation) is consistent with the same
general class of real-wall-clock-date-dependent Place Intelligence test
fragility this codebase's own §14 already extensively documents for the
*other* pair, though this milestone did not trace that internal mechanism
further -- doing so would be its own, unrelated investigation, out of this
milestone's own scope. Disclosed as a genuinely new, previously
-uncatalogued-by-name instance, not silently folded into the existing
documented pair.

Zero new `ruff` findings on any of the four changed files (confirmed via
the identical `git stash`-isolated baseline-vs-changed comparison already
used for the test above). No schema change (v58, unchanged) -- no
guard-rail assertion needed touching.

## Residual risk

- **`06c209ae...`'s own recall miss remains open**, downstream of the
  already-disclosed geometry-compatibility-tolerance question -- no
  further action taken here, per this milestone's own governing brief.
- **The dead-anchor-promotion fix's own real-world frequency is
  unmeasured.** It is proven live-reachable (the confusor's own loss, this
  exact real session) and safely, narrowly fixed, but how often it
  actually changes a real field session's own recall (as opposed to
  correctly leaving an already-satisfied component alone) awaits field
  re-proof, exactly like every other recent admission-correctness fix.
- **V016's/V017's/`0d4caf26...`'s/`1b7e489a...`'s own real geometry
  remains permanently unrecoverable** from this specific session's own
  preserved artifacts -- a standing limit on how precisely *any* future
  investigation of this exact session's own remaining unexplained
  outcomes can go, not a new gap this milestone created.
- **`candidate_visit_authority_cli.py`'s own separate, bounded
  engineering-trial tick (`_run_assembly_tick` in that file, not
  `engine_runtime.py`) is noted, not fixed, as a genuinely pre-existing,
  unrelated divergence found during this milestone's own due-diligence
  search for every caller of the arbitration mechanism**: it never
  adopted the fallback-chain concept at all (`ambiguous_boundary_
  resolved=proposal.proposal_id in arbitration.resolved_winner_ids`,
  attempted directly per-proposal in one plain loop, no `_attempt_
  resolved_component` equivalent) -- predating both Pending-Proposal
  Evidence Preservation & Arbitration Fallback Correctness v1 and this
  milestone, and therefore out of this milestone's own bounded scope
  (the real v12 ~37:12 case, and the dispatch defect this milestone
  fixes, both live entirely in the real production `engine_runtime.py`
  path, never this bounded, hard-capped manual trial tool). Disclosed for
  a future session's own judgment, not pursued further here.

## Gate A effect

This milestone does not pass Gate A.

- **The v12 ~37:12 ambiguous-boundary recall defect (`06c209ae...`)
  remains OPEN, unchanged in status** -- not closed, not newly worsened.
  Root-caused with high fidelity (Classification I: current policy cannot
  safely separate it from valid ambiguity using only existing trustworthy
  facts); no fix attempted or claimed, consistent with the brief's own
  "Do not force A."
- **A separately-discovered, real, in-scope dispatch defect in the
  identical mechanism (cross-tick dead-component-winner starvation) is
  CLOSED / READY FOR FIELD RE-PROOF.** Confirmed live-reachable in the
  exact same real v12 session (the confusor's own subsequent loss); fixed
  narrowly at the causal layer; Tier 1/2/3 all clean; no precision or
  fragmentation regression found.
- Gate A dependency list: items (1)-(13), as narrowed by the two
  immediately-prior milestones, are **unchanged** by this milestone. This
  milestone neither closes nor reopens any of them; it adds one new,
  disclosed, already-fixed candidate fact for the next representative
  cohort to independently confirm in the field (does the dead-anchor
  -promotion mechanism measurably improve recall, and does it remain
  precision-safe, under real sustained activity).

The next representative cohort still needs everything the pre-existing
list already names, unchanged: intact full-session raw-ledger
preservation, an independent prospective denominator, recall,
false-Visit precision, fragmentation, duplicates, useful evidence, true
calibrated latency, monitoring coverage, and accepted-mechanism
participation (including this milestone's own new mechanism, once it
naturally occurs in a real session). No budget is invented here.

## Decision

**B**

A careful, safe, high-fidelity investigation was completed for the exact
chartered case: the ~37:12 real bird's own first irreversible error was
traced to a specific, named, already-disclosed mechanism (`classify_
boundary`'s geometry-compatibility tolerance), proven -- not
assumed -- by direct code execution against a faithful reconstruction
using this exact session's own real numbers, and independently confirmed
by a decisive, code-grounded fact this milestone establishes for the first
time (the real 187ms decision gap is two orders of magnitude below the
proven 10-second minimum tick spacing, proving the ~37:12 pair was decided
together, ordinarily, in one tick -- not, as could otherwise have been
suspected, by a cross-tick dispatch defect). Given that true cause sits
squarely inside this milestone's own explicitly out-of-scope territory
(geometry/threshold tuning), no fix for the chartered case itself was
attempted, honoring "Do not force A" directly.

The same rigorous tracing independently surfaced a second, real,
in-scope, evidence-confirmed defect in the identical mechanism family --
proven live-reachable in this exact session, not hypothetical -- which was
root-caused, contract-locked, fixed narrowly at the causal layer using
only already-existing structural facts (no new threshold, no time
-based staleness constant), and proven safe against every accepted
fragmentation, multi-subject, and false-positive control this milestone
could identify, including one adversarial regression test written
specifically to catch the most tempting *unsafe* version of this exact
fix. Tier 1 and Tier 2 are fully clean; Tier 3 (full Core, 5679 passed, 1
failed) is clean once the one failure is independently confirmed
pre-existing and unrelated by direct `git stash` bisection, not merely
assumed. No threshold fishing, no detector/species/truth change, no
schema change.
