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
    # Stage 6.16: `maximum_weak_support_span_ms=1` keeps this test isolated
    # from the new widened confirmed-track gap tolerance (`_gap_bound`) --
    # this test is about non-revival/ambiguous-reentry reporting, not
    # confirmed-track continuity, so the loss window at frame 2 stays
    # exactly as tight as before this stage (an eligibility span this
    # short expires between frame 1's confirmation and frame 2, unlike
    # `maximum_unsupported_detector_ms`, which frame 0->1's own
    # confirmation step also depends on staying generous).
    tracker = ProviderNeutralFrameTracker(
        "stream",
        _config(
            maximum_missed_frames=1, tracker_expiry_ms=500, ambiguous_reentry_window_ms=3000,
            maximum_weak_support_span_ms=1,
        ),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(3)]
    # Stage 6.16: kept below _config()'s strong_detection_threshold(0.8) so
    # this confirmed-via-repeated-weak-evidence track never "graduates" to
    # permanent widened-tolerance eligibility -- maximum_weak_support_span_
    # ms=1 above then correctly isolates this test from the new tolerance.
    tracker.observe(frames[0], (_animal(frames[0], box, score=0.5),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box, score=0.5),))
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
    # Stage 6.16: see the comment in
    # test_ambiguous_reentry_is_reported_explicitly_without_reviving_the_generation
    # -- `maximum_weak_support_span_ms=1` keeps this test isolated from the
    # new widened confirmed-track gap tolerance.
    tracker = ProviderNeutralFrameTracker(
        "stream", _config(maximum_missed_frames=1, tracker_expiry_ms=500, maximum_weak_support_span_ms=1),
    )
    box = (0.2, 0.2, 0.5, 0.5)
    frames = [_frame(index, index * 1000) for index in range(3)]
    # Stage 6.16: kept weak (see the comment in the ambiguous-reentry test
    # above) so this test's tight-bound timing is unaffected by the new
    # widened confirmed-track tolerance.
    tracker.observe(frames[0], (_animal(frames[0], box, score=0.5),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box, score=0.5),))
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


# --- Stage 6.16: sustained-visit continuity through detector-confidence dips
#
# Hardware-free tests for the bounded strong/weak/tracker-only evidence
# hierarchy (see docs/frame-driven-shadow-provider-contract.md). Real
# attempt-3 fragmentation reproduction and the fix-proof end-to-end scenario
# live in tests/test_observation_frame_driven.py; this module covers the
# tracker's own unit-level continuity/confirmation/bound rules directly.


def _stage616_config(**overrides: object) -> TrackerConfiguration:
    """Values chosen to mirror the real deployed frame-driven provider
    configuration (data/models/observation-onnx-cuda/frame-driven-provider-
    config.json) rather than arbitrary test-only numbers, so these tests
    exercise the same bound relationships the real fragmentation was
    characterized against."""
    values: dict[str, object] = {
        "strong_detection_threshold": 0.7,
        "minimum_detector_confirmations": 2,
        "minimum_tracker_support_frames": 1,
        "maximum_missed_frames": 3,
        "maximum_frame_gap_ms": 1500,
        "tracker_expiry_ms": 1200,
        "maximum_track_duration_ms": 120_000,
        "maximum_active_tracks": 8,
        "maximum_unsupported_detector_ms": 5000,
        "negative_detector_frames_to_end": 2,
        "weak_detector_support_floor": 0.05,
        "maximum_weak_support_span_ms": 15000,
    }
    values.update(overrides)
    return TrackerConfiguration(**values)


def test_strong_weak_strong_remains_one_confirmed_episode() -> None:
    """Scenario 1: a confirmed track's confidence dipping below
    `strong_detection_threshold` and then recovering never fragments the
    episode -- the core Stage 6.16 continuity guarantee, reproducing the
    proven real attempt-3 mechanism (see
    data/field-acceptance/2026-08-07-stage6.16-sustained-visit-continuity/
    fragmentation-characterization.md) at unit scale."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.4, 0.4, 0.6, 0.6)
    offsets = [0, 500, 3000, 6000]
    frames = [_frame(index, offset) for index, offset in enumerate(offsets)]
    tracker.observe(frames[0], (_animal(frames[0], box, score=0.8),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box, score=0.82),))
    generation = confirm_step.updates[-1].generation_id
    assert confirm_step.updates[-1].lifecycle_state == "confirmed"

    # 2500ms gap, past maximum_frame_gap_ms(1500), inside the widened bound.
    weak_step = tracker.observe(frames[2], (_animal(frames[2], box, score=0.3),))
    assert weak_step.updates[-1].generation_id == generation
    assert weak_step.updates[-1].lifecycle_state == "confirmed"
    assert weak_step.updates[-1].support_state == "weak_detector_supported"
    assert weak_step.updates[-1].weak_detector_support_count == 1

    strong_step = tracker.observe(frames[3], (_animal(frames[3], box, score=0.85),))
    assert strong_step.updates[-1].generation_id == generation
    assert strong_step.updates[-1].support_state == "strong_detector_supported"
    assert tracker.active_count == 1


def test_weak_support_does_not_increment_strong_confirmation_count() -> None:
    """Scenario 2. `weak_detector_support_count` tracks weak observations
    separately from `detector_confirmation_count` -- which keeps its
    pre-existing, unchanged meaning of "every genuine matched observation,"
    strong or weak (real attempt-3 evidence proved a genuinely continuous
    subject's own confirming pair is routinely both individually below
    `strong_detection_threshold` -- see fragmentation-characterization.md --
    so gating that count itself on strength would hurt appearance recall,
    not just continuity). What weak evidence never does is advance the
    widened-tolerance anchor (`last_strong_detector_offset_ms`, exercised
    via `support_state` below and the dedicated widening tests)."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.4, 0.4, 0.6, 0.6)
    frames = [_frame(index, index * 500) for index in range(5)]
    tracker.observe(frames[0], (_animal(frames[0], box, score=0.75),))
    confirm_step = tracker.observe(frames[1], (_animal(frames[1], box, score=0.78),))
    assert confirm_step.updates[-1].detector_confirmation_count == 2
    assert confirm_step.updates[-1].lifecycle_state == "confirmed"
    internal_track = next(iter(tracker._tracks.values()))
    strong_anchor_after_confirm = internal_track.last_strong_detector_offset_ms
    assert strong_anchor_after_confirm == 500

    for index in range(2, 5):
        step = tracker.observe(frames[index], (_animal(frames[index], box, score=0.2),))
        update = step.updates[-1]
        assert update.detector_confirmation_count == 2 + (index - 1)  # unchanged, ordinary counting
        assert update.weak_detector_support_count == index - 1
        assert update.support_state == "weak_detector_supported"
        # The strong anchor never advances from a weak hit.
        assert next(iter(tracker._tracks.values())).last_strong_detector_offset_ms == strong_anchor_after_confirm


def test_weak_support_alone_cannot_confirm_a_tentative_track() -> None:
    """Scenario 3, precisely stated: a single, isolated weak observation --
    exactly like a single isolated strong one -- cannot confirm by itself;
    `minimum_detector_confirmations` was always a repeated-evidence bar, not
    a strength bar, and this stage does not change that (real attempt-3
    evidence proved a genuinely continuous subject's own confirming pair is
    routinely both individually weak -- gating the count itself on strength
    would hurt recall, not just continuity; see fragmentation-
    characterization.md). What Stage 6.16 specifically adds: a track
    confirmed entirely from weak evidence (no strong hit ever) gets only a
    bounded, one-time "provisional" widened-tolerance allowance from its
    own start (`maximum_weak_support_span_ms`), not the permanent one a
    genuinely strong hit grants (see
    test_graduated_track_keeps_widened_tolerance_past_the_provisional_span)."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _stage616_config(minimum_detector_confirmations=2, maximum_weak_support_span_ms=3000),
    )
    box = (0.4, 0.4, 0.6, 0.6)
    single_frame = _frame(0, 0)
    single_step = tracker.observe(single_frame, (_animal(single_frame, box, score=0.3),))
    assert single_step.updates[-1].lifecycle_state == "tentative"

    confirm_frame = _frame(1, 500)
    confirm_step = tracker.observe(confirm_frame, (_animal(confirm_frame, box, score=0.32),))
    generation = confirm_step.updates[-1].generation_id
    assert confirm_step.updates[-1].lifecycle_state == "confirmed"  # two coherent weak hits: ordinary bar met
    internal_track = next(iter(tracker._tracks.values()))
    assert internal_track.last_strong_detector_offset_ms is None  # never anchored -- "provisional" tier only

    # Still within the bounded provisional window from track start
    # (0 -> 2400 = 2400ms <= 3000ms): bridges fine even with no strong hit.
    bridge_frame = _frame(2, 2400)
    bridge_step = tracker.observe(bridge_frame, (_animal(bridge_frame, box, score=0.25),))
    assert bridge_step.updates[-1].generation_id == generation
    assert bridge_step.updates[-1].lifecycle_state == "confirmed"

    # Past the provisional window from track start (0 -> 5000 = 5000ms >
    # 3000ms), still with no strong hit ever: the one-time allowance is
    # exhausted and the ordinary tight bound governs again.
    late_frame = _frame(3, 5000)
    late_step = tracker.observe(late_frame, ())
    terminal = next(item for item in late_step.terminals if item.view.generation_id == generation)
    assert terminal.terminal_reason == "tracker_lost"
    assert terminal.confirmed is True


def test_graduated_track_keeps_widened_tolerance_past_the_provisional_span() -> None:
    """Scenario 5: once a confirmed track has shown at least one genuinely
    strong detector hit, the widened confirmed-track gap tolerance no
    longer expires after `maximum_weak_support_span_ms` -- that bounded
    span governs only a track that has never shown strong evidence (the
    "provisional" tier tested above)."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config(maximum_weak_support_span_ms=1000))
    box = (0.4, 0.4, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.75),))
    confirm_step = tracker.observe(_frame(1, 500), (_animal(_frame(1, 500), box, score=0.8),))
    generation = confirm_step.updates[-1].generation_id
    internal_track = next(iter(tracker._tracks.values()))
    assert internal_track.last_strong_detector_offset_ms == 500

    # Well past maximum_weak_support_span_ms(1000) since track start
    # (0 -> 4500 = 4500ms), which would have expired a provisional
    # (never-strong) track's eligibility -- but this one graduated.
    late_gap_frame = _frame(2, 4500)
    step = tracker.observe(late_gap_frame, (_animal(late_gap_frame, box, score=0.2),))
    assert step.updates[-1].generation_id == generation
    assert step.updates[-1].lifecycle_state == "confirmed"


def test_bounded_weak_support_refreshes_continuity() -> None:
    """Scenario 4."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.4, 0.4, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.75),))
    confirm_step = tracker.observe(_frame(1, 500), (_animal(_frame(1, 500), box, score=0.8),))
    generation = confirm_step.updates[-1].generation_id

    gap_frame = _frame(2, 2900)  # 2400ms gap: past the tight bound, inside the widened one
    step = tracker.observe(gap_frame, (_animal(gap_frame, box, score=0.25),))
    update = step.updates[-1]
    assert update.generation_id == generation
    assert update.lifecycle_state == "confirmed"
    assert update.support_state == "weak_detector_supported"
    assert step.confidence_dip_bridges == 1
    internal_track = next(iter(tracker._tracks.values()))
    assert internal_track.missed_frames == 0
    assert internal_track.last_offset_ms == 2900


def test_strong_tracker_only_strong_bridges_within_limit() -> None:
    """Scenario 6."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _stage616_config(), support_resolver=lambda _frame, track: track.bounding_box,
    )
    box = (0.4, 0.4, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.75),))
    confirm_step = tracker.observe(_frame(1, 500), (_animal(_frame(1, 500), box, score=0.8),))
    generation = confirm_step.updates[-1].generation_id

    tracker_only_frame = _frame(2, 2900)  # 2400ms gap, no detection at all
    step = tracker.observe(tracker_only_frame, ())
    update = step.updates[-1]
    assert update.generation_id == generation
    assert update.support_state == "tracker_supported"
    assert update.lifecycle_state == "confirmed"

    strong_frame = _frame(3, 3400)
    strong_step = tracker.observe(strong_frame, (_animal(strong_frame, box, score=0.85),))
    assert strong_step.updates[-1].generation_id == generation
    assert tracker.active_count == 1


def test_tracker_only_support_remains_bounded() -> None:
    """Scenario 7: tracker-only support (image/tracker coherence with no
    current detector support) may bridge only a bounded interval -- once
    even the widened bound is exceeded with nothing but tracker-support in
    between, the episode still ends, even though the support resolver would
    keep matching if asked."""
    tracker = ProviderNeutralFrameTracker(
        "stream", _stage616_config(maximum_unsupported_detector_ms=3000),
        support_resolver=lambda _frame, track: track.bounding_box,
    )
    box = (0.4, 0.4, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.75),))
    confirm_step = tracker.observe(_frame(1, 500), (_animal(_frame(1, 500), box, score=0.8),))
    generation = confirm_step.updates[-1].generation_id

    # last_detector_offset_ms stays 500 (tracker-support never refreshes
    # it): 500 -> 4000 = 3500ms > maximum_unsupported_detector_ms(3000).
    late_frame = _frame(2, 4000)
    step = tracker.observe(late_frame, ())
    terminal = next(item for item in step.terminals if item.view.generation_id == generation)
    assert terminal.terminal_reason == "maximum_unsupported_duration"


def test_unsupported_interval_terminates() -> None:
    """Scenario 8: no supporting evidence of any kind -- temporary loss,
    then eventual deterministic expiry."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.4, 0.4, 0.6, 0.6)
    frame0 = _frame(0, 0)
    tracker.observe(frame0, (_animal(frame0, box, score=0.75),))
    silent_frame = _frame(1, 3000)  # gap with zero evidence of any kind
    step = tracker.observe(silent_frame, ())
    assert len(step.terminals) == 1
    assert step.terminals[0].terminal_reason == "insufficient_support"
    assert tracker.active_count == 0


def test_explicit_negative_frames_still_matter_for_confirmed_track() -> None:
    """Scenario 9: Stage 6.16's widened tolerance never touches the
    explicit-negative-frame mechanism -- a confirmed track still ends
    promptly on `negative_detector_frames_to_end` consecutive frames the
    detector genuinely ran and found nothing usable, even though every gap
    involved is comfortably inside the widened bound."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config(negative_detector_frames_to_end=2))
    box = (0.4, 0.4, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.75),))
    confirm_step = tracker.observe(_frame(1, 500), (_animal(_frame(1, 500), box, score=0.8),))
    generation = confirm_step.updates[-1].generation_id

    tracker.observe(_frame(2, 1000), (), detector_ran=True)
    tracker.observe(_frame(3, 1500), (), detector_ran=True)
    # The negative-frame count reaches `negative_detector_frames_to_end`
    # after frame 3's own miss; the pre-check loop that acts on it runs at
    # the *start* of the next observe() call (frame 4), exactly like the
    # pre-existing `test_explicit_negative_frames_then_reentry_starts_new_
    # generation` above.
    step = tracker.observe(_frame(4, 2000), (), detector_ran=True)
    terminal = next(item for item in step.terminals if item.view.generation_id == generation)
    assert terminal.terminal_reason == "negative_interval_reentry"


def test_real_departure_closes_episode() -> None:
    """Scenario 10: a confirmed subject that genuinely leaves still closes
    within bounded policy, and a later, coincidentally same-geometry
    detection never revives the ended generation."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.4, 0.4, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.75),))
    confirm_step = tracker.observe(_frame(1, 500), (_animal(_frame(1, 500), box, score=0.8),))
    generation = confirm_step.updates[-1].generation_id

    step = tracker.observe(_frame(2, 20_000), ())  # true departure: silence well past every bound
    terminal = next(item for item in step.terminals if item.view.generation_id == generation)
    assert terminal.confirmed is True
    assert tracker.active_count == 0

    reentry_frame = _frame(3, 20_500)
    reentry_step = tracker.observe(reentry_frame, (_animal(reentry_frame, box, score=0.8),))
    started = [u for u in reentry_step.updates if u.status == "started"]
    assert len(started) == 1
    assert started[0].generation_id != generation


def test_persistent_weak_static_artifact_confirms_but_never_gets_widened_tolerance() -> None:
    """Scenario 12 (attempt-2-style hard-negative principle), precisely
    stated: the same static geometry producing a weak detection on every
    frame, with genuine strong support never once occurring, *may* still
    confirm from repeated spatially-coherent weak evidence -- this is
    pre-existing, unchanged behavior (attempt-2's own real session already
    produced 38 such confirmed clutter proposals under pre-Stage-6.16 code;
    see the representative-shadow-acceptance FINAL-REPORT.md), not a new
    regression this stage introduces or is scoped to prevent. What this
    stage specifically guarantees: such a track never becomes eligible for
    the widened confirmed-track gap tolerance (`last_strong_detector_
    offset_ms` stays `None` forever), so it cannot live any longer or span
    any wider a gap than it already could before this stage -- confirmed by
    zero `confidence_dip_bridges` throughout a long run."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.4, 0.4, 0.6, 0.6)
    dip_bridges = 0
    for index in range(40):
        frame = _frame(index, index * 400)  # tight, 400ms cadence -- comfortably inside every ordinary bound
        step = tracker.observe(frame, (_animal(frame, box, score=0.35),))
        dip_bridges += step.confidence_dip_bridges
    internal_track = next(iter(tracker._tracks.values()))
    assert internal_track.last_strong_detector_offset_ms is None
    assert dip_bridges == 0


def test_persistent_weak_static_artifact_cannot_stay_alive_indefinitely() -> None:
    """Scenario 13: even a continuously-refreshed weak artifact is bounded
    -- `maximum_track_duration_ms` still caps it regardless of confirmed
    status, exactly as it did before this stage."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config(maximum_track_duration_ms=10_000))
    box = (0.4, 0.4, 0.6, 0.6)
    terminated = False
    generations: set[str] = set()
    index, offset = 0, 0
    while offset <= 12_000:
        frame = _frame(index, offset)
        step = tracker.observe(frame, (_animal(frame, box, score=0.35),))
        generations.update(u.generation_id for u in step.updates)
        if step.terminals:
            terminated = True
            assert step.terminals[0].terminal_reason == "maximum_duration"
        index += 1
        offset += 400
    assert terminated
    assert len(generations) <= 2  # bounded, not immortal


def test_confirmed_track_still_bounded_by_maximum_track_duration() -> None:
    """The widened tolerance never defeats the absolute
    `maximum_track_duration_ms` cap, even for a continuously well-supported
    confirmed track."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config(maximum_track_duration_ms=5000))
    box = (0.4, 0.4, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.8),))
    confirm_step = tracker.observe(_frame(1, 300), (_animal(_frame(1, 300), box, score=0.85),))
    generation = confirm_step.updates[-1].generation_id

    for index, offset in enumerate((1000, 2000, 3000, 4000), start=2):
        frame = _frame(index, offset)
        step = tracker.observe(frame, (_animal(frame, box, score=0.85),))
        assert not step.terminals

    final_frame = _frame(6, 5100)
    step = tracker.observe(final_frame, (_animal(final_frame, box, score=0.85),))
    terminal = next(item for item in step.terminals if item.view.generation_id == generation)
    assert terminal.terminal_reason == "maximum_duration"


def test_later_subject_creates_new_generation() -> None:
    """Scenario 11."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box_a = (0.05, 0.05, 0.2, 0.2)
    box_b = (0.75, 0.75, 0.95, 0.95)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box_a, score=0.8),))
    confirm_step = tracker.observe(_frame(1, 300), (_animal(_frame(1, 300), box_a, score=0.85),))
    generation_a = confirm_step.updates[-1].generation_id
    tracker.observe(_frame(2, 25_000), ())  # A departs, long silence

    frame_b = _frame(3, 25_500)
    step = tracker.observe(frame_b, (_animal(frame_b, box_b, score=0.8),))
    started = [u for u in step.updates if u.status == "started"]
    assert len(started) == 1
    assert started[0].generation_id != generation_a


def test_geometry_incompatible_weak_detection_is_ignored() -> None:
    """Scenario 14: a weak detection far from an existing track's geometry
    cannot associate to it -- the existing IoU/centroid gate governs weak
    evidence exactly like strong evidence; a spatially distant weak
    detection instead starts its own separate, independently-tentative
    generation rather than silently extending the original track."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.1, 0.1, 0.3, 0.3)
    far_box = (0.8, 0.8, 0.95, 0.95)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.8),))
    confirm_step = tracker.observe(_frame(1, 300), (_animal(_frame(1, 300), box, score=0.85),))
    generation = confirm_step.updates[-1].generation_id

    far_frame = _frame(2, 600)
    step = tracker.observe(far_frame, (_animal(far_frame, far_box, score=0.3),))
    original_update = next(u for u in step.updates if u.generation_id == generation)
    assert original_update.support_state != "weak_detector_supported"
    started = [u for u in step.updates if u.status == "started"]
    assert len(started) == 1
    assert started[0].generation_id != generation
    assert started[0].lifecycle_state == "tentative"
    assert tracker.active_count == 2


def test_broad_class_mismatch_is_ignored() -> None:
    """Scenario 15."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box = (0.3, 0.3, 0.6, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box, score=0.8, label="animal"),))
    confirm_step = tracker.observe(_frame(1, 300), (_animal(_frame(1, 300), box, score=0.85, label="animal"),))
    generation = confirm_step.updates[-1].generation_id

    mismatch_frame = _frame(2, 600)
    step = tracker.observe(mismatch_frame, (_animal(mismatch_frame, box, score=0.3, label="vehicle"),))
    original_update = next(u for u in step.updates if u.generation_id == generation)
    assert original_update.support_state != "weak_detector_supported"
    started = [u for u in step.updates if u.status == "started"]
    assert len(started) == 1
    assert started[0].broad_class == "vehicle"
    assert started[0].generation_id != generation


def test_ambiguous_association_does_not_silently_merge() -> None:
    """Scenario 16 (bounded evidence hierarchy variant of the existing
    ambiguity-margin protection): an ambiguous weak detection touching two
    already-confirmed tracks is assigned to neither."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    box_a, box_b = (0.2, 0.2, 0.4, 0.4), (0.22, 0.2, 0.42, 0.4)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), box_a, score=0.8), _animal(_frame(0, 0), box_b, score=0.8)))
    confirm_step = tracker.observe(
        _frame(1, 300), (_animal(_frame(1, 300), box_a, score=0.85), _animal(_frame(1, 300), box_b, score=0.85)),
    )
    assert len({u.generation_id for u in confirm_step.updates}) == 2

    midpoint_box = (0.21, 0.2, 0.41, 0.4)
    midpoint_frame = _frame(2, 600)
    step = tracker.observe(midpoint_frame, (_animal(midpoint_frame, midpoint_box, score=0.3),))
    assert step.ambiguous_associations == 1
    started = [u for u in step.updates if u.status == "started"]
    assert len(started) == 1
    assert tracker.active_count == 3


def test_two_simultaneous_subjects_remain_separate() -> None:
    """Scenario 17."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    left_box, right_box = (0.05, 0.05, 0.2, 0.2), (0.8, 0.8, 0.95, 0.95)
    tracker.observe(
        _frame(0, 0), (_animal(_frame(0, 0), left_box, score=0.8), _animal(_frame(0, 0), right_box, score=0.8)),
    )
    confirm_step = tracker.observe(
        _frame(1, 300), (_animal(_frame(1, 300), left_box, score=0.85), _animal(_frame(1, 300), right_box, score=0.85)),
    )
    left_gen = next(u.generation_id for u in confirm_step.updates if u.bounding_box == left_box)
    right_gen = next(u.generation_id for u in confirm_step.updates if u.bounding_box == right_box)
    assert left_gen != right_gen

    # Both dip below strong threshold independently, on a gap outside the
    # ordinary tight bound but inside the widened one.
    dip_frame = _frame(2, 2200)
    step = tracker.observe(
        dip_frame, (_animal(dip_frame, left_box, score=0.2), _animal(dip_frame, right_box, score=0.25)),
    )
    dip_generations = {u.generation_id for u in step.updates if u.status == "updated"}
    assert dip_generations == {left_gen, right_gen}
    assert tracker.active_count == 2


def test_crossing_subjects_remain_separate() -> None:
    """Scenario 18: two subjects on a converging path (each frame-to-frame
    step small enough for the existing motion-prediction association gate
    to follow its own subject, one step carrying a weak-scored detection)
    stay distinguishable and never merge into one generation, right up to
    -- but not through -- the point where they would become genuinely
    ambiguous (that exact edge case is its own dedicated test above)."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
    left0, right0 = (0.02, 0.4, 0.18, 0.6), (0.82, 0.4, 0.98, 0.6)
    left1, right1 = (0.12, 0.4, 0.28, 0.6), (0.72, 0.4, 0.88, 0.6)
    tracker.observe(_frame(0, 0), (_animal(_frame(0, 0), left0, score=0.8), _animal(_frame(0, 0), right0, score=0.8)))
    confirm_step = tracker.observe(
        _frame(1, 300), (_animal(_frame(1, 300), left1, score=0.85), _animal(_frame(1, 300), right1, score=0.85)),
    )
    left_gen = next(u.generation_id for u in confirm_step.updates if u.bounding_box == left1)
    right_gen = next(u.generation_id for u in confirm_step.updates if u.bounding_box == right1)
    assert left_gen != right_gen

    # Each subject keeps closing the gap by the same 0.10 step its own
    # velocity already predicts -- association follows the moving subject,
    # not just its starting point. One side is weak this step.
    left2, right2 = (0.22, 0.4, 0.38, 0.6), (0.62, 0.4, 0.78, 0.6)
    step2 = tracker.observe(
        _frame(2, 600), (_animal(_frame(2, 600), left2, score=0.85), _animal(_frame(2, 600), right2, score=0.3)),
    )
    assert {u.generation_id for u in step2.updates} == {left_gen, right_gen}
    assert tracker.active_count == 2

    left3, right3 = (0.32, 0.4, 0.48, 0.6), (0.52, 0.4, 0.68, 0.6)
    step3 = tracker.observe(
        _frame(3, 900), (_animal(_frame(3, 900), left3, score=0.85), _animal(_frame(3, 900), right3, score=0.85)),
    )
    assert {u.generation_id for u in step3.updates} == {left_gen, right_gen}
    left_final = next(u for u in step3.updates if u.generation_id == left_gen)
    right_final = next(u for u in step3.updates if u.generation_id == right_gen)
    assert left_final.bounding_box == left3
    assert right_final.bounding_box == right3
    assert tracker.active_count == 2


def test_episode_ids_remain_deterministic() -> None:
    """Scenario 21: running the identical evidence sequence through two
    fresh trackers produces identical generation ids -- Stage 6.16 adds no
    non-deterministic input (wall-clock, randomness) to id derivation."""
    box = (0.4, 0.4, 0.6, 0.6)
    schedule = [(0, 0.8), (300, 0.85), (2600, 0.2), (5000, 0.86)]

    def run() -> list[str]:
        tracker = ProviderNeutralFrameTracker("stream", _stage616_config())
        generations: list[str] = []
        for index, (offset, score) in enumerate(schedule):
            frame = _frame(index, offset)
            step = tracker.observe(frame, (_animal(frame, box, score=score),))
            generations.extend(u.generation_id for u in step.updates)
        return generations

    assert run() == run()
