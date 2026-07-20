"""Product-shaped API schemas for MockingBird."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    archived = "archived"


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
    local_camera = "local_camera"


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
    live_ready = "live_ready"
    needs_stream_url = "needs_stream_url"
    unsupported_rtsp_bridge_required = "unsupported_rtsp_bridge_required"
    unsupported_stream_type = "unsupported_stream_type"
    playback_error = "playback_error"
    unknown = "unknown"


class StreamPlaybackKind(str, Enum):
    placeholder = "placeholder"
    demo_panel = "demo_panel"
    external_url = "external_url"
    media_preview = "media_preview"
    mjpeg = "mjpeg"
    browser_video = "browser_video"
    hls = "hls"
    rtsp = "rtsp"
    local_usb = "local_usb"
    windows_dshow = "windows_dshow"
    unknown = "unknown"


class StreamMonitoringMode(str, Enum):
    off = "off"
    armed = "armed"
    paused = "paused"


class StreamRuntimeState(str, Enum):
    stopped = "stopped"
    starting = "starting"
    running = "running"
    backoff = "backoff"
    blocked = "blocked"
    stopping = "stopping"
    interrupted = "interrupted"


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


class LocalCameraFrameCaptureStatus(str, Enum):
    saved = "saved"
    unavailable = "unavailable"
    unsupported = "unsupported"
    ffmpeg_missing = "ffmpeg_missing"
    camera_not_configured = "camera_not_configured"
    capture_failed = "capture_failed"


class WindowsCameraDiscoveryStatus(str, Enum):
    available = "available"
    no_devices = "no_devices"
    ffmpeg_missing = "ffmpeg_missing"
    unsupported_platform = "unsupported_platform"
    failed = "failed"


class WindowsCameraControlsStatus(str, Enum):
    launched = "launched"
    monitor_running = "monitor_running"
    camera_running = "camera_running"
    camera_not_configured = "camera_not_configured"
    ffmpeg_missing = "ffmpeg_missing"
    unsupported_platform = "unsupported_platform"
    controls_unavailable = "controls_unavailable"
    launch_failed = "launch_failed"


class LiveMotionEvaluationStatus(str, Enum):
    evaluated = "evaluated"
    start_session_required = "start_session_required"
    waiting_for_live_frames = "waiting_for_live_frames"
    no_recent_frames = "no_recent_frames"
    not_enough_frames = "not_enough_frames"
    decode_failed = "decode_failed"
    activity_detected = "activity_detected"
    no_activity = "no_activity"


class ZoneType(str, Enum):
    feeder = "feeder"
    birdbath = "birdbath"
    ground = "ground"
    perch = "perch"
    yard = "yard"
    driveway = "driveway"
    privacy = "privacy"
    ignore = "ignore"


class ZoneActivitySensitivity(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class ReviewStatus(str, Enum):
    needs_review = "needs_review"
    reviewed = "reviewed"
    rejected = "rejected"


class VisitReviewOutcome(str, Enum):
    needs_review = "needs_review"
    confirmed_bird = "confirmed_bird"
    false_positive = "false_positive"
    blank = "blank"
    ambiguous = "ambiguous"
    non_bird = "non_bird"
    reviewed_other = "reviewed_other"
    rejected = "rejected"


class ReviewQueueBulkCorrectionTargetType(str, Enum):
    event = "event"
    visit = "visit"


class ReviewQueueBulkCorrectionResultStatus(str, Enum):
    succeeded = "succeeded"
    skipped = "skipped"
    failed = "failed"


class FastReviewNavigationDirection(str, Enum):
    next = "next"
    previous = "previous"


class ReviewIdentificationStatus(str, Enum):
    suggestion_present = "suggestion_present"
    proposal_present = "proposal_present"
    configured_available = "configured_available"
    ready = "ready"
    setup_required = "setup_required"
    unavailable_no_adapter = "unavailable_no_adapter"
    unavailable = "unavailable"
    unsupported_media = "unsupported_media"
    no_best_frame = "no_best_frame"
    running = "running"
    suggestion_created = "suggestion_created"
    proposal_created = "proposal_created"
    no_proposal = "no_proposal"
    failed = "failed"


class FocusCropSource(str, Enum):
    zone = "zone"
    activity = "activity"
    detector = "detector"
    manual = "manual"
    none = "none"


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


class ModelAdapterSetupStatus(str, Enum):
    available = "available"
    setup_required = "setup_required"
    unavailable = "unavailable"
    demo = "demo"


class MotionEvidenceStatus(str, Enum):
    pending = "pending"
    promoted = "promoted"
    ignored = "ignored"


class MotionEvidenceBulkAction(str, Enum):
    ignore = "ignore"
    promote = "promote"


class MotionEvidenceBulkActionResultStatus(str, Enum):
    succeeded = "succeeded"
    skipped = "skipped"
    failed = "failed"


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


class CameraSourceCreate(BaseModel):
    """Create one user-facing camera and its default Stream."""

    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Camera name cannot be empty.")
        return name


class CameraSourceUpdate(BaseModel):
    """Rename or archive one user-facing camera without changing its evidence."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    archived: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("Camera name cannot be empty.")
        return name

    @model_validator(mode="after")
    def require_change(self) -> "CameraSourceUpdate":
        if self.name is None and self.archived is None:
            raise ValueError("Provide a camera name or archive state.")
        return self


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


class WorkerStatusItem(BaseModel):
    # Worker status is future lifecycle visibility only; it must not create truth.
    worker_key: str
    display_name: str
    category: str
    state: str
    enabled: bool
    implemented: bool
    provider_key: str | None = None
    source_id: str | None = None
    stream_id: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_error: str | None = None
    message: str
    can_create_media_assets: bool = False
    can_create_motion_evidence: bool = False
    can_create_events: bool = False
    can_create_visits: bool = False
    can_create_review_labels: bool = False
    can_create_truth: bool = False
    warnings: list[str] = Field(default_factory=list)


class WorkerStatusSummary(BaseModel):
    total_workers: int = Field(ge=0)
    implemented_workers: int = Field(ge=0)
    enabled_workers: int = Field(ge=0)
    running_workers: int = Field(ge=0)
    failed_workers: int = Field(ge=0)
    truth_creating_workers: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class WorkerStatusResponse(BaseModel):
    workers: list[WorkerStatusItem]
    summary: WorkerStatusSummary
    generated_at: datetime
    read_only: bool = True


class ExternalUrlWorkerDryRunItem(BaseModel):
    source_id: str
    source_name: str
    provider_key: str
    worker_key: str
    eligible: bool
    state: str
    would_fetch: bool = False
    would_create_media_asset: bool = False
    would_create_motion_evidence: bool = False
    would_create_event: bool = False
    would_create_visit: bool = False
    would_create_review_label: bool = False
    would_create_truth: bool = False
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExternalUrlWorkerDryRunSummary(BaseModel):
    total_sources_considered: int = Field(ge=0)
    eligible_sources: int = Field(ge=0)
    ineligible_sources: int = Field(ge=0)
    would_fetch_count: int = Field(ge=0)
    would_create_media_asset_count: int = Field(ge=0)
    would_create_motion_evidence_count: int = Field(ge=0)
    would_create_truth_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ExternalUrlWorkerDryRunResponse(BaseModel):
    worker_key: str
    provider_key: str
    read_only: bool = True
    dry_run: bool = True
    generated_at: datetime
    items: list[ExternalUrlWorkerDryRunItem] = Field(default_factory=list)
    summary: ExternalUrlWorkerDryRunSummary


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


class WebhookMotionEvidenceRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    shared_secret_marker: str | None = None
    default_stream_id: str | None = None
    default_zone_id: str | None = None
    note: str | None = None
    reason: str | None = None
    duplicate_policy: str = "skip_existing"
    confirm: bool = False


class WebhookMotionEvidenceResponse(BaseModel):
    source_id: str
    provider_key: str
    motion_evidence_id: str | None = None
    status: str
    candidate_type: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    external_event_id: str | None = None
    duplicate_skipped: bool
    existing_motion_evidence_id: str | None = None
    creates_motion_evidence: bool
    creates_media_asset: bool = False
    creates_event: bool = False
    creates_visit: bool = False
    creates_review_label: bool = False
    creates_truth: bool = False
    message: str
    warnings: list[str] = Field(default_factory=list)


class Stream(BaseModel):
    id: str
    source_id: str
    name: str
    description: str
    is_live: bool


class StreamMonitoringPolicyResponse(BaseModel):
    # Desired state is durable configuration; it is never proof of active capture.
    stream_id: str
    source_id: str
    mode: StreamMonitoringMode
    auto_create_review_candidates: bool = False
    evaluation_interval_seconds: float = Field(ge=0.25, le=10)
    quiet_period_seconds: int = Field(ge=1, le=300)
    minimum_detection_count: int = Field(ge=1, le=100)
    policy_revision: int = Field(ge=1)
    armed_at: datetime | None = None
    paused_at: datetime | None = None
    updated_at: datetime | None = None
    pause_reason: str | None = None
    persisted: bool
    read_only: bool = False
    continuity_available: bool = True
    can_arm: bool = True
    creates_review_candidates: bool = False
    creates_review_truth: bool = False
    message: str
    warnings: list[str] = Field(default_factory=list)


class StreamRuntimeStatusResponse(BaseModel):
    # Runtime checkpoints are observability metadata, not proof or product truth.
    stream_id: str
    source_id: str
    desired_mode: StreamMonitoringMode
    actual_state: StreamRuntimeState
    observed_policy_revision: int = Field(ge=1)
    checkpoint_present: bool
    active_session_count: int = Field(default=0, ge=0)
    checkpoint_updated_at: datetime | None = None
    last_start_attempt_at: datetime | None = None
    last_healthy_frame_at: datetime | None = None
    last_clean_stop_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_code: str | None = None
    consecutive_failure_count: int = Field(ge=0)
    next_retry_at: datetime | None = None
    last_stop_reason: str | None = None
    safety_hold_active: bool = False
    read_only: bool = False
    continuity_available: bool = True
    camera_start_requested: bool = False
    monitor_start_requested: bool = False
    creates_review_candidates: bool = False
    creates_review_truth: bool = False
    message: str
    warnings: list[str] = Field(default_factory=list)


class StreamMonitoringPolicyUpdate(BaseModel):
    """An explicit, idempotent request to enable or disable one Stream."""

    enabled: bool
    idempotency_key: str = Field(min_length=8, max_length=120)


class StreamMonitoringRetryRequest(BaseModel):
    """An explicit, idempotent request to retry an enabled Stream now."""

    idempotency_key: str = Field(min_length=8, max_length=120)


class StreamMonitoringMutationResponse(BaseModel):
    policy: StreamMonitoringPolicyResponse
    runtime: StreamRuntimeStatusResponse
    idempotent: bool = False
    message: str
    creates_review_candidates: bool = False
    creates_review_truth: bool = False


class StreamMonitoringStatusListResponse(BaseModel):
    items: list[StreamRuntimeStatusResponse]
    limit: int = Field(ge=1, le=50)
    message: str
    creates_review_candidates: bool = False
    creates_review_truth: bool = False


class CameraSourceCreateResponse(BaseModel):
    # Source creation establishes product context only; setup and evidence stay explicit.
    source: CameraSource
    stream: Stream


class CameraSourceMutationResult(BaseModel):
    # Camera lifecycle changes preserve related Streams, Zones, evidence, and truth.
    source: CameraSource
    streams: list[Stream]


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
    live_stream_type: str | None = None
    live_stream_url_display: str | None = None
    rtsp_bridge_required: bool = False
    rtsp_bridge_available: bool = False
    rtsp_bridge_status: str | None = None
    local_camera_bridge_available: bool = False
    local_camera_status: str | None = None
    local_camera_device_display: str | None = None
    windows_camera_bridge_available: bool = False
    windows_camera_status: str | None = None
    windows_camera_name_display: str | None = None
    windows_ffmpeg_binary_display: str | None = None
    camera_settings: dict[str, str] = Field(default_factory=dict)
    bridged_mjpeg_url: str | None = None


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


class LocalCameraFrameCaptureResponse(BaseModel):
    # Captured frames are local MediaAssets only; correction remains truth.
    stream_id: str
    source_id: str | None = None
    media_asset_id: str | None = None
    status: LocalCameraFrameCaptureStatus
    message: str
    file_name: str | None = None
    relative_path: str | None = None
    bytes_written: int = Field(default=0, ge=0)
    content_type: str | None = None
    capture_source: str | None = None
    live_frame_age_ms: int | None = Field(default=None, ge=0)
    creates_truth: bool = False
    creates_event: bool = False
    creates_visit: bool = False
    creates_export: bool = False
    warnings: list[str] = Field(default_factory=list)


class WindowsCameraDiscoveryResponse(BaseModel):
    status: WindowsCameraDiscoveryStatus
    devices: list[str] = Field(default_factory=list)
    message: str
    creates_truth: bool = False


class WindowsCameraControlsResponse(BaseModel):
    # The DirectShow property page changes driver state only; it creates no product data.
    stream_id: str
    source_id: str | None = None
    status: WindowsCameraControlsStatus
    message: str
    creates_media: bool = False
    creates_evidence: bool = False
    creates_event: bool = False
    creates_visit: bool = False
    creates_truth: bool = False
    warnings: list[str] = Field(default_factory=list)


class LiveCameraSessionDiagnosticEventResponse(BaseModel):
    # Safe transition metadata only: never frame bytes, URLs, credentials, or model output.
    sequence: int = Field(ge=1)
    recorded_at: datetime
    event_type: str
    status: str | None = None
    reason: str | None = None
    activity_session_id: str | None = None
    frame_count: int = Field(default=0, ge=0)
    detection_count: int = Field(default=0, ge=0)
    near_miss_count: int = Field(default=0, ge=0)
    candidate_frame_count: int = Field(default=0, ge=0)
    quality_warning_codes: list[str] = Field(default_factory=list)
    creates_truth: bool = False


class LiveCameraSessionDiagnosticsResponse(BaseModel):
    stream_id: str
    diagnostic_events: list[LiveCameraSessionDiagnosticEventResponse] = Field(
        default_factory=list,
        max_length=100,
    )
    diagnostic_events_truncated: bool = False
    creates_truth: bool = False


class LiveCameraSessionStatusResponse(BaseModel):
    # Backend-owned live camera sessions are user-started and in-memory only.
    stream_id: str
    source_id: str | None = None
    playback_kind: str | None = None
    status: str
    started_at: datetime | None = None
    last_frame_at: datetime | None = None
    latest_frame_age_ms: int | None = Field(default=None, ge=0)
    newest_frame_age_ms: int | None = Field(default=None, ge=0)
    frame_count: int = Field(default=0, ge=0)
    clients_connected: int = Field(default=0, ge=0)
    monitor_running: bool = False
    auto_create_review_candidates: bool = False
    auto_review_quiet_seconds: int = Field(default=30, ge=1)
    auto_review_min_detections: int = Field(default=1, ge=1)
    auto_review_created_count: int = Field(default=0, ge=0)
    last_auto_review_created_at: datetime | None = None
    auto_review_last_error: str | None = None
    last_auto_review_motion_evidence_id: str | None = None
    last_auto_review_event_id: str | None = None
    last_auto_review_visit_id: str | None = None
    last_auto_review_queue_item_id: str | None = None
    last_motion_evaluation_at: datetime | None = None
    open_activity_session_count: int = Field(default=0, ge=0)
    open_activity_zone_names: list[str] = Field(default_factory=list)
    ready_activity_session_count: int = Field(default=0, ge=0)
    latest_activity_review_queue_item_id: str | None = None
    current_activity_session: dict[str, Any] | None = None
    current_activity_session_id: str | None = None
    activity_started_at: datetime | None = None
    activity_last_seen_at: datetime | None = None
    activity_detection_count: int = Field(default=0, ge=0)
    activity_near_miss_count: int = Field(default=0, ge=0)
    activity_frames_evaluated_count: int = Field(default=0, ge=0)
    activity_candidate_frame_count: int = Field(default=0, ge=0)
    activity_saved_candidate_count: int = Field(default=0, ge=0)
    activity_session_duration_seconds: float = Field(default=0.0, ge=0)
    activity_completed_at: datetime | None = None
    activity_ready_for_review: bool = False
    activity_manual_review_needed: bool = False
    activity_review_state: str | None = None
    activity_quiet_remaining_seconds: int | None = Field(default=None, ge=0)
    activity_best_frame_sequence: int | None = Field(default=None, ge=0)
    activity_best_score: float | None = None
    activity_best_changed_ratio: float | None = Field(default=None, ge=0)
    activity_best_changed_pixels: int | None = Field(default=None, ge=0)
    activity_best_total_scored_pixels: int | None = Field(default=None, ge=0)
    activity_effective_threshold_used: float | None = Field(default=None, ge=0)
    activity_threshold_source: str | None = None
    activity_fine_motion_applied: bool = False
    activity_near_miss: bool = False
    activity_cooldown_remaining_seconds: int | None = Field(default=None, ge=0)
    activity_review_activity_created: bool = False
    activity_motion_evidence_id: str | None = None
    activity_event_id: str | None = None
    activity_visit_id: str | None = None
    activity_review_queue_item_id: str | None = None
    notification_event: str | None = None
    last_activity: dict[str, Any] | None = None
    last_motion_result: dict[str, Any] | None = None
    last_error: str | None = None
    stop_reason: str | None = None
    max_runtime_seconds: int = Field(default=1800, ge=1)
    persistent: bool = False
    camera_settings: dict[str, Any] = Field(default_factory=dict)
    message: str
    warnings: list[str] = Field(default_factory=list)


class SourceMonitorStartRequest(BaseModel):
    interval_seconds: int = Field(default=15, ge=5)
    max_runtime_minutes: int = Field(default=30, ge=1, le=120)
    max_snapshots: int = Field(default=100, ge=1, le=500)
    check_motion: bool = True
    create_review_activity: bool = False


class SourceMonitorStatusResponse(BaseModel):
    # Monitor state is in-memory and evidence-only; correction remains truth.
    monitor_id: str
    source_id: str
    stream_id: str
    status: str
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_tick_at: datetime | None = None
    next_tick_at: datetime | None = None
    interval_seconds: int = Field(ge=1)
    max_runtime_seconds: int = Field(ge=1)
    max_snapshots: int = Field(ge=1)
    snapshots_attempted: int = Field(ge=0)
    snapshots_saved: int = Field(ge=0)
    motion_checks_run: int = Field(ge=0)
    last_snapshot_media_asset_id: str | None = None
    last_motion_media_asset_ids: list[str] = Field(default_factory=list)
    last_activity_detected: bool | None = None
    last_activity_area: dict[str, Any] | None = None
    last_session_status: str | None = None
    best_snapshot_media_asset_id: str | None = None
    crop_plan: MotionCropPlanResponse | None = None
    review_activity_available: bool = False
    review_activity_created: bool = False
    review_activity_unavailable_reason: str | None = None
    review_activity_motion_evidence_id: str | None = None
    review_activity_event_id: str | None = None
    review_activity_visit_id: str | None = None
    last_error: str | None = None
    consecutive_failures: int = Field(ge=0)
    stop_reason: str | None = None
    check_motion: bool = True
    create_review_activity: bool = False
    creates_truth: bool = False
    creates_exports: bool = False
    persistent: bool = False
    message: str


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


class SavedMediaBulkMotionEvidenceRequest(BaseModel):
    media_asset_ids: list[str]


class SavedMediaBulkMotionEvidenceResult(BaseModel):
    media_asset_id: str
    status: MotionEvidenceBulkActionResultStatus
    message: str
    created_motion_evidence_id: str | None = None


class SavedMediaBulkMotionEvidenceResponse(BaseModel):
    # Bulk saved-media handoff still creates pending evidence only.
    requested_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: list[SavedMediaBulkMotionEvidenceResult]


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


class PixelBoundingBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Zone(BaseModel):
    # Privacy and ignore zones are product concepts, not adapter settings.
    id: str
    stream_id: str
    name: str
    zone_type: ZoneType
    polygon: list[Point]
    is_active: bool
    monitoring_policy: ZoneMonitoringPolicy | None = None


class ZoneMonitoringPolicy(BaseModel):
    """Effective product settings for future activity sessions in one Zone."""

    monitoring_enabled: bool
    activity_sensitivity: ZoneActivitySensitivity
    minimum_sustained_activity_seconds: int = Field(ge=0, le=60)
    quiet_period_seconds: int = Field(ge=5, le=300)
    maximum_visit_duration_seconds: int = Field(ge=30, le=900)
    maximum_evidence_frames: int = Field(ge=1, le=4)
    customized_fields: list[str] = Field(default_factory=list)
    inherited_fields: list[str] = Field(default_factory=list)
    uses_recommended_defaults: bool = True


class ZoneMonitoringPolicyUpdate(BaseModel):
    """Explicit overrides only; omitted values keep the Zone-type recommendation."""

    model_config = ConfigDict(extra="forbid")

    monitoring_enabled: bool | None = None
    activity_sensitivity: ZoneActivitySensitivity | None = None
    minimum_sustained_activity_seconds: int | None = Field(default=None, ge=0, le=60)
    quiet_period_seconds: int | None = Field(default=None, ge=5, le=300)
    maximum_visit_duration_seconds: int | None = Field(default=None, ge=30, le=900)
    maximum_evidence_frames: int | None = Field(default=None, ge=1, le=4)

    @model_validator(mode="after")
    def require_change(self) -> "ZoneMonitoringPolicyUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("Provide at least one monitoring setting to update.")
        return self


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
    zone_id: str | None = None
    is_superseded: bool = False


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


class VisitEvidenceFrame(BaseModel):
    # Bounded, observational media for one Visit. Never expose its local path.
    media_asset_id: str
    preview_url: str
    captured_at: datetime
    relative_position: float = Field(ge=0, le=1)
    frame_sequence: int | None = Field(default=None, ge=0)
    is_primary: bool
    content_type: str
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class VisitCurationHistoryEntry(BaseModel):
    """Plain-language structural history; API IDs are navigation data, never copy."""

    action: str
    message: str
    created_at: datetime


class VisitCurationSequencePreview(BaseModel):
    evidence_frames: list[VisitEvidenceFrame] = Field(default_factory=list)
    activity_started_at: datetime | None = None
    activity_ended_at: datetime | None = None
    evidence_count: int = Field(ge=0)


class VisitEvidenceCurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retained_media_asset_ids: list[str] = Field(min_length=1, max_length=4)
    primary_media_asset_id: str = Field(min_length=1, max_length=256)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitEvidenceCurationResponse(BaseModel):
    visit: Visit
    evidence_frames: list[VisitEvidenceFrame] = Field(default_factory=list)
    review_state_token: str
    idempotent: bool = False
    message: str


class VisitSplitPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boundary_after_media_asset_id: str = Field(min_length=1, max_length=256)
    expected_state_token: str = Field(min_length=1, max_length=256)


class VisitSplitPreview(BaseModel):
    first: VisitCurationSequencePreview
    second: VisitCurationSequencePreview
    review_implication: str
    state_token: str


class VisitSplitRequest(VisitSplitPreviewRequest):
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitSplitResponse(BaseModel):
    source_visit: Visit
    resulting_visits: list[Visit] = Field(min_length=2, max_length=2)
    review_state_token: str
    idempotent: bool = False
    message: str


class VisitMergeCandidate(BaseModel):
    visit: "StreamVisitSummary"
    gap_seconds: float = Field(ge=0)


class VisitMergeCandidatesResponse(BaseModel):
    candidates: list[VisitMergeCandidate] = Field(default_factory=list)
    maximum_gap_seconds: int = Field(ge=1)


class VisitMergePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_visit_ids: list[str] = Field(min_length=1, max_length=9)
    expected_state_token: str = Field(min_length=1, max_length=256)


class VisitMergePreview(BaseModel):
    source_visits: list[Visit] = Field(min_length=2, max_length=10)
    combined: VisitCurationSequencePreview
    review_implication: str
    state_token: str


class VisitMergeRequest(VisitMergePreviewRequest):
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitMergeResponse(BaseModel):
    visit: Visit
    source_visits: list[Visit] = Field(min_length=2, max_length=10)
    review_state_token: str
    idempotent: bool = False
    message: str


class VisitZoneReassignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(min_length=1, max_length=256)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitZoneReassignmentResponse(BaseModel):
    visit: Visit
    review_state_token: str
    idempotent: bool = False
    message: str


class StreamVisitSummary(BaseModel):
    # Compact, Stream-scoped history. Full evidence is loaded only on inspection.
    id: str
    event_id: str
    stream_id: str
    captured_at: datetime
    activity_started_at: datetime
    activity_ended_at: datetime | None = None
    duration_seconds: float = Field(ge=0)
    zone_id: str | None = None
    zone_name: str | None = None
    zone_type: ZoneType | None = None
    review_status: ReviewStatus
    reviewed_label: str | None = None
    review_outcome: VisitReviewOutcome
    suggested_label: str | None = None
    has_suggestion: bool = False
    evidence_frame_count: int = Field(ge=0)
    primary_evidence: VisitEvidenceFrame | None = None


class ActivityLibraryReviewFilter(str, Enum):
    all = "all"
    needs_review = "needs_review"
    reviewed_observation = "reviewed_observation"
    non_bird = "non_bird"
    blank_false = "blank_false"
    ambiguous_unknown = "ambiguous_unknown"


class ActivityLibraryFilters(BaseModel):
    """Strict, local-only filters for a bounded cross-Stream Visit search."""

    model_config = ConfigDict(extra="forbid")

    review_filter: ActivityLibraryReviewFilter = ActivityLibraryReviewFilter.all
    stream_id: str | None = Field(default=None, min_length=1, max_length=256)
    source_id: str | None = Field(default=None, min_length=1, max_length=256)
    zone_id: str | None = Field(default=None, min_length=1, max_length=256)
    confirmed_label: str | None = Field(default=None, min_length=1, max_length=256)
    has_suggestion: bool | None = None
    search: str | None = Field(default=None, max_length=256)
    start_at: datetime | None = None
    end_at: datetime | None = None
    include_superseded: bool = False

    @model_validator(mode="after")
    def validate_date_range(self) -> "ActivityLibraryFilters":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("end_at must be on or after start_at")
        return self


class ActivityLibrarySearchRequest(ActivityLibraryFilters):
    page_size: int = Field(default=24, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=10_000)


class ActivityLibrarySavedView(BaseModel):
    id: str
    name: str
    filters: ActivityLibraryFilters
    created_at: datetime
    updated_at: datetime


class ActivityLibrarySavedViewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    filters: ActivityLibraryFilters


class ActivityLibrarySavedViewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    filters: ActivityLibraryFilters | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ActivityLibrarySavedViewUpdate":
        if self.name is None and self.filters is None:
            raise ValueError("Provide a name or filters to update this saved view")
        return self


class DashboardStreamRuntimeStatus(BaseModel):
    """Read-only runtime facts collected without starting a camera or monitor."""

    monitoring_active: bool = False
    monitor_control: str = "none"
    can_start_monitor: bool = False
    can_stop_monitor: bool = False
    open_activity_session_count: int = Field(default=0, ge=0)
    ready_activity_session_count: int = Field(default=0, ge=0)


class DashboardVisitSummary(StreamVisitSummary):
    # Product context for a compact cross-Stream Visit row; evidence stays bounded.
    stream_name: str
    source_id: str
    source_name: str


class DashboardStreamSummary(BaseModel):
    stream_id: str
    stream_name: str
    source_id: str
    source_name: str
    availability_status: StreamPlaybackStatusValue
    availability_message: str
    monitoring_active: bool = False
    monitor_control: str = "none"
    can_start_monitor: bool = False
    can_stop_monitor: bool = False
    open_activity_session_count: int = Field(default=0, ge=0)
    ready_activity_session_count: int = Field(default=0, ge=0)
    needs_review_visit_count: int = Field(default=0, ge=0)
    latest_visit: DashboardVisitSummary | None = None


class DashboardReviewedObservation(BaseModel):
    # One reviewed label grouping; suggestions never reach this serializer.
    label: str
    display_name: str
    category: LabelCategory
    observation_count: int = Field(ge=1)
    latest_visit: DashboardVisitSummary


class DashboardHeadline(BaseModel):
    configured_stream_count: int = Field(ge=0)
    monitored_stream_count: int = Field(ge=0)
    open_activity_session_count: int = Field(ge=0)
    needs_review_visit_count: int = Field(ge=0)
    reviewed_observation_count_today: int = Field(ge=0)


class DashboardSummary(BaseModel):
    # Bounded daily operations surface; never a full Visit-detail payload.
    local_day: str
    generated_at: datetime
    headline: DashboardHeadline
    streams: list[DashboardStreamSummary] = Field(default_factory=list, max_length=50)
    needs_review_visits: list[DashboardVisitSummary] = Field(
        default_factory=list,
        max_length=12,
    )
    today_observations: list[DashboardReviewedObservation] = Field(
        default_factory=list,
        max_length=12,
    )
    reviewed_non_bird_activity: list[DashboardReviewedObservation] = Field(
        default_factory=list,
        max_length=8,
    )
    recent_activity: list[DashboardVisitSummary] = Field(default_factory=list, max_length=25)
    warnings: list[str] = Field(default_factory=list, max_length=12)


class ActivityLibraryVisitSummary(DashboardVisitSummary):
    # Structural curation is provenance context, never a second review truth.
    curation_actions: list[str] = Field(default_factory=list, max_length=8)


class ActivityLibrarySearchResponse(BaseModel):
    visits: list[ActivityLibraryVisitSummary] = Field(default_factory=list, max_length=50)
    has_more: bool
    next_offset: int | None = Field(default=None, ge=0)


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


class ModelAdapterSetupSummary(BaseModel):
    # Adapter setup visibility is safe metadata only; it never validates secrets or runs models.
    adapter_id: str
    adapter_name: str
    adapter_kind: ModelAdapterKind
    status: ModelAdapterSetupStatus
    local_only: bool = True
    is_demo: bool = False
    supported_media_types: list[str]
    required_env_var: str | None = None
    model_path_hint: str | None = None
    setup_hint: str | None = None
    can_run: bool = False
    can_run_on_review_best_frame: bool = False
    creates_truth: bool = False


class ModelAdapter(BaseModel):
    # Model adapters produce proposal or suggestion evidence; review labels remain truth.
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
    adapter_setup: list[ModelAdapterSetupSummary] = Field(default_factory=list)
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


MotionEvidenceFrameConfigValue = str | int | float | bool | None
MotionScoringConfigValue = (
    str
    | int
    | float
    | bool
    | list[str]
    | list[dict[str, MotionEvidenceFrameConfigValue]]
    | None
)


class MotionEvidenceCreateRequest(BaseModel):
    source_id: str | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    start_frame_index: int | None = None
    end_frame_index: int | None = None
    best_frame_index: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    best_frame_time: str | None = None
    peak_changed_ratio: float = Field(ge=0, le=1)
    triggered_frame_count: int = Field(ge=1)
    scoring_config: dict[str, MotionScoringConfigValue] = Field(default_factory=dict)
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
    zone_id: str | None
    start_frame_index: int | None
    end_frame_index: int | None
    best_frame_index: int | None
    start_time: str | None
    end_time: str | None
    best_frame_time: str | None
    peak_changed_ratio: float
    triggered_frame_count: int
    scoring_config: dict[str, MotionScoringConfigValue]
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


class SavedMediaFrameSummary(BaseModel):
    media_asset_id: str
    created_at: datetime
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class MotionEvaluateSavedMediaRequest(BaseModel):
    stream_id: str
    media_asset_ids: list[str]
    zone_ids: list[str] | None = None
    create_motion_evidence: bool = False
    attach_best_snapshot: bool = True
    frame_index_start: int = Field(default=0, ge=0)
    pixel_delta_threshold: float = Field(default=25.0, ge=0)
    min_changed_ratio: float = Field(default=0.02, ge=0, le=1)
    min_triggered_frames: int = Field(default=2, ge=1)
    max_gap_frames: int = Field(default=1, ge=0)
    notes: str | None = None


class MotionActivityAreaResponse(BaseModel):
    area_id: str
    label: str
    source: str
    left: float
    top: float
    right: float
    bottom: float
    zone_id: str | None = None
    cell_ids: list[str] = Field(default_factory=list)


class MotionSuppressedZoneSummaryResponse(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: ZoneType
    reason: str
    triggered_frame_count: int = Field(ge=0)
    peak_changed_ratio: float = 0.0


class MotionCropBoxNormalizedResponse(BaseModel):
    left: float
    top: float
    right: float
    bottom: float


class MotionCropBoxPixelsResponse(BaseModel):
    left: int = Field(ge=0)
    top: int = Field(ge=0)
    right: int = Field(ge=1)
    bottom: int = Field(ge=1)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class MotionCropPlanResponse(BaseModel):
    source_media_asset_id: str | None = None
    crop_box_normalized: MotionCropBoxNormalizedResponse
    crop_box_pixels: MotionCropBoxPixelsResponse
    crop_reason: str
    padding_ratio: float = Field(ge=0)
    is_full_frame_fallback: bool = False
    derived_crop_media_asset_id: str | None = None
    warning: str | None = None


class MotionEvaluateSavedMediaResponse(BaseModel):
    # Saved snapshots can create pending evidence only; review correction remains truth.
    stream_id: str
    source_id: str
    media_asset_ids: list[str]
    zones: list[MotionZoneInput]
    activity_areas: list[MotionActivityAreaResponse] = Field(default_factory=list)
    region_source: str
    uses_auto_regions: bool = False
    strongest_zone_name: str | None = None
    strongest_zone_type: ZoneType | None = None
    strongest_activity_area_id: str | None = None
    strongest_activity_area_label: str | None = None
    suppressed_zone_summaries: list[MotionSuppressedZoneSummaryResponse] = Field(
        default_factory=list
    )
    suppressed_auto_region_count: int = Field(default=0, ge=0)
    activity_summary: str | None = None
    can_create_review_activity: bool = True
    review_activity_created: bool = False
    creation_skipped_reason: str | None = None
    session_key: str | None = None
    session_status: str = "no_activity"
    should_create_review_activity: bool = False
    session_message: str | None = None
    existing_activity_reference: str | None = None
    best_snapshot_media_asset_id: str | None = None
    best_snapshot_reason: str | None = None
    crop_plan: MotionCropPlanResponse | None = None
    quiet_period_seconds: int = Field(default=30, ge=1)
    cooldown_seconds: int = Field(default=30, ge=0)
    max_snapshots_per_session: int = Field(default=3, ge=1)
    session_debug: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    debug_cell_zones: list[MotionZoneInput] = Field(default_factory=list)
    frames: list[SavedMediaFrameSummary]
    frame_scores: list[MotionFrameScoreResponse]
    candidates: list[MotionCandidateResponse]
    created_evidence: list[MotionEvidenceResponse]
    activity_detected: bool
    strongest_zone_id: str | None = None
    strongest_changed_ratio: float = 0.0
    best_media_asset_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    local_first_note: str


class LiveMotionEvaluateRequest(BaseModel):
    save_best_frame: bool = True
    create_review_activity: bool = False
    bird_sized_feeder_motion: bool = True
    pixel_delta_threshold: float = Field(default=25.0, ge=0)
    min_changed_ratio: float = Field(default=0.02, ge=0, le=1)
    min_triggered_frames: int = Field(default=1, ge=1)
    max_gap_frames: int = Field(default=1, ge=0)
    max_age_seconds: float = Field(default=20.0, ge=1, le=60)
    max_frames: int = Field(default=20, ge=2, le=30)
    focus_zone_id: str | None = None
    notes: str | None = None


class LiveMotionMonitorStartRequest(LiveMotionEvaluateRequest):
    interval_seconds: float = Field(default=1.5, ge=0.25, le=10)
    auto_create_review_candidates: bool = False
    auto_review_quiet_seconds: int = Field(default=30, ge=1, le=300)
    auto_review_min_detections: int = Field(default=1, ge=1, le=100)


class LiveMotionMonitorSettingsRequest(BaseModel):
    auto_create_review_candidates: bool = False
    auto_review_quiet_seconds: int = Field(default=30, ge=1, le=300)
    auto_review_min_detections: int = Field(default=1, ge=1, le=100)


class LiveMotionReviewActivityResponse(BaseModel):
    stream_id: str
    source_id: str | None = None
    status: str
    activity_detected: bool = False
    review_activity_created: bool = False
    review_activity_reused: bool = False
    review_activity_already_exists: bool = False
    already_exists: bool = False
    activity_session_id: str | None = None
    activity_detection_count: int = Field(default=0, ge=0)
    activity_started_at: datetime | None = None
    activity_last_seen_at: datetime | None = None
    motion_evidence_id: str | None = None
    event_id: str | None = None
    visit_id: str | None = None
    media_asset_id: str | None = None
    review_queue_item_id: str | None = None
    suggested_label: str | None = None
    suggestion_id: str | None = None
    suggestion_confidence: float | None = None
    review_status: ReviewStatus | None = None
    creates_event: bool = False
    creates_visit: bool = False
    creates_truth: bool = False
    creates_export: bool = False
    message: str
    warnings: list[str] = Field(default_factory=list)


class LiveMotionFrameSummary(BaseModel):
    sequence: int = Field(ge=1)
    captured_at: datetime
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class LiveMotionEvaluateResponse(BaseModel):
    # Live motion uses the active stream cache only; review correction remains truth.
    stream_id: str
    source_id: str
    status: LiveMotionEvaluationStatus
    evaluated_at: datetime
    activity_detected: bool
    frames_available: int = Field(ge=0)
    frames_considered: int = Field(ge=0)
    recent_frame_count: int = Field(ge=0)
    newest_frame_age_ms: int | None = None
    oldest_frame_age_ms: int | None = None
    newest_frame_sequence: int | None = None
    buffer_capacity: int = Field(default=20, ge=1)
    fresh_enough: bool = False
    last_frame_at: datetime | None = None
    camera_session_status: str | None = None
    camera_session_frame_count: int = Field(default=0, ge=0)
    camera_session_clients_connected: int = Field(default=0, ge=0)
    camera_session_latest_frame_age_ms: int | None = Field(default=None, ge=0)
    camera_session_runtime_limit_seconds: int | None = Field(default=None, ge=1)
    frames: list[LiveMotionFrameSummary] = Field(default_factory=list)
    frame_scores: list[MotionFrameScoreResponse] = Field(default_factory=list)
    candidates: list[MotionCandidateResponse] = Field(default_factory=list)
    activity_areas: list[MotionActivityAreaResponse] = Field(default_factory=list)
    region_source: str = "user_zones"
    uses_auto_regions: bool = False
    strongest_zone_id: str | None = None
    strongest_zone_name: str | None = None
    strongest_zone_type: ZoneType | None = None
    strongest_activity_area: MotionActivityAreaResponse | None = None
    strongest_activity_area_id: str | None = None
    strongest_activity_area_label: str | None = None
    suppressed_zone_summaries: list[MotionSuppressedZoneSummaryResponse] = Field(
        default_factory=list
    )
    activity_summary: str | None = None
    strongest_changed_ratio: float = 0.0
    pixel_delta_threshold: float | None = None
    min_changed_ratio: float | None = None
    strongest_zone_min_changed_ratio: float | None = None
    requested_threshold: float | None = None
    effective_threshold_used: float | None = None
    threshold_used: float | None = None
    threshold_source: str | None = None
    fine_motion_applied: bool = False
    bird_sized_feeder_motion: bool = True
    changed_pixels: int | None = Field(default=None, ge=0)
    total_pixels: int | None = Field(default=None, ge=0)
    total_scored_pixels: int | None = Field(default=None, ge=0)
    mean_delta: float | None = None
    margin_to_threshold: float | None = None
    near_miss: bool = False
    frame_pair_sequences: list[int] = Field(default_factory=list)
    feeder_threshold_applied: bool = False
    focus_zone_id: str | None = None
    focus_zone_name: str | None = None
    focus_zone_type: ZoneType | None = None
    focus_applied: bool = False
    evaluation_cadence_seconds: float | None = None
    image_quality_warnings: list[str] = Field(default_factory=list)
    strongest_frame_start_sequence: int | None = None
    strongest_frame_end_sequence: int | None = None
    best_frame_sequence: int | None = None
    best_frame_captured_at: datetime | None = None
    best_media_asset_id: str | None = None
    media_asset_id: str | None = None
    activity_session_id: str | None = None
    activity_started_at: datetime | None = None
    activity_last_seen_at: datetime | None = None
    activity_detection_count: int = Field(default=0, ge=0)
    activity_near_miss_count: int = Field(default=0, ge=0)
    activity_frames_evaluated_count: int = Field(default=0, ge=0)
    activity_candidate_frame_count: int = Field(default=0, ge=0)
    activity_saved_candidate_count: int = Field(default=0, ge=0)
    activity_session_duration_seconds: float = Field(default=0.0, ge=0)
    activity_completed_at: datetime | None = None
    activity_ready_for_review: bool = False
    activity_review_state: str | None = None
    activity_quiet_remaining_seconds: int | None = Field(default=None, ge=0)
    activity_manual_review_needed: bool = False
    activity_best_frame_sequence: int | None = Field(default=None, ge=0)
    activity_best_score: float | None = None
    activity_best_changed_ratio: float | None = Field(default=None, ge=0)
    activity_best_changed_pixels: int | None = Field(default=None, ge=0)
    activity_best_total_scored_pixels: int | None = Field(default=None, ge=0)
    activity_effective_threshold_used: float | None = Field(default=None, ge=0)
    activity_threshold_source: str | None = None
    activity_fine_motion_applied: bool = False
    activity_near_miss: bool = False
    can_create_review_activity: bool = False
    review_activity_available: bool = False
    review_activity_created: bool = False
    review_activity_reused: bool = False
    review_activity_already_exists: bool = False
    existing_review_activity_reference: str | None = None
    session_status: str = "watching"
    cooldown_remaining_seconds: int | None = None
    auto_create_review_candidates: bool = False
    auto_review_quiet_seconds: int = Field(default=30, ge=1)
    auto_review_min_detections: int = Field(default=1, ge=1)
    auto_review_created_count: int = Field(default=0, ge=0)
    last_auto_review_created_at: datetime | None = None
    auto_review_last_error: str | None = None
    last_auto_review_motion_evidence_id: str | None = None
    last_auto_review_event_id: str | None = None
    last_auto_review_visit_id: str | None = None
    last_auto_review_queue_item_id: str | None = None
    notification_event: str | None = None
    last_evaluation_message: str | None = None
    last_error: str | None = None
    motion_evidence_id: str | None = None
    event_id: str | None = None
    visit_id: str | None = None
    review_queue_item_id: str | None = None
    review_status: ReviewStatus | None = None
    suggested_label: str | None = None
    suggestion_id: str | None = None
    suggestion_confidence: float | None = Field(default=None, ge=0, le=1)
    suggestion_reason: str | None = None
    suggestion_creates_truth: bool = False
    created_evidence: list[MotionEvidenceResponse] = Field(default_factory=list)
    debug_cell_zones: list[MotionZoneInput] = Field(default_factory=list)
    creates_event: bool = False
    creates_visit: bool = False
    creates_truth: bool = False
    creates_export: bool = False
    message: str
    warnings: list[str] = Field(default_factory=list)
    local_first_note: str


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


class MotionEvidenceBulkActionRequest(BaseModel):
    motion_evidence_ids: list[str] = Field(min_length=1)
    action: MotionEvidenceBulkAction


class MotionEvidenceBulkActionResult(BaseModel):
    motion_evidence_id: str
    status: MotionEvidenceBulkActionResultStatus
    message: str
    created_event_id: str | None = None
    created_visit_id: str | None = None


class MotionEvidenceBulkActionResponse(BaseModel):
    action: MotionEvidenceBulkAction
    requested_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: list[MotionEvidenceBulkActionResult]


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


class ReviewIdentificationSummary(BaseModel):
    # Identification assist is evidence context only; ReviewLabel correction remains truth.
    status: ReviewIdentificationStatus
    message: str
    media_asset_id: str | None = None
    adapter_id: str | None = None
    adapter_name: str | None = None
    adapter_kind: ModelAdapterKind | None = None
    adapter_status: ModelAdapterStatus | None = None
    adapter_is_demo: bool = False
    setup_status: ModelAdapterSetupStatus | None = None
    local_only: bool = True
    supported_media_types: list[str] = Field(default_factory=list)
    can_run: bool = False
    can_run_on_best_frame: bool = False
    required_env_var: str | None = None
    model_path_hint: str | None = None
    setup_hint: str | None = None
    unavailable_reason: str | None = None
    suggestion: SpeciesSuggestionResponse | None = None
    proposal: DetectionProposal | None = None
    suggestion_count: int = Field(default=0, ge=0)
    proposal_count: int = Field(default=0, ge=0)
    created_suggestion_ids: list[str] = Field(default_factory=list)
    created_proposal_ids: list[str] = Field(default_factory=list)
    focus_crop_available: bool = False
    focus_crop_source: FocusCropSource = FocusCropSource.none
    focus_crop_box_normalized: BoundingBox | None = None
    focus_crop_box_pixels: PixelBoundingBox | None = None
    focus_crop_label: str | None = None
    focus_crop_warnings: list[str] = Field(default_factory=list)
    creates_truth: bool = False
    creates_export: bool = False


class ReviewIdentificationRequest(BaseModel):
    adapter_id: str | None = None
    media_asset_id: str | None = None
    requested_labels: list[str] | None = None
    notes: str | None = None


class DemoDetectionRunResult(BaseModel):
    detection_run: DetectionRun
    proposals: list[DetectionProposal]
    review_queue_count: int


class ReviewQueueItem(BaseModel):
    id: str
    item_type: str
    target_type: str
    target_id: str
    title: str
    stream_id: str
    stream_name: str | None = None
    source_id: str | None = None
    source_name: str | None = None
    event_id: str | None = None
    visit_id: str | None = None
    primary_zone_id: str | None = None
    primary_zone_name: str | None = None
    primary_zone_type: ZoneType | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    zone_type: ZoneType | None = None
    best_media_asset_id: str | None = None
    activity_session_id: str | None = None
    activity_started_at: datetime | None = None
    activity_last_seen_at: datetime | None = None
    detection_count: int = Field(default=0, ge=0)
    near_miss_count: int = Field(default=0, ge=0)
    frames_evaluated_count: int = Field(default=0, ge=0)
    candidate_frame_count: int = Field(default=0, ge=0)
    saved_candidate_count: int = Field(default=0, ge=0)
    best_frame_sequence: int | None = Field(default=None, ge=0)
    best_changed_ratio: float | None = Field(default=None, ge=0)
    best_changed_pixels: int | None = Field(default=None, ge=0)
    best_total_scored_pixels: int | None = Field(default=None, ge=0)
    effective_threshold_used: float | None = Field(default=None, ge=0)
    threshold_source: str | None = None
    fine_motion_applied: bool = False
    image_quality_warnings: list[str] = Field(default_factory=list)
    suggested_label: str | None = None
    suggestion_id: str | None = None
    suggestion_confidence: float | None = Field(default=None, ge=0, le=1)
    suggestion_reason: str | None = None
    suggestion_creates_truth: bool = False
    focus_crop_available: bool = False
    focus_crop_source: FocusCropSource = FocusCropSource.none
    focus_crop_box_normalized: BoundingBox | None = None
    focus_crop_box_pixels: PixelBoundingBox | None = None
    focus_crop_label: str | None = None
    focus_crop_warnings: list[str] = Field(default_factory=list)
    identification: ReviewIdentificationSummary | None = None
    media_asset: MediaAsset | None = None
    evidence_frames: list[VisitEvidenceFrame] = Field(default_factory=list)
    review_status: ReviewStatus
    review_state_token: str = ""
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


class VisitReviewRevisionCreate(BaseModel):
    """Replace the current reviewed Visit truth without changing its history."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=256)
    notes: str | None = Field(default=None, max_length=4000)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitReviewReopenCreate(BaseModel):
    """Deliberately remove current reviewed truth and return the Visit to review."""

    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=4000)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class FastReviewQueueTarget(BaseModel):
    target_type: ReviewQueueBulkCorrectionTargetType
    target_id: str = Field(min_length=1, max_length=256)


class FastReviewQueueNavigationRequest(BaseModel):
    """A bounded client-filtered queue snapshot for one navigation decision."""

    model_config = ConfigDict(extra="forbid")

    ordered_targets: list[FastReviewQueueTarget] = Field(min_length=1, max_length=200)
    current_target: FastReviewQueueTarget | None = None
    direction: FastReviewNavigationDirection = FastReviewNavigationDirection.next
    stream_id: str | None = Field(default=None, max_length=256)


class FastReviewQueueNavigationResponse(BaseModel):
    item: ReviewQueueItem | None = None
    position: int | None = Field(default=None, ge=1)
    unresolved_count: int = Field(ge=0)
    message: str


class FastReviewCorrectionCreate(BaseModel):
    """An explicit, conflict-aware request that still writes a normal ReviewLabel."""

    model_config = ConfigDict(extra="forbid")

    target_type: ReviewQueueBulkCorrectionTargetType
    target_id: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=256)
    notes: str | None = Field(default=None, max_length=4000)
    review_session_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    expected_state_token: str = Field(min_length=1, max_length=256)


class ReviewQueueBulkCorrectionRequest(BaseModel):
    target_ids: list[str]
    target_type: ReviewQueueBulkCorrectionTargetType
    label: str
    notes: str | None = None


class ReviewQueueBulkCorrectionResult(BaseModel):
    target_id: str
    status: ReviewQueueBulkCorrectionResultStatus
    message: str
    created_review_label_id: str | None = None


class ReviewQueueBulkCorrectionResponse(BaseModel):
    # Bulk correction writes user-selected ReviewLabel truth only.
    requested_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: list[ReviewQueueBulkCorrectionResult]


class ReviewIdentificationResponse(BaseModel):
    # Running assist may create proposal or suggestion evidence, never truth or exports.
    target_type: ReviewQueueBulkCorrectionTargetType
    target_id: str
    identification: ReviewIdentificationSummary
    detection_run: DetectionRun | None = None
    proposals: list[DetectionProposal] = Field(default_factory=list)
    species_suggestion: SpeciesSuggestionResponse | None = None
    review_queue_item: ReviewQueueItem | None = None
    created_suggestion_ids: list[str] = Field(default_factory=list)
    created_proposal_ids: list[str] = Field(default_factory=list)
    creates_truth: bool = False
    creates_export: bool = False
    creates_review_label: bool = False
    warnings: list[str] = Field(default_factory=list)


class DatasetExport(BaseModel):
    id: str
    name: str
    status: ExportStatus
    reviewed_only: bool
    include_detections: bool = True
    include_zone_context: bool = True
    record_count: int = Field(ge=0)
    created_at: datetime
    selected_visit_ids: list[str] | None = Field(default=None, max_length=50)


class DatasetExportCreate(BaseModel):
    name: str
    reviewed_only: bool = True
    include_detections: bool = True
    include_zone_context: bool = True
    selected_visit_ids: list[str] | None = Field(default=None, max_length=50)

    @field_validator("selected_visit_ids")
    @classmethod
    def validate_selected_visit_ids(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = [value.strip() for value in values]
        if not all(normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("selected_visit_ids must be unique non-empty Visit IDs")
        return normalized


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


class ActivityLibraryExportSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    visit_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("visit_ids")
    @classmethod
    def validate_visit_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if not all(normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("visit_ids must be unique non-empty Visit IDs")
        return normalized


class ActivityLibraryExportExclusion(BaseModel):
    visit_id: str
    reason: str


class ActivityLibraryExportSelectionResponse(BaseModel):
    export: DatasetExportDetail | None = None
    included_visit_ids: list[str] = Field(default_factory=list, max_length=50)
    excluded: list[ActivityLibraryExportExclusion] = Field(default_factory=list, max_length=50)


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
    database_schema_version: int = Field(ge=1)
    database_schema_current_version: int = Field(ge=1)
    database_integrity_check: str
    seed_data_present: bool
    local_first_note: str


class StorageRetentionFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"


class StorageRetentionSettings(BaseModel):
    automatic_cleanup_enabled: bool = False
    cleanup_frequency: StorageRetentionFrequency = StorageRetentionFrequency.weekly
    retain_unresolved_visit_evidence: bool = True
    retain_reviewed_bird_wildlife_evidence: bool = True
    reviewed_non_bird_age_days: int = Field(default=180, ge=30, le=3650)
    superseded_evidence_age_days: int = Field(default=90, ge=14, le=3650)
    orphaned_media_age_days: int = Field(default=30, ge=7, le=3650)
    maximum_managed_media_bytes: int | None = Field(default=None, ge=1_048_576)
    policy_revision: int = Field(ge=1)
    persisted: bool
    recommended_defaults: bool
    updated_at: datetime | None = None
    last_automatic_run_at: datetime | None = None
    last_automatic_result: str | None = None
    message: str


class StorageRetentionSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    automatic_cleanup_enabled: bool
    cleanup_frequency: StorageRetentionFrequency
    retain_unresolved_visit_evidence: bool
    retain_reviewed_bird_wildlife_evidence: bool
    reviewed_non_bird_age_days: int = Field(ge=30, le=3650)
    superseded_evidence_age_days: int = Field(ge=14, le=3650)
    orphaned_media_age_days: int = Field(ge=7, le=3650)
    maximum_managed_media_bytes: int | None = Field(default=None, ge=1_048_576)
    idempotency_key: str = Field(min_length=8, max_length=120)


class StorageSummary(BaseModel):
    total_managed_media_bytes: int = Field(ge=0)
    total_managed_media_count: int = Field(ge=0)
    oldest_managed_media_at: datetime | None = None
    newest_managed_media_at: datetime | None = None
    approximate_database_bytes: int | None = Field(default=None, ge=0)
    active_visit_media_count: int = Field(ge=0)
    active_visit_media_bytes: int = Field(ge=0)
    superseded_only_media_count: int = Field(ge=0)
    superseded_only_media_bytes: int = Field(ge=0)
    orphaned_managed_media_count: int = Field(ge=0)
    orphaned_managed_media_bytes: int = Field(ge=0)
    unresolved_visit_evidence_count: int = Field(ge=0)
    reviewed_bird_wildlife_evidence_count: int = Field(ge=0)
    reviewed_non_bird_blank_ambiguous_evidence_count: int = Field(ge=0)
    storage_warning: str | None = None
    message: str


class StorageCleanupCategorySummary(BaseModel):
    category: str
    media_count: int = Field(ge=0)
    bytes: int = Field(ge=0)


class StorageCleanupPreviewResponse(BaseModel):
    preview_token: str
    generated_at: datetime
    expires_at: datetime
    eligible_media_count: int = Field(ge=0)
    estimated_recoverable_bytes: int = Field(ge=0)
    categories: list[StorageCleanupCategorySummary] = Field(default_factory=list)
    oldest_eligible_at: datetime | None = None
    newest_eligible_at: datetime | None = None
    affected_visit_count: int = Field(ge=0)
    protected_counts: list[StorageCleanupCategorySummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str
    creates_review_truth: bool = False


class StorageCleanupExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_token: str = Field(min_length=8, max_length=160)
    confirm: bool = False
    idempotency_key: str = Field(min_length=8, max_length=120)


class StorageCleanupResult(BaseModel):
    batch_id: str
    state: str
    moved_to_recovery_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    recovered_bytes: int = Field(ge=0)
    recovery_expires_at: datetime | None = None
    message: str
    warnings: list[str] = Field(default_factory=list)
    idempotent: bool = False
    creates_review_truth: bool = False


class StorageCleanupHistoryItem(BaseModel):
    batch_id: str
    origin: str
    state: str
    created_at: datetime
    media_count: int = Field(ge=0)
    recovered_bytes: int = Field(ge=0)
    permanently_purged_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    recovery_expires_at: datetime | None = None
    message: str
    can_restore: bool = False


class StorageCleanupHistoryResponse(BaseModel):
    items: list[StorageCleanupHistoryItem] = Field(default_factory=list)
    message: str


class StorageCleanupRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=120)


class StorageCleanupPurgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    idempotency_key: str = Field(min_length=8, max_length=120)


class LocalBackupKind(str, Enum):
    manual = "manual"
    pre_restore = "pre_restore"


class LocalBackupVerificationStatus(str, Enum):
    verified = "verified"
    not_checked = "not_checked"


class LocalBackupSummary(BaseModel):
    id: str
    created_at: datetime
    kind: LocalBackupKind
    database_schema_version: int = Field(ge=1)
    database_size_bytes: int = Field(ge=0)
    media_file_count: int = Field(ge=0)
    media_size_bytes: int = Field(ge=0)
    archive_size_bytes: int = Field(ge=0)
    verification_status: LocalBackupVerificationStatus
    restore_compatible: bool


class LocalBackupLibraryResponse(BaseModel):
    backups: list[LocalBackupSummary]
    unreadable_backup_count: int = Field(ge=0)
    local_first_note: str


class LocalBackupVerificationResponse(BaseModel):
    backup: LocalBackupSummary
    verified: bool = True
    checked_at: datetime
    message: str


class LocalBackupRestorePlanRequest(BaseModel):
    rebind_managed_storage: bool = False


class LocalBackupStorageLayout(BaseModel):
    platform: str
    absolute: bool
    leaf_name: str


class LocalBackupRestorePlan(BaseModel):
    backup_valid: bool = True
    database_schema_version: int = Field(ge=1)
    source_database_layout: LocalBackupStorageLayout
    source_media_layout: LocalBackupStorageLayout
    target_database_layout: LocalBackupStorageLayout
    target_media_layout: LocalBackupStorageLayout
    managed_database_reference_count: int = Field(ge=0)
    media_archive_entry_count: int = Field(ge=0)
    external_paths_preserved: list[str]
    warnings: list[str]
    unsafe_paths: list[str]
    collisions: list[str]
    expected_entity_counts: dict[str, int]
    rebind_managed_storage: bool
    dry_run: bool
    confirmed: bool
    restore_allowed: bool


class LocalBackupRestoreRequest(BaseModel):
    confirm: bool = False
    rebind_managed_storage: bool = False


class LocalBackupRestoreResponse(BaseModel):
    restored_backup: LocalBackupSummary
    safety_backup: LocalBackupSummary
    restore_plan: LocalBackupRestorePlan
    status: LocalDataStatus
    message: str


class SampleDataRemovalRequest(BaseModel):
    confirm: bool = False


class SampleDataRemovalResponse(BaseModel):
    removed: bool
    removed_counts: dict[str, int] = Field(default_factory=dict)
    preserved_source_count: int = Field(ge=0)
    status: LocalDataStatus
    message: str


class ReviewCorrectionResult(BaseModel):
    review_label: ReviewLabel
    visit: Visit | None = None
    event: Event | None = None
    review_queue_count: int = Field(ge=0)
    analytics: AnalyticsSummary


class VisitReviewRevisionResponse(BaseModel):
    result: ReviewCorrectionResult
    review_state_token: str
    idempotent: bool = False


class VisitReviewReopenResponse(BaseModel):
    visit: Visit
    event: Event
    review_queue_count: int = Field(ge=0)
    analytics: AnalyticsSummary
    review_state_token: str
    idempotent: bool = False
    message: str


class VisitReviewHistoryEntry(BaseModel):
    """A user-facing correction history entry with no internal identifier exposure."""

    action: str
    label: str | None = None
    notes: str | None = None
    created_at: datetime
    is_current: bool = False


class VisitReviewHistory(BaseModel):
    visit_id: str
    review_status: ReviewStatus
    reviewed_label: str | None = None
    review_state_token: str
    entries: list[VisitReviewHistoryEntry] = Field(default_factory=list)


class FastReviewCorrectionResponse(BaseModel):
    result: ReviewCorrectionResult
    idempotent: bool = False
    undo_state_token: str


class FastReviewUndoRequest(BaseModel):
    """Reverse only the caller's newest Fast Review correction, append-only."""

    model_config = ConfigDict(extra="forbid")

    review_label_id: str = Field(min_length=1, max_length=256)
    review_session_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    expected_state_token: str = Field(min_length=1, max_length=256)


class FastReviewUndoResponse(BaseModel):
    reversal_review_label_id: str
    target_type: ReviewQueueBulkCorrectionTargetType
    target_id: str
    review_queue_count: int = Field(ge=0)
    analytics: AnalyticsSummary
    idempotent: bool = False
    message: str


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
    motion_evidence: MotionEvidenceResponse | None = None
    media_asset: MediaAsset | None = None
    detection_proposals: list[DetectionProposal] = Field(default_factory=list)
    detection_runs: list[DetectionRun] = Field(default_factory=list)
    review_labels: list[ReviewLabel]
    correction_history: list[VisitReviewHistoryEntry] = Field(default_factory=list)
    curation_history: list[VisitCurationHistoryEntry] = Field(default_factory=list)
    resulting_visits: list[Visit] = Field(default_factory=list)
    eligible_zones: list[Zone] = Field(default_factory=list)
    review_state_token: str = ""
    dataset_ready: bool
    review_summary: str


class VisitDetail(BaseModel):
    visit: Visit
    event: Event
    stream: Stream
    primary_zone: Zone | None = None
    detections: list[Detection]
    motion_evidence: MotionEvidenceResponse | None = None
    media_asset: MediaAsset | None = None
    evidence_frames: list[VisitEvidenceFrame] = Field(default_factory=list)
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
