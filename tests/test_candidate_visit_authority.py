"""Stage 7 pure candidate-Visit authority gate (see
docs/candidate-visit-authority-contract.md). No product-repository or database
import anywhere in this test file's own import graph -- `candidate_visit_authority`
must stay a pure decision module exactly like `reconnect_continuity`/
`session_timeline`/`visit_episode_assembler`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mockingbird.observation.candidate_visit_authority import (
    AuthorityLimits,
    AuthorityState,
    ObservationAuthorityMode,
    evaluate_candidate_authority,
)
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal


NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)


def _proposal(
    *,
    proposal_id: str = "visit-episode:fixture",
    ambiguous_adjacent_proposal_ids: tuple[str, ...] = (),
    source_capture_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    supporting_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    constituent_generation_ids: tuple[str, ...] = ("gen-1",),
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
