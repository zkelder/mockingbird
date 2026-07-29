import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type {
  DashboardSummary,
  DashboardVisitSummary,
  CameraHealthSummary,
  HealthStatus,
  ModelAdapter,
  StorageSummary,
  StreamRuntimeStatus,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { LiveCameraOverview } from "../components/LiveCameraOverview";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface ReviewQueueFocus {
  source: "live-motion";
  search: string;
  status: "unreviewed";
}

interface DashboardPageProps {
  health: HealthStatus | null;
  onOpenStream: (streamId: string) => void;
  onOpenStreams: () => void;
  onOpenCameraConfiguration: (streamId: string) => void;
  onAddCamera: () => void;
  onOpenReview: (context?: ReviewQueueFocus) => void;
  onOpenBirdLog: () => void;
  onOpenInsights: () => void;
  onOpenVisit: (visitId: string) => void;
}

const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;

function cameraHealthLabel(state: CameraHealthSummary["state"]): string {
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
  }[state];
}

function cameraHealthTone(state: CameraHealthSummary["state"]): "good" | "review" | "quiet" {
  if (state === "healthy") return "good";
  if (state === "stopped" || state === "starting") return "quiet";
  return "review";
}

function outcomeLabel(visit: DashboardVisitSummary): string {
  if (visit.review_outcome === "needs_review") {
    return "Needs review";
  }
  if (visit.review_outcome === "confirmed_bird") {
    return visit.reviewed_label
      ? `Confirmed bird: ${formatLabel(visit.reviewed_label)}`
      : "Confirmed bird observation";
  }
  if (visit.review_outcome === "non_bird") {
    return visit.reviewed_label
      ? `Reviewed activity: ${formatLabel(visit.reviewed_label)}`
      : "Reviewed non-bird activity";
  }
  if (visit.review_outcome === "false_positive") {
    return "False-positive outcome";
  }
  if (visit.review_outcome === "blank") {
    return "Blank outcome";
  }
  if (visit.review_outcome === "ambiguous") {
    return "Ambiguous or unknown outcome";
  }
  if (visit.review_outcome === "rejected") {
    return "Dismissed outcome";
  }
  return visit.reviewed_label
    ? `Reviewed outcome: ${formatLabel(visit.reviewed_label)}`
    : "Reviewed outcome";
}

function durationLabel(seconds: number): string {
  if (seconds <= 0) {
    return "Instant";
  }
  if (seconds < 60) {
    return `${Math.round(seconds)} sec`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return remainder ? `${minutes} min ${remainder} sec` : `${minutes} min`;
}

function VisitPreview({ visit }: { visit: DashboardVisitSummary }) {
  const [unavailable, setUnavailable] = useState(false);
  if (!visit.primary_evidence || unavailable) {
    return <div className="dashboard-visit-preview dashboard-preview-unavailable">Preview unavailable</div>;
  }
  return (
    <img
      alt={`Visit from ${formatDateTime(visit.captured_at)}`}
      className="dashboard-visit-preview"
      onError={() => setUnavailable(true)}
      src={`${apiClient.baseUrl}${visit.primary_evidence.preview_url}`}
    />
  );
}

function VisitContext({ visit }: { visit: DashboardVisitSummary }) {
  return (
    <span className="meta-text">
      {visit.stream_name} · {visit.zone_name ? visit.zone_name : "No Zone"} · {durationLabel(visit.duration_seconds)}
    </span>
  );
}

export function DashboardPage({
  health,
  onOpenStream,
  onOpenStreams,
  onOpenCameraConfiguration,
  onAddCamera,
  onOpenReview,
  onOpenBirdLog,
  onOpenInsights,
  onOpenVisit,
}: DashboardPageProps) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [monitorActionError, setMonitorActionError] = useState<string | null>(null);
  const [durableStatusByStream, setDurableStatusByStream] = useState<
    Record<string, StreamRuntimeStatus>
  >({});
  const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);
  const [detectorStatus, setDetectorStatus] = useState<ModelAdapter | null>(null);

  const refreshDashboard = useCallback(async (initialLoad = false) => {
    if (initialLoad) {
      setIsLoading(true);
    } else {
      setIsRefreshing(true);
    }
    try {
      const [nextSummary, monitoringStatuses, nextStorageSummary, nextDetectorStatus] = await Promise.all([
        apiClient.getDashboardSummary(),
        apiClient.getStreamMonitoringStatuses().catch(() => null),
        apiClient.getStorageRetentionSummary().catch(() => null),
        apiClient.getModelAdapter("megadetector").catch(() => null),
      ]);
      setSummary(nextSummary);
      setStorageSummary(nextStorageSummary);
      setDetectorStatus(nextDetectorStatus);
      if (monitoringStatuses) {
        setDurableStatusByStream(
          Object.fromEntries(
            monitoringStatuses.items.map((status) => [status.stream_id, status]),
          ),
        );
      }
      setRefreshError(null);
    } catch {
      // Keep the last product snapshot visible during a transient local API failure.
      setRefreshError("Could not refresh daily operations.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refreshDashboard(true);
    const refreshTimer = window.setInterval(
      () => void refreshDashboard(),
      DASHBOARD_REFRESH_INTERVAL_MS,
    );
    return () => window.clearInterval(refreshTimer);
  }, [refreshDashboard]);

  async function handleDurableMonitoringAction(
    streamId: string,
    action: "enable" | "disable" | "retry",
  ) {
    setMonitorActionError(null);
    const idempotencyKey =
      globalThis.crypto?.randomUUID?.() ??
      `dashboard-monitoring-${action}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    try {
      const result =
        action === "retry"
          ? await apiClient.retryStreamMonitoring(streamId, {
              idempotency_key: idempotencyKey,
            })
          : await apiClient.updateStreamMonitoringPolicy(streamId, {
              enabled: action === "enable",
              idempotency_key: idempotencyKey,
            });
      setDurableStatusByStream((current) => ({
        ...current,
        [streamId]: result.runtime,
      }));
      await refreshDashboard();
    } catch {
      setMonitorActionError(
        "Could not update persistent monitoring. Open Stream Detail to check this camera.",
      );
    }
  }

  function openVisitReview(visit: DashboardVisitSummary) {
    onOpenReview({ source: "live-motion", search: visit.id, status: "unreviewed" });
  }

  if (isLoading && !summary) {
    return <div className="panel">Loading daily operations…</div>;
  }

  if (!summary) {
    return (
      <div className="error-panel">
        <strong>Daily operations are unavailable.</strong>
        <span>{refreshError ?? "MockingBird could not load its current Stream activity."}</span>
        <button className="secondary-action" onClick={() => void refreshDashboard()} type="button">
          Retry
        </button>
      </div>
    );
  }

  const { headline } = summary;
  return (
    <div className="page-stack dashboard-operations-page">
      <section className="dashboard-hero dashboard-operations-hero">
        <div>
          <StatusPill
            label={health?.status === "ok" ? "Local app connected" : "Local status unavailable"}
            tone={health?.status === "ok" ? "good" : "review"}
          />
          <h1>Today’s outdoor operations</h1>
          <p>
            Monitor Streams, review activity, and see only reviewed observations from {summary.local_day}.
          </p>
        </div>
        <div className="hero-actions">
          <button className="primary-action" onClick={onAddCamera} type="button">
            Add Camera
          </button>
          <button className="primary-action" onClick={onOpenStreams} type="button">
            Open Cameras / Streams
          </button>
          <button className="secondary-action" onClick={onOpenInsights} type="button">
            Zone & Feeder Insights
          </button>
          <button className="secondary-action" onClick={() => void refreshDashboard()} type="button">
            {isRefreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </section>

      {refreshError ? (
        <div className="dashboard-refresh-notice" role="status">
          <span>Could not refresh. Showing the last successful dashboard data.</span>
          <button className="text-action" onClick={() => void refreshDashboard()} type="button">
            Retry
          </button>
        </div>
      ) : null}
      {summary.warnings.length > 0 ? (
        <div className="dashboard-refresh-notice" role="status">
          <span>{summary.warnings[0]}</span>
          {summary.warnings.length > 1 ? <span>+{summary.warnings.length - 1} more Stream updates</span> : null}
        </div>
      ) : null}
      {storageSummary?.storage_warning ? (
        <div className="dashboard-refresh-notice" role="status">
          <span>{storageSummary.storage_warning}</span>
        </div>
      ) : null}

      <section aria-label="Current operations" className="dashboard-operations-metrics">
        <button className="dashboard-operation-card" onClick={onOpenStreams} type="button">
          <span>Configured Streams</span>
          <strong>{headline.configured_stream_count}</strong>
          <small>Open Cameras / Streams</small>
        </button>
        <button className="dashboard-operation-card" onClick={onOpenStreams} type="button">
          <span>Monitoring now</span>
          <strong>{headline.monitored_stream_count}</strong>
          <small>Explicitly started only</small>
        </button>
        <button className="dashboard-operation-card" onClick={onOpenStreams} type="button">
          <span>Open activity sessions</span>
          <strong>{headline.open_activity_session_count}</strong>
          <small>Zone activity still in progress</small>
        </button>
        <button className="dashboard-operation-card" onClick={() => onOpenReview()} type="button">
          <span>Animal candidates</span>
          <strong>{headline.actionable_animal_visit_count}</strong>
          <small>{headline.legacy_activity_count > 0 ? `${headline.legacy_activity_count} legacy activity items are secondary` : "Open Product Mode"}</small>
        </button>
        <button className="dashboard-operation-card" onClick={onOpenBirdLog} type="button">
          <span>Reviewed observations today</span>
          <strong>{headline.reviewed_observation_count_today}</strong>
          <small>Correction-derived bird truth</small>
        </button>
        <div className="dashboard-operation-card">
          <span>Detector</span>
          <strong>{detectorStatus?.status === "available" ? "Ready" : "Unavailable"}</strong>
          <small>{detectorStatus?.status === "available" ? "MegaDetector is ready for evidence proposals" : "Monitoring stays safe without it"}</small>
        </div>
      </section>

      {monitorActionError ? <div className="dashboard-action-error" role="alert">{monitorActionError}</div> : null}
      {summary.camera_attention.length > 0 ? (
        <section className="panel dashboard-camera-attention" aria-label="Cameras needing attention">
          <div className="section-heading">
            <div>
              <h2>Cameras needing attention</h2>
              <span className="meta-text">Only enabled Streams with a meaningful current camera-health concern</span>
            </div>
            <StatusPill label={`${summary.camera_attention.length} needs attention`} tone="review" />
          </div>
          <div className="dashboard-visit-list">
            {summary.camera_attention.map((camera) => (
              <article className="dashboard-visit-row" key={camera.stream_id}>
                <div>
                  <StatusPill label={cameraHealthLabel(camera.state)} tone={cameraHealthTone(camera.state)} />
                  <strong>{camera.stream_name}</strong>
                  <span className="meta-text">{camera.source_name} · {camera.desired_mode} / {camera.actual_state}</span>
                  <span className="meta-text">
                    Last good frame {camera.last_good_frame_at ? formatDateTime(camera.last_good_frame_at) : "not yet received"}
                    {camera.last_evidence_persisted_at ? ` · Evidence write ${formatDateTime(camera.last_evidence_persisted_at)}` : ""}
                    {camera.next_retry_at ? ` · Next retry ${formatDateTime(camera.next_retry_at)}` : ""}
                  </span>
                  <span className="meta-text">{camera.failure_reason ?? camera.message}</span>
                </div>
                <div className="detail-actions">
                  <button className="secondary-action" onClick={() => onOpenStream(camera.stream_id)} type="button">Open Stream</button>
                  {camera.desired_mode === "armed" ? <button className="secondary-action" onClick={() => void handleDurableMonitoringAction(camera.stream_id, "retry")} type="button">Retry now</button> : null}
                  <button className="text-action" onClick={() => onOpenCameraConfiguration(camera.stream_id)} type="button">Edit camera setup</button>
                  {camera.desired_mode === "armed" ? <button className="text-action" onClick={() => void handleDurableMonitoringAction(camera.stream_id, "disable")} type="button">Disable monitoring</button> : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      <LiveCameraOverview
        onOpenReview={(streamId) =>
          onOpenReview({ source: "live-motion", search: streamId, status: "unreviewed" })
        }
        onOpenStream={onOpenStream}
        onOpenCameraConfiguration={onOpenCameraConfiguration}
        onToggleMonitoring={(stream, runtime) =>
          void handleDurableMonitoringAction(
            stream.stream_id,
            runtime.desired_mode === "armed" ? "disable" : "enable",
          )
        }
        runtimeByStream={durableStatusByStream}
        streams={summary.streams}
      />

      <section className="panel dashboard-needs-review">
        <div className="section-heading">
          <div>
            <h2>Current animal candidates</h2>
            <span className="meta-text">Detector-qualified animal Visits · legacy activity remains secondary</span>
          </div>
          <button className="secondary-action" onClick={() => onOpenReview()} type="button">
            Open Review Queue
          </button>
        </div>
        {summary.actionable_animal_visits.length > 0 ? (
          <div className="dashboard-visit-list">
            {summary.actionable_animal_visits.map((visit) => (
              <article className="dashboard-visit-row" key={visit.id}>
                <VisitPreview visit={visit} />
                <div>
                  <strong>{formatDateTime(visit.captured_at)}</strong>
                  <VisitContext visit={visit} />
                  <span className="meta-text">
                    {visit.evidence_frame_count > 1 ? `${visit.evidence_frame_count} evidence frames` : "One evidence frame"}
                    {visit.has_suggestion ? ` · Suggestion: ${visit.suggested_label ? formatLabel(visit.suggested_label) : "available"}` : ""}
                  </span>
                </div>
                <button className="primary-action" onClick={() => openVisitReview(visit)} type="button">
                  Review
                </button>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No detector-qualified animal Visits need review"
            description="New detector-qualified animal activity appears here; legacy activity stays in its secondary Review Queue tab."
            action={<button className="secondary-action" onClick={() => onOpenReview()} type="button">Open Review Queue</button>}
          />
        )}
      </section>

      <section className="dashboard-observation-grid">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Today’s Observations</h2>
              <span className="meta-text">Reviewed bird observations only</span>
            </div>
            <button className="text-action" onClick={onOpenBirdLog} type="button">Open Bird Log</button>
          </div>
          {summary.today_observations.length > 0 ? (
            <div className="dashboard-observation-list">
              {summary.today_observations.map((observation) => (
                <article className="dashboard-observation-row" key={observation.label}>
                  <VisitPreview visit={observation.latest_visit} />
                  <div>
                    <strong>{observation.display_name}</strong>
                    <span>{observation.observation_count} observation{observation.observation_count === 1 ? "" : "s"}</span>
                    <VisitContext visit={observation.latest_visit} />
                    <span className="meta-text">Latest {formatDateTime(observation.latest_visit.captured_at)}</span>
                  </div>
                  <button className="text-action" onClick={() => onOpenVisit(observation.latest_visit.id)} type="button">
                    View
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No reviewed bird observations today"
              description="Corrections for bird Visits appear here; suggestions never count as observations."
            />
          )}
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Reviewed activity</h2>
              <span className="meta-text">Non-bird activity, not bird observations</span>
            </div>
            <StatusPill label="Activity" tone="quiet" />
          </div>
          {summary.reviewed_non_bird_activity.length > 0 ? (
            <div className="dashboard-observation-list">
              {summary.reviewed_non_bird_activity.map((observation) => (
                <article className="dashboard-observation-row" key={observation.label}>
                  <VisitPreview visit={observation.latest_visit} />
                  <div>
                    <strong>{observation.display_name}</strong>
                    <span>{observation.observation_count} reviewed activity case{observation.observation_count === 1 ? "" : "s"}</span>
                    <VisitContext visit={observation.latest_visit} />
                  </div>
                  <button className="text-action" onClick={() => onOpenVisit(observation.latest_visit.id)} type="button">
                    View
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No reviewed non-bird activity today"
              description="People, pets, mammals, vehicles, and other reviewed activity stay separate from Bird observations."
            />
          )}
        </section>
      </section>

      <section className="panel dashboard-recent-activity">
        <div className="section-heading">
          <div>
            <h2>Recent activity</h2>
            <span className="meta-text">Newest Visits across Streams</span>
          </div>
          <span className="meta-text">Updated {formatDateTime(summary.generated_at)}</span>
        </div>
        {summary.recent_activity.length > 0 ? (
          <div className="dashboard-visit-list">
            {summary.recent_activity.map((visit) => (
              <article className="dashboard-visit-row dashboard-activity-row" key={visit.id}>
                <VisitPreview visit={visit} />
                <div>
                  <strong>{outcomeLabel(visit)}</strong>
                  <span>{formatDateTime(visit.captured_at)}</span>
                  <VisitContext visit={visit} />
                </div>
                <div className="detail-actions">
                  {visit.review_status === "needs_review" ? (
                    <button className="secondary-action" onClick={() => openVisitReview(visit)} type="button">Review</button>
                  ) : (
                    <button className="secondary-action" onClick={() => onOpenVisit(visit.id)} type="button">Visit detail</button>
                  )}
                  <button className="text-action" onClick={() => onOpenStream(visit.stream_id)} type="button">Stream</button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No recent activity"
            description="Captured Visits will appear here after activity becomes reviewable."
            action={<button className="secondary-action" onClick={onOpenStreams} type="button">Open Cameras / Streams</button>}
          />
        )}
      </section>
    </div>
  );
}
