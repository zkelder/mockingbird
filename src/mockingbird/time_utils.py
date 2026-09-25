"""Shared UTC normalization and local-timezone resolution for reporting.

The normalization helpers below are for persisted operational timestamps.
`resolve_host_local_timezone` is a separate, small concern -- discovering
this single-site install's actual local IANA timezone (for example
"America/New_York") -- kept in this same module because every analytics
surface that needs "local time" already imports this module for UTC
normalization (see `mockingbird.repository.product_repository`).
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
    3. `tzlocal.get_localzone_name()` -- the platform-native lookup, and on
       native Windows the *only* path that can produce an IANA key at all:
       Windows names its zone in its own vocabulary
       (`HKLM\\SYSTEM\\CurrentControlSet\\Control\\TimeZoneInformation`
       `TimeZoneKeyName`, e.g. "Eastern Standard Time"), which `tzlocal`
       translates through the CLDR `windowsZones` mapping it bundles. This
       is deliberately an established mapping mechanism rather than a
       hand-maintained table in this repository (see
       docs/native-windows-field-reliability-corrections-v1-contract.md,
       "Windows timezone contract"). `tzdata` is packaged alongside it for
       native Windows, which has no system zoneinfo database for `ZoneInfo`
       to read.
    4. A fixed-offset snapshot of the host's current local UTC offset --
       this product's original behavior, correct only for the supplied (or
       current) instant, not across a range that spans a DST transition.
       Reached only when every named-zone path above fails (for example a
       Windows zone CLDR does not map, or a runtime with neither `tzlocal`
       nor any zoneinfo database installed). It is a disclosed, honest
       degradation -- never a crash and never an invented number.

    Native Windows reached step 4 for every timestamp before *Native-Windows
    Field Reliability Corrections v1*, which is exactly why a December
    instant rendered with a June DST offset; step 3 closes that.

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

    yield from _etc_localtime_zone_name_candidates()
    yield from _platform_native_zone_name_candidates()


def _etc_localtime_zone_name_candidates() -> Iterator[str]:
    """The POSIX `/etc/localtime` symlink convention. Its own generator so a
    host where this path is absent or unreadable (native Windows) still
    reaches the platform-native lookup below -- an earlier version returned
    from the shared generator here, which silently made every later
    candidate unreachable."""

    try:
        resolved = os.path.realpath("/etc/localtime")
    except OSError:
        return
    marker = "zoneinfo/"
    index = resolved.rfind(marker)
    if index != -1:
        yield resolved[index + len(marker) :]


def _platform_native_zone_name_candidates() -> Iterator[str]:
    """`tzlocal`'s platform-native resolution, wrapped so this module keeps
    its "never raises" contract even if `tzlocal` is absent (a minimal
    install) or its own lookup fails (`ZoneInfoNotFoundError`, a registry
    `OSError`, or the `LookupError` it raises on an unrecognizable Windows
    configuration). On native Windows this is the registry ->
    CLDR `windowsZones` -> IANA path; on POSIX it is a redundant
    confirmation of the two candidates above, which is why it is tried
    last and never changes existing Linux/macOS behavior."""

    try:
        from tzlocal import get_localzone_name
    except Exception:  # noqa: BLE001 - an optional dependency must never break resolution
        return
    try:
        name = get_localzone_name()
    except Exception:  # noqa: BLE001 - see docstring: every documented failure mode is non-fatal here
        return
    if isinstance(name, str) and name.strip():
        yield name.strip()
