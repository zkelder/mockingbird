"""Compatibility provider for the existing explicit snapshot monitor."""

from __future__ import annotations

from typing import Any

from mockingbird.monitoring.source_monitor import (
    SourceMonitorManager,
    SourceMonitorOptions,
    SourceMonitorState,
)
from mockingbird.observation.contracts import (
    EvidenceCandidate,
    FramePacket,
    ObservationProviderCapabilities,
    ObservationProviderDescriptor,
    ObservationProviderHealth,
    ObservationResult,
    VisitProposal,
)


class SnapshotObservationProvider:
    """Run the established bounded snapshot observer through the v2 boundary.

    The wrapped manager remains the owner of its timer and existing product
    handoff. This provider only translates its retained facts for future replay
    or accelerated providers; it never creates a parallel loop or truth path.
    """

    provider_id = "snapshot"
    display_name = "Snapshot Observation Provider"
    capabilities = ObservationProviderCapabilities(
        timer_driven=True,
        emits_frame_packets=True,
        emits_detection_observations=False,
        emits_track_updates=False,
        emits_evidence_candidates=True,
        emits_visit_proposals=True,
    )

    def __init__(self, monitor: SourceMonitorManager) -> None:
        self._monitor = monitor

    async def start(
        self,
        *,
        source_id: str,
        stream_id: str,
        options: SourceMonitorOptions,
        autostart: bool = True,
    ) -> SourceMonitorState:
        return await self._monitor.start(
            source_id=source_id,
            stream_id=stream_id,
            options=options,
            autostart=autostart,
        )

    async def status(self, stream_id: str) -> SourceMonitorState | None:
        return await self._monitor.status(stream_id)

    async def stop(self, stream_id: str) -> SourceMonitorState | None:
        return await self._monitor.stop(stream_id)

    async def reset(self) -> None:
        await self._monitor.reset()

    def cancel_all(self) -> None:
        self._monitor.cancel_all()

    async def mark_review_activity_result(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> SourceMonitorState | None:
        return await self._monitor.mark_review_activity_result(*args, **kwargs)

    async def run_one_tick_for_tests(
        self,
        stream_id: str,
    ) -> SourceMonitorState | None:
        """Preserve the established test-only monitor seam during migration."""

        return await self._monitor.run_one_tick_for_tests(stream_id)

    async def observe_one_tick_for_tests(self, stream_id: str) -> ObservationResult:
        """Exercise the existing test tick and return only provider-neutral facts."""

        state = await self._monitor.run_one_tick_for_tests(stream_id)
        if state is None:
            raise ValueError(f"No snapshot monitor is active for Stream {stream_id}.")
        return self._result_from_state(state)

    async def health(self, *, stream_id: str | None = None) -> ObservationProviderHealth:
        """Read in-memory state only; status never captures or starts monitoring."""

        if stream_id is None:
            return ObservationProviderHealth(
                state="idle",
                healthy=True,
                message="Snapshot provider is ready; monitoring remains explicit.",
            )
        state = await self._monitor.status(stream_id)
        if state is None:
            return ObservationProviderHealth(
                state="idle",
                healthy=True,
                message="No snapshot monitor is active for this Stream.",
            )
        if state.status in {"starting", "monitoring"}:
            return ObservationProviderHealth(
                state="running",
                healthy=state.last_error is None,
                message=state.last_error or "Snapshot monitoring is active.",
                observed_at=state.last_tick_at,
            )
        if state.status == "error":
            return ObservationProviderHealth(
                state="degraded",
                healthy=False,
                message=state.last_error or "Snapshot monitoring stopped after an error.",
                observed_at=state.last_tick_at,
            )
        return ObservationProviderHealth(
            state="stopped",
            healthy=True,
            message="Snapshot monitoring is stopped.",
            observed_at=state.last_tick_at,
        )

    async def describe(
        self,
        *,
        stream_id: str | None = None,
    ) -> ObservationProviderDescriptor:
        return ObservationProviderDescriptor(
            provider_id=self.provider_id,
            display_name=self.display_name,
            capabilities=self.capabilities,
            health=await self.health(stream_id=stream_id),
        )

    def _result_from_state(self, state: SourceMonitorState) -> ObservationResult:
        frame_packets = (
            (
                FramePacket(
                    stream_id=state.stream_id,
                    media_asset_id=state.last_snapshot_media_asset_id,
                    captured_at=state.last_tick_at,
                ),
            )
            if state.last_snapshot_media_asset_id
            else ()
        )
        evidence_ids = tuple(dict.fromkeys(state.last_motion_media_asset_ids))
        if (
            state.last_snapshot_media_asset_id
            and state.last_snapshot_media_asset_id not in evidence_ids
        ):
            evidence_ids = (*evidence_ids, state.last_snapshot_media_asset_id)
        evidence_candidates = tuple(
            EvidenceCandidate(
                media_asset_id=media_asset_id,
                stream_id=state.stream_id,
                role=(
                    "snapshot_best_frame"
                    if media_asset_id == state.best_snapshot_media_asset_id
                    else "snapshot_context"
                ),
                captured_at=state.last_tick_at,
            )
            for media_asset_id in evidence_ids
        )
        proposals = (
            (
                VisitProposal(
                    proposal_key=f"snapshot:{state.monitor_id}:{state.last_tick_at!s}",
                    source_id=state.source_id,
                    stream_id=state.stream_id,
                    evidence_media_asset_ids=evidence_ids,
                    reason="snapshot_motion_activity",
                ),
            )
            if state.review_activity_available and evidence_ids
            else ()
        )
        return ObservationResult(
            provider_id=self.provider_id,
            source_id=state.source_id,
            stream_id=state.stream_id,
            observed_at=state.last_tick_at,
            frame_packets=frame_packets,
            evidence_candidates=evidence_candidates,
            visit_proposals=proposals,
        )
