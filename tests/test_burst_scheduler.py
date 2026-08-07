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
    DECISION_NOVELTY_RESERVE_ISSUED,
    DECISION_OPERATOR_OVERRIDE_ISSUED,
    DECISION_RETRY_ISSUED,
    DECISION_SUPPRESSED_ACTIVE_REQUEST,
    DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED,
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
    # The Stage 6.12 fairness reserve is explicitly disabled here to isolate
    # the ordinary session budget's own hard, absolute enforcement -- the
    # reserve's fallback behavior is covered separately below.
    scheduler = _scheduler(
        max_bursts_per_session=2, max_concurrent_requests=10, minimum_burst_interval_ms=0,
        recurrence_group_cooldown_ms=0, novelty_reserve_capacity=0,
    )
    outcomes = []
    for index in range(4):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"generation-{index}", subject_geometry=_box(dx=index * 0.08), session_offset_ms=index * 1_000,
        ))
        _resolve(scheduler, decision) if decision.should_issue else None
        outcomes.append(decision.outcome)
    assert outcomes.count(DECISION_BURST_ISSUED) == 2
    # Each of these 4 opportunities has spatially distinct geometry, so every
    # one is a brand-new recurrence group -- i.e. independently proven not a
    # suppressible recurrence. With the reserve at capacity=0, the third and
    # fourth are therefore rejected with the more precise Stage 6.12 code
    # (materially novel, but no capacity anywhere -- ordinary or reserve),
    # not the older, less specific suppressed_session_budget; that code's own
    # meaning (an override's dedicated allowance exhausted with no reserve
    # fallback) is covered by test_override_respects_hard_session_budget.
    assert outcomes.count(DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED) == 2
    assert outcomes.count(DECISION_SUPPRESSED_SESSION_BUDGET) == 0
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

    # Consume the dedicated operator/engineering override allowance too, with
    # an unrelated engineering validation burst -- both dedicated channels
    # (ordinary and override) are now fully, absolutely exhausted.
    override_consumed = scheduler.decide(_opportunity(
        track_generation_id="unrelated-override-generation", subject_geometry=(0.20, 0.20, 0.25, 0.25),
        engineering_validation_request=True, session_offset_ms=800,
    ))
    assert override_consumed.outcome == DECISION_ENGINEERING_OVERRIDE_ISSUED
    _resolve(scheduler, override_consumed)

    # An operator-confirmed genuine appearance still reaches a burst through
    # the small, separately bounded, session-relative-time Stage 6.12
    # fairness reserve -- retaining eligibility even after *both* the
    # ordinary budget and the dedicated override allowance are exhausted,
    # which is exactly what a real, busy recurring-static-geometry session
    # (session-04) proved could otherwise starve a late genuine appearance
    # completely (see docs/burst-scheduler-contract.md's Stage 6.12 section).
    marked = scheduler.decide(_opportunity(
        track_generation_id="operator-marked-generation",
        subject_geometry=_box(), detector_score=0.05, operator_marker_present=True,
        session_offset_ms=1_500,
    ))
    assert marked.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    assert marked.should_issue is True
    assert marked.is_override is True
    assert NOVELTY_OPERATOR_MARKER in marked.novelty_signals


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


# ==========================================================================
# Stage 6.12: late-session evidence-burst fairness and novelty reserve.
#
# Root cause (proven by replaying real session-04 facts through this exact
# module, see docs/burst-scheduler-contract.md's Stage 6.12 section): the
# ordinary session budget was a single, undifferentiated counter checked
# *before* recurrence/novelty evaluation ever ran, so once early-session
# activity exhausted it, every later opportunity -- including the session's
# richest, latest, two-simultaneous-bird reviewed appearance -- was rejected
# unconditionally, regardless of novelty. The fix reorders the existing
# checks (recurrence/novelty now always evaluated first) and adds one small,
# bounded, session-relative-time rolling reserve that only an opportunity
# already proven not to be a suppressible recurrence may draw from once the
# ordinary/override budget is exhausted. Numbered comments below reference
# the Stage 6.12 task's own hardware-free test list.
# ==========================================================================


def _static_structure_decisions(
    scheduler: BurstScheduler, *, count: int, start_offset_ms: int = 1_000, step_ms: int = 1_200,
) -> list:
    """Feed `count` low-score, near-identical, brand-new-generation-per-
    occurrence opportunities through `scheduler` -- the same recurring
    static-structure fixture used earlier in this file (session-02's
    shepherd's-hook pattern) -- and return every decision."""

    decisions = []
    for index in range(count):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"static-structure-generation-{index}",
            subject_geometry=_box(dx=0.0003 * index),
            detector_score=0.05,
            detector_confirmation_count=1,
            tracker_support_count=0,
            session_offset_ms=start_offset_ms + index * step_ms,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)
        decisions.append(decision)
    return decisions


# --------------------------------------------------------------------------
# 1 / 4. Early static recurrence cannot consume all later novelty capacity;
# low-novelty recurrence cannot consume the reserve at all.
# --------------------------------------------------------------------------


def test_low_novelty_recurrence_never_consumes_novelty_reserve() -> None:
    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=60_000)
    # Exhaust the ordinary budget with one unrelated issuance first.
    first = scheduler.decide(_opportunity(
        track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100,
    ))
    assert first.outcome == DECISION_BURST_ISSUED
    _resolve(scheduler, first)

    # The static structure's first-ever sighting is, by the unmodified
    # Stage 6.9 rule, never itself a suppressible recurrence -- with the
    # ordinary budget already exhausted it may draw the reserve exactly
    # once, same as any other brand-new group would (a separate, pre-
    # existing rule, not what this test is about). What matters here is
    # every *subsequent* occurrence of the now-established, genuinely
    # recurring group: none of the remaining 29 may ever draw the reserve,
    # no matter how many arrive.
    decisions = _static_structure_decisions(scheduler, count=30, start_offset_ms=1_000)
    assert decisions[0].outcome == DECISION_NOVELTY_RESERVE_ISSUED
    assert all(decision.outcome != DECISION_NOVELTY_RESERVE_ISSUED for decision in decisions[1:])
    assert scheduler.diagnostics().novelty_reserve_issued == 1
    assert sum(1 for decision in decisions if decision.outcome == DECISION_SUPPRESSED_RECURRING_GEOMETRY) >= 25

    # The reserve still has room left for a genuinely novel, spatially
    # distinct opportunity later in the same session.
    genuine = scheduler.decide(_opportunity(
        track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80),
        detector_score=0.9, session_offset_ms=60_000,
    ))
    assert genuine.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    assert genuine.should_issue is True


# --------------------------------------------------------------------------
# 2. Hard session safety cap remains absolute (ordinary and override
# channels; test_override_respects_hard_session_budget above covers the
# override channel specifically).
# --------------------------------------------------------------------------


def test_ordinary_budget_stays_absolute_even_with_reserve_enabled() -> None:
    scheduler = _scheduler(max_bursts_per_session=3, recurrence_group_cooldown_ms=0)
    boxes = [(0.05, 0.05, 0.10, 0.10), (0.20, 0.20, 0.25, 0.25), (0.40, 0.40, 0.45, 0.45), (0.60, 0.60, 0.65, 0.65)]
    issued_ordinary = 0
    for index in range(3):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"generation-{index}", subject_geometry=boxes[index], session_offset_ms=index * 1_000,
        ))
        assert decision.outcome == DECISION_BURST_ISSUED
        _resolve(scheduler, decision)
        issued_ordinary += 1
    assert issued_ordinary == 3
    # A 4th, spatially distinct (still novel) opportunity can no longer use
    # the ordinary channel -- max_bursts_per_session's own absolute meaning
    # is unchanged; it may still fall through to the separately bounded
    # reserve, but never back into DECISION_BURST_ISSUED.
    fourth = scheduler.decide(_opportunity(
        track_generation_id="generation-3", subject_geometry=boxes[3], session_offset_ms=3_000,
    ))
    assert fourth.outcome != DECISION_BURST_ISSUED
    assert fourth.outcome in (DECISION_NOVELTY_RESERVE_ISSUED, DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED)


# --------------------------------------------------------------------------
# 3. Rate cap remains bounded, including reserve-funded issuance.
# --------------------------------------------------------------------------


def test_rate_budget_still_bounds_reserve_issuance() -> None:
    scheduler = _scheduler(
        max_bursts_per_session=1, max_bursts_per_minute=1, rate_window_ms=60_000,
        recurrence_group_cooldown_ms=0,
    )
    first = scheduler.decide(_opportunity(
        track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100,
    ))
    assert first.outcome == DECISION_BURST_ISSUED
    _resolve(scheduler, first)

    # Ordinary budget is exhausted and the rate window (capacity 1) was just
    # spent by the same issuance -- a materially novel opportunity a moment
    # later is rate-limited before the reserve is ever consulted.
    rate_limited = scheduler.decide(_opportunity(
        track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80),
        detector_score=0.9, session_offset_ms=500,
    ))
    assert rate_limited.outcome == DECISION_SUPPRESSED_RATE_BUDGET

    # Once the rate window genuinely elapses, the same opportunity can reach
    # and use the reserve.
    later = scheduler.decide(_opportunity(
        track_generation_id="genuine-generation-2", subject_geometry=(0.70, 0.70, 0.80, 0.80),
        detector_score=0.9, session_offset_ms=61_000,
    ))
    assert later.outcome == DECISION_NOVELTY_RESERVE_ISSUED


# --------------------------------------------------------------------------
# 5. Novel opportunity can use the reserve after ordinary allocation is
# exhausted (the exact reproduced session-04 mechanism).
# --------------------------------------------------------------------------


def test_novel_opportunity_uses_reserve_after_ordinary_exhausted() -> None:
    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=0)
    first = scheduler.decide(_opportunity(
        track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100,
    ))
    assert first.outcome == DECISION_BURST_ISSUED
    _resolve(scheduler, first)
    assert scheduler.health().session_budget_remaining == 0

    genuine = scheduler.decide(_opportunity(
        track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80),
        detector_score=0.9, session_offset_ms=1_000,
    ))
    assert genuine.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    assert genuine.should_issue is True
    assert scheduler.diagnostics().novelty_reserve_issued == 1


# --------------------------------------------------------------------------
# 6. Operator wildlife marker can use the reserve: see
# test_operator_marked_genuine_appearance_retains_burst_eligibility above.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 7 / 8. Engineering override remains explicitly labeled and never falls
# back to the fairness reserve; still cannot exceed its own absolute cap.
# --------------------------------------------------------------------------


def test_engineering_override_never_falls_back_to_novelty_reserve() -> None:
    scheduler = _scheduler(max_bursts_per_session=1, operator_override_reserved_bursts=1, recurrence_group_cooldown_ms=0)
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)
    second = scheduler.decide(_opportunity(track_generation_id="engineering-generation", subject_geometry=(0.20, 0.20, 0.25, 0.25), engineering_validation_request=True, session_offset_ms=200))
    assert second.outcome == DECISION_ENGINEERING_OVERRIDE_ISSUED
    _resolve(scheduler, second)

    # Both the ordinary and dedicated override allowances are now exhausted.
    # Unlike an operator marker, an engineering request has no fairness-
    # reserve fallback -- it remains a deliberately narrow, explicitly
    # labeled, one-off validation mechanism, not a wildlife-evidence path.
    third = scheduler.decide(_opportunity(track_generation_id="engineering-generation-2", subject_geometry=(0.40, 0.40, 0.45, 0.45), engineering_validation_request=True, session_offset_ms=300))
    assert third.outcome == DECISION_SUPPRESSED_SESSION_BUDGET
    assert third.should_issue is False


# --------------------------------------------------------------------------
# 9. Long session does not require known final duration.
# --------------------------------------------------------------------------


def test_reserve_works_without_knowing_final_session_duration() -> None:
    """The reserve is configured purely as a capacity-per-rolling-window
    rate; nothing in its implementation or configuration ever references a
    total/expected session length. A session that turns out to run for
    hours behaves identically to a short one at every point along the way."""

    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=0)
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)

    # Materially novel opportunities spaced widely across a simulated
    # multi-hour session (session-relative time only -- no wall-clock sleep).
    outcomes = []
    for hour in range(6):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"genuine-generation-{hour}",
            subject_geometry=(0.10 + hour * 0.01, 0.10 + hour * 0.01, 0.15 + hour * 0.01, 0.15 + hour * 0.01),
            detector_score=0.9, session_offset_ms=hour * 3_600_000,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)
        outcomes.append(decision.outcome)
    # Each arrives roughly an hour apart -- far outside the reserve's own
    # (much shorter) replenishment window -- so every one of them is treated
    # identically: the reserve has fully replenished by the time each
    # arrives, regardless of how long the session has already run or will
    # continue to run.
    assert outcomes == [DECISION_NOVELTY_RESERVE_ISSUED] * 6


# --------------------------------------------------------------------------
# 10 / 27. Rolling/token reserve state is deterministic; semantic
# fingerprints repeat.
# --------------------------------------------------------------------------


def test_novelty_reserve_state_is_deterministic() -> None:
    opportunities = [
        _opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100),
        *[
            _opportunity(
                track_generation_id=f"static-structure-generation-{index}",
                subject_geometry=_box(dx=0.0003 * index), detector_score=0.05,
                detector_confirmation_count=1, tracker_support_count=0,
                session_offset_ms=1_000 + index * 1_200,
            )
            for index in range(6)
        ],
        _opportunity(track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80), detector_score=0.9, session_offset_ms=20_000),
    ]

    def _run() -> list[str]:
        scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=60_000)
        outcomes = []
        for opportunity in opportunities:
            decision = scheduler.decide(opportunity)
            if decision.should_issue:
                _resolve(scheduler, decision)
            outcomes.append(decision.outcome)
        return outcomes

    first_run, second_run = _run(), _run()
    assert first_run == second_run
    assert first_run[-1] == DECISION_NOVELTY_RESERVE_ISSUED


# --------------------------------------------------------------------------
# 13. Session-relative time drives fairness decisions, not wall-clock time.
# --------------------------------------------------------------------------


def test_reserve_replenishment_uses_session_relative_time_only() -> None:
    scheduler = _scheduler(
        max_bursts_per_session=1, novelty_reserve_capacity=1, novelty_reserve_window_ms=10_000,
        recurrence_group_cooldown_ms=0,
    )
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)

    reserved = scheduler.decide(_opportunity(track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80), detector_score=0.9, session_offset_ms=1_000))
    assert reserved.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    _resolve(scheduler, reserved)

    # A second materially novel opportunity only 500ms of *session-relative*
    # time later (well inside the 10s reserve window) cannot yet reuse the
    # single reserve slot, no matter how much real wall-clock time this test
    # process itself takes to execute the two decide() calls.
    too_soon = scheduler.decide(_opportunity(track_generation_id="genuine-generation-2", subject_geometry=(0.30, 0.30, 0.35, 0.35), detector_score=0.9, session_offset_ms=1_500))
    assert too_soon.outcome == DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED

    # Once enough *session-relative* time has elapsed, the slot returns.
    later = scheduler.decide(_opportunity(track_generation_id="genuine-generation-3", subject_geometry=(0.30, 0.30, 0.35, 0.35), detector_score=0.9, session_offset_ms=11_200))
    assert later.outcome == DECISION_NOVELTY_RESERVE_ISSUED


# --------------------------------------------------------------------------
# 17. Stronger evidence may retain eligibility even when the ordinary
# budget is already exhausted (novelty escape + reserve, combined).
# --------------------------------------------------------------------------


def test_stronger_confidence_escape_can_use_reserve_after_exhaustion() -> None:
    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=60_000, stronger_confidence_delta=0.15)
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)

    weak_a = scheduler.decide(_opportunity(track_generation_id="generation-a", subject_geometry=_box(), detector_score=0.30, session_offset_ms=1_000))
    assert weak_a.outcome == DECISION_NOVELTY_RESERVE_ISSUED  # first sighting of this group, ordinary already exhausted
    _resolve(scheduler, weak_a)
    weak_b = scheduler.decide(_opportunity(track_generation_id="generation-b", subject_geometry=_box(dx=0.001), detector_score=0.30, session_offset_ms=2_000))
    assert weak_b.outcome == DECISION_SUPPRESSED_RECURRING_GEOMETRY  # now genuinely recurring, no novelty yet

    stronger = scheduler.decide(_opportunity(
        track_generation_id="generation-c", subject_geometry=_box(dx=0.001), detector_score=0.85, session_offset_ms=3_000,
    ))
    assert stronger.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    assert NOVELTY_STRONGER_CONFIDENCE in stronger.novelty_signals


# --------------------------------------------------------------------------
# 19. Same Zone does not collapse opportunities automatically -- the real
# session-04 two-simultaneous-bird geometry, distilled to a fixture.
# --------------------------------------------------------------------------


def test_two_simultaneous_subjects_in_one_zone_remain_independently_eligible() -> None:
    """Distilled from the real session-04 reviewed two-bird frame: a
    long-recurring feeder-perch box (`BASE_BOX`) and a second, spatially
    distinct box near the same feeder structure (same broad_class, same
    Zone/stream) must not collapse into one recurrence group merely because
    they share a class and physical structure."""

    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=60_000)
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)

    # Establish the long-recurring perch geometry as genuinely recurring.
    recurring_decisions = _static_structure_decisions(scheduler, count=4, start_offset_ms=1_000)
    assert recurring_decisions[-1].outcome == DECISION_SUPPRESSED_RECURRING_GEOMETRY

    # A second, simultaneous, geometry-divergent subject near the same
    # feeder structure (not overlapping the recurring perch box) remains
    # independently eligible -- it starts its own recurrence group and, the
    # ordinary budget already being exhausted, reaches a burst via the
    # fairness reserve rather than being silently folded into the first
    # subject's already-recurring, suppressed group.
    second_subject = scheduler.decide(_opportunity(
        track_generation_id="second-subject-generation",
        subject_geometry=(0.503, 0.558, 0.557, 0.611),  # the real "near red-glass feeder" box
        detector_score=0.79, session_offset_ms=6_000,
    ))
    assert second_subject.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    assert second_subject.recurrence_group_id != recurring_decisions[0].recurrence_group_id


# --------------------------------------------------------------------------
# 22 / 23 / 24 / 35. Provider reset / session stop / generation replacement
# clear fairness state; a benign reconnect (simply continuing to call
# decide(), with no reset()) leaves it intact.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("reason", [RESET_PROVIDER_RESET, RESET_SESSION_STOP, RESET_GENERATION_REPLACEMENT, RESET_ENGINEERING_RESET])
def test_reset_clears_novelty_reserve_state_too(reason: str) -> None:
    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=0)
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)
    reserved = scheduler.decide(_opportunity(track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80), detector_score=0.9, session_offset_ms=1_000))
    assert reserved.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    assert scheduler.diagnostics().novelty_reserve_issued == 1

    scheduler.reset(reason)

    assert scheduler.diagnostics().novelty_reserve_issued == 0
    assert scheduler.health().novelty_reserve_remaining == scheduler.config.novelty_reserve_capacity
    # Budgets are fresh, so an identical opportunity issues ordinarily again
    # rather than needing the reserve.
    fresh = scheduler.decide(_opportunity(track_generation_id="ordinary-generation-2", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    assert fresh.outcome == DECISION_BURST_ISSUED


def test_benign_reconnect_does_not_clear_novelty_reserve_state() -> None:
    """A benign transport reconnect never calls reset() at all (see
    docs/reconnect-continuity-contract.md / camera_node_live.py) -- it is
    simply more decide() calls with a different connection_segment_id.
    Fairness state (recurrence groups, reserve window) must survive exactly
    like every other piece of session-scoped scheduler state already does."""

    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=60_000)
    first = scheduler.decide(_opportunity(
        track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10),
        session_offset_ms=100, connection_segment_id="segment-a",
    ))
    _resolve(scheduler, first)
    reserved = scheduler.decide(_opportunity(
        track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80), detector_score=0.9,
        session_offset_ms=1_000, connection_segment_id="segment-a",
    ))
    assert reserved.outcome == DECISION_NOVELTY_RESERVE_ISSUED
    _resolve(scheduler, reserved)

    # A "reconnect" from this module's point of view is nothing more than a
    # later opportunity carrying a new connection_segment_id -- no reset()
    # call happens on the benign path.
    after_reconnect = scheduler.decide(_opportunity(
        track_generation_id="genuine-generation-2", subject_geometry=(0.70, 0.70, 0.80, 0.80), detector_score=0.9,
        session_offset_ms=1_200, connection_segment_id="segment-b",
    ))
    # Still inside the reserve window and the recurrence-group cooldown, and
    # nothing reset either -- the second, near-identical genuine sighting
    # reads as a recurring, not-yet-novel-again duplicate of the first,
    # exactly as it would with no reconnect involved at all.
    assert after_reconnect.outcome == DECISION_SUPPRESSED_RECURRING_GEOMETRY
    assert scheduler.diagnostics().novelty_reserve_issued == 1  # unchanged, not cleared


# --------------------------------------------------------------------------
# 32 / 33. Session-04 starvation synthetic fixture is fixed: a genuine late
# opportunity is not suppressed solely because it arrived late.
# --------------------------------------------------------------------------


def test_session_04_starvation_synthetic_fixture_is_fixed() -> None:
    """A distilled, hardware-free, synthetic replay of the real session-04
    mechanism proven in docs/burst-scheduler-contract.md: many early,
    low-value recurring-structure opportunities (and a couple of genuine
    early sightings) exhaust the ordinary session budget within the first
    slice of the session; a much later, materially novel, genuinely
    reviewed-worthy appearance must still retain burst eligibility."""

    scheduler = _scheduler(max_bursts_per_session=8, recurrence_group_cooldown_ms=60_000)
    outcomes = []

    # Several distinct "first sighting of a new static structure" bursts,
    # spread across the first minute -- exactly the pattern that spends the
    # ordinary budget in the real session without any suppression failure.
    for index in range(8):
        decision = scheduler.decide(_opportunity(
            track_generation_id=f"structure-{index}-generation",
            subject_geometry=(0.05 + index * 0.09, 0.05, 0.10 + index * 0.09, 0.10),
            detector_score=0.4, session_offset_ms=1_000 + index * 5_000,
        ))
        if decision.should_issue:
            _resolve(scheduler, decision)
        outcomes.append(decision.outcome)
    assert outcomes.count(DECISION_BURST_ISSUED) == 8
    assert scheduler.health().session_budget_remaining == 0

    # A long quiet stretch (session-04's own gap between its early activity
    # and its late, richest appearance was hundreds of seconds), then a
    # late, genuinely novel, spatially distinct appearance arrives.
    late_genuine = scheduler.decide(_opportunity(
        track_generation_id="late-genuine-generation",
        subject_geometry=(0.70, 0.70, 0.85, 0.85), detector_score=0.85,
        session_offset_ms=500_000,
    ))
    assert late_genuine.should_issue is True
    assert late_genuine.outcome == DECISION_NOVELTY_RESERVE_ISSUED


# --------------------------------------------------------------------------
# 34. Ordinary late static recurrence can still be suppressed -- arriving
# late does not, by itself, grant reserve access to a non-novel repeat.
# --------------------------------------------------------------------------


def test_late_static_recurrence_is_still_suppressed_not_rescued_by_reserve() -> None:
    scheduler = _scheduler(max_bursts_per_session=1, recurrence_group_cooldown_ms=60_000)
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)

    # Establish the group as genuinely recurring already very late in
    # session-relative time (300s in) -- the ordinary budget would be long
    # exhausted by this point in a real multi-minute session.
    _static_structure_decisions(scheduler, count=3, start_offset_ms=300_000, step_ms=1_200)

    # An immediate further repeat right after -- no elapsed cooldown, no
    # stronger evidence, no operator marker -- remains suppressed. Arriving
    # at session-relative time ~300s does not, by itself, grant reserve
    # access; only genuine novelty (evaluated by the unmodified recurrence
    # rules) ever does, exactly as it would at session-relative time zero.
    immediate_repeat = scheduler.decide(_opportunity(
        track_generation_id="static-structure-generation-late",
        subject_geometry=_box(), detector_score=0.05,
        detector_confirmation_count=1, tracker_support_count=0,
        session_offset_ms=303_700,
    ))
    assert immediate_repeat.outcome == DECISION_SUPPRESSED_RECURRING_GEOMETRY
    assert immediate_repeat.should_issue is False


# --------------------------------------------------------------------------
# Additional focused coverage: config validation, exports, and diagnostics
# shape for the new fields.
# --------------------------------------------------------------------------


def test_config_rejects_invalid_novelty_reserve_bounds() -> None:
    with pytest.raises(BurstSchedulerError):
        BurstSchedulerConfig(novelty_reserve_capacity=-1)
    with pytest.raises(BurstSchedulerError):
        BurstSchedulerConfig(novelty_reserve_window_ms=0)


def test_novelty_reserve_decisions_are_stable_exports() -> None:
    assert DECISION_NOVELTY_RESERVE_ISSUED in SCHEDULER_DECISIONS
    assert DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED in SCHEDULER_DECISIONS
    assert DECISION_NOVELTY_RESERVE_ISSUED in ISSUING_DECISIONS
    assert DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED not in ISSUING_DECISIONS


def test_diagnostics_and_health_partition_reserve_from_dedicated_channels() -> None:
    scheduler = _scheduler(max_bursts_per_session=1, operator_override_reserved_bursts=1, recurrence_group_cooldown_ms=0)
    first = scheduler.decide(_opportunity(track_generation_id="ordinary-generation", subject_geometry=(0.05, 0.05, 0.10, 0.10), session_offset_ms=100))
    _resolve(scheduler, first)
    override = scheduler.decide(_opportunity(track_generation_id="override-generation", subject_geometry=(0.20, 0.20, 0.25, 0.25), engineering_validation_request=True, session_offset_ms=200))
    _resolve(scheduler, override)
    reserved = scheduler.decide(_opportunity(track_generation_id="genuine-generation", subject_geometry=(0.70, 0.70, 0.80, 0.80), detector_score=0.9, session_offset_ms=300))
    _resolve(scheduler, reserved)

    diagnostics = scheduler.diagnostics()
    assert diagnostics.issued_count == 3
    assert diagnostics.novelty_reserve_issued == 1
    assert diagnostics.engineering_overrides == 1
    assert diagnostics.operator_overrides == 0
    # The three channels partition issued_count with no double-count.
    assert 1 + diagnostics.novelty_reserve_issued + diagnostics.engineering_overrides + diagnostics.operator_overrides == diagnostics.issued_count

    health = scheduler.health()
    assert 0 <= health.novelty_reserve_remaining <= scheduler.config.novelty_reserve_capacity
