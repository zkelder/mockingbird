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


# --------------------------------------------------------------------------
# Stage 6.8: reconnect-safe ReplayFrame provenance
# --------------------------------------------------------------------------


def test_replay_frame_without_timeline_fields_keeps_the_pre_stage_6_8_fingerprint() -> None:
    """A `ReplayFrame` built by any caller that predates Stage 6.8 leaves
    every new field at its default, and the fingerprint it produces must
    stay byte-identical to what an older checkout would have computed --
    nothing about this extension should change an already-committed
    replay manifest's semantic fingerprint."""

    baseline = ReplayInput("id", "stream", 4, 4, 1.0, (ReplayFrame(0, 0, "a"), ReplayFrame(1, 1000, "b")))
    same_shape = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", None, (), None, None, None, None, None, None, False, None),
        ReplayFrame(1, 1000, "b"),
    ))
    assert baseline.fingerprint == same_shape.fingerprint


def test_replay_frame_ordinary_reconnect_reset_does_not_fail_ordered_timestamps() -> None:
    """A reconnect-safe export feeds `source_offset_ms` the session-relative
    (already monotonic) coordinate, not the raw connection-local one that
    resets on every reconnect -- so a full-session replay input covering
    several reconnects still passes `ReplayInput`'s own strict ordering
    check unmodified (see docs/session-timeline-contract.md: normalize the
    export, do not weaken replay validation)."""

    frames = (
        ReplayFrame(0, 0, "a", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 500, "b", connection_segment_id="conn-a", connection_segment_ordinal=0),
        # A reconnect: the *original* connection-local offset reset to 0
        # (preserved below as `original_source_offset_ms`), but the fed
        # `source_offset_ms` keeps climbing.
        ReplayFrame(
            2, 501, "c", connection_segment_id="conn-b", connection_segment_ordinal=1,
            original_source_offset_ms=0, temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
    )
    replay = ReplayInput("id", "stream", 4, 4, 1.0, frames)
    packets = replay.packets()
    assert [item.source_offset_ms for item in packets] == [0, 500, 501]
    boundary = dict(packets[2].timing_facts)
    assert boundary["temporal_discontinuity"] is True
    assert boundary["connection_segment_id"] == "conn-b"
    assert boundary["original_source_offset_ms"] == 0


def test_replay_frame_timeline_facts_are_part_of_the_semantic_fingerprint() -> None:
    plain = ReplayInput("id", "stream", 4, 4, 1.0, (ReplayFrame(0, 0, "a"), ReplayFrame(1, 500, "b")))
    with_discontinuity = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a"),
        ReplayFrame(1, 500, "b", temporal_discontinuity=True, connection_segment_id="conn-b"),
    ))
    assert plain.fingerprint != with_discontinuity.fingerprint
    # Deterministic and reproducible for repeated processing of the same input.
    assert with_discontinuity.fingerprint == ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a"),
        ReplayFrame(1, 500, "b", temporal_discontinuity=True, connection_segment_id="conn-b"),
    )).fingerprint


def test_replay_packets_carry_original_capture_timestamp_and_source_sequence() -> None:
    replay = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", captured_at_iso="2026-08-06T12:00:00+00:00", source_sequence=1, provider_generation="gen-1"),
    ))
    packet = replay.packets()[0]
    assert packet.captured_at == datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)
    assert packet.frame_sequence == 1
    assert packet.provider_generation == "gen-1"
