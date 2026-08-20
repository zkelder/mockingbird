"""Perception Replay Regression Harness v1: real-fixture acceptance.

Skip-guarded exactly like `test_burst_scheduler_replay.py`'s own real-
session convention: these fixtures point at real 2026-08-19/08-20
`acceptance_recorder` output living outside this checkout entirely (real
field evidence is never committed to git -- see docs/perception-replay-
regression-harness-contract.md "Fixtures"), so this file is a no-op skip on
any environment that does not have that exact local data. On the sandbox
that produced it, it is real acceptance evidence: real recorded frame
bytes/timestamps flow through the actual production tracking/assembly/
admission stack, repeatably and deterministically, without ever touching
the real product database.

The detector used here is an explicit, disclosed *position-based* synthetic
stand-in (never real MDv5 inference -- that would require the real CUDA
runtime this harness deliberately keeps optional, see "Real acceptance
tonight" in the contract doc) -- it proves the harness's own mechanical
properties (real frame ordering/identity/timing flowing correctly through
tracking -> assembly -> admission, safely, repeatably) on real data. It is
not a claim about detector accuracy on this footage.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenSettings
from mockingbird.observation.perception_regression import run_perception_regression
from mockingbird.observation.perception_regression_io import load_fixture_registry

pytestmark = pytest.mark.anyio

FIXTURE_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "perception_replay_fixtures" / "fixtures.json"


def _registry_available() -> bool:
    return FIXTURE_REGISTRY_PATH.is_file()


def _fixture_frames_available(fixture_id: str) -> bool:
    if not _registry_available():
        return False
    try:
        registry = load_fixture_registry(FIXTURE_REGISTRY_PATH)
    except Exception:
        return False
    fixture = registry.get(fixture_id)
    return fixture is not None and Path(fixture.frames_path).is_dir()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _PositionBasedSyntheticDetector:
    """Explicit, disclosed synthetic stand-in -- never real detector
    inference. Deterministically reports one mid-confidence "animal" box on
    every frame whose index falls in the caller-chosen `active_indices` set,
    nothing on every other frame. Exists only to exercise real-data timing/
    identity through tracking/assembly/admission end to end."""

    def __init__(self, active_indices: frozenset[int]) -> None:
        self._active_indices = active_indices

    def probe(self) -> dict[str, object]:
        return {"cuda_available": True, "model_bundle_compatible": True}

    def load(self) -> None:
        pass

    async def infer_frame(self, frame: FramePacket) -> tuple[DetectionObservation, ...]:
        index = int((frame.media_asset_id or "replay:-1").split(":")[-1]) if frame.media_asset_id else -1
        if index not in self._active_indices:
            return ()
        return (DetectionObservation(
            "synthetic-position-based:1", "animal", 0.75, frame.captured_at or datetime.now(),
            f"synthetic-detection:{frame.frame_id}", frame.frame_id, "synthetic", "synthetic",
            "synthetic-gen", (0.35, 0.35, 0.55, 0.55), "0", True,
        ),)

    def finalize_replay(self) -> None:
        pass

    def close(self) -> None:
        pass

    def report_metadata(self) -> dict[str, object]:
        return {"model": {"key": "position-based-synthetic-stand-in", "version": "1"}}

    def execution_facts(self) -> dict[str, object]:
        return {}


def _settings() -> FrameDrivenSettings:
    return FrameDrivenSettings(
        source_nominal_fps=1.0, baseline_detector_fps=1.0, candidate_detector_fps=1.0,
        strong_detection_threshold=0.7, minimum_detector_confirmations=2, minimum_tracker_support_frames=1,
        maximum_missed_frames=3, maximum_frame_gap_ms=15_000, tracker_expiry_ms=15_000,
        maximum_track_duration_ms=120_000, maximum_active_tracks=24,
        maximum_unsupported_detector_ms=60_000, negative_detector_frames_to_end=100,
    )


@pytest.mark.skipif(not _fixture_frames_available("e2e_2026_08_19_encounter_1_sustained_valid"),
                     reason="real 2026-08-19 acceptance-recorder frames are not present on this checkout")
async def test_real_encounter_1_replays_repeatedly_and_deterministically() -> None:
    """The core 'real acceptance tonight' proof: real recorded frame bytes/
    timestamps from a genuine field session flow through the real
    production tracking/assembly/admission stack twice, producing
    byte-identical semantic results both times, without ever touching the
    real product database."""

    from mockingbird.observation.perception_regression_io import load_acceptance_recording

    registry = load_fixture_registry(FIXTURE_REGISTRY_PATH)
    fixture = registry["e2e_2026_08_19_encounter_1_sustained_valid"]
    bundle = load_acceptance_recording(
        Path(fixture.frames_path), stream_id=fixture.stream_id, input_id=fixture.fixture_id,
        window_start_ms=fixture.window_start_ms, window_end_ms=fixture.window_end_ms,
    )
    assert len(bundle.replay.frames) > 50  # real, substantial real-frame count
    assert bundle.replay.width == 1920 and bundle.replay.height == 1080  # real Camera Node resolution

    # Position-based synthetic detector: "active" for the middle third of
    # this real window, where the independently-adjudicated encounter table
    # places the confirmed sighting.
    frame_count = len(bundle.replay.frames)
    active = frozenset(range(frame_count // 3, 2 * frame_count // 3))

    async def _run():
        provider = FrameDrivenObservationProvider(detector=_PositionBasedSyntheticDetector(active), settings=_settings())
        provider.load()
        return await run_perception_regression(
            bundle, provider=provider, provider_key=provider.provider_id, base_observed_at=fixture.base_observed_at,
        )

    first = await _run()
    second = await _run()

    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.replay.metrics["frames_supplied"]["value"] == frame_count
    assert first.replay.metrics["tracks_confirmed"]["value"] >= 1
    assert first.admission is not None
    assert first.admission.outcome_counts.get("created", 0) >= 1


@pytest.mark.skipif(not _fixture_frames_available("cache128_2026_08_20_nighttime_zero_activity"),
                     reason="real 2026-08-20 overnight acceptance-recorder frames are not present on this checkout")
async def test_real_nighttime_negative_control_stays_quiet() -> None:
    """The real known-quiet overnight session: with the detector reporting
    nothing (matching this fixture's own real disclosed disposition -- zero
    confirmed tracks in production), the harness must honestly report zero
    Visits, not fabricate activity."""

    from mockingbird.observation.perception_regression_io import load_acceptance_recording

    registry = load_fixture_registry(FIXTURE_REGISTRY_PATH)
    fixture = registry["cache128_2026_08_20_nighttime_zero_activity"]
    bundle = load_acceptance_recording(
        Path(fixture.frames_path), stream_id=fixture.stream_id, input_id=fixture.fixture_id,
        window_start_ms=0, window_end_ms=120_000,  # first bounded 2 minutes only -- fast, still real
    )
    assert len(bundle.replay.frames) > 10

    provider = FrameDrivenObservationProvider(detector=_PositionBasedSyntheticDetector(frozenset()), settings=_settings())
    provider.load()
    report = await run_perception_regression(
        bundle, provider=provider, provider_key=provider.provider_id, base_observed_at=fixture.base_observed_at,
    )
    assert report.replay.metrics["tracks_confirmed"]["value"] == 0
    assert len(report.assembly.proposals) == 0
    assert report.admission is not None
    assert report.admission.outcome_counts == {}
