"""Explicit selection of the current Observation Engine provider."""

from __future__ import annotations

from collections.abc import Sequence

from mockingbird.observation.contracts import (
    ObservationEngineStatus,
    ObservationProvider,
)


class ObservationEngineRegistry:
    """A small registry keeps future providers out of product truth objects."""

    def __init__(
        self,
        providers: Sequence[ObservationProvider],
        *,
        active_provider_id: str | None = None,
    ) -> None:
        by_id = {provider.provider_id: provider for provider in providers}
        if not by_id:
            raise ValueError("Observation Engine needs one provider.")
        if len(by_id) != len(providers):
            raise ValueError("Observation Engine provider ids must be unique.")
        active_id = active_provider_id or next(iter(by_id))
        if active_id not in by_id:
            raise ValueError(f"Unknown Observation Engine provider: {active_id}")
        self._providers = by_id

        self._active_provider_id = active_id

    @property
    def active_provider_id(self) -> str:
        return self._active_provider_id

    def provider_for(self, provider_id: str) -> ObservationProvider:
        if provider_id not in self._providers:
            raise ValueError(f"Unknown Observation Engine provider: {provider_id}")
        return self._providers[provider_id]

    @property
    def active_provider(self) -> ObservationProvider:
        return self._providers[self._active_provider_id]

    async def status(self, *, stream_id: str | None = None) -> ObservationEngineStatus:
        provider = self.active_provider
        return ObservationEngineStatus(
            active_provider_id=provider.provider_id,
            provider=await provider.describe(stream_id=stream_id),
        )
