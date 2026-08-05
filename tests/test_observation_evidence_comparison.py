from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from mockingbird.observation.contracts import (
    EvidenceCandidate,
    FramePacket,
    ObservationProviderCapabilities,
    ObservationResult,
    VisitProposal,
)
from mockingbird.observation.replay import (
    BenchmarkManifest,
    ExpectedAppearance,
    ExpectedEvidence,
    ExpectedVisit,
    ReplayFrame,
    ReplayInput,
    ReplayRunner,
    compare_replay_reports,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class EvidenceProvider:
    candidates: tuple[EvidenceCandidate, ...]
    provider_id: str = "frame-driven-onnx-cuda"
    capabilities: ObservationProviderCapabilities = ObservationProviderCapabilities(
        False, True, True, True, True, True, deterministic_replay=True, frame_driven=True,
    )

    async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]:
        proposal = VisitProposal(
            "proposal", "shadow", frames[0].stream_id,
            tuple(item.media_asset_id for item in self.candidates), "confirmed_visit",
            0, 1000, track_generation_id="track",
        )
        return (ObservationResult(
            self.provider_id, "shadow", frames[0].stream_id, datetime(2026, 1, 1, tzinfo=UTC),
            frame_packets=frames, evidence_candidates=self.candidates,
            visit_proposals=(proposal,) if self.capabilities.emits_visit_proposals else (),
        ),)


def _input(tmp_path: Path) -> ReplayInput:
    paths = []
    for index in range(2):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", (320, 240), "gray").save(path)
        paths.append(path)
    return ReplayInput("input", "stream", 320, 240, 1.0, (
        ReplayFrame(0, 0, "a", str(paths[0])), ReplayFrame(1, 1000, "b", str(paths[1])),
    ))


@pytest.mark.anyio
async def test_replay_scores_evidence_and_optional_truth_deterministically(tmp_path: Path) -> None:
    replay = _input(tmp_path)
    candidates = (
        EvidenceCandidate(
            "replay:0", "stream", "tracked_best", None, replay.packets()[0].frame_id,
            0, 320, 240, (0.2, 0.2, 0.6, 0.7), "track", "detector", "tracker",
            (("track_supported", True), ("temporal_alignment", "aligned")),
        ),
        EvidenceCandidate(
            "replay:1", "stream", "pretrigger", None, replay.packets()[1].frame_id,
            1000, 320, 240, None, "track", quality_facts=(("decodable", True),),
        ),
    )
    manifest = BenchmarkManifest(
        1, "benchmark", replay.fingerprint,
        (ExpectedAppearance("bird", 0, 1000),),
        (ExpectedVisit("visit", ("bird",), 0, 1000),),
        evidence=(
            ExpectedEvidence("replay:0", useful_identification=True, subject_visible=True),
            ExpectedEvidence("replay:1", useful_context=True, preferred_context=True),
        ),
    )
    provider = EvidenceProvider(candidates)
    runner = ReplayRunner({provider.provider_id: provider})
    first = await runner.run(replay, manifest, provider_key=provider.provider_id)
    second = await runner.run(replay, manifest, provider_key=provider.provider_id)
    assert first.evidence_selections == second.evidence_selections
    assert first.evidence_fingerprint == second.evidence_fingerprint
    assert first.metrics["useful_identification_evidence"] == {"state": "evaluated", "value": 1}
    assert first.metrics["useful_context_evidence"] == {"state": "evaluated", "value": 1}
    assert first.metrics["useful_primary_rate"] == {"state": "evaluated", "value": 1.0}


@pytest.mark.anyio
async def test_missing_and_ambiguous_evidence_truth_have_honest_states(tmp_path: Path) -> None:
    replay = _input(tmp_path)
    candidate = EvidenceCandidate(
        "replay:0", "stream", "tracked_best", None, replay.packets()[0].frame_id,
        0, 320, 240, (0.2, 0.2, 0.6, 0.7), "track", quality_facts=(("decodable", True),),
    )
    provider = EvidenceProvider((candidate,))
    empty = BenchmarkManifest(1, "empty", replay.fingerprint, (), ())
    report = await ReplayRunner({provider.provider_id: provider}).run(replay, empty, provider_key=provider.provider_id)
    assert report.metrics["useful_primary_rate"]["state"] == "not_evaluated"
    ambiguous = BenchmarkManifest(
        1, "ambiguous", replay.fingerprint, (), (),
        evidence=(ExpectedEvidence("replay:0", ambiguous=True),),
    )
    report = await ReplayRunner({provider.provider_id: provider}).run(replay, ambiguous, provider_key=provider.provider_id)
    assert report.metrics["useful_primary_rate"]["state"] == "insufficient_truth"


@pytest.mark.anyio
async def test_provider_comparison_classifies_each_metric_without_winner_score(tmp_path: Path) -> None:
    replay = _input(tmp_path)
    manifest = BenchmarkManifest(1, "benchmark", replay.fingerprint, (), ())
    frame = EvidenceProvider(())
    snapshot = EvidenceProvider((), provider_id="snapshot", capabilities=ObservationProviderCapabilities(
        True, True, False, False, True, False, deterministic_replay=True,
    ))
    snapshot_report = await ReplayRunner({"snapshot": snapshot}).run(replay, manifest, provider_key="snapshot")
    frame_report = await ReplayRunner({frame.provider_id: frame}).run(replay, manifest, provider_key=frame.provider_id)
    first = compare_replay_reports(snapshot_report, frame_report)
    assert first == compare_replay_reports(snapshot_report, frame_report)
    assert "winner" not in first
    assert {item["classification"] for item in first["metrics"]} <= {
        "frame-driven better", "snapshot better", "equivalent",
        "insufficient truth", "unsupported for one provider",
    }
    evidence_metric = next(item for item in first["metrics"] if item["metric"] == "useful_primary_rate")
    assert evidence_metric["classification"] == "unsupported for one provider"
