"""Hardware-free tests for the Stage 6.11 reconnect-continuity decision
contract (`mockingbird.observation.reconnect_continuity`).

Pure, deterministic, resolution/species-independent -- no private media, no
network, no CUDA. See docs/reconnect-continuity-contract.md.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mockingbird.observation.contracts import FramePacket
from mockingbird.observation.reconnect_continuity import (
    CONTINUE_ACROSS_TRANSPORT_RECONNECT,
    REASON_ANALYSIS_PROFILE_INCOMPATIBLE,
    REASON_BENIGN_TRANSPORT_RECONNECT,
    REASON_CAMERA_IDENTITY_CHANGED,
    REASON_CAMERA_NODE_IDENTITY_CHANGED,
    REASON_CONNECTION_SEGMENT_NOT_ADVANCED,
    REASON_EXCESSIVE_RECONNECT_GAP,
    REASON_EXCESSIVE_TEMPORAL_UNCERTAINTY,
    REASON_EXPLICIT_DISCONTINUITY,
    REASON_MISSING_CONNECTION_SEGMENT_IDENTITY,
    REASON_MISSING_PROVIDER_GENERATION_PROVENANCE,
    REASON_MISSING_SOURCE_GAP_PROVENANCE,
    REASON_MISSING_TEMPORAL_UNCERTAINTY_PROVENANCE,
    REASON_PROVIDER_GENERATION_CHANGED,
    REASON_SHUTDOWN_START_BOUNDARY,
    REASON_STREAM_CHANGED,
    RECONNECT_CONTINUITY_DECISIONS,
    REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE,
    RESET_SOURCE_GENERATION,
    ReconnectBridgeConfig,
    ReconnectContinuityDecision,
    classify_frame_reconnect_boundary,
    is_reconnect_boundary_signal,
)


def _frame(offset_ms: int, **overrides: object) -> FramePacket:
    values: dict[str, object] = {
        "stream_id": "stream-a",
        "media_asset_id": f"replay:{offset_ms}",
        "captured_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=offset_ms),
        "frame_id": f"frame-{offset_ms}",
        "source_offset_ms": offset_ms,
        "width": 1280,
        "height": 720,
        "provider_generation": "gen-1",
    }
    values.update(overrides)
    return FramePacket(**values)


def _benign_previous(offset_ms: int = 10_000, *, segment: str = "segment-a", **overrides: object) -> FramePacket:
    values: dict[str, object] = {"timing_facts": (("connection_segment_id", segment),)}
    values.update(overrides)
    return _frame(offset_ms, **values)


def _benign_current(
    offset_ms: int = 12_500, *, segment: str = "segment-b", uncertainty_ms: int = 50, **overrides: object,
) -> FramePacket:
    values: dict[str, object] = {
        "timing_facts": (
            ("connection_segment_id", segment),
            ("temporal_discontinuity", True),
            ("temporal_uncertainty_ms", uncertainty_ms),
        ),
    }
    values.update(overrides)
    return _frame(offset_ms, **values)


# --- outer gate: is anything discontinuous signaled at all? ----------------


def test_no_signal_never_indicates_a_boundary_backward_compatible() -> None:
    """Every pre-Stage-6.8 replay input carries neither signal; the outer
    gate must return False so the classifier is never even invoked and
    tracking continues completely unaffected by this stage."""
    assert is_reconnect_boundary_signal(_frame(1000), _frame(1200)) is False


def test_temporal_discontinuity_fact_alone_is_a_signal() -> None:
    current = _frame(1200, timing_facts=(("temporal_discontinuity", True),))
    assert is_reconnect_boundary_signal(_frame(1000), current) is True


def test_provider_generation_change_alone_is_a_signal() -> None:
    current = _frame(1200, provider_generation="gen-2")
    assert is_reconnect_boundary_signal(_frame(1000), current) is True


# --- scenario 1 / benign eligibility: bridges when fully provenanced -------


def test_benign_reconnect_with_full_provenance_continues() -> None:
    decision = classify_frame_reconnect_boundary(_benign_previous(), _benign_current(), ReconnectBridgeConfig())
    assert decision.decision == CONTINUE_ACROSS_TRANSPORT_RECONNECT
    assert decision.reason == REASON_BENIGN_TRANSPORT_RECONNECT
    assert decision.source_gap_ms == 2500
    assert decision.temporal_uncertainty_ms == 50
    assert decision.previous_connection_segment_id == "segment-a"
    assert decision.current_connection_segment_id == "segment-b"


# --- scenarios 13-15: transport-local churn alone never disqualifies -------


def test_transport_sequence_reset_alone_does_not_prevent_bridging() -> None:
    previous = _benign_previous(frame_sequence=412)
    current = _benign_current(frame_sequence=1)
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == CONTINUE_ACROSS_TRANSPORT_RECONNECT


def test_source_offset_reset_alone_does_not_prevent_bridging() -> None:
    """`original_source_offset_ms` (the raw connection-local value Stage 6.8
    preserves as additive provenance) resets to near zero on every
    reconnect; `source_offset_ms` itself (session-relative, already
    monotonic) is what the decision actually reads."""
    previous = _benign_previous(offset_ms=10_000, timing_facts=(
        ("connection_segment_id", "segment-a"), ("original_source_offset_ms", 9_800),
    ))
    current = _benign_current(offset_ms=12_500, timing_facts=(
        ("connection_segment_id", "segment-b"), ("temporal_discontinuity", True),
        ("temporal_uncertainty_ms", 50), ("original_source_offset_ms", 0),
    ))
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == CONTINUE_ACROSS_TRANSPORT_RECONNECT


def test_connection_segment_ordinal_change_alone_does_not_prevent_bridging() -> None:
    previous = _benign_previous(timing_facts=(
        ("connection_segment_id", "segment-a"), ("connection_segment_ordinal", 3),
    ))
    current = _benign_current(timing_facts=(
        ("connection_segment_id", "segment-b"), ("connection_segment_ordinal", 4),
        ("temporal_discontinuity", True), ("temporal_uncertainty_ms", 50),
    ))
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == CONTINUE_ACROSS_TRANSPORT_RECONNECT


# --- scenarios 6-10: confidently evidenced source-generation resets --------


def test_stream_change_resets() -> None:
    current = _benign_current(stream_id="stream-b")
    decision = classify_frame_reconnect_boundary(_benign_previous(), current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_STREAM_CHANGED


def test_provider_generation_change_resets() -> None:
    current = _benign_current(provider_generation="gen-2")
    decision = classify_frame_reconnect_boundary(_benign_previous(), current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_PROVIDER_GENERATION_CHANGED


def test_camera_identity_change_resets() -> None:
    previous = _benign_previous(timing_facts=(("connection_segment_id", "segment-a"), ("camera_id", "cam-1")))
    current = _benign_current(timing_facts=(
        ("connection_segment_id", "segment-b"), ("temporal_discontinuity", True),
        ("temporal_uncertainty_ms", 50), ("camera_id", "cam-2"),
    ))
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_CAMERA_IDENTITY_CHANGED


def test_camera_node_identity_change_resets() -> None:
    previous = _benign_previous(timing_facts=(("connection_segment_id", "segment-a"), ("camera_node_id", "node-1")))
    current = _benign_current(timing_facts=(
        ("connection_segment_id", "segment-b"), ("temporal_discontinuity", True),
        ("temporal_uncertainty_ms", 50), ("camera_node_id", "node-2"),
    ))
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_CAMERA_NODE_IDENTITY_CHANGED


def test_explicit_analysis_profile_id_incompatibility_resets() -> None:
    previous = _benign_previous(timing_facts=(
        ("connection_segment_id", "segment-a"), ("analysis_profile_id", "profile-1"),
    ))
    current = _benign_current(timing_facts=(
        ("connection_segment_id", "segment-b"), ("temporal_discontinuity", True),
        ("temporal_uncertainty_ms", 50), ("analysis_profile_id", "profile-2"),
    ))
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_ANALYSIS_PROFILE_INCOMPATIBLE


def test_dimension_incompatibility_resets() -> None:
    current = _benign_current(width=640, height=480)
    decision = classify_frame_reconnect_boundary(_benign_previous(), current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_ANALYSIS_PROFILE_INCOMPATIBLE


def test_explicit_discontinuity_reason_resets() -> None:
    current = _benign_current(timing_facts=(
        ("connection_segment_id", "segment-b"), ("temporal_discontinuity", True),
        ("temporal_uncertainty_ms", 50), ("explicit_discontinuity_reason", "application_shutdown"),
    ))
    decision = classify_frame_reconnect_boundary(_benign_previous(), current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_EXPLICIT_DISCONTINUITY


def test_shutdown_start_boundary_resets() -> None:
    current = _benign_current(timing_facts=(
        ("connection_segment_id", "segment-b"), ("temporal_discontinuity", True),
        ("temporal_uncertainty_ms", 50), ("shutdown_boundary", True),
    ))
    decision = classify_frame_reconnect_boundary(_benign_previous(), current, ReconnectBridgeConfig())
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_SHUTDOWN_START_BOUNDARY


def test_excessive_reconnect_gap_resets() -> None:
    config = ReconnectBridgeConfig(maximum_reconnect_gap_ms=5_000)
    current = _benign_current(offset_ms=10_000 + 20_000)
    decision = classify_frame_reconnect_boundary(_benign_previous(), current, config)
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_EXCESSIVE_RECONNECT_GAP


def test_high_temporal_uncertainty_resets() -> None:
    """Scenario 12: a *known* but excessive uncertainty is confident
    evidence of a discontinuity too uncertain to safely bridge -- distinct
    from *missing* uncertainty provenance, which is insufficient-provenance
    (see test_missing_temporal_uncertainty_rejects_continuity below)."""
    config = ReconnectBridgeConfig(maximum_temporal_uncertainty_ms=2_000)
    current = _benign_current(uncertainty_ms=5_000)
    decision = classify_frame_reconnect_boundary(_benign_previous(), current, config)
    assert decision.decision != CONTINUE_ACROSS_TRANSPORT_RECONNECT
    assert decision.decision == RESET_SOURCE_GENERATION
    assert decision.reason == REASON_EXCESSIVE_TEMPORAL_UNCERTAINTY


# --- scenario 11: missing timeline provenance rejects continuity -----------


def test_missing_connection_segment_identity_rejects_continuity() -> None:
    previous = _frame(10_000)  # no connection_segment_id at all
    current = _frame(12_500, timing_facts=(("temporal_discontinuity", True), ("temporal_uncertainty_ms", 50)))
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE
    assert decision.reason == REASON_MISSING_CONNECTION_SEGMENT_IDENTITY


def test_missing_source_gap_rejects_continuity() -> None:
    previous = _benign_previous()
    current = FramePacket(**{**_benign_current().__dict__, "source_offset_ms": None})
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE
    assert decision.reason == REASON_MISSING_SOURCE_GAP_PROVENANCE


def test_missing_temporal_uncertainty_rejects_continuity() -> None:
    previous = _benign_previous()
    current = _frame(12_500, timing_facts=(("connection_segment_id", "segment-b"), ("temporal_discontinuity", True)))
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE
    assert decision.reason == REASON_MISSING_TEMPORAL_UNCERTAINTY_PROVENANCE


def test_missing_provider_generation_rejects_continuity() -> None:
    previous = _benign_previous()
    current = _benign_current(provider_generation=None)
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE
    assert decision.reason == REASON_MISSING_PROVIDER_GENERATION_PROVENANCE


def test_connection_segment_not_advanced_rejects_continuity() -> None:
    """A discontinuity fired but the segment identity did not actually
    change -- the session-timeline provenance disagrees with itself; the
    safe default is to reject rather than guess which fact is right."""
    previous = _benign_previous(segment="segment-a")
    current = _benign_current(segment="segment-a")
    decision = classify_frame_reconnect_boundary(previous, current, ReconnectBridgeConfig())
    assert decision.decision == REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE
    assert decision.reason == REASON_CONNECTION_SEGMENT_NOT_ADVANCED


# --- contract/bounds validation --------------------------------------------


def test_decision_rejects_an_unknown_decision_value() -> None:
    with pytest.raises(ValueError, match="invalid_reconnect_continuity_decision"):
        ReconnectContinuityDecision("not_a_real_decision", "reason")


@pytest.mark.parametrize(
    "override",
    [
        {"maximum_reconnect_gap_ms": 0},
        {"maximum_reconnect_bridge_duration_ms": 0},
        {"maximum_reconnect_bridge_frames": 0},
        {"maximum_reconnect_geometry_displacement": 0.0},
        {"maximum_reconnect_size_change_ratio": 0.0},
        {"minimum_post_reconnect_support": 0},
        {"ambiguity_policy": "guess"},
    ],
)
def test_reconnect_bridge_config_rejects_out_of_bound_values(override: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="invalid_reconnect_bridge_config"):
        ReconnectBridgeConfig(**override)


def test_reconnect_bridge_config_defaults_are_general_not_session_specific() -> None:
    """Real session-03/04 gaps measured 940-6868ms (see
    docs/reconnect-continuity-contract.md); the default bound leaves
    generous, principled headroom above that observed range rather than
    being tuned to just barely include it."""
    config = ReconnectBridgeConfig()
    assert config.maximum_reconnect_gap_ms >= 2 * 6_868
    assert config.ambiguity_policy == "reject"


def test_all_four_decision_values_are_stable_and_distinct() -> None:
    assert len(RECONNECT_CONTINUITY_DECISIONS) == len(set(RECONNECT_CONTINUITY_DECISIONS)) == 4
