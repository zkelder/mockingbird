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

export type ReviewStatus = "needs_review" | "reviewed" | "rejected";
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
export type FocusCropSource = "zone" | "activity" | "manual" | "none";
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
  checkpoint_updated_at?: string | null;
  last_start_attempt_at?: string | null;
  last_healthy_frame_at?: string | null;
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
    | "opened"
    | "camera_running"
    | "camera_not_configured"
    | "ffmpeg_missing"
    | "unsupported"
    | "timed_out"
    | "failed";
  message: string;
  creates_media: boolean;
  creates_evidence: boolean;
  creates_event: boolean;
  creates_visit: boolean;
  creates_truth: boolean;
  warnings: string[];
}

export interface LiveCameraSessionStatus {
  stream_id: string;
  source_id?: string | null;
  playback_kind?: string | null;
  status: "stopped" | "starting" | "running" | "stopping" | "failed" | string;
  started_at?: string | null;
  last_frame_at?: string | null;
  latest_frame_age_ms?: number | null;
  newest_frame_age_ms?: number | null;
  frame_count: number;
  clients_connected: number;
  monitor_running: boolean;
  auto_create_review_candidates: boolean;
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
  zone_id: string;
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
  zone_id: string;
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
  auto_review_quiet_seconds?: number;
  auto_review_min_detections?: number;
}

export interface LiveMotionMonitorSettingsRequest {
  auto_create_review_candidates?: boolean;
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
  review_status: ReviewStatus;
  reason: string;
}

export interface ReviewLabel {
  id: string;
  target_type: string;
  target_id: string;
  label: string;
  notes?: string | null;
  created_at: string;
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
}

export interface ReviewCorrectionResult {
  review_label: ReviewLabel;
  visit?: Visit | null;
  event?: Event | null;
  review_queue_count: number;
  analytics: AnalyticsSummary;
}

export type ReviewQueueBulkCorrectionTargetType = "event" | "visit";
export type ReviewQueueBulkCorrectionResultStatus = "succeeded" | "skipped" | "failed";

export interface ReviewIdentificationRequest {
  adapter_id?: string | null;
  media_asset_id?: string | null;
  requested_labels?: string[] | null;
  notes?: string | null;
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
  detection_proposals: DetectionProposal[];
  detection_runs: DetectionRun[];
  review_labels: ReviewLabel[];
  dataset_ready: boolean;
  review_summary: string;
}

export interface DatasetExport {
  id: string;
  name: string;
  status: ExportStatus;
  reviewed_only: boolean;
  include_detections: boolean;
  include_zone_context: boolean;
  record_count: number;
  created_at: string;
}

export interface DatasetExportCreate {
  name: string;
  reviewed_only?: boolean;
  include_detections?: boolean;
  include_zone_context?: boolean;
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

export interface SampleDataRemovalResponse {
  removed: boolean;
  removed_counts: Record<string, number>;
  preserved_source_count: number;
  status: LocalDataStatus;
  message: string;
}
