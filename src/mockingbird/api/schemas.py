"""Product-shaped API schemas for MockingBird."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# `ReviewOrigin`/`ReviewOriginStored` are the canonical provenance-value
# types (see docs/review-decision-provenance-contract.md): defined once in
# the small, dependency-free `review_provenance` module and reused here
# rather than a second, possibly-drifting Enum duplicating the same values.
# `ReviewOrigin` (3 values) types every *create* request field: a stored
# row can never be freshly claimed as `legacy_unattributed`.
# `ReviewOriginStored` (4 values) types every *response* field: a real
# backfilled legacy row must round-trip through the API without a
# validation error.
from mockingbird.review_provenance import ReviewOrigin, ReviewOriginStored


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


class AutomaticIdentificationStatus(str, Enum):
    off = "off"
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    no_result = "no_result"
    timed_out = "timed_out"
    failed = "failed"
    skipped_existing = "skipped_existing"


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
    camera_node = "camera_node"
    unknown = "unknown"


class DashboardLivePreviewKind(str, Enum):
    unavailable = "unavailable"
    browser_direct = "browser_direct"
    backend_session = "backend_session"


class LivePreviewLeaseStatus(str, Enum):
    live = "live"
    limit_reached = "limit_reached"
    unavailable = "unavailable"


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


class CameraHealthState(str, Enum):
    healthy = "healthy"
    starting = "starting"
    waiting_for_capacity = "waiting_for_capacity"
    camera_unavailable = "camera_unavailable"
    no_recent_frame = "no_recent_frame"
    evidence_storage_degraded = "evidence_storage_degraded"
    recovering = "recovering"
    stopped = "stopped"
    setup_incomplete = "setup_incomplete"


class CameraHealthIncidentCategory(str, Enum):
    camera_unavailable = "camera_unavailable"
    no_recent_frame = "no_recent_frame"
    evidence_persistence_degraded = "evidence_persistence_degraded"
    recovery_exhausted = "recovery_exhausted"
    capacity_waiting = "capacity_waiting"
    configuration_invalid = "configuration_invalid"


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



class ReviewQueueSpeciesSuggestionBatchPrepareStatus(str, Enum):
    queued = "queued"
    skipped = "skipped"
    setup_required = "setup_required"


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
    # Identification Eligibility + Abstention v1: a real, honest outcome --
    # not an error. Either subject evidence did not meet the identification
    # eligibility floor, or a real model result was too ambiguous/unspecific
    # to present as a named species. Distinguished from `unsupported_media`
    # (a media-type/zone problem) and `failed` (an adapter/runtime problem):
    # this is a considered "not enough support to name a species" verdict,
    # honest uncertainty rather than a malfunction. See `unavailable_reason`
    # for the specific bounded reason code
    # (`bioclip_identification_evidence_ineligible` /
    # `bioclip_identification_ambiguous`).
    identification_uncertain = "identification_uncertain"


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


class SpeciesCandidatePackStatus(str, Enum):
    active = "active"
    archived = "archived"


class SpeciesCandidatePackSummary(BaseModel):
    id: str
    display_name: str
    version: int = Field(ge=1)
    status: SpeciesCandidatePackStatus
    is_builtin: bool
    candidate_count: int = Field(ge=2, le=200)
    content_sha256: str


class SpeciesCandidatePack(SpeciesCandidatePackSummary):
    description: str | None = None
    members: list[TaxonomyLabel] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SpeciesCandidatePackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    taxonomy_label_ids: list[str] = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=280)


class SpeciesCandidatePackUpdate(SpeciesCandidatePackCreate):
    """Editing creates an immutable successor version and preserves prior evidence."""


class SpeciesCandidatePackCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=280)


class StreamSpeciesCandidatePackSelection(BaseModel):
    stream_id: str
    selected_pack_id: str | None = None
    effective_pack: SpeciesCandidatePackSummary
    warning: str | None = None


class StreamSpeciesCandidatePackSelectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_pack_id: str = Field(min_length=1, max_length=120)


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
    # Camera / Source + Multi-Camera Maturity v1, Phase D: the one bounded,
    # truthful classification -- see `mockingbird.observation.provider_
    # compatibility`'s own module docstring for why this exists alongside
    # `status` above (which answers a narrower, different question and
    # currently lumps a fully-built import path in with genuine vaporware).
    compatibility: Literal["certified", "compatible", "experimental", "import_only", "unsupported"]
    compatibility_label: str


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


class OnvifDiscoverProfilesRequest(BaseModel):
    """v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF").
    Stateless -- no Source needs to exist yet; this is the "Add camera ->
    Discover with ONVIF" step. `onvif_password` never appears in any
    response (see `OnvifDiscoveredProfile`'s docstring)."""

    model_config = ConfigDict(extra="forbid")

    onvif_host: str = Field(min_length=1, max_length=255)
    onvif_port: int = Field(default=80, ge=1, le=65535)
    onvif_username: str = Field(default="", max_length=255)
    onvif_password: str = Field(default="", max_length=255)


class OnvifDiscoveredProfile(BaseModel):
    """One media profile plus its camera-provided stream URI -- always the
    bare URI with no credentials embedded (see docs/source-provider-
    configuration-contract.md "Secret/Redaction policy": a transient
    discovery response is held to the identical never-echo-a-secret
    discipline as a saved-config read). `advertised_width`/`advertised_
    height` are this camera's own unverified claim, never presented as
    observed/verified resolution."""

    profile_token: str
    profile_name: str | None = None
    advertised_width: int | None = None
    advertised_height: int | None = None
    encoding: str | None = None
    stream_uri: str


class OnvifDiscoverProfilesResponse(BaseModel):
    status: Literal[
        "available", "unreachable", "authentication_rejected", "no_profiles", "error"
    ]
    message: str
    device_manufacturer: str | None = None
    device_model: str | None = None
    device_firmware_version: str | None = None
    profiles: list[OnvifDiscoveredProfile] = Field(default_factory=list)


class OnvifRecordProfileRequest(BaseModel):
    """v0.1 Acquisition/Ingest Interoperability Closure v1: persists which
    ONVIF device/profile an already-configured `external_url`+rtsp Source
    was set up through. `live_stream_url` is the credential-embedded RTSP
    URI the caller already built client-side (from `OnvifDiscoverProfiles
    Response.profiles[].stream_uri` plus the password it still holds --
    see docs/onvif-provider-boundary-design.md) -- this request never
    carries a raw password field of its own."""

    model_config = ConfigDict(extra="forbid")

    onvif_host: str = Field(min_length=1, max_length=255)
    onvif_port: int = Field(default=80, ge=1, le=65535)
    onvif_username: str = Field(default="", max_length=255)
    profile_token: str = Field(min_length=1)
    profile_name: str | None = None
    device_manufacturer: str | None = None
    device_model: str | None = None
    device_firmware_version: str | None = None
    advertised_width: int | None = None
    advertised_height: int | None = None
    live_stream_url: str = Field(min_length=1)


class OnvifRecordProfileResponse(BaseModel):
    source_id: str
    status: Literal["saved", "invalid_stream_url"]
    message: str
    provider_configuration: SourceProviderConfiguration | None = None


class CameraConfigurationSecretAction(str, Enum):
    keep = "keep"
    replace = "replace"
    remove = "remove"


class CameraConfigurationValidationSummary(BaseModel):
    """Readiness-only validation for a saved camera edit; never a connection check."""

    status: str
    message: str
    missing_fields: list[str] = Field(default_factory=list)
    can_apply: bool


class CameraNodeHardwareReplacementSummary(BaseModel):
    """Bounded, "most recent transition only" provenance -- never a growing
    hardware-asset ledger. Present only once this camera's Camera Node
    hardware has actually been replaced through a confirmed reprovision."""

    replaced_at: datetime
    reason: str | None = None


class CameraConfigurationEditResponse(BaseModel):
    """A secret-safe edit contract that intentionally omits saved provider values."""

    stream_id: str
    source_id: str
    source_name: str
    stream_name: str
    provider_key: str
    provider_display_name: str
    editable: bool
    editable_fields: list[SourceProviderField] = Field(default_factory=list)
    configured_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    field_states: dict[str, str] = Field(default_factory=dict)
    state_token: str
    monitoring_policy: StreamMonitoringPolicyResponse
    runtime: StreamRuntimeStatusResponse
    health: CameraHealthSummary
    # Non-secret (see `SOURCE_PROVIDER_DEFINITIONS`'s `node_display_name`):
    # the display name a replacement Camera Node should be given so its
    # `node_id` matches this Source's existing one, reattaching through
    # ordinary repair-pairing without confirming a hardware replacement.
    node_expected_display_name: str | None = None
    hardware_replacement: CameraNodeHardwareReplacementSummary | None = None
    message: str


class CameraConfigurationChangeRequest(BaseModel):
    """A partial in-place edit. Secret values require an explicit action."""

    model_config = ConfigDict(extra="forbid")

    provider_key: str
    config: dict[str, str | None] = Field(default_factory=dict)
    secret_actions: dict[str, CameraConfigurationSecretAction] = Field(default_factory=dict)
    node_pairing_token: str | None = Field(default=None, min_length=16, max_length=160)
    source_name: str | None = Field(default=None, max_length=120)
    stream_name: str | None = Field(default=None, max_length=120)
    expected_state_token: str = Field(min_length=16, max_length=160)
    # Reprovision / Replacement Recovery v1: a deliberate, operator-confirmed
    # override for a genuine Camera Node hardware swap on an already-paired
    # camera. Present on the shared base (not apply-only) so preview can
    # describe the swap's impact honestly instead of erroring exactly like
    # apply would. Ordinary same-identity credential repair never needs it.
    # See docs/camera-node-reprovision-recovery-design.md.
    confirm_node_identity_change: bool = False
    replacement_reason: str | None = Field(default=None, max_length=280)

    @field_validator("source_name", "stream_name")
    @classmethod
    def normalize_optional_names(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Camera and Stream names cannot be blank when changed.")
        return normalized

    @field_validator("replacement_reason")
    @classmethod
    def normalize_replacement_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CameraConfigurationImpactPreviewRequest(CameraConfigurationChangeRequest):
    pass


class CameraNodeIdentityReplacementImpact(BaseModel):
    """Impact of a confirmed Camera Node hardware swap, shown before apply."""

    previous_node_id: str
    new_node_id: str
    zones_review_recommended: bool
    message: str
    # Appliance / Storage / Privacy / Recovery v1, Phase I: the previous
    # physical node's own last-self-reported remote-transport backlog count,
    # when Remote/Intermittent-WAN Transport was configured for it -- `None`
    # when transport was never configured or has never reported (nothing to
    # disclose). Not re-derived after replacement: the old node's credential
    # becomes unusable the moment this replacement is applied, so any items
    # still sitting in *its own* local spool at that moment cannot be
    # delivered afterward. See `message` for the plain-language warning.
    pending_transport_backlog_count: int | None = None


class CameraConfigurationImpactPreview(BaseModel):
    stream_id: str
    source_id: str
    provider_key: str
    state_token: str
    preview_token: str
    changed_fields: list[str] = Field(default_factory=list)
    restart_required: bool
    requires_explicit_restart_choice: bool
    monitoring_desired: StreamMonitoringMode
    monitoring_actual: StreamRuntimeState
    open_activity_session_count: int = Field(ge=0)
    preview_may_be_briefly_unavailable: bool
    preservation_summary: list[str] = Field(default_factory=list)
    node_identity_replacement: CameraNodeIdentityReplacementImpact | None = None
    validation: CameraConfigurationValidationSummary
    message: str


class CameraConfigurationApplyRequest(CameraConfigurationChangeRequest):
    preview_token: str = Field(min_length=16, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=120)
    restart_monitoring: bool = False


class CameraConfigurationRevision(BaseModel):
    id: str
    stream_id: str
    source_id: str
    provider_key: str
    changed_fields: list[str] = Field(default_factory=list)
    change_fingerprint: str
    restart_required: bool
    restart_requested: bool
    desired_mode: StreamMonitoringMode
    actual_state_before: StreamRuntimeState
    actual_state_after: StreamRuntimeState
    outcome: str
    created_at: datetime


class CameraConfigurationHistoryResponse(BaseModel):
    items: list[CameraConfigurationRevision] = Field(default_factory=list, max_length=20)
    limit: int = Field(ge=1, le=20)
    message: str


class CameraConfigurationApplyResponse(BaseModel):
    configuration: CameraConfigurationEditResponse
    preview: CameraConfigurationImpactPreview
    revision: CameraConfigurationRevision
    idempotent: bool = False
    message: str


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
    exposure_interval_active: bool = False
    current_healthy_duration_seconds: float | None = Field(default=None, ge=0)
    durable_exposure_today_seconds: float = Field(default=0, ge=0)
    exposure_history_available_from: datetime | None = None
    latest_confirmed_exposure_at: datetime | None = None
    most_recent_exposure_close_reason: str | None = None
    last_evidence_persisted_at: datetime | None = None
    last_evidence_failure_at: datetime | None = None
    evidence_failure_code: str | None = None
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


class CameraHealthIncident(BaseModel):
    """A bounded, sanitized operational state transition for one Stream."""

    id: str
    stream_id: str
    category: CameraHealthIncidentCategory
    severity: AlertSeverity
    started_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    reason_code: str
    condition_fingerprint: str
    next_retry_at: datetime | None = None
    occurrence_count: int = Field(ge=1, le=100)
    alert_id: str | None = None


class CameraHealthSummary(BaseModel):
    """Product-facing camera health; it intentionally excludes connection details."""

    stream_id: str
    stream_name: str
    source_id: str
    source_name: str
    state: CameraHealthState
    message: str
    desired_mode: StreamMonitoringMode
    actual_state: StreamRuntimeState
    readiness_status: StreamPlaybackStatusValue
    preview_available: bool = False
    last_good_frame_at: datetime | None = None
    frame_age_seconds: int | None = Field(default=None, ge=0)
    last_evidence_persisted_at: datetime | None = None
    last_evidence_failure_at: datetime | None = None
    open_activity_session_count: int = Field(default=0, ge=0)
    latest_visit_at: datetime | None = None
    next_retry_at: datetime | None = None
    failure_reason: str | None = None
    unread_alert: bool = False
    stale: bool = False
    # Camera / Source + Multi-Camera Maturity v1, Phase F/K: honest,
    # existing-diagnostics-only disambiguation. Both fields stay `None`/
    # unset by default -- the ordinary case, unchanged. `connectivity_reason
    # == "host_unreachable"` is set only when there is *positive* evidence
    # the paired Camera Node itself is alive (a fresh Remote/Intermittent-
    # WAN Transport contact) despite the ordinary host<->Node API path
    # currently failing -- never a guess, and never claimed the other
    # direction ("camera_hardware") merely by absence of that evidence,
    # since a failed pull path alone cannot actually prove the camera itself
    # is at fault. See `ProductRepository._camera_node_transport_backlog_
    # facts`.
    connectivity_reason: Literal["host_unreachable"] | None = None
    backlog_pending_count: int | None = Field(default=None, ge=0)
    backlog_last_synced_at: datetime | None = None
    # Camera / Source + Multi-Camera Maturity v1, Phase B/E: this Stream's
    # one unambiguous representative "Area" (see `ProductRepository.
    # _representative_area_name`) -- `None` when zero or more than one
    # active, non-privacy Zone exists, never a guess.
    area_name: str | None = None


class CameraHealthDetailResponse(BaseModel):
    health: CameraHealthSummary
    incidents: list[CameraHealthIncident] = Field(default_factory=list, max_length=20)
    message: str


class CameraHealthListResponse(BaseModel):
    items: list[CameraHealthSummary] = Field(default_factory=list, max_length=50)
    limit: int = Field(ge=1, le=50)
    message: str


class CameraHealthIncidentListResponse(BaseModel):
    items: list[CameraHealthIncident] = Field(default_factory=list, max_length=20)
    limit: int = Field(ge=1, le=20)
    message: str


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
    # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.16
    # Capability reporting"): purely informational provenance -- never
    # authoritative over `status`/`live_stream_type`/anything above. A
    # Source configured manually (the ordinary case) simply has
    # `onvif_connected=False`.
    onvif_connected: bool = False
    onvif_device_summary: str | None = None


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
    auto_identify_review_candidates: bool = False
    automatic_identification_status: AutomaticIdentificationStatus = (
        AutomaticIdentificationStatus.off
    )
    last_auto_identification_target_id: str | None = None
    last_auto_identification_attempt_id: str | None = None
    last_auto_identification_suggestion_id: str | None = None
    last_auto_identification_message: str | None = None
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
    activity_subject_state: str | None = None
    activity_promotion_category: str | None = None
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


class LivePreviewLeaseRequest(BaseModel):
    """A browser-local owner for one explicitly opened overview preview."""

    model_config = ConfigDict(extra="forbid")

    owner_id: str = Field(
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class LivePreviewLeaseResponse(BaseModel):
    stream_id: str
    owner_id: str
    status: LivePreviewLeaseStatus
    preview_url: str | None = None
    expires_at: datetime | None = None
    max_active_previews: int = Field(ge=1, le=4)
    effective_limit: int = Field(ge=1, le=4)
    monitoring_changed: bool = False
    creates_media: bool = False
    creates_evidence: bool = False
    creates_event: bool = False
    creates_visit: bool = False
    creates_truth: bool = False
    message: str


class LivePreviewReleaseResponse(BaseModel):
    stream_id: str
    owner_id: str
    released: bool
    monitoring_changed: bool = False
    creates_media: bool = False
    creates_evidence: bool = False
    creates_event: bool = False
    creates_visit: bool = False
    creates_truth: bool = False
    message: str


class SourceMonitorStartRequest(BaseModel):
    interval_seconds: int = Field(default=15, ge=5)
    max_runtime_minutes: int = Field(default=30, ge=1, le=120)
    max_snapshots: int = Field(default=100, ge=1, le=500)
    check_motion: bool = True
    create_review_activity: bool = False


class ObservationProviderCapabilitiesResponse(BaseModel):
    timer_driven: bool
    emits_frame_packets: bool
    emits_detection_observations: bool
    emits_track_updates: bool
    emits_evidence_candidates: bool
    emits_visit_proposals: bool
    # Source-Resolution + Multi-Frame Species Evidence v1: previously
    # computed on `ObservationProviderCapabilities` (see
    # `mockingbird.observation.contracts`) but never exposed through this
    # public response model -- "can this provider ever produce a genuinely
    # higher-resolution evidence capture at all" is exactly the honest,
    # capability-driven fact "Capability-aware UX" in product-doctrine.md
    # calls for. `False` (the dataclass default) for any provider kind that
    # predates or never implements this, never fabricated `True`.
    high_resolution_burst: bool = False


class ObservationProviderHealthResponse(BaseModel):
    state: Literal["idle", "running", "stopped", "degraded"]
    healthy: bool
    message: str
    observed_at: datetime | None = None


class ObservationEngineStatusResponse(BaseModel):
    active_provider_id: str
    provider_id: str
    provider_name: str
    capabilities: ObservationProviderCapabilitiesResponse
    health: ObservationProviderHealthResponse
    creates_truth: bool = False
    persistent: bool = False


class ObservationSessionCounts(BaseModel):
    """Transient, per-running-session diagnostic counts -- advanced
    diagnostics only, never dataset truth or a durable record."""

    track_updates_observed: int = 0
    evidence_candidates_observed: int = 0
    proposals_observed: int = 0
    candidates_created: int = 0
    candidates_suppressed: int = 0
    suppressed_reasons: list[list[str | int]] = Field(default_factory=list)


class ObservationSessionStatusResponse(BaseModel):
    """The unified Observation panel's whole product contract (Unified
    Observation Experience v1): current state, camera health, and
    observation-capability health for one Stream, regardless of which
    existing runtime actually backs it (Camera Node's frame-driven engine,
    existing backend-owned live monitoring, or the existing Snapshot Source
    monitor). Side-effect-free to read; only start/stop mutate it. Basic
    fields only (`state`, `observing`, `message`, `camera_connected`,
    `camera_message`, `runtime_available`, `setup_action`, `retry_action`);
    `advanced` is the bounded, optional diagnostics surface (runtime kind,
    provider ids, activation boundary, suppressed-candidate reasons) the
    basic UI never needs to render."""

    stream_id: str
    state: Literal["stopped", "starting", "observing", "stopping", "needs_attention"]
    observing: bool
    message: str
    camera_connected: bool
    camera_message: str
    engine_available: bool
    engine_message: str
    # False only when this Stream has no integrated observation runtime at
    # all (an honest unavailable state rather than a Start button that
    # would only fail).
    runtime_available: bool = True
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    stopped_reason: str | None = None
    last_candidate_visit_id: str | None = None
    last_useful_frame_at: datetime | None = None
    # When set, the basic UI shows the one relevant existing setup action
    # (Edit camera setup) instead of a Start button that cannot succeed yet.
    setup_action: Literal["edit_camera_setup"] | None = None
    # True only for the existing live-monitoring lane's own bounded
    # runtime/retry action, reusing `POST .../runtime/retry` unchanged.
    retry_action: bool = False
    # Visit Authority Budget + Ambiguous-Boundary Recall Closure v1: truthful
    # even while `observing`/`engine_available` stay true -- a genuinely
    # exhausted in-session candidate budget must never be silently absorbed
    # into an otherwise-healthy status. `False`/`None` for every other lane
    # and for a Camera Node session that has never hit this. Raw counters
    # (configured budget, consumed count, activation identity, exhaustion
    # timestamp) remain in `advanced` only -- this is the one plain-language
    # fact the basic UI may show.
    candidate_authority_exhausted: bool = False
    candidate_authority_message: str | None = None
    counts: ObservationSessionCounts = Field(default_factory=ObservationSessionCounts)
    advanced: dict[str, object] = Field(default_factory=dict)


class CounterfactualConfidenceSummaryResponse(BaseModel):
    """A minimal, wire-lean projection of `contracts.ConfidenceEvidenceSummary`
    -- count/max/strong-count only, never the full per-detection sample
    list (available to a Python-level caller of the underlying pure module
    directly; kept out of the HTTP contract to stay a small, practical
    surface -- see docs/rejected-detection-attribution-contract.md)."""

    detection_count: int
    max_confidence: float | None = None
    strong_detection_count: int | None = None


class CounterfactualRawDetectionResponse(BaseModel):
    """One raw detector-evaluation fact -- either a genuine detection
    (`bounding_box` set) or an explicit "the detector ran here and found
    nothing usable" heartbeat (`bounding_box` absent). Diagnostic evidence
    only, never reviewed truth."""

    source_offset_ms: int
    captured_at: datetime | None = None
    frame_id: str | None = None
    detector_id: str | None = None
    provider_id: str | None = None
    broad_class: str | None = None
    is_animal: bool | None = None
    confidence: float | None = None
    bounding_box: list[float] | None = None


class CounterfactualTrackGenerationResponse(BaseModel):
    """One finalized tracker generation -- confirmed *or* rejected -- that
    build_tracklets would otherwise have discarded entirely when not
    confirmed."""

    generation_id: str
    broad_class: str
    track_ids: list[str]
    start_offset_ms: int
    end_offset_ms: int
    start_bounding_box: list[float]
    end_bounding_box: list[float]
    geometry_envelope: list[float]
    confirmed: bool
    terminal_reason: str | None = None
    terminal_geometry_source: Literal["detector", "tracker", "carried_forward"] | None = None
    confidence_evidence: CounterfactualConfidenceSummaryResponse
    # Gate A Measurement Closure v1: wall-clock twins of start_offset_ms/
    # end_offset_ms, Node-domain (see docs/camera-node-live-shadow-
    # contract.md "Clock-drift disposition") -- diagnostic only, never
    # itself observational authority. `None` only when the underlying
    # `TrackGenerationRecord` predates this field.
    start_captured_at: datetime | None = None
    end_captured_at: datetime | None = None


class CounterfactualProposalOutcomeResponse(BaseModel):
    """One decided admission attempt, recorded regardless of outcome."""

    proposal_id: str
    broad_class: str
    zone_id: str | None = None
    start_offset_ms: int
    end_offset_ms: int
    constituent_generation_ids: list[str]
    outcome: str
    reason: str
    admitted: bool
    visit_id: str | None = None
    decided_at: datetime


class CounterfactualClockCalibrationResponse(BaseModel):
    """Camera Node -> Host Clock Normalization v1 (additive; see
    docs/camera-node-host-clock-normalization-latency-v1-report.md): one
    calibration attempt for this stream, anchored to `source_offset_ms`
    (the Node-session-relative coordinate every other record here already
    keys off). `state == "insufficient_samples"` is a real, auditable
    outcome, not an error -- `offset_ms`/`uncertainty_ms` stay `None` in
    that case, never a fabricated number. `clock_jump_detected` marks a
    sample whose own offset moved by more than the module's disclosed
    jump threshold relative to the immediately-preceding calibrated
    sample -- everything before it may no longer govern an offset at or
    after this one (see `clock_calibration.active_calibration_for_offset`)."""

    source_offset_ms: int
    calibrated_at: datetime
    sample_count: int
    state: Literal["calibrated", "insufficient_samples"]
    offset_ms: float | None = None
    uncertainty_ms: float | None = None
    clock_jump_detected: bool = False


class CounterfactualRttClockCalibrationResponse(BaseModel):
    """Camera Node <-> Host RTT-Bounded Clock Calibration v1 (additive; see
    docs/camera-node-host-rtt-bounded-clock-calibration-v1-report.md): one
    RTT-bounded calibration batch for this stream -- the defensible
    absolute anchor `CounterfactualClockCalibrationResponse` above cannot
    itself provide (that one-way estimator is a one-sided upper bound
    only). `offset_ms` is the interval's own midpoint, never represented
    as exact; `offset_min_ms`/`offset_max_ms` carry the full, honest bound.
    `state == "insufficient_samples"`/`"inconsistent_samples"` are real,
    auditable outcomes, not errors -- every numeric field stays `None` in
    either case, never a fabricated number. `rtt_ms`/`node_processing_ms`
    describe the single lowest-RTT sample actually used to anchor the
    combined interval, not an average across the batch."""

    source_offset_ms: int
    calibrated_at: datetime
    sample_count: int
    valid_sample_count: int
    state: Literal["calibrated", "insufficient_samples", "inconsistent_samples"]
    offset_ms: float | None = None
    offset_min_ms: float | None = None
    offset_max_ms: float | None = None
    uncertainty_ms: float | None = None
    rtt_ms: float | None = None
    node_processing_ms: float | None = None
    clock_jump_detected: bool = False


class CounterfactualLedgerAccountingResponse(BaseModel):
    """Clear eviction accounting: how much of this ledger's own bounded
    history is still retained versus already evicted."""

    retained_count: int
    evicted_count: int
    recorded_count: int
    oldest_retained_offset_ms: int | None = None
    newest_retained_offset_ms: int | None = None


class CounterfactualCoverageResponse(BaseModel):
    session_first_offset_ms: int | None = None
    session_last_offset_ms: int | None = None
    raw_detections: CounterfactualLedgerAccountingResponse
    track_generations: CounterfactualLedgerAccountingResponse
    proposal_outcomes: CounterfactualLedgerAccountingResponse


class CounterfactualWindowResponse(BaseModel):
    """Rejected / Suppressed Detection Attribution v1 (see
    docs/rejected-detection-attribution-contract.md): a bounded, read-only
    reconstruction of what happened around one source-relative time window
    -- and, optionally, one region of interest -- for the current (or most
    recently stopped) Observation Engine session on this Stream. Never
    starts a session, never creates evidence, and never itself reviewed
    truth: `attribution` is diagnostic accounting a human reviewer's own
    judgment must still confirm, exactly like `localization_attribution`'s
    own classification already is."""

    stream_id: str
    start_offset_ms: int
    end_offset_ms: int
    roi: list[float] | None = None
    raw_detections: list[CounterfactualRawDetectionResponse]
    track_generations: list[CounterfactualTrackGenerationResponse]
    proposal_outcomes: list[CounterfactualProposalOutcomeResponse]
    raw_detection_count_in_roi: int
    track_generation_count_in_roi: int
    coverage: CounterfactualCoverageResponse
    attribution: str
    attribution_reason: str
    # Camera Node -> Host Clock Normalization v1 (additive). `clock_
    # calibration_required` is `False` for a same-clock-domain session
    # (RTSP/local/USB/replay -- no Camera Node ever in this Stream's own
    # capture path) and every ledger snapshot saved before this field
    # existed; `clock_calibrations` is empty in both of those cases, never
    # fabricated.
    clock_calibrations: list[CounterfactualClockCalibrationResponse] = Field(default_factory=list)
    clock_calibration_required: bool = False
    # Camera Node <-> Host RTT-Bounded Clock Calibration v1 (additive). The
    # defensible, bounded absolute-anchor history -- see
    # `CounterfactualRttClockCalibrationResponse`'s own docstring. Empty
    # for a same-clock-domain session (identical reasoning to `clock_
    # calibrations` above) and for every ledger snapshot that predates
    # this field.
    rtt_clock_calibrations: list[CounterfactualRttClockCalibrationResponse] = Field(default_factory=list)


class SceneConfusorLearningStatusResponse(BaseModel):
    """Site-Specific Learning & Local Adaptation v1 (see docs/scene-
    confusor-suspicion-contract.md, "Operator surface"): the smallest
    honest status the "Learning from reviewed activity on this camera" /
    "Not enough reviewed history yet" / "Local adjustment active" / "Local
    adjustment disabled" product surface needs. Deliberately does not
    expose region ids, geometry, occurrence counts, or any other model-
    internal detail -- see the governing milestone brief's Phase 6."""

    stream_id: str
    reviewed_evidence_enabled: bool
    regions_with_reviewed_evidence: int
    regions_currently_adjusted: int


class SceneConfusorLearningEnabledUpdate(BaseModel):
    """Body for enabling/disabling this Stream's own reviewed-evidence
    suspicion path -- see `SceneConfusorLearningStatusResponse`."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SourceMonitorStatusResponse(BaseModel):
    # Monitor state is in-memory and evidence-only; correction remains truth.
    observation_provider_id: str = "snapshot"
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


class CameraSetupOption(BaseModel):
    """One backend-authoritative setup choice; adapter keys are never client-defined."""

    provider_key: str
    display_name: str
    description: str
    availability: str
    supports_live_playback: bool
    fields: list[SourceProviderField] = Field(default_factory=list)
    message: str
    # Camera / Source + Multi-Camera Maturity v1, Phase D -- see
    # `SourceProviderDefinition.compatibility`'s own docstring.
    compatibility: Literal["certified", "compatible", "experimental", "import_only", "unsupported"]
    compatibility_label: str


class CameraSetupOptionsResponse(BaseModel):
    options: list[CameraSetupOption]
    message: str


class CameraSetupValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_key: str
    config: dict[str, str | None] = Field(default_factory=dict)
    node_pairing_token: str | None = Field(default=None, min_length=16, max_length=160)


class CameraSetupValidationResponse(BaseModel):
    provider_key: str
    status: str
    message: str
    safe_config_preview: dict[str, str] = Field(default_factory=dict)
    supports_live_playback: bool
    can_continue: bool
    preview_available: bool
    creates_events: bool = False
    creates_visits: bool = False
    creates_media: bool = False
    creates_truth: bool = False


class CameraSetupZoneDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    zone_type: ZoneType
    polygon: list[Point] = Field(min_length=3, max_length=32)
    is_active: bool = True
    monitoring_policy: ZoneMonitoringPolicyUpdate | None = None


class CameraSetupCompleteRequest(BaseModel):
    """One intentional, bounded completion request for a browser-local setup draft."""

    model_config = ConfigDict(extra="forbid")

    camera_name: str = Field(min_length=1, max_length=120)
    stream_name: str = Field(min_length=1, max_length=120)
    provider_key: str
    config: dict[str, str | None] = Field(default_factory=dict)
    node_pairing_token: str | None = Field(default=None, min_length=16, max_length=160)
    zones: list[CameraSetupZoneDraft] = Field(min_length=1, max_length=12)
    enable_monitoring: bool = False
    idempotency_key: str = Field(min_length=8, max_length=120)

    @field_validator("camera_name", "stream_name")
    @classmethod
    def normalize_setup_names(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("A camera and view name are required.")
        return normalized


class CameraSetupCompletionResponse(BaseModel):
    source: CameraSource
    stream: Stream
    zones: list[Zone]
    monitoring_policy: StreamMonitoringPolicyResponse
    validation: CameraSetupValidationResponse
    idempotent: bool = False
    message: str


class CameraNodePairRequest(BaseModel):
    """One explicit local-LAN pairing request; the pairing code is never stored."""

    model_config = ConfigDict(extra="forbid")

    base_address: str = Field(min_length=8, max_length=260)
    pairing_code: str = Field(min_length=8, max_length=128)
    renews_pairing_token: str | None = Field(default=None, min_length=16, max_length=160)


class CameraNodeAdvertisedCamera(BaseModel):
    camera_id: str
    display_name: str
    status: str
    snapshot_supported: bool
    setup_hint: str | None = None
    provider_type: str | None = None
    capture_profiles: list["CameraNodeCaptureProfile"] = Field(
        default_factory=list,
        max_length=12,
    )


class CameraNodeCaptureProfile(BaseModel):
    profile_id: str
    purposes: list[str] = Field(default_factory=list, max_length=3)
    width: int = Field(ge=1, le=16_000)
    height: int = Field(ge=1, le=12_000)
    jpeg_supported: bool
    max_expected_bytes: int = Field(ge=32_768, le=16_000_000)
    capture_class: str
    geometry_group: str | None = None
    orientation: str = "normal"
    mirrored: bool = False
    same_fov: bool = False


class CameraNodePairResponse(BaseModel):
    """Confirms a one-time code was accepted. The pairing itself is already
    durable server-side by the time this response is sent (see
    docs/camera-node-pairing-persistence-design.md) -- `pairing_token` is an
    opaque reference to that durable record, not a time-boxed handoff, so
    this response deliberately carries no expiry: the one-time *code* was
    already consumed to produce it, and nothing about finishing setup is
    still racing a clock.
    """

    pairing_token: str
    node_id: str
    display_name: str
    api_version: str
    cameras: list[CameraNodeAdvertisedCamera] = Field(default_factory=list, max_length=16)
    message: str


class CameraNodePendingSetupResponse(BaseModel):
    """Safe, resumable view of a durable Camera Node pairing/setup draft.

    Never includes the Node address or credential -- both stay server-side
    only, exactly like a completed Source's saved configuration keeps them.
    `status == "needs_renewal"` means the Node no longer accepts the stored
    credential (for example a genuine revocation); setup can only continue
    after an explicit, deliberate re-pair, and any already-entered draft
    fields below are preserved through that re-pair.
    """

    pairing_token: str
    status: str
    node_id: str
    display_name: str
    api_version: str
    cameras: list[CameraNodeAdvertisedCamera] = Field(default_factory=list, max_length=16)
    selected_camera_id: str | None = None
    camera_name: str | None = None
    stream_name: str | None = None
    zone_name: str | None = None
    zone_type: ZoneType | None = None
    polygon: list[Point] | None = None
    sensitivity: ZoneActivitySensitivity | None = None
    monitoring_enabled: bool = False
    message: str


class CameraNodePendingSetupDraftUpdate(BaseModel):
    """Explicit update to a resumable draft's own already-entered fields.

    Never accepts a camera address or credential -- those change only
    through pairing itself. This exists solely so a camera name, view name,
    Zone, or sensitivity already typed survives a refresh or app restart
    too, not only the pairing. Any field left out keeps its saved value.
    """

    model_config = ConfigDict(extra="forbid")

    selected_camera_id: str | None = Field(default=None, max_length=120)
    camera_name: str | None = Field(default=None, max_length=120)
    stream_name: str | None = Field(default=None, max_length=120)
    zone_name: str | None = Field(default=None, max_length=120)
    zone_type: ZoneType | None = None
    polygon: list[Point] | None = Field(default=None, min_length=3, max_length=32)
    sensitivity: ZoneActivitySensitivity | None = None
    monitoring_enabled: bool | None = None


class CameraNodePreviewRequest(BaseModel):
    """Request one explicitly selected, transient Node snapshot."""

    model_config = ConfigDict(extra="forbid")

    pairing_token: str = Field(min_length=16, max_length=160)
    camera_id: str = Field(min_length=1, max_length=120)


class CameraNodePendingSetupRevokeRequest(BaseModel):
    """Explicit, deliberate 'forget this Camera Node' action.

    Distinct from leaving/refreshing/discarding the wizard, which always
    preserves a resumable pending pairing -- see 'Pairing semantics' in
    docs/camera-node-pairing-persistence-design.md. This is the one path
    that actually revokes Node access.
    """

    model_config = ConfigDict(extra="forbid")

    pairing_token: str = Field(min_length=16, max_length=160)


class CameraNodePairRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream_id: str = Field(min_length=1, max_length=120)


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
    parent_media_asset_id: str | None = None
    evidence_role: str | None = None
    image_width: int | None = Field(default=None, ge=1)
    image_height: int | None = Field(default=None, ge=1)
    capture_profile_id: str | None = None
    normalized_track_box: list[float] | None = None
    normalized_padded_crop_box: list[float] | None = None
    geometry_transform_id: str | None = None
    trigger_id: str | None = None
    trigger_started_at: datetime | None = None
    capture_requested_at: datetime | None = None
    captured_at: datetime | None = None
    alignment_status: str | None = None
    alignment_failure_code: str | None = None
    normalized_crop_box: list[float] | None = None
    derived_from_visit_id: str | None = None
    derived_from_event_id: str | None = None
    derived_from_zone_id: str | None = None
    parent_image_width: int | None = Field(default=None, ge=1)
    parent_image_height: int | None = Field(default=None, ge=1)
    content_sha256: str | None = None
    derivation_source: str | None = None
    previous_effective_crop_media_asset_id: str | None = None
    # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.8 Offline
    # recorded video"): the source clip's own known duration -- honest
    # acquisition-effort provenance, never wired into monitoring coverage/
    # maturity (see "II.10 Offline vs monitoring coverage"). `None` for
    # every image and for any video whose duration ffprobe could not
    # determine.
    duration_seconds: float | None = Field(default=None, ge=0)
    # Acoustic / BirdNET Observation Foundation v1: the audio analog of
    # `image_width`/`image_height`. `None` for every image/video and for
    # any audio asset whose source metadata could not be determined.
    audio_sample_rate_hz: int | None = Field(default=None, ge=1)
    audio_channel_count: int | None = Field(default=None, ge=1)


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
    evidence_role: str = "monitoring_frame"
    normalized_crop_box: list[float] | None = None
    # Only populated when this exact frame still spans the camera's full
    # field of view and an already-proven alignment transform vouches for
    # the fraction (see `_frame_local_subject_box` in product_repository.py).
    # A derived/cropped frame (e.g. `activity_crop`) omits this rather than
    # reprojecting a box computed for a different frame's own pixels.
    normalized_track_box: list[float] | None = None
    # This asset's own persisted `GeometryAttribution.resolution_provenance`
    # (see docs/source-resolution-multi-frame-species-evidence-contract.md),
    # read back verbatim -- `None` for an asset with no recorded geometry
    # attribution (the ordinary case), never fabricated. Only `"synchronized"`
    # means a genuinely proven higher-resolution capture; the other values
    # describe temporal/identity trust, not resolution.
    resolution_provenance: (
        Literal["exact_same_frame", "synchronized", "near_time_capture", "fallback"] | None
    ) = None


class RepresentativeEvidence(BaseModel):
    """Gate C -- Representative Species Evidence v1 (see docs/representative-
    species-evidence-contract.md): the one persisted evidence image that
    currently best represents a reviewed taxon, chosen by `mockingbird.
    analytics.representative_evidence.select_representative_evidence` from
    that taxon's own confirmed Visits only. Deliberately reuses the exact
    `VisitEvidenceFrame` shape/serialization the Evidence Gallery and Bird
    Log already use -- never a second, drifting evidence representation --
    adding only the one fact a bare frame does not carry on its own: which
    Visit it belongs to. Always derived, never persisted (see "Schema" in
    the contract doc); recomputed on every report read, so a reviewed
    correction is reflected on the very next read with no backfill.

    Place Story Deep Dives & Representative Evidence v1 reuses this exact
    shape, unmodified, for a Place Feature's own representative evidence
    (`PlaceFeatureDetail.representative_evidence`) -- the candidate pool is
    every confirmed Visit across that Feature's own linked camera/Zone
    views instead of one taxon's Visits, but the selector and this response
    shape are identical, never a second "best image" concept.

    `stream_id`/`stream_name` (Multi-Camera Place Experience v2): which
    camera/view produced this winning evidence -- a human-readable name,
    never a raw UUID surfaced as the label (see product-doctrine.md). Both
    additive; `None` only in the practically-unreachable case of the
    winning Visit's own Stream row having disappeared underneath it.
    """

    visit_id: str
    evidence: VisitEvidenceFrame
    stream_id: str | None = None
    stream_name: str | None = None


class ClassifierSupportingEvidence(BaseModel):
    """Visit Same-Frame Classifier Evidence Visibility v1 (see docs/visit-
    classifier-evidence-visibility-contract.md): the real, already-persisted
    MediaAsset the species classifier actually used for this Visit's latest
    SpeciesSuggestion (Same-Frame Species Evidence v1's own `classifier_
    input` provenance, reused here, never re-resolved), reusing the exact
    same `VisitEvidenceFrame` shape/serialization as the Visit's ordinary
    evidence gallery. Present only when that asset is not already one of the
    Visit's own `evidence_frames` -- see "Avoid duplicate-image clutter" in
    the contract.

    Supporting/diagnostic evidence only: never the Visit's primary/canonical
    image, never a redefinition or alteration of the species suggestion
    itself, and never a substitute for human review/correction truth.
    """

    frame: VisitEvidenceFrame
    # The SpeciesSuggestion this evidence explains -- lets a caller with
    # more than one historical suggestion for a Visit confirm which one.
    species_suggestion_id: str
    # Mirrors `classifier_input.same_frame`/`.input_type` from the
    # suggestion's own `evidence_region_json` (Same-Frame Species Evidence
    # v1; Source-Resolution + Multi-Frame Species Evidence v1 adds a third
    # tier): whether the resolver proved this exact frame (not merely a
    # nearby one), and which resolver tier supplied it
    # (`same_frame_crop` | `persisted_crop` | `native_resolution_crop`).
    same_frame: bool | None = None
    input_type: str | None = None


class EffectivePrimaryEvidence(BaseModel):
    selected_media_asset_id: str | None = None
    persisted_primary_media_asset_id: str | None = None
    recommended_effective_primary_media_asset_id: str | None = None
    evidence_role: str | None = None
    selection_reason: str
    is_useful: bool
    is_user_controlled: bool = False
    temporally_supported: bool | None = None
    temporal_status: Literal["supported", "uncertain", "rejected"] = "uncertain"
    containment_status: bool | None = None
    edge_clipped: bool | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    candidate_count: int = Field(ge=0, le=4)
    historical_preview_only: bool = False
    would_change_automatically: bool = False


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


class RefinedCropCreateRequest(BaseModel):
    """A reviewer can submit only normalized source-image geometry."""

    model_config = ConfigDict(extra="forbid")

    left: float
    top: float
    right: float
    bottom: float


class VisitCropHistoryEntry(BaseModel):
    media_asset_id: str
    preview_url: str
    parent_media_asset_id: str
    evidence_role: str
    derivation_source: str
    normalized_crop_box: list[float] | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    created_at: datetime
    is_primary: bool
    previous_effective_crop_media_asset_id: str | None = None


class RefinedCropResponse(BaseModel):
    visit: Visit
    refined_crop: MediaAsset
    evidence_frames: list[VisitEvidenceFrame] = Field(default_factory=list)
    crop_history: list[VisitCropHistoryEntry] = Field(default_factory=list)
    stale_species_suggestions: bool = False
    created: bool = False
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


class VisitMultimodalPartnerSummary(BaseModel):
    """Everyday Discovery / Product Experience v2 (Phase B; see docs/
    multimodal-list-presentation-contract.md): the compact, list-row-safe
    counterpart to `VisitMultimodalAssociation` -- naming only the paired
    Visit's id (never the full nested `Visit`, unlike the detail-page
    version) so ordinary list summaries stay cheap. Present on a
    `StreamVisitSummary`/`WildlifeJournalObservation` only when that row's
    own `evidence_modality` is `"seen_and_heard"` (a confidently-associated
    pair collapsed into this one row) -- never for a `"possible"`
    association, which always stays two separate, uncollapsed rows."""

    visit_id: str
    tier: Literal["associated", "possible"]
    taxon_agreement: Literal["agrees", "differs", "not_comparable"]


class VisitCrossCameraPartnerSummary(BaseModel):
    """Camera / Source + Multi-Camera Maturity v1, Phase I: the compact,
    list-row-safe counterpart to `VisitCrossCameraAssociation` -- mirrors
    `VisitMultimodalPartnerSummary`'s own shape exactly, plus the one fact
    that actually matters for a cross-camera (not cross-modality) pair: which
    *other* camera/Area this row's evidence was also captured on. Present on
    a `StreamVisitSummary`/`WildlifeJournalObservation` only when a
    confidently-`"associated"` pair was collapsed into this one row for
    presentation -- a `"possible"` association always stays two separate,
    uncollapsed rows, exactly like the multimodal case. Independent of
    `evidence_modality`/`multimodal_partner`: a row can have either, both, or
    neither -- they answer different questions (what modality; which other
    camera)."""

    visit_id: str
    tier: Literal["associated", "possible"]
    taxon_agreement: Literal["agrees", "differs", "not_comparable"]
    other_source_name: str
    other_stream_name: str


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
    # Everyday Discovery / Product Experience v2 (Phase B): this Visit's own
    # recording modality -- always "visual" or "acoustic" as resolved from
    # its Event, *unless* a caller that opts into presentation-level
    # multimodal collapse (Today's `best_moments`/`recent_activity`, Bird
    # Log's gallery -- see `_collapse_associated_multimodal_pairs`) merged a
    # confidently-associated opposite-modality partner into this row, in
    # which case it is "seen_and_heard" and `multimodal_partner` names the
    # (still independently real, never deleted) Visit it absorbed. Ordinary
    # callers that never opt into collapse always see plain "visual"/
    # "acoustic" and a `None` `multimodal_partner`.
    evidence_modality: Literal["visual", "acoustic", "seen_and_heard"] = "visual"
    multimodal_partner: VisitMultimodalPartnerSummary | None = None
    # Camera / Source + Multi-Camera Maturity v1, Phase I/H: set only when a
    # confidently-associated same-encounter Visit from a *different* camera
    # was collapsed into this row -- see `VisitCrossCameraPartnerSummary`'s
    # own docstring. Independent of `multimodal_partner` above.
    cross_camera_partner: VisitCrossCameraPartnerSummary | None = None


class ActivityLibraryReviewFilter(str, Enum):
    all = "all"
    needs_review = "needs_review"
    reviewed_observation = "reviewed_observation"
    confirmed_wildlife = "confirmed_wildlife"
    non_bird = "non_bird"
    blank_false = "blank_false"
    blank = "blank"
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
    favorites_only: bool = False
    has_note: bool | None = None
    collection_id: str | None = Field(default=None, min_length=1, max_length=256)
    oldest_first: bool = False
    tag_id: str | None = Field(default=None, min_length=1, max_length=256)
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
    # Camera Node's canonical ObservationEngineSessionManager truth, bridged
    # in so the aggregate camera-health summary can distinguish a genuinely
    # terminal engine failure from a Stream that was simply never armed
    # (which a camera_node Stream, by design, can never be through
    # StreamMonitoringPolicy). See "_camera_health_summary_from_models".
    engine_terminally_unavailable: bool = False
    engine_unavailable_message: str | None = None


class DashboardVisitSummary(StreamVisitSummary):
    # Product context for a compact cross-Stream Visit row; evidence stays bounded.
    stream_name: str
    source_id: str
    source_name: str


class DashboardZoneOverlay(BaseModel):
    """Read-only normalized geometry for one Stream's overview tile."""

    id: str
    stream_id: str
    name: str
    zone_type: ZoneType
    polygon: list[Point] = Field(default_factory=list, max_length=32)
    is_active: bool


class DashboardLivePreview(BaseModel):
    """Safe capability metadata; it never includes source configuration or secrets."""

    kind: DashboardLivePreviewKind = DashboardLivePreviewKind.unavailable
    available: bool = False
    media_kind: Literal["image", "video"] = "image"
    preview_url: str | None = None
    message: str


class DashboardStreamSummary(BaseModel):
    stream_id: str
    stream_name: str
    source_id: str
    source_name: str
    source_kind: SourceKind
    source_status: SourceStatus
    setup_incomplete: bool = False
    availability_status: StreamPlaybackStatusValue
    playback_kind: StreamPlaybackKind = StreamPlaybackKind.placeholder
    availability_message: str
    live_preview: DashboardLivePreview
    zone_overlays: list[DashboardZoneOverlay] = Field(default_factory=list, max_length=32)
    monitoring_active: bool = False
    monitor_control: str = "none"
    can_start_monitor: bool = False
    can_stop_monitor: bool = False
    open_activity_session_count: int = Field(default=0, ge=0)
    ready_activity_session_count: int = Field(default=0, ge=0)
    needs_review_visit_count: int = Field(default=0, ge=0)
    latest_visit: DashboardVisitSummary | None = None
    camera_health: CameraHealthSummary | None = None


class DashboardReviewedObservation(BaseModel):
    # One reviewed label grouping; suggestions never reach this serializer.
    label: str
    display_name: str
    category: LabelCategory
    observation_count: int = Field(ge=1)
    latest_visit: DashboardVisitSummary


class DashboardHeadline(BaseModel):
    configured_stream_count: int = Field(ge=0)
    # Same population as `configured_stream_count` minus any Source whose
    # *current* provider configuration is still literally unconfigured
    # (`provider_key == "demo"`) -- a durable, already-present semantic
    # distinction (the same field `engine_active`/`live_active`/
    # `source_active` already gate on), not a display-name/fixture-identity
    # special case, and not the Source's own `kind` (which never updates
    # once set, so it cannot tell a still-inert demo Source from one later
    # repurposed into a real camera). Only `ProductHealthObservationSummary`'s
    # "Observing X of Y cameras" ratio uses this; `configured_stream_count`
    # itself is unchanged everywhere else (including TodayReportPanel's own
    # "do you have anything configured at all" empty-state gate, where the
    # demo Stream legitimately counts as something to explore -- excluding
    # it there would misrepresent intentional demo mode as "nothing
    # configured").
    real_stream_count: int = Field(ge=0)
    monitored_stream_count: int = Field(ge=0)
    open_activity_session_count: int = Field(ge=0)
    needs_review_visit_count: int = Field(ge=0)
    actionable_animal_visit_count: int = Field(default=0, ge=0)
    legacy_activity_count: int = Field(default=0, ge=0)
    reviewed_observation_count_today: int = Field(ge=0)


class DashboardTodaySpecies(BaseModel):
    """A species occurrence grouped for the selected local day.

    `is_confirmed=True` (the default, and the only value `new_today`/
    `recent_regulars` ever use) means every Visit behind this group carries
    authoritative human-reviewed truth. `is_confirmed=False` marks a
    provisional group (`likely_today`) built entirely from an automatic,
    unreviewed BioCLIP suggestion -- useful and shown by default, but never
    reviewed truth; see the Automatic Species Suggestion v1 milestone.
    """

    label: str
    display_name: str
    distinct_days_seen: int = Field(default=1, ge=1, le=14)
    latest_visit: DashboardVisitSummary
    is_confirmed: bool = True
    # Canonical New/Regular Species v1 (Everyday Discovery / Product
    # Experience v2; see docs/canonical-new-regular-species-contract.md): the
    # exact same `SpeciesHistoricalStatusValue` the Place Activity Report
    # digest and Bird Log use, so `new_today`/`recent_regulars` word "new"
    # vs. "first record" identically to every other surface instead of a
    # single fixed caption regardless of Place baseline maturity. Always
    # `None` for `likely_today` (provisional, never establishes history).
    historical_status: Literal["new", "first_record", "regular", "seen_before"] | None = None


class DashboardTodayZoneActivity(BaseModel):
    zone_id: str | None = None
    zone_name: str = "No Zone"
    animal_visit_count: int = Field(ge=1)


class DashboardTodayHourActivity(BaseModel):
    hour: int = Field(ge=0, le=23)
    animal_visit_count: int = Field(ge=0)


class DashboardTodaySummary(BaseModel):
    """Bounded, read-only nature discovery facts for one selected local day."""

    detector_qualified_animal_visit_count: int = Field(ge=0)
    confirmed_bird_visit_count: int = Field(ge=0)
    confirmed_species_count: int = Field(ge=0)
    unresolved_animal_visit_count: int = Field(ge=0)
    best_moments: list[DashboardVisitSummary] = Field(default_factory=list, max_length=6)
    new_today: list[DashboardTodaySpecies] = Field(default_factory=list, max_length=12)
    recent_regulars: list[DashboardTodaySpecies] = Field(default_factory=list, max_length=12)
    # Automatic Species Suggestion v1: unreviewed today's Visits grouped by
    # their top-1 BioCLIP suggestion. Additive and separate from
    # `new_today`/`recent_regulars`, which stay confirmed-truth-only exactly
    # as before -- Today is useful without requiring review first, while
    # "new species this year"-style history stays tied to real truth.
    likely_today: list[DashboardTodaySpecies] = Field(default_factory=list, max_length=12)
    activity_by_zone: list[DashboardTodayZoneActivity] = Field(default_factory=list, max_length=50)
    activity_by_hour: list[DashboardTodayHourActivity] = Field(default_factory=list, max_length=24)
    needs_help: list[DashboardVisitSummary] = Field(default_factory=list, max_length=3)
    observation_health: list[CameraHealthSummary] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=4)


class DashboardSummary(BaseModel):
    # Bounded daily operations surface; never a full Visit-detail payload.
    local_day: str
    generated_at: datetime
    headline: DashboardHeadline
    today: DashboardTodaySummary
    streams: list[DashboardStreamSummary] = Field(default_factory=list, max_length=50)
    needs_review_visits: list[DashboardVisitSummary] = Field(
        default_factory=list,
        max_length=12,
    )
    actionable_animal_visits: list[DashboardVisitSummary] = Field(
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
    camera_attention: list[CameraHealthSummary] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=12)


class ActivityLibraryVisitSummary(DashboardVisitSummary):
    # Structural curation is provenance context, never a second review truth.
    curation_actions: list[str] = Field(default_factory=list, max_length=8)
    is_favorite: bool = False
    has_note: bool = False
    collection_count: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    tag_count: int = Field(default=0, ge=0)


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
    | dict[str, MotionEvidenceFrameConfigValue]
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
            raise ValueError(
                "end_frame_index must be greater than or equal to start_frame_index"
            )

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
    session_debug: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )
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
    detector_preset: Literal["high_sensitivity", "normal", "low_noise"] = "normal"
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
    auto_identify_review_candidates: bool = False
    auto_review_quiet_seconds: int = Field(default=30, ge=1, le=300)
    auto_review_min_detections: int = Field(default=1, ge=1, le=100)


class LiveMotionMonitorSettingsRequest(BaseModel):
    auto_create_review_candidates: bool = False
    auto_identify_review_candidates: bool = False
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
    detector_preset: Literal["high_sensitivity", "normal", "low_noise"] = "normal"
    source_frame_width: int | None = Field(default=None, ge=1)
    source_frame_height: int | None = Field(default=None, ge=1)
    analysis_frame_width: int | None = Field(default=None, ge=1)
    analysis_frame_height: int | None = Field(default=None, ge=1)
    zone_source_crop_width: int | None = Field(default=None, ge=1)
    zone_source_crop_height: int | None = Field(default=None, ge=1)
    analysis_zone_id: str | None = None
    analysis_frame_identity: str | None = None
    analysis_frame_age_ms: int | None = Field(default=None, ge=0)
    duplicate_frame_count: int = Field(default=0, ge=0)
    dropped_frame_count: int = Field(default=0, ge=0)
    frozen_frame_count: int = Field(default=0, ge=0)
    foreground_model_state: str | None = None
    foreground_mask_available: bool = False
    foreground_mask_data_url: str | None = None
    global_illumination_suppressed: bool = False
    latest_ignored_frame_reason: str | None = None
    motion_regions: list[dict[str, Any]] = Field(default_factory=list)
    tracked_objects: list[dict[str, Any]] = Field(default_factory=list)
    activity_triggers: list[dict[str, Any]] = Field(default_factory=list)
    object_detector_available: bool = False
    object_detector_unavailable_reason: str | None = None
    object_detector_zone_id: str | None = None
    object_detector_zone_source_crop_width: int | None = Field(default=None, ge=1)
    object_detector_zone_source_crop_height: int | None = Field(default=None, ge=1)
    object_detector_input_width: int | None = Field(default=None, ge=1)
    object_detector_input_height: int | None = Field(default=None, ge=1)
    object_detector_boxes: list[dict[str, Any]] = Field(default_factory=list)
    object_detector_tracks: list[dict[str, Any]] = Field(default_factory=list)
    object_detector_triggers: list[dict[str, Any]] = Field(default_factory=list)
    object_detector_cadence_seconds: float | None = Field(default=None, ge=0)
    object_detector_inference_latency_ms: int | None = Field(default=None, ge=0)
    object_detector_queue_depth: int = Field(default=0, ge=0)
    object_detector_queue_capacity: int = Field(default=1, ge=1)
    object_detector_dropped_frame_count: int = Field(default=0, ge=0)
    object_detector_stale_frame_count: int = Field(default=0, ge=0)
    object_detector_timed_out_count: int = Field(default=0, ge=0)
    object_detector_runtime_state: Literal["ready", "loading", "running", "delayed", "timed_out", "recovering", "unavailable"] = "ready"
    object_detector_model_configuration_state: str = "unknown"
    object_detector_model_loaded: bool = False
    object_detector_worker_alive: bool = False
    object_detector_in_flight_job_identity: str | None = None
    object_detector_in_flight_age_ms: int | None = Field(default=None, ge=0)
    object_detector_last_submitted_at: datetime | None = None
    object_detector_last_completed_at: datetime | None = None
    object_detector_last_completed_age_ms: int | None = Field(default=None, ge=0)
    object_detector_latest_successful_inference_latency_ms: int | None = Field(default=None, ge=0)
    object_detector_worker_reset_count: int = Field(default=0, ge=0)
    object_detector_recovery_count: int = Field(default=0, ge=0)
    object_detector_queue_replacement_count: int = Field(default=0, ge=0)
    object_detector_execution_device: str | None = None
    object_detector_last_safe_error_category: str | None = None
    object_detector_runtime_generation: int = Field(default=0, ge=0)
    object_detector_admission_observability_available: bool = False
    object_detector_admission_runtime_generation: int = Field(default=0, ge=0)
    object_detector_admission_counters: dict[str, int] = Field(default_factory=dict)
    object_detector_current_admission_candidates: list[dict[str, Any]] = Field(default_factory=list)
    object_detector_recent_admission_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    object_detector_last_admission_decision_at: datetime | None = None
    object_detector_last_successful_promotion_at: datetime | None = None
    activity_trigger_source: Literal["object_verified", "motion_fallback"] | None = None
    selected_evidence_profile_id: str | None = None
    high_resolution_capture_status: str | None = None
    high_resolution_frame_width: int | None = Field(default=None, ge=1)
    high_resolution_frame_height: int | None = Field(default=None, ge=1)
    high_resolution_crop_width: int | None = Field(default=None, ge=1)
    high_resolution_crop_height: int | None = Field(default=None, ge=1)
    high_resolution_alignment_status: str | None = None
    high_resolution_alignment_failure_code: str | None = None
    high_resolution_capture_failure_code: str | None = None
    high_resolution_capture_latency_ms: int | None = Field(default=None, ge=0)
    high_resolution_track_to_capture_delay_ms: int | None = Field(default=None, ge=0)
    high_resolution_track_box: list[float] | None = None
    high_resolution_padded_crop_box: list[float] | None = None
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
    activity_subject_state: str | None = None
    activity_promotion_category: str | None = None
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
    auto_identify_review_candidates: bool = False
    automatic_identification_status: AutomaticIdentificationStatus = (
        AutomaticIdentificationStatus.off
    )
    last_auto_identification_target_id: str | None = None
    last_auto_identification_attempt_id: str | None = None
    last_auto_identification_suggestion_id: str | None = None
    last_auto_identification_message: str | None = None
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
    candidate_pack: SpeciesCandidatePackSummary | None = None
    candidate_pack_warning: str | None = None
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
    # Acoustic / BirdNET Observation Foundation v1: the temporal analog of
    # `evidence_region` -- which bounded window of the source audio clip
    # this suggestion came from. `None` for an image-backed suggestion
    # (unchanged); any adapter may populate `model_provenance` (not
    # audio-specific by construction) -- an adapter-neutral provenance
    # object (model name/version/license, runtime identity, resolved
    # config, source evidence content hash).
    window_start_ms: int | None = Field(default=None, ge=0)
    window_end_ms: int | None = Field(default=None, ge=0)
    model_provenance: dict[str, Any] | None = None

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

    @field_validator("model_provenance")
    @classmethod
    def model_provenance_must_be_json_compatible(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None:
            _ensure_json_compatible(value, "model_provenance")
        return value

    @model_validator(mode="after")
    def window_end_not_before_start(self) -> "SpeciesSuggestionCreateRequest":
        if (
            self.window_start_ms is not None
            and self.window_end_ms is not None
            and self.window_end_ms < self.window_start_ms
        ):
            raise ValueError("window_end_ms must not be before window_start_ms")
        return self


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
    window_start_ms: int | None = None
    window_end_ms: int | None = None
    model_provenance: dict[str, Any] | None = None


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
    candidate_pack: SpeciesCandidatePackSummary | None = None
    candidate_pack_warning: str | None = None


class ReviewIdentificationRequest(BaseModel):
    adapter_id: str | None = None
    media_asset_id: str | None = None
    requested_labels: list[str] | None = None
    notes: str | None = None


class VisitIdentificationEvidenceMode(str, Enum):
    """Legacy request values; the assistant resolves one effective saved input."""

    primary_only = "primary_only"
    all_retained_evidence = "all_retained_evidence"


class VisitIdentificationAssistantRequest(BaseModel):
    """An explicit, one-Visit request for optional local suggestion evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_mode: VisitIdentificationEvidenceMode = (
        VisitIdentificationEvidenceMode.primary_only
    )
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitIdentificationAssistantResponse(BaseModel):
    # All outputs remain evidence. The established correction endpoints create truth.
    visit_id: str
    availability: ReviewIdentificationSummary
    evidence_mode: VisitIdentificationEvidenceMode
    selected_evidence_frames: list[VisitEvidenceFrame] = Field(default_factory=list)
    run: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    message: str
    creates_truth: bool = False
    creates_export: bool = False


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
    # Read-only presentation guidance. It never changes a Visit's persisted
    # primary link, evidence, review state, or dataset-grade correction.
    effective_primary: EffectivePrimaryEvidence | None = None
    stale_species_suggestions: bool = False
    review_status: ReviewStatus
    # Everyday Product / Discovery UX Closure v1: the current authoritative label,
    # so the Reviewed tab can say what a card was actually reviewed as instead of
    # an undifferentiated "Reviewed activity" for every card. `None` while
    # `review_status` is still `needs_review`; present once reviewed.
    reviewed_label: str | None = None
    review_state_token: str = ""
    reason: str
    # Product Mode is derived from durable source and detector provenance. It is
    # presentation metadata only: none of these fields can create review truth.
    product_category: Literal[
        "animal",
        "other_activity",
        "unchecked",
        "legacy_activity",
        "reviewed",
    ] = "unchecked"
    detector_class: Literal["animal", "person", "vehicle"] | None = None
    detector_score: float | None = Field(default=None, ge=0, le=1)
    track_generation_id: str | None = None
    detector_provenance: dict[str, Any] | None = None
    captured_at: datetime | None = None
    evidence_count: int = Field(default=0, ge=0)
    is_demo_source: bool = False
    is_legacy_activity: bool = False


class ReviewLabel(BaseModel):
    # Review labels are dataset-grade truth candidates that can override
    # detections -- but see `is_authoritative` below: only some origins are
    # actually eligible to establish or correct durable reviewed truth (see
    # docs/review-decision-provenance-contract.md).
    id: str
    target_type: str
    target_id: str
    label: str
    notes: str | None = None
    created_at: datetime
    # `None` means a create request made after this field existed omitted
    # it. A row that predates this field entirely reads back the explicit
    # `"legacy_unattributed"` sentinel instead (backfilled once by the
    # schema migration) -- never `None` and never a fabricated "human".
    review_origin: ReviewOriginStored | None = None
    reviewer_identity: str | None = None
    # Local Identity, Multi-User & Organization Access v1: the durable
    # actor reference `reviewer_identity` (a free-text display string) was
    # explicitly documented as never having. `None` for every row created
    # before user identity existed, or by a non-interactive/offline
    # pathway with no signed-in user -- never fabricated. See
    # `ReviewLabelModel.reviewed_by_user_id`.
    reviewed_by_user_id: str | None = None
    # Server-computed from `review_origin` via `mockingbird.review_
    # provenance.is_authority_eligible` -- never client-supplied directly,
    # so a caller cannot simply assert authority without an eligible
    # origin. This is the one field API/frontend consumers should check
    # before treating a Review Decision as reviewed observational truth.
    is_authoritative: bool


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
    # Explicit provenance at the creation boundary (Part 4): omitting this
    # field NEVER defaults to "human" -- it is recorded as no-explicit-
    # origin and is not authority-eligible for this new row. The product's
    # own interactive review UI sets this explicitly to "human" on every
    # request it issues; it is not inferred from the absence of any other
    # signal. See docs/review-decision-provenance-contract.md.
    review_origin: ReviewOrigin | None = None
    reviewer_identity: str | None = Field(default=None, max_length=256)
    # Local Identity, Multi-User & Organization Access v1: optional so
    # every existing non-interactive caller (bulk-correct's internal reuse
    # of this same schema shape, demo-seed data, offline/CLI callers) is
    # entirely unaffected -- omitting it preserves today's exact last-
    # write-wins behavior. The product's own interactive single-Visit
    # review UI always supplies the `review_state_token` it just fetched;
    # see `mockingbird.api.main.create_review_label`, which enforces a
    # mismatch as HTTP 409 exactly like `VisitReviewRevisionCreate` already
    # does below -- reusing that same tested mechanism rather than adding
    # a second one.
    expected_state_token: str | None = Field(default=None, min_length=1, max_length=256)


class VisitReviewRevisionCreate(BaseModel):
    """Replace the current reviewed Visit truth without changing its history."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=256)
    notes: str | None = Field(default=None, max_length=4000)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)
    review_origin: ReviewOrigin | None = None
    reviewer_identity: str | None = Field(default=None, max_length=256)


class VisitReviewReopenCreate(BaseModel):
    """Deliberately remove current reviewed truth and return the Visit to review."""

    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=4000)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)
    review_origin: ReviewOrigin | None = None
    reviewer_identity: str | None = Field(default=None, max_length=256)


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
    review_origin: ReviewOrigin | None = None
    reviewer_identity: str | None = Field(default=None, max_length=256)


class ReviewQueueBulkCorrectionRequest(BaseModel):
    target_ids: list[str]
    target_type: ReviewQueueBulkCorrectionTargetType
    label: str
    notes: str | None = None
    review_origin: ReviewOrigin | None = None
    reviewer_identity: str | None = Field(default=None, max_length=256)
    # Local Identity, Multi-User & Organization Access v1 (bulk-correct
    # concurrency closure): optional `target_id -> expected_state_token`
    # map, reusing the exact same `_review_state_token`/
    # `ReviewRevisionConflictError` mechanism `ReviewCorrectionCreate.
    # expected_state_token` already uses for the single-item path -- see
    # that field's own docstring for why it stays optional rather than
    # required. A `target_id` present here is checked immediately before
    # its own write is attempted; on a mismatch, that one item alone is
    # rejected as a `failed` result (`ProductRepository.bulk_correct_
    # review_queue_items`) -- the rest of the batch is unaffected, exactly
    # like every other per-item failure this endpoint already tolerates.
    # A `target_id` absent from this map (or the map omitted entirely) is
    # never checked, preserving today's exact last-write-wins behavior for
    # that item -- so every existing caller that omits this field is
    # entirely unaffected.
    expected_state_tokens: dict[str, str] | None = None


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



class ReviewQueueSpeciesSuggestionBatchPrepareRequest(BaseModel):
    """Validate up to 25 unresolved Visit targets before client-side sequencing."""

    model_config = ConfigDict(extra="forbid")

    visit_ids: list[str] = Field(min_length=1, max_length=25)


class ReviewQueueSpeciesSuggestionBatchPrepareResult(BaseModel):
    visit_id: str
    status: ReviewQueueSpeciesSuggestionBatchPrepareStatus
    message: str
    media_asset_id: str | None = None
    candidate_pack: SpeciesCandidatePackSummary | None = None
    candidate_pack_warning: str | None = None


class ReviewQueueSpeciesSuggestionBatchPrepareResponse(BaseModel):
    # This preflight selects no model and creates no product or truth records.
    requested_count: int = Field(ge=0, le=25)
    queued_count: int = Field(ge=0, le=25)
    skipped_count: int = Field(ge=0, le=25)
    setup_required_count: int = Field(ge=0, le=25)
    results: list[ReviewQueueSpeciesSuggestionBatchPrepareResult]
    creates_truth: bool = False
    creates_export: bool = False


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
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
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
    planned_media_files: list[ClassifierManifestPlannedMediaFile] = Field(
        default_factory=list
    )
    skipped_media: list[ClassifierManifestSkippedMediaRecord] = Field(
        default_factory=list
    )
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


class ResearchClassification(str, Enum):
    """Mirrors `mockingbird.research.eligibility.ResearchRecordClassification`
    exactly -- see docs/research-conservation-export-contract.md "Research-
    safe eligibility"."""

    confirmed_taxon = "confirmed_taxon"
    confirmed_unidentified_wildlife = "confirmed_unidentified_wildlife"
    non_wildlife = "non_wildlife"
    provisional_suggestion = "provisional_suggestion"
    unresolved = "unresolved"
    rejected = "rejected"
    superseded = "superseded"


class ResearchEligibility(BaseModel):
    classification: ResearchClassification
    eligible: bool
    eligible_as_named_taxon: bool
    eligible_as_unidentified_wildlife: bool
    required_reasons: list[str] = Field(default_factory=list)
    recommended_reasons: list[str] = Field(default_factory=list)


class ResearchEvidence(BaseModel):
    # Never a local filesystem path -- mirrors VisitEvidenceFrame's own rule.
    media_id: str
    evidence_role: str
    captured_at: datetime | None = None
    width: int | None = None
    height: int | None = None
    content_type: str
    resolution_provenance: str | None = None
    is_crop: bool
    content_sha256: str | None = None


class ResearchObservationRecord(BaseModel):
    """One provider-neutral research-safe exported Observation (see
    "Provenance contract" in the governing milestone brief). A Camera Node,
    generic RTSP, ONVIF, or offline/recorded-media Visit all produce this
    identical shape -- only `acquisition_type`/`acquisition_provider` vary."""

    observation_id: str
    event_id: str
    source_id: str
    source_name: str
    stream_id: str
    stream_name: str

    acquisition_type: Literal["continuous_live", "recorded_video", "still_image", "unknown"]
    acquisition_provider: str | None = None
    is_offline_acquisition: bool

    captured_at: datetime
    captured_at_end: datetime | None = None
    capture_timestamp_confidence: Literal["recorded", "unknown"]

    review_status: ReviewStatus
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None

    classification: ResearchClassification
    taxon_label: str | None = None
    taxon_display_name: str | None = None
    taxon_scientific_name: str | None = None
    taxon_category: LabelCategory | None = None
    is_species: bool | None = None

    zone_id: str | None = None
    zone_name: str | None = None
    zone_type: ZoneType | None = None

    resolution_provenance: str | None = None
    evidence: list[ResearchEvidence] = Field(default_factory=list)

    eligibility: ResearchEligibility

    suggested_taxon_label: str | None = None
    suggested_taxon_display_name: str | None = None
    suggested_taxon_scientific_name: str | None = None
    suggested_by: str | None = None
    suggested_confidence: float | None = None


class ResearchExportFilters(BaseModel):
    """Bounded export filters (see "Export filters" in the governing
    milestone brief) -- deliberately not a general query language."""

    model_config = ConfigDict(extra="forbid")

    start_at: datetime | None = None
    end_at: datetime | None = None
    stream_ids: list[str] | None = Field(default=None, max_length=50)
    source_ids: list[str] | None = Field(default=None, max_length=50)
    taxon_labels: list[str] | None = Field(default=None, max_length=100)
    acquisition_scope: Literal["live", "offline", "both"] = "both"
    collection_id: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "ResearchExportFilters":
        if self.start_at is not None and self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ResearchExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filters: ResearchExportFilters = Field(default_factory=ResearchExportFilters)
    include_media: bool = False
    dry_run: bool = False
    output_name: str | None = None

    @field_validator("output_name")
    @classmethod
    def validate_output_name(cls, value: str | None) -> str | None:
        return _validate_export_output_name(value)


class ResearchExportManifest(BaseModel):
    """Reproducibility metadata every research export carries (see
    "Versioning / reproducibility" in the governing milestone brief)."""

    schema_version: str
    export_id: str
    generated_at: datetime
    application_version: str | None = None
    eligibility_policy_version: str
    filters: ResearchExportFilters
    source_ids: list[str] = Field(default_factory=list)
    observation_count: int = Field(ge=0)
    media_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    excluded_reasons: dict[str, int] = Field(default_factory=dict)
    content_fingerprint: str


class ResearchExportResponse(BaseModel):
    export_id: str
    output_directory: str | None = None
    files: list[ClassifierManifestExportFile] = Field(default_factory=list)
    observation_count: int = Field(ge=0)
    media_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    excluded_reasons: dict[str, int] = Field(default_factory=dict)
    manifest: ResearchExportManifest
    dry_run: bool


class CamtrapDpExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filters: ResearchExportFilters = Field(default_factory=ResearchExportFilters)
    include_media: bool = False
    site_name: str | None = Field(default=None, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    include_machine_classifications: bool = True
    dry_run: bool = False
    output_name: str | None = None

    @field_validator("output_name")
    @classmethod
    def validate_output_name(cls, value: str | None) -> str | None:
        return _validate_export_output_name(value)


class CamtrapDpValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CamtrapDpExportResponse(BaseModel):
    export_id: str
    output_directory: str | None = None
    files: list[ClassifierManifestExportFile] = Field(default_factory=list)
    profile_version: str
    deployment_count: int = Field(ge=0)
    media_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    validation: CamtrapDpValidation
    dry_run: bool


class ConservationSpeciesEntry(BaseModel):
    label: str
    display_name: str
    scientific_name: str | None = None
    is_species: bool
    confirmed_visit_count: int = Field(ge=0)
    occurrence_day_count: int = Field(ge=0)
    first_confirmed_at: datetime
    last_confirmed_at: datetime
    occurrence_note: str | None = None


class ConservationReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: datetime
    end_at: datetime
    stream_ids: list[str] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_range(self) -> "ConservationReportRequest":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ConservationReportResponse(BaseModel):
    """Bounded conservation/natural-history report (see "Conservation
    Reporting v1" in the governing milestone brief). Never claims
    abundance, population size, occupancy, a biodiversity index, ecological
    significance, or a decline/increase trend -- no such field exists here."""

    period_start_at: datetime
    period_end_at: datetime
    generated_at: datetime
    maturity: Literal["no_data", "sparse", "usable"]

    live_monitoring_monitored_seconds: float | None = None
    live_monitoring_usable_day_count: int | None = None

    offline_recorded_video_count: int = Field(ge=0)
    offline_recorded_video_analyzed_seconds: float = Field(ge=0)
    offline_recorded_video_unknown_duration_count: int = Field(ge=0)
    offline_still_image_count: int = Field(ge=0)
    # Acoustic / BirdNET Observation Foundation v1: the audio analog of the
    # recorded-video fields above.
    offline_recorded_audio_count: int = Field(default=0, ge=0)
    offline_recorded_audio_analyzed_seconds: float = Field(default=0.0, ge=0)
    offline_recorded_audio_unknown_duration_count: int = Field(default=0, ge=0)

    confirmed_species: list[ConservationSpeciesEntry] = Field(default_factory=list)
    confirmed_unidentified_wildlife_visit_count: int = Field(ge=0)
    reviewed_wildlife_visit_count: int = Field(ge=0)
    provisional_wildlife_visit_count: int = Field(ge=0)
    unresolved_visit_count: int = Field(ge=0)
    total_visit_count: int = Field(ge=0)

    first_activity_at: datetime | None = None
    last_activity_at: datetime | None = None

    confirmed_wildlife_visits_with_evidence_count: int = Field(ge=0)


class ResearchCollectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    curator_identity: str | None = Field(default=None, max_length=200)
    visit_ids: list[str] = Field(min_length=1, max_length=500)

    @field_validator("visit_ids")
    @classmethod
    def validate_visit_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if not all(normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("visit_ids must be unique non-empty Visit IDs")
        return normalized


class ResearchCollection(BaseModel):
    id: str
    name: str
    description: str | None = None
    curator_identity: str | None = None
    visit_ids: list[str]
    eligibility_policy_version: str
    created_at: datetime
    updated_at: datetime
    eligible_observation_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)


class ResearchCollectionSummary(BaseModel):
    id: str
    name: str
    curator_identity: str | None = None
    visit_count: int = Field(ge=0)
    created_at: datetime


class DarwinCoreExportRequest(BaseModel):
    """Bounded Darwin Core Occurrence-core export (Phase 29 of the
    Ecological Interoperability & Submission Workflows v1 milestone brief)
    -- mirrors `CamtrapDpExportRequest` exactly, including the same
    never-inferred location fields."""

    model_config = ConfigDict(extra="forbid")

    filters: ResearchExportFilters = Field(default_factory=ResearchExportFilters)
    site_name: str | None = Field(default=None, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_uncertainty_meters: float | None = Field(default=None, ge=0)
    dry_run: bool = False
    output_name: str | None = None

    @field_validator("output_name")
    @classmethod
    def validate_output_name(cls, value: str | None) -> str | None:
        return _validate_export_output_name(value)


class DarwinCoreExportResponse(BaseModel):
    export_id: str
    output_directory: str | None = None
    files: list[ClassifierManifestExportFile] = Field(default_factory=list)
    schema_version: str
    occurrence_count: int = Field(ge=0)
    dry_run: bool


# ---------------------------------------------------------------------------
# Ecological Interoperability & Submission Workflows v1 (see docs/ecological-
# interoperability-submission-v1-contract.md). A distinct concept from the
# research-export family above: preparing/tracking a Reviewed Visit's
# submission to a specific named external ecological destination
# (iNaturalist today; eBird deliberately not offered -- see "Destination
# decisions"), rather than a generic dataset/standards export. Composes the
# research-eligibility gate and `ResearchObservation` above; never a second
# truth system.
# ---------------------------------------------------------------------------


class EcologicalDestinationInfo(BaseModel):
    key: Literal["inaturalist", "ebird"]
    display_name: str
    offered: bool
    offered_reason: str | None = None


class EcologicalLocationInput(BaseModel):
    """An explicit, never-defaulted location choice (see "Location is a
    separate consent boundary" in the governing contract doc) -- never
    silently reused from `EnvironmentalContextSettingsModel`'s coarse
    weather coordinate."""

    model_config = ConfigDict(extra="forbid")

    choice: Literal["none", "coarse", "exact"] = "none"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    place_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_choice_matches_coordinates(self) -> "EcologicalLocationInput":
        has_coordinates = self.latitude is not None and self.longitude is not None
        if self.choice == "none" and has_coordinates:
            raise ValueError("choice='none' must not carry a latitude/longitude")
        if self.choice in ("coarse", "exact") and not has_coordinates:
            raise ValueError(f"choice={self.choice!r} requires both latitude and longitude")
        return self


class EcologicalMediaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: Literal["none", "metadata_only"] = "none"
    media_asset_id: str | None = None

    @model_validator(mode="after")
    def validate_policy_matches_asset(self) -> "EcologicalMediaInput":
        if self.policy == "none" and self.media_asset_id is not None:
            raise ValueError("policy='none' must not carry a media_asset_id")
        if self.policy == "metadata_only" and self.media_asset_id is None:
            raise ValueError("policy='metadata_only' requires a media_asset_id")
        return self


class EcologicalEligibilityPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: Literal["inaturalist", "ebird"]
    filters: ResearchExportFilters = Field(default_factory=ResearchExportFilters)


class EcologicalEligibilityPreviewItem(BaseModel):
    visit_id: str
    classification: str
    taxon_label: str | None = None
    taxon_display_name: str | None = None
    captured_at: datetime
    status: Literal["eligible", "needs_input", "excluded"]
    needs_input_reasons: list[str] = Field(default_factory=list)
    excluded_reasons: list[str] = Field(default_factory=list)


class EcologicalEligibilityPreviewResponse(BaseModel):
    destination: EcologicalDestinationInfo
    items: list[EcologicalEligibilityPreviewItem] = Field(default_factory=list)
    eligible_count: int = Field(ge=0)
    needs_input_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)


class PrepareEcologicalSubmissionsRequest(BaseModel):
    """Batch prepare (Phase 20): one explicit location/media choice applied
    uniformly to every selected Visit, mirroring `CamtrapDpExportRequest`'s
    identical one-site-level-override-per-call convention. Explicit user
    selection required -- never "everything reviewed" (Phase 20)."""

    model_config = ConfigDict(extra="forbid")

    visit_ids: list[str] = Field(min_length=1, max_length=500)
    destination: Literal["inaturalist", "ebird"]
    location: EcologicalLocationInput = Field(default_factory=EcologicalLocationInput)
    media: EcologicalMediaInput = Field(default_factory=EcologicalMediaInput)

    @field_validator("visit_ids")
    @classmethod
    def validate_visit_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if not all(normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("visit_ids must be unique non-empty Visit IDs")
        return normalized


class EcologicalSubmissionRecord(BaseModel):
    id: str
    visit_id: str
    destination: Literal["inaturalist", "ebird"]
    status: Literal["prepared", "needs_input", "excluded", "exported", "submitted"]
    #: Computed fresh at read time by comparing this record's stored
    #: `content_fingerprint` against a fresh rebuild from current truth --
    #: never a stored/cached flag (Phase 32: "MockingBird has been corrected
    #: since this external submission" must always reflect *current* truth).
    is_stale: bool = False
    content_fingerprint: str
    taxon_label: str | None = None
    taxon_scientific_name: str | None = None
    destination_taxon_id: str | None = None
    destination_taxon_match_status: Literal["matched", "ambiguous", "not_found"] | None = None
    taxonomy_mapping_version: str | None = None
    location_choice: Literal["none", "coarse", "exact"]
    location_latitude: float | None = None
    location_longitude: float | None = None
    location_place_name: str | None = None
    media_policy: Literal["none", "metadata_only"]
    media_selection_asset_id: str | None = None
    needs_input_reasons: list[str] = Field(default_factory=list)
    excluded_reasons: list[str] = Field(default_factory=list)
    prepared_at: datetime
    prepared_by_user_id: str | None = None
    exported_at: datetime | None = None
    external_id: str | None = None
    external_url: str | None = None
    result_recorded_at: datetime | None = None
    result_notes: str | None = None
    updated_at: datetime


class ExportEcologicalSubmissionsRequest(BaseModel):
    """Explicit submission-package generation (Phase 24: nothing leaves the
    Host without a deliberate action). Every id must reference an already-
    `prepare`d record -- this never silently prepares on the caller's
    behalf."""

    model_config = ConfigDict(extra="forbid")

    submission_ids: list[str] = Field(min_length=1, max_length=500)


class ExportEcologicalSubmissionsSkip(BaseModel):
    submission_id: str
    reason: Literal["stale_since_prepared", "not_eligible"]


class ExportEcologicalSubmissionsResponse(BaseModel):
    destination: Literal["inaturalist", "ebird"]
    output_directory: str | None = None
    files: list[ClassifierManifestExportFile] = Field(default_factory=list)
    included_count: int = Field(ge=0)
    skipped: list[ExportEcologicalSubmissionsSkip] = Field(default_factory=list)


class RecordEcologicalSubmissionResultRequest(BaseModel):
    """A user's own explicit, after-the-fact self-report of what the
    destination gave back (Phase 18) -- free text the user pastes in, never
    a value MockingBird itself fetched or validated against the destination.
    `external_url` is restricted to `http`/`https` (Phase 39 security
    review): the frontend renders this back as a clickable link, and
    without this check a `javascript:`-scheme value would be stored
    verbatim and execute in the viewer's own session when clicked."""

    model_config = ConfigDict(extra="forbid")

    external_id: str | None = Field(default=None, max_length=200)
    external_url: str | None = Field(default=None, max_length=500)
    result_notes: str | None = Field(default=None, max_length=1000)

    @field_validator("external_url")
    @classmethod
    def validate_external_url_scheme(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("external_url must be an http(s) URL")
        return value


def _validate_export_output_name(value: str | None) -> str | None:
    if value is None:
        return None
    name = value.strip()
    safe_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
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


class WildlifeInsightsRangePreset(str, Enum):
    today = "today"
    last_7_days = "last_7_days"
    last_30_days = "last_30_days"
    custom = "custom"


class WildlifeInsightsRequest(BaseModel):
    """A bounded local-date range for reviewed Wildlife Insights."""

    model_config = ConfigDict(extra="forbid")

    preset: WildlifeInsightsRangePreset = WildlifeInsightsRangePreset.last_7_days
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "WildlifeInsightsRequest":
        if self.preset == WildlifeInsightsRangePreset.custom:
            if self.start_date is None or self.end_date is None:
                raise ValueError("custom_range_requires_start_and_end_dates")
            if self.end_date < self.start_date:
                raise ValueError("custom_range_end_precedes_start")
            if (self.end_date - self.start_date).days > 365:
                raise ValueError("custom_range_must_not_exceed_366_days")
        return self


class WildlifeInsightsPeriod(BaseModel):
    preset: WildlifeInsightsRangePreset
    start_date: date
    end_date: date
    previous_start_date: date
    previous_end_date: date
    timezone_name: str


class WildlifeInsightsDrilldown(BaseModel):
    """A URL-preservable Activity Library scope, expressed as local calendar dates."""

    review_filter: ActivityLibraryReviewFilter
    start_date: date
    end_date: date
    stream_id: str | None = None
    zone_id: str | None = None
    confirmed_label: str | None = None


class WildlifeInsightsRepresentative(BaseModel):
    visit_id: str
    event_id: str
    stream_id: str
    stream_name: str
    zone_id: str | None = None
    zone_name: str | None = None
    label: str
    display_name: str
    observed_at: datetime
    primary_evidence: VisitEvidenceFrame | None = None


class WildlifeInsightsBreakdown(BaseModel):
    id: str
    name: str
    count: int = Field(ge=0)
    previous_count: int = Field(ge=0)
    change: int
    first_observed_at: datetime | None = None
    latest_observed_at: datetime | None = None
    representative: WildlifeInsightsRepresentative | None = None
    drilldown: WildlifeInsightsDrilldown


class WildlifeInsightsDailyBucket(BaseModel):
    local_date: date
    count: int = Field(ge=0)


class WildlifeInsightsHourBucket(BaseModel):
    hour: int = Field(ge=0, le=23)
    count: int = Field(ge=0)


class WildlifeInsightsHeadline(BaseModel):
    active_stream_count: int = Field(ge=0)
    active_visit_count: int = Field(ge=0)
    reviewed_wildlife_observation_count: int = Field(ge=0)
    unique_confirmed_label_count: int = Field(ge=0)
    unresolved_visit_count: int = Field(ge=0)
    reviewed_non_bird_activity_count: int = Field(ge=0)
    busiest_stream: WildlifeInsightsBreakdown | None = None
    busiest_zone: WildlifeInsightsBreakdown | None = None
    peak_activity_hour: int | None = Field(default=None, ge=0, le=23)
    first_observation: WildlifeInsightsRepresentative | None = None
    latest_observation: WildlifeInsightsRepresentative | None = None


class WildlifeInsightsComparison(BaseModel):
    previous_reviewed_wildlife_observation_count: int = Field(ge=0)
    reviewed_wildlife_observation_change: int
    new_labels: list[str] = Field(default_factory=list, max_length=12)
    labels_not_seen: list[str] = Field(default_factory=list, max_length=12)


class WildlifeInsightsReviewContext(BaseModel):
    blank_or_false_count: int = Field(ge=0)
    ambiguous_or_unknown_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    unclassified_reviewed_count: int = Field(ge=0)
    pending_suggestion_evidence_count: int = Field(ge=0)


class WildlifeInsightsSummary(BaseModel):
    period: WildlifeInsightsPeriod
    headline: WildlifeInsightsHeadline
    comparison: WildlifeInsightsComparison
    leading_labels: list[WildlifeInsightsBreakdown] = Field(default_factory=list, max_length=12)
    daily_trend: list[WildlifeInsightsDailyBucket] = Field(default_factory=list, max_length=366)
    activity_by_hour: list[WildlifeInsightsHourBucket] = Field(default_factory=list, max_length=24)
    stream_breakdown: list[WildlifeInsightsBreakdown] = Field(default_factory=list, max_length=12)
    zone_breakdown: list[WildlifeInsightsBreakdown] = Field(default_factory=list, max_length=12)
    review_context: WildlifeInsightsReviewContext
    confirmed_activity_drilldown: WildlifeInsightsDrilldown
    unresolved_activity_drilldown: WildlifeInsightsDrilldown


class ZoneInsightsQualityStatus(str, Enum):
    sufficient = "sufficient"
    limited_monitoring = "limited_monitoring"
    limited_review_coverage = "limited_review_coverage"
    no_confirmed_activity = "no_confirmed_activity"
    unavailable_exposure = "unavailable_exposure"
    unavailable = "unavailable"


class ZoneInsightsRequest(BaseModel):
    """Strict bounded filters for read-only Zone and feeder comparisons."""

    model_config = ConfigDict(extra="forbid")

    start_at: datetime | None = None
    end_at: datetime | None = None
    stream_id: str | None = Field(default=None, min_length=1, max_length=256)
    source_id: str | None = Field(default=None, min_length=1, max_length=256)
    zone_type: ZoneType | None = None
    confirmed_taxonomy_id: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_range(self) -> "ZoneInsightsRequest":
        if (self.start_at is None) != (self.end_at is None):
            raise ValueError("zone_insights_range_requires_start_and_end")
        if self.start_at is not None and self.end_at is not None:
            if self.end_at <= self.start_at:
                raise ValueError("zone_insights_end_must_follow_start")
            if self.end_at - self.start_at > timedelta(days=366):
                raise ValueError("zone_insights_range_must_not_exceed_366_days")
        return self


class ZoneInsightsAppliedFilters(BaseModel):
    start_at: datetime
    end_at: datetime
    stream_id: str | None = None
    source_id: str | None = None
    zone_type: ZoneType | None = None
    confirmed_taxonomy_id: str | None = None


class ZoneInsightsDrilldown(BaseModel):
    """An explicit existing Activity Library filter set for aggregate evidence."""

    filters: ActivityLibraryFilters


class ZoneInsightsSpeciesComposition(BaseModel):
    taxonomy_id: str
    label: str
    display_name: str
    visit_count: int = Field(ge=1)
    percentage: float = Field(ge=0, le=100)
    drilldown: ZoneInsightsDrilldown


class ZoneInsightsMetrics(BaseModel):
    healthy_monitored_hours: float | None = Field(default=None, ge=0)
    exposure_history_available_from: datetime | None = None
    exposure_history_is_partial: bool = False
    exposure_interval_count: int = Field(default=0, ge=0)
    confirmed_bird_visit_count: int = Field(ge=0)
    confirmed_bird_visits_per_monitored_hour: float | None = Field(default=None, ge=0)
    total_confirmed_bird_dwell_seconds: float = Field(ge=0)
    median_confirmed_bird_duration_seconds: float | None = Field(default=None, ge=0)
    confirmed_species_richness: int = Field(ge=0)
    unresolved_visit_count: int = Field(ge=0)
    reviewed_visit_count: int = Field(ge=0)
    reviewed_blank_count: int = Field(ge=0)
    reviewed_non_bird_count: int = Field(ge=0)
    reviewed_false_positive_count: int = Field(ge=0)
    review_coverage_percentage: float | None = Field(default=None, ge=0, le=100)
    reviewed_false_positive_percentage: float | None = Field(default=None, ge=0, le=100)
    evidence_success_percentage: float | None = Field(default=None, ge=0, le=100)
    first_confirmed_activity_at: datetime | None = None
    last_confirmed_activity_at: datetime | None = None
    data_quality_status: ZoneInsightsQualityStatus
    warnings: list[str] = Field(default_factory=list, max_length=12)


class ZoneInsightsZone(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: ZoneType
    stream_id: str
    stream_name: str
    source_id: str
    source_name: str
    metrics: ZoneInsightsMetrics
    species_composition: list[ZoneInsightsSpeciesComposition] = Field(default_factory=list, max_length=30)
    confirmed_activity_drilldown: ZoneInsightsDrilldown
    unresolved_activity_drilldown: ZoneInsightsDrilldown
    reviewed_blank_drilldown: ZoneInsightsDrilldown
    reviewed_non_bird_drilldown: ZoneInsightsDrilldown


class ZoneInsightsDailyBucket(BaseModel):
    local_date: date
    confirmed_bird_visit_count: int = Field(ge=0)
    drilldown: ZoneInsightsDrilldown


class ZoneInsightsHourBucket(BaseModel):
    hour: int = Field(ge=0, le=23)
    confirmed_bird_visit_count: int = Field(ge=0)
    drilldown: ZoneInsightsDrilldown


class ZoneInsightsSummary(BaseModel):
    generated_at: datetime
    applied_filters: ZoneInsightsAppliedFilters
    aggregate: ZoneInsightsMetrics
    zone_count: int = Field(ge=0, le=50)
    zones: list[ZoneInsightsZone] = Field(default_factory=list, max_length=50)
    daily_trend: list[ZoneInsightsDailyBucket] = Field(default_factory=list, max_length=366)
    activity_by_hour: list[ZoneInsightsHourBucket] = Field(default_factory=list, max_length=24)
    busiest_supported_hour: int | None = Field(default=None, ge=0, le=23)
    warnings: list[str] = Field(default_factory=list, max_length=16)


class PlaceActivityReportRequest(BaseModel):
    """An explicit, bounded reporting period for one Place Activity Report
    (see docs/place-activity-report-contract.md). Timezone is resolved
    server-side from the same existing product convention every other local-
    time analytics surface uses (`ProductRepository.place_activity_report`);
    it is not a caller-supplied field -- MockingBird is a single-site,
    local-first product with no per-Place timezone setting today."""

    model_config = ConfigDict(extra="forbid")

    start_at: datetime
    end_at: datetime
    # Camera / Source + Multi-Camera Maturity v1, Phase N: optional,
    # additive Source filter. `None` (the default, and every existing
    # caller) means the unfiltered whole-Place report, byte-identical to
    # before this field existed. A non-empty list scopes every count/
    # baseline/coverage fact in the report to only those Sources' Streams --
    # it never changes reviewed truth itself, only which of it this one
    # report call includes (see "source_ids filtering never changes truth"
    # in docs/camera-source-multi-camera-maturity-v1-contract.md).
    source_ids: list[str] | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_range(self) -> "PlaceActivityReportRequest":
        if self.end_at <= self.start_at:
            raise ValueError("place_activity_report_end_must_follow_start")
        if self.end_at - self.start_at > timedelta(days=366):
            raise ValueError("place_activity_report_range_must_not_exceed_366_days")
        return self


class PlaceActivityReportTaxonHistoricalStatus(BaseModel):
    """One confirmed taxon's Place-history status (Historical Baseline
    Maturity + New/Regular Species v1; see
    docs/historical-baseline-maturity-contract.md). Present only when this
    taxon has at least one authoritative (reviewed, non-superseded)
    confirmation -- never populated from a provisional SpeciesSuggestion
    alone; see `PlaceActivityReportTaxonEntry.historical_status`.

    `first_confirmed_at`/`last_confirmed_at` are all-time facts. `distinct_
    confirmed_days`/`distinct_confirmed_usable_days`/`total_confirmed_count`
    are bounded to the trailing historical window (see `historical_
    baseline.HISTORICAL_BASELINE_WINDOW_DAYS`) ending at this report's own
    `period_end_at` -- how present this taxon has been *recently*, not
    cumulatively over the Place's entire lifetime.
    """

    first_confirmed_at: datetime
    last_confirmed_at: datetime
    distinct_confirmed_days: int = Field(ge=0)
    distinct_confirmed_usable_days: int = Field(ge=0)
    total_confirmed_count: int = Field(ge=0)
    # "new"/"first_record" are the same underlying fact (this taxon's
    # all-time-earliest confirmed record falls within this report's own
    # period) presented with maturity-appropriate language -- "new" only
    # when the Place's own historical_baseline.maturity is "established"
    # (an ecological-novelty claim is supportable); "first_record"
    # otherwise (a true first record, without implying deep Place history).
    # "regular" requires confirmation on at least `historical_baseline.
    # MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR` distinct genuinely-monitored
    # days -- never raw Visit count. "seen_before" is the calm default:
    # confirmed previously, neither new this period nor yet regular.
    status: Literal["new", "first_record", "regular", "seen_before"]


class PlaceActivityReportTaxonChangeStatus(BaseModel):
    """One taxon's recent-vs-reference presence comparison (Gate C --
    Meaningful Change Detection / Baseline Comparison v1; see
    docs/meaningful-change-detection-contract.md). Present only for an
    authoritatively-confirmed taxon -- never populated from a provisional
    SpeciesSuggestion alone, matching `historical_status`'s identical truth
    contract.

    `recent_presence_days`/`reference_presence_days` count distinct
    genuinely-monitored (usable) days this taxon was confirmed on -- never
    raw Visit count, so one busy afternoon can never look like several
    independent days of presence. `recent_usable_day_count`/`reference_
    usable_day_count` are the fixed window-size targets (`place_change_
    summary.RECENT_WINDOW_USABLE_DAYS`/`REFERENCE_WINDOW_USABLE_DAYS`) this
    comparison actually achieved -- always exactly 7/14 whenever `status` is
    anything other than `insufficient_baseline`/`insufficient_recent_
    coverage`, repeated here so this entry is self-explanatory without
    cross-referencing `PlaceActivityReportChangeWindows`.
    """

    recent_presence_days: int = Field(ge=0)
    recent_usable_day_count: int = Field(ge=0)
    reference_presence_days: int = Field(ge=0)
    reference_usable_day_count: int = Field(ge=0)
    status: Literal[
        "insufficient_baseline",
        "insufficient_recent_coverage",
        "no_supported_change",
        "higher_recent_presence",
        "lower_recent_presence",
    ]


class PlaceActivityReportTaxonZoneActivity(BaseModel):
    """One Zone's share of a single taxon's *reviewed* Visits (Gate C --
    Per-Species Zone + Time Pattern Intelligence v1). `zone_id is None` is
    the "No Zone" bucket -- it can appear here but is never `most_active_
    zone` on `PlaceActivityReportTaxonEntry`, matching `PlaceActivityReport
    ZoneActivity`'s identical rule for the report-wide busiest_zone."""

    zone_id: str | None = None
    display_name: str
    reviewed_visit_count: int = Field(ge=0)


class PlaceActivityReportTaxonHourActivity(BaseModel):
    local_hour: int = Field(ge=0, le=23)
    reviewed_visit_count: int = Field(ge=0)


class PlaceActivityReportRegularityNarrative(BaseModel):
    """Place / Yard Intelligence v2, Phase 4: a synthesis of `historical_
    status`/`change_status` into one small, richer state -- see
    docs/place-yard-intelligence-v2-contract.md section 3.1. `basis`
    discloses honestly whether a change signal was actually available;
    never rendered as jargon in normal UI."""

    state: Literal[
        "first_record", "new", "occasional", "becoming_regular",
        "regular", "quieter_lately", "returned_after_absence",
    ]
    basis: Literal["historical_status_only", "historical_and_change"]


class PlaceActivityReportMonthPresence(BaseModel):
    month: int = Field(ge=1, le=12)
    usable_day_count: int = Field(ge=0)
    presence_day_count: int = Field(ge=0)


class PlaceActivityReportSeasonalPattern(BaseModel):
    """Place / Yard Intelligence v2, Phase 5: a restrained, single-trailing-
    year seasonality signal -- see docs/place-yard-intelligence-v2-contract.md
    section 3.2. `"insufficient_history"` is the expected, honest status for
    a young installation; `months` always carries all 12 entries so a
    drill-down view can show the whole year's shape regardless of status."""

    status: Literal[
        "insufficient_history", "no_pattern_detected", "developing_pattern", "established_pattern"
    ]
    months: list[PlaceActivityReportMonthPresence] = Field(min_length=12, max_length=12)
    typical_months: list[int] = Field(default_factory=list)
    current_month_is_typical: bool | None = None


class PlaceActivityReportTemporalPattern(BaseModel):
    """Place / Yard Intelligence v2, Phase 6 + the day/night slice of Phase
    10 -- see docs/place-yard-intelligence-v2-contract.md section 3.5.
    `daylight_association`/`dominant_band` read `"insufficient_data"`/`None`
    honestly when there is not enough evidence or solar is not configured;
    never a fabricated guess."""

    reviewed_visit_count: int = Field(ge=0)
    day_count: int = Field(ge=0)
    night_count: int = Field(ge=0)
    unknown_daylight_count: int = Field(ge=0)
    daylight_association: Literal[
        "insufficient_data", "mostly_daytime", "mostly_nighttime", "spans_day_and_night"
    ]
    dominant_band: Literal[
        "early_morning", "morning", "midday", "afternoon", "evening", "night"
    ] | None = None
    most_active_hour: int | None = Field(default=None, ge=0, le=23)


class PlaceActivityReportHabitatAssociation(BaseModel):
    """Place / Yard Intelligence v2, Phase 11: association language only,
    never causal -- see docs/place-yard-intelligence-v2-contract.md section
    3.4/3.6. Only entries clearing `conditional_association`'s own
    minimum-sample floor on both sides are ever produced; see
    `habitat_association.py`'s own docstring for why a true before/after
    habitat-change comparison is not built here."""

    subject_label: str
    phenomenon: str
    status: Literal[
        "no_clear_association", "more_common_under_condition", "less_common_under_condition"
    ]
    presence_days_in_condition: int = Field(ge=0)
    usable_days_in_condition: int = Field(ge=0)
    presence_days_out_of_condition: int = Field(ge=0)
    usable_days_out_of_condition: int = Field(ge=0)


class PlaceActivityReportWeatherAssociation(BaseModel):
    """Environmental Context v2: association language only, never causal --
    mirrors `PlaceActivityReportHabitatAssociation` field-for-field, using
    `mockingbird.analytics.weather_association`'s identical
    `conditional_association`-backed gating instead of a phenology interval.
    See docs/environmental-context-v2-contract.md "Phase 6/7". Only entries
    clearing `conditional_association`'s own minimum-sample floor on both
    sides are ever produced."""

    condition: Literal["cooler_than_typical", "warmer_than_typical", "wet_day"]
    condition_label: str
    status: Literal[
        "no_clear_association", "more_common_under_condition", "less_common_under_condition"
    ]
    presence_days_in_condition: int = Field(ge=0)
    usable_days_in_condition: int = Field(ge=0)
    presence_days_out_of_condition: int = Field(ge=0)
    usable_days_out_of_condition: int = Field(ge=0)


class PlaceActivityReportSourceActivity(BaseModel):
    """Place / Yard Intelligence v2, Phase 7: one Source's (camera's)
    coverage-normalized confirmed-wildlife activity for this report's own
    period -- see docs/place-yard-intelligence-v2-contract.md section 3.6.
    `visits_per_monitored_hour`/`data_sufficient` mirror Zone Insights' own
    `>=2` healthy-hour floor exactly, reused rather than reinvented.
    `monitored_seconds=None` is an honest "no durable exposure history yet"
    signal, never a fabricated zero."""

    source_id: str
    source_name: str
    confirmed_wildlife_visit_count: int = Field(ge=0)
    monitored_seconds: float | None = Field(default=None, ge=0)
    visits_per_monitored_hour: float | None = Field(default=None, ge=0)
    data_sufficient: bool


class PlaceActivityReportSourceQualitySignal(BaseModel):
    """Place / Yard Intelligence v2, Phase 8: a bounded, cross-Source
    admission-yield comparison -- see
    docs/place-yard-intelligence-v2-contract.md section 3.6.
    `candidates_attempted_count`/`candidates_created_count`/
    `suppressed_count` are durable, lifetime-cumulative-since-activation
    counters (never scoped to this report's own period -- see
    `source_activity.py`'s own docstring for why the alternative, the live
    counterfactual ledger, cannot answer this question durably at all).
    Never a physical-placement instruction."""

    source_id: str
    source_name: str
    candidates_attempted_count: int = Field(ge=0)
    candidates_created_count: int = Field(ge=0)
    suppressed_count: int = Field(ge=0)
    admission_yield_ratio: float | None = Field(default=None, ge=0, le=1)
    place_average_yield_ratio: float | None = Field(default=None, ge=0, le=1)
    signal: Literal["insufficient_data", "typical_yield", "lower_yield_than_place_average"]


class PlaceActivityReportTaxonEntry(BaseModel):
    """One represented taxon and its Visit-count backing. `confirmed_visit_
    count`/`provisional_visit_count` are always kept separate -- see "Report
    truth precedence" in docs/place-activity-report-contract.md."""

    label: str
    display_name: str
    category: LabelCategory
    is_species: bool
    confirmed_visit_count: int = Field(ge=0)
    provisional_visit_count: int = Field(ge=0)
    total_visit_count: int = Field(ge=0)
    first_activity_at: datetime
    last_activity_at: datetime
    # `None` when this taxon has never been authoritatively confirmed at
    # this Place (only a provisional SpeciesSuggestion backs it in today's
    # report) -- the truth contract forbids a provisional suggestion from
    # ever establishing historical status. See
    # docs/historical-baseline-maturity-contract.md.
    historical_status: PlaceActivityReportTaxonHistoricalStatus | None = None
    # `None` under the identical condition as `historical_status` above.
    # See docs/meaningful-change-detection-contract.md.
    change_status: PlaceActivityReportTaxonChangeStatus | None = None
    # Gate C -- Per-Species Zone + Time Pattern Intelligence v1: where and
    # when this taxon has been reviewed at this Place, computed over the
    # same bounded trailing historical window as `historical_status`/
    # `change_status` above (not just today's period) -- see "Per-species
    # Zone and time patterns" in docs/place-activity-report-contract.md.
    # Always `[]`/`[]`/`None`/`None` under the identical truth-contract
    # condition as `historical_status` (never populated from a provisional
    # SpeciesSuggestion alone). `zone_activity`/`hour_activity` list only
    # buckets that occurred (never zero-padded); `most_active_zone`/
    # `most_active_hour` are `None` below this milestone's minimum-support
    # floor, even when `zone_activity`/`hour_activity` are non-empty.
    zone_activity: list[PlaceActivityReportTaxonZoneActivity] = Field(default_factory=list)
    hour_activity: list[PlaceActivityReportTaxonHourActivity] = Field(default_factory=list)
    most_active_zone: PlaceActivityReportTaxonZoneActivity | None = None
    most_active_hour: PlaceActivityReportTaxonHourActivity | None = None
    # Gate C -- Representative Species Evidence v1 (see docs/representative-
    # species-evidence-contract.md): `None` whenever this taxon has no
    # confirmed Visit in *this report period* with safe, still-present
    # evidence -- including when this taxon is provisional-only (never
    # populated from a SpeciesSuggestion alone) or every candidate's media
    # is missing/deleted. A taxon with `representative_evidence is None`
    # remains a completely normal report entry; the frontend omits the
    # image rather than treating this as an error. Deliberately scoped to
    # this report's own period only -- never a historical fallback -- so
    # Today can never present old evidence as though captured today; see
    # "Time scope" in the contract doc.
    representative_evidence: RepresentativeEvidence | None = None
    # Place / Yard Intelligence v2: all four `None`/`[]` under the identical
    # truth-contract condition as `historical_status` above (never populated
    # from a provisional SpeciesSuggestion alone), computed over the same
    # bounded trailing historical window as `historical_status`/
    # `change_status`/`zone_activity`/`hour_activity` -- not just today's
    # period. See docs/place-yard-intelligence-v2-contract.md.
    regularity_narrative: PlaceActivityReportRegularityNarrative | None = None
    seasonal_pattern: PlaceActivityReportSeasonalPattern | None = None
    temporal_pattern: PlaceActivityReportTemporalPattern | None = None
    habitat_associations: list[PlaceActivityReportHabitatAssociation] = Field(default_factory=list)
    # Environmental Context v2: identical truth-contract/coverage-safety
    # condition as `habitat_associations` above. See
    # docs/environmental-context-v2-contract.md "Phase 6/7".
    weather_associations: list[PlaceActivityReportWeatherAssociation] = Field(default_factory=list)


class PlaceActivityReportZoneActivity(BaseModel):
    # `zone_id is None` is the "No Zone" bucket (see NO_ZONE_LABEL in
    # place_activity_report.py); it can appear here but is never
    # `busiest_zone`.
    zone_id: str | None = None
    zone_name: str
    wildlife_visit_count: int = Field(ge=0)


class PlaceActivityReportHourActivity(BaseModel):
    hour: int = Field(ge=0, le=23)
    wildlife_visit_count: int = Field(ge=0)


class PlaceActivityReportCoverageGap(BaseModel):
    start_at: datetime
    end_at: datetime
    duration_seconds: float = Field(ge=0)


class PlaceActivityReportCoverage(BaseModel):
    """Monitoring coverage for the reporting period, from durable exposure
    history only -- never inferred from Visit timestamps, camera
    configuration, or current runtime state. `monitored_seconds`/
    `coverage_ratio` are `None` when no durable exposure history exists yet
    for the reported scope; that is an honest "not yet computable" signal,
    never a fabricated number. See "Monitoring coverage" in
    docs/place-activity-report-contract.md."""

    period_seconds: float = Field(ge=0)
    monitored_seconds: float | None = Field(default=None, ge=0)
    coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    history_available_from: datetime | None = None
    history_is_partial: bool = False
    gaps: list[PlaceActivityReportCoverageGap] = Field(default_factory=list, max_length=20)
    gaps_truncated: bool = False


class PlaceActivityReportHistoricalBaseline(BaseModel):
    """Place-wide historical baseline facts (Historical Baseline Maturity +
    New/Regular Species v1; see docs/historical-baseline-maturity-contract.md).
    Bounded to a trailing window ending at this report's own `period_end_at`
    -- not "now" -- so a report for a past period always reproduces the same
    historical facts, regardless of when it is re-viewed.

    `total_monitored_seconds` is `None` specifically when no durable
    monitoring exposure history exists at all (mirrors `PlaceActivityReport
    Coverage.monitored_seconds`'s identical convention), distinct from a
    real, known zero for a Place monitored heavily long ago but not at all
    within this window.
    """

    window_start_at: datetime
    window_end_at: datetime
    usable_day_count: int = Field(ge=0)
    total_monitored_seconds: float | None = Field(default=None, ge=0)
    # The smallest useful classification of whether accumulated monitoring
    # history is deep enough to make a new-vs-regular species statement
    # useful at all -- purely a function of usable_day_count, never of taxa
    # or Visit counts (mirrors `maturity`'s identical discipline below) and
    # never of raw calendar age alone.
    maturity: Literal["insufficient", "developing", "established"]
    distinct_taxa_count: int = Field(ge=0)
    earliest_authoritative_record_at: datetime | None = None
    latest_authoritative_record_at: datetime | None = None


class PlaceActivityReportChangeWindows(BaseModel):
    """The bounded recent/reference comparison windows Gate C -- Meaningful
    Change Detection / Baseline Comparison v1 used to produce every
    `change_status` in this report (see
    docs/meaningful-change-detection-contract.md). `is_valid=False` means no
    per-taxon or Place-wide change status in this report is anything other
    than `invalid_reason` -- never a fabricated comparison from a partial
    window. `*_start_at` fields are `None` only when the corresponding
    window could not be populated at all."""

    policy_version: int = Field(ge=1)
    recent_window_start_at: datetime | None = None
    recent_window_end_at: datetime
    reference_window_start_at: datetime | None = None
    reference_window_end_at: datetime | None = None
    is_valid: bool
    invalid_reason: Literal["insufficient_baseline", "insufficient_recent_coverage"] | None = None


class PlaceActivityReportOverallChangeStatus(BaseModel):
    """The Place-wide aggregate comparison: any confirmed wildlife activity
    (named-species and "unknown_bird"/"unknown_animal" abstentions alike),
    never a forced blend of potentially conflicting per-species signals --
    see docs/meaningful-change-detection-contract.md."""

    recent_presence_days: int = Field(ge=0)
    recent_usable_day_count: int = Field(ge=0)
    reference_presence_days: int = Field(ge=0)
    reference_usable_day_count: int = Field(ge=0)
    status: Literal[
        "building_baseline",
        "insufficient_recent_coverage",
        "no_supported_change",
        "more_activity_recorded",
        "less_activity_recorded",
    ]


class PlaceActivityReportDigestSpeciesHighlight(BaseModel):
    """Gate C -- Calm Daily Digest v1 (see `mockingbird.analytics.daily_
    digest`): one named, reviewed-truth-backed species highlight. Always
    reuses the identical `historical_status`/`change_status`/`most_active_
    zone`/`most_active_hour`/`representative_evidence` facts already present
    on this taxon's own `PlaceActivityReportTaxonEntry` -- never a second,
    independently-derived set of facts."""

    label: str
    display_name: str
    category: LabelCategory
    is_species: bool
    confirmed_visit_count: int = Field(ge=0)
    provisional_visit_count: int = Field(ge=0)
    first_activity_at: datetime
    last_activity_at: datetime
    reason: Literal[
        "first_confirmed_record",
        "returned_after_absence",
        "meaningful_change",
        "unusual_timing",
        "seasonal_pattern_typical",
        "strong_representative_evidence",
        "regular_activity",
        "confirmed_activity",
    ]
    historical_note: str | None = None
    change_note: str | None = None
    pattern_note: str | None = None
    # Place / Yard Intelligence v2: same wording-only-when-earned discipline
    # as the three notes above -- see `daily_digest._REGULARITY_NOTES`/
    # `_SEASONAL_TYPICAL_NOTE`.
    regularity_note: str | None = None
    seasonal_note: str | None = None
    # Reused unmodified from `PlaceActivityReportTaxonEntry.representative_
    # evidence` for this same taxon -- the digest never selects or ranks
    # evidence itself (Representative Species Evidence v1 remains the only
    # selector). `None` is a completely normal outcome; the frontend omits
    # the image rather than treating it as an error.
    representative_evidence: RepresentativeEvidence | None = None


class PlaceActivityReportDigestOtherSpecies(BaseModel):
    """One additional confirmed species beyond the primary highlight bound
    -- compact, name-only continuity (see "Also recorded" in the milestone
    brief)."""

    label: str
    display_name: str
    category: LabelCategory
    is_species: bool
    confirmed_visit_count: int = Field(ge=0)


class PlaceActivityReportDigestOtherActivity(BaseModel):
    """Wildlife activity that is not (yet) reviewed truth -- always an
    anonymous count, never a species name. A provisional SpeciesSuggestion
    alone can never create a digest species."""

    provisional_visit_count: int = Field(ge=0)
    unresolved_visit_count: int = Field(ge=0)


class PlaceActivityReportDigestCoverage(BaseModel):
    """How much confidence today's digest may claim, and one calm sentence
    describing it. `state` is purely a function of monitoring coverage plus
    honest activity counts, never a judgment about whether the amount of
    wildlife found is normal -- see `mockingbird.analytics.daily_digest.
    _classify_coverage`."""

    state: Literal[
        "no_monitoring",
        "sparse_monitoring",
        "no_confirmed_activity",
        "unresolved_activity_only",
        "confirmed_wildlife",
    ]
    maturity: Literal["no_data", "sparse", "usable"]
    message: str


class PlaceActivityReportDigest(BaseModel):
    """Gate C -- Calm Daily Digest v1: one calm "what happened here today"
    recap, composed entirely from this same report's own already-resolved
    facts (see `mockingbird.analytics.daily_digest`). Creates no new
    observational authority -- every field here is derivable from `taxa`/
    `coverage`/`maturity`/`overall_change_status` elsewhere on this same
    response; this is a presentation-ready composition, not a second source
    of truth. Bounded to `MAX_PRIMARY_HIGHLIGHTS` (5) primary highlights;
    additional confirmed species appear compactly in `other_species`."""

    coverage: PlaceActivityReportDigestCoverage
    primary_highlights: list[PlaceActivityReportDigestSpeciesHighlight] = Field(
        default_factory=list, max_length=5
    )
    other_species: list[PlaceActivityReportDigestOtherSpecies] = Field(default_factory=list)
    other_activity: PlaceActivityReportDigestOtherActivity
    # The single Place-level baseline/change sentence, when supported --
    # `None` for the calm "no_supported_change" case (silence is the
    # message). Identical wording to `overall_change_status`'s existing
    # Today presentation; this field exists so a caller does not have to
    # re-derive the same sentence from the enum a second time.
    place_change_note: str | None = None
    first_activity_at: datetime | None = None
    last_activity_at: datetime | None = None
    confirmed_wildlife_visit_count: int = Field(ge=0)


class SoundscapeSummaryRequest(BaseModel):
    """An explicit, bounded reporting period for one Soundscape summary
    (Multimodal Observation & Soundscape v1, Phase K -- see docs/
    multimodal-observation-soundscape-v1-contract.md). Mirrors
    `PlaceActivityReportRequest` exactly: server-resolved timezone, no
    caller-supplied Place/timezone field."""

    model_config = ConfigDict(extra="forbid")

    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def validate_range(self) -> "SoundscapeSummaryRequest":
        if self.end_at <= self.start_at:
            raise ValueError("soundscape_summary_end_must_follow_start")
        if self.end_at - self.start_at > timedelta(days=366):
            raise ValueError("soundscape_summary_range_must_not_exceed_366_days")
        return self


class SoundscapeSpeciesHeardEntry(BaseModel):
    label: str
    display_name: str
    encounter_count: int


class SoundscapeHourlyActivity(BaseModel):
    hour: int
    encounter_count: int


class SoundscapeSummaryResponse(BaseModel):
    """The bounded acoustic-history foundation this milestone's Phase K
    calls for -- not a soundscape analytics product. No raw inference
    dump, no spectrogram, no ecological claim beyond the observed/reviewed
    data for this explicit period."""

    period_start: datetime
    period_end: datetime
    species_heard: list[SoundscapeSpeciesHeardEntry] = Field(default_factory=list)
    acoustic_encounter_count: int
    visual_only_count: int
    acoustic_only_count: int
    multimodal_count: int
    hourly_acoustic_activity: list[SoundscapeHourlyActivity] = Field(default_factory=list)


class PlaceActivityReportResponse(BaseModel):
    """One deterministic current-period activity report for a Place (see
    docs/place-activity-report-contract.md). Every count is a Visit count,
    never an individual-animal count -- the same bird can create several
    Visits, and MockingBird has no individual-animal identity model."""

    period_start_at: datetime
    period_end_at: datetime
    timezone_name: str
    generated_at: datetime

    # Honest accounting: these five buckets always sum to total_visit_count.
    total_visit_count: int = Field(ge=0)
    confirmed_wildlife_visit_count: int = Field(ge=0)
    provisional_wildlife_visit_count: int = Field(ge=0)
    unresolved_visit_count: int = Field(ge=0)
    non_wildlife_visit_count: int = Field(ge=0)
    excluded_visit_count: int = Field(ge=0)

    # Subset of confirmed_wildlife_visit_count with no resolvable taxon -- a
    # human confirmed real wildlife but abstained on species/kind (an
    # "unknown_bird"/"unknown_animal" correction).
    confirmed_species_unresolved_visit_count: int = Field(ge=0)
    # Headline count: confirmed + provisional wildlife Visits together.
    wildlife_visit_count: int = Field(ge=0)

    distinct_taxa_count: int = Field(ge=0)
    distinct_species_count: int = Field(ge=0)
    taxa: list[PlaceActivityReportTaxonEntry] = Field(default_factory=list)

    first_activity_at: datetime | None = None
    last_activity_at: datetime | None = None

    activity_by_zone: list[PlaceActivityReportZoneActivity] = Field(default_factory=list)
    busiest_zone: PlaceActivityReportZoneActivity | None = None
    # Always exactly 24 entries (hour 0-23), even when an hour had no activity.
    activity_by_hour: list[PlaceActivityReportHourActivity] = Field(
        default_factory=list, max_length=24
    )

    coverage: PlaceActivityReportCoverage
    # The smallest useful classification of whether `coverage` is sufficient
    # to trust a summary at all -- never a claim about how much wildlife
    # appeared, and never "normal"/"unusual"/"declining" (those need a
    # historical baseline this report does not compute). See
    # `mockingbird.analytics.place_activity_report.compute_report_maturity`.
    maturity: Literal["no_data", "sparse", "usable"]
    # Place-wide historical baseline facts -- a *different* maturity concept
    # from `maturity` above (that one is "is today's coverage enough to
    # trust today's summary"; this one is "is accumulated history deep
    # enough to trust a new-vs-regular species claim"). See
    # docs/historical-baseline-maturity-contract.md.
    historical_baseline: PlaceActivityReportHistoricalBaseline
    # Gate C -- Meaningful Change Detection / Baseline Comparison v1 (see
    # docs/meaningful-change-detection-contract.md): the bounded windows
    # backing every `taxa[].change_status`/`overall_change_status` below,
    # plus the Place-wide aggregate comparison. Never population/ecological
    # claims -- only a bounded, coverage-aware comparison of what was
    # recorded under comparable monitoring.
    change_windows: PlaceActivityReportChangeWindows
    overall_change_status: PlaceActivityReportOverallChangeStatus
    warnings: list[str] = Field(default_factory=list, max_length=10)
    # Gate C -- Calm Daily Digest v1: a bounded, ranked, presentation-ready
    # composition of the facts above -- see `PlaceActivityReportDigest`.
    digest: PlaceActivityReportDigest
    # Place / Yard Intelligence v2, Phase 13: the identical `digest` shape
    # above, computed over the 7-usable-day recent window `change_windows`
    # already establishes instead of this report's own requested period --
    # so a caller can show "this week" alongside "today" regardless of what
    # period was actually requested. See
    # docs/place-yard-intelligence-v2-contract.md section 3.7.
    weekly_digest: PlaceActivityReportDigest | None = None
    # Phase 7: coverage-normalized cross-Source (camera) activity
    # comparison, scoped to this report's own requested period -- never a
    # persisted "Area" (see product-doctrine.md "Spatial doctrine"). Empty
    # when no Source has enough monitored coverage to compare, or when
    # fewer than two Sources are configured.
    activity_by_source: list[PlaceActivityReportSourceActivity] = Field(default_factory=list)
    # Phase 8: a bounded, lifetime-cumulative (never period-scoped --
    # see `source_activity.py`'s own docstring) admission-yield comparison
    # across Sources. Never a physical-placement instruction.
    source_quality_signals: list[PlaceActivityReportSourceQualitySignal] = Field(default_factory=list)


class WildlifeJournalOrder(str, Enum):
    most_recent = "most_recent"
    most_observed = "most_observed"
    alphabetical = "alphabetical"
    first_observed = "first_observed"


class WildlifeJournalGalleryOrder(str, Enum):
    newest = "newest"
    oldest = "oldest"


class WildlifeJournalRangePreset(str, Enum):
    all_time = "all_time"
    today = "today"
    last_7_days = "last_7_days"
    last_30_days = "last_30_days"
    this_year = "this_year"
    custom = "custom"


class WildlifeJournalOverviewRequest(BaseModel):
    """Bounded ordering for one current reviewed-wildlife label summary."""

    model_config = ConfigDict(extra="forbid")

    order: WildlifeJournalOrder = WildlifeJournalOrder.most_recent
    # Multi-Camera Place Experience v2: optional camera scoping, matching
    # the per-species drilldown's existing `stream_id` filter (Wildlife
    # JournalHistoryRequest) rather than inventing a second convention on
    # the same page family. `None` (the default) is byte-identical to
    # this field not existing -- unfiltered, current-active-observatory
    # scope, unchanged from before this field was added.
    stream_id: str | None = Field(default=None, min_length=1, max_length=256)


class WildlifeJournalHistoryRequest(BaseModel):
    """Strict local-date scope and one bounded page of a reviewed label history."""

    model_config = ConfigDict(extra="forbid")

    preset: WildlifeJournalRangePreset = WildlifeJournalRangePreset.all_time
    start_date: date | None = None
    end_date: date | None = None
    stream_id: str | None = Field(default=None, min_length=1, max_length=256)
    zone_id: str | None = Field(default=None, min_length=1, max_length=256)
    favorites_only: bool = False
    tag_id: str | None = Field(default=None, min_length=1, max_length=256)
    gallery_order: WildlifeJournalGalleryOrder = WildlifeJournalGalleryOrder.newest
    page_size: int = Field(default=24, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def validate_range(self) -> "WildlifeJournalHistoryRequest":
        if self.preset == WildlifeJournalRangePreset.custom:
            if self.start_date is None or self.end_date is None:
                raise ValueError("custom_range_requires_start_and_end_date")
            if self.end_date < self.start_date:
                raise ValueError("custom_range_end_must_not_precede_start")
            if (self.end_date - self.start_date).days > 365:
                raise ValueError("custom_range_must_not_exceed_366_days")
        return self


class WildlifeJournalScope(BaseModel):
    preset: WildlifeJournalRangePreset
    start_date: date | None = None
    end_date: date | None = None
    stream_id: str | None = None
    zone_id: str | None = None
    favorites_only: bool = False
    tag_id: str | None = None
    timezone_name: str


class WildlifeJournalDrilldown(BaseModel):
    """A URL-preservable Activity Library scope without a second search contract."""

    review_filter: ActivityLibraryReviewFilter = ActivityLibraryReviewFilter.confirmed_wildlife
    confirmed_label: str
    start_date: date | None = None
    end_date: date | None = None
    stream_id: str | None = None
    zone_id: str | None = None


class WildlifeJournalRepresentative(BaseModel):
    visit_id: str
    event_id: str
    stream_id: str
    stream_name: str
    source_name: str
    zone_id: str | None = None
    zone_name: str | None = None
    label: str
    display_name: str
    observed_at: datetime
    primary_evidence: VisitEvidenceFrame | None = None


class WildlifeJournalRecentDay(BaseModel):
    local_date: date
    count: int = Field(ge=0)


class WildlifeJournalLabelSummary(BaseModel):
    label: str
    display_name: str
    observation_count: int = Field(ge=1)
    first_observed_at: datetime
    latest_observed_at: datetime
    stream_count: int = Field(ge=0)
    zone_count: int = Field(ge=0)
    recent_activity: list[WildlifeJournalRecentDay] = Field(default_factory=list, max_length=14)
    representative: WildlifeJournalRepresentative | None = None
    # Historical Baseline Maturity + New/Regular Species v1 (see
    # docs/historical-baseline-maturity-contract.md): distinct genuinely-
    # monitored days, within the trailing historical window, this label was
    # confirmed on -- never raw observation_count, which one busy afternoon
    # could inflate. `is_regular` is that count meeting the same coverage-
    # aware bar `PlaceActivityReportTaxonHistoricalStatus.status ==
    # "regular"` uses. See `baseline_maturity` on the overview response for
    # whether this Place's own accumulated history is deep enough to trust
    # either figure.
    distinct_confirmed_usable_days: int = Field(default=0, ge=0)
    is_regular: bool = False
    # Canonical New/Regular Species v1 (Everyday Discovery / Product
    # Experience v2; see docs/canonical-new-regular-species-contract.md): the
    # same `SpeciesHistoricalStatusValue` the Today digest uses, sourced from
    # the identical `compute_species_historical_statuses` call --
    # `is_regular`/`distinct_confirmed_usable_days` above are now populated
    # from this same canonical fact rather than an independently-recomputed
    # one, so this grid can never disagree with Today. Unlike `is_regular`,
    # this also makes "new"/"first_record" visible at grid level for the
    # first time (previously only `WildlifeJournalHistoryResponse.is_new_
    # label_in_range` existed, and only inside a manually-narrowed date
    # filter). `None` only in the defensive edge case where this label falls
    # outside the canonical computation's own Stream scope (e.g. all its
    # confirmations are on an archived Stream); `is_regular`/`distinct_
    # confirmed_usable_days` fall back to this surface's own computation in
    # that case rather than silently disappearing.
    historical_status: Literal["new", "first_record", "regular", "seen_before"] | None = None
    # Gate C -- Meaningful Change Detection / Baseline Comparison v1 -- see
    # docs/meaningful-change-detection-contract.md. `None` under the
    # identical truth-contract condition as `historical_status` elsewhere:
    # never populated from a provisional SpeciesSuggestion alone.
    change_status: PlaceActivityReportTaxonChangeStatus | None = None


class WildlifeJournalOverviewResponse(BaseModel):
    order: WildlifeJournalOrder
    labels: list[WildlifeJournalLabelSummary] = Field(default_factory=list, max_length=100)
    # Place-wide baseline maturity, as of now -- see `WildlifeJournalLabelSummary.
    # is_regular` and docs/historical-baseline-maturity-contract.md. Repeated
    # here (rather than only on the Today report) so Bird Log can word a
    # first-ever label honestly ("First confirmed record so far" vs. "New to
    # your reviewed history") without a second round trip.
    baseline_maturity: Literal["insufficient", "developing", "established"] = "insufficient"


class LikelySpeciesOverviewResponse(BaseModel):
    """Bird Log's provisional counterpart to the confirmed-only Wildlife
    Journal overview above: currently-unreviewed Visits grouped by an
    automatic top-1 BioCLIP suggestion (`DashboardTodaySpecies.is_confirmed`
    is always False here). Automatic Species Suggestion v1: these groups
    let Bird Log stay useful before review, while confirmed Journal labels
    remain the only current reviewed truth."""

    species: list[DashboardTodaySpecies] = Field(default_factory=list, max_length=50)


class WildlifeJournalBreakdown(BaseModel):
    id: str
    name: str
    count: int = Field(ge=1)


class WildlifeJournalHourBucket(BaseModel):
    hour: int = Field(ge=0, le=23)
    count: int = Field(ge=0)


class WildlifeJournalObservation(BaseModel):
    """One gallery row: compact reviewed context, never full evidence or correction history."""

    visit_id: str
    event_id: str
    stream_id: str
    stream_name: str
    source_name: str
    zone_id: str | None = None
    zone_name: str | None = None
    observed_at: datetime
    activity_started_at: datetime
    activity_ended_at: datetime | None = None
    duration_seconds: float = Field(ge=0)
    evidence_frame_count: int = Field(ge=0)
    reviewed_label: str
    display_name: str
    primary_evidence: VisitEvidenceFrame | None = None
    has_curation_history: bool = False
    has_review_revision: bool = False
    is_first_on_stream: bool = False
    is_first_in_zone: bool = False
    is_favorite: bool = False
    has_note: bool = False
    collection_count: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    # Everyday Discovery / Product Experience v2 (Phase B): identical
    # contract to `StreamVisitSummary.evidence_modality`/`multimodal_
    # partner` -- see that field's docstring.
    evidence_modality: Literal["visual", "acoustic", "seen_and_heard"] = "visual"
    multimodal_partner: VisitMultimodalPartnerSummary | None = None
    cross_camera_partner: VisitCrossCameraPartnerSummary | None = None


class WildlifeJournalGallery(BaseModel):
    order: WildlifeJournalGalleryOrder
    observations: list[WildlifeJournalObservation] = Field(default_factory=list, max_length=50)
    has_more: bool
    next_offset: int | None = Field(default=None, ge=0)


class WildlifeJournalHistoryResponse(BaseModel):
    label: str
    display_name: str
    scope: WildlifeJournalScope
    observation_count: int = Field(ge=0)
    first_observation: WildlifeJournalRepresentative | None = None
    latest_observation: WildlifeJournalRepresentative | None = None
    representative: WildlifeJournalRepresentative | None = None
    busiest_stream: WildlifeJournalBreakdown | None = None
    busiest_zone: WildlifeJournalBreakdown | None = None
    peak_activity_hour: int | None = Field(default=None, ge=0, le=23)
    stream_breakdown: list[WildlifeJournalBreakdown] = Field(default_factory=list, max_length=50)
    zone_breakdown: list[WildlifeJournalBreakdown] = Field(default_factory=list, max_length=50)
    activity_by_hour: list[WildlifeJournalHourBucket] = Field(default_factory=list, max_length=24)
    # Deliberately distinct from `historical_status` below: this is scoped to
    # whatever date range the viewer currently has selected (including
    # "all_time", where it is unconditionally False -- see
    # `_wildlife_journal_date_range`), answering "is this taxon's debut
    # visible in the range I'm looking at" rather than the canonical,
    # always-on "is this taxon new" fact.
    is_new_label_in_range: bool = False
    # Historical Baseline Maturity + New/Regular Species v1 -- see
    # `WildlifeJournalLabelSummary.distinct_confirmed_usable_days`/
    # `is_regular` and `WildlifeJournalOverviewResponse.baseline_maturity`,
    # repeated here so this independently-fetched per-label detail view
    # does not have to re-derive them from the overview response.
    distinct_confirmed_usable_days: int = Field(default=0, ge=0)
    is_regular: bool = False
    baseline_maturity: Literal["insufficient", "developing", "established"] = "insufficient"
    # Canonical New/Regular Species v1 (Everyday Discovery / Product
    # Experience v2; see docs/canonical-new-regular-species-contract.md): the
    # same all-time, period-agnostic `SpeciesHistoricalStatusValue` the Today
    # digest and the overview grid use -- unlike `is_new_label_in_range`,
    # this is never `False` merely because the viewer is on "all_time". See
    # `WildlifeJournalLabelSummary.historical_status` for the identical
    # fallback-to-`None` edge case.
    historical_status: Literal["new", "first_record", "regular", "seen_before"] | None = None
    # Gate C -- Meaningful Change Detection / Baseline Comparison v1 -- see
    # `WildlifeJournalLabelSummary.change_status` and
    # docs/meaningful-change-detection-contract.md.
    change_status: PlaceActivityReportTaxonChangeStatus | None = None
    # Biodiversity & Place Intelligence v1 -- habitat/environmental context
    # associated with this taxon's single most recent reviewed observation
    # only, never a per-Visit or statistical summary. `None` when there is
    # no confirmed observation at all (defensive; every real label reaching
    # this response has at least one). See docs/biodiversity-place-
    # intelligence-v1-contract.md "Taxon Place History."
    place_context: TaxonPlaceContext | None = None
    # Place / Yard Intelligence v2 -- the identical per-taxon shapes
    # `PlaceActivityReportTaxonEntry` carries, reused rather than
    # re-derived, so this label's own history page can never disagree with
    # Today/the Place Report about its regularity/seasonal/temporal/habitat
    # facts. `None`/`[]` under the identical truth-contract condition as
    # `historical_status` above. See docs/place-yard-intelligence-v2-contract.md.
    regularity_narrative: PlaceActivityReportRegularityNarrative | None = None
    seasonal_pattern: PlaceActivityReportSeasonalPattern | None = None
    temporal_pattern: PlaceActivityReportTemporalPattern | None = None
    habitat_associations: list[PlaceActivityReportHabitatAssociation] = Field(default_factory=list)
    weather_associations: list[PlaceActivityReportWeatherAssociation] = Field(default_factory=list)
    activity_library_drilldown: WildlifeJournalDrilldown
    gallery: WildlifeJournalGallery


class AlertCategory(str, Enum):
    review = "review"
    monitoring = "monitoring"
    storage = "storage"
    journal = "journal"
    # Calm Attention & Notifications v1: Place Story-derived regularity
    # transitions, mature Feature before/after comparisons, and the daily/
    # weekly digest recap. Deliberately separate from `journal` (which stays
    # exactly what it already meant -- "first confirmed local observation")
    # rather than overloading one category with two different kinds of fact
    # -- see docs/calm-attention-notifications-v1-report.md "Semantic
    # deduplication."
    insight = "insight"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    high = "high"


class AlertActionType(str, Enum):
    review_visit = "review_visit"
    open_stream = "open_stream"
    open_storage_retention = "open_storage_retention"
    open_wildlife_journal = "open_wildlife_journal"
    # Calm Attention & Notifications v1.
    open_place_story = "open_place_story"
    open_place_report = "open_place_report"


class AttentionCategory(str, Enum):
    """Calm Attention & Notifications v1, Phase 2: the small, user-centered
    taxonomy every `AlertCategory` presents as -- never a second, divergent
    vocabulary a user must learn alongside `AlertCategory`'s own internal/
    historical names (`journal`, `monitoring`). Purely a presentation-layer
    grouping computed from `(AlertCategory, AlertSeverity)`; never stored."""

    discovery = "discovery"
    insight = "insight"
    needs_help = "needs_help"
    observatory_health = "observatory_health"


class AttentionUrgency(str, Enum):
    """Calm Attention & Notifications v1, Phase 3: explicit delivery
    urgency, distinct from `AlertSeverity` (how bad) and `AttentionCategory`
    (what kind). `immediate` is reserved for a sustained, actionable
    Observatory Health condition; almost everything else is `digest`;
    per-item review work is always `in_app_only` (see Phase 10 -- reviewed
    work is grouped into the daily digest's own sentence, never repeated as
    a second per-item interruption)."""

    immediate = "immediate"
    digest = "digest"
    in_app_only = "in_app_only"


class ProductAlertAction(BaseModel):
    """A bounded product intent. The server, not the browser, chooses its route data."""

    action_type: AlertActionType
    visit_id: str | None = None
    stream_id: str | None = None
    label: str | None = None
    # Calm Attention & Notifications v1: optional Place Story deep-link
    # filters for `open_place_story` only -- mirrors `GET /api/place/story`'s
    # own `taxon`/`feature_id`/`kinds` query filters exactly, so the link
    # opens the Story page already scoped to the one event that prompted it.
    taxon_label: str | None = None
    feature_id: str | None = None
    story_kind: str | None = None


class ProductAlert(BaseModel):
    id: str
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    created_at: datetime
    updated_at: datetime
    read_at: datetime | None = None
    dismissed_at: datetime | None = None
    resolved_at: datetime | None = None
    status: str
    stream_id: str | None = None
    stream_name: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    visit_id: str | None = None
    source_id: str | None = None
    action: ProductAlertAction
    # Calm Attention & Notifications v1: derived presentation fields, never
    # persisted -- see `AttentionCategory`/`AttentionUrgency` above and
    # `ProductRepository._attention_category_for`/`_attention_urgency_for`.
    attention_category: AttentionCategory
    urgency: AttentionUrgency


class ProductAlertListResponse(BaseModel):
    items: list[ProductAlert] = Field(default_factory=list, max_length=100)
    next_offset: int | None = Field(default=None, ge=0)


class ProductAlertUnreadResponse(BaseModel):
    unread_count: int = Field(ge=0)
    recent: list[ProductAlert] = Field(default_factory=list, max_length=12)


class ProductAlertMarkVisibleReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_ids: list[str] = Field(default_factory=list, max_length=50)


class UserNotificationPreferences(BaseModel):
    """Calm Attention & Notifications v1, Phase 16/17/18: one signed-in
    user's own delivery preferences. Deliberately per-user (this is the
    first per-user settings row in the product -- see the milestone
    report's "Multi-user behavior"), while the underlying attention
    condition (`ProductAlertModel`) stays observatory-level exactly as
    before -- a preference here changes what one person is shown/notified,
    never the shared read/dismissed/resolved state other users see.

    Defaults are conservative by design (Phase 16): every category starts
    visible in-app, but `browser_notifications_enabled` starts `False` --
    MockingBird never asks for OS notification permission, or delivers a
    live interruption, until a signed-in user explicitly opts in (Phase 29).
    """

    discovery_enabled: bool = True
    insight_enabled: bool = True
    needs_help_enabled: bool = True
    observatory_health_enabled: bool = True
    browser_notifications_enabled: bool = False
    quiet_hours_enabled: bool = False
    # Minutes since local midnight, in the viewer's own browser-local time --
    # never a stored server/Place timezone (there is no per-Place timezone
    # setting; see mockingbird.time_utils.resolve_host_local_timezone's own
    # docstring). Quiet hours affect delivery only, never the underlying
    # attention condition or Observation Engine (Phase 17).
    quiet_hours_start_minute: int = Field(default=22 * 60, ge=0, le=1439)
    quiet_hours_end_minute: int = Field(default=7 * 60, ge=0, le=1439)
    updated_at: datetime


class UserNotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discovery_enabled: bool | None = None
    insight_enabled: bool | None = None
    needs_help_enabled: bool | None = None
    observatory_health_enabled: bool | None = None
    browser_notifications_enabled: bool | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start_minute: int | None = Field(default=None, ge=0, le=1439)
    quiet_hours_end_minute: int | None = Field(default=None, ge=0, le=1439)


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
    # Appliance / Storage / Privacy / Recovery v1, Phase D: opt-in age
    # threshold for `linked_evidence_or_analysis` media (a file referenced
    # only by a rejected/suppressed detection/analysis record, never by a
    # Visit) -- `None` (the default) keeps this category protected forever,
    # matching every installation's behavior before this field existed.
    rejected_analysis_media_age_days: int | None = Field(default=None, ge=7, le=3650)
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
    rejected_analysis_media_age_days: int | None = Field(default=None, ge=7, le=3650)
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
    # Appliance / Storage / Privacy / Recovery v1, Phase B/D: media
    # referenced only by a rejected/suppressed detection/analysis record
    # (never a Visit) -- previously invisible in this summary entirely,
    # even though it is retained forever by default. See
    # `StorageRetentionSettings.rejected_analysis_media_age_days` for the
    # one opt-in lever that can ever make this category cleanup-eligible.
    linked_evidence_or_analysis_count: int = Field(default=0, ge=0)
    linked_evidence_or_analysis_bytes: int = Field(default=0, ge=0)
    # Host-disk facts, distinct from the managed-media accounting above: a
    # normal user's "is my storage okay" question is about the real volume
    # MockingBird's data directory lives on, not a configured retention
    # target. `is_writable` is a genuine bounded write probe, not `os.access`.
    disk_total_bytes: int = Field(ge=0)
    disk_free_bytes: int = Field(ge=0)
    is_writable: bool
    # Appliance / Storage / Privacy / Recovery v1, Phase C: a graduated
    # healthy/getting_low/action_recommended/critical read of the same disk
    # facts above -- see `storage.database.LocalStorageDiskStatus.storage_
    # health_tier`. `storage_warning`/`is_writable` are unchanged; this is
    # additive, not a replacement.
    storage_health_tier: str = "healthy"
    storage_warning: str | None = None
    message: str


class SetupState(BaseModel):
    """Durable first-run/onboarding progress (see AppSetupStateModel)."""

    completed: bool
    current_step: str
    last_created_stream_id: str | None = None
    updated_at: datetime


class SetupStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_step: str = Field(min_length=1, max_length=40)
    completed: bool
    last_created_stream_id: str | None = Field(default=None, max_length=64)


class ProductHealthCameraSummary(BaseModel):
    needs_attention_count: int = Field(ge=0)


class ProductHealthObservationSummary(BaseModel):
    # Deliberately sourced from `DashboardHeadline.real_stream_count`
    # (excludes a still-unconfigured demo Source), not
    # `.configured_stream_count` -- this field feeds only the "Observing X
    # of Y cameras" ratio, where a demo Stream that can never be observed
    # would otherwise understate real observing coverage. See
    # `DashboardHeadline.real_stream_count`.
    configured_stream_count: int = Field(ge=0)
    monitored_stream_count: int = Field(ge=0)


class ProductHealthBackupSummary(BaseModel):
    has_backup: bool
    last_backup_at: datetime | None = None
    last_backup_verified: bool | None = None
    # Calm, non-nagging backup-awareness nudge (v0.1 Release Hardening v1):
    # true only once first-run setup is complete and no backup has ever been
    # created. Computed fresh on every read, never persisted/scheduled/
    # dismissed -- there is nothing to nag about repeatedly since it stops
    # being true the moment a backup exists. See
    # docs/local-backup-recovery-design.md.
    suggest_first_backup: bool = False


class ProductHealthAcousticSummary(BaseModel):
    """Whole-Product UI / Accessibility / Performance Closure v1: the
    product's first product-facing acoustic health/status surface -- closes
    the bounded gap
    docs/acoustic-productization-licensing-field-acceptance-v1-report.md
    disclosed ("the two status endpoints that could tell a user 'microphone/
    model unavailable' have zero frontend callers anywhere"). Mirrors
    `ProductHealthCameraSummary`'s bounded, additive shape -- composed
    entirely from already-existing facts (`get_birdnet_status()`, each
    Stream's existing `microphone` provider configuration,
    `acoustic_analysis_queue_diagnostics`'s existing 24h failure signal);
    never a new acoustic computation, never a live capture probe, and never
    a factor in `ProductHealthStatus.ready` -- acoustic is optional and its
    status can never make the product read as "not ready." See
    ProductHealthPanel.tsx.
    """

    configured: bool
    status: Literal[
        "not_configured", "healthy", "degraded", "model_unavailable", "microphone_unavailable"
    ]
    detail: str


class ProductHealthStatus(BaseModel):
    """One bounded, basic-first product status aggregate.

    Reuses `storage_summary`, the Dashboard's existing camera-attention list,
    and the existing backup library rather than recomputing any of them; see
    docs/local-product-packaging-design.md. Advanced-only facts
    (`database_schema_version`, `log_path`, and the version fields below)
    stay out of the basic fields the same way the Observation panel keeps
    runtime vocabulary out of its basic state.

    First-Hour Onboarding + Whole-Product Observability Closure v1 ("C5
    version reporting"): `camera_node_service_version`/
    `research_export_schema_version`/`camtrap_dp_profile_version` close a
    real gap this milestone's compatibility inventory found -- a support
    conversation previously had no single API response that could answer
    "which Camera Node software version, and which export policy version,
    is this installation actually running." `camera_node_service_version`
    reflects the most-recently-seen paired Camera Node's own reported
    version (`CameraSourceModel.camera_node_service_version`, already
    durable -- see Doctor's identical Camera Node check); `None` when no
    Camera Node has ever reported one. The export policy versions are
    fixed, already-accepted constants (`research.research_export.
    RESEARCH_EXPORT_SCHEMA_VERSION`/`research.camtrap_dp.
    CAMTRAP_DP_PROFILE_VERSION`), always present. Deliberately excluded:
    a live Camera Node *API* version re-check, which would require a fresh
    network probe of the Node's `secret=True`-flagged address from this
    read-only status aggregate -- see the milestone report's "known
    limitations."
    """

    app_version: str
    ready: bool
    message: str
    storage_writable: bool
    storage_low_space: bool
    # Appliance / Storage / Privacy / Recovery v1, Phase C/L: graduated
    # reading of the same disk facts `storage_low_space` already
    # summarizes as a single boolean -- see `StorageSummary.storage_health_
    # tier`. `storage_low_space` keeps its exact existing meaning/trigger.
    storage_health_tier: str = "healthy"
    storage_warning: str | None = None
    cameras: ProductHealthCameraSummary
    observation: ProductHealthObservationSummary
    backup: ProductHealthBackupSummary
    acoustic: ProductHealthAcousticSummary
    previous_shutdown_clean: bool | None = None
    database_schema_version: int = Field(ge=1)
    # Release Engineering Foundation v1: set only when *this running
    # process* actually performed an in-place schema upgrade at its own
    # startup (never on an ordinary already-current launch) -- see
    # `mockingbird.storage.database.DatabaseSchemaStatus.migrated_from_
    # version`. Advanced-tier, alongside `database_schema_version`, so a
    # user who just upgraded can confirm it worked without needing the
    # (often console-less, packaged-launcher) startup log.
    database_migrated_from_version: int | None = None
    log_path: str | None = None
    camera_node_service_version: str | None = None
    research_export_schema_version: str
    camtrap_dp_profile_version: str
    # Appliance / Storage / Privacy / Recovery v1, Phase N: each of these
    # is a fixed, always-present constant (never a live network probe --
    # see docs/appliance-storage-privacy-recovery-v1-contract.md,
    # "Compatibility boundaries") that was previously enforced in code but
    # surfaced on no diagnostic/status endpoint at all -- a recovery/support
    # conversation had no way to see a mismatch without attempting the
    # actual operation and hitting its error. `camera_node_api_version`/
    # `transport_protocol_version` are this host's own supported wire
    # versions, not a live re-check of what a specific paired Node speaks.
    backup_format_version: int
    camera_node_api_version: str
    transport_protocol_version: str
    generated_at: datetime


class ProductInstanceIdentity(BaseModel):
    """Identity of THIS running MockingBird process's own local installation.

    Used by the local launcher, to tell an already-running copy of this
    exact installation apart from an unrelated service, a different
    MockingBird install, or one forwarded from another environment (for
    example WSL) that merely answers on the same port -- see "Windows
    launcher defects" in docs/camera-node-pairing-persistence-design.md.
    Never process name, PID, or hostname: those are exactly the kind of
    guessable, spoofable, or environment-specific signal that could falsely
    match. `instance_id` is `None` only when this process was not started
    through the real launcher (for example a bare development server),
    which conservatively means "cannot confirm this is the same install."

    `git_commit`/`build_id` additionally answer "exactly which build is
    this" -- for a developer verifying a Windows dev deployment (see
    docs/windows-dev-deployment-design.md), never for the basic product UI.
    Both are `None` unless this process is running from a bundle built by
    `scripts/build_local_product.py` (a bare `python -m mockingbird` from a
    development checkout has neither). `build_id` is a fresh random token
    minted once per *build*, not per commit: two builds of the same commit
    (a rebuild after an unrelated local fix) still get different `build_id`s,
    so a stale build can never be mistaken for a fresh one that happens to
    share a commit.
    """

    instance_id: str | None = None
    app_version: str
    git_commit: str | None = None
    build_id: str | None = None


class ProductConnectionInfo(BaseModel):
    """How THIS Host is currently reachable on the network -- Mobile &
    Remote Experience v1's bounded "Phase 14/17" surface. Authenticated
    (not part of `_ALWAYS_PUBLIC_PATHS`), unlike `ProductInstanceIdentity`/
    `ProductHealthStatus`: this is operational detail about the running
    Host's own network exposure, not a launcher-facing liveness check, so
    it stays behind a signed-in session even though the underlying facts
    (an install's own bind flags) are not deeply sensitive.

    Every field is either a directly-known launch fact (`bind_host`,
    `bind_port`, `network_access_allowed` -- exactly what `--host`/
    `--allow-network` were passed at startup, see runtime.py) or a single
    best-effort local-network address detection with an honest `None` on
    any failure -- never a guess presented as certain. This intentionally
    stops short of trying to distinguish "local" from "remote/overlay-
    network" per-request (see Phase 20 of the governing brief: normal UI
    should not need NAT/network topology to make sense of this); that
    remains future, if ever built, Advanced Diagnostics work, not this
    field.
    """

    bind_host: str
    bind_port: int
    network_access_allowed: bool
    is_loopback_only: bool
    local_network_url: str | None = None


class ProductShutdownResponse(BaseModel):
    """Result of asking this running MockingBird process to stop itself
    gracefully -- Release Reliability & First-Run Recovery v1's own
    graceful-stop/shutdown-status UX contract. See `POST
    /api/product/shutdown`'s own docstring for the full mechanism.

    `accepted=False` is the honest degrade for a process not started
    through the real launch path (a bare development/test import of
    `api.main.app`, which never has a real `uvicorn.Server` to signal) --
    never a crash, and never a false claim that shutdown was requested
    when nothing can actually act on it.
    """

    accepted: bool
    message: str


class CameraNodeLiveStorageHealth(BaseModel):
    """One Camera Node's own local storage (pairing/config state directory
    -- never the media pipeline, which this product does not route through
    a Camera Node's own disk). Mirrors `mockingbird_node.hardware_health.
    StorageHealth.as_payload()`'s field names exactly -- a direct pass
    -through, never a second computation of the tier."""

    total_bytes: int
    free_bytes: int
    storage_health_tier: str


class CameraNodeLiveHardwareQuality(BaseModel):
    """A Camera Node's own `vcgencmd`-derived undervoltage/throttling/
    temperature facts. Mirrors `mockingbird_node.hardware_health.
    HardwareQuality.as_payload()`'s field names exactly. Every field is
    independently `None` when that specific fact could not be confirmed --
    never fabricated, matching this product's capability-aware-UX
    doctrine."""

    undervoltage_active: bool | None
    throttled_active: bool | None
    undervoltage_occurred: bool | None
    throttled_occurred: bool | None
    temperature_celsius: float | None


class CameraNodeHardwareHealthResponse(BaseModel):
    """Product Operations & First-Observation Completion v1: a bounded,
    live, on-demand, non-persisting check of a paired Camera Node's own
    storage/hardware-quality facts -- the human-visibility half of Release
    Reliability & First-Run Recovery v1's `hardware_health.py`, which
    shipped real facts on `/node/v1/health` that nothing on the Host ever
    read. Mirrors `CameraSetupPage`'s existing "Check the picture" bounded
    -live-check pattern, not Doctor's own read-only/DB-only design (Doctor
    itself is unmodified and untouched by this endpoint).

    `applicable=False` for a Stream that is not a paired Camera Node Stream
    at all (hardware/storage checks do not apply to RTSP/local/other
    providers). `applicable=True, reachable=False` when the Node could not
    be reached just now -- a normal, expected outcome (offline, network
    hiccup), never surfaced as an error. `storage`/`hardware` are `None`
    exactly when the Node's own response has them `None` (no probe
    directory configured; off Raspberry Pi) -- never fabricated.
    """

    applicable: bool
    reachable: bool
    message: str
    storage: CameraNodeLiveStorageHealth | None = None
    hardware: CameraNodeLiveHardwareQuality | None = None
    checked_at: datetime


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
    pre_migration = "pre_migration"


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


class ReviewLabelProvenanceReclassifyRequest(BaseModel):
    """A bounded maintenance request (see
    docs/review-decision-provenance-contract.md Part 8 and
    scripts/repair_review_label_provenance.py) -- not part of the normal
    interactive product review flow, and not exposed by the frontend."""

    model_config = ConfigDict(extra="forbid")

    review_origin: ReviewOrigin
    reviewer_identity: str = Field(min_length=1, max_length=256)
    expected_current_review_origin: ReviewOriginStored | None = None


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
    review_origin: ReviewOriginStored | None = None
    # Fail-safe default: every real construction site sets this explicitly
    # from `mockingbird.review_provenance.is_authority_eligible`, but a
    # missing/forgotten value should read as "not authoritative" rather
    # than silently implying a human confirmed it.
    is_authoritative: bool = False


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


class RecordedMediaAnalysisRun(BaseModel):
    """One offline recorded-video analysis attempt -- operational history
    and bounded progress/diagnostics, never evidence or truth by itself
    (Offline / Recorded Observation Ingest v1, see docs/offline-recorded-
    media-observation-contract.md)."""

    id: str
    media_asset_id: str
    stream_id: str
    pipeline_version: str
    status: str
    sample_fps: float
    source_duration_seconds: float | None = None
    frames_considered: int = Field(default=0, ge=0)
    frames_analyzed: int = Field(default=0, ge=0)
    events_created: int = Field(default=0, ge=0)
    visits_created: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime


class RecordedMediaAnalysisRequest(BaseModel):
    # Every field is optional: omitted, this route uses this pipeline's own
    # documented defaults (see docs/offline-recorded-media-observation-
    # contract.md "Frame sampling policy").
    sample_fps: float | None = Field(default=None, gt=0)
    max_frames: int | None = Field(default=None, gt=0)
    pipeline_version: str | None = None
    force_reprocess: bool = False


class RecordedMediaAnalysisResponse(BaseModel):
    run_id: str
    status: str
    media_asset_id: str
    stream_id: str
    pipeline_version: str
    sample_fps: float
    frames_considered: int = Field(default=0, ge=0)
    frames_analyzed: int = Field(default=0, ge=0)
    events_created: int = Field(default=0, ge=0)
    visits_created: int = Field(default=0, ge=0)
    visit_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    source_duration_seconds: float | None = None
    truncated: bool = False
    capture_time_known: bool = False
    error_code: str | None = None
    error_message: str | None = None
    # This route's own fixed category disclosure (mirrors `SourceFolder
    # ImportResponse`'s identical convention): it can create ordinary,
    # needs-review candidate Events/Visits exactly like a live Camera Node
    # session, but it never creates reviewed truth -- only the existing,
    # unmodified correction path can.
    creates_events: bool = True
    creates_visits: bool = True
    creates_truth: bool = False


class AcousticAnalysisRun(BaseModel):
    """One BirdNET analysis attempt over one audio `MediaAsset` --
    operational history and bounded progress/diagnostics, never evidence or
    truth by itself (Acoustic / BirdNET Observation Foundation v1, see
    docs/acoustic-birdnet-observation-foundation-v1-contract.md). Mirrors
    `RecordedMediaAnalysisRun` exactly."""

    id: str
    media_asset_id: str
    stream_id: str
    pipeline_version: str
    status: str
    min_confidence: float = Field(ge=0, le=1)
    source_duration_seconds: float | None = None
    windows_analyzed: int = Field(default=0, ge=0)
    detections_above_threshold: int = Field(default=0, ge=0)
    species_suggestions_created: int = Field(default=0, ge=0)
    events_created: int = Field(default=0, ge=0)
    visits_created: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    # Acoustic Runtime & Quality v1 (schema 44): bounded retry/backoff and a
    # crash-safe claim token -- see `AcousticAnalysisRunModel`.
    consecutive_failure_count: int = Field(default=0, ge=0)
    next_retry_at: datetime | None = None
    claimed_by: str | None = None
    claimed_at: datetime | None = None


class AudioCaptureStatusResponse(BaseModel):
    """Read-only local-microphone capture status for one Stream -- current-
    process state only (see "Restart-safety" in `mockingbird.observation.
    audio_capture`'s module docstring), never proof of anything beyond
    this running process."""

    stream_id: str
    is_running: bool
    consent_granted: bool
    device: str | None = None


class BirdNetStatusResponse(BaseModel):
    """Explicit local readiness for the optional BirdNET acoustic adapter --
    mirrors the existing `GET .../bioclip-status`-style contract. Read-only;
    never loads the model or runs inference."""

    status: str  # "available" | "unavailable"
    runtime_available: bool
    detail: str


class RecordedAudioAnalysisRequest(BaseModel):
    # Every field is optional: omitted, this route uses this pipeline's own
    # documented defaults (see docs/acoustic-birdnet-observation-
    # foundation-v1-contract.md "Configuration").
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    pipeline_version: str | None = None
    force_reprocess: bool = False
    # Optional BirdNET species-range filter override for this one request
    # only -- never persisted, mirroring `CamtrapDpExportRequest.latitude`/
    # `.longitude`'s identical "no persisted per-Source coordinate model,
    # explicit per-call override only" precedent (see "Privacy" in docs/
    # research-conservation-export-contract.md). Omitted, BirdNET evaluates
    # its full global species list with no location narrowing.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class RecordedAudioAnalysisResponse(BaseModel):
    run_id: str
    status: str
    media_asset_id: str
    stream_id: str
    pipeline_version: str
    min_confidence: float = Field(ge=0, le=1)
    windows_analyzed: int = Field(default=0, ge=0)
    detections_above_threshold: int = Field(default=0, ge=0)
    species_suggestions_created: int = Field(default=0, ge=0)
    events_created: int = Field(default=0, ge=0)
    visits_created: int = Field(default=0, ge=0)
    visit_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    source_duration_seconds: float | None = None
    capture_time_known: bool = False
    error_code: str | None = None
    error_message: str | None = None
    # This route's own fixed category disclosure, mirroring
    # `RecordedMediaAnalysisResponse`'s identical convention: it can create
    # ordinary, needs-review candidate Events/Visits, but it never creates
    # reviewed truth -- only the existing, unmodified correction path can.
    creates_events: bool = True
    creates_visits: bool = True
    creates_truth: bool = False


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
    # Everyday Product / Discovery UX Closure v1: `media_asset` below depends
    # entirely on some Visit's legacy `representative_media_path` being set,
    # which the dominant current Visit-creation path (Camera Node/offline
    # ingest) leaves null -- an Event case file could show zero photos
    # anywhere, and gave no way to tell multiple Visits/subjects apart. Keyed
    # by `Visit.id`; a Visit with no resolvable evidence is simply absent
    # from this dict rather than a fabricated placeholder entry. Reuses the
    # exact same per-Visit evidence-frame resolution `VisitDetail.evidence_
    # frames` already uses -- no new evidence-selection logic.
    visit_previews: dict[str, VisitEvidenceFrame] = Field(default_factory=dict)
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


class VisitMultimodalAssociation(BaseModel):
    """Multimodal Observation & Soundscape v1, Phase D/E/I (see docs/
    multimodal-observation-soundscape-v1-contract.md): one durable
    `VisitAssociationModel` row touching this Visit, resolved to the full
    opposite-modality Visit it points at -- mirrors `VisitDetail.
    sibling_visits`'s own "return the real nested Visit, not a summary"
    precedent so the frontend reuses its existing Visit-rendering logic
    rather than needing a second species/evidence-display path.

    `taxon_agreement` is always recomputed fresh at read time from each
    Visit's *current* top label (see `VisitAssociationModel`'s own
    docstring) -- never a stored, potentially stale fact.
    """

    association_id: str
    other_visit: Visit
    other_modality: Literal["visual", "acoustic"]
    tier: Literal["associated", "possible"]
    taxon_agreement: Literal["agrees", "differs", "not_comparable"]
    overlap_ms: int
    gap_ms: int


class VisitCrossCameraAssociation(BaseModel):
    """Camera / Source + Multi-Camera Maturity v1, Phase I: one durable
    `CrossCameraVisitAssociationModel` row touching this Visit, resolved to
    the full same-encounter (or possibly-same-encounter) Visit it points at
    on a *different* camera -- mirrors `VisitMultimodalAssociation`'s own
    "return the real nested Visit, not a summary" shape.

    `taxon_agreement` is recomputed fresh at read time, never stored,
    exactly like the multimodal case. `spatial_signal`/`multi_subject` are
    disclosed, not hidden, so a reviewer can see *why* a pair reached its
    tier (e.g. "possible" because two subjects were on camera at once, not
    because the system merely guessed)."""

    association_id: str
    other_visit: Visit
    other_source_name: str
    other_stream_name: str
    tier: Literal["associated", "possible"]
    taxon_agreement: Literal["agrees", "differs", "not_comparable"]
    overlap_ms: int
    gap_ms: int
    spatial_signal: Literal["matching_area_name", "unknown"]
    multi_subject: bool


class VisitDetail(BaseModel):
    visit: Visit
    event: Event
    stream: Stream
    # Camera / Source + Multi-Camera Maturity v1, Phase B/G: `stream.
    # source_id` alone is an opaque id -- this is the one place `VisitDetail`
    # resolves it to the Source's actual display name, so evidence/Visit
    # detail (the most-visited attribution surface) never has to show a raw
    # UUID as "Source." Mirrors `DashboardVisitSummary.source_name`'s own
    # existing precedent, applied to the one surface that was missing it.
    source_name: str
    primary_zone: Zone | None = None
    detections: list[Detection]
    motion_evidence: MotionEvidenceResponse | None = None
    media_asset: MediaAsset | None = None
    evidence_frames: list[VisitEvidenceFrame] = Field(default_factory=list)
    effective_primary: EffectivePrimaryEvidence | None = None
    # Visit Same-Frame Classifier Evidence Visibility v1 (see docs/visit-
    # classifier-evidence-visibility-contract.md): present only when the
    # asset the species classifier actually used differs materially from
    # `evidence_frames` above -- never a second copy of an already-visible
    # image, never the Visit's primary/canonical evidence.
    classifier_supporting_evidence: ClassifierSupportingEvidence | None = None
    crop_history: list[VisitCropHistoryEntry] = Field(default_factory=list)
    stale_species_suggestions: bool = False
    detection_proposals: list[DetectionProposal] = Field(default_factory=list)
    detection_runs: list[DetectionRun] = Field(default_factory=list)
    review_labels: list[ReviewLabel]
    correction_history: list[VisitReviewHistoryEntry] = Field(default_factory=list)
    curation_history: list[VisitCurationHistoryEntry] = Field(default_factory=list)
    resulting_visits: list[Visit] = Field(default_factory=list)
    # Multi-Subject Visit Assembly & Review v1, Phase 2 (see docs/multi-
    # subject-visit-assembly-review-v1.md): every other Visit sharing this
    # Visit's own Event, when there is more than one -- the common
    # single-subject case reports an empty list, byte-identical to today.
    # A reviewer usually reaches a Visit directly (Review Queue, Bird Log),
    # not via its Event, so this is the one place `VisitDetail` needs to
    # expose the encounter/sibling relationship `EventDetail.visits` already
    # carries; this never changes review/correction/truth semantics -- each
    # sibling remains an independently reviewable `Visit`.
    sibling_visits: list[Visit] = Field(default_factory=list)
    # Multimodal Observation & Soundscape v1 (see docs/multimodal-
    # observation-soundscape-v1-contract.md): every durable association
    # this Visit has to an opposite-modality Visit (visual <-> acoustic) --
    # empty for the common single-modality case. Never merges/overwrites
    # this Visit's own evidence or review state; each associated Visit
    # remains independently reviewable.
    multimodal_associations: list[VisitMultimodalAssociation] = Field(default_factory=list)
    # Camera / Source + Multi-Camera Maturity v1, Phase I: every durable
    # association this Visit has to a same-encounter (or possibly-same-
    # encounter) Visit on a *different* camera -- empty for the common
    # single-camera case. Independent of `multimodal_associations` above.
    cross_camera_associations: list[VisitCrossCameraAssociation] = Field(default_factory=list)
    eligible_zones: list[Zone] = Field(default_factory=list)
    review_state_token: str
    dataset_ready: bool
    review_summary: str


class VisitOrganizationState(BaseModel):
    visit_id: str
    is_favorite: bool = False
    note: str = ""
    inherited_from_visit_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    state_token: str


class VisitOrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_favorite: bool | None = None
    note: str | None = Field(default=None, max_length=4000)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_change(self) -> "VisitOrganizationUpdate":
        if self.is_favorite is None and self.note is None:
            raise ValueError("Provide a favorite state or note")
        return self


class VisitOrganizationBulkAction(str, Enum):
    favorite = "favorite"
    unfavorite = "unfavorite"


class VisitOrganizationBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visit_ids: list[str] = Field(min_length=1, max_length=50)
    action: VisitOrganizationBulkAction
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitOrganizationBulkResult(BaseModel):
    visit_id: str
    status: str


class VisitOrganizationBulkResponse(BaseModel):
    results: list[VisitOrganizationBulkResult]


class VisitCollectionSummary(BaseModel):
    """Safe local Collection metadata; it never exposes a filesystem location."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    state_token: str
    active_visit_count: int = Field(default=0, ge=0)
    latest_active_visit_at: datetime | None = None
    representative_evidence: VisitEvidenceFrame | None = None


class VisitCollectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitCollectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_change(self) -> "VisitCollectionUpdate":
        if not ({"name", "description"} & self.model_fields_set):
            raise ValueError("Provide a Collection name or description")
        return self


class VisitCollectionArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitCollectionMembershipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitCollectionMembershipStatus(str, Enum):
    updated = "updated"
    already_present = "already_present"
    already_absent = "already_absent"
    skipped_unavailable = "skipped_unavailable"
    skipped_superseded = "skipped_superseded"


class VisitCollectionMembershipResult(BaseModel):
    visit_id: str
    status: VisitCollectionMembershipStatus


class VisitCollectionMembershipResponse(BaseModel):
    collection: VisitCollectionSummary
    result: VisitCollectionMembershipResult


class VisitCollectionBulkAction(str, Enum):
    add = "add"
    remove = "remove"


class VisitCollectionBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_id: str = Field(min_length=1, max_length=256)
    visit_ids: list[str] = Field(min_length=1, max_length=50)
    action: VisitCollectionBulkAction
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitCollectionBulkResponse(BaseModel):
    collection: VisitCollectionSummary
    results: list[VisitCollectionMembershipResult]


class VisitCollectionsForVisitResponse(BaseModel):
    visit_id: str
    collections: list[VisitCollectionSummary] = Field(default_factory=list, max_length=20)


class VisitTagSummary(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    state_token: str
    active_visit_count: int = Field(default=0, ge=0)


class VisitTagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitTagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitTagArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitTagMembershipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitTagMembershipStatus(str, Enum):
    updated = "updated"
    already_present = "already_present"
    already_absent = "already_absent"
    skipped_unavailable = "skipped_unavailable"
    skipped_superseded = "skipped_superseded"
    skipped_limit = "skipped_limit"


class VisitTagMembershipResult(BaseModel):
    visit_id: str
    status: VisitTagMembershipStatus


class VisitTagMembershipResponse(BaseModel):
    tag: VisitTagSummary
    result: VisitTagMembershipResult


class VisitTagBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tag_id: str = Field(min_length=1, max_length=256)
    visit_ids: list[str] = Field(min_length=1, max_length=50)
    action: Literal["add", "remove"]
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VisitTagBulkResponse(BaseModel):
    tag: VisitTagSummary
    results: list[VisitTagMembershipResult]


class VisitTagsForVisitResponse(BaseModel):
    visit_id: str
    tags: list[VisitTagSummary] = Field(default_factory=list, max_length=20)


class YardMapAreaPoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class YardMapBackground(BaseModel):
    preview_url: str
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    width: int = Field(gt=0, le=8192)
    height: int = Field(gt=0, le=8192)


class YardMapSettings(BaseModel):
    id: str
    canvas_width: int = Field(ge=320, le=4096)
    canvas_height: int = Field(ge=240, le=4096)
    background: YardMapBackground | None = None
    background_missing: bool = False
    state_token: str
    created_at: datetime
    updated_at: datetime


class YardMapBlankCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canvas_width: int = Field(default=1200, ge=320, le=4096)
    canvas_height: int = Field(default=800, ge=240, le=4096)
    idempotency_key: str = Field(min_length=1, max_length=128)


class YardMapSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canvas_width: int = Field(ge=320, le=4096)
    canvas_height: int = Field(ge=240, le=4096)
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class YardMapStreamPlacementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    heading_degrees: float = Field(ge=0, lt=360)
    field_of_view_degrees: float = Field(ge=10, le=180)
    display_scale: float | None = Field(default=None, ge=0.25, le=3)
    expected_state_token: str | None = Field(default=None, min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class YardMapZonePlacementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    area: list[YardMapAreaPoint] | None = Field(default=None, min_length=3, max_length=12)
    expected_state_token: str | None = Field(default=None, min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class YardMapPlacementDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class YardMapBackgroundDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_state_token: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128)


class YardMapStreamPlacement(BaseModel):
    stream_id: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    heading_degrees: float = Field(ge=0, lt=360)
    field_of_view_degrees: float = Field(ge=10, le=180)
    display_scale: float | None = Field(default=None, ge=0.25, le=3)
    state_token: str
    updated_at: datetime


class YardMapZonePlacement(BaseModel):
    zone_id: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    area: list[YardMapAreaPoint] | None = None
    state_token: str
    updated_at: datetime


class YardMapActivitySummary(BaseModel):
    monitoring_desired_state: StreamMonitoringMode
    monitoring_actual_state: StreamRuntimeState
    camera_health_state: CameraHealthState = CameraHealthState.stopped
    open_activity_session: bool = False
    needs_review_count: int = Field(ge=0)
    needs_review_visit_ids: list[str] = Field(default_factory=list, max_length=50)
    latest_visit_id: str | None = None
    latest_visit_at: datetime | None = None
    latest_confirmed_label: str | None = None
    latest_preview_url: str | None = None


class YardMapStreamItem(BaseModel):
    id: str
    name: str
    source_name: str
    is_live: bool
    placement: YardMapStreamPlacement | None = None
    activity: YardMapActivitySummary


class YardMapZoneItem(BaseModel):
    id: str
    stream_id: str
    name: str
    zone_type: ZoneType
    is_active: bool
    placement: YardMapZonePlacement | None = None


class YardMapResponse(BaseModel):
    map: YardMapSettings | None = None
    streams: list[YardMapStreamItem] = Field(default_factory=list, max_length=50)
    zones: list[YardMapZoneItem] = Field(default_factory=list, max_length=200)
    range: Literal["today", "last_24_hours", "last_7_days"] = "today"
    warnings: list[str] = Field(default_factory=list, max_length=20)


def _ensure_json_compatible(value: Any, field_name: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be JSON-compatible") from error


# --- Local Identity, Multi-User & Organization Access v1 -------------------
# See docs/local-identity-multi-user-contract.md. A deliberately small
# 3-value role ladder (Viewer < Reviewer < Administrator) -- see
# `mockingbird.api.auth.Role` for the ordering/comparison logic used by
# the authorization middleware; this Enum is the wire representation only.


class UserRole(str, Enum):
    viewer = "viewer"
    reviewer = "reviewer"
    administrator = "administrator"


class CurrentUser(BaseModel):
    """The signed-in identity of the caller making this request -- returned
    by sign-in and `GET /api/auth/session`, and embedded nowhere else (the
    frontend account menu/review provenance reuses this one shape)."""

    id: str
    display_name: str
    login_identity: str
    role: UserRole
    enabled: bool


class SignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_identity: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class SelfPasswordChangeRequest(BaseModel):
    """A signed-in user changing their own password -- requires proving the
    current one, unlike an Administrator's reset of someone else's."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UserSummary(BaseModel):
    """Administrator-facing user listing/detail. Never includes
    `password_hash` or any session token -- see docs/local-identity-multi-
    user-contract.md "Privacy"."""

    id: str
    display_name: str
    login_identity: str
    role: UserRole
    enabled: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=128)
    login_identity: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    role: UserRole


class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole


class UserEnabledUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class AdminPasswordResetRequest(BaseModel):
    """An Administrator setting someone else's password -- no current-
    password proof required (that's the whole point of a reset), unlike
    `SelfPasswordChangeRequest`."""

    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=1, max_length=256)


class AdministratorBootstrapRequest(BaseModel):
    """First-run administrator creation -- see `mockingbird.api.auth.
    create_first_administrator`. No `role` field: the very first account is
    always Administrator, by construction, never client-chosen."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=128)
    login_identity: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuditLogEntry(BaseModel):
    """One durable audit-trail row (see AuditLogEntryModel). `actor_display_
    name` is a point-in-time snapshot -- it does not change if the actor is
    later renamed/disabled."""

    id: str
    created_at: datetime
    actor_user_id: str | None = None
    actor_display_name: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    metadata: dict[str, Any] | None = None
    correlation_id: str | None = None


class InstallationSettings(BaseModel):
    """Lightweight installation-level display metadata only -- never an
    `Organization` tenancy record (see InstallationSettingsModel)."""

    installation_name: str | None = None
    organization_name: str | None = None
    contact_display: str | None = None
    updated_at: datetime


class InstallationSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installation_name: str | None = Field(default=None, max_length=128)
    organization_name: str | None = Field(default=None, max_length=128)
    contact_display: str | None = Field(default=None, max_length=256)


# --- Non-Interactive Field Acceptance Authentication & Session Access v1 ---
# See docs/non-interactive-field-acceptance-authentication-session-access-
# v1-contract.md. A second, narrow, parallel identity for bounded
# non-interactive tooling -- deliberately not a `UserRole` value (see
# `FieldAcceptanceCredentialModel`'s own docstring for why).

DEFAULT_FIELD_ACCEPTANCE_CREDENTIAL_TTL_HOURS = 24
MINIMUM_FIELD_ACCEPTANCE_CREDENTIAL_TTL_HOURS = 1
MAXIMUM_FIELD_ACCEPTANCE_CREDENTIAL_TTL_HOURS = 720  # 30 days


class FieldAcceptancePrincipal(BaseModel):
    """The resolved identity of a valid bearer-token field-acceptance
    credential -- the non-human counterpart to `CurrentUser`, populated on
    `request.state.field_acceptance_principal` by the same central
    authorization gate. Never returned directly by any endpoint; see
    `FieldAcceptanceCredentialSummary` for the admin-facing shape."""

    id: str
    label: str


class FieldAcceptanceCredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="Field Acceptance Operator", min_length=1, max_length=128)
    expires_in_hours: int = Field(
        default=DEFAULT_FIELD_ACCEPTANCE_CREDENTIAL_TTL_HOURS,
        ge=MINIMUM_FIELD_ACCEPTANCE_CREDENTIAL_TTL_HOURS,
        le=MAXIMUM_FIELD_ACCEPTANCE_CREDENTIAL_TTL_HOURS,
    )


class FieldAcceptanceCredentialSummary(BaseModel):
    """Administrator-facing credential listing/detail. Never includes
    `token_hash` or the raw secret -- see `FieldAcceptanceCredentialCreated`
    for the one-time-only shape that does carry the raw token."""

    id: str
    label: str
    created_at: datetime
    created_by_user_id: str | None = None
    created_by_display_name: str | None = None
    expires_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class FieldAcceptanceCredentialCreated(FieldAcceptanceCredentialSummary):
    """Returned exactly once, at creation -- the only response shape in this
    product that ever carries a field-acceptance bearer token in plaintext.
    Never reconstructable afterward; losing it means creating a new
    credential and revoking this one."""

    token: str


class EnvironmentalContextSettings(BaseModel):
    """The one opt-in, local-only Place location setting (Environmental
    Context Foundation v1) -- see docs/environmental-context-foundation-
    v1-contract.md "Place coordinates: a deliberate, narrow exception...".
    Always rounded to ~11 km before being persisted; `coarse_` in the
    field names encodes that contract, not just a comment. Never read by,
    or written from, `CamtrapDpExportRequest.latitude`/`.longitude` or
    `RecordedAudioAnalysisRequest.latitude`/`.longitude`, which remain
    explicit-per-call-only and untouched by this milestone."""

    coarse_latitude: float | None = None
    coarse_longitude: float | None = None
    configured: bool
    # Environmental Context v2: a second, independent opt-in, separate from
    # `configured` above -- see docs/environmental-context-v2-contract.md
    # "Phase 16" / "Privacy / location". Configuring coordinates enables
    # only local, offline solar computation; this flag is the explicit,
    # separate consent required before this installation ever sends that
    # coordinate to an external weather provider over the network.
    weather_enabled: bool = False
    updated_at: datetime


class EnvironmentalContextSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    weather_enabled: bool = False

    @field_validator("latitude", "longitude")
    @classmethod
    def _round_to_coarse_precision(cls, value: float | None) -> float | None:
        """Round here too (the repository setter is the authoritative,
        defense-in-depth enforcement point) so a caller inspecting this
        request's own validated value never sees a precision the stored
        value will not actually have."""

        return value if value is None else round(value, 1)

    @model_validator(mode="after")
    def _both_or_neither(self) -> "EnvironmentalContextSettingsUpdate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be set, or both omitted")
        return self


class SolarContext(BaseModel):
    """Locally-derived solar/daylight context for one date at the
    configured Place location. `information_class` is always `"inferred"`
    when present -- the same closed Measured/Inferred/Reviewed vocabulary
    in product-doctrine.md "Measured, Inferred, and Reviewed" that governs
    every other domain in this product, not a fourth, domain-specific
    value. Solar geometry is computed deterministically from Place
    coordinates and a UTC instant via a documented algorithm (`astral`),
    never read from a physical sensor, so it is not "Measured"; no human
    reviews or confirms it, so it is not "Reviewed"; that leaves
    "Inferred" -- model/algorithm-derived intelligence -- which is correct
    here even though the computation is deterministic and repeatable:
    repeatability is not the same property as direct physical measurement
    (see docs/environmental-context-foundation-v1-contract.md "Information
    class / provenance" for the full reasoning). `provider_key` carries
    *which* mechanism produced this record (`"solar_local"` for v1); that
    identity belongs there, never in `information_class`.
    `available=False` is a normal, expected outcome (no location
    configured, or a genuine polar day/night date) -- never an error;
    every other field is `None` in that case, never guessed."""

    available: bool
    reason: Literal["not_configured", "computed", "unavailable_for_date"] | None = None
    sunrise_at: datetime | None = None
    sunset_at: datetime | None = None
    daylight_state: Literal["day", "night"] | None = None
    provider_key: str | None = None
    information_class: Literal["inferred"] | None = None
    basis_latitude: float | None = None
    basis_longitude: float | None = None


class WeatherConditions(BaseModel):
    """One resolved weather snapshot from the `open_meteo` provider
    (Environmental Context v2 -- see docs/environmental-context-v2-
    contract.md). `information_class` is always `"inferred"`, never
    `"measured"`: every value here is a gridded/interpolated numerical-
    weather-prediction estimate for the Place's coordinate, not a direct
    physical-sensor reading, including "current" conditions -- the same
    reasoning `SolarContext` already applies to deterministic solar
    computation, extended to a genuinely probabilistic external estimate
    (see product-doctrine.md "Measured, Inferred, and Reviewed").

    `status` carries *why* weather may be unavailable, independently of the
    containing response's own `available`/`reason` (which describe solar):
    `"not_configured"` (no location), `"disabled"` (location set but
    weather not opted in), `"out_of_range"` (older than the provider's
    bounded window, or in the future), `"unavailable"` (provider failure,
    nothing cached), `"stale"` (cached data exists but is older than the
    refresh interval and a refresh attempt just failed), `"available"`.
    Every value field below is `None` unless `status` is `"available"` or
    `"stale"`. `temperature_band` is `None` whenever this Place's own
    recent temperature baseline is not yet established (Phase 7: never an
    absolute-threshold claim without a Place-relative basis)."""

    status: Literal["available", "not_configured", "disabled", "out_of_range", "unavailable", "stale"]
    observed_at: datetime | None = None
    retrieved_at: datetime | None = None
    provider_key: str | None = None
    information_class: Literal["inferred"] | None = None
    air_temperature_c: float | None = None
    relative_humidity_percent: float | None = None
    precipitation_mm: float | None = None
    snowfall_cm: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_degrees: float | None = None
    cloud_cover_percent: float | None = None
    surface_pressure_hpa: float | None = None
    temperature_band: Literal["cooler_than_typical", "typical", "warmer_than_typical"] | None = None
    precipitation_state: Literal["dry", "rain", "snow"] | None = None
    summary_text: str | None = None


class VisitEnvironmentalContext(SolarContext):
    visit_id: str
    evaluated_at: datetime | None = None
    # Environmental Context v2: `None` only when weather has never been
    # resolved for this response at all (defensive; every real call site
    # populates it -- see `ProductRepository.get_visit_environmental_
    # context`). Absence of *data* is expressed via `weather.status`, not by
    # this field being `None`.
    weather: WeatherConditions | None = None


class PlaceEnvironmentalContext(SolarContext):
    for_date: date
    weather: WeatherConditions | None = None


# --- Habitat & Phenology Foundation v1 -------------------------------------
# See docs/habitat-phenology-foundation-v1-contract.md. A separate domain
# from Environmental Context Foundation above (durable/dated *user-recorded*
# facts about a Place's habitat and biological season, never a sensor/solar
# computation), but deliberately reusing that milestone's naming and
# temporal-honesty conventions where the same shape genuinely applies.

HabitatFactCategory = Literal["setting", "vegetation", "feature"]
PhenologyStatus = Literal["current", "recent", "past"]


class PlaceHabitatFact(BaseModel):
    """A durable, user-recorded habitat fact -- see `PlaceHabitatFactModel`
    for the full field-by-field rationale. `information_class` is
    deliberately a single-value `Literal["reviewed"]` here (unlike the DB
    column, which stays a plain string so a future writer can honestly
    report a different doctrine-legal value, e.g. `"inferred"` for an
    automatic plant-recognition analyzer) because v1's only writer is a
    human describing their own Place -- mirrors `SolarContext.
    information_class: Literal["inferred"]`'s identical "the response type
    reflects what can actually be returned today" discipline."""

    id: str
    category: HabitatFactCategory
    label: str
    note: str | None = None
    information_class: Literal["reviewed"]
    provenance: str
    created_at: datetime
    updated_at: datetime


class PlaceHabitatFactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: HabitatFactCategory
    label: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)


class PlaceHabitatFactUpdate(BaseModel):
    """Partial update (PATCH semantics): an omitted/`None` field leaves the
    stored value unchanged, mirroring `ZoneUpdate`. `note` is the one
    exception, since it is the only optional field here and PATCH
    semantics otherwise offer no way to clear one: an explicit empty
    string (`""`) clears the stored note to `NULL`; `None`/omitted leaves
    it unchanged. Documented here rather than silently relied upon."""

    model_config = ConfigDict(extra="forbid")

    category: HabitatFactCategory | None = None
    label: str | None = Field(default=None, min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_change(self) -> "PlaceHabitatFactUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("Provide at least one field to update.")
        return self


class PlacePhenologyObservation(BaseModel):
    """A dated/interval phenology observation -- see
    `PlacePhenologyObservationModel` for the full field-by-field rationale.
    `status` is computed at read time (never persisted -- mirrors
    `PlaceEnvironmentalContext.daylight_state`'s identical "classification
    is derived, not frozen at write time" discipline) via
    `mockingbird.habitat.phenology.classify_phenology_status` against the
    current UTC calendar date; a historical observation whose interval does
    not cover today is honestly `"past"`, never silently still `"current"`.
    """

    id: str
    subject_label: str
    phenomenon: str
    information_class: Literal["reviewed"]
    provenance: str
    observed_start_date: date
    observed_end_date: date | None = None
    note: str | None = None
    status: PhenologyStatus
    created_at: datetime
    updated_at: datetime


class PlacePhenologyObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_label: str = Field(min_length=1, max_length=120)
    phenomenon: str = Field(min_length=1, max_length=120)
    observed_start_date: date
    # `None` means a single-date observation -- see `PlacePhenologyObservationModel`
    # "observed_end_date=NULL" -- never "ongoing indefinitely."
    observed_end_date: date | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> "PlacePhenologyObservationCreate":
        if self.observed_end_date is not None and self.observed_end_date < self.observed_start_date:
            raise ValueError("observed_end_date must not be before observed_start_date")
        return self


class PlacePhenologyObservationUpdate(BaseModel):
    """Partial update (PATCH semantics), matching `PlaceHabitatFactUpdate`
    exactly, including the same empty-string-clears-`note` convention. A
    plain `date | None` field cannot itself distinguish "omit this field"
    from "explicitly set it to null" under PATCH semantics, so clearing a
    previously-set `observed_end_date` back to "single-date observation"
    uses a separate explicit flag instead of overloading the date field: a
    real date value sets it, `None`/omitted leaves it unchanged, and
    `clear_observed_end_date=True` clears it -- checked ahead of
    `observed_end_date` in the repository so a caller cannot set both at
    once and have one silently win."""

    model_config = ConfigDict(extra="forbid")

    subject_label: str | None = Field(default=None, min_length=1, max_length=120)
    phenomenon: str | None = Field(default=None, min_length=1, max_length=120)
    observed_start_date: date | None = None
    observed_end_date: date | None = None
    clear_observed_end_date: bool = False
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_change(self) -> "PlacePhenologyObservationUpdate":
        if not self.model_dump(exclude_none=True) and not self.clear_observed_end_date:
            raise ValueError("Provide at least one field to update.")
        return self

    @model_validator(mode="after")
    def _end_not_before_start(self) -> "PlacePhenologyObservationUpdate":
        if (
            self.observed_start_date is not None
            and self.observed_end_date is not None
            and self.observed_end_date < self.observed_start_date
        ):
            raise ValueError("observed_end_date must not be before observed_start_date")
        return self

    @model_validator(mode="after")
    def _no_conflicting_end_date_instruction(self) -> "PlacePhenologyObservationUpdate":
        if self.clear_observed_end_date and self.observed_end_date is not None:
            raise ValueError(
                "Provide either observed_end_date or clear_observed_end_date, not both."
            )
        return self


class PlaceHabitatContext(BaseModel):
    """The compact, efficient "what's relevant right now" bundle for a
    Today-style surface -- deliberately separate from the full CRUD list
    endpoints (`GET /api/place/habitat`, `GET /api/place/phenology`),
    mirroring exactly how `GET /api/place/environmental-context/today` is
    its own dedicated read rather than a field bolted onto a fuller report
    (see "API surface" in docs/environmental-context-foundation-v1-
    contract.md, the same reasoning applied here). Habitat facts are
    durable/open-ended so the full list is always "current" by
    definition; phenology is split into `current_phenology`
    (`status == "current"`) and `recent_phenology`
    (`status == "recent"`) so a caller never has to re-derive that
    distinction -- and never receives `"past"` entries here at all."""

    habitat_facts: list[PlaceHabitatFact]
    current_phenology: list[PlacePhenologyObservation]
    recent_phenology: list[PlacePhenologyObservation]


# Place Features & Habitat Change v2 -- see docs/place-features-habitat-
# change-v2-contract.md. Re-declared locally rather than imported from
# `mockingbird.habitat.place_feature`, matching this file's existing
# no-cross-package-import convention for closed vocabularies (see
# `HabitatFactCategory`/`PhenologyStatus`, just above).
PlaceFeatureType = Literal[
    "feeder", "water", "nest_box", "vegetation_patch", "structure", "habitat_area", "other"
]
PlaceFeatureChangeEventType = Literal[
    "added",
    "removed",
    "moved",
    "modified",
    "replenished",
    "food_changed",
    "vegetation_changed",
    "other",
]
# Narrower than `conditional_association.AssociationStatus`: `"insufficient_
# data"` is never present here because a `PlaceFeatureAssociation` with no
# trustworthy verdict is represented by `maturity`/`status=None` instead --
# mirrors `PlaceActivityReportHabitatAssociation`'s identical 3-value
# narrowing.
FeatureAssociationStatus = Literal[
    "no_clear_association", "more_common_under_condition", "less_common_under_condition"
]
FeatureComparisonMaturity = Literal[
    "too_soon", "insufficient_coverage", "early_signal", "comparable"
]

# Environmental Context x Place Story & Habitat Change Composition v1: why an
# environmental-context comparison for one Feature change event has (or does
# not yet have) something to say. `"not_configured"`/`"disabled"` mirror
# `WeatherConditions.status`'s own identical two values verbatim (no Place
# location set; a location is set but weather was never opted in).
# `"insufficient_coverage"` mirrors `FeatureComparisonMaturity`'s own value
# (not enough locally cached weather over these specific before/after
# windows -- a distinct, independent gate from the wildlife side's own
# coverage floor). `"comparable"` means enough weather was cached to say
# *something*, including the honest "nothing meaningfully different" case --
# see `FeatureEnvironmentalComparison.summary`.
EnvironmentalComparisonStatus = Literal[
    "not_configured", "disabled", "insufficient_coverage", "comparable"
]


class PlaceFeatureObservationLink(BaseModel):
    """One camera/Zone observation view of a Place Feature -- see
    `PlaceFeatureObservationLinkModel` for the full field-by-field
    rationale. `source_name`/`zone_name`/`source_archived` are joined in
    fresh at read time (never stored redundantly), so a camera rename is
    always reflected immediately and never breaks the link -- see the
    governing brief's "Source / Stream identity"."""

    id: str
    source_id: str
    source_name: str
    source_archived: bool
    zone_id: str | None = None
    zone_name: str | None = None
    created_at: datetime


class PlaceFeatureObservationLinkCreate(BaseModel):
    """At least one of `source_id`/`zone_id` is required -- unlike
    `PlaceFeatureCreate`/`PlaceFeatureUpdate`'s own identical pair (where
    both `None` validly means "no association yet"), a dedicated "add a
    view" call with neither would add nothing. `zone_id`, when given, is
    authoritative over `source_id` exactly as `PlaceFeatureModel`'s own
    association resolution already works (see `ProductRepository.
    _resolve_feature_association`), reapplied per link."""

    model_config = ConfigDict(extra="forbid")

    source_id: str | None = None
    zone_id: str | None = None

    @model_validator(mode="after")
    def _require_source_or_zone(self) -> "PlaceFeatureObservationLinkCreate":
        if self.source_id is None and self.zone_id is None:
            raise ValueError("Provide a camera or Zone to link.")
        return self


class PlaceFeature(BaseModel):
    """A durable, user-recorded Place Feature -- see `PlaceFeatureModel`
    for the full field-by-field rationale. `information_class` is a single-
    value `Literal["reviewed"]` here (the DB column stays a plain string),
    mirroring `PlaceHabitatFact.information_class`'s identical "the
    response type reflects what can actually be returned today" discipline."""

    id: str
    feature_type: PlaceFeatureType
    name: str
    note: str | None = None
    is_active: bool
    installed_date: date | None = None
    removed_date: date | None = None
    source_id: str | None = None
    """Compatibility mirror, not the source of truth: populated only when
    this Feature has exactly one observation link (byte-identical to
    every pre-multi-view Feature's own value), and `None` for zero or
    two-or-more links -- see `observation_links` and
    `PlaceFeatureModel`'s own updated docstring."""
    zone_id: str | None = None
    """Compatibility mirror of `observation_links`'s single link, under
    the identical rule as `source_id` above."""
    feeder_food_type: str | None = None
    information_class: Literal["reviewed"]
    provenance: str
    created_at: datetime
    updated_at: datetime
    observation_links: list[PlaceFeatureObservationLink] = Field(default_factory=list)
    """The canonical, possibly-plural relationship set (Multi-Camera Place
    Feature Linking & Cross-View Habitat Context v1) -- zero, one, or many
    camera/Zone views of this one Feature. Use
    `POST .../observation-links`/`DELETE .../observation-links/{id}` to
    add or remove a view; `source_id`/`zone_id` above are a read-only
    compatibility mirror only."""


class PlaceFeatureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_type: PlaceFeatureType
    name: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    installed_date: date | None = None
    source_id: str | None = None
    zone_id: str | None = None
    feeder_food_type: str | None = Field(default=None, max_length=120)


class PlaceFeatureUpdate(BaseModel):
    """Partial update (PATCH semantics), mirroring `PlaceHabitatFactUpdate`:
    an omitted/`None` field leaves the stored value unchanged; an explicit
    empty string (`""`) clears `note`/`feeder_food_type`/`source_id`/
    `zone_id` to `NULL`. Clearing `source_id` also clears `zone_id` (a Zone
    always implies a Source -- see `PlaceFeatureModel`'s association
    reasoning); clearing only `zone_id` leaves `source_id` as-is ("still
    this camera, no specific Zone drawn"). `removed_date` is deliberately
    not present here at all -- it is only ever set by recording a
    `event_type="removed"` change event (see `PlaceFeatureModel`'s
    docstring).

    `source_id`/`zone_id` here are a legacy, full-replacement compatibility
    operation, preserved unchanged from before multi-view linking existed:
    setting either **replaces this Feature's entire observation-link set**
    with exactly the one view given (or clears it to zero views, for
    `source_id=""`) -- it is not an incremental add. A Feature that already
    has more than one linked view should be edited with
    `POST/DELETE .../observation-links` instead; using this field on such a
    Feature is a deliberate, documented "collapse back to one view"
    operation, never a silent one."""

    model_config = ConfigDict(extra="forbid")

    feature_type: PlaceFeatureType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    installed_date: date | None = None
    clear_installed_date: bool = False
    source_id: str | None = None
    zone_id: str | None = None
    feeder_food_type: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _require_change(self) -> "PlaceFeatureUpdate":
        if not self.model_dump(exclude_none=True) and not self.clear_installed_date:
            raise ValueError("Provide at least one field to update.")
        return self

    @model_validator(mode="after")
    def _no_conflicting_installed_date_instruction(self) -> "PlaceFeatureUpdate":
        if self.clear_installed_date and self.installed_date is not None:
            raise ValueError("Provide either installed_date or clear_installed_date, not both.")
        return self


class PlaceFeatureChangeEvent(BaseModel):
    """A durable, user-recorded, dated fact about something that changed
    around the Place -- see `PlaceFeatureChangeEventModel` for the full
    field-by-field rationale."""

    id: str
    feature_id: str | None = None
    event_type: PlaceFeatureChangeEventType
    effective_date: date
    note: str | None = None
    prior_value: str | None = None
    new_value: str | None = None
    information_class: Literal["reviewed"]
    provenance: str
    created_at: datetime
    updated_at: datetime


class PlaceFeatureChangeEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str | None = None
    event_type: PlaceFeatureChangeEventType
    effective_date: date
    note: str | None = Field(default=None, max_length=500)
    prior_value: str | None = Field(default=None, max_length=200)
    new_value: str | None = Field(default=None, max_length=200)


class PlaceFeatureChangeEventUpdate(BaseModel):
    """Partial update (PATCH semantics), matching `PlaceFeatureUpdate`'s
    identical empty-string-clears convention for `note`/`prior_value`/
    `new_value`."""

    model_config = ConfigDict(extra="forbid")

    event_type: PlaceFeatureChangeEventType | None = None
    effective_date: date | None = None
    note: str | None = Field(default=None, max_length=500)
    prior_value: str | None = Field(default=None, max_length=200)
    new_value: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _require_change(self) -> "PlaceFeatureChangeEventUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("Provide at least one field to update.")
        return self


class PlaceFeatureAssociation(BaseModel):
    """One change event's before/after comparison outcome -- association
    language only, never causal (see `mockingbird.analytics.feature_change_
    comparison`). Every field beyond `maturity` is `None` exactly when
    `maturity` is `"too_soon"` or `"insufficient_coverage"` -- no
    comparable window exists yet, so there is nothing honest to show beyond
    that maturity state itself."""

    maturity: FeatureComparisonMaturity
    window_days: int | None = None
    pre_start: date | None = None
    post_end: date | None = None
    status: FeatureAssociationStatus | None = None
    presence_days_in_condition: int | None = None
    usable_days_in_condition: int | None = None
    presence_days_out_of_condition: int | None = None
    usable_days_out_of_condition: int | None = None


class FeatureEnvironmentalComparison(BaseModel):
    """Restrained, non-causal environmental context over the *identical*
    before/after calendar-day windows `PlaceFeatureAssociation` already
    established for the same change event (see `mockingbird.analytics.
    environmental_period_comparison` "No new statistical primitive") --
    context only, never a cause: this never claims weather explains a
    wildlife change, only that conditions differed (or did not) between the
    two periods. `pre_start`/`post_end`/`window_days` are always populated
    whenever this object exists at all (mirroring the sibling
    `PlaceFeatureAssociation`'s own window fields) so a caller can state
    *which* period was or was not compared even when `status` is not
    `"comparable"`. Every other field is `None` unless `status ==
    "comparable"`; `summary` is the one restrained, ready-to-render sentence
    ("The after period was notably cooler." / "Conditions were broadly
    similar across the two periods.") -- always non-`None` when `status ==
    "comparable"`, since the neutral "similar" case is itself a valid,
    intentional answer on this dedicated comparison surface (contrast Place
    Story's own stricter, never-neutral `comparison_insight` caveat)."""

    status: EnvironmentalComparisonStatus
    window_days: int | None = None
    pre_start: date | None = None
    post_end: date | None = None
    information_class: Literal["inferred"] | None = None
    provider_key: str | None = None
    pre_mean_temperature_c: float | None = None
    post_mean_temperature_c: float | None = None
    pre_total_precipitation_mm: float | None = None
    post_total_precipitation_mm: float | None = None
    summary: str | None = None


class PlaceFeatureChangeEventWithComparison(BaseModel):
    """One change event plus its own before/after comparison, computed
    fresh at read time -- never persisted (see `PlaceFeatureChangeEventModel`
    "Correction model"), so a correction to the event is reflected on the
    very next read with no invalidation step required."""

    event: PlaceFeatureChangeEvent
    comparison: PlaceFeatureAssociation | None = None
    """`None` only when the event's Feature has no camera/Zone association
    to compare against (`feature_id=None`, or a Feature with zero
    `observation_links`) -- distinct from a `maturity` of `"too_soon"`/
    `"insufficient_coverage"`, which means an association *was* attempted
    (across every one of the Feature's own linked views, unioned and
    cross-camera-deduplicated) but is not yet trustworthy."""
    environmental_comparison: FeatureEnvironmentalComparison | None = None
    """`None` under the identical condition as `comparison` being `None`
    (no monitoring scope), plus one further case: `comparison.maturity` is
    `"too_soon"`/`"insufficient_coverage"` (no before/after window exists
    yet at all for the wildlife side, so there is no period for
    environmental context to align with either) -- computed fresh at read
    time exactly like `comparison`, with the identical correction-safety
    property."""


class PlaceFeatureYieldSummary(BaseModel):
    """A recent-window activity snapshot for one Feature's own associated
    monitoring scope -- see `mockingbird.analytics.feature_yield`."""

    confirmed_wildlife_visit_count: int
    distinct_taxon_count: int
    monitored_seconds: float | None = None
    visits_per_monitored_hour: float | None = None
    data_sufficient: bool
    window_days: int


class PlaceFeatureDetail(BaseModel):
    """The full detail bundle for one Feature: current state, its complete
    change-event timeline (each with its own before/after comparison), and
    a recent-window activity snapshot. Deliberately separate from the plain
    CRUD list endpoint, mirroring `GET /api/place/habitat-context`'s
    identical "dedicated bundle, not a field bolted onto a fuller report"
    precedent."""

    feature: PlaceFeature
    changes: list[PlaceFeatureChangeEventWithComparison]
    recent_yield: PlaceFeatureYieldSummary | None = None
    """`None` when the Feature has zero observation links -- yield cannot
    honestly be computed without at least one. Otherwise computed across
    every one of the Feature's own linked views, unioned (coverage) and
    cross-camera-deduplicated (Visit counts)."""
    representative_evidence: RepresentativeEvidence | None = None
    """Place Story Deep Dives & Representative Evidence v1: the single best
    already-persisted evidence image across every confirmed Visit in this
    Feature's own linked camera/Zone views (all Feature history, not just
    `recent_yield`'s bounded window -- mirrors Bird Log's own unbounded-
    history representative-evidence precedent). Reuses the identical Gate C
    selector `PlaceActivityReportTaxonEntry.representative_evidence`/
    `WildlifeJournalLabelSummary.representative` already use, unmodified --
    never a second "best image" engine. `None` is a fully honest outcome:
    zero observation links, zero confirmed Visits in scope, or every
    candidate's underlying media file missing -- never an error, and never
    an unrelated frame chosen merely to fill layout."""


class PlaceFeaturesSummary(BaseModel):
    """A compact, Dashboard-safe bundle: how many active Features exist,
    how many changes were recorded recently, and at most one restrained,
    backend-composed highlight sentence -- never a raw ranking table (Phase
    20 of the governing brief: "Do not flood Today")."""

    active_feature_count: int
    recent_change_count: int
    highlight: str | None = None


class PlaceFeatureComparisonRow(BaseModel):
    """Place Feature Comparison & Habitat Outcomes v1: one Feature's own
    comparable facts, for a Place-wide overview -- see
    docs/place-feature-comparison-habitat-outcomes-v1-contract.md
    "Core deliverable A." Every field is reused, unmodified, from an
    already-accepted single-Feature primitive; nothing here is computed
    only for this row. `latest_change` deliberately carries only this
    Feature's single most-recent change event (never its full history --
    that stays one click away at this Feature's own Story/detail page)
    so a Place-wide overview stays proportionate to Feature count, not
    to total change-event count across every Feature."""

    feature: PlaceFeature
    recent_yield: PlaceFeatureYieldSummary | None = None
    """`None` under the identical condition as `PlaceFeatureDetail.recent_
    yield` -- zero observation links. Never a fabricated zero rate."""
    latest_change: PlaceFeatureChangeEventWithComparison | None = None
    """`None` when this Feature has no recorded change events at all --
    an honest "nothing recorded yet," distinct from a change event
    existing whose own `comparison` is `None`/`too_soon`."""
    representative_evidence: RepresentativeEvidence | None = None
    """Identical selection/semantics to `PlaceFeatureDetail.representative_
    evidence` -- the single best already-persisted evidence image across
    this Feature's entire history, never a second "best image" engine."""


class PlaceFeatureComparisonOverview(BaseModel):
    """Place Feature Comparison & Habitat Outcomes v1: the bounded,
    Place-wide comparison surface -- see docs/place-feature-comparison-
    habitat-outcomes-v1-contract.md. `features` is Core Deliverable A
    (one row per Feature); `change_outcomes` is Core Deliverable B (one
    entry per Reviewed change event that has an attempted before/after
    comparison -- i.e. its own Feature had at least one observation link
    at the time of the request, so a comparison was at least attempted,
    whatever its `maturity` turned out to be). Computed fresh from
    current rows on every call, never persisted -- a correction to any
    underlying Feature, change event, or observation link is reflected
    on the very next call with no invalidation step, mirroring
    `PlaceFeatureDetail`'s identical correction-safety property.
    Deliberately not paginated: Features and their manually-recorded
    change events are both realistically small-N per Place (a person
    must deliberately record each one), unlike Visits -- see the
    contract's own "Non-goals reaffirmed" section."""

    generated_at: datetime
    features: list[PlaceFeatureComparisonRow]
    change_outcomes: list[PlaceFeatureChangeEventWithComparison]


class TaxonPlaceContext(BaseModel):
    """Restrained, non-causal habitat/environmental context associated with
    one taxon's single most recent reviewed observation at this Place --
    see "Habitat + Environment Connection" in docs/biodiversity-place-
    intelligence-v1-contract.md. Descriptive association only ("recorded
    near sunrise", "recorded while a phenomenon was current"), never a
    claim that context caused the observation. `environmental_context` is
    never `None` -- it mirrors `SolarContext`'s own established convention
    of an always-present object whose `available` flag carries honest
    absence (not configured / unavailable for that date), matching
    `PlaceEnvironmentalContext`/`VisitEnvironmentalContext` exactly.
    `phenology_context` is independently honest-absent as `[]` when no
    phenomenon was current as of that observation -- neither field ever
    blocks or degrades the other."""

    observed_at: datetime
    environmental_context: SolarContext
    phenology_context: list[PlacePhenologyObservation] = Field(default_factory=list)


class PlaceBiodiversityTaxonEntry(BaseModel):
    """One all-time-confirmed taxon's identity plus its canonical
    historical status -- reuses `PlaceActivityReportTaxonHistoricalStatus`
    verbatim (the exact same nested shape Today's report already returns)
    so a taxon's status here can never silently disagree with what Today
    or Bird Log show for the same taxon at the same moment. See
    docs/canonical-new-regular-species-contract.md."""

    label: str
    display_name: str
    category: LabelCategory
    is_species: bool
    historical_status: PlaceActivityReportTaxonHistoricalStatus


class PlaceBiodiversitySummaryResponse(BaseModel):
    """A Place-wide, "as of right now" biodiversity summary -- see
    docs/biodiversity-place-intelligence-v1-contract.md. A live view, not a
    fixed report period, unlike `PlaceActivityReportResponse`: re-requesting
    later can honestly change the answer as new reviewed observations and
    monitoring history accumulate.

    `taxa`/`new_taxa`/`regular_taxa`/`recently_observed_taxa` are built
    exclusively from authoritative reviewed truth. `provisional_taxa`
    (unreviewed AI suggestions, the same `DashboardTodaySpecies` shape
    Bird Log's "Likely sightings" panel already renders) is a structurally
    separate list that can never inflate any of the authoritative counts
    above it. `new_taxa`/`regular_taxa`/`recently_observed_taxa` are
    convenience subsets of `taxa`, not a partition: a taxon may appear in
    more than one, in none of the three, or -- for `regular_taxa` without
    `recently_observed_taxa` -- be a regular visitor simply not seen in the
    last two weeks, which this response never states as "absent"."""

    generated_at: datetime
    historical_baseline: PlaceActivityReportHistoricalBaseline
    distinct_species_count: int = Field(ge=0)
    taxa: list[PlaceBiodiversityTaxonEntry] = Field(default_factory=list)
    new_taxa: list[PlaceBiodiversityTaxonEntry] = Field(default_factory=list)
    regular_taxa: list[PlaceBiodiversityTaxonEntry] = Field(default_factory=list)
    recently_observed_taxa: list[PlaceBiodiversityTaxonEntry] = Field(default_factory=list)
    provisional_taxa: list[DashboardTodaySpecies] = Field(default_factory=list, max_length=20)
    habitat_context: PlaceHabitatContext
    environmental_context: PlaceEnvironmentalContext
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Year-over-Year Seasonality & Long-Term Place Memory v1 -- see
# `mockingbird.analytics.year_over_year_comparison` and docs/year-over-year-
# seasonality-long-term-place-memory-v1-report.md. Mirrors that pure
# module's vocabulary field-for-field (the same "response type mirrors the
# pure module, never a second definition" discipline `PlaceStoryEntry`,
# above, already follows), and reuses `PlaceFeatureAssociation`'s own
# flattened-`ConditionalAssociation` field shape/naming for
# `PlaceYearOverYearAssociation` below rather than inventing a second
# association wrapper shape.
# ---------------------------------------------------------------------------

PlaceYearOverYearStatus = Literal[
    "comparable",
    "no_material_difference",
    "insufficient_prior_history",
    "insufficient_current_coverage",
    "insufficient_prior_coverage",
    "partial_period",
]
PlaceYearOverYearActivityDirection = Literal["higher", "lower", "similar"]
PlaceYearOverYearTimingStatus = Literal["comparable", "insufficient_data"]
# Deliberately the *full* `ConditionalAssociation.status` range (unlike
# `FeatureAssociationStatus`, above, which excludes `"insufficient_data"`
# because `FeatureChangeComparison`'s own contract guarantees `association`
# is `None` whenever that value would occur): a year-over-year comparison's
# `association` is always populated, even in an abstention status, so its
# own `status` can legitimately be `"insufficient_data"` (see `PlaceYear
# OverYearAssociation`, below).
PlaceYearOverYearAssociationStatus = Literal[
    "insufficient_data", "no_clear_association", "more_common_under_condition", "less_common_under_condition"
]


class PlaceYearOverYearPeriod(BaseModel):
    """One compared period's own summary facts -- current or prior year.
    `is_complete` is `False` only for a current, still-in-progress calendar
    period (a month not yet finished); the prior-year comparable period is
    always complete."""

    start_date: date
    end_date: date
    is_complete: bool
    usable_day_count: int = Field(ge=0)
    monitored_seconds: float | None = None
    confirmed_wildlife_visit_count: int = Field(ge=0)


class PlaceYearOverYearAssociation(BaseModel):
    """The underlying presence-day-rate facts behind one year-over-year
    verdict -- reuses `PlaceFeatureAssociation`'s own flattened
    `ConditionalAssociation` field naming verbatim (same field names), but
    with the *full* `PlaceYearOverYearAssociationStatus` range: unlike
    `PlaceFeatureAssociation` (whose `association` is `None` precisely when
    its status would be `"insufficient_data"`), a year-over-year
    comparison's `association` is always populated, even in an abstention
    status, so drill-down can still show the underlying counts (e.g. "0 of
    5 usable days" behind an `insufficient_current_coverage` verdict)."""

    status: PlaceYearOverYearAssociationStatus | None = None
    presence_days_in_condition: int | None = None
    usable_days_in_condition: int | None = None
    presence_days_out_of_condition: int | None = None
    usable_days_out_of_condition: int | None = None


class PlaceYearOverYearComparison(BaseModel):
    """The Place-wide year-over-year comparison for one current period
    against its prior-year comparable period. `overall_activity` is
    populated exactly when `status` is `"comparable"` (a real difference)
    or `"no_material_difference"` (`"similar"`) -- `None` for every
    abstention status."""

    policy_version: int = Field(ge=1)
    current_period: PlaceYearOverYearPeriod
    prior_period: PlaceYearOverYearPeriod
    status: PlaceYearOverYearStatus
    overall_activity: PlaceYearOverYearActivityDirection | None = None
    association: PlaceYearOverYearAssociation | None = None
    information_class: Literal["inferred"] = "inferred"


class PlaceYearOverYearSpeciesEntry(BaseModel):
    """One taxon's year-over-year activity comparison, plus an optional
    first-observed-timing comparison. `first_observed_day_difference` is
    negative when the taxon was first observed earlier this period than in
    the prior-year comparable period; populated only when `first_observed_
    timing_status == "comparable"`. `first_observed_is_material` gates
    whether the day-difference is large enough to narrate (see
    `mockingbird.analytics.year_over_year_comparison.
    MIN_MATERIAL_TIMING_DIFFERENCE_DAYS`) -- a UI should not state a timing
    claim when this is `False`, even though the underlying dates are still
    disclosed for drill-down."""

    label: str
    display_name: str
    category: LabelCategory
    is_species: bool
    status: PlaceYearOverYearStatus
    activity_direction: PlaceYearOverYearActivityDirection | None = None
    association: PlaceYearOverYearAssociation | None = None
    current_first_observed_date: date | None = None
    prior_first_observed_date: date | None = None
    first_observed_timing_status: PlaceYearOverYearTimingStatus
    first_observed_day_difference: int | None = None
    first_observed_is_material: bool


class PlaceYearOverYearResponse(BaseModel):
    """`GET /api/place/year-over-year` -- a bounded, calm year-over-year
    summary: the Place-wide comparison plus a small, ranked set of notable
    species-level changes (never every species -- see `select_notable_
    species_changes`'s own bounded-and-ranked-by-evidence-strength
    discipline). Always computed fresh from current rows on every call,
    never cached, matching every other Place read-model's identical
    live-query-always discipline (`PlaceActivityReportResponse`,
    `PlaceStoryResponse`, ...) -- a Reviewed correction is reflected on the
    very next call with no invalidation step."""

    generated_at: datetime
    place: PlaceYearOverYearComparison
    notable_species_changes: list[PlaceYearOverYearSpeciesEntry] = Field(default_factory=list, max_length=5)
    # Place Story Deep Dives & Representative Evidence v1: one taxon's own
    # comparison, populated only when the caller passed `?taxon=` -- reuses
    # the identical `PlaceYearOverYearSpeciesEntry` shape `notable_species_
    # changes` already uses, never a second per-taxon response type. `None`
    # both when no `taxon` was requested and when that taxon has no
    # comparable data (an honest abstention, not an error) -- a Taxon Story
    # header must tell these apart from its own request, not from this
    # field's shape.
    taxon_comparison: PlaceYearOverYearSpeciesEntry | None = None


# ---------------------------------------------------------------------------
# Place Story & Seasonal Timeline v1 -- see
# docs/place-story-seasonal-timeline-v1-report.md. A derived read-model over
# already-authoritative facts (Reviewed wildlife history, Reviewed Place
# Feature changes, Reviewed phenology observations) -- no new durable table,
# no schema change. Mirrors `mockingbird.analytics.place_story`'s own
# vocabulary field-for-field, the same "response type mirrors the pure
# module, never a second definition" discipline every other Place surface
# in this file already follows (see `PlaceFeatureChangeEventType`, above).
# ---------------------------------------------------------------------------

PlaceStoryEventGroup = Literal["wildlife", "place", "context", "summary"]
PlaceStoryEventKind = Literal[
    "first_seen",
    "return",
    "regularity_change",
    "noteworthy_activity",
    "diversity_milestone",
    "feature_change",
    "phenology",
    "comparison_insight",
    "year_over_year",
    "period_summary",
]
PlaceStoryImportance = Literal["major", "notable"]


class PlaceStoryEntry(BaseModel):
    """One Place Story timeline entry -- see `mockingbird.analytics.place_
    story.PlaceStoryEvent` for the full field-by-field rationale. `kind` is
    a stable, machine-readable tag for filtering; `title`/`summary` already
    carry the plain-language, reader-facing text -- the UI must never
    render `kind`/`group` directly as user-facing copy (Phase 3 of the
    governing brief: "do not expose internal enum names directly")."""

    id: str
    kind: PlaceStoryEventKind
    group: PlaceStoryEventGroup
    event_date: date
    event_end_date: date | None = None
    title: str
    summary: str
    information_class: Literal["measured", "inferred", "reviewed"]
    importance: PlaceStoryImportance
    taxon_label: str | None = None
    taxon_display_name: str | None = None
    feature_id: str | None = None
    feature_name: str | None = None
    visit_id: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    source_id: str | None = None
    detail_refs: dict[str, str] = Field(default_factory=dict)


class PlaceStoryResponse(BaseModel):
    """`GET /api/place-story` -- a bounded, filtered, paginated page over
    the merged Place Story. `entries` newest-first (see `build_place_story`'s
    own ordering contract). Always computed fresh from current rows on every
    call, never cached (Phase 15: "no stale narrative truth") -- mirrors
    every other Place read-model's identical live-query-always discipline
    (`PlaceActivityReportResponse`, `PlaceFeatureDetail`, ...)."""

    generated_at: datetime
    period_start_at: datetime
    period_end_at: datetime
    entries: list[PlaceStoryEntry] = Field(default_factory=list, max_length=100)
    has_more: bool
    next_offset: int | None = Field(default=None, ge=0)
    total_matched: int = Field(ge=0)
    # Honest early-experience signal (Phase 23): `True` only when this
    # Place has essentially no accumulated history at all yet -- mirrors
    # `HistoricalPlaceBaseline.maturity == "insufficient"` -- so the
    # frontend can show a calm "your Place Story is just beginning" state
    # instead of a bare empty list indistinguishable from a filter that
    # simply matched nothing.
    is_early_experience: bool
