"""The provider-neutral exported-Observation shape and generic research
export row-building (see "Provenance contract" and "Generic research export"
in the governing milestone brief, and docs/research-conservation-export-
contract.md).

One `ResearchObservation` dataclass represents a research-safe exported
record regardless of acquisition provider -- a Camera Node, generic RTSP,
ONVIF, or offline/recorded-media Visit all produce the identical shape, with
only `acquisition_type`/`acquisition_provider` varying (see "ONVIF/RTSP/
Camera Node integration" in the governing brief: never a per-provider
exported-Observation subtype). This module never queries a database; every
value it works with is already resolved by
`ProductRepository._research_observation_for_visit`.

Only a record whose `eligibility.eligible` is true belongs in a *trusted*
export table -- see `mockingbird.research.eligibility`. This module still
carries the full `ResearchExportEligibility` on every `ResearchObservation`
it is handed so a caller can choose to report *why* a record was excluded
without a second lookup.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from mockingbird.research.eligibility import ResearchExportEligibility

AcquisitionType = Literal["continuous_live", "recorded_video", "still_image", "unknown"]
TimestampConfidence = Literal["recorded", "unknown"]

#: The generic research export's own schema version -- bumped only when the
#: exported row *shape* changes, independent of `CURRENT_DATABASE_SCHEMA_
#: VERSION` (see "Versioning / reproducibility" in the governing brief).
RESEARCH_EXPORT_SCHEMA_VERSION = "research-export-v1"


@dataclass(frozen=True)
class ResearchEvidenceRecord:
    """One persisted evidence MediaAsset backing a `ResearchObservation`.
    Never a local filesystem path -- mirrors `api.schemas.VisitEvidenceFrame`'s
    own "never expose its local path" rule. `content_sha256` is included only
    when it was actually computed for this asset (folder-imported/offline
    media only today); `None` is an honest "not computed," never a
    placeholder."""

    media_id: str
    evidence_role: str
    captured_at: datetime | None
    width: int | None
    height: int | None
    content_type: str
    resolution_provenance: str | None
    is_crop: bool
    content_sha256: str | None


@dataclass(frozen=True)
class ResearchObservation:
    """One research-safe exported Observation. See the module docstring for
    why this is the *only* exported-Observation shape regardless of
    acquisition provider."""

    observation_id: str
    event_id: str
    source_id: str
    source_name: str
    stream_id: str
    stream_name: str

    acquisition_type: AcquisitionType
    acquisition_provider: str | None
    is_offline_acquisition: bool

    captured_at: datetime
    captured_at_end: datetime | None
    capture_timestamp_confidence: TimestampConfidence

    review_status: str
    reviewed_at: datetime | None
    # Free-text `ReviewLabelModel.reviewer_identity` from the current
    # authoritative review, reused verbatim (see "Contributor authority" in
    # the governing brief: this is reviewer/contributor attribution, never a
    # new identity system, and it never grants taxonomic authority beyond
    # what the review itself already carries). `None` when no identity was
    # ever recorded -- honest "unattributed," never a fabricated name.
    reviewed_by: str | None

    classification: str
    taxon_label: str | None
    taxon_display_name: str | None
    taxon_scientific_name: str | None
    taxon_category: str | None
    is_species: bool | None

    zone_id: str | None
    zone_name: str | None
    zone_type: str | None

    resolution_provenance: str | None
    evidence: tuple[ResearchEvidenceRecord, ...]

    eligibility: ResearchExportEligibility

    # Machine-classification provenance (see "Camtrap DP truth mapping" in
    # the governing brief): the most recent `SpeciesSuggestion` on this
    # Visit, if any -- exported only as clearly-separated machine provenance
    # (Camtrap DP's own `classificationMethod="machine"` observation row),
    # never blended into the human-validated taxon fields above. `None`
    # throughout when no suggestion was ever produced for this Visit.
    suggested_taxon_label: str | None = None
    suggested_taxon_display_name: str | None = None
    suggested_taxon_scientific_name: str | None = None
    suggested_by: str | None = None
    suggested_confidence: float | None = None
    suggested_at: datetime | None = None


def sorted_observations(observations: list[ResearchObservation]) -> list[ResearchObservation]:
    """Deterministic export order regardless of the database's own row
    order -- see "Deterministic regressions" (#16) in the governing brief.
    Sorted by capture time then observation id (a stable, monotonically
    assigned string -- see `ProductRepository._next_id`), never by
    insertion/scan order."""

    return sorted(observations, key=lambda obs: (obs.captured_at, obs.observation_id))


def observation_to_json(observation: ResearchObservation) -> dict[str, Any]:
    """Deterministic, JSON-safe reshaping of one `ResearchObservation`. Never
    includes ineligibility reason codes in the *value* fields themselves --
    a caller deciding whether to include a record at all should already have
    filtered on `observation.eligibility.eligible` before reaching here;
    this function only reshapes, never filters."""

    return {
        "observation_id": observation.observation_id,
        "event_id": observation.event_id,
        "source_id": observation.source_id,
        "source_name": observation.source_name,
        "stream_id": observation.stream_id,
        "stream_name": observation.stream_name,
        "acquisition_type": observation.acquisition_type,
        "acquisition_provider": observation.acquisition_provider,
        "is_offline_acquisition": observation.is_offline_acquisition,
        "captured_at": observation.captured_at.isoformat(),
        "captured_at_end": observation.captured_at_end.isoformat() if observation.captured_at_end else None,
        "capture_timestamp_confidence": observation.capture_timestamp_confidence,
        "review_status": observation.review_status,
        "reviewed_at": observation.reviewed_at.isoformat() if observation.reviewed_at else None,
        "reviewed_by": observation.reviewed_by,
        "classification": observation.classification,
        "taxon_label": observation.taxon_label,
        "taxon_display_name": observation.taxon_display_name,
        "taxon_scientific_name": observation.taxon_scientific_name,
        "taxon_category": observation.taxon_category,
        "is_species": observation.is_species,
        "zone_id": observation.zone_id,
        "zone_name": observation.zone_name,
        "zone_type": observation.zone_type,
        "resolution_provenance": observation.resolution_provenance,
        "evidence_count": len(observation.evidence),
        "evidence_media_ids": [item.media_id for item in observation.evidence],
        "suggested_taxon_label": observation.suggested_taxon_label,
        "suggested_taxon_display_name": observation.suggested_taxon_display_name,
        "suggested_taxon_scientific_name": observation.suggested_taxon_scientific_name,
        "suggested_by": observation.suggested_by,
        "suggested_confidence": observation.suggested_confidence,
        "suggested_at": observation.suggested_at.isoformat() if observation.suggested_at else None,
    }


#: The stable, ordered field list every `observations.csv` row uses --
#: matches `observation_to_json`'s keys minus the list-valued
#: `evidence_media_ids` (CSV has no native list type), plus a flattened
#: `evidence_ids` column instead.
OBSERVATION_CSV_FIELDNAMES: tuple[str, ...] = (
    "observation_id", "event_id", "source_id", "source_name", "stream_id", "stream_name",
    "acquisition_type", "acquisition_provider", "is_offline_acquisition",
    "captured_at", "captured_at_end", "capture_timestamp_confidence",
    "review_status", "reviewed_at", "reviewed_by", "classification",
    "taxon_label", "taxon_display_name", "taxon_scientific_name", "taxon_category", "is_species",
    "zone_id", "zone_name", "zone_type", "resolution_provenance",
    "evidence_count", "evidence_ids",
    "suggested_taxon_label", "suggested_taxon_display_name", "suggested_taxon_scientific_name",
    "suggested_by", "suggested_confidence", "suggested_at",
)


def observation_to_csv_row(observation: ResearchObservation) -> dict[str, Any]:
    row = observation_to_json(observation)
    row["evidence_ids"] = "|".join(row.pop("evidence_media_ids"))
    return {name: row.get(name) for name in OBSERVATION_CSV_FIELDNAMES}


def media_records_for_observations(
    observations: list[ResearchObservation],
) -> list[dict[str, Any]]:
    """Deduplicated, deterministically-ordered `media.csv`/`media.jsonl` rows
    -- one per distinct evidence MediaAsset referenced by any included
    observation. Never duplicates a media id already emitted for an earlier
    observation."""

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for observation in sorted_observations(observations):
        for item in observation.evidence:
            if item.media_id in seen:
                continue
            seen.add(item.media_id)
            rows.append(
                {
                    "media_id": item.media_id,
                    "observation_id": observation.observation_id,
                    "evidence_role": item.evidence_role,
                    "is_crop": item.is_crop,
                    "captured_at": item.captured_at.isoformat() if item.captured_at else None,
                    "width": item.width,
                    "height": item.height,
                    "content_type": item.content_type,
                    "resolution_provenance": item.resolution_provenance,
                    "content_sha256": item.content_sha256,
                }
            )
    return rows


def source_records_for_observations(observations: list[ResearchObservation]) -> list[dict[str, Any]]:
    """Deduplicated, deterministically-ordered `sources.csv`/`sources.jsonl`
    rows -- one per distinct (source, stream) pair. Carries only safe,
    already-redacted product identity: no credential, token, or local
    filesystem path is a field on `ResearchObservation` in the first place,
    so there is nothing here to accidentally leak (see "Privacy" in the
    governing brief)."""

    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for observation in sorted_observations(observations):
        key = (observation.source_id, observation.stream_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "source_id": observation.source_id,
                "source_name": observation.source_name,
                "stream_id": observation.stream_id,
                "stream_name": observation.stream_name,
            }
        )
    return rows


def observations_content_fingerprint(observations: list[ResearchObservation]) -> str:
    """A cheap, deterministic sha256 over sorted observation ids and their
    classification/taxon -- lets a downstream researcher confirm two exports
    describe the same retained truth (see "Research replication / dataset
    identity" in the governing brief). Not a security hash and never
    includes media bytes -- only enough to detect "did the underlying
    reviewed truth change.\""""

    payload = [
        {
            "observation_id": obs.observation_id,
            "classification": obs.classification,
            "taxon_label": obs.taxon_label,
            "review_status": obs.review_status,
        }
        for obs in sorted_observations(observations)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
