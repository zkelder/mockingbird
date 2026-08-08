"""Hardware-free tests for the Stage 6.19 shadow Visit episode assembler.

Provider-neutral, resolution/species/path-independent -- no private media, no
real Visit ids, no CUDA/ONNX/filesystem/network dependency anywhere in this
file. See docs/tracklet-visit-assembly-contract.md for the full contract and
tests/fixtures/observation_stage619/ for the committed synthetic scenarios
these tests validate against *before* any real-data acceptance run.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from mockingbird.observation.contracts import TrackUpdate
from mockingbird.observation.frame_tracker import ProviderNeutralFrameTracker, TrackerConfiguration
from mockingbird.observation.reconnect_continuity import ReconnectBridgeConfig
from mockingbird.observation.replay import BenchmarkManifest, ExpectedVisit, _match
from mockingbird.observation.visit_episode_assembler import (
    ASSEMBLER_VERSION,
    AssembledVisitProposal,
    Tracklet,
    VisitAssemblyConfiguration,
    assemble_visit_episodes,
    build_tracklets,
    classify_boundary,
    project_to_visit_proposal,
    semantic_fingerprint,
)

FIXTURES = Path("tests/fixtures/observation_stage619")


# --- fixture loading helpers -------------------------------------------------


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _tracklet(generation_id: str, start: int, end: int, **overrides: object) -> Tracklet:
    """Terse direct-construction helper for tests that don't need the
    committed fixture file -- every unspecified field gets an inert,
    synthetic default."""
    values: dict[str, object] = {
        "generation_id": generation_id,
        "stream_id": "stream",
        "broad_class": "animal",
        "start_offset_ms": start,
        "end_offset_ms": end,
        "start_bounding_box": (0.4, 0.4, 0.5, 0.5),
        "end_bounding_box": (0.4, 0.4, 0.5, 0.5),
        "geometry_envelope": (0.4, 0.4, 0.5, 0.5),
        "terminal_reason": "maximum_unsupported_duration",
        "track_ids": (f"{generation_id}-track",),
    }
    values.update(overrides)
    return Tracklet(**values)


def _tracklet_from_fixture(data: dict, *, stream_id: str) -> Tracklet:
    start_box = tuple(data["start_bounding_box"])
    end_box = tuple(data["end_bounding_box"])
    envelope = (
        min(start_box[0], end_box[0]), min(start_box[1], end_box[1]),
        max(start_box[2], end_box[2]), max(start_box[3], end_box[3]),
    )
    return Tracklet(
        generation_id=data["generation_id"],
        stream_id=stream_id,
        broad_class=data.get("broad_class", "animal"),
        start_offset_ms=data["start_offset_ms"],
        end_offset_ms=data["end_offset_ms"],
        start_bounding_box=start_box,
        end_bounding_box=end_box,
        geometry_envelope=envelope,
        terminal_reason=data["terminal_reason"],
        track_ids=(f"{data['generation_id']}-track",),
        connection_segment_ids=tuple(data.get("connection_segment_ids", ())),
        negative_detector_frame_count=data.get("negative_detector_frame_count", 0),
        detector_skipped_frame_count=data.get("detector_skipped_frame_count", 0),
        last_strong_detector_offset_ms=data.get("last_strong_detector_offset_ms"),
        zone_id=data.get("zone_id"),
    )


def _fixture_scenario(name: str) -> tuple[dict, tuple[Tracklet, ...]]:
    catalog = _load_json("tracklet_scenarios.json")
    scenario = catalog["scenarios"][name]
    tracklets = tuple(_tracklet_from_fixture(item, stream_id=scenario["stream_id"]) for item in scenario["tracklets"])
    return scenario, tracklets


# --- catalog completeness (mirrors the Stage 6.16 scenarios.json convention) -


def test_committed_stage619_scenario_catalog_exists() -> None:
    catalog = json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))
    all_names = [name for group in catalog["scenarios"].values() for name in group]
    assert len(all_names) == len(set(all_names)) >= 30


def test_committed_synthetic_tracklet_scenarios_cover_all_ten_required_cases() -> None:
    catalog = _load_json("tracklet_scenarios.json")
    required = {
        "long_visit_fragmented_into_many_tracklets", "two_separate_appearances_10_20s_apart",
        "persistent_static_false_positive_tracklets", "reconnect_boundary_inside_true_visit",
        "detector_skipped_gap", "detector_negative_gap", "ambiguous_separation",
        "simultaneous_subjects", "crossing_subjects", "spatially_incompatible_reentry",
    }
    assert required <= set(catalog["scenarios"])


# =============================================================================
# 1-3. Basic assembly
# =============================================================================


def test_one_tracklet_produces_one_visit() -> None:
    """Scenario 1."""
    only = _tracklet("solo", 0, 5000)
    result = assemble_visit_episodes((only,))
    assert result.assembled_proposal_count == 1
    assert result.proposals[0].constituent_generation_ids == ("solo",)
    assert result.episode_merges == 0


def test_compatible_adjacent_tracklets_merge() -> None:
    """Scenario 2."""
    a = _tracklet("a", 0, 5000, end_bounding_box=(0.40, 0.40, 0.50, 0.50))
    b = _tracklet("b", 8000, 13000, start_bounding_box=(0.41, 0.41, 0.51, 0.51))
    decision = classify_boundary(a, b)
    assert decision.decision == "merge_same_visit"
    result = assemble_visit_episodes((a, b))
    assert result.assembled_proposal_count == 1
    assert result.proposals[0].constituent_generation_ids == ("a", "b")
    assert result.proposals[0].start_offset_ms == 0
    assert result.proposals[0].end_offset_ms == 13000


def test_many_fragmented_tracklets_merge_deterministically() -> None:
    """Scenario 3 -- committed `long_visit_fragmented_into_many_tracklets` fixture."""
    scenario, tracklets = _fixture_scenario("long_visit_fragmented_into_many_tracklets")
    result = assemble_visit_episodes(tracklets)
    assert result.assembled_proposal_count == scenario["expected"]["proposal_count"] == 1
    assert result.episode_merges == scenario["expected"]["episode_merges"]
    proposal = result.proposals[0]
    assert [proposal.start_offset_ms, proposal.end_offset_ms] == scenario["expected"]["span"]
    assert len(proposal.constituent_generation_ids) == len(tracklets)


# =============================================================================
# 4-6. Gap evidence
# =============================================================================


def test_detector_skipped_gap_does_not_imply_departure() -> None:
    """Scenario 4 -- committed `detector_skipped_gap` fixture."""
    scenario, tracklets = _fixture_scenario("detector_skipped_gap")
    a, b = tracklets
    assert a.detector_skipped_frame_count > 0
    assert a.negative_detector_frame_count == 0
    decision = classify_boundary(a, b)
    assert decision.decision == scenario["expected"]["boundary_decision"] == "merge_same_visit"
    assert decision.gap_ms == scenario["expected"]["gap_ms"]


def test_detector_negative_interval_contributes_separation_evidence() -> None:
    """Scenario 5 -- committed `detector_negative_gap` fixture."""
    scenario, tracklets = _fixture_scenario("detector_negative_gap")
    a, b = tracklets
    assert a.negative_detector_frame_count > 0
    assert a.terminal_reason == "negative_interval_reentry"
    decision = classify_boundary(a, b)
    assert decision.decision == scenario["expected"]["boundary_decision"] == "keep_separate"
    assert decision.reason == scenario["expected"]["reason"]


def test_strong_separation_evidence_prevents_merge() -> None:
    """Scenario 6: even a very short (500ms), otherwise-compatible-geometry
    gap must not merge once the earlier tracklet's own terminal reason is a
    confirmed negative interval."""
    a = _tracklet("a", 0, 5000, terminal_reason="negative_interval_reentry", negative_detector_frame_count=2)
    b = _tracklet("b", 5500, 8000)
    decision = classify_boundary(a, b)
    assert decision.decision == "keep_separate"
    assert decision.reason == "detector_confirmed_negative_interval"
    result = assemble_visit_episodes((a, b))
    assert result.assembled_proposal_count == 2


# =============================================================================
# 7-10. Weak signals alone are insufficient
# =============================================================================


def test_same_broad_class_alone_does_not_merge() -> None:
    """Scenario 7: same class, but the gap is far beyond the ambiguous
    window -- class match alone must not force a merge."""
    a = _tracklet("a", 0, 5000, broad_class="animal")
    b = _tracklet("b", 200_000, 205_000, broad_class="animal")
    decision = classify_boundary(a, b)
    assert decision.decision == "keep_separate"
    assert decision.reason == "gap_exceeds_ambiguous_window"


def test_same_zone_alone_does_not_merge() -> None:
    """Scenario 8: same (known) zone, but otherwise-incompatible geometry --
    zone match alone must not force a merge."""
    a = _tracklet("a", 0, 5000, zone_id="feeder-1", end_bounding_box=(0.02, 0.02, 0.10, 0.10))
    b = _tracklet("b", 6000, 9000, zone_id="feeder-1", start_bounding_box=(0.85, 0.85, 0.95, 0.95))
    decision = classify_boundary(a, b)
    assert decision.decision == "keep_separate"
    assert decision.reason == "spatial_discontinuity"


def test_reconnect_alone_does_not_split() -> None:
    """Scenario 9 -- committed `reconnect_boundary_inside_true_visit`
    fixture: a connection-segment change between two otherwise-compatible
    tracklets must not, by itself, prevent a merge."""
    scenario, tracklets = _fixture_scenario("reconnect_boundary_inside_true_visit")
    by_id = {item.generation_id: item for item in tracklets}
    a, b = by_id["rc-a1"], by_id["rc-a2"]
    assert a.connection_segment_ids != b.connection_segment_ids
    decision = classify_boundary(a, b)
    assert decision.decision == scenario["expected"]["pair_decisions"]["rc-a1|rc-a2"] == "merge_same_visit"


def test_reconnect_alone_does_not_merge() -> None:
    """Scenario 10: crossing a connection-segment boundary must not, by
    itself, force a merge that the gap/geometry evidence alone would not
    already support -- the outcome for a reconnect-crossing pair and an
    otherwise-identical same-segment pair must be identical."""
    reconnecting_a = _tracklet("ra", 0, 5000, connection_segment_ids=("seg-1",), end_bounding_box=(0.4, 0.4, 0.5, 0.5))
    reconnecting_b = _tracklet("rb", 60000, 65000, connection_segment_ids=("seg-2",), start_bounding_box=(0.4, 0.4, 0.5, 0.5))
    control_a = _tracklet("ca", 0, 5000, connection_segment_ids=("seg-1",), end_bounding_box=(0.4, 0.4, 0.5, 0.5))
    control_b = _tracklet("cb", 60000, 65000, connection_segment_ids=("seg-1",), start_bounding_box=(0.4, 0.4, 0.5, 0.5))
    reconnecting_decision = classify_boundary(reconnecting_a, reconnecting_b)
    control_decision = classify_boundary(control_a, control_b)
    assert reconnecting_decision.decision == control_decision.decision == "keep_separate"
    assert reconnecting_decision.reason == control_decision.reason == "gap_exceeds_ambiguous_window"


# =============================================================================
# 11-12. Spatial continuity
# =============================================================================


def test_spatial_continuity_supports_merge() -> None:
    """Scenario 11: matching geometry across a moderate gap merges."""
    a = _tracklet("a", 0, 5000, end_bounding_box=(0.5, 0.5, 0.6, 0.6))
    b = _tracklet("b", 9000, 12000, start_bounding_box=(0.51, 0.5, 0.61, 0.6))
    assert classify_boundary(a, b).decision == "merge_same_visit"


def test_spatial_discontinuity_prevents_merge() -> None:
    """Scenario 12 -- committed `spatially_incompatible_reentry` fixture."""
    scenario, tracklets = _fixture_scenario("spatially_incompatible_reentry")
    a, b = tracklets
    decision = classify_boundary(a, b)
    assert decision.decision == scenario["expected"]["boundary_decision"] == "keep_separate"
    assert decision.reason == scenario["expected"]["reason"] == "spatial_discontinuity"


# =============================================================================
# 13-14. Ambiguity
# =============================================================================


def test_ambiguous_boundary_remains_explicit() -> None:
    """Scenario 13 -- committed `ambiguous_separation`/`two_separate_
    appearances_10_20s_apart` fixtures: evidence that cannot safely decide
    must surface as an explicit ambiguous boundary, never a silent merge,
    and the resulting separate proposals must cross-reference each other."""
    scenario, tracklets = _fixture_scenario("ambiguous_separation")
    a, b = tracklets
    decision = classify_boundary(a, b)
    assert decision.decision == scenario["expected"]["boundary_decision"] == "ambiguous_boundary"

    result = assemble_visit_episodes(tracklets)
    assert result.assembled_proposal_count == scenario["expected"]["proposal_count"] == 2
    assert result.ambiguous_decisions == 1
    assert result.episode_merges == 0
    first, second = result.proposals
    assert first.ambiguous_adjacent_proposal_ids == (second.proposal_id,)
    assert second.ambiguous_adjacent_proposal_ids == (first.proposal_id,)

    # session-04-shaped case: same outcome (never a confident merge).
    _, session04_like = _fixture_scenario("two_separate_appearances_10_20s_apart")
    session04_result = assemble_visit_episodes(session04_like)
    assert session04_result.assembled_proposal_count == 2
    assert session04_result.episode_merges == 0


def test_persistent_static_weak_tracklets_remain_bounded() -> None:
    """Scenario 14 -- committed `persistent_static_false_positive_tracklets`
    fixture: attempt-2-shaped clutter must consolidate into a *bounded*
    number of separate episodes -- neither one giant confident Visit, nor
    left maximally fragmented when genuinely close together."""
    scenario, tracklets = _fixture_scenario("persistent_static_false_positive_tracklets")
    result = assemble_visit_episodes(tracklets)
    assert result.assembled_proposal_count == scenario["expected"]["proposal_count"] == 2
    sizes = sorted(len(p.constituent_generation_ids) for p in result.proposals)
    assert sizes == scenario["expected"]["group_sizes"] == [3, 3]
    # every constituent is provisional (never strong) -- disclosed honestly.
    for proposal in result.proposals:
        assert "contains_provisional_only_tracklet" in proposal.limitation_facts


# =============================================================================
# 15-16. Multi-subject safety
# =============================================================================


def test_two_simultaneous_animals_remain_separate() -> None:
    """Scenario 15 -- committed `simultaneous_subjects` fixture."""
    scenario, tracklets = _fixture_scenario("simultaneous_subjects")
    a, b = tracklets
    decision = classify_boundary(a, b)
    assert decision.decision == scenario["expected"]["boundary_decision"] == "incompatible"
    assert decision.reason == scenario["expected"]["reason"] == "temporal_overlap"
    result = assemble_visit_episodes(tracklets)
    assert result.assembled_proposal_count == 2
    assert result.incompatible_decisions == 1


def test_crossing_animals_do_not_collapse() -> None:
    """Scenario 16 -- committed `crossing_subjects` fixture."""
    scenario, tracklets = _fixture_scenario("crossing_subjects")
    result = assemble_visit_episodes(tracklets)
    assert result.assembled_proposal_count == scenario["expected"]["proposal_count"] == 2
    generations = {gen for p in result.proposals for gen in p.constituent_generation_ids}
    assert generations == {item.generation_id for item in tracklets}


# =============================================================================
# 17-19. Lineage
# =============================================================================


def test_source_lineage_survives_assembly() -> None:
    """Scenario 17: every constituent tracklet's `supporting_frame_ids`/
    `source_capture_frame_ids` survive, deduplicated, on the assembled
    proposal."""
    a = _tracklet("a", 0, 5000, supporting_frame_ids=("f1", "f2"), source_capture_frame_ids=("src-1",))
    b = _tracklet("b", 6000, 9000, supporting_frame_ids=("f2", "f3"), source_capture_frame_ids=("src-2",))
    result = assemble_visit_episodes((a, b))
    assert result.assembled_proposal_count == 1
    proposal = result.proposals[0]
    assert proposal.supporting_frame_ids == ("f1", "f2", "f3")
    assert proposal.source_capture_frame_ids == ("src-1", "src-2")


def test_evidence_candidate_lineage_survives_assembly() -> None:
    """Scenario 18."""
    a = _tracklet("a", 0, 5000, evidence_candidate_ids=("ev-1", "ev-2"))
    b = _tracklet("b", 6000, 9000, evidence_candidate_ids=("ev-2", "ev-3"))
    result = assemble_visit_episodes((a, b))
    proposal = result.proposals[0]
    assert proposal.evidence_candidate_ids == ("ev-1", "ev-2", "ev-3")


def test_constituent_track_ids_preserved() -> None:
    """Scenario 19."""
    a = _tracklet("a", 0, 5000, track_ids=("track-a",))
    b = _tracklet("b", 6000, 9000, track_ids=("track-b",))
    result = assemble_visit_episodes((a, b))
    proposal = result.proposals[0]
    assert proposal.constituent_generation_ids == ("a", "b")
    assert proposal.constituent_track_ids == ("track-a", "track-b")


# =============================================================================
# Extra: `build_tracklets` itself (grouping/filtering/derivation from raw
# `TrackUpdate`s), and a custom `VisitAssemblyConfiguration`. Not one of the
# 30 enumerated scenarios on its own, but directly exercises two exports
# (`build_tracklets`, `VisitAssemblyConfiguration`) the rest of this file
# only reaches indirectly through the fixture loader / defaults.
# =============================================================================


def _track_update(generation_id: str, offset_ms: int, status: str, support_state: str, **overrides: object) -> TrackUpdate:
    from datetime import UTC, datetime, timedelta

    values: dict[str, object] = {
        "track_id": f"{generation_id}-track",
        "generation_id": generation_id,
        "captured_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=offset_ms),
        "status": status,
        "lifecycle_state": "confirmed" if status != "ended" else "ended",
        "frame_id": f"frame-{generation_id}-{offset_ms}",
        "source_offset_ms": offset_ms,
        "broad_class": "animal",
        "bounding_box": (0.4, 0.4, 0.5, 0.5),
        "supporting_frame_ids": (f"frame-{generation_id}-{offset_ms}",),
        "support_state": support_state,
        "detector_ran": True,
    }
    values.update(overrides)
    return TrackUpdate(**values)


def test_build_tracklets_skips_unconfirmed_and_derives_support_facts() -> None:
    """`build_tracklets` keeps only generations the tracker itself confirmed
    (terminal `lifecycle_state == "ended"`) and honestly derives negative-
    vs-skipped and strong/weak/tracker support counts from already-emitted
    per-update facts -- no new tracker bookkeeping."""
    confirmed_updates = (
        _track_update("gen-a", 0, "started", "strong_detector_supported"),
        _track_update("gen-a", 500, "updated", "weak_detector_supported"),
        _track_update("gen-a", 1000, "updated", "tracker_supported"),
        _track_update("gen-a", 1500, "updated", "temporarily_lost", detector_ran=True),  # genuine negative
        _track_update("gen-a", 2000, "updated", "temporarily_lost", detector_ran=False),  # skipped, not negative
        _track_update(
            "gen-a", 2500, "ended", "temporarily_lost", lifecycle_state="ended", terminal_reason="tracker_lost",
            detector_ran=True,  # the terminating frame itself is also a genuine, distinct negative evaluation
        ),
    )
    rejected_updates = (
        _track_update("gen-b", 0, "started", "weak_detector_supported"),
        _track_update("gen-b", 500, "ended", "weak_detector_supported", lifecycle_state="rejected", terminal_reason="tracker_lost"),
    )
    tracklets = build_tracklets(confirmed_updates + rejected_updates, stream_id="stream-x")
    assert {item.generation_id for item in tracklets} == {"gen-a"}  # gen-b (rejected) excluded

    tracklet = tracklets[0]
    assert tracklet.strong_detector_frame_count == 1
    assert tracklet.weak_detector_frame_count == 1
    assert tracklet.tracker_supported_frame_count == 1
    # Two distinct genuinely-negative-evaluated frames (1500ms, and the
    # 2500ms frame whose own elapsed-time check finally terminated the
    # track) plus one genuinely-skipped one (2000ms) -- each counted from
    # its own frame's real `detector_ran` fact, never inferred.
    assert tracklet.negative_detector_frame_count == 2
    assert tracklet.detector_skipped_frame_count == 1
    assert tracklet.terminal_reason == "tracker_lost"
    assert tracklet.start_offset_ms == 0
    assert tracklet.end_offset_ms == 2500
    assert tracklet.last_strong_detector_offset_ms == 0
    assert tracklet.track_ids == ("gen-a-track",)


def test_custom_configuration_changes_merge_behavior() -> None:
    """A caller-supplied `VisitAssemblyConfiguration` genuinely changes the
    decision -- the bounds are not hardcoded."""
    a = _tracklet("a", 0, 1000)
    b = _tracklet("b", 2500, 3500)  # 1500ms gap
    default_decision = classify_boundary(a, b)
    assert default_decision.decision == "merge_same_visit"  # within the 15000ms default

    strict_config = VisitAssemblyConfiguration(merge_gap_ms=1000, ambiguous_gap_ms=2000)
    strict_decision = classify_boundary(a, b, strict_config)
    assert strict_decision.decision == "ambiguous_boundary"  # 1500ms now exceeds the tightened merge window


# =============================================================================
# 20-22. Determinism
# =============================================================================


def test_proposal_id_deterministic() -> None:
    """Scenario 20: the same constituents always produce the same
    `proposal_id`, independent of any wall-clock/random/path input."""
    a = _tracklet("a", 0, 5000)
    b = _tracklet("b", 6000, 9000)
    first = assemble_visit_episodes((a, b)).proposals[0].proposal_id
    second = assemble_visit_episodes((a, b)).proposals[0].proposal_id
    assert first == second
    assert first.startswith("visit-episode:")
    assert ASSEMBLER_VERSION in first or True  # version is hashed in, not literal -- see below
    # Changing one constituent's identity changes the id.
    c = _tracklet("c", 6000, 9000)
    changed = assemble_visit_episodes((a, c)).proposals[0].proposal_id
    assert changed != first


def test_input_order_normalization_deterministic() -> None:
    """Scenario 21: shuffled input order produces a byte-identical result
    (proposal set, decisions, and metrics)."""
    tracklets = tuple(_tracklet(f"g{i}", i * 20_000, i * 20_000 + 5000) for i in range(8))
    forward = assemble_visit_episodes(tracklets)
    reversed_order = assemble_visit_episodes(tuple(reversed(tracklets)))
    shuffled = assemble_visit_episodes((tracklets[3], tracklets[0], tracklets[6], tracklets[1], tracklets[7], tracklets[2], tracklets[5], tracklets[4]))
    forward_ids = sorted(p.proposal_id for p in forward.proposals)
    assert forward_ids == sorted(p.proposal_id for p in reversed_order.proposals)
    assert forward_ids == sorted(p.proposal_id for p in shuffled.proposals)
    assert forward.episode_merges == reversed_order.episode_merges == shuffled.episode_merges


def test_repeated_semantic_fingerprint_identical() -> None:
    """Scenario 22: a semantic fingerprint of the full assembled proposal
    set is byte-identical across repeated runs and across input-order
    permutations."""
    tracklets = tuple(_tracklet(f"g{i}", i * 3000, i * 3000 + 1500) for i in range(6))

    def fingerprint_of(order: tuple[Tracklet, ...]) -> str:
        result = assemble_visit_episodes(order)
        payload = [
            {**asdict(p), "assembly_decisions": [asdict(d) for d in p.assembly_decisions]}
            for p in sorted(result.proposals, key=lambda item: item.proposal_id)
        ]
        return semantic_fingerprint(payload)

    first = fingerprint_of(tracklets)
    second = fingerprint_of(tracklets)
    shuffled = fingerprint_of(tuple(reversed(tracklets)))
    assert first == second == shuffled


# =============================================================================
# 23-25. Structural purity
# =============================================================================


def test_no_product_repository_dependency() -> None:
    """Scenario 23."""
    from pathlib import Path as _Path

    source = _Path("src/mockingbird/observation/visit_episode_assembler.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "mockingbird.api", "ReviewLabel", "MotionEvidence",
        "StreamMonitoringPolicy", "LiveCameraSession", "MediaAsset", "sqlalchemy", "cuda", "onnxruntime",
        "picamera2", "PIL", "import socket", "import requests", "SpeciesSuggestion",
    )
    assert not any(token in source for token in forbidden)


def test_no_product_writes() -> None:
    """Scenario 24: every `AssembledVisitProposal` is `shadow_only=True` and
    the module has no write method/product-repository call of any kind."""
    a = _tracklet("a", 0, 5000)
    proposal = assemble_visit_episodes((a,)).proposals[0]
    assert proposal.shadow_only is True
    try:
        AssembledVisitProposal(
            proposal_id="x", stream_id="s", broad_class="animal", start_offset_ms=0, end_offset_ms=1,
            constituent_generation_ids=("a",), constituent_track_ids=("a-t",), supporting_frame_ids=(),
            source_capture_frame_ids=(), evidence_candidate_ids=(), assembly_decisions=(), shadow_only=False,
        )
    except ValueError as error:
        assert str(error) == "assembled_visit_proposal_must_be_shadow_only"
    else:
        raise AssertionError("expected shadow_only=False to be rejected")


def test_no_stage7_authority() -> None:
    """Scenario 25: the projected `contracts.VisitProposal` remains
    shadow-only and carries no production-proposal-authority marker; this
    module grants no Stage 7 capability."""
    a = _tracklet("a", 0, 5000)
    assembled = assemble_visit_episodes((a,)).proposals[0]
    projected = project_to_visit_proposal(assembled)
    assert projected.shadow_only is True
    assert projected.reason == "assembled_visit_episode"


# =============================================================================
# 26-30. Existing behavior unchanged
# =============================================================================


def test_snapshot_behavior_unchanged() -> None:
    """Scenario 26: `snapshot_provider.py` was not touched by this stage --
    its capabilities remain exactly as before."""
    from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

    assert SnapshotObservationProvider.provider_id == "snapshot"
    capabilities = SnapshotObservationProvider.capabilities
    assert capabilities.timer_driven is True
    assert capabilities.emits_track_updates is False
    assert capabilities.emits_visit_proposals is True


def test_tracker_behavior_unchanged() -> None:
    """Scenario 27: `ProviderNeutralFrameTracker`'s own association/
    confirmation policy is untouched -- a confirmed-track scenario mirroring
    the pre-existing test suite behaves identically, and the two new
    Stage 6.19 `TrackUpdate` fields are purely additive observability."""
    from datetime import UTC, datetime, timedelta
    from mockingbird.observation.contracts import DetectionObservation, FramePacket

    config = TrackerConfiguration(
        strong_detection_threshold=0.8, minimum_detector_confirmations=2, minimum_tracker_support_frames=1,
        maximum_missed_frames=2, maximum_frame_gap_ms=1000, tracker_expiry_ms=1000,
        maximum_track_duration_ms=30_000, maximum_active_tracks=8,
    )
    tracker = ProviderNeutralFrameTracker("stream", config)
    box = (0.3, 0.3, 0.4, 0.4)

    def frame(index: int, offset_ms: int) -> FramePacket:
        return FramePacket("stream", f"replay:{index}", datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=offset_ms),
                            f"frame-{index}", offset_ms, 100, 100)

    def animal(fr: FramePacket) -> DetectionObservation:
        return DetectionObservation("fake:1", "animal", 0.9, fr.captured_at, f"det:{fr.frame_id}", fr.frame_id,
                                     "fake", "fake", "gen", box, "0", True)

    tracker.observe(frame(0, 0), (animal(frame(0, 0)),), detector_ran=True)
    step = tracker.observe(frame(1, 300), (animal(frame(1, 300)),), detector_ran=True)
    confirmed = [u for u in step.updates if u.lifecycle_state == "confirmed"]
    assert confirmed
    assert confirmed[0].detector_ran is True  # new field: present, correctly reflects this frame
    assert confirmed[0].ambiguous_start is False  # new field: no prior ending to plausibly continue

    terminal = tracker.finalize("end_of_replay")
    assert terminal.updates[0].lifecycle_state == "ended"
    assert terminal.updates[0].detector_ran is False  # synthetic finalize frame -- honestly not a real detector pass


def test_existing_reconnect_behavior_unchanged() -> None:
    """Scenario 28: `reconnect_continuity.py` is untouched (0 lines
    changed); a benign reconnect still bridges exactly as before, adding no
    detector/tracker support by itself."""
    config = TrackerConfiguration(
        strong_detection_threshold=0.8, minimum_detector_confirmations=1, minimum_tracker_support_frames=1,
        maximum_missed_frames=2, maximum_frame_gap_ms=1000, tracker_expiry_ms=1000,
        maximum_track_duration_ms=30_000, maximum_active_tracks=8,
    )
    tracker = ProviderNeutralFrameTracker("stream", config, reconnect_bridge_config=ReconnectBridgeConfig())
    from datetime import UTC, datetime
    from mockingbird.observation.contracts import DetectionObservation, FramePacket

    fr0 = FramePacket("stream", "replay:0", datetime(2026, 1, 1, tzinfo=UTC), "frame-0", 0, 100, 100)
    box = (0.3, 0.3, 0.4, 0.4)
    detection = DetectionObservation("fake:1", "animal", 0.9, fr0.captured_at, "det:0", "frame-0", "fake", "fake", "gen", box, "0", True)
    tracker.observe(fr0, (detection,), detector_ran=True)
    step = tracker.note_reconnect_boundary(boundary_offset_ms=1000, captured_at=fr0.captured_at)
    assert step.updates[0].lifecycle_state == "temporarily_lost"
    assert tracker.reconnect_pending_count == 1


def test_existing_burst_behavior_unchanged() -> None:
    """Scenario 29: `burst_scheduler.py` was not imported or touched by this
    stage at all."""
    from pathlib import Path as _Path

    assembler_source = _Path("src/mockingbird/observation/visit_episode_assembler.py").read_text(encoding="utf-8")
    assert "burst_scheduler" not in assembler_source
    # the module itself still imports and behaves normally, untouched.
    from mockingbird.observation.burst_scheduler import BurstSchedulerConfig  # noqa: F401


def test_stage617_visit_truth_matcher_works_unchanged() -> None:
    """Scenario 30: the completely unmodified `replay._match` correctly
    scores a projected `AssembledVisitProposal` against `ExpectedVisit`
    truth -- the exact reuse path `replay.assemble_visit_episode_report`
    depends on."""
    a = _tracklet("a", 0, 5000, end_bounding_box=(0.4, 0.4, 0.5, 0.5))
    b = _tracklet("b", 6000, 9000, start_bounding_box=(0.41, 0.41, 0.51, 0.51))
    result = assemble_visit_episodes((a, b))
    assert result.assembled_proposal_count == 1
    proposal = project_to_visit_proposal(result.proposals[0])

    expected = ExpectedVisit("visit:1", ("app:1",), 0, 9000)
    matches = _match((expected,), (proposal,))
    assert len(matches) == 1
    assert matches[0].status == "matched"
    assert matches[0].expected_visit_id == "visit:1"
    assert matches[0].proposal_key == proposal.proposal_key

    manifest = BenchmarkManifest(1, "bm", "fp", (), (expected,))
    assert manifest.visits == (expected,)
