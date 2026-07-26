"""Shared UTC normalization for persisted operational timestamps."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the canonical timezone-aware clock value for runtime writes."""

    return datetime.now(UTC)


def normalize_utc(value: datetime) -> datetime:
    """Return an aware UTC timestamp, treating legacy naive persisted values as UTC."""

    if not isinstance(value, datetime):
        raise ValueError("timestamp_invalid")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_optional_utc(value: datetime | None) -> datetime | None:
    """Normalize an optional persisted timestamp without changing an absent value."""

    return normalize_utc(value) if value is not None else None
