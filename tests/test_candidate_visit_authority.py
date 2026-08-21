"""Stage 7 pure candidate-Visit authority gate (see
docs/candidate-visit-authority-contract.md). No product-repository or database
import anywhere in this test file's own import graph -- `candidate_visit_authority`
must stay a pure decision module exactly like `reconnect_continuity`/
`session_timeline`/`visit_episode_assembler`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import permutations

import pytest

from mockingbird.observation.candidate_visit_authority import (
    AuthorityLimits,
    AuthorityState,
    ObservationAuthorityMode,
    evaluate_candidate_authority,
    resolve_ambiguous_boundary_arbitration,
)
from mockingbird.observation.contracts import EMPTY_CONFIDENCE_EVIDENCE
from mockingbird.observation.visit_episode_assembler import (
    AssembledVisitProposal,
    BoundaryDecision,
    Tracklet,
    assemble_visit_episodes,
)


NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)


def _proposal(
    *,
    proposal_id: str = "visit-episode:fixture",
    ambiguous_adjacent_proposal_ids: tuple[str, ...] = (),
    source_capture_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    supporting_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    constituent_generation_ids: tuple[str, ...] = ("gen-1",),
    continuation_pending: bool = False,
) -> AssembledVisitProposal:
    return AssembledVisitProposal(
        proposal_id=proposal_id,
        stream_id="stream-a",
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=5000,
        constituent_generation_ids=constituent_generation_ids,
        constituent_track_ids=("track-1",),
        supporting_frame_ids=supporting_frame_ids,
        source_capture_frame_ids=source_capture_frame_ids,
        evidence_candidate_ids=("evidence-1",),
        assembly_decisions=(),
        ambiguous_adjacent_proposal_ids=ambiguous_adjacent_proposal_ids,
        continuation_pending=continuation_pending,
    )


def _state(
    *,
    mode: ObservationAuthorityMode = ObservationAuthorityMode.candidate_visit,
    activation_boundary_at: datetime | None = NOW - timedelta(minutes=1),
    candidates_created_in_session: int = 0,
    candidates_created_in_trailing_hour: int = 0,
) -> AuthorityState:
    return AuthorityState(
        mode=mode,
        activation_boundary_at=activation_boundary_at,
        candidates_created_in_session=candidates_created_in_session,
        candidates_created_in_trailing_hour=candidates_created_in_trailing_hour,
    )


# --- 1. Default authority is shadow -----------------------------------------


def test_default_authority_mode_is_shadow() -> None:
    assert AuthorityState.default_mode() == ObservationAuthorityMode.shadow


# --- 2. Shadow mode blocks candidate creation -------------------------------


def test_shadow_mode_blocks_candidate_creation() -> None:
    decision = evaluate_candidate_authority(
        _proposal(), observed_at=NOW, state=_state(mode=ObservationAuthorityMode.shadow),
    )
    assert decision.outcome == "blocked_shadow_mode"
    assert not decision.should_create


# --- 3. Explicit candidate authority allows exactly one create -------------


def test_candidate_authority_allows_creation_when_all_gates_pass() -> None:
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=_state())
    assert decision.outcome == "create"
    assert decision.should_create
    assert decision.proposal_id == "visit-episode:fixture"


# --- 6. One proposal cannot create two candidates (already_exists honored) -


def test_already_existing_candidate_is_idempotent_regardless_of_mode() -> None:
    decision = evaluate_candidate_authority(
        _proposal(), observed_at=NOW, state=_state(mode=ObservationAuthorityMode.shadow), already_exists=True,
    )
    assert decision.outcome == "idempotent_repeat"
    assert not decision.should_create


def test_already_existing_candidate_is_idempotent_when_authority_active() -> None:
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=_state(), already_exists=True)
    assert decision.outcome == "idempotent_repeat"


# --- 7 / 8. Activation boundary ---------------------------------------------


def test_proposal_observed_before_activation_boundary_is_blocked() -> None:
    state = _state(activation_boundary_at=NOW + timedelta(seconds=1))
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=state)
    assert decision.outcome == "blocked_pre_activation"


def test_proposal_observed_after_activation_boundary_may_create() -> None:
    state = _state(activation_boundary_at=NOW - timedelta(seconds=1))
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=state)
    assert decision.outcome == "create"


def test_no_activation_boundary_recorded_blocks_creation() -> None:
    """Authority mode alone is never sufficient without a recorded activation
    fact -- guards against a hypothetical future bug that flips `mode` without
    also recording `activation_boundary_at`."""
    state = _state(activation_boundary_at=None)
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=state)
    assert decision.outcome == "blocked_pre_activation"


def test_proposal_observed_exactly_at_activation_boundary_may_create() -> None:
    state = _state(activation_boundary_at=NOW)
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=state)
    assert decision.outcome == "create"


# --- 22. Invalid lineage fails safely ---------------------------------------


def test_missing_all_frame_lineage_blocked_as_invalid_lineage() -> None:
    """Real Stage 7 live-trial finding: a genuine live Camera Node session
    never populates `source_capture_frame_ids` (that identity only exists
    for frames a human has already retained through temporal-review
    capture -- see docs/candidate-visit-authority-contract.md, "Lineage
    validity"). Only a proposal with *no* frame identity at all -- neither
    field -- is genuinely invalid."""

    decision = evaluate_candidate_authority(
        _proposal(source_capture_frame_ids=(), supporting_frame_ids=()), observed_at=NOW, state=_state(),
    )
    assert decision.outcome == "blocked_invalid_lineage"


def test_missing_source_capture_frame_ids_alone_is_not_invalid_lineage() -> None:
    """The exact real live-session shape: no reviewed-source identity, but
    real ordinary per-track frame identity -- eligible to create, never
    blocked for lacking a field that live sessions structurally never
    populate."""

    decision = evaluate_candidate_authority(
        _proposal(source_capture_frame_ids=(), supporting_frame_ids=("live-frame-1", "live-frame-2")),
        observed_at=NOW, state=_state(),
    )
    assert decision.outcome == "create"


def test_missing_supporting_frame_ids_alone_is_not_invalid_lineage() -> None:
    """The reviewed-replay shape: reviewed-source identity present even
    when, unusually, the ordinary field is not -- still eligible."""

    decision = evaluate_candidate_authority(
        _proposal(source_capture_frame_ids=("reviewed-frame-1",), supporting_frame_ids=()),
        observed_at=NOW, state=_state(),
    )
    assert decision.outcome == "create"


# --- 24 / 25. Session + hourly budgets --------------------------------------


def test_session_candidate_limit_enforced() -> None:
    limits = AuthorityLimits(max_candidates_per_session=2)
    state = _state(candidates_created_in_session=2)
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=state, limits=limits)
    assert decision.outcome == "blocked_session_limit"


def test_session_candidate_limit_allows_up_to_bound() -> None:
    limits = AuthorityLimits(max_candidates_per_session=2)
    state = _state(candidates_created_in_session=1)
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=state, limits=limits)
    assert decision.outcome == "create"


def test_hourly_candidate_limit_enforced() -> None:
    limits = AuthorityLimits(max_candidates_per_hour=5)
    state = _state(candidates_created_in_trailing_hour=5)
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=state, limits=limits)
    assert decision.outcome == "blocked_hourly_limit"


# --- 29. Ambiguous assembly stays blocked according to explicit policy -----


def test_ambiguous_adjacent_proposal_is_blocked_not_guessed() -> None:
    decision = evaluate_candidate_authority(
        _proposal(ambiguous_adjacent_proposal_ids=("visit-episode:other",)),
        observed_at=NOW,
        state=_state(),
    )
    assert decision.outcome == "blocked_ambiguous_boundary"
    assert not decision.should_create


# --- 30. Visit Continuity / Provisional Admission Fix v1 -------------------
# (see docs/tracklet-visit-assembly-contract.md "Episode finality" and the
# fresh-cohort candidate-004/005 field defect this stage fixes.)


def test_continuation_pending_proposal_is_blocked_not_admitted_early() -> None:
    decision = evaluate_candidate_authority(
        _proposal(continuation_pending=True), observed_at=NOW, state=_state(),
    )
    assert decision.outcome == "blocked_continuation_pending"
    assert not decision.should_create


def test_continuation_pending_false_is_the_default_and_does_not_block() -> None:
    decision = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=_state())
    assert decision.should_create


def test_continuation_pending_outcome_is_the_only_retryable_one() -> None:
    """The live/trial loop's own retry bookkeeping (`engine_runtime.py`,
    `candidate_visit_authority_cli.py`) relies on this set being exactly
    `{"blocked_continuation_pending"}` -- every other outcome is a
    permanently resolved fact about a given `proposal_id`."""
    from mockingbird.observation.candidate_visit_authority import RETRYABLE_OUTCOMES

    assert RETRYABLE_OUTCOMES == frozenset({"blocked_continuation_pending"})


def test_ambiguity_is_checked_before_continuation_pending() -> None:
    """When a proposal is somehow both -- an explicit same-pass ambiguity
    conflict is a stronger, more specific signal than "not yet final" --
    the more specific outcome is reported."""
    decision = evaluate_candidate_authority(
        _proposal(ambiguous_adjacent_proposal_ids=("visit-episode:other",), continuation_pending=True),
        observed_at=NOW,
        state=_state(),
    )
    assert decision.outcome == "blocked_ambiguous_boundary"


# --- 31. Ambiguous boundary arbitration (Admission Recall Investigation +
# Conditional Fix v1) -- see "Ambiguous boundary arbitration" in
# docs/tracklet-visit-assembly-contract.md. A real ~94-minute accepted
# daily-use session found `blocked_ambiguous_boundary`, unlike
# `blocked_continuation_pending`, was a genuinely permanent verdict with no
# recovery path at all -- including for a confirmed, above-strong
# -detection-threshold (0.795) real detection, and for a well-evidenced,
# cleanly-merged 14-generation episode that kept absorbing continuation
# evidence without ever being reconsidered. These tests exercise the gate's
# own `ambiguous_boundary_resolved` bypass and the pure, per-tick
# cross-proposal decision (`resolve_ambiguous_boundary_arbitration`) a
# caller uses to decide when it is safe to assert that bypass.
# -----------------------------------------------------------------------


def test_ambiguous_boundary_resolved_bypasses_the_block_when_asserted() -> None:
    decision = evaluate_candidate_authority(
        _proposal(ambiguous_adjacent_proposal_ids=("visit-episode:other",)),
        observed_at=NOW,
        state=_state(),
        ambiguous_boundary_resolved=True,
    )
    assert decision.should_create
    assert decision.reason == "eligible_assembled_proposal_ambiguous_boundary_arbitration_winner"


def test_ambiguous_boundary_resolved_true_is_a_no_op_when_not_ambiguous() -> None:
    """The bypass only ever matters when the proposal is actually ambiguous
    -- asserting it for an ordinary, unambiguous proposal must not change
    the outcome or reason string at all."""
    ordinary = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=_state())
    with_bypass = evaluate_candidate_authority(
        _proposal(), observed_at=NOW, state=_state(), ambiguous_boundary_resolved=True,
    )
    assert ordinary == with_bypass
    assert with_bypass.reason == "eligible_assembled_proposal"


def test_ambiguous_boundary_resolved_does_not_defeat_continuation_pending() -> None:
    """Arbitration is only ever safe to assert once a proposal's own
    cluster has fully stabilized (see `resolve_ambiguous_boundary_
    arbitration`); if a proposal is somehow both ambiguous-resolved *and*
    still `continuation_pending`, the gate still correctly blocks on that
    more fundamental, unrelated fact -- the bypass is narrowly scoped to
    step 5 (the ambiguity check) only, never a general override."""
    decision = evaluate_candidate_authority(
        _proposal(ambiguous_adjacent_proposal_ids=("visit-episode:other",), continuation_pending=True),
        observed_at=NOW,
        state=_state(),
        ambiguous_boundary_resolved=True,
    )
    assert decision.outcome == "blocked_continuation_pending"


def test_ambiguous_boundary_resolved_still_respects_rate_limits() -> None:
    """Bypassing the ambiguity check does not bypass every later check --
    an arbitration winner is still an ordinary proposal for every other
    purpose, including session/hourly candidate budgets."""
    decision = evaluate_candidate_authority(
        _proposal(ambiguous_adjacent_proposal_ids=("visit-episode:other",)),
        observed_at=NOW,
        state=_state(candidates_created_in_session=50),
        ambiguous_boundary_resolved=True,
    )
    assert decision.outcome == "blocked_session_limit"


def _arbitration_proposal(
    proposal_id: str,
    *,
    ambiguous_adjacent_proposal_ids: tuple[str, ...] = (),
    continuation_pending: bool = False,
    max_confidence: float | None = None,
    constituent_generation_ids: tuple[str, ...] = ("gen-1",),
) -> AssembledVisitProposal:
    # `AssembledVisitProposal.__post_init__` requires exactly one
    # `BoundaryDecision` per internal merge (`len(constituent_generation_
    # ids) - 1`); these tests only ever compare *counts* of constituent
    # generations (evidence volume), never inspect the decisions
    # themselves, so bare placeholders satisfy the invariant without
    # implying anything about geometry/timing.
    filler_decisions = tuple(
        BoundaryDecision(f"gen-{index}", f"gen-{index + 1}", "merge_same_visit", "test_fixture")
        for index in range(len(constituent_generation_ids) - 1)
    )
    base = replace(
        _proposal(
            proposal_id=proposal_id,
            ambiguous_adjacent_proposal_ids=ambiguous_adjacent_proposal_ids,
            continuation_pending=continuation_pending,
        ),
        constituent_generation_ids=constituent_generation_ids,
        assembly_decisions=filler_decisions,
    )
    return replace(base, confidence_evidence=replace(EMPTY_CONFIDENCE_EVIDENCE, max_confidence=max_confidence))


def test_arbitration_ignores_proposals_with_no_ambiguity() -> None:
    result = resolve_ambiguous_boundary_arbitration([_arbitration_proposal("p1"), _arbitration_proposal("p2")])
    assert result.resolved_winner_ids == frozenset()
    assert result.deferred_ids == frozenset()


def test_arbitration_picks_the_higher_confidence_stable_sibling() -> None:
    """Direct reproduction of the real field pair: two mutually-ambiguous,
    fully-stable, confirmed generations 1.7s apart with near-identical
    geometry -- one carries a genuine 0.795 strong detection, the other
    0.590. The stronger one must win; the weaker must not also win."""
    strong = _arbitration_proposal("p-strong", ambiguous_adjacent_proposal_ids=("p-weak",), max_confidence=0.795)
    weak = _arbitration_proposal("p-weak", ambiguous_adjacent_proposal_ids=("p-strong",), max_confidence=0.590)
    result = resolve_ambiguous_boundary_arbitration([strong, weak])
    assert result.resolved_winner_ids == frozenset({"p-strong"})
    assert result.deferred_ids == frozenset()


def test_arbitration_defers_when_self_still_growing() -> None:
    strong = _arbitration_proposal(
        "p-strong", ambiguous_adjacent_proposal_ids=("p-weak",), max_confidence=0.9, continuation_pending=True,
    )
    weak = _arbitration_proposal("p-weak", ambiguous_adjacent_proposal_ids=("p-strong",), max_confidence=0.1)
    result = resolve_ambiguous_boundary_arbitration([strong, weak])
    # Neither may be arbitrated yet: `p-strong` might still grow (a
    # continuation tracklet could still merge into it, changing the
    # evidence comparison this arbitration would otherwise make final).
    assert result.resolved_winner_ids == frozenset()
    assert result.deferred_ids == frozenset({"p-strong", "p-weak"})


def test_arbitration_defers_when_a_sibling_is_still_growing() -> None:
    """Even a proposal that has itself stopped growing must wait for its
    sibling to stabilize too -- the sibling could still grow stronger,
    changing which one should win."""
    stable = _arbitration_proposal("p-stable", ambiguous_adjacent_proposal_ids=("p-growing",), max_confidence=0.5)
    growing = _arbitration_proposal(
        "p-growing", ambiguous_adjacent_proposal_ids=("p-stable",), max_confidence=0.1, continuation_pending=True,
    )
    result = resolve_ambiguous_boundary_arbitration([stable, growing])
    assert result.resolved_winner_ids == frozenset()
    assert result.deferred_ids == frozenset({"p-stable", "p-growing"})


def test_arbitration_never_admits_both_sides_of_a_pair() -> None:
    """The central duplicate-Visit protection this fix must preserve: at
    most one member of a mutually-ambiguous pair is ever a winner,
    regardless of how confidence/evidence compares."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.5)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a",), max_confidence=0.5)
    result = resolve_ambiguous_boundary_arbitration([a, b])
    assert len(result.resolved_winner_ids) <= 1


def test_arbitration_tie_break_is_deterministic() -> None:
    """Equal confidence and equal evidence volume: the `proposal_id`
    tiebreak must still produce exactly one, reproducible winner -- never
    both, never neither, and never a different answer depending on input
    order (`resolve_ambiguous_boundary_arbitration` never sorts its own
    input)."""
    a = _arbitration_proposal("p-aaa", ambiguous_adjacent_proposal_ids=("p-bbb",), max_confidence=0.5)
    b = _arbitration_proposal("p-bbb", ambiguous_adjacent_proposal_ids=("p-aaa",), max_confidence=0.5)
    first = resolve_ambiguous_boundary_arbitration([a, b])
    second = resolve_ambiguous_boundary_arbitration([b, a])
    assert first == second
    assert len(first.resolved_winner_ids) == 1


def test_arbitration_more_constituent_evidence_breaks_a_confidence_tie() -> None:
    thin = _arbitration_proposal(
        "p-thin", ambiguous_adjacent_proposal_ids=("p-rich",), max_confidence=0.5,
        constituent_generation_ids=("gen-1",),
    )
    rich = _arbitration_proposal(
        "p-rich", ambiguous_adjacent_proposal_ids=("p-thin",), max_confidence=0.5,
        constituent_generation_ids=("gen-1", "gen-2", "gen-3"),
    )
    result = resolve_ambiguous_boundary_arbitration([thin, rich])
    assert result.resolved_winner_ids == frozenset({"p-rich"})


def test_arbitration_resolves_transitive_chain_to_a_single_winner() -> None:
    """Ambiguous-Boundary Transitive Fragmentation Closure v1. Supersedes
    the prior disclosed-but-now-closed "local, not transitive" scope
    boundary (see "Chain scope" history in
    docs/tracklet-visit-assembly-contract.md): A-B ambiguous, B-C
    ambiguous, A and C never directly listing each other -- the real shape
    a temporal chain produces, since the assembler only ever compares a
    tracklet against the tail of a still-open episode. Root cause: under
    the prior pairwise-only scope, `p-a` and `p-c` each independently beat
    their shared neighbor `p-b` in their own local comparison and both won
    arbitration -- two admitted Visits for one connected, still-ambiguous
    chain, exactly the "one real bird -> 2-3 Visits" defect this milestone
    closes. The full three-proposal connected component now resolves to
    exactly one winner: the single best-evidenced member of the *whole*
    chain, never of one local pair."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.9)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a", "p-c"), max_confidence=0.2)
    c = _arbitration_proposal("p-c", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.85)
    result = resolve_ambiguous_boundary_arbitration([a, b, c])
    # b loses to both neighbors; a -- the strongest member of the whole
    # connected chain -- is the only winner. c must not also win merely
    # because it was never directly compared against a.
    assert result.resolved_winner_ids == frozenset({"p-a"})
    assert result.deferred_ids == frozenset()


def test_arbitration_transitive_chain_winner_is_order_independent() -> None:
    """The identical A-B-C chain, arbitrated from every possible input
    order, must always agree on the same single winner -- this function
    never sorts its own input, so order-independence must come from the
    algorithm (a deterministic connected-component partition), never from
    incidental input ordering."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.9)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a", "p-c"), max_confidence=0.2)
    c = _arbitration_proposal("p-c", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.85)
    baseline = resolve_ambiguous_boundary_arbitration([a, b, c])
    for order in permutations([a, b, c]):
        assert resolve_ambiguous_boundary_arbitration(list(order)) == baseline
    assert baseline.resolved_winner_ids == frozenset({"p-a"})


def test_arbitration_resolves_four_node_chain_to_a_single_winner() -> None:
    """A-B, B-C, C-D: a longer chain than the minimal 3-node case, still
    resolved as one connected component with exactly one winner -- proves
    the traversal keeps following links rather than stopping after one
    hop beyond the seed proposal."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.3)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a", "p-c"), max_confidence=0.2)
    c = _arbitration_proposal("p-c", ambiguous_adjacent_proposal_ids=("p-b", "p-d"), max_confidence=0.4)
    d = _arbitration_proposal("p-d", ambiguous_adjacent_proposal_ids=("p-c",), max_confidence=0.95)
    result = resolve_ambiguous_boundary_arbitration([a, b, c, d])
    assert result.resolved_winner_ids == frozenset({"p-d"})
    assert result.deferred_ids == frozenset()


def test_arbitration_resolves_independent_ambiguous_components_separately() -> None:
    """Two disjoint ambiguous pairs sharing no proposal must each resolve
    to their own winner, completely independently of the other pair's own
    confidence values -- a bounded component, never a single global
    ranking across every ambiguous proposal this tick."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.9)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a",), max_confidence=0.1)
    c = _arbitration_proposal("p-c", ambiguous_adjacent_proposal_ids=("p-d",), max_confidence=0.2)
    d = _arbitration_proposal("p-d", ambiguous_adjacent_proposal_ids=("p-c",), max_confidence=0.7)
    result = resolve_ambiguous_boundary_arbitration([a, b, c, d])
    assert result.resolved_winner_ids == frozenset({"p-a", "p-d"})
    assert result.deferred_ids == frozenset()


def test_arbitration_component_traversal_ignores_concurrent_sibling_ids() -> None:
    """Multi-Subject Visit Assembly Phase 1/2's `concurrent_sibling_
    proposal_ids` is a structurally distinct relationship (genuinely
    simultaneous, distinct subjects) that this function must never treat
    as an ambiguity edge -- `ProposalArbitrationFacts` does not even
    expose that field, but a real `AssembledVisitProposal` still carries
    it, so traversal must not accidentally reach through it anyway. `p-d`
    shares no `ambiguous_adjacent_proposal_ids` with anyone: it must never
    appear in either result set, and its presence -- deliberately given
    the single highest confidence of the four -- must not change which
    proposal wins the unrelated ambiguous chain."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.9)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a", "p-c"), max_confidence=0.2)
    c = _arbitration_proposal("p-c", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.85)
    d = replace(
        _arbitration_proposal("p-d", max_confidence=0.99),
        concurrent_sibling_proposal_ids=("p-c",),
    )
    result = resolve_ambiguous_boundary_arbitration([a, b, c, d])
    assert result.resolved_winner_ids == frozenset({"p-a"})
    assert "p-d" not in result.resolved_winner_ids
    assert "p-d" not in result.deferred_ids


def test_arbitration_defers_whole_component_when_any_member_is_growing() -> None:
    """The growing member need not be directly adjacent to every other
    component member -- `p-c` here is only ever listed by `p-b`, never by
    `p-a` -- but the whole three-proposal component must still defer: a
    continuation tracklet merging into `p-c` could still reshape the
    entire chain's own evidence comparison, not only `p-b`'s."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.9)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a", "p-c"), max_confidence=0.2)
    c = _arbitration_proposal(
        "p-c", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.85, continuation_pending=True,
    )
    result = resolve_ambiguous_boundary_arbitration([a, b, c])
    assert result.resolved_winner_ids == frozenset()
    assert result.deferred_ids == frozenset({"p-a", "p-b", "p-c"})


def test_arbitration_winner_creates_losers_stay_blocked_in_authority_gate() -> None:
    """End-to-end proof through the real gate a live tick actually calls
    (`engine_runtime._EngineSession._run_assembly_tick`): the resolved
    winner of a 3-node ambiguous chain is admitted; both losers -- even
    `p-c`, never directly compared to the winner `p-a` -- stay permanently
    `blocked_ambiguous_boundary`, preserving "at most one Visit per
    connected ambiguous component"."""
    a = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.9)
    b = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a", "p-c"), max_confidence=0.2)
    c = _arbitration_proposal("p-c", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.85)
    arbitration = resolve_ambiguous_boundary_arbitration([a, b, c])
    assert arbitration.resolved_winner_ids == frozenset({"p-a"})

    state = _state()
    outcomes = {
        proposal.proposal_id: evaluate_candidate_authority(
            proposal, observed_at=NOW, state=state,
            ambiguous_boundary_resolved=proposal.proposal_id in arbitration.resolved_winner_ids,
        )
        for proposal in (a, b, c)
    }
    assert outcomes["p-a"].outcome == "create"
    assert outcomes["p-b"].outcome == "blocked_ambiguous_boundary"
    assert outcomes["p-c"].outcome == "blocked_ambiguous_boundary"


def test_arbitration_result_does_not_depend_on_a_previous_call() -> None:
    """Pure function, no module-level cache/state (see "No cross-session/
    Stream propagation," Ambiguous-Boundary Transitive Fragmentation
    Closure v1): the identical `proposal_id` ("p-a") loses in one call and
    wins in a completely separate, later call with different sibling
    facts -- proving no session/tick memory leaks between calls."""
    weak = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.1)
    strong_rival = _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a",), max_confidence=0.9)
    first = resolve_ambiguous_boundary_arbitration([weak, strong_rival])
    assert first.resolved_winner_ids == frozenset({"p-b"})

    now_strong = _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-c",), max_confidence=0.9)
    weak_rival = _arbitration_proposal("p-c", ambiguous_adjacent_proposal_ids=("p-a",), max_confidence=0.05)
    second = resolve_ambiguous_boundary_arbitration([weak_rival, now_strong])
    assert second.resolved_winner_ids == frozenset({"p-a"})


def test_arbitration_missing_sibling_this_tick_is_treated_as_no_rival() -> None:
    """A sibling id no longer present in this tick's own freshly-assembled
    proposal set (already superseded into a bigger proposal within this
    same call, which gets its own fresh evaluation) never blocks
    arbitration for the proposal still referencing it."""
    lone = _arbitration_proposal("p-lone", ambiguous_adjacent_proposal_ids=("p-vanished",), max_confidence=0.1)
    result = resolve_ambiguous_boundary_arbitration([lone])
    assert result.resolved_winner_ids == frozenset({"p-lone"})
    assert result.deferred_ids == frozenset()


def test_arbitration_is_pure_and_deterministic() -> None:
    proposals = [
        _arbitration_proposal("p-a", ambiguous_adjacent_proposal_ids=("p-b",), max_confidence=0.6),
        _arbitration_proposal("p-b", ambiguous_adjacent_proposal_ids=("p-a",), max_confidence=0.3),
    ]
    first = resolve_ambiguous_boundary_arbitration(proposals)
    second = resolve_ambiguous_boundary_arbitration(proposals)
    assert first == second


# --- Real-assembler integration (mixed ambiguous/concurrent-sibling graphs) -
#
# The tests above hand-construct `ProposalArbitrationFacts` directly, matching
# this file's own established convention for a pure decision function. The
# two tests below instead drive the real, completely unmodified
# `visit_episode_assembler.assemble_visit_episodes` -- preferred here because
# the milestone this section implements (Ambiguous-Boundary Transitive
# Fragmentation Closure v1) must prove its fix against the actual graph shape
# the assembler produces, not only a graph a test author might assume.


def _mixed_graph_tracklet(generation_id: str, start: int, end: int, **overrides: object) -> Tracklet:
    """Terse direct-construction helper, mirroring `test_visit_episode_
    assembler.py`'s own `_tracklet` convention (duplicated rather than
    cross-imported between test files -- matching `visit_episode_assembler.
    semantic_fingerprint`'s own established "small pure helper duplicated,
    not shared" precedent). Used only by the two tests below."""
    values: dict[str, object] = {
        "generation_id": generation_id,
        "stream_id": "stream-mixed",
        "broad_class": "bird",
        "start_offset_ms": start,
        "end_offset_ms": end,
        "start_bounding_box": (0.40, 0.40, 0.50, 0.50),
        "end_bounding_box": (0.40, 0.40, 0.50, 0.50),
        "geometry_envelope": (0.40, 0.40, 0.50, 0.50),
        "terminal_reason": "maximum_unsupported_duration",
        "track_ids": (f"{generation_id}-track",),
        "supporting_frame_ids": (f"{generation_id}-frame-1",),
        "confidence_evidence": EMPTY_CONFIDENCE_EVIDENCE,
    }
    values.update(overrides)
    return Tracklet(**values)


def test_transitive_component_and_concurrent_sibling_do_not_cross_contaminate() -> None:
    """Mixed-graph interaction with Multi-Subject Visit Assembly Phase 1/2
    (see "Interaction with Phase 2," Ambiguous-Boundary Transitive
    Fragmentation Closure v1): drives the real assembler over a sequential
    A-B-C ambiguous chain (each pairwise gap 20s, inside the 45s ambiguous
    window, so A and C are never directly compared -- A's episode has
    already closed by the time C is processed) where a fourth tracklet D
    genuinely, temporally overlaps C -- a real concurrent, distinct
    subject, never a continuation of the chain.

    Proves the two mechanisms stay structurally disjoint all the way
    through arbitration: A/B/C resolve as one connected ambiguous
    component (a single winner); D -- deliberately given the single
    highest confidence of the four, to catch an implementation that
    wrongly traversed `concurrent_sibling_proposal_ids` too -- never
    enters either arbitration result set at all."""
    a = _mixed_graph_tracklet(
        "gen-a", 0, 2_000, confidence_evidence=replace(EMPTY_CONFIDENCE_EVIDENCE, max_confidence=0.90),
    )
    b = _mixed_graph_tracklet(
        "gen-b", 22_000, 30_000, confidence_evidence=replace(EMPTY_CONFIDENCE_EVIDENCE, max_confidence=0.20),
    )
    c = _mixed_graph_tracklet(
        "gen-c", 50_000, 52_000, confidence_evidence=replace(EMPTY_CONFIDENCE_EVIDENCE, max_confidence=0.85),
    )
    d = _mixed_graph_tracklet(
        "gen-d", 51_000, 54_000,
        start_bounding_box=(0.85, 0.85, 0.95, 0.95), end_bounding_box=(0.85, 0.85, 0.95, 0.95),
        geometry_envelope=(0.85, 0.85, 0.95, 0.95),
        confidence_evidence=replace(EMPTY_CONFIDENCE_EVIDENCE, max_confidence=0.99),
    )
    result = assemble_visit_episodes((a, b, c, d))
    assert result.assembled_proposal_count == 4

    by_generation = {p.constituent_generation_ids[0]: p for p in result.proposals}
    pa, pb, pc, pd = (
        by_generation["gen-a"], by_generation["gen-b"], by_generation["gen-c"], by_generation["gen-d"],
    )

    # The assembler's own graph: A-B-C chained (A and C never directly
    # listing each other), D linked to C only, and only as a concurrent
    # sibling -- never as an ambiguous edge.
    assert set(pa.ambiguous_adjacent_proposal_ids) == {pb.proposal_id}
    assert set(pb.ambiguous_adjacent_proposal_ids) == {pa.proposal_id, pc.proposal_id}
    assert set(pc.ambiguous_adjacent_proposal_ids) == {pb.proposal_id}
    assert pd.ambiguous_adjacent_proposal_ids == ()
    assert pc.concurrent_sibling_proposal_ids == (pd.proposal_id,)
    assert pd.concurrent_sibling_proposal_ids == (pc.proposal_id,)
    assert pa.concurrent_sibling_proposal_ids == ()
    assert pb.concurrent_sibling_proposal_ids == ()

    arbitration = resolve_ambiguous_boundary_arbitration(result.proposals)
    assert arbitration.resolved_winner_ids == frozenset({pa.proposal_id})
    assert pd.proposal_id not in arbitration.resolved_winner_ids
    assert pd.proposal_id not in arbitration.deferred_ids


def test_ordinary_single_episode_merge_never_reaches_arbitration() -> None:
    """Required case 7 (Ambiguous-Boundary Transitive Fragmentation
    Closure v1): two ordinary fragments of one real bird, close enough to
    merge cleanly (`merge_same_visit`), must assemble into exactly one
    proposal with an empty `ambiguous_adjacent_proposal_ids` -- arbitration
    and the authority gate's `ambiguous_boundary_resolved` bypass are never
    involved at all, and the ordinary `eligible_assembled_proposal` reason
    is unchanged."""
    a = _mixed_graph_tracklet("gen-x", 0, 4_000)
    b = _mixed_graph_tracklet("gen-y", 5_000, 9_000)  # 1s gap, identical geometry -> merge_same_visit
    result = assemble_visit_episodes((a, b))
    assert result.assembled_proposal_count == 1
    proposal = result.proposals[0]
    assert proposal.ambiguous_adjacent_proposal_ids == ()

    arbitration = resolve_ambiguous_boundary_arbitration(result.proposals)
    assert arbitration.resolved_winner_ids == frozenset()
    assert arbitration.deferred_ids == frozenset()

    outcome = evaluate_candidate_authority(
        proposal, observed_at=NOW, state=_state(), ambiguous_boundary_resolved=False,
    )
    assert outcome.outcome == "create"
    assert outcome.reason == "eligible_assembled_proposal"


# --- Explicit authority states (no vague boolean) ---------------------------


def test_authority_mode_has_exactly_two_explicit_values() -> None:
    assert {member.value for member in ObservationAuthorityMode} == {"shadow", "candidate_visit"}


def test_authority_limits_reject_out_of_bound_values() -> None:
    with pytest.raises(ValueError):
        AuthorityLimits(max_candidates_per_session=0)
    with pytest.raises(ValueError):
        AuthorityLimits(max_candidates_per_hour=0)
    with pytest.raises(ValueError):
        AuthorityLimits(max_evidence_items_per_candidate=0)
    with pytest.raises(ValueError):
        AuthorityLimits(max_evidence_bytes_per_candidate=0)


def test_gate_is_pure_and_deterministic_for_same_inputs() -> None:
    first = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=_state())
    second = evaluate_candidate_authority(_proposal(), observed_at=NOW, state=_state())
    assert first == second


def test_candidate_visit_authority_module_has_no_product_repository_import() -> None:
    """Structural guard mirroring `test_visit_episode_assembler.py`'s own
    `test_no_product_repository_dependency`: the authority *gate* must never
    import the product repository/database -- only the narrow adapter
    (Stage 7's own persistence-boundary module) may."""
    from pathlib import Path as _Path

    source = _Path("src/mockingbird/observation/candidate_visit_authority.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy",
        "import socket", "import requests", "ReviewLabel", "MotionEvidence", "MediaAsset",
    )
    for token in forbidden:
        assert token not in source, f"candidate_visit_authority.py must not reference {token}"
