"""FastAPI app for the MockingBird product API."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI

from mockingbird.api import demo_data
from mockingbird.api.schemas import (
    AnalyticsSummary,
    CameraSource,
    DatasetExport,
    Event,
    ReviewLabel,
    ReviewLabelCreate,
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sources", response_model=list[CameraSource])
async def list_sources() -> list[CameraSource]:
    return demo_data.SOURCES


@app.get("/api/streams", response_model=list[Stream])
async def list_streams() -> list[Stream]:
    return demo_data.STREAMS


@app.get("/api/zones", response_model=list[Zone])
async def list_zones() -> list[Zone]:
    return demo_data.ZONES


@app.get("/api/events", response_model=list[Event])
async def list_events() -> list[Event]:
    return demo_data.EVENTS


@app.get("/api/visits", response_model=list[Visit])
async def list_visits() -> list[Visit]:
    return demo_data.VISITS


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
