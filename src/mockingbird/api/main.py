"""FastAPI app for the MockingBird product API."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
    Stream,
    Visit,
    VisitDetail,
    Zone,
    ZoneCreate,
    ZoneMutationResult,
    ZoneUpdate,
)
from mockingbird.repository.product_repository import ProductRepository

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

_repository: ProductRepository | None = None


def get_repository() -> ProductRepository:
    global _repository
    if _repository is None:
        _repository = ProductRepository()
    return _repository


def configure_repository(repository: ProductRepository | None) -> None:
    global _repository
    _repository = repository


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
    return get_repository().list_sources()


# Detail and nested routes support frontend product navigation, not adapter plumbing.
@app.get("/api/sources/{source_id}", response_model=CameraSource)
async def get_source(source_id: str) -> CameraSource:
    source = get_repository().get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return source


@app.get("/api/sources/{source_id}/streams", response_model=list[Stream])
async def list_source_streams(source_id: str) -> list[Stream]:
    repository = get_repository()
    source = repository.get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return repository.streams_for_source(source_id)


@app.get("/api/streams", response_model=list[Stream])
async def list_streams() -> list[Stream]:
    return get_repository().list_streams()


@app.get("/api/streams/{stream_id}", response_model=Stream)
async def get_stream(stream_id: str) -> Stream:
    stream = get_repository().get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return stream


@app.get("/api/streams/{stream_id}/zones", response_model=list[Zone])
async def list_stream_zones(stream_id: str) -> list[Zone]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.zones_for_stream(stream_id)


@app.get("/api/streams/{stream_id}/events", response_model=list[Event])
async def list_stream_events(stream_id: str) -> list[Event]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.events_for_stream(stream_id)


@app.get("/api/zones", response_model=list[Zone])
async def list_zones() -> list[Zone]:
    return get_repository().list_zones()


@app.get("/api/zones/{zone_id}", response_model=Zone)
async def get_zone(zone_id: str) -> Zone:
    zone = get_repository().get_zone(zone_id)
    if zone is None:
        raise _not_found("Zone", zone_id)
    return zone


@app.post("/api/zones", response_model=ZoneMutationResult, status_code=201)
async def create_zone(payload: ZoneCreate) -> ZoneMutationResult:
    repository = get_repository()
    stream = repository.get_stream(payload.stream_id)
    if stream is None:
        raise _not_found("Stream", payload.stream_id)
    if len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    # Zones are user-authored stream context; later detections and events should
    # respect privacy and ignore zones without making adapters the product center.
    zone = repository.create_zone(payload)
    return ZoneMutationResult(
        zone=zone,
        zones=repository.zones_for_stream(zone.stream_id),
    )


@app.patch("/api/zones/{zone_id}", response_model=ZoneMutationResult)
async def update_zone(zone_id: str, payload: ZoneUpdate) -> ZoneMutationResult:
    repository = get_repository()
    existing_zone = repository.get_zone(zone_id)
    if existing_zone is None:
        raise _not_found("Zone", zone_id)
    if payload.polygon is not None and len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    zone = repository.update_zone(zone_id, payload)
    if zone is None:
        raise _not_found("Zone", zone_id)

    return ZoneMutationResult(
        zone=zone,
        zones=repository.zones_for_stream(zone.stream_id),
    )


@app.get("/api/events", response_model=list[Event])
async def list_events() -> list[Event]:
    return get_repository().list_events()


@app.get("/api/events/{event_id}", response_model=Event)
async def get_event(event_id: str) -> Event:
    event = get_repository().get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return event


# Detail routes are review case files: detections are evidence, zones provide
# context, and review labels are dataset-grade truth for local exports.
@app.get("/api/events/{event_id}/detail", response_model=EventDetail)
async def get_event_detail(event_id: str) -> EventDetail:
    repository = get_repository()
    event = repository.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)

    stream = repository.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    dataset_ready = repository.event_is_dataset_ready(event)
    return EventDetail(
        event=event,
        stream=stream,
        primary_zone=(
            repository.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        visits=repository.visits_for_event(event.id),
        review_labels=repository.review_labels_for_event_tree(event.id),
        dataset_ready=dataset_ready,
        review_summary=repository.review_summary_for_dataset_state(dataset_ready),
    )


@app.get("/api/events/{event_id}/visits", response_model=list[Visit])
async def list_event_visits(event_id: str) -> list[Visit]:
    repository = get_repository()
    event = repository.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return repository.visits_for_event(event_id)


@app.get("/api/visits", response_model=list[Visit])
async def list_visits() -> list[Visit]:
    return get_repository().list_visits()


@app.get("/api/visits/{visit_id}", response_model=Visit)
async def get_visit(visit_id: str) -> Visit:
    visit = get_repository().get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)
    return visit


@app.get("/api/visits/{visit_id}/detail", response_model=VisitDetail)
async def get_visit_detail(visit_id: str) -> VisitDetail:
    repository = get_repository()
    visit = repository.get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)

    event = repository.get_event(visit.event_id)
    if event is None:
        raise _not_found("Event", visit.event_id)

    stream = repository.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    dataset_ready = repository.visit_is_dataset_ready(visit)
    return VisitDetail(
        visit=visit,
        event=event,
        stream=stream,
        primary_zone=(
            repository.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        detections=event.detections,
        review_labels=(
            repository.review_labels_for_event(event.id)
            + repository.review_labels_for_visit(visit.id)
        ),
        dataset_ready=dataset_ready,
        review_summary=repository.review_summary_for_dataset_state(dataset_ready),
    )


@app.get("/api/review-queue", response_model=list[ReviewQueueItem])
async def list_review_queue() -> list[ReviewQueueItem]:
    return get_repository().review_queue_items()


@app.get("/api/review-labels", response_model=list[ReviewLabel])
async def list_review_labels() -> list[ReviewLabel]:
    return get_repository().list_review_labels()


@app.post("/api/review-labels", response_model=ReviewCorrectionResult, status_code=201)
async def create_review_label(payload: ReviewCorrectionCreate) -> ReviewCorrectionResult:
    repository = get_repository()

    if payload.target_type == "visit":
        if repository.get_visit(payload.target_id) is None:
            raise _not_found("Visit", payload.target_id)

        # Review labels are user-confirmed dataset truth; detections remain evidence.
        return repository.create_review_label(payload)

    if payload.target_type == "event":
        if repository.get_event(payload.target_id) is None:
            raise _not_found("Event", payload.target_id)

        return repository.create_review_label(payload)

    raise _unsupported_target(payload.target_type)


@app.get("/api/dataset-exports", response_model=list[DatasetExport])
async def list_dataset_exports() -> list[DatasetExport]:
    return get_repository().list_dataset_exports()


@app.post("/api/dataset-exports", response_model=DatasetExportDetail, status_code=201)
async def create_dataset_export(payload: DatasetExportCreate) -> DatasetExportDetail:
    repository = get_repository()
    dataset_export = repository.create_dataset_export(payload)
    manifest = repository.build_dataset_manifest(dataset_export.id)
    if manifest is None:
        raise _not_found("Dataset export", dataset_export.id)
    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get("/api/dataset-exports/{export_id}", response_model=DatasetExportDetail)
async def get_dataset_export(export_id: str) -> DatasetExportDetail:
    repository = get_repository()
    dataset_export = repository.get_dataset_export(export_id)
    if dataset_export is None:
        raise _not_found("Dataset export", export_id)

    manifest = repository.build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)

    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get("/api/dataset-exports/{export_id}/manifest", response_model=DatasetExportManifest)
async def get_dataset_export_manifest(export_id: str) -> DatasetExportManifest:
    manifest = get_repository().build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)
    return manifest


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary() -> AnalyticsSummary:
    return get_repository().analytics_summary()
