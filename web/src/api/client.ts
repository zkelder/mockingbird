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
  CameraHealthDetailResponse,
  CameraHealthIncidentListResponse,
  CameraHealthListResponse,
  CameraConfigurationApplyRequest,
  CameraConfigurationApplyResponse,
  CameraConfigurationEditResponse,
  CameraConfigurationHistoryResponse,
  CameraConfigurationImpactPreview,
  CameraConfigurationImpactPreviewRequest,
  CameraNodePairRequest,
  CameraNodePairResponse,
  CameraNodePendingSetupDraftUpdate,
  CameraNodePendingSetupResponse,
  CameraNodePendingSetupRevokeRequest,
  CameraNodePreviewRequest,
  CameraNodePairRevokeRequest,
  CameraSetupCompleteRequest,
  CameraSetupCompletionResponse,
  CameraSetupOptionsResponse,
  CameraSetupValidationRequest,
  CameraSetupValidationResponse,
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
  ObservationSessionStatus,
  LivePreviewLeaseRequest,
  LivePreviewLeaseResponse,
  LivePreviewReleaseResponse,
  LocalBackupLibraryResponse,
  LocalBackupRestoreResponse,
  LocalBackupVerificationResponse,
  LocalDataStatus,
  OnvifDiscoverProfilesRequest,
  OnvifDiscoverProfilesResponse,
  PlaceActivityReportRequest,
  PlaceActivityReportResponse,
  ProductHealthStatus,
  SetupState,
  SetupStateUpdate,
  SoundscapeSummaryRequest,
  SoundscapeSummaryResponse,
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
  LikelySpeciesOverviewResponse,
  MotionEvidenceStatus,
  MotionEvaluateSavedMediaRequest,
  MotionEvaluateSavedMediaResponse,
  MotionEvaluateSequenceRequest,
  MotionEvaluateSequenceResponse,
  ReviewCorrectionCreate,
  ReviewCorrectionResult,
  VisitEvidenceCurationRequest,
  VisitEvidenceCurationResponse,
  RefinedCropCreateRequest,
  RefinedCropResponse,
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
  VisitIdentificationAssistantRequest,
  VisitIdentificationAssistantResponse,
  FastReviewCorrectionCreate,
  FastReviewCorrectionResponse,
  FastReviewQueueNavigationRequest,
  FastReviewQueueNavigationResponse,
  FastReviewUndoRequest,
  FastReviewUndoResponse,
  ReviewIdentificationRequest,
  ReviewIdentificationResponse,
  ReviewLabel,
  ProductAlertListResponse,
  ProductAlertUnreadResponse,
  AlertCategory,
  ReviewQueueBulkCorrectionRequest,
  ReviewQueueBulkCorrectionResponse,
  ReviewQueueItem,
  ReviewQueueSpeciesSuggestionBatchPrepareRequest,
  ReviewQueueSpeciesSuggestionBatchPrepareResponse,
  AcousticAnalysisRun,
  AudioCaptureStatusResponse,
  BirdNetStatusResponse,
  RecordedAudioAnalysisRequest,
  RecordedAudioAnalysisResponse,
  RecordedMediaAnalysisRequest,
  RecordedMediaAnalysisResponse,
  RecordedMediaAnalysisRun,
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
  SpeciesCandidatePack,
  SpeciesCandidatePackCloneRequest,
  SpeciesCandidatePackCreate,
  SpeciesCandidatePackUpdate,
  SourceConnectionStatus,
  SourceMonitorStartRequest,
  SourceMonitorStatusResponse,
  SourceProviderConfiguration,
  SourceProviderConfigurationUpdate,
  SourceProviderDefinition,
  SourceSetupReviewResponse,
  Stream,
  StreamSpeciesCandidatePackSelection,
  StreamSpeciesCandidatePackSelectionUpdate,
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
  VisitOrganizationState,
  VisitOrganizationUpdate,
  VisitOrganizationBulkRequest,
  VisitOrganizationBulkResponse,
  VisitCollectionArchiveRequest,
  VisitCollectionBulkRequest,
  VisitCollectionBulkResponse,
  VisitCollectionCreate,
  VisitCollectionMembershipRequest,
  VisitCollectionMembershipResponse,
  VisitCollectionSummary,
  VisitCollectionUpdate,
  VisitCollectionsForVisitResponse,
  VisitTagArchiveRequest, VisitTagBulkRequest, VisitTagBulkResponse, VisitTagCreate, VisitTagMembershipRequest, VisitTagMembershipResponse, VisitTagSummary, VisitTagUpdate, VisitTagsForVisitResponse,
  YardMapBackgroundDelete, YardMapBlankCreate, YardMapPlacementDelete, YardMapRange, YardMapResponse, YardMapSettingsUpdate, YardMapStreamPlacementUpdate, YardMapZonePlacementUpdate,
  WorkerStatusResponse,
    WildlifeInsightsRequest,
    WildlifeInsightsSummary,
    ZoneInsightsRequest,
    ZoneInsightsSummary,
    WildlifeJournalHistoryRequest,
    WildlifeJournalHistoryResponse,
    WildlifeJournalOrder,
    WildlifeJournalOverviewResponse,
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

async function requestImage(path: string, payload: CameraNodePreviewRequest): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? detail;
    } catch {
      // The status text is safe fallback context for a non-JSON response.
    }
    throw new ApiError(detail, response.status);
  }
  if (!response.headers.get("content-type")?.startsWith("image/jpeg")) {
    throw new ApiError("Camera Node did not provide a JPEG preview.", 502);
  }
  return response.blob();
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
  listSpeciesCandidatePacks: (includeArchived = true) =>
    request<SpeciesCandidatePack[]>(
      `/api/species-candidate-packs?include_archived=${String(includeArchived)}`,
    ),
  getSpeciesCandidatePack: (packId: string) =>
    request<SpeciesCandidatePack>(
      `/api/species-candidate-packs/${encodeURIComponent(packId)}`,
    ),
  createSpeciesCandidatePack: (payload: SpeciesCandidatePackCreate) =>
    request<SpeciesCandidatePack>("/api/species-candidate-packs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cloneSpeciesCandidatePack: (
    packId: string,
    payload: SpeciesCandidatePackCloneRequest = {},
  ) =>
    request<SpeciesCandidatePack>(
      `/api/species-candidate-packs/${encodeURIComponent(packId)}/clone`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  updateSpeciesCandidatePack: (packId: string, payload: SpeciesCandidatePackUpdate) =>
    request<SpeciesCandidatePack>(
      `/api/species-candidate-packs/${encodeURIComponent(packId)}`,
      { method: "PUT", body: JSON.stringify(payload) },
    ),
  archiveSpeciesCandidatePack: (packId: string) =>
    request<SpeciesCandidatePack>(
      `/api/species-candidate-packs/${encodeURIComponent(packId)}/archive`,
      { method: "POST" },
    ),
  getSources: () => request<CameraSource[]>("/api/sources"),
  getCameraSetupOptions: () => request<CameraSetupOptionsResponse>("/api/camera-setup/options"),
  pairCameraNode: (payload: CameraNodePairRequest) =>
    request<CameraNodePairResponse>("/api/camera-nodes/pair", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  previewCameraNode: (payload: CameraNodePreviewRequest) =>
    requestImage("/api/camera-nodes/preview", payload),
  getCameraNodePendingSetup: () =>
    request<CameraNodePendingSetupResponse>("/api/camera-nodes/pending-setup"),
  updateCameraNodePendingSetup: (
    pairingToken: string,
    payload: CameraNodePendingSetupDraftUpdate,
  ) =>
    request<CameraNodePendingSetupResponse>(
      `/api/camera-nodes/pending-setup/${encodeURIComponent(pairingToken)}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    ),
  revokeCameraNodePendingSetup: (payload: CameraNodePendingSetupRevokeRequest) =>
    request<void>("/api/camera-nodes/pending-setup/revoke", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  revokeCameraNodePairing: (payload: CameraNodePairRevokeRequest) =>
    request<void>("/api/camera-nodes/pair/revoke", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  validateCameraSetup: (payload: CameraSetupValidationRequest) =>
    request<CameraSetupValidationResponse>("/api/camera-setup/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  completeCameraSetup: (payload: CameraSetupCompleteRequest) =>
    request<CameraSetupCompletionResponse>("/api/camera-setup/complete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF"):
  // stateless -- no source_id, nothing persisted.
  discoverOnvifProfiles: (payload: OnvifDiscoverProfilesRequest) =>
    request<OnvifDiscoverProfilesResponse>("/api/onvif/discover-profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getCameraConfiguration: (streamId: string) =>
    request<CameraConfigurationEditResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-configuration`,
    ),
  getCameraConfigurationPendingPairing: (streamId: string) =>
    request<CameraNodePendingSetupResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-configuration/pending-pairing`,
    ),
  previewCameraConfiguration: (
    streamId: string,
    payload: CameraConfigurationImpactPreviewRequest,
  ) =>
    request<CameraConfigurationImpactPreview>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-configuration/preview`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  applyCameraConfiguration: (
    streamId: string,
    payload: CameraConfigurationApplyRequest,
  ) =>
    request<CameraConfigurationApplyResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-configuration/apply`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  getCameraConfigurationHistory: (streamId: string, limit = 20) =>
    request<CameraConfigurationHistoryResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-configuration/history?limit=${limit}`,
    ),
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
  getDashboardSummary: (localDate?: string) =>
    request<DashboardSummary>(
      localDate
        ? `/api/dashboard/summary?local_date=${encodeURIComponent(localDate)}`
        : "/api/dashboard/summary",
    ),
  getYardMap: (range: YardMapRange = "today") => request<YardMapResponse>(`/api/yard-map?range=${encodeURIComponent(range)}`),
  createBlankYardMap: (payload: YardMapBlankCreate) => request<YardMapResponse>("/api/yard-map/blank", { method: "POST", body: JSON.stringify(payload) }),
  updateYardMapSettings: (payload: YardMapSettingsUpdate) => request<YardMapResponse>("/api/yard-map", { method: "PATCH", body: JSON.stringify(payload) }),
  uploadYardMapBackground: (file: File, expectedStateToken: string | null, idempotencyKey: string) => {
    const form = new FormData(); form.append("file", file); if (expectedStateToken) form.append("expected_state_token", expectedStateToken); form.append("idempotency_key", idempotencyKey);
    return request<YardMapResponse>("/api/yard-map/background", { method: "POST", body: form });
  },
  removeYardMapBackground: (payload: YardMapBackgroundDelete) => request<YardMapResponse>("/api/yard-map/background", { method: "DELETE", body: JSON.stringify(payload) }),
  updateYardMapStreamPlacement: (streamId: string, payload: YardMapStreamPlacementUpdate) => request<YardMapResponse>(`/api/yard-map/streams/${encodeURIComponent(streamId)}`, { method: "PUT", body: JSON.stringify(payload) }),
  removeYardMapStreamPlacement: (streamId: string, payload: YardMapPlacementDelete) => request<YardMapResponse>(`/api/yard-map/streams/${encodeURIComponent(streamId)}`, { method: "DELETE", body: JSON.stringify(payload) }),
  updateYardMapZonePlacement: (zoneId: string, payload: YardMapZonePlacementUpdate) => request<YardMapResponse>(`/api/yard-map/zones/${encodeURIComponent(zoneId)}`, { method: "PUT", body: JSON.stringify(payload) }),
  removeYardMapZonePlacement: (zoneId: string, payload: YardMapPlacementDelete) => request<YardMapResponse>(`/api/yard-map/zones/${encodeURIComponent(zoneId)}`, { method: "DELETE", body: JSON.stringify(payload) }),
  getStreams: () => request<Stream[]>("/api/streams"),
  getStreamMonitoringStatuses: (limit = 50) =>
    request<StreamMonitoringStatusListResponse>(
      `/api/streams/monitoring-status?limit=${encodeURIComponent(String(limit))}`,
    ),
  getCameraHealth: (limit = 50) =>
    request<CameraHealthListResponse>(
      `/api/camera-health?limit=${encodeURIComponent(String(limit))}`,
    ),
  getZones: () => request<Zone[]>("/api/zones"),
  getStream: (streamId: string) => request<Stream>(`/api/streams/${streamId}`),
  getStreamSpeciesCandidatePackSelection: (streamId: string) =>
    request<StreamSpeciesCandidatePackSelection>(
      `/api/streams/${encodeURIComponent(streamId)}/species-candidate-pack`,
    ),
  setStreamSpeciesCandidatePackSelection: (
    streamId: string,
    payload: StreamSpeciesCandidatePackSelectionUpdate,
  ) =>
    request<StreamSpeciesCandidatePackSelection>(
      `/api/streams/${encodeURIComponent(streamId)}/species-candidate-pack`,
      { method: "PUT", body: JSON.stringify(payload) },
    ),
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
  getStreamCameraHealth: (streamId: string) =>
    request<CameraHealthDetailResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-health`,
    ),
  getStreamCameraHealthIncidents: (streamId: string, limit = 20) =>
    request<CameraHealthIncidentListResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/camera-health/incidents?limit=${encodeURIComponent(String(limit))}`,
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
  startStreamObservation: (streamId: string) =>
    request<ObservationSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/observation/start`,
      { method: "POST" },
    ),
  stopStreamObservation: (streamId: string) =>
    request<ObservationSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/observation/stop`,
      { method: "POST" },
    ),
  getStreamObservationStatus: (streamId: string) =>
    request<ObservationSessionStatus>(
      `/api/streams/${encodeURIComponent(streamId)}/observation/status`,
    ),
  liveCameraCurrentFrameUrl: (streamId: string) =>
    `${API_BASE_URL}/api/streams/${encodeURIComponent(streamId)}/live-session/current-frame`,
  openLiveOverviewPreview: (streamId: string, payload: LivePreviewLeaseRequest) =>
    request<LivePreviewLeaseResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/live-preview/open`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  closeLiveOverviewPreview: (streamId: string, payload: LivePreviewLeaseRequest) =>
    request<LivePreviewReleaseResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/live-preview/close`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
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
  getVisitOrganization: (visitId: string) => request<VisitOrganizationState>(`/api/visits/${encodeURIComponent(visitId)}/organization`),
  updateVisitOrganization: (visitId: string, payload: VisitOrganizationUpdate) =>
    request<VisitOrganizationState>(`/api/visits/${encodeURIComponent(visitId)}/organization`, { method: "PUT", body: JSON.stringify(payload) }),
  bulkUpdateVisitOrganization: (payload: VisitOrganizationBulkRequest) =>
    request<VisitOrganizationBulkResponse>("/api/visit-organization/bulk", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getVisitCollections: () => request<VisitCollectionSummary[]>("/api/collections"),
  createVisitCollection: (payload: VisitCollectionCreate) =>
    request<VisitCollectionSummary>("/api/collections", { method: "POST", body: JSON.stringify(payload) }),
  getVisitCollection: (collectionId: string) =>
    request<VisitCollectionSummary>(`/api/collections/${encodeURIComponent(collectionId)}`),
  updateVisitCollection: (collectionId: string, payload: VisitCollectionUpdate) =>
    request<VisitCollectionSummary>(`/api/collections/${encodeURIComponent(collectionId)}`, { method: "PATCH", body: JSON.stringify(payload) }),
  archiveVisitCollection: (collectionId: string, payload: VisitCollectionArchiveRequest) =>
    request<VisitCollectionSummary>(`/api/collections/${encodeURIComponent(collectionId)}/archive`, { method: "POST", body: JSON.stringify(payload) }),
  searchVisitCollection: (collectionId: string, payload: ActivityLibrarySearchRequest) =>
    request<ActivityLibrarySearchResponse>(`/api/collections/${encodeURIComponent(collectionId)}/visits/search`, { method: "POST", body: JSON.stringify(payload) }),
  getCollectionsForVisit: (visitId: string) =>
    request<VisitCollectionsForVisitResponse>(`/api/visits/${encodeURIComponent(visitId)}/collections`),
  addVisitToCollection: (collectionId: string, visitId: string, payload: VisitCollectionMembershipRequest) =>
    request<VisitCollectionMembershipResponse>(`/api/collections/${encodeURIComponent(collectionId)}/visits/${encodeURIComponent(visitId)}`, { method: "POST", body: JSON.stringify(payload) }),
  removeVisitFromCollection: (collectionId: string, visitId: string, payload: VisitCollectionMembershipRequest) =>
    request<VisitCollectionMembershipResponse>(`/api/collections/${encodeURIComponent(collectionId)}/visits/${encodeURIComponent(visitId)}`, { method: "DELETE", body: JSON.stringify(payload) }),
  bulkUpdateVisitCollectionMemberships: (payload: VisitCollectionBulkRequest) =>
    request<VisitCollectionBulkResponse>("/api/collections/memberships/bulk", { method: "POST", body: JSON.stringify(payload) }),
  getVisitTags: () => request<VisitTagSummary[]>("/api/tags"),
  getManageableVisitTags: () => request<VisitTagSummary[]>("/api/tags/manage"),
  createVisitTag: (payload: VisitTagCreate) => request<VisitTagSummary>("/api/tags", { method: "POST", body: JSON.stringify(payload) }),
  updateVisitTag: (tagId: string, payload: VisitTagUpdate) => request<VisitTagSummary>(`/api/tags/${encodeURIComponent(tagId)}`, { method: "PATCH", body: JSON.stringify(payload) }),
  archiveVisitTag: (tagId: string, payload: VisitTagArchiveRequest) => request<VisitTagSummary>(`/api/tags/${encodeURIComponent(tagId)}/archive`, { method: "POST", body: JSON.stringify(payload) }),
  getTagsForVisit: (visitId: string) => request<VisitTagsForVisitResponse>(`/api/visits/${encodeURIComponent(visitId)}/tags`),
  addVisitTag: (tagId: string, visitId: string, payload: VisitTagMembershipRequest) => request<VisitTagMembershipResponse>(`/api/tags/${encodeURIComponent(tagId)}/visits/${encodeURIComponent(visitId)}`, { method: "POST", body: JSON.stringify(payload) }),
  removeVisitTag: (tagId: string, visitId: string, payload: VisitTagMembershipRequest) => request<VisitTagMembershipResponse>(`/api/tags/${encodeURIComponent(tagId)}/visits/${encodeURIComponent(visitId)}`, { method: "DELETE", body: JSON.stringify(payload) }),
  bulkUpdateVisitTags: (payload: VisitTagBulkRequest) => request<VisitTagBulkResponse>("/api/tags/memberships/bulk", { method: "POST", body: JSON.stringify(payload) }),
  getVisitIdentificationAssistant: (visitId: string) =>
    request<VisitIdentificationAssistantResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/identification-assistant`,
    ),
  startVisitIdentificationAssistant: (
    visitId: string,
    payload: VisitIdentificationAssistantRequest,
  ) =>
    request<VisitIdentificationAssistantResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/identification-assistant`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  curateVisitEvidence: (visitId: string, payload: VisitEvidenceCurationRequest) =>
    request<VisitEvidenceCurationResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/evidence-curation`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  createRefinedVisitCrop: (visitId: string, payload: RefinedCropCreateRequest) =>
    request<RefinedCropResponse>(`/api/visits/${encodeURIComponent(visitId)}/refined-crop`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  promoteVisitCropHistory: (visitId: string, mediaAssetId: string) =>
    request<RefinedCropResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/crop-history/${encodeURIComponent(mediaAssetId)}/promote`,
      { method: "POST" },
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
  analyzeRecordedMedia: (mediaId: string, payload: RecordedMediaAnalysisRequest = {}) =>
    request<RecordedMediaAnalysisResponse>(
      `/api/media/${encodeURIComponent(mediaId)}/analyze-recorded`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  getRecordedMediaAnalysisRuns: (mediaId: string) =>
    request<RecordedMediaAnalysisRun[]>(
      `/api/media/${encodeURIComponent(mediaId)}/analysis-runs`,
    ),
  // Acoustic / BirdNET Observation Foundation v1: mirrors the recorded-
  // video analysis client methods immediately above.
  analyzeRecordedAudio: (mediaId: string, payload: RecordedAudioAnalysisRequest = {}) =>
    request<RecordedAudioAnalysisResponse>(
      `/api/media/${encodeURIComponent(mediaId)}/analyze-audio`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  getAcousticAnalysisRuns: (mediaId: string) =>
    request<AcousticAnalysisRun[]>(
      `/api/media/${encodeURIComponent(mediaId)}/audio-analysis-runs`,
    ),
  getBirdNetStatus: () => request<BirdNetStatusResponse>("/api/birdnet/status"),
  startMicrophoneCapture: (streamId: string) =>
    request<AudioCaptureStatusResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/audio-capture/start`,
      { method: "POST" },
    ),
  stopMicrophoneCapture: (streamId: string) =>
    request<AudioCaptureStatusResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/audio-capture/stop`,
      { method: "POST" },
    ),
  getMicrophoneCaptureStatus: (streamId: string) =>
    request<AudioCaptureStatusResponse>(
      `/api/streams/${encodeURIComponent(streamId)}/audio-capture/status`,
    ),
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
  getReviewQueue: (options: { includeReviewed?: boolean } = {}) =>
    request<ReviewQueueItem[]>(
      `/api/review-queue${options.includeReviewed ? "?include_reviewed=true" : ""}`,
    ),
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
  getWildlifeInsights: (payload: WildlifeInsightsRequest) =>
    request<WildlifeInsightsSummary>("/api/analytics/wildlife-insights", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getZoneInsights: (payload: ZoneInsightsRequest) =>
    request<ZoneInsightsSummary>("/api/analytics/zone-insights", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getPlaceActivityReport: (payload: PlaceActivityReportRequest) =>
    request<PlaceActivityReportResponse>("/api/analytics/place-activity-report", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSoundscapeSummary: (payload: SoundscapeSummaryRequest) =>
    request<SoundscapeSummaryResponse>("/api/analytics/soundscape-summary", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getWildlifeJournal: (order: WildlifeJournalOrder = "most_recent") =>
    request<WildlifeJournalOverviewResponse>(
      `/api/bird-log/journal?${new URLSearchParams({ order }).toString()}`,
    ),
  getLikelySpeciesOverview: () =>
    request<LikelySpeciesOverviewResponse>("/api/bird-log/likely"),
  getWildlifeJournalHistory: (label: string, params: WildlifeJournalHistoryRequest = {}) => {
    const searchParams = new URLSearchParams();
    if (params.preset) searchParams.set("preset", params.preset);
    if (params.start_date) searchParams.set("start_date", params.start_date);
    if (params.end_date) searchParams.set("end_date", params.end_date);
    if (params.stream_id) searchParams.set("stream_id", params.stream_id);
    if (params.zone_id) searchParams.set("zone_id", params.zone_id);
    if (params.favorites_only) searchParams.set("favorites_only", "true");
    if (params.tag_id) searchParams.set("tag_id", params.tag_id);
    if (params.gallery_order) searchParams.set("gallery_order", params.gallery_order);
    if (params.page_size) searchParams.set("page_size", String(params.page_size));
    if (params.offset) searchParams.set("offset", String(params.offset));
    const query = searchParams.toString();
    return request<WildlifeJournalHistoryResponse>(
      `/api/bird-log/journal/${encodeURIComponent(label)}${query ? `?${query}` : ""}`,
    );
  },
  getLocalDataStatus: () => request<LocalDataStatus>("/api/settings/local-data"),
  getSetupState: () => request<SetupState>("/api/setup/state"),
  updateSetupState: (payload: SetupStateUpdate) =>
    request<SetupState>("/api/setup/state", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  getProductHealth: () => request<ProductHealthStatus>("/api/product/health"),
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
  // Review Decision Provenance / Truth Boundary v1 (see
  // docs/review-decision-provenance-contract.md): every one of these
  // functions is only ever reachable from this product's own interactive
  // browser UI (Review Queue, Fast Review, Visit Detail correction/
  // revision/reopen, bulk correction) -- a real person clicked something to
  // reach this call. Each one explicitly stamps `review_origin: "human"`
  // here, at this one client boundary, rather than leaving it to every
  // page component to remember. This is an explicit assertion by the
  // product's own review UI, not a default the backend applies for a
  // caller that omits the field -- any other HTTP caller (a script, a
  // future automation, an LLM agent) that calls the underlying API
  // directly gets no such stamp and is never treated as human.
  createReviewLabel: (payload: ReviewCorrectionCreate) =>
    request<ReviewCorrectionResult>("/api/review-labels", {
      method: "POST",
      body: JSON.stringify({ ...payload, review_origin: "human" }),
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
        body: JSON.stringify({ ...payload, review_origin: "human" }),
      },
    ),
  reopenVisitReview: (visitId: string, payload: VisitReviewReopenCreate) =>
    request<VisitReviewReopenResponse>(
      `/api/visits/${encodeURIComponent(visitId)}/reopen`,
      {
        method: "POST",
        body: JSON.stringify({ ...payload, review_origin: "human" }),
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
      body: JSON.stringify({ ...payload, review_origin: "human" }),
    }),
  undoFastReviewCorrection: (payload: FastReviewUndoRequest) =>
    request<FastReviewUndoResponse>("/api/review-queue/fast/undo", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  prepareReviewQueueSpeciesSuggestionBatch: (
    payload: ReviewQueueSpeciesSuggestionBatchPrepareRequest,
  ) =>
    request<ReviewQueueSpeciesSuggestionBatchPrepareResponse>(
      "/api/review-queue/species-suggestions/prepare",
      { method: "POST", body: JSON.stringify(payload) },
    ),
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
      body: JSON.stringify({ ...payload, review_origin: "human" }),
    }),
  getAlertUnread: () => request<ProductAlertUnreadResponse>("/api/alerts/unread"),
  getAlerts: (category?: AlertCategory, offset = 0) => {
    const params = new URLSearchParams({ page_size: "30", offset: String(offset) });
    if (category) params.set("category", category);
    return request<ProductAlertListResponse>(`/api/alerts?${params.toString()}`);
  },
  markAlertRead: (alertId: string) =>
    request<ProductAlertUnreadResponse>(`/api/alerts/${encodeURIComponent(alertId)}/read`, { method: "POST" }),
  markVisibleAlertsRead: (alertIds: string[]) =>
    request<ProductAlertUnreadResponse>("/api/alerts/read-visible", {
      method: "POST", body: JSON.stringify({ alert_ids: alertIds.slice(0, 50) }),
    }),
  dismissAlert: (alertId: string) =>
    request<ProductAlertUnreadResponse>(`/api/alerts/${encodeURIComponent(alertId)}/dismiss`, { method: "POST" }),
};
