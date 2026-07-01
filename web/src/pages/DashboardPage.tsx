import type { AnalyticsSummary, HealthStatus, ReviewQueueItem, Stream } from "../api/types";
import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { formatLabel, sortedEntries } from "../utils";

interface DashboardPageProps {
  health: HealthStatus | null;
  streams: Stream[];
  analytics: AnalyticsSummary | null;
  reviewQueue: ReviewQueueItem[];
  onOpenStream: (streamId: string) => void;
}

export function DashboardPage({
  health,
  streams,
  analytics,
  reviewQueue,
  onOpenStream,
}: DashboardPageProps) {
  const mainStream = streams[0];
  const topSpecies = analytics ? sortedEntries(analytics.species_counts).slice(0, 4) : [];
  const topZones = analytics ? sortedEntries(analytics.zone_activity_counts).slice(0, 4) : [];

  return (
    <div className="page-stack">
      <section className="dashboard-hero">
        <div>
          <StatusPill
            label={health?.status === "ok" ? "API connected" : "API unavailable"}
            tone={health?.status === "ok" ? "good" : "review"}
          />
          <h1>Backyard streams, reviewable outdoor activity, local knowledge.</h1>
        </div>
        {mainStream ? (
          <button className="primary-action" onClick={() => onOpenStream(mainStream.id)}>
            Open main stream
          </button>
        ) : null}
      </section>

      <section className="metric-grid">
        <MetricCard label="Streams" value={streams.length} detail="outdoor views" />
        <MetricCard label="Events" value={analytics?.event_count ?? 0} detail="detected activity" />
        <MetricCard label="Visits" value={analytics?.visit_count ?? 0} detail="animal-centered" />
        <MetricCard
          label="Needs review"
          value={analytics?.needs_review_count ?? reviewQueue.length}
          detail="labels to confirm"
        />
      </section>

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Top labels</h2>
          </div>
          <div className="list-stack">
            {topSpecies.map(([label, count]) => (
              <div className="summary-row" key={label}>
                <span>{formatLabel(label)}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <div className="section-heading">
            <h2>Zone activity</h2>
          </div>
          <div className="list-stack">
            {topZones.map(([zoneId, count]) => (
              <div className="summary-row" key={zoneId}>
                <span>{formatLabel(zoneId.replace("zone-", ""))}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
