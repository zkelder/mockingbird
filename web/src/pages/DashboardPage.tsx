import type {
  AnalyticsSummary,
  DatasetExport,
  HealthStatus,
  ReviewQueueItem,
  Stream,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { taxonomyKey } from "../components/taxonomy";
import { formatLabel, sortedEntries } from "../utils";

interface DashboardPageProps {
  health: HealthStatus | null;
  streams: Stream[];
  analytics: AnalyticsSummary | null;
  reviewQueue: ReviewQueueItem[];
  exports: DatasetExport[];
  onOpenStream: (streamId: string) => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onOpenImport: () => void;
  onOpenDetectionProposals: () => void;
}

export function DashboardPage({
  health,
  streams,
  analytics,
  reviewQueue,
  exports,
  onOpenStream,
  onOpenReview,
  onOpenExports,
  onOpenImport,
  onOpenDetectionProposals,
}: DashboardPageProps) {
  const mainStream = streams[0];
  const latestExport = exports[exports.length - 1];
  const topSpecies = analytics ? sortedEntries(analytics.species_counts).slice(0, 4) : [];
  const topZones = analytics ? sortedEntries(analytics.zone_activity_counts).slice(0, 4) : [];
  const datasetRecordCount = exports.reduce(
    (total, datasetExport) => total + datasetExport.record_count,
    0,
  );
  const reviewedSpeciesCount = analytics
    ? Object.entries(analytics.species_counts).reduce(
        (total, [label, count]) => (analytics.species_label_ids.includes(label) ? total + count : total),
        0,
      )
    : 0;
  const unknownBirdCount = analytics?.species_counts.unknown_bird ?? 0;
  const unknownAnimalCount = analytics?.species_counts.unknown_animal ?? 0;
  const birdSpeciesReviewCount = reviewQueue.filter((item) => {
    const label = taxonomyKey(item.suggested_label ?? "");
    return label === "bird" || label === "unknown_bird" || Boolean(analytics?.species_label_ids.includes(label));
  }).length;

  return (
    <div className="page-stack">
      <section className="dashboard-hero">
        <div>
          <StatusPill
            label={health?.status === "ok" ? "API connected" : "API unavailable"}
            tone={health?.status === "ok" ? "good" : "review"}
          />
          <h1>Outdoor streams become reviewable events, corrections, analytics, and local datasets.</h1>
          <p>
            Start with the stream, draw context zones, confirm what happened, then export reviewed
            labels as local dataset truth.
          </p>
        </div>
        <div className="hero-actions">
          <button className="primary-action" onClick={onOpenImport}>
            Import media
          </button>
          <button className="secondary-action" onClick={onOpenDetectionProposals}>
            Detection proposals
          </button>
          {mainStream ? (
            <button className="secondary-action" onClick={() => onOpenStream(mainStream.id)}>
              Open main stream
            </button>
          ) : null}
          {reviewQueue.length > 0 ? (
            <button className="secondary-action" onClick={onOpenReview}>
              Review {reviewQueue.length} item{reviewQueue.length === 1 ? "" : "s"}
            </button>
          ) : (
            <button className="secondary-action" onClick={onOpenExports}>
              Open exports
            </button>
          )}
        </div>
      </section>

      <section className="metric-grid">
        <MetricCard label="Streams" value={streams.length} detail="video-centered outdoor views" />
        <MetricCard
          label="Needs review"
          value={analytics?.needs_review_count ?? reviewQueue.length}
          detail="labels to confirm as truth"
        />
        <MetricCard
          label="Dataset records"
          value={datasetRecordCount}
          detail={latestExport ? `latest: ${latestExport.name}` : "reviewed local exports"}
        />
        <MetricCard
          label="Events and visits"
          value={`${analytics?.event_count ?? 0}/${analytics?.visit_count ?? 0}`}
          detail="activity cases / animal visits"
        />
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Bird/species review"
          value={birdSpeciesReviewCount}
          detail="items to resolve"
        />
        <MetricCard label="Reviewed species" value={reviewedSpeciesCount} detail="local truth" />
        <MetricCard label="Unknown birds" value={unknownBirdCount} detail="needs species detail" />
        <MetricCard label="Unknown animals" value={unknownAnimalCount} detail="needs label review" />
      </section>

      <section className="notice-panel">
        <strong>Resolve species before export</strong>
        <span>
          Unknown bird visits stay in review until corrected species or labels become dataset truth
          for analytics and exports.
        </span>
        <div className="detail-actions">
          <button className="secondary-action" onClick={onOpenReview}>
            Open Review Queue
          </button>
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        </div>
      </section>

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Top labels</h2>
          </div>
          <div className="list-stack">
            {topSpecies.length > 0 ? (
              topSpecies.map(([label, count]) => (
                <div className="summary-row" key={label}>
                  <span>{analytics?.label_display_names[label] ?? formatLabel(label)}</span>
                  <strong>{count}</strong>
                </div>
              ))
            ) : (
              <EmptyState
                title="No reviewed labels yet"
                description="Review visits and events to build local label counts."
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
          <div className="list-stack">
            {topZones.length > 0 ? (
              topZones.map(([zoneId, count]) => (
                <div className="summary-row" key={zoneId}>
                  <span>{formatLabel(zoneId.replace("zone-", ""))}</span>
                  <strong>{count}</strong>
                </div>
              ))
            ) : (
              <EmptyState
                title="No zone activity yet"
                description="Zones give outdoor events the context that makes analytics useful."
                action={
                  mainStream ? (
                    <button className="secondary-action" onClick={() => onOpenStream(mainStream.id)}>
                      Open Stream Detail
                    </button>
                  ) : null
                }
              />
            )}
          </div>
        </div>
      </section>
      <section className="notice-panel">
        <strong>Detection proposals are evidence first</strong>
        <span>
          Accept proposal evidence into reviewable events and visits, then correct labels before
          analytics or exports treat them as truth.
        </span>
        <button className="secondary-action" onClick={onOpenDetectionProposals}>
          Open Detection Proposals
        </button>
      </section>
    </div>
  );
}
