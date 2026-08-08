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


# --------------------------------------------------------------------------
# Stage 6.17: reviewed appearance intervals as deterministic replay Visit
# truth -- see docs/reviewed-visit-truth-contract.md.
# --------------------------------------------------------------------------


def test_expected_visit_new_fields_default_safely_and_round_trip_through_replay_io() -> None:
    """`broad_class`/`entry_uncertain`/`exit_uncertain`/
    `source_capture_frame_ids`/`reviewer` are optional, additive reviewed-
    Visit-truth provenance -- absent (safe defaults) on any pre-Stage-6.17
    construction, and round-tripping through the same JSON shape
    `replay_io._visit` loads."""

    from mockingbird.observation.replay_io import _visit as load_expected_visit

    bare = ExpectedVisit("visit-1", ("a",), 0, 1000)
    assert bare.broad_class is None
    assert bare.entry_uncertain is False and bare.exit_uncertain is False
    assert bare.source_capture_frame_ids == ()
    assert bare.reviewer is None

    document = {
        "visit_id": "visit-1", "appearance_ids": ["a"], "start_offset_ms": 0, "end_offset_ms": 1000,
        "outcome": None, "zone_id": "feeder", "ambiguous": False, "broad_class": "bird",
        "entry_uncertain": True, "exit_uncertain": False, "source_capture_frame_ids": ["f1", "f2"], "reviewer": "alice",
    }
    loaded = load_expected_visit(document)
    assert loaded.broad_class == "bird"
    assert loaded.entry_uncertain is True and loaded.exit_uncertain is False
    assert loaded.source_capture_frame_ids == ("f1", "f2")
    assert loaded.reviewer == "alice"


def test_expected_visit_loader_accepts_a_pre_stage_6_17_document_without_new_fields() -> None:
    from mockingbird.observation.replay_io import _visit as load_expected_visit

    loaded = load_expected_visit({"visit_id": "visit-1", "appearance_ids": ["a"], "start_offset_ms": 0, "end_offset_ms": 1000})
    assert loaded.broad_class is None
    assert loaded.source_capture_frame_ids == ()


@pytest.mark.anyio
async def test_fragmentation_and_duplicate_metrics_evaluate_against_reviewed_visit_truth() -> None:
    """(27, 29) Once real reviewed Visit truth exists, the pre-existing
    fragmentation/duplicate counters -- computed by the unchanged matcher --
    report real, non-trivial values against genuine ground truth instead of
    a structurally-forced zero. No matcher/threshold change."""

    @dataclass
    class ThreeProposalProvider:
        provider_id: str = "three"
        capabilities: ObservationProviderCapabilities = ObservationProviderCapabilities(False, True, False, False, True, True)

        async def describe(self, *, stream_id: str | None = None) -> ObservationProviderDescriptor:
            return ObservationProviderDescriptor(self.provider_id, "Three", self.capabilities,
                                                  ObservationProviderHealth("idle", True, "ready"))

        async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]:
            proposals = (
                VisitProposal("p1", "source", frames[0].stream_id, ("m1",), "reason-a", start_offset_ms=0, end_offset_ms=30, shadow_only=True),
                # An exact signature duplicate of p1.
                VisitProposal("p2", "source", frames[0].stream_id, ("m1",), "reason-a", start_offset_ms=0, end_offset_ms=30, shadow_only=True),
                # A distinct proposal over the same expected visit -> fragmented.
                VisitProposal("p3", "source", frames[0].stream_id, ("m3",), "reason-b", start_offset_ms=10, end_offset_ms=30, shadow_only=True),
            )
            return (ObservationResult(self.provider_id, "source", frames[0].stream_id,
                    datetime(2026, 1, 1, tzinfo=UTC), frame_packets=frames, visit_proposals=proposals),)

    one_visit = BenchmarkManifest(1, "benchmark-frag", replay_input().fingerprint,
        (ExpectedAppearance("appearance-1", 0, 30),), (ExpectedVisit("visit-1", ("appearance-1",), 0, 30),))

    runner = ReplayRunner({"three": ThreeProposalProvider()})
    report = await runner.run(replay_input(), one_visit, provider_key="three")

    assert report.metrics["matched_visit_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["duplicate_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["fragmentation_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["incorrect_merge_count"] == {"state": "evaluated", "value": 0}


@pytest.mark.anyio
async def test_incorrect_merge_metric_evaluates_against_reviewed_visit_truth() -> None:
    """(28) A single proposal spanning two distinct reviewed Visits is
    honestly counted as an incorrect merge -- the pre-existing matcher rule,
    now genuinely exercised because real Visit truth exists to merge
    across."""

    @dataclass
    class MergingProvider:
        provider_id: str = "merge"
        capabilities: ObservationProviderCapabilities = ObservationProviderCapabilities(False, True, False, False, True, True)

        async def describe(self, *, stream_id: str | None = None) -> ObservationProviderDescriptor:
            return ObservationProviderDescriptor(self.provider_id, "Merge", self.capabilities,
                                                  ObservationProviderHealth("idle", True, "ready"))

        async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]:
            proposal = VisitProposal("p4", "source", frames[0].stream_id, ("m4",), "reason-c",
                                     start_offset_ms=0, end_offset_ms=1030, shadow_only=True)
            return (ObservationResult(self.provider_id, "source", frames[0].stream_id,
                    datetime(2026, 1, 1, tzinfo=UTC), frame_packets=frames, visit_proposals=(proposal,)),)

    two_visits = BenchmarkManifest(1, "benchmark-merge", replay_input().fingerprint,
        (ExpectedAppearance("appearance-1", 0, 30), ExpectedAppearance("appearance-2", 1000, 1030)),
        (ExpectedVisit("visit-1", ("appearance-1",), 0, 30), ExpectedVisit("visit-2", ("appearance-2",), 1000, 1030)))

    runner = ReplayRunner({"merge": MergingProvider()})
    report = await runner.run(replay_input(), two_visits, provider_key="merge")

    assert report.metrics["incorrect_merge_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["matched_visit_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["missed_visit_count"] == {"state": "evaluated", "value": 1}


@pytest.mark.anyio
async def test_zone_attribution_accuracy_evaluates_once_reviewed_zone_truth_exists() -> None:
    """`zone_attribution_accuracy` moves from a permanent `insufficient_truth`
    stub to a real value once at least one matched Visit carries reviewed
    Zone truth; stays honestly `insufficient_truth` when no Visit in the
    manifest carries a `zone_id` at all. No matcher/threshold change."""

    runner = ReplayRunner({"fake": FakeProvider()})
    with_zone_truth = await runner.run(replay_input(), manifest(), provider_key="fake")
    assert with_zone_truth.metrics["zone_attribution_accuracy"] == {"state": "evaluated", "value": 1.0}

    without_zone_truth = BenchmarkManifest(1, "benchmark-1", replay_input().fingerprint,
        (ExpectedAppearance("appearance-1", 1000, 2000, "unknown_bird"),),
        (ExpectedVisit("visit-1", ("appearance-1",), 1000, 2000, "unknown_bird"),))  # no zone_id
    report = await runner.run(replay_input(), without_zone_truth, provider_key="fake")
    assert report.metrics["zone_attribution_accuracy"]["state"] == "insufficient_truth"


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


# --------------------------------------------------------------------------
# Stage 6.14: reviewed-to-replay evidence identity lineage
# --------------------------------------------------------------------------


def test_replay_frame_id_stays_deterministic_for_the_same_logical_input() -> None:
    """(2) The replay-local `frame_id` `packets()` computes -- a fingerprint
    of (input root, index, offset, content hash) -- is fully reproducible
    for the same logical input, including its source lineage: two
    separately constructed but identical `ReplayInput`s (same reviewed
    lineage included) produce byte-identical replay frame identities. Source
    lineage is semantic (see docs/reviewed-replay-lineage-contract.md), so
    it legitimately participates in the root fingerprint the replay identity
    is derived from -- exactly like the Stage 6.8 timeline facts already do
    (test_replay_frame_timeline_facts_are_part_of_the_semantic_fingerprint)
    -- rather than being invisible to it."""

    def build() -> ReplayInput:
        return ReplayInput("id", "stream", 4, 4, 1.0, (
            ReplayFrame(0, 0, "a", source_capture_frame_id="reviewed-frame-1", source_capture_session_id="session-1", session_sequence=7),
        ))
    assert build().packets()[0].frame_id == build().packets()[0].frame_id


def test_source_and_replay_identities_may_differ_without_losing_lineage() -> None:
    """(3) A replay frame's own `frame_id` (replay-local) and
    `source_capture_frame_id` (the original reviewed capture frame) are
    deliberately distinct identities; both survive onto the produced
    `FramePacket` rather than one silently replacing the other."""

    replay = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", source_capture_frame_id="reviewed-frame-1"),
    ))
    packet = replay.packets()[0]
    assert packet.frame_id != packet.source_capture_frame_id
    assert packet.source_capture_frame_id == "reviewed-frame-1"
    assert packet.source_content_hash == "a"


def test_generic_replay_without_reviewed_source_still_works() -> None:
    """(4) A `ReplayInput` built from a manifest with no reviewed-capture
    provenance at all (an ordinary Stage 2 frame-directory benchmark input)
    replays exactly as before: `source_capture_frame_id` stays `None`
    throughout, and nothing about validation, ordering, or packet
    production requires it."""

    replay = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a"), ReplayFrame(1, 100, "b"), ReplayFrame(2, 200, "c"),
    ))
    packets = replay.packets()
    assert len(packets) == 3
    assert all(packet.source_capture_frame_id is None for packet in packets)
    assert all(packet.frame_id is not None for packet in packets)


def test_duplicate_source_capture_frame_id_within_one_replay_input_rejects() -> None:
    """(16) One reviewed source frame may be referenced by at most one
    replay frame within a single input -- a duplicate is rejected outright
    rather than silently accepted, regardless of whether the two entries'
    own content hashes happen to agree."""

    with pytest.raises(ReplayValidationError, match="duplicate_source_capture_frame_id"):
        ReplayInput("id", "stream", 4, 4, 1.0, (
            ReplayFrame(0, 0, "hash-a", source_capture_frame_id="reviewed-frame-1"),
            ReplayFrame(1, 100, "hash-b", source_capture_frame_id="reviewed-frame-1"),
        ))
    with pytest.raises(ReplayValidationError, match="duplicate_source_capture_frame_id"):
        ReplayInput("id", "stream", 4, 4, 1.0, (
            ReplayFrame(0, 0, "hash-a", source_capture_frame_id="reviewed-frame-1"),
            ReplayFrame(1, 100, "hash-a", source_capture_frame_id="reviewed-frame-1"),
        ))
    # Distinct source identities remain fully supported.
    ok = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "hash-a", source_capture_frame_id="reviewed-frame-1"),
        ReplayFrame(1, 100, "hash-b", source_capture_frame_id="reviewed-frame-2"),
    ))
    assert len(ok.frames) == 2


def test_stable_derived_ids_remain_deterministic_across_repeated_calls() -> None:
    """(24) Repeated `packets()` calls over the same `ReplayInput` produce
    byte-identical replay and source-lineage identities."""

    replay = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", source_capture_frame_id="reviewed-frame-1", session_sequence=3),
    ))
    first, second = replay.packets(), replay.packets()
    assert first[0].frame_id == second[0].frame_id
    assert first[0].source_capture_frame_id == second[0].source_capture_frame_id == "reviewed-frame-1"


def test_source_lineage_fields_are_part_of_the_semantic_fingerprint() -> None:
    """(25) Two replay inputs that differ only in reviewed source-frame
    identity are semantically different runs and must fingerprint
    differently; identical inputs reproduce identical fingerprints, and a
    frame with no source lineage at all keeps its pre-Stage-6.14
    fingerprint unchanged (purely additive, see
    test_replay_frame_without_timeline_fields_keeps_the_pre_stage_6_8_fingerprint
    for the equivalent Stage 6.8 proof)."""

    plain = ReplayInput("id", "stream", 4, 4, 1.0, (ReplayFrame(0, 0, "a"),))
    same_shape = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", None, (), None, None, None, None, None, None, False, None, None, None, None),
    ))
    assert plain.fingerprint == same_shape.fingerprint

    with_lineage = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", source_capture_frame_id="reviewed-frame-1"),
    ))
    other_lineage = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", source_capture_frame_id="reviewed-frame-2"),
    ))
    repeat_of_first = ReplayInput("id", "stream", 4, 4, 1.0, (
        ReplayFrame(0, 0, "a", source_capture_frame_id="reviewed-frame-1"),
    ))
    assert plain.fingerprint != with_lineage.fingerprint
    assert with_lineage.fingerprint != other_lineage.fingerprint
    assert with_lineage.fingerprint == repeat_of_first.fingerprint
