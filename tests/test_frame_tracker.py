"""Direct, deterministic tests for the provider-neutral frame tracker's episode
boundary between continuing, temporarily losing, ending, and starting a new
generation.  These are hardware-free, resolution/species/path-independent, and
use only synthetic geometry -- no private media, real Visit ids, or one exact
frame count.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_tracker import (
    ProviderNeutralFrameTracker,
    TrackerConfiguration,
    TrackerStep,
)
from mockingbird.observation.reconnect_continuity import ReconnectBridgeConfig


def _config(**overrides: object) -> TrackerConfiguration:
    values: dict[str, object] = {
        "strong_detection_threshold": 0.8,
        "minimum_detector_confirmations": 2,
        "minimum_tracker_support_frames": 1,
        "maximum_missed_frames": 2,
        "maximum_frame_gap_ms": 1000,
        "tracker_expiry_ms": 1000,
        "maximum_track_duration_ms": 30_000,
        "maximum_active_tracks": 8,
    }
    values.update(overrides)
    return TrackerConfiguration(**values)


def _frame(index: int, offset_ms: int, **overrides: object) -> FramePacket:
    values: dict[str, object] = {
        "stream_id": "stream",
        "media_asset_id": f"replay:{index}",
        "captured_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=offset_ms),
        "frame_id": f"frame-{index}",
        "source_offset_ms": offset_ms,
        "width": 100,
        "height": 100,
    }
    values.update(overrides)
    return FramePacket(**values)


def _animal(
    frame: FramePacket,
    box: tuple[float, float, float, float],
    *,
    score: float = 0.9,
    label: str = "animal",
) -> DetectionObservation:
    return DetectionObservation(
        "fake:1", label, score, frame.captured_at, f"detection:{frame.frame_id}:{box}",
        frame.frame_id, "fake", "fake", "fake-generation", box, "0", True,
    )


def test_ghost_tracker_support_does_not_absorb_a_later_distinct_appearance() -> None:
    """Reproduces the general shape of the reviewed-replay incorrect merge: a
    tracker-support resolver that keeps echoing the track's last-known box (a
    stand-in for a loose real patch matcher finding background) must not let a
    later, unrelated appearance at a similar position continue the same
    episode once genuine detector support has been stale for too long."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(), support_resolver=lambda _frame, track: track.bounding_box,
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(9)]

    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    assert any(update.lifecycle_state == "confirmed" for update in confirm_step.updates)
    first_generation = confirm_step.updates[-1].generation_id

    for index in range(2, 8):
        tracker.observe(frames[index], ())

    reentry_step = tracker.observe(frames[8], (_animal(frames[8], box),))
    reentry_update = next(item for item in reentry_step.updates if item.frame_id == frames[8].frame_id)

    assert reentry_update.generation_id != first_generation
    assert reentry_update.status == "started"


def test_brief_detector_miss_remains_one_episode() -> None:
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(), support_resolver=lambda _frame, track: track.bounding_box,
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 200) for index in range(4)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    miss_step = tracker.observe(frames[2], ())
    assert miss_step.updates[-1].generation_id == generation
    assert miss_step.updates[-1].status == "updated"

    reconfirm_step = tracker.observe(frames[3], (_animal(frames[3], box),))
    assert reconfirm_step.updates[-1].generation_id == generation


def test_brief_tracker_miss_remains_one_episode() -> None:
    tracker = ProviderNeutralFrameTracker("stream", _config())
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 200) for index in range(4)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    miss_step = tracker.observe(frames[2], ())
    assert miss_step.updates[-1].generation_id == generation
    assert miss_step.updates[-1].lifecycle_state == "temporarily_lost"

    reconfirm_step = tracker.observe(frames[3], (_animal(frames[3], box),))
    assert reconfirm_step.updates[-1].generation_id == generation
    assert reconfirm_step.updates[-1].lifecycle_state == "confirmed"


def test_long_stationary_animal_remains_one_episode() -> None:
    tracker = ProviderNeutralFrameTracker("stream", _config(maximum_track_duration_ms=60_000))
    box = (0.3, 0.3, 0.6, 0.6)
    frames = [_frame(index, index * 1000) for index in range(20)]
    generations = set()
    for frame in frames:
        step = tracker.observe(frame, (_animal(frame, box),))
        generations.update(update.generation_id for update in step.updates)
    assert len(generations) == 1

    finalize_step = tracker.finalize()
    assert len(finalize_step.terminals) == 1
    assert finalize_step.terminals[0].confirmed is True


def test_spatially_discontinuous_reappearance_starts_new_generation() -> None:
    tracker = ProviderNeutralFrameTracker("stream", _config())
    frames = [_frame(index, index * 1000) for index in range(3)]
    box_a = (0.05, 0.05, 0.2, 0.2)
    box_b = (0.75, 0.75, 0.95, 0.95)
    tracker.observe(frames[0], (_animal(frames[0], box_a),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box_a),))
    generation_a = confirm_step.updates[-1].generation_id

    step = tracker.observe(frames[2], (_animal(frames[2], box_b),))
    started = [update for update in step.updates if update.status == "started"]
    assert len(started) == 1
    assert started[0].generation_id != generation_a
    assert tracker.active_count == 2


def test_explicit_negative_frames_then_reentry_starts_new_generation() -> None:
    tracker = ProviderNeutralFrameTracker(
        "stream",
        _config(
            negative_detector_frames_to_end=2,
            maximum_missed_frames=10,
            tracker_expiry_ms=60_000,
            maximum_frame_gap_ms=60_000,
        ),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(5)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    tracker.observe(frames[2], (), detector_ran=True)
    tracker.observe(frames[3], (), detector_ran=True)
    reentry_step = tracker.observe(frames[4], (_animal(frames[4], box),), detector_ran=True)

    terminal = next(item for item in reentry_step.terminals if item.view.generation_id == generation)
    assert terminal.terminal_reason == "negative_interval_reentry"
    started = next(update for update in reentry_step.updates if update.status == "started")
    assert started.generation_id != generation


def test_ambiguous_reentry_is_reported_explicitly_without_reviving_the_generation() -> None:
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(maximum_missed_frames=1, tracker_expiry_ms=500, ambiguous_reentry_window_ms=3000),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(3)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    lost_step = tracker.observe(frames[2], ())
    terminal = next(item for item in lost_step.terminals if item.view.generation_id == generation)
    assert terminal.terminal_reason == "tracker_lost"

    reentry_frame = _frame(3, 2500)
    reentry_step = tracker.observe(reentry_frame, (_animal(reentry_frame, box),))
    started = next(update for update in reentry_step.updates if update.status == "started")
    assert started.generation_id != generation
    assert reentry_step.ambiguous_reentries == 1


def test_terminal_generation_cannot_be_revived() -> None:
    tracker = ProviderNeutralFrameTracker("stream", _config(maximum_missed_frames=1, tracker_expiry_ms=500))
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(3)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    lost_step = tracker.observe(frames[2], ())
    assert any(item.view.generation_id == generation for item in lost_step.terminals)

    reentry_frame = _frame(3, 2200)
    reentry_step = tracker.observe(reentry_frame, (_animal(reentry_frame, box),))
    assert all(update.generation_id != generation for update in reentry_step.updates)
    assert tracker.active_count == 1


def test_repeated_frame_identity_adds_no_support() -> None:
    tracker = ProviderNeutralFrameTracker("stream", _config())
    box = (0.2, 0.2, 0.5, 0.5)
    frame0 = _frame(0, 0)
    tracker.observe(frame0, (_animal(frame0, box),))

    duplicate = _frame(1, 500, frame_id=frame0.frame_id)
    repeat_step = tracker.observe(duplicate, (_animal(duplicate, box),))

    assert repeat_step == TrackerStep()
    assert tracker.active_count == 1


def test_invalid_episode_boundary_bounds_are_rejected() -> None:
    for overrides in (
        {"maximum_unsupported_detector_ms": 0},
        {"negative_detector_frames_to_end": 0},
        {"ambiguous_reentry_window_ms": 0},
    ):
        with pytest.raises(ValueError, match="invalid_tracker_bound"):
            _config(**overrides)


# --------------------------------------------------------------------------
# Stage 6.14: reviewed-to-replay evidence identity lineage
# --------------------------------------------------------------------------


def test_track_update_accumulates_supporting_source_capture_frame_ids() -> None:
    """(6, 30) `TrackUpdate.supporting_source_capture_frame_ids` mirrors
    `supporting_frame_ids` in reviewed-source-lineage space: it accumulates
    the original captured frame identity of every frame that genuinely
    supported this track generation, deduplicated independently, and stays
    empty for a frame carrying no known source lineage -- ordinary tracker
    episode-boundary behavior (confirmation, dedup, termination) is
    otherwise completely unaffected, matching every pre-existing test in
    this file passing unmodified."""

    tracker = ProviderNeutralFrameTracker("stream", _config())
    box = (0.2, 0.2, 0.5, 0.5)

    frame0 = _frame(0, 0, source_capture_frame_id="reviewed-frame-a")
    started = tracker.observe(frame0, (_animal(frame0, box),))
    assert started.updates[0].supporting_source_capture_frame_ids == ("reviewed-frame-a",)

    # A second, later frame with its own distinct source lineage.
    frame1 = _frame(1, 500, source_capture_frame_id="reviewed-frame-b")
    step1 = tracker.observe(frame1, (_animal(frame1, box),))
    assert step1.updates[0].supporting_source_capture_frame_ids == ("reviewed-frame-a", "reviewed-frame-b")
    # The replay-local supporting list keeps its own, distinct identities.
    assert step1.updates[0].supporting_frame_ids == (frame0.frame_id, frame1.frame_id)

    # A frame with no known source lineage (a generic, non-temporal-review
    # replay input) contributes nothing to the source list, but continues
    # supporting the replay-local list exactly as before.
    frame2 = _frame(2, 1000)
    assert frame2.source_capture_frame_id is None
    step2 = tracker.observe(frame2, (_animal(frame2, box),))
    assert step2.updates[0].supporting_source_capture_frame_ids == ("reviewed-frame-a", "reviewed-frame-b")
    assert step2.updates[0].supporting_frame_ids == (frame0.frame_id, frame1.frame_id, frame2.frame_id)

    # A repeated source identity (re-observing the same reviewed frame,
    # however that could happen) is deduplicated, matching the existing
    # replay-local dedup convention (test_repeated_frame_identity_adds_no_support).
    frame3 = _frame(3, 1500, source_capture_frame_id="reviewed-frame-b")
    step3 = tracker.observe(frame3, (_animal(frame3, box),))
    assert step3.updates[0].supporting_source_capture_frame_ids == ("reviewed-frame-a", "reviewed-frame-b")

    terminal = tracker.finalize("end_of_replay")
    assert terminal.updates[0].supporting_source_capture_frame_ids == ("reviewed-frame-a", "reviewed-frame-b")


def test_frame_tracker_module_has_structural_no_write_boundary() -> None:
    from pathlib import Path

    source = Path("src/mockingbird/observation/frame_tracker.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence",
        "StreamMonitoringPolicy", "LiveCameraSession", "species",
    )
    assert not any(token in source for token in forbidden)


def test_reconnect_continuity_module_has_structural_no_write_boundary() -> None:
    """`reconnect_continuity.py` is pure (see its module docstring): no
    product-repository/truth-write type and no network/filesystem import.
    Its own prose legitimately discusses *not* using species identity as a
    decision input, so unlike the sibling check above this does not forbid
    the bare word "species" -- it forbids actual product-write/transport
    dependencies."""
    from pathlib import Path

    source = Path("src/mockingbird/observation/reconnect_continuity.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence",
        "StreamMonitoringPolicy", "LiveCameraSession", "import socket", "import requests",
        "SpeciesSuggestion",
    )
    assert not any(token in source for token in forbidden)


# --- Stage 6.11: reconnect-safe tracker continuity --------------------------
#
# Hardware-free tests for ProviderNeutralFrameTracker.note_reconnect_boundary
# and the bounded per-track bridge state it grants. See
# docs/reconnect-continuity-contract.md. End-to-end (provider/replay-level)
# coverage, including the real session-03/04 fragmentation reproduction and
# fix, lives in tests/test_observation_frame_driven.py.


def _bridge_config(**overrides: object) -> ReconnectBridgeConfig:
    values: dict[str, object] = {
        "maximum_reconnect_gap_ms": 15_000,
        "maximum_reconnect_bridge_duration_ms": 5_000,
        "maximum_reconnect_bridge_frames": 4,
        "maximum_reconnect_geometry_displacement": 0.18,
        "maximum_reconnect_size_change_ratio": 0.5,
    }
    values.update(overrides)
    return ReconnectBridgeConfig(**values)


def _boundary_time(offset_ms: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=offset_ms)


def test_confirmed_track_bridges_a_short_benign_reconnect() -> None:
    """Scenario 1: a confirmed, coherent track survives one generation
    across a reconnect gap that comfortably exceeds the tracker's own
    ordinary maximum_frame_gap_ms/tracker_expiry_ms bounds -- exactly the
    case this bridge exists to cover."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id
    assert confirm_step.updates[-1].lifecycle_state == "confirmed"

    boundary_step = tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    assert len(boundary_step.updates) == 1
    assert boundary_step.updates[0].generation_id == generation
    assert boundary_step.updates[0].lifecycle_state == "temporarily_lost"
    assert boundary_step.updates[0].status == "updated"
    assert tracker.reconnect_pending_count == 1

    reacquire_frame = _frame(2, 6200)
    reacquire_step = tracker.observe(reacquire_frame, (_animal(reacquire_frame, box),))
    reacquired = next(item for item in reacquire_step.updates if item.generation_id == generation)
    assert reacquired.lifecycle_state == "confirmed"
    assert reacquire_step.reconnect_bridges_continued == 1
    assert reacquire_step.reconnect_bridges_expired == 0
    assert not reacquire_step.terminals
    assert tracker.active_count == 1
    assert tracker.reconnect_pending_count == 0


def test_reconnect_survival_alone_does_not_confirm_a_tentative_track() -> None:
    """Scenario 2: merely surviving a reconnect boundary must never confirm
    a tentative track -- only real evidence can."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(minimum_detector_confirmations=2), reconnect_bridge_config=_bridge_config(),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    start_frame = _frame(0, 0)
    start_step = tracker.observe(start_frame, (_animal(start_frame, box),))
    generation = start_step.updates[-1].generation_id
    assert start_step.updates[-1].lifecycle_state == "tentative"

    boundary_step = tracker.note_reconnect_boundary(boundary_offset_ms=5000, captured_at=_boundary_time(5000))
    assert boundary_step.updates[0].generation_id == generation
    assert boundary_step.updates[0].lifecycle_state == "temporarily_lost"

    internal_track = next(iter(tracker._tracks.values()))
    assert internal_track.detector_confirmation_count == 1
    assert internal_track.confirmed is False


def test_post_reconnect_detector_support_continues_a_track() -> None:
    """Scenario 3."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    reacquire_frame = _frame(2, 6200)
    step = tracker.observe(reacquire_frame, (_animal(reacquire_frame, box),), detector_ran=True)
    reacquired = next(item for item in step.updates if item.generation_id == generation)
    assert reacquired.lifecycle_state == "confirmed"
    assert reacquired.detector_confirmation_count == 3


def test_post_reconnect_coherent_tracker_support_continues_when_configured() -> None:
    """Scenario 4: bounded local tracker-support (no fresh detector hit) is
    also sufficient to reacquire during the bridge window, exactly like
    ordinary frame-to-frame tracker-support."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(), support_resolver=lambda frame, track: track.bounding_box,
        reconnect_bridge_config=_bridge_config(),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    reacquire_frame = _frame(2, 6200)
    step = tracker.observe(reacquire_frame, ())
    reacquired = next(item for item in step.updates if item.generation_id == generation)
    assert reacquired.lifecycle_state == "confirmed"
    assert step.reconnect_bridges_continued == 1


def test_no_post_reconnect_support_eventually_expires_the_track() -> None:
    """Scenario 5: with no matching evidence at all, the bridge's own
    bounded frame budget -- not the ordinary miss/expiry bounds -- ends the
    episode with a distinguishable terminal reason."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(),
        reconnect_bridge_config=_bridge_config(maximum_reconnect_bridge_frames=2, maximum_reconnect_bridge_duration_ms=100_000),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    generation = confirm_step.updates[-1].generation_id

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    step1 = tracker.observe(_frame(2, 6200), ())
    assert step1.terminals == ()
    assert tracker.active_count == 1
    step2 = tracker.observe(_frame(3, 6400), ())
    assert len(step2.terminals) == 1
    assert step2.terminals[0].terminal_reason == "reconnect_bridge_expired"
    assert step2.terminals[0].view.generation_id == generation
    assert step2.reconnect_bridges_expired == 1
    assert tracker.active_count == 0


def test_reconnect_boundary_itself_adds_no_detector_or_tracker_support() -> None:
    """Scenario 17: noting a reconnect boundary is not itself evidence."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    tracker.observe(frames[1], (_animal(frames[1], box),))
    before = next(iter(tracker._tracks.values()))
    detector_before, support_before = before.detector_confirmation_count, before.tracker_support_count

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    tracker.note_reconnect_boundary(boundary_offset_ms=6100, captured_at=_boundary_time(6100))
    after = next(iter(tracker._tracks.values()))
    assert after.detector_confirmation_count == detector_before
    assert after.tracker_support_count == support_before


def test_repeated_reconnects_cannot_confirm_a_tentative_track() -> None:
    """Scenario 18: several reconnect cycles, each bridged only by
    tracker-support reacquisition (never a fresh, strong detector hit),
    must never accumulate into a confirmed track."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(minimum_detector_confirmations=5, strong_detection_threshold=0.99),
        support_resolver=lambda frame, track: track.bounding_box,
        reconnect_bridge_config=_bridge_config(),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    start_frame = _frame(0, 0)
    start_step = tracker.observe(start_frame, (_animal(start_frame, box, score=0.5),))
    generation = start_step.updates[-1].generation_id
    assert start_step.updates[-1].lifecycle_state == "tentative"

    offset = 0
    for cycle in range(4):
        offset += 5000
        tracker.note_reconnect_boundary(boundary_offset_ms=offset, captured_at=_boundary_time(offset))
        reacquire_step = tracker.observe(_frame(10 + cycle, offset + 200), ())
        reacquired = next(item for item in reacquire_step.updates if item.generation_id == generation)
        assert reacquired.lifecycle_state == "tentative"
    assert tracker.active_count == 1


def test_spatially_incompatible_reentry_after_reconnect_starts_a_new_generation() -> None:
    """Scenario 19 (and the merge-protection principle "broad-class match
    alone is insufficient for continuity"): a same-broad-class detection far
    from the pending track's last known geometry cannot reacquire it."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    box = (0.1, 0.1, 0.3, 0.3)
    far_box = (0.7, 0.7, 0.9, 0.9)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    original_generation = confirm_step.updates[-1].generation_id

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    reentry_frame = _frame(2, 6200)
    step = tracker.observe(reentry_frame, (_animal(reentry_frame, far_box),))
    started = [item for item in step.updates if item.status == "started"]
    assert len(started) == 1
    assert started[0].generation_id != original_generation
    assert step.reconnect_bridges_continued == 0
    # The original pending track is untouched by the incompatible
    # detection -- still pending, not silently merged and not terminated.
    assert tracker.active_count == 2


def test_different_broad_class_after_reconnect_does_not_merge() -> None:
    """Scenario 20: a different-broad-class subject after reconnect starts
    its own generation and never merges into the pending one."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box, label="animal"),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box, label="animal"),))
    original_generation = confirm_step.updates[-1].generation_id

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    reentry_frame = _frame(2, 6200)
    step = tracker.observe(reentry_frame, (_animal(reentry_frame, box, label="vehicle"),))
    started = [item for item in step.updates if item.status == "started"]
    assert len(started) == 1
    assert started[0].broad_class == "vehicle"
    assert started[0].generation_id != original_generation
    assert tracker.active_count == 2


def test_simultaneous_tracks_bridge_independently() -> None:
    """Scenario 21: two simultaneously active tracks each get their own
    bounded bridge budget -- one may reacquire while the other expires, in
    the very same frame, with no cross-contamination."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(maximum_active_tracks=8),
        reconnect_bridge_config=_bridge_config(maximum_reconnect_bridge_frames=1, maximum_reconnect_bridge_duration_ms=100_000),
    )
    left_box, right_box = (0.05, 0.05, 0.2, 0.2), (0.8, 0.8, 0.95, 0.95)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], left_box), _animal(frames[0], right_box)))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], left_box), _animal(frames[1], right_box)))
    left_generation = next(u.generation_id for u in confirm_step.updates if u.bounding_box == left_box)
    right_generation = next(u.generation_id for u in confirm_step.updates if u.bounding_box == right_box)
    assert left_generation != right_generation

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    # Only the left subject reappears; the right one sends no further
    # evidence and must expire on its own bounded budget in this same step.
    reacquire_frame = _frame(2, 6200)
    step = tracker.observe(reacquire_frame, (_animal(reacquire_frame, left_box),))
    left_update = next(u for u in step.updates if u.generation_id == left_generation)
    assert left_update.lifecycle_state == "confirmed"
    assert step.reconnect_bridges_continued == 1
    assert step.reconnect_bridges_expired == 1
    assert any(
        item.view.generation_id == right_generation and item.terminal_reason == "reconnect_bridge_expired"
        for item in step.terminals
    )
    assert tracker.active_count == 1


def test_ambiguous_post_reconnect_association_does_not_silently_merge() -> None:
    """Scenario 22: one incoming detection plausibly, near-equidistantly
    compatible with two pending tracks must not be silently assigned to
    either. Uses the tracker's default (tight) ambiguity_margin -- box_a and
    box_b are close enough to each other that a *self*-match still clearly
    wins on ordinary frames (score gap ~0.2, no ambiguity), but a detection
    placed at their midpoint scores almost identically against both pending
    tracks (score gap ~0.0), which is exactly the ambiguous case."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    box_a, box_b = (0.2, 0.2, 0.4, 0.4), (0.22, 0.2, 0.42, 0.4)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box_a), _animal(frames[0], box_b)))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box_a), _animal(frames[1], box_b)))
    assert len({u.generation_id for u in confirm_step.updates}) == 2

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    generations_before = {track.generation_id for track in tracker._tracks.values()}
    midpoint_box = (0.21, 0.2, 0.41, 0.4)
    midpoint_frame = _frame(2, 6200)
    step = tracker.observe(midpoint_frame, (_animal(midpoint_frame, midpoint_box),))
    assert step.reconnect_ambiguous_associations >= 1
    assert step.reconnect_bridges_continued == 0
    # Neither pending track is silently merged onto the ambiguous
    # detection (an unmatched detection starts its own new, distinct
    # generation instead -- exactly the existing, unmodified ambiguous-
    # reentry philosophy: "an ambiguous association is exposed as a count,
    # never a silent merge", see frame-driven-shadow-provider-contract.md),
    # and neither original pending track is terminated by it either.
    assert tracker.active_count == 3
    started = [item for item in step.updates if item.status == "started"]
    assert len(started) == 1
    assert started[0].generation_id not in generations_before


def test_reconnect_bridge_expired_generation_cannot_revive() -> None:
    """Scenario 23: a terminated (bridge-expired) generation never comes
    back, even when a later detection lands at the exact same geometry."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(),
        reconnect_bridge_config=_bridge_config(maximum_reconnect_bridge_frames=1, maximum_reconnect_bridge_duration_ms=100_000),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box),))
    original_generation = confirm_step.updates[-1].generation_id

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    expire_step = tracker.observe(_frame(2, 6200), ())
    assert any(
        item.view.generation_id == original_generation and item.terminal_reason == "reconnect_bridge_expired"
        for item in expire_step.terminals
    )
    assert tracker.active_count == 0

    revival_attempt_frame = _frame(3, 6400)
    revival_step = tracker.observe(revival_attempt_frame, (_animal(revival_attempt_frame, box),))
    started = [item for item in revival_step.updates if item.status == "started"]
    assert len(started) == 1
    assert started[0].generation_id != original_generation
    assert started[0].track_id != expire_step.terminals[0].view.track_id


def test_bridge_state_is_bounded_and_no_op_with_no_active_tracks() -> None:
    """Scenario 32: noting a reconnect boundary with nothing active is a
    safe, bounded no-op -- it never grows any state on its own."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    step = tracker.note_reconnect_boundary(boundary_offset_ms=1000, captured_at=_boundary_time(1000))
    assert step == TrackerStep()
    assert tracker.active_count == 0
    assert tracker.reconnect_pending_count == 0


def test_reset_releases_pending_bridge_state() -> None:
    """Scenario 33: stop/reset releases any in-progress bridge state."""
    tracker = ProviderNeutralFrameTracker("stream", _config(), reconnect_bridge_config=_bridge_config())
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(2)]
    tracker.observe(frames[0], (_animal(frames[0], box),))
    tracker.observe(frames[1], (_animal(frames[1], box),))
    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=_boundary_time(6000))
    assert tracker.reconnect_pending_count == 1

    tracker.reset()
    assert tracker.active_count == 0
    assert tracker.reconnect_pending_count == 0


def test_reconnect_bridge_config_defaults_used_when_not_supplied() -> None:
    """A tracker built without an explicit reconnect_bridge_config still
    gets a valid, bounded default rather than failing or silently disabling
    the bridge."""
    tracker = ProviderNeutralFrameTracker("stream", _config())
    assert isinstance(tracker._reconnect_bridge_config, ReconnectBridgeConfig)
