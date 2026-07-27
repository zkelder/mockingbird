from datetime import UTC, datetime, timedelta
import threading
from types import SimpleNamespace

import numpy as np

from mockingbird.api.main import _tracked_activity_evidence_payload
from mockingbird.motion.tracked_activity import (
    TrackedOutdoorActivityDetector,
    TrackedZone,
)
from mockingbird.playback.live_camera_session import _LiveActivitySession, _LiveCameraSession


FRAME_HEIGHT = 360
FRAME_WIDTH = 640


def _frame(*, left: int | None = None, top: int = 160, size: int = 12) -> np.ndarray:
    image = np.zeros((FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint8)
    if left is not None:
        image[top : top + size, left : left + size] = 255
    return image


def _zone(*, blocked: bool = False) -> TrackedZone:
    return TrackedZone(
        "blocked" if blocked else "feeder",
        "privacy" if blocked else "feeder",
        ((0.1, 0.2), (0.9, 0.2), (0.9, 0.8), (0.1, 0.8)),
        blocked=blocked,
    )


def _observe(
    detector: TrackedOutdoorActivityDetector,
    frame: np.ndarray,
    index: int,
    *,
    zones: tuple[TrackedZone, ...],
):
    captured_at = datetime(2026, 7, 25, tzinfo=UTC) + timedelta(milliseconds=index * 200)
    return detector.observe(
        frame,
        sequence=index + 1,
        captured_at=captured_at,
        source_width=1920,
        source_height=1080,
        frame_identity=f"frame-{index}",
        zones=zones,
        now=captured_at,
    )


def test_compact_feeder_region_triggers_after_two_coherent_hits() -> None:
    detector = TrackedOutdoorActivityDetector("stream-one", preset="high_sensitivity")
    zones = (_zone(),)

    _observe(detector, _frame(), 0, zones=zones)
    _observe(detector, _frame(), 1, zones=zones)
    first = _observe(detector, _frame(left=200), 2, zones=zones)
    second = _observe(detector, _frame(left=203), 3, zones=zones)

    assert first.regions
    assert second.triggers
    assert second.triggers[0].reason == "coherent_track"
    assert second.triggers[0].pretrigger_frame_identities
    assert second.tracks[0].hit_count == 2
    region = second.regions[0]
    assert 0.1 <= region.left < region.right <= 0.9
    assert region.pixel_area >= 8



def test_mog2_trigger_telemetry_has_no_object_generation_requirement() -> None:
    detector = TrackedOutdoorActivityDetector("stream-mog2", preset="high_sensitivity")
    zones = (_zone(),)

    _observe(detector, _frame(), 0, zones=zones)
    _observe(detector, _frame(), 1, zones=zones)
    _observe(detector, _frame(left=200), 2, zones=zones)
    result = _observe(detector, _frame(left=203), 3, zones=zones)

    payload = _tracked_activity_evidence_payload(result)

    assert payload["triggers"][0]["track_id"] == result.triggers[0].track_id
    assert "track_generation_id" not in payload["triggers"][0]

def test_duplicate_and_global_illumination_frames_are_not_activity() -> None:
    detector = TrackedOutdoorActivityDetector("stream-two")
    zones = (_zone(),)
    _observe(detector, _frame(), 0, zones=zones)
    _observe(detector, _frame(), 1, zones=zones)

    duplicate = detector.observe(
        _frame(),
        sequence=3,
        captured_at=datetime(2026, 7, 25, tzinfo=UTC) + timedelta(milliseconds=400),
        source_width=1920,
        source_height=1080,
        frame_identity="frame-1",
        zones=zones,
    )
    lighting = _observe(detector, np.full((FRAME_HEIGHT, FRAME_WIDTH), 255, dtype=np.uint8), 3, zones=zones)

    assert duplicate.telemetry.ignored_reason == "duplicate_frame"
    assert duplicate.telemetry.duplicate_frame_count == 1
    assert not duplicate.triggers
    assert lighting.global_illumination_suppressed is True
    assert not lighting.regions


def test_privacy_zone_excludes_foreground_before_tracking() -> None:
    detector = TrackedOutdoorActivityDetector("stream-three", preset="high_sensitivity")
    blocked = (_zone(blocked=True),)

    _observe(detector, _frame(), 0, zones=blocked)
    _observe(detector, _frame(), 1, zones=blocked)
    result = _observe(detector, _frame(left=200), 2, zones=blocked)

    assert not result.regions
    assert not result.tracks
    assert not result.triggers


def test_zone_first_detector_maps_local_regions_back_to_source_coordinates() -> None:
    detector = TrackedOutdoorActivityDetector("stream-zone-first", preset="high_sensitivity")
    zone = TrackedZone(
        "feeder",
        "feeder",
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
    )
    coordinate_box = (0.2, 0.25, 0.6, 0.75)
    started = datetime(2026, 7, 25, tzinfo=UTC)
    for index, left in enumerate((None, None, 200)):
        result = detector.observe(
            _frame(left=left),
            sequence=index + 1,
            captured_at=started + timedelta(milliseconds=index * 200),
            source_width=1920,
            source_height=1080,
            frame_identity=f"zone-first-{index}",
            zones=(zone,),
            coordinate_box=coordinate_box,
        )

    assert result.regions
    region = result.regions[0]
    assert 0.32 <= region.left <= 0.34
    assert 0.33 <= region.right <= 0.35
    assert 0.46 <= region.top <= 0.49
    assert 0.49 <= region.bottom <= 0.52


def test_triggered_track_becomes_stationary_before_it_disappears() -> None:
    detector = TrackedOutdoorActivityDetector("stream-four", preset="high_sensitivity")
    zones = (_zone(),)
    _observe(detector, _frame(), 0, zones=zones)
    _observe(detector, _frame(), 1, zones=zones)
    _observe(detector, _frame(left=200), 2, zones=zones)
    triggered = _observe(detector, _frame(left=203), 3, zones=zones)
    assert triggered.triggers

    stationary = _observe(detector, _frame(), 4, zones=zones)

    assert stationary.tracks[0].state == "stationary"
    assert stationary.tracks[0].triggered is True


def test_activity_session_keeps_pretrigger_frames_bounded_until_review() -> None:
    started_at = datetime(2026, 7, 25, tzinfo=UTC)
    session = _LiveActivitySession.from_detection(
        {
            "zone_id": "feeder",
            "zone_name": "Feeder",
            "zone_type": "feeder",
            "best_score": 1.0,
            "best_frame_sequence": 3,
            "best_frame_captured_at": started_at + timedelta(milliseconds=400),
            "best_frame_width": 1920,
            "best_frame_height": 1080,
        },
        stream_id="stream-five",
        source_id="source-five",
        region_key="zone:feeder",
        now=started_at + timedelta(milliseconds=400),
        frame_bytes=b"entry-frame",
        frame_content_type="image/jpeg",
    )

    session.record_pretrigger_frames(
        [
            {
                "sequence": 1,
                "captured_at": started_at,
                "frame_bytes": b"before-first-motion",
                "content_type": "image/jpeg",
                "width": 1920,
                "height": 1080,
            },
            {
                "sequence": 2,
                "captured_at": started_at + timedelta(milliseconds=200),
                "frame_bytes": b"entry-context",
                "content_type": "image/jpeg",
                "width": 1920,
                "height": 1080,
            },
            {
                "sequence": 99,
                "captured_at": started_at + timedelta(milliseconds=300),
                "frame_bytes": b"must-not-be-retained",
                "content_type": "image/jpeg",
            },
        ]
    )

    evidence = session.evidence_frames(max_frames=4)

    assert len(evidence) == 3
    assert sum(frame.is_primary for frame in evidence) == 1
    assert [frame.sequence for frame in evidence] == [1, 2, 3]
    assert all(frame.width == 1920 for frame in evidence)
    assert all(frame.height == 1080 for frame in evidence)


def test_distinct_track_generations_own_independent_capture_claims() -> None:
    """A bird cannot inherit the false-positive track's capture or its failure state."""

    started_at = datetime(2026, 7, 25, tzinfo=UTC)

    def activity(generation: str, offset: int) -> _LiveActivitySession:
        return _LiveActivitySession.from_detection(
            {
                "zone_id": "feeder",
                "zone_name": "Feeder",
                "zone_type": "feeder",
                "track_generation_id": generation,
                "best_score": 0.8,
                "best_frame_sequence": offset,
                "best_frame_captured_at": started_at + timedelta(seconds=offset),
                "best_frame_width": 1920,
                "best_frame_height": 1440,
            },
            stream_id="stream-capture-claims",
            source_id="source-capture-claims",
            region_key=f"zone:feeder|track:{generation}",
            now=started_at + timedelta(seconds=offset),
            frame_bytes=b"monitoring-frame",
            frame_content_type="image/jpeg",
        )

    false_positive = activity("generation-false", 1)
    bird = activity("generation-bird", 2)
    session = object.__new__(_LiveCameraSession)
    session.stream_id = "stream-capture-claims"
    session._lock = threading.RLock()
    session.activity_sessions = {
        false_positive.region_key: false_positive,
        bird.region_key: bird,
    }
    session.current_activity_session_id = false_positive.activity_session_id
    session.track_capture_claims = {}
    session.last_activity = None

    def claim_values(generation: str, frame: str) -> dict[str, object]:
        return {
            "zone_id": "feeder",
            "track_generation_id": generation,
            "qualifying_frame_identity": frame,
            "detector_name": "megadetector",
            "detector_class": "animal",
            "detector_score": 0.875,
            "normalized_track_box": [0.2, 0.3, 0.4, 0.5],
            "monitoring_width": 1920,
            "monitoring_height": 1440,
            "zone_geometry": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
            "alignment_group_id": "same-fov",
            "monitoring_profile_id": "monitoring-1920x1440",
            "evidence_profile_id": "evidence-4624x3472",
            "monitoring_geometry_group_id": "same-fov",
            "evidence_profile_width": 4624,
            "evidence_profile_height": 3472,
            "claim_timestamp": started_at,
        }

    false_claim = session.claim_activity_high_resolution_capture(
        false_positive.activity_session_id,
        claim_values("generation-false", "false-frame"),
    )
    assert false_claim is not None
    assert false_claim["status"] == "requested"
    assert (
        session.claim_activity_high_resolution_capture(
            false_positive.activity_session_id,
            claim_values("generation-false", "false-frame"),
        )
        is None
    )
    completed_false = session.complete_activity_high_resolution_capture(
        false_positive.activity_session_id,
        str(false_claim["capture_claim_id"]),
        {"track_generation_id": "generation-false", "full_image": b"false-jpeg"},
    )
    assert completed_false is not None
    assert completed_false.high_resolution_capture_claim["status"] == "succeeded"
    assert (
        completed_false.high_resolution_capture_claim["monitoring_profile_id"]
        == "monitoring-1920x1440"
    )
    assert (
        completed_false.high_resolution_capture_claim["evidence_profile_id"]
        == "evidence-4624x3472"
    )
    assert (
        completed_false.high_resolution_capture_claim["monitoring_geometry_group_id"]
        == "same-fov"
    )

    bird_claim = session.claim_activity_high_resolution_capture(
        bird.activity_session_id,
        claim_values("generation-bird", "bird-frame"),
    )
    assert bird_claim is not None
    assert bird_claim["capture_claim_id"] != false_claim["capture_claim_id"]
    completed_bird = session.complete_activity_high_resolution_capture(
        bird.activity_session_id,
        str(bird_claim["capture_claim_id"]),
        {"track_generation_id": "generation-bird", "full_image": b"bird-jpeg"},
    )
    assert completed_bird is not None
    assert completed_bird.high_resolution_capture_claim["status"] == "succeeded"
    assert completed_bird.high_resolution_evidence["full_image_present"] is True
    assert completed_bird.high_resolution_evidence["full_image_size_bytes"] == len(b"bird-jpeg")

    stale = session.complete_activity_high_resolution_capture(
        false_positive.activity_session_id,
        str(bird_claim["capture_claim_id"]),
        {"track_generation_id": "generation-bird", "full_image": b"late-jpeg"},
    )
    assert stale is not None
    assert stale.high_resolution_capture_claim["status"] == "succeeded"
    assert bird.high_resolution_evidence["full_image"] == b"bird-jpeg"
    assert false_positive.high_resolution_evidence["full_image"] == b"false-jpeg"


def test_failed_claim_and_current_detector_support_do_not_create_a_capture_loop() -> None:
    now = datetime.now(UTC)
    activity = _LiveActivitySession.from_detection(
        {
            "zone_id": "feeder",
            "zone_name": "Feeder",
            "zone_type": "feeder",
            "track_generation_id": "generation-failed",
            "best_score": 0.8,
            "best_frame_sequence": 3,
            "best_frame_captured_at": now - timedelta(seconds=60),
            "best_frame_width": 1920,
            "best_frame_height": 1440,
        },
        stream_id="stream-support",
        source_id="source-support",
        region_key="zone:feeder|track:generation-failed",
        now=now - timedelta(seconds=60),
        frame_bytes=b"monitoring-frame",
        frame_content_type="image/jpeg",
    )
    session = object.__new__(_LiveCameraSession)
    session.stream_id = "stream-support"
    session._lock = threading.RLock()
    session.activity_sessions = {activity.region_key: activity}
    session.current_activity_session_id = activity.activity_session_id
    session.track_capture_claims = {}
    session.last_activity = None

    claim = session.claim_activity_high_resolution_capture(
        activity.activity_session_id,
        {
            "zone_id": "feeder",
            "track_generation_id": "generation-failed",
            "qualifying_frame_identity": "frame-3",
            "detector_name": "megadetector",
            "detector_class": "animal",
            "detector_score": 0.8,
            "normalized_track_box": [0.2, 0.3, 0.4, 0.5],
            "monitoring_width": 1920,
            "monitoring_height": 1440,
            "zone_geometry": [],
            "alignment_group_id": "same-fov",
        },
    )
    assert claim is not None
    failed = session.complete_activity_high_resolution_capture(
        activity.activity_session_id,
        str(claim["capture_claim_id"]),
        {
            "track_generation_id": "generation-failed",
            "capture_failure_code": "node_unavailable",
        },
    )
    assert failed is not None
    assert failed.high_resolution_capture_claim["status"] == "failed"
    assert failed.high_resolution_evidence["full_image_present"] is False
    assert (
        session.claim_activity_high_resolution_capture(
            activity.activity_session_id,
            {**claim, "track_generation_id": "generation-failed"},
        )
        is None
    )

    supported = session.record_activity_track_support(
        "generation-failed",
        observed_at=now,
        detector_evidence={"object_detector": {"current": True}},
    )
    assert supported is not None
    assert supported.last_seen_at == now
    assert session.mark_quiet_activity_sessions_ready_for_review(quiet_seconds=5) == []


def test_near_miss_cannot_preempt_an_open_confirmed_track_session() -> None:
    started_at = datetime(2026, 7, 27, tzinfo=UTC)
    session = _LiveCameraSession(
        config=SimpleNamespace(
            stream_id="stream-confirmed-track",
            source_id="source-confirmed-track",
            live_stream_type="camera_node",
        ),
        process=SimpleNamespace(),
        max_runtime_seconds=300,
    )
    confirmed = session.record_activity_detection(
        {
            "region_key": "zone:feeder|object-track:generation-001",
            "zone_id": "feeder",
            "zone_name": "Feeder",
            "zone_type": "feeder",
            "track_generation_id": "generation-001",
            "activity_detected": True,
            "best_score": 0.9,
            "best_frame_sequence": 4,
            "best_frame_captured_at": started_at,
            "last_seen_at": started_at,
        },
        frame_bytes=b"confirmed-track-frame",
        frame_content_type="image/jpeg",
        quiet_window_seconds=30,
    )
    near_miss = session.record_activity_detection(
        {
            "region_key": "zone:feeder",
            "zone_id": "feeder",
            "zone_name": "Feeder",
            "zone_type": "feeder",
            "activity_detected": False,
            "near_miss": True,
            "best_score": 0.1,
            "best_frame_sequence": 5,
            "best_frame_captured_at": started_at + timedelta(seconds=1),
            "last_seen_at": started_at + timedelta(seconds=1),
        },
        frame_bytes=b"near-miss-frame",
        frame_content_type="image/jpeg",
        quiet_window_seconds=30,
    )

    assert near_miss.detection_count == 0
    assert session.current_activity_session_id == confirmed.activity_session_id
    assert session.last_activity is not None
    assert session.last_activity["activity_session_id"] == confirmed.activity_session_id
