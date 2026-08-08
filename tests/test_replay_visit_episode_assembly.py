"""Hardware-free integration tests for the Stage 6.19 shadow assembly stage
wired into `replay.py` (`assemble_visit_episode_report`). Complements
`tests/test_visit_episode_assembler.py` (pure-module unit tests) by proving
the *wiring*: a full `ReplayRunner.run()` report feeds `build_tracklets`
correctly, tracker-level fragmentation stays visible independent of what
assembly does about it, and calling this new, optional stage never mutates
or otherwise affects the pre-existing `ReplayReport`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenSettings
from mockingbird.observation.replay import (
    BenchmarkManifest,
    ExpectedAppearance,
    ExpectedVisit,
    ReplayFrame,
    ReplayInput,
    ReplayRunner,
    assemble_visit_episode_report,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeDetector:
    def __init__(self, detections: dict[str, tuple[DetectionObservation, ...]]) -> None:
        self.detections = detections
        self.loaded = False

    def probe(self) -> dict[str, object]:
        return {"cuda_available": True, "model_bundle_compatible": True}

    def load(self) -> None:
        self.loaded = True

    async def infer_frame(self, frame: FramePacket) -> tuple[DetectionObservation, ...]:
        return self.detections.get(frame.frame_id or "", ())

    def finalize_replay(self) -> None:
        pass

    def close(self) -> None:
        self.loaded = False

    def report_metadata(self) -> dict[str, object]:
        return {"model": {"key": "fake", "version": "1"}}

    def execution_facts(self) -> dict[str, object]:
        return {}


def _animal(frame: FramePacket, box: tuple[float, float, float, float], score: float = 0.5) -> DetectionObservation:
    return DetectionObservation(
        "fake:1", "animal", score, frame.captured_at or datetime(2026, 1, 1, tzinfo=UTC),
        f"detection:{frame.frame_id}:{box}", frame.frame_id, "fake", "fake", "fake-gen", box, "0", True,
    )


def _replay_input(count: int, *, step_ms: int = 500) -> ReplayInput:
    frames = tuple(
        ReplayFrame(index=index, source_offset_ms=index * step_ms, content_hash=f"hash-{index}")
        for index in range(count)
    )
    return ReplayInput("input-1", "stream-a", 100, 100, 2.0, frames)


async def _run(detections: dict[str, tuple[DetectionObservation, ...]], *, frame_count: int, manifest: BenchmarkManifest):
    replay = _replay_input(frame_count)
    detector = _FakeDetector(detections)
    provider = FrameDrivenObservationProvider(
        detector=detector,
        settings=FrameDrivenSettings(
            source_nominal_fps=2.0, baseline_detector_fps=2.0, candidate_detector_fps=2.0,
            strong_detection_threshold=0.8, minimum_detector_confirmations=2, minimum_tracker_support_frames=1,
            maximum_missed_frames=2, maximum_frame_gap_ms=1000, tracker_expiry_ms=1000,
            maximum_track_duration_ms=30_000, maximum_active_tracks=8,
            # A large negative-frames-to-end bound isolates the bounded-
            # timeout ("maximum_unsupported_duration"/"tracker_lost")
            # pathway this integration test exercises -- the tracker's own
            # genuine negative-interval detection (already covered directly
            # by `test_detector_negative_interval_contributes_separation_
            # evidence` in the pure assembler test file) is a *separate*,
            # dense-cadence-dependent mechanism this fake detector's regular
            # per-frame cadence would otherwise trigger first.
            maximum_unsupported_detector_ms=5000, negative_detector_frames_to_end=100,
        ),
    )
    provider.load()
    runner = ReplayRunner({provider.provider_id: provider})
    report = await runner.run(replay, manifest, provider_key=provider.provider_id)
    return report, replay


async def test_assemble_visit_episode_report_merges_confirmed_generations_and_matches_truth() -> None:
    """Two confirmed tracklets, separated by a gap the raw tracker cannot
    bridge (well past `maximum_unsupported_detector_ms`) but well within the
    assembler's own `merge_gap_ms`, with compatible geometry: the raw report
    shows 2 confirmed tracks/proposals; the assembled report consolidates
    them into 1 proposal that matches one `ExpectedVisit` spanning both."""
    box = (0.4, 0.4, 0.5, 0.5)
    # First tracklet: frames 0-3 (0-1500ms), confirmed, then a silent gap.
    # Second tracklet: frames 14-17 (7000-8500ms) -- gap 5500ms > maximum_
    # unsupported_detector_ms(5000), so the raw tracker cannot bridge it.
    detections: dict[str, tuple[DetectionObservation, ...]] = {}
    frame_count = 20
    replay_probe = _replay_input(frame_count)
    packets = replay_probe.packets()
    for index in (0, 1, 2, 3, 14, 15, 16, 17):
        detections[packets[index].frame_id] = (_animal(packets[index], box, score=0.5),)

    manifest = BenchmarkManifest(
        1, "bm-merge", replay_probe.fingerprint,
        (ExpectedAppearance("app-1", 0, 8500),),
        (ExpectedVisit("visit:app-1", ("app-1",), 0, 8500),),
    )
    report, _ = await _run(detections, frame_count=frame_count, manifest=manifest)

    assert report.metrics["tracks_confirmed"]["value"] == 2
    assert len(report.proposals) == 2  # raw, one-proposal-per-generation baseline

    assembled = assemble_visit_episode_report(report, manifest)
    assert assembled.assembly_metrics["tracklets_input"]["value"] == 2
    assert assembled.assembly_metrics["episode_merges"]["value"] == 1
    assert assembled.assembly_metrics["assembled_visit_proposals"]["value"] == 1
    assert len(assembled.proposals) == 1
    assert assembled.proposals[0].constituent_generation_ids != ()
    assert len(assembled.proposals[0].constituent_generation_ids) == 2

    assert assembled.visit_truth_metrics["matched_visit_count"]["value"] == 1
    assert assembled.visit_truth_metrics["appearance_recall"]["value"] == 1.0
    assert assembled.visit_truth_metrics["incorrect_merge_count"]["value"] == 0

    # Track-level metrics stay visible and unaffected by assembly.
    assert assembled.track_metrics["tracks_confirmed"] == report.metrics["tracks_confirmed"]


async def test_track_metrics_expose_raw_fragmentation_independent_of_assembly() -> None:
    """Fragmentation must never be hidden by assembly: raw `tracks_
    confirmed`/proposal count stays exactly as high as before, even though
    the assembled-Visit layer reports far fewer proposals."""
    box = (0.35, 0.35, 0.45, 0.45)
    step_ms = 500
    frame_count = 52
    replay_probe = _replay_input(frame_count, step_ms=step_ms)
    packets = replay_probe.packets()
    # Four confirmed tracklets, each separated by a fixed 6500ms silent gap:
    # > maximum_unsupported_detector_ms(5000) so the raw tracker cannot
    # bridge it (genuine fragmentation), but < the assembler's own
    # merge_gap_ms(15000) with compatible geometry throughout.
    detections: dict[str, tuple[DetectionObservation, ...]] = {}
    for group_start_ms in (0, 8000, 16000, 24000):
        for offset_ms in (0, 500, 1000, 1500):
            index = (group_start_ms + offset_ms) // step_ms
            detections[packets[index].frame_id] = (_animal(packets[index], box, score=0.5),)

    manifest = BenchmarkManifest(1, "bm-fragmented", replay_probe.fingerprint, (), ())
    report, _ = await _run(detections, frame_count=frame_count, manifest=manifest)
    raw_confirmed = report.metrics["tracks_confirmed"]["value"]
    assert raw_confirmed >= 3  # genuinely fragmented at the raw tracker layer

    assembled = assemble_visit_episode_report(report, manifest)
    assert assembled.track_metrics["tracks_confirmed"]["value"] == raw_confirmed  # unchanged, still visible
    assert assembled.assembly_metrics["assembled_visit_proposals"]["value"] < raw_confirmed  # assembly reduced it


async def test_assemble_visit_episode_report_does_not_mutate_replay_report() -> None:
    """Calling the new, optional assembly stage has zero effect on the
    already-produced `ReplayReport` -- its own semantic fingerprint is
    identical whether or not assembly is ever invoked."""
    box = (0.5, 0.5, 0.6, 0.6)
    frame_count = 6
    replay_probe = _replay_input(frame_count)
    packets = replay_probe.packets()
    detections = {packets[index].frame_id: (_animal(packets[index], box, score=0.5),) for index in (0, 1)}
    manifest = BenchmarkManifest(1, "bm-no-mutate", replay_probe.fingerprint, (), ())
    report, _ = await _run(detections, frame_count=frame_count, manifest=manifest)
    fingerprint_before = report.semantic_fingerprint
    assemble_visit_episode_report(report, manifest)
    assert report.semantic_fingerprint == fingerprint_before
