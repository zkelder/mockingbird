from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

from mockingbird.observation.contracts import (
    FramePacket,
    ObservationProviderCapabilities,
    ObservationProviderDescriptor,
    ObservationProviderHealth,
    ObservationResult,
    VisitProposal,
)
from mockingbird.observation.replay import (
    BenchmarkManifest,
    ExpectedAppearance,
    ExpectedVisit,
    _match,
    ReplayFrame,
    ReplayInput,
    ReplayRunner,
    ReplayValidationError,
)


@dataclass
class FakeProvider:
    provider_id: str = "fake"
    display_name: str = "Fake"
    capabilities: ObservationProviderCapabilities = ObservationProviderCapabilities(
        False, True, False, False, True, True
    )

    async def describe(self, *, stream_id: str | None = None) -> ObservationProviderDescriptor:
        return ObservationProviderDescriptor(
            self.provider_id, self.display_name, self.capabilities,
            ObservationProviderHealth("idle", True, "ready"),
        )

    async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]:
        proposal = VisitProposal(
            "proposal-1", "source", frames[0].stream_id, (frames[1].media_asset_id,), "fake",
            start_offset_ms=1000, end_offset_ms=2000, zone_id="feeder", shadow_only=True,
        )
        return (ObservationResult(self.provider_id, "source", frames[0].stream_id,
                datetime(2026, 1, 1, tzinfo=UTC), frame_packets=frames,
                visit_proposals=(proposal,)),)


def replay_input() -> ReplayInput:
    return ReplayInput("replay-1", "stream-1", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a"), ReplayFrame(1, 1000, "b"), ReplayFrame(2, 2000, "c"),
    ))


def manifest() -> BenchmarkManifest:
    data = replay_input()
    return BenchmarkManifest(1, "benchmark-1", data.fingerprint,
        (ExpectedAppearance("appearance-1", 1000, 2000, "unknown_bird"),),
        (ExpectedVisit("visit-1", ("appearance-1",), 1000, 2000, "unknown_bird", "feeder"),))


@pytest.mark.anyio
async def test_replay_is_deterministic_shadow_only_and_matches() -> None:
    runner = ReplayRunner({"fake": FakeProvider()})
    first = await runner.run(replay_input(), manifest(), provider_key="fake")
    second = await runner.run(replay_input(), manifest(), provider_key="fake")
    assert [frame.frame_id for frame in first.frames] == [frame.frame_id for frame in second.frames]
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.metrics["appearance_recall"] == {"state": "evaluated", "value": 1.0}
    assert first.metrics["proposal_precision"] == {"state": "evaluated", "value": 1.0}
    assert first.matches[0].status == "matched"
    assert all(proposal.shadow_only for proposal in first.proposals)
    assert first.creates_truth is False


@pytest.mark.anyio
async def test_replay_rejects_unknown_provider_and_production_authority() -> None:
    runner = ReplayRunner({"fake": FakeProvider()})
    with pytest.raises(ReplayValidationError, match="unsupported_provider"):
        await runner.run(replay_input(), manifest(), provider_key="missing")

    class Unsafe(FakeProvider):
        async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]:
            result = (await super().replay_frames(frames))[0]
            return (ObservationResult(**{**result.__dict__, "creates_truth": True}),)

    with pytest.raises(ReplayValidationError, match="production_authority"):
        await ReplayRunner({"unsafe": Unsafe()}).run(replay_input(), manifest(), provider_key="unsafe")


def test_manifest_rejects_invalid_order_and_out_of_duration_appearance() -> None:
    with pytest.raises(ReplayValidationError, match="ordered_timestamps"):
        ReplayInput("id", "stream", 4, 4, 1.0, (ReplayFrame(0, 1, "a"), ReplayFrame(1, 0, "b")))
    with pytest.raises(ReplayValidationError, match="appearance_outside_duration"):
        BenchmarkManifest(1, "bad", replay_input().fingerprint,
            (ExpectedAppearance("a", 0, 9000, "unknown_bird"),), ()).validate(replay_input())


def test_matcher_records_every_shadow_diagnostic_deterministically() -> None:
    expected = (ExpectedVisit("one", ("a",), 0, 30), ExpectedVisit("two", ("b",), 20, 40), ExpectedVisit("uncertain", ("c",), 50, 60, ambiguous=True))
    def proposal(key: str, start: int, end: int, reason: str = "same") -> VisitProposal:
        return VisitProposal(key, "source", "stream", ("media",), reason, start, end)
    matches = _match(expected, (proposal("a", 0, 30), proposal("b", 0, 30), proposal("c", 0, 30, "different"), proposal("merge", 20, 30), proposal("false", 70, 80)))
    assert {item.status for item in matches} >= {"matched", "missed", "false", "duplicate", "fragmented", "incorrectly_merged", "ambiguous"}


def test_onnx_cuda_provider_import_is_optional_and_probe_is_side_effect_free() -> None:
    from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider
    provider = OnnxCudaObservationProvider.unconfigured()
    assert provider.provider_id == "onnx-cuda"
    assert provider.capabilities.emits_detection_observations is True
    assert provider.session_loaded is False
