import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type {
  DashboardStreamSummary,
  DashboardSummary,
  DashboardVisitSummary,
  HealthStatus,
  StorageSummary,
  StreamRuntimeStatus,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
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
  onAddCamera: () => void;
  onOpenReview: (context?: ReviewQueueFocus) => void;
  onOpenBirdLog: () => void;
  onOpenVisit: (visitId: string) => void;
}

const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;

function availabilityTone(
  status: DashboardStreamSummary["availability_status"],
): "good" | "review" | "quiet" {
  if (status === "demo" || status === "live_ready") {
    return "good";
  }
  if (
    status === "not_configured" ||
    status === "unavailable" ||
    status === "offline" ||
    status === "playback_error" ||
    status.startsWith("unsupported")
  ) {
    return "review";
  }
  return "quiet";
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
  onAddCamera,
  onOpenReview,
  onOpenBirdLog,
  onOpenVisit,
}: DashboardPageProps) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [monitorActionId, setMonitorActionId] = useState<string | null>(null);
  const [monitorActionError, setMonitorActionError] = useState<string | null>(null);
  const [durableStatusByStream, setDurableStatusByStream] = useState<
    Record<string, StreamRuntimeStatus>
  >({});
  const [durableActionId, setDurableActionId] = useState<string | null>(null);
  const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);

  const refreshDashboard = useCallback(async (initialLoad = false) => {
    if (initialLoad) {
      setIsLoading(true);
    } else {
      setIsRefreshing(true);
    }
    try {
      const [nextSummary, monitoringStatuses, nextStorageSummary] = await Promise.all([
        apiClient.getDashboardSummary(),
        apiClient.getStreamMonitoringStatuses().catch(() => null),
        apiClient.getStorageRetentionSummary().catch(() => null),
      ]);
      setSummary(nextSummary);
      setStorageSummary(nextStorageSummary);
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

  async function handleMonitorAction(stream: DashboardStreamSummary) {
    setMonitorActionId(stream.stream_id);
    setMonitorActionError(null);
    try {
      if (stream.can_stop_monitor) {
        if (stream.monitor_control === "source_monitor") {
          await apiClient.stopStreamMonitor(stream.stream_id);
        } else {
          await apiClient.stopLiveMotionMonitor(stream.stream_id);
        }
      } else if (stream.monitor_control === "source_monitor") {
        await apiClient.startStreamMonitor(stream.stream_id);
      } else if (stream.monitor_control === "live_motion") {
        await apiClient.startLiveMotionMonitor(stream.stream_id);
      }
      await refreshDashboard();
    } catch {
      setMonitorActionError(
        "Could not update monitoring from Dashboard. Open Stream Detail to check its current status.",
      );
    } finally {
      setMonitorActionId(null);
    }
  }

  async function handleDurableMonitoringAction(
    streamId: string,
    action: "enable" | "disable" | "retry",
  ) {
    setDurableActionId(`${action}-${streamId}`);
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
    } finally {
      setDurableActionId(null);
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
          <span>Visits needing review</span>
          <strong>{headline.needs_review_visit_count}</strong>
          <small>Open Review Queue</small>
        </button>
        <button className="dashboard-operation-card" onClick={onOpenBirdLog} type="button">
          <span>Reviewed observations today</span>
          <strong>{headline.reviewed_observation_count_today}</strong>
          <small>Correction-derived bird truth</small>
        </button>
      </section>

      <section className="panel dashboard-stream-overview">
        <div className="section-heading">
          <div>
            <h2>Camera and Stream status</h2>
            <span className="meta-text">Availability is read-only. Persistent monitoring starts only after Enable.</span>
          </div>
          <StatusPill
            label={headline.monitored_stream_count ? "Monitoring active" : "No Stream monitored"}
            tone={headline.monitored_stream_count ? "good" : "quiet"}
          />
        </div>
        {monitorActionError ? <div className="dashboard-action-error" role="alert">{monitorActionError}</div> : null}
        {summary.streams.length > 0 ? (
          <div className="dashboard-stream-grid">
            {summary.streams.map((stream) => (
              <article className="dashboard-stream-card" key={stream.stream_id}>
                {(() => {
                  const durableStatus = durableStatusByStream[stream.stream_id];
                  const monitoringEnabled = durableStatus?.desired_mode === "armed";
                  return (
                    <>
                <div className="item-title-row">
                  <div>
                    <h3>{stream.stream_name}</h3>
                    <span className="meta-text">{stream.source_name}</span>
                  </div>
                  <StatusPill
                    label={formatLabel(stream.availability_status)}
                    tone={availabilityTone(stream.availability_status)}
                  />
                </div>
                <span className="dashboard-stream-message">{stream.availability_message}</span>
                <div className="dashboard-stream-facts">
                  <span>
                    Monitoring: <strong>{stream.monitoring_active ? "Active" : "Inactive"}</strong>
                  </span>
                  <span>
                    Persistent: <strong>{monitoringEnabled ? "Enabled" : "Disabled"}</strong>
                    {durableStatus ? ` · ${formatLabel(durableStatus.actual_state)}` : ""}
                  </span>
                  <span>
                    Open sessions: <strong>{stream.open_activity_session_count}</strong>
                    {stream.ready_activity_session_count ? ` (${stream.ready_activity_session_count} ready)` : ""}
                  </span>
                  <span>
                    Needs review: <strong>{stream.needs_review_visit_count}</strong>
                  </span>
                </div>
                {stream.latest_visit ? (
                  <div className="dashboard-stream-latest">
                    <VisitPreview visit={stream.latest_visit} />
                    <div>
                      <strong>Latest Visit</strong>
                      <span>{formatDateTime(stream.latest_visit.captured_at)}</span>
                      <VisitContext visit={stream.latest_visit} />
                    </div>
                  </div>
                ) : (
                  <span className="meta-text">No Visits captured for this Stream yet.</span>
                )}
                <div className="detail-actions">
                  <button className="secondary-action" onClick={() => onOpenStream(stream.stream_id)} type="button">
                    Open Stream Detail
                  </button>
                  {stream.can_start_monitor || stream.can_stop_monitor ? (
                    <button
                      className={stream.can_stop_monitor ? "secondary-action" : "primary-action"}
                      disabled={monitorActionId === stream.stream_id}
                      onClick={() => void handleMonitorAction(stream)}
                      type="button"
                    >
                      {monitorActionId === stream.stream_id
                        ? "Updating…"
                        : stream.can_stop_monitor
                          ? "Stop monitoring"
                          : "Start monitoring"}
                    </button>
                  ) : null}
                  {durableStatus ? (
                    <button
                      className={monitoringEnabled ? "secondary-action" : "primary-action"}
                      disabled={durableActionId !== null}
                      onClick={() =>
                        void handleDurableMonitoringAction(
                          stream.stream_id,
                          monitoringEnabled ? "disable" : "enable",
                        )
                      }
                      type="button"
                    >
                      {durableActionId === `${monitoringEnabled ? "disable" : "enable"}-${stream.stream_id}`
                        ? "Updating…"
                        : monitoringEnabled
                          ? "Disable monitoring"
                          : "Enable monitoring"}
                    </button>
                  ) : null}
                  {monitoringEnabled && durableStatus?.actual_state !== "running" ? (
                    <button
                      className="text-action"
                      disabled={durableActionId !== null}
                      onClick={() =>
                        void handleDurableMonitoringAction(stream.stream_id, "retry")
                      }
                      type="button"
                    >
                      {durableActionId === `retry-${stream.stream_id}` ? "Retrying…" : "Retry monitoring"}
                    </button>
                  ) : null}
                  {stream.needs_review_visit_count ? (
                    <button
                      className="text-action"
                      onClick={() =>
                        onOpenReview({
                          source: "live-motion",
                          search: stream.stream_id,
                          status: "unreviewed",
                        })
                      }
                      type="button"
                    >
                      Review this Stream
                    </button>
                  ) : null}
                </div>
                    </>
                  );
                })()}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No Sources or Streams configured"
            description="Add a camera or media Source to create the first Stream for daily operations."
            action={<button className="secondary-action" onClick={onOpenStreams} type="button">Open Cameras / Streams</button>}
          />
        )}
      </section>

      <section className="panel dashboard-needs-review">
        <div className="section-heading">
          <div>
            <h2>Needs Review</h2>
            <span className="meta-text">Newest unresolved Visits across Streams</span>
          </div>
          <button className="secondary-action" onClick={() => onOpenReview()} type="button">
            Open Review Queue
          </button>
        </div>
        {summary.needs_review_visits.length > 0 ? (
          <div className="dashboard-visit-list">
            {summary.needs_review_visits.map((visit) => (
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
            title="No Visits need review"
            description="New reviewable activity will appear here when it is created."
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
