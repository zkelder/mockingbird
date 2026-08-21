"""Real-cohort loading for the source-resolution species benchmark (see
`source_resolution_species_benchmark.py`, which stays pure). This is the
one module allowed to touch a real product database/filesystem.

Safety rule (never weaken this): a caller-supplied database is always
copied to a caller-owned scratch path before this module opens it --
`ProductRepository`'s own startup can apply schema migrations, and this
benchmark must never risk mutating someone's real, in-use product database
merely by reading it for analysis. See `copy_database_for_read_only_analysis`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from sqlalchemy import select

from mockingbird.observation.source_resolution_species_benchmark import ResolutionEvidencePair
from mockingbird.repository.product_repository import MediaAssetModel, ProductRepository, VisitEvidenceLinkModel, VisitModel

# The one real, already-persisted evidence relationship this loader knows
# how to read: a derived crop (`activity_crop`) whose own `parent_media_
# asset_id` points to the real native-resolution image it was cropped from.
# This is real, existing product data (the "high-resolution evidence"
# feature predating this milestone -- see `mockingbird.motion.high_
# resolution_evidence`), not data produced by this milestone's own new
# code -- used here strictly as a source of genuine paired native/derived-
# crop imagery for the benchmark, never claimed to be `resolution_
# provenance="synchronized"` evidence from the new schema.
NATIVE_DERIVED_CROP_EVIDENCE_ROLE = "activity_crop"


@dataclass(frozen=True)
class CohortLoadSummary:
    """What the loader actually found, for an honest report even before any
    comparison metric is computed."""

    total_candidate_rows: int
    usable_pairs: int
    skipped_missing_dimensions: int
    skipped_missing_box: int
    skipped_missing_parent: int


def copy_database_for_read_only_analysis(source_db_path: Path, *, workspace: Path) -> Path:
    """Copy `source_db_path` into `workspace` and return the copy's path.
    Never opens `source_db_path` itself -- every subsequent read in this
    module operates on the copy, so this benchmark cannot mutate a real,
    possibly still-in-use product database."""

    if not source_db_path.is_file():
        raise ValueError("source_database_not_found")
    workspace.mkdir(parents=True, exist_ok=True)
    destination = workspace / source_db_path.name
    shutil.copy2(source_db_path, destination)
    return destination


def load_resolution_evidence_pairs(
    db_path: Path, *, media_root: Path, max_pairs: int | None = None,
) -> tuple[tuple[ResolutionEvidencePair, ...], CohortLoadSummary]:
    """Load every real, usable (derived native-resolution crop, real native
    parent, real Visit) triple from `db_path` -- which the caller must
    already have produced via `copy_database_for_read_only_analysis` -- as
    pure `ResolutionEvidencePair` records.

    `media_root` is only used to resolve a MediaAsset's own `local_path`
    when computing sibling counts does not need pixel bytes -- this loader
    never opens/decodes an image; only the DB's own already-recorded
    `image_width`/`image_height`/`normalized_track_box_json` facts are used
    (real facts computed once when the media was originally imported/
    captured, not re-derived here).
    """

    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        with repository.session_factory() as session:
            links = session.scalars(
                select(VisitEvidenceLinkModel).where(
                    VisitEvidenceLinkModel.evidence_role == NATIVE_DERIVED_CROP_EVIDENCE_ROLE
                )
            ).all()
            total_candidate_rows = len(links)
            # First pass: which visits have more than one usable crop, so
            # `sibling_native_candidate_count` reflects real availability
            # rather than an artifact of iteration order.
            by_visit: dict[str, list[tuple[VisitEvidenceLinkModel, MediaAssetModel, MediaAssetModel]]] = {}
            skipped_missing_dimensions = 0
            skipped_missing_box = 0
            skipped_missing_parent = 0
            for link in links:
                crop = session.get(MediaAssetModel, link.media_asset_id)
                if crop is None:
                    continue
                if crop.parent_media_asset_id is None:
                    skipped_missing_parent += 1
                    continue
                native = session.get(MediaAssetModel, crop.parent_media_asset_id)
                if native is None:
                    skipped_missing_parent += 1
                    continue
                if not crop.image_width or not crop.image_height or not native.image_width or not native.image_height:
                    skipped_missing_dimensions += 1
                    continue
                box = _decode_box(crop.normalized_track_box_json) or _decode_box(native.normalized_track_box_json)
                if box is None:
                    skipped_missing_box += 1
                    continue
                by_visit.setdefault(link.visit_id, []).append((link, crop, native))

            pairs: list[ResolutionEvidencePair] = []
            for visit_id, items in by_visit.items():
                visit = session.get(VisitModel, visit_id)
                reviewed_label = visit.reviewed_label if visit is not None else None
                for link, crop, native in items:
                    box = _decode_box(crop.normalized_track_box_json) or _decode_box(native.normalized_track_box_json)
                    assert box is not None
                    pairs.append(ResolutionEvidencePair(
                        visit_id=visit_id,
                        media_asset_id=crop.id,
                        reviewed_label=reviewed_label,
                        subject_box_normalized=box,
                        native_source_width=native.image_width,
                        native_source_height=native.image_height,
                        native_crop_width=crop.image_width,
                        native_crop_height=crop.image_height,
                        sibling_native_candidate_count=len(items) - 1,
                    ))
            if max_pairs is not None:
                pairs = pairs[:max_pairs]
            summary = CohortLoadSummary(
                total_candidate_rows=total_candidate_rows,
                usable_pairs=len(pairs),
                skipped_missing_dimensions=skipped_missing_dimensions,
                skipped_missing_box=skipped_missing_box,
                skipped_missing_parent=skipped_missing_parent,
            )
            return tuple(pairs), summary
    finally:
        repository.close()


def _decode_box(payload: str | None) -> tuple[float, float, float, float] | None:
    if not payload:
        return None
    import json

    try:
        values = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(values, list) or len(values) != 4:
        return None
    try:
        left, top, right, bottom = (float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0):
        return None
    return (left, top, right, bottom)


__all__ = [
    "CohortLoadSummary",
    "NATIVE_DERIVED_CROP_EVIDENCE_ROLE",
    "copy_database_for_read_only_analysis",
    "load_resolution_evidence_pairs",
]
