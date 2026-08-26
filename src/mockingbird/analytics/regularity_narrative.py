"""Place / Yard Intelligence v2: pure synthesis of a taxon's already-computed
`historical_baseline.SpeciesHistoricalStatus` and (optional)
`place_change_summary.TaxonChangeStatus` into one small, richer regularity
narrative -- "becoming a regular visitor," "quieter lately," "back after a
quiet stretch" -- instead of a reader having to mentally combine two
separate facts themselves.

This module gathers **no new data** and re-derives **no truth**: it accepts
the two already-computed statuses (or their relevant scalar fields) and
applies one deterministic decision table. See
docs/place-yard-intelligence-v2-contract.md section 3.1.

Never implies individual-animal identity or return -- every state describes
the *taxon's* presence at this Place, matching product-doctrine.md's
"Wildlife-native semantics" (do not assume one Visit equals one bird, do not
imply individual-animal recognition).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# Mirrors `historical_baseline.SpeciesHistoricalStatusValue` /
# `place_change_summary.TaxonChangeStatusValue` by convention, exactly like
# `daily_digest.py`'s own local re-declaration -- this module stays
# dependency-free rather than importing two sibling modules for two Literal
# aliases.
HistoricalStatusValue = Literal["new", "first_record", "regular", "seen_before"]
ChangeStatusValue = Literal[
    "insufficient_baseline",
    "insufficient_recent_coverage",
    "no_supported_change",
    "higher_recent_presence",
    "lower_recent_presence",
]

RegularityStateValue = Literal[
    "first_record",
    "new",
    "occasional",
    "becoming_regular",
    "regular",
    "quieter_lately",
    "returned_after_absence",
]

# Which of the two inputs actually decided the final state -- exposed so a
# caller/explanation surface can honestly say whether a change signal was
# even available, rather than implying every narrative used one.
RegularityBasis = Literal["historical_status_only", "historical_and_change"]


@dataclass(frozen=True)
class RegularityNarrative:
    """One taxon's synthesized regularity state, plus which inputs decided
    it (for explainability drill-down -- see Phase 14 in the milestone
    brief)."""

    state: RegularityStateValue
    basis: RegularityBasis


# Change statuses that carry no honest recent-vs-reference comparison at
# all -- either the Place-wide window itself is not valid yet, or the
# comparison ran and found nothing worth reporting. Both fall back to plain
# historical-status wording, never a fabricated regularity claim.
_NO_USABLE_CHANGE_SIGNAL: frozenset[ChangeStatusValue] = frozenset(
    {"insufficient_baseline", "insufficient_recent_coverage", "no_supported_change"}
)


def compute_regularity_narrative(
    historical_status: HistoricalStatusValue,
    change_status: ChangeStatusValue | None,
    *,
    reference_presence_days: int | None = None,
    first_confirmed_at: datetime | None = None,
    reference_window_start_at: datetime | None = None,
) -> RegularityNarrative:
    """Synthesize one taxon's regularity narrative.

    `reference_presence_days` is `TaxonChangeStatus.reference_presence_days`
    -- required only to distinguish `returned_after_absence` (zero reference
    presence, a real gap) from a plain increase; ignored, safely, when
    `change_status` is not `"higher_recent_presence"`.

    `first_confirmed_at`/`reference_window_start_at` are optional timing
    context (`SpeciesHistoricalStatus.first_confirmed_at` and
    `PlaceChangeWindows.reference_window_start_at`) that, when both are
    supplied, additionally guard `returned_after_absence` against a taxon
    that is merely *young* -- its reference window reads zero presence
    because the taxon did not exist yet, not because an established taxon
    went quiet and came back. A caller that omits either (the historical
    default, before Mobile & Remote Experience v1) gets the original,
    ungated behavior -- this is an additive refinement, never a narrower
    default for existing callers.

    Decision table, most specific first:

    1. `historical_status in ("first_record", "new")` -- baseline is either
       too immature (`first_record`) or this genuinely is this Place's
       all-time-first confirmation (`new`); a change overlay could not add
       anything honest to either, so both pass through unchanged.
    2. Otherwise (`"seen_before"` or `"regular"`), with no usable change
       signal (`change_status is None` or in `_NO_USABLE_CHANGE_SIGNAL`):
       fall back to plain `"occasional"` (from `seen_before`) or
       `"regular"` (from `regular`).
    3. `change_status == "higher_recent_presence"`:
       - `reference_presence_days == 0` AND the taxon is not merely young
         (see `first_confirmed_at`/`reference_window_start_at` above) ->
         `"returned_after_absence"` (stronger and more specific than a
         generic increase: this taxon was entirely absent from the whole
         14-usable-day reference window immediately prior, then
         reappeared).
       - else, from `"seen_before"` -> `"becoming_regular"` (trending
         upward, not yet at the `>=3`-distinct-usable-day regular bar).
       - else, from `"regular"` -> stays `"regular"` (already regular; the
         increase is real but does not need a new label of its own --
         `change_status` is still shown separately alongside it).
    4. `change_status == "lower_recent_presence"`:
       - from `"regular"` -> `"quieter_lately"`.
       - from `"seen_before"` -> stays `"occasional"` (already infrequent;
         a further decrease from "occasional" does not need its own label).

    Raises `ValueError` on a `reference_presence_days` value that would make
    the `returned_after_absence` branch unreachable-but-silently-wrong (a
    negative count), since that would indicate a caller bug in the
    upstream `TaxonChangeStatus`, not a legitimate product state.
    """

    if reference_presence_days is not None and reference_presence_days < 0:
        raise ValueError("reference_presence_days must be >= 0")

    if historical_status in ("first_record", "new"):
        return RegularityNarrative(state=historical_status, basis="historical_status_only")

    # historical_status is now "seen_before" or "regular".
    fallback_state: RegularityStateValue = (
        "regular" if historical_status == "regular" else "occasional"
    )

    if change_status is None or change_status in _NO_USABLE_CHANGE_SIGNAL:
        return RegularityNarrative(state=fallback_state, basis="historical_status_only")

    if change_status == "higher_recent_presence":
        # Unknown timing context (either omitted) preserves the original,
        # ungated behavior -- only a taxon this function can actually prove
        # predates the reference window is ever excluded.
        predates_reference_window = (
            first_confirmed_at is None
            or reference_window_start_at is None
            or first_confirmed_at < reference_window_start_at
        )
        if reference_presence_days == 0 and predates_reference_window:
            return RegularityNarrative(
                state="returned_after_absence", basis="historical_and_change"
            )
        if historical_status == "seen_before":
            return RegularityNarrative(state="becoming_regular", basis="historical_and_change")
        return RegularityNarrative(state="regular", basis="historical_and_change")

    # change_status == "lower_recent_presence"
    if historical_status == "regular":
        return RegularityNarrative(state="quieter_lately", basis="historical_and_change")
    return RegularityNarrative(state="occasional", basis="historical_and_change")
