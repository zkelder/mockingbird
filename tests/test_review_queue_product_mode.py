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
from mockingbird.storage.models import CameraSourceModel, EventModel, StreamModel, VisitModel


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


def _durable_counts(repository: ProductRepository) -> tuple[int, int, int, int]:
    with repository.session_factory() as session:
        return (
            session.scalar(select(func.count(EventModel.id))) or 0,
            session.scalar(select(func.count(VisitModel.id))) or 0,
            session.scalar(select(func.count(MotionEvidenceModel.id))) or 0,
            session.scalar(select(func.count(SourceProviderConfigurationModel.source_id)))
            or 0,
        )
