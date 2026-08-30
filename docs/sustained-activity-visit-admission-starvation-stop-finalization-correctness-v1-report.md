# Sustained-Activity Visit Admission Starvation & Stop-Finalization Correctness v1

Status: **Classification A**. A real,
previously-undocumented P0 (sustained genuine wildlife activity producing zero admitted
Visits for an entire live session) is root-caused, deterministically reproduced pre-fix,
and fixed with a bounded-decision-horizon contract; the companion stop-finalization
question the field report left open is independently root-caused and fixed; two further
real, materially-contributing defects this milestone's own investigation found along the
way (evidence-cache selection order, and evidence-generation scoping) are fixed narrowly
alongside it, each with its own deterministic RED/GREEN proof.

## Starting state

- Branch `main`, accepted HEAD `b0b080f883eed5d117f3a728693ddc263f45fd77` (the
  reconciliation commit for Representative Daylight Gate A Field Acceptance v4).
  Confirmed to match the governing instruction's own stated starting state exactly
  before any edit.
- Schema `v58`, unchanged by this milestone -- no model/migration change.
- Worktree safety: the seven preserved untracked detector files were hashed at session
  start and re-verified byte-identical at multiple points throughout (including
  immediately after a `git stash`/`git stash pop` bisection cycle); `uv.lock` and every
  other untracked file were likewise confirmed untouched. No other writer was found
  active in this worktree (every other local Claude Code process sharing this
  `cwd` was confirmed present only as an idle/reading session via `/proc/<pid>/cwd`,
  never mid-write).
- Field evidence motivating this milestone: Representative Daylight Gate A Field
  Acceptance v4 (`docs/representative-daylight-gate-a-field-acceptance-v4-report.md`) --
  a real, live ~112-minute Observation session against the real reference Camera Node,
  99.78% independent-recorder coverage, 593 confirmed MDv5 animal-class tracks
  (96.6% at one feeder location, near-continuous for effectively the entire session),
  a separate ground-mammal sighting -- yet `candidates_created` stayed at exactly 0 for
  the whole session, and the real Observation stop did not visibly rescue anything
  either (`stopped_reason: user_stopped`, still 0 nine minutes later). That report
  precisely root-caused the *symptom* to stage 6 (admission/arbitration) by direct code
  reading, but explicitly stopped short of a fix ("comparable in scope to a full
  milestone... does not belong inside a field-measurement session") and left the
  stop-finalization question as an open, disclosed, unresolved sub-question.

## Reproducer

### Continuous-activity starvation (RED)

`tests/test_candidate_visit_authority.py::test_arbitration_still_defers_forever_without_a_horizon`
pins the exact pre-fix behavior directly against the real, unmodified
`resolve_ambiguous_boundary_arbitration`: a two-member ambiguous component whose tail
keeps growing defers forever, at any age. At the real production call site,
`tests/test_engine_runtime.py::test_sustained_activity_does_not_starve_admission_forever`
drives `_EngineSession._run_assembly_tick` -- the actual code path -- across 26
simulated minutes of continuous, merge-eligible activity (`known_horizon_ms` advanced in
large, purely source-offset-relative steps, never a real wall-clock wait). Against the
pre-fix `engine_runtime.py` (which called `resolve_ambiguous_boundary_arbitration(proposals)`
with no horizon), this reproducer fails deterministically:
`candidates_created_after_each_tick` stays `[0, 0, 0, ..., 0]` across all 25 ticks, with
`suppressed == {'blocked_continuation_pending': 21}` and zero `blocked_ambiguous_boundary`
-- direct, precise confirmation that the whole connected component (a frozen pre-split
chain plus its still-growing successor) was silently deferred every tick, never even
reaching the authority gate.

### Stop-finalization race (RED)

`tests/test_engine_runtime.py::test_stop_does_not_race_the_kill_switch_against_a_still_finalizing_session`
drives the real `ObservationEngineSessionManager.start`/`.stop()` orchestration boundary
-- never a bypassed helper -- forcing the exact race deterministically via a controllable
blocking transport (`_BlockingAfterFirstBatchTransport`, gated by a `threading.Event`)
plus a monkeypatched, tiny `_STOP_JOIN_TIMEOUT_SECONDS`. Against the pre-fix `stop()`
(which reverted authority to shadow unconditionally the instant its own bounded
`thread.join()` returned, whether or not the thread had actually finished), this fails
deterministically: `status.state == "stopped"` even though the background thread is
still genuinely blocked (never reached its own finalize tick), proving the *false claim
of success* directly; releasing the blocking event afterward and letting the real
finalize tick run then sees `blocked_shadow_mode` for the confirmed track, so the
candidate is silently lost forever -- confirming the exact mechanism, not just its
symptom.

## Root cause

The two defects are **structurally distinct**, confirmed by direct code tracing, not
assumed to share one cause:

### 1. Continuous-activity starvation

Individual episodes are already correctly bounded:
`VisitAssemblyConfiguration.maximum_episode_duration_ms` (1,200,000ms/20min) caps one
episode's own span, and `ambiguous_gap_ms` (45,000ms) caps how long any one proposal's
own tail may stay `continuation_pending` once it genuinely stops growing. Neither bound
is wrong; the gap is one layer up. When sustained real activity keeps producing new
tracklets, a fresh chain that starts right after a `maximum_episode_duration_ms` split
reliably becomes `ambiguous_adjacent_proposal_ids`-linked to the chain it just
superseded (the identical "genuine multi-way merge tie" mechanism
`assemble_visit_episodes` already uses for any two simultaneously-eligible merge
targets -- verified directly: a 26-minute synthetic single-subject sequence produces
exactly this shape, confirmed by direct `assemble_visit_episodes` inspection). Because a
connected component's own currently-active tail is, by construction, still growing for
as long as raw activity continues,
`candidate_visit_authority.resolve_ambiguous_boundary_arbitration`'s own "defer the
whole component if any member is still growing" rule -- correct and necessary for a
component that might still change shape -- never gets a chance to fire for the entire
remaining life of the session. The component keeps absorbing every subsequent
activity-driven episode fragment, transitively, all the way back to the start of the
session, and the single currently-growing tail holds the entire historical prefix
hostage. **Nothing previously bounded how long the connected component as a whole may
keep deferring while its own tail keeps being refreshed by new activity** -- exactly
the "no forced-decision policy" gap the governing brief's own §7 anticipated.

### 2. Stop-finalization

`_EngineSession.stop()`'s own kill-switch revert-to-shadow ran unconditionally the
instant its own bounded `thread.join()` returned -- on a genuine timeout (the
background thread still alive) exactly as much as on a real completion. This raced the
background thread's own, separately-correct `_run_async` teardown sequence (tracker
finalize -> forced-decision finalize tick -> that same thread's own already-existing
revert-to-shadow, all in the right order, on one thread, using one repository
connection). `ProductRepository.create_candidate_visit_from_proposal` re-reads
authority mode fresh from the repository by design (the actual, concurrency-safe
authority boundary) -- so a finalize tick that reached it *after* the caller thread's
premature revert saw `shadow` and silently discarded an already-force-decided,
genuinely valid candidate as `blocked_shadow_mode`. The two defects are related (the
second becomes far more likely to manifest under exactly the sustained-load conditions
the first produces, since a busier session's own finalize tick has more work to do,
and a starved session that never got to try admitting anything mid-session pushes the
*entire* backlog into the one finalize-tick attempt) but are **not the same
mechanism**: defect 1 exists even for a single, short, otherwise-ordinary session that
happens to run long; defect 2 exists even for a session with only one, single-generation
pending proposal, independent of arbitration entirely (verified by a dedicated,
minimal reproducer with no ambiguous component at all).

### 3 & 4. Two further real defects found during evidence-cache investigation (brief §13)

Directly investigating whether the 128-entry evidence-byte cache "materially
contributes to starvation or poor forced-finalization behavior" (as instructed, not
generic cache tuning) found it does, via two distinct, narrow, pre-existing mechanisms
-- neither previously reachable because nothing ever forced a decision on a
proposal old/large enough to expose them before this milestone's own fix #1 existed:

- **Selection-order bias.** `evidence_scoring.score_proposal_evidence` truncates its
  candidate pool to `EvidenceScoringBounds.max_candidates` (16) using a plain,
  offset-first order, computed *before* checking whether each candidate's own bytes are
  still present in the caller's cache. For a long-lived, forced-decision proposal with
  far more than 16 retained evidence-candidate facts, the "earliest 16" are also the
  ones most likely already evicted -- even when byte-backed evidence exists later in the
  very same proposal.
- **Generation-scope bias.** `visit_episode_assembler.project_to_visit_proposal` set
  `track_generation_id` to only the proposal's *first* constituent generation, and
  `score_proposal_evidence` uses that field, when non-`None`, to exclude any candidate
  whose own capture-time `track_generation_id` differs. Real `EvidenceCandidate`s are
  tagged with the specific constituent generation active at capture time (verified
  directly in `camera_node_live.py`/`frame_driven_provider.py`), so for any
  multi-generation-merged proposal, real evidence from every generation but the first
  was silently invisible to scoring -- for an ordinary short merge this rarely mattered
  in practice; for a 240-generation forced-decision proposal it was the *dominant*
  blocking mechanism in this milestone's own worst-case reproduction (a single evidence
  candidate, guaranteed evicted, was the entire eligible pool regardless of the
  selection-order fix above).

Direct, deterministic reproduction against the real, unmodified scorer and the real,
bounded 128-entry cache: a forced-decision winner with real, byte-backed evidence for
115 of its own 240 constituent generations still reached `blocked_missing_evidence`
before these two fixes -- the identical "zero Visits" symptom recurring one gate later,
even after defects 1 and 2 above were fixed.

## Contract

**Bounded-decision rule.** A still-growing ambiguous component defers unconditionally,
exactly as before, *unless* its own oldest member (by `start_offset_ms`) has been
waiting longer than `maximum_component_pending_ms` -- reused verbatim from
`VisitAssemblyConfiguration.maximum_episode_duration_ms` (20 minutes), not a new
magic number. Once forced, the winner is selected only from members that have
themselves already stopped growing (a still-growing member would fail the
authority gate's own continuation-pending check regardless of the ambiguity bypass),
ranked by *recency* rather than confidence (the one proposal-level fact this pure
module can reason about without cache awareness that predicts evidence-cache
survival). A forced decision changes *when* a component is decided, never *how* its
winner is chosen among the eligible pool, and never loses a cut-off member's own
continuation -- a later tracklet that keeps merging onto it produces a new, larger,
never-before-attempted proposal id, offered again through the identical path.

**Stop-finalization rule.** The background thread's own natural teardown -- forced
-decision finalize tick, then authority revert, in that order, on one thread -- is
authoritative. The external `stop()` caller's own defensive revert-and-`_state`
transition only fires once that thread has *actually* finished (covers both the
ordinary fast case and a session that failed before ever reaching the repository at
all); if the bounded join times out against a genuinely still-running thread, `stop()`
does nothing further and honestly reports `_state == "stopping"` plus
`advanced["stop_finalization_pending"] = True`, relying on the daemon thread's own
unconditional `finally` chain to guarantee eventual completion and self-correct the
status once it finishes.

## Implementation

- `src/mockingbird/observation/candidate_visit_authority.py`: `ProposalArbitrationFacts`
  gains `start_offset_ms`/`end_offset_ms`. `resolve_ambiguous_boundary_arbitration`
  gains optional `known_horizon_ms`/`maximum_component_pending_ms` (both `None` by
  default -- every pre-existing call site untouched); new `_component_pending_horizon_exceeded`
  and `_forced_decision_key` (recency-first ranking, used only for a forced decision).
- `src/mockingbird/observation/engine_runtime.py`: new `_MAXIMUM_COMPONENT_PENDING_MS`
  constant (reads `VisitAssemblyConfiguration().maximum_episode_duration_ms`, one
  source of truth); `_run_assembly_tick` passes both new arbitration parameters.
  `_EngineSession.stop()` restructured to make the join's own outcome (thread actually
  finished vs. timed out) authoritative for whether the external revert runs; `_run()`'s
  own `finally` clears `stop_finalization_pending` unconditionally once the thread truly
  completes.
- `src/mockingbird/observation/evidence_scoring.py`: new `_candidate_selection_order`
  (byte-availability-first, falling back to the unmodified `_candidate_order`), used for
  the `max_candidates` truncation sort.
- `src/mockingbird/observation/visit_episode_assembler.py`: `project_to_visit_proposal`
  sets `track_generation_id=None` for a proposal merged from more than one constituent
  generation (unchanged for the single-generation case).
- Documentation: `docs/tracklet-visit-assembly-contract.md` ("Bounded component decision
  horizon"), `docs/candidate-visit-authority-contract.md` ("Stop-finalization ordering,"
  "Selection-priority and generation-scope fixes"), `docs/multi-frame-evidence-scoring-contract.md`
  ("Boundary," "Bounds") all updated as the authoritative contract record.

## Non-regression

- **Ordinary short activity / gaps**: the full pre-existing `test_visit_episode_assembler.py`
  (69 tests, including every gap-threshold/merge/keep-separate/ambiguous scenario) and
  `test_candidate_visit_authority.py`'s pre-existing continuation-pending/ambiguity suite
  pass unchanged -- every new parameter defaults to `None`/inert.
- **Multi-subject**: `test_field_derived_multi_subject_stress_replay` (105 simulated
  minutes, two simultaneously-active, geometrically-distinct subjects sharing one joint
  tick history) asserts zero cross-subject contamination across every forced decision
  made; the full pre-existing concurrent-sibling/transitive-component test families in
  both `test_visit_episode_assembler.py` and `test_candidate_visit_authority.py` pass
  unchanged.
- **Evidence**: `test_natural_arbitration_still_prefers_confidence_unaffected_by_recency_fix`
  proves a naturally-resolved component's ranking is byte-for-byte unaffected;
  `test_candidate_order_is_unchanged_when_every_candidate_has_bytes`/
  `..._when_no_media_is_supplied` prove the evidence-scoring fix is a complete no-op
  whenever nothing has been evicted (every pre-existing scoring scenario); the full
  pre-existing `test_observation_evidence_scoring.py` (15 tests) and
  `test_observation_replay.py`/`test_observation_replay_report_contract.py`/
  `test_replay_visit_episode_assembly.py` (the consumers of `project_to_visit_proposal`
  most at risk from the `track_generation_id` change) all pass unchanged.
- **Duplicates**: `duplicate_count == 0` asserted directly in the stress replay;
  `test_repeated_stop_while_finalization_is_still_pending_is_safe` proves a second
  `stop()` call mid-finalization never double-reverts or double-creates; the full
  pre-existing `test_concurrent_candidate_visit_persistence_reliability.py` and
  `test_candidate_visit_repository.py` idempotency suites pass unchanged.

## Long-run replay

`test_field_derived_multi_subject_stress_replay` (the brief's §18 field-derived stress
replay): 105 simulated minutes, two simultaneous subjects, one joint tick history
(never two runs stitched together), real bounded assertions rather than an assumed
precise count:

- Logical Visit-group count: bounded (`0 < count <= 20` asserted and held) across both
  subjects combined -- non-starved, non-exploded.
- Maximum admitted-episode lifetime: bounded by `_MAXIMUM_COMPONENT_PENDING_MS` plus one
  tick's worth of slack -- no giant infinite episode.
- Duplicates: 0.
- Evidence: every created candidate carries real, non-empty persisted evidence.
- First admission landed within 25 simulated minutes (never deferred toward the
  session's end) -- proving this is a live-session fix, not merely a session-end
  rescue.
- Real elapsed time: well under the test's own 90-second bound despite the fully
  unmodified, from-scratch-every-tick assembler re-running over an ever-growing
  track-update history -- no O(n^2)-class blowup observed at this scale.

`test_forced_decision_winner_survives_the_real_bounded_evidence_cache` runs the
identical 26-minute single-subject shape against the *real*, bounded
`_MAX_CACHED_BURST_BYTES` cache (not the unbounded local test double the other
sustained-activity tests deliberately use to isolate arbitration from cache concerns)
-- the worst-case adversarial shape this investigation's own probe first found the
evidence-scoring gap through -- and confirms `candidates_created == 1`,
`blocked_missing_evidence` absent.

## Validation

**Tier 1** (new tests, this milestone): 22 new tests across
`tests/test_candidate_visit_authority.py` (9), `tests/test_engine_runtime.py` (10),
`tests/test_observation_evidence_scoring.py` (3) -- every one independently confirmed
RED against the pre-fix code (either by direct construction before the fix existed, or,
for the two evidence-scoring findings, by a throwaway probe script reproducing the exact
mechanism before formalizing it as a committed test) and GREEN after.

**Tier 2** (brief §21's named subsystem list): 505 passed, 0 failed, 0 skipped across 22
files -- `test_engine_runtime.py`, `test_candidate_visit_authority.py`,
`test_visit_episode_assembler.py`, `test_candidate_visit_authority_acceptance.py`,
`test_candidate_visit_adapter.py`, `test_candidate_visit_repository.py`,
`test_candidate_visit_review_workflow.py`, `test_candidate_visit_rollback.py`,
`test_concurrent_candidate_visit_persistence_reliability.py`,
`test_counterfactual_lineage.py`, `test_multi_camera_concurrent_runtime.py`,
`test_scene_confusor.py`, `test_scene_confusor_repository.py`,
`test_candidate_quality_gate.py`, `test_observation_evidence_scoring.py`,
`test_observation_evidence_comparison.py`, `test_dashboard_observation_engine_truth.py`,
`test_replay_visit_episode_assembly.py`, `test_unified_observation_status.py`,
`test_observation_unified_api.py`, `test_observation_session_api.py`,
`test_observation_replay.py`, `test_observation_replay_report_contract.py`.

**Tier 3** (full Core, `scripts/verify_core.py` / `pytest -m "not slow"`): one clean run,
5238 passed, 3 failed, 3 skipped, 23 deselected, 11 xfailed, 36m03s. Every failure
independently confirmed unrelated, not merely assumed from precedent:

- `test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary`
  and `::test_human_correction_updates_place_biodiversity_intelligence_correctly` --
  the identical, already-repeatedly-documented pre-existing
  `historical_status`/`seen_before`-vs-`new` classification defect (zero code-path
  relationship to this milestone's own changes -- confined entirely to
  `src/mockingbird/observation/`). Confirmed unrelated directly, not by citation alone:
  `git stash` of every one of this milestone's own changes reproduced the byte-identical
  failure (`assert 'seen_before' == 'new'`) against the untouched pre-milestone
  baseline; restored cleanly afterward (worktree/preserved-file integrity re-verified).
- `test_transport_worker.py` -- **not** a single consistent failure: three consecutive
  full-file runs against the exact same, unmodified current code produced three
  different outcomes (`test_sticky_diagnostic_set_on_protocol_incompatibility_and_
  cleared_on_next_success` failed once, `test_retryable_failure_returns_item_to_failed_
  retryable_and_eventually_succeeds` failed once, all 7 passed once) -- direct,
  conclusive proof of a genuine, pre-existing, timing-sensitive flake (the file's own
  `_run_until` helper polls a fixed-timeout `asyncio` condition, inherently susceptible
  to real host scheduling jitter) rather than a deterministic regression. Confirmed
  structurally unrelated too: zero import relationship between `mockingbird_node`
  (the package this test file exercises) and any file this milestone changed (all
  confined to `mockingbird.observation`), and the identical file passed cleanly (7/7)
  in a direct baseline bisection. Matches this exact test file's own prior,
  independently-documented flake precedent (Concurrent Candidate Visit Persistence
  Reliability v1's own Tier 3 run).

Zero regressions attributable to this milestone across all three.

`ruff check`: zero new findings on every changed file, confirmed by direct
clean-baseline bisection for the two pre-existing findings in `tests/test_engine_runtime.py`
(both present identically in the unmodified `HEAD` blob, unrelated to this milestone's
own additions).

## Self-review

One adversarial pass after GREEN, per the governing brief's §22 checklist:

- **Starvation under another state**: traced the bound (per-member `continuation_pending`
  resolution is itself already bounded independent of arbitration) and confirmed the
  `stable_members`-non-empty precondition is a narrow, self-correcting transitional
  window (at most a tick or two), never a permanent stall.
- **Duplicate Visit creation**: no new path found; existing idempotency mechanism
  untouched and re-verified.
- **Over-fragmentation**: bounded by design and by test (a handful of Visits per long
  run, never one per tick or one per generation).
- **Multi-subject regression**: directly tested under forced decisions specifically
  (not just under the pre-existing, unforced case); zero contamination found.
- **Stop race**: this *was* the concrete finding -- fixed, with a deterministic
  reproducer proving both the pre-fix false-success claim and the post-fix honest,
  eventually-consistent behavior.
- **Async flush race**: none beyond the stop race found; the background thread's own
  teardown sequence was already correctly ordered before this milestone (finalize tick
  before its own revert) -- only the *external* caller's redundant revert needed fixing.
- **Evidence loss**: this *was* the concrete finding -- adversarially probed with a
  worst-case (240-generation, high-confidence-but-ancient winner) construction against
  the real bounded cache, found two real, distinct, narrow mechanisms, fixed both,
  proved the combined fix closes the exact worst case that motivated the investigation.
- **Idempotency**: unmodified mechanism; re-verified via existing suite plus a new
  repeated-stop-mid-finalization test.
- **Long-run memory**: no new unbounded structure introduced; `attempted_proposal_ids`
  growth from more distinct forced-decision outcomes over a long session is
  negligible (hundreds of short strings at most over many hours), and the 65/105
  -minute replay tests ran within their own bounded real-time budgets with no
  quadratic-looking slowdown observed.

No further findings surfaced; per the brief's own instruction, a second broad audit was
not conducted.

## Remaining risks

Concrete, disclosed, none release-blocking for *this* milestone's own scope:

- The evidence-scoring fixes (selection order, generation scope) are real, and were
  found and closed narrowly, but the underlying `EvidenceScoringBounds.max_candidates`
  (16) bound itself was not re-examined or re-tuned -- this milestone deliberately
  fixed *which* candidates are prioritized within that bound, not the bound's own size,
  per the governing brief's explicit "do not use this milestone for generic cache
  tuning" instruction. A pathologically evidence-dense, multi-hour single component
  could in principle still exhaust even the now-correctly-prioritized pool; not
  observed at any scale this milestone tested.
- `candidate_visit_authority_cli.py`'s own separate, bounded (10-minute/3-candidate)
  engineering-trial tick was deliberately left calling `resolve_ambiguous_boundary_arbitration`
  with neither new parameter: its own hard cap means it can never run long enough to
  reach a 20-minute decision horizon, so the pre-fix unconditional-defer behavior there
  is inert, not a live gap -- noted for completeness, not treated as in-scope.
- The `stop_finalization_pending` status flag is a new, narrow, internal/diagnostic
  field (not a new user-facing UI surface, per the brief's own §14/§15 boundary); no
  frontend surface was added or changed to display it.
- This milestone's own reproducers and replay tests are all deterministic, synthetic,
  and offset-driven (never a real wall-clock wait or real hardware) -- per the brief's
  own explicit §20 instruction not to run a real field session tonight. The next
  daylight field session (see below) is the remaining, necessary real-world proof.

## Field-rerun requirement

The next representative daylight Gate A session against a busy, real feeder Stream must
prove, with real evidence:

1. `candidates_created` is no longer stuck at exactly 0 across a full busy session --
   at least one admission occurs well before the session's natural end, not only at
   stop.
2. The admitted Visit count is bounded and coherent for the observed activity level
   (not zero, not an explosion of tiny duplicate Visits).
3. A real Observation stop against genuinely still-pending work completes honestly --
   either synchronously with the pending work resolved, or (if the join genuinely times
   out under real load) the status correctly reports `stop_finalization_pending` and
   later settles to a fully-resolved state with the real evidence intact, not silently
   dropped.
4. `blocked_shadow_mode` and `blocked_missing_evidence` occurrence counts, checked
   against the counterfactual ledger, to directly confirm neither of the two
   evidence/race defects this milestone fixed recurs under real load.
5. Multi-subject correctness (several birds at once, as this exact field session
   already showed) holds through to real admitted Visits, not just through assembly --
   the one dimension the motivating field session could not exercise at all, since
   nothing there ever reached admission.

## Decision

**Classification A.** Both primary defects (continuous-activity starvation;
stop-finalization) are independently root-caused with direct code evidence,
deterministically reproduced RED against the real, unmodified pre-fix code at the real
production call site (never a bypassed helper), and fixed with a
bounded-decision-horizon/ordering-correctness contract that reuses existing,
already-calibrated bounds rather than inventing new magic numbers. Two further real,
materially-contributing defects surfaced during the required evidence-cache
investigation were found, precisely diagnosed, and fixed narrowly, each with its own
RED/GREEN proof and non-regression coverage -- not deferred, since leaving either
unfixed would have meant this milestone's own acceptance bar ("the system emits
bounded, useful Visits rather than zero," under realistic, bounded-cache conditions) was
not actually met despite the primary fix. No duplicate-Visit, fragmentation, or
multi-subject regression found. Tier 1/2 clean (527 passed across the new tests plus
the brief's own named subsystem list, 0 failed). Tier 3 (full Core) clean apart from
three independently, directly (not merely by precedent) confirmed pre-existing/flaky
failures with zero code-path relationship to this milestone's own changes.
