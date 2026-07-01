import type {
  AnalyticsSummary,
  CameraSource,
  DatasetExport,
  Event,
  HealthStatus,
  ReviewCorrectionCreate,
  ReviewCorrectionResult,
  ReviewQueueItem,
  Stream,
  Visit,
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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
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
  getAnalyticsSummary: () => request<AnalyticsSummary>("/api/analytics/summary"),
  createReviewLabel: (payload: ReviewCorrectionCreate) =>
    request<ReviewCorrectionResult>("/api/review-labels", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
