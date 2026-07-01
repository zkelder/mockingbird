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


class DetectionSource(str, Enum):
    manual = "manual"
    demo_rule = "demo_rule"
    future_model = "future_model"
    integration = "integration"


class DetectionRunStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class DetectionProposalStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"
    converted = "converted"


class DetectionProposalDecision(str, Enum):
    accept = "accept"
    reject = "reject"
    convert_to_event = "convert_to_event"


class ModelAdapterKind(str, Enum):
    object_detector = "object_detector"
    species_classifier = "species_classifier"
    audio_classifier = "audio_classifier"
    motion_filter = "motion_filter"
    integration = "integration"
    demo = "demo"


class ModelAdapterStatus(str, Enum):
    available = "available"
    unavailable = "unavailable"
    disabled = "disabled"


class LabelCategory(str, Enum):
    bird = "bird"
    mammal = "mammal"
    pet = "pet"
    person = "person"
    vehicle = "vehicle"
    object = "object"
    false_positive = "false_positive"
    unknown = "unknown"


class TaxonomyLabel(BaseModel):
    # Taxonomy labels are normalized review targets; detections remain evidence.
    id: str
    label: str
    display_name: str
    category: LabelCategory
    scientific_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    is_species: bool
    is_reviewable: bool
    sort_order: int | None = None


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


class DetectionRun(BaseModel):
    id: str
    media_asset_id: str
    source: DetectionSource
    summary: str | None = None
    status: DetectionRunStatus
    created_at: datetime
    completed_at: datetime | None = None


class DetectionRunCreate(BaseModel):
    media_asset_id: str
    source: DetectionSource = DetectionSource.demo_rule
    summary: str | None = None


class DemoDetectionRunCreate(BaseModel):
    media_asset_id: str
    zone_id: str | None = None
    label: str = "bird"
    confidence: float = Field(default=0.72, ge=0, le=1)
    suggested_subject_label: str = "unknown_bird"
    suggested_species: str | None = None
    notes: str | None = None


class ModelAdapter(BaseModel):
    # Model adapters produce proposal evidence only; review labels remain truth.
    id: str
    name: str
    kind: ModelAdapterKind
    status: ModelAdapterStatus
    version: str | None = None
    description: str
    supported_media_types: list[str]
    supported_labels: list[str]
    creates_review_truth: bool = False
    local_only: bool = True
    notes: str | None = None


class ModelAdapterRunRequest(BaseModel):
    adapter_id: str
    media_asset_id: str
    zone_ids: list[str] | None = None
    requested_labels: list[str] | None = None
    notes: str | None = None


class DetectionProposal(BaseModel):
    id: str
    run_id: str
    media_asset_id: str
    stream_id: str
    zone_id: str | None = None
    event_id: str | None = None
    visit_id: str | None = None
    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox | None = None
    suggested_event_type: str
    suggested_subject_label: str
    suggested_species: str | None = None
    status: DetectionProposalStatus
    notes: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class DetectionProposalCreate(BaseModel):
    media_asset_id: str
    stream_id: str | None = None
    zone_id: str | None = None
    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox | None = None
    suggested_event_type: str = "animal_visit"
    suggested_subject_label: str = "unknown_animal"
    suggested_species: str | None = None
    notes: str | None = None


class DetectionProposalDecisionCreate(BaseModel):
    decision: DetectionProposalDecision
    event_title: str | None = None
    subject_label: str | None = None
    species_guess: str | None = None
    notes: str | None = None


class DemoDetectionRunResult(BaseModel):
    detection_run: DetectionRun
    proposals: list[DetectionProposal]
    review_queue_count: int


class ReviewQueueItem(BaseModel):
    id: str
    item_type: str
    title: str
    stream_id: str
    event_id: str | None = None
    visit_id: str | None = None
    primary_zone_id: str | None = None
    suggested_label: str | None = None
    media_asset: MediaAsset | None = None
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
    label_display_name: str | None = None
    label_category: LabelCategory | None = None
    is_species: bool | None = None
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


class DatasetCoverageSpecies(BaseModel):
    label: str
    display_name: str
    category: str
    is_species: bool
    reviewed_record_count: int = Field(ge=0)
    export_ready_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    media_asset_count: int = Field(ge=0)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class DatasetCoverageGap(BaseModel):
    label: str
    display_name: str
    reason: str
    target_category: str | None = None


class DatasetCoverageSummary(BaseModel):
    reviewed_record_count: int = Field(ge=0)
    export_ready_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    unknown_bird_count: int = Field(ge=0)
    unknown_animal_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    reviewed_species_count: int = Field(ge=0)
    target_species_count: int = Field(ge=0)
    covered_target_species_count: int = Field(ge=0)
    missing_target_species_count: int = Field(ge=0)
    species: list[DatasetCoverageSpecies]
    gaps: list[DatasetCoverageGap]
    generated_at: datetime
    local_first_note: str


class DatasetQualityIssue(BaseModel):
    id: str
    severity: str
    issue_type: str
    title: str
    description: str
    target_type: str
    target_id: str
    event_id: str | None = None
    visit_id: str | None = None
    media_asset_id: str | None = None
    label: str | None = None
    suggested_action: str
    link_path: str | None = None


class DatasetQualitySummary(BaseModel):
    issue_count: int = Field(ge=0)
    high_count: int = Field(ge=0)
    medium_count: int = Field(ge=0)
    low_count: int = Field(ge=0)
    freeform_label_count: int = Field(ge=0)
    unknown_label_count: int = Field(ge=0)
    missing_zone_count: int = Field(ge=0)
    missing_media_count: int = Field(ge=0)
    conflicting_correction_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    export_ready_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    issues: list[DatasetQualityIssue]
    generated_at: datetime
    local_first_note: str


class AnalyticsSummary(BaseModel):
    event_count: int = Field(ge=0)
    visit_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    species_counts: dict[str, int]
    label_display_names: dict[str, str] = Field(default_factory=dict)
    label_categories: dict[str, LabelCategory] = Field(default_factory=dict)
    species_label_ids: list[str] = Field(default_factory=list)
    zone_activity_counts: dict[str, int]


class DetectionProposalDecisionResult(BaseModel):
    proposal: DetectionProposal
    event: Event | None = None
    visit: Visit | None = None
    review_queue_count: int = Field(ge=0)
    analytics: AnalyticsSummary


class ModelAdapterRunResult(BaseModel):
    adapter: ModelAdapter
    detection_run: DetectionRun
    proposals: list[DetectionProposal]
    review_queue_count: int = Field(ge=0)
    local_first_note: str


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
    detection_run_count: int = Field(ge=0)
    detection_proposal_count: int = Field(ge=0)
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


class FolderImportPreviewRequest(BaseModel):
    folder_path: str


class FolderImportCandidate(BaseModel):
    filename: str
    path: str
    content_type: str
    media_type: str
    file_size_bytes: int = Field(ge=0)


class FolderImportSkippedFile(BaseModel):
    filename: str
    reason: str


class FolderImportPreview(BaseModel):
    folder_path: str
    supported_files: list[FolderImportCandidate]
    skipped_files: list[FolderImportSkippedFile]
    supported_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)


class FolderImportCreate(BaseModel):
    folder_path: str
    stream_id: str | None = None
    zone_id: str | None = None
    subject_label: str = "unknown_animal"
    species_guess: str | None = None
    notes: str | None = None
    limit: int | None = Field(default=None, ge=1)


class FolderImportResult(BaseModel):
    folder_path: str
    imported_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    media_assets: list[MediaAsset]
    events: list[Event]
    visits: list[Visit]
    skipped_files: list[FolderImportSkippedFile]
    review_queue_count: int = Field(ge=0)


class EventDetail(BaseModel):
    event: Event
    stream: Stream
    primary_zone: Zone | None = None
    visits: list[Visit]
    media_asset: MediaAsset | None = None
    detection_proposals: list[DetectionProposal] = Field(default_factory=list)
    detection_runs: list[DetectionRun] = Field(default_factory=list)
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
    detection_proposals: list[DetectionProposal] = Field(default_factory=list)
    detection_runs: list[DetectionRun] = Field(default_factory=list)
    review_labels: list[ReviewLabel]
    dataset_ready: bool
    review_summary: str
