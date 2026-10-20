"""Pure planning/naming helpers for bundling eligible evidence media bytes
into a research export (see docs/research-export-ecological-workflow-
completion-v1-contract.md, "Media-byte inclusion").

This module never touches a database or the filesystem. It only decides
*names* and *statuses* for media that an already-eligible observation
references; the repository does the safe resolution and copying. Eligibility
is never computed or widened here -- a caller hands in only the observations
that already passed `evaluate_research_export_eligibility`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from mockingbird.research.camtrap_dp import MEDIA_FILE_EXTENSIONS
from mockingbird.research.research_export import ResearchObservation

#: Narrow, explicitly justified bounds (no export-media limit existed before
#: this milestone). Exceeding either refuses the export rather than silently
#: shipping a half-filled bundle.
RESEARCH_EXPORT_MEDIA_MAX_FILES = 2000
RESEARCH_EXPORT_MEDIA_MAX_TOTAL_BYTES = 1024 * 1024 * 1024

BUNDLE_MEDIA_DIRECTORY = "media"
MEDIA_BUNDLE_FILE_NAME = "media-bundle.csv"
MEDIA_BUNDLE_CSV_FIELDNAMES = (
    "media_id", "observation_ids", "bundled_path", "size_bytes", "sha256", "status",
)

STATUS_BUNDLED = "bundled"
STATUS_OMITTED_MISSING = "omitted_missing"
STATUS_OMITTED_UNSAFE_PATH = "omitted_unsafe_path"
STATUS_OMITTED_UNSAFE_NAME = "omitted_unsafe_name"
STATUS_OMITTED_UNSUPPORTED_TYPE = "omitted_unsupported_type"
STATUS_OMITTED_NAME_COLLISION = "omitted_name_collision"
STATUS_OMITTED_INTEGRITY = "omitted_integrity_mismatch"

# A media id becomes a path component inside the bundle, so it must be a plain
# token: no separators, no dot-only names, no leading dot/dash, bounded length.
_SAFE_MEDIA_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class MediaBundleRequest:
    media_id: str
    content_type: str
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class MediaBundleName:
    """Planned in-bundle path, or the reason this media can never be bundled."""

    media_id: str
    relative_path: str | None
    omit_status: str | None


@dataclass(frozen=True)
class MediaBundleEntry:
    media_id: str
    observation_ids: tuple[str, ...]
    bundled_path: str | None
    size_bytes: int | None
    sha256: str | None
    status: str


def media_requests_for_observations(
    observations: Iterable[ResearchObservation],
) -> list[MediaBundleRequest]:
    """One request per distinct media id (deduplicated, sorted by id), each
    carrying every exported observation that references it -- one asset can
    back several observations (sibling subjects of one Event, crops)."""

    content_types: dict[str, str] = {}
    referencing: dict[str, set[str]] = {}
    for observation in observations:
        for item in observation.evidence:
            content_types.setdefault(item.media_id, item.content_type)
            referencing.setdefault(item.media_id, set()).add(observation.observation_id)
    return [
        MediaBundleRequest(
            media_id=media_id,
            content_type=content_types[media_id],
            observation_ids=tuple(sorted(referencing[media_id])),
        )
        for media_id in sorted(content_types)
    ]


def plan_bundle_names(requests: Iterable[MediaBundleRequest]) -> dict[str, MediaBundleName]:
    """Name every request, never trusting stored filenames or paths.

    The extension comes from a fixed content-type allowlist. Names are
    compared case-insensitively so a bundle extracted on a case-insensitive
    filesystem can never have two entries overwrite each other; the earlier
    (sorted) id wins and the later one is omitted, visibly."""

    planned: dict[str, MediaBundleName] = {}
    taken: set[str] = set()
    for request in requests:
        extension = MEDIA_FILE_EXTENSIONS.get(request.content_type)
        if not _SAFE_MEDIA_ID.fullmatch(request.media_id):
            planned[request.media_id] = MediaBundleName(request.media_id, None, STATUS_OMITTED_UNSAFE_NAME)
            continue
        if extension is None:
            planned[request.media_id] = MediaBundleName(request.media_id, None, STATUS_OMITTED_UNSUPPORTED_TYPE)
            continue
        relative = f"{BUNDLE_MEDIA_DIRECTORY}/{request.media_id}{extension}"
        key = relative.lower()
        if key in taken:
            planned[request.media_id] = MediaBundleName(request.media_id, None, STATUS_OMITTED_NAME_COLLISION)
            continue
        taken.add(key)
        planned[request.media_id] = MediaBundleName(request.media_id, relative, None)
    return planned


def entry_to_row(entry: MediaBundleEntry) -> dict[str, object]:
    return {
        "media_id": entry.media_id,
        "observation_ids": "|".join(entry.observation_ids),
        "bundled_path": entry.bundled_path,
        "size_bytes": entry.size_bytes,
        "sha256": entry.sha256,
        "status": entry.status,
    }
