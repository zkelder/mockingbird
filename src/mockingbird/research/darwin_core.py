"""Bounded Darwin Core Occurrence-core export -- Phase 29 of the Ecological
Interoperability & Submission Workflows v1 milestone brief. Confirmed via
official TDWG/GBIF sources (checked 2026-08-25, see docs/ecological-
interoperability-submission-v1-contract.md "Darwin Core" research section):
Darwin Core is an open, account-free vocabulary -- no institutional
publishing infrastructure is required to *produce* a Darwin Core Archive --
and the already-accepted Camtrap DP export is NOT itself a Darwin Core
Archive (it is a Frictionless Data Package; GBIF's own tooling transforms
one to the other only for its own ingestion, one-way and lossily, per
GBIF's official camera-trap guide). This module is therefore additive, not
redundant: a small, deterministic, flat Occurrence-core Darwin Core Archive
any generic DwC-A consumer can read directly, without needing to
understand Camtrap DP at all.

Lives in `mockingbird.research` (not `mockingbird.ecological`) because it
is a bounded extension of the already-accepted generic research-export
family (like Camtrap DP), not a destination-submission workflow -- see
"Canonical reviewed external observation" in the governing contract doc for
why that distinction is preserved.

Maps `mockingbird.research.research_export.ResearchObservation` rows onto a
single Occurrence-core table -- no Event-core linkage (MockingBird has no
deployment-lifecycle/sequence model that would make one meaningful; mirrors
Camtrap DP's own identical, already-disclosed "no deployment lifecycle"
choice). `basisOfRecord` is unconditionally `"MachineObservation"` for
every row -- GBIF's own official camera-trap guide (docs.gbif.org/
camera-trap-guide, checked 2026-08-25) recommends exactly this value for
every camera-trap record: "the capturing of the record is done by a
machine responding to a sensor," which is exactly how a MockingBird Visit
is created; the *identification* is a separate, human-reviewed fact,
carried in `identifiedBy`. `individualCount` is never populated --
MockingBird has no individual-animal counting model (see "Wildlife-native
semantics" in product-doctrine.md, and the identical decision `camtrap_dp.
py` already made); `occurrenceStatus` is unconditionally `"detected"`,
since only positive detections are ever exported. Only research-eligible
records (`ResearchExportEligibility.eligible`) are mapped at all -- a
provisional/unresolved/rejected/superseded/non-wildlife/privacy-restricted
Visit never becomes a Darwin Core Occurrence.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mockingbird.research.research_export import ResearchObservation, sorted_observations

DARWIN_CORE_ARCHIVE_SCHEMA_VERSION = "darwin-core-archive-v1"
_DWC_OCCURRENCE_ROW_TYPE = "http://rs.tdwg.org/dwc/terms/Occurrence"
_DWC_TERM_NAMESPACE = "http://rs.tdwg.org/dwc/terms/"


@dataclass(frozen=True)
class DarwinCoreMappingOptions:
    """Explicit, never-inferred export-time context -- mirrors
    `mockingbird.research.camtrap_dp.CamtrapDpMappingOptions` exactly (see
    "Location is a separate consent boundary" in the governing contract
    doc). Every field defaults to the honest "not supplied" state; none of
    these is ever read from `EnvironmentalContextSettingsModel`'s coarse
    weather coordinate."""

    site_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    coordinate_uncertainty_meters: float | None = None


@dataclass(frozen=True)
class DarwinCoreOccurrence:
    occurrence_id: str
    basis_of_record: str
    event_date: datetime
    scientific_name: str | None
    taxon_rank: str | None
    decimal_latitude: float | None
    decimal_longitude: float | None
    coordinate_uncertainty_in_meters: float | None
    geodetic_datum: str | None
    occurrence_status: str
    identified_by: str | None
    locality: str | None
    associated_media: str | None


@dataclass(frozen=True)
class DarwinCoreArchive:
    schema_version: str
    occurrences: list[DarwinCoreOccurrence]


def build_darwin_core_archive(
    observations: list[ResearchObservation],
    *,
    options: DarwinCoreMappingOptions = DarwinCoreMappingOptions(),
) -> DarwinCoreArchive:
    """Map already-resolved, already-eligibility-classified
    `ResearchObservation`s onto a bounded Darwin Core Occurrence table.
    Never queries anything; never re-derives eligibility -- mirrors
    `mockingbird.research.camtrap_dp.build_camtrap_dp_package`'s identical
    "exclude ineligible records exactly once, at this one boundary" shape.
    """

    eligible = [obs for obs in sorted_observations(observations) if obs.eligibility.eligible]
    has_location = options.latitude is not None and options.longitude is not None

    occurrences = [
        DarwinCoreOccurrence(
            occurrence_id=obs.observation_id,
            basis_of_record="MachineObservation",
            event_date=obs.captured_at,
            scientific_name=obs.taxon_scientific_name,
            taxon_rank=("species" if obs.is_species and obs.taxon_scientific_name else None),
            decimal_latitude=options.latitude,
            decimal_longitude=options.longitude,
            coordinate_uncertainty_in_meters=(
                options.coordinate_uncertainty_meters if has_location else None
            ),
            geodetic_datum=("WGS84" if has_location else None),
            occurrence_status="detected",
            identified_by=obs.reviewed_by,
            locality=options.site_name or obs.source_name,
            associated_media=("|".join(f"media/{item.media_id}" for item in obs.evidence) or None),
        )
        for obs in eligible
    ]
    return DarwinCoreArchive(schema_version=DARWIN_CORE_ARCHIVE_SCHEMA_VERSION, occurrences=occurrences)


OCCURRENCE_CSV_FIELDNAMES: tuple[str, ...] = (
    "occurrenceID", "basisOfRecord", "eventDate", "scientificName", "taxonRank",
    "decimalLatitude", "decimalLongitude", "coordinateUncertaintyInMeters", "geodeticDatum",
    "occurrenceStatus", "identifiedBy", "locality", "associatedMedia",
)


def occurrence_to_row(occurrence: DarwinCoreOccurrence) -> dict[str, Any]:
    return {
        "occurrenceID": occurrence.occurrence_id,
        "basisOfRecord": occurrence.basis_of_record,
        "eventDate": occurrence.event_date.isoformat(),
        "scientificName": occurrence.scientific_name,
        "taxonRank": occurrence.taxon_rank,
        "decimalLatitude": occurrence.decimal_latitude,
        "decimalLongitude": occurrence.decimal_longitude,
        "coordinateUncertaintyInMeters": occurrence.coordinate_uncertainty_in_meters,
        "geodeticDatum": occurrence.geodetic_datum,
        "occurrenceStatus": occurrence.occurrence_status,
        "identifiedBy": occurrence.identified_by,
        "locality": occurrence.locality,
        "associatedMedia": occurrence.associated_media,
    }


def build_meta_xml(*, core_filename: str = "occurrence.csv") -> str:
    """A bounded, structurally-valid Darwin Core Archive `meta.xml` -- the
    smallest correct descriptor naming the Occurrence core file and its
    field-to-term mapping (see "Camtrap DP package validation" in
    docs/research-conservation-export-contract.md for the identical
    "smallest structural completeness, not full external conformance"
    precedent this mirrors: no external Frictionless/DwC-A validator was
    integrated hermetically for this milestone either)."""

    occurrence_id_index = OCCURRENCE_CSV_FIELDNAMES.index("occurrenceID")
    fields = "".join(
        f'    <field index="{index}" term="{_DWC_TERM_NAMESPACE}{term}"/>\n'
        for index, term in enumerate(OCCURRENCE_CSV_FIELDNAMES)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<archive xmlns="http://rs.tdwg.org/dwc/text/" metadata="eml.xml">\n'
        '  <core encoding="UTF-8" fieldsTerminatedBy="," linesTerminatedBy="\\n" '
        f"fieldsEnclosedBy='\"' ignoreHeaderLines=\"1\" rowType=\"{_DWC_OCCURRENCE_ROW_TYPE}\">\n"
        f"    <files>\n      <location>{html.escape(core_filename)}</location>\n    </files>\n"
        f'    <id index="{occurrence_id_index}"/>\n'
        f"{fields}"
        "  </core>\n"
        "</archive>\n"
    )


def build_eml_xml(
    *, generated_at: datetime, title: str = "MockingBird ecological observation export",
) -> str:
    """A bounded, structurally-valid minimal EML dataset-metadata document --
    title/abstract/publication date only. Deliberately omits a license,
    contact, or institution claim MockingBird cannot honestly make on the
    exporting user's behalf (see "Licensing" in the governing contract
    doc's Darwin Core/GBIF research: CC-BY-NC is GBIF-supported but
    soft-discouraged, CC0/CC-BY are preferred -- that choice belongs to
    whoever actually publishes this data, not to this bounded personal
    export). A future institutional publication step (Phase 30, explicitly
    deferred) is where those decisions belong."""

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<eml:eml xmlns:eml="eml://ecoinformatics.org/eml-2.1.1" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'packageId="mockingbird-ecological-export" system="mockingbird">\n'
        "  <dataset>\n"
        f"    <title>{html.escape(title)}</title>\n"
        "    <abstract>\n"
        "      <para>Reviewed wildlife observations exported from a local MockingBird "
        "observatory. Location, if present, was explicitly supplied by the exporting "
        "user at export time -- never inferred or defaulted from any other coordinate "
        "setting. No license is asserted by this export; a publisher should choose one "
        "explicitly before any further distribution.</para>\n"
        "    </abstract>\n"
        f"    <pubDate>{generated_at.date().isoformat()}</pubDate>\n"
        "  </dataset>\n"
        "</eml:eml>\n"
    )


__all__ = [
    "DARWIN_CORE_ARCHIVE_SCHEMA_VERSION",
    "DarwinCoreMappingOptions",
    "DarwinCoreOccurrence",
    "DarwinCoreArchive",
    "build_darwin_core_archive",
    "OCCURRENCE_CSV_FIELDNAMES",
    "occurrence_to_row",
    "build_meta_xml",
    "build_eml_xml",
]
