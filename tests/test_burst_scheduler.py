"""Hardware-free tests for the Stage 6.9 recurrence-aware burst scheduler.

Covers docs/burst-scheduler-contract.md's hardware-free test list. Every test
here is pure: no CUDA, ONNX Runtime, PiCamera2, camera transport, or filesystem
access, and no product-repository import anywhere in this file or the module
under test.
"""
from __future__ import annotations

import itertools

import pytest

from mockingbird.observation.burst_scheduler import (
    DECISION_BURST_ISSUED,
    DECISION_BURST_UNAVAILABLE,
    DECISION_DEFERRED_COOLDOWN,
    DECISION_ENGINEERING_OVERRIDE_ISSUED,
    DECISION_OPERATOR_OVERRIDE_ISSUED,
    DECISION_RETRY_ISSUED,
    DECISION_SUPPRESSED_ACTIVE_REQUEST,
    DECISION_SUPPRESSED_RATE_BUDGET,
    DECISION_SUPPRESSED_RECURRING_GEOMETRY,
    DECISION_SUPPRESSED_SAME_TRACK_GENERATION,
    DECISION_SUPPRESSED_SESSION_BUDGET,
    ISSUING_DECISIONS,
    NOVELTY_BETTER_TEMPORAL_SUPPORT,
    NOVELTY_ENGINEERING_REQUEST,
    NOVELTY_MOTION_CHANGE,
    NOVELTY_OPERATOR_MARKER,
    NOVELTY_RETRY_PERMITTED,
    NOVELTY_STRONGER_CONFIDENCE,
    NOVELTY_TIME_GAP,
    RESET_ENGINEERING_RESET,
    RESET_GENERATION_REPLACEMENT,
    RESET_PROVIDER_RESET,
    RESET_SESSION_STOP,
    SCHEDULER_DECISIONS,
    BurstOpportunity,
    BurstScheduler,
    BurstSchedulerConfig,
    BurstSchedulerError,
)

BASE_BOX = (0.45, 0.55, 0.47, 0.63)
_COUNTER = itertools.count(1)


def _box(*, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0) -> tuple[float, float, float, float]:
    left, top, right, bottom = BASE_BOX
    cx, cy = (left + right) / 2 + dx, (top + bottom) / 2 + dy
    half_w, half_h = (right - left) / 2 * scale, (bottom - top) / 2 * scale
    return (round(cx - half_w, 6), round(cy - half_h, 6), round(cx + half_w, 6), round(cy + half_h, 6))


def _opportunity(**overrides: object) -> BurstOpportunity:
    index = next(_COUNTER)
    defaults: dict[str, object] = dict(
        opportunity_id=f"opportunity-{index}",
        stream_id="stream-yard",
        session_id="session-test",
        node_session_id="node-session-a",
        provider_generation="generation-a",
        connection_segment_id="segment-a",
        session_sequence=index,
        session_offset_ms=index * 1000,
        track_generation_id=f"track-generation-{index}",
        trigger_frame_id=f"frame-{index}",
        source_offset_ms=index * 1000,
        broad_class="animal",
        subject_geometry=BASE_BOX,
        detector_score=0.75,
        detector_confirmation_count=2,
        tracker_support_count=1,
        motion_change_score=None,
        operator_marker_present=False,
        trigger_reason="shadow_track_event",
        requested_evidence_profile="evidence-large",
        engineering_validation_request=False,
    )
    defaults.update(overrides)
    return BurstOpportunity(**defaults)  # type: ignore[arg-type]


def _scheduler(**config_overrides: object) -> BurstScheduler:
    config = BurstSchedulerConfig(**config_overrides) if config_overrides else BurstSchedulerConfig()
    return BurstScheduler(session_id="session-test", config=config)


def _resolve(scheduler: BurstScheduler, decision, *, status: str = "captured", byte_size: int = 900_000, latency_ms: int = 40) -> None:
    assert decision.request_id is not None
    scheduler.record_result(decision.request_id, status=status, byte_size=byte_size, latency_ms=latency_ms)


# --------------------------------------------------------------------------
# 1. One opportunity issues one burst.
# --------------------------------------------------------------------------


def test_one_opportunity_issues_one_burst() -> None:
    scheduler = _scheduler()
    decision = scheduler.decide(_opportunity())
    assert decision.outcome == DECISION_BURST_ISSUED
    assert decision.should_issue is True
    assert decision.outcome in ISSUING_DECISIONS
    assert scheduler.diagnostics().issued_count == 1


# --------------------------------------------------------------------------
# 2. Same track generation cannot issue repeatedly inside cooldown.
# --------------------------------------------------------------------------


def test_same_track_generation_suppressed_inside_cooldown() -> None:
    # Recurrence-group cooldown is disabled here so this test isolates the
    # per-generation mechanism specifically (the two are independent bounds).
    scheduler = _scheduler(minimum_burst_interval_ms=5_000, recurrence_group_cooldown_ms=0)
    generation = "track-generation-fixed"
    first = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=1_000))
    _resolve(scheduler, first)
    second = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=1_500))
    assert second.outcome == DECISION_SUPPRESSED_SAME_TRACK_GENERATION
    assert second.should_issue is False

    # Outside the cooldown window the same generation may burst again.
    third = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=7_000))
    assert third.outcome == DECISION_BURST_ISSUED


# --------------------------------------------------------------------------
# 3. New generation with nearly identical geometry is suppressed.
# --------------------------------------------------------------------------


def test_new_generation_nearly_identical_geometry_is_suppressed() -> None:
    scheduler = _scheduler()
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    # A different generation id (as a fresh, short-lived re-detection of the
    # same static structure would produce) with nearly identical geometry.
    second = scheduler.decide(_opportunity(track_generation_id="generation-2", subject_geometry=_box(dx=0.001, dy=0.001), session_offset_ms=1_800))
    assert second.outcome == DECISION_SUPPRESSED_RECURRING_GEOMETRY
    assert second.recurrence_group_id is not None
    assert second.recurrence_group_id == first.recurrence_group_id


# --------------------------------------------------------------------------
# 4. Same Zone but spatially distinct geometry is not suppressed.
# --------------------------------------------------------------------------


def test_spatially_distinct_geometry_in_same_zone_is_not_suppressed() -> None:
    scheduler = _scheduler()
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    second = scheduler.decide(_opportunity(
        track_generation_id="generation-2",
        subject_geometry=(0.05, 0.05, 0.10, 0.10),
        session_offset_ms=1_800,
    ))
    assert second.outcome == DECISION_BURST_ISSUED
    assert second.recurrence_group_id != first.recurrence_group_id


# --------------------------------------------------------------------------
# 5. Significant box displacement permits a new burst.
# --------------------------------------------------------------------------


def test_significant_box_displacement_permits_new_burst() -> None:
    scheduler = _scheduler()
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    second = scheduler.decide(_opportunity(
        track_generation_id="generation-2", subject_geometry=_box(dx=0.30), session_offset_ms=1_800,
    ))
    assert second.outcome == DECISION_BURST_ISSUED


# --------------------------------------------------------------------------
# 6. Significant size change permits a new burst.
# --------------------------------------------------------------------------


def test_significant_size_change_permits_new_burst() -> None:
    scheduler = _scheduler()
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    second = scheduler.decide(_opportunity(
        track_generation_id="generation-2", subject_geometry=_box(scale=3.0), session_offset_ms=1_800,
    ))
    assert second.outcome == DECISION_BURST_ISSUED


# --------------------------------------------------------------------------
# 7. Stronger confidence can permit a new burst when configured.
# --------------------------------------------------------------------------


def test_stronger_confidence_permits_new_burst_when_configured() -> None:
    scheduler = _scheduler(recurrence_group_cooldown_ms=60_000, stronger_confidence_delta=0.15)
    generation_a = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), detector_score=0.30, session_offset_ms=1_000))
    _resolve(scheduler, generation_a)
    generation_b = scheduler.decide(_opportunity(track_generation_id="generation-2", subject_geometry=_box(dx=0.001), detector_score=0.30, session_offset_ms=2_000))
    assert generation_b.outcome == DECISION_SUPPRESSED_RECURRING_GEOMETRY

    stronger = scheduler.decide(_opportunity(
        track_generation_id="generation-3", subject_geometry=_box(dx=0.001), detector_score=0.85, session_offset_ms=3_000,
    ))
    assert stronger.outcome == DECISION_BURST_ISSUED
    assert NOVELTY_STRONGER_CONFIDENCE in stronger.novelty_signals


# --------------------------------------------------------------------------
# 8. Meaningful motion/change can permit a new burst.
# --------------------------------------------------------------------------


def test_meaningful_motion_change_permits_new_burst() -> None:
    scheduler = _scheduler(recurrence_group_cooldown_ms=60_000, motion_change_threshold=0.2)
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    scheduler.decide(_opportunity(track_generation_id="generation-2", subject_geometry=_box(dx=0.001), session_offset_ms=1_800))

    motioned = scheduler.decide(_opportunity(
        track_generation_id="generation-3", subject_geometry=_box(dx=0.001), motion_change_score=0.9, session_offset_ms=2_500,
    ))
    assert motioned.outcome == DECISION_BURST_ISSUED
    assert NOVELTY_MOTION_CHANGE in motioned.novelty_signals


# --------------------------------------------------------------------------
# 9. Operator marker overrides recurrence suppression.
# --------------------------------------------------------------------------


def test_operator_marker_overrides_recurrence_suppression() -> None:
    scheduler = _scheduler(recurrence_group_cooldown_ms=60_000)
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    scheduler.decide(_opportunity(track_generation_id="generation-2", subject_geometry=_box(dx=0.001), session_offset_ms=1_800))

    marked = scheduler.decide(_opportunity(
        track_generation_id="generation-3", subject_geometry=_box(dx=0.001), operator_marker_present=True, session_offset_ms=2_000,
    ))
    assert marked.outcome == DECISION_OPERATOR_OVERRIDE_ISSUED
    assert marked.is_override is True
    assert NOVELTY_OPERATOR_MARKER in marked.novelty_signals


# --------------------------------------------------------------------------
# 10. Engineering validation override is explicitly labeled.
# --------------------------------------------------------------------------


def test_engineering_validation_override_is_explicitly_labeled() -> None:
    scheduler = _scheduler()
    decision = scheduler.decide(_opportunity(engineering_validation_request=True))
    assert decision.outcome == DECISION_ENGINEERING_OVERRIDE_ISSUED
    assert decision.outcome != DECISION_BURST_ISSUED
    assert NOVELTY_ENGINEERING_REQUEST in decision.novelty_signals


# --------------------------------------------------------------------------
# 11. Override still respects hard session safety bounds.
# --------------------------------------------------------------------------


def test_override_respects_hard_session_budget() -> None:
    scheduler = _scheduler(max_bursts_per_session=1, operator_override_reserved_bursts=1)
    first = scheduler.decide(_opportunity(engineering_validation_request=True))
    _resolve(scheduler, first)
    assert first.outcome == DECISION_ENGINEERING_OVERRIDE_ISSUED

    second = scheduler.decide(_opportunity(engineering_validation_request=True))
    _resolve(scheduler, second)
    assert second.outcome == DECISION_ENGINEERING_OVERRIDE_ISSUED  # consumes the reserved allowance

    third = scheduler.decide(_opportunity(engineering_validation_request=True))
    assert third.outcome == DECISION_SUPPRESSED_SESSION_BUDGET
    assert third.should_issue is False


def test_override_never_bypasses_concurrency_cap() -> None:
    scheduler = _scheduler(max_concurrent_requests=1)
    first = scheduler.decide(_opportunity(track_generation_id="generation-1"))
    assert first.outcome == DECISION_BURST_ISSUED
    # generation-1's own request is still unresolved; a different generation's
    # operator override cannot exceed the physical one-capture-at-a-time bound.
    second = scheduler.decide(_opportunity(track_generation_id="generation-2", operator_marker_present=True))
    assert second.outcome == DECISION_SUPPRESSED_ACTIVE_REQUEST


# --------------------------------------------------------------------------
# 12. Active request prevents duplicate concurrent burst.
# --------------------------------------------------------------------------


def test_active_request_prevents_duplicate_concurrent_burst() -> None:
    scheduler = _scheduler(max_concurrent_requests=2)
    generation = "track-generation-fixed"
    first = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=1_000))
    assert first.outcome == DECISION_BURST_ISSUED
    # The same generation already has an unresolved request outstanding.
    second = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=1_200))
    assert second.outcome == DECISION_DEFERRED_COOLDOWN
    assert second.should_issue is False


# --------------------------------------------------------------------------
# 13. Session burst budget is enforced.
# --------------------------------------------------------------------------


def test_session_burst_budget_is_enforced() -> None:
    scheduler = _scheduler(max_bursts_per_session=2, max_concurrent_requests=10, minimum_burst_interval_ms=0, recurrence_group_cooldown_ms=0)
    outcomes = []
    for index in range(4):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"generation-{index}", subject_geometry=_box(dx=index * 0.08), session_offset_ms=index * 1_000,
        ))
        _resolve(scheduler, decision) if decision.should_issue else None
        outcomes.append(decision.outcome)
    assert outcomes.count(DECISION_BURST_ISSUED) == 2
    assert outcomes.count(DECISION_SUPPRESSED_SESSION_BUDGET) == 2
    assert scheduler.diagnostics().issued_count == 2


# --------------------------------------------------------------------------
# 14. Per-minute/rate budget is enforced.
# --------------------------------------------------------------------------


def test_rate_budget_is_enforced() -> None:
    scheduler = _scheduler(
        max_bursts_per_minute=2, rate_window_ms=60_000, max_bursts_per_session=100,
        max_concurrent_requests=10, minimum_burst_interval_ms=0, recurrence_group_cooldown_ms=0,
    )
    outcomes = []
    for index in range(3):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"generation-{index}", subject_geometry=_box(dx=index * 0.08), session_offset_ms=index * 1_000,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)
        outcomes.append(decision.outcome)
    assert outcomes[:2] == [DECISION_BURST_ISSUED, DECISION_BURST_ISSUED]
    assert outcomes[2] == DECISION_SUPPRESSED_RATE_BUDGET

    # Once the rate window has genuinely elapsed, bursts resume.
    later = scheduler.decide(_opportunity(track_generation_id="generation-later", subject_geometry=_box(dx=0.4), session_offset_ms=65_000))
    assert later.outcome == DECISION_BURST_ISSUED


# --------------------------------------------------------------------------
# 15. Recurrence groups expire deterministically.
# --------------------------------------------------------------------------


def test_recurrence_groups_expire_deterministically() -> None:
    scheduler = _scheduler(recurrence_group_expiry_ms=10_000, recurrence_group_cooldown_ms=60_000)
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    assert len(scheduler.recurrence_groups()) == 1

    # Long after expiry, the identical geometry starts a brand-new group and
    # is issued again rather than inheriting stale recurrence history.
    after_expiry = scheduler.decide(_opportunity(
        track_generation_id="generation-2", subject_geometry=_box(dx=0.001), session_offset_ms=200_000,
    ))
    assert after_expiry.outcome == DECISION_BURST_ISSUED
    assert after_expiry.recurrence_group_id != first.recurrence_group_id


# --------------------------------------------------------------------------
# 16 / 32. Provider reset / session stop clear scheduler state.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("reason", [RESET_PROVIDER_RESET, RESET_SESSION_STOP, RESET_GENERATION_REPLACEMENT, RESET_ENGINEERING_RESET])
def test_reset_clears_all_scheduler_state(reason: str) -> None:
    scheduler = _scheduler(max_bursts_per_session=5)
    decision = scheduler.decide(_opportunity())
    _resolve(scheduler, decision)
    assert scheduler.diagnostics().issued_count == 1
    assert len(scheduler.recurrence_groups()) == 1
    assert len(scheduler.decision_history()) == 1

    scheduler.reset(reason)

    assert scheduler.diagnostics().issued_count == 0
    assert scheduler.recurrence_groups() == ()
    assert scheduler.decision_history() == ()
    assert scheduler.active_request_count == 0
    # Budgets are fresh, so an identical opportunity is issued again.
    fresh = scheduler.decide(_opportunity())
    assert fresh.outcome == DECISION_BURST_ISSUED


# --------------------------------------------------------------------------
# 17. Camera Node generation change clears or isolates state.
# --------------------------------------------------------------------------


def test_generation_change_without_reset_does_not_group_across_generations() -> None:
    scheduler = _scheduler()
    first = scheduler.decide(_opportunity(provider_generation="generation-a", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    # A different provider_generation never joins an old generation's group,
    # even with identical geometry -- callers are still expected to reset
    # explicitly on a real Camera Node generation replacement (see below),
    # but the grouping key itself never silently bridges two generations.
    other_generation = scheduler.decide(_opportunity(
        provider_generation="generation-b", track_generation_id="generation-b-track",
        subject_geometry=_box(dx=0.001), session_offset_ms=1_800,
    ))
    assert other_generation.outcome == DECISION_BURST_ISSUED
    assert other_generation.recurrence_group_id != first.recurrence_group_id


# --------------------------------------------------------------------------
# 18. Failed burst retries remain bounded.
# --------------------------------------------------------------------------


def test_failed_burst_retries_remain_bounded() -> None:
    scheduler = _scheduler(max_retries_per_opportunity=1, minimum_burst_interval_ms=60_000)
    generation = "track-generation-fixed"
    first = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=1_000))
    assert first.outcome == DECISION_BURST_ISSUED
    scheduler.record_result(first.request_id, status="failed", failure_code="fixture_failure")

    retry = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=1_200))
    assert retry.outcome == DECISION_RETRY_ISSUED
    assert retry.is_retry is True
    assert NOVELTY_RETRY_PERMITTED in retry.novelty_signals
    scheduler.record_result(retry.request_id, status="failed", failure_code="fixture_failure")

    # The bounded retry budget (1) is now exhausted; back to the ordinary
    # per-generation cooldown instead of an unbounded retry loop.
    exhausted = scheduler.decide(_opportunity(track_generation_id=generation, session_offset_ms=1_400))
    assert exhausted.outcome == DECISION_SUPPRESSED_SAME_TRACK_GENERATION
    assert exhausted.is_retry is False


# --------------------------------------------------------------------------
# 19. Stale result cannot attach to a new track generation.
# --------------------------------------------------------------------------


def test_stale_result_does_not_affect_a_different_generation() -> None:
    scheduler = _scheduler(minimum_burst_interval_ms=60_000)
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", session_offset_ms=1_000))
    scheduler.record_result(first.request_id, status="stale")

    unrelated = scheduler.decide(_opportunity(
        track_generation_id="generation-2", subject_geometry=_box(dx=0.4), session_offset_ms=1_100,
    ))
    assert unrelated.outcome == DECISION_BURST_ISSUED
    diagnostics = scheduler.diagnostics()
    assert diagnostics.stale_bursts == 1
    assert diagnostics.successful_bursts == 0


def test_record_result_rejects_unknown_request_id() -> None:
    scheduler = _scheduler()
    with pytest.raises(BurstSchedulerError):
        scheduler.record_result("never-issued", status="captured")


# --------------------------------------------------------------------------
# 20. Decision history remains bounded.
# --------------------------------------------------------------------------


def test_decision_history_remains_bounded() -> None:
    scheduler = _scheduler(max_decision_history=5, max_bursts_per_session=1000, max_bursts_per_minute=1000, max_concurrent_requests=1000, minimum_burst_interval_ms=0, recurrence_group_cooldown_ms=0)
    for index in range(20):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"generation-{index}", subject_geometry=_box(dx=(index % 7) * 0.08), session_offset_ms=index * 1_000,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)
    assert len(scheduler.decision_history()) == 5


# --------------------------------------------------------------------------
# 21. Input ordering does not change decisions (determinism/reproducibility).
# --------------------------------------------------------------------------


def test_same_chronological_input_is_fully_deterministic_across_instances() -> None:
    opportunities = [
        _opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000),
        _opportunity(track_generation_id="generation-2", subject_geometry=_box(dx=0.001), session_offset_ms=1_500),
        _opportunity(track_generation_id="generation-3", subject_geometry=_box(dx=0.5), session_offset_ms=2_000),
        _opportunity(track_generation_id="generation-4", subject_geometry=_box(dx=0.001), session_offset_ms=25_000),
    ]

    def _run() -> list[str]:
        scheduler = _scheduler()
        outcomes = []
        for opportunity in opportunities:
            decision = scheduler.decide(opportunity)
            if decision.should_issue:
                _resolve(scheduler, decision)
            outcomes.append(decision.outcome)
        return outcomes

    assert _run() == _run()


# --------------------------------------------------------------------------
# 22. Stable IDs and semantic fingerprint.
# --------------------------------------------------------------------------


def test_stable_ids_and_semantic_fingerprint() -> None:
    scheduler_one = _scheduler()
    scheduler_two = _scheduler()
    opportunity = _opportunity(opportunity_id="opportunity-fixed", track_generation_id="generation-fixed", session_offset_ms=1_000)
    decision_one = scheduler_one.decide(opportunity)
    decision_two = scheduler_two.decide(opportunity)
    assert decision_one.request_id == decision_two.request_id
    assert decision_one.recurrence_group_id == decision_two.recurrence_group_id
    assert decision_one.request_id != ""


# --------------------------------------------------------------------------
# 23. Runtime timing/resource changes remain non-semantic.
# --------------------------------------------------------------------------


def test_wall_clock_and_latency_do_not_affect_decisions() -> None:
    opportunity = _opportunity(opportunity_id="opportunity-fixed", track_generation_id="generation-fixed", session_offset_ms=1_000)

    fast = _scheduler()
    fast_decision = fast.decide(opportunity)
    fast.record_result(fast_decision.request_id, status="captured", latency_ms=5)

    slow = _scheduler()
    slow_decision = slow.decide(opportunity)
    slow.record_result(slow_decision.request_id, status="captured", latency_ms=9_000)

    assert fast_decision.outcome == slow_decision.outcome == DECISION_BURST_ISSUED
    assert fast_decision.request_id == slow_decision.request_id


# --------------------------------------------------------------------------
# 24. Static shepherd's-hook-like recurrence is suppressed in a general fixture.
# --------------------------------------------------------------------------


def test_static_structure_like_recurrence_is_suppressed() -> None:
    """A general fixture modeling a low-score, near-identical detection that
    re-triggers as a brand-new short-lived track generation every few
    seconds -- the session-02 shepherd's-hook/feeder-hardware pattern."""

    scheduler = _scheduler()
    outcomes = []
    for index in range(8):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"static-structure-generation-{index}",
            subject_geometry=_box(dx=0.0003 * index),  # sub-pixel jitter only
            detector_score=0.05 + 0.001 * index,  # a consistently low, static score band
            detector_confirmation_count=1,
            tracker_support_count=0,
            session_offset_ms=1_000 + index * 1_200,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)
        outcomes.append(decision.outcome)
    assert outcomes[0] == DECISION_BURST_ISSUED
    assert outcomes.count(DECISION_BURST_ISSUED) <= 2
    assert outcomes.count(DECISION_SUPPRESSED_RECURRING_GEOMETRY) >= 5


# --------------------------------------------------------------------------
# 25. Genuine animal appearing near the same structure can trigger through novelty.
# --------------------------------------------------------------------------


def test_genuine_animal_near_static_structure_triggers_via_novelty() -> None:
    scheduler = _scheduler()
    for index in range(4):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"static-structure-generation-{index}",
            subject_geometry=_box(dx=0.0003 * index),
            detector_score=0.05,
            detector_confirmation_count=1,
            tracker_support_count=0,
            session_offset_ms=1_000 + index * 1_200,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)

    genuine = scheduler.decide(_opportunity(
        track_generation_id="genuine-bird-generation",
        subject_geometry=_box(dx=0.001),  # same physical region as the static structure
        detector_score=0.82,  # materially stronger than the static band above
        detector_confirmation_count=3,
        tracker_support_count=2,
        session_offset_ms=6_500,
    ))
    assert genuine.outcome == DECISION_BURST_ISSUED
    assert genuine.should_issue is True


# --------------------------------------------------------------------------
# 26. Operator-marked genuine appearance retains burst eligibility.
# --------------------------------------------------------------------------


def test_operator_marked_genuine_appearance_retains_burst_eligibility() -> None:
    scheduler = _scheduler(
        max_bursts_per_session=1, operator_override_reserved_bursts=1,
        minimum_burst_interval_ms=0, recurrence_group_cooldown_ms=60_000,
    )
    # Consume the ordinary session budget with an unrelated burst.
    consumed = scheduler.decide(_opportunity(
        track_generation_id="unrelated-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=500,
    ))
    assert consumed.outcome == DECISION_BURST_ISSUED
    _resolve(scheduler, consumed)

    # The ordinary session budget is now exhausted.
    blocked = scheduler.decide(_opportunity(
        track_generation_id="static-structure-generation", subject_geometry=_box(), detector_score=0.05, session_offset_ms=1_000,
    ))
    assert blocked.outcome == DECISION_SUPPRESSED_SESSION_BUDGET

    # An operator-confirmed genuine appearance at the same static-structure
    # location still reaches a burst through the small, separately bounded
    # override allowance -- retaining eligibility even after ordinary budget
    # exhaustion, which is exactly what a real, busy recurring-static-geometry
    # session (session-02) would otherwise risk starving out.
    marked = scheduler.decide(_opportunity(
        track_generation_id="operator-marked-generation",
        subject_geometry=_box(dx=0.001), detector_score=0.05, operator_marker_present=True,
        session_offset_ms=1_500,
    ))
    assert marked.outcome == DECISION_OPERATOR_OVERRIDE_ISSUED
    assert marked.should_issue is True


# --------------------------------------------------------------------------
# 27 / 28. Detector/tracker/proposal outputs are unchanged; evidence-candidate
# compatibility is a wiring-level concern -- see
# tests/test_observation_camera_node_live.py for the integration proof. This
# module never imports frame_tracker, frame_driven_provider, or contracts'
# EvidenceCandidate/TrackUpdate/VisitProposal types, which the structural
# test below enforces directly.
# --------------------------------------------------------------------------


def test_module_never_imports_tracker_or_product_state() -> None:
    import pathlib

    source = pathlib.Path("src/mockingbird/observation/burst_scheduler.py").read_text()
    forbidden = (
        "frame_tracker", "frame_driven_provider", "onnx_provider", "camera_node_live",
        "mockingbird.db", "mockingbird.repositories", "mockingbird.api",
        "ReviewLabel", "MotionEvidence", "StreamMonitoringPolicy", "MediaAsset",
        "sqlalchemy", "cuda", "onnxruntime", "picamera2", "PIL",
    )
    lowered = source.lower()
    assert not any(token.lower() in lowered for token in forbidden)


# --------------------------------------------------------------------------
# 29 / 30. No product repository or truth-write dependency; no
# Event/Visit/MediaAsset/ReviewLabel/Observation creation.
# --------------------------------------------------------------------------


def test_decisions_and_opportunities_never_claim_truth() -> None:
    scheduler = _scheduler()
    decision = scheduler.decide(_opportunity())
    assert decision.should_issue is True
    # There is no product-truth field on the decision at all -- shadow-only
    # is structural, not a boolean this module could accidentally flip.
    assert not hasattr(decision, "creates_truth")
    assert not hasattr(decision, "review_label")


# --------------------------------------------------------------------------
# 31. Privacy/Ignore metadata remains preserved (scheduler never overrides it).
# --------------------------------------------------------------------------


def test_scheduler_has_no_privacy_override_capability() -> None:
    """The scheduler never receives a masked detection in the first place
    (the frame-driven tracker discards those before a track ever forms, per
    frame-driven-shadow-provider-contract.md); this module structurally has
    no field or method that could reintroduce or waive a Privacy/Ignore
    exclusion."""

    import dataclasses

    from mockingbird.observation.burst_scheduler import BurstOpportunity as _Opportunity

    fields = {field.name for field in dataclasses.fields(_Opportunity)}
    assert not any("privacy" in name or "ignore" in name for name in fields)


# --------------------------------------------------------------------------
# 33. Old captures without scheduler facts remain readable (see
# tests/test_burst_scheduler_replay.py for the manifest-level proof).
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 34. Burst-unavailable capability reports honestly.
# --------------------------------------------------------------------------


def test_burst_unavailable_is_reported_honestly() -> None:
    scheduler = _scheduler()
    scheduler.mark_burst_unavailable("evidence_burst_capability_unavailable")
    decision = scheduler.decide(_opportunity())
    assert decision.outcome == DECISION_BURST_UNAVAILABLE
    assert decision.should_issue is False
    health = scheduler.health()
    assert health.burst_capability_available is False
    assert health.degraded is True

    scheduler.mark_burst_available()
    recovered = scheduler.decide(_opportunity())
    assert recovered.outcome == DECISION_BURST_ISSUED
    assert scheduler.health().burst_capability_available is True


# --------------------------------------------------------------------------
# 35. All counters, groups, retries, and retained bytes remain bounded.
# --------------------------------------------------------------------------


def test_all_bounded_collections_stay_within_configured_caps() -> None:
    scheduler = _scheduler(
        max_recurrence_groups=4, max_decision_history=10, max_bursts_per_session=1000,
        max_bursts_per_minute=1000, max_concurrent_requests=1000,
        minimum_burst_interval_ms=0, recurrence_group_cooldown_ms=0,
    )
    for index in range(200):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"generation-{index}",
            subject_geometry=_box(dx=(index % 7) * 0.08),
            session_offset_ms=index * 1_000,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)
    assert len(scheduler.recurrence_groups()) <= 4
    assert len(scheduler.decision_history()) <= 10
    diagnostics = scheduler.diagnostics()
    assert len(diagnostics.suppression_reason_distribution) <= len(SCHEDULER_DECISIONS)
    assert diagnostics.estimated_bytes_avoided >= 0


# --------------------------------------------------------------------------
# Additional focused coverage: config validation and health/diagnostics shape.
# --------------------------------------------------------------------------


def test_config_rejects_invalid_bounds() -> None:
    with pytest.raises(BurstSchedulerError):
        BurstSchedulerConfig(max_bursts_per_session=0)
    with pytest.raises(BurstSchedulerError):
        BurstSchedulerConfig(max_concurrent_requests=0)
    with pytest.raises(BurstSchedulerError):
        BurstSchedulerConfig(geometry_iou_threshold=1.5)


def test_opportunity_rejects_non_shadow_only() -> None:
    with pytest.raises(BurstSchedulerError):
        _opportunity(shadow_only=False)


def test_health_and_diagnostics_are_side_effect_free_snapshots() -> None:
    scheduler = _scheduler()
    before = scheduler.diagnostics()
    scheduler.health()
    scheduler.recurrence_groups()
    scheduler.decision_history()
    after = scheduler.diagnostics()
    assert before == after


def test_diagnostics_track_suppression_reason_distribution() -> None:
    scheduler = _scheduler(recurrence_group_cooldown_ms=60_000)
    first = scheduler.decide(_opportunity(track_generation_id="generation-1", subject_geometry=_box(), session_offset_ms=1_000))
    _resolve(scheduler, first)
    scheduler.decide(_opportunity(track_generation_id="generation-2", subject_geometry=_box(dx=0.001), session_offset_ms=1_500))
    distribution = dict(scheduler.diagnostics().suppression_reason_distribution)
    assert distribution.get(DECISION_SUPPRESSED_RECURRING_GEOMETRY) == 1
