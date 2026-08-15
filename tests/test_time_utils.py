"""`mockingbird.time_utils.resolve_host_local_timezone` (see "DST-correct
local-time bucketing" in docs/place-activity-report-contract.md).

These tests exercise the resolution order deterministically by controlling
the environment/`os.path.realpath` inputs -- never by depending on this
sandbox's own ambient host timezone, so they pass identically on any CI
machine regardless of its configured system zone.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from mockingbird.time_utils import resolve_host_local_timezone


def test_tz_environment_variable_is_used_when_it_names_a_real_zone(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "America/Chicago")

    resolved = resolve_host_local_timezone()

    assert resolved == ZoneInfo("America/Chicago")


def test_tz_environment_variable_wins_over_etc_localtime(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    monkeypatch.setattr(
        "os.path.realpath",
        lambda path: "/usr/share/zoneinfo/America/Chicago" if path == "/etc/localtime" else path,
    )

    resolved = resolve_host_local_timezone()

    assert resolved == ZoneInfo("Asia/Tokyo")


def test_invalid_tz_environment_variable_falls_through_to_etc_localtime(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "not_a_real_zone_key")
    monkeypatch.setattr(
        "os.path.realpath",
        lambda path: "/usr/share/zoneinfo/Europe/Berlin" if path == "/etc/localtime" else path,
    )

    resolved = resolve_host_local_timezone()

    assert resolved == ZoneInfo("Europe/Berlin")


def test_etc_localtime_symlink_target_is_parsed_for_the_iana_key(monkeypatch) -> None:
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr(
        "os.path.realpath",
        lambda path: "/usr/share/zoneinfo/Pacific/Auckland" if path == "/etc/localtime" else path,
    )

    resolved = resolve_host_local_timezone()

    assert resolved == ZoneInfo("Pacific/Auckland")


def test_no_discoverable_iana_zone_falls_back_to_a_fixed_offset_snapshot(monkeypatch) -> None:
    """When neither `TZ` nor `/etc/localtime` names a real IANA zone (for
    example a plain Windows host with no `tzdata` package installed), the
    resolver must fall back honestly to a fixed-offset snapshot -- this
    product's original, disclosed, moment-only-correct behavior -- rather
    than raising and breaking report generation outright."""

    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr("os.path.realpath", lambda path: path)  # no symlink resolution at all

    winter_now = datetime(2026, 1, 15, 17, 0, tzinfo=UTC)  # noon EST if the host were US Eastern
    resolved = resolve_host_local_timezone(now=winter_now)

    # A fixed-offset `datetime.timezone`, matching the pre-existing
    # behavior's own type -- never raises, never a variable-offset zone it
    # could not actually discover.
    assert isinstance(resolved, timezone)
    # Deterministic: driven by the supplied `now`, not real wall-clock time.
    local_now = winter_now.astimezone(resolved)
    assert local_now.utcoffset() == winter_now.astimezone().utcoffset()


def test_fallback_offset_is_deterministic_from_the_supplied_now(monkeypatch) -> None:
    """The fallback path must be reproducible in tests: two calls with the
    same explicit `now` must resolve to the same fixed offset, regardless
    of when the test itself actually runs."""

    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr("os.path.realpath", lambda path: path)

    moment = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    first = resolve_host_local_timezone(now=moment)
    second = resolve_host_local_timezone(now=moment)

    assert moment.astimezone(first).utcoffset() == moment.astimezone(second).utcoffset()


def test_resolved_zone_is_dst_correct_across_a_transition(monkeypatch) -> None:
    """The whole point of this helper: unlike a fixed offset, the resolved
    zone must apply the historically-correct offset independently at two
    different timestamps that straddle a real DST transition."""

    monkeypatch.setenv("TZ", "America/New_York")

    resolved = resolve_host_local_timezone()

    before_spring_forward = datetime(2026, 3, 8, 6, 30, tzinfo=UTC)
    after_spring_forward = datetime(2026, 3, 8, 8, 30, tzinfo=UTC)
    assert before_spring_forward.astimezone(resolved).utcoffset() == timedelta(hours=-5)
    assert after_spring_forward.astimezone(resolved).utcoffset() == timedelta(hours=-4)


@pytest.mark.parametrize("bad_tz", ["", "   "])
def test_blank_tz_environment_variable_is_ignored(monkeypatch, bad_tz: str) -> None:
    monkeypatch.setenv("TZ", bad_tz)
    monkeypatch.setattr(
        "os.path.realpath",
        lambda path: "/usr/share/zoneinfo/America/Denver" if path == "/etc/localtime" else path,
    )

    resolved = resolve_host_local_timezone()

    assert resolved == ZoneInfo("America/Denver")
