import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type {
  DashboardSummary,
  DashboardVisitSummary,
  CameraHealthSummary,
  HealthStatus,
  PlaceActivityReportResponse,
  StorageSummary,
  StreamRuntimeStatus,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { LiveCameraOverview } from "../components/LiveCameraOverview";
import { ProductHealthPanel } from "../components/ProductHealthPanel";
import { StatusPill } from "../components/StatusPill";
import { TodayReportPanel } from "../components/TodayReportPanel";
import {
  cameraHealthLabel,
  cameraHealthTone,
  effectiveSpeciesText,
  formatDateTime,
  formatLabel,
  unconfirmedActivityText,
} from "../utils";

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

// The Place Activity Report is period-scoped; "today" is the browser's own
// local midnight-to-midnight span, converted to the UTC instants the report
// API expects. MockingBird has no per-Place timezone setting (see "Local
// time and DST correctness" in docs/place-activity-report-contract.md), so
// this mirrors what a normal user means by "today" on the device in front
// of them; the report's own per-Visit hour bucketing still resolves this
// single-site install's actual host timezone independently.
function todayLocalRange(): { start_at: string; end_at: string } {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start_at: start.toISOString(), end_at: end.toISOString() };
}

// cameraHealthLabel/cameraHealthTone now live in ../utils (First-Hour
// Onboarding + Whole-Product Observability Closure v1, "B7 health model")
// -- shared with Yard & Camera Map so the same CameraHealthState can never
// show a different label/tone on two different pages again.

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
  // Acoustic / BirdNET Observation Foundation v1: audio evidence has no
  // visual thumbnail to show here -- an honest "heard, not seen" icon,
  // never a fabricated image standing in for it. Full playback is
  // available from Visit Detail.
  if (visit.primary_evidence.content_type.startsWith("audio/")) {
    return (
      <div className="dashboard-visit-preview dashboard-preview-audio" aria-label="Heard, no image evidence">
        🔊
      </div>
    );
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
  const [report, setReport] = useState<PlaceActivityReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [monitorActionError, setMonitorActionError] = useState<string | null>(null);
  const [durableStatusByStream, setDurableStatusByStream] = useState<
    Record<string, StreamRuntimeStatus>
  >({});
  const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);

  const refreshDashboard = useCallback(async (initialLoad = false) => {
    if (initialLoad) {
      setIsLoading(true);
    } else {
      setIsRefreshing(true);
    }
    try {
      const [nextSummary, monitoringStatuses, nextStorageSummary, nextReport] = await Promise.all([
        apiClient.getDashboardSummary(),
        apiClient.getStreamMonitoringStatuses().catch(() => null),
        apiClient.getStorageRetentionSummary().catch(() => null),
        apiClient.getPlaceActivityReport(todayLocalRange()).catch(() => null),
      ]);
      setSummary(nextSummary);
      setStorageSummary(nextStorageSummary);
      setReport(nextReport);
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

  const { today } = summary;
  return (
    <div className="page-stack dashboard-operations-page">
      <section className="dashboard-hero dashboard-operations-hero">
        <div>
          <StatusPill
            label={health?.status === "ok" ? "Local app connected" : "Local status unavailable"}
            tone={health?.status === "ok" ? "good" : "review"}
          />
          <h1>Today in Your Yard</h1>
          <p>
            What visited, how often, and where — for {summary.local_day}.
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

      <ProductHealthPanel />

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

      <TodayReportPanel
        configuredStreamCount={summary.headline.configured_stream_count}
        isLoading={isLoading}
        monitoredStreamCount={summary.headline.monitored_stream_count}
        onAddCamera={onAddCamera}
        onOpenBirdLog={onOpenBirdLog}
        onOpenReview={() => onOpenReview()}
        onOpenStreams={onOpenStreams}
        report={report}
      />

      <section aria-label="Recent highlights" className="page-stack">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Best moments</h2>
              <span className="meta-text">Evidence-backed animal Visits, with reviewed wildlife first</span>
            </div>
          </div>
          {today.best_moments.length > 0 ? (
            <div className="dashboard-visit-list">
              {today.best_moments.map((visit) => (
                <article className="dashboard-visit-row" key={visit.id}>
                  <VisitPreview visit={visit} />
                  <div>
                    <strong>
                      {effectiveSpeciesText(visit) ??
                        unconfirmedActivityText(visit.primary_evidence?.content_type)}
                    </strong>
                    <VisitContext visit={visit} />
                    <span className="meta-text">{formatDateTime(visit.captured_at)}</span>
                  </div>
                  <button className="text-action" onClick={() => onOpenVisit(visit.id)} type="button">View</button>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No animal Visits yet today" description="New evidence-backed animal activity will appear here." />
          )}
        </section>

        <section className="dashboard-observation-grid dashboard-secondary-section">
          <section className="panel">
            <div className="section-heading"><div><h2>New today</h2><span className="meta-text">First confirmed here today</span></div></div>
            {today.new_today.length > 0 ? today.new_today.map((species) => (
              <article className="dashboard-observation-row" key={species.label}>
                <VisitPreview visit={species.latest_visit} /><div><strong>{species.display_name}</strong><span>First confirmed here today</span></div>
                <button className="text-action" onClick={() => onOpenVisit(species.latest_visit.id)} type="button">View</button>
              </article>
            )) : <EmptyState title="No new confirmed species today" description="Species appear here only after a reviewed correction." />}
          </section>
          <section className="panel">
            <div className="section-heading"><div><h2>Recent regulars</h2><span className="meta-text">Reviewed species active on at least 3 of the last 14 days</span></div></div>
            {today.recent_regulars.length > 0 ? today.recent_regulars.map((species) => (
              <article className="dashboard-observation-row" key={species.label}>
                <VisitPreview visit={species.latest_visit} /><div><strong>{species.display_name}</strong><span>Seen on {species.distinct_days_seen} of the last 14 days</span></div>
                <button className="text-action" onClick={() => onOpenVisit(species.latest_visit.id)} type="button">View</button>
              </article>
            )) : <EmptyState title="No regular species yet" description="Regulars appear after reviewed occurrences on three different local days." />}
          </section>
        </section>
      </section>

      {monitorActionError ? <div className="dashboard-action-error" role="alert">{monitorActionError}</div> : null}
      {today.observation_health.length > 0 ? (
        <section className="panel dashboard-camera-attention" aria-label="Cameras needing attention">
          <div className="section-heading">
            <div>
              <h2>Cameras needing attention</h2>
              <span className="meta-text">Compact observation-health facts from enabled Streams</span>
            </div>
            <StatusPill label={`${today.observation_health.length} needs attention`} tone="review" />
          </div>
          <div className="dashboard-visit-list">
            {today.observation_health.map((camera) => (
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
