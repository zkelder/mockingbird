import type {
  AdapterEvaluationSummary,
  AnalyticsSummary,
  CameraSource,
  CameraSourceCreateRequest,
  CameraSourceCreateResponse,
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
  LocalDataStatus,
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
  StreamPlaybackStatus,
  TaxonomyLabel,
  Visit,
  VisitDetail,
  WorkerStatusResponse,
  WindowsCameraDiscoveryResponse,
  Zone,
  ZoneCreate,
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
  getStreams: () => request<Stream[]>("/api/streams"),
  getStream: (streamId: string) => request<Stream>(`/api/streams/${streamId}`),
  getStreamPlaybackStatus: (streamId: string) =>
    request<StreamPlaybackStatus>(`/api/streams/${streamId}/playback`),
  rtspMjpegBridgeUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live/rtsp-mjpeg`,
  localCameraMjpegBridgeUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live/local-mjpeg`,
  windowsDshowMjpegBridgeUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live/windows-dshow-mjpeg`,
  discoverWindowsCameras: () =>
    request<WindowsCameraDiscoveryResponse>("/api/local-cameras/windows"),
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
  getEventVisits: (eventId: string) => request<Visit[]>(`/api/events/${eventId}/visits`),
  getEventDetail: (eventId: string) => request<EventDetail>(`/api/events/${eventId}/detail`),
  getVisitDetail: (visitId: string) => request<VisitDetail>(`/api/visits/${visitId}/detail`),
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
  getReviewQueue: () => request<ReviewQueueItem[]>("/api/review-queue"),
  getReviewLabels: () => request<ReviewLabel[]>("/api/review-labels"),
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
  resetDemoData: () =>
    request<LocalDataStatus>("/api/settings/reset-demo-data", {
      method: "POST",
    }),
  createReviewLabel: (payload: ReviewCorrectionCreate) =>
    request<ReviewCorrectionResult>("/api/review-labels", {
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
