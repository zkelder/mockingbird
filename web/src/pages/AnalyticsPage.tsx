import type { AnalyticsSummary, DatasetCoverageSummary, DatasetQualitySummary } from "../api/types";
import { DatasetCoveragePanel } from "../components/DatasetCoveragePanel";
import { DatasetQualityPanel } from "../components/DatasetQualityPanel";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { formatLabel, sortedEntries } from "../utils";

interface AnalyticsPageProps {
  analytics: AnalyticsSummary | null;
  datasetCoverage: DatasetCoverageSummary | null;
  datasetQuality: DatasetQualitySummary | null;
  onOpenExports: () => void;
  onOpenReview: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenDetectionProposals: () => void;
  onOpenStream?: () => void;
}

export function AnalyticsPage({
  analytics,
  datasetCoverage,
  datasetQuality,
  onOpenExports,
  onOpenReview,
  onOpenEvent,
  onOpenVisit,
  onOpenDetectionProposals,
  onOpenStream,
}: AnalyticsPageProps) {
  if (!analytics) {
    return <div className="panel">Analytics are unavailable.</div>;
  }

  const speciesEntries = sortedEntries(analytics.species_counts);
  const zoneEntries = sortedEntries(analytics.zone_activity_counts);
  const reviewedSpeciesTotal = speciesEntries.reduce(
    (total, [label, count]) => (analytics.species_label_ids.includes(label) ? total + count : total),
    0,
  );
  const unknownBirdCount = analytics.species_counts.unknown_bird ?? 0;
  const unknownAnimalCount = analytics.species_counts.unknown_animal ?? 0;
  const falsePositiveCount = analytics.species_counts.false_positive ?? 0;
  const categoryCounts = speciesEntries.reduce<Record<string, number>>((counts, [label, count]) => {
    const category = analytics.label_categories[label] ?? "custom";
    counts[category] = (counts[category] ?? 0) + count;
    return counts;
  }, {});

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
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
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
      <section className="metric-grid">
        <MetricCard
          label="Reviewed species"
          value={reviewedSpeciesTotal}
          detail="corrected bird truth"
        />
        <MetricCard label="Unknown birds" value={unknownBirdCount} detail="needs species resolution" />
        <MetricCard label="Unknown animals" value={unknownAnimalCount} detail="needs label review" />
        <MetricCard label="False positives" value={falsePositiveCount} detail="reviewed out" />
      </section>
      <section className="notice-panel">
        <strong>Reviewed imports count here</strong>
        <span>
          Manual media imports become events and visits, then corrected labels roll into these local
          summaries and dataset manifests. Corrected species is local dataset truth; detection
          proposals only count here after they become reviewable visits or events and receive corrected
          labels.
        </span>
      </section>
      <DatasetCoveragePanel
        coverage={datasetCoverage}
        onOpenExports={onOpenExports}
        onOpenReview={onOpenReview}
      />
      <DatasetQualityPanel
        quality={datasetQuality}
        onOpenEvent={onOpenEvent}
        onOpenExports={onOpenExports}
        onOpenReview={onOpenReview}
        onOpenVisit={onOpenVisit}
      />
      <section className="panel">
        <div className="section-heading">
          <h2>Label categories</h2>
          <span className="meta-text">Corrected taxonomy labels grouped for scanning</span>
        </div>
        <div className="taxonomy-category-list">
          {sortedEntries(categoryCounts).map(([category, count]) => (
            <div className="summary-row" key={category}>
              <span>{formatLabel(category)}</span>
              <strong>{count}</strong>
            </div>
          ))}
          {Object.keys(categoryCounts).length === 0 ? (
            <span className="meta-text">Review corrections will create taxonomy category counts.</span>
          ) : null}
        </div>
      </section>
      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Reviewed species and labels</h2>
          </div>
          <div className="bar-list">
            {speciesEntries.length > 0 ? (
              speciesEntries.map(([label, count]) => (
                <div className="bar-row" key={label}>
                  <span>
                    {analytics.label_display_names[label] ?? formatLabel(label)}
                    {analytics.label_categories[label] ? (
                      <EvidenceBadge
                        label={`${formatLabel(analytics.label_categories[label])}${
                          analytics.species_label_ids.includes(label) ? " reviewed species" : ""
                        }`}
                        tone="quiet"
                      />
                    ) : null}
                  </span>
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
