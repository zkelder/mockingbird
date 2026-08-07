"""Hardware-free and real-historical tests for the Stage 6.9 burst-schedule
replay evaluator. The real-session tests replay actual Stage 6.7 capture
manifests already present on this local checkout; they are skipped (not
failed) when that ignored local data is absent so the hardware-free suite
never depends on it.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from mockingbird.observation.burst_scheduler import BurstSchedulerConfig
from mockingbird.observation.burst_scheduler_replay import (
    BurstScheduleReplayError,
    reconstruct_opportunities,
    replay_burst_schedule,
)
from mockingbird.observation.burst_scheduler_replay_cli import run as run_replay_cli
from mockingbird.observation.burst_scheduler_replay_io import load_json_document


def _frame(
    frame_id: str, sequence: int, *, source_offset_ms: int, trigger_reasons: list[str],
    track_generation_ids: list[str] | None = None, detection_boxes: list[tuple[float, float, float, float, float]] | None = None,
    provider_generation: str = "generation-a", high_resolution: bool = False, operator_marker_ids: list[str] | None = None,
) -> dict[str, object]:
    boxes = detection_boxes or []
    return {
        "frame_id": frame_id,
        "sequence": sequence,
        "source_offset_ms": source_offset_ms,
        "provider_generation": provider_generation,
        "trigger_reasons": trigger_reasons,
        "track_generation_ids": track_generation_ids or [],
        "detection_boxes": [list(box) for box in boxes],
        "animal_detection_count": len(boxes),
        "active_track_count": len(track_generation_ids or []),
        "high_resolution": high_resolution,
        "operator_marker_ids": operator_marker_ids or [],
        "connection_segment_id": "",
        "host_received_at": "",
        "source_capture_timestamp": None,
    }


def _manifest(frames: list[dict[str, object]], *, session_id: str = "capture-session-fixture", stream_id: str = "stream-yard") -> dict[str, object]:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "node_session_id": "node-session-fixture",
        "config": {"stream_id": stream_id},
        "generation_reset_count": 0,
        "frames": frames,
        "operator_markers": [],
        "stop_condition": "duration_elapsed",
    }


STATIC_BOX = (0.45, 0.55, 0.47, 0.63)


def _static_recurrence_frames(count: int, *, start_offset_ms: int = 1_000, step_ms: int = 1_500) -> list[dict[str, object]]:
    """A general fixture modeling a fixed static structure (a shepherd's-hook-
    like recurring false positive) re-detected as a brand-new short-lived
    track generation every few seconds -- the session-02 pattern."""

    frames = []
    for index in range(count):
        frames.append(_frame(
            f"static-frame-{index}", index + 1, source_offset_ms=start_offset_ms + index * step_ms,
            trigger_reasons=["shadow_track_event", "recurring_static_geometry", "high_resolution_burst"],
            track_generation_ids=[f"static-generation-{index}"],
            detection_boxes=[(*STATIC_BOX, 0.05 + 0.001 * index)],
            high_resolution=True,
        ))
    return frames


# --------------------------------------------------------------------------
# Reconstruction
# --------------------------------------------------------------------------


def test_reconstruct_opportunities_orders_by_session_timeline_and_skips_non_track_frames() -> None:
    manifest = _manifest([
        _frame("frame-2", 2, source_offset_ms=2_000, trigger_reasons=["shadow_track_event"], track_generation_ids=["gen-a"], detection_boxes=[(*STATIC_BOX, 0.5)]),
        _frame("frame-1", 1, source_offset_ms=1_000, trigger_reasons=["shadow_track_event"], track_generation_ids=["gen-a"], detection_boxes=[(*STATIC_BOX, 0.5)]),
        _frame("frame-negative", 3, source_offset_ms=3_000, trigger_reasons=["periodic_negative_sample"]),
    ])
    opportunities = reconstruct_opportunities(manifest, session_id="session-x")
    assert [item.trigger_frame_id for item in opportunities] == ["frame-1", "frame-2"]
    assert opportunities[0].source_offset_ms == 1_000


def test_reconstruct_opportunities_collapses_one_frame_to_one_representative_opportunity() -> None:
    """The manifest does not record which box belongs to which generation,
    so one busy frame reconstructs to exactly one opportunity (the frame's
    best box, attributed to one deterministic representative generation)
    rather than a near-identical opportunity per active generation -- which
    would otherwise inflate replay volume well past what the live
    per-generation TrackUpdate path would ever raise."""

    manifest = _manifest([
        _frame(
            "frame-multi", 1, source_offset_ms=1_000, trigger_reasons=["shadow_track_event"],
            track_generation_ids=["gen-b", "gen-a"], detection_boxes=[(*STATIC_BOX, 0.4), (0.05, 0.05, 0.1, 0.1, 0.6)],
        ),
    ])
    opportunities = reconstruct_opportunities(manifest, session_id="session-x")
    assert len(opportunities) == 1
    # Deterministic representative: the lexicographically first generation
    # id active on the frame, regardless of the manifest's own array order.
    assert opportunities[0].track_generation_id == "gen-a"
    assert opportunities[0].subject_geometry == (0.05, 0.05, 0.1, 0.1)
    assert opportunities[0].detector_score == 0.6
    # Fixed neutral constants -- not derived from the frame's own detection/
    # generation counts (see the module's documented reconstruction limits).
    assert opportunities[0].detector_confirmation_count == 1
    assert opportunities[0].tracker_support_count == 0


def test_reconstruct_opportunities_rejects_blank_session_id() -> None:
    with pytest.raises(BurstScheduleReplayError):
        reconstruct_opportunities(_manifest([]), session_id="")


def test_reconstruct_opportunities_reads_a_legacy_pre_stage_6_8_manifest() -> None:
    """Item 33: old captures without scheduler facts (and without any
    session-timeline field at all) remain readable."""

    manifest = _manifest(_static_recurrence_frames(3))
    assert "session_sequence" not in manifest["frames"][0]
    opportunities = reconstruct_opportunities(manifest, session_id="session-legacy")
    assert len(opportunities) == 3


# --------------------------------------------------------------------------
# Stage 6.15: live/replay temporal-support convergence
# (docs/burst-scheduler-contract.md). Before this stage,
# detector_confirmation_count/tracker_support_count were fixed neutral
# constants (1, 0) in every reconstructed opportunity specifically to
# conservatively disable the stronger_temporal_support novelty signal in
# replay -- a workaround for the live floor-based bug, not a fix, that left
# replay structurally unable to ever exercise that signal at all. Now that
# BurstScheduler's own comparison is safe against generation rebirth, replay
# reconstructs a real, per-generation running occurrence count instead.
# --------------------------------------------------------------------------


def _rebirth_frames(
    generation_count: int, frames_per_generation: int, *, start_offset_ms: int = 1_000, step_ms: int = 1_500,
) -> list[dict[str, object]]:
    """Mirror _static_recurrence_frames, but each generation persists across
    several consecutive frames (its own reconstructed support climbing with
    each one) before a brand-new generation id takes over -- the
    manifest-level shape of the live generation-rebirth issuance storm this
    stage fixes. `step_ms` exceeds BurstSchedulerConfig's default
    `minimum_burst_interval_ms` so a generation's own later frames are never
    swallowed by its own per-generation cooldown before reaching the
    recurrence group, mirroring the same timing consideration
    test_burst_scheduler.py's `_rebirth_series` fixture documents."""

    frames = []
    index = 0
    for generation_index in range(generation_count):
        generation_id = f"rebirth-generation-{generation_index}"
        for step in range(frames_per_generation):
            frames.append(_frame(
                f"rebirth-frame-{generation_index}-{step}", index + 1,
                source_offset_ms=start_offset_ms + index * step_ms,
                trigger_reasons=["shadow_track_event", "recurring_static_geometry", "high_resolution_burst"],
                track_generation_ids=[generation_id],
                detection_boxes=[(*STATIC_BOX, 0.06)],
                high_resolution=True,
            ))
            index += 1
    return frames


def test_reconstruct_opportunities_derives_growing_per_generation_support() -> None:
    manifest = _manifest(_rebirth_frames(2, 3))
    opportunities = reconstruct_opportunities(manifest, session_id="session-x")
    assert len(opportunities) == 6
    # The first generation's own reconstructed support climbs 1, 2, 3 across
    # its three frames...
    assert [item.detector_confirmation_count for item in opportunities[:3]] == [1, 2, 3]
    # ...and a brand-new generation id restarts at 1, honestly mirroring the
    # live tracker's own monotonic per-generation counters resetting on
    # rebirth.
    assert [item.detector_confirmation_count for item in opportunities[3:]] == [1, 2, 3]
    assert all(item.tracker_support_count == 0 for item in opportunities)


def test_replay_generation_rebirth_does_not_repeatedly_issue_via_support_alone() -> None:
    """The replay-side counterpart of test_burst_scheduler.py's
    test_generation_rebirth_does_not_repeatedly_create_temporal_support_novelty:
    many short-lived rebirths at the same static geometry, each honestly
    reconstructed as climbing its own support exactly like a real generation
    would, must not each independently escape recurrence suppression through
    stronger_temporal_support merely because a fresh generation restarted its
    own counters."""

    manifest = _manifest(_rebirth_frames(10, 3))
    report = replay_burst_schedule(manifest, session_id="session-rebirth-storm")
    assert report.current_track_generations == 10
    assert report.reconstructed_opportunity_count == 30
    # Only the very first opportunity of the whole session may issue (Stage
    # 6.9's own "first opportunity is never suppressed" rule); every other
    # rebirth reaching a previously-seen support level must be suppressed as
    # a recurrence.
    assert report.proposed_issued_count == 1
    assert report.static_recurrence_suppressions == 29


# --------------------------------------------------------------------------
# Replay report: recurrence reduction
# --------------------------------------------------------------------------


def test_replay_reduces_recurring_static_geometry_bursts() -> None:
    manifest = _manifest(_static_recurrence_frames(8))
    report = replay_burst_schedule(manifest, session_id="session-static")
    assert report.current_high_resolution_frames == 8
    assert report.current_track_generations == 8
    assert report.reconstructed_opportunity_count == 8
    assert report.proposed_issued_count < report.current_high_resolution_frames
    assert report.static_recurrence_suppressions > 0
    assert report.high_resolution_frames_reduction > 0
    assert report.high_resolution_frames_reduction_ratio is not None and report.high_resolution_frames_reduction_ratio > 0
    assert report.genuine_appearance_reviewed is None  # no annotation supplied
    assert report.missed_useful_burst_risk == ()


def test_replay_never_mutates_its_inputs() -> None:
    manifest = _manifest(_static_recurrence_frames(5))
    annotation = {"schema_version": 1, "frames": [], "appearances": []}
    before_manifest = copy.deepcopy(manifest)
    before_annotation = copy.deepcopy(annotation)
    replay_burst_schedule(manifest, session_id="session-immutable", annotation=annotation)
    assert manifest == before_manifest
    assert annotation == before_annotation


def test_replay_is_deterministic_and_reproducible() -> None:
    manifest = _manifest(_static_recurrence_frames(6))
    first = replay_burst_schedule(manifest, session_id="session-repeat")
    second = replay_burst_schedule(manifest, session_id="session-repeat")
    assert first.fingerprint == second.fingerprint


# --------------------------------------------------------------------------
# Replay report: genuine-appearance retention via reviewed annotation
# --------------------------------------------------------------------------


def _annotation_frame(frame_id: str, *, truth: str = "yes", truth_source: str = "detector_crop") -> dict[str, object]:
    return {
        "frame_id": frame_id, "whole_frame_truth": truth, "boxes": [],
        "evidence_usefulness": {}, "provenance": {"truth_source": truth_source},
    }


def _appearance(appearance_id: str, frame_id: str) -> dict[str, object]:
    # Every real Stage 6.7 appearance found so far is instantaneous
    # (start == end); a multi-frame span is exercised separately below.
    return {"appearance_id": appearance_id, "start_frame_id": frame_id, "end_frame_id": frame_id, "instantaneous": True}


def test_replay_retains_a_genuine_appearance_through_novelty_despite_static_recurrence() -> None:
    frames = _static_recurrence_frames(4)
    frames.append(_frame(
        "genuine-frame", 5, source_offset_ms=1_000 + 4 * 1_500, trigger_reasons=["shadow_track_event", "recurring_static_geometry", "high_resolution_burst"],
        track_generation_ids=["genuine-generation"], detection_boxes=[(*STATIC_BOX, 0.85)], high_resolution=True,
    ))
    manifest = _manifest(frames)
    annotation = {
        "schema_version": 1, "frames": [_annotation_frame("genuine-frame")],
        "appearances": [_appearance("appearance-genuine", "genuine-frame")],
    }

    report = replay_burst_schedule(manifest, session_id="session-genuine", annotation=annotation)
    assert report.genuine_appearance_reviewed == 1
    assert report.genuine_appearance_retained == 1
    assert report.genuine_appearance_lost == ()
    assert report.reviewed_positive_frame_total == 1
    assert report.reviewed_positive_frame_retained == 1


def test_replay_reports_operator_marked_appearance_retention() -> None:
    frames = _static_recurrence_frames(2)
    frames.append(_frame(
        "marked-frame", 3, source_offset_ms=1_000 + 2 * 1_500, trigger_reasons=["shadow_track_event", "operator_marker"],
        track_generation_ids=["marked-generation"], detection_boxes=[(*STATIC_BOX, 0.3)], operator_marker_ids=["marker-1"],
    ))
    manifest = _manifest(frames)
    annotation = {
        "schema_version": 1, "frames": [_annotation_frame("marked-frame", truth_source="operator_marker")],
        "appearances": [_appearance("appearance-marked", "marked-frame")],
    }

    report = replay_burst_schedule(manifest, session_id="session-marked", annotation=annotation)
    assert report.operator_marked_appearance_reviewed == 1
    assert report.operator_marked_appearance_retained == 1
    assert report.operator_marked_appearance_lost == ()
    # An operator marker is itself a novelty/override signal, so this
    # opportunity issues regardless of any recurrence-group state.
    assert report.proposed_operator_overrides >= 1


def test_replay_appearance_retained_if_any_frame_in_a_multi_frame_span_issues() -> None:
    """A multi-frame appearance retains eligibility when at least one frame
    in its span was issued, even if earlier frames in the same span were
    suppressed as a same-generation/recurring duplicate of that first shot."""

    frames = [
        _frame(
            "span-start", 1, source_offset_ms=1_000, trigger_reasons=["shadow_track_event", "high_resolution_burst"],
            track_generation_ids=["span-generation"], detection_boxes=[(*STATIC_BOX, 0.8)], high_resolution=True,
        ),
        _frame(
            "span-middle", 2, source_offset_ms=1_200, trigger_reasons=["shadow_track_event"],
            track_generation_ids=["span-generation"], detection_boxes=[(*STATIC_BOX, 0.82)],
        ),
        _frame(
            "span-end", 3, source_offset_ms=1_400, trigger_reasons=["shadow_track_event"],
            track_generation_ids=["span-generation"], detection_boxes=[(*STATIC_BOX, 0.83)],
        ),
    ]
    manifest = _manifest(frames)
    annotation = {
        "schema_version": 1,
        "frames": [_annotation_frame(fid) for fid in ("span-start", "span-middle", "span-end")],
        "appearances": [{"appearance_id": "appearance-span", "start_frame_id": "span-start", "end_frame_id": "span-end", "instantaneous": False}],
    }
    report = replay_burst_schedule(manifest, session_id="session-span", annotation=annotation)
    assert report.genuine_appearance_reviewed == 1
    assert report.genuine_appearance_retained == 1
    # The middle/end frames are the same still-cooling-down generation as the
    # first shot, so per-frame retention is properly stricter than the
    # appearance-level view.
    assert report.reviewed_positive_frame_total == 3
    assert report.reviewed_positive_frame_retained == 1


def test_replay_detects_missed_useful_burst_risk() -> None:
    """A frame the old system actually captured, reviewed genuine, but that
    the proposed scheduler would now suppress under a deliberately starved
    budget -- the honest regression-risk case the report must surface. The
    Stage 6.12 fairness reserve is explicitly disabled: this test is about
    the report's own missed-risk detection under genuine, total starvation
    (every channel exhausted), not about the reserve's fallback behavior,
    which test_burst_scheduler.py covers directly. Without disabling it, a
    materially novel opportunity like this one (a brand-new recurrence
    group) would correctly be rescued by the reserve -- proving the exact
    Stage 6.12 fix this scenario predates."""

    frames = [_frame(
        "budget-consumer", 1, source_offset_ms=500, trigger_reasons=["shadow_track_event", "high_resolution_burst"],
        track_generation_ids=["consumer-generation"], detection_boxes=[(0.05, 0.05, 0.10, 0.10, 0.9)], high_resolution=True,
    ), _frame(
        "reviewed-genuine", 2, source_offset_ms=1_000, trigger_reasons=["shadow_track_event", "high_resolution_burst"],
        track_generation_ids=["genuine-generation"], detection_boxes=[(*STATIC_BOX, 0.8)], high_resolution=True,
    )]
    manifest = _manifest(frames)
    annotation = {
        "schema_version": 1, "frames": [_annotation_frame("reviewed-genuine")],
        "appearances": [_appearance("appearance-starved", "reviewed-genuine")],
    }
    config = BurstSchedulerConfig(max_bursts_per_session=1, operator_override_reserved_bursts=0, novelty_reserve_capacity=0)

    report = replay_burst_schedule(manifest, session_id="session-starved", config=config, annotation=annotation)
    assert report.genuine_appearance_reviewed == 1
    assert report.genuine_appearance_retained == 0
    assert report.genuine_appearance_lost == ("appearance-starved",)
    assert "appearance-starved" in report.missed_useful_burst_risk


def test_replay_rescues_genuine_appearance_via_novelty_reserve() -> None:
    """The same scenario as test_replay_detects_missed_useful_burst_risk
    above, but with the Stage 6.12 fairness reserve at its default capacity:
    the materially novel reviewed appearance is no longer lost merely
    because an earlier, unrelated opportunity happened to exhaust the
    ordinary budget first."""

    frames = [_frame(
        "budget-consumer", 1, source_offset_ms=500, trigger_reasons=["shadow_track_event", "high_resolution_burst"],
        track_generation_ids=["consumer-generation"], detection_boxes=[(0.05, 0.05, 0.10, 0.10, 0.9)], high_resolution=True,
    ), _frame(
        "reviewed-genuine", 2, source_offset_ms=1_000, trigger_reasons=["shadow_track_event", "high_resolution_burst"],
        track_generation_ids=["genuine-generation"], detection_boxes=[(*STATIC_BOX, 0.8)], high_resolution=True,
    )]
    manifest = _manifest(frames)
    annotation = {
        "schema_version": 1, "frames": [_annotation_frame("reviewed-genuine")],
        "appearances": [_appearance("appearance-rescued", "reviewed-genuine")],
    }
    config = BurstSchedulerConfig(max_bursts_per_session=1, operator_override_reserved_bursts=0)

    report = replay_burst_schedule(manifest, session_id="session-rescued", config=config, annotation=annotation)
    assert report.genuine_appearance_reviewed == 1
    assert report.genuine_appearance_retained == 1
    assert report.genuine_appearance_lost == ()
    assert "appearance-rescued" not in report.missed_useful_burst_risk


# --------------------------------------------------------------------------
# CLI round-trip
# --------------------------------------------------------------------------


def test_cli_round_trip_writes_a_deterministic_report(tmp_path: Path) -> None:
    manifest = _manifest(_static_recurrence_frames(6))
    annotation = {"schema_version": 1, "frames": [], "appearances": []}
    manifest_path = tmp_path / "capture-session-manifest.json"
    annotation_path = tmp_path / "annotation.json"
    manifest_path.write_text(json.dumps(manifest))
    annotation_path.write_text(json.dumps(annotation))
    output = tmp_path / "replay-out"

    exit_code = run_replay_cli([
        "--manifest", str(manifest_path), "--annotation", str(annotation_path),
        "--session-id", "cli-session", "--output", str(output),
    ])
    assert exit_code == 0
    report_path = output / "burst-schedule-replay-report.json"
    assert report_path.is_file()
    payload = json.loads(report_path.read_text())
    assert payload["session_id"] == "cli-session"
    assert payload["creates_truth"] is False
    assert payload["shadow_only"] is True
    assert "semantic_fingerprint" in payload


def test_cli_rejects_a_missing_manifest(tmp_path: Path) -> None:
    exit_code = run_replay_cli([
        "--manifest", str(tmp_path / "does-not-exist.json"), "--output", str(tmp_path / "out"),
    ])
    assert exit_code != 0


# --------------------------------------------------------------------------
# Real Stage 6.7 session-01/session-02 acceptance
# --------------------------------------------------------------------------

_DAYLIGHT_ROOT = Path("data/field-acceptance/2026-08-06-daylight-temporal-collection")
_SESSION_PATHS = {
    "session-01": (_DAYLIGHT_ROOT / "session-01" / "capture-out" / "capture-session-manifest.json", _DAYLIGHT_ROOT / "session-01" / "review-out" / "annotation.json"),
    "session-02": (_DAYLIGHT_ROOT / "session-02" / "capture-out" / "capture-session-manifest.json", _DAYLIGHT_ROOT / "session-02" / "review-out" / "annotation.json"),
}


def _real_session_available(name: str) -> bool:
    manifest_path, annotation_path = _SESSION_PATHS[name]
    return manifest_path.is_file() and annotation_path.is_file()


@pytest.mark.parametrize("session_name", ["session-01", "session-02"])
def test_real_stage_6_7_session_replay_does_not_rewrite_source_files(session_name: str) -> None:
    if not _real_session_available(session_name):
        pytest.skip(f"real Stage 6.7 {session_name} capture data is not present on this checkout")
    manifest_path, annotation_path = _SESSION_PATHS[session_name]
    manifest_before = manifest_path.read_bytes()
    annotation_before = annotation_path.read_bytes()

    manifest = load_json_document(manifest_path)
    annotation = load_json_document(annotation_path)
    replay_burst_schedule(manifest, session_id=f"replay-{session_name}", annotation=annotation)

    assert manifest_path.read_bytes() == manifest_before
    assert annotation_path.read_bytes() == annotation_before
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == hashlib.sha256(manifest_before).hexdigest()


@pytest.mark.skipif(not _real_session_available("session-02"), reason="real Stage 6.7 session-02 capture data is not present on this checkout")
def test_real_session_02_reduces_recurring_static_geometry_substantially() -> None:
    manifest_path, annotation_path = _SESSION_PATHS["session-02"]
    manifest = load_json_document(manifest_path)
    annotation = load_json_document(annotation_path)
    report = replay_burst_schedule(manifest, session_id="replay-session-02", annotation=annotation)

    assert report.current_high_resolution_frames == 123
    assert report.current_track_generations == 379
    # The critical acceptance requirement: a substantial reduction in
    # recurring-static-geometry burst volume without a hard-coded numeric
    # target -- any genuine, measured reduction driven by actual suppression
    # (not an artifact of a starved budget) satisfies it.
    assert report.static_recurrence_suppressions > 0
    assert report.proposed_issued_count < report.current_high_resolution_frames
    assert dict(report.proposed_suppression_reason_distribution).get("suppressed_recurring_geometry", 0) == report.static_recurrence_suppressions
    # Every reviewed genuine appearance in this session must still retain
    # burst eligibility -- the safe-separation requirement.
    assert report.genuine_appearance_reviewed is not None and report.genuine_appearance_reviewed > 0
    assert report.genuine_appearance_retained == report.genuine_appearance_reviewed
    assert report.genuine_appearance_lost == ()


@pytest.mark.skipif(not _real_session_available("session-01"), reason="real Stage 6.7 session-01 capture data is not present on this checkout")
def test_real_session_01_retains_reviewed_genuine_appearances() -> None:
    manifest_path, annotation_path = _SESSION_PATHS["session-01"]
    manifest = load_json_document(manifest_path)
    annotation = load_json_document(annotation_path)
    report = replay_burst_schedule(manifest, session_id="replay-session-01", annotation=annotation)

    assert report.current_high_resolution_frames == 32
    assert report.genuine_appearance_reviewed is not None and report.genuine_appearance_reviewed > 0
    assert report.genuine_appearance_retained == report.genuine_appearance_reviewed
    assert report.genuine_appearance_lost == ()
