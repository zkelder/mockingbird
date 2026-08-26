"""The one canonical external-ecological-submission projection over
MockingBird truth (Phase 4 of the governing contract doc) plus the static
destination-adapter boundary (Phase 28).

Composes `mockingbird.research.research_export.ResearchObservation` --
never a second, parallel truth shape. `ResearchObservation` already carries
everything Phase 4 asks for (MockingBird Observation/Visit identity,
reviewed taxon label/scientific name/category, capture timestamp and its
confidence, reviewer provenance, acquisition provenance, evidence
identity, and the full research-eligibility verdict); this module adds only
what a destination workflow needs beyond a research export: a destination
identity, the extra per-destination eligibility layer (`destination_
eligibility.py`), an explicit -- never silently defaulted -- location/media
choice (see "Location is a separate consent boundary" in the governing
contract doc), and a resolved destination taxonomy mapping.

Static, built-in adapters only -- no plugin marketplace, no dynamic
third-party Python loading (Phase 28 of the governing milestone brief).
`mockingbird.repository.product_repository` owns every database session;
this module stays pure/dependency-free like the rest of `mockingbird.
ecological` and `mockingbird.research`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from mockingbird.ecological.destination_eligibility import (
    DestinationEligibility,
    DestinationRequirements,
    evaluate_destination_eligibility,
)
from mockingbird.research.research_export import ResearchObservation

EcologicalDestination = Literal["inaturalist", "ebird"]

LocationChoice = Literal["none", "coarse", "exact"]
MediaPolicy = Literal["none", "metadata_only"]


@dataclass(frozen=True)
class LocationSelection:
    """An explicit, never-defaulted-from-the-weather-coordinate location
    choice for one submission (see "Location is a separate consent
    boundary" in the governing contract doc). `choice="none"` is the honest
    default; `"coarse"`/`"exact"` both carry a real `latitude`/`longitude`
    the user supplied at prepare time -- `choice` records the user's stated
    *intent* (their belief about how precise this location is), not a
    number MockingBird itself measures or verifies."""

    choice: LocationChoice = "none"
    latitude: float | None = None
    longitude: float | None = None
    place_name: str | None = None


@dataclass(frozen=True)
class MediaSelection:
    """An explicit media choice (Phase 12). `policy="none"` -- no media
    reference included at all -- is the honest default. This milestone
    never bundles media *bytes* into an ecological submission package (see
    "Media behavior" in the governing contract doc); `media_asset_id` is
    retained only as a reference so a user can find and attach the right
    photo themselves on the destination's own site."""

    policy: MediaPolicy = "none"
    media_asset_id: str | None = None


@dataclass(frozen=True)
class DestinationTaxonomyMapping:
    """One resolved (or honestly unresolved) destination taxonomy mapping
    -- see `mockingbird.ecological.inaturalist_taxonomy.TaxonMatch`, which
    this mirrors at the destination-agnostic layer. Never mutates
    MockingBird's own `TaxonomyLabelModel`; this is a translation-layer
    fact only (Phase 7 of the governing brief)."""

    match_status: Literal["matched", "ambiguous", "not_found"]
    destination_taxon_id: str | None = None
    destination_scientific_name: str | None = None
    destination_display_name: str | None = None
    taxonomy_source_version: str | None = None


@dataclass(frozen=True)
class EcologicalSubmissionCandidate:
    """One canonical, destination-scoped projection of a Reviewed
    MockingBird Visit -- composes a `ResearchObservation` unmodified."""

    research_observation: ResearchObservation
    destination: EcologicalDestination
    destination_eligibility: DestinationEligibility
    taxonomy_mapping: DestinationTaxonomyMapping | None
    location: LocationSelection
    media: MediaSelection


class EcologicalDestinationAdapter(Protocol):
    """The smallest useful per-destination interface (Phase 28): a
    destination identity and what it genuinely requires. No adapter in this
    milestone implements a live authenticated `submit` -- see the governing
    contract doc's per-destination "Workflow" sections for why, and Phase
    28 of the governing brief for why this stays a plain Python object,
    never dynamically loaded."""

    key: EcologicalDestination
    display_name: str

    def requirements(self) -> DestinationRequirements: ...


@dataclass(frozen=True)
class EBirdAdapter:
    """Not offered. See the governing contract doc's "eBird workflow" for
    the cited, current eBird policy this decision rests on --
    support.ebird.org's "eBird Rules and Best Practices" (checked
    2026-08-25, page shows "Last Updated Tue, 17 Feb 2026"): "Remote sensed
    images or video - do not enter any data from nest cameras, feeder
    cameras, trail cams..." and "eBird is designed to collect in-person
    observations of living wild birds." MockingBird's entire product
    category is named explicitly, with no carve-out found for a human
    reviewing camera footage before submission. This is a real,
    evidence-based policy conflict, not an unfinished feature -- see Phase
    3 of the governing milestone brief ("Choose the honest path")."""

    key: EcologicalDestination = "ebird"
    display_name: str = "eBird"

    def requirements(self) -> DestinationRequirements:
        return DestinationRequirements(
            offered=False,
            offered_reason=(
                "eBird's own Rules and Best Practices exclude nest/feeder/trail-camera "
                'observations ("eBird is designed to collect in-person observations of '
                'living wild birds") -- checked 2026-08-25, see support.ebird.org/en/'
                "support/solutions/articles/48000795623. MockingBird does not offer eBird "
                "preparation for this reason."
            ),
        )


@dataclass(frozen=True)
class INaturalistAdapter:
    """A real, offered destination -- see the governing contract doc's
    "iNaturalist workflow" for the full, officially-researched mapping this
    adapter's callers implement (`observed_on_string`/geoprivacy/
    `captive_flag`/taxon mapping/the confirmed bulk-import CSV shape). No
    live OAuth submit is implemented (Phase 26 of the governing brief: no
    unsafe credential-storage workaround invented for a capability that
    does not yet exist) -- preparing a submission-ready CSV for
    iNaturalist's own bulk importer, which needs no destination credential
    at all, is this adapter's real v1 capability."""

    key: EcologicalDestination = "inaturalist"
    display_name: str = "iNaturalist"

    def requirements(self) -> DestinationRequirements:
        return DestinationRequirements(
            offered=True,
            requires_location=False,
            requires_species_level_taxon=False,
            accepts_unidentified_wildlife=True,
            requires_count=False,
        )


#: Static registry only -- adding a destination means adding a line here,
#: never dynamic/third-party loading (Phase 28).
DESTINATION_ADAPTERS: dict[EcologicalDestination, EcologicalDestinationAdapter] = {
    "inaturalist": INaturalistAdapter(),
    "ebird": EBirdAdapter(),
}


def build_submission_candidate(
    research_observation: ResearchObservation,
    *,
    destination: EcologicalDestination,
    taxonomy_mapping: DestinationTaxonomyMapping | None,
    location: LocationSelection,
    media: MediaSelection,
) -> EcologicalSubmissionCandidate:
    """The one place a `ResearchObservation` becomes an
    `EcologicalSubmissionCandidate` for one destination -- callers
    (`mockingbird.repository.product_repository`) never construct the
    destination-eligibility verdict themselves."""

    adapter = DESTINATION_ADAPTERS[destination]
    requirements = adapter.requirements()
    is_confirmed_taxon = research_observation.classification == "confirmed_taxon"
    destination_elig = evaluate_destination_eligibility(
        research_observation.eligibility,
        requirements,
        has_taxonomy_mapping=(
            not is_confirmed_taxon
            or (taxonomy_mapping is not None and taxonomy_mapping.match_status == "matched")
        ),
        taxonomy_mapping_ambiguous=(
            is_confirmed_taxon and taxonomy_mapping is not None and taxonomy_mapping.match_status == "ambiguous"
        ),
        has_location=(location.choice != "none"),
        has_count=True,
    )
    return EcologicalSubmissionCandidate(
        research_observation=research_observation,
        destination=destination,
        destination_eligibility=destination_elig,
        taxonomy_mapping=taxonomy_mapping,
        location=location,
        media=media,
    )


__all__ = [
    "EcologicalDestination",
    "LocationChoice",
    "MediaPolicy",
    "LocationSelection",
    "MediaSelection",
    "DestinationTaxonomyMapping",
    "EcologicalSubmissionCandidate",
    "EcologicalDestinationAdapter",
    "EBirdAdapter",
    "INaturalistAdapter",
    "DESTINATION_ADAPTERS",
    "build_submission_candidate",
]
