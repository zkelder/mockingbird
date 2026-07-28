"""In-memory frame cache for active live stream requests."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime


DEFAULT_MAX_AGE_SECONDS = 10.0
DEFAULT_RECENT_MAX_AGE_SECONDS = 20.0
DEFAULT_MAX_FRAMES = 20


@dataclass(frozen=True)
class LiveFrame:
    stream_id: str
    frame_bytes: bytes
    content_type: str
    captured_at: datetime
    sequence: int

    def age_ms(self, now: datetime | None = None) -> int:
        reference = now or datetime.now(UTC)
        return max(0, int((reference - self.captured_at).total_seconds() * 1000))


@dataclass(frozen=True)
class LiveFrameCacheStatus:
    stream_id: str
    recent_frame_count: int
    newest_frame_age_ms: int | None
    oldest_frame_age_ms: int | None
    newest_frame_sequence: int | None
    buffer_capacity: int
    fresh_enough: bool
    last_frame_at: datetime | None


_RECENT_FRAMES: dict[str, deque[LiveFrame]] = {}
_NEXT_SEQUENCE: dict[str, int] = {}


def store_latest_frame(
    stream_id: str,
    frame_bytes: bytes,
    *,
    content_type: str = "image/jpeg",
    captured_at: datetime | None = None,
) -> LiveFrame:
    sequence = _NEXT_SEQUENCE.get(stream_id, 0) + 1
    _NEXT_SEQUENCE[stream_id] = sequence
    frame = LiveFrame(
        stream_id=stream_id,
        frame_bytes=frame_bytes,
        content_type=content_type,
        captured_at=captured_at or datetime.now(UTC),
        sequence=sequence,
    )
    frames = _RECENT_FRAMES.setdefault(stream_id, deque(maxlen=DEFAULT_MAX_FRAMES))
    frames.append(frame)
    return frame


def get_latest_frame(
    stream_id: str,
    *,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> LiveFrame | None:
    frames = _RECENT_FRAMES.get(stream_id)
    frame = frames[-1] if frames else None
    if frame is None:
        return None
    reference = now or datetime.now(UTC)
    if (reference - frame.captured_at).total_seconds() > max_age_seconds:
        return None
    return frame


def get_last_frame(stream_id: str) -> LiveFrame | None:
    """Return the latest cached frame even when it is stale.

    The current-frame viewer must present a stale image honestly instead of
    pretending there is no recent camera context. It remains an in-memory,
    read-only cache lookup; callers still require an active session before
    exposing the frame.
    """

    frames = _RECENT_FRAMES.get(stream_id)
    return frames[-1] if frames else None


def get_recent_frames(
    stream_id: str,
    *,
    max_age_seconds: float = DEFAULT_RECENT_MAX_AGE_SECONDS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    now: datetime | None = None,
) -> list[LiveFrame]:
    frames = _RECENT_FRAMES.get(stream_id)
    if not frames:
        return []
    reference = now or datetime.now(UTC)
    fresh_frames = [
        frame
        for frame in frames
        if (reference - frame.captured_at).total_seconds() <= max_age_seconds
    ]
    return fresh_frames[-max_frames:]


def get_cache_status(
    stream_id: str,
    *,
    max_age_seconds: float = DEFAULT_RECENT_MAX_AGE_SECONDS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    now: datetime | None = None,
) -> LiveFrameCacheStatus:
    frames = _RECENT_FRAMES.get(stream_id)
    reference = now or datetime.now(UTC)
    if not frames:
        return LiveFrameCacheStatus(
            stream_id=stream_id,
            recent_frame_count=0,
            newest_frame_age_ms=None,
            oldest_frame_age_ms=None,
            newest_frame_sequence=None,
            buffer_capacity=max_frames,
            fresh_enough=False,
            last_frame_at=None,
        )

    cached_frames = list(frames)[-max_frames:]
    fresh_frames = [
        frame
        for frame in cached_frames
        if (reference - frame.captured_at).total_seconds() <= max_age_seconds
    ]
    newest_frame = cached_frames[-1]
    oldest_frame = cached_frames[0]
    return LiveFrameCacheStatus(
        stream_id=stream_id,
        recent_frame_count=len(fresh_frames),
        newest_frame_age_ms=newest_frame.age_ms(reference),
        oldest_frame_age_ms=oldest_frame.age_ms(reference),
        newest_frame_sequence=newest_frame.sequence,
        buffer_capacity=max_frames,
        fresh_enough=len(fresh_frames) >= 2,
        last_frame_at=newest_frame.captured_at,
    )


def iter_cached_stream_ids() -> Iterable[str]:
    return _RECENT_FRAMES.keys()


def clear_latest_frame(stream_id: str) -> None:
    _RECENT_FRAMES.pop(stream_id, None)
    _NEXT_SEQUENCE.pop(stream_id, None)


def clear_all_frames() -> None:
    _RECENT_FRAMES.clear()
    _NEXT_SEQUENCE.clear()


__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "DEFAULT_MAX_FRAMES",
    "DEFAULT_RECENT_MAX_AGE_SECONDS",
    "LiveFrame",
    "LiveFrameCacheStatus",
    "clear_all_frames",
    "clear_latest_frame",
    "get_cache_status",
    "get_recent_frames",
    "get_latest_frame",
    "get_last_frame",
    "iter_cached_stream_ids",
    "store_latest_frame",
]
