import type { AnalyticsSummary } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { formatLabel, sortedEntries } from "../utils";

interface AnalyticsPageProps {
  analytics: AnalyticsSummary | null;
  onOpenExports: () => void;
  onOpenReview: () => void;
  onOpenStream?: () => void;
}

export function AnalyticsPage({
  analytics,
  onOpenExports,
  onOpenReview,
  onOpenStream,
}: AnalyticsPageProps) {
  if (!analytics) {
    return <div className="panel">Analytics are unavailable.</div>;
  }

  const speciesEntries = sortedEntries(analytics.species_counts);
  const zoneEntries = sortedEntries(analytics.zone_activity_counts);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Local summaries"
        title="Analytics"
        description="Summaries come from reviewable outdoor activity and corrected labels."
        actions={
          <>
            {analytics.needs_review_count > 0 ? (
              <button className="secondary-action" onClick={onOpenReview}>
                Review needed items
              </button>
            ) : null}
            <button className="secondary-action" onClick={onOpenExports}>
              Open Dataset Exports
            </button>
          </>
        }
      />
      <section className="metric-grid">
        <MetricCard label="Events" value={analytics.event_count} detail="outdoor activity" />
        <MetricCard label="Visits" value={analytics.visit_count} detail="animal visits" />
        <MetricCard
          label="Needs review"
          value={analytics.needs_review_count}
          detail="correction work"
        />
        <MetricCard
          label="Zones"
          value={Object.keys(analytics.zone_activity_counts).length}
          detail="activity contexts"
        />
      </section>
      <section className="notice-panel">
        <strong>Reviewed imports count here</strong>
        <span>
          Manual media imports become events and visits, then corrected labels roll into these local
          summaries and dataset manifests.
        </span>
      </section>
      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Species and labels</h2>
          </div>
          <div className="bar-list">
            {speciesEntries.length > 0 ? (
              speciesEntries.map(([label, count]) => (
                <div className="bar-row" key={label}>
                  <span>{formatLabel(label)}</span>
                  <div>
                    <i style={{ width: `${Math.max(10, count * 35)}px` }} />
                    <strong>{count}</strong>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                title="No labels counted yet"
                description="Corrections will become dataset-grade labels and appear here."
                action={
                  <button className="secondary-action" onClick={onOpenReview}>
                    Open Review Queue
                  </button>
                }
              />
            )}
          </div>
        </div>
        <div className="panel">
          <div className="section-heading">
            <h2>Zone activity</h2>
          </div>
          <div className="bar-list">
            {zoneEntries.length > 0 ? (
              zoneEntries.map(([zoneId, count]) => (
                <div className="bar-row" key={zoneId}>
                  <span>{formatLabel(zoneId.replace("zone-", ""))}</span>
                  <div>
                    <i style={{ width: `${Math.max(10, count * 35)}px` }} />
                    <strong>{count}</strong>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                title="No zone activity counted"
                description="Draw zones on a stream to make future outdoor activity easier to understand."
                action={
                  onOpenStream ? (
                    <button className="secondary-action" onClick={onOpenStream}>
                      Open Stream Detail
                    </button>
                  ) : null
                }
              />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
