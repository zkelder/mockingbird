"""Product-shaped API schemas for MockingBird."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    demo = "demo"
    manual_upload = "manual_upload"
    local_folder = "local_folder"
    rtsp = "rtsp"
    local_camera = "local_camera"
    webhook = "webhook"
    integration = "integration"


class SourceStatus(str, Enum):
    connected = "connected"
    disconnected = "disconnected"
    needs_setup = "needs_setup"


class ZoneType(str, Enum):
    feeder = "feeder"
    birdbath = "birdbath"
    ground = "ground"
    perch = "perch"
    yard = "yard"
    driveway = "driveway"
    privacy = "privacy"
    ignore = "ignore"


class ReviewStatus(str, Enum):
    needs_review = "needs_review"
    reviewed = "reviewed"
    rejected = "rejected"


class ExportStatus(str, Enum):
    ready = "ready"
    building = "building"
    failed = "failed"


class CameraSource(BaseModel):
    # Source adapters normalize into product streams and events later.
    id: str
    name: str
    kind: SourceKind
    status: SourceStatus
    description: str


class Stream(BaseModel):
    id: str
    source_id: str
    name: str
    description: str
    is_live: bool


class Point(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class BoundingBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class Zone(BaseModel):
    # Privacy and ignore zones are product concepts, not adapter settings.
    id: str
    stream_id: str
    name: str
    zone_type: ZoneType
    polygon: list[Point]
    is_active: bool


class ZoneCreate(BaseModel):
    stream_id: str
    name: str
    zone_type: ZoneType
    polygon: list[Point]
    is_active: bool = True


class ZoneUpdate(BaseModel):
    name: str | None = None
    zone_type: ZoneType | None = None
    polygon: list[Point] | None = None
    is_active: bool | None = None


class ZoneMutationResult(BaseModel):
    zone: Zone
    zones: list[Zone]


class Detection(BaseModel):
    # Detection is model or rule evidence. It is not user-confirmed truth.
    id: str
    label: str
    confidence: float = Field(ge=0, le=1)
    zone_id: str | None = None
    bbox: BoundingBox | None = None


class Event(BaseModel):
    id: str
    stream_id: str
    title: str
    event_type: str
    started_at: datetime
    ended_at: datetime | None = None
    primary_zone_id: str | None = None
    review_status: ReviewStatus
    detections: list[Detection]


class Visit(BaseModel):
    id: str
    event_id: str
    subject_label: str
    species_guess: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reviewed_label: str | None = None
    review_status: ReviewStatus
    representative_media_path: str | None = None


class MediaAsset(BaseModel):
    # Media assets are local evidence references that feed reviewable product events.
    id: str
    source_id: str | None = None
    stream_id: str
    filename: str
    content_type: str
    media_type: str
    local_path: str
    original_filename: str
    file_size_bytes: int = Field(ge=0)
    created_at: datetime
    notes: str | None = None


class ReviewQueueItem(BaseModel):
    id: str
    item_type: str
    title: str
    stream_id: str
    event_id: str | None = None
    visit_id: str | None = None
    primary_zone_id: str | None = None
    suggested_label: str | None = None
    review_status: ReviewStatus
    reason: str


class ReviewLabel(BaseModel):
    # Review labels are dataset-grade user truth that can override detections.
    id: str
    target_type: str
    target_id: str
    label: str
    notes: str | None = None
    created_at: datetime


class ReviewLabelCreate(BaseModel):
    target_type: str
    target_id: str
    label: str
    notes: str | None = None


class ReviewCorrectionCreate(BaseModel):
    target_type: str
    target_id: str
    label: str
    notes: str | None = None


class DatasetExport(BaseModel):
    id: str
    name: str
    status: ExportStatus
    reviewed_only: bool
    include_detections: bool = True
    include_zone_context: bool = True
    record_count: int = Field(ge=0)
    created_at: datetime


class DatasetExportCreate(BaseModel):
    name: str
    reviewed_only: bool = True
    include_detections: bool = True
    include_zone_context: bool = True


class DatasetExportRecord(BaseModel):
    record_id: str
    event_id: str
    visit_id: str | None = None
    stream_id: str
    source_id: str
    label: str
    subject_label: str
    zone_id: str | None = None
    zone_name: str | None = None
    zone_type: ZoneType | None = None
    reviewed: bool
    dataset_ready: bool
    media_path: str | None = None
    started_at: datetime
    detections: list[Detection] = Field(default_factory=list)


class DatasetExportManifest(BaseModel):
    export: DatasetExport
    records: list[DatasetExportRecord]
    skipped_count: int = Field(ge=0)
    skipped_reasons: dict[str, int]
    generated_at: datetime


class DatasetExportDetail(BaseModel):
    export: DatasetExport
    manifest: DatasetExportManifest


class AnalyticsSummary(BaseModel):
    event_count: int = Field(ge=0)
    visit_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    species_counts: dict[str, int]
    zone_activity_counts: dict[str, int]


class LocalDataStatus(BaseModel):
    database_url: str
    database_path: str | None = None
    using_default_database: bool
    source_count: int = Field(ge=0)
    stream_count: int = Field(ge=0)
    zone_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    visit_count: int = Field(ge=0)
    media_asset_count: int = Field(ge=0)
    review_label_count: int = Field(ge=0)
    dataset_export_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    database_ready: bool
    seed_data_present: bool
    local_first_note: str


class ReviewCorrectionResult(BaseModel):
    review_label: ReviewLabel
    visit: Visit | None = None
    event: Event | None = None
    review_queue_count: int = Field(ge=0)
    analytics: AnalyticsSummary


class MediaImportResult(BaseModel):
    media_asset: MediaAsset
    event: Event
    visit: Visit | None = None
    stream: Stream
    review_queue_count: int = Field(ge=0)


class EventDetail(BaseModel):
    event: Event
    stream: Stream
    primary_zone: Zone | None = None
    visits: list[Visit]
    media_asset: MediaAsset | None = None
    review_labels: list[ReviewLabel]
    dataset_ready: bool
    review_summary: str


class VisitDetail(BaseModel):
    visit: Visit
    event: Event
    stream: Stream
    primary_zone: Zone | None = None
    detections: list[Detection]
    media_asset: MediaAsset | None = None
    review_labels: list[ReviewLabel]
    dataset_ready: bool
    review_summary: str
