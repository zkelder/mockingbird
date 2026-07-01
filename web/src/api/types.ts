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

export interface HealthStatus {
  status: string;
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

export interface AnalyticsSummary {
  event_count: number;
  visit_count: number;
  needs_review_count: number;
  species_counts: Record<string, number>;
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
