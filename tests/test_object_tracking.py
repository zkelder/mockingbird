from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event
from time import sleep


from mockingbird.detectors.megadetector_adapter import MegaDetectorBox, MegaDetectorProposal
from mockingbird.motion.object_tracking import LiveObjectDetectorManager
from mockingbird.motion import object_tracking


STARTED_AT = datetime(2026, 7, 26, tzinfo=UTC)


def _proposal(
    label: str = "animal", score: float = 0.8, box: MegaDetectorBox | None = None
) -> MegaDetectorProposal:
    return MegaDetectorProposal(
        label=label,
        confidence=score,
        bbox=box or MegaDetectorBox(x=0.3, y=0.4, width=0.1, height=0.1),
    )


def _isolated_timeout_runner(
    image: bytes, coordinate_box: MegaDetectorBox
) -> list[MegaDetectorProposal]:
    del coordinate_box
    if image == b"hung-crop":
        sleep(5)
    return [_proposal()]

def _isolated_timing_runner(
    image: bytes, coordinate_box: MegaDetectorBox
) -> list[MegaDetectorProposal]:
    del coordinate_box
    sleep(0.08 if image in {b"initial-load", b"steady-inference"} else 0)
    return [_proposal()]


def _submit(
    manager: LiveObjectDetectorManager,
    *,
    sequence: int,
    zone_id: str = "zone-feeder",
    zone_type: str = "feeder",
    captured_at: datetime = STARTED_AT,
    image: bytes = b"bounded-zone-jpeg",
    frame_identity: str | None = None,
) -> None:
    manager.submit(
        stream_id="stream-yard",
        zone_id=zone_id,
        zone_type=zone_type,
        frame_identity=frame_identity or f"frame-{sequence}",
        sequence=sequence,
        captured_at=captured_at,
        coordinate_box=(0.2, 0.25, 0.8, 0.9),
        image=image,
    )


def _completed(
    manager: LiveObjectDetectorManager,
    sequence: int = 1,
    frame_identity: str | None = None,
):
    expected_frame_identity = frame_identity or f"frame-{sequence}"
    for _ in range(100):
        snapshot = manager.poll("stream-yard")
        if snapshot.completed_frame_identity == expected_frame_identity:
            return snapshot
        sleep(0.01)
    raise AssertionError("object inference did not complete")


def test_admission_observability_records_no_animal_and_bounds_recent_outcomes() -> None:
    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(runner=lambda _image, _box: [], now=lambda: current[0])
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        snapshot = _completed(manager)

        assert snapshot.admission_counters["inferences_completed"] == 1
        assert snapshot.admission_counters["inferences_without_animal"] == 1
        assert [outcome["reason"] for outcome in snapshot.recent_admission_outcomes] == [
            "no_animal_detection"
        ]
        assert snapshot.admission_observability_available is True
    finally:
        manager.shutdown()


def test_feeder_animal_track_requires_two_distinct_frames_without_motion_input() -> None:
    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal()], now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        first = _completed(manager)

        assert len(first.detections) == 1
        assert first.detections[0].label == "animal"
        assert first.detections[0].box == (0.3, 0.4, 0.4, 0.5)
        assert not first.triggers

        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, captured_at=current[0])
        second = _completed(manager, 2)
        assert second.triggers[0].track_id == "object-track-0001"
        assert second.triggers[0].label == "animal"
        assert second.triggers[0].score == 0.8
    finally:
        manager.shutdown()


def test_whole_stream_animal_track_triggers_without_zone_or_motion_crop() -> None:
    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal()], now=lambda: current[0]
    )
    try:
        _submit(
            manager,
            sequence=1,
            zone_id="whole-stream",
            zone_type="whole_stream",
            captured_at=current[0],
            image=b"masked-1920x1440-monitoring-frame",
        )
        first = _completed(manager)
        current[0] += timedelta(seconds=2)
        _submit(
            manager,
            sequence=2,
            zone_id="whole-stream",
            zone_type="whole_stream",
            captured_at=current[0],
            image=b"masked-1920x1440-monitoring-frame-2",
        )
        snapshot = _completed(manager, 2)

        assert snapshot.cadence_seconds == 1.5
        assert first.detections[0].label == "animal"
        assert snapshot.detections[0].zone_id == "whole-stream"
        assert snapshot.triggers[0].zone_id == "whole-stream"
    finally:
        manager.shutdown()


def test_two_weak_animal_observations_trigger_and_then_remain_stationary() -> None:
    current = [STARTED_AT]
    answers = [
        [_proposal(score=0.30)],
        [_proposal(score=0.31, box=MegaDetectorBox(0.31, 0.4, 0.1, 0.1))],
        [],
    ]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: answers.pop(0), now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        first = _completed(manager, 1)
        assert not first.triggers

        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, captured_at=current[0])
        second = _completed(manager, 2)
        assert second.triggers[0].track_id == "object-track-0001"
        assert second.tracks[0].hit_count == 2

        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=3, captured_at=current[0])
        stationary = _completed(manager, 3)
        assert stationary.tracks[0].state == "stationary"
        assert stationary.tracks[0].triggered is True
    finally:
        manager.shutdown()



def test_repeated_cached_frame_does_not_count_as_animal_confirmation() -> None:
    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal(score=0.91)], now=lambda: current[0]
    )
    try:
        _submit(
            manager,
            sequence=1,
            captured_at=current[0],
            frame_identity="same-monitoring-frame",
        )
        first = _completed(manager, frame_identity="same-monitoring-frame")
        assert not first.triggers

        current[0] += timedelta(seconds=1)
        _submit(
            manager,
            sequence=2,
            captured_at=current[0],
            frame_identity="same-monitoring-frame",
        )
        repeated = _completed(manager, 2, frame_identity="same-monitoring-frame")
        assert not repeated.triggers
        assert repeated.tracks[0].hit_count == 1
    finally:
        manager.shutdown()


def test_spatially_incoherent_animal_observations_do_not_form_one_admitted_track() -> None:
    current = [STARTED_AT]
    answers = [
        [_proposal(box=MegaDetectorBox(0.10, 0.10, 0.05, 0.05))],
        [_proposal(box=MegaDetectorBox(0.75, 0.75, 0.05, 0.05))],
    ]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: answers.pop(0), now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        assert not _completed(manager).triggers
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, captured_at=current[0])
        second = _completed(manager, 2)
        assert not second.triggers
        assert sorted(track.hit_count for track in second.tracks) == [1, 1]
    finally:
        manager.shutdown()


def test_brief_fast_small_bird_is_admitted_with_two_coherent_fresh_frames() -> None:
    current = [STARTED_AT]
    answers = [
        [_proposal(score=0.22, box=MegaDetectorBox(0.30, 0.40, 0.03, 0.03))],
        [_proposal(score=0.24, box=MegaDetectorBox(0.38, 0.41, 0.03, 0.03))],
    ]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: answers.pop(0), now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        assert not _completed(manager).triggers
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, captured_at=current[0])
        admitted = _completed(manager, 2)
        assert admitted.triggers[0].label == "animal"
        assert admitted.triggers[0].score == 0.24
        assert admitted.tracks[0].hit_count == 2
    finally:
        manager.shutdown()


def test_admission_target_replay_rejects_single_frame_false_positives() -> None:
    """Exercise the field gate shape without placing field media in the repo."""

    current = [STARTED_AT]
    visible_scores = [0.208, 0.255, 0.317, 0.385, 0.457, 0.513, 0.56, 0.585,
                      0.588, 0.612, 0.631, 0.672, 0.744]
    false_positive_scores = [0.297, 0.597, 0.598, 0.643, 0.662,
                             0.673, 0.691, 0.72, 0.763, 0.805]
    answers = iter(
        [
            _proposal(score=score, box=MegaDetectorBox(0.30, 0.40, 0.04, 0.04))
            for score in visible_scores
            for _ in range(2)
        ]
        + [
            _proposal(score=score, box=MegaDetectorBox(0.70, 0.70, 0.04, 0.04))
            for score in false_positive_scores
        ]
        + [None]
    )

    def replay_runner(_image, _box):
        proposal = next(answers)
        return [] if proposal is None else [proposal]

    manager = LiveObjectDetectorManager(runner=replay_runner, now=lambda: current[0])
    admitted_visible = 0
    admitted_false_positives = 0
    try:
        sequence = 0
        for index in range(len(visible_scores)):
            zone_id = f"replay-visible-{index}"
            sequence += 1
            _submit(manager, sequence=sequence, zone_id=zone_id, captured_at=current[0])
            assert not _completed(manager, sequence).triggers
            current[0] += timedelta(seconds=1)
            sequence += 1
            _submit(manager, sequence=sequence, zone_id=zone_id, captured_at=current[0])
            admitted_visible += len(_completed(manager, sequence).triggers)
            current[0] += timedelta(seconds=1)

        for index in range(len(false_positive_scores)):
            sequence += 1
            _submit(
                manager,
                sequence=sequence,
                zone_id=f"replay-false-positive-{index}",
                captured_at=current[0],
            )
            admitted_false_positives += len(_completed(manager, sequence).triggers)
            current[0] += timedelta(seconds=1)

        # One completed empty inference closes the final one-frame modeled false
        # candidate without creating a product record.
        sequence += 1
        _submit(
            manager,
            sequence=sequence,
            zone_id="replay-empty",
            captured_at=current[0],
        )
        replay = _completed(manager, sequence)

        retained_visible = admitted_visible
        rejected_false_positives = len(false_positive_scores) - admitted_false_positives
        precision = retained_visible / (retained_visible + admitted_false_positives)
        reasons = [item["reason"] for item in replay.recent_admission_outcomes]
        assert retained_visible == 13
        assert rejected_false_positives == 10
        assert precision == 1.0
        assert replay.admission_counters["admissions_satisfied"] == 13
        assert replay.admission_counters["single_frame_candidates_expired"] == 10
        assert reasons.count("admission_satisfied") == 13
        assert reasons.count("single_frame_candidate_expired") == 10
        assert not replay.current_admission_candidates
    finally:
        manager.shutdown()


def test_feeder_rejects_person_but_driveway_keeps_outdoor_context() -> None:
    answers = [[_proposal(label="person")], [_proposal(label="vehicle")]]
    manager = LiveObjectDetectorManager(runner=lambda _image, _box: answers.pop(0))
    try:
        _submit(manager, sequence=1, zone_type="feeder")
        feeder = _completed(manager, 1)
        assert not feeder.detections
        assert not feeder.triggers

        _submit(manager, sequence=2, zone_id="zone-driveway", zone_type="driveway")
        driveway = _completed(manager, 2)
        assert driveway.detections[0].label == "vehicle"
        assert driveway.triggers[0].label == "vehicle"
    finally:
        manager.shutdown()


def test_yard_does_not_treat_a_vehicle_as_a_wildlife_activity_trigger() -> None:
    manager = LiveObjectDetectorManager(runner=lambda _image, _box: [_proposal(label="vehicle")])
    try:
        _submit(manager, sequence=1, zone_type="yard")
        snapshot = _completed(manager, 1)
        assert not snapshot.detections
        assert not snapshot.triggers
    finally:
        manager.shutdown()


def test_queue_replaces_waiting_frame_and_stale_sequence_is_dropped() -> None:
    current = [STARTED_AT]
    entered = Event()
    release = Event()

    def slow_runner(_image: bytes, _box: MegaDetectorBox):
        entered.set()
        assert release.wait(timeout=2)
        return []

    manager = LiveObjectDetectorManager(runner=slow_runner, now=lambda: current[0])
    try:
        _submit(manager, sequence=1, zone_id="zone-one", captured_at=current[0])
        assert entered.wait(timeout=1)
        current[0] += timedelta(seconds=3)
        _submit(manager, sequence=2, zone_id="zone-two", zone_type="driveway", captured_at=current[0])
        current[0] += timedelta(seconds=3)
        _submit(manager, sequence=3, zone_id="zone-three", zone_type="yard", captured_at=current[0])
        # Same Zone and sequence is stale even while a different Zone is active.
        _submit(manager, sequence=3, zone_id="zone-three", zone_type="yard", captured_at=current[0])
        queued = manager.poll("stream-yard")
        assert queued.queue_depth == 1
        assert queued.dropped_frame_count == 1
        assert queued.stale_frame_count == 1
        release.set()
    finally:
        release.set()
        manager.shutdown()


def test_runtime_failure_is_reported_without_throwing_from_monitor_submit() -> None:
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: (_ for _ in ()).throw(RuntimeError("offline"))
    )
    try:
        _submit(manager, sequence=1)
        snapshot = _completed(manager)
        assert snapshot.unavailable_reason == "megadetector_unavailable"
        assert not snapshot.detections
        assert not snapshot.triggers
    finally:
        manager.shutdown()


def test_timed_out_native_runtime_drops_the_late_result_and_recovers_fresh_work(
    monkeypatch,
) -> None:
    """A hung native call must not permanently occupy live inference."""

    monkeypatch.setattr(object_tracking, "INFERENCE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(object_tracking, "INITIAL_RUNTIME_LOAD_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(object_tracking, "RUNTIME_RECOVERY_BACKOFF_SECONDS", 0.0)
    manager = LiveObjectDetectorManager(isolated_runner=_isolated_timeout_runner)
    try:
        _submit(manager, sequence=1, image=b"hung-crop")
        for _ in range(200):
            if manager._active is not None:
                break
            sleep(0.01)
        assert manager._active is not None

        sleep(0.08)
        timed_out = manager.poll("stream-yard")
        assert timed_out.unavailable_reason == "inference_timeout"
        assert timed_out.runtime_state in {"timed_out", "recovering"}
        assert timed_out.last_safe_error_category == "inference_timeout"
        assert timed_out.recovery_count == 1

        _submit(manager, sequence=2, zone_id="zone-fresh", image=b"fresh-crop")
        recovered = None
        for _ in range(300):
            snapshot = manager.poll("stream-yard")
            if snapshot.completed_frame_identity == "frame-2":
                recovered = snapshot
                break
            sleep(0.01)

        assert recovered is not None
        assert recovered.detections[0].frame_identity == "frame-2"
        assert recovered.timed_out_count == 1
        assert recovered.stale_frame_count >= 1
        assert recovered.runtime_state == "ready"
        assert recovered.recovery_count == 1
        assert recovered.worker_reset_count == 1
    finally:
        manager.shutdown()



def test_shutdown_releases_active_generation_work_before_returning(monkeypatch) -> None:
    monkeypatch.setattr(object_tracking, "INFERENCE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(object_tracking, "INITIAL_RUNTIME_LOAD_TIMEOUT_SECONDS", 0.05)
    manager = LiveObjectDetectorManager(isolated_runner=_isolated_timeout_runner)
    _submit(manager, sequence=1, image=b"hung-crop")
    for _ in range(200):
        if manager._active is not None:
            break
        sleep(0.01)
    assert manager._active is not None

    manager.shutdown()

    assert manager._runtime_process is None
    assert manager._runtime_connection is None
    assert manager._active is None
    assert not manager._queue
    assert not manager._completed
    assert not manager._expired_jobs
    assert not manager._states
    assert not manager._worker.is_alive()


def test_initial_model_load_allowance_is_separate_from_steady_inference_deadline(
    monkeypatch,
) -> None:
    monkeypatch.setattr(object_tracking, "INITIAL_RUNTIME_LOAD_TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(object_tracking, "INFERENCE_TIMEOUT_SECONDS", 0.04)
    monkeypatch.setattr(object_tracking, "RUNTIME_RECOVERY_BACKOFF_SECONDS", 0.0)
    manager = LiveObjectDetectorManager(isolated_runner=_isolated_timing_runner)
    try:
        _submit(manager, sequence=1, image=b"initial-load")
        for _ in range(200):
            if manager._active is not None:
                break
            sleep(0.01)
        assert manager._active is not None
        loaded = _completed(manager)
        assert loaded.model_loaded is True
        assert loaded.inference_latency_ms is not None
        assert loaded.inference_latency_ms >= 50
        assert loaded.last_completed_at is not None
        assert loaded.latest_successful_inference_latency_ms is not None
        assert loaded.timed_out_count == 0

        _submit(
            manager,
            sequence=2,
            zone_id="zone-steady",
            image=b"steady-inference",
        )
        timed_out = None
        for _ in range(200):
            snapshot = manager.poll("stream-yard")
            if snapshot.unavailable_reason == "inference_timeout":
                timed_out = snapshot
                break
            sleep(0.01)

        assert timed_out is not None
        assert timed_out.timed_out_count == 1
    finally:
        manager.shutdown()


def test_slow_inference_within_the_deadline_completes_normally(monkeypatch) -> None:
    monkeypatch.setattr(object_tracking, "INFERENCE_TIMEOUT_SECONDS", 0.2)

    def slow_runner(_image: bytes, _box: MegaDetectorBox) -> list[MegaDetectorProposal]:
        sleep(0.05)
        return [_proposal()]

    manager = LiveObjectDetectorManager(runner=slow_runner)
    try:
        _submit(manager, sequence=1)
        completed = _completed(manager)
        assert completed.unavailable_reason is None
        assert completed.timed_out_count == 0
        assert completed.inference_latency_ms is not None
        assert 30 <= completed.inference_latency_ms < 200
    finally:
        manager.shutdown()


def test_late_thread_result_is_ignored_after_the_job_becomes_stale(monkeypatch) -> None:
    monkeypatch.setattr(object_tracking, "INFERENCE_TIMEOUT_SECONDS", 0.05)
    entered = Event()
    release = Event()

    def late_runner(_image: bytes, _box: MegaDetectorBox) -> list[MegaDetectorProposal]:
        entered.set()
        assert release.wait(timeout=2)
        return [_proposal()]

    manager = LiveObjectDetectorManager(runner=late_runner)
    try:
        _submit(manager, sequence=1)
        assert entered.wait(timeout=1)
        sleep(0.08)
        timed_out = manager.poll("stream-yard")
        assert timed_out.unavailable_reason == "inference_timeout"
        assert not timed_out.detections

        release.set()
        for _ in range(100):
            if manager._active is None:
                break
            sleep(0.01)
        late = manager.poll("stream-yard")
        assert late.completed_frame_identity == "frame-1"
        assert not late.detections
        assert not late.tracks
        assert not late.triggers
    finally:
        release.set()
        manager.shutdown()


def test_result_processing_failure_does_not_stop_later_monitoring(monkeypatch) -> None:
    manager = LiveObjectDetectorManager(runner=lambda _image, _box: [_proposal()])
    original_observations = object_tracking._observations_for_job

    def broken_observations(*_args, **_kwargs):
        raise RuntimeError("callback failed")

    try:
        monkeypatch.setattr(object_tracking, "_observations_for_job", broken_observations)
        _submit(manager, sequence=1)
        failed = _completed(manager)
        assert failed.unavailable_reason == "megadetector_unavailable"
        assert failed.last_safe_error_category == "result_processing_failed"

        monkeypatch.setattr(object_tracking, "_observations_for_job", original_observations)
        _submit(manager, sequence=2, zone_id="zone-recovered")
        recovered = _completed(manager, 2)
        assert recovered.detections[0].frame_identity == "frame-2"
        assert recovered.runtime_state == "ready"
        assert recovered.last_safe_error_category is None
    finally:
        manager.shutdown()


def test_normalized_detector_box_stays_in_full_frame_coordinates() -> None:
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [
            _proposal(box=MegaDetectorBox(0.26, 0.38, 0.12, 0.10))
        ]
    )
    try:
        _submit(manager, sequence=1)
        snapshot = _completed(manager)
        detection = snapshot.detections[0]
        assert detection.box == (0.26, 0.38, 0.38, 0.48)
        assert all(0 <= value <= 1 for value in detection.box)
    finally:
        manager.shutdown()


def test_reused_numeric_track_id_has_a_distinct_generation_identity() -> None:
    """A restarted detector must not let an old capture satisfy a new track."""

    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal()], now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        _completed(manager, 1)
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, captured_at=current[0])
        first = _completed(manager, 2).triggers[0]

        # A monitor/session reset intentionally restarts the human-readable
        # counter. Capture ownership must still distinguish the two lifetimes.
        manager.reset("stream-yard")
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=1, captured_at=current[0])
        _completed(manager, 1)
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, captured_at=current[0])
        second = _completed(manager, 2).triggers[0]

        assert first.track_id == second.track_id == "object-track-0001"
        assert first.track_generation_id != second.track_generation_id
    finally:
        manager.shutdown()



def test_process_restart_generates_a_new_capture_ownership_identity() -> None:
    current = [STARTED_AT]
    first_manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal()], now=lambda: current[0]
    )
    try:
        _submit(first_manager, sequence=1, captured_at=current[0])
        _completed(first_manager, 1)
        current[0] += timedelta(seconds=1)
        _submit(first_manager, sequence=2, captured_at=current[0])
        first = _completed(first_manager, 2).triggers[0]
    finally:
        first_manager.shutdown()

    second_manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal()], now=lambda: current[0]
    )
    try:
        current[0] += timedelta(seconds=1)
        _submit(second_manager, sequence=1, captured_at=current[0])
        _completed(second_manager, 1)
        current[0] += timedelta(seconds=1)
        _submit(second_manager, sequence=2, captured_at=current[0])
        second = _completed(second_manager, 2).triggers[0]

        assert first.track_id == second.track_id == "object-track-0001"
        assert first.track_generation_id != second.track_generation_id
    finally:
        second_manager.shutdown()


def test_old_generation_success_cannot_update_a_replacement_runtime() -> None:
    class ProcessStub:
        def is_alive(self) -> bool:
            return True

    class ConnectionStub:
        def __init__(self, manager) -> None:
            self.manager = manager
            self.received = 0

        def send(self, _message) -> None:
            return None

        def poll(self, _timeout) -> bool:
            return True

        def recv(self):
            self.received += 1
            if self.received == 1:
                return ("started",)
            self.manager._runtime_generation += 1
            self.manager._runtime_connection = object()
            return ("success", [_proposal()], "cpu")

    manager = LiveObjectDetectorManager(isolated_runner=_isolated_timing_runner)
    try:
        connection = ConnectionStub(manager)
        manager._runtime_process = ProcessStub()
        manager._runtime_connection = connection
        manager._runtime_generation = 1
        job = object_tracking._InferenceJob(
            stream_id="stream-yard", zone_id="zone-feeder", zone_type="feeder",
            frame_identity="old-frame", sequence=1, captured_at=STARTED_AT,
            submitted_at=STARTED_AT, coordinate_box=(0.2, 0.25, 0.8, 0.9),
            image=b"old-crop",
        )

        try:
            manager._run_isolated_runtime(job, lambda: None)
        except object_tracking._RuntimeInferenceFailure:
            pass
        else:
            raise AssertionError("stale generation result was accepted")

        assert manager._runtime_model_loaded is False
        assert manager._runtime_execution_device is None
    finally:
        manager._runtime_process = None
        manager._runtime_connection = None
        manager.shutdown()


def test_admission_observability_labels_duplicate_spatial_expiry_and_success() -> None:
    current = [STARTED_AT]
    answers = [
        [_proposal()],
        [_proposal()],
        [_proposal(box=MegaDetectorBox(0.10, 0.10, 0.05, 0.05))],
        [_proposal(box=MegaDetectorBox(0.75, 0.75, 0.05, 0.05))],
        [_proposal()],
        [_proposal()],
        [],
    ]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: answers.pop(0), now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, zone_id="zone-admit", captured_at=current[0])
        _completed(manager, 1)
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, zone_id="zone-admit", captured_at=current[0])
        admitted = _completed(manager, 2)
        assert admitted.admission_counters["valid_second_distinct_frames"] == 1
        assert admitted.admission_counters["admissions_satisfied"] == 1
        assert "admission_satisfied" in {
            item["reason"] for item in admitted.recent_admission_outcomes
        }

        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=3, zone_id="zone-far", captured_at=current[0])
        _completed(manager, 3)
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=4, zone_id="zone-far", captured_at=current[0])
        rejected = _completed(manager, 4)
        assert rejected.admission_counters["spatial_coherence_rejected"] == 1
        assert "spatial_coherence_rejected" in {
            item["reason"] for item in rejected.recent_admission_outcomes
        }

        current[0] += timedelta(seconds=1)
        _submit(
            manager,
            sequence=5,
            zone_id="zone-duplicate",
            captured_at=current[0],
            frame_identity="cached-frame",
        )
        _completed(manager, 5, frame_identity="cached-frame")
        current[0] += timedelta(seconds=1)
        _submit(
            manager,
            sequence=6,
            zone_id="zone-duplicate",
            captured_at=current[0],
            frame_identity="cached-frame",
        )
        expired = None
        for _ in range(100):
            snapshot = manager.poll("stream-yard")
            if snapshot.admission_counters["duplicate_frame_identities_ignored"] == 1:
                expired = snapshot
                break
            sleep(0.01)
        assert expired is not None
        reasons = [item["reason"] for item in expired.recent_admission_outcomes]
        assert expired.admission_counters["duplicate_frame_identities_ignored"] == 1
        assert "duplicate_frame_ignored" in reasons

        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=7, zone_id="zone-empty", captured_at=current[0])
        expired = _completed(manager, 7)
        reasons = [item["reason"] for item in expired.recent_admission_outcomes]
        assert "single_frame_candidate_expired" in reasons
        assert not expired.current_admission_candidates
    finally:
        manager.shutdown()


def test_admission_observability_records_durable_promotion_outcomes() -> None:
    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal()], now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        _completed(manager, 1)
        current[0] += timedelta(seconds=1)
        _submit(manager, sequence=2, captured_at=current[0])
        admitted = _completed(manager, 2)
        generation = admitted.triggers[0].track_generation_id

        manager.record_admission_promotion(
            stream_id="stream-yard",
            track_generation_id=generation,
            event_id="event-observable",
            visit_id="visit-observable",
        )
        manager.record_admission_promotion(
            stream_id="stream-yard",
            track_generation_id=generation,
            error_category="database_conflict with private path /tmp/secret",
        )
        snapshot = manager.poll("stream-yard")
        reasons = [item["reason"] for item in snapshot.recent_admission_outcomes]
        assert snapshot.admission_counters["durable_promotion_attempts"] == 2
        assert snapshot.admission_counters["successful_visit_promotions"] == 1
        assert snapshot.admission_counters["failed_promotion_attempts"] == 1
        assert reasons[-2:] == ["visit_promoted", "promotion_failed"]
        assert snapshot.last_successful_promotion_at is not None
        assert snapshot.recent_admission_outcomes[-1]["error_category"] == (
            "database_conflict_with_private_path__tmp_secret"
        )
    finally:
        manager.shutdown()


def test_admission_observability_records_stale_generation_and_reset_cleanup() -> None:
    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(
        runner=lambda _image, _box: [_proposal()], now=lambda: current[0]
    )
    try:
        _submit(manager, sequence=1, captured_at=current[0])
        _completed(manager, 1)
        state = manager._states["stream-yard"]
        state.admission.detector_generation = 1
        manager._runtime_generation = 1
        with manager._condition:
            manager._recover_isolated_runtime_locked(counts_as_timeout=False)
        reset = manager.poll("stream-yard")
        assert reset.admission_counters["reset_interrupted_candidates"] == 1
        assert [item["reason"] for item in reset.recent_admission_outcomes] == [
            "detector_reset_interrupted"
        ]
        assert not reset.current_admission_candidates

        job = object_tracking._InferenceJob(
            stream_id="stream-yard",
            zone_id="zone-feeder",
            zone_type="feeder",
            frame_identity="old-generation-frame",
            sequence=99,
            captured_at=current[0],
            submitted_at=current[0],
            coordinate_box=(0.2, 0.25, 0.8, 0.9),
            image=b"no-retained-bytes",
        )
        with manager._condition:
            manager._completed.append((job, None, 0, "stale_generation"))
        stale = manager.poll("stream-yard")
        assert stale.admission_counters["stale_generation_results_ignored"] == 1
        assert stale.recent_admission_outcomes[-1]["reason"] == "stale_generation_ignored"
    finally:
        manager.shutdown()


def test_admission_observability_ring_and_counter_bounds() -> None:
    current = [STARTED_AT]
    manager = LiveObjectDetectorManager(runner=lambda _image, _box: [], now=lambda: current[0])
    try:
        for sequence in range(1, object_tracking.MAX_ADMISSION_RECENT_OUTCOMES + 8):
            _submit(
                manager,
                sequence=sequence,
                zone_id=f"zone-{sequence}",
                captured_at=current[0],
            )
            _completed(manager, sequence)
            current[0] += timedelta(seconds=2)
        snapshot = manager.poll("stream-yard")
        assert len(snapshot.recent_admission_outcomes) == object_tracking.MAX_ADMISSION_RECENT_OUTCOMES
        assert snapshot.admission_counters["inferences_without_animal"] == (
            object_tracking.MAX_ADMISSION_RECENT_OUTCOMES + 7
        )
        assert all(
            value <= object_tracking.MAX_ADMISSION_COUNTER
            for value in snapshot.admission_counters.values()
        )
    finally:
        manager.shutdown()
