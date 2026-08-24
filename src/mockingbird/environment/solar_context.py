"""Local solar/daylight context: sunrise, sunset, and day/night
classification derived deterministically from a Place's coordinates and a
UTC instant. No network access; `astral` is a small, pure-Python,
Apache-2.0 core dependency (see pyproject.toml), not an optional heavy
runtime the way the species-suggestion adapters' ML libraries are -- so
unlike `bioclip_adapter`/`birdnet_adapter`, this module has no
"unavailable, missing dependency" case to guard against. Its only "not
ready" case is "no coordinates configured yet."

Temporal semantics (corrected during "Solar Temporal-Semantics Acceptance
Closure" -- see docs/environmental-context-foundation-v1-contract.md):
`astral.sun.sun`'s `date` argument is interpreted *in the timezone passed
as `tzinfo`*. Passing `tzinfo=UTC` asks, honestly and correctly, for
"whichever sunrise/sunset instant falls within this UTC calendar day" --
that is real, well-defined, unambiguous per-event behavior, not a bug, and
not evidence that astral "mislabels" anything. An earlier version of this
module treated a sunset instant landing one UTC calendar day later than a
naive reader might expect (for a longitude far from Greenwich) as an
astral defect, and worked around it with a longitude-derived pseudo-
timezone passed as `tzinfo` -- presenting an approximation as if it were
the Place's real civil time. That framing was wrong on two counts: astral
was not misbehaving, and a longitude-derived offset is not a real
timezone (no DST, no political boundary, no legal standing) and must never
be presented as one. See `find_daylight_window`, below, for the corrected
approach: classification and "today's" sunrise/sunset depend on exactly
two inputs -- Place coordinates and the UTC instant being evaluated -- and
never on any timezone concept, real or approximate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from astral import Observer
from astral.sun import sun

SOLAR_PROVIDER_KEY = "solar_local"
SOLAR_INFORMATION_CLASS = "derived"
SOLAR_ALGORITHM_ID = "astral.sun.sun"
SOLAR_ALGORITHM_VERSION = "3.2"

SolarContextStatusValue = Literal["available", "not_configured"]
DaylightState = Literal["day", "night"]
SolarEventKind = Literal["sunrise", "sunset"]


class SolarContextUnavailableError(ValueError):
    """Raised only for a genuine polar day/night UTC calendar date (the
    sun does not rise or set within it) at the configured coordinates --
    never for a missing dependency or a transient failure. Callers should
    treat this the same as "unavailable for this date," not as a bug."""


@dataclass(frozen=True)
class SolarContextStatus:
    """Side-effect-free readiness summary, mirroring
    `BioClipAdapterStatus`'s shape for the same product-level question:
    "can this feature do anything useful right now."
    """

    status: SolarContextStatusValue
    configured: bool
    detail: str


@dataclass(frozen=True)
class DailySolarFacts:
    """Sunrise/sunset as exact, UTC-aware instants, both guaranteed to
    fall within `for_date` itself in UTC terms (confirmed directly:
    `astral.sun.sun(..., tzinfo=UTC).date() == for_date` holds for every
    coordinate tested, east and west of Greenwich alike).

    `for_date` is the *UTC calendar date* passed to `astral.sun.sun` as
    `date`, with `tzinfo=timezone.utc` -- nothing more. It is never a
    claim about the Place's local/civil date: for a longitude far from
    Greenwich, `sunset_at` can carry an earlier time-of-day than
    `sunrise_at` on this same `for_date` (each is independently "whichever
    instance of that event falls in this UTC day," and the two need not
    belong to the same real day/night cycle) -- do not pair one row's own
    `sunrise_at`/`sunset_at` together as if they were a coherent day/night
    window; use `find_daylight_window` instead.
    """

    for_date: date
    sunrise_at: datetime
    sunset_at: datetime


def get_solar_context_status(
    latitude: float | None, longitude: float | None
) -> SolarContextStatus:
    """Never raises. Coordinates absent is the only "not ready" case this
    provider has -- there is no optional runtime dependency to probe."""

    if latitude is None or longitude is None:
        return SolarContextStatus(
            status="not_configured",
            configured=False,
            detail="No approximate location is configured for this installation.",
        )
    return SolarContextStatus(
        status="available", configured=True, detail="Approximate location configured."
    )


def compute_daily_solar_facts(
    latitude: float, longitude: float, for_date: date
) -> DailySolarFacts:
    """Compute the sunrise/sunset that fall within *UTC calendar date*
    `for_date` -- literally `astral.sun.sun(observer, date=for_date,
    tzinfo=timezone.utc)`, no other timezone involved anywhere. See this
    module's own docstring and `DailySolarFacts`'s for why this pair is
    not always a chronologically sane [sunrise, sunset) window on its own.

    Uses `astral`'s standard geometric sunrise/sunset (center of the solar
    disc crossing the horizon, with standard atmospheric refraction) -- not
    a twilight band. v1 deliberately stops at day/night; see "Provider:
    local solar context" in docs/environmental-context-foundation-v1-
    contract.md for why civil/nautical/astronomical twilight is deferred.

    Raises `SolarContextUnavailableError` for a genuine polar day/night
    UTC calendar date where the sun does not rise or set -- callers must
    treat this as "unavailable for this date," never as a crash.
    """

    observer = Observer(latitude=latitude, longitude=longitude)
    try:
        facts = sun(observer, date=for_date, tzinfo=timezone.utc)
    except ValueError as exc:
        raise SolarContextUnavailableError(
            f"No sunrise/sunset within UTC calendar date {for_date.isoformat()} "
            "at this location (likely polar day/night)."
        ) from exc
    return DailySolarFacts(
        for_date=for_date,
        sunrise_at=facts["sunrise"].astimezone(timezone.utc),
        sunset_at=facts["sunset"].astimezone(timezone.utc),
    )


def classify_daylight_state(
    instant: datetime, sunrise_at: datetime, sunset_at: datetime
) -> DaylightState:
    """"day" when `instant` falls within [sunrise_at, sunset_at), else
    "night". All three datetimes must be timezone-aware; naive datetimes
    raise ValueError rather than silently comparing against an assumed
    zone. `sunrise_at`/`sunset_at` must be a genuinely bracketing pair for
    `instant` (`sunrise_at <= sunset_at`) -- obtain that pair from
    `find_daylight_window`, not by pairing one `DailySolarFacts` row's own
    two fields blindly."""

    if instant.tzinfo is None or sunrise_at.tzinfo is None or sunset_at.tzinfo is None:
        raise ValueError("classify_daylight_state requires timezone-aware datetimes")
    return "day" if sunrise_at <= instant < sunset_at else "night"


def candidate_dates_for_window(instant: datetime) -> tuple[date, date, date]:
    """The three *UTC calendar dates* `find_daylight_window` needs facts
    for for `instant` to be safely bracketed: the UTC calendar date
    `instant` itself falls on, plus the one immediately before and after
    it. Three is always enough: `compute_daily_solar_facts` guarantees
    both of a date's returned instants fall within that same UTC day, so
    the true most-recent sunrise before `instant` is always found on
    `instant`'s own UTC date or the one immediately preceding it, and the
    true next sunset after that sunrise is always found on `instant`'s own
    UTC date or the one immediately following it -- regardless of
    longitude (confirmed directly for both east- and west-of-Greenwich
    coordinates)."""

    if instant.tzinfo is None:
        raise ValueError("candidate_dates_for_window requires a timezone-aware instant")
    center = instant.date()
    return (center - timedelta(days=1), center, center + timedelta(days=1))


def find_daylight_window(
    candidates: list[DailySolarFacts], instant: datetime
) -> tuple[datetime, datetime] | None:
    """The [sunrise_at, sunset_at) pair relevant to `instant`: the most
    recent sunrise at or before `instant`, paired with the next sunset
    after that sunrise. Found by treating every candidate's sunrise and
    sunset as independent events on one sorted timeline -- never by
    pairing one `DailySolarFacts` row's own two fields together (see
    `DailySolarFacts`'s docstring for why that pairing is not always
    chronologically sane by itself). Depends only on the supplied facts
    and `instant`; no timezone concept, real or approximate, is used here.

    `candidates` should be the `DailySolarFacts` for the three dates
    `candidate_dates_for_window(instant)` names (fewer than three -- for
    example, because a candidate date was polar day/night and skipped --
    is tolerated and simply narrows the search). Returns `None` only if
    the supplied candidates do not actually bracket `instant` (an
    incomplete candidate list, or enough candidate dates being polar
    day/night) -- callers must treat that the same as "unavailable,"
    never as a crash.
    """

    if instant.tzinfo is None:
        raise ValueError("find_daylight_window requires a timezone-aware instant")

    events: list[tuple[datetime, SolarEventKind]] = []
    for facts in candidates:
        events.append((facts.sunrise_at, "sunrise"))
        events.append((facts.sunset_at, "sunset"))
    events.sort(key=lambda event: event[0])

    preceding_sunrises = [at for at, kind in events if kind == "sunrise" and at <= instant]
    if not preceding_sunrises:
        return None
    sunrise_at = preceding_sunrises[-1]
    following_sunsets = [at for at, kind in events if kind == "sunset" and at > sunrise_at]
    if not following_sunsets:
        return None
    return sunrise_at, following_sunsets[0]


__all__ = [
    "SOLAR_PROVIDER_KEY",
    "SOLAR_INFORMATION_CLASS",
    "SOLAR_ALGORITHM_ID",
    "SOLAR_ALGORITHM_VERSION",
    "SolarContextStatusValue",
    "DaylightState",
    "SolarEventKind",
    "SolarContextUnavailableError",
    "SolarContextStatus",
    "DailySolarFacts",
    "get_solar_context_status",
    "compute_daily_solar_facts",
    "classify_daylight_state",
    "candidate_dates_for_window",
    "find_daylight_window",
]
