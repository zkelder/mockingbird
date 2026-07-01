"""In-memory demo data for the first MockingBird API contract."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from mockingbird.api.schemas import (
    AnalyticsSummary,
    BoundingBox,
    CameraSource,
    DatasetExport,
    Detection,
    Event,
    ExportStatus,
    Point,
    ReviewLabel,
    ReviewStatus,
    SourceKind,
    SourceStatus,
    Stream,
    Visit,
    Zone,
    ZoneType,
)

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"


SOURCES: list[CameraSource] = [
    CameraSource(
        id=SOURCE_ID,
        name="Backyard demo source",
        kind=SourceKind.demo,
        status=SourceStatus.connected,
        description="Demo outdoor video source used to prove the product flow before real camera adapters.",
    )
]

STREAMS: list[Stream] = [
    Stream(
        id=STREAM_ID,
        source_id=SOURCE_ID,
        name="Backyard feeder stream",
        description="Product-centered stream of feeder, ground, and yard activity.",
        is_live=True,
    )
]

ZONES: list[Zone] = [
    Zone(
        id=FEEDER_ZONE_ID,
        stream_id=STREAM_ID,
        name="Feeder",
        zone_type=ZoneType.feeder,
        polygon=[
            Point(x=0.38, y=0.24),
            Point(x=0.62, y=0.24),
            Point(x=0.64, y=0.56),
            Point(x=0.36, y=0.56),
        ],
        is_active=True,
    ),
    Zone(
        id=GROUND_ZONE_ID,
        stream_id=STREAM_ID,
        name="Ground below feeder",
        zone_type=ZoneType.ground,
        polygon=[
            Point(x=0.22, y=0.58),
            Point(x=0.78, y=0.58),
            Point(x=0.86, y=0.95),
            Point(x=0.14, y=0.95),
        ],
        is_active=True,
    ),
    Zone(
        id=IGNORE_ZONE_ID,
        stream_id=STREAM_ID,
        name="Driveway edge ignore zone",
        zone_type=ZoneType.ignore,
        polygon=[
            Point(x=0.0, y=0.0),
            Point(x=0.18, y=0.0),
            Point(x=0.18, y=1.0),
            Point(x=0.0, y=1.0),
        ],
        is_active=True,
    ),
]

EVENTS: list[Event] = [
    Event(
        id="event-bird-feeder-001",
        stream_id=STREAM_ID,
        title="Bird visit at feeder",
        event_type="bird_feeder_visit",
        started_at=datetime(2026, 1, 15, 13, 20, tzinfo=UTC),
        ended_at=datetime(2026, 1, 15, 13, 22, tzinfo=UTC),
        primary_zone_id=FEEDER_ZONE_ID,
        review_status=ReviewStatus.needs_review,
        detections=[
            Detection(
                id="detection-bird-001",
                label="unknown_bird",
                confidence=0.82,
                zone_id=FEEDER_ZONE_ID,
                bbox=BoundingBox(x=0.44, y=0.30, width=0.14, height=0.20),
            )
        ],
    ),
    Event(
        id="event-squirrel-ground-001",
        stream_id=STREAM_ID,
        title="Squirrel under feeder",
        event_type="ground_activity",
        started_at=datetime(2026, 1, 15, 14, 5, tzinfo=UTC),
        ended_at=datetime(2026, 1, 15, 14, 7, tzinfo=UTC),
        primary_zone_id=GROUND_ZONE_ID,
        review_status=ReviewStatus.reviewed,
        detections=[
            Detection(
                id="detection-squirrel-001",
                label="squirrel",
                confidence=0.91,
                zone_id=GROUND_ZONE_ID,
                bbox=BoundingBox(x=0.48, y=0.68, width=0.18, height=0.12),
            )
        ],
    ),
]

VISITS: list[Visit] = [
    Visit(
        id="visit-bird-feeder-001",
        event_id="event-bird-feeder-001",
        subject_label="bird",
        species_guess="northern_cardinal",
        confidence=0.68,
        reviewed_label=None,
        review_status=ReviewStatus.needs_review,
        representative_media_path="demo://backyard-feeder/bird-feeder-001.jpg",
    )
]

REVIEW_LABELS: list[ReviewLabel] = [
    ReviewLabel(
        id="review-label-squirrel-001",
        target_type="event",
        target_id="event-squirrel-ground-001",
        label="squirrel",
        notes="Confirmed squirrel activity under the feeder.",
        created_at=datetime(2026, 1, 15, 14, 10, tzinfo=UTC),
    )
]

DATASET_EXPORTS: list[DatasetExport] = [
    DatasetExport(
        id="dataset-export-reviewed-yard-001",
        name="Reviewed backyard activity",
        status=ExportStatus.ready,
        reviewed_only=True,
        record_count=1,
        created_at=datetime(2026, 1, 15, 15, 0, tzinfo=UTC),
    )
]


def build_analytics_summary() -> AnalyticsSummary:
    needs_review_count = sum(
        event.review_status == ReviewStatus.needs_review for event in EVENTS
    ) + sum(visit.review_status == ReviewStatus.needs_review for visit in VISITS)

    species_counts: Counter[str] = Counter()
    for visit in VISITS:
        species_counts[visit.reviewed_label or visit.species_guess or visit.subject_label] += 1
    for label in REVIEW_LABELS:
        species_counts[label.label] += 1

    zone_activity_counts: Counter[str] = Counter()
    for event in EVENTS:
        if event.primary_zone_id is not None:
            zone_activity_counts[event.primary_zone_id] += 1

    return AnalyticsSummary(
        event_count=len(EVENTS),
        visit_count=len(VISITS),
        needs_review_count=needs_review_count,
        species_counts=dict(species_counts),
        zone_activity_counts=dict(zone_activity_counts),
    )
