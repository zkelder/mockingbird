"""Shared UTC normalization and local-timezone resolution for reporting.

The normalization helpers below are for persisted operational timestamps.
`resolve_host_local_timezone` is a separate, small concern -- discovering
this single-site install's actual local IANA timezone (for example
"America/New_York") -- kept in this same dependency-free module because
every analytics surface that needs "local time" already imports this module
for UTC normalization (see `mockingbird.repository.product_repository`).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, tzinfo
from typing import Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def resolve_host_local_timezone(now: datetime | None = None) -> tzinfo:
    """Best-effort resolution of this host's actual IANA-named local timezone
    (for example ``ZoneInfo("America/New_York")``), so a caller converting
    many timestamps spread across a date range gets the historically-correct
    UTC offset applied at *each* individual timestamp -- not one fixed
    offset resolved once from a single moment and reused for the whole
    range. See "Local time and DST correctness" in
    docs/place-activity-report-contract.md, which this exists for.

    MockingBird has no per-Place timezone setting (product-doctrine.md:
    single-site, local-first), so "local" is inferred from the host
    environment. Resolution order:

    1. The `TZ` environment variable, if it names a real IANA zone.
    2. The `/etc/localtime` symlink target, if this host is POSIX and its
       system zoneinfo database resolves it to a real IANA zone (the
       standard Linux/macOS convention; this sandbox and any Linux/macOS
       deployment satisfy it today).
    3. A fixed-offset snapshot of the host's current local UTC offset --
       this product's original behavior, correct only for the supplied (or
       current) instant, not across a range that spans a DST transition.
       This is the only path a plain Windows host without the optional
       `tzdata` package can reach, since `zoneinfo` needs a system or
       `tzdata`-provided database to resolve an IANA key, and Windows does
       not name its local zone in IANA terms without one. It is a disclosed,
       honest degradation -- identical to this product's pre-existing
       behavior on such a host, never a crash and never an invented number.

    This never raises.
    """

    for candidate in _host_iana_zone_name_candidates():
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    reference = now if now is not None else datetime.now()
    return reference.astimezone().tzinfo


def _host_iana_zone_name_candidates() -> Iterator[str]:
    """Yield candidate IANA zone keys to try, most-authoritative first.
    Never raises; a candidate that later fails to construct a `ZoneInfo` is
    simply skipped by the caller."""

    env_tz = os.environ.get("TZ", "").strip()
    if env_tz:
        yield env_tz

    try:
        resolved = os.path.realpath("/etc/localtime")
    except OSError:
        return
    marker = "zoneinfo/"
    index = resolved.rfind(marker)
    if index != -1:
        yield resolved[index + len(marker) :]
