from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    DatasetExportCreate,
    RefinedCropCreateRequest,
    SpeciesSuggestionCreateRequest,
    VisitIdentificationEvidenceMode,
)
from mockingbird.motion.high_resolution_evidence import (
    CaptureProfileGeometry,
    NormalizedGeometryTransform,
    crop_jpeg,
    padded_box,
    validate_refined_crop_box,
    resolve_alignment,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel, VisitModel


SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
client = TestClient(app)


@pytest.fixture
def evidence_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)
    repository.close()


def _jpeg(width: int, height: int) -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[height // 4 : height // 2, width // 4 : width // 2] = (255, 255, 255)
    encoded, output = cv2.imencode(".jpg", image)
    assert encoded
    return output.tobytes()


def _profile(
    profile_id: str,
    *,
    orientation: str = "normal",
    mirrored: bool = False,
    group: str | None = "shared-fov",
    same_fov: bool = True,
) -> CaptureProfileGeometry:
    return CaptureProfileGeometry(
        profile_id=profile_id,
        width=1920 if profile_id == "monitoring" else 9152,
        height=1080 if profile_id == "monitoring" else 6944,
        geometry_group=group,
        orientation=orientation,
        mirrored=mirrored,
        same_fov=same_fov,
    )


def test_aligned_profiles_map_normalized_track_with_orientation_and_mirror() -> None:
    decision = resolve_alignment(
        _profile("monitoring", orientation="normal", mirrored=False),
        _profile("evidence", orientation="rotate_90", mirrored=True),
    )

    assert decision.status == "aligned"
    assert decision.transform is not None
    mapped = decision.transform.map_box((0.2, 0.3, 0.4, 0.6))
    assert mapped == (0.4, 0.6, 0.7, 0.8)
    assert decision.transform.transform_id.startswith("normalized-fov-")


def test_unproven_alignment_preserves_full_still_without_crop_mapping() -> None:
    decision = resolve_alignment(
        _profile("monitoring"),
        _profile("evidence", group="different-fov", same_fov=False),
    )

    assert decision.status == "full_only"
    assert decision.transform is None
    assert decision.failure_code == "geometry_unproven"


def test_padded_crop_stays_inside_image_bounds_and_retains_subject_pixels() -> None:
    padded = padded_box((0.92, 0.90, 0.99, 0.98), padding_ratio=0.35)
    assert padded == pytest.approx((0.8955, 0.872, 1.0, 1.0))

    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[90:99, 92:99] = (255, 255, 255)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    crop = crop_jpeg(encoded.tobytes(), padded)

    assert crop is not None
    assert crop.width == 11
    assert crop.height == 13
    assert crop.normalized_crop_box == pytest.approx((0.89, 0.87, 1.0, 1.0))
    assert len(crop.image) > 0


def test_transform_rejects_invalid_boxes_instead_of_inventing_crop_coordinates() -> None:
    transform = NormalizedGeometryTransform("test")
    assert transform.map_box((0.6, 0.2, 0.4, 0.8)) is None


def test_full_still_crop_lineage_is_primary_review_evidence_without_truth(
    evidence_repository: ProductRepository,
) -> None:
    captured_at = datetime.now(UTC)
    full = evidence_repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(1600, 1000),
        captured_at=captured_at,
        frame_sequence=7,
        evidence_role="high_resolution_original",
        image_width=1600,
        image_height=1000,
        capture_profile_id="evidence-still",
        normalized_track_box=(0.25, 0.25, 0.5, 0.5),
        geometry_transform_id="normalized-fov-test",
        trigger_id="track-7",
        trigger_started_at=captured_at,
        capture_requested_at=captured_at,
        evidence_captured_at=captured_at,
        alignment_status="aligned",
    )
    crop = evidence_repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(400, 300),
        captured_at=captured_at,
        frame_sequence=7,
        parent_media_asset_id=full.id,
        evidence_role="activity_crop",
        image_width=400,
        image_height=300,
        capture_profile_id="evidence-still",
        normalized_track_box=(0.25, 0.25, 0.5, 0.5),
        normalized_padded_crop_box=(0.2, 0.2, 0.55, 0.55),
        geometry_transform_id="normalized-fov-test",
        trigger_id="track-7",
        trigger_started_at=captured_at,
        capture_requested_at=captured_at,
        evidence_captured_at=captured_at,
        alignment_status="aligned",
    )
    with evidence_repository.session_factory() as session:
        with session.begin():
            event = EventModel(
                id="event-high-resolution-evidence",
                stream_id=STREAM_ID,
                title="Tracked activity fixture",
                event_type="motion_evidence",
                started_at=captured_at,
                ended_at=captured_at,
                primary_zone_id="zone-feeder",
                review_status="needs_review",
            )
            session.add(event)
            session.add(
                VisitModel(
                    id="visit-high-resolution-evidence",
                    event_id=event.id,
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id="zone-feeder",
                    is_superseded=False,
                )
            )

    labels_before = len(evidence_repository.list_review_labels())
    frames = evidence_repository.attach_visit_evidence_media_assets(
        "visit-high-resolution-evidence",
        [
            {
                "media_asset_id": full.id,
                "captured_at": captured_at,
                "frame_sequence": 7,
                "is_primary": False,
                "evidence_role": "high_resolution_original",
            },
            {
                "media_asset_id": crop.id,
                "captured_at": captured_at,
                "frame_sequence": 7,
                "is_primary": True,
                "evidence_role": "activity_crop",
            },
        ],
    )

    assert [frame.evidence_role for frame in frames] == [
        "high_resolution_original",
        "activity_crop",
    ]
    assert [frame.media_asset_id for frame in frames if frame.is_primary] == [crop.id]
    assert all(frame.preview_url.endswith("/preview") for frame in frames)
    assert evidence_repository.get_media_asset(crop.id).parent_media_asset_id == full.id
    selected = evidence_repository._review_identification_assistant_frames(
        frames,
        VisitIdentificationEvidenceMode.all_retained_evidence,
    )
    assert [frame.media_asset_id for frame in selected] == [crop.id]
    assert len(evidence_repository.list_review_labels()) == labels_before


def test_review_preview_is_bounded_and_full_resolution_is_explicit(
    evidence_repository: ProductRepository,
) -> None:
    original = _jpeg(2400, 1600)
    asset = evidence_repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=original,
        captured_at=datetime.now(UTC),
        frame_sequence=1,
        evidence_role="high_resolution_original",
        image_width=2400,
        image_height=1600,
    )

    preview = client.get(f"/api/media/{asset.id}/preview")
    original_response = client.get(f"/api/media/{asset.id}/full-resolution")

    assert preview.status_code == 200
    preview_image = cv2.imdecode(
        np.frombuffer(preview.content, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    assert preview.headers["content-type"].startswith("image/jpeg")
    assert preview_image is not None
    assert max(preview_image.shape[:2]) <= 1600
    assert len(preview.content) <= 3_000_000
    assert original_response.status_code == 200
    original_image = cv2.imdecode(
        np.frombuffer(original_response.content, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    assert original_image is not None
    assert original_image.shape[:2] == (1600, 2400)


def _create_refinable_high_resolution_visit(
    repository: ProductRepository,
) -> tuple[str, str, str]:
    captured_at = datetime.now(UTC)
    full = repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(1600, 1000),
        captured_at=captured_at,
        frame_sequence=9,
        evidence_role="high_resolution_original",
        image_width=1600,
        image_height=1000,
    )
    automatic = repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(320, 220),
        captured_at=captured_at,
        frame_sequence=9,
        parent_media_asset_id=full.id,
        evidence_role="activity_crop",
        image_width=320,
        image_height=220,
        normalized_padded_crop_box=(0.2, 0.2, 0.6, 0.6),
    )
    visit_id = "visit-refinable-high-resolution"
    with repository.session_factory() as session:
        with session.begin():
            event = EventModel(
                id="event-refinable-high-resolution",
                stream_id=STREAM_ID,
                title="Refinable tracked activity",
                event_type="motion_evidence",
                started_at=captured_at,
                ended_at=captured_at,
                primary_zone_id="zone-feeder",
                review_status="needs_review",
            )
            session.add(event)
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event.id,
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id="zone-feeder",
                    is_superseded=False,
                )
            )
    repository.attach_visit_evidence_media_assets(
        visit_id,
        [
            {
                "media_asset_id": full.id,
                "captured_at": captured_at,
                "frame_sequence": 9,
                "is_primary": False,
                "evidence_role": "high_resolution_original",
            },
            {
                "media_asset_id": automatic.id,
                "captured_at": captured_at,
                "frame_sequence": 9,
                "is_primary": True,
                "evidence_role": "activity_crop",
            },
        ],
    )
    return visit_id, full.id, automatic.id


def test_refined_crop_validation_rejects_nonfinite_tiny_and_overlarge_boxes() -> None:
    assert validate_refined_crop_box((0.1, 0.1, 0.5, 0.5), image_width=1600, image_height=1000)
    assert validate_refined_crop_box((float("nan"), 0.1, 0.5, 0.5), image_width=1600, image_height=1000) is None
    assert validate_refined_crop_box((0.1, 0.1, 0.11, 0.11), image_width=1600, image_height=1000) is None
    assert validate_refined_crop_box((0.0, 0.0, 1.0, 1.0), image_width=1600, image_height=1000) is None


def test_refined_crop_is_immutable_primary_history_and_stale_suggestion_evidence(
    evidence_repository: ProductRepository,
) -> None:
    visit_id, full_id, automatic_id = _create_refinable_high_resolution_visit(evidence_repository)
    labels_before = len(evidence_repository.list_review_labels())
    evidence_repository.create_species_suggestion(
        SpeciesSuggestionCreateRequest(
            source_id=SOURCE_ID,
            stream_id=STREAM_ID,
            event_id="event-refinable-high-resolution",
            visit_id=visit_id,
            media_asset_id=automatic_id,
            adapter_id="fixture",
            adapter_name="Fixture evidence",
            suggested_label="unknown_bird",
        )
    )

    saved = evidence_repository.create_refined_visit_crop(
        visit_id,
        RefinedCropCreateRequest(left=0.25, top=0.20, right=0.70, bottom=0.72),
    )

    assert saved.created is True
    assert saved.refined_crop.parent_media_asset_id == full_id
    assert saved.refined_crop.derivation_source == "user_refined_crop"
    assert saved.refined_crop.image_width == 720
    assert saved.refined_crop.image_height == 520
    assert saved.refined_crop.content_sha256 == sha256(
        Path(saved.refined_crop.local_path).read_bytes()
    ).hexdigest()
    assert [frame.media_asset_id for frame in saved.evidence_frames if frame.is_primary] == [
        saved.refined_crop.id
    ]
    assert evidence_repository.get_media_asset(automatic_id) is not None
    assert saved.stale_species_suggestions is True
    assert len(evidence_repository.list_review_labels()) == labels_before
    export = evidence_repository.create_dataset_export(
        DatasetExportCreate(
            name="refined crop export fixture",
            reviewed_only=False,
            selected_visit_ids=[visit_id],
        )
    )
    manifest = evidence_repository.build_dataset_manifest(export.id)
    assert manifest is not None
    assert [record.media_path for record in manifest.records if record.visit_id == visit_id] == [
        saved.refined_crop.local_path
    ]
    assert len(evidence_repository.list_review_labels()) == labels_before

    history_count_after_save = len(evidence_repository.visit_curation_history(visit_id))
    repeated = evidence_repository.create_refined_visit_crop(
        visit_id,
        RefinedCropCreateRequest(left=0.25, top=0.20, right=0.70, bottom=0.72),
    )
    assert repeated.created is False
    assert repeated.refined_crop.id == saved.refined_crop.id
    assert len(evidence_repository.visit_curation_history(visit_id)) == history_count_after_save

    revision = evidence_repository.create_refined_visit_crop(
        visit_id,
        RefinedCropCreateRequest(left=0.28, top=0.20, right=0.72, bottom=0.72),
    )
    assert revision.created is True
    assert revision.refined_crop.id != saved.refined_crop.id
    assert revision.refined_crop.previous_effective_crop_media_asset_id == saved.refined_crop.id
    assert len(revision.crop_history) == 3

    restored = evidence_repository.promote_visit_crop_history(visit_id, automatic_id)
    assert restored.refined_crop.id == automatic_id
    assert [frame.media_asset_id for frame in restored.evidence_frames if frame.is_primary] == [automatic_id]
    assert len(evidence_repository.list_review_labels()) == labels_before


def test_refined_crop_rejects_a_visit_without_linked_full_resolution_parent(
    evidence_repository: ProductRepository,
) -> None:
    with pytest.raises(ValueError, match="missing_high_resolution_parent"):
        evidence_repository.create_refined_visit_crop(
            "visit-bird-feeder-001",
            RefinedCropCreateRequest(left=0.2, top=0.2, right=0.6, bottom=0.6),
        )
