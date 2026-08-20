"""Perception Replay Regression Harness v1: `perception_regression.py`
orchestration -- full-funnel run, bounded time-window selection, and
baseline-vs-candidate comparison. Hardware-free throughout: a fake detector
drives the real `FrameDrivenObservationProvider`/tracker/assembler/admission
stack exactly like `test_replay_visit_episode_assembly.py` already
establishes for the stage below this one.
"""
from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenSettings
from mockingbird.observation.perception_regression import (
    compare_perception_regression_reports,
    perception_regression_report_to_json,
    run_perception_regression,
    select_time_window,
)
from mockingbird.observation.replay import BenchmarkManifest, ReplayFrame, ReplayInput, ReplayValidationError
from mockingbird.observation.replay_io import ReplayBundle

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeDetector:
    def __init__(self, detections: dict[str, tuple[DetectionObservation, ...]]) -> None:
        self.detections = detections

    def probe(self) -> dict[str, object]:
        return {"cuda_available": True, "model_bundle_compatible": True}

    def load(self) -> None:
        pass

    async def infer_frame(self, frame: FramePacket) -> tuple[DetectionObservation, ...]:
        return self.detections.get(frame.frame_id or "", ())

    def finalize_replay(self) -> None:
        pass

    def close(self) -> None:
        pass

    def report_metadata(self) -> dict[str, object]:
        return {"model": {"key": "fake", "version": "1"}}

    def execution_facts(self) -> dict[str, object]:
        return {}


def _animal(frame: FramePacket, box: tuple[float, float, float, float], score: float = 0.9) -> DetectionObservation:
    return DetectionObservation(
        "fake:1", "animal", score, frame.captured_at or datetime(2026, 1, 1, tzinfo=UTC),
        f"detection:{frame.frame_id}:{box}", frame.frame_id, "fake", "fake", "fake-gen", box, "0", True,
    )


def _settings() -> FrameDrivenSettings:
    return FrameDrivenSettings(
        source_nominal_fps=2.0, baseline_detector_fps=2.0, candidate_detector_fps=2.0,
        strong_detection_threshold=0.8, minimum_detector_confirmations=2, minimum_tracker_support_frames=1,
        maximum_missed_frames=2, maximum_frame_gap_ms=1000, tracker_expiry_ms=1000,
        maximum_track_duration_ms=30_000, maximum_active_tracks=8,
        maximum_unsupported_detector_ms=5000, negative_detector_frames_to_end=100,
    )


def _jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), color=(40, 90, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _bundle_with_real_frames(
    tmp_path: Path, *, count: int, step_ms: int = 500, stream_id: str = "replay:fixture-feeder",
) -> ReplayBundle:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    payload = _jpeg_bytes()
    import hashlib
    frames = []
    for index in range(count):
        path = frames_dir / f"frame-{index:03d}.jpg"
        path.write_bytes(payload)
        frames.append(ReplayFrame(index, index * step_ms, hashlib.sha256(payload).hexdigest(), str(path)))
    replay = ReplayInput("input-1", stream_id, 320, 240, 2.0, tuple(frames))
    manifest = BenchmarkManifest(1, "bm-fixture", replay.fingerprint, (), ())
    return ReplayBundle(replay, manifest, {})


async def test_run_perception_regression_produces_a_full_funnel_report(tmp_path: Path) -> None:
    box = (0.4, 0.4, 0.5, 0.5)
    bundle = _bundle_with_real_frames(tmp_path, count=6)
    packets = bundle.replay.packets()
    detections = {packets[index].frame_id: (_animal(packets[index], box),) for index in (0, 1, 2, 3)}
    provider = FrameDrivenObservationProvider(detector=_FakeDetector(detections), settings=_settings())
    provider.load()

    report = await run_perception_regression(
        bundle, provider=provider, provider_key=provider.provider_id,
        base_observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert report.replay.metrics["tracks_confirmed"]["value"] == 1
    assert len(report.assembly.proposals) == 1
    assert report.admission is not None
    assert report.admission.outcome_counts.get("created") == 1
    assert report.provenance.harness_version == "perception-replay-regression-harness-v1"
    assert report.provenance.admission_evaluated is True

    payload = perception_regression_report_to_json(report)
    assert payload["admission"]["outcome_counts"] == {"created": 1}
    assert payload["schema_version"] == 1


async def test_run_perception_regression_without_admission_leaves_it_none(tmp_path: Path) -> None:
    bundle = _bundle_with_real_frames(tmp_path, count=3)
    provider = FrameDrivenObservationProvider(detector=_FakeDetector({}), settings=_settings())
    provider.load()
    report = await run_perception_regression(bundle, provider=provider, provider_key=provider.provider_id, run_admission=False)
    assert report.admission is None
    assert report.provenance.admission_evaluated is False


async def test_semantic_fingerprint_is_stable_across_repeated_runs_despite_provenance_timestamps(tmp_path: Path) -> None:
    """Determinism acceptance: two runs of the identical input/config, only
    seconds apart, must agree on every semantic fact even though their own
    `run_started_at` timestamps necessarily differ."""

    box = (0.4, 0.4, 0.5, 0.5)
    bundle = _bundle_with_real_frames(tmp_path, count=6)
    packets = bundle.replay.packets()
    detections = {packets[index].frame_id: (_animal(packets[index], box),) for index in (0, 1, 2, 3)}

    async def _run() -> object:
        provider = FrameDrivenObservationProvider(detector=_FakeDetector(detections), settings=_settings())
        provider.load()
        return await run_perception_regression(
            bundle, provider=provider, provider_key=provider.provider_id,
            base_observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    first = await _run()
    second = await _run()
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.provenance.run_started_at != "" and second.provenance.run_started_at != ""


def test_select_time_window_rebases_frames_and_drops_partial_truth(tmp_path: Path) -> None:
    bundle = _bundle_with_real_frames(tmp_path, count=10, step_ms=1000)
    from mockingbird.observation.replay import ExpectedAppearance, ExpectedVisit

    manifest = BenchmarkManifest(
        1, "bm-window", bundle.replay.fingerprint,
        (ExpectedAppearance("app-inside", 3000, 5000), ExpectedAppearance("app-outside", 8000, 9000)),
        (ExpectedVisit("visit-inside", ("app-inside",), 3000, 5000),
         ExpectedVisit("visit-partial", ("app-outside",), 8000, 9500)),
    )
    bundle = ReplayBundle(bundle.replay, manifest, bundle.thresholds)

    windowed = select_time_window(bundle, start_offset_ms=2000, end_offset_ms=6000)
    assert [frame.source_offset_ms for frame in windowed.replay.frames] == [0, 1000, 2000, 3000, 4000]
    assert {item.appearance_id for item in windowed.manifest.appearances} == {"app-inside"}
    assert {item.visit_id for item in windowed.manifest.visits} == {"visit-inside"}
    # Rebased: original 3000-5000 -> windowed origin is 2000 -> 1000-3000.
    assert windowed.manifest.visits[0].start_offset_ms == 1000
    assert windowed.manifest.visits[0].end_offset_ms == 3000


def test_select_time_window_rejects_an_empty_selection(tmp_path: Path) -> None:
    bundle = _bundle_with_real_frames(tmp_path, count=5, step_ms=1000)
    with pytest.raises(ReplayValidationError, match="empty_window_selection"):
        select_time_window(bundle, start_offset_ms=100_000, end_offset_ms=200_000)


async def test_compare_perception_regression_reports_flags_an_admission_change(tmp_path: Path) -> None:
    box = (0.4, 0.4, 0.5, 0.5)
    bundle = _bundle_with_real_frames(tmp_path, count=6)
    packets = bundle.replay.packets()
    detections = {packets[index].frame_id: (_animal(packets[index], box),) for index in (0, 1, 2, 3)}

    provider_a = FrameDrivenObservationProvider(detector=_FakeDetector(detections), settings=_settings())
    provider_a.load()
    baseline = await run_perception_regression(
        bundle, provider=provider_a, provider_key=provider_a.provider_id,
        base_observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    # Candidate: identical perception, but admission turned off -- a clean,
    # deterministic "something changed" signal without needing two providers.
    provider_b = FrameDrivenObservationProvider(detector=_FakeDetector(detections), settings=_settings())
    provider_b.load()
    candidate = await run_perception_regression(
        bundle, provider=provider_b, provider_key=provider_b.provider_id, run_admission=False,
    )

    diff = compare_perception_regression_reports(baseline, candidate)
    created_row = next(item for item in diff["admission_comparisons"] if item["metric"] == "created")
    assert created_row["classification"] == "not_evaluated"
    assert diff["replay_comparison"]["semantic_fingerprint"]  # reused, unmodified comparison still present
