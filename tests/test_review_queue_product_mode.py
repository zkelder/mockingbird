from __future__ import annotations

from datetime import UTC, datetime
import json

from sqlalchemy import func, select

from mockingbird.api.schemas import ReviewStatus, SourceKind, SourceStatus
from mockingbird.repository.product_repository import (
    MotionEvidenceModel,
    ProductRepository,
    SourceProviderConfigurationModel,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
)


def test_review_queue_product_categories_are_durable_and_reviewed_is_opt_in(tmp_path) -> None:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'review.sqlite3'}")
    source_id = "source-product-mode"
    stream_id = "stream-product-mode"
    now = datetime(2026, 7, 28, 18, 30, tzinfo=UTC)

    categories = {
        "animal": {"class": "animal", "score": 0.752},
        "person": {"class": "person", "score": 0.91},
        "vehicle": {"class": "vehicle", "score": 0.88},
        "ambiguous": {"class": "unrecognized", "score": 0.5},
        "legacy": None,
        "unchecked": "no_evidence",
        "reviewed": {"class": "animal", "score": 0.63},
    }
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=source_id,
                    name="Product Mode Camera",
                    kind=SourceKind.integration.value,
                    status=SourceStatus.connected.value,
                    description="A real-source provenance fixture.",
                )
            )
            session.add(
                SourceProviderConfigurationModel(
                    source_id=source_id,
                    provider_key="camera_node",
                    config_json="{}",
                    updated_at=now,
                )
            )
            session.add(
                StreamModel(
                    id=stream_id,
                    source_id=source_id,
                    name="Product Mode Stream",
                    description="Fixture stream",
                    is_live=True,
                )
            )
            for name, detector in categories.items():
                event_id = f"event-{name}"
                visit_id = f"visit-{name}"
                review_status = (
                    ReviewStatus.reviewed.value
                    if name == "reviewed"
                    else ReviewStatus.needs_review.value
                )
                session.add(
                    EventModel(
                        id=event_id,
                        stream_id=stream_id,
                        title=name,
                        event_type="fixture",
                        started_at=now,
                        ended_at=now,
                        primary_zone_id=None,
                        review_status=review_status,
                    )
                )
                session.add(
                    VisitModel(
                        id=visit_id,
                        event_id=event_id,
                        subject_label="unknown_animal",
                        species_guess=None,
                        confidence=None,
                        reviewed_label="bird" if name == "reviewed" else None,
                        review_status=review_status,
                        representative_media_path=None,
                        zone_id=None,
                        is_superseded=False,
                    )
                )
                if name == "animal":
                    session.add(
                        MediaAssetModel(
                            id="media-animal",
                            source_id=source_id,
                            stream_id=stream_id,
                            filename="animal.jpg",
                            content_type="image/jpeg",
                            media_type="image",
                            local_path="fixture/animal.jpg",
                            original_filename="animal.jpg",
                            file_size_bytes=12,
                            created_at=now,
                            notes="Product Mode effective-primary fixture.",
                            evidence_role="activity_crop",
                            image_width=300,
                            image_height=300,
                            normalized_track_box_json=json.dumps([0.4, 0.4, 0.5, 0.5]),
                            normalized_padded_crop_box_json=json.dumps([0.3, 0.3, 0.7, 0.7]),
                        )
                    )
                    session.add(
                        VisitEvidenceLinkModel(
                            id="link-animal",
                            visit_id=visit_id,
                            media_asset_id="media-animal",
                            captured_at=now,
                            frame_sequence=0,
                            sort_order=0,
                            is_primary=True,
                            evidence_role="activity_crop",
                            created_at=now,
                        )
                    )
                if detector == "no_evidence":
                    continue
                detector_evidence = (
                    {"current_track": {"track_generation_id": f"generation-{name}", **detector}}
                    if detector is not None
                    else {"tracks": [{"track_generation_id": "motion-only"}]}
                )
                if name == "animal":
                    detector_evidence["object_detector"] = {
                        "detections": [{"class": "vehicle", "score": 0.84}],
                        "triggers": [{"class": "animal", "score": 0.752}],
                        "tracks": [{"class": "animal", "score": 0.752}],
                    }

                session.add(
                    MotionEvidenceModel(
                        id=f"evidence-{name}",
                        source_id=source_id,
                        stream_id=stream_id,
                        zone_id=None,
                        start_frame_index=None,
                        end_frame_index=None,
                        best_frame_index=None,
                        start_time=None,
                        end_time=None,
                        best_frame_time=None,
                        peak_changed_ratio=0.1,
                        triggered_frame_count=1,
                        scoring_config_json=json.dumps(
                            {"detector_evidence": json.dumps(detector_evidence)}
                        ),
                        snapshot_media_asset_id=None,
                        status="promoted",
                        promoted_event_id=event_id,
                        promoted_visit_id=visit_id,
                        created_at=now,
                        notes=None,
                    )
                )

    durable_counts_before_view = _durable_counts(repository)
    unresolved = {
        item.visit_id: item
        for item in repository.review_queue_items()
        if item.visit_id and item.stream_id == stream_id
    }
    assert set(unresolved) == {
        "visit-animal",
        "visit-person",
        "visit-legacy",
        "visit-vehicle",
        "visit-ambiguous",
        "visit-unchecked",
    }
    assert unresolved["visit-animal"].product_category == "animal"
    assert unresolved["visit-animal"].detector_class == "animal"
    assert unresolved["visit-animal"].detector_score == 0.752
    assert unresolved["visit-animal"].detector_provenance["object_detector"]["triggers"][0]["class"] == "animal"
    assert unresolved["visit-animal"].track_generation_id == "generation-animal"
    assert unresolved["visit-animal"].is_demo_source is False
    effective_primary = unresolved["visit-animal"].effective_primary
    assert effective_primary is not None
    assert effective_primary.selected_media_asset_id == "media-animal"
    assert effective_primary.persisted_primary_media_asset_id == "media-animal"
    assert effective_primary.recommended_effective_primary_media_asset_id == "media-animal"
    assert effective_primary.selection_reason == "no_useful_primary_evidence"
    assert effective_primary.is_useful is False
    assert effective_primary.is_user_controlled is False
    assert effective_primary.temporally_supported is None
    assert effective_primary.containment_status is True
    assert effective_primary.edge_clipped is False
    assert effective_primary.candidate_count == 1
    assert effective_primary.historical_preview_only is False
    assert effective_primary.would_change_automatically is False
    assert sum(item.visit_id == "visit-animal" for item in unresolved.values()) == 1
    assert unresolved["visit-vehicle"].product_category == "other_activity"
    assert unresolved["visit-ambiguous"].product_category == "legacy_activity"
    assert unresolved["visit-person"].product_category == "other_activity"
    assert unresolved["visit-legacy"].product_category == "legacy_activity"
    assert unresolved["visit-unchecked"].product_category == "unchecked"

    with_reviewed = {
        item.visit_id: item
        for item in repository.review_queue_items(include_reviewed=True)
        if item.visit_id and item.stream_id == stream_id
    }
    assert with_reviewed["visit-reviewed"].product_category == "reviewed"
    assert len({item.target_id for item in with_reviewed.values()}) == len(with_reviewed)

    dashboard = repository.dashboard_summary(now=now)
    assert dashboard.headline.actionable_animal_visit_count == 1
    assert [visit.id for visit in dashboard.actionable_animal_visits] == ["visit-animal"]
    assert dashboard.headline.legacy_activity_count >= 1
    assert _durable_counts(repository) == durable_counts_before_view

    with repository.session_factory() as session:
        with session.begin():
            source = session.get(CameraSourceModel, source_id)
            provider = session.get(SourceProviderConfigurationModel, source_id)
            assert source is not None
            assert provider is not None
            source.kind = SourceKind.demo.value
            provider.provider_key = "demo"

    demo_item = next(
        item
        for item in repository.review_queue_items()
        if item.visit_id == "visit-animal"
    )
    assert demo_item.product_category == "legacy_activity"
    assert demo_item.is_demo_source is True


def test_imported_visits_without_detector_evidence_are_product_category_animal(tmp_path) -> None:
    """Whole-Product UI / Accessibility / Performance Closure v1 regression.

    Manually imported (`event_type == "manual_media_import"`) and folder
    -imported (`event_type == "folder_media_import"`) Visits never run the
    object detector and never populate `MotionEvidenceModel`, so before this
    fix they always fell through `_review_queue_triage_fields` to
    `product_category == "unchecked"` regardless of `subject_label` --
    exactly the same gap the `observation_engine_candidate`/
    `acoustic_observation_candidate` fallback above already closed for other
    event types. Review Queue's default "Animals" tab excludes "unchecked"
    items, so real imported wildlife photos -- the default, promoted
    acquisition path for a camera-less setup -- were invisible from the
    product's own default review view. This is the real, previously
    misattributed root cause of `web/e2e/reviewed-product-loop.spec.ts`'s
    long-standing failure.
    """
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'imported.sqlite3'}")
    source_id = "source-import-fixture"
    stream_id = "stream-import-fixture"
    now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=source_id,
                    name="Import Fixture Camera",
                    kind=SourceKind.manual_upload.value,
                    status=SourceStatus.connected.value,
                    description="Non-demo source for import-classification fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=stream_id,
                    source_id=source_id,
                    name="Import Fixture Stream",
                    description="Fixture stream",
                    is_live=False,
                )
            )
            for event_type, visit_id, subject_label in (
                ("manual_media_import", "visit-manual-default", "unknown_animal"),
                ("folder_media_import", "visit-folder-default", "unknown_animal"),
                ("manual_media_import", "visit-manual-person", "person"),
            ):
                event_id = f"event-{visit_id}"
                session.add(
                    EventModel(
                        id=event_id,
                        stream_id=stream_id,
                        title=visit_id,
                        event_type=event_type,
                        started_at=now,
                        ended_at=now,
                        primary_zone_id=None,
                        review_status=ReviewStatus.needs_review.value,
                    )
                )
                session.add(
                    VisitModel(
                        id=visit_id,
                        event_id=event_id,
                        subject_label=subject_label,
                        species_guess=None,
                        confidence=None,
                        reviewed_label=None,
                        review_status=ReviewStatus.needs_review.value,
                        representative_media_path=None,
                        zone_id=None,
                        is_superseded=False,
                    )
                )

    items = {
        item.visit_id: item
        for item in repository.review_queue_items()
        if item.visit_id and item.stream_id == stream_id
    }
    assert items["visit-manual-default"].product_category == "animal"
    assert items["visit-manual-default"].detector_class == "animal"
    assert items["visit-folder-default"].product_category == "animal"
    assert items["visit-folder-default"].detector_class == "animal"
    # A user-supplied "person"/"vehicle" subject_label still correctly
    # routes away from the Animals tab -- the fix only reclassifies the
    # genuinely-wildlife default, it does not blindly mark every import
    # "animal".
    assert items["visit-manual-person"].product_category == "other_activity"
    assert items["visit-manual-person"].detector_class == "person"


def test_create_media_import_is_reviewable_from_the_default_animals_tab(tmp_path) -> None:
    """End-to-end proof against the real production entry point
    (`ProductRepository.create_media_import`, what `POST /api/media-import`
    actually calls on a user's behalf): an imported photo with the default
    subject_label must be findable via the same `review_queue_items()` call
    the frontend's default "Animals" tab reads, not merely correctly
    classified in isolation."""
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'e2e-import.sqlite3'}")
    source_id = "source-e2e-import"
    stream_id = "stream-e2e-import"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=source_id,
                    name="E2E Import Camera",
                    kind=SourceKind.manual_upload.value,
                    status=SourceStatus.connected.value,
                    description="Non-demo source for the real create_media_import path.",
                )
            )
            session.add(
                StreamModel(
                    id=stream_id,
                    source_id=source_id,
                    name="E2E Import Stream",
                    description="Fixture stream",
                    is_live=False,
                )
            )

    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"
    import_result = repository.create_media_import(
        content=jpeg_bytes,
        original_filename="backyard-visitor.jpg",
        content_type="image/jpeg",
        stream_id=stream_id,
    )

    animal_tab_visit_ids = {
        item.visit_id
        for item in repository.review_queue_items()
        if item.product_category == "animal"
    }
    assert import_result.visit.id in animal_tab_visit_ids


def _durable_counts(repository: ProductRepository) -> tuple[int, int, int, int]:
    with repository.session_factory() as session:
        return (
            session.scalar(select(func.count(EventModel.id))) or 0,
            session.scalar(select(func.count(VisitModel.id))) or 0,
            session.scalar(select(func.count(MotionEvidenceModel.id))) or 0,
            session.scalar(select(func.count(SourceProviderConfigurationModel.source_id)))
            or 0,
        )
