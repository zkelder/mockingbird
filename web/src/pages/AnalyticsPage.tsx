import type { AnalyticsSummary } from "../api/types";
import { MetricCard } from "../components/MetricCard";
import { formatLabel, sortedEntries } from "../utils";

interface AnalyticsPageProps {
  analytics: AnalyticsSummary | null;
}

export function AnalyticsPage({ analytics }: AnalyticsPageProps) {
  if (!analytics) {
    return <div className="panel">Analytics are unavailable.</div>;
  }

  return (
    <div className="page-stack">
      <div className="section-heading">
        <h1>Analytics</h1>
      </div>
      <section className="metric-grid">
        <MetricCard label="Events" value={analytics.event_count} detail="outdoor activity" />
        <MetricCard label="Visits" value={analytics.visit_count} detail="animal visits" />
        <MetricCard label="Needs review" value={analytics.needs_review_count} detail="correction work" />
      </section>
      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Species and labels</h2>
          </div>
          <div className="bar-list">
            {sortedEntries(analytics.species_counts).map(([label, count]) => (
              <div className="bar-row" key={label}>
                <span>{formatLabel(label)}</span>
                <div>
                  <i style={{ width: `${Math.max(10, count * 35)}px` }} />
                  <strong>{count}</strong>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <div className="section-heading">
            <h2>Zone activity</h2>
          </div>
          <div className="bar-list">
            {sortedEntries(analytics.zone_activity_counts).map(([zoneId, count]) => (
              <div className="bar-row" key={zoneId}>
                <span>{formatLabel(zoneId.replace("zone-", ""))}</span>
                <div>
                  <i style={{ width: `${Math.max(10, count * 35)}px` }} />
                  <strong>{count}</strong>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
