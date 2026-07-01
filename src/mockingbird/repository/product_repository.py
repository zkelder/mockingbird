"""Repository for persisted MockingBird product state."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from mockingbird.api import demo_data
from mockingbird.api.schemas import (
    AnalyticsSummary,
    BoundingBox,
    CameraSource,
    DatasetExport,
    DatasetExportCreate,
    DatasetExportDetail,
    DatasetExportManifest,
    DatasetExportRecord,
    Detection,
    Event,
    ExportStatus,
    Point,
    ReviewCorrectionCreate,
    ReviewCorrectionResult,
    ReviewLabel,
    ReviewQueueItem,
    ReviewStatus,
    SourceKind,
    SourceStatus,
    Stream,
    Visit,
    Zone,
    ZoneCreate,
    ZoneType,
    ZoneUpdate,
)
from mockingbird.storage.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    DatasetExportModel,
    DetectionModel,
    EventModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)


class ProductRepository:
    """Persist product-level stream, zone, event, review, and export state.

    Source adapters will normalize activity into these tables later; they do not
    define the core product model.
    """

    def __init__(self, db_url: str | None = None, engine: Engine | None = None) -> None:
        self.engine = engine or create_database_engine(db_url)
        initialize_database(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.seed_if_empty()

    def seed_if_empty(self) -> None:
        with self.session_factory() as session:
            with session.begin():
                source_count = session.scalar(select(func.count(CameraSourceModel.id))) or 0
                if source_count > 0:
                    return

                (
                    sources,
                    streams,
                    zones,
                    events,
                    visits,
                    review_labels,
                    dataset_exports,
                ) = demo_data.seed_product_data()

                session.add_all(
                    [
                        CameraSourceModel(
                            id=source.id,
                            name=source.name,
                            kind=source.kind.value,
                            status=source.status.value,
                            description=source.description,
                        )
                        for source in sources
                    ]
                )
                session.add_all(
                    [
                        StreamModel(
                            id=stream.id,
                            source_id=stream.source_id,
                            name=stream.name,
                            description=stream.description,
                            is_live=stream.is_live,
                        )
                        for stream in streams
                    ]
                )
                session.add_all(
                    [
                        ZoneModel(
                            id=zone.id,
                            stream_id=zone.stream_id,
                            name=zone.name,
                            zone_type=zone.zone_type.value,
                            polygon_json=_points_to_json(zone.polygon),
                            is_active=zone.is_active,
                        )
                        for zone in zones
                    ]
                )
                session.add_all(
                    [
                        EventModel(
                            id=event.id,
                            stream_id=event.stream_id,
                            title=event.title,
                            event_type=event.event_type,
                            started_at=event.started_at,
                            ended_at=event.ended_at,
                            primary_zone_id=event.primary_zone_id,
                            review_status=event.review_status.value,
                        )
                        for event in events
                    ]
                )
                session.add_all(
                    [
                        DetectionModel(
                            id=detection.id,
                            event_id=event.id,
                            label=detection.label,
                            confidence=detection.confidence,
                            zone_id=detection.zone_id,
                            bbox_json=_bbox_to_json(detection.bbox),
                        )
                        for event in events
                        for detection in event.detections
                    ]
                )
                session.add_all(
                    [
                        VisitModel(
                            id=visit.id,
                            event_id=visit.event_id,
                            subject_label=visit.subject_label,
                            species_guess=visit.species_guess,
                            confidence=visit.confidence,
                            reviewed_label=visit.reviewed_label,
                            review_status=visit.review_status.value,
                            representative_media_path=visit.representative_media_path,
                        )
                        for visit in visits
                    ]
                )
                session.add_all(
                    [
                        ReviewLabelModel(
                            id=label.id,
                            target_type=label.target_type,
                            target_id=label.target_id,
                            label=label.label,
                            notes=label.notes,
                            created_at=label.created_at,
                        )
                        for label in review_labels
                    ]
                )
                session.add_all(
                    [
                        DatasetExportModel(
                            id=dataset_export.id,
                            name=dataset_export.name,
                            status=dataset_export.status.value,
                            reviewed_only=dataset_export.reviewed_only,
                            include_detections=dataset_export.include_detections,
                            include_zone_context=dataset_export.include_zone_context,
                            record_count=dataset_export.record_count,
                            created_at=dataset_export.created_at,
                        )
                        for dataset_export in dataset_exports
                    ]
                )

    def list_sources(self) -> list[CameraSource]:
        with self.session_factory() as session:
            sources = session.scalars(select(CameraSourceModel).order_by(CameraSourceModel.id)).all()
            return [_source_from_model(source) for source in sources]

    def get_source(self, source_id: str) -> CameraSource | None:
        with self.session_factory() as session:
            source = session.get(CameraSourceModel, source_id)
            return _source_from_model(source) if source else None

    def list_streams(self) -> list[Stream]:
        with self.session_factory() as session:
            streams = session.scalars(select(StreamModel).order_by(StreamModel.id)).all()
            return [_stream_from_model(stream) for stream in streams]

    def get_stream(self, stream_id: str) -> Stream | None:
        with self.session_factory() as session:
            stream = session.get(StreamModel, stream_id)
            return _stream_from_model(stream) if stream else None

    def streams_for_source(self, source_id: str) -> list[Stream]:
        with self.session_factory() as session:
            streams = session.scalars(
                select(StreamModel)
                .where(StreamModel.source_id == source_id)
                .order_by(StreamModel.id)
            ).all()
            return [_stream_from_model(stream) for stream in streams]

    def list_zones(self) -> list[Zone]:
        with self.session_factory() as session:
            zones = session.scalars(select(ZoneModel).order_by(ZoneModel.id)).all()
            return [_zone_from_model(zone) for zone in zones]

    def get_zone(self, zone_id: str) -> Zone | None:
        with self.session_factory() as session:
            zone = session.get(ZoneModel, zone_id)
            return _zone_from_model(zone) if zone else None

    def zones_for_stream(self, stream_id: str) -> list[Zone]:
        with self.session_factory() as session:
            return self._zones_for_stream(session, stream_id)

    def create_zone(self, payload: ZoneCreate) -> Zone:
        with self.session_factory() as session:
            with session.begin():
                zone = ZoneModel(
                    id=self._next_id(session, ZoneModel, "zone"),
                    stream_id=payload.stream_id,
                    name=payload.name,
                    zone_type=payload.zone_type.value,
                    polygon_json=_points_to_json(payload.polygon),
                    is_active=payload.is_active,
                )
                session.add(zone)
                session.flush()
                return _zone_from_model(zone)

    def update_zone(self, zone_id: str, payload: ZoneUpdate) -> Zone | None:
        with self.session_factory() as session:
            with session.begin():
                zone = session.get(ZoneModel, zone_id)
                if zone is None:
                    return None

                if payload.name is not None:
                    zone.name = payload.name
                if payload.zone_type is not None:
                    zone.zone_type = payload.zone_type.value
                if payload.polygon is not None:
                    zone.polygon_json = _points_to_json(payload.polygon)
                if payload.is_active is not None:
                    zone.is_active = payload.is_active

                session.flush()
                return _zone_from_model(zone)

    def list_events(self) -> list[Event]:
        with self.session_factory() as session:
            events = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
            return [self._event_from_model(session, event) for event in events]

    def get_event(self, event_id: str) -> Event | None:
        with self.session_factory() as session:
            event = session.get(EventModel, event_id)
            return self._event_from_model(session, event) if event else None

    def events_for_stream(self, stream_id: str) -> list[Event]:
        with self.session_factory() as session:
            events = session.scalars(
                select(EventModel)
                .where(EventModel.stream_id == stream_id)
                .order_by(EventModel.started_at)
            ).all()
            return [self._event_from_model(session, event) for event in events]

    def list_visits(self) -> list[Visit]:
        with self.session_factory() as session:
            visits = session.scalars(select(VisitModel).order_by(VisitModel.id)).all()
            return [_visit_from_model(visit) for visit in visits]

    def get_visit(self, visit_id: str) -> Visit | None:
        with self.session_factory() as session:
            visit = session.get(VisitModel, visit_id)
            return _visit_from_model(visit) if visit else None

    def visits_for_event(self, event_id: str) -> list[Visit]:
        with self.session_factory() as session:
            return self._visits_for_event(session, event_id)

    def list_review_labels(self) -> list[ReviewLabel]:
        with self.session_factory() as session:
            labels = session.scalars(
                select(ReviewLabelModel).order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
            return [_review_label_from_model(label) for label in labels]

    def review_labels_for_event(self, event_id: str) -> list[ReviewLabel]:
        with self.session_factory() as session:
            return self._review_labels_for_event(session, event_id)

    def review_labels_for_visit(self, visit_id: str) -> list[ReviewLabel]:
        with self.session_factory() as session:
            return self._review_labels_for_visit(session, visit_id)

    def review_labels_for_event_tree(self, event_id: str) -> list[ReviewLabel]:
        with self.session_factory() as session:
            visit_ids = {visit.id for visit in self._visits_for_event(session, event_id)}
            labels = session.scalars(
                select(ReviewLabelModel).order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
            return [
                _review_label_from_model(label)
                for label in labels
                if (label.target_type == "event" and label.target_id == event_id)
                or (label.target_type == "visit" and label.target_id in visit_ids)
            ]

    def create_review_label(
        self,
        payload: ReviewCorrectionCreate,
        created_at: datetime | None = None,
    ) -> ReviewCorrectionResult:
        with self.session_factory() as session:
            with session.begin():
                label_model = ReviewLabelModel(
                    id=self._next_id(session, ReviewLabelModel, "review-label"),
                    target_type=payload.target_type,
                    target_id=payload.target_id,
                    label=payload.label,
                    notes=payload.notes,
                    created_at=created_at or datetime.now(UTC),
                )

                visit: Visit | None = None
                event: Event | None = None

                if payload.target_type == "visit":
                    visit_model = session.get(VisitModel, payload.target_id)
                    if visit_model is None:
                        raise ValueError("missing_visit")

                    session.add(label_model)
                    visit_model.reviewed_label = payload.label
                    visit_model.review_status = ReviewStatus.reviewed.value

                    event_model = session.get(EventModel, visit_model.event_id)
                    if event_model is not None:
                        child_visits = self._visit_models_for_event(session, event_model.id)
                        if all(
                            child_visit.review_status != ReviewStatus.needs_review.value
                            for child_visit in child_visits
                        ):
                            event_model.review_status = ReviewStatus.reviewed.value
                        event = self._event_from_model(session, event_model)

                    visit = _visit_from_model(visit_model)

                elif payload.target_type == "event":
                    event_model = session.get(EventModel, payload.target_id)
                    if event_model is None:
                        raise ValueError("missing_event")

                    session.add(label_model)
                    event_model.review_status = ReviewStatus.reviewed.value
                    event = self._event_from_model(session, event_model)
                else:
                    raise ValueError("unsupported_target")

                session.flush()
                review_label = _review_label_from_model(label_model)
                return ReviewCorrectionResult(
                    review_label=review_label,
                    visit=visit,
                    event=event,
                    review_queue_count=len(self._review_queue_items(session)),
                    analytics=self._analytics_summary(session),
                )

    def review_queue_items(self) -> list[ReviewQueueItem]:
        with self.session_factory() as session:
            return self._review_queue_items(session)

    def list_dataset_exports(self) -> list[DatasetExport]:
        with self.session_factory() as session:
            exports = session.scalars(
                select(DatasetExportModel).order_by(
                    DatasetExportModel.created_at,
                    DatasetExportModel.id,
                )
            ).all()
            return [_dataset_export_from_model(dataset_export) for dataset_export in exports]

    def get_dataset_export(self, export_id: str) -> DatasetExport | None:
        with self.session_factory() as session:
            dataset_export = session.get(DatasetExportModel, export_id)
            return _dataset_export_from_model(dataset_export) if dataset_export else None

    def create_dataset_export(self, payload: DatasetExportCreate) -> DatasetExport:
        with self.session_factory() as session:
            with session.begin():
                dataset_export = DatasetExport(
                    id=self._next_id(session, DatasetExportModel, "dataset-export"),
                    name=payload.name,
                    status=ExportStatus.ready,
                    reviewed_only=payload.reviewed_only,
                    include_detections=payload.include_detections,
                    include_zone_context=payload.include_zone_context,
                    record_count=0,
                    created_at=datetime.now(UTC),
                )
                records, _ = self._export_records_for_current_reviews(session, dataset_export)
                model = DatasetExportModel(
                    id=dataset_export.id,
                    name=dataset_export.name,
                    status=dataset_export.status.value,
                    reviewed_only=dataset_export.reviewed_only,
                    include_detections=dataset_export.include_detections,
                    include_zone_context=dataset_export.include_zone_context,
                    record_count=len(records),
                    created_at=dataset_export.created_at,
                )
                session.add(model)
                session.flush()
                return _dataset_export_from_model(model)

    def build_dataset_manifest(self, export_id: str) -> DatasetExportManifest | None:
        with self.session_factory() as session:
            dataset_export = session.get(DatasetExportModel, export_id)
            if dataset_export is None:
                return None

            return self._build_dataset_manifest_for_export(
                session,
                _dataset_export_from_model(dataset_export),
            )

    def analytics_summary(self) -> AnalyticsSummary:
        with self.session_factory() as session:
            return self._analytics_summary(session)

    def build_analytics_summary(self) -> AnalyticsSummary:
        return self.analytics_summary()

    def visit_is_dataset_ready(self, visit: Visit) -> bool:
        with self.session_factory() as session:
            return self._visit_is_dataset_ready(session, visit)

    def event_is_dataset_ready(self, event: Event) -> bool:
        with self.session_factory() as session:
            return self._event_is_dataset_ready(session, event)

    def review_summary_for_dataset_state(self, dataset_ready: bool) -> str:
        if dataset_ready:
            return "Ready for local dataset export. Corrected label will be used as local dataset truth."

        return "Needs review before export. Detections are evidence, not final truth."

    def dataset_export_detail(self, export_id: str) -> DatasetExportDetail | None:
        dataset_export = self.get_dataset_export(export_id)
        manifest = self.build_dataset_manifest(export_id)
        if dataset_export is None or manifest is None:
            return None
        return DatasetExportDetail(export=dataset_export, manifest=manifest)

    def _zones_for_stream(self, session: Session, stream_id: str) -> list[Zone]:
        zones = session.scalars(
            select(ZoneModel).where(ZoneModel.stream_id == stream_id).order_by(ZoneModel.id)
        ).all()
        return [_zone_from_model(zone) for zone in zones]

    def _visit_models_for_event(self, session: Session, event_id: str) -> list[VisitModel]:
        return list(
            session.scalars(
                select(VisitModel).where(VisitModel.event_id == event_id).order_by(VisitModel.id)
            ).all()
        )

    def _visits_for_event(self, session: Session, event_id: str) -> list[Visit]:
        return [_visit_from_model(visit) for visit in self._visit_models_for_event(session, event_id)]

    def _review_label_models_for_event(
        self,
        session: Session,
        event_id: str,
    ) -> list[ReviewLabelModel]:
        return list(
            session.scalars(
                select(ReviewLabelModel)
                .where(
                    ReviewLabelModel.target_type == "event",
                    ReviewLabelModel.target_id == event_id,
                )
                .order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
        )

    def _review_label_models_for_visit(
        self,
        session: Session,
        visit_id: str,
    ) -> list[ReviewLabelModel]:
        return list(
            session.scalars(
                select(ReviewLabelModel)
                .where(
                    ReviewLabelModel.target_type == "visit",
                    ReviewLabelModel.target_id == visit_id,
                )
                .order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
        )

    def _review_labels_for_event(self, session: Session, event_id: str) -> list[ReviewLabel]:
        return [
            _review_label_from_model(label)
            for label in self._review_label_models_for_event(session, event_id)
        ]

    def _review_labels_for_visit(self, session: Session, visit_id: str) -> list[ReviewLabel]:
        return [
            _review_label_from_model(label)
            for label in self._review_label_models_for_visit(session, visit_id)
        ]

    def _event_from_model(self, session: Session, event: EventModel) -> Event:
        detections = session.scalars(
            select(DetectionModel)
            .where(DetectionModel.event_id == event.id)
            .order_by(DetectionModel.id)
        ).all()
        return Event(
            id=event.id,
            stream_id=event.stream_id,
            title=event.title,
            event_type=event.event_type,
            started_at=_as_utc(event.started_at),
            ended_at=_as_utc(event.ended_at) if event.ended_at else None,
            primary_zone_id=event.primary_zone_id,
            review_status=ReviewStatus(event.review_status),
            detections=[_detection_from_model(detection) for detection in detections],
        )

    def _visit_is_dataset_ready(self, session: Session, visit: Visit) -> bool:
        return visit.review_status == ReviewStatus.reviewed and (
            visit.reviewed_label is not None
            or bool(self._review_label_models_for_visit(session, visit.id))
            or bool(self._review_label_models_for_event(session, visit.event_id))
        )

    def _event_is_dataset_ready(self, session: Session, event: Event) -> bool:
        visits = self._visits_for_event(session, event.id)
        if visits:
            return all(self._visit_is_dataset_ready(session, visit) for visit in visits)

        return event.review_status == ReviewStatus.reviewed and bool(
            self._review_label_models_for_event(session, event.id)
        )

    def _latest_label(self, labels: list[ReviewLabel]) -> str | None:
        if not labels:
            return None
        return max(labels, key=lambda label: label.created_at).label

    def _zone_context(
        self,
        session: Session,
        zone_id: str | None,
    ) -> tuple[str | None, str | None, ZoneType | None]:
        if zone_id is None:
            return None, None, None

        zone = session.get(ZoneModel, zone_id)
        if zone is None:
            return zone_id, None, None

        zone_schema = _zone_from_model(zone)
        return zone_schema.id, zone_schema.name, zone_schema.zone_type

    def _visit_export_record(
        self,
        session: Session,
        visit: Visit,
        event: Event,
        stream: Stream,
        export: DatasetExport,
    ) -> DatasetExportRecord:
        zone_id, zone_name, zone_type = (
            self._zone_context(session, event.primary_zone_id)
            if export.include_zone_context
            else (None, None, None)
        )
        label = (
            visit.reviewed_label
            or self._latest_label(self._review_labels_for_visit(session, visit.id))
            or self._latest_label(self._review_labels_for_event(session, event.id))
            or visit.species_guess
            or visit.subject_label
        )

        return DatasetExportRecord(
            record_id=f"record-{visit.id}",
            event_id=event.id,
            visit_id=visit.id,
            stream_id=event.stream_id,
            source_id=stream.source_id,
            label=label,
            subject_label=visit.subject_label,
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            reviewed=visit.review_status == ReviewStatus.reviewed,
            dataset_ready=self._visit_is_dataset_ready(session, visit),
            media_path=visit.representative_media_path,
            started_at=event.started_at,
            detections=event.detections if export.include_detections else [],
        )

    def _event_export_record(
        self,
        session: Session,
        event: Event,
        stream: Stream,
        export: DatasetExport,
    ) -> DatasetExportRecord:
        zone_id, zone_name, zone_type = (
            self._zone_context(session, event.primary_zone_id)
            if export.include_zone_context
            else (None, None, None)
        )
        label = self._latest_label(self._review_labels_for_event(session, event.id)) or (
            event.detections[0].label if event.detections else event.event_type
        )

        return DatasetExportRecord(
            record_id=f"record-{event.id}",
            event_id=event.id,
            visit_id=None,
            stream_id=event.stream_id,
            source_id=stream.source_id,
            label=label,
            subject_label=event.event_type,
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            reviewed=event.review_status == ReviewStatus.reviewed,
            dataset_ready=self._event_is_dataset_ready(session, event),
            media_path=None,
            started_at=event.started_at,
            detections=event.detections if export.include_detections else [],
        )

    def _export_records_for_current_reviews(
        self,
        session: Session,
        export: DatasetExport,
    ) -> tuple[list[DatasetExportRecord], Counter[str]]:
        records: list[DatasetExportRecord] = []
        skipped_reasons: Counter[str] = Counter()
        visits = self._visits_for_eventless_query(session)
        event_ids_with_visits = {visit.event_id for visit in visits}

        for visit in visits:
            event_model = session.get(EventModel, visit.event_id)
            if event_model is None:
                skipped_reasons["missing_event"] += 1
                continue

            event = self._event_from_model(session, event_model)
            stream_model = session.get(StreamModel, event.stream_id)
            if stream_model is None:
                skipped_reasons["missing_stream"] += 1
                continue
            stream = _stream_from_model(stream_model)

            dataset_ready = self._visit_is_dataset_ready(session, visit)
            if export.reviewed_only and not dataset_ready:
                skipped_reasons["needs_review"] += 1
                continue

            records.append(self._visit_export_record(session, visit, event, stream, export))

        event_models = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        for event_model in event_models:
            if event_model.id in event_ids_with_visits:
                continue

            stream_model = session.get(StreamModel, event_model.stream_id)
            if stream_model is None:
                skipped_reasons["missing_stream"] += 1
                continue
            stream = _stream_from_model(stream_model)
            event = self._event_from_model(session, event_model)

            dataset_ready = self._event_is_dataset_ready(session, event)
            if export.reviewed_only and not dataset_ready:
                skipped_reasons["needs_review"] += 1
                continue

            records.append(self._event_export_record(session, event, stream, export))

        return records, skipped_reasons

    def _build_dataset_manifest_for_export(
        self,
        session: Session,
        dataset_export: DatasetExport,
    ) -> DatasetExportManifest:
        # Dataset manifests use corrections as truth, detections as evidence,
        # and media paths as references until local media storage exists.
        records, skipped_reasons = self._export_records_for_current_reviews(session, dataset_export)
        return DatasetExportManifest(
            export=dataset_export,
            records=records,
            skipped_count=sum(skipped_reasons.values()),
            skipped_reasons=dict(skipped_reasons),
            generated_at=datetime.now(UTC),
        )

    def _review_queue_items(self, session: Session) -> list[ReviewQueueItem]:
        queue: list[ReviewQueueItem] = []
        visits = self._visits_for_eventless_query(session)

        for visit in visits:
            if visit.review_status != ReviewStatus.needs_review:
                continue

            event_model = session.get(EventModel, visit.event_id)
            if event_model is None:
                continue

            event = self._event_from_model(session, event_model)
            queue.append(
                ReviewQueueItem(
                    id=f"review-queue-{visit.id}",
                    item_type="visit",
                    title=f"Review {visit.subject_label} visit",
                    stream_id=event.stream_id,
                    event_id=event.id,
                    visit_id=visit.id,
                    primary_zone_id=event.primary_zone_id,
                    suggested_label=visit.species_guess or visit.subject_label,
                    review_status=visit.review_status,
                    reason="Confirm or correct the suggested species label.",
                )
            )

        visit_event_ids = {item.event_id for item in queue if item.event_id is not None}
        event_models = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        for event_model in event_models:
            event = self._event_from_model(session, event_model)
            if event.review_status != ReviewStatus.needs_review or event.id in visit_event_ids:
                continue

            queue.append(
                ReviewQueueItem(
                    id=f"review-queue-{event.id}",
                    item_type="event",
                    title=event.title,
                    stream_id=event.stream_id,
                    event_id=event.id,
                    visit_id=None,
                    primary_zone_id=event.primary_zone_id,
                    suggested_label=event.detections[0].label if event.detections else None,
                    review_status=event.review_status,
                    reason="Review detected outdoor activity and correct the event meaning.",
                )
            )

        return queue

    def _analytics_summary(self, session: Session) -> AnalyticsSummary:
        events = [
            self._event_from_model(session, event)
            for event in session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        ]
        visits = self._visits_for_eventless_query(session)
        review_labels = self.list_review_labels_from_session(session)

        needs_review_count = sum(
            event.review_status == ReviewStatus.needs_review for event in events
        ) + sum(visit.review_status == ReviewStatus.needs_review for visit in visits)

        species_counts: Counter[str] = Counter()
        for visit in visits:
            species_counts[visit.reviewed_label or visit.species_guess or visit.subject_label] += 1

        visit_event_ids = {visit.event_id for visit in visits}
        for label in review_labels:
            if label.target_type == "visit":
                continue
            if label.target_type == "event" and label.target_id in visit_event_ids:
                continue
            species_counts[label.label] += 1

        zone_activity_counts: Counter[str] = Counter()
        for event in events:
            if event.primary_zone_id is not None:
                zone_activity_counts[event.primary_zone_id] += 1

        return AnalyticsSummary(
            event_count=len(events),
            visit_count=len(visits),
            needs_review_count=needs_review_count,
            species_counts=dict(species_counts),
            zone_activity_counts=dict(zone_activity_counts),
        )

    def list_review_labels_from_session(self, session: Session) -> list[ReviewLabel]:
        labels = session.scalars(
            select(ReviewLabelModel).order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
        ).all()
        return [_review_label_from_model(label) for label in labels]

    def _visits_for_eventless_query(self, session: Session) -> list[Visit]:
        visits = session.scalars(select(VisitModel).order_by(VisitModel.id)).all()
        return [_visit_from_model(visit) for visit in visits]

    def _next_id(self, session: Session, model: type, prefix: str) -> str:
        count = session.scalar(select(func.count(model.id))) or 0
        candidate_number = count + 1
        while True:
            candidate = f"{prefix}-{candidate_number:03d}"
            if session.get(model, candidate) is None:
                return candidate
            candidate_number += 1


def _source_from_model(source: CameraSourceModel) -> CameraSource:
    return CameraSource(
        id=source.id,
        name=source.name,
        kind=SourceKind(source.kind),
        status=SourceStatus(source.status),
        description=source.description,
    )


def _stream_from_model(stream: StreamModel) -> Stream:
    return Stream(
        id=stream.id,
        source_id=stream.source_id,
        name=stream.name,
        description=stream.description,
        is_live=stream.is_live,
    )


def _zone_from_model(zone: ZoneModel) -> Zone:
    return Zone(
        id=zone.id,
        stream_id=zone.stream_id,
        name=zone.name,
        zone_type=ZoneType(zone.zone_type),
        polygon=[Point(**point) for point in json.loads(zone.polygon_json)],
        is_active=zone.is_active,
    )


def _detection_from_model(detection: DetectionModel) -> Detection:
    bbox = BoundingBox(**json.loads(detection.bbox_json)) if detection.bbox_json else None
    return Detection(
        id=detection.id,
        label=detection.label,
        confidence=detection.confidence,
        zone_id=detection.zone_id,
        bbox=bbox,
    )


def _visit_from_model(visit: VisitModel) -> Visit:
    return Visit(
        id=visit.id,
        event_id=visit.event_id,
        subject_label=visit.subject_label,
        species_guess=visit.species_guess,
        confidence=visit.confidence,
        reviewed_label=visit.reviewed_label,
        review_status=ReviewStatus(visit.review_status),
        representative_media_path=visit.representative_media_path,
    )


def _review_label_from_model(label: ReviewLabelModel) -> ReviewLabel:
    return ReviewLabel(
        id=label.id,
        target_type=label.target_type,
        target_id=label.target_id,
        label=label.label,
        notes=label.notes,
        created_at=_as_utc(label.created_at),
    )


def _dataset_export_from_model(dataset_export: DatasetExportModel) -> DatasetExport:
    return DatasetExport(
        id=dataset_export.id,
        name=dataset_export.name,
        status=ExportStatus(dataset_export.status),
        reviewed_only=dataset_export.reviewed_only,
        include_detections=dataset_export.include_detections,
        include_zone_context=dataset_export.include_zone_context,
        record_count=dataset_export.record_count,
        created_at=_as_utc(dataset_export.created_at),
    )


def _points_to_json(points: list[Point]) -> str:
    return json.dumps([point.model_dump() for point in points])


def _bbox_to_json(bbox: BoundingBox | None) -> str | None:
    if bbox is None:
        return None
    return json.dumps(bbox.model_dump())


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
