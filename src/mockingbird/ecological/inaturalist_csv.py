"""iNaturalist bulk-import CSV builder -- the exact positional 8-column
format iNaturalist's own web importer (`inaturalist.org/observations/
import`) expects, confirmed directly against iNaturalist's own open-source
Rails application (`lib/bulk_observation_file.rb`, checked 2026-08-25): (0)
species_guess, (1) observed_on_string, (2) description, (3) place_guess,
(4) latitude, (5) longitude, (6) tags, (7) geoprivacy. This format carries
NO photo column -- iNaturalist's bulk importer does not support attaching
media at import time (see "Media behavior" in docs/ecological-
interoperability-submission-v1-contract.md); a user who wants a photo on
the resulting observation must add it themselves, after import, on
iNaturalist's own site. This module never calls the network and never
touches a database -- pure formatting only.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import datetime

from mockingbird.csv_safety import csv_injection_safe_value
from mockingbird.ecological.adapters import EcologicalSubmissionCandidate
from mockingbird.time_utils import resolve_host_local_timezone

#: The exact column order iNaturalist's own importer reads positionally --
#: see the module docstring. Never reorder these.
INATURALIST_CSV_COLUMNS: tuple[str, ...] = (
    "species_guess",
    "observed_on_string",
    "description",
    "place_guess",
    "latitude",
    "longitude",
    "tags",
    "geoprivacy",
)


def _observed_on_string(captured_at: datetime) -> str:
    """Full ISO 8601 with an explicit UTC offset -- confirmed (checked
    2026-08-25, `app/models/observation.rb`) to hit iNaturalist's
    unambiguous fast parse path rather than its natural-language `chronic`
    fallback. Converted to this host's actual local time (never a
    longitude-derived guess -- see `mockingbird.time_utils.
    resolve_host_local_timezone`'s own doctrine) so the resulting checklist
    reads in the observer's own civil time, not UTC."""

    local_zone = resolve_host_local_timezone(captured_at)
    return captured_at.astimezone(local_zone).isoformat(timespec="seconds")


def _species_guess(candidate: EcologicalSubmissionCandidate) -> str:
    obs = candidate.research_observation
    mapping = candidate.taxonomy_mapping
    if obs.classification == "confirmed_unidentified_wildlife":
        # iNaturalist's own "Unknown" observation state is the honest
        # representation of confirmed-wildlife-but-unresolved-species --
        # never a fabricated taxon (Phase 6 of the governing brief).
        return ""
    if mapping is not None and mapping.match_status == "matched":
        return mapping.destination_scientific_name or mapping.destination_display_name or ""
    # No confident destination mapping -- fall back to MockingBird's own
    # reviewed label as free text, never a destination id we are not
    # actually confident about (Phase 7: "missing mapping must block
    # automatic destination submission, not fabricate a mapping" -- the
    # *record* itself is already flagged `needs_input` by `destination_
    # eligibility.py`; a caller that still chooses to export this row
    # despite that flag gets an honest, human-readable free-text guess
    # iNaturalist's own community can resolve, never a wrong id).
    return obs.taxon_display_name or obs.taxon_label or ""


def _geoprivacy(candidate: EcologicalSubmissionCandidate) -> str:
    if candidate.location.choice == "none":
        return ""
    # "coarse" and "exact" both submit the coordinate the user explicitly
    # chose; iNaturalist's own "obscured" geoprivacy only affects *public
    # display* -- iNaturalist's servers still receive and permanently store
    # the exact value submitted either way (confirmed directly in
    # `observation.rb`'s `obscure_coordinates`, checked 2026-08-25).
    # MockingBird therefore never claims choosing "obscured" here hides a
    # coordinate *from iNaturalist itself* -- see "Location precision /
    # privacy UX" in the governing contract doc.
    return "obscured" if candidate.location.choice == "coarse" else "open"


def submission_candidate_to_inaturalist_row(candidate: EcologicalSubmissionCandidate) -> dict[str, str]:
    """One candidate -> one CSV row, using the exact column names in
    `INATURALIST_CSV_COLUMNS`. Callers should not include a candidate whose
    `destination_eligibility.eligible` is false in a real batch export --
    see `mockingbird.repository.product_repository.export_ecological_batch`,
    which filters before this function is reached for a real export."""

    obs = candidate.research_observation
    location = candidate.location
    return {
        "species_guess": _species_guess(candidate),
        "observed_on_string": _observed_on_string(obs.captured_at),
        "description": (
            "Recorded by a MockingBird wildlife-camera observatory"
            + (f" (reviewed by {obs.reviewed_by})" if obs.reviewed_by else "")
            + "."
        ),
        "place_guess": location.place_name or "",
        "latitude": f"{location.latitude:.6f}" if location.latitude is not None else "",
        "longitude": f"{location.longitude:.6f}" if location.longitude is not None else "",
        "tags": "mockingbird",
        "geoprivacy": _geoprivacy(candidate),
    }


def build_inaturalist_csv(candidates: Iterable[EcologicalSubmissionCandidate]) -> str:
    """A complete, ready-to-upload CSV body -- the repository layer owns
    where/whether this is written to disk."""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(INATURALIST_CSV_COLUMNS))
    writer.writeheader()
    for candidate in candidates:
        row = submission_candidate_to_inaturalist_row(candidate)
        writer.writerow({name: csv_injection_safe_value(value) for name, value in row.items()})
    return buffer.getvalue()


__all__ = [
    "INATURALIST_CSV_COLUMNS",
    "submission_candidate_to_inaturalist_row",
    "build_inaturalist_csv",
]
