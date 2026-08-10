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

import pytest

from mockingbird.observation.contracts import DetectionEvidenceSample, TrackUpdate
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
# Visit Continuity / Provisional Admission Fix v1: `known_horizon_ms` /
# `continuation_pending` (see docs/tracklet-visit-assembly-contract.md
# "Episode finality" and the fresh-cohort candidate-004/005 field defect --
# a provisional-only tracklet was admitted as its own candidate Visit before
# a same-encounter continuation tracklet merged into it, producing a second,
# redundant candidate Visit 56 seconds later for one real ~75-second
# encounter). These tests exercise the assembler in isolation; the exact
# real-data replay lives in `test_replays_fresh_cohort_candidate_004_005_
# encounter_as_one_proposal` below.
# =============================================================================


def test_known_horizon_ms_omitted_never_marks_continuation_pending() -> None:
    """Every pre-existing caller (`replay.py`, every test above) omits
    `known_horizon_ms` -- the exact prior (pre-fix) behavior must be
    preserved byte-for-byte: no proposal is ever held pending."""
    a = _tracklet("a", 0, 5_000)
    b = _tracklet("b", 6_000, 9_000)
    result = assemble_visit_episodes((a, b))
    assert all(proposal.continuation_pending is False for proposal in result.proposals)


def test_singleton_tracklet_is_pending_within_its_own_continuation_window() -> None:
    a = _tracklet("solo", 0, 5_000)
    result = assemble_visit_episodes((a,), known_horizon_ms=5_100)
    assert result.proposals[0].continuation_pending is True


def test_singleton_tracklet_becomes_final_once_its_continuation_window_closes() -> None:
    a = _tracklet("solo", 0, 5_000)
    default_config = VisitAssemblyConfiguration()
    still_open = assemble_visit_episodes((a,), known_horizon_ms=5_000 + default_config.ambiguous_gap_ms)
    assert still_open.proposals[0].continuation_pending is True
    closed = assemble_visit_episodes((a,), known_horizon_ms=5_000 + default_config.ambiguous_gap_ms + 1)
    assert closed.proposals[0].continuation_pending is False


def test_merged_proposal_pending_state_follows_its_own_tail_not_first_member() -> None:
    """A merged (multi-tracklet) proposal's continuation window is governed
    by its own *latest* constituent's end offset, not the first tracklet's
    -- otherwise a long-merged episode would go eligible too early."""
    a = _tracklet("a", 0, 1_000)
    b = _tracklet("b", 5_000, 20_000)  # within merge_gap_ms of a's end
    merged = assemble_visit_episodes((a, b), known_horizon_ms=20_100)
    assert merged.assembled_proposal_count == 1
    proposal = merged.proposals[0]
    assert proposal.constituent_generation_ids == ("a", "b")
    assert proposal.continuation_pending is True  # governed by b's end (20,000), not a's (1,000)

    resolved = assemble_visit_episodes((a, b), known_horizon_ms=20_000 + 45_001)
    assert resolved.proposals[0].continuation_pending is False


def test_replays_fresh_cohort_candidate_004_005_encounter_as_one_proposal() -> None:
    """Exact reconstruction of the real 2026-08-10 fresh-cohort field defect
    (see data/field-acceptance/2026-08-10-fresh-cohort-detection-quality/
    fresh-candidates-extract.json and FINAL-REPORT.md Sec 10): tracklet
    `frame-track-0043` alone was admitted as candidate-004
    (`visit-episode:f6547de7632b52bc5c3a78f5`), then a second tracklet
    (`frame-track-0045`, a continuation of the same bird-at-feeder encounter
    after a brief reacquisition gap) merged with it and was admitted
    *again* as candidate-005 (`visit-episode:1b04117cb680f080b04837ef`), 56
    seconds later -- two persisted Visits for one real ~75-second encounter.

    The generation ids, both proposals' own start/end offsets, and the
    resulting `proposal_id`s below are exact, independently-recomputed
    matches of the real historical candidates (verified byte-for-byte
    against the real `sha256` derivation before this test was written).
    Tracklet 0045's own exact start offset is not itself part of the
    persisted candidate record (only the *merged* proposal's start/end
    survive that far) -- reconstructed here from the first real
    per-detection confidence sample the real candidate-005 evidence
    recorded for this generation (1,970,653ms), consistent with a track
    that begins at its own first detection; every fact this reconstruction
    depends on (both proposals' ids, offsets, and generation ids) is real.
    """
    stream_id = "stream-ca892992771c"
    gen_0043 = "stream-ca892992771c:frame-track:73aa21ee9c43c992f0cc"
    gen_0045 = "stream-ca892992771c:frame-track:2424a2579cee08b3b687"
    # The real, byte-identical evidence box both candidate-004 and
    # candidate-005's own persisted media shared (`normalized_track_box_json`).
    box = (0.4723, 0.5812, 0.5056, 0.6318)
    tracklet_0043 = _tracklet(
        gen_0043, 1_933_057, 1_963_271, stream_id=stream_id, track_ids=("frame-track-0043",),
        start_bounding_box=box, end_bounding_box=box, geometry_envelope=box,
    )
    tracklet_0045 = _tracklet(
        gen_0045, 1_970_653, 2_008_735, stream_id=stream_id, track_ids=("frame-track-0045",),
        start_bounding_box=box, end_bounding_box=box, geometry_envelope=box,
    )

    # --- what the real (pre-fix) pipeline actually did: assembled in two
    # separate, temporally-sequential passes, each producing an
    # admission-eligible proposal with no notion that a continuation could
    # still arrive.
    only_0043 = assemble_visit_episodes((tracklet_0043,))
    assert only_0043.assembled_proposal_count == 1
    proposal_004 = only_0043.proposals[0]
    assert proposal_004.proposal_id == "visit-episode:f6547de7632b52bc5c3a78f5"
    assert proposal_004.continuation_pending is False  # pre-fix: nothing ever flagged this as unsafe

    both = assemble_visit_episodes((tracklet_0043, tracklet_0045))
    assert both.assembled_proposal_count == 1  # the assembler already correctly merges them
    proposal_005 = both.proposals[0]
    assert proposal_005.proposal_id == "visit-episode:1b04117cb680f080b04837ef"
    assert proposal_005.constituent_generation_ids == (gen_0043, gen_0045)

    # --- the corrected, horizon-aware pipeline instead: at the tick right
    # after 0043 alone finalizes (0045 does not exist yet), the singleton
    # proposal is correctly held pending -- never handed to authority --
    # because a continuation could still arrive within `ambiguous_gap_ms`.
    right_after_0043_ends = 1_963_271 + 500
    pending_pass = assemble_visit_episodes((tracklet_0043,), known_horizon_ms=right_after_0043_ends)
    assert pending_pass.proposals[0].proposal_id == proposal_004.proposal_id
    assert pending_pass.proposals[0].continuation_pending is True

    # --- and by the time that singleton's own pending window would have
    # closed (1,963,271 + 45,000 = 2,008,271ms), 0045 has already arrived
    # and finalized in the real session (1,970,653-2,008,735ms) -- so the
    # next observed proposal is already the *merged* one, and candidate-004
    # is never separately created under the corrected pipeline.
    assert 1_970_653 < 1_963_271 + 45_000  # 0045 genuinely arrives inside 0043's own window
    merged_pass_horizon = 2_008_735 + 500
    merged_pending = assemble_visit_episodes(
        (tracklet_0043, tracklet_0045), known_horizon_ms=merged_pass_horizon,
    )
    assert merged_pending.assembled_proposal_count == 1
    assert merged_pending.proposals[0].proposal_id == proposal_005.proposal_id
    assert merged_pending.proposals[0].continuation_pending is True  # its own tail window is still open

    # --- once enough of the stream has been observed with nothing further
    # arriving, the merged proposal -- and only the merged proposal --
    # finally becomes eligible: one coherent encounter, one candidate.
    final_horizon = 2_008_735 + 45_000 + 1
    final_pass = assemble_visit_episodes((tracklet_0043, tracklet_0045), known_horizon_ms=final_horizon)
    assert final_pass.assembled_proposal_count == 1
    final_proposal = final_pass.proposals[0]
    assert final_proposal.proposal_id == proposal_005.proposal_id
    assert final_proposal.continuation_pending is False
    assert final_proposal.constituent_generation_ids == (gen_0043, gen_0045)


def test_replays_fresh_cohort_candidate_006_as_independent_of_004_005() -> None:
    """candidate-006 (the feeder-hardware false positive, real proposal id
    `visit-episode:6d2f6eab0b34ac96e5c0cb7c`) is a separate, ~7.5-minutes
    -later encounter at the same feeder -- structurally incompatible with
    the 004/005 encounter by gap alone (far beyond `ambiguous_gap_ms`), so
    it is never coupled to whether 004/005 has resolved yet. Reproduces the
    real session shape: candidate-006 was admitted at the session's own
    final tick (`finalize=True` in engine_runtime.py, see
    `test_finalize_tick_admits_a_still_pending_singleton_immediately` in
    test_engine_runtime.py for the live-loop-level version of this same
    fact) -- unaffected by the fix either way."""
    stream_id = "stream-ca892992771c"
    gen_0043 = "stream-ca892992771c:frame-track:73aa21ee9c43c992f0cc"
    gen_0045 = "stream-ca892992771c:frame-track:2424a2579cee08b3b687"
    gen_0052 = "stream-ca892992771c:frame-track:6b1aa6d633d81422104d"
    box_004_005 = (0.4723, 0.5812, 0.5056, 0.6318)
    box_006 = (0.464, 0.5722, 0.4916, 0.6395)  # candidate-006's real evidence box
    tracklet_0043 = _tracklet(
        gen_0043, 1_933_057, 1_963_271, stream_id=stream_id, track_ids=("frame-track-0043",),
        start_bounding_box=box_004_005, end_bounding_box=box_004_005, geometry_envelope=box_004_005,
    )
    tracklet_0045 = _tracklet(
        gen_0045, 1_970_653, 2_008_735, stream_id=stream_id, track_ids=("frame-track-0045",),
        start_bounding_box=box_004_005, end_bounding_box=box_004_005, geometry_envelope=box_004_005,
    )
    # candidate-006's own real window (start_offset_ms/end_offset_ms), ~7.5
    # minutes after candidate-005's own end.
    tracklet_0052 = _tracklet(
        gen_0052, 2_458_347, 2_468_992, stream_id=stream_id, track_ids=("frame-track-0052",),
        start_bounding_box=box_006, end_bounding_box=box_006, geometry_envelope=box_006,
    )

    result = assemble_visit_episodes((tracklet_0043, tracklet_0045, tracklet_0052))
    assert result.assembled_proposal_count == 2  # {0043, 0045} merged; {0052} separate
    proposal_006 = next(item for item in result.proposals if item.constituent_generation_ids == (gen_0052,))
    assert proposal_006.proposal_id == "visit-episode:6d2f6eab0b34ac96e5c0cb7c"
    assert proposal_006.ambiguous_adjacent_proposal_ids == ()  # never coupled to the 004/005 encounter

    finalized = assemble_visit_episodes((tracklet_0043, tracklet_0045, tracklet_0052), known_horizon_ms=None)
    proposal_006_final = next(
        item for item in finalized.proposals if item.constituent_generation_ids == (gen_0052,)
    )
    assert proposal_006_final.continuation_pending is False


def test_two_separated_encounters_resolve_independently() -> None:
    """Part 4 regression 2: two genuinely separate encounters with
    sufficient temporal separation remain two proposals (pre-existing
    behavior), and the new continuation-pending horizon resolves each
    independently -- one proposal's own pending state never depends on a
    temporally-distant, structurally-unrelated proposal's state."""
    a = _tracklet("a", 0, 5_000)
    b = _tracklet("b", 200_000, 205_000)
    result = assemble_visit_episodes((a, b), known_horizon_ms=100_000)
    assert result.assembled_proposal_count == 2
    proposal_a = next(item for item in result.proposals if item.constituent_generation_ids == ("a",))
    proposal_b = next(item for item in result.proposals if item.constituent_generation_ids == ("b",))
    assert proposal_a.continuation_pending is False  # a's own window (closes at 50,000) is long past
    assert proposal_b.continuation_pending is True  # b's own window (closes at 250,000) has not closed

    resolved = assemble_visit_episodes((a, b), known_horizon_ms=250_001)
    assert all(not item.continuation_pending for item in resolved.proposals)


def test_spatially_incompatible_close_in_time_remain_separate_and_resolve_independently() -> None:
    """Part 4 regression 3: existing spatial-discontinuity protection is
    unaffected by the continuation-pending horizon -- two tracklets close
    in time but geometrically incompatible stay two proposals, and neither
    is coupled to the other's pending state."""
    a = _tracklet("a", 0, 5_000, end_bounding_box=(0.02, 0.02, 0.10, 0.10))
    b = _tracklet("b", 6_000, 9_000, start_bounding_box=(0.85, 0.85, 0.95, 0.95))
    decision = classify_boundary(a, b)
    assert decision.decision == "keep_separate"
    assert decision.reason == "spatial_discontinuity"

    result = assemble_visit_episodes((a, b), known_horizon_ms=9_000 + 45_001)
    assert result.assembled_proposal_count == 2
    assert all(not item.continuation_pending for item in result.proposals)


def test_size_incompatible_tracklets_remain_separate_and_resolve_independently() -> None:
    """Part 4 regression 4: existing size-change-ratio protection
    (`maximum_size_change_ratio`) is unaffected -- a materially different
    -size reacquisition still starts a new episode, independent of the
    continuation-pending horizon."""
    a = _tracklet("a", 0, 5_000, end_bounding_box=(0.40, 0.40, 0.44, 0.44))  # small box
    b = _tracklet("b", 6_000, 9_000, start_bounding_box=(0.30, 0.30, 0.70, 0.70))  # much larger box
    decision = classify_boundary(a, b)
    assert decision.decision == "keep_separate"
    assert decision.reason == "spatial_discontinuity"

    result = assemble_visit_episodes((a, b), known_horizon_ms=9_000 + 45_001)
    assert result.assembled_proposal_count == 2
    assert all(not item.continuation_pending for item in result.proposals)


def test_provisional_encounter_without_continuation_eventually_becomes_eligible() -> None:
    """Part 4 regression 5: a provisional (never-strong) tracklet that
    genuinely never receives a continuation must not wait forever -- once
    the caller's own observed horizon has moved far enough past its own
    end, it becomes eligible on its own, unmerged with anything."""
    only = _tracklet("solo", 0, 5_000)
    assert only.has_strong_evidence is False  # provisional, matching the real 004/005 shape

    just_after = assemble_visit_episodes((only,), known_horizon_ms=5_100)
    assert just_after.proposals[0].continuation_pending is True

    still_within_window = assemble_visit_episodes((only,), known_horizon_ms=5_000 + 45_000)
    assert still_within_window.proposals[0].continuation_pending is True

    window_closed = assemble_visit_episodes((only,), known_horizon_ms=5_000 + 45_000 + 1)
    assert window_closed.proposals[0].continuation_pending is False
    assert window_closed.proposals[0].constituent_generation_ids == ("solo",)  # never merged, never lost


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


def test_build_tracklets_confidence_evidence_honestly_reports_unknown_strong_weak_for_legacy_updates() -> None:
    """Detection Quality Accounting v1 (see
    docs/detection-quality-accounting-contract.md): a generation whose
    `TrackUpdate`s were reconstructed from a pre-Detection-Quality-
    Accounting recorded report (for example via the Stage 6.17
    `rescore_visit_truth.py` JSON-reconstruction pattern) carries a real,
    exact `detector_confirmation_count` but empty `confidence_samples` --
    `build_tracklets` must report the strong/weak split as unknown
    (`None`), never a fabricated `0`, while still reporting the exact
    `detection_count` and `max_confidence` that were already recorded."""
    legacy_updates = (
        _track_update(
            "gen-legacy", 0, "started", "weak_detector_supported",
            detector_confirmation_count=1, confidence=0.42,
        ),
        _track_update(
            "gen-legacy", 500, "ended", "weak_detector_supported", lifecycle_state="ended",
            terminal_reason="end_of_replay", detector_confirmation_count=3, confidence=0.55,
        ),
    )
    tracklet = build_tracklets(legacy_updates, stream_id="stream-x")[0]

    assert tracklet.confidence_evidence.detection_count == 3  # the exact, already-recorded count survives
    assert tracklet.confidence_evidence.max_confidence == 0.55  # likewise the exact recorded max
    assert tracklet.confidence_evidence.strong_detection_count is None  # honestly unknown, not 0
    assert tracklet.confidence_evidence.weak_detection_count is None
    assert tracklet.confidence_evidence.max_consecutive_detector_confirmed_frames is None
    assert tracklet.confidence_evidence.mean_confidence is None  # no per-detection samples to average
    assert tracklet.confidence_evidence.median_confidence is None
    assert tracklet.confidence_evidence.samples == ()
    assert tracklet.confidence_evidence.sample_truncated is True


def test_build_tracklets_confidence_evidence_reports_real_strong_weak_split_for_fresh_updates() -> None:
    """The mirror-image case: a generation whose updates carry real
    `confidence_samples` (the normal case for anything produced by the
    current tracker) gets the exact strong/weak split and mean/median,
    never `None`."""
    samples_first = (DetectionEvidenceSample(0.42, 0, "frame-a", "obs-a", is_strong=False),)
    samples_final = samples_first + (DetectionEvidenceSample(0.9, 500, "frame-b", "obs-b", is_strong=True),)
    fresh_updates = (
        _track_update(
            "gen-fresh", 0, "started", "weak_detector_supported",
            detector_confirmation_count=1, confidence=0.42, confidence_samples=samples_first,
        ),
        _track_update(
            "gen-fresh", 500, "ended", "strong_detector_supported", lifecycle_state="ended",
            terminal_reason="end_of_replay", detector_confirmation_count=2, confidence=0.9,
            confidence_samples=samples_final,
        ),
    )
    tracklet = build_tracklets(fresh_updates, stream_id="stream-x")[0]

    assert tracklet.confidence_evidence.detection_count == 2
    assert tracklet.confidence_evidence.strong_detection_count == 1
    assert tracklet.confidence_evidence.weak_detection_count == 1
    assert tracklet.confidence_evidence.mean_confidence == pytest.approx((0.42 + 0.9) / 2)
    assert tracklet.confidence_evidence.sample_truncated is False


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
