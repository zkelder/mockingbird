# Tracklet Visit-episode assembly contract

Status: Observation Engine v2 Stage 6.19 engineering-workflow contract.
Independent of, and composes unchanged with,
[sustained-visit-continuity-contract.md](sustained-visit-continuity-contract.md)
(Stage 6.16) and [reviewed-visit-truth-contract.md](reviewed-visit-truth-contract.md)
(Stage 6.17). Supersedes the *approach* (never the diagnosis) of the
uncommitted, failed Stage 6.18 `episode_boundary.py` experiment.

## Problem

Stage 6.18 tried to fix Visit-level fragmentation and incorrect merges by
changing the *tracker's own* episode-boundary logic. Real reviewed evidence
proved this is a single mechanism being asked to serve two opposite goals at
once, and it cannot honestly serve both:

- **attempt-3**: one genuine ~5-minute feeder visit. Widening tracker
  tolerance (or making negative-evidence bookkeeping more honest, as Stage
  6.18 did) either still fragments it, or risks weakening the exact
  hard-negative protection that keeps attempt-2's persistent clutter from
  becoming a false Visit.
- **session-04**: reviewed appearances B and C, ~16.2s apart, genuinely
  separate. The same widened tolerance that rescues attempt-3 lets weak
  detector/tracker evidence bridge straight across this real gap.

Stage 6.18's own real-CUDA acceptance run confirmed the tension precisely:
fixing attempt-3 fragmentation regressed it further (18→20) and did not
resolve session-04's merge (stayed at 1) -- see
`data/field-acceptance/2026-08-08-stage6.18-episode-boundary/FINAL-REPORT.md`
(uncommitted, local). Its own "characterization for the next attempt" named
the fix this stage implements: distinguish "brief interruption inside a
continuous appearance" from "genuine departure" using **geometry stability
and evidence density across the gap**, not count/elapsed-time alone -- as a
layer *above* the tracker, not a further change to it.

**Track lifetime and Visit lifetime are separate concepts.** The tracker
stays conservative, bounded, and allowed to fragment. A higher-level
`VisitEpisodeAssembler` decides whether adjacent confirmed tracklets belong
to one reviewed appearance.

## Why a separate layer, not a smarter tracker

`ProviderNeutralFrameTracker` decides *frame-by-frame*, forward-only, with no
knowledge of what comes next. It cannot know that a track it is about to
lose will be picked up again 3 seconds later by a near-identical box, or that
a track it is about to bridge across a 16-second gap is actually a different
subject arriving. Both facts are only knowable by looking at *both* tracklets
at once, after they exist -- which is exactly what a tracker cannot do while
it is still deciding one frame at a time, and exactly what an assembler,
operating on already-finalized tracklets, can. Keeping this a separate,
later, optional pass is also why it is safe: it can be wrong without ever
corrupting the tracker's own bounded, already-validated behavior, and it can
be disabled entirely with zero effect on every existing consumer.

## Pipeline

```
FramePackets -> DetectionObservations -> conservative TrackUpdates/tracklets
             -> VisitEpisodeAssembler -> shadow AssembledVisitProposal
```

`mockingbird/observation/visit_episode_assembler.py` is a new, pure module
(no filesystem, network, CUDA/ONNX Runtime/OpenCV, or product-repository
import -- structurally enforced the same way every sibling Stage 6.x
decision module already is). It does not replace, subclass, or wrap
`ProviderNeutralFrameTracker`; it consumes only already-emitted `TrackUpdate`
facts.

## Tracklet contract

`Tracklet` (frozen, immutable) is the only unit `assemble_visit_episodes`
accepts: a provider-neutral summary of one *finalized, confirmed* track
generation, containing only facts needed for Visit assembly. No
implementation-specific tracker object leaks into it, and it never carries
species identity (only `broad_class`, exactly like every other Stage 6.x
fact).

Built by `build_tracklets(track_updates, *, stream_id, ...)`, which groups
already-emitted `TrackUpdate`s by `generation_id` and keeps only generations
whose terminal update reached `lifecycle_state == "confirmed"` (i.e. its
final "ended" update carries `lifecycle_state == "ended"` -- see
`frame_tracker._terminate`). A generation the tracker itself never confirmed
(terminal `lifecycle_state == "rejected"`) is out of scope: the tracker's own
confirmation bar already judged it insufficient evidence, and revisiting
that judgment here would be exactly the "redesign tracker confirmation" this
stage must not do.

Fields: `generation_id`, `stream_id`, `broad_class`, `start_offset_ms`/
`end_offset_ms`, `start_bounding_box`/`end_bounding_box`, `geometry_envelope`
(union box across the tracklet's life), `terminal_reason`, `track_ids`,
`supporting_frame_ids`, `source_capture_frame_ids`, `connection_segment_ids`
(from an optional caller-supplied frame->segment lookup -- Stage 6.19 adds no
new segment-membership mechanism, it reads the same `connection_segment_id`
timing fact `replay._reconnect_metrics` already reads), `evidence_candidate_
ids` (from an optional caller-supplied generation->evidence lookup),
`strong_detector_frame_count`/`weak_detector_frame_count`/`tracker_supported_
frame_count`/`negative_detector_frame_count`/`detector_skipped_frame_count`,
`detector_confirmation_count`/`tracker_support_count`/`confidence`,
`last_strong_detector_offset_ms` (Stage 6.16's own "graduated" anchor, reused
verbatim), `zone_id` (`None` unless a caller supplies one -- there is still no
Zone concept upstream of this pipeline), `ambiguous_start`.

### Two small additive `TrackUpdate` fields

`negative_detector_frame_count` vs. `detector_skipped_frame_count` -- "a
detector-negative interval is separation evidence, a detector-skipped gap is
not" -- cannot be told apart from `support_state="temporarily_lost"` alone;
that value means "not currently matched," whether or not the detector even
ran this frame. The tracker's own `observe(frame, detections, detector_ran=)`
parameter already knows the answer every frame; it was simply never carried
onto the emitted fact. `TrackUpdate.detector_ran: bool = False` (defaulted,
purely additive) fixes that with zero behavior change: threaded through
every existing `_update`/`_terminal_update` call site in
`frame_tracker.observe`/`finalize`/`note_reconnect_boundary` with the exact
value already in scope there (`False` only for the two synthetic
non-per-frame call sites, `note_reconnect_boundary`'s boundary marker and
`finalize`'s end-of-replay marker -- honest, since no detector evaluation
happened for either).

`TrackUpdate.ambiguous_start: bool = False` mirrors the tracker's own
already-computed `_is_ambiguous_reentry` result at the moment a generation
began, carried onto every update of that generation so a consumer inspecting
only the terminal update still sees it -- feeds `Tracklet.ambiguous_start`,
one of the ambiguity facts a proposal's `limitation_facts` can disclose.

Neither field changes tracker association, confirmation, or termination
decisions in any way -- both are pure, backward-compatible observability
additions (48+120 pre-existing frame-tracker/frame-driven/reconnect/replay
tests pass completely unmodified; see the final report).

## Assembly decision contract

`classify_boundary(earlier, later, config) -> BoundaryDecision` classifies
one pair of temporally-adjacent tracklets. Order-independent (swaps its
arguments first if called reversed) and a pure function of the two
tracklets' own facts plus `VisitAssemblyConfiguration` -- never an absolute
path, one feeder geometry, a specific Visit id, species identity, or
wall-clock time.

1. **Structural incompatibility** (`incompatible`, never even a close call):
   different `stream_id`; temporal overlap (`later.start_offset_ms <
   earlier.end_offset_ms` -- two confirmed tracklets active at once are two
   simultaneous/crossing subjects or an upstream tracker-association
   artifact, either way not this layer's call, matching "do not redesign
   tracker association"); `broad_class` mismatch; a known, differing
   `zone_id` on both sides (an unknown `zone_id` on either side decides
   nothing, mirroring `replay._zone_score`'s own existing neutral-unknown
   convention).
2. **Explicit separation evidence** (`keep_separate`): `earlier.
   terminal_reason == "negative_interval_reentry"` -- the tracker itself
   already confirmed absence (genuine, repeated, detector-evaluated negative
   frames) right at this boundary; or incompatible geometry across the gap
   (below); or a gap beyond `ambiguous_gap_ms` even with compatible
   geometry.
3. **Positive continuity** (`merge_same_visit`): gap `<= merge_gap_ms`,
   compatible geometry, and `earlier` is not "graduated and stale" (below).
4. **Ambiguity** (`ambiguous_boundary`): compatible geometry, no explicit
   separation evidence, but the gap exceeds the confident-merge window, or
   `earlier` is graduated-and-stale. Never guessed into a merge.

**Historical rationale, preserved, still correct as far as it goes:** rule 1
above is a deliberate, historically-justified conservative boundary -- this
layer genuinely cannot tell "two simultaneous real subjects" apart from "one
tracker-association artifact," and guessing wrong in either direction is
worse than the current behavior (fabricating false continuity, or silently
merging two different animals into one identity). It is not, and has never
been, an implementation bug.

**Downstream consequence, now a v0.1 release-gate item:** 2026-08-19 field
evidence traced real duplicate/fragmented Visits directly to this rule
(one real sighting producing three Visits with three different species
labels; a separate two-simultaneous-birds encounter producing zero Visits)
-- see
[end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)
§7. That resulting duplicate/fragmentation *behavior* is classified as a
current v0.1 correctness gap (see "Multi-subject Visit correctness" under
Gate A in [roadmap.md](roadmap.md)), even though the design decision that
causes it remains sound as originally reasoned. Any future fix must resolve
concurrent-subject disambiguation safely (or preserve the ambiguity all the
way to review) rather than simply relaxing this rule -- naively merging
temporally-overlapping tracklets would reintroduce exactly the fabricated-
continuity failure mode this rule exists to prevent. This contract, together
with [candidate-visit-authority-contract.md](candidate-visit-authority-contract.md),
is the design authority a future **Multi-Subject Visit Assembly & Review
v1** milestone extends; do not design that milestone as a parallel system.

### Concurrent-sibling detection (Multi-Subject Visit Assembly & Review v1, Phase 1)

Implemented 2026-08-19, per
[multi-subject-visit-assembly-review-v1.md](multi-subject-visit-assembly-review-v1.md)'s
own "Implementation phases" §1. `AssembledVisitProposal.concurrent_sibling_
proposal_ids` names every other proposal this one was classified
`incompatible`/`temporal_overlap` against specifically -- the "two
simultaneous/crossing subjects" case rule 1 above already, deliberately,
never tries to resolve, now positively recorded rather than only counted.
Computed inside the same tracklet-comparison loop `assemble_visit_episodes`
already runs, using the same bookkeeping shape `ambiguous_adjacent_
proposal_ids` already established (see "Ambiguity policy" below) -- not a
new temporal subsystem, and structurally disjoint from it: a pair's single
`BoundaryDecision` can never populate both fields, since `_temporal_overlap`
is evaluated before any ambiguous-boundary logic runs.

**Purely additive and inert on its own.** This field changes nothing about
which tracklets merge, which proposals result, or which are admitted --
verified directly: every existing test in `test_visit_episode_assembler.py`
passes unchanged, and a real 2026-08-19 field fixture replayed through the
Perception Replay Regression Harness before/after this change classified
every admission/assembly metric `equivalent`. **Phase 2 (Event-reuse
persistence, schema 36) shipped 2026-08-20** -- `_create_candidate_visit_
locked` now reuses an already-persisted sibling's `event_id` instead of
minting a new one when this field is non-empty (see "Candidate Visit
semantics" in
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
for the persistence-side mechanism); this field itself, and this module,
remain completely unchanged by that consumption.

### Bounded gap windows -- reused, not invented

`merge_gap_ms` (default 15000ms) reuses `TrackerConfiguration.maximum_weak_
support_span_ms`'s own already-justified Stage 6.16 default ("long enough to
bridge a real subject's early confidence dips"). `ambiguous_gap_ms` (default
45000ms) is an explicitly-derived 3x multiple of it, mirroring the exact
derivation Stage 6.16 used to derive that same 15000ms number from
`maximum_unsupported_detector_ms` (5000ms) in the first place. Real attempt-3
gaps between fragments of the one true visit are bounded by the tracker's own
`maximum_unsupported_detector_ms`/`maximum_frame_gap_ms` (observed up to
~10.4s per the Stage 6.16 fragmentation characterization) -- comfortably
inside `merge_gap_ms`. Session-04's real B/C gap (16.2s) sits just past it,
inside the ambiguous window -- which conservatively does not merge either,
satisfying the hard requirement through the *ambiguity* policy, not a
coincidental hard cutoff (see "Real offline acceptance" below for what
actually decides that specific case).

### Bounded geometry compatibility -- reused, not invented

A base allowance (box jitter, shaped like the tracker's own per-frame
`maximum_centroid_distance`) plus a per-second allowance (an implied bounded
motion speed), capped -- deliberately wider than one frame-to-frame
association step, since this spans a real multi-second-to-tens-of-seconds
gap. Size-change tolerance (0.65) is `ReconnectBridgeConfig.maximum_
reconnect_size_change_ratio` (0.5) widened slightly for the same reason.

### Evidence freshness -- the mechanism that actually protects session-04

A tracklet that ever showed a genuinely strong detector hit
(`Tracklet.has_strong_evidence`, Stage 6.16's "graduated" concept reused
verbatim) is normally a *more* trustworthy merge anchor. But if its own last
strong hit is more than `graduated_freshness_bound_ms` (5000ms, reusing
`maximum_unsupported_detector_ms` again) before it ended, it is coasting on
the tracker's own widened bounded-tolerance mechanism, not fresh confidence
-- `_graduated_and_stale`. A confident merge should not be built on stale
credibility alone; such a boundary downgrades to `ambiguous_boundary` instead
even when gap and geometry alone would look mergeable. A tracklet that never
showed strong evidence at all ("provisional") has no stale claim to begin
with and is judged purely on the ordinary gap/geometry rule -- this is
deliberate: real attempt-3 tracklets are overwhelmingly provisional (per
Stage 6.16's own finding, only 4 raw detections in the whole ~600s session
ever reached strong threshold), so this mechanism does not suppress
attempt-3's own fragmentation reduction while still catching session-04's
specific failure shape (see "Real offline acceptance").

### Skipped vs. negative gaps

`Tracklet.negative_detector_frame_count` (detector ran, found nothing usable
for this exact track) and `detector_skipped_frame_count` (detector never
inspected this frame at all) are kept as separate, honest facts on every
tracklet. Only the former is ever treated as separation-adjacent evidence
(via `terminal_reason == "negative_interval_reentry"`, which the tracker
itself already only reaches from genuine `detector_ran=True` frames); an
idle-cadence gap never contributes to a `keep_separate` decision by itself.

## Ambiguity policy

When evidence cannot safely distinguish one fragmented Visit from two nearby
separate Visits, `assemble_visit_episodes` **never guesses a merge**.
`ambiguous_boundary` tracklet pairs are kept in **separate** assembled
proposals (the conservative default this contract documents), and the
relationship is not silently discarded: each resulting proposal's
`ambiguous_adjacent_proposal_ids` names the other proposal(s) it was
ambiguous against, and `limitation_facts` records the same honestly. A
consumer that wants to treat ambiguous-adjacent proposals as one candidate
Visit downstream can do so from this recorded fact; this stage does not
decide that for them.

## Episode finality (Visit Continuity / Provisional Admission Fix v1)

The ambiguity policy above protects two proposals that are *both already
visible in the same assembly pass*. It cannot protect against the shape a
real 2026-08-10 fresh field cohort surfaced instead: a caller (`engine_
runtime.py`, `candidate_visit_authority_cli.py`) that reruns
`assemble_visit_episodes` periodically over a still-live stream's
accumulated tracklets can observe a *singleton* proposal, hand it to Stage 7
authority, and only later see a same-encounter continuation tracklet
finalize and merge into what is now a *different, larger* proposal (a
different `proposal_id`, since that id depends on the constituent set) --
with nothing connecting the two, because the continuation tracklet did not
exist yet at the moment the first proposal was assembled. Real evidence:
candidate-004 (`{frame-track-0043}`) was admitted, then candidate-005
(`{frame-track-0043, frame-track-0045}` -- a strict superset) was admitted
56 seconds later for what a human reviewer's own visual inspection
confirmed was one continuous ~75-second encounter.

`assemble_visit_episodes` accepts an additional, optional, purely-additive
`known_horizon_ms: int | None` parameter -- a source-offset-relative fact
(never a wall-clock read, matching every other bound in this module) naming
the latest point in the stream the caller has actually observed so far.
When supplied, every resulting `AssembledVisitProposal.continuation_pending`
reuses exactly `ambiguous_gap_ms` -- the identical bound the algorithm
above already uses to decide whether a later tracklet could still be
compared against a given episode's own tail -- to report whether *this*
proposal's own tail boundary might still change:
`continuation_pending = (known_horizon_ms - proposal.end_offset_ms) <=
ambiguous_gap_ms`. Omitted (the default), every proposal reports
`continuation_pending=False`, preserving the exact prior behavior for every
existing caller (`replay.py`, every offline/already-complete recording,
every pre-existing test).

`candidate_visit_authority.evaluate_candidate_authority` blocks a
`continuation_pending` proposal (`blocked_continuation_pending`) immediately
after it checks `ambiguous_boundary` -- a fact the assembler already
computed, never reconstructed in the authority gate, structurally identical
to how the ambiguity check already works. Unlike every other blocked
outcome, this one is retryable (`candidate_visit_authority.RETRYABLE_
OUTCOMES`): the identical `proposal_id`, re-evaluated later with nothing
else changed but more of the stream having been observed, can honestly
reach a different outcome once its own boundary finalizes. A live/trial
caller that reruns assembly on a timer (`engine_runtime._EngineSession.
_run_assembly_tick`, `candidate_visit_authority_cli._run_assembly_tick`)
supplies the latest source-relative offset it has actually processed --
advancing on every analyzed frame regardless of whether that frame carried
a track, so a genuinely quiet period still lets a pending episode's own
window eventually close -- and never permanently marks a `blocked_
continuation_pending` proposal as attempted, so it is naturally re-offered
on a later tick. The session-ending tick omits the horizon entirely
(`finalize=True`): once the stream itself has ended, no continuation could
ever arrive, so nothing is left waiting forever.

This is a *timing* correction, not a new merge rule: `classify_boundary`'s
own gap/geometry/evidence-freshness logic is completely unchanged (every
pre-existing replay/synthetic scenario above is unaffected, since none of
them supply `known_horizon_ms`). The fix only changes *when* an
already-correct merge decision is allowed to become an irreversible product
write -- deliberately not a post-persistence deduplication pass: candidate
authority is never made responsible for reconstructing tracker/assembler
semantics a second time (see "Persistence adapter boundary" in
docs/candidate-visit-authority-contract.md).

## Ambiguous boundary arbitration (Admission Recall Investigation + Conditional Fix v1)

Episode finality (above) fixed a proposal's own *tail* boundary being
locked in too early. It did not fix a distinct, real defect a ~94-minute
accepted daily-use field session (2026-08-17) found in the *ambiguity*
policy itself: unlike `blocked_continuation_pending`,
`blocked_ambiguous_boundary` was a genuinely **permanent** verdict with no
recovery path at all -- for any proposal, forever, regardless of what else
happened afterward. Direct evidence from that session's own counterfactual
ledger:

- A confirmed, single-generation proposal carrying a genuine detection at
  0.795 confidence -- above `strong_detection_threshold` (0.7), the
  strongest single detection anywhere in the session's retained lineage --
  was permanently blocked because a temporally-adjacent (1.7s gap),
  near-identical-geometry sibling generation (0.590 confidence) made the
  pair `ambiguous_boundary` (`stale_graduated_evidence`: the 0.795 hit
  happened early in the first generation's life, more than
  `graduated_freshness_bound_ms` before it ended). Both proposals were
  attempted exactly once and blocked forever; neither ever became a Visit.
- A cleanly-merged, 14-generation, ~5.3-minute episode (13 successful
  internal `merge_same_visit` decisions -- `visit-episode:b410c58dfa...`)
  was *also* permanently `blocked_ambiguous_boundary`, in a single attempt,
  despite its own extensive internal evidence, because it inherited an
  ambiguous link established by its very first constituent generation
  against an earlier, unrelated fragment before the other 13 generations
  ever merged in. Tracing the ledger further found this is a general
  mechanism, not a one-off: 29 of the session's own `blocked_ambiguous_
  boundary` proposals were later *superseded* (a continuation tracklet
  merged into their own constituent set, producing a new, larger proposal
  id) -- and the superseding, larger proposal inherited the identical
  permanent block every time, regardless of how much additional clean
  evidence it had absorbed.

The root cause is structural, not a threshold: `assemble_visit_episodes`
records an `ambiguous_adjacent_proposal_ids` link the moment a tracklet
first fails to merge with a still-open episode while also being ambiguous
against it (see "Ambiguity policy," above) -- and that link stays attached
to *whatever episode index it was recorded against*, for the rest of that
same assembly pass, even as that episode's own membership keeps growing
through entirely unrelated, unambiguous merges later in the same pass. The
authority gate then treats *any* non-empty `ambiguous_adjacent_proposal_ids`
as an unconditional, non-retryable block (`RETRYABLE_OUTCOMES` never
included it). Nothing in the original design distinguished "this specific
boundary is still genuinely uncertain" from "this boundary was uncertain
once, before either side had finished accumulating its own evidence."

### Fix: bounded, deterministic arbitration once a cluster stops growing

`candidate_visit_authority.resolve_ambiguous_boundary_arbitration` is a
new, pure, per-tick function: given the current tick's full, freshly
-assembled proposal set (every `AssembledVisitProposal`, not only the ones
not yet attempted), it classifies every proposal with non-empty `ambiguous_
adjacent_proposal_ids` into exactly one of:

- **deferred**: this proposal, or a sibling it lists in its own `ambiguous_
  adjacent_proposal_ids` that is still present this tick, is itself
  `continuation_pending` -- a same-encounter continuation tracklet has not
  yet had its own chance to arrive and change the picture (exactly the
  reason `continuation_pending` exists one layer below). The caller must
  not attempt this proposal at all this tick, and must not mark it
  permanently attempted -- identical in spirit to how an ordinary
  `continuation_pending` proposal is already retried, without inventing a
  new outcome code for this case.
- **resolved winner**: every member of this proposal's own cluster (itself
  and every live, listed sibling) has stopped growing. This proposal is the
  single best-evidenced member of that cluster -- ranked by detector
  confidence (`confidence_evidence.max_confidence`), then constituent
  evidence volume (`len(constituent_generation_ids)`), then a deterministic
  `proposal_id` tiebreak, so a genuine tie never produces an ambiguous
  arbitration result itself. The caller attempts this proposal with
  `evaluate_candidate_authority(..., ambiguous_boundary_resolved=True)`,
  letting it bypass the ambiguity block (still subject to every other check
  -- lineage, rate limits, the quality gate -- unchanged).
- **untouched**: empty `ambiguous_adjacent_proposal_ids` (not ambiguous at
  all), or a stable cluster member that is not the winner. Attempted
  exactly as before this fix -- the loser(s) of a resolved cluster still
  correctly land on `blocked_ambiguous_boundary`, permanently.

At most one Visit is ever admitted per ambiguous cluster: the original
duplicate-Visit protection the ambiguity policy existed to provide is
fully preserved, since a resolved cluster's non-winning member(s) are never
given the bypass. Arbitration is bounded and does not cascade: if the
single winner is later rejected by an unrelated, later gate (missing
evidence, the quality gate), the next-best sibling is *not* automatically
promoted -- a deliberate, disclosed scope boundary (cascading arbitration
would let progressively weaker evidence keep trying until something is
admitted, exactly the "meaningless dark patch" the quality gate exists to
prevent).

### Chain scope: bounded connected component (Ambiguous-Boundary Transitive
### Fragmentation Closure v1, 2026-08-20)

Arbitration originally compared each proposal only against its own
immediately-listed `ambiguous_adjacent_proposal_ids`, never a transitive
closure across a longer chain (A-B ambiguous, B-C ambiguous, A-C never
directly compared) -- a deliberate, disclosed scope boundary at the time,
reasoned as bounded and rare (at most one extra Visit per chain, never a
runaway cascade). Real root-cause confirmation (2026-08-20, reproduced
deterministically against the real, unmodified assembler and arbitration
code -- no live field session required) proved this scope boundary was the
direct mechanism behind "one real bird -> 2-3 Visits with inconsistent
species labels": `A` and `C` each independently won arbitration against
their own shared neighbor `B` in their own local pairwise comparison
(which lost both comparisons and stayed permanently blocked, exactly as
designed), even though `A` and `C` were never compared to each other
directly -- admitting two Visits for one connected, still-unresolved
chain. A second, more subtle instance of the identical root cause: a
component's own "winner" could be attempted even while a transitively- but
not directly-linked member was still `continuation_pending` (still
growing), since the old scope only ever checked a proposal's own
immediately-listed siblings for growth, never the whole chain.

`candidate_visit_authority.resolve_ambiguous_boundary_arbitration` now
resolves the full bounded *connected component* reachable from each
proposal via `ambiguous_adjacent_proposal_ids` links (`_ambiguous_
component`: an iterative, never-recursive traversal) before ranking a
single winner or deciding the component must defer -- contained entirely
within that one function, no schema change, no new live incremental pass,
no new outcome code. A proposal id absent from the current tick's own
supplied proposal set remains a dead end exactly as before (a vanished
sibling was, and still is, treated as no rival). The graph is always
undirected by construction (`assemble_visit_episodes` only ever records an
ambiguous link in both directions at once), so the resulting component --
and therefore the winner -- is identical regardless of traversal order or
the caller's own input order. At most one winner is now ever selected per
connected component, not per locally-listed pairwise set, closing the "two
Visits from one chain" defect while preserving the original "at most one
Visit per ambiguous cluster" intent exactly.

### Interaction with concurrent siblings

A connected ambiguous component and a `concurrent_sibling_proposal_ids`
relationship (see "Concurrent-sibling detection," above) never share an
edge: `classify_boundary` returns exactly one `BoundaryDecisionKind` per
pair, and a pair's `_temporal_overlap` check is evaluated before any
ambiguous-boundary logic runs, so the two link sets `assemble_visit_
episodes` builds (`ambiguous_links`/`sibling_links`) are already
structurally disjoint before arbitration ever runs -- and the arbitration
traversal itself has no knowledge of `concurrent_sibling_proposal_ids` at
all (`ProposalArbitrationFacts` does not expose that field). A proposal
genuinely concurrent with a member of an ambiguous chain -- for example
A-B-C sequentially ambiguous while C is also concurrent with a
simultaneous, distinct subject D -- resolves independently: A/B/C
arbitrate as one component exactly as any other chain, and D, having no
`ambiguous_adjacent_proposal_ids` of its own, is never visited by the
traversal and is attempted through the ordinary, unmodified single-subject
path regardless of the chain's own outcome -- Phase 2's own Event-reuse
grouping is unaffected either way. Verified directly against the real,
unmodified assembler: `test_transitive_component_and_concurrent_sibling_
do_not_cross_contaminate` in `tests/test_candidate_visit_authority.py`.

`engine_runtime._EngineSession._run_assembly_tick` and `candidate_visit_
authority_cli.py`'s own mirrored tick both call `resolve_ambiguous_
boundary_arbitration` once per tick, over the same full proposal set
`known_horizon_ms`/`finalize` already use -- no second live incremental
pass, no product-database read, no new schema (`ambiguous_adjacent_
proposal_ids_json` was already persisted on the candidate ledger row before
this fix; a reviewer or diagnostic can already tell an admitted Visit was
an arbitration winner from that existing field being non-empty, without a
new column). See docs/candidate-visit-authority-contract.md's own
"Ambiguity policy" for the authority-gate side of this fix.

## Bounded component decision horizon (Sustained-Activity Visit Admission Starvation & Stop-Finalization Correctness v1)

Ambiguous boundary arbitration (above) fixed a *resolved* component's own
winner from being lost to a stale pairwise-only scope. It did not bound
*how long* a component may keep deferring while it is not yet resolved --
a real, previously-undocumented defect Representative Daylight Gate A Field
Acceptance v4 found and precisely root-caused: a real ~112-minute session of
sustained, near-continuous multi-bird feeder activity produced
`candidates_created == 0` for the *entire* live session, not merely a longer
delay than usual.

**Mechanism.** Individual episodes are already correctly bounded:
`maximum_episode_duration_ms` caps one episode's own span (forcing a new
chain to start once a single glued sequence gets too long), and
`ambiguous_gap_ms` caps how long any one proposal's own tail may stay
`continuation_pending` once it genuinely stops growing (see "Episode
finality," above). Neither bound, individually, is the gap. The gap is
structural, one layer up: when sustained real activity keeps producing new
tracklets, a fresh chain that starts right after a `maximum_episode_
duration_ms` split reliably becomes `ambiguous_adjacent_proposal_ids`-linked
to the chain it just superseded -- the identical "genuine multi-way merge
tie" mechanism `assemble_visit_episodes` already uses for any two
simultaneously-eligible merge targets (see "Chain scope," above, for the
transitive-closure traversal this then feeds into). Because a connected
component's own currently-active tail is, by construction, still growing
for as long as raw activity continues, `resolve_ambiguous_boundary_
arbitration`'s own "defer the whole component if any member is still
growing" rule (correct and necessary for a component that might still
change shape) never gets a chance to fire for the *entire remaining life of
the session* -- the component keeps absorbing every subsequent activity
-driven episode fragment, transitively, all the way back to the start of
the session, and the single currently-growing tail holds the entire
historical prefix hostage. This is the third, most severe member of the
family "Episode finality"/"Ambiguous boundary arbitration" above already
document (2026-08-10 duplicate; 2026-08-17 permanent block; 2026-08-19
cache eviction) -- the first case where an entire live session admitted
zero Visits, and the first where the family's own designed resolution
mechanism did not fire at all, rather than merely producing a downstream
side effect.

**Fix: a bounded decision horizon, reusing the existing episode-span bound.**
`candidate_visit_authority.resolve_ambiguous_boundary_arbitration` accepts
two new, optional, purely-additive parameters: `known_horizon_ms` (the same
source-offset-relative "latest point in the stream the caller has actually
observed" fact `assemble_visit_episodes` already takes) and `maximum_
component_pending_ms`. Omitted (the default), a still-growing component
defers *unconditionally* -- the exact pre-fix behavior every prior test/
caller already relies on, unchanged. When both are supplied, a component
whose own oldest member (by `start_offset_ms`) has been waiting longer than
`maximum_component_pending_ms` is force-arbitrated even though some member
is still `continuation_pending`: the identical `_arbitration_key` ranking
still selects the single best-evidenced member (by detector confidence,
then evidence volume, then a deterministic tiebreak) -- forcing *when* a
component may be decided never changes *how* its winner is chosen, and
every non-winning member is still attempted normally and still blocks,
exactly preserving "at most one Visit per ambiguous cluster."

`engine_runtime._EngineSession._run_assembly_tick` is the one real
production caller: it passes its own live `known_horizon_ms` (unconditionally,
not gated on `finalize` -- inert there regardless, since every proposal
already reports `continuation_pending=False` unconditionally once
`finalize=True`, so no component can ever be "still growing" at that
point) and `engine_runtime._MAXIMUM_COMPONENT_PENDING_MS`, which reuses
`VisitAssemblyConfiguration.maximum_episode_duration_ms` (1,200,000ms/20
minutes) *verbatim* -- the identical, already-calibrated "how long may one
grouping decision legitimately stay open" bound this codebase already uses
for one episode's own span, not a newly-invented magic number (see this
codebase's own established convention against that, cited on
`VisitAssemblyConfiguration` itself). `candidate_visit_authority_cli.py`'s
own separate, bounded (10-minute/3-candidate) engineering-trial tick is
deliberately left passing neither parameter: its own hard cap means it can
never run long enough to reach a 20-minute decision horizon in the first
place, so the pre-fix unconditional-defer behavior there is inert, not a
gap.

**A forced decision loses no evidence.** A member cut off mid-growth by a
forced decision is not discarded: a tracklet that later continues merging
onto its own tail produces a new, larger, never-before-attempted proposal
id on a later tick (a different constituent set, hence a different hash --
see "Episode finality," above, for why this is already how every
continuation is re-offered), which is then evaluated, and potentially
force-decided again, through this identical, unmodified path. This is the
same "one continuous, biologically-real encounter may legitimately become
more than one product Visit once it runs long enough" tradeoff `maximum_
episode_duration_ms` already makes for one episode's own span -- extended
here to the connected-component level for the identical reason: a bounded,
understandable grouping policy that never lets sustained real activity
prevent every admission, without inventing a new Visit model or a
behavior-analysis research project.

## VisitProposal lineage

`AssembledVisitProposal`: deterministic `proposal_id` (`sha256` of the
assembler version plus the sorted constituent generation ids -- depends on
nothing but semantic tracklet identity, never an absolute path, PID, or
wall-clock value; repeated assembly of the same tracklets, in any input
order, reproduces a byte-identical id and proposal set -- see determinism
tests), all constituent `track_generation_id`s and `track_id`s, all `source_
capture_frame_ids`, temporal span, `broad_class`, `zone_id` when supported,
`evidence_candidate_ids`, `assembly_decisions` (the `BoundaryDecision` that
produced each internal merge), `ambiguous_adjacent_proposal_ids`/
`limitation_facts`, `shadow_only=True` always enforced (`__post_init__`
raises otherwise). There is no product Visit write path anywhere in this
module.

`project_to_visit_proposal` is a separate, intentionally lossy adapter onto
the existing, completely unmodified `contracts.VisitProposal`, used only so
the already-proven Stage 6.17 matcher (`replay._match`) can score an
assembled proposal exactly like any other. `AssembledVisitProposal` remains
the authoritative lineage record; the projection exists for metrics reuse
only.

## Critical architectural rule

Nothing in this module reads an absolute filesystem path, assumes one feeder
geometry, references a specific Visit id, uses species identity, reads
wall-clock time, or writes a product record. Every decision is a pure
function of already-supplied `Tracklet` facts and `VisitAssemblyConfiguration`.
`visit_episode_assembler.py` imports nothing from `replay.py`,
`temporal_annotation.py`, `mockingbird.repository`, `mockingbird.api`, or
SQLAlchemy -- the same structural no-product-import test list every other
Stage 6.x pure module is already on.

## Replay integration

`replay.py` gains one new, optional, purely-additive function --
`assemble_visit_episode_report(report, manifest, config=None)` -- called
*after* an ordinary `ReplayRunner.run(...)`, touching no existing code path.
It builds tracklets from the report's own already-collected `track_updates`,
runs `assemble_visit_episodes`, projects the result through
`project_to_visit_proposal`, and re-scores it against the *same* manifest
through the **completely unmodified** `replay._match`. `ReplayRunner.run`
itself is unchanged; every pre-existing report/metric it produces is
byte-identical to before this stage.

The result separates three independent metric groups, on purpose --
tracker-level fragmentation is never hidden merely because assembly repairs
it:

- **Track metrics** (already-existing `ReplayReport.metrics`, unchanged):
  tracks started/confirmed/rejected, tracker fragmentation.
- **Assembly metrics** (new): tracklets input, episode merges, separate
  decisions, ambiguous decisions, assembled proposals.
- **Visit-truth-via-assembly metrics** (new, same shape as the existing
  Visit-level metrics, computed against assembled proposals instead of raw
  per-tracklet ones): expected/matched/recall/precision/fragmentation/
  duplicates/incorrect merges.

## Non-goals honored

No detector/model threshold change. No tracker-policy tuning
(`TrackerConfiguration` is untouched; `frame_tracker.py`'s only changes are
the two additive `TrackUpdate` fields threaded through unchanged control
flow). No reconnect redesign (`reconnect_continuity.py` untouched, 0 lines
changed). No burst changes (`burst_scheduler*.py` untouched). No species
inference. No product Visit creation. No Stage 7 authority. No UI.

See the final acceptance report for synthetic-test results, real attempt-2/
attempt-3/session-03/session-04 before/after numbers, evidence-lineage
compatibility, and the structural no-write proof.
