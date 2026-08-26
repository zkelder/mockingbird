"""Pure computation tests for mockingbird.analytics.regularity_narrative.

No repository, no database -- matches the existing test_historical_
baseline.py / test_place_change_summary.py precedent for pure sibling
modules. Exercises every branch of `compute_regularity_narrative`'s own
decision table (see that function's docstring, and
docs/place-yard-intelligence-v2-contract.md section 3.1 for the product
contract it implements), including which `basis` each branch reports.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mockingbird.analytics.regularity_narrative import (
    ChangeStatusValue,
    HistoricalStatusValue,
    RegularityNarrative,
    compute_regularity_narrative,
)

# ---------------------------------------------------------------------------
# historical_status in ("first_record", "new") always passes through,
# regardless of change_status or reference_presence_days.
# ---------------------------------------------------------------------------

_CHANGE_STATUS_AND_REFERENCE_DAYS_VARIANTS: list[tuple[ChangeStatusValue | None, int | None]] = [
    (None, None),
    ("insufficient_baseline", None),
    ("insufficient_recent_coverage", None),
    ("no_supported_change", None),
    ("lower_recent_presence", None),
    ("higher_recent_presence", 0),  # even the zero-reference "absence" rule must not intrude
    ("higher_recent_presence", 3),
]


@pytest.mark.parametrize("change_status,reference_presence_days", _CHANGE_STATUS_AND_REFERENCE_DAYS_VARIANTS)
def test_first_record_passes_through_regardless_of_change_status(
    change_status: ChangeStatusValue | None, reference_presence_days: int | None
) -> None:
    result = compute_regularity_narrative(
        "first_record", change_status, reference_presence_days=reference_presence_days
    )
    assert result.state == "first_record"
    assert result.basis == "historical_status_only"


@pytest.mark.parametrize("change_status,reference_presence_days", _CHANGE_STATUS_AND_REFERENCE_DAYS_VARIANTS)
def test_new_passes_through_regardless_of_change_status(
    change_status: ChangeStatusValue | None, reference_presence_days: int | None
) -> None:
    result = compute_regularity_narrative(
        "new", change_status, reference_presence_days=reference_presence_days
    )
    assert result.state == "new"
    assert result.basis == "historical_status_only"


# ---------------------------------------------------------------------------
# seen_before / regular with no usable change signal at all
# (change_status is None) fall back to plain historical wording.
# ---------------------------------------------------------------------------


def test_seen_before_with_no_change_status_reads_occasional() -> None:
    result = compute_regularity_narrative("seen_before", None)
    assert result.state == "occasional"
    assert result.basis == "historical_status_only"


def test_regular_with_no_change_status_stays_regular() -> None:
    result = compute_regularity_narrative("regular", None)
    assert result.state == "regular"
    assert result.basis == "historical_status_only"


# ---------------------------------------------------------------------------
# seen_before / regular with a change_status that carries no *usable*
# comparison (invalid window, or a validly-run comparison that found
# nothing worth reporting) fall back identically to the None case above.
# ---------------------------------------------------------------------------

_NO_USABLE_CHANGE_SIGNAL_STATUSES: list[ChangeStatusValue] = [
    "insufficient_baseline",
    "insufficient_recent_coverage",
    "no_supported_change",
]


@pytest.mark.parametrize("change_status", _NO_USABLE_CHANGE_SIGNAL_STATUSES)
def test_seen_before_with_unusable_change_signal_falls_back_to_occasional(
    change_status: ChangeStatusValue,
) -> None:
    result = compute_regularity_narrative("seen_before", change_status)
    assert result.state == "occasional"
    assert result.basis == "historical_status_only"


@pytest.mark.parametrize("change_status", _NO_USABLE_CHANGE_SIGNAL_STATUSES)
def test_regular_with_unusable_change_signal_falls_back_to_plain_regular(
    change_status: ChangeStatusValue,
) -> None:
    result = compute_regularity_narrative("regular", change_status)
    assert result.state == "regular"
    assert result.basis == "historical_status_only"


# ---------------------------------------------------------------------------
# change_status == "higher_recent_presence"
# ---------------------------------------------------------------------------


def test_seen_before_returns_after_absence_when_reference_presence_is_zero() -> None:
    result = compute_regularity_narrative(
        "seen_before", "higher_recent_presence", reference_presence_days=0
    )
    assert result.state == "returned_after_absence"
    assert result.basis == "historical_and_change"


def test_regular_also_returns_after_absence_when_reference_presence_is_zero() -> None:
    """The zero-reference-presence rule outranks prior status -- even an
    already-`regular` taxon that was entirely absent across the whole
    reference window reads as a real gap, not a plain continuing
    "regular"."""

    result = compute_regularity_narrative(
        "regular", "higher_recent_presence", reference_presence_days=0
    )
    assert result.state == "returned_after_absence"
    assert result.basis == "historical_and_change"


def test_seen_before_with_nonzero_increase_becomes_regular() -> None:
    result = compute_regularity_narrative(
        "seen_before", "higher_recent_presence", reference_presence_days=3
    )
    assert result.state == "becoming_regular"
    assert result.basis == "historical_and_change"


def test_regular_with_nonzero_increase_stays_regular_with_a_change_basis() -> None:
    """Same resulting state ("regular") as the no-usable-change-signal
    fallback above, but this time a change signal genuinely was consulted
    -- `basis` is what tells the two cases apart, not `state` alone."""

    result = compute_regularity_narrative(
        "regular", "higher_recent_presence", reference_presence_days=3
    )
    assert result.state == "regular"
    assert result.basis == "historical_and_change"


# ---------------------------------------------------------------------------
# first_confirmed_at / reference_window_start_at (Mobile & Remote
# Experience v1 Phase 0): optional timing context distinguishing a real
# established-taxon return from a merely young taxon.
# ---------------------------------------------------------------------------


def test_returned_after_absence_still_fires_when_timing_context_is_omitted() -> None:
    """Backward compatibility: a caller that never learned about the new
    keyword-only parameters (every call site before this milestone) gets
    the identical, original, ungated behavior -- this is an additive
    refinement, never a narrower default."""

    result = compute_regularity_narrative(
        "seen_before", "higher_recent_presence", reference_presence_days=0
    )
    assert result.state == "returned_after_absence"


def test_returned_after_absence_fires_when_first_confirmed_before_reference_window() -> None:
    reference_window_start_at = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_regularity_narrative(
        "regular",
        "higher_recent_presence",
        reference_presence_days=0,
        first_confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
        reference_window_start_at=reference_window_start_at,
    )
    assert result.state == "returned_after_absence"
    assert result.basis == "historical_and_change"


def test_returned_after_absence_suppressed_for_a_taxon_younger_than_the_reference_window() -> None:
    """The taxon's own all-time-first confirmation falls *after* the
    reference window started -- its zero reference presence is honestly
    explained by not existing yet, not by a real absence, so this must
    fall back to the plain `"regular"`/`"becoming_regular"` a change signal
    without the zero-reference special case would produce (mirrors the
    former `place_story._effective_regularity_state`'s own `(d)` guard,
    now shared here instead of duplicated per caller)."""

    reference_window_start_at = datetime(2026, 8, 1, tzinfo=UTC)
    first_confirmed_at = datetime(2026, 8, 10, tzinfo=UTC)  # after the window started
    assert first_confirmed_at > reference_window_start_at

    regular_result = compute_regularity_narrative(
        "regular",
        "higher_recent_presence",
        reference_presence_days=0,
        first_confirmed_at=first_confirmed_at,
        reference_window_start_at=reference_window_start_at,
    )
    assert regular_result.state == "regular"

    seen_before_result = compute_regularity_narrative(
        "seen_before",
        "higher_recent_presence",
        reference_presence_days=0,
        first_confirmed_at=first_confirmed_at,
        reference_window_start_at=reference_window_start_at,
    )
    assert seen_before_result.state == "becoming_regular"


def test_returned_after_absence_suppressed_only_when_both_timing_fields_are_known() -> None:
    """Half-known timing context (one field present, the other `None`) must
    not accidentally suppress the state either -- only a caller that
    supplies *both* fields gets the guard applied."""

    result_missing_reference = compute_regularity_narrative(
        "regular",
        "higher_recent_presence",
        reference_presence_days=0,
        first_confirmed_at=datetime(2026, 8, 10, tzinfo=UTC),
        reference_window_start_at=None,
    )
    assert result_missing_reference.state == "returned_after_absence"

    result_missing_first_confirmed = compute_regularity_narrative(
        "regular",
        "higher_recent_presence",
        reference_presence_days=0,
        first_confirmed_at=None,
        reference_window_start_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert result_missing_first_confirmed.state == "returned_after_absence"


def test_first_confirmed_timing_is_ignored_when_reference_presence_is_nonzero() -> None:
    """The timing guard only ever matters for the zero-reference branch --
    a taxon younger than the reference window but with real (nonzero)
    reference presence is a contradiction that cannot occur from honest
    inputs, and is not this guard's concern either way."""

    result = compute_regularity_narrative(
        "seen_before",
        "higher_recent_presence",
        reference_presence_days=3,
        first_confirmed_at=datetime(2026, 8, 10, tzinfo=UTC),
        reference_window_start_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert result.state == "becoming_regular"


# ---------------------------------------------------------------------------
# change_status == "lower_recent_presence"
# ---------------------------------------------------------------------------


def test_regular_with_lower_recent_presence_reads_quieter_lately() -> None:
    result = compute_regularity_narrative("regular", "lower_recent_presence")
    assert result.state == "quieter_lately"
    assert result.basis == "historical_and_change"


def test_seen_before_with_lower_recent_presence_stays_occasional_with_a_change_basis() -> None:
    """Same resulting state ("occasional") as the no-usable-change-signal
    fallback; `basis` again is the only thing distinguishing a genuinely-
    consulted decrease from a plain fallback."""

    result = compute_regularity_narrative("seen_before", "lower_recent_presence")
    assert result.state == "occasional"
    assert result.basis == "historical_and_change"


# ---------------------------------------------------------------------------
# reference_presence_days validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("historical_status", ["first_record", "new", "seen_before", "regular"])
def test_negative_reference_presence_days_raises_value_error(
    historical_status: HistoricalStatusValue,
) -> None:
    with pytest.raises(ValueError):
        compute_regularity_narrative(historical_status, None, reference_presence_days=-1)


# ---------------------------------------------------------------------------
# Result shape and determinism
# ---------------------------------------------------------------------------


def test_result_is_a_regularity_narrative_instance() -> None:
    result = compute_regularity_narrative("seen_before", None)
    assert isinstance(result, RegularityNarrative)


def test_computation_is_deterministic() -> None:
    first = compute_regularity_narrative(
        "seen_before", "higher_recent_presence", reference_presence_days=3
    )
    second = compute_regularity_narrative(
        "seen_before", "higher_recent_presence", reference_presence_days=3
    )
    assert first == second
