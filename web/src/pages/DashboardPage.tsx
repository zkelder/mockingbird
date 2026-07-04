import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  AnalyticsSummary,
  CameraSource,
  DatasetCoverageSummary,
  DatasetExport,
  DatasetQualitySummary,
  HealthStatus,
  ModelReadinessSummary,
  ReviewQueueItem,
  SourceSetupReviewResponse,
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
  sources: CameraSource[];
  streams: Stream[];
  analytics: AnalyticsSummary | null;
  datasetCoverage: DatasetCoverageSummary | null;
  datasetQuality: DatasetQualitySummary | null;
  modelReadiness: ModelReadinessSummary | null;
  reviewQueue: ReviewQueueItem[];
  exports: DatasetExport[];
  onOpenStream: (streamId: string) => void;
  onOpenStreams: () => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onOpenImport: () => void;
  onOpenMotionEvidence: () => void;
  onOpenSavedMediaRetention: () => void;
  onOpenDetectionProposals: () => void;
  onOpenModelAdapters: () => void;
  onOpenClassifierReadiness: () => void;
}

type SourceWorkflowRoute = "import" | "stream-detail" | "streams";

interface SourceWorkflow {
  source: CameraSource;
  providerLabel: string;
  readinessLabel: string;
  readinessTone: "good" | "review" | "quiet";
  summary: string;
  streamCount: number;
  livePlaybackLabel: string;
  zoneEditingLabel: string;
  nextActionLabel: string;
  nextActionDetail: string;
  actionLabel: string;
  actionRoute: SourceWorkflowRoute;
  streamId?: string;
}

function readinessTone(
  readinessLevel?: SourceSetupReviewResponse["readiness_level"],
): "good" | "review" | "quiet" {
  if (readinessLevel === "demo_ready" || readinessLevel === "metadata_ready") {
    return "good";
  }
  if (readinessLevel === "needs_setup" || readinessLevel === "unavailable") {
    return "review";
  }
  return "quiet";
}

function providerFallbackLabel(source: CameraSource): string {
  if (source.kind === "demo") {
    return "Demo";
  }
  if (source.kind === "manual_upload") {
    return "Manual media";
  }
  if (source.kind === "local_folder") {
    return "Folder / trail-cam import";
  }
  return "Demo/future";
}

function buildSourceWorkflow(
  source: CameraSource,
  review: SourceSetupReviewResponse | undefined,
  sourceStreams: Stream[],
): SourceWorkflow {
  const providerKey = review?.provider_key ?? source.kind;
  const sourceStream = sourceStreams[0] ?? null;
  const readinessLabel = review ? formatLabel(review.readiness_level) : "Loading";
  const streamCount = review?.stream_count ?? sourceStreams.length;
  const livePlaybackLabel = review
    ? providerKey === "external_url" || providerKey === "folder_import_future"
      ? "Live playback not implemented for this provider"
      : review.supports_live_playback
        ? "Available"
        : "Not implemented"
    : "Loading";
  const zoneEditingLabel = review
    ? review.supports_zone_editing
      ? "Available"
      : "Unavailable"
    : "Loading";
  let nextActionLabel = "Review Source setup";
  let nextActionDetail = "Load provider workflow status before taking provider action.";
  let actionLabel = "Open Streams";
  let actionRoute: SourceWorkflowRoute = "streams";
  let streamId: string | undefined;

  if (review?.readiness_level === "needs_setup") {
    nextActionLabel = "Complete Source setup";
    nextActionDetail = "Open Streams to finish provider metadata before any provider workflow.";
  } else if (providerKey === "external_url" && review) {
    nextActionLabel = "Explicit preview";
    nextActionDetail =
      "Open Streams to fetch still-image preview, save as MediaAsset, then create Pending evidence when useful.";
  } else if (providerKey === "folder_import_future" && review) {
    nextActionLabel = "Import as MediaAssets";
    nextActionDetail =
      "Open Streams to preview folder import explicitly, then import selected files as MediaAssets. Correction remains truth.";
  } else if (providerKey === "manual_media" && review) {
    nextActionLabel = "Import media";
    nextActionDetail =
      "Use Import Media for explicit local media import. Correction remains truth.";
    actionLabel = "Import Media";
    actionRoute = "import";
  } else if (review?.readiness_level === "demo_ready") {
    nextActionLabel = "Open Stream Detail";
    nextActionDetail = "Open Stream Detail and draw Zones before reviewing activity.";
    actionLabel = sourceStream ? "Open Stream Detail" : "Open Streams";
    actionRoute = sourceStream ? "stream-detail" : "streams";
    streamId = sourceStream?.id;
  } else if (review) {
    nextActionDetail = review.next_step || "Open Streams to review provider workflow.";
  }

  return {
    source,
    providerLabel: review?.provider_display_name ?? providerFallbackLabel(source),
    readinessLabel,
    readinessTone: readinessTone(review?.readiness_level),
    summary: review?.summary ?? source.description,
    streamCount,
    livePlaybackLabel,
    zoneEditingLabel,
    nextActionLabel,
    nextActionDetail,
    actionLabel,
    actionRoute,
    streamId,
  };
}

export function DashboardPage({
  health,
  sources,
  streams,
  analytics,
  datasetCoverage,
  datasetQuality,
  modelReadiness,
  reviewQueue,
  exports,
  onOpenStream,
  onOpenStreams,
  onOpenReview,
  onOpenExports,
  onOpenImport,
  onOpenMotionEvidence,
  onOpenSavedMediaRetention,
  onOpenDetectionProposals,
  onOpenModelAdapters,
  onOpenClassifierReadiness,
}: DashboardPageProps) {
  const [sourceSetupReviews, setSourceSetupReviews] = useState<
    Record<string, SourceSetupReviewResponse>
  >({});
  const [sourceSetupError, setSourceSetupError] = useState<string | null>(null);
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
  const streamsBySource = useMemo(() => {
    const next = new Map<string, Stream[]>();
    for (const stream of streams) {
      const sourceStreams = next.get(stream.source_id) ?? [];
      sourceStreams.push(stream);
      next.set(stream.source_id, sourceStreams);
    }
    return next;
  }, [streams]);
  const sourceWorkflows = useMemo(
    () =>
      sources.map((source) =>
        buildSourceWorkflow(
          source,
          sourceSetupReviews[source.id],
          streamsBySource.get(source.id) ?? [],
        ),
      ),
    [sources, sourceSetupReviews, streamsBySource],
  );

  useEffect(() => {
    let isMounted = true;

    async function loadSourceSetupReviews() {
      if (sources.length === 0) {
        setSourceSetupReviews({});
        setSourceSetupError(null);
        return;
      }

      setSourceSetupError(null);
      try {
        const entries = await Promise.all(
          sources.map(async (source) => [
            source.id,
            await apiClient.getSourceSetupReview(source.id),
          ] as const),
        );
        if (isMounted) {
          setSourceSetupReviews(Object.fromEntries(entries));
        }
      } catch (caught) {
        if (isMounted) {
          setSourceSetupError(
            caught instanceof Error ? caught.message : "Could not load provider workflow status.",
          );
        }
      }
    }

    void loadSourceSetupReviews();

    return () => {
      isMounted = false;
    };
  }, [sources]);

  function handleWorkflowAction(workflow: SourceWorkflow) {
    if (workflow.actionRoute === "import") {
      onOpenImport();
      return;
    }
    if (workflow.actionRoute === "stream-detail" && workflow.streamId) {
      onOpenStream(workflow.streamId);
      return;
    }
    onOpenStreams();
  }

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

      <section className="panel source-provider-status-panel">
        <div className="section-heading">
          <div>
            <h2>Source provider status</h2>
            <span className="meta-text">
              Provider workflow readiness, live playback status, and next safe actions
            </span>
          </div>
          <StatusPill
            label={`${sources.length} Source${sources.length === 1 ? "" : "s"}`}
            tone={sources.length > 0 ? "good" : "review"}
          />
        </div>
        {sourceSetupError ? <div className="error-panel compact-error">{sourceSetupError}</div> : null}
        {sourceWorkflows.length > 0 ? (
          <div className="provider-workflow-grid">
            {sourceWorkflows.map((workflow) => (
              <article className="provider-workflow-card" key={workflow.source.id}>
                <div className="item-title-row">
                  <div className="provider-workflow-summary">
                    <h3>{workflow.source.name}</h3>
                    <span>{workflow.summary}</span>
                  </div>
                  <StatusPill label={workflow.readinessLabel} tone={workflow.readinessTone} />
                </div>
                <div className="source-overview-grid provider-workflow-facts">
                  <div>
                    <span>Provider workflow</span>
                    <strong>{workflow.providerLabel}</strong>
                  </div>
                  <div>
                    <span>Streams</span>
                    <strong>{workflow.streamCount}</strong>
                  </div>
                  <div>
                    <span>Live playback</span>
                    <strong>{workflow.livePlaybackLabel}</strong>
                  </div>
                  <div>
                    <span>Zone editing</span>
                    <strong>{workflow.zoneEditingLabel}</strong>
                  </div>
                </div>
                <div className="provider-workflow-next">
                  <div>
                    <span>Next action</span>
                    <strong>{workflow.nextActionLabel}</strong>
                    <small>{workflow.nextActionDetail}</small>
                  </div>
                  <button
                    className="secondary-action"
                    onClick={() => handleWorkflowAction(workflow)}
                    type="button"
                  >
                    {workflow.actionLabel}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No Sources configured"
            description="Open Streams to review Source setup before provider workflows."
            action={
              <button className="secondary-action" onClick={onOpenStreams} type="button">
                Open Streams
              </button>
            }
          />
        )}
        <div className="detail-actions">
          <button className="secondary-action" onClick={onOpenStreams} type="button">
            Streams
          </button>
          <button className="secondary-action" onClick={onOpenMotionEvidence} type="button">
            Motion Evidence
          </button>
          <button className="secondary-action" onClick={onOpenSavedMediaRetention} type="button">
            Saved Media Retention
          </button>
          <button className="secondary-action" onClick={onOpenReview} type="button">
            Review Queue
          </button>
        </div>
        <p className="meta-text">
          Dashboard uses read-only Source setup review. It does not fetch URLs, scan folders,
          create media, create evidence, or create truth.
        </p>
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
            <button className="secondary-action" onClick={onOpenClassifierReadiness}>
              Classifier Readiness
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
