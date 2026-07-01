import type {
  AnalyticsSummary,
  CameraSource,
  DatasetExport,
  DatasetExportCreate,
  DatasetExportDetail,
  DatasetExportManifest,
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
  ReviewCorrectionCreate,
  ReviewCorrectionResult,
  ReviewQueueItem,
  Stream,
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
