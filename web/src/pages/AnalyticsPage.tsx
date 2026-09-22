import type {
  ActivityLibraryFilters,
  AnalyticsSummary,
  DatasetCoverageSummary,
  DatasetQualitySummary,
  CameraSource,
  Stream,
} from "../api/types";
import { DatasetCoveragePanel } from "../components/DatasetCoveragePanel";
import { DatasetQualityPanel } from "../components/DatasetQualityPanel";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { WildlifeInsightsPanel } from "../components/WildlifeInsightsPanel";
import { ZoneInsightsPanel } from "../components/ZoneInsightsPanel";
import { formatLabel, sortedEntries } from "../utils";

interface AnalyticsPageProps {
  analytics: AnalyticsSummary | null;
  sources: CameraSource[];
  streams: Stream[];
  datasetCoverage: DatasetCoverageSummary | null;
  datasetQuality: DatasetQualitySummary | null;
  onOpenExports: () => void;
  onOpenReview: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  // Retained for the App-level call site; Detection Proposals is a
  // developer surface and no longer linked from this page's header.
  onOpenDetectionProposals?: () => void;
  onOpenStream?: (streamId?: string) => void;
  onOpenActivityLibrary: (filters: ActivityLibraryFilters) => void;
  onOpenBirdLog: () => void;
}

export function AnalyticsPage({
  analytics,
  sources,
  streams,
  datasetCoverage,
  datasetQuality,
  onOpenExports,
  onOpenReview,
  onOpenEvent,
  onOpenVisit,
  onOpenStream,
  onOpenActivityLibrary,
  onOpenBirdLog,
}: AnalyticsPageProps) {
  if (!analytics) {
    return <div className="panel">Insights are unavailable.</div>;
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
        eyebrow="Patterns at this place"
        title="Insights"
        description="What has visited, how often, and where — counted from activity recorded here and from what you have confirmed."
        actions={
          <>
            {analytics.needs_review_count > 0 ? (
              <button className="secondary-action" onClick={onOpenReview}>
                Review needed items
              </button>
            ) : null}
            <button className="text-action" onClick={onOpenExports} type="button">
              Exports
            </button>
          </>
        }
      />
      <WildlifeInsightsPanel
        onOpenActivityLibrary={onOpenActivityLibrary}
        onOpenBirdLog={onOpenBirdLog}
        onOpenReview={onOpenReview}
        onOpenStream={(streamId) => onOpenStream?.(streamId)}
        onOpenStreams={() => onOpenStream?.()}
        onOpenVisit={onOpenVisit}
      />
      <ZoneInsightsPanel
        sources={sources}
        streams={streams}
        onOpenActivityLibrary={onOpenActivityLibrary}
      />
      {/* UI/UX & First-Run Adoption v1: these totals are all-time, while the
          panels above are range-scoped — the page read as if it contradicted
          itself ("No activity in this range" above "Visits 2"). */}
      <div className="section-heading analytics-alltime-heading">
        <div>
          <h2>All time at this place</h2>
          <span className="meta-text">Every recorded visit, not just the range above</span>
        </div>
      </div>
      <section className="metric-grid">
        <MetricCard label="Activity sessions" value={analytics.event_count} detail="times something was active" />
        <MetricCard label="Visits" value={analytics.visit_count} detail="individual animal visits" />
        <MetricCard
          label="Waiting for you"
          value={analytics.needs_review_count}
          detail="visits to confirm"
        />
        <MetricCard
          label="Active zones"
          value={Object.keys(analytics.zone_activity_counts).length}
          detail="have recorded activity"
        />
      </section>
      <section className="metric-grid">
        <MetricCard
          label="Species you confirmed"
          value={reviewedSpeciesTotal}
          detail="distinct confirmed species"
        />
        <MetricCard label="Birds, species unknown" value={unknownBirdCount} detail="confirmed as a bird" />
        <MetricCard label="Wildlife, kind unknown" value={unknownAnimalCount} detail="confirmed as wildlife" />
        <MetricCard label="Not wildlife" value={falsePositiveCount} detail="ruled out by you" />
      </section>
      <section className="notice-panel">
        <strong>What you confirm shapes these numbers</strong>
        <span>Species counts come from visits you have confirmed or corrected, never from a model's guess alone.</span>
      </section>
      {/* UI/UX & First-Run Adoption v1: dataset/model-readiness material is
          real and useful, but it is export preparation, not nature insight --
          collapsed so Insights reads as a place page by default. */}
      <details className="panel analytics-dataset-readiness">
        <summary>Dataset readiness (for exports and model work)</summary>
        <div className="page-stack">
          <DatasetCoveragePanel
            coverage={datasetCoverage}
            onOpenExports={onOpenExports}
            onOpenReview={onOpenReview}
          />
          <DatasetQualityPanel
            quality={datasetQuality}
            onOpenEvent={onOpenEvent}
            onOpenExports={onOpenExports}
            onOpenVisit={onOpenVisit}
            onOpenReview={onOpenReview}
          />
        </div>
      </details>
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
                description="Reviewed corrections will appear here."
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
                description="Draw zones on a stream, create reviewable activity, then correct Visits before zone activity becomes useful analytics."
                action={
                  onOpenStream ? (
                    <button className="secondary-action" onClick={() => onOpenStream()}>
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
