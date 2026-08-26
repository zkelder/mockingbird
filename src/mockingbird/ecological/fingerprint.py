"""Deterministic content fingerprinting for one ecological-submission
candidate (Phase 35 of the governing contract doc: "Export
reproducibility"). Mirrors `mockingbird.research.research_export.
observations_content_fingerprint`'s identical shape and guarantee: the
same retained Reviewed truth, the same destination, the same taxonomy
mapping, and the same explicit location/media choices always produce the
same fingerprint -- a correction, a changed mapping, or a changed consent
choice always changes it (Phase 32: a stale fingerprint is the signal a
previously-prepared package must be rebuilt before use, never silently
reused). Not a security hash -- a cheap, stable sha256 over exactly the
facts that make one submission package identical to, or different from,
another.
"""

from __future__ import annotations

import hashlib
import json

from mockingbird.ecological.adapters import EcologicalSubmissionCandidate


def submission_candidate_fingerprint(candidate: EcologicalSubmissionCandidate) -> str:
    obs = candidate.research_observation
    mapping = candidate.taxonomy_mapping
    payload = {
        "observation_id": obs.observation_id,
        "destination": candidate.destination,
        "classification": obs.classification,
        "taxon_label": obs.taxon_label,
        "review_status": obs.review_status,
        "reviewed_at": obs.reviewed_at.isoformat() if obs.reviewed_at else None,
        "taxonomy_mapping": (
            {
                "match_status": mapping.match_status,
                "destination_taxon_id": mapping.destination_taxon_id,
                "taxonomy_source_version": mapping.taxonomy_source_version,
            }
            if mapping is not None
            else None
        ),
        "location": {
            "choice": candidate.location.choice,
            "latitude": candidate.location.latitude,
            "longitude": candidate.location.longitude,
            "place_name": candidate.location.place_name,
        },
        "media": {
            "policy": candidate.media.policy,
            "media_asset_id": candidate.media.media_asset_id,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["submission_candidate_fingerprint"]
