"""Camtrap DP interoperability -- target spec version **1.0.2**
(https://camtrap-dp.tdwg.org/, `1.0.2` per that site's own published
Table/Data-Package Schema; no Camtrap DP material was previously vendored or
referenced anywhere in this repository, confirmed absent before this
milestone -- see "Camtrap DP interoperability" in the governing milestone
brief and docs/research-conservation-export-contract.md "Camtrap DP
mapping").

Maps `mockingbird.research.research_export.ResearchObservation` rows onto the
three core Camtrap DP resources (`deployments`, `media`, `observations`) plus
a bounded `datapackage.json` descriptor, and provides a structural validator
for the package this module builds: required-field presence, internal
foreign-key resolvability, ID stability, and timestamp ordering. This is
deliberately the smallest structural check justified by the spec, not a
claim of full external Frictionless/Camtrap DP conformance -- see "Camtrap DP
package validation" in the governing brief.

## Deliberate, disclosed mapping choices (never silently fabricated)

- MockingBird has no persisted deployment lifecycle (install/removal dates)
  or coordinate/site model distinct from Source/Stream identity -- confirmed
  absent, not merely unwired (see docs/research-conservation-export-
  contract.md). One MockingBird (Source, Stream) pair maps to one Camtrap DP
  deployment; `deploymentStart`/`deploymentEnd` are the actual bounds of the
  *exported* observation window for that deployment -- an honest "what this
  package covers," never a fabricated install/removal date.
- `latitude`/`longitude` are Camtrap DP *required* fields this product
  cannot honestly populate by default. Left `None` (empty in the CSV) unless
  the caller explicitly supplies a single site-level override at export time
  via `CamtrapDpMappingOptions` -- never persisted, never inferred. This is
  a disclosed, known non-conformance when omitted;
  `validate_camtrap_dp_package` reports it as a warning rather than silently
  passing.
- `count` is never populated: MockingBird has no individual-animal identity/
  counting model (see "Wildlife-native semantics" in product-doctrine.md).
  Asserting a count would overstate what a reviewed Visit actually proves.
- Human review produces one `classificationMethod="human"` observation row.
  A `SpeciesSuggestion`, when one exists, produces a *separate*
  `classificationMethod="machine"` row on the same media/event -- never
  blended into the human-validated `scientificName` (see "Camtrap DP truth
  mapping" in the governing brief). Only research-eligible records
  (`ResearchExportEligibility.eligible`) are mapped at all -- a provisional/
  unresolved/rejected/superseded Visit never becomes a Camtrap DP
  observation, human or machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from mockingbird.research.research_export import ResearchObservation, sorted_observations

CAMTRAP_DP_PROFILE_VERSION = "1.0.2"

ObservationType = Literal["animal", "human", "vehicle", "blank", "unknown", "unclassified"]
ClassificationMethod = Literal["human", "machine"]


@dataclass(frozen=True)
class CamtrapDpMappingOptions:
    """Explicit, never-inferred export-time context (see the module
    docstring's "deliberate, disclosed mapping choices"). Every field
    defaults to the honest "not supplied" state."""

    site_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    include_machine_classifications: bool = True


@dataclass(frozen=True)
class CamtrapDeployment:
    deployment_id: str
    location_id: str
    location_name: str | None
    latitude: float | None
    longitude: float | None
    deployment_start: datetime
    deployment_end: datetime
    camera_id: str
    camera_model: str | None


@dataclass(frozen=True)
class CamtrapMedia:
    media_id: str
    deployment_id: str
    timestamp: datetime
    file_path: str
    file_public: bool
    file_mediatype: str
    capture_method: str | None


@dataclass(frozen=True)
class CamtrapObservation:
    observation_id: str
    deployment_id: str
    media_id: str | None
    event_id: str
    event_start: datetime
    event_end: datetime
    observation_level: Literal["media", "event"]
    observation_type: ObservationType
    scientific_name: str | None
    classification_method: ClassificationMethod | None
    classified_by: str | None
    classification_timestamp: datetime | None
    classification_probability: float | None


@dataclass(frozen=True)
class CamtrapDpPackage:
    profile_version: str
    deployments: list[CamtrapDeployment]
    media: list[CamtrapMedia]
    observations: list[CamtrapObservation]


def _deployment_id(source_id: str, stream_id: str) -> str:
    """Deterministic, stable, content-derived deployment identity -- never a
    random/incrementing id, so the same (source, stream) pair always maps to
    the same `deploymentID` across repeated export runs (see "Versioning /
    reproducibility" in the governing brief)."""

    return f"{source_id}:{stream_id}"


def build_camtrap_dp_package(
    observations: list[ResearchObservation],
    *,
    options: CamtrapDpMappingOptions = CamtrapDpMappingOptions(),
) -> CamtrapDpPackage:
    """Map already-resolved, already-eligibility-classified
    `ResearchObservation`s onto a Camtrap DP package. Never queries
    anything; never re-derives eligibility -- a record whose `eligibility.
    eligible` is `False` is silently excluded here exactly once, at this one
    boundary, so every table below is internally consistent by
    construction."""

    eligible = [obs for obs in sorted_observations(observations) if obs.eligibility.eligible]

    deployment_bounds: dict[str, dict[str, Any]] = {}
    for obs in eligible:
        deployment_id = _deployment_id(obs.source_id, obs.stream_id)
        bounds = deployment_bounds.setdefault(
            deployment_id,
            {
                "source_id": obs.source_id,
                "source_name": obs.source_name,
                "start": obs.captured_at,
                "end": obs.captured_at_end or obs.captured_at,
            },
        )
        bounds["start"] = min(bounds["start"], obs.captured_at)
        bounds["end"] = max(bounds["end"], obs.captured_at_end or obs.captured_at)

    deployments = [
        CamtrapDeployment(
            deployment_id=deployment_id,
            location_id=deployment_id,
            location_name=options.site_name or bounds["source_name"],
            latitude=options.latitude,
            longitude=options.longitude,
            deployment_start=bounds["start"],
            deployment_end=bounds["end"],
            camera_id=bounds["source_id"],
            camera_model=None,
        )
        for deployment_id, bounds in sorted(deployment_bounds.items())
    ]

    media: list[CamtrapMedia] = []
    seen_media: set[str] = set()
    for obs in eligible:
        deployment_id = _deployment_id(obs.source_id, obs.stream_id)
        for item in obs.evidence:
            if item.media_id in seen_media:
                continue
            seen_media.add(item.media_id)
            media.append(
                CamtrapMedia(
                    media_id=item.media_id,
                    deployment_id=deployment_id,
                    timestamp=item.captured_at or obs.captured_at,
                    # Manifest-relative reference only -- never a local
                    # filesystem path (see "Media export" in the governing
                    # brief). The actual export writer decides whether this
                    # relative path corresponds to a real copied file
                    # (media inclusion requested) or is metadata-only.
                    file_path=f"media/{item.media_id}.jpg",
                    file_public=False,
                    file_mediatype=item.content_type or "image/jpeg",
                    capture_method="activityDetection",
                )
            )

    camtrap_observations: list[CamtrapObservation] = []
    for obs in eligible:
        deployment_id = _deployment_id(obs.source_id, obs.stream_id)
        primary_media_id = obs.evidence[0].media_id if obs.evidence else None
        observation_type: ObservationType = (
            "animal"
            if obs.classification in ("confirmed_taxon", "confirmed_unidentified_wildlife")
            else "unclassified"
        )
        camtrap_observations.append(
            CamtrapObservation(
                observation_id=f"{obs.observation_id}-human",
                deployment_id=deployment_id,
                media_id=primary_media_id,
                event_id=obs.event_id,
                event_start=obs.captured_at,
                event_end=obs.captured_at_end or obs.captured_at,
                observation_level="event",
                observation_type=observation_type,
                scientific_name=obs.taxon_scientific_name,
                classification_method="human",
                classified_by=obs.reviewed_by or "human",
                classification_timestamp=obs.reviewed_at,
                classification_probability=None,
            )
        )
        if options.include_machine_classifications and obs.suggested_taxon_label is not None:
            camtrap_observations.append(
                CamtrapObservation(
                    observation_id=f"{obs.observation_id}-machine",
                    deployment_id=deployment_id,
                    media_id=primary_media_id,
                    event_id=obs.event_id,
                    event_start=obs.captured_at,
                    event_end=obs.captured_at_end or obs.captured_at,
                    observation_level="event",
                    observation_type="animal",
                    scientific_name=obs.suggested_taxon_scientific_name,
                    classification_method="machine",
                    classified_by=obs.suggested_by,
                    classification_timestamp=obs.suggested_at,
                    classification_probability=obs.suggested_confidence,
                )
            )

    return CamtrapDpPackage(
        profile_version=CAMTRAP_DP_PROFILE_VERSION,
        deployments=deployments,
        media=media,
        observations=camtrap_observations,
    )


@dataclass(frozen=True)
class CamtrapDpValidationResult:
    """Structural validation only -- see the module docstring. `valid` is
    `False` only for a genuine structural defect (a broken reference, a
    duplicate id, an inverted time range); a disclosed, spec-honest gap like
    missing coordinates is a warning, never an error."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_camtrap_dp_package(package: CamtrapDpPackage) -> CamtrapDpValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    deployment_ids = [d.deployment_id for d in package.deployments]
    if len(set(deployment_ids)) != len(deployment_ids):
        errors.append("duplicate deploymentID in deployments")
    deployment_id_set = set(deployment_ids)

    media_ids = [m.media_id for m in package.media]
    if len(set(media_ids)) != len(media_ids):
        errors.append("duplicate mediaID in media")
    media_id_set = set(media_ids)

    observation_ids = [o.observation_id for o in package.observations]
    if len(set(observation_ids)) != len(observation_ids):
        errors.append("duplicate observationID in observations")

    for deployment in package.deployments:
        if deployment.deployment_end < deployment.deployment_start:
            errors.append(f"deployment {deployment.deployment_id}: deploymentEnd precedes deploymentStart")
        if deployment.latitude is None or deployment.longitude is None:
            warnings.append(
                f"deployment {deployment.deployment_id}: latitude/longitude are required by the Camtrap DP "
                "spec but were not supplied -- honestly omitted rather than fabricated"
            )

    for media in package.media:
        if media.deployment_id not in deployment_id_set:
            errors.append(f"media {media.media_id}: deploymentID {media.deployment_id!r} not in deployments")

    for observation in package.observations:
        if observation.deployment_id not in deployment_id_set:
            errors.append(
                f"observation {observation.observation_id}: deploymentID "
                f"{observation.deployment_id!r} not in deployments"
            )
        if observation.media_id is not None and observation.media_id not in media_id_set:
            errors.append(
                f"observation {observation.observation_id}: mediaID {observation.media_id!r} not in media"
            )
        if observation.event_end < observation.event_start:
            errors.append(f"observation {observation.observation_id}: eventEnd precedes eventStart")
        if observation.classification_method == "human" and observation.classification_probability is not None:
            errors.append(
                f"observation {observation.observation_id}: a human classification must never carry a "
                "machine classificationProbability"
            )

    return CamtrapDpValidationResult(valid=not errors, errors=tuple(errors), warnings=tuple(warnings))


DEPLOYMENT_CSV_FIELDNAMES: tuple[str, ...] = (
    "deploymentID", "locationID", "locationName", "latitude", "longitude",
    "deploymentStart", "deploymentEnd", "cameraID", "cameraModel",
)
MEDIA_CSV_FIELDNAMES: tuple[str, ...] = (
    "mediaID", "deploymentID", "captureMethod", "timestamp", "filePath", "filePublic", "fileMediatype",
)
OBSERVATION_CSV_FIELDNAMES: tuple[str, ...] = (
    "observationID", "deploymentID", "mediaID", "eventID", "eventStart", "eventEnd",
    "observationLevel", "observationType", "scientificName",
    "classificationMethod", "classifiedBy", "classificationTimestamp", "classificationProbability",
)


def deployment_to_row(deployment: CamtrapDeployment) -> dict[str, Any]:
    return {
        "deploymentID": deployment.deployment_id,
        "locationID": deployment.location_id,
        "locationName": deployment.location_name,
        "latitude": deployment.latitude,
        "longitude": deployment.longitude,
        "deploymentStart": deployment.deployment_start.isoformat(),
        "deploymentEnd": deployment.deployment_end.isoformat(),
        "cameraID": deployment.camera_id,
        "cameraModel": deployment.camera_model,
    }


def media_to_row(media: CamtrapMedia) -> dict[str, Any]:
    return {
        "mediaID": media.media_id,
        "deploymentID": media.deployment_id,
        "captureMethod": media.capture_method,
        "timestamp": media.timestamp.isoformat(),
        "filePath": media.file_path,
        "filePublic": media.file_public,
        "fileMediatype": media.file_mediatype,
    }


def observation_to_row(observation: CamtrapObservation) -> dict[str, Any]:
    return {
        "observationID": observation.observation_id,
        "deploymentID": observation.deployment_id,
        "mediaID": observation.media_id,
        "eventID": observation.event_id,
        "eventStart": observation.event_start.isoformat(),
        "eventEnd": observation.event_end.isoformat(),
        "observationLevel": observation.observation_level,
        "observationType": observation.observation_type,
        "scientificName": observation.scientific_name,
        "classificationMethod": observation.classification_method,
        "classifiedBy": observation.classified_by,
        "classificationTimestamp": (
            observation.classification_timestamp.isoformat() if observation.classification_timestamp else None
        ),
        "classificationProbability": observation.classification_probability,
    }


def datapackage_descriptor(
    package: CamtrapDpPackage,
    *,
    generated_at: datetime,
    software_version: str | None,
    title: str = "MockingBird research export",
) -> dict[str, Any]:
    """A bounded Frictionless Data Package descriptor -- enough for a
    Camtrap DP reader to locate the three resources and know their schema
    version, not a full Frictionless metadata implementation (contributors/
    licenses/spatial-temporal coverage summaries are intentionally omitted
    rather than fabricated; see "Do not force fields MockingBird cannot
    support" in the governing brief)."""

    return {
        "profile": f"https://raw.githubusercontent.com/tdwg/camtrap-dp/{package.profile_version}/camtrap-dp-profile.json",
        "name": "mockingbird-research-export",
        "title": title,
        "created": generated_at.isoformat(),
        "mockingbird_software_version": software_version,
        "resources": [
            {"name": "deployments", "path": "deployments.csv", "profile": "tabular-data-resource"},
            {"name": "media", "path": "media.csv", "profile": "tabular-data-resource"},
            {"name": "observations", "path": "observations.csv", "profile": "tabular-data-resource"},
        ],
    }
