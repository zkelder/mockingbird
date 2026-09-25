"""`mockingbird.time_utils.resolve_host_local_timezone` (see "DST-correct
local-time bucketing" in docs/place-activity-report-contract.md).

These tests exercise the resolution order deterministically by controlling
the environment/`os.path.realpath`/`tzlocal` inputs -- never by depending on
this sandbox's own ambient host timezone, so they pass identically on any CI
machine regardless of its configured system zone. In particular the
native-Windows path (step 3) is exercised by substituting `tzlocal.
get_localzone_name`, which is exactly the one function that reads the Windows
registry and maps its zone name through CLDR -- this suite runs on Linux and
must still prove the Windows contract.
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from mockingbird.time_utils import resolve_host_local_timezone


def _no_posix_zone(monkeypatch) -> None:
    """Silence both POSIX candidate sources (`TZ`, `/etc/localtime`) so a test
    is genuinely exercising what comes *after* them -- the native-Windows
    shape, where neither exists."""

    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr("os.path.realpath", lambda path: path)


def _no_platform_native_zone(monkeypatch) -> None:
    """Silence step 3 the way a host genuinely unable to name its zone does:
    `tzlocal` raising `ZoneInfoNotFoundError`, which is precisely what it
    raises for a Windows `TimeZoneKeyName` that CLDR does not map."""

    def unresolvable() -> str:
        raise ZoneInfoNotFoundError("no mappable local zone")

    monkeypatch.setattr("tzlocal.get_localzone_name", unresolvable)


def _windows_registry_zone(monkeypatch, iana_name: str) -> None:
    """Stand in for `tzlocal`'s real native-Windows resolution: read
    `HKLM\\...\\TimeZoneInformation` `TimeZoneKeyName` (e.g. "Eastern
    Standard Time") and translate it through the bundled CLDR
    `windowsZones` table to an IANA key. The mapping itself is `tzlocal`'s
    own tested responsibility; what MockingBird owns, and what these tests
    pin, is that the resulting key is actually reached and actually used to
    convert timestamps."""

    _no_posix_zone(monkeypatch)
    monkeypatch.setattr("tzlocal.get_localzone_name", lambda: iana_name)


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
    """When *no* candidate source names a real IANA zone -- neither `TZ`, nor
    `/etc/localtime`, nor the platform-native lookup (a Windows
    `TimeZoneKeyName` CLDR cannot map, or a runtime with no zoneinfo
    database at all) -- the resolver must fall back honestly to a
    fixed-offset snapshot, this product's original, disclosed,
    moment-only-correct behavior, rather than raising and breaking report
    generation outright."""

    _no_posix_zone(monkeypatch)
    _no_platform_native_zone(monkeypatch)

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

    _no_posix_zone(monkeypatch)
    _no_platform_native_zone(monkeypatch)

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


# --------------------------------------------------------------------------
# Native-Windows timezone contract (Native-Windows Field Reliability
# Corrections v1, Blocker 1)
#
# The reproduced field defect at `d5dd1d9`, verbatim from
# docs/field-validation-closure-v1-report.md Q-1:
#
#     resolved tz : Eastern Daylight Time | IANA key: None
#       2026-07-15 16:00 UTC -> 12:00 EDT-0400                (correct)
#       2026-12-15 16:00 UTC -> 12:00 "…Daylight Time-0400"   (WRONG: 11:00 EST)
#
# Every test below asserts a converted *offset or wall-clock value*, never a
# zone abbreviation string: the defect was a wrong instant, and a label that
# merely reads "EST" proves nothing about the arithmetic.
# --------------------------------------------------------------------------


def test_native_windows_registry_zone_name_is_resolved_to_a_real_iana_zone(monkeypatch) -> None:
    """Native Windows supplies neither `TZ` nor `/etc/localtime`, so before
    this milestone *nothing* in the product ever derived an IANA key there and
    every timestamp got one fixed offset. The platform-native candidate must
    now produce a genuine variable-offset `ZoneInfo`."""

    _windows_registry_zone(monkeypatch, "America/New_York")

    resolved = resolve_host_local_timezone()

    assert resolved == ZoneInfo("America/New_York")
    assert not isinstance(resolved, timezone)  # not the fixed-offset fallback


def test_native_windows_renders_the_reproduced_december_instant_as_standard_time(monkeypatch) -> None:
    """The exact reproduced field case. 2026-12-15 16:00 UTC is 11:00 EST
    (UTC-5), not the 12:00 the fixed-offset fallback produced."""

    _windows_registry_zone(monkeypatch, "America/New_York")

    resolved = resolve_host_local_timezone()
    local = datetime(2026, 12, 15, 16, 0, tzinfo=UTC).astimezone(resolved)

    assert (local.hour, local.minute) == (11, 0)
    assert local.utcoffset() == timedelta(hours=-5)
    assert local.dst() == timedelta(0)


def test_native_windows_renders_a_summer_instant_as_daylight_time(monkeypatch) -> None:
    """The other half of the same proof: the summer instant the broken
    fallback happened to get right must still be right."""

    _windows_registry_zone(monkeypatch, "America/New_York")

    resolved = resolve_host_local_timezone()
    local = datetime(2026, 7, 15, 16, 0, tzinfo=UTC).astimezone(resolved)

    assert (local.hour, local.minute) == (12, 0)
    assert local.utcoffset() == timedelta(hours=-4)
    assert local.dst() == timedelta(hours=1)


def test_native_windows_one_resolved_zone_serves_both_seasons_correctly(monkeypatch) -> None:
    """The defect's real shape was not "one wrong timestamp" but "one offset
    sampled once, reused for a whole range." A single resolved zone object
    -- the one an analytics surface resolves once and then applies across a
    year of Visits -- must give each instant its own correct offset."""

    _windows_registry_zone(monkeypatch, "America/New_York")

    resolved = resolve_host_local_timezone()

    winter = datetime(2026, 1, 15, 16, 0, tzinfo=UTC).astimezone(resolved)
    summer = datetime(2026, 7, 15, 16, 0, tzinfo=UTC).astimezone(resolved)
    assert winter.hour == 11
    assert summer.hour == 12
    assert winter.utcoffset() != summer.utcoffset()


def test_native_windows_spring_dst_transition_is_correct_on_both_sides(monkeypatch) -> None:
    """2026 US spring-forward: 2026-03-08 07:00 UTC is 02:00 EST, and one
    second later local time jumps to 03:00 EDT."""

    _windows_registry_zone(monkeypatch, "America/New_York")

    resolved = resolve_host_local_timezone()

    before = datetime(2026, 3, 8, 6, 59, 59, tzinfo=UTC).astimezone(resolved)
    after = datetime(2026, 3, 8, 7, 0, 0, tzinfo=UTC).astimezone(resolved)
    assert (before.hour, before.minute, before.second) == (1, 59, 59)
    assert before.utcoffset() == timedelta(hours=-5)
    assert (after.hour, after.minute, after.second) == (3, 0, 0)
    assert after.utcoffset() == timedelta(hours=-4)


def test_native_windows_fall_dst_transition_is_correct_on_both_sides(monkeypatch) -> None:
    """2026 US fall-back: 2026-11-01 05:59:59 UTC is 01:59:59 EDT and
    2026-11-01 06:00:00 UTC is 01:00:00 EST -- the repeated local hour, which
    a fixed offset renders as a single monotonic 02:00 and therefore
    mis-buckets."""

    _windows_registry_zone(monkeypatch, "America/New_York")

    resolved = resolve_host_local_timezone()

    before = datetime(2026, 11, 1, 5, 59, 59, tzinfo=UTC).astimezone(resolved)
    after = datetime(2026, 11, 1, 6, 0, 0, tzinfo=UTC).astimezone(resolved)
    assert (before.hour, before.minute) == (1, 59)
    assert before.utcoffset() == timedelta(hours=-4)
    assert (after.hour, after.minute) == (1, 0)
    assert after.utcoffset() == timedelta(hours=-5)
    # Both really are the repeated local hour. Note that subtracting two
    # aware datetimes sharing one `tzinfo` is wall-clock arithmetic, so the
    # "one second apart" fact has to be asserted on the UTC instants -- the
    # ambiguity these two wall-clock readings carry is exactly why stored
    # truth stays UTC (see docs/field-validation-closure-v1-report.md N).
    assert before.hour == after.hour
    assert after.astimezone(UTC) - before.astimezone(UTC) == timedelta(seconds=1)
    assert after.fold == 1 and before.fold == 0


def test_native_windows_utc_zone_resolves_with_a_zero_offset_year_round(monkeypatch) -> None:
    """A Windows Host set to "UTC" maps to `Etc/UTC`; it must convert with a
    zero offset in both seasons and never acquire a DST shift."""

    _windows_registry_zone(monkeypatch, "Etc/UTC")

    resolved = resolve_host_local_timezone()

    for moment in (datetime(2026, 1, 15, 16, 0, tzinfo=UTC), datetime(2026, 7, 15, 16, 0, tzinfo=UTC)):
        local = moment.astimezone(resolved)
        assert local.hour == 16
        assert local.utcoffset() == timedelta(0)
        assert local.dst() == timedelta(0)


@pytest.mark.parametrize(
    ("iana_name", "expected_offset"),
    [
        ("America/Phoenix", timedelta(hours=-7)),  # "US Mountain Standard Time"
        ("Asia/Kolkata", timedelta(hours=5, minutes=30)),  # "India Standard Time", half-hour offset
    ],
)
def test_native_windows_non_dst_zone_has_one_offset_in_both_seasons(
    monkeypatch, iana_name: str, expected_offset: timedelta
) -> None:
    """A genuinely DST-free zone must resolve to the *same* offset in winter
    and summer -- the correct answer here happens to match what the old
    fixed-offset fallback produced, and this pins that the fix did not
    introduce a spurious seasonal shift where none exists."""

    _windows_registry_zone(monkeypatch, iana_name)

    resolved = resolve_host_local_timezone()

    winter = datetime(2026, 1, 15, 16, 0, tzinfo=UTC).astimezone(resolved)
    summer = datetime(2026, 7, 15, 16, 0, tzinfo=UTC).astimezone(resolved)
    assert winter.utcoffset() == expected_offset
    assert summer.utcoffset() == expected_offset
    assert winter.dst() == timedelta(0)
    assert summer.dst() == timedelta(0)


def test_southern_hemisphere_dst_runs_the_opposite_way(monkeypatch) -> None:
    """Guards against "winter means standard time" being baked in anywhere:
    Australia/Sydney is on daylight time in January and standard time in
    July."""

    _windows_registry_zone(monkeypatch, "Australia/Sydney")

    resolved = resolve_host_local_timezone()

    january = datetime(2026, 1, 15, 2, 0, tzinfo=UTC).astimezone(resolved)
    july = datetime(2026, 7, 15, 2, 0, tzinfo=UTC).astimezone(resolved)
    assert january.utcoffset() == timedelta(hours=11)
    assert january.dst() == timedelta(hours=1)
    assert july.utcoffset() == timedelta(hours=10)
    assert july.dst() == timedelta(0)


def test_unmappable_windows_zone_falls_back_without_raising(monkeypatch) -> None:
    """`tzlocal` raises `ZoneInfoNotFoundError` for a `TimeZoneKeyName` CLDR
    has no entry for. That must degrade to the honest fixed-offset snapshot,
    exactly as before this milestone -- never propagate and break report
    generation."""

    _no_posix_zone(monkeypatch)
    _no_platform_native_zone(monkeypatch)

    resolved = resolve_host_local_timezone(now=datetime(2026, 12, 15, 16, 0, tzinfo=UTC))

    assert isinstance(resolved, timezone)


def test_platform_native_lookup_raising_any_error_is_non_fatal(monkeypatch) -> None:
    """The Windows registry read can fail in ways that are not
    `ZoneInfoNotFoundError` (a permissions `OSError`, `tzlocal`'s own
    `LookupError` on a configuration it cannot interpret). None of them may
    escape a resolver documented as never raising."""

    _no_posix_zone(monkeypatch)

    for error in (OSError("registry unavailable"), LookupError("no timezone configuration")):

        def failing(_error=error) -> str:
            raise _error

        monkeypatch.setattr("tzlocal.get_localzone_name", failing)
        assert isinstance(resolve_host_local_timezone(), (timezone, ZoneInfo))


def test_absent_tzlocal_dependency_falls_back_instead_of_crashing(monkeypatch) -> None:
    """`tzlocal` is a declared core dependency, but a source install that
    skipped it (or a stripped runtime) must still resolve *something* rather
    than raise `ModuleNotFoundError` out of every analytics surface."""

    _no_posix_zone(monkeypatch)
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "tzlocal" or name.startswith("tzlocal."):
            raise ModuleNotFoundError("No module named 'tzlocal'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    resolved = resolve_host_local_timezone(now=datetime(2026, 12, 15, 16, 0, tzinfo=UTC))

    assert isinstance(resolved, timezone)


def test_posix_etc_localtime_still_wins_over_the_platform_native_lookup(monkeypatch) -> None:
    """Ordering guard: the platform-native candidate is appended *after* the
    two existing POSIX sources, so no Linux/macOS deployment's resolution can
    change behavior because this milestone added step 3."""

    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr(
        "os.path.realpath",
        lambda path: "/usr/share/zoneinfo/Europe/Berlin" if path == "/etc/localtime" else path,
    )
    monkeypatch.setattr("tzlocal.get_localzone_name", lambda: "Asia/Tokyo")

    assert resolve_host_local_timezone() == ZoneInfo("Europe/Berlin")


def test_tz_environment_variable_still_wins_over_the_platform_native_lookup(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "America/Chicago")
    monkeypatch.setattr("tzlocal.get_localzone_name", lambda: "Asia/Tokyo")

    assert resolve_host_local_timezone() == ZoneInfo("America/Chicago")


def test_blank_platform_native_name_is_ignored(monkeypatch) -> None:
    """Defensive: a whitespace-only or empty name must never be handed to
    `ZoneInfo` as if it were a real key."""

    _no_posix_zone(monkeypatch)
    monkeypatch.setattr("tzlocal.get_localzone_name", lambda: "   ")

    assert isinstance(resolve_host_local_timezone(now=datetime(2026, 12, 15, 16, 0, tzinfo=UTC)), timezone)
