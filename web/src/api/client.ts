import type {
  ActivityLibraryExportSelectionRequest,
  ActivityLibraryExportSelectionResponse,
  ActivityLibrarySavedView,
  ActivityLibrarySavedViewCreate,
  ActivityLibrarySavedViewUpdate,
  ActivityLibrarySearchRequest,
  ActivityLibrarySearchResponse,
  AdapterEvaluationSummary,
  AnalyticsSummary,
  CameraSource,
  CameraSourceCreateRequest,
  CameraSourceCreateResponse,
  CameraSourceMutationResult,
  CameraSourceUpdateRequest,
  ClassifierManifestFileExportRequest,
  ClassifierManifestFileExportResponse,
  ClassifierReadinessReport,
  ClassifierTrainingManifestResponse,
  DatasetCoverageSummary,
  DatasetExport,
  DatasetExportCreate,
  DatasetExportDetail,
  DatasetExportManifest,
  DatasetQualitySummary,
  DashboardSummary,
  DemoDetectionRunCreate,
  DemoDetectionRunResult,
  DetectionProposal,
  DetectionProposalCreate,
  DetectionProposalDecisionCreate,
  DetectionProposalDecisionResult,
  DetectionRun,
  DetectionRunCreate,
  Event,
  EventDetail,
  ExternalUrlWorkerDryRunResponse,
  ExternalUrlPreviewRequest,
  ExternalUrlPreviewResponse,
  ExternalUrlPreviewSaveRequest,
  ExternalUrlPreviewSaveResponse,
  FolderImportEvidenceBatchCreateRequest,
  FolderImportEvidenceBatchCreateResponse,
  FolderImportEvidenceBatchDryRunRequest,
  FolderImportEvidenceBatchDryRunResponse,
  FolderImportRequest,
  FolderImportResponse,
  LegacyFolderImportCreate,
  FolderImportPreview,
  FolderImportPreviewRequest,
  FolderImportPreviewResponse,
  FolderImportResult,
  LegacyFolderImportPreviewRequest,
  HealthStatus,
  LocalCameraFrameCaptureResponse,
  LiveCameraSessionStatus,
  LocalBackupLibraryResponse,
  LocalBackupRestoreResponse,
  LocalBackupVerificationResponse,
  LocalDataStatus,
  StorageCleanupHistoryResponse,
  StorageCleanupPreviewResponse,
  StorageCleanupResult,
  StorageRetentionSettings,
  StorageRetentionSettingsUpdate,
  StorageSummary,
  MediaAsset,
  MediaImportResult,
  LiveMotionEvaluateRequest,
  LiveMotionEvaluateResponse,
  LiveMotionMonitorSettingsRequest,
  LiveMotionMonitorStartRequest,
  LiveMotionReviewActivityResponse,
  MockSpeciesSuggestionRequest,
  ModelAdapter,
  ModelReadinessSummary,
  ModelAdapterRunRequest,
  ModelAdapterRunResult,
  MotionEvidence,
  MotionEvidenceAttachMediaRequest,
  MotionEvidenceBulkActionRequest,
  MotionEvidenceBulkActionResponse,
  MotionEvidenceCreateRequest,
  MotionEvidenceListResponse,
  MotionEvidencePromoteRequest,
  MotionEvidencePromoteResponse,
  MotionEvidenceStatus,
  MotionEvaluateSavedMediaRequest,
  MotionEvaluateSavedMediaResponse,
  MotionEvaluateSequenceRequest,
  MotionEvaluateSequenceResponse,
  ReviewCorrectionCreate,
  ReviewCorrectionResult,
  VisitEvidenceCurationRequest,
  VisitEvidenceCurationResponse,
  VisitMergeCandidatesResponse,
  VisitMergePreview,
  VisitMergePreviewRequest,
  VisitMergeRequest,
  VisitMergeResponse,
  VisitReviewHistory,
  VisitReviewReopenCreate,
  VisitReviewReopenResponse,
  VisitReviewRevisionCreate,
  VisitReviewRevisionResponse,
  VisitSplitPreview,
  VisitSplitPreviewRequest,
  VisitSplitRequest,
  VisitSplitResponse,
  VisitZoneReassignmentRequest,
  VisitZoneReassignmentResponse,
  FastReviewCorrectionCreate,
  FastReviewCorrectionResponse,
  FastReviewQueueNavigationRequest,
  FastReviewQueueNavigationResponse,
  FastReviewUndoRequest,
  FastReviewUndoResponse,
  ReviewIdentificationRequest,
  ReviewIdentificationResponse,
  ReviewLabel,
  ReviewQueueBulkCorrectionRequest,
  ReviewQueueBulkCorrectionResponse,
  ReviewQueueItem,
  SavedMediaBulkMotionEvidenceRequest,
  SavedMediaBulkMotionEvidenceResponse,
  SavedMediaCleanupDryRunRequest,
  SavedMediaCleanupDryRunResponse,
  SavedMediaCleanupRequest,
  SavedMediaCleanupResponse,
  SavedMediaRetentionReportResponse,
  SavedPreviewMotionEvidenceRequest,
  SavedPreviewMotionEvidenceResponse,
  SampleDataRemovalResponse,
  SpeciesSuggestion,
  SpeciesSuggestionCreateRequest,
  SpeciesSuggestionListResponse,
  SpeciesSuggestionStatus,
  SpeciesSuggestionStatusUpdateRequest,
  SourceConnectionStatus,
  SourceMonitorStartRequest,
  SourceMonitorStatusResponse,
  SourceProviderConfiguration,
  SourceProviderConfigurationUpdate,
  SourceProviderDefinition,
  SourceSetupReviewResponse,
  Stream,
  StreamMonitoringMutationResponse,
  StreamMonitoringPolicy,
  StreamMonitoringPolicyUpdate,
  StreamMonitoringRetryRequest,
  StreamMonitoringStatusListResponse,
  StreamPlaybackStatus,
  StreamRuntimeStatus,
  StreamVisitSummary,
  TaxonomyLabel,
  Visit,
  VisitDetail,
  WorkerStatusResponse,
  WindowsCameraControlsResponse,
  WindowsCameraDiscoveryResponse,
  Zone,
  ZoneCreate,
  ZoneMonitoringPolicy,
  ZoneMonitoringPolicyUpdate,
  ZoneMutationResult,
  ZoneUpdate,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const headers = new Headers(init?.headers);
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function previewFolderImport(
  sourceId: string,
  payload?: FolderImportPreviewRequest,
): Promise<FolderImportPreviewResponse>;
function previewFolderImport(
  payload: LegacyFolderImportPreviewRequest,
): Promise<FolderImportPreview>;
function previewFolderImport(
  sourceIdOrPayload: string | LegacyFolderImportPreviewRequest,
  payload: FolderImportPreviewRequest = {},
) {
  if (typeof sourceIdOrPayload === "string") {
    return request<FolderImportPreviewResponse>(
      `/api/sources/${encodeURIComponent(sourceIdOrPayload)}/folder-import/preview`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  return request<FolderImportPreview>("/api/media/folder-preview", {
    method: "POST",
    body: JSON.stringify(sourceIdOrPayload),
  });
}

function importFolderMedia(
  sourceId: string,
  payload?: FolderImportRequest,
): Promise<FolderImportResponse>;
function importFolderMedia(payload: LegacyFolderImportCreate): Promise<FolderImportResult>;
function importFolderMedia(
  sourceIdOrPayload: string | LegacyFolderImportCreate,
  payload: FolderImportRequest = {},
) {
  if (typeof sourceIdOrPayload === "string") {
    return request<FolderImportResponse>(
      `/api/sources/${encodeURIComponent(sourceIdOrPayload)}/folder-import`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  return request<FolderImportResult>("/api/media/folder-import", {
    method: "POST",
    body: JSON.stringify(sourceIdOrPayload),
  });
}

export const apiClient = {
  baseUrl: API_BASE_URL,
  getHealth: () => request<HealthStatus>("/health"),
  getTaxonomyLabels: () => request<TaxonomyLabel[]>("/api/taxonomy/labels"),
  getTaxonomyLabel: (label: string) =>
    request<TaxonomyLabel>(`/api/taxonomy/labels/${encodeURIComponent(label)}`),
  getTaxonomySuggestions: (params: { query?: string; category?: string } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.query) {
      searchParams.set("query", params.query);
    }
    if (params.category) {
      searchParams.set("category", params.category);
    }
    const query = searchParams.toString();
    return request<TaxonomyLabel[]>(`/api/taxonomy/suggestions${query ? `?${query}` : ""}`);
  },
  getSources: () => request<CameraSource[]>("/api/sources"),
  createCameraSource: (payload: CameraSourceCreateRequest) =>
    request<CameraSourceCreateResponse>("/api/sources", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCameraSource: (sourceId: string, payload: CameraSourceUpdateRequest) =>
    request<CameraSourceMutationResult>(`/api/sources/${encodeURIComponent(sourceId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getSourceProviderDefinitions: () =>
    request<SourceProviderDefinition[]>("/api/source-provider-definitions"),
  getWorkerStatus: () => request<WorkerStatusResponse>("/api/workers/status"),
  getExternalUrlWorkerDryRunPlan: () =>
    request<ExternalUrlWorkerDryRunResponse>("/api/workers/external-url-preview/dry-run"),
  getSourceConnectionStatus: (sourceId: string) =>
    request<SourceConnectionStatus>(`/api/sources/${sourceId}/connection`),
  getSourceSetupReview: (sourceId: string) =>
    request<SourceSetupReviewResponse>(`/api/sources/${sourceId}/setup-review`),
  getSourceProviderConfiguration: (sourceId: string) =>
    request<SourceProviderConfiguration>(`/api/sources/${sourceId}/provider-configuration`),
  updateSourceProviderConfiguration: (
    sourceId: string,
    payload: SourceProviderConfigurationUpdate,
  ) =>
    request<SourceProviderConfiguration>(`/api/sources/${sourceId}/provider-configuration`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  fetchExternalUrlPreview: (sourceId: string, payload: ExternalUrlPreviewRequest = {}) =>
    request<ExternalUrlPreviewResponse>(`/api/sources/${sourceId}/external-url/preview`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveExternalUrlPreview: (sourceId: string, payload: ExternalUrlPreviewSaveRequest = {}) =>
    request<ExternalUrlPreviewSaveResponse>(`/api/sources/${sourceId}/external-url/preview/save`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startStreamMonitor: (streamId: string, payload: SourceMonitorStartRequest = {}) =>
    request<SourceMonitorStatusResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/monitor/start`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  stopStreamMonitor: (streamId: string) =>
    request<SourceMonitorStatusResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/monitor/stop`,
      {
        method: "POST",
      },
    ),
  createStreamMonitorReviewActivity: (streamId: string) =>
    request<SourceMonitorStatusResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/monitor/review-activity`,
      {
        method: "POST",
      },
    ),
  getStreamMonitorStatus: (streamId: string) =>
    request<SourceMonitorStatusResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/monitor/status`,
    ),
  getDashboardSummary: () => request<DashboardSummary>("/api/dashboard/summary"),
  getStreams: () => request<Stream[]>("/api/streams"),
  getStreamMonitoringStatuses: (limit = 50) =>
    request<StreamMonitoringStatusListResponse>(
      `/api/streams/monitoring-status?limit=${encodeURIComponent(String(limit))}`,
    ),
  getZones: () => request<Zone[]>("/api/zones"),
  getStream: (streamId: string) => request<Stream>(`/api/streams/${streamId}`),
  getStreamPlaybackStatus: (streamId: string) =>
    request<StreamPlaybackStatus>(`/api/streams/${streamId}/playback`),
  getStreamMonitoringPolicy: (streamId: string) =>
    request<StreamMonitoringPolicy>(
      `/api/streams/${encodeURIComponent(streamId)}/monitoring-policy`,
    ),
  getStreamRuntimeStatus: (streamId: string) =>
    request<StreamRuntimeStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/runtime-status`,
    ),
  updateStreamMonitoringPolicy: (
    streamId: string,
    payload: StreamMonitoringPolicyUpdate,
  ) =>
    request<StreamMonitoringMutationResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/monitoring-policy`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    ),
  retryStreamMonitoring: (
    streamId: string,
    payload: StreamMonitoringRetryRequest,
  ) =>
    request<StreamMonitoringMutationResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/runtime/retry`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  rtspMjpegBridgeUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live/rtsp-mjpeg`,
  localCameraMjpegBridgeUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live/local-mjpeg`,
  windowsDshowMjpegBridgeUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live/windows-dshow-mjpeg`,
  discoverWindowsCameras: () =>
    request<WindowsCameraDiscoveryResponse>("/api/local-cameras/windows"),
  openWindowsCameraControls: (streamId: string) =>
    request<WindowsCameraControlsResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-controls/open`,
      {
        method: "POST",
      },
    ),
  startLiveCameraSession: (streamId: string) =>
    request<LiveCameraSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/live-session/start`,
      {
        method: "POST",
      },
    ),
  stopLiveCameraSession: (streamId: string) =>
    request<LiveCameraSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/live-session/stop`,
      {
        method: "POST",
      },
    ),
  getLiveCameraSessionStatus: (streamId: string) =>
    request<LiveCameraSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/live-session/status`,
    ),
  liveCameraSessionMjpegUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live-session/mjpeg`,
  captureLocalCameraFrame: (streamId: string) =>
    request<LocalCameraFrameCaptureResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/local-camera/capture-frame`,
      {
        method: "POST",
      },
    ),
  evaluateLiveMotion: (streamId: string, payload: LiveMotionEvaluateRequest = {}) =>
    request<LiveMotionEvaluateResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/live-motion/evaluate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  startLiveMotionMonitor: (
    streamId: string,
    payload: LiveMotionMonitorStartRequest = {},
  ) =>
    request<LiveMotionEvaluateResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/live-motion/start`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  updateLiveMotionMonitorSettings: (
    streamId: string,
    payload: LiveMotionMonitorSettingsRequest = {},
  ) =>
    request<LiveCameraSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/live-motion/settings`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  stopLiveMotionMonitor: (streamId: string) =>
    request<LiveCameraSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/live-motion/stop`,
      {
        method: "POST",
      },
    ),
  createLiveMotionReviewActivity: (streamId: string) =>
    request<LiveMotionReviewActivityResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/live-motion/review-activity`,
      {
        method: "POST",
      },
    ),
  getStreamZones: (streamId: string) => request<Zone[]>(`/api/streams/${streamId}/zones`),
  getStreamEvents: (streamId: string) => request<Event[]>(`/api/streams/${streamId}/events`),
  getStreamRecentVisits: (
    streamId: string,
    params: {
      limit?: number;
      review_status?: "needs_review" | "reviewed" | "rejected";
      zone_id?: string;
      start_at?: string;
      end_at?: string;
    } = {},
  ) => {
    const searchParams = new URLSearchParams();
    if (params.limit != null) {
      searchParams.set("limit", String(params.limit));
    }
    if (params.review_status) {
      searchParams.set("review_status", params.review_status);
    }
    if (params.zone_id) {
      searchParams.set("zone_id", params.zone_id);
    }
    if (params.start_at) {
      searchParams.set("start_at", params.start_at);
    }
    if (params.end_at) {
      searchParams.set("end_at", params.end_at);
    }
    const query = searchParams.toString();
    return request<StreamVisitSummary[]>(
      `/api/streams/${encodeURIComponent(streamId)}/visits${query ? `?${query}` : ""}`,
    );
  },
  getEventVisits: (eventId: string) => request<Visit[]>(`/api/events/${eventId}/visits`),
  getEventDetail: (eventId: string) => request<EventDetail>(`/api/events/${eventId}/detail`),
  getVisitDetail: (visitId: string) => request<VisitDetail>(`/api/visits/${visitId}/detail`),
  curateVisitEvidence: (visitId: string, payload: VisitEvidenceCurationRequest) =>
    request<VisitEvidenceCurationResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/evidence-curation`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  previewVisitSplit: (visitId: string, payload: VisitSplitPreviewRequest) =>
    request<VisitSplitPreview>(`/api/visits/${encodeURIComponent(visitId)}/split/preview`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  splitVisit: (visitId: string, payload: VisitSplitRequest) =>
    request<VisitSplitResponse>(`/api/visits/${encodeURIComponent(visitId)}/split`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getVisitMergeCandidates: (visitId: string) =>
    request<VisitMergeCandidatesResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/merge-candidates`,
    ),
  previewVisitMerge: (visitId: string, payload: VisitMergePreviewRequest) =>
    request<VisitMergePreview>(`/api/visits/${encodeURIComponent(visitId)}/merge/preview`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  mergeVisits: (visitId: string, payload: VisitMergeRequest) =>
    request<VisitMergeResponse>(`/api/visits/${encodeURIComponent(visitId)}/merge`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reassignVisitZone: (visitId: string, payload: VisitZoneReassignmentRequest) =>
    request<VisitZoneReassignmentResponse>(`/api/visits/${encodeURIComponent(visitId)}/zone`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getMediaAssets: () => request<MediaAsset[]>("/api/media"),
  getMediaAsset: (mediaId: string) => request<MediaAsset>(`/api/media/${mediaId}`),
  getSavedMediaRetentionReport: () =>
    request<SavedMediaRetentionReportResponse>("/api/media/saved-preview-retention"),
  dryRunSavedMediaCleanup: (payload: SavedMediaCleanupDryRunRequest = {}) =>
    request<SavedMediaCleanupDryRunResponse>(
      "/api/media/saved-preview-retention/dry-run-cleanup",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  cleanupSavedPreviewMedia: (mediaAssetId: string, payload: SavedMediaCleanupRequest) =>
    request<SavedMediaCleanupResponse>(
      `/api/media/${encodeURIComponent(mediaAssetId)}/cleanup-preview`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  createMotionEvidenceFromMedia: (
    mediaId: string,
    payload: SavedPreviewMotionEvidenceRequest = {},
  ) =>
    request<SavedPreviewMotionEvidenceResponse>(
      `/api/media/${encodeURIComponent(mediaId)}/create-motion-evidence`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  bulkCreateMotionEvidenceFromMedia: (payload: SavedMediaBulkMotionEvidenceRequest) =>
    request<SavedMediaBulkMotionEvidenceResponse>("/api/media/bulk-create-motion-evidence", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  dryRunFolderImportEvidence: (payload: FolderImportEvidenceBatchDryRunRequest) =>
    request<FolderImportEvidenceBatchDryRunResponse>("/api/folder-import/evidence/dry-run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createFolderImportEvidenceBatch: (payload: FolderImportEvidenceBatchCreateRequest) =>
    request<FolderImportEvidenceBatchCreateResponse>("/api/folder-import/evidence/batch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDetectionRuns: () => request<DetectionRun[]>("/api/detection-runs"),
  createDetectionRun: (payload: DetectionRunCreate) =>
    request<DetectionRun>("/api/detection-runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createDemoDetectionRun: (payload: DemoDetectionRunCreate) =>
    request<DemoDetectionRunResult>("/api/detection-runs/demo", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDetectionRunProposals: (runId: string) =>
    request<DetectionProposal[]>(`/api/detection-runs/${runId}/proposals`),
  getDetectionProposals: () => request<DetectionProposal[]>("/api/detection-proposals"),
  createDetectionProposal: (payload: DetectionProposalCreate) =>
    request<DetectionProposal>("/api/detection-proposals", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  decideDetectionProposal: (proposalId: string, payload: DetectionProposalDecisionCreate) =>
    request<DetectionProposalDecisionResult>(`/api/detection-proposals/${proposalId}/decision`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  importMedia: (payload: FormData) =>
    request<MediaImportResult>("/api/media/import", {
      method: "POST",
      body: payload,
    }),
  previewFolderImport,
  importFolderMedia,
  mediaFileUrl: (mediaId: string) => `${API_BASE_URL}/api/media/${encodeURIComponent(mediaId)}/file`,
  getModelAdapters: () => request<ModelAdapter[]>("/api/model-adapters"),
  getModelAdapter: (adapterId: string) =>
    request<ModelAdapter>(`/api/model-adapters/${encodeURIComponent(adapterId)}`),
  getModelAdapterEvaluation: (params: { adapterId?: string } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.adapterId) {
      searchParams.set("adapter_id", params.adapterId);
    }
    const query = searchParams.toString();
    return request<AdapterEvaluationSummary>(
      `/api/model-adapters/evaluation${query ? `?${query}` : ""}`,
    );
  },
  getModelReadinessSummary: () => request<ModelReadinessSummary>("/api/model-readiness/summary"),
  getClassifierReadiness: () => request<ClassifierReadinessReport>("/api/classifier-readiness"),
  getClassifierTrainingManifest: () =>
    request<ClassifierTrainingManifestResponse>("/api/classifier-training-manifest"),
  createClassifierManifestExport: (payload: ClassifierManifestFileExportRequest) =>
    request<ClassifierManifestFileExportResponse>("/api/classifier-training-manifest/exports", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runModelAdapter: (adapterId: string, payload: ModelAdapterRunRequest) =>
    request<ModelAdapterRunResult>(`/api/model-adapters/${encodeURIComponent(adapterId)}/runs`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listMotionEvidence: (params: { status?: MotionEvidenceStatus | "all"; zone_id?: string } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.status && params.status !== "all") {
      searchParams.set("status", params.status);
    }
    if (params.zone_id) {
      searchParams.set("zone_id", params.zone_id);
    }
    const query = searchParams.toString();
    return request<MotionEvidenceListResponse>(`/api/motion/evidence${query ? `?${query}` : ""}`);
  },
  getMotionEvidence: (id: string) =>
    request<MotionEvidence>(`/api/motion/evidence/${encodeURIComponent(id)}`),
  createMotionEvidence: (payload: MotionEvidenceCreateRequest) =>
    request<MotionEvidence>("/api/motion/evidence", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  evaluateMotionSequence: (payload: MotionEvaluateSequenceRequest) =>
    request<MotionEvaluateSequenceResponse>("/api/motion/evaluate-sequence", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  evaluateSavedMediaMotion: (payload: MotionEvaluateSavedMediaRequest) =>
    request<MotionEvaluateSavedMediaResponse>("/api/motion/evaluate-saved-media", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  ignoreMotionEvidence: (id: string) =>
    request<MotionEvidence>(`/api/motion/evidence/${encodeURIComponent(id)}/ignore`, {
      method: "POST",
    }),
  attachMotionEvidenceMedia: (id: string, payload: MotionEvidenceAttachMediaRequest) =>
    request<MotionEvidence>(`/api/motion/evidence/${encodeURIComponent(id)}/attach-media`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  promoteMotionEvidence: (id: string, payload: MotionEvidencePromoteRequest = {}) =>
    request<MotionEvidencePromoteResponse>(
      `/api/motion/evidence/${encodeURIComponent(id)}/promote`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  bulkMotionEvidenceAction: (payload: MotionEvidenceBulkActionRequest) =>
    request<MotionEvidenceBulkActionResponse>("/api/motion-evidence/bulk-action", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listSpeciesSuggestions: (
	    params: {
      status?: SpeciesSuggestionStatus | "all";
      visit_id?: string;
      event_id?: string;
      media_asset_id?: string;
      suggested_label?: string;
    } = {},
  ) => {
    const searchParams = new URLSearchParams();
    if (params.status && params.status !== "all") {
      searchParams.set("status", params.status);
    }
    if (params.visit_id) {
      searchParams.set("visit_id", params.visit_id);
    }
    if (params.event_id) {
      searchParams.set("event_id", params.event_id);
    }
    if (params.media_asset_id) {
      searchParams.set("media_asset_id", params.media_asset_id);
    }
    if (params.suggested_label) {
      searchParams.set("suggested_label", params.suggested_label);
    }
    const query = searchParams.toString();
    return request<SpeciesSuggestionListResponse>(
      `/api/species-suggestions${query ? `?${query}` : ""}`,
    );
  },
  getSpeciesSuggestion: (id: string) =>
    request<SpeciesSuggestion>(`/api/species-suggestions/${encodeURIComponent(id)}`),
  createSpeciesSuggestion: (payload: SpeciesSuggestionCreateRequest) =>
    request<SpeciesSuggestion>("/api/species-suggestions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createMockSpeciesSuggestion: (payload: MockSpeciesSuggestionRequest) =>
    request<SpeciesSuggestion>("/api/species-suggestions/mock", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateSpeciesSuggestionStatus: (id: string, status: SpeciesSuggestionStatus) =>
    request<SpeciesSuggestion>(`/api/species-suggestions/${encodeURIComponent(id)}/status`, {
      method: "POST",
      body: JSON.stringify({ status } satisfies SpeciesSuggestionStatusUpdateRequest),
    }),
  createZone: (payload: ZoneCreate) =>
    request<ZoneMutationResult>("/api/zones", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateZone: (zoneId: string, payload: ZoneUpdate) =>
    request<ZoneMutationResult>(`/api/zones/${zoneId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getZoneMonitoringPolicy: (zoneId: string) =>
    request<ZoneMonitoringPolicy>(
      `/api/zones/${encodeURIComponent(zoneId)}/monitoring-policy`,
    ),
  updateZoneMonitoringPolicy: (zoneId: string, payload: ZoneMonitoringPolicyUpdate) =>
    request<ZoneMonitoringPolicy>(
      `/api/zones/${encodeURIComponent(zoneId)}/monitoring-policy`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    ),
  restoreZoneMonitoringPolicyDefaults: (zoneId: string) =>
    request<ZoneMonitoringPolicy>(
      `/api/zones/${encodeURIComponent(zoneId)}/monitoring-policy/restore-defaults`,
      { method: "POST" },
    ),
  deleteZone: (zoneId: string) =>
    request<ZoneMutationResult>(`/api/zones/${zoneId}`, {
      method: "DELETE",
    }),
  getReviewQueue: () => request<ReviewQueueItem[]>("/api/review-queue"),
  getReviewLabels: () => request<ReviewLabel[]>("/api/review-labels"),
  searchActivityLibrary: (payload: ActivityLibrarySearchRequest) =>
    request<ActivityLibrarySearchResponse>("/api/activity-library/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getActivityLibrarySavedViews: () =>
    request<ActivityLibrarySavedView[]>("/api/activity-library/saved-views"),
  createActivityLibrarySavedView: (payload: ActivityLibrarySavedViewCreate) =>
    request<ActivityLibrarySavedView>("/api/activity-library/saved-views", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateActivityLibrarySavedView: (viewId: string, payload: ActivityLibrarySavedViewUpdate) =>
    request<ActivityLibrarySavedView>(
      `/api/activity-library/saved-views/${encodeURIComponent(viewId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    ),
  deleteActivityLibrarySavedView: (viewId: string) =>
    request<void>(`/api/activity-library/saved-views/${encodeURIComponent(viewId)}`, {
      method: "DELETE",
    }),
  createActivityLibraryExportSelection: (payload: ActivityLibraryExportSelectionRequest) =>
    request<ActivityLibraryExportSelectionResponse>("/api/activity-library/export-selection", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDatasetExports: () => request<DatasetExport[]>("/api/dataset-exports"),
  getDatasetExport: (exportId: string) =>
    request<DatasetExportDetail>(`/api/dataset-exports/${exportId}`),
  getDatasetExportManifest: (exportId: string) =>
    request<DatasetExportManifest>(`/api/dataset-exports/${exportId}/manifest`),
  createDatasetExport: (payload: DatasetExportCreate) =>
    request<DatasetExportDetail>("/api/dataset-exports", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDatasetCoverageSummary: () =>
    request<DatasetCoverageSummary>("/api/dataset-coverage/summary"),
  getDatasetQualitySummary: () =>
    request<DatasetQualitySummary>("/api/dataset-quality/summary"),
  getAnalyticsSummary: () => request<AnalyticsSummary>("/api/analytics/summary"),
  getLocalDataStatus: () => request<LocalDataStatus>("/api/settings/local-data"),
  getStorageRetentionSummary: () =>
    request<StorageSummary>("/api/settings/storage-retention/summary"),
  getStorageRetentionSettings: () =>
    request<StorageRetentionSettings>("/api/settings/storage-retention"),
  updateStorageRetentionSettings: (payload: StorageRetentionSettingsUpdate) =>
    request<StorageRetentionSettings>("/api/settings/storage-retention", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  previewStorageRetentionCleanup: () =>
    request<StorageCleanupPreviewResponse>("/api/settings/storage-retention/cleanup-preview", {
      method: "POST",
    }),
  executeStorageRetentionCleanup: (payload: {
    preview_token: string;
    confirm: boolean;
    idempotency_key: string;
  }) =>
    request<StorageCleanupResult>("/api/settings/storage-retention/cleanup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getStorageRetentionCleanupHistory: () =>
    request<StorageCleanupHistoryResponse>("/api/settings/storage-retention/cleanup-history"),
  restoreStorageRetentionCleanup: (batchId: string, idempotencyKey: string) =>
    request<StorageCleanupResult>(
      `/api/settings/storage-retention/cleanup-history/${encodeURIComponent(batchId)}/restore`,
      { method: "POST", body: JSON.stringify({ idempotency_key: idempotencyKey }) },
    ),
  purgeStorageRetentionCleanup: (batchId: string, idempotencyKey: string) =>
    request<StorageCleanupResult>(
      `/api/settings/storage-retention/cleanup-history/${encodeURIComponent(batchId)}/purge`,
      {
        method: "POST",
        body: JSON.stringify({ confirm: true, idempotency_key: idempotencyKey }),
      },
    ),
  getLocalBackups: () => request<LocalBackupLibraryResponse>("/api/settings/backups"),
  createLocalBackup: () =>
    request<LocalBackupVerificationResponse>("/api/settings/backups", {
      method: "POST",
    }),
  importLocalBackup: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<LocalBackupVerificationResponse>("/api/settings/backups/import", {
      method: "POST",
      body: form,
    });
  },
  verifyLocalBackup: (backupId: string) =>
    request<LocalBackupVerificationResponse>(
      `/api/settings/backups/${encodeURIComponent(backupId)}/verify`,
      { method: "POST" },
    ),
  restoreLocalBackup: (backupId: string) =>
    request<LocalBackupRestoreResponse>(
      `/api/settings/backups/${encodeURIComponent(backupId)}/restore`,
      {
        method: "POST",
        body: JSON.stringify({ confirm: true }),
      },
    ),
  localBackupDownloadUrl: (backupId: string) =>
    `${API_BASE_URL}/api/settings/backups/${encodeURIComponent(backupId)}/download`,
  resetDemoData: () =>
    request<LocalDataStatus>("/api/settings/reset-demo-data", {
      method: "POST",
    }),
  removeSampleData: () =>
    request<SampleDataRemovalResponse>("/api/settings/remove-sample-data", {
      method: "POST",
      body: JSON.stringify({ confirm: true }),
    }),
  createReviewLabel: (payload: ReviewCorrectionCreate) =>
    request<ReviewCorrectionResult>("/api/review-labels", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getVisitReviewHistory: (visitId: string) =>
    request<VisitReviewHistory>(
      `/api/visits/${encodeURIComponent(visitId)}/correction-history`,
    ),
  reviseVisitReview: (visitId: string, payload: VisitReviewRevisionCreate) =>
    request<VisitReviewRevisionResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/revision`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  reopenVisitReview: (visitId: string, payload: VisitReviewReopenCreate) =>
    request<VisitReviewReopenResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/reopen`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  navigateFastReviewQueue: (payload: FastReviewQueueNavigationRequest) =>
    request<FastReviewQueueNavigationResponse>("/api/review-queue/fast/navigate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createFastReviewCorrection: (payload: FastReviewCorrectionCreate) =>
    request<FastReviewCorrectionResponse>("/api/review-queue/fast/correct", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  undoFastReviewCorrection: (payload: FastReviewUndoRequest) =>
    request<FastReviewUndoResponse>("/api/review-queue/fast/undo", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  identifyReviewQueueItem: (
    targetType: "event" | "visit",
    targetId: string,
    payload: ReviewIdentificationRequest = {},
  ) =>
    request<ReviewIdentificationResponse>(
      `/api/review-queue/${encodeURIComponent(targetType)}/${encodeURIComponent(targetId)}/identify`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  bulkCorrectReviewQueueItems: (payload: ReviewQueueBulkCorrectionRequest) =>
    request<ReviewQueueBulkCorrectionResponse>("/api/review-queue/bulk-correct", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
