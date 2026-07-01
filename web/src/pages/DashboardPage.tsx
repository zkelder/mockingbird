import type {
  AnalyticsSummary,
  DatasetCoverageSummary,
  DatasetExport,
  DatasetQualitySummary,
  HealthStatus,
  ModelReadinessSummary,
  ReviewQueueItem,
  Stream,
} from "../api/types";
import { DatasetCoveragePanel } from "../components/DatasetCoveragePanel";
import { DatasetQualityPanel } from "../components/DatasetQualityPanel";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { taxonomyKey } from "../components/taxonomy";
import { formatLabel, sortedEntries } from "../utils";

interface DashboardPageProps {
  health: HealthStatus | null;
  streams: Stream[];
  analytics: AnalyticsSummary | null;
  datasetCoverage: DatasetCoverageSummary | null;
  datasetQuality: DatasetQualitySummary | null;
  modelReadiness: ModelReadinessSummary | null;
  reviewQueue: ReviewQueueItem[];
  exports: DatasetExport[];
  onOpenStream: (streamId: string) => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onOpenImport: () => void;
  onOpenDetectionProposals: () => void;
  onOpenModelAdapters: () => void;
}

export function DashboardPage({
  health,
  streams,
  analytics,
  datasetCoverage,
  datasetQuality,
  modelReadiness,
  reviewQueue,
  exports,
  onOpenStream,
  onOpenReview,
  onOpenExports,
  onOpenImport,
  onOpenDetectionProposals,
  onOpenModelAdapters,
}: DashboardPageProps) {
  const mainStream = streams[0];
  const latestExport = exports[exports.length - 1];
  const topSpecies = analytics ? sortedEntries(analytics.species_counts).slice(0, 4) : [];
  const topZones = analytics ? sortedEntries(analytics.zone_activity_counts).slice(0, 4) : [];
  const datasetRecordCount = exports.reduce(
    (total, datasetExport) => total + datasetExport.record_count,
    0,
  );
  const reviewedSpeciesCount = datasetCoverage
    ? datasetCoverage.reviewed_species_count
    : analytics
    ? Object.entries(analytics.species_counts).reduce(
        (total, [label, count]) => (analytics.species_label_ids.includes(label) ? total + count : total),
        0,
      )
    : 0;
  const unknownBirdCount = datasetCoverage?.unknown_bird_count ?? analytics?.species_counts.unknown_bird ?? 0;
  const unknownAnimalCount =
    datasetCoverage?.unknown_animal_count ?? analytics?.species_counts.unknown_animal ?? 0;
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
          <button className="secondary-action" onClick={onOpenModelAdapters}>
            Model adapters
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
          value={datasetCoverage?.needs_review_count ?? birdSpeciesReviewCount}
          detail="items to resolve"
        />
        <MetricCard label="Reviewed species" value={reviewedSpeciesCount} detail="local truth" />
        <MetricCard label="Unknown birds" value={unknownBirdCount} detail="needs species detail" />
        <MetricCard label="Unknown animals" value={unknownAnimalCount} detail="needs label review" />
      </section>

      <DatasetCoveragePanel
        coverage={datasetCoverage}
        onOpenExports={onOpenExports}
        onOpenReview={onOpenReview}
        variant="compact"
      />

      <DatasetQualityPanel
        quality={datasetQuality}
        onOpenExports={onOpenExports}
        onOpenReview={onOpenReview}
        variant="compact"
      />

      {modelReadiness ? (
        <section className="panel model-readiness-panel compact">
          <div className="section-heading">
            <div>
              <h2>Pre-model readiness</h2>
              <span className="meta-text">{modelReadiness.recommended_next_step}</span>
            </div>
            <StatusPill
              label={
                modelReadiness.ready_for_first_detector_spike
                  ? "Ready for first detector spike"
                  : "Readiness work remains"
              }
              tone={modelReadiness.ready_for_first_detector_spike ? "good" : "review"}
            />
          </div>
          <div className="model-readiness-grid">
            <div>
              <span className="meta-text">Reviewed / export-ready</span>
              <strong>
                {modelReadiness.reviewed_record_count} / {modelReadiness.export_ready_count}
              </strong>
            </div>
            <div>
              <span className="meta-text">QA issues / high</span>
              <strong>
                {modelReadiness.dataset_quality_issue_count} / {modelReadiness.high_quality_issue_count}
              </strong>
            </div>
            <div>
              <span className="meta-text">Species coverage</span>
              <strong>
                {modelReadiness.covered_target_species_count} / {modelReadiness.target_species_count}
              </strong>
            </div>
            <div>
              <span className="meta-text">Adapter evidence</span>
              <strong>
                {modelReadiness.adapter_reviewed_count} / {modelReadiness.adapter_proposal_count}
              </strong>
            </div>
          </div>
          <p className="meta-text">
            Evidence stays separate from truth. Corrected labels are dataset truth; this panel does
            not run ML.
          </p>
          <div className="detail-actions">
            <button className="secondary-action" onClick={onOpenReview}>
              Review Queue
            </button>
            <button className="secondary-action" onClick={onOpenExports}>
              Dataset Exports
            </button>
            <button className="secondary-action" onClick={onOpenModelAdapters}>
              Model Adapters
            </button>
          </div>
        </section>
      ) : null}

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
          Future detector hooks create proposal evidence under the product loop. Accept proposal
          evidence into reviewable events and visits, then correct labels before analytics or exports
          treat them as truth.
        </span>
        <div className="detail-actions">
          <button className="secondary-action" onClick={onOpenModelAdapters}>
            Open Model Adapters
          </button>
          <button className="secondary-action" onClick={onOpenDetectionProposals}>
            Open Detection Proposals
          </button>
        </div>
      </section>
    </div>
  );
}
