"""Bounded, in-memory ownership for explicit overview live previews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import threading
from collections.abc import Callable

from mockingbird.monitoring.durable_supervisor import DEFAULT_MAX_CONCURRENT_STREAMS


DEFAULT_MAX_PREVIEWS_PER_OWNER = 4
# Backend previews share the host-level camera-session budget with durable
# monitors; a browser tile can never silently exceed that local capacity.
DEFAULT_MAX_BACKEND_PREVIEW_STREAMS = DEFAULT_MAX_CONCURRENT_STREAMS
DEFAULT_LEASE_SECONDS = 90


@dataclass(frozen=True)
class LivePreviewLease:
    owner_id: str
    stream_id: str
    expires_at: datetime


@dataclass(frozen=True)
class LivePreviewLeaseDecision:
    status: str
    lease: LivePreviewLease | None
    should_start_session: bool = False
    effective_limit: int = DEFAULT_MAX_PREVIEWS_PER_OWNER
    message: str = ""


@dataclass(frozen=True)
class LivePreviewLeaseRelease:
    released: bool
    should_stop_session: bool = False


class LivePreviewLeaseManager:
    """Tracks explicit browser-owned previews without owning monitoring policy.

    A lease exists only in the current app process. Its timer is solely a safety
    release for a departed browser; it never evaluates media or changes durable
    monitoring intent.
    """

    def __init__(
        self,
        *,
        on_expired_stream: Callable[[str], None] | None = None,
        clock: Callable[[], datetime] | None = None,
        max_previews_per_owner: int = DEFAULT_MAX_PREVIEWS_PER_OWNER,
        max_backend_preview_streams: int = DEFAULT_MAX_BACKEND_PREVIEW_STREAMS,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> None:
        if max_previews_per_owner < 1 or max_backend_preview_streams < 1:
            raise ValueError("preview_limits_must_be_positive")
        if lease_seconds < 1:
            raise ValueError("preview_lease_seconds_must_be_positive")
        self._on_expired_stream = on_expired_stream
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_previews_per_owner = max_previews_per_owner
        self._max_backend_preview_streams = max_backend_preview_streams
        self._lease_seconds = lease_seconds
        self._leases: dict[tuple[str, str], LivePreviewLease] = {}
        self._overview_started_streams: set[str] = set()
        self._timers: dict[tuple[str, str], threading.Timer] = {}
        self._lock = threading.RLock()

    @property
    def max_previews_per_owner(self) -> int:
        return self._max_previews_per_owner

    @property
    def max_backend_preview_streams(self) -> int:
        return self._max_backend_preview_streams

    def acquire(
        self,
        *,
        owner_id: str,
        stream_id: str,
        backend_session_active: bool,
    ) -> LivePreviewLeaseDecision:
        """Reserve one preview tile, idempotently, before opening a camera session."""

        expired_streams: set[str] = set()
        with self._lock:
            expired_streams = self._expire_locked(self._clock())
            key = (owner_id, stream_id)
            existing = self._leases.get(key)
            if existing is not None:
                lease = self._refresh_locked(existing)
                decision = LivePreviewLeaseDecision(
                    status="live",
                    lease=lease,
                    effective_limit=self._effective_limit(backend_session_active),
                    message="Live preview is already active for this camera.",
                )
            else:
                owner_count = sum(1 for candidate in self._leases.values() if candidate.owner_id == owner_id)
                if owner_count >= self._max_previews_per_owner:
                    decision = LivePreviewLeaseDecision(
                        status="limit_reached",
                        lease=None,
                        effective_limit=self._max_previews_per_owner,
                        message="Live preview limit reached. Stop another live view before opening this one.",
                    )
                else:
                    stream_is_overview_owned = stream_id in self._overview_started_streams
                    needs_backend_slot = not backend_session_active and not stream_is_overview_owned
                    if (
                        needs_backend_slot
                        and len(self._overview_started_streams)
                        >= self._max_backend_preview_streams
                    ):
                        decision = LivePreviewLeaseDecision(
                            status="limit_reached",
                            lease=None,
                            effective_limit=min(
                                self._max_previews_per_owner,
                                self._max_backend_preview_streams,
                            ),
                            message="Live preview limit reached. This computer has no remaining local preview capacity.",
                        )
                    else:
                        if needs_backend_slot:
                            # Reserve the slot before process startup so concurrent requests
                            # cannot exceed the local camera-session budget.
                            self._overview_started_streams.add(stream_id)
                        lease = LivePreviewLease(
                            owner_id=owner_id,
                            stream_id=stream_id,
                            expires_at=self._clock() + timedelta(seconds=self._lease_seconds),
                        )
                        self._leases[key] = lease
                        self._schedule_locked(lease)
                        decision = LivePreviewLeaseDecision(
                            status="live",
                            lease=lease,
                            should_start_session=needs_backend_slot,
                            effective_limit=self._effective_limit(backend_session_active),
                            message="Live preview is connecting.",
                        )
        self._notify_expired(expired_streams)
        return decision

    def release(self, *, owner_id: str, stream_id: str) -> LivePreviewLeaseRelease:
        """Release one owner tile and report whether its overview session may stop."""

        expired_streams: set[str] = set()
        with self._lock:
            expired_streams = self._expire_locked(self._clock())
            key = (owner_id, stream_id)
            released = key in self._leases
            should_stop = self._release_locked(key)
        self._notify_expired(expired_streams)
        return LivePreviewLeaseRelease(
            released=released,
            should_stop_session=should_stop,
        )

    def abandon(self, *, owner_id: str, stream_id: str) -> None:
        """Undo a reservation when an on-demand backend session could not start."""

        with self._lock:
            self._release_locked((owner_id, stream_id))

    def shutdown(self) -> None:
        """Cancel lease timers; app shutdown owns the actual camera stop ordering."""

        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            self._leases.clear()
            self._overview_started_streams.clear()

    def _effective_limit(self, backend_session_active: bool) -> int:
        if backend_session_active:
            return self._max_previews_per_owner
        return min(self._max_previews_per_owner, self._max_backend_preview_streams)

    def _refresh_locked(self, lease: LivePreviewLease) -> LivePreviewLease:
        refreshed = LivePreviewLease(
            owner_id=lease.owner_id,
            stream_id=lease.stream_id,
            expires_at=self._clock() + timedelta(seconds=self._lease_seconds),
        )
        self._leases[(lease.owner_id, lease.stream_id)] = refreshed
        self._schedule_locked(refreshed)
        return refreshed

    def _schedule_locked(self, lease: LivePreviewLease) -> None:
        key = (lease.owner_id, lease.stream_id)
        previous = self._timers.pop(key, None)
        if previous is not None:
            previous.cancel()
        delay = max(0.01, (lease.expires_at - self._clock()).total_seconds())
        timer = threading.Timer(
            delay,
            self._expire_lease,
            args=(lease.owner_id, lease.stream_id, lease.expires_at),
        )
        timer.daemon = True
        self._timers[key] = timer
        timer.start()

    def _expire_lease(self, owner_id: str, stream_id: str, expires_at: datetime) -> None:
        with self._lock:
            lease = self._leases.get((owner_id, stream_id))
            if lease is None or lease.expires_at != expires_at or lease.expires_at > self._clock():
                return
            should_stop = self._release_locked((owner_id, stream_id))
        if should_stop:
            self._notify_expired({stream_id})

    def _expire_locked(self, now: datetime) -> set[str]:
        streams_to_stop: set[str] = set()
        for key, lease in tuple(self._leases.items()):
            if lease.expires_at <= now and self._release_locked(key):
                streams_to_stop.add(lease.stream_id)
        return streams_to_stop

    def _release_locked(self, key: tuple[str, str]) -> bool:
        lease = self._leases.pop(key, None)
        timer = self._timers.pop(key, None)
        if timer is not None:
            timer.cancel()
        if lease is None:
            return False
        has_other_owner = any(candidate.stream_id == lease.stream_id for candidate in self._leases.values())
        if has_other_owner or lease.stream_id not in self._overview_started_streams:
            return False
        self._overview_started_streams.discard(lease.stream_id)
        return True

    def _notify_expired(self, stream_ids: set[str]) -> None:
        if self._on_expired_stream is None:
            return
        for stream_id in stream_ids:
            try:
                self._on_expired_stream(stream_id)
            except Exception:
                # Cleanup must not make an unrelated summary or preview request fail.
                continue


__all__ = [
    "DEFAULT_LEASE_SECONDS",
    "DEFAULT_MAX_BACKEND_PREVIEW_STREAMS",
    "DEFAULT_MAX_PREVIEWS_PER_OWNER",
    "LivePreviewLease",
    "LivePreviewLeaseDecision",
    "LivePreviewLeaseRelease",
    "LivePreviewLeaseManager",
]
