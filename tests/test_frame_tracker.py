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


def test_frame_tracker_module_has_structural_no_write_boundary() -> None:
    from pathlib import Path

    source = Path("src/mockingbird/observation/frame_tracker.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence",
        "StreamMonitoringPolicy", "LiveCameraSession", "species",
    )
    assert not any(token in source for token in forbidden)
