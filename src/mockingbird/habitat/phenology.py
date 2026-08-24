"""Pure temporal-status logic for Place phenology observations.

No database access, no network access -- mirrors `mockingbird.environment.
solar_context`'s own "small pure function, directly testable" shape and
its discipline of computing classification at read time rather than
persisting it (see that module's `classify_daylight_state`). A phenology
observation's [`observed_start_date`, `observed_end_date`] interval is
fixed at write time; whether it counts as "current," "recent," or "past"
depends on today's date and must always be re-derived, never frozen --
otherwise an observation from April would silently keep reading as
current in August (see "Temporal semantics" in
docs/habitat-phenology-foundation-v1-contract.md).

Dates here are plain `date` values, never `datetime` instants: a phenology
observation is a human-entered, day-granularity fact ("azaleas started
flowering around August 1st"), not a precisely timed event the way solar
sunrise/sunset are. "Today" is always the *UTC calendar date*
(`datetime.now(UTC).date()`) -- the same "no timezone invention, follow
the UTC-instant/date convention" discipline the Environmental Context
Foundation v1 acceptance closure established, applied here without any of
that milestone's own astral-specific complexity (there is no instant to
bracket, only a plain date-range containment check).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

HABITAT_INFORMATION_CLASS = "user_reported"
HABITAT_PROVENANCE_MANUAL_ENTRY = "user_manual_entry"

HabitatFactCategory = Literal["setting", "vegetation", "feature"]
HABITAT_FACT_CATEGORIES: tuple[HabitatFactCategory, ...] = ("setting", "vegetation", "feature")

PhenologyStatus = Literal["current", "recent", "past"]

# Bounded and explicit, matching this codebase's "no open-ended decay
# heuristic" discipline elsewhere (e.g. the scene-confusor spread bound).
# A phenology entry with no explicit end date describes a single day (see
# `phenology_interval_covers`'s docstring) -- this constant only controls
# how long a *concluded* interval still surfaces under "recent" framing,
# never whether something still reads as "current."
DEFAULT_RECENT_WINDOW_DAYS = 14


def phenology_interval_covers(
    start_date: date, end_date: date | None, on_date: date
) -> bool:
    """True when `on_date` falls within [`start_date`, `end_date`].

    `end_date=None` means a single-date observation -- equivalent to
    `end_date == start_date` for containment purposes -- and never means
    "ongoing indefinitely." A user who wants a fact to read as covering a
    longer span must say so explicitly with a real `end_date`; silently
    treating an open end as "still going" is exactly the dishonest
    "observation from April still looks current in August" failure this
    module exists to avoid.
    """

    effective_end = end_date if end_date is not None else start_date
    return start_date <= on_date <= effective_end


@dataclass(frozen=True)
class PhenologyStatusResult:
    """The read-time classification of one observation's interval against
    one reference date, plus the bounded window that produced it (so a
    caller/UI can explain "recent" honestly rather than presenting it as
    unqualified "current")."""

    status: PhenologyStatus
    today: date
    recent_window_days: int


def classify_phenology_status(
    start_date: date,
    end_date: date | None,
    *,
    today: date,
    recent_window_days: int = DEFAULT_RECENT_WINDOW_DAYS,
) -> PhenologyStatusResult:
    """Classify one observation's interval relative to `today`:

    - "current": `today` falls within [start_date, effective_end_date].
    - "recent": concluded, but its effective end date falls within the
      last `recent_window_days` days before `today` -- a bounded, explicit
      grace window, never an open-ended "still probably relevant" guess.
    - "past": everything else, including a future-dated interval that has
      not started yet (honestly not "current" or "recent" -- it simply
      has not happened relative to `today` yet).

    `recent_window_days` must be >= 0; a value of 0 means "current only,
    nothing is ever recent," which is a valid, if unusual, caller choice.
    """

    if recent_window_days < 0:
        raise ValueError("recent_window_days must be >= 0")

    if phenology_interval_covers(start_date, end_date, today):
        status: PhenologyStatus = "current"
    else:
        effective_end = end_date if end_date is not None else start_date
        recently_concluded = (
            effective_end < today and (today - effective_end) <= timedelta(days=recent_window_days)
        )
        status = "recent" if recently_concluded else "past"

    return PhenologyStatusResult(status=status, today=today, recent_window_days=recent_window_days)


__all__ = [
    "HABITAT_INFORMATION_CLASS",
    "HABITAT_PROVENANCE_MANUAL_ENTRY",
    "HabitatFactCategory",
    "HABITAT_FACT_CATEGORIES",
    "PhenologyStatus",
    "DEFAULT_RECENT_WINDOW_DAYS",
    "phenology_interval_covers",
    "PhenologyStatusResult",
    "classify_phenology_status",
]
