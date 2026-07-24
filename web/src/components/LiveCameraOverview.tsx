import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type {
  DashboardStreamSummary,
  DashboardZoneOverlay,
  StreamRuntimeStatus,
} from "../api/types";
import { formatDateTime } from "../utils";
import { EmptyState } from "./EmptyState";
import { StatusPill } from "./StatusPill";

const MAX_BROWSER_PREVIEWS = 4;
const PREVIEW_RENEWAL_MS = 45_000;
const OVERVIEW_OWNER_KEY = "mockingbird-live-overview-owner-v1";

type PreviewState =
  | { state: "connecting"; backend: boolean; message: string }
  | { state: "live"; backend: boolean; mediaUrl: string; mediaKind: "image" | "video" }
  | { state: "limit"; backend: boolean; message: string }
  | { state: "unavailable"; backend: boolean; message: string };

interface LiveCameraOverviewProps {
  streams: DashboardStreamSummary[];
  runtimeByStream: Record<string, StreamRuntimeStatus>;
  onOpenStream: (streamId: string) => void;
  onOpenCameraConfiguration?: (streamId: string) => void;
  onOpenReview: (streamId: string) => void;
  onToggleMonitoring?: (stream: DashboardStreamSummary, runtime: StreamRuntimeStatus) => void;
}

function previewOwnerId(): string {
  const existing = window.sessionStorage.getItem(OVERVIEW_OWNER_KEY);
  if (existing) return existing;
  const generated = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  const ownerId = `overview-${generated.replace(/[^A-Za-z0-9_-]/g, "")}`;
  window.sessionStorage.setItem(OVERVIEW_OWNER_KEY, ownerId);
  return ownerId;
}

function previewUrl(value: string): string {
  return value.startsWith("/") ? `${apiClient.baseUrl}${value}` : value;
}

function polygonPoints(points: DashboardZoneOverlay["polygon"]): string {
  return points.map((point) => `${point.x * 100},${point.y * 100}`).join(" ");
}

function ViewOnlyZoneOverlay({ zones }: { zones: DashboardZoneOverlay[] }) {
  const renderableZones = zones.filter((zone) => zone.polygon.length >= 3);
  if (!renderableZones.length) return null;
  return (
    <svg aria-label="View-only camera Zones" className="camera-overview-zone-overlay" preserveAspectRatio="none" viewBox="0 0 100 100">
      {renderableZones.map((zone) => (
        <polygon
          aria-label={`${zone.name} ${zone.zone_type} Zone`}
          className={`zone-shape zone-${zone.zone_type}${zone.is_active ? "" : " zone-inactive"}`}
          key={zone.id}
          points={polygonPoints(zone.polygon)}
        />
      ))}
    </svg>
  );
}

function LatestActivityFallback({ stream }: { stream: DashboardStreamSummary }) {
  const [mediaUnavailable, setMediaUnavailable] = useState(false);
  const visit = stream.latest_visit;
  if (visit?.primary_evidence && !mediaUnavailable) {
    return (
      <img
        alt={`Latest activity from ${stream.stream_name}`}
        className="camera-overview-media"
        onError={() => setMediaUnavailable(true)}
        src={previewUrl(visit.primary_evidence.preview_url)}
      />
    );
  }
  return (
    <div className="camera-overview-placeholder">
      <strong>{visit ? "Latest activity" : "No activity captured yet"}</strong>
      <span>
        {visit
          ? "The latest Visit image is unavailable, but its review status remains available."
          : "Show live view only when you want to look at this camera now."}
      </span>
    </div>
  );
}

function activityState(stream: DashboardStreamSummary): string {
  if (stream.ready_activity_session_count > 0) return "Finishing Visit";
  if (stream.open_activity_session_count > 0) return "Open activity";
  if (stream.monitoring_active) return "Waiting for sustained activity";
  return "No open activity";
}

function monitoringState(stream: DashboardStreamSummary, runtime?: StreamRuntimeStatus): string {
  const health = stream.camera_health;
  if (health) {
    return {
      healthy: "Healthy",
      starting: "Starting",
      waiting_for_capacity: "Waiting for capacity",
      camera_unavailable: "Camera unavailable",
      no_recent_frame: "No recent frame",
      evidence_storage_degraded: "Evidence storage degraded",
      recovering: "Recovering",
      stopped: "Monitoring stopped",
      setup_incomplete: "Setup incomplete",
    }[health.state];
  }
  if (stream.monitoring_active || runtime?.actual_state === "running") return "Monitoring running";
  if (runtime?.desired_mode === "armed" && runtime.failure_code === "waiting_for_capacity") {
    return "Waiting for monitoring capacity";
  }
  if (runtime?.desired_mode === "armed") return "Monitoring enabled, not currently running";
  return "Monitoring disabled";
}

function monitoringTone(stream: DashboardStreamSummary, runtime?: StreamRuntimeStatus): "good" | "review" | "quiet" {
  if (stream.camera_health?.state === "healthy") return "good";
  if (stream.camera_health?.state === "stopped" || stream.camera_health?.state === "starting") return "quiet";
  if (stream.camera_health) return "review";
  if (stream.monitoring_active || runtime?.actual_state === "running") return "good";
  if (runtime?.desired_mode === "armed") return "review";
  return "quiet";
}

function isActivePreview(state: PreviewState | undefined): boolean {
  return state?.state === "connecting" || state?.state === "live";
}

export function LiveCameraOverview({
  streams,
  runtimeByStream,
  onOpenStream,
  onOpenCameraConfiguration,
  onOpenReview,
  onToggleMonitoring,
}: LiveCameraOverviewProps) {
  const [isVisualOverview, setIsVisualOverview] = useState(true);
  const [showZonesByStream, setShowZonesByStream] = useState<Record<string, boolean>>({});
  const [previews, setPreviews] = useState<Record<string, PreviewState>>({});
  const previewsRef = useRef(previews);
  const isMountedRef = useRef(true);
  const ownerIdRef = useRef(previewOwnerId());

  useEffect(() => {
    previewsRef.current = previews;
  }, [previews]);

  const closeBackendPreview = useCallback((streamId: string) => {
    void apiClient.closeLiveOverviewPreview(streamId, { owner_id: ownerIdRef.current });
  }, []);

  const stopPreview = useCallback(
    (streamId: string) => {
      const current = previewsRef.current[streamId];
      if (current?.backend) closeBackendPreview(streamId);
      setPreviews((existing) => {
        const next = { ...existing };
        delete next[streamId];
        return next;
      });
    },
    [closeBackendPreview],
  );

  const previewFailed = useCallback(
    (streamId: string) => {
      const current = previewsRef.current[streamId];
      if (current?.backend) closeBackendPreview(streamId);
      setPreviews((existing) => ({
        ...existing,
        [streamId]: {
          state: "unavailable",
          backend: Boolean(current?.backend),
          message: "Preview unavailable. Latest activity remains visible for review.",
        },
      }));
    },
    [closeBackendPreview],
  );

  const stopAllPreviews = useCallback(() => {
    const active = previewsRef.current;
    Object.entries(active).forEach(([streamId, preview]) => {
      if (preview.backend) closeBackendPreview(streamId);
    });
    setPreviews({});
  }, [closeBackendPreview]);

  useEffect(() => {
    isMountedRef.current = true;
    const onVisibilityChange = () => {
      if (document.hidden) stopAllPreviews();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      isMountedRef.current = false;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      Object.entries(previewsRef.current).forEach(([streamId, preview]) => {
        if (preview.backend) closeBackendPreview(streamId);
      });
    };
  }, [closeBackendPreview, stopAllPreviews]);

  useEffect(() => {
    const renewal = window.setInterval(() => {
      Object.entries(previewsRef.current).forEach(([streamId, preview]) => {
        if (preview.backend && isActivePreview(preview)) {
          void apiClient.openLiveOverviewPreview(streamId, { owner_id: ownerIdRef.current });
        }
      });
    }, PREVIEW_RENEWAL_MS);
    return () => window.clearInterval(renewal);
  }, []);

  const showLiveView = useCallback(
    async (stream: DashboardStreamSummary) => {
      const current = previewsRef.current[stream.stream_id];
      if (isActivePreview(current)) return;
      const activeCount = Object.values(previewsRef.current).filter(isActivePreview).length;
      const backend = stream.live_preview.kind === "backend_session";
      if (activeCount >= MAX_BROWSER_PREVIEWS) {
        setPreviews((existing) => ({
          ...existing,
          [stream.stream_id]: {
            state: "limit",
            backend,
            message: "Live preview limit reached. Stop another live view before opening this one.",
          },
        }));
        return;
      }
      if (!stream.live_preview.available) {
        setPreviews((existing) => ({
          ...existing,
          [stream.stream_id]: {
            state: "unavailable",
            backend,
            message: stream.live_preview.message,
          },
        }));
        return;
      }
      const directPreviewUrl = stream.live_preview.preview_url;
      if (stream.live_preview.kind === "browser_direct" && directPreviewUrl) {
        setPreviews((existing) => ({
          ...existing,
          [stream.stream_id]: {
            state: "live",
            backend: false,
            mediaUrl: previewUrl(directPreviewUrl),
            mediaKind: stream.live_preview.media_kind,
          },
        }));
        return;
      }

      setPreviews((existing) => ({
        ...existing,
        [stream.stream_id]: { state: "connecting", backend: true, message: "Connecting" },
      }));
      try {
        const response = await apiClient.openLiveOverviewPreview(stream.stream_id, {
          owner_id: ownerIdRef.current,
        });
        if (!isMountedRef.current) {
          closeBackendPreview(stream.stream_id);
          return;
        }
        if (response.status === "limit_reached") {
          setPreviews((existing) => ({
            ...existing,
            [stream.stream_id]: { state: "limit", backend: true, message: response.message },
          }));
          return;
        }
        const backendPreviewUrl = response.preview_url;
        if (!backendPreviewUrl) throw new Error("Preview unavailable");
        setPreviews((existing) => ({
          ...existing,
          [stream.stream_id]: {
            state: "live",
            backend: true,
            mediaUrl: previewUrl(backendPreviewUrl),
            mediaKind: "image",
          },
        }));
      } catch {
        closeBackendPreview(stream.stream_id);
        setPreviews((existing) => ({
          ...existing,
          [stream.stream_id]: {
            state: "unavailable",
            backend: true,
            message: "Camera unavailable. Latest activity remains visible for review.",
          },
        }));
      }
    },
    [closeBackendPreview],
  );

  if (!streams.length) {
    return (
      <section className="panel camera-overview-panel">
        <div className="section-heading">
          <div>
            <h2>Live Camera Overview</h2>
            <span className="meta-text">Choose a camera to begin setup; nothing starts automatically.</span>
          </div>
        </div>
        <EmptyState
          title="No configured cameras"
          description="Add a camera to see its latest activity and optional live view here."
        />
      </section>
    );
  }

  return (
    <section className="panel camera-overview-panel">
      <div className="section-heading">
        <div>
          <h2>Live Camera Overview</h2>
          <span className="meta-text">
            Latest activity stays visible by default. Live views open only when selected and never enable monitoring.
          </span>
        </div>
        <button
          className="secondary-action"
          onClick={() => setIsVisualOverview((current) => !current)}
          type="button"
        >
          {isVisualOverview ? "Compact status" : "Visual overview"}
        </button>
      </div>
      <div className={`camera-overview-grid${isVisualOverview ? "" : " is-compact"}`}>
        {streams.map((stream) => {
          const runtime = runtimeByStream[stream.stream_id];
          const preview = previews[stream.stream_id];
          const showZones = Boolean(showZonesByStream[stream.stream_id]);
          const canShowLive = stream.live_preview.available;
          return (
            <article className="camera-overview-tile" key={stream.stream_id}>
              <div className="item-title-row">
                <div>
                  <h3>{stream.stream_name}</h3>
                  <span className="meta-text">{stream.source_name}</span>
                </div>
                <StatusPill label={monitoringState(stream, runtime)} tone={monitoringTone(stream, runtime)} />
              </div>

              {isVisualOverview ? (
                <div className="camera-overview-frame">
                  {preview?.state === "live" ? (
                    preview.mediaKind === "video" ? (
                      <video autoPlay className="camera-overview-media" muted onError={() => previewFailed(stream.stream_id)} playsInline src={preview.mediaUrl} />
                    ) : (
                      <img alt={`Live view from ${stream.stream_name}`} className="camera-overview-media" onError={() => previewFailed(stream.stream_id)} src={preview.mediaUrl} />
                    )
                  ) : preview?.state === "connecting" ? (
                    <div className="camera-overview-placeholder"><strong>Connecting</strong><span>{preview.message}</span></div>
                  ) : (
                    <LatestActivityFallback stream={stream} />
                  )}
                  {showZones ? <ViewOnlyZoneOverlay zones={stream.zone_overlays} /> : null}
                </div>
              ) : null}

              <div className="camera-overview-facts">
                <span>Desired: <strong>{(stream.camera_health?.desired_mode ?? runtime?.desired_mode) === "armed" ? "Monitoring enabled" : "Monitoring disabled"}</strong></span>
                <span>Actual: <strong>{monitoringState(stream, runtime)}</strong></span>
                <span>{activityState(stream)}</span>
                <span>Open sessions: <strong>{stream.camera_health?.open_activity_session_count ?? stream.open_activity_session_count}</strong></span>
                <span>Last good frame: <strong>{stream.camera_health?.last_good_frame_at ? formatDateTime(stream.camera_health.last_good_frame_at) : "Not yet received"}</strong></span>
                {stream.camera_health?.next_retry_at ? <span>Recovery: <strong>{formatDateTime(stream.camera_health.next_retry_at)}</strong></span> : null}
                {stream.camera_health?.unread_alert ? <span>Unread camera alert</span> : null}
                <span>Needs review: <strong>{stream.needs_review_visit_count}</strong></span>
                <span>Latest Visit: <strong>{stream.latest_visit ? formatDateTime(stream.latest_visit.captured_at) : "None yet"}</strong></span>
                {stream.setup_incomplete ? <span>Setup incomplete</span> : null}
              </div>

              {preview?.state === "limit" || preview?.state === "unavailable" ? (
                <div className="camera-overview-notice" role="status">{preview.message}</div>
              ) : null}

              <div className="detail-actions camera-overview-actions">
                <button className="secondary-action" onClick={() => onOpenStream(stream.stream_id)} type="button">
                  Open Stream
                </button>
                {onOpenCameraConfiguration ? <button className="text-action" onClick={() => onOpenCameraConfiguration(stream.stream_id)} type="button">Edit camera setup</button> : null}
                {isActivePreview(preview) ? (
                  <button className="secondary-action" onClick={() => stopPreview(stream.stream_id)} type="button">
                    Stop live view
                  </button>
                ) : (
                  <button className="primary-action" disabled={!canShowLive} onClick={() => void showLiveView(stream)} type="button">
                    Show live view
                  </button>
                )}
                {stream.zone_overlays.length ? (
                  <button
                    className="text-action"
                    onClick={() => setShowZonesByStream((current) => ({ ...current, [stream.stream_id]: !showZones }))}
                    type="button"
                  >
                    {showZones ? "Hide Zones" : "Show Zones"}
                  </button>
                ) : null}
                {stream.needs_review_visit_count ? (
                  <button className="text-action" onClick={() => onOpenReview(stream.stream_id)} type="button">
                    Review this Stream
                  </button>
                ) : null}
                {onToggleMonitoring && runtime ? (
                  <button className="text-action" onClick={() => onToggleMonitoring(stream, runtime)} type="button">
                    {runtime.desired_mode === "armed" ? "Disable monitoring" : "Enable monitoring"}
                  </button>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
