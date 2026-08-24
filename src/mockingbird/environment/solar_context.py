"""Local solar/daylight context: sunrise, sunset, and day/night
classification derived deterministically from a Place's coordinates and a
date. No network access; `astral` is a small, pure-Python, Apache-2.0 core
dependency (see pyproject.toml), not an optional heavy runtime the way the
species-suggestion adapters' ML libraries are -- so unlike
`bioclip_adapter`/`birdnet_adapter`, this module has no "unavailable,
missing dependency" case to guard against. Its only "not ready" case is
"no coordinates configured yet."

See docs/environmental-context-foundation-v1-contract.md "Provider: local
solar context".
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


class SolarContextUnavailableError(ValueError):
    """Raised only for a genuine polar day/night date (the sun does not
    rise or set at all) at the configured coordinates -- never for a
    missing dependency or a transient failure. Callers should treat this
    the same as "unavailable for this date," not as a bug."""


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
    """One calendar date's sunrise/sunset, in UTC, for one coordinate pair."""

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


def _approximate_local_offset(longitude: float) -> timezone:
    """A coarse, no-secret stand-in for "this coordinate's local timezone,"
    good only for picking the right *calendar date* -- never shown to a
    user or persisted as a claimed real timezone.

    `astral.sun.sun` anchors its `date` argument to whatever `tzinfo` it is
    given: pass it a real local zone and `date=D` correctly means "the
    calendar day D runs from local midnight to local midnight there."
    Pass it `timezone.utc` for a location far from Greenwich instead, and
    the *labeled date* of an event that actually falls right after local
    midnight silently shifts by a day -- confirmed directly: for New York
    (UTC-4 in June), asking for `date=2026-06-21, tzinfo=UTC` returns a
    `sunset` of `2026-06-21 00:30 UTC`, one full calendar day earlier than
    the correct `2026-06-22 00:30 UTC` (verified against the same
    computation using the real `America/New_York` zone). A fixed
    15-degrees-per-hour offset derived from longitude is not a real
    timezone (no DST, no political boundaries), but it is accurate enough
    to resolve which calendar day an event belongs to -- the only thing
    `date` is used for here; the returned instants are still exact,
    UTC-aware, and converted back to UTC before being returned.
    """

    offset_hours = max(-12, min(12, round(longitude / 15)))
    return timezone(timedelta(hours=offset_hours))


def approximate_local_date(instant: datetime, longitude: float) -> date:
    """The calendar date `instant` (a real, exact UTC-aware instant) falls
    on on the local side of this coordinate -- using the same coarse
    per-15-degrees offset `compute_daily_solar_facts` anchors its own
    `date` argument to, so the two stay consistent with each other."""

    if instant.tzinfo is None:
        raise ValueError("approximate_local_date requires a timezone-aware instant")
    offset = _approximate_local_offset(longitude)
    return instant.astimezone(offset).date()


def compute_daily_solar_facts(
    latitude: float, longitude: float, for_date: date
) -> DailySolarFacts:
    """Compute sunrise/sunset for one calendar date, at this coordinate's
    approximate local day boundary (see `_approximate_local_offset`), as
    exact UTC-aware instants.

    Uses `astral`'s standard geometric sunrise/sunset (center of the solar
    disc crossing the horizon, with standard atmospheric refraction) -- not
    a twilight band. v1 deliberately stops at day/night; see "Provider:
    local solar context" in docs/environmental-context-foundation-v1-
    contract.md for why civil/nautical/astronomical twilight is deferred.

    Raises `SolarContextUnavailableError` for a genuine polar day/night
    date where the sun does not rise or set -- callers must treat this as
    "unavailable for this date," never as a crash.
    """

    observer = Observer(latitude=latitude, longitude=longitude)
    anchor_tz = _approximate_local_offset(longitude)
    try:
        facts = sun(observer, date=for_date, tzinfo=anchor_tz)
    except ValueError as exc:
        raise SolarContextUnavailableError(
            f"No sunrise/sunset at this location for {for_date.isoformat()} "
            "(likely polar day/night)."
        ) from exc
    return DailySolarFacts(
        sunrise_at=facts["sunrise"].astimezone(timezone.utc),
        sunset_at=facts["sunset"].astimezone(timezone.utc),
    )


def classify_daylight_state(
    instant: datetime, sunrise_at: datetime, sunset_at: datetime
) -> DaylightState:
    """"day" when `instant` falls within [sunrise_at, sunset_at), else
    "night". All three datetimes must be timezone-aware; naive datetimes
    raise ValueError rather than silently comparing against an assumed
    zone."""

    if instant.tzinfo is None or sunrise_at.tzinfo is None or sunset_at.tzinfo is None:
        raise ValueError("classify_daylight_state requires timezone-aware datetimes")
    return "day" if sunrise_at <= instant < sunset_at else "night"


__all__ = [
    "SOLAR_PROVIDER_KEY",
    "SOLAR_INFORMATION_CLASS",
    "SOLAR_ALGORITHM_ID",
    "SOLAR_ALGORITHM_VERSION",
    "SolarContextStatusValue",
    "DaylightState",
    "SolarContextUnavailableError",
    "SolarContextStatus",
    "DailySolarFacts",
    "get_solar_context_status",
    "approximate_local_date",
    "compute_daily_solar_facts",
    "classify_daylight_state",
]
