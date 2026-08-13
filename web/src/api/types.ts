export type SourceKind =
  | "demo"
  | "manual_upload"
  | "local_folder"
  | "rtsp"
  | "local_camera"
  | "webhook"
  | "integration";

export type SourceStatus = "connected" | "disconnected" | "needs_setup" | "archived";
export type SourceConnectionStatusValue =
  | "demo"
  | "not_configured"
  | "configured"
  | "unavailable"
  | "offline"
  | "unsupported";
export type SourceProviderKind =
  | "demo"
  | "placeholder"
  | "future_adapter"
  | "manual_media"
  | "external_url"
  | "local_camera";
export type StreamPlaybackStatusValue =
  | "demo"
  | "not_configured"
  | "unavailable"
  | "offline"
  | "unsupported"
  | "live_ready"
  | "needs_stream_url"
  | "unsupported_rtsp_bridge_required"
  | "unsupported_stream_type"
  | "playback_error"
  | "unknown";
export type StreamPlaybackKind =
  | "placeholder"
  | "demo_panel"
  | "external_url"
  | "media_preview"
  | "mjpeg"
  | "browser_video"
  | "hls"
  | "rtsp"
  | "local_usb"
  | "windows_dshow"
  | "camera_node"
  | "unknown";
export type StreamMonitoringMode = "off" | "armed" | "paused";
export type StreamRuntimeState =
  | "stopped"
  | "starting"
  | "running"
  | "backoff"
  | "blocked"
  | "stopping"
  | "interrupted";
export type CameraHealthState =
  | "healthy"
  | "starting"
  | "waiting_for_capacity"
  | "camera_unavailable"
  | "no_recent_frame"
  | "evidence_storage_degraded"
  | "recovering"
  | "stopped"
  | "setup_incomplete";
export type CameraHealthIncidentCategory =
  | "camera_unavailable"
  | "no_recent_frame"
  | "evidence_persistence_degraded"
  | "recovery_exhausted"
  | "capacity_waiting"
  | "configuration_invalid";
export type ExternalUrlPreviewStatus =
  | "available"
  | "not_configured"
  | "unavailable"
  | "unsupported"
  | "error";
export type ExternalUrlPreviewSaveStatus =
  | "saved"
  | "not_configured"
  | "unavailable"
  | "unsupported"
  | "error";
export type LocalCameraFrameCaptureStatus =
  | "saved"
  | "unavailable"
  | "unsupported"
  | "ffmpeg_missing"
  | "camera_not_configured"
  | "capture_failed";
export type LocalCameraFrameCaptureSource =
  | "live_camera_session"
  | "one_shot_ffmpeg"
  | "unavailable";
export type LiveMotionEvaluationStatus =
  | "evaluated"
  | "start_session_required"
  | "waiting_for_live_frames"
  | "no_recent_frames"
  | "not_enough_frames"
  | "decode_failed"
  | "activity_detected"
  | "no_activity";

export type ZoneType =
  | "feeder"
  | "birdbath"
  | "ground"
  | "perch"
  | "yard"
  | "driveway"
  | "privacy"
  | "ignore";
export type ZoneActivitySensitivity = "low" | "normal" | "high";

export type ReviewStatus = "needs_review" | "reviewed" | "rejected";
export type VisitReviewOutcome =
  | "needs_review"
  | "confirmed_bird"
  | "false_positive"
  | "blank"
  | "ambiguous"
  | "non_bird"
  | "reviewed_other"
  | "rejected";
export type ReviewIdentificationStatus =
  | "suggestion_present"
  | "proposal_present"
  | "configured_available"
  | "ready"
  | "setup_required"
  | "unavailable_no_adapter"
  | "unavailable"
  | "unsupported_media"
  | "no_best_frame"
  | "running"
  | "suggestion_created"
  | "proposal_created"
  | "no_proposal"
  | "failed";
export type FocusCropSource = "zone" | "activity" | "detector" | "manual" | "none";
export type ExportStatus = "ready" | "building" | "failed";
export type DetectionSource = "manual" | "demo_rule" | "future_model" | "integration";
export type DetectionRunStatus = "pending" | "completed" | "failed";
export type DetectionProposalStatus = "proposed" | "accepted" | "rejected" | "converted";
export type DetectionProposalDecision = "accept" | "reject" | "convert_to_event";
export type MotionEvidenceStatus = "pending" | "promoted" | "ignored";
export type ActivitySessionStatus =
  | "new_activity"
  | "ongoing_activity"
  | "cooldown_suppressed"
  | "no_activity";
export type SpeciesSuggestionStatus = "pending" | "accepted" | "rejected" | "superseded";
export type AdapterEvaluationOutcome =
  | "matched_reviewed_truth"
  | "mismatched_reviewed_truth"
  | "awaiting_review"
  | "rejected_evidence"
  | "converted_needs_review"
  | "unknown_reviewed_label";
export type ModelAdapterKind =
  | "object_detector"
  | "species_classifier"
  | "audio_classifier"
  | "motion_filter"
  | "integration"
  | "demo";
export type ModelAdapterStatus = "available" | "not_configured" | "unavailable" | "disabled";
export type ModelAdapterSetupStatus =
  | "available"
  | "setup_required"
  | "unavailable"
  | "demo";
export type LabelCategory =
  | "bird"
  | "mammal"
  | "pet"
  | "person"
  | "vehicle"
  | "object"
  | "false_positive"
  | "unknown";

export interface HealthStatus {
  status: string;
}

export interface TaxonomyLabel {
  id: string;
  label: string;
  display_name: string;
  category: LabelCategory;
  scientific_name?: string | null;
  aliases: string[];
  is_species: boolean;
  is_reviewable: boolean;
  sort_order?: number | null;
}

export type SpeciesCandidatePackStatus = "active" | "archived";

export interface SpeciesCandidatePackSummary {
  id: string;
  display_name: string;
  version: number;
  status: SpeciesCandidatePackStatus;
  is_builtin: boolean;
  candidate_count: number;
  content_sha256: string;
}

export interface SpeciesCandidatePack extends SpeciesCandidatePackSummary {
  description?: string | null;
  members: TaxonomyLabel[];
  created_at: string;
  updated_at: string;
}

export interface SpeciesCandidatePackCreate {
  display_name: string;
  taxonomy_label_ids: string[];
  description?: string | null;
}

export type SpeciesCandidatePackUpdate = SpeciesCandidatePackCreate;

export interface SpeciesCandidatePackCloneRequest {
  display_name?: string | null;
  description?: string | null;
}

export interface StreamSpeciesCandidatePackSelection {
  stream_id: string;
  selected_pack_id?: string | null;
  effective_pack: SpeciesCandidatePackSummary;
  warning?: string | null;
}

export interface StreamSpeciesCandidatePackSelectionUpdate {
  candidate_pack_id: string;
}

export interface CameraSource {
  id: string;
  name: string;
  kind: SourceKind;
  status: SourceStatus;
  description: string;
}

export interface CameraSourceCreateRequest {
  name: string;
}

export interface CameraSourceCreateResponse {
  source: CameraSource;
  stream: Stream;
}

export interface CameraSourceUpdateRequest {
  name?: string;
  archived?: boolean;
}

export interface CameraSourceMutationResult {
  source: CameraSource;
  streams: Stream[];
}

export interface SourceConnectionStatus {
  source_id: string;
  status: SourceConnectionStatusValue;
  provider_kind: SourceProviderKind;
  display_title: string;
  message: string;
  setup_hint?: string | null;
  supports_streams: boolean;
  supports_live_playback: boolean;
  supports_zone_editing: boolean;
  adapter_key?: string | null;
  configured_fields: string[];
  missing_fields: string[];
  stream_ids: string[];
  last_checked_at?: string | null;
}

export interface SourceProviderField {
  key: string;
  label: string;
  required: boolean;
  secret: boolean;
  description?: string | null;
  placeholder?: string | null;
}

export interface SourceProviderDefinition {
  provider_key: string;
  display_name: string;
  description: string;
  status: "available_contract_only" | "future_adapter" | "demo";
  supports_live_playback: boolean;
  supports_zone_editing: boolean;
  fields: SourceProviderField[];
}

export interface SourceProviderConfiguration {
  source_id: string;
  provider_key: string;
  configured_fields: string[];
  missing_fields: string[];
  safe_config_preview: Record<string, string>;
  supports_live_playback: boolean;
  supports_zone_editing: boolean;
  message: string;
  setup_hint?: string | null;
}

export interface SourceProviderConfigurationUpdate {
  provider_key: string;
  config: Record<string, string | null>;
}

export type CameraConfigurationSecretAction = "keep" | "replace" | "remove";

export interface CameraConfigurationValidationSummary {
  status: string;
  message: string;
  missing_fields: string[];
  can_apply: boolean;
}

export interface CameraConfigurationEditResponse {
  stream_id: string;
  source_id: string;
  source_name: string;
  stream_name: string;
  provider_key: string;
  provider_display_name: string;
  editable: boolean;
  editable_fields: SourceProviderField[];
  configured_fields: string[];
  missing_fields: string[];
  field_states: Record<string, "configured" | "not_configured" | string>;
  state_token: string;
  monitoring_policy: StreamMonitoringPolicy;
  runtime: StreamRuntimeStatus;
  health: CameraHealthSummary;
  message: string;
}

export interface CameraConfigurationImpactPreviewRequest {
  provider_key: string;
  config: Record<string, string | null>;
  secret_actions: Record<string, CameraConfigurationSecretAction>;
  node_pairing_token?: string | null;
  source_name?: string | null;
  stream_name?: string | null;
  expected_state_token: string;
}

export interface CameraConfigurationImpactPreview {
  stream_id: string;
  source_id: string;
  provider_key: string;
  state_token: string;
  preview_token: string;
  changed_fields: string[];
  restart_required: boolean;
  requires_explicit_restart_choice: boolean;
  monitoring_desired: StreamMonitoringMode;
  monitoring_actual: StreamRuntimeState;
  open_activity_session_count: number;
  preview_may_be_briefly_unavailable: boolean;
  preservation_summary: string[];
  validation: CameraConfigurationValidationSummary;
  message: string;
}

export interface CameraConfigurationApplyRequest extends CameraConfigurationImpactPreviewRequest {
  preview_token: string;
  idempotency_key: string;
  restart_monitoring: boolean;
}

export interface CameraConfigurationRevision {
  id: string;
  stream_id: string;
  source_id: string;
  provider_key: string;
  changed_fields: string[];
  change_fingerprint: string;
  restart_required: boolean;
  restart_requested: boolean;
  desired_mode: StreamMonitoringMode;
  actual_state_before: StreamRuntimeState;
  actual_state_after: StreamRuntimeState;
  outcome: string;
  created_at: string;
}

export interface CameraConfigurationHistoryResponse {
  items: CameraConfigurationRevision[];
  limit: number;
  message: string;
}

export interface CameraConfigurationApplyResponse {
  configuration: CameraConfigurationEditResponse;
  preview: CameraConfigurationImpactPreview;
  revision: CameraConfigurationRevision;
  idempotent: boolean;
  message: string;
}

export interface CameraSetupOption {
  provider_key: string;
  display_name: string;
  description: string;
  availability: string;
  supports_live_playback: boolean;
  fields: SourceProviderField[];
  message: string;
}

export interface CameraSetupOptionsResponse {
  options: CameraSetupOption[];
  message: string;
}

export interface CameraSetupValidationRequest {
  provider_key: string;
  config: Record<string, string | null>;
  node_pairing_token?: string | null;
}

export interface CameraSetupValidationResponse {
  provider_key: string;
  status: string;
  message: string;
  safe_config_preview: Record<string, string>;
  supports_live_playback: boolean;
  can_continue: boolean;
  preview_available: boolean;
  creates_events: boolean;
  creates_visits: boolean;
  creates_media: boolean;
  creates_truth: boolean;
}

export interface CameraSetupZoneDraft {
  name: string;
  zone_type: ZoneType;
  polygon: Point[];
  is_active: boolean;
  monitoring_policy?: ZoneMonitoringPolicyUpdate | null;
}

export interface CameraSetupCompleteRequest {
  camera_name: string;
  stream_name: string;
  provider_key: string;
  config: Record<string, string | null>;
  node_pairing_token?: string | null;
  zones: CameraSetupZoneDraft[];
  enable_monitoring: boolean;
  idempotency_key: string;
}

export interface CameraSetupCompletionResponse {
  source: CameraSource;
  stream: Stream;
  zones: Zone[];
  monitoring_policy: StreamMonitoringPolicy;
  validation: CameraSetupValidationResponse;
  idempotent: boolean;
  message: string;
}

export interface CameraNodePairRequest {
  base_address: string;
  pairing_code: string;
  /** Set only when this pairing renews an existing "needs renewal" setup;
   * carries its already-entered draft fields over and retires it. */
  renews_pairing_token?: string | null;
}

export interface CameraNodeAdvertisedCamera {
  camera_id: string;
  display_name: string;
  status: string;
  snapshot_supported: boolean;
  setup_hint?: string | null;
  provider_type?: string | null;
}

export interface CameraNodePairResponse {
  pairing_token: string;
  node_id: string;
  display_name: string;
  api_version: string;
  cameras: CameraNodeAdvertisedCamera[];
  message: string;
}

/**
 * Safe, resumable view of a durable Camera Node pairing/setup draft --
 * never the Node address or credential, exactly like a completed camera's
 * saved configuration never returns them either. `status ===
 * "needs_renewal"` means the Node no longer accepts the stored credential;
 * every other field below still reflects what was already entered.
 */
export interface CameraNodePendingSetupResponse {
  pairing_token: string;
  status: "active" | "needs_renewal";
  node_id: string;
  display_name: string;
  api_version: string;
  cameras: CameraNodeAdvertisedCamera[];
  selected_camera_id?: string | null;
  camera_name?: string | null;
  stream_name?: string | null;
  zone_name?: string | null;
  zone_type?: ZoneType | null;
  polygon?: Point[] | null;
  sensitivity?: ZoneActivitySensitivity | null;
  monitoring_enabled: boolean;
  message: string;
}

export interface CameraNodePendingSetupDraftUpdate {
  selected_camera_id?: string | null;
  camera_name?: string | null;
  stream_name?: string | null;
  zone_name?: string | null;
  zone_type?: ZoneType | null;
  polygon?: Point[] | null;
  sensitivity?: ZoneActivitySensitivity | null;
  monitoring_enabled?: boolean | null;
}

export interface CameraNodePendingSetupRevokeRequest {
  pairing_token: string;
}

export interface CameraNodePreviewRequest {
  pairing_token: string;
  camera_id: string;
}

export interface CameraNodePairRevokeRequest {
  stream_id: string;
}

export type SourceSetupReviewStepStatus =
  | "complete"
  | "missing"
  | "future"
  | "available"
  | "unavailable"
  | "warning";

export type SourceSetupReviewReadinessLevel =
  | "demo_ready"
  | "metadata_ready"
  | "needs_setup"
  | "future_adapter_required"
  | "unavailable";

export interface SourceSetupReviewStep {
  key: string;
  label: string;
  status: SourceSetupReviewStepStatus;
  message: string;
}

export interface SourceSetupReviewStream {
  stream_id: string;
  display_name: string;
  playback_status: StreamPlaybackStatusValue;
  playback_kind: StreamPlaybackKind;
  supports_live_playback: boolean;
  supports_zone_editing: boolean;
  message: string;
}

export interface SourceSetupReviewResponse {
  source_id: string;
  provider_key: string;
  provider_display_name: string;
  source_status: SourceConnectionStatusValue;
  readiness_level: SourceSetupReviewReadinessLevel;
  display_title: string;
  summary: string;
  next_step: string;
  configured_fields: string[];
  missing_fields: string[];
  supports_live_playback: boolean;
  supports_zone_editing: boolean;
  stream_count: number;
  streams: SourceSetupReviewStream[];
  steps: SourceSetupReviewStep[];
  warnings: string[];
}

export interface WorkerStatusItem {
  worker_key: string;
  display_name: string;
  category: string;
  state: string;
  enabled: boolean;
  implemented: boolean;
  provider_key?: string | null;
  source_id?: string | null;
  stream_id?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  message: string;
  can_create_media_assets: boolean;
  can_create_motion_evidence: boolean;
  can_create_events: boolean;
  can_create_visits: boolean;
  can_create_review_labels: boolean;
  can_create_truth: boolean;
  warnings: string[];
}

export interface WorkerStatusSummary {
  total_workers: number;
  implemented_workers: number;
  enabled_workers: number;
  running_workers: number;
  failed_workers: number;
  truth_creating_workers: number;
  warnings: string[];
}

export interface WorkerStatusResponse {
  workers: WorkerStatusItem[];
  summary: WorkerStatusSummary;
  generated_at: string;
  read_only: boolean;
}

export interface ExternalUrlWorkerDryRunItem {
  source_id: string;
  source_name: string;
  provider_key: string;
  worker_key: string;
  eligible: boolean;
  state: string;
  would_fetch: boolean;
  would_create_media_asset: boolean;
  would_create_motion_evidence: boolean;
  would_create_event: boolean;
  would_create_visit: boolean;
  would_create_review_label: boolean;
  would_create_truth: boolean;
  reasons: string[];
  warnings: string[];
}

export interface ExternalUrlWorkerDryRunSummary {
  total_sources_considered: number;
  eligible_sources: number;
  ineligible_sources: number;
  would_fetch_count: number;
  would_create_media_asset_count: number;
  would_create_motion_evidence_count: number;
  would_create_truth_count: number;
  warnings: string[];
}

export interface ExternalUrlWorkerDryRunResponse {
  worker_key: string;
  provider_key: string;
  read_only: boolean;
  dry_run: boolean;
  generated_at: string;
  items: ExternalUrlWorkerDryRunItem[];
  summary: ExternalUrlWorkerDryRunSummary;
}

export interface Stream {
  id: string;
  source_id: string;
  name: string;
  description: string;
  is_live: boolean;
}

export interface StreamMonitoringPolicy {
  stream_id: string;
  source_id: string;
  mode: StreamMonitoringMode;
  auto_create_review_candidates: boolean;
  evaluation_interval_seconds: number;
  quiet_period_seconds: number;
  minimum_detection_count: number;
  policy_revision: number;
  armed_at?: string | null;
  paused_at?: string | null;
  updated_at?: string | null;
  pause_reason?: string | null;
  persisted: boolean;
  read_only: boolean;
  continuity_available: boolean;
  can_arm: boolean;
  creates_review_candidates: boolean;
  creates_review_truth: boolean;
  message: string;
  warnings: string[];
}

export interface StreamRuntimeStatus {
  stream_id: string;
  source_id: string;
  desired_mode: StreamMonitoringMode;
  actual_state: StreamRuntimeState;
  observed_policy_revision: number;
  checkpoint_present: boolean;
  active_session_count: number;
  checkpoint_updated_at?: string | null;
  last_start_attempt_at?: string | null;
  last_healthy_frame_at?: string | null;
  exposure_interval_active: boolean;
  current_healthy_duration_seconds?: number | null;
  durable_exposure_today_seconds: number;
  exposure_history_available_from?: string | null;
  latest_confirmed_exposure_at?: string | null;
  most_recent_exposure_close_reason?: string | null;
  last_evidence_persisted_at?: string | null;
  last_evidence_failure_at?: string | null;
  evidence_failure_code?: string | null;
  last_clean_stop_at?: string | null;
  last_failure_at?: string | null;
  failure_code?: string | null;
  consecutive_failure_count: number;
  next_retry_at?: string | null;
  last_stop_reason?: string | null;
  safety_hold_active: boolean;
  read_only: boolean;
  continuity_available: boolean;
  camera_start_requested: boolean;
  monitor_start_requested: boolean;
  creates_review_candidates: boolean;
  creates_review_truth: boolean;
  message: string;
  warnings: string[];
}

export interface CameraHealthIncident {
  id: string;
  stream_id: string;
  category: CameraHealthIncidentCategory;
  severity: AlertSeverity;
  started_at: string;
  updated_at: string;
  resolved_at?: string | null;
  reason_code: string;
  condition_fingerprint: string;
  next_retry_at?: string | null;
  occurrence_count: number;
  alert_id?: string | null;
}

export interface CameraHealthSummary {
  stream_id: string;
  stream_name: string;
  source_id: string;
  source_name: string;
  state: CameraHealthState;
  message: string;
  desired_mode: StreamMonitoringMode;
  actual_state: StreamRuntimeState;
  readiness_status: StreamPlaybackStatusValue;
  preview_available: boolean;
  last_good_frame_at?: string | null;
  frame_age_seconds?: number | null;
  last_evidence_persisted_at?: string | null;
  last_evidence_failure_at?: string | null;
  open_activity_session_count: number;
  latest_visit_at?: string | null;
  next_retry_at?: string | null;
  failure_reason?: string | null;
  unread_alert: boolean;
  stale: boolean;
}

export interface CameraHealthDetailResponse {
  health: CameraHealthSummary;
  incidents: CameraHealthIncident[];
  message: string;
}

export interface CameraHealthListResponse {
  items: CameraHealthSummary[];
  limit: number;
  message: string;
}

export interface CameraHealthIncidentListResponse {
  items: CameraHealthIncident[];
  limit: number;
  message: string;
}

export interface StreamMonitoringPolicyUpdate {
  enabled: boolean;
  idempotency_key: string;
}

export interface StreamMonitoringRetryRequest {
  idempotency_key: string;
}

export interface StreamMonitoringMutationResponse {
  policy: StreamMonitoringPolicy;
  runtime: StreamRuntimeStatus;
  idempotent: boolean;
  message: string;
  creates_review_candidates: boolean;
  creates_review_truth: boolean;
}

export interface StreamMonitoringStatusListResponse {
  items: StreamRuntimeStatus[];
  limit: number;
  message: string;
  creates_review_candidates: boolean;
  creates_review_truth: boolean;
}

export interface StreamPlaybackStatus {
  stream_id: string;
  source_id: string;
  status: StreamPlaybackStatusValue;
  playback_kind: StreamPlaybackKind;
  display_title: string;
  message: string;
  setup_hint?: string | null;
  supports_zone_editing: boolean;
  supports_live_playback: boolean;
  adapter_key?: string | null;
  last_checked_at?: string | null;
  preview_media_asset_id?: string | null;
  preview_url?: string | null;
  live_stream_type?: string | null;
  live_stream_url_display?: string | null;
  rtsp_bridge_required: boolean;
  rtsp_bridge_available: boolean;
  rtsp_bridge_status?: string | null;
  local_camera_bridge_available: boolean;
  local_camera_status?: string | null;
  local_camera_device_display?: string | null;
  windows_camera_bridge_available: boolean;
  windows_camera_status?: string | null;
  windows_camera_name_display?: string | null;
  windows_ffmpeg_binary_display?: string | null;
  camera_settings: Record<string, string>;
  bridged_mjpeg_url?: string | null;
}

export interface ExternalUrlPreviewRequest {
  timeout_seconds?: number | null;
  max_bytes?: number | null;
}

export interface ExternalUrlPreviewSaveRequest {
  stream_id?: string | null;
  timeout_seconds?: number | null;
  max_bytes?: number | null;
  note?: string | null;
}

export interface ExternalUrlPreviewResponse {
  source_id: string;
  provider_key: string;
  status: ExternalUrlPreviewStatus;
  message: string;
  fetched_at?: string | null;
  content_type?: string | null;
  content_length?: number | null;
  bytes_read?: number | null;
  preview_data_url?: string | null;
  supports_live_playback: boolean;
  creates_truth: boolean;
  creates_media_asset: boolean;
  warnings: string[];
}

export interface ExternalUrlPreviewSaveResponse {
  source_id: string;
  stream_id?: string | null;
  media_asset_id?: string | null;
  status: ExternalUrlPreviewSaveStatus;
  message: string;
  fetched_at?: string | null;
  content_type?: string | null;
  bytes_written: number;
  file_name?: string | null;
  relative_path?: string | null;
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  warnings: string[];
}

export interface LocalCameraFrameCaptureResponse {
  stream_id: string;
  source_id?: string | null;
  media_asset_id?: string | null;
  status: LocalCameraFrameCaptureStatus;
  message: string;
  file_name?: string | null;
  relative_path?: string | null;
  bytes_written: number;
  content_type?: string | null;
  capture_source?: LocalCameraFrameCaptureSource | null;
  live_frame_age_ms?: number | null;
  creates_truth: boolean;
  creates_event: boolean;
  creates_visit: boolean;
  creates_export: boolean;
  warnings: string[];
}

export interface WindowsCameraDiscoveryResponse {
  status:
    | "available"
    | "no_devices"
    | "ffmpeg_missing"
    | "unsupported_platform"
    | "failed";
  devices: string[];
  message: string;
  creates_truth: boolean;
}

export interface WindowsCameraControlsResponse {
  stream_id: string;
  source_id?: string | null;
  status:
    | "launched"
    | "monitor_running"
    | "camera_running"
    | "camera_not_configured"
    | "ffmpeg_missing"
    | "unsupported_platform"
    | "controls_unavailable"
    | "launch_failed";
  message: string;
  creates_media: boolean;
  creates_evidence: boolean;
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  warnings: string[];
}

export type AutomaticIdentificationStatus = string;

export interface LiveCameraSessionStatus {
  stream_id: string;
  source_id?: string | null;
  playback_kind?: string | null;
  status: "stopped" | "starting" | "running" | "stopping" | "failed" | "paused" | string;
  started_at?: string | null;
  last_frame_at?: string | null;
  latest_frame_age_ms?: number | null;
  newest_frame_age_ms?: number | null;
  frame_count: number;
  clients_connected: number;
  monitor_running: boolean;
  auto_create_review_candidates: boolean;
  auto_identify_review_candidates: boolean;
  automatic_identification_status: AutomaticIdentificationStatus;
  last_auto_identification_target_id?: string | null;
  last_auto_identification_attempt_id?: string | null;
  last_auto_identification_suggestion_id?: string | null;
  last_auto_identification_message?: string | null;
  auto_review_quiet_seconds: number;
  auto_review_min_detections: number;
  auto_review_created_count: number;
  last_auto_review_created_at?: string | null;
  auto_review_last_error?: string | null;
  last_auto_review_motion_evidence_id?: string | null;
  last_auto_review_event_id?: string | null;
  last_auto_review_visit_id?: string | null;
  last_auto_review_queue_item_id?: string | null;
  last_motion_evaluation_at?: string | null;
  open_activity_session_count: number;
  open_activity_zone_names: string[];
  ready_activity_session_count: number;
  latest_activity_review_queue_item_id?: string | null;
  current_activity_session?: Record<string, unknown> | null;
  current_activity_session_id?: string | null;
  activity_started_at?: string | null;
  activity_last_seen_at?: string | null;
  activity_detection_count: number;
  activity_near_miss_count: number;
  activity_frames_evaluated_count: number;
  activity_candidate_frame_count: number;
  activity_saved_candidate_count: number;
  activity_session_duration_seconds: number;
  activity_completed_at?: string | null;
  activity_ready_for_review: boolean;
  activity_manual_review_needed: boolean;
  activity_review_state?: string | null;
  activity_subject_state?: string | null;
  activity_quiet_remaining_seconds?: number | null;
  activity_best_frame_sequence?: number | null;
  activity_best_score?: number | null;
  activity_best_changed_ratio?: number | null;
  activity_best_changed_pixels?: number | null;
  activity_best_total_scored_pixels?: number | null;
  activity_effective_threshold_used?: number | null;
  activity_threshold_source?: string | null;
  activity_fine_motion_applied: boolean;
  activity_near_miss: boolean;
  activity_cooldown_remaining_seconds?: number | null;
  activity_review_activity_created: boolean;
  activity_motion_evidence_id?: string | null;
  activity_event_id?: string | null;
  activity_visit_id?: string | null;
  activity_review_queue_item_id?: string | null;
  notification_event?: string | null;
  last_activity?: Record<string, unknown> | null;
  last_motion_result?: LiveMotionEvaluateResponse | null;
  last_error?: string | null;
  stop_reason?: string | null;
  max_runtime_seconds: number;
  persistent: boolean;
  camera_settings: Record<string, unknown>;
  message: string;
  warnings: string[];
}

/** The unified Observation panel's whole product contract for one Stream
 * (Unified Observation Experience v1): current state, camera health, and
 * observation-capability health, regardless of which existing runtime
 * actually backs it (Camera Node's frame-driven engine, existing
 * backend-owned live monitoring, or the existing Snapshot Source monitor).
 * `advanced` is optional, bounded diagnostics (runtime kind, provider ids,
 * suppressed-candidate reasons) the basic UI never needs to render. */
export interface ObservationSessionCounts {
  track_updates_observed: number;
  evidence_candidates_observed: number;
  proposals_observed: number;
  candidates_created: number;
  candidates_suppressed: number;
  suppressed_reasons: Array<[string, number]>;
}

export interface ObservationSessionStatus {
  stream_id: string;
  state: "stopped" | "starting" | "observing" | "stopping" | "needs_attention";
  observing: boolean;
  message: string;
  camera_connected: boolean;
  camera_message: string;
  engine_available: boolean;
  engine_message: string;
  /** False only when this Stream has no integrated observation runtime at
   * all -- an honest unavailable state rather than a Start button that
   * would only fail. */
  runtime_available: boolean;
  started_at?: string | null;
  stopped_at?: string | null;
  stopped_reason?: string | null;
  last_candidate_visit_id?: string | null;
  last_useful_frame_at?: string | null;
  /** When set, show the one relevant existing setup action instead of a
   * Start button that cannot succeed yet. */
  setup_action?: "edit_camera_setup" | null;
  /** True only for the existing live-monitoring lane's own bounded
   * runtime/retry action. */
  retry_action: boolean;
  counts: ObservationSessionCounts;
  advanced: Record<string, unknown>;
}

export interface LivePreviewLeaseRequest {
  owner_id: string;
}

export interface LivePreviewLeaseResponse {
  stream_id: string;
  owner_id: string;
  status: "live" | "limit_reached" | "unavailable";
  preview_url?: string | null;
  expires_at?: string | null;
  max_active_previews: number;
  effective_limit: number;
  monitoring_changed: boolean;
  creates_media: boolean;
  creates_evidence: boolean;
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  message: string;
}

export interface LivePreviewReleaseResponse {
  stream_id: string;
  owner_id: string;
  released: boolean;
  monitoring_changed: boolean;
  creates_media: boolean;
  creates_evidence: boolean;
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  message: string;
}

export interface SourceMonitorStartRequest {
  interval_seconds?: number;
  max_runtime_minutes?: number;
  max_snapshots?: number;
  check_motion?: boolean;
  create_review_activity?: boolean;
}

export interface SourceMonitorStatusResponse {
  monitor_id: string;
  source_id: string;
  stream_id: string;
  status: string;
  started_at?: string | null;
  stopped_at?: string | null;
  last_tick_at?: string | null;
  next_tick_at?: string | null;
  interval_seconds: number;
  max_runtime_seconds: number;
  max_snapshots: number;
  snapshots_attempted: number;
  snapshots_saved: number;
  motion_checks_run: number;
  last_snapshot_media_asset_id?: string | null;
  last_motion_media_asset_ids: string[];
  last_activity_detected?: boolean | null;
  last_activity_area?: Record<string, unknown> | null;
  last_session_status?: string | null;
  best_snapshot_media_asset_id?: string | null;
  crop_plan?: MotionCropPlan | null;
  review_activity_available: boolean;
  review_activity_created: boolean;
  review_activity_unavailable_reason?: string | null;
  review_activity_motion_evidence_id?: string | null;
  review_activity_event_id?: string | null;
  review_activity_visit_id?: string | null;
  last_error?: string | null;
  consecutive_failures: number;
  stop_reason?: string | null;
  check_motion: boolean;
  create_review_activity: boolean;
  creates_truth: boolean;
  creates_exports: boolean;
  persistent: boolean;
  message: string;
}

export interface SavedPreviewMotionEvidenceRequest {
  stream_id?: string | null;
  zone_id?: string | null;
  note?: string | null;
  reason?: string | null;
  duplicate_policy?: "skip_existing" | "allow_duplicate" | null;
}

export interface SavedPreviewMotionEvidenceResponse {
  motion_evidence_id: string;
  media_asset_id: string;
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  status: MotionEvidenceStatus;
  message: string;
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  duplicate_skipped: boolean;
  existing_motion_evidence_id?: string | null;
  provenance_kind?: string | null;
  warnings: string[];
}

export interface SavedMediaBulkMotionEvidenceRequest {
  media_asset_ids: string[];
}

export type SavedMediaBulkMotionEvidenceResultStatus = "succeeded" | "skipped" | "failed";

export interface SavedMediaBulkMotionEvidenceResult {
  media_asset_id: string;
  status: SavedMediaBulkMotionEvidenceResultStatus;
  message: string;
  created_motion_evidence_id?: string | null;
}

export interface SavedMediaBulkMotionEvidenceResponse {
  requested_count: number;
  succeeded_count: number;
  skipped_count: number;
  failed_count: number;
  results: SavedMediaBulkMotionEvidenceResult[];
}

export interface FolderImportEvidenceBatchDryRunRequest {
  media_asset_ids?: string[] | null;
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  duplicate_policy?: "skip_existing" | "allow_duplicate";
  max_items?: number | null;
}

export interface FolderImportEvidenceBatchDryRunItem {
  media_asset_id: string;
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  file_name?: string | null;
  eligible: boolean;
  would_create_motion_evidence: boolean;
  duplicate_skipped: boolean;
  existing_motion_evidence_id?: string | null;
  skip_reason?: string | null;
  warnings: string[];
}

export interface FolderImportEvidenceBatchDryRunResponse {
  items: FolderImportEvidenceBatchDryRunItem[];
  total_items: number;
  eligible_count: number;
  would_create_count: number;
  duplicate_skipped_count: number;
  skipped_count: number;
  dry_run: boolean;
  creates_motion_evidence: boolean;
  creates_events: boolean;
  creates_visits: boolean;
  creates_truth: boolean;
  warnings: string[];
}

export interface FolderImportEvidenceBatchCreateRequest {
  media_asset_ids?: string[] | null;
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  duplicate_policy?: "skip_existing" | "allow_duplicate";
  max_items?: number | null;
  confirm?: boolean;
  note?: string | null;
  reason?: string | null;
}

export interface FolderImportEvidenceBatchCreateItem {
  media_asset_id: string;
  motion_evidence_id?: string | null;
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  created: boolean;
  duplicate_skipped: boolean;
  existing_motion_evidence_id?: string | null;
  skip_reason?: string | null;
  warnings: string[];
}

export interface FolderImportEvidenceBatchCreateResponse {
  items: FolderImportEvidenceBatchCreateItem[];
  total_items: number;
  created_count: number;
  skipped_count: number;
  duplicate_skipped_count: number;
  creates_motion_evidence: boolean;
  creates_events: boolean;
  creates_visits: boolean;
  creates_truth: boolean;
  message: string;
  warnings: string[];
}

export interface SavedMediaRetentionItem {
  media_asset_id: string;
  source_id?: string | null;
  stream_id?: string | null;
  file_name?: string | null;
  content_type?: string | null;
  size_bytes?: number | null;
  created_at?: string | null;
  fetched_at?: string | null;
  provider_key?: string | null;
  provenance?: string | null;
  linked_motion_evidence_count: number;
  linked_event_count: number;
  linked_visit_count: number;
  reviewed_truth_count: number;
  risk_level: "low" | "medium" | "high" | "protected" | string;
  media_state: string;
  recommended_action: string;
  warnings: string[];
}

export interface SavedMediaRetentionSummary {
  total_items: number;
  total_known_bytes: number;
  unknown_size_count: number;
  low_risk_count: number;
  medium_risk_count: number;
  high_risk_count: number;
  protected_count: number;
  warnings: string[];
}

export interface SavedMediaRetentionReportResponse {
  items: SavedMediaRetentionItem[];
  summary: SavedMediaRetentionSummary;
  generated_at: string;
  dry_run_only: boolean;
}

export interface SavedMediaCleanupDryRunRequest {
  media_asset_ids?: string[] | null;
  risk_levels?: string[] | null;
  include_protected?: boolean;
  mode?: string;
}

export interface SavedMediaCleanupDryRunItem {
  media_asset_id: string;
  risk_level: string;
  would_delete_file: boolean;
  would_delete_record: boolean;
  would_skip: boolean;
  skip_reason?: string | null;
  file_name?: string | null;
  size_bytes?: number | null;
  warnings: string[];
}

export interface SavedMediaCleanupDryRunResponse {
  items: SavedMediaCleanupDryRunItem[];
  total_would_delete_files: number;
  total_would_delete_records: number;
  total_known_bytes_to_delete: number;
  skipped_count: number;
  protected_skipped_count: number;
  dry_run: boolean;
  creates_truth: boolean;
  deletes_truth: boolean;
  warnings: string[];
}

export interface SavedMediaCleanupRequest {
  mode?: string;
  confirm?: boolean;
  reason?: string | null;
}

export interface SavedMediaCleanupResponse {
  media_asset_id: string;
  status: "deleted_file" | "already_missing" | "skipped" | "rejected" | string;
  risk_level: string;
  media_state: string;
  file_deleted: boolean;
  record_deleted: boolean;
  creates_truth: boolean;
  deletes_truth: boolean;
  message: string;
  file_name?: string | null;
  size_bytes?: number | null;
  warnings: string[];
}

export interface Point {
  x: number;
  y: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PixelBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Zone {
  id: string;
  stream_id: string;
  name: string;
  zone_type: ZoneType;
  polygon: Point[];
  is_active: boolean;
  monitoring_policy?: ZoneMonitoringPolicy | null;
}

export interface ZoneMonitoringPolicy {
  monitoring_enabled: boolean;
  activity_sensitivity: ZoneActivitySensitivity;
  minimum_sustained_activity_seconds: number;
  quiet_period_seconds: number;
  maximum_visit_duration_seconds: number;
  maximum_evidence_frames: number;
  customized_fields: string[];
  inherited_fields: string[];
  uses_recommended_defaults: boolean;
}

export interface ZoneMonitoringPolicyUpdate {
  monitoring_enabled?: boolean;
  activity_sensitivity?: ZoneActivitySensitivity;
  minimum_sustained_activity_seconds?: number;
  quiet_period_seconds?: number;
  maximum_visit_duration_seconds?: number;
  maximum_evidence_frames?: number;
}

export interface ZoneCreate {
  stream_id: string;
  name: string;
  zone_type: ZoneType;
  polygon: Point[];
  is_active?: boolean;
}

export interface ZoneUpdate {
  name?: string;
  zone_type?: ZoneType;
  polygon?: Point[];
  is_active?: boolean;
}

export interface ZoneMutationResult {
  zone: Zone;
  zones: Zone[];
}

export interface Detection {
  id: string;
  label: string;
  confidence: number;
  zone_id?: string | null;
  bbox?: BoundingBox | null;
}

export interface Event {
  id: string;
  stream_id: string;
  title: string;
  event_type: string;
  started_at: string;
  ended_at?: string | null;
  primary_zone_id?: string | null;
  review_status: ReviewStatus;
  detections: Detection[];
}

export interface Visit {
  id: string;
  event_id: string;
  subject_label: string;
  species_guess?: string | null;
  confidence?: number | null;
  reviewed_label?: string | null;
  review_status: ReviewStatus;
  representative_media_path?: string | null;
  zone_id?: string | null;
  is_superseded: boolean;
}

export interface MediaAsset {
  id: string;
  source_id?: string | null;
  stream_id: string;
  filename: string;
  content_type: string;
  media_type: string;
  local_path: string;
  original_filename: string;
  file_size_bytes: number;
  created_at: string;
  notes?: string | null;
  parent_media_asset_id?: string | null;
  evidence_role?: string | null;
  image_width?: number | null;
  image_height?: number | null;
  normalized_crop_box?: number[] | null;
  derived_from_visit_id?: string | null;
  derived_from_event_id?: string | null;
  derived_from_zone_id?: string | null;
  parent_image_width?: number | null;
  parent_image_height?: number | null;
  content_sha256?: string | null;
  derivation_source?: string | null;
  previous_effective_crop_media_asset_id?: string | null;
}

export interface VisitEvidenceFrame {
  media_asset_id: string;
  preview_url: string;
  captured_at: string;
  relative_position: number;
  frame_sequence?: number | null;
  is_primary: boolean;
  content_type: string;
  width?: number | null;
  height?: number | null;
  evidence_role: string;
  normalized_crop_box?: number[] | null;
}

/**
 * Read-only, bounded recommendation over a Visit's already-saved evidence
 * frames (see `mockingbird.motion.effective_primary`). Never model
 * inference and never written back to the Visit -- `is_primary` in
 * `VisitEvidenceFrame` above stays the actual persisted evidence-selection
 * fact regardless of what this recommends.
 */
export interface EffectivePrimaryEvidence {
  selected_media_asset_id?: string | null;
  persisted_primary_media_asset_id?: string | null;
  recommended_effective_primary_media_asset_id?: string | null;
  evidence_role?: string | null;
  selection_reason: string;
  is_useful: boolean;
  is_user_controlled: boolean;
  temporally_supported?: boolean | null;
  temporal_status: "supported" | "uncertain" | "rejected";
  containment_status?: boolean | null;
  edge_clipped?: boolean | null;
  width?: number | null;
  height?: number | null;
  candidate_count: number;
  historical_preview_only: boolean;
  would_change_automatically: boolean;
}

export interface StreamVisitSummary {
  id: string;
  event_id: string;
  stream_id: string;
  captured_at: string;
  activity_started_at: string;
  activity_ended_at?: string | null;
  duration_seconds: number;
  zone_id?: string | null;
  zone_name?: string | null;
  zone_type?: ZoneType | null;
  review_status: ReviewStatus;
  reviewed_label?: string | null;
  review_outcome: VisitReviewOutcome;
  suggested_label?: string | null;
  has_suggestion: boolean;
  evidence_frame_count: number;
  primary_evidence?: VisitEvidenceFrame | null;
}

export interface DashboardVisitSummary extends StreamVisitSummary {
  stream_name: string;
  source_id: string;
  source_name: string;
}

export interface DashboardZoneOverlay {
  id: string;
  stream_id: string;
  name: string;
  zone_type: ZoneType;
  polygon: Point[];
  is_active: boolean;
}

export interface DashboardLivePreview {
  kind: "unavailable" | "browser_direct" | "backend_session";
  available: boolean;
  media_kind: "image" | "video";
  preview_url?: string | null;
  message: string;
}

export type ActivityLibraryReviewFilter =
  | "all"
  | "needs_review"
  | "reviewed_observation"
  | "confirmed_wildlife"
  | "non_bird"
  | "blank_false"
  | "blank"
  | "ambiguous_unknown";

export interface ActivityLibraryFilters {
  review_filter?: ActivityLibraryReviewFilter;
  stream_id?: string | null;
  source_id?: string | null;
  zone_id?: string | null;
  confirmed_label?: string | null;
  has_suggestion?: boolean | null;
  favorites_only?: boolean;
  has_note?: boolean | null;
  collection_id?: string | null;
  tag_id?: string | null;
  oldest_first?: boolean;
  search?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  include_superseded?: boolean;
}

export interface ActivityLibrarySearchRequest extends ActivityLibraryFilters {
  page_size?: number;
  offset?: number;
}

export interface ActivityLibraryVisitSummary extends DashboardVisitSummary {
  curation_actions: string[];
  is_favorite: boolean;
  has_note: boolean;
  collection_count: number;
  tags: string[];
  tag_count: number;
}

export interface ActivityLibrarySearchResponse {
  visits: ActivityLibraryVisitSummary[];
  has_more: boolean;
  next_offset?: number | null;
}

export interface ActivityLibrarySavedView {
  id: string;
  name: string;
  filters: ActivityLibraryFilters;
  created_at: string;
  updated_at: string;
}

export interface ActivityLibrarySavedViewCreate {
  name: string;
  filters: ActivityLibraryFilters;
}

export interface ActivityLibrarySavedViewUpdate {
  name?: string;
  filters?: ActivityLibraryFilters;
}

export interface DashboardStreamSummary {
  stream_id: string;
  stream_name: string;
  source_id: string;
  source_name: string;
  source_kind: SourceKind;
  source_status: SourceStatus;
  setup_incomplete: boolean;
  availability_status: StreamPlaybackStatusValue;
  playback_kind: StreamPlaybackKind;
  availability_message: string;
  live_preview: DashboardLivePreview;
  zone_overlays: DashboardZoneOverlay[];
  monitoring_active: boolean;
  monitor_control: "none" | "live_motion" | "source_monitor";
  can_start_monitor: boolean;
  can_stop_monitor: boolean;
  open_activity_session_count: number;
  ready_activity_session_count: number;
  needs_review_visit_count: number;
  latest_visit?: DashboardVisitSummary | null;
  camera_health?: CameraHealthSummary | null;
}

export interface DashboardReviewedObservation {
  label: string;
  display_name: string;
  category: LabelCategory;
  observation_count: number;
  latest_visit: DashboardVisitSummary;
}

export interface DashboardHeadline {
  configured_stream_count: number;
  monitored_stream_count: number;
  open_activity_session_count: number;
  needs_review_visit_count: number;
  actionable_animal_visit_count: number;
  legacy_activity_count: number;
  reviewed_observation_count_today: number;
}

export interface DashboardTodaySpecies {
  label: string;
  display_name: string;
  distinct_days_seen: number;
  latest_visit: DashboardVisitSummary;
}

export interface DashboardTodayZoneActivity {
  zone_id?: string | null;
  zone_name: string;
  animal_visit_count: number;
}

export interface DashboardTodayHourActivity {
  hour: number;
  animal_visit_count: number;
}

export interface DashboardTodaySummary {
  detector_qualified_animal_visit_count: number;
  confirmed_bird_visit_count: number;
  confirmed_species_count: number;
  unresolved_animal_visit_count: number;
  best_moments: DashboardVisitSummary[];
  new_today: DashboardTodaySpecies[];
  recent_regulars: DashboardTodaySpecies[];
  activity_by_zone: DashboardTodayZoneActivity[];
  activity_by_hour: DashboardTodayHourActivity[];
  needs_help: DashboardVisitSummary[];
  observation_health: CameraHealthSummary[];
  warnings: string[];
}

export interface DashboardSummary {
  local_day: string;
  generated_at: string;
  headline: DashboardHeadline;
  today: DashboardTodaySummary;
  streams: DashboardStreamSummary[];
  needs_review_visits: DashboardVisitSummary[];
  actionable_animal_visits: DashboardVisitSummary[];
  today_observations: DashboardReviewedObservation[];
  reviewed_non_bird_activity: DashboardReviewedObservation[];
  recent_activity: DashboardVisitSummary[];
  camera_attention: CameraHealthSummary[];
  warnings: string[];
}

export interface MediaImportResult {
  media_asset: MediaAsset;
  event: Event;
  visit?: Visit | null;
  stream: Stream;
  review_queue_count: number;
}

export interface DetectionRun {
  id: string;
  media_asset_id: string;
  source: DetectionSource;
  summary?: string | null;
  status: DetectionRunStatus;
  created_at: string;
  completed_at?: string | null;
}

export interface DetectionRunCreate {
  media_asset_id: string;
  source?: DetectionSource;
  summary?: string | null;
}

export interface DemoDetectionRunCreate {
  media_asset_id: string;
  zone_id?: string | null;
  label?: string;
  confidence?: number;
  suggested_subject_label?: string;
  suggested_species?: string | null;
  notes?: string | null;
}

export interface ModelAdapterConfigurationStatus {
  adapter_id: string;
  model_path_configured: boolean;
  labels_path_configured: boolean;
  runtime_available: boolean;
  supported_media_types: string[];
  can_run: boolean;
  status_reason: string;
  setup_hint: string;
  creates_review_truth: boolean;
  local_only: boolean;
}

export interface ModelAdapterSetupSummary {
  adapter_id: string;
  adapter_name: string;
  adapter_kind: ModelAdapterKind;
  status: ModelAdapterSetupStatus;
  local_only: boolean;
  is_demo: boolean;
  supported_media_types: string[];
  required_env_var?: string | null;
  model_path_hint?: string | null;
  setup_hint?: string | null;
  can_run: boolean;
  can_run_on_review_best_frame: boolean;
  creates_truth: boolean;
}

export interface ModelAdapter {
  id: string;
  name: string;
  kind: ModelAdapterKind;
  status: ModelAdapterStatus;
  version?: string | null;
  description: string;
  supported_media_types: string[];
  supported_labels: string[];
  creates_review_truth: boolean;
  local_only: boolean;
  notes?: string | null;
  configuration_status?: ModelAdapterConfigurationStatus | null;
}

export interface ModelAdapterRunRequest {
  adapter_id: string;
  media_asset_id: string;
  zone_ids?: string[] | null;
  requested_labels?: string[] | null;
  notes?: string | null;
}

export interface AdapterEvaluationItem {
  proposal_id: string;
  detection_run_id: string;
  adapter_id?: string | null;
  media_asset_id: string;
  event_id?: string | null;
  visit_id?: string | null;
  proposal_label: string;
  proposal_display_name?: string | null;
  proposal_confidence: number;
  reviewed_label?: string | null;
  reviewed_display_name?: string | null;
  review_status: ReviewStatus;
  outcome: AdapterEvaluationOutcome;
  notes?: string | null;
}

export interface AdapterEvaluationSummary {
  adapter_id?: string | null;
  adapter_name?: string | null;
  proposal_count: number;
  reviewed_count: number;
  unreviewed_count: number;
  matched_count: number;
  mismatched_count: number;
  rejected_count: number;
  converted_count: number;
  unknown_reviewed_count: number;
  match_rate?: number | null;
  items: AdapterEvaluationItem[];
  generated_at: string;
  local_first_note: string;
}

export interface ModelReadinessChecklistItem {
  id: string;
  label: string;
  status: string;
  severity: string;
  description: string;
  suggested_action: string;
  link_path?: string | null;
}

export interface ModelReadinessSummary {
  reviewed_record_count: number;
  export_ready_count: number;
  dataset_quality_issue_count: number;
  high_quality_issue_count: number;
  reviewed_species_count: number;
  target_species_count: number;
  covered_target_species_count: number;
  missing_target_species_count: number;
  adapter_proposal_count: number;
  adapter_reviewed_count: number;
  adapter_match_rate?: number | null;
  ready_for_first_detector_spike: boolean;
  recommended_next_step: string;
  adapter_setup: ModelAdapterSetupSummary[];
  checklist: ModelReadinessChecklistItem[];
  generated_at: string;
  local_first_note: string;
}

export interface ClassifierReadinessSpeciesSummary {
  label: string;
  reviewed_examples: number;
  media_backed_examples: number;
  export_ready_examples: number;
  warnings: string[];
}

export interface ClassifierReadinessSkipSummary {
  reason: string;
  count: number;
}

export interface ClassifierReadinessReport {
  ready_for_manifest_export: boolean;
  reviewed_examples: number;
  media_backed_reviewed_examples: number;
  export_ready_examples: number;
  species: ClassifierReadinessSpeciesSummary[];
  missing_target_labels: string[];
  unknown_label_count: number;
  false_positive_count: number;
  out_of_taxonomy_count: number;
  skipped: ClassifierReadinessSkipSummary[];
  warnings: string[];
  recommended_next_step: string;
}

export interface ClassifierManifestExample {
  example_id: string;
  visit_id: string;
  event_id?: string | null;
  media_asset_id: string;
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  local_media_path?: string | null;
  label: string;
  taxonomy_id?: string | null;
  common_name?: string | null;
  scientific_name?: string | null;
  reviewed_label_id?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  split: string;
  quality_flags: string[];
  provenance: Record<string, unknown>;
}

export interface ClassifierManifestSkippedRecord {
  record_id: string;
  record_type: string;
  visit_id?: string | null;
  event_id?: string | null;
  media_asset_id?: string | null;
  label?: string | null;
  reason: string;
  detail?: string | null;
}

export interface ClassifierManifestTaxonomyEntry {
  label: string;
  taxonomy_id?: string | null;
  common_name?: string | null;
  scientific_name?: string | null;
  aliases: string[];
}

export interface ClassifierManifestSummary {
  examples: number;
  skipped: number;
  labels: Record<string, number>;
  splits: Record<string, number>;
  warnings: string[];
}

export interface ClassifierTrainingManifestResponse {
  manifest_version: string;
  generated_at: string;
  examples: ClassifierManifestExample[];
  skipped_records: ClassifierManifestSkippedRecord[];
  taxonomy: ClassifierManifestTaxonomyEntry[];
  summary: ClassifierManifestSummary;
  warnings: string[];
}

export interface ClassifierManifestFileExportRequest {
  include_csv?: boolean;
  include_summary?: boolean;
  split_seed?: string | null;
  output_name?: string | null;
  media_policy?: "reference_only";
  dry_run?: boolean;
}

export interface ClassifierManifestExportFile {
  name: string;
  relative_path: string;
  content_type: string;
  size_bytes?: number | null;
}

export interface ClassifierManifestFileExportResponse {
  export_id: string;
  output_directory?: string | null;
  files: ClassifierManifestExportFile[];
  examples: number;
  skipped: number;
  warnings: string[];
  created_at: string;
  dry_run: boolean;
}

export interface DetectionProposal {
  id: string;
  run_id: string;
  media_asset_id: string;
  stream_id: string;
  zone_id?: string | null;
  event_id?: string | null;
  visit_id?: string | null;
  label: string;
  confidence: number;
  bbox?: BoundingBox | null;
  suggested_event_type: string;
  suggested_subject_label: string;
  suggested_species?: string | null;
  status: DetectionProposalStatus;
  notes?: string | null;
  created_at: string;
  decided_at?: string | null;
}

export interface DetectionProposalCreate {
  media_asset_id: string;
  stream_id?: string | null;
  zone_id?: string | null;
  label: string;
  confidence: number;
  bbox?: BoundingBox | null;
  suggested_event_type?: string;
  suggested_subject_label?: string;
  suggested_species?: string | null;
  notes?: string | null;
}

export interface DetectionProposalDecisionCreate {
  decision: DetectionProposalDecision;
  event_title?: string | null;
  subject_label?: string | null;
  species_guess?: string | null;
  notes?: string | null;
}

export interface DetectionProposalDecisionResult {
  proposal: DetectionProposal;
  event?: Event | null;
  visit?: Visit | null;
  review_queue_count: number;
  analytics: AnalyticsSummary;
}

export interface DemoDetectionRunResult {
  detection_run: DetectionRun;
  proposals: DetectionProposal[];
  review_queue_count: number;
}

export interface ModelAdapterRunResult {
  adapter: ModelAdapter;
  detection_run: DetectionRun;
  proposals: DetectionProposal[];
  review_queue_count: number;
  local_first_note: string;
}

export interface MotionEvidence {
  id: string;
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  start_frame_index?: number | null;
  end_frame_index?: number | null;
  best_frame_index?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  best_frame_time?: string | null;
  peak_changed_ratio: number;
  triggered_frame_count: number;
  scoring_config: Record<string, string | number | boolean | string[] | null>;
  snapshot_media_asset_id?: string | null;
  status: MotionEvidenceStatus;
  promoted_event_id?: string | null;
  promoted_visit_id?: string | null;
  created_at: string;
  notes?: string | null;
}

export interface MotionEvidenceListResponse {
  motion_evidence: MotionEvidence[];
}

export interface MotionEvidenceCreateRequest {
  source_id?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  start_frame_index?: number | null;
  end_frame_index?: number | null;
  best_frame_index?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  best_frame_time?: string | null;
  peak_changed_ratio: number;
  triggered_frame_count: number;
  scoring_config?: Record<string, string | number | boolean | string[] | null>;
  snapshot_media_asset_id?: string | null;
  notes?: string | null;
}

export interface MotionEvidenceAttachMediaRequest {
  snapshot_media_asset_id?: string | null;
}

export interface MotionZoneInput {
  zone_id: string;
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface MotionScoreResponse {
  zone_id: string;
  changed_pixels: number;
  total_pixels: number;
  changed_ratio: number;
  mean_delta: number;
  triggered: boolean;
}

export interface MotionFrameScoreResponse {
  frame_index: number;
  scores: MotionScoreResponse[];
  triggered_zone_ids: string[];
  strongest_zone_id?: string | null;
  strongest_changed_ratio: number;
}

export interface MotionCandidateResponse {
  zone_id: string;
  start_frame_index: number;
  end_frame_index: number;
  best_frame_index: number;
  peak_changed_ratio: number;
  triggered_frame_count: number;
}

export interface MotionEvaluateSequenceRequest {
  frames: number[][][];
  zones: MotionZoneInput[];
  source_id?: string | null;
  stream_id?: string | null;
  frame_index_start?: number;
  pixel_delta_threshold?: number;
  min_changed_ratio?: number;
  min_triggered_frames?: number;
  max_gap_frames?: number;
  create_motion_evidence?: boolean;
  notes?: string | null;
}

export interface MotionEvaluateSequenceResponse {
  frame_scores: MotionFrameScoreResponse[];
  candidates: MotionCandidateResponse[];
  created_evidence: MotionEvidence[];
}

export interface SavedMediaFrameSummary {
  media_asset_id: string;
  created_at: string;
  width: number;
  height: number;
}

export interface MotionActivityArea {
  area_id: string;
  label: string;
  source: "user_zone" | "auto_region" | string;
  left: number;
  top: number;
  right: number;
  bottom: number;
  zone_id?: string | null;
  cell_ids: string[];
}

export interface MotionSuppressedZoneSummary {
  zone_id: string;
  zone_name: string;
  zone_type: ZoneType;
  reason: string;
  triggered_frame_count: number;
  peak_changed_ratio: number;
}

export interface MotionCropBoxNormalized {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface MotionCropBoxPixels {
  left: number;
  top: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
}

export interface MotionCropPlan {
  source_media_asset_id?: string | null;
  crop_box_normalized: MotionCropBoxNormalized;
  crop_box_pixels: MotionCropBoxPixels;
  crop_reason: "activity_motion" | "full_frame_fallback" | string;
  padding_ratio: number;
  is_full_frame_fallback: boolean;
  derived_crop_media_asset_id?: string | null;
  warning?: string | null;
}

export interface MotionEvaluateSavedMediaRequest {
  stream_id: string;
  media_asset_ids: string[];
  zone_ids?: string[] | null;
  create_motion_evidence?: boolean;
  attach_best_snapshot?: boolean;
  frame_index_start?: number;
  pixel_delta_threshold?: number;
  min_changed_ratio?: number;
  min_triggered_frames?: number;
  max_gap_frames?: number;
  notes?: string | null;
}

export interface MotionEvaluateSavedMediaResponse {
  stream_id: string;
  source_id: string;
  media_asset_ids: string[];
  zones: MotionZoneInput[];
  activity_areas: MotionActivityArea[];
  region_source: "user_zones" | "auto_regions" | string;
  uses_auto_regions: boolean;
  strongest_zone_name?: string | null;
  strongest_zone_type?: ZoneType | null;
  strongest_activity_area_id?: string | null;
  strongest_activity_area_label?: string | null;
  suppressed_zone_summaries: MotionSuppressedZoneSummary[];
  suppressed_auto_region_count: number;
  activity_summary?: string | null;
  can_create_review_activity: boolean;
  review_activity_created: boolean;
  creation_skipped_reason?: string | null;
  session_key?: string | null;
  session_status: ActivitySessionStatus | string;
  should_create_review_activity: boolean;
  session_message?: string | null;
  existing_activity_reference?: string | null;
  best_snapshot_media_asset_id?: string | null;
  best_snapshot_reason?: string | null;
  crop_plan?: MotionCropPlan | null;
  quiet_period_seconds: number;
  cooldown_seconds: number;
  max_snapshots_per_session: number;
  session_debug: Record<string, string | number | boolean | null>;
  debug_cell_zones: MotionZoneInput[];
  frames: SavedMediaFrameSummary[];
  frame_scores: MotionFrameScoreResponse[];
  candidates: MotionCandidateResponse[];
  created_evidence: MotionEvidence[];
  activity_detected: boolean;
  strongest_zone_id?: string | null;
  strongest_changed_ratio: number;
  best_media_asset_id?: string | null;
  warnings: string[];
  local_first_note: string;
}

export interface LiveMotionEvaluateRequest {
  save_best_frame?: boolean;
  create_review_activity?: boolean;
  detector_preset?: "high_sensitivity" | "normal" | "low_noise";
  bird_sized_feeder_motion?: boolean;
  pixel_delta_threshold?: number;
  min_changed_ratio?: number;
  min_triggered_frames?: number;
  max_gap_frames?: number;
  max_age_seconds?: number;
  max_frames?: number;
  focus_zone_id?: string | null;
  notes?: string | null;
}

export interface LiveMotionMonitorStartRequest extends LiveMotionEvaluateRequest {
  interval_seconds?: number;
  auto_create_review_candidates?: boolean;
  auto_identify_review_candidates?: boolean;
  auto_review_quiet_seconds?: number;
  auto_review_min_detections?: number;
}

export interface LiveMotionMonitorSettingsRequest {
  auto_create_review_candidates?: boolean;
  auto_identify_review_candidates?: boolean;
  auto_review_quiet_seconds?: number;
  auto_review_min_detections?: number;
}

export interface LiveMotionReviewActivityResponse {
  stream_id: string;
  source_id?: string | null;
  status: string;
  activity_detected: boolean;
  review_activity_created: boolean;
  review_activity_reused: boolean;
  review_activity_already_exists: boolean;
  already_exists: boolean;
  activity_session_id?: string | null;
  activity_detection_count: number;
  activity_started_at?: string | null;
  activity_last_seen_at?: string | null;
  motion_evidence_id?: string | null;
  event_id?: string | null;
  visit_id?: string | null;
  media_asset_id?: string | null;
  review_queue_item_id?: string | null;
  suggested_label?: string | null;
  suggestion_id?: string | null;
  suggestion_confidence?: number | null;
  review_status?: ReviewStatus | null;
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  creates_export: boolean;
  message: string;
  warnings: string[];
}

export interface LiveMotionFrameSummary {
  sequence: number;
  captured_at: string;
  width: number;
  height: number;
}

export interface LiveMotionEvaluateResponse {
  stream_id: string;
  source_id: string;
  status: LiveMotionEvaluationStatus;
  evaluated_at: string;
  activity_detected: boolean;
  frames_available: number;
  frames_considered: number;
  recent_frame_count: number;
  newest_frame_age_ms?: number | null;
  oldest_frame_age_ms?: number | null;
  newest_frame_sequence?: number | null;
  buffer_capacity: number;
  fresh_enough: boolean;
  last_frame_at?: string | null;
  camera_session_status?: string | null;
  camera_session_frame_count: number;
  camera_session_clients_connected: number;
  camera_session_latest_frame_age_ms?: number | null;
  camera_session_runtime_limit_seconds?: number | null;
  frames: LiveMotionFrameSummary[];
  detector_preset: "high_sensitivity" | "normal" | "low_noise";
  source_frame_width?: number | null;
  source_frame_height?: number | null;
  analysis_frame_width?: number | null;
  analysis_frame_height?: number | null;
  zone_source_crop_width?: number | null;
  zone_source_crop_height?: number | null;
  analysis_zone_id?: string | null;
  analysis_frame_identity?: string | null;
  analysis_frame_age_ms?: number | null;
  duplicate_frame_count: number;
  dropped_frame_count: number;
  frozen_frame_count: number;
  foreground_model_state?: string | null;
  foreground_mask_available: boolean;
  foreground_mask_data_url?: string | null;
  global_illumination_suppressed: boolean;
  latest_ignored_frame_reason?: string | null;
  motion_regions: Array<Record<string, unknown>>;
  tracked_objects: Array<Record<string, unknown>>;
  activity_triggers: Array<Record<string, unknown>>;
  object_detector_available: boolean;
  object_detector_unavailable_reason?: string | null;
  object_detector_zone_id?: string | null;
  object_detector_zone_source_crop_width?: number | null;
  object_detector_zone_source_crop_height?: number | null;
  object_detector_input_width?: number | null;
  object_detector_input_height?: number | null;
  object_detector_boxes: Array<Record<string, unknown>>;
  object_detector_tracks: Array<Record<string, unknown>>;
  object_detector_triggers: Array<Record<string, unknown>>;
  object_detector_cadence_seconds?: number | null;
  object_detector_inference_latency_ms?: number | null;
  object_detector_queue_depth: number;
  object_detector_queue_capacity: number;
  object_detector_dropped_frame_count: number;
  object_detector_stale_frame_count: number;
  object_detector_timed_out_count: number;
  object_detector_runtime_state: "ready" | "loading" | "running" | "delayed" | "timed_out" | "recovering" | "unavailable";
  object_detector_model_configuration_state: string;
  object_detector_model_loaded: boolean;
  object_detector_worker_alive: boolean;
  object_detector_in_flight_job_identity?: string | null;
  object_detector_in_flight_age_ms?: number | null;
  object_detector_last_submitted_at?: string | null;
  object_detector_last_completed_at?: string | null;
  object_detector_last_completed_age_ms?: number | null;
  object_detector_latest_successful_inference_latency_ms?: number | null;
  object_detector_worker_reset_count: number;
  object_detector_recovery_count: number;
  object_detector_queue_replacement_count: number;
  object_detector_execution_device?: string | null;
  object_detector_last_safe_error_category?: string | null;
  object_detector_runtime_generation: number;
  activity_trigger_source?: "object_verified" | "motion_fallback" | null;
  selected_evidence_profile_id?: string | null;
  high_resolution_capture_status?: string | null;
  high_resolution_frame_width?: number | null;
  high_resolution_frame_height?: number | null;
  high_resolution_crop_width?: number | null;
  high_resolution_crop_height?: number | null;
  high_resolution_alignment_status?: string | null;
  high_resolution_alignment_failure_code?: string | null;
  high_resolution_capture_failure_code?: string | null;
  high_resolution_capture_latency_ms?: number | null;
  high_resolution_track_to_capture_delay_ms?: number | null;
  high_resolution_track_box?: number[] | null;
  high_resolution_padded_crop_box?: number[] | null;
  frame_scores: MotionFrameScoreResponse[];
  candidates: MotionCandidateResponse[];
  activity_areas: MotionActivityArea[];
  region_source: "user_zones" | "auto_regions" | string;
  uses_auto_regions: boolean;
  strongest_zone_id?: string | null;
  strongest_zone_name?: string | null;
  strongest_zone_type?: ZoneType | null;
  strongest_activity_area?: MotionActivityArea | null;
  strongest_activity_area_id?: string | null;
  strongest_activity_area_label?: string | null;
  suppressed_zone_summaries: MotionSuppressedZoneSummary[];
  activity_summary?: string | null;
  strongest_changed_ratio: number;
  pixel_delta_threshold?: number | null;
  min_changed_ratio?: number | null;
  strongest_zone_min_changed_ratio?: number | null;
  requested_threshold?: number | null;
  effective_threshold_used?: number | null;
  threshold_used?: number | null;
  threshold_source?: string | null;
  fine_motion_applied: boolean;
  bird_sized_feeder_motion: boolean;
  changed_pixels?: number | null;
  total_pixels?: number | null;
  total_scored_pixels?: number | null;
  mean_delta?: number | null;
  margin_to_threshold?: number | null;
  near_miss: boolean;
  frame_pair_sequences: number[];
  feeder_threshold_applied: boolean;
  focus_zone_id?: string | null;
  focus_zone_name?: string | null;
  focus_zone_type?: ZoneType | null;
  focus_applied: boolean;
  evaluation_cadence_seconds?: number | null;
  image_quality_warnings: string[];
  strongest_frame_start_sequence?: number | null;
  strongest_frame_end_sequence?: number | null;
  best_frame_sequence?: number | null;
  best_frame_captured_at?: string | null;
  best_media_asset_id?: string | null;
  media_asset_id?: string | null;
  activity_session_id?: string | null;
  activity_started_at?: string | null;
  activity_last_seen_at?: string | null;
  activity_detection_count: number;
  activity_near_miss_count: number;
  activity_frames_evaluated_count: number;
  activity_candidate_frame_count: number;
  activity_saved_candidate_count: number;
  activity_session_duration_seconds: number;
  activity_completed_at?: string | null;
  activity_ready_for_review: boolean;
  activity_review_state?: string | null;
  activity_subject_state?: string | null;
  activity_quiet_remaining_seconds?: number | null;
  activity_manual_review_needed: boolean;
  activity_best_frame_sequence?: number | null;
  activity_best_score?: number | null;
  activity_best_changed_ratio?: number | null;
  activity_best_changed_pixels?: number | null;
  activity_best_total_scored_pixels?: number | null;
  activity_effective_threshold_used?: number | null;
  activity_threshold_source?: string | null;
  activity_fine_motion_applied: boolean;
  activity_near_miss: boolean;
  can_create_review_activity: boolean;
  review_activity_available: boolean;
  review_activity_created: boolean;
  review_activity_reused: boolean;
  review_activity_already_exists: boolean;
  existing_review_activity_reference?: string | null;
  session_status: string;
  cooldown_remaining_seconds?: number | null;
  auto_create_review_candidates: boolean;
  auto_identify_review_candidates: boolean;
  automatic_identification_status: AutomaticIdentificationStatus;
  last_auto_identification_target_id?: string | null;
  last_auto_identification_attempt_id?: string | null;
  last_auto_identification_suggestion_id?: string | null;
  last_auto_identification_message?: string | null;
  auto_review_quiet_seconds: number;
  auto_review_min_detections: number;
  auto_review_created_count: number;
  last_auto_review_created_at?: string | null;
  auto_review_last_error?: string | null;
  last_auto_review_motion_evidence_id?: string | null;
  last_auto_review_event_id?: string | null;
  last_auto_review_visit_id?: string | null;
  last_auto_review_queue_item_id?: string | null;
  notification_event?: string | null;
  last_evaluation_message?: string | null;
  last_error?: string | null;
  motion_evidence_id?: string | null;
  event_id?: string | null;
  visit_id?: string | null;
  review_queue_item_id?: string | null;
  review_status?: ReviewStatus | null;
  suggested_label?: string | null;
  suggestion_id?: string | null;
  suggestion_confidence?: number | null;
  suggestion_reason?: string | null;
  candidate_pack?: SpeciesCandidatePackSummary | null;
  candidate_pack_warning?: string | null;
  suggestion_creates_truth: boolean;
  created_evidence: MotionEvidence[];
  debug_cell_zones: MotionZoneInput[];
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  creates_export: boolean;
  message: string;
  warnings: string[];
  local_first_note: string;
}

export interface MotionEvidencePromoteRequest {
  event_title?: string | null;
  visit_label_hint?: string | null;
  notes?: string | null;
  create_event?: boolean;
  create_visit?: boolean;
  attach_snapshot_media_asset_id?: string | null;
}

export interface MotionEvidencePromoteResponse {
  evidence: MotionEvidence;
  event_id?: string | null;
  visit_id?: string | null;
}

export type MotionEvidenceBulkAction = "ignore" | "promote";

export type MotionEvidenceBulkActionResultStatus = "succeeded" | "skipped" | "failed";

export interface MotionEvidenceBulkActionRequest {
  motion_evidence_ids: string[];
  action: MotionEvidenceBulkAction;
}

export interface MotionEvidenceBulkActionResult {
  motion_evidence_id: string;
  status: MotionEvidenceBulkActionResultStatus;
  message: string;
  created_event_id?: string | null;
  created_visit_id?: string | null;
}

export interface MotionEvidenceBulkActionResponse {
  action: MotionEvidenceBulkAction;
  requested_count: number;
  succeeded_count: number;
  skipped_count: number;
  failed_count: number;
  results: MotionEvidenceBulkActionResult[];
}

export interface SpeciesSuggestion {
  id: string;
  source_id?: string | null;
  stream_id?: string | null;
  event_id?: string | null;
  visit_id?: string | null;
  media_asset_id?: string | null;
  motion_evidence_id?: string | null;
  adapter_id: string;
  adapter_name: string;
  suggested_label: string;
  suggested_common_name?: string | null;
  suggested_scientific_name?: string | null;
  confidence?: number | null;
  rank: number;
  alternatives: Array<Record<string, unknown>>;
  evidence_region?: Record<string, unknown> | null;
  status: SpeciesSuggestionStatus;
  created_at: string;
  notes?: string | null;
}

export interface SpeciesSuggestionCreateRequest {
  source_id?: string | null;
  stream_id?: string | null;
  event_id?: string | null;
  visit_id?: string | null;
  media_asset_id?: string | null;
  motion_evidence_id?: string | null;
  adapter_id: string;
  adapter_name: string;
  suggested_label: string;
  suggested_common_name?: string | null;
  suggested_scientific_name?: string | null;
  confidence?: number | null;
  rank?: number;
  alternatives?: Array<Record<string, unknown>>;
  evidence_region?: Record<string, unknown> | null;
  notes?: string | null;
}

export interface MockSpeciesSuggestionRequest {
  visit_id: string;
  adapter_id?: string;
  adapter_name?: string;
  suggested_label?: string | null;
  confidence?: number;
  notes?: string | null;
}

export interface SpeciesSuggestionListResponse {
  species_suggestions: SpeciesSuggestion[];
}

export interface SpeciesSuggestionStatusUpdateRequest {
  status: SpeciesSuggestionStatus;
}

export interface FolderImportPreviewRequest {
  recursive?: boolean | null;
  allowed_extensions?: string[] | null;
  max_files?: number | null;
  max_depth?: number | null;
}

export interface FolderImportPreviewCandidate {
  relative_path: string;
  file_name: string;
  extension: string;
  size_bytes?: number | null;
  modified_at?: string | null;
  planned_media_kind: string;
  warnings: string[];
}

export interface FolderImportPreviewSkipped {
  relative_path?: string | null;
  file_name?: string | null;
  reason: string;
  message: string;
}

export interface FolderImportPreviewResponse {
  source_id: string;
  provider_key: string;
  folder_configured: boolean;
  recursive: boolean;
  allowed_extensions: string[];
  candidates: FolderImportPreviewCandidate[];
  skipped: FolderImportPreviewSkipped[];
  total_candidates: number;
  total_skipped: number;
  total_known_bytes: number;
  unknown_size_count: number;
  scanned_at: string;
  dry_run: boolean;
  creates_media_assets: boolean;
  creates_events: boolean;
  creates_visits: boolean;
  creates_truth: boolean;
  warnings: string[];
}

export interface FolderImportRequest {
  recursive?: boolean | null;
  allowed_extensions?: string[] | null;
  max_files?: number | null;
  max_depth?: number | null;
  relative_paths?: string[] | null;
  default_stream_id?: string | null;
  default_zone_id?: string | null;
  note?: string | null;
  copy_mode?: string;
}

export interface FolderImportCreatedMediaAsset {
  media_asset_id: string;
  relative_source_path: string;
  file_name: string;
  content_type?: string | null;
  size_bytes?: number | null;
  stream_id?: string | null;
  zone_id?: string | null;
  warnings: string[];
}

export interface FolderImportSkipped {
  relative_path?: string | null;
  file_name?: string | null;
  reason: string;
  message: string;
}

export interface FolderImportResponse {
  source_id: string;
  provider_key: string;
  imported: FolderImportCreatedMediaAsset[];
  skipped: FolderImportSkipped[];
  total_imported: number;
  total_skipped: number;
  total_bytes_copied: number;
  imported_at: string;
  copy_mode: string;
  creates_media_assets: boolean;
  creates_motion_evidence: boolean;
  creates_events: boolean;
  creates_visits: boolean;
  creates_truth: boolean;
  warnings: string[];
}

export interface LegacyFolderImportPreviewRequest {
  folder_path: string;
}

export interface FolderImportCandidate {
  filename: string;
  path: string;
  content_type: string;
  media_type: string;
  file_size_bytes: number;
}

export interface FolderImportSkippedFile {
  filename: string;
  reason: string;
}

export interface FolderImportPreview {
  folder_path: string;
  supported_files: FolderImportCandidate[];
  skipped_files: FolderImportSkippedFile[];
  supported_count: number;
  skipped_count: number;
}

export interface LegacyFolderImportCreate {
  folder_path: string;
  stream_id?: string | null;
  zone_id?: string | null;
  subject_label?: string;
  species_guess?: string | null;
  notes?: string | null;
  limit?: number | null;
}

export interface FolderImportResult {
  folder_path: string;
  imported_count: number;
  skipped_count: number;
  media_assets: MediaAsset[];
  events: Event[];
  visits: Visit[];
  skipped_files: FolderImportSkippedFile[];
  review_queue_count: number;
}

export interface ReviewIdentificationSummary {
  status: ReviewIdentificationStatus;
  message: string;
  media_asset_id?: string | null;
  adapter_id?: string | null;
  adapter_name?: string | null;
  adapter_kind?: ModelAdapterKind | null;
  adapter_status?: ModelAdapterStatus | null;
  adapter_is_demo: boolean;
  setup_status?: ModelAdapterSetupStatus | null;
  local_only: boolean;
  supported_media_types: string[];
  can_run: boolean;
  can_run_on_best_frame: boolean;
  required_env_var?: string | null;
  model_path_hint?: string | null;
  setup_hint?: string | null;
  unavailable_reason?: string | null;
  suggestion?: SpeciesSuggestion | null;
  proposal?: DetectionProposal | null;
  suggestion_count: number;
  proposal_count: number;
  created_suggestion_ids: string[];
  created_proposal_ids: string[];
  focus_crop_available: boolean;
  focus_crop_source: FocusCropSource;
  focus_crop_box_normalized?: BoundingBox | null;
  focus_crop_box_pixels?: PixelBoundingBox | null;
  focus_crop_label?: string | null;
  focus_crop_warnings: string[];
  creates_truth: boolean;
  creates_export: boolean;
  candidate_pack?: SpeciesCandidatePackSummary | null;
  candidate_pack_warning?: string | null;
}

export interface ReviewQueueItem {
  id: string;
  item_type: string;
  target_type: string;
  target_id: string;
  title: string;
  stream_id: string;
  stream_name?: string | null;
  source_id?: string | null;
  source_name?: string | null;
  event_id?: string | null;
  visit_id?: string | null;
  primary_zone_id?: string | null;
  primary_zone_name?: string | null;
  primary_zone_type?: ZoneType | null;
  zone_id?: string | null;
  zone_name?: string | null;
  zone_type?: ZoneType | null;
  best_media_asset_id?: string | null;
  activity_session_id?: string | null;
  activity_started_at?: string | null;
  activity_last_seen_at?: string | null;
  detection_count: number;
  near_miss_count: number;
  frames_evaluated_count: number;
  candidate_frame_count: number;
  saved_candidate_count: number;
  best_frame_sequence?: number | null;
  best_changed_ratio?: number | null;
  best_changed_pixels?: number | null;
  best_total_scored_pixels?: number | null;
  effective_threshold_used?: number | null;
  threshold_source?: string | null;
  fine_motion_applied: boolean;
  image_quality_warnings: string[];
  suggested_label?: string | null;
  suggestion_id?: string | null;
  suggestion_confidence?: number | null;
  suggestion_reason?: string | null;
  suggestion_creates_truth: boolean;
  focus_crop_available: boolean;
  focus_crop_source: FocusCropSource;
  focus_crop_box_normalized?: BoundingBox | null;
  focus_crop_box_pixels?: PixelBoundingBox | null;
  focus_crop_label?: string | null;
  focus_crop_warnings: string[];
  identification?: ReviewIdentificationSummary | null;
  media_asset?: MediaAsset | null;
  evidence_frames: VisitEvidenceFrame[];
  stale_species_suggestions: boolean;
  review_status: ReviewStatus;
  review_state_token: string;
  reason: string;
  product_category: "animal" | "other_activity" | "unchecked" | "legacy_activity" | "reviewed";
  detector_class?: "animal" | "person" | "vehicle" | null;
  detector_score?: number | null;
  track_generation_id?: string | null;
  detector_provenance?: Record<string, unknown> | null;
  captured_at?: string | null;
  evidence_count: number;
  is_demo_source: boolean;
  is_legacy_activity: boolean;
}

// Review Decision Provenance / Truth Boundary v1 (see
// docs/review-decision-provenance-contract.md). `undefined`/omitted never
// means "human" -- see `apiClient`'s review-correction functions, which are
// the only place this frontend explicitly stamps "human". `ReviewOrigin`
// types what a *create* request may claim; a real stored row can also read
// back the migration-backfilled `"legacy_unattributed"` sentinel, which a
// create request can never legitimately claim -- see `ReviewOriginStored`.
export type ReviewOrigin = "human" | "imported_curated" | "agent_diagnostic";
export type ReviewOriginStored = ReviewOrigin | "legacy_unattributed";

export interface ReviewLabel {
  id: string;
  target_type: string;
  target_id: string;
  label: string;
  notes?: string | null;
  created_at: string;
  review_origin?: ReviewOriginStored | null;
  reviewer_identity?: string | null;
  // Server-computed; only a human review or explicitly governed imported
  // truth is eligible to establish or correct durable reviewed truth.
  is_authoritative: boolean;
}

export interface ReviewLabelCreate {
  target_type: string;
  target_id: string;
  label: string;
  notes?: string | null;
}

export interface ReviewCorrectionCreate {
  target_type: string;
  target_id: string;
  label: string;
  notes?: string | null;
  review_origin?: ReviewOrigin | null;
  reviewer_identity?: string | null;
}

export interface ReviewCorrectionResult {
  review_label: ReviewLabel;
  visit?: Visit | null;
  event?: Event | null;
  review_queue_count: number;
  analytics: AnalyticsSummary;
}

export interface VisitReviewRevisionCreate {
  label: string;
  notes?: string | null;
  expected_state_token: string;
  idempotency_key: string;
  review_origin?: ReviewOrigin | null;
  reviewer_identity?: string | null;
}

export interface VisitReviewReopenCreate {
  notes?: string | null;
  expected_state_token: string;
  idempotency_key: string;
  review_origin?: ReviewOrigin | null;
  reviewer_identity?: string | null;
}

export interface VisitReviewRevisionResponse {
  result: ReviewCorrectionResult;
  review_state_token: string;
  idempotent: boolean;
}

export interface VisitReviewReopenResponse {
  visit: Visit;
  event: Event;
  review_queue_count: number;
  analytics: AnalyticsSummary;
  review_state_token: string;
  idempotent: boolean;
  message: string;
}

export interface VisitReviewHistoryEntry {
  action: string;
  label?: string | null;
  notes?: string | null;
  created_at: string;
  is_current: boolean;
  review_origin?: ReviewOriginStored | null;
  is_authoritative: boolean;
}

export interface VisitReviewHistory {
  visit_id: string;
  review_status: ReviewStatus;
  reviewed_label?: string | null;
  review_state_token: string;
  entries: VisitReviewHistoryEntry[];
}

export interface VisitCurationHistoryEntry {
  action: string;
  message: string;
  created_at: string;
}

export interface VisitCurationSequencePreview {
  evidence_frames: VisitEvidenceFrame[];
  activity_started_at?: string | null;
  activity_ended_at?: string | null;
  evidence_count: number;
}

export interface VisitEvidenceCurationRequest {
  retained_media_asset_ids: string[];
  primary_media_asset_id: string;
  expected_state_token: string;
  idempotency_key: string;
}

export interface VisitEvidenceCurationResponse {
  visit: Visit;
  evidence_frames: VisitEvidenceFrame[];
  review_state_token: string;
  idempotent: boolean;
  message: string;
}

export interface RefinedCropCreateRequest {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface VisitCropHistoryEntry {
  media_asset_id: string;
  preview_url: string;
  parent_media_asset_id: string;
  evidence_role: string;
  derivation_source: string;
  normalized_crop_box?: number[] | null;
  width?: number | null;
  height?: number | null;
  created_at: string;
  is_primary: boolean;
  previous_effective_crop_media_asset_id?: string | null;
}

export interface RefinedCropResponse {
  visit: Visit;
  refined_crop: MediaAsset;
  evidence_frames: VisitEvidenceFrame[];
  crop_history: VisitCropHistoryEntry[];
  stale_species_suggestions: boolean;
  created: boolean;
  message: string;
}

export interface VisitSplitPreviewRequest {
  boundary_after_media_asset_id: string;
  expected_state_token: string;
}

export interface VisitSplitPreview {
  first: VisitCurationSequencePreview;
  second: VisitCurationSequencePreview;
  review_implication: string;
  state_token: string;
}

export interface VisitSplitRequest extends VisitSplitPreviewRequest {
  idempotency_key: string;
}

export interface VisitSplitResponse {
  source_visit: Visit;
  resulting_visits: Visit[];
  review_state_token: string;
  idempotent: boolean;
  message: string;
}

export interface VisitMergeCandidate {
  visit: StreamVisitSummary;
  gap_seconds: number;
}

export interface VisitMergeCandidatesResponse {
  candidates: VisitMergeCandidate[];
  maximum_gap_seconds: number;
}

export interface VisitMergePreviewRequest {
  candidate_visit_ids: string[];
  expected_state_token: string;
}

export interface VisitMergePreview {
  source_visits: Visit[];
  combined: VisitCurationSequencePreview;
  review_implication: string;
  state_token: string;
}

export interface VisitMergeRequest extends VisitMergePreviewRequest {
  idempotency_key: string;
}

export interface VisitMergeResponse {
  visit: Visit;
  source_visits: Visit[];
  review_state_token: string;
  idempotent: boolean;
  message: string;
}

export interface VisitZoneReassignmentRequest {
  zone_id: string;
  expected_state_token: string;
  idempotency_key: string;
}

export interface VisitZoneReassignmentResponse {
  visit: Visit;
  review_state_token: string;
  idempotent: boolean;
  message: string;
}

export type FastReviewNavigationDirection = "next" | "previous";

export interface FastReviewQueueTarget {
  target_type: ReviewQueueBulkCorrectionTargetType;
  target_id: string;
}

export interface FastReviewQueueNavigationRequest {
  ordered_targets: FastReviewQueueTarget[];
  current_target?: FastReviewQueueTarget | null;
  direction?: FastReviewNavigationDirection;
  stream_id?: string | null;
}

export interface FastReviewQueueNavigationResponse {
  item?: ReviewQueueItem | null;
  position?: number | null;
  unresolved_count: number;
  message: string;
}

export interface FastReviewCorrectionCreate {
  target_type: ReviewQueueBulkCorrectionTargetType;
  target_id: string;
  label: string;
  notes?: string | null;
  review_session_id: string;
  idempotency_key: string;
  expected_state_token: string;
  review_origin?: ReviewOrigin | null;
  reviewer_identity?: string | null;
}

export interface FastReviewCorrectionResponse {
  result: ReviewCorrectionResult;
  idempotent: boolean;
  undo_state_token: string;
}

export interface FastReviewUndoRequest {
  review_label_id: string;
  review_session_id: string;
  idempotency_key: string;
  expected_state_token: string;
}

export interface FastReviewUndoResponse {
  reversal_review_label_id: string;
  target_type: ReviewQueueBulkCorrectionTargetType;
  target_id: string;
  review_queue_count: number;
  analytics: AnalyticsSummary;
  idempotent: boolean;
  message: string;
}

export type AlertCategory = "review" | "monitoring" | "storage" | "journal";
export type AlertSeverity = "info" | "warning" | "high";
export type AlertActionType = "review_visit" | "open_stream" | "open_storage_retention" | "open_wildlife_journal";

export interface ProductAlertAction {
  action_type: AlertActionType;
  visit_id?: string | null;
  stream_id?: string | null;
  label?: string | null;
}

export interface ProductAlert {
  id: string;
  category: AlertCategory;
  severity: AlertSeverity;
  title: string;
  message: string;
  created_at: string;
  updated_at: string;
  read_at?: string | null;
  dismissed_at?: string | null;
  resolved_at?: string | null;
  status: "unread" | "read" | "dismissed" | "resolved";
  stream_id?: string | null;
  stream_name?: string | null;
  zone_id?: string | null;
  zone_name?: string | null;
  visit_id?: string | null;
  source_id?: string | null;
  action: ProductAlertAction;
}

export interface ProductAlertListResponse {
  items: ProductAlert[];
  next_offset?: number | null;
}

export interface ProductAlertUnreadResponse {
  unread_count: number;
  recent: ProductAlert[];
}

export type ReviewQueueBulkCorrectionTargetType = "event" | "visit";
export type ReviewQueueBulkCorrectionResultStatus = "succeeded" | "skipped" | "failed";


export type ReviewQueueSpeciesSuggestionBatchPrepareStatus =
  | "queued"
  | "skipped"
  | "setup_required";

export interface ReviewQueueSpeciesSuggestionBatchPrepareRequest {
  visit_ids: string[];
}

export interface ReviewQueueSpeciesSuggestionBatchPrepareResult {
  visit_id: string;
  status: ReviewQueueSpeciesSuggestionBatchPrepareStatus;
  message: string;
  media_asset_id?: string | null;
  candidate_pack?: SpeciesCandidatePackSummary | null;
  candidate_pack_warning?: string | null;
}

export interface ReviewQueueSpeciesSuggestionBatchPrepareResponse {
  requested_count: number;
  queued_count: number;
  skipped_count: number;
  setup_required_count: number;
  results: ReviewQueueSpeciesSuggestionBatchPrepareResult[];
  creates_truth: boolean;
  creates_export: boolean;
}


export interface ReviewIdentificationRequest {
  adapter_id?: string | null;
  media_asset_id?: string | null;
  requested_labels?: string[] | null;
  notes?: string | null;
}

export type VisitIdentificationEvidenceMode = "primary_only" | "all_retained_evidence";

export interface VisitIdentificationAssistantRequest {
  evidence_mode?: VisitIdentificationEvidenceMode;
  idempotency_key: string;
}

export interface VisitIdentificationAssistantSuggestion {
  suggestion_id: string;
  attempt_id?: string | null;
  label: string;
  rank: number;
  score?: number | null;
  score_label: string;
  provider: string;
  provider_id: string;
  media_asset_id?: string | null;
  frame_role: string;
  model_runtime_version?: string | null;
  analyzed_at: string;
  status: SpeciesSuggestionStatus;
  origin: "user_triggered_review_assistance" | "previously_generated";
  support_count: number;
}

export interface VisitIdentificationAssistantResponse {
  visit_id: string;
  availability: ReviewIdentificationSummary;
  evidence_mode: VisitIdentificationEvidenceMode;
  selected_evidence_frames: VisitEvidenceFrame[];
  run?: Record<string, unknown> | null;
  attempts: Array<Record<string, unknown>>;
  suggestions: VisitIdentificationAssistantSuggestion[];
  message: string;
  creates_truth: boolean;
  creates_export: boolean;
}

export interface ReviewIdentificationResponse {
  target_type: ReviewQueueBulkCorrectionTargetType;
  target_id: string;
  identification: ReviewIdentificationSummary;
  detection_run?: DetectionRun | null;
  proposals: DetectionProposal[];
  species_suggestion?: SpeciesSuggestion | null;
  review_queue_item?: ReviewQueueItem | null;
  created_suggestion_ids: string[];
  created_proposal_ids: string[];
  creates_truth: boolean;
  creates_export: boolean;
  creates_review_label: boolean;
  warnings: string[];
}

export interface ReviewQueueBulkCorrectionRequest {
  target_ids: string[];
  target_type: ReviewQueueBulkCorrectionTargetType;
  label: string;
  notes?: string | null;
  review_origin?: ReviewOrigin | null;
  reviewer_identity?: string | null;
}

export interface ReviewQueueBulkCorrectionResult {
  target_id: string;
  status: ReviewQueueBulkCorrectionResultStatus;
  message: string;
  created_review_label_id?: string | null;
}

export interface ReviewQueueBulkCorrectionResponse {
  requested_count: number;
  succeeded_count: number;
  skipped_count: number;
  failed_count: number;
  results: ReviewQueueBulkCorrectionResult[];
}

export interface EventDetail {
  event: Event;
  stream: Stream;
  primary_zone?: Zone | null;
  visits: Visit[];
  motion_evidence?: MotionEvidence | null;
  media_asset?: MediaAsset | null;
  detection_proposals: DetectionProposal[];
  detection_runs: DetectionRun[];
  review_labels: ReviewLabel[];
  dataset_ready: boolean;
  review_summary: string;
}

export interface VisitDetail {
  visit: Visit;
  event: Event;
  stream: Stream;
  primary_zone?: Zone | null;
  detections: Detection[];
  motion_evidence?: MotionEvidence | null;
  media_asset?: MediaAsset | null;
  evidence_frames: VisitEvidenceFrame[];
  effective_primary?: EffectivePrimaryEvidence | null;
  crop_history: VisitCropHistoryEntry[];
  stale_species_suggestions: boolean;
  detection_proposals: DetectionProposal[];
  detection_runs: DetectionRun[];
  review_labels: ReviewLabel[];
  correction_history: VisitReviewHistoryEntry[];
  curation_history: VisitCurationHistoryEntry[];
  resulting_visits: Visit[];
  eligible_zones: Zone[];
  review_state_token: string;
  dataset_ready: boolean;
  review_summary: string;
}

export interface VisitOrganizationState {
  visit_id: string;
  is_favorite: boolean;
  note: string;
  inherited_from_visit_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  state_token: string;
}

export interface VisitOrganizationUpdate {
  is_favorite?: boolean | null;
  note?: string | null;
  expected_state_token: string;
  idempotency_key: string;
}

export type VisitOrganizationBulkAction = "favorite" | "unfavorite";

export interface VisitOrganizationBulkRequest {
  visit_ids: string[];
  action: VisitOrganizationBulkAction;
  idempotency_key: string;
}

export interface VisitOrganizationBulkResult {
  visit_id: string;
  status: "updated" | "skipped";
}

export interface VisitOrganizationBulkResponse {
  results: VisitOrganizationBulkResult[];
}

export interface VisitCollectionSummary {
  id: string;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;
  state_token: string;
  active_visit_count: number;
  latest_active_visit_at?: string | null;
  representative_evidence?: VisitEvidenceFrame | null;
}

export interface VisitCollectionCreate {
  name: string;
  description?: string | null;
  idempotency_key: string;
}

export interface VisitCollectionUpdate {
  name?: string | null;
  description?: string | null;
  expected_state_token: string;
  idempotency_key: string;
}

export interface VisitCollectionArchiveRequest {
  expected_state_token: string;
  idempotency_key: string;
}

export interface VisitCollectionMembershipRequest {
  expected_state_token: string;
  idempotency_key: string;
}

export type VisitCollectionMembershipStatus =
  | "updated"
  | "already_present"
  | "already_absent"
  | "skipped_unavailable"
  | "skipped_superseded";

export interface VisitCollectionMembershipResult {
  visit_id: string;
  status: VisitCollectionMembershipStatus;
}

export interface VisitCollectionMembershipResponse {
  collection: VisitCollectionSummary;
  result: VisitCollectionMembershipResult;
}

export interface VisitCollectionBulkRequest {
  collection_id: string;
  visit_ids: string[];
  action: "add" | "remove";
  expected_state_token: string;
  idempotency_key: string;
}

export interface VisitCollectionBulkResponse {
  collection: VisitCollectionSummary;
  results: VisitCollectionMembershipResult[];
}

export interface VisitCollectionsForVisitResponse {
  visit_id: string;
  collections: VisitCollectionSummary[];
}

export interface VisitTagSummary { id: string; name: string; created_at: string; updated_at: string; archived_at?: string | null; state_token: string; active_visit_count: number; }
export interface VisitTagCreate { name: string; idempotency_key: string; }
export interface VisitTagUpdate { name: string; expected_state_token: string; idempotency_key: string; }
export interface VisitTagArchiveRequest { expected_state_token: string; idempotency_key: string; }
export interface VisitTagMembershipRequest { expected_state_token: string; idempotency_key: string; }
export type VisitTagMembershipStatus = "updated" | "already_present" | "already_absent" | "skipped_unavailable" | "skipped_superseded" | "skipped_limit";
export interface VisitTagMembershipResult { visit_id: string; status: VisitTagMembershipStatus; }
export interface VisitTagMembershipResponse { tag: VisitTagSummary; result: VisitTagMembershipResult; }
export interface VisitTagBulkRequest { tag_id: string; visit_ids: string[]; action: "add" | "remove"; expected_state_token: string; idempotency_key: string; }
export interface VisitTagBulkResponse { tag: VisitTagSummary; results: VisitTagMembershipResult[]; }
export interface VisitTagsForVisitResponse { visit_id: string; tags: VisitTagSummary[]; }

export type YardMapRange = "today" | "last_24_hours" | "last_7_days";
export interface YardMapAreaPoint { x: number; y: number; }
export interface YardMapBackground { preview_url: string; content_type: "image/jpeg" | "image/png" | "image/webp"; width: number; height: number; }
export interface YardMapSettings { id: string; canvas_width: number; canvas_height: number; background?: YardMapBackground | null; background_missing: boolean; state_token: string; created_at: string; updated_at: string; }
export interface YardMapBlankCreate { canvas_width?: number; canvas_height?: number; idempotency_key: string; }
export interface YardMapSettingsUpdate { canvas_width: number; canvas_height: number; expected_state_token: string; idempotency_key: string; }
export interface YardMapStreamPlacementUpdate { x: number; y: number; heading_degrees: number; field_of_view_degrees: number; display_scale?: number | null; expected_state_token?: string | null; idempotency_key: string; }
export interface YardMapZonePlacementUpdate { x: number; y: number; area?: YardMapAreaPoint[] | null; expected_state_token?: string | null; idempotency_key: string; }
export interface YardMapPlacementDelete { expected_state_token: string; idempotency_key: string; }
export interface YardMapBackgroundDelete { expected_state_token: string; idempotency_key: string; }
export interface YardMapStreamPlacement { stream_id: string; x: number; y: number; heading_degrees: number; field_of_view_degrees: number; display_scale?: number | null; state_token: string; updated_at: string; }
export interface YardMapZonePlacement { zone_id: string; x: number; y: number; area?: YardMapAreaPoint[] | null; state_token: string; updated_at: string; }
export interface YardMapActivitySummary { monitoring_desired_state: "off" | "armed" | "paused"; monitoring_actual_state: "stopped" | "starting" | "running" | "backoff" | "blocked" | "stopping" | "interrupted"; camera_health_state: CameraHealthState; open_activity_session: boolean; needs_review_count: number; needs_review_visit_ids: string[]; latest_visit_id?: string | null; latest_visit_at?: string | null; latest_confirmed_label?: string | null; latest_preview_url?: string | null; }
export interface YardMapStreamItem { id: string; name: string; source_name: string; is_live: boolean; placement?: YardMapStreamPlacement | null; activity: YardMapActivitySummary; }
export interface YardMapZoneItem { id: string; stream_id: string; name: string; zone_type: ZoneType; is_active: boolean; placement?: YardMapZonePlacement | null; }
export interface YardMapResponse { map?: YardMapSettings | null; streams: YardMapStreamItem[]; zones: YardMapZoneItem[]; range: YardMapRange; warnings: string[]; }

export interface DatasetExport {
  id: string;
  name: string;
  status: ExportStatus;
  reviewed_only: boolean;
  include_detections: boolean;
  include_zone_context: boolean;
  record_count: number;
  created_at: string;
  selected_visit_ids?: string[] | null;
}

export interface DatasetExportCreate {
  name: string;
  reviewed_only?: boolean;
  include_detections?: boolean;
  include_zone_context?: boolean;
  selected_visit_ids?: string[] | null;
}

export interface DatasetExportRecord {
  record_id: string;
  event_id: string;
  visit_id?: string | null;
  stream_id: string;
  source_id: string;
  label: string;
  label_display_name?: string | null;
  label_category?: LabelCategory | null;
  is_species?: boolean | null;
  subject_label: string;
  zone_id?: string | null;
  zone_name?: string | null;
  zone_type?: ZoneType | null;
  reviewed: boolean;
  dataset_ready: boolean;
  media_path?: string | null;
  started_at: string;
  detections: Detection[];
}

export interface DatasetExportManifest {
  export: DatasetExport;
  records: DatasetExportRecord[];
  skipped_count: number;
  skipped_reasons: Record<string, number>;
  generated_at: string;
}

export interface DatasetExportDetail {
  export: DatasetExport;
  manifest: DatasetExportManifest;
}

export interface ActivityLibraryExportSelectionRequest {
  name: string;
  visit_ids: string[];
}

export interface ActivityLibraryExportExclusion {
  visit_id: string;
  reason: string;
}

export interface ActivityLibraryExportSelectionResponse {
  export?: DatasetExportDetail | null;
  included_visit_ids: string[];
  excluded: ActivityLibraryExportExclusion[];
}

export interface DatasetCoverageSpecies {
  label: string;
  display_name: string;
  category: string;
  is_species: boolean;
  reviewed_record_count: number;
  export_ready_count: number;
  needs_review_count: number;
  unknown_count: number;
  media_asset_count: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface DatasetCoverageGap {
  label: string;
  display_name: string;
  reason: string;
  target_category?: string | null;
}

export interface DatasetCoverageSummary {
  reviewed_record_count: number;
  export_ready_count: number;
  needs_review_count: number;
  unknown_bird_count: number;
  unknown_animal_count: number;
  false_positive_count: number;
  reviewed_species_count: number;
  target_species_count: number;
  covered_target_species_count: number;
  missing_target_species_count: number;
  species: DatasetCoverageSpecies[];
  gaps: DatasetCoverageGap[];
  generated_at: string;
  local_first_note: string;
}

export interface DatasetQualityIssue {
  id: string;
  severity: string;
  issue_type: string;
  title: string;
  description: string;
  target_type: string;
  target_id: string;
  event_id?: string | null;
  visit_id?: string | null;
  media_asset_id?: string | null;
  label?: string | null;
  suggested_action: string;
  link_path?: string | null;
}

export interface DatasetQualitySummary {
  issue_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  freeform_label_count: number;
  unknown_label_count: number;
  missing_zone_count: number;
  missing_media_count: number;
  conflicting_correction_count: number;
  false_positive_count: number;
  export_ready_count: number;
  needs_review_count: number;
  issues: DatasetQualityIssue[];
  generated_at: string;
  local_first_note: string;
}

export interface AnalyticsSummary {
  event_count: number;
  visit_count: number;
  needs_review_count: number;
  species_counts: Record<string, number>;
  label_display_names: Record<string, string>;
  label_categories: Partial<Record<string, LabelCategory>>;
  species_label_ids: string[];
  zone_activity_counts: Record<string, number>;
}

export type WildlifeInsightsRangePreset = "today" | "last_7_days" | "last_30_days" | "custom";

export interface WildlifeInsightsRequest {
  preset: WildlifeInsightsRangePreset;
  start_date?: string | null;
  end_date?: string | null;
}

export interface WildlifeInsightsPeriod {
  preset: WildlifeInsightsRangePreset;
  start_date: string;
  end_date: string;
  previous_start_date: string;
  previous_end_date: string;
  timezone_name: string;
}

export interface WildlifeInsightsDrilldown {
  review_filter: ActivityLibraryReviewFilter;
  start_date: string;
  end_date: string;
  stream_id?: string | null;
  zone_id?: string | null;
  confirmed_label?: string | null;
}

export interface WildlifeInsightsRepresentative {
  visit_id: string;
  event_id: string;
  stream_id: string;
  stream_name: string;
  zone_id?: string | null;
  zone_name?: string | null;
  label: string;
  display_name: string;
  observed_at: string;
  primary_evidence?: VisitEvidenceFrame | null;
}

export interface WildlifeInsightsBreakdown {
  id: string;
  name: string;
  count: number;
  previous_count: number;
  change: number;
  first_observed_at?: string | null;
  latest_observed_at?: string | null;
  representative?: WildlifeInsightsRepresentative | null;
  drilldown: WildlifeInsightsDrilldown;
}

export interface WildlifeInsightsDailyBucket {
  local_date: string;
  count: number;
}

export interface WildlifeInsightsHourBucket {
  hour: number;
  count: number;
}

export interface WildlifeInsightsHeadline {
  active_stream_count: number;
  active_visit_count: number;
  reviewed_wildlife_observation_count: number;
  unique_confirmed_label_count: number;
  unresolved_visit_count: number;
  reviewed_non_bird_activity_count: number;
  busiest_stream?: WildlifeInsightsBreakdown | null;
  busiest_zone?: WildlifeInsightsBreakdown | null;
  peak_activity_hour?: number | null;
  first_observation?: WildlifeInsightsRepresentative | null;
  latest_observation?: WildlifeInsightsRepresentative | null;
}

export interface WildlifeInsightsComparison {
  previous_reviewed_wildlife_observation_count: number;
  reviewed_wildlife_observation_change: number;
  new_labels: string[];
  labels_not_seen: string[];
}

export interface WildlifeInsightsReviewContext {
  blank_or_false_count: number;
  ambiguous_or_unknown_count: number;
  rejected_count: number;
  unclassified_reviewed_count: number;
  pending_suggestion_evidence_count: number;
}

export interface WildlifeInsightsSummary {
  period: WildlifeInsightsPeriod;
  headline: WildlifeInsightsHeadline;
  comparison: WildlifeInsightsComparison;
  leading_labels: WildlifeInsightsBreakdown[];
  daily_trend: WildlifeInsightsDailyBucket[];
  activity_by_hour: WildlifeInsightsHourBucket[];
  stream_breakdown: WildlifeInsightsBreakdown[];
  zone_breakdown: WildlifeInsightsBreakdown[];
  review_context: WildlifeInsightsReviewContext;
  confirmed_activity_drilldown: WildlifeInsightsDrilldown;
  unresolved_activity_drilldown: WildlifeInsightsDrilldown;
}


export type ZoneInsightsQualityStatus =
  | "sufficient"
  | "limited_monitoring"
  | "limited_review_coverage"
  | "no_confirmed_activity"
  | "unavailable_exposure"
  | "unavailable";

export interface ZoneInsightsRequest {
  start_at?: string | null;
  end_at?: string | null;
  stream_id?: string | null;
  source_id?: string | null;
  zone_type?: ZoneType | null;
  confirmed_taxonomy_id?: string | null;
}

export interface ZoneInsightsAppliedFilters {
  start_at: string;
  end_at: string;
  stream_id?: string | null;
  source_id?: string | null;
  zone_type?: ZoneType | null;
  confirmed_taxonomy_id?: string | null;
}

export interface ZoneInsightsDrilldown {
  filters: ActivityLibraryFilters;
}

export interface ZoneInsightsSpeciesComposition {
  taxonomy_id: string;
  label: string;
  display_name: string;
  visit_count: number;
  percentage: number;
  drilldown: ZoneInsightsDrilldown;
}

export interface ZoneInsightsMetrics {
  healthy_monitored_hours?: number | null;
  exposure_history_available_from?: string | null;
  exposure_history_is_partial: boolean;
  exposure_interval_count: number;
  confirmed_bird_visit_count: number;
  confirmed_bird_visits_per_monitored_hour?: number | null;
  total_confirmed_bird_dwell_seconds: number;
  median_confirmed_bird_duration_seconds?: number | null;
  confirmed_species_richness: number;
  unresolved_visit_count: number;
  reviewed_visit_count: number;
  reviewed_blank_count: number;
  reviewed_non_bird_count: number;
  reviewed_false_positive_count: number;
  review_coverage_percentage?: number | null;
  reviewed_false_positive_percentage?: number | null;
  evidence_success_percentage?: number | null;
  first_confirmed_activity_at?: string | null;
  last_confirmed_activity_at?: string | null;
  data_quality_status: ZoneInsightsQualityStatus;
  warnings: string[];
}

export interface ZoneInsightsZone {
  zone_id: string;
  zone_name: string;
  zone_type: ZoneType;
  stream_id: string;
  stream_name: string;
  source_id: string;
  source_name: string;
  metrics: ZoneInsightsMetrics;
  species_composition: ZoneInsightsSpeciesComposition[];
  confirmed_activity_drilldown: ZoneInsightsDrilldown;
  unresolved_activity_drilldown: ZoneInsightsDrilldown;
  reviewed_blank_drilldown: ZoneInsightsDrilldown;
  reviewed_non_bird_drilldown: ZoneInsightsDrilldown;
}

export interface ZoneInsightsDailyBucket {
  local_date: string;
  confirmed_bird_visit_count: number;
  drilldown: ZoneInsightsDrilldown;
}

export interface ZoneInsightsHourBucket {
  hour: number;
  confirmed_bird_visit_count: number;
  drilldown: ZoneInsightsDrilldown;
}

export interface ZoneInsightsSummary {
  generated_at: string;
  applied_filters: ZoneInsightsAppliedFilters;
  aggregate: ZoneInsightsMetrics;
  zone_count: number;
  zones: ZoneInsightsZone[];
  daily_trend: ZoneInsightsDailyBucket[];
  activity_by_hour: ZoneInsightsHourBucket[];
  busiest_supported_hour?: number | null;
  warnings: string[];
}

export type WildlifeJournalOrder =
  | "most_recent"
  | "most_observed"
  | "alphabetical"
  | "first_observed";
export type WildlifeJournalGalleryOrder = "newest" | "oldest";
export type WildlifeJournalRangePreset =
  | "all_time"
  | "today"
  | "last_7_days"
  | "last_30_days"
  | "this_year"
  | "custom";

export interface WildlifeJournalHistoryRequest {
  preset?: WildlifeJournalRangePreset;
  start_date?: string | null;
  end_date?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  favorites_only?: boolean;
  tag_id?: string | null;
  gallery_order?: WildlifeJournalGalleryOrder;
  page_size?: number;
  offset?: number;
}

export interface WildlifeJournalScope {
  preset: WildlifeJournalRangePreset;
  start_date?: string | null;
  end_date?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
  favorites_only: boolean;
  tag_id?: string | null;
  timezone_name: string;
}

export interface WildlifeJournalDrilldown {
  review_filter: ActivityLibraryReviewFilter;
  confirmed_label: string;
  start_date?: string | null;
  end_date?: string | null;
  stream_id?: string | null;
  zone_id?: string | null;
}

export interface WildlifeJournalRepresentative {
  visit_id: string;
  event_id: string;
  stream_id: string;
  stream_name: string;
  source_name: string;
  zone_id?: string | null;
  zone_name?: string | null;
  label: string;
  display_name: string;
  observed_at: string;
  primary_evidence?: VisitEvidenceFrame | null;
}

export interface WildlifeJournalRecentDay {
  local_date: string;
  count: number;
}

export interface WildlifeJournalLabelSummary {
  label: string;
  display_name: string;
  observation_count: number;
  first_observed_at: string;
  latest_observed_at: string;
  stream_count: number;
  zone_count: number;
  recent_activity: WildlifeJournalRecentDay[];
  representative?: WildlifeJournalRepresentative | null;
}

export interface WildlifeJournalOverviewResponse {
  order: WildlifeJournalOrder;
  labels: WildlifeJournalLabelSummary[];
}

export interface WildlifeJournalBreakdown {
  id: string;
  name: string;
  count: number;
}

export interface WildlifeJournalHourBucket {
  hour: number;
  count: number;
}

export interface WildlifeJournalObservation {
  visit_id: string;
  event_id: string;
  stream_id: string;
  stream_name: string;
  source_name: string;
  zone_id?: string | null;
  zone_name?: string | null;
  observed_at: string;
  activity_started_at: string;
  activity_ended_at?: string | null;
  duration_seconds: number;
  evidence_frame_count: number;
  reviewed_label: string;
  display_name: string;
  primary_evidence?: VisitEvidenceFrame | null;
  has_curation_history: boolean;
  has_review_revision: boolean;
  is_first_on_stream: boolean;
  is_first_in_zone: boolean;
  is_favorite: boolean;
  has_note: boolean;
  collection_count: number;
  tags: string[];
}

export interface WildlifeJournalGallery {
  order: WildlifeJournalGalleryOrder;
  observations: WildlifeJournalObservation[];
  has_more: boolean;
  next_offset?: number | null;
}

export interface WildlifeJournalHistoryResponse {
  label: string;
  display_name: string;
  scope: WildlifeJournalScope;
  observation_count: number;
  first_observation?: WildlifeJournalRepresentative | null;
  latest_observation?: WildlifeJournalRepresentative | null;
  representative?: WildlifeJournalRepresentative | null;
  busiest_stream?: WildlifeJournalBreakdown | null;
  busiest_zone?: WildlifeJournalBreakdown | null;
  peak_activity_hour?: number | null;
  stream_breakdown: WildlifeJournalBreakdown[];
  zone_breakdown: WildlifeJournalBreakdown[];
  activity_by_hour: WildlifeJournalHourBucket[];
  is_new_label_in_range: boolean;
  activity_library_drilldown: WildlifeJournalDrilldown;
  gallery: WildlifeJournalGallery;
}

export interface LocalDataStatus {
  database_url: string;
  database_path?: string | null;
  using_default_database: boolean;
  source_count: number;
  stream_count: number;
  zone_count: number;
  event_count: number;
  visit_count: number;
  media_asset_count: number;
  detection_run_count: number;
  detection_proposal_count: number;
  motion_evidence_count: number;
  review_label_count: number;
  dataset_export_count: number;
  needs_review_count: number;
  database_ready: boolean;
  database_schema_version: number;
  database_schema_current_version: number;
  database_integrity_check: string;
  seed_data_present: boolean;
  local_first_note: string;
}

export type LocalBackupKind = "manual" | "pre_restore";
export type LocalBackupVerificationStatus = "verified" | "not_checked";

export interface LocalBackupSummary {
  id: string;
  created_at: string;
  kind: LocalBackupKind;
  database_schema_version: number;
  database_size_bytes: number;
  media_file_count: number;
  media_size_bytes: number;
  archive_size_bytes: number;
  verification_status: LocalBackupVerificationStatus;
  restore_compatible: boolean;
}

export interface LocalBackupLibraryResponse {
  backups: LocalBackupSummary[];
  unreadable_backup_count: number;
  local_first_note: string;
}

export interface LocalBackupVerificationResponse {
  backup: LocalBackupSummary;
  verified: boolean;
  checked_at: string;
  message: string;
}

export interface LocalBackupRestoreResponse {
  restored_backup: LocalBackupSummary;
  safety_backup: LocalBackupSummary;
  status: LocalDataStatus;
  message: string;
}

export type StorageRetentionFrequency = "daily" | "weekly";

export interface StorageRetentionSettings {
  automatic_cleanup_enabled: boolean;
  cleanup_frequency: StorageRetentionFrequency;
  retain_unresolved_visit_evidence: boolean;
  retain_reviewed_bird_wildlife_evidence: boolean;
  reviewed_non_bird_age_days: number;
  superseded_evidence_age_days: number;
  orphaned_media_age_days: number;
  maximum_managed_media_bytes?: number | null;
  policy_revision: number;
  persisted: boolean;
  recommended_defaults: boolean;
  updated_at?: string | null;
  last_automatic_run_at?: string | null;
  last_automatic_result?: string | null;
  message: string;
}

export interface StorageRetentionSettingsUpdate {
  automatic_cleanup_enabled: boolean;
  cleanup_frequency: StorageRetentionFrequency;
  retain_unresolved_visit_evidence: boolean;
  retain_reviewed_bird_wildlife_evidence: boolean;
  reviewed_non_bird_age_days: number;
  superseded_evidence_age_days: number;
  orphaned_media_age_days: number;
  maximum_managed_media_bytes?: number | null;
  idempotency_key: string;
}

export interface StorageSummary {
  total_managed_media_bytes: number;
  total_managed_media_count: number;
  oldest_managed_media_at?: string | null;
  newest_managed_media_at?: string | null;
  approximate_database_bytes?: number | null;
  active_visit_media_count: number;
  active_visit_media_bytes: number;
  superseded_only_media_count: number;
  superseded_only_media_bytes: number;
  orphaned_managed_media_count: number;
  orphaned_managed_media_bytes: number;
  unresolved_visit_evidence_count: number;
  reviewed_bird_wildlife_evidence_count: number;
  reviewed_non_bird_blank_ambiguous_evidence_count: number;
  disk_total_bytes: number;
  disk_free_bytes: number;
  is_writable: boolean;
  storage_warning?: string | null;
  message: string;
}

export interface SetupState {
  completed: boolean;
  current_step: string;
  last_created_stream_id?: string | null;
  updated_at: string;
}

export interface SetupStateUpdate {
  current_step: string;
  completed: boolean;
  last_created_stream_id?: string | null;
}

export interface ProductHealthStatus {
  app_version: string;
  ready: boolean;
  message: string;
  storage_writable: boolean;
  storage_low_space: boolean;
  storage_warning?: string | null;
  cameras: { needs_attention_count: number };
  observation: { configured_stream_count: number; monitored_stream_count: number };
  backup: {
    has_backup: boolean;
    last_backup_at?: string | null;
    last_backup_verified?: boolean | null;
  };
  previous_shutdown_clean?: boolean | null;
  database_schema_version: number;
  log_path?: string | null;
  generated_at: string;
}

export interface StorageCleanupCategorySummary {
  category: string;
  media_count: number;
  bytes: number;
}

export interface StorageCleanupPreviewResponse {
  preview_token: string;
  generated_at: string;
  expires_at: string;
  eligible_media_count: number;
  estimated_recoverable_bytes: number;
  categories: StorageCleanupCategorySummary[];
  oldest_eligible_at?: string | null;
  newest_eligible_at?: string | null;
  affected_visit_count: number;
  protected_counts: StorageCleanupCategorySummary[];
  warnings: string[];
  message: string;
  creates_review_truth: boolean;
}

export interface StorageCleanupResult {
  batch_id: string;
  state: string;
  moved_to_recovery_count: number;
  skipped_count: number;
  failed_count: number;
  recovered_bytes: number;
  recovery_expires_at?: string | null;
  message: string;
  warnings: string[];
  idempotent: boolean;
  creates_review_truth: boolean;
}

export interface StorageCleanupHistoryItem {
  batch_id: string;
  origin: string;
  state: string;
  created_at: string;
  media_count: number;
  recovered_bytes: number;
  permanently_purged_count: number;
  skipped_count: number;
  failed_count: number;
  recovery_expires_at?: string | null;
  message: string;
  can_restore: boolean;
}

export interface StorageCleanupHistoryResponse {
  items: StorageCleanupHistoryItem[];
  message: string;
}

export interface SampleDataRemovalResponse {
  removed: boolean;
  removed_counts: Record<string, number>;
  preserved_source_count: number;
  status: LocalDataStatus;
  message: string;
}
