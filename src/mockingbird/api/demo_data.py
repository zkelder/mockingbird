"""In-memory demo data for the first MockingBird API contract."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
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
    ReviewQueueItem,
    ReviewStatus,
    SourceKind,
    SourceStatus,
    Stream,
    Visit,
    Zone,
    ZoneCreate,
    ZoneUpdate,
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
    ),
    Visit(
        id="visit-squirrel-ground-001",
        event_id="event-squirrel-ground-001",
        subject_label="squirrel",
        species_guess=None,
        confidence=0.91,
        reviewed_label="squirrel",
        review_status=ReviewStatus.reviewed,
        representative_media_path="demo://backyard-feeder/squirrel-ground-001.jpg",
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


_INITIAL_SOURCES = deepcopy(SOURCES)
_INITIAL_STREAMS = deepcopy(STREAMS)
_INITIAL_ZONES = deepcopy(ZONES)
_INITIAL_EVENTS = deepcopy(EVENTS)
_INITIAL_VISITS = deepcopy(VISITS)
_INITIAL_REVIEW_LABELS = deepcopy(REVIEW_LABELS)
_INITIAL_DATASET_EXPORTS = deepcopy(DATASET_EXPORTS)


def reset_demo_data() -> None:
    global SOURCES, STREAMS, ZONES, EVENTS, VISITS, REVIEW_LABELS, DATASET_EXPORTS

    SOURCES = deepcopy(_INITIAL_SOURCES)
    STREAMS = deepcopy(_INITIAL_STREAMS)
    ZONES = deepcopy(_INITIAL_ZONES)
    EVENTS = deepcopy(_INITIAL_EVENTS)
    VISITS = deepcopy(_INITIAL_VISITS)
    REVIEW_LABELS = deepcopy(_INITIAL_REVIEW_LABELS)
    DATASET_EXPORTS = deepcopy(_INITIAL_DATASET_EXPORTS)


def get_source(source_id: str) -> CameraSource | None:
    return next((source for source in SOURCES if source.id == source_id), None)


def get_stream(stream_id: str) -> Stream | None:
    return next((stream for stream in STREAMS if stream.id == stream_id), None)


def get_zone(zone_id: str) -> Zone | None:
    return next((zone for zone in ZONES if zone.id == zone_id), None)


def get_event(event_id: str) -> Event | None:
    return next((event for event in EVENTS if event.id == event_id), None)


def get_visit(visit_id: str) -> Visit | None:
    return next((visit for visit in VISITS if visit.id == visit_id), None)


def create_zone(payload: ZoneCreate) -> Zone:
    zone = Zone(
        id=f"zone-{len(ZONES) + 1:03d}",
        stream_id=payload.stream_id,
        name=payload.name,
        zone_type=payload.zone_type,
        polygon=payload.polygon,
        is_active=payload.is_active,
    )
    ZONES.append(zone)
    return zone


def update_zone(zone_id: str, payload: ZoneUpdate) -> Zone | None:
    zone = get_zone(zone_id)
    if zone is None:
        return None

    for field, value in payload.model_dump(exclude_none=True, exclude_unset=True).items():
        setattr(zone, field, value)

    return zone


def streams_for_source(source_id: str) -> list[Stream]:
    return [stream for stream in STREAMS if stream.source_id == source_id]


def zones_for_stream(stream_id: str) -> list[Zone]:
    return [zone for zone in ZONES if zone.stream_id == stream_id]


def events_for_stream(stream_id: str) -> list[Event]:
    return [event for event in EVENTS if event.stream_id == stream_id]


def visits_for_event(event_id: str) -> list[Visit]:
    return [visit for visit in VISITS if visit.event_id == event_id]


def review_labels_for_event(event_id: str) -> list[ReviewLabel]:
    return [
        label
        for label in REVIEW_LABELS
        if label.target_type == "event" and label.target_id == event_id
    ]


def review_labels_for_visit(visit_id: str) -> list[ReviewLabel]:
    return [
        label
        for label in REVIEW_LABELS
        if label.target_type == "visit" and label.target_id == visit_id
    ]


def review_labels_for_event_tree(event_id: str) -> list[ReviewLabel]:
    visit_ids = {visit.id for visit in visits_for_event(event_id)}
    return [
        label
        for label in REVIEW_LABELS
        if (label.target_type == "event" and label.target_id == event_id)
        or (label.target_type == "visit" and label.target_id in visit_ids)
    ]


def visit_is_dataset_ready(visit: Visit) -> bool:
    return visit.review_status == ReviewStatus.reviewed and (
        visit.reviewed_label is not None
        or bool(review_labels_for_visit(visit.id))
        or bool(review_labels_for_event(visit.event_id))
    )


def event_is_dataset_ready(event: Event) -> bool:
    visits = visits_for_event(event.id)
    if visits:
        return all(visit_is_dataset_ready(visit) for visit in visits)

    return event.review_status == ReviewStatus.reviewed and bool(review_labels_for_event(event.id))


def review_summary_for_dataset_state(dataset_ready: bool) -> str:
    if dataset_ready:
        return "Ready for local dataset export. Corrected label will be used as local dataset truth."

    return "Needs review before export. Detections are evidence, not final truth."


def review_queue_items() -> list[ReviewQueueItem]:
    queue: list[ReviewQueueItem] = []

    for visit in VISITS:
        if visit.review_status != ReviewStatus.needs_review:
            continue

        event = get_event(visit.event_id)
        if event is None:
            continue

        # The review queue is user-facing correction work, not raw model output.
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
    for event in EVENTS:
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


def build_analytics_summary() -> AnalyticsSummary:
    needs_review_count = sum(
        event.review_status == ReviewStatus.needs_review for event in EVENTS
    ) + sum(visit.review_status == ReviewStatus.needs_review for visit in VISITS)

    species_counts: Counter[str] = Counter()
    for visit in VISITS:
        species_counts[visit.reviewed_label or visit.species_guess or visit.subject_label] += 1

    visit_event_ids = {visit.event_id for visit in VISITS}
    for label in REVIEW_LABELS:
        if label.target_type == "visit":
            continue
        if label.target_type == "event" and label.target_id in visit_event_ids:
            continue
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
