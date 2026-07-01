"""FastAPI app for the MockingBird product API."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from mockingbird.api import demo_data
from mockingbird.api.schemas import (
    AnalyticsSummary,
    CameraSource,
    DatasetExport,
    DatasetExportCreate,
    DatasetExportDetail,
    DatasetExportManifest,
    Event,
    EventDetail,
    ReviewLabel,
    ReviewCorrectionCreate,
    ReviewCorrectionResult,
    ReviewQueueItem,
    ReviewStatus,
    Stream,
    Visit,
    VisitDetail,
    Zone,
    ZoneCreate,
    ZoneMutationResult,
    ZoneUpdate,
)

app = FastAPI(
    title="MockingBird API",
    version="0.1.0",
    description=(
        "Local-first outdoor video intelligence centered on streams, zones, "
        "events, visits, review, corrections, exports, and analytics."
    ),
)

# Local Vite dev origins let the stream-first frontend use the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _not_found(product_type: str, product_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"{product_type} '{product_id}' was not found.",
    )


def _unsupported_target(target_type: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=(
            f"Unsupported review target_type '{target_type}'. "
            "Supported target types are 'visit' and 'event'."
        ),
    )


def _invalid_zone_polygon() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail="Zone polygon must contain at least 3 points.",
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sources", response_model=list[CameraSource])
async def list_sources() -> list[CameraSource]:
    return demo_data.SOURCES


# Detail and nested routes support frontend product navigation, not adapter plumbing.
@app.get("/api/sources/{source_id}", response_model=CameraSource)
async def get_source(source_id: str) -> CameraSource:
    source = demo_data.get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return source


@app.get("/api/sources/{source_id}/streams", response_model=list[Stream])
async def list_source_streams(source_id: str) -> list[Stream]:
    source = demo_data.get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return demo_data.streams_for_source(source_id)


@app.get("/api/streams", response_model=list[Stream])
async def list_streams() -> list[Stream]:
    return demo_data.STREAMS


@app.get("/api/streams/{stream_id}", response_model=Stream)
async def get_stream(stream_id: str) -> Stream:
    stream = demo_data.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return stream


@app.get("/api/streams/{stream_id}/zones", response_model=list[Zone])
async def list_stream_zones(stream_id: str) -> list[Zone]:
    stream = demo_data.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return demo_data.zones_for_stream(stream_id)


@app.get("/api/streams/{stream_id}/events", response_model=list[Event])
async def list_stream_events(stream_id: str) -> list[Event]:
    stream = demo_data.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return demo_data.events_for_stream(stream_id)


@app.get("/api/zones", response_model=list[Zone])
async def list_zones() -> list[Zone]:
    return demo_data.ZONES


@app.get("/api/zones/{zone_id}", response_model=Zone)
async def get_zone(zone_id: str) -> Zone:
    zone = demo_data.get_zone(zone_id)
    if zone is None:
        raise _not_found("Zone", zone_id)
    return zone


@app.post("/api/zones", response_model=ZoneMutationResult, status_code=201)
async def create_zone(payload: ZoneCreate) -> ZoneMutationResult:
    stream = demo_data.get_stream(payload.stream_id)
    if stream is None:
        raise _not_found("Stream", payload.stream_id)
    if len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    # Zones are user-authored stream context; later detections and events should
    # respect privacy and ignore zones without making adapters the product center.
    zone = demo_data.create_zone(payload)
    return ZoneMutationResult(
        zone=zone,
        zones=demo_data.zones_for_stream(zone.stream_id),
    )


@app.patch("/api/zones/{zone_id}", response_model=ZoneMutationResult)
async def update_zone(zone_id: str, payload: ZoneUpdate) -> ZoneMutationResult:
    existing_zone = demo_data.get_zone(zone_id)
    if existing_zone is None:
        raise _not_found("Zone", zone_id)
    if payload.polygon is not None and len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    zone = demo_data.update_zone(zone_id, payload)
    if zone is None:
        raise _not_found("Zone", zone_id)

    return ZoneMutationResult(
        zone=zone,
        zones=demo_data.zones_for_stream(zone.stream_id),
    )


@app.get("/api/events", response_model=list[Event])
async def list_events() -> list[Event]:
    return demo_data.EVENTS


@app.get("/api/events/{event_id}", response_model=Event)
async def get_event(event_id: str) -> Event:
    event = demo_data.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return event


# Detail routes are review case files: detections are evidence, zones provide
# context, and review labels are dataset-grade truth for local exports.
@app.get("/api/events/{event_id}/detail", response_model=EventDetail)
async def get_event_detail(event_id: str) -> EventDetail:
    event = demo_data.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)

    stream = demo_data.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    dataset_ready = demo_data.event_is_dataset_ready(event)
    return EventDetail(
        event=event,
        stream=stream,
        primary_zone=(
            demo_data.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        visits=demo_data.visits_for_event(event.id),
        review_labels=demo_data.review_labels_for_event_tree(event.id),
        dataset_ready=dataset_ready,
        review_summary=demo_data.review_summary_for_dataset_state(dataset_ready),
    )


@app.get("/api/events/{event_id}/visits", response_model=list[Visit])
async def list_event_visits(event_id: str) -> list[Visit]:
    event = demo_data.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return demo_data.visits_for_event(event_id)


@app.get("/api/visits", response_model=list[Visit])
async def list_visits() -> list[Visit]:
    return demo_data.VISITS


@app.get("/api/visits/{visit_id}", response_model=Visit)
async def get_visit(visit_id: str) -> Visit:
    visit = demo_data.get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)
    return visit


@app.get("/api/visits/{visit_id}/detail", response_model=VisitDetail)
async def get_visit_detail(visit_id: str) -> VisitDetail:
    visit = demo_data.get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)

    event = demo_data.get_event(visit.event_id)
    if event is None:
        raise _not_found("Event", visit.event_id)

    stream = demo_data.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    dataset_ready = demo_data.visit_is_dataset_ready(visit)
    return VisitDetail(
        visit=visit,
        event=event,
        stream=stream,
        primary_zone=(
            demo_data.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        detections=event.detections,
        review_labels=(
            demo_data.review_labels_for_event(event.id)
            + demo_data.review_labels_for_visit(visit.id)
        ),
        dataset_ready=dataset_ready,
        review_summary=demo_data.review_summary_for_dataset_state(dataset_ready),
    )


@app.get("/api/review-queue", response_model=list[ReviewQueueItem])
async def list_review_queue() -> list[ReviewQueueItem]:
    return demo_data.review_queue_items()


@app.get("/api/review-labels", response_model=list[ReviewLabel])
async def list_review_labels() -> list[ReviewLabel]:
    return demo_data.REVIEW_LABELS


@app.post("/api/review-labels", response_model=ReviewCorrectionResult, status_code=201)
async def create_review_label(payload: ReviewCorrectionCreate) -> ReviewCorrectionResult:
    label = ReviewLabel(
        id=f"review-label-{len(demo_data.REVIEW_LABELS) + 1:03d}",
        target_type=payload.target_type,
        target_id=payload.target_id,
        label=payload.label,
        notes=payload.notes,
        created_at=datetime.now(UTC),
    )

    if payload.target_type == "visit":
        visit = demo_data.get_visit(payload.target_id)
        if visit is None:
            raise _not_found("Visit", payload.target_id)

        # Review labels are user-confirmed dataset truth; detections remain evidence.
        demo_data.REVIEW_LABELS.append(label)
        visit.reviewed_label = payload.label
        visit.review_status = ReviewStatus.reviewed

        event = demo_data.get_event(visit.event_id)
        if event is not None and all(
            child_visit.review_status != ReviewStatus.needs_review
            for child_visit in demo_data.visits_for_event(event.id)
        ):
            event.review_status = ReviewStatus.reviewed

        return ReviewCorrectionResult(
            review_label=label,
            visit=visit,
            event=event,
            review_queue_count=len(demo_data.review_queue_items()),
            analytics=demo_data.build_analytics_summary(),
        )

    if payload.target_type == "event":
        event = demo_data.get_event(payload.target_id)
        if event is None:
            raise _not_found("Event", payload.target_id)

        demo_data.REVIEW_LABELS.append(label)
        event.review_status = ReviewStatus.reviewed

        return ReviewCorrectionResult(
            review_label=label,
            event=event,
            review_queue_count=len(demo_data.review_queue_items()),
            analytics=demo_data.build_analytics_summary(),
        )

    raise _unsupported_target(payload.target_type)


@app.get("/api/dataset-exports", response_model=list[DatasetExport])
async def list_dataset_exports() -> list[DatasetExport]:
    return demo_data.DATASET_EXPORTS


@app.post("/api/dataset-exports", response_model=DatasetExportDetail, status_code=201)
async def create_dataset_export(payload: DatasetExportCreate) -> DatasetExportDetail:
    dataset_export = demo_data.create_dataset_export(payload)
    manifest = demo_data.build_dataset_manifest(dataset_export.id)
    if manifest is None:
        raise _not_found("Dataset export", dataset_export.id)
    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get("/api/dataset-exports/{export_id}", response_model=DatasetExportDetail)
async def get_dataset_export(export_id: str) -> DatasetExportDetail:
    dataset_export = demo_data.get_dataset_export(export_id)
    if dataset_export is None:
        raise _not_found("Dataset export", export_id)

    manifest = demo_data.build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)

    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get("/api/dataset-exports/{export_id}/manifest", response_model=DatasetExportManifest)
async def get_dataset_export_manifest(export_id: str) -> DatasetExportManifest:
    manifest = demo_data.build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)
    return manifest


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary() -> AnalyticsSummary:
    return demo_data.build_analytics_summary()
