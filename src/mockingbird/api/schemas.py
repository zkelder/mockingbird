"""Product-shaped API schemas for MockingBird."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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


class SourceConnectionStatusValue(str, Enum):
    demo = "demo"
    not_configured = "not_configured"
    configured = "configured"
    unavailable = "unavailable"
    offline = "offline"
    unsupported = "unsupported"


class SourceProviderKind(str, Enum):
    demo = "demo"
    placeholder = "placeholder"
    future_adapter = "future_adapter"
    manual_media = "manual_media"
    external_url = "external_url"


class SourceProviderDefinitionStatus(str, Enum):
    available_contract_only = "available_contract_only"
    future_adapter = "future_adapter"
    demo = "demo"


class StreamPlaybackStatusValue(str, Enum):
    demo = "demo"
    not_configured = "not_configured"
    unavailable = "unavailable"
    offline = "offline"
    unsupported = "unsupported"


class StreamPlaybackKind(str, Enum):
    placeholder = "placeholder"
    demo_panel = "demo_panel"
    external_url = "external_url"
    media_preview = "media_preview"


class ExternalUrlPreviewStatus(str, Enum):
    available = "available"
    not_configured = "not_configured"
    unavailable = "unavailable"
    unsupported = "unsupported"
    error = "error"


class ExternalUrlPreviewSaveStatus(str, Enum):
    saved = "saved"
    not_configured = "not_configured"
    unavailable = "unavailable"
    unsupported = "unsupported"
    error = "error"


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
    not_configured = "not_configured"
    unavailable = "unavailable"
    disabled = "disabled"


class MotionEvidenceStatus(str, Enum):
    pending = "pending"
    promoted = "promoted"
    ignored = "ignored"


class SpeciesSuggestionStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"


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


class SourceConnectionStatus(BaseModel):
    # Source connection status is product-level readiness, not provider plumbing.
    source_id: str
    status: SourceConnectionStatusValue
    provider_kind: SourceProviderKind
    display_title: str
    message: str
    setup_hint: str | None = None
    supports_streams: bool
    supports_live_playback: bool
    supports_zone_editing: bool
    adapter_key: str | None = None
    configured_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    stream_ids: list[str] = Field(default_factory=list)
    last_checked_at: datetime | None = None


class SourceConnectionStatusResponse(SourceConnectionStatus):
    pass


class SourceProviderField(BaseModel):
    key: str
    label: str
    required: bool
    secret: bool
    description: str | None = None
    placeholder: str | None = None


class SourceProviderDefinition(BaseModel):
    provider_key: str
    display_name: str
    description: str
    status: SourceProviderDefinitionStatus
    supports_live_playback: bool
    supports_zone_editing: bool
    fields: list[SourceProviderField] = Field(default_factory=list)


class SourceProviderConfiguration(BaseModel):
    source_id: str
    provider_key: str
    configured_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    safe_config_preview: dict[str, str] = Field(default_factory=dict)
    supports_live_playback: bool
    supports_zone_editing: bool
    message: str
    setup_hint: str | None = None


class SourceProviderConfigurationUpdate(BaseModel):
    provider_key: str
    config: dict[str, str | None] = Field(default_factory=dict)


class SourceSetupReviewStep(BaseModel):
    key: str
    label: str
    status: str
    message: str


class SourceSetupReviewStream(BaseModel):
    stream_id: str
    display_name: str
    playback_status: str
    playback_kind: str
    supports_live_playback: bool
    supports_zone_editing: bool
    message: str


class SourceSetupReviewResponse(BaseModel):
    # Read-only setup review combines product status without touching adapters.
    source_id: str
    provider_key: str
    provider_display_name: str
    source_status: str
    readiness_level: str
    display_title: str
    summary: str
    next_step: str
    configured_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    supports_live_playback: bool
    supports_zone_editing: bool
    stream_count: int = Field(ge=0)
    streams: list[SourceSetupReviewStream] = Field(default_factory=list)
    steps: list[SourceSetupReviewStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WebhookPayloadValidationRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    shared_secret_marker: str | None = None
    default_stream_id: str | None = None
    default_zone_id: str | None = None


class WebhookPayloadCandidate(BaseModel):
    candidate_type: str
    source_id: str
    stream_id: str | None = None
    zone_id: str | None = None
    external_event_id: str | None = None
    external_label: str | None = None
    external_confidence: float | None = None
    media_reference: str | None = None
    message: str
    warnings: list[str] = Field(default_factory=list)


class WebhookPayloadValidationResponse(BaseModel):
    source_id: str
    provider_key: str
    valid: bool
    dry_run: bool
    would_create_media_asset: bool
    would_create_motion_evidence: bool
    would_create_event: bool
    would_create_visit: bool
    would_create_review_label: bool
    would_create_species_suggestion: bool
    would_create_detection_proposal: bool
    would_create_truth: bool
    candidate: WebhookPayloadCandidate | None = None
    skipped_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class Stream(BaseModel):
    id: str
    source_id: str
    name: str
    description: str
    is_live: bool


class StreamPlaybackStatus(BaseModel):
    # Playback status is product-level readiness; adapters feed it later.
    stream_id: str
    source_id: str
    status: StreamPlaybackStatusValue
    playback_kind: StreamPlaybackKind
    display_title: str
    message: str
    setup_hint: str | None = None
    supports_zone_editing: bool
    supports_live_playback: bool
    adapter_key: str | None = None
    last_checked_at: datetime | None = None
    preview_media_asset_id: str | None = None
    preview_url: str | None = None


class StreamPlaybackStatusResponse(StreamPlaybackStatus):
    pass


class ExternalUrlPreviewRequest(BaseModel):
    timeout_seconds: float | None = Field(default=3.0)
    max_bytes: int | None = Field(default=5_000_000)


class ExternalUrlPreviewSaveRequest(BaseModel):
    stream_id: str | None = None
    timeout_seconds: float | None = Field(default=3.0)
    max_bytes: int | None = Field(default=5_000_000)
    note: str | None = None


class ExternalUrlPreviewResponse(BaseModel):
    # External URL preview is transient evidence context, not saved product truth.
    source_id: str
    provider_key: str
    status: ExternalUrlPreviewStatus
    message: str
    fetched_at: datetime | None = None
    content_type: str | None = None
    content_length: int | None = None
    bytes_read: int | None = None
    preview_data_url: str | None = None
    supports_live_playback: bool = False
    creates_truth: bool = False
    creates_media_asset: bool = False
    warnings: list[str] = Field(default_factory=list)


class ExternalUrlPreviewSaveResponse(BaseModel):
    # Saved previews are local MediaAssets only; correction remains truth.
    source_id: str
    stream_id: str | None = None
    media_asset_id: str | None = None
    status: ExternalUrlPreviewSaveStatus
    message: str
    fetched_at: datetime | None = None
    content_type: str | None = None
    bytes_written: int = Field(default=0, ge=0)
    file_name: str | None = None
    relative_path: str | None = None
    creates_event: bool = False
    creates_visit: bool = False
    creates_truth: bool = False
    warnings: list[str] = Field(default_factory=list)


class SavedPreviewMotionEvidenceRequest(BaseModel):
    stream_id: str | None = None
    zone_id: str | None = None
    note: str | None = None
    reason: str | None = None
    duplicate_policy: str | None = "skip_existing"


class SavedPreviewMotionEvidenceResponse(BaseModel):
    # Saved/imported media can become pending evidence only through explicit user action.
    motion_evidence_id: str
    media_asset_id: str
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    status: MotionEvidenceStatus
    message: str
    creates_event: bool = False
    creates_visit: bool = False
    creates_truth: bool = False
    duplicate_skipped: bool = False
    existing_motion_evidence_id: str | None = None
    provenance_kind: str | None = None
    warnings: list[str] = Field(default_factory=list)


class FolderImportEvidenceBatchDryRunRequest(BaseModel):
    media_asset_ids: list[str] | None = None
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    duplicate_policy: str = "skip_existing"
    max_items: int | None = Field(default=100, ge=1)


class FolderImportEvidenceBatchDryRunItem(BaseModel):
    media_asset_id: str
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    file_name: str | None = None
    eligible: bool
    would_create_motion_evidence: bool
    duplicate_skipped: bool = False
    existing_motion_evidence_id: str | None = None
    skip_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class FolderImportEvidenceBatchDryRunResponse(BaseModel):
    # Batch handoff dry-runs classify existing folder media without mutating truth.
    items: list[FolderImportEvidenceBatchDryRunItem]
    total_items: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    would_create_count: int = Field(ge=0)
    duplicate_skipped_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    dry_run: bool = True
    creates_motion_evidence: bool = False
    creates_events: bool = False
    creates_visits: bool = False
    creates_truth: bool = False
    warnings: list[str] = Field(default_factory=list)


class FolderImportEvidenceBatchCreateRequest(BaseModel):
    media_asset_ids: list[str] | None = None
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    duplicate_policy: str = "skip_existing"
    max_items: int | None = Field(default=100, ge=1)
    confirm: bool = False
    note: str | None = None
    reason: str | None = None


class FolderImportEvidenceBatchCreateItem(BaseModel):
    media_asset_id: str
    motion_evidence_id: str | None = None
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    created: bool
    duplicate_skipped: bool = False
    existing_motion_evidence_id: str | None = None
    skip_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class FolderImportEvidenceBatchCreateResponse(BaseModel):
    # Confirmed batch handoff creates pending evidence only; correction remains truth.
    items: list[FolderImportEvidenceBatchCreateItem]
    total_items: int = Field(ge=0)
    created_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    duplicate_skipped_count: int = Field(ge=0)
    creates_motion_evidence: bool
    creates_events: bool = False
    creates_visits: bool = False
    creates_truth: bool = False
    message: str
    warnings: list[str] = Field(default_factory=list)


class SavedMediaRetentionItem(BaseModel):
    # Retention reporting classifies storage risk without changing truth.
    media_asset_id: str
    source_id: str | None = None
    stream_id: str | None = None
    file_name: str | None = None
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    created_at: datetime | None = None
    fetched_at: datetime | None = None
    provider_key: str | None = None
    provenance: str | None = None
    linked_motion_evidence_count: int = Field(ge=0)
    linked_event_count: int = Field(ge=0)
    linked_visit_count: int = Field(ge=0)
    reviewed_truth_count: int = Field(ge=0)
    risk_level: str
    media_state: str
    recommended_action: str
    warnings: list[str] = Field(default_factory=list)


class SavedMediaRetentionSummary(BaseModel):
    total_items: int = Field(ge=0)
    total_known_bytes: int = Field(ge=0)
    unknown_size_count: int = Field(ge=0)
    low_risk_count: int = Field(ge=0)
    medium_risk_count: int = Field(ge=0)
    high_risk_count: int = Field(ge=0)
    protected_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class SavedMediaRetentionReportResponse(BaseModel):
    items: list[SavedMediaRetentionItem]
    summary: SavedMediaRetentionSummary
    generated_at: datetime
    dry_run_only: bool = True


class SavedMediaCleanupDryRunRequest(BaseModel):
    media_asset_ids: list[str] | None = None
    risk_levels: list[str] | None = None
    include_protected: bool = False
    mode: str = "delete_file_only"


class SavedMediaCleanupDryRunItem(BaseModel):
    media_asset_id: str
    risk_level: str
    would_delete_file: bool
    would_delete_record: bool
    would_skip: bool
    skip_reason: str | None = None
    file_name: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)


class SavedMediaCleanupDryRunResponse(BaseModel):
    items: list[SavedMediaCleanupDryRunItem]
    total_would_delete_files: int = Field(ge=0)
    total_would_delete_records: int = Field(ge=0)
    total_known_bytes_to_delete: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    protected_skipped_count: int = Field(ge=0)
    dry_run: bool = True
    creates_truth: bool = False
    deletes_truth: bool = False
    warnings: list[str] = Field(default_factory=list)


class SavedMediaCleanupRequest(BaseModel):
    mode: str = "delete_file_only"
    confirm: bool = False
    reason: str | None = None


class SavedMediaCleanupResponse(BaseModel):
    media_asset_id: str
    status: str
    risk_level: str
    media_state: str
    file_deleted: bool
    record_deleted: bool = False
    creates_truth: bool = False
    deletes_truth: bool = False
    message: str
    file_name: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)


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


class ModelAdapterConfigurationStatus(BaseModel):
    adapter_id: str
    model_path_configured: bool
    labels_path_configured: bool
    runtime_available: bool
    supported_media_types: list[str]
    can_run: bool
    status_reason: str
    setup_hint: str
    creates_review_truth: bool
    local_only: bool


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
    configuration_status: ModelAdapterConfigurationStatus | None = None


class ModelAdapterRunRequest(BaseModel):
    adapter_id: str
    media_asset_id: str
    zone_ids: list[str] | None = None
    requested_labels: list[str] | None = None
    notes: str | None = None


class AdapterEvaluationOutcome(str, Enum):
    matched_reviewed_truth = "matched_reviewed_truth"
    mismatched_reviewed_truth = "mismatched_reviewed_truth"
    awaiting_review = "awaiting_review"
    rejected_evidence = "rejected_evidence"
    converted_needs_review = "converted_needs_review"
    unknown_reviewed_label = "unknown_reviewed_label"


class AdapterEvaluationItem(BaseModel):
    # Adapter evaluation compares evidence against reviewed truth without mutating product state.
    proposal_id: str
    detection_run_id: str
    adapter_id: str | None = None
    media_asset_id: str
    event_id: str | None = None
    visit_id: str | None = None
    proposal_label: str
    proposal_display_name: str | None = None
    proposal_confidence: float = Field(ge=0, le=1)
    reviewed_label: str | None = None
    reviewed_display_name: str | None = None
    review_status: ReviewStatus
    outcome: AdapterEvaluationOutcome
    notes: str | None = None


class AdapterEvaluationSummary(BaseModel):
    adapter_id: str | None = None
    adapter_name: str | None = None
    proposal_count: int = Field(ge=0)
    reviewed_count: int = Field(ge=0)
    unreviewed_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    mismatched_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    converted_count: int = Field(ge=0)
    unknown_reviewed_count: int = Field(ge=0)
    match_rate: float | None = Field(default=None, ge=0, le=1)
    items: list[AdapterEvaluationItem]
    generated_at: datetime
    local_first_note: str


class ModelReadinessChecklistItem(BaseModel):
    id: str
    label: str
    status: str
    severity: str
    description: str
    suggested_action: str
    link_path: str | None = None


class ModelReadinessSummary(BaseModel):
    # Pre-model readiness is a product guardrail. It does not run media analysis.
    reviewed_record_count: int = Field(ge=0)
    export_ready_count: int = Field(ge=0)
    dataset_quality_issue_count: int = Field(ge=0)
    high_quality_issue_count: int = Field(ge=0)
    reviewed_species_count: int = Field(ge=0)
    target_species_count: int = Field(ge=0)
    covered_target_species_count: int = Field(ge=0)
    missing_target_species_count: int = Field(ge=0)
    adapter_proposal_count: int = Field(ge=0)
    adapter_reviewed_count: int = Field(ge=0)
    adapter_match_rate: float | None = Field(default=None, ge=0, le=1)
    ready_for_first_detector_spike: bool
    recommended_next_step: str
    checklist: list[ModelReadinessChecklistItem]
    generated_at: datetime
    local_first_note: str


class MotionZoneInput(BaseModel):
    zone_id: str
    left: float
    top: float
    right: float
    bottom: float


class MotionEvaluateFrameRequest(BaseModel):
    previous_frame: list[list[float]]
    current_frame: list[list[float]]
    zones: list[MotionZoneInput]
    frame_index: int = 0
    pixel_delta_threshold: float = 25.0
    min_changed_ratio: float = 0.02


class MotionScoreResponse(BaseModel):
    zone_id: str
    changed_pixels: int = Field(ge=0)
    total_pixels: int = Field(ge=0)
    changed_ratio: float
    mean_delta: float
    triggered: bool


class MotionFrameScoreResponse(BaseModel):
    frame_index: int
    scores: list[MotionScoreResponse]
    triggered_zone_ids: list[str]
    strongest_zone_id: str | None
    strongest_changed_ratio: float


class MotionCandidateResponse(BaseModel):
    zone_id: str
    start_frame_index: int
    end_frame_index: int
    best_frame_index: int
    peak_changed_ratio: float
    triggered_frame_count: int = Field(ge=0)


class MotionExtractCandidatesRequest(BaseModel):
    frame_scores: list[MotionFrameScoreResponse]
    min_triggered_frames: int = 2
    max_gap_frames: int = 1


class MotionExtractCandidatesResponse(BaseModel):
    candidates: list[MotionCandidateResponse]


class MotionEvaluateSequenceRequest(BaseModel):
    frames: list[list[list[float]]] = Field(min_length=2)
    zones: list[MotionZoneInput] = Field(min_length=1)
    source_id: str | None = None
    stream_id: str | None = None
    frame_index_start: int = Field(default=0, ge=0)
    pixel_delta_threshold: float = Field(default=25.0, ge=0)
    min_changed_ratio: float = Field(default=0.02, ge=0, le=1)
    min_triggered_frames: int = Field(default=2, ge=1)
    max_gap_frames: int = Field(default=1, ge=0)
    create_motion_evidence: bool = False
    notes: str | None = None


class MotionEvidenceCreateRequest(BaseModel):
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str
    start_frame_index: int | None = None
    end_frame_index: int | None = None
    best_frame_index: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    best_frame_time: str | None = None
    peak_changed_ratio: float = Field(ge=0, le=1)
    triggered_frame_count: int = Field(ge=1)
    scoring_config: dict[str, str | int | float | bool] = Field(default_factory=dict)
    snapshot_media_asset_id: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_frame_window(self) -> "MotionEvidenceCreateRequest":
        if (
            self.start_frame_index is not None
            and self.end_frame_index is not None
            and self.end_frame_index < self.start_frame_index
        ):
            raise ValueError("end_frame_index must be greater than or equal to start_frame_index")

        if (
            self.best_frame_index is not None
            and self.start_frame_index is not None
            and self.best_frame_index < self.start_frame_index
        ):
            raise ValueError("best_frame_index must be within the frame range")

        if (
            self.best_frame_index is not None
            and self.end_frame_index is not None
            and self.best_frame_index > self.end_frame_index
        ):
            raise ValueError("best_frame_index must be within the frame range")

        return self


class MotionEvidenceResponse(BaseModel):
    id: str
    source_id: str | None
    stream_id: str | None
    zone_id: str
    start_frame_index: int | None
    end_frame_index: int | None
    best_frame_index: int | None
    start_time: str | None
    end_time: str | None
    best_frame_time: str | None
    peak_changed_ratio: float
    triggered_frame_count: int
    scoring_config: dict[str, str | int | float | bool]
    snapshot_media_asset_id: str | None
    status: MotionEvidenceStatus
    promoted_event_id: str | None
    promoted_visit_id: str | None
    created_at: datetime
    notes: str | None


class MotionEvaluateSequenceResponse(BaseModel):
    frame_scores: list[MotionFrameScoreResponse]
    candidates: list[MotionCandidateResponse]
    created_evidence: list[MotionEvidenceResponse]


class MotionEvidenceListResponse(BaseModel):
    motion_evidence: list[MotionEvidenceResponse]


class MotionEvidenceAttachMediaRequest(BaseModel):
    snapshot_media_asset_id: str | None = None


class MotionEvidencePromoteRequest(BaseModel):
    event_title: str | None = None
    visit_label_hint: str | None = None
    notes: str | None = None
    create_event: bool = True
    create_visit: bool = True
    attach_snapshot_media_asset_id: str | None = None


class MotionEvidencePromoteResponse(BaseModel):
    evidence: MotionEvidenceResponse
    event_id: str | None
    visit_id: str | None


class SpeciesSuggestionCreateRequest(BaseModel):
    source_id: str | None = None
    stream_id: str | None = None
    event_id: str | None = None
    visit_id: str | None = None
    media_asset_id: str | None = None
    motion_evidence_id: str | None = None
    adapter_id: str
    adapter_name: str
    suggested_label: str
    suggested_common_name: str | None = None
    suggested_scientific_name: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    rank: int = Field(default=1, ge=1)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    evidence_region: dict[str, Any] | None = None
    notes: str | None = None

    @field_validator("adapter_id", "adapter_name", "suggested_label")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value

    @field_validator("alternatives")
    @classmethod
    def alternatives_must_be_json_compatible(
        cls,
        value: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        _ensure_json_compatible(value, "alternatives")
        return value

    @field_validator("evidence_region")
    @classmethod
    def evidence_region_must_be_json_compatible(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None:
            _ensure_json_compatible(value, "evidence_region")
        return value


class MockSpeciesSuggestionRequest(BaseModel):
    visit_id: str
    adapter_id: str = "mock_species_suggester"
    adapter_name: str = "Mock species suggester"
    suggested_label: str | None = None
    confidence: float = Field(default=0.72, ge=0, le=1)
    notes: str | None = None

    @field_validator("visit_id", "adapter_id", "adapter_name")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value

    @field_validator("suggested_label")
    @classmethod
    def optional_label_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("field must not be blank")
        return value


class SpeciesSuggestionResponse(BaseModel):
    id: str
    source_id: str | None
    stream_id: str | None
    event_id: str | None
    visit_id: str | None
    media_asset_id: str | None
    motion_evidence_id: str | None
    adapter_id: str
    adapter_name: str
    suggested_label: str
    suggested_common_name: str | None
    suggested_scientific_name: str | None
    confidence: float | None
    rank: int
    alternatives: list[dict[str, Any]]
    evidence_region: dict[str, Any] | None
    status: SpeciesSuggestionStatus
    created_at: datetime
    notes: str | None


class SpeciesSuggestionListResponse(BaseModel):
    species_suggestions: list[SpeciesSuggestionResponse]


class SpeciesSuggestionStatusUpdateRequest(BaseModel):
    status: SpeciesSuggestionStatus


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


class ClassifierReadinessSpeciesSummary(BaseModel):
    label: str
    reviewed_examples: int = Field(ge=0)
    media_backed_examples: int = Field(ge=0)
    export_ready_examples: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ClassifierReadinessSkipSummary(BaseModel):
    reason: str
    count: int = Field(ge=0)


class ClassifierReadinessReport(BaseModel):
    # Readiness is a pre-export signal. It does not generate datasets or run models.
    ready_for_manifest_export: bool
    reviewed_examples: int = Field(ge=0)
    media_backed_reviewed_examples: int = Field(ge=0)
    export_ready_examples: int = Field(ge=0)
    species: list[ClassifierReadinessSpeciesSummary]
    missing_target_labels: list[str]
    unknown_label_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    out_of_taxonomy_count: int = Field(ge=0)
    skipped: list[ClassifierReadinessSkipSummary]
    warnings: list[str] = Field(default_factory=list)
    recommended_next_step: str


class ClassifierManifestExample(BaseModel):
    example_id: str
    visit_id: str
    event_id: str | None = None
    media_asset_id: str
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    local_media_path: str | None = None
    label: str
    taxonomy_id: str | None = None
    common_name: str | None = None
    scientific_name: str | None = None
    reviewed_label_id: str | None = None
    reviewed_at: str | None = None
    created_at: str | None = None
    split: str
    quality_flags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ClassifierManifestSkippedRecord(BaseModel):
    record_id: str
    record_type: str
    visit_id: str | None = None
    event_id: str | None = None
    media_asset_id: str | None = None
    label: str | None = None
    reason: str
    detail: str | None = None


class ClassifierManifestTaxonomyEntry(BaseModel):
    label: str
    taxonomy_id: str | None = None
    common_name: str | None = None
    scientific_name: str | None = None
    aliases: list[str] = Field(default_factory=list)


class ClassifierManifestSummary(BaseModel):
    examples: int = Field(ge=0)
    skipped: int = Field(ge=0)
    labels: dict[str, int]
    splits: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


class ClassifierTrainingManifestResponse(BaseModel):
    # Manifest preview is read-only structured data. It writes no files and runs no models.
    manifest_version: str
    generated_at: str
    examples: list[ClassifierManifestExample]
    skipped_records: list[ClassifierManifestSkippedRecord]
    taxonomy: list[ClassifierManifestTaxonomyEntry]
    summary: ClassifierManifestSummary
    warnings: list[str] = Field(default_factory=list)


class ClassifierManifestFileExportRequest(BaseModel):
    include_csv: bool = False
    include_summary: bool = True
    split_seed: str | None = None
    output_name: str | None = None
    media_policy: str = "reference_only"
    dry_run: bool = False

    @field_validator("media_policy")
    @classmethod
    def validate_media_policy(cls, value: str) -> str:
        if value not in {"reference_only", "copy_media"}:
            raise ValueError("media_policy must be 'reference_only' or 'copy_media'")
        return value

    @model_validator(mode="after")
    def validate_copy_media_phase(self) -> "ClassifierManifestFileExportRequest":
        if self.media_policy == "copy_media" and not self.dry_run:
            raise ValueError("copy_media export is dry-run only in this phase.")
        return self

    @field_validator("output_name")
    @classmethod
    def validate_output_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        name = value.strip()
        safe_chars = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "._-"
        )
        if (
            not name
            or len(name) > 80
            or name in {".", ".."}
            or not name[0].isalnum()
            or any(char not in safe_chars for char in name)
        ):
            raise ValueError(
                "output_name must be a safe filename using letters, numbers, '.', '_', or '-'"
            )
        return name


class ClassifierManifestExportFile(BaseModel):
    name: str
    relative_path: str
    content_type: str
    size_bytes: int | None = Field(default=None, ge=0)


class ClassifierManifestPlannedMediaFile(BaseModel):
    example_id: str
    media_asset_id: str
    source_path: str | None = None
    planned_relative_path: str
    size_bytes: int | None = Field(default=None, ge=0)
    reason: str | None = None


class ClassifierManifestSkippedMediaRecord(BaseModel):
    example_id: str
    media_asset_id: str
    source_path: str | None = None
    reason: str
    detail: str | None = None


class ClassifierManifestFileExportResponse(BaseModel):
    # Metadata exports write local manifest files only; reviewed corrections remain truth.
    export_id: str
    output_directory: str | None = None
    files: list[ClassifierManifestExportFile]
    examples: int = Field(ge=0)
    skipped: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    created_at: str
    dry_run: bool
    media_policy: str = "reference_only"
    planned_media_files: list[ClassifierManifestPlannedMediaFile] = Field(default_factory=list)
    skipped_media: list[ClassifierManifestSkippedMediaRecord] = Field(default_factory=list)
    total_planned_media_bytes: int | None = Field(default=None, ge=0)


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
    motion_evidence_count: int = Field(ge=0)
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


class SourceFolderImportPreviewRequest(BaseModel):
    recursive: bool | None = None
    allowed_extensions: list[str] | None = None
    max_files: int | None = Field(default=500, ge=1)
    max_depth: int | None = Field(default=1, ge=0)


class SourceFolderImportPreviewCandidate(BaseModel):
    relative_path: str
    file_name: str
    extension: str
    size_bytes: int | None = Field(default=None, ge=0)
    modified_at: datetime | None = None
    planned_media_kind: str
    warnings: list[str] = Field(default_factory=list)


class SourceFolderImportPreviewSkipped(BaseModel):
    relative_path: str | None = None
    file_name: str | None = None
    reason: str
    message: str


class SourceFolderImportPreviewResponse(BaseModel):
    # Source-scoped folder preview is an explicit dry run; it creates no truth.
    source_id: str
    provider_key: str
    folder_configured: bool
    recursive: bool
    allowed_extensions: list[str]
    candidates: list[SourceFolderImportPreviewCandidate] = Field(default_factory=list)
    skipped: list[SourceFolderImportPreviewSkipped] = Field(default_factory=list)
    total_candidates: int = Field(ge=0)
    total_skipped: int = Field(ge=0)
    total_known_bytes: int = Field(ge=0)
    unknown_size_count: int = Field(ge=0)
    scanned_at: datetime
    dry_run: bool = True
    creates_media_assets: bool = False
    creates_events: bool = False
    creates_visits: bool = False
    creates_truth: bool = False
    warnings: list[str] = Field(default_factory=list)


class SourceFolderImportRequest(BaseModel):
    recursive: bool | None = None
    allowed_extensions: list[str] | None = None
    max_files: int | None = Field(default=500, ge=1)
    max_depth: int | None = Field(default=1, ge=0)
    relative_paths: list[str] | None = None
    default_stream_id: str | None = None
    default_zone_id: str | None = None
    note: str | None = None
    copy_mode: str = "copy_to_media_root"


class SourceFolderImportCreatedMediaAsset(BaseModel):
    media_asset_id: str
    relative_source_path: str
    file_name: str
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    stream_id: str | None = None
    zone_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SourceFolderImportSkipped(BaseModel):
    relative_path: str | None = None
    file_name: str | None = None
    reason: str
    message: str


class SourceFolderImportResponse(BaseModel):
    # Source-scoped folder import copies media only; review truth remains future/user-created.
    source_id: str
    provider_key: str
    imported: list[SourceFolderImportCreatedMediaAsset] = Field(default_factory=list)
    skipped: list[SourceFolderImportSkipped] = Field(default_factory=list)
    total_imported: int = Field(ge=0)
    total_skipped: int = Field(ge=0)
    total_bytes_copied: int = Field(ge=0)
    imported_at: datetime
    copy_mode: str
    creates_media_assets: bool
    creates_motion_evidence: bool = False
    creates_events: bool = False
    creates_visits: bool = False
    creates_truth: bool = False
    warnings: list[str] = Field(default_factory=list)


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


def _ensure_json_compatible(value: Any, field_name: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be JSON-compatible") from error
