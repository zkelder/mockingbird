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
    Event,
    ReviewLabel,
    ReviewLabelCreate,
    ReviewQueueItem,
    Stream,
    Visit,
    Zone,
)

app = FastAPI(
    title="MockingBird API",
    version="0.1.0",
    description=(
        "Local-first outdoor video intelligence centered on streams, zones, "
        "events, visits, review, corrections, exports, and analytics."
    ),
)

# Local Vite origins let the stream-first frontend use the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _not_found(product_type: str, product_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"{product_type} '{product_id}' was not found.",
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


@app.get("/api/events", response_model=list[Event])
async def list_events() -> list[Event]:
    return demo_data.EVENTS


@app.get("/api/events/{event_id}", response_model=Event)
async def get_event(event_id: str) -> Event:
    event = demo_data.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return event


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


@app.get("/api/review-queue", response_model=list[ReviewQueueItem])
async def list_review_queue() -> list[ReviewQueueItem]:
    return demo_data.review_queue_items()


@app.get("/api/review-labels", response_model=list[ReviewLabel])
async def list_review_labels() -> list[ReviewLabel]:
    return demo_data.REVIEW_LABELS


@app.post("/api/review-labels", response_model=ReviewLabel, status_code=201)
async def create_review_label(payload: ReviewLabelCreate) -> ReviewLabel:
    label = ReviewLabel(
        id=f"review-label-{len(demo_data.REVIEW_LABELS) + 1:03d}",
        target_type=payload.target_type,
        target_id=payload.target_id,
        label=payload.label,
        notes=payload.notes,
        created_at=datetime.now(UTC),
    )
    demo_data.REVIEW_LABELS.append(label)
    return label


@app.get("/api/dataset-exports", response_model=list[DatasetExport])
async def list_dataset_exports() -> list[DatasetExport]:
    return demo_data.DATASET_EXPORTS


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary() -> AnalyticsSummary:
    return demo_data.build_analytics_summary()
