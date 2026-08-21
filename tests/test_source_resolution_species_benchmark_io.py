"""Real-cohort loader tests for the source-resolution species benchmark --
builds a small, real sqlite database via `ProductRepository` (mirroring the
established `tests/test_native_resolution_species_evidence.py` direct-
construction pattern), then proves `copy_database_for_read_only_analysis`
never touches the original and `load_resolution_evidence_pairs` reads real
rows correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from mockingbird.observation.source_resolution_species_benchmark_io import (
    copy_database_for_read_only_analysis,
    load_resolution_evidence_pairs,
)
from mockingbird.repository.product_repository import MediaAssetModel, ProductRepository, VisitEvidenceLinkModel
from mockingbird.storage.models import CameraSourceModel, EventModel, StreamModel, VisitModel

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)


def _build_fixture_database(db_path: Path, media_root: Path) -> None:
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        with repository.session_factory() as session:
            with session.begin():
                session.add(CameraSourceModel(id="source-1", name="x", kind="camera_node", status="active", description="x"))
                session.add(StreamModel(id="stream-1", source_id="source-1", name="x", description="x", is_live=True))
                session.add(EventModel(
                    id="event-1", stream_id="stream-1", title="x", event_type="motion_evidence",
                    started_at=NOW, ended_at=NOW, primary_zone_id=None, review_status="needs_review",
                ))
                session.add(VisitModel(
                    id="visit-1", event_id="event-1", subject_label="unknown_bird", species_guess=None,
                    confidence=None, reviewed_label="house_finch", review_status="reviewed",
                    representative_media_path=None, zone_id=None, is_superseded=False,
                ))
                session.add(MediaAssetModel(
                    id="native-1", source_id="source-1", stream_id="stream-1", filename="native-1.jpg",
                    content_type="image/jpeg", media_type="image", local_path="unused.jpg",
                    original_filename="native-1.jpg", file_size_bytes=1000, created_at=NOW,
                    evidence_role="high_resolution_original", image_width=4624, image_height=3472,
                ))
                session.add(MediaAssetModel(
                    id="crop-1", source_id="source-1", stream_id="stream-1", filename="crop-1.jpg",
                    content_type="image/jpeg", media_type="image", local_path="unused.jpg",
                    original_filename="crop-1.jpg", file_size_bytes=100, created_at=NOW,
                    parent_media_asset_id="native-1", evidence_role="activity_crop",
                    image_width=279, image_height=99,
                    normalized_track_box_json=json.dumps([0.44475, 0.4222, 0.48015, 0.43885]),
                ))
                # A second, sibling crop for the same real Visit -- proves
                # sibling_native_candidate_count reflects real availability.
                session.add(MediaAssetModel(
                    id="native-2", source_id="source-1", stream_id="stream-1", filename="native-2.jpg",
                    content_type="image/jpeg", media_type="image", local_path="unused.jpg",
                    original_filename="native-2.jpg", file_size_bytes=1000, created_at=NOW,
                    evidence_role="high_resolution_original", image_width=4624, image_height=3472,
                ))
                session.add(MediaAssetModel(
                    id="crop-2", source_id="source-1", stream_id="stream-1", filename="crop-2.jpg",
                    content_type="image/jpeg", media_type="image", local_path="unused.jpg",
                    original_filename="crop-2.jpg", file_size_bytes=100, created_at=NOW,
                    parent_media_asset_id="native-2", evidence_role="activity_crop",
                    image_width=300, image_height=120,
                    normalized_track_box_json=json.dumps([0.50, 0.50, 0.55, 0.53]),
                ))
                # An unusable row: activity_crop with no parent (must be
                # skipped, never crash the loader).
                session.add(MediaAssetModel(
                    id="crop-orphan", source_id="source-1", stream_id="stream-1", filename="crop-orphan.jpg",
                    content_type="image/jpeg", media_type="image", local_path="unused.jpg",
                    original_filename="crop-orphan.jpg", file_size_bytes=100, created_at=NOW,
                    evidence_role="activity_crop", image_width=50, image_height=50,
                ))
                session.add(VisitEvidenceLinkModel(
                    id="link-1", visit_id="visit-1", media_asset_id="crop-1",
                    captured_at=NOW, created_at=NOW, sort_order=0, is_primary=True, evidence_role="activity_crop",
                ))
                session.add(VisitEvidenceLinkModel(
                    id="link-2", visit_id="visit-1", media_asset_id="crop-2",
                    captured_at=NOW, created_at=NOW, sort_order=1, is_primary=False, evidence_role="activity_crop",
                ))
                session.add(VisitEvidenceLinkModel(
                    id="link-orphan", visit_id="visit-1", media_asset_id="crop-orphan",
                    captured_at=NOW, created_at=NOW, sort_order=2, is_primary=False, evidence_role="activity_crop",
                ))
    finally:
        repository.close()


def test_copy_never_touches_the_original_and_loader_reads_real_rows(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    db_path = source_dir / "mockingbird.sqlite3"
    _build_fixture_database(db_path, source_dir / "media")
    original_bytes = db_path.read_bytes()

    workspace = tmp_path / "workspace"
    copy_path = copy_database_for_read_only_analysis(db_path, workspace=workspace)
    assert copy_path != db_path
    assert copy_path.read_bytes() == original_bytes

    pairs, summary = load_resolution_evidence_pairs(copy_path, media_root=source_dir)

    # The original file is provably untouched by anything the loader did.
    assert db_path.read_bytes() == original_bytes

    assert summary.total_candidate_rows == 3
    assert summary.usable_pairs == 2
    assert summary.skipped_missing_parent == 1

    by_media_id = {pair.media_asset_id: pair for pair in pairs}
    assert set(by_media_id) == {"crop-1", "crop-2"}
    first = by_media_id["crop-1"]
    assert first.visit_id == "visit-1"
    assert first.reviewed_label == "house_finch"
    assert first.native_source_width == 4624
    assert first.native_source_height == 3472
    assert first.native_crop_width == 279
    assert first.native_crop_height == 99
    assert first.subject_box_normalized == pytest.approx((0.44475, 0.4222, 0.48015, 0.43885))
    # Both real crops belong to the same real Visit -- each sees the other
    # as one genuine sibling candidate.
    assert first.sibling_native_candidate_count == 1
    assert by_media_id["crop-2"].sibling_native_candidate_count == 1


def test_copy_rejects_a_missing_source_database(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        copy_database_for_read_only_analysis(tmp_path / "does-not-exist.sqlite3", workspace=tmp_path / "ws")


def test_loader_respects_max_pairs_bound(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    db_path = source_dir / "mockingbird.sqlite3"
    _build_fixture_database(db_path, source_dir / "media")
    copy_path = copy_database_for_read_only_analysis(db_path, workspace=tmp_path / "workspace")

    pairs, _summary = load_resolution_evidence_pairs(copy_path, media_root=source_dir, max_pairs=1)
    assert len(pairs) == 1
