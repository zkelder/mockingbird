"""In-memory latest-frame cache for active live stream requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


DEFAULT_MAX_AGE_SECONDS = 10.0


@dataclass(frozen=True)
class LiveFrame:
    stream_id: str
    frame_bytes: bytes
    content_type: str
    captured_at: datetime

    def age_ms(self, now: datetime | None = None) -> int:
        reference = now or datetime.now(UTC)
        return max(0, int((reference - self.captured_at).total_seconds() * 1000))


_LATEST_FRAMES: dict[str, LiveFrame] = {}


def store_latest_frame(
    stream_id: str,
    frame_bytes: bytes,
    *,
    content_type: str = "image/jpeg",
    captured_at: datetime | None = None,
) -> LiveFrame:
    frame = LiveFrame(
        stream_id=stream_id,
        frame_bytes=frame_bytes,
        content_type=content_type,
        captured_at=captured_at or datetime.now(UTC),
    )
    _LATEST_FRAMES[stream_id] = frame
    return frame


def get_latest_frame(
    stream_id: str,
    *,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> LiveFrame | None:
    frame = _LATEST_FRAMES.get(stream_id)
    if frame is None:
        return None
    reference = now or datetime.now(UTC)
    if (reference - frame.captured_at).total_seconds() > max_age_seconds:
        return None
    return frame


def clear_latest_frame(stream_id: str) -> None:
    _LATEST_FRAMES.pop(stream_id, None)


def clear_all_frames() -> None:
    _LATEST_FRAMES.clear()


__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "LiveFrame",
    "clear_all_frames",
    "clear_latest_frame",
    "get_latest_frame",
    "store_latest_frame",
]
