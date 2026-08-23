import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type {
  DashboardStreamSummary,
  DashboardZoneOverlay,
  LiveCameraSessionStatus,
  StreamRuntimeStatus,
} from "../api/types";
import { cameraHealthLabel, cameraHealthTone, formatDateTime } from "../utils";
import { CurrentFrameView } from "./CurrentFrameView";
import { EmptyState } from "./EmptyState";
import { StatusPill } from "./StatusPill";

const MAX_BROWSER_PREVIEWS = 4;
const PREVIEW_RENEWAL_MS = 45_000;
const OVERVIEW_OWNER_KEY = "mockingbird-live-overview-owner-v1";
// How often to refresh the legacy live-session ownership signal below --
// fast enough to un-mask a real ownership hand-off promptly, slow enough
// (unlike CurrentFrameView's own 1s frame poll) to avoid multiplying
// request volume across every configured camera_node tile.
const OWNERSHIP_POLL_MS = 5_000;

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

function exposureDurationLabel(seconds?: number | null): string {
  if (seconds == null || seconds <= 0) return "just started";
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  return `${Math.floor(seconds / 60)} min`;
}

function monitoringState(
  stream: DashboardStreamSummary,
  runtime?: StreamRuntimeStatus,
  pausedForObservation?: boolean,
): string {
  // Observation Engine deliberately pauses this Stream's legacy live
  // session to take exclusive Camera Node ownership (see the ownership-poll
  // effect in LiveCameraOverview below) -- a healthy, expected hand-off,
  // never a camera failure. `camera_health` below is sourced entirely from
  // the legacy monitoring-policy subsystem, which Observation Engine never
  // touches, so it would otherwise keep reading "Monitoring stopped" the
  // whole time Observation is actively, healthily watching this camera.
  if (pausedForObservation) return "Observing";
  const health = stream.camera_health;
  // Camera / Source + Multi-Camera Maturity v1, Phase F: reuse the one
  // canonical `cameraHealthLabel` (utils.ts, the "B7 health model" this
  // milestone's own doctrine names) instead of this file's own separately-
  // maintained copy of the same mapping -- exactly the divergence risk that
  // model was built to close, and the reason this file's tone below had
  // silently drifted out of sync with the shared 4-tone severity fix.
  if (health) return cameraHealthLabel(health.state);
  if (stream.monitoring_active || runtime?.actual_state === "running") return "Monitoring running";
  if (runtime?.desired_mode === "armed" && runtime.failure_code === "waiting_for_capacity") {
    return "Waiting for monitoring capacity";
  }
  if (runtime?.desired_mode === "armed") return "Monitoring enabled, not currently running";
  return "Monitoring disabled";
}

function monitoringTone(
  stream: DashboardStreamSummary,
  runtime?: StreamRuntimeStatus,
  pausedForObservation?: boolean,
): "good" | "review" | "alert" | "quiet" {
  if (pausedForObservation) return "good";
  if (stream.camera_health) return cameraHealthTone(stream.camera_health.state);
  if (stream.monitoring_active || runtime?.actual_state === "running") return "good";
  if (runtime?.desired_mode === "armed") return "review";
  return "quiet";
}

function isActivePreview(state: PreviewState | undefined): boolean {
  return state?.state === "connecting" || state?.state === "live";
}

function isProductActiveCamera(
  stream: DashboardStreamSummary,
  runtime?: StreamRuntimeStatus,
): boolean {
  if (stream.source_kind === "demo") return false;
  return (
    stream.monitoring_active ||
    runtime?.actual_state === "running" ||
    runtime?.actual_state === "starting" ||
    runtime?.desired_mode === "armed" ||
    stream.camera_health?.state === "healthy" ||
    (stream.playback_kind === "camera_node" && stream.availability_status === "live_ready")
  );
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
  const [showInactiveCameras, setShowInactiveCameras] = useState(false);
  const [showDemoData, setShowDemoData] = useState(false);
  const [showZonesByStream, setShowZonesByStream] = useState<Record<string, boolean>>({});
  const [previews, setPreviews] = useState<Record<string, PreviewState>>({});
  const [liveSessionByStream, setLiveSessionByStream] = useState<Record<string, LiveCameraSessionStatus>>({});
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

  // Legacy live-session ownership signal for every configured camera_node
  // Stream (Pi Camera Node), refreshed independently of the parent's own
  // ~30s dashboard summary refresh -- mirrors StreamDetailPage's own
  // already-fixed `liveSessionPausedForObservation` gate (see below).
  // `cameraNodeStreamIdsKey`, not `streams` itself (a new array reference
  // on every parent refresh even when nothing changed), is the effect
  // dependency so the poll interval is not torn down and rebuilt for no
  // reason every time the parent refreshes.
  const cameraNodeStreamIdsKey = streams
    .filter((stream) => stream.playback_kind === "camera_node")
    .map((stream) => stream.stream_id)
    .join(",");

  useEffect(() => {
    const ids = cameraNodeStreamIdsKey ? cameraNodeStreamIdsKey.split(",") : [];
    if (!ids.length) return;
    let disposed = false;
    const poll = async () => {
      const entries = await Promise.all(
        ids.map(async (streamId) => {
          try {
            return [streamId, await apiClient.getLiveCameraSessionStatus(streamId)] as const;
          } catch {
            return null;
          }
        }),
      );
      if (disposed) return;
      setLiveSessionByStream((existing) => {
        const next = { ...existing };
        for (const entry of entries) {
          if (entry) next[entry[0]] = entry[1];
        }
        return next;
      });
    };
    void poll();
    const timer = window.setInterval(() => void poll(), OWNERSHIP_POLL_MS);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [cameraNodeStreamIdsKey]);

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

  const activeStreams = streams.filter((stream) =>
    isProductActiveCamera(stream, runtimeByStream[stream.stream_id]),
  );
  const inactiveStreams = streams.filter(
    (stream) =>
      stream.source_kind !== "demo" &&
      !isProductActiveCamera(stream, runtimeByStream[stream.stream_id]),
  );
  const demoStreams = streams.filter((stream) => stream.source_kind === "demo");
  const visibleStreams = [
    ...activeStreams,
    ...(showInactiveCameras ? inactiveStreams : []),
    ...(showDemoData ? demoStreams : []),
  ];

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
      <div className="camera-overview-groups">
        <div className="camera-overview-group-heading">
          <strong>Active cameras</strong>
          <span>{activeStreams.length ? "Monitoring, healthy, or selected for everyday use" : "No active camera is reporting yet"}</span>
        </div>
        {inactiveStreams.length ? (
          <button
            aria-expanded={showInactiveCameras}
            className="text-action"
            onClick={() => setShowInactiveCameras((current) => !current)}
            type="button"
          >
            {showInactiveCameras ? "Hide inactive saved cameras" : `Show inactive saved cameras (${inactiveStreams.length})`}
          </button>
        ) : null}
        {demoStreams.length ? (
          <button
            aria-expanded={showDemoData}
            className="text-action"
            onClick={() => setShowDemoData((current) => !current)}
            type="button"
          >
            {showDemoData ? "Hide demo and test data" : "Show demo and test data"}
          </button>
        ) : null}
      </div>
      <div className={`camera-overview-grid${isVisualOverview ? "" : " is-compact"}`}>
        {visibleStreams.map((stream) => {
          const runtime = runtimeByStream[stream.stream_id];
          const preview = previews[stream.stream_id];
          const showZones = Boolean(showZonesByStream[stream.stream_id]);
          const canShowLive = stream.live_preview.available;
          const liveSession = liveSessionByStream[stream.stream_id];
          // `status === "paused"` is set by Observation Engine's own
          // `pause_for_observation` call path only, and unconditionally
          // reverted (even on a real Camera Node failure -- see
          // `_EngineSession._run`'s `finally` block) the moment Observation
          // itself stops, so this cannot linger stale after a real outage:
          // it is already authoritative for "Observation owns this camera
          // right now," exactly like StreamDetailPage's identical gate.
          const liveSessionPausedForObservation = liveSession?.status === "paused";
          return (
            <article className="camera-overview-tile" key={stream.stream_id}>
              <div className="item-title-row">
                <div>
                  <h3>{stream.stream_name}</h3>
                  <span className="meta-text">
                    {stream.source_name}
                    {stream.camera_health?.area_name ? ` · ${stream.camera_health.area_name}` : ""}
                  </span>
                </div>
                <StatusPill
                  label={monitoringState(stream, runtime, liveSessionPausedForObservation)}
                  tone={monitoringTone(stream, runtime, liveSessionPausedForObservation)}
                />
              </div>

              {isVisualOverview ? (
                <div className="camera-overview-frame">
                  {stream.playback_kind === "camera_node" ? (
                    liveSessionPausedForObservation ? (
                      // Observation owns the camera right now: the
                      // current-frame endpoint deterministically 409s (see
                      // `get_stream_live_camera_current_frame`), so mounting
                      // CurrentFrameView here would only manufacture a
                      // "Current camera frame unavailable" failure signal
                      // out of a healthy, expected hand-off -- the same
                      // masking bug already fixed on Stream Detail. Show the
                      // backend's own honest paused message instead of
                      // inventing a new preview (Observation exposes none).
                      <div className="camera-overview-placeholder">
                        <strong>Live preview paused</strong>
                        <span>
                          {liveSession?.message ??
                            "Live preview is paused while MockingBird is monitoring this camera."}
                        </span>
                      </div>
                    ) : (
                      <CurrentFrameView
                        active={isVisualOverview}
                        alt={`Current view from ${stream.stream_name}`}
                        className="camera-overview-media"
                        streamId={stream.stream_id}
                      />
                    )
                  ) : preview?.state === "live" ? (
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
                <span>Actual: <strong>{monitoringState(stream, runtime, liveSessionPausedForObservation)}</strong></span>
                <span>{activityState(stream)}</span>
                <span>Open sessions: <strong>{stream.camera_health?.open_activity_session_count ?? stream.open_activity_session_count}</strong></span>
                <span>Last good frame: <strong>{stream.camera_health?.last_good_frame_at ? formatDateTime(stream.camera_health.last_good_frame_at) : "Not yet received"}</strong></span>
                {runtime?.exposure_interval_active ? <span>Active exposure: <strong>{exposureDurationLabel(runtime.current_healthy_duration_seconds)}</strong></span> : null}
                {stream.camera_health?.next_retry_at ? <span>Recovery: <strong>{formatDateTime(stream.camera_health.next_retry_at)}</strong></span> : null}
                {stream.camera_health?.unread_alert ? <span>Unread camera alert</span> : null}
                {
                  // Camera / Source + Multi-Camera Maturity v1, Phase F/K:
                  // plain wording only -- "kept working while disconnected,
                  // items waiting to sync" is the target phrasing from the
                  // milestone brief, never transport/protocol jargon.
                  stream.camera_health?.connectivity_reason === "host_unreachable" ? (
                    <span>
                      The camera kept working while disconnected
                      {typeof stream.camera_health.backlog_pending_count === "number"
                        ? ` and has ${stream.camera_health.backlog_pending_count} item(s) waiting to sync`
                        : ""}
                      .
                    </span>
                  ) : typeof stream.camera_health?.backlog_pending_count === "number" &&
                    stream.camera_health.backlog_pending_count > 0 ? (
                    <span>Backlog pending: <strong>{stream.camera_health.backlog_pending_count} item(s) waiting to sync</strong></span>
                  ) : null
                }
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
                {stream.playback_kind === "camera_node" ? null : isActivePreview(preview) ? (
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
                {/* `runtime` (StreamRuntimeStatus) always resolves from the
                    *legacy* durable-monitoring-policy subsystem
                    (list_stream_monitoring_statuses has no provider filter),
                    so it is truthy even for a `camera_node` Stream that has
                    never used that subsystem. A paired Camera Node is
                    exclusively governed by the accepted Observation Engine's
                    own Start/Stop control and its Stage 7 admission gate
                    (see unified_status.resolve_observation_runtime); arming
                    this legacy toggle here would durably start an
                    ungated zone-motion session against the same camera --
                    including auto-created Visits with none of that gate's
                    quality checks -- and keep silently resuming it every
                    time Observation later stops
                    (LiveCameraSessionManager.resume_after_observation).
                    Hidden here for camera_node, exactly like "Show/Stop live
                    view" above, rather than routing this Stream type
                    through a control it must never use. */}
                {onToggleMonitoring && runtime && stream.playback_kind !== "camera_node" ? (
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
