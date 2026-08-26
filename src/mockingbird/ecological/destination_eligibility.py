"""Per-destination ecological-submission eligibility (see "Reviewed-truth
gate" and "Eligibility preview" in docs/ecological-interoperability-
submission-v1-contract.md).

Composes -- never re-derives or duplicates -- `mockingbird.research.
eligibility.evaluate_research_export_eligibility`'s own research-safe
verdict (see product-doctrine.md's truth boundary: there is exactly one
place that decides whether a record is trustworthy Reviewed truth, and this
module is not a second one). A record that fails the underlying research
eligibility (not yet reviewed, a provisional suggestion, rejected,
non-wildlife, unresolved, structurally superseded, or privacy-restricted)
is never re-litigated here -- it is always `"excluded"`, for exactly the
same reason `ResearchExportEligibility` already gives.

This module only adds the destination-specific completeness checks a plain
research export never needed: a destination that is not offered at all
(see `EBirdAdapter` in `adapters.py`), an unresolved or ambiguous
destination taxonomy mapping, a destination that requires species-level
identity a confirmed-unidentified-wildlife record cannot honestly provide,
and a destination that requires location/count information the record does
not yet carry. Pure, dependency-free -- mirrors `mockingbird.research.
eligibility`'s own "no SQLAlchemy/FastAPI import" convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mockingbird.research.eligibility import ResearchExportEligibility

DestinationEligibilityStatus = Literal["eligible", "needs_input", "excluded"]

#: Reasons layered ON TOP of `ResearchExportEligibility.required_reasons` --
#: never a replacement for them. These only ever apply to a record the
#: underlying research eligibility gate has already passed.
DESTINATION_NEEDS_INPUT_REASONS = frozenset(
    {
        "taxonomy_mapping_unresolved",
        "taxonomy_mapping_ambiguous",
        "location_required",
        "count_required",
        "media_selection_required",
    }
)
DESTINATION_EXCLUDED_REASONS = frozenset(
    {
        "destination_not_offered",
        "species_level_taxon_required",
    }
)


@dataclass(frozen=True)
class DestinationRequirements:
    """What one destination genuinely needs, in the destination's own terms
    -- never guessed, always sourced from official destination documentation
    (see the governing contract doc's per-destination "Workflow" sections
    and "Destination research"). `offered=False` short-circuits every other
    field: a not-offered destination is always `"excluded"`, regardless of
    how complete the record otherwise is."""

    offered: bool
    offered_reason: str | None = None
    requires_location: bool = False
    requires_species_level_taxon: bool = False
    accepts_unidentified_wildlife: bool = True
    requires_count: bool = False


@dataclass(frozen=True)
class DestinationEligibility:
    """One record's verdict for one destination. Never a bare bool -- a
    caller (an eligibility-preview UI, a batch-prepare skip report) needs to
    know *why*, the same discipline `ResearchExportEligibility` already
    established."""

    status: DestinationEligibilityStatus
    needs_input_reasons: tuple[str, ...] = ()
    excluded_reasons: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return self.status == "eligible"


def evaluate_destination_eligibility(
    research_eligibility: ResearchExportEligibility,
    requirements: DestinationRequirements,
    *,
    has_taxonomy_mapping: bool,
    taxonomy_mapping_ambiguous: bool = False,
    has_location: bool,
    has_count: bool = True,
) -> DestinationEligibility:
    """One record's verdict for one destination.

    `research_eligibility` must already be `.eligible` for this function to
    return anything but `"excluded"` -- see the module docstring. `has_
    taxonomy_mapping`/`taxonomy_mapping_ambiguous` are only consulted for a
    `"confirmed_taxon"` record: a `"confirmed_unidentified_wildlife"` record
    never needs a taxonomy mapping at all (an honestly-unresolved species is
    represented to a destination as "unknown," never blocked on a mapping
    that could not exist -- see "Confirmed unidentified wildlife" in the
    governing contract doc).
    """

    if not research_eligibility.eligible:
        return DestinationEligibility("excluded", excluded_reasons=research_eligibility.required_reasons)

    if not requirements.offered:
        return DestinationEligibility("excluded", excluded_reasons=("destination_not_offered",))

    is_confirmed_taxon = research_eligibility.classification == "confirmed_taxon"
    is_unidentified_wildlife = research_eligibility.classification == "confirmed_unidentified_wildlife"

    if requirements.requires_species_level_taxon and not is_confirmed_taxon:
        return DestinationEligibility("excluded", excluded_reasons=("species_level_taxon_required",))
    if is_unidentified_wildlife and not requirements.accepts_unidentified_wildlife:
        return DestinationEligibility("excluded", excluded_reasons=("species_level_taxon_required",))

    needs_input: list[str] = []
    if is_confirmed_taxon:
        if taxonomy_mapping_ambiguous:
            needs_input.append("taxonomy_mapping_ambiguous")
        elif not has_taxonomy_mapping:
            needs_input.append("taxonomy_mapping_unresolved")
    if requirements.requires_location and not has_location:
        needs_input.append("location_required")
    if requirements.requires_count and not has_count:
        needs_input.append("count_required")

    if needs_input:
        return DestinationEligibility("needs_input", needs_input_reasons=tuple(needs_input))
    return DestinationEligibility("eligible")


__all__ = [
    "DestinationEligibilityStatus",
    "DESTINATION_NEEDS_INPUT_REASONS",
    "DESTINATION_EXCLUDED_REASONS",
    "DestinationRequirements",
    "DestinationEligibility",
    "evaluate_destination_eligibility",
]
