export type SourceKind =
  | "demo"
  | "manual_upload"
  | "local_folder"
  | "rtsp"
  | "local_camera"
  | "webhook"
  | "integration";

export type SourceStatus = "connected" | "disconnected" | "needs_setup";

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
export type ExportStatus = "ready" | "building" | "failed";
export type DetectionSource = "manual" | "demo_rule" | "future_model" | "integration";
export type DetectionRunStatus = "pending" | "completed" | "failed";
export type DetectionProposalStatus = "proposed" | "accepted" | "rejected" | "converted";
export type DetectionProposalDecision = "accept" | "reject" | "convert_to_event";
export type MotionEvidenceStatus = "pending" | "promoted" | "ignored";
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

export interface Stream {
  id: string;
  source_id: string;
  name: string;
  description: string;
  is_live: boolean;
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
  checklist: ModelReadinessChecklistItem[];
  generated_at: string;
  local_first_note: string;
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
  scoring_config: Record<string, string | number | boolean>;
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
  scoring_config?: Record<string, string | number | boolean>;
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

export interface FolderImportCreate {
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

export interface ReviewQueueItem {
  id: string;
  item_type: string;
  title: string;
  stream_id: string;
  event_id?: string | null;
  visit_id?: string | null;
  primary_zone_id?: string | null;
  suggested_label?: string | null;
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

export interface EventDetail {
  event: Event;
  stream: Stream;
  primary_zone?: Zone | null;
  visits: Visit[];
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
  review_label_count: number;
  dataset_export_count: number;
  needs_review_count: number;
  database_ready: boolean;
  seed_data_present: boolean;
  local_first_note: string;
}
