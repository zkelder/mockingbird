import type {
  AdapterEvaluationSummary,
  AnalyticsSummary,
  CameraSource,
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
  FolderImportCreate,
  FolderImportPreview,
  FolderImportPreviewRequest,
  FolderImportResult,
  HealthStatus,
  LocalDataStatus,
  MediaAsset,
  MediaImportResult,
  ModelAdapter,
  ModelReadinessSummary,
  ModelAdapterRunRequest,
  ModelAdapterRunResult,
  MotionEvidence,
  MotionEvidenceAttachMediaRequest,
  MotionEvidenceCreateRequest,
  MotionEvidenceListResponse,
  MotionEvidencePromoteRequest,
  MotionEvidencePromoteResponse,
  MotionEvidenceStatus,
  MotionEvaluateSequenceRequest,
  MotionEvaluateSequenceResponse,
  ReviewCorrectionCreate,
  ReviewCorrectionResult,
  ReviewQueueItem,
  Stream,
  TaxonomyLabel,
  Visit,
  VisitDetail,
  Zone,
  ZoneCreate,
  ZoneMutationResult,
  ZoneUpdate,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

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
  getStreams: () => request<Stream[]>("/api/streams"),
  getStream: (streamId: string) => request<Stream>(`/api/streams/${streamId}`),
  getStreamZones: (streamId: string) => request<Zone[]>(`/api/streams/${streamId}/zones`),
  getStreamEvents: (streamId: string) => request<Event[]>(`/api/streams/${streamId}/events`),
  getEventVisits: (eventId: string) => request<Visit[]>(`/api/events/${eventId}/visits`),
  getEventDetail: (eventId: string) => request<EventDetail>(`/api/events/${eventId}/detail`),
  getVisitDetail: (visitId: string) => request<VisitDetail>(`/api/visits/${visitId}/detail`),
  getMediaAssets: () => request<MediaAsset[]>("/api/media"),
  getMediaAsset: (mediaId: string) => request<MediaAsset>(`/api/media/${mediaId}`),
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
  previewFolderImport: (payload: FolderImportPreviewRequest) =>
    request<FolderImportPreview>("/api/media/folder-preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  importFolderMedia: (payload: FolderImportCreate) =>
    request<FolderImportResult>("/api/media/folder-import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
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
};
