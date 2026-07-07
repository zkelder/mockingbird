"""Seed data for the first MockingBird product loop."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime

from mockingbird.api.schemas import (
    AnalyticsSummary,
    BoundingBox,
    CameraSource,
    DatasetExport,
    DatasetExportCreate,
    DatasetExportManifest,
    DatasetExportRecord,
    Detection,
    Event,
    ExportStatus,
    LabelCategory,
    Point,
    ReviewLabel,
    ReviewQueueItem,
    ReviewStatus,
    SourceKind,
    SourceStatus,
    Stream,
    TaxonomyLabel,
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
        include_detections=True,
        include_zone_context=True,
        record_count=1,
        created_at=datetime(2026, 1, 15, 15, 0, tzinfo=UTC),
    )
]


TAXONOMY_LABELS: list[TaxonomyLabel] = [
    TaxonomyLabel(
        id="unknown_bird",
        label="unknown_bird",
        display_name="Unknown Bird",
        category=LabelCategory.unknown,
        aliases=["unknown bird", "unidentified bird"],
        is_species=False,
        is_reviewable=True,
        sort_order=10,
    ),
    TaxonomyLabel(
        id="unknown_animal",
        label="unknown_animal",
        display_name="Unknown Animal",
        category=LabelCategory.unknown,
        aliases=["unknown animal", "unidentified animal"],
        is_species=False,
        is_reviewable=True,
        sort_order=20,
    ),
    TaxonomyLabel(
        id="bird",
        label="bird",
        display_name="Bird",
        category=LabelCategory.bird,
        aliases=["avian"],
        is_species=False,
        is_reviewable=True,
        sort_order=30,
    ),
    TaxonomyLabel(
        id="squirrel",
        label="squirrel",
        display_name="Squirrel",
        category=LabelCategory.mammal,
        aliases=[],
        is_species=False,
        is_reviewable=True,
        sort_order=40,
    ),
    TaxonomyLabel(
        id="cat",
        label="cat",
        display_name="Cat",
        category=LabelCategory.pet,
        aliases=["domestic cat"],
        is_species=False,
        is_reviewable=True,
        sort_order=50,
    ),
    TaxonomyLabel(
        id="dog",
        label="dog",
        display_name="Dog",
        category=LabelCategory.pet,
        aliases=["domestic dog"],
        is_species=False,
        is_reviewable=True,
        sort_order=60,
    ),
    TaxonomyLabel(
        id="person",
        label="person",
        display_name="Person",
        category=LabelCategory.person,
        aliases=["human"],
        is_species=False,
        is_reviewable=True,
        sort_order=70,
    ),
    TaxonomyLabel(
        id="vehicle",
        label="vehicle",
        display_name="Vehicle",
        category=LabelCategory.vehicle,
        aliases=["car", "truck"],
        is_species=False,
        is_reviewable=True,
        sort_order=80,
    ),
    TaxonomyLabel(
        id="false_positive",
        label="false_positive",
        display_name="False Positive",
        category=LabelCategory.false_positive,
        aliases=["false alarm", "not activity"],
        is_species=False,
        is_reviewable=True,
        sort_order=90,
    ),
    TaxonomyLabel(
        id="northern_mockingbird",
        label="northern_mockingbird",
        display_name="Northern Mockingbird",
        category=LabelCategory.bird,
        aliases=["mockingbird"],
        is_species=True,
        is_reviewable=True,
        sort_order=100,
    ),
    TaxonomyLabel(
        id="carolina_wren",
        label="carolina_wren",
        display_name="Carolina Wren",
        category=LabelCategory.bird,
        aliases=[],
        is_species=True,
        is_reviewable=True,
        sort_order=110,
    ),
    TaxonomyLabel(
        id="mourning_dove",
        label="mourning_dove",
        display_name="Mourning Dove",
        category=LabelCategory.bird,
        aliases=["dove"],
        is_species=True,
        is_reviewable=True,
        sort_order=120,
    ),
    TaxonomyLabel(
        id="american_robin",
        label="american_robin",
        display_name="American Robin",
        category=LabelCategory.bird,
        aliases=["robin"],
        is_species=True,
        is_reviewable=True,
        sort_order=130,
    ),
    TaxonomyLabel(
        id="northern_cardinal",
        label="northern_cardinal",
        display_name="Northern Cardinal",
        category=LabelCategory.bird,
        aliases=["cardinal", "red bird"],
        is_species=True,
        is_reviewable=True,
        sort_order=140,
    ),
    TaxonomyLabel(
        id="blue_jay",
        label="blue_jay",
        display_name="Blue Jay",
        category=LabelCategory.bird,
        aliases=["jay"],
        is_species=True,
        is_reviewable=True,
        sort_order=150,
    ),
    TaxonomyLabel(
        id="tufted_titmouse",
        label="tufted_titmouse",
        display_name="Tufted Titmouse",
        category=LabelCategory.bird,
        aliases=["titmouse"],
        is_species=True,
        is_reviewable=True,
        sort_order=160,
    ),
    TaxonomyLabel(
        id="carolina_chickadee",
        label="carolina_chickadee",
        display_name="Carolina Chickadee",
        category=LabelCategory.bird,
        aliases=["chickadee"],
        is_species=True,
        is_reviewable=True,
        sort_order=170,
    ),
    TaxonomyLabel(
        id="house_finch",
        label="house_finch",
        display_name="House Finch",
        category=LabelCategory.bird,
        aliases=["finch"],
        is_species=True,
        is_reviewable=True,
        sort_order=180,
    ),
    TaxonomyLabel(
        id="eastern_bluebird",
        label="eastern_bluebird",
        display_name="Eastern Bluebird",
        category=LabelCategory.bird,
        aliases=["bluebird"],
        is_species=True,
        is_reviewable=True,
        sort_order=190,
    ),
    TaxonomyLabel(
        id="red_bellied_woodpecker",
        label="red_bellied_woodpecker",
        display_name="Red-bellied Woodpecker",
        category=LabelCategory.bird,
        aliases=["red bellied woodpecker"],
        is_species=True,
        is_reviewable=True,
        sort_order=200,
    ),
    TaxonomyLabel(
        id="downy_woodpecker",
        label="downy_woodpecker",
        display_name="Downy Woodpecker",
        category=LabelCategory.bird,
        aliases=[],
        is_species=True,
        is_reviewable=True,
        sort_order=210,
    ),
    TaxonomyLabel(
        id="brown_thrasher",
        label="brown_thrasher",
        display_name="Brown Thrasher",
        category=LabelCategory.bird,
        aliases=["thrasher"],
        is_species=True,
        is_reviewable=True,
        sort_order=220,
    ),
    TaxonomyLabel(
        id="gray_catbird",
        label="gray_catbird",
        display_name="Gray Catbird",
        category=LabelCategory.bird,
        aliases=["catbird"],
        is_species=True,
        is_reviewable=True,
        sort_order=230,
    ),
]


_INITIAL_SOURCES = deepcopy(SOURCES)
_INITIAL_STREAMS = deepcopy(STREAMS)
_INITIAL_ZONES = deepcopy(ZONES)
_INITIAL_EVENTS = deepcopy(EVENTS)
_INITIAL_VISITS = deepcopy(VISITS)
_INITIAL_REVIEW_LABELS = deepcopy(REVIEW_LABELS)
_INITIAL_DATASET_EXPORTS = deepcopy(DATASET_EXPORTS)
_INITIAL_TAXONOMY_LABELS = deepcopy(TAXONOMY_LABELS)


def seed_product_data() -> tuple[
    list[CameraSource],
    list[Stream],
    list[Zone],
    list[Event],
    list[Visit],
    list[ReviewLabel],
    list[DatasetExport],
]:
    # These records prove the product loop before real camera adapters exist.
    return (
        deepcopy(_INITIAL_SOURCES),
        deepcopy(_INITIAL_STREAMS),
        deepcopy(_INITIAL_ZONES),
        deepcopy(_INITIAL_EVENTS),
        deepcopy(_INITIAL_VISITS),
        deepcopy(_INITIAL_REVIEW_LABELS),
        deepcopy(_INITIAL_DATASET_EXPORTS),
    )


def seed_taxonomy_labels() -> list[TaxonomyLabel]:
    return deepcopy(_INITIAL_TAXONOMY_LABELS)


def reset_demo_data() -> None:
    global SOURCES, STREAMS, ZONES, EVENTS, VISITS, REVIEW_LABELS, DATASET_EXPORTS, TAXONOMY_LABELS

    SOURCES = deepcopy(_INITIAL_SOURCES)
    STREAMS = deepcopy(_INITIAL_STREAMS)
    ZONES = deepcopy(_INITIAL_ZONES)
    EVENTS = deepcopy(_INITIAL_EVENTS)
    VISITS = deepcopy(_INITIAL_VISITS)
    REVIEW_LABELS = deepcopy(_INITIAL_REVIEW_LABELS)
    DATASET_EXPORTS = deepcopy(_INITIAL_DATASET_EXPORTS)
    TAXONOMY_LABELS = deepcopy(_INITIAL_TAXONOMY_LABELS)


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


def get_dataset_export(export_id: str) -> DatasetExport | None:
    return next((dataset_export for dataset_export in DATASET_EXPORTS if dataset_export.id == export_id), None)


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


def _latest_label(labels: list[ReviewLabel]) -> str | None:
    if not labels:
        return None
    return max(labels, key=lambda label: label.created_at).label


def _skipped(skipped_reasons: Counter[str], reason: str) -> None:
    skipped_reasons[reason] += 1


def _zone_context(zone_id: str | None) -> tuple[str | None, str | None, ZoneType | None]:
    if zone_id is None:
        return None, None, None

    zone = get_zone(zone_id)
    if zone is None:
        return zone_id, None, None

    return zone.id, zone.name, zone.zone_type


def _visit_export_record(
    visit: Visit,
    event: Event,
    stream: Stream,
    export: DatasetExport,
) -> DatasetExportRecord:
    zone_id, zone_name, zone_type = (
        _zone_context(event.primary_zone_id)
        if export.include_zone_context
        else (None, None, None)
    )
    label = (
        visit.reviewed_label
        or _latest_label(review_labels_for_visit(visit.id))
        or _latest_label(review_labels_for_event(event.id))
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
        dataset_ready=visit_is_dataset_ready(visit),
        media_path=visit.representative_media_path,
        started_at=event.started_at,
        detections=event.detections if export.include_detections else [],
    )


def _event_export_record(event: Event, stream: Stream, export: DatasetExport) -> DatasetExportRecord:
    zone_id, zone_name, zone_type = (
        _zone_context(event.primary_zone_id)
        if export.include_zone_context
        else (None, None, None)
    )
    label = _latest_label(review_labels_for_event(event.id)) or (
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
        dataset_ready=event_is_dataset_ready(event),
        media_path=None,
        started_at=event.started_at,
        detections=event.detections if export.include_detections else [],
    )


def export_records_for_current_reviews(
    export: DatasetExport,
) -> tuple[list[DatasetExportRecord], Counter[str]]:
    records: list[DatasetExportRecord] = []
    skipped_reasons: Counter[str] = Counter()
    event_ids_with_visits = {visit.event_id for visit in VISITS}

    for visit in VISITS:
        event = get_event(visit.event_id)
        if event is None:
            _skipped(skipped_reasons, "missing_event")
            continue

        stream = get_stream(event.stream_id)
        if stream is None:
            _skipped(skipped_reasons, "missing_stream")
            continue

        dataset_ready = visit_is_dataset_ready(visit)
        if export.reviewed_only and not dataset_ready:
            _skipped(skipped_reasons, "needs_review")
            continue

        records.append(_visit_export_record(visit, event, stream, export))

    for event in EVENTS:
        if event.id in event_ids_with_visits:
            continue

        stream = get_stream(event.stream_id)
        if stream is None:
            _skipped(skipped_reasons, "missing_stream")
            continue

        dataset_ready = event_is_dataset_ready(event)
        if export.reviewed_only and not dataset_ready:
            _skipped(skipped_reasons, "needs_review")
            continue

        records.append(_event_export_record(event, stream, export))

    return records, skipped_reasons


def build_dataset_manifest(export_id: str) -> DatasetExportManifest | None:
    dataset_export = get_dataset_export(export_id)
    if dataset_export is None:
        return None

    # The manifest is the local-first dataset contract: corrections are truth,
    # detections are evidence, and media paths are references until storage exists.
    records, skipped_reasons = export_records_for_current_reviews(dataset_export)
    return DatasetExportManifest(
        export=dataset_export,
        records=records,
        skipped_count=sum(skipped_reasons.values()),
        skipped_reasons=dict(skipped_reasons),
        generated_at=datetime.now(UTC),
    )


def create_dataset_export(payload: DatasetExportCreate) -> DatasetExport:
    dataset_export = DatasetExport(
        id=f"dataset-export-{len(DATASET_EXPORTS) + 1:03d}",
        name=payload.name,
        status=ExportStatus.ready,
        reviewed_only=payload.reviewed_only,
        include_detections=payload.include_detections,
        include_zone_context=payload.include_zone_context,
        record_count=0,
        created_at=datetime.now(UTC),
    )
    records, _ = export_records_for_current_reviews(dataset_export)
    dataset_export.record_count = len(records)
    DATASET_EXPORTS.append(dataset_export)
    return dataset_export


def review_queue_items() -> list[ReviewQueueItem]:
    queue: list[ReviewQueueItem] = []

    for visit in VISITS:
        if visit.review_status != ReviewStatus.needs_review:
            continue

        event = get_event(visit.event_id)
        if event is None:
            continue
        stream = get_stream(event.stream_id)
        source = get_source(stream.source_id) if stream is not None else None
        zone = get_zone(event.primary_zone_id) if event.primary_zone_id is not None else None

        # The review queue is user-facing correction work, not raw model output.
        queue.append(
            ReviewQueueItem(
                id=f"review-queue-{visit.id}",
                item_type="visit",
                target_type="visit",
                target_id=visit.id,
                title=f"Review {visit.subject_label} visit",
                stream_id=event.stream_id,
                stream_name=stream.name if stream is not None else None,
                source_id=stream.source_id if stream is not None else None,
                source_name=source.name if source is not None else None,
                event_id=event.id,
                visit_id=visit.id,
                primary_zone_id=event.primary_zone_id,
                primary_zone_name=zone.name if zone is not None else None,
                primary_zone_type=zone.zone_type if zone is not None else None,
                zone_id=event.primary_zone_id,
                zone_name=zone.name if zone is not None else None,
                zone_type=zone.zone_type if zone is not None else None,
                suggested_label=visit.species_guess or visit.subject_label,
                review_status=visit.review_status,
                reason="Confirm or correct the suggested species label.",
            )
        )

    visit_event_ids = {item.event_id for item in queue if item.event_id is not None}
    for event in EVENTS:
        if event.review_status != ReviewStatus.needs_review or event.id in visit_event_ids:
            continue
        stream = get_stream(event.stream_id)
        source = get_source(stream.source_id) if stream is not None else None
        zone = get_zone(event.primary_zone_id) if event.primary_zone_id is not None else None

        queue.append(
            ReviewQueueItem(
                id=f"review-queue-{event.id}",
                item_type="event",
                target_type="event",
                target_id=event.id,
                title=event.title,
                stream_id=event.stream_id,
                stream_name=stream.name if stream is not None else None,
                source_id=stream.source_id if stream is not None else None,
                source_name=source.name if source is not None else None,
                event_id=event.id,
                visit_id=None,
                primary_zone_id=event.primary_zone_id,
                primary_zone_name=zone.name if zone is not None else None,
                primary_zone_type=zone.zone_type if zone is not None else None,
                zone_id=event.primary_zone_id,
                zone_name=zone.name if zone is not None else None,
                zone_type=zone.zone_type if zone is not None else None,
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
