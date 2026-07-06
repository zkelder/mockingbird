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
    "clear_all_frames",
    "clear_latest_frame",
    "get_recent_frames",
    "get_latest_frame",
    "iter_cached_stream_ids",
    "store_latest_frame",
]
