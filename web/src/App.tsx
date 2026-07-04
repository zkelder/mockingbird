import { useEffect, useMemo, useState } from "react";
import { apiClient } from "./api/client";
import type {
  AnalyticsSummary,
  CameraSource,
  DatasetCoverageSummary,
  DatasetExport,
  DatasetQualitySummary,
  HealthStatus,
  ModelReadinessSummary,
  ReviewCorrectionResult,
  ReviewQueueItem,
  SpeciesSuggestion,
  Stream,
} from "./api/types";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ClassifierManifestPage } from "./pages/ClassifierManifestPage";
import { ClassifierReadinessPage } from "./pages/ClassifierReadinessPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DetectionProposalsPage } from "./pages/DetectionProposalsPage";
import { EventDetailPage } from "./pages/EventDetailPage";
import { ExportsPage } from "./pages/ExportsPage";
import { FolderImportPage } from "./pages/FolderImportPage";
import { LocalDataPage } from "./pages/LocalDataPage";
import { ManualImportPage } from "./pages/ManualImportPage";
import { ModelAdaptersPage } from "./pages/ModelAdaptersPage";
import { MotionEvidenceDetailPage } from "./pages/MotionEvidenceDetailPage";
import { MotionEvidencePage } from "./pages/MotionEvidencePage";
import {
  ReviewQueuePage,
  type ReviewQueueInitialContext,
} from "./pages/ReviewQueuePage";
import { SavedMediaRetentionPage } from "./pages/SavedMediaRetentionPage";
import { SpeciesSuggestionsPage } from "./pages/SpeciesSuggestionsPage";
import { StreamDetailPage } from "./pages/StreamDetailPage";
import { StreamsPage } from "./pages/StreamsPage";
import { VisitDetailPage } from "./pages/VisitDetailPage";
import { WorkerStatusPage } from "./pages/WorkerStatusPage";

type Page =
  | "dashboard"
  | "streams"
  | "import"
  | "folder-import"
  | "model-adapters"
  | "detection-proposals"
  | "motion-evidence"
  | "motion-evidence-detail"
  | "species-suggestions"
  | "classifier-readiness"
  | "classifier-manifest"
  | "stream-detail"
  | "event-detail"
  | "visit-detail"
  | "review"
  | "analytics"
  | "exports"
  | "saved-media-retention"
  | "worker-status"
  | "settings";

interface AppData {
  health: HealthStatus | null;
  sources: CameraSource[];
  streams: Stream[];
  reviewQueue: ReviewQueueItem[];
  exports: DatasetExport[];
  analytics: AnalyticsSummary | null;
  datasetCoverage: DatasetCoverageSummary | null;
  datasetQuality: DatasetQualitySummary | null;
  modelReadiness: ModelReadinessSummary | null;
}

interface VisitCorrectionPrefill {
  visitId: string;
  label: string;
  speciesSuggestionId: string;
  suggestedCommonName?: string | null;
  suggestedScientificName?: string | null;
}

const initialData: AppData = {
  health: null,
  sources: [],
  streams: [],
  reviewQueue: [],
  exports: [],
  analytics: null,
  datasetCoverage: null,
  datasetQuality: null,
  modelReadiness: null,
};

const navItems: Array<{ page: Page; label: string }> = [
  { page: "dashboard", label: "Dashboard" },
  { page: "streams", label: "Streams" },
  { page: "import", label: "Import Media" },
  { page: "folder-import", label: "Folder Import" },
  { page: "model-adapters", label: "Model Adapters" },
  { page: "detection-proposals", label: "Detection Proposals" },
  { page: "motion-evidence", label: "Motion Evidence" },
  { page: "species-suggestions", label: "Species Suggestions" },
  { page: "classifier-readiness", label: "Classifier Readiness" },
  { page: "classifier-manifest", label: "Classifier Manifest" },
  { page: "review", label: "Review" },
  { page: "analytics", label: "Analytics" },
  { page: "exports", label: "Exports" },
  { page: "saved-media-retention", label: "Saved Media Retention" },
  { page: "worker-status", label: "Worker Status" },
  { page: "settings", label: "Local Data" },
];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedStreamId, setSelectedStreamId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedVisitId, setSelectedVisitId] = useState<string | null>(null);
  const [selectedMotionEvidenceId, setSelectedMotionEvidenceId] = useState<string | null>(null);
  const [reviewQueueInitialContext, setReviewQueueInitialContext] =
    useState<ReviewQueueInitialContext | null>(null);
  const [visitCorrectionPrefill, setVisitCorrectionPrefill] =
    useState<VisitCorrectionPrefill | null>(null);
  const [data, setData] = useState<AppData>(initialData);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadAppData(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const [
        health,
        sources,
        streams,
        reviewQueue,
        exports,
        analytics,
        datasetCoverage,
        datasetQuality,
        modelReadiness,
      ] = await Promise.all([
        apiClient.getHealth(),
        apiClient.getSources(),
        apiClient.getStreams(),
        apiClient.getReviewQueue(),
        apiClient.getDatasetExports(),
        apiClient.getAnalyticsSummary(),
        apiClient.getDatasetCoverageSummary(),
        apiClient.getDatasetQualitySummary(),
        apiClient.getModelReadinessSummary(),
      ]);

      setData({
        health,
        sources,
        streams,
        reviewQueue,
        exports,
        analytics,
        datasetCoverage,
        datasetQuality,
        modelReadiness,
      });
      setSelectedStreamId((current) => current ?? streams[0]?.id ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load MockingBird data.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadAppData();
  }, []);

  const selectedStream = useMemo(
    () => data.streams.find((stream) => stream.id === selectedStreamId) ?? data.streams[0],
    [data.streams, selectedStreamId],
  );

  function openStream(streamId: string) {
    setSelectedStreamId(streamId);
    setPage("stream-detail");
  }

  function openEvent(eventId: string) {
    setSelectedEventId(eventId);
    setPage("event-detail");
  }

  function openVisit(visitId: string, prefill?: Omit<VisitCorrectionPrefill, "visitId">) {
    setSelectedVisitId(visitId);
    setVisitCorrectionPrefill(prefill ? { visitId, ...prefill } : null);
    setPage("visit-detail");
  }

  function openMotionEvidence(motionEvidenceId: string) {
    setSelectedMotionEvidenceId(motionEvidenceId);
    setPage("motion-evidence-detail");
  }

  function openReviewQueue(context?: ReviewQueueInitialContext | null) {
    setReviewQueueInitialContext(context ?? null);
    setPage("review");
  }

  function openReviewQueueForClassifierLabel(label: string) {
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      openReviewQueue();
      return;
    }
    openReviewQueue({
      source: "classifier-readiness",
      sourceLabel: trimmedLabel,
      search: trimmedLabel,
      correctionLabel: trimmedLabel,
      status: "unreviewed",
    });
  }

  function useSpeciesSuggestionAsCorrection(suggestion: SpeciesSuggestion) {
    if (!suggestion.visit_id) {
      return;
    }
    openVisit(suggestion.visit_id, {
      label: suggestion.suggested_label,
      speciesSuggestionId: suggestion.id,
      suggestedCommonName: suggestion.suggested_common_name,
      suggestedScientificName: suggestion.suggested_scientific_name,
    });
  }

  async function createCorrection(
    item: ReviewQueueItem,
    label: string,
    notes: string,
  ): Promise<ReviewCorrectionResult> {
    // Corrections are dataset-grade user labels that refresh queue and analytics state.
    const result = await apiClient.createReviewLabel({
      target_type: item.visit_id ? "visit" : "event",
      target_id: item.visit_id ?? item.event_id ?? item.id,
      label,
      notes: notes || undefined,
    });
    await loadAppData({ showLoading: false });
    return result;
  }

  async function refreshAfterLocalReset() {
    setSelectedEventId(null);
    setSelectedVisitId(null);
    setSelectedMotionEvidenceId(null);
    setVisitCorrectionPrefill(null);
    await loadAppData({ showLoading: false });
  }

  async function refreshAfterVisitCorrection() {
    setVisitCorrectionPrefill(null);
    await loadAppData({ showLoading: false });
  }

  function renderPage() {
    if (isLoading) {
      return <div className="panel">Loading MockingBird...</div>;
    }

    if (error) {
      return (
        <div className="error-panel">
          <strong>Could not reach the MockingBird API.</strong>
          <span>{error}</span>
          <span>API base: {apiClient.baseUrl}</span>
          <button className="secondary-action" onClick={() => void loadAppData()}>
            Retry
          </button>
        </div>
      );
    }

    if (page === "dashboard") {
      return (
        <DashboardPage
          health={data.health}
          sources={data.sources}
          streams={data.streams}
          analytics={data.analytics}
          datasetCoverage={data.datasetCoverage}
          datasetQuality={data.datasetQuality}
          modelReadiness={data.modelReadiness}
          reviewQueue={data.reviewQueue}
          exports={data.exports}
          onOpenStream={openStream}
          onOpenStreams={() => setPage("streams")}
          onOpenImport={() => setPage("import")}
          onOpenMotionEvidence={() => setPage("motion-evidence")}
          onOpenSavedMediaRetention={() => setPage("saved-media-retention")}
          onOpenModelAdapters={() => setPage("model-adapters")}
          onOpenClassifierReadiness={() => setPage("classifier-readiness")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenWorkerStatus={() => setPage("worker-status")}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
        />
      );
    }

    if (page === "streams") {
      return (
        <StreamsPage
          streams={data.streams}
          sources={data.sources}
          onOpenImport={() => setPage("import")}
          onOpenStream={openStream}
        />
      );
    }

    if (page === "import") {
      return (
        <ManualImportPage
          streams={data.streams}
          sources={data.sources}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenStream={openStream}
          onOpenStreams={() => setPage("streams")}
          onOpenFolderImport={() => setPage("folder-import")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onImportComplete={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "folder-import") {
      return (
        <FolderImportPage
          streams={data.streams}
          sources={data.sources}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenStream={openStream}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onImportComplete={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "detection-proposals") {
      return (
        <DetectionProposalsPage
          streams={data.streams}
          sources={data.sources}
          onOpenImport={() => setPage("import")}
          onOpenModelAdapters={() => setPage("model-adapters")}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
          onProposalChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "model-adapters") {
      return (
        <ModelAdaptersPage
          onOpenImport={() => setPage("import")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
          onProposalChanged={() => loadAppData({ showLoading: false })}
          modelReadiness={data.modelReadiness}
        />
      );
    }

    if (page === "motion-evidence") {
      return (
        <MotionEvidencePage
          streams={data.streams}
          sources={data.sources}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenMotionEvidence={openMotionEvidence}
          onOpenReview={() => openReviewQueue()}
          onEvidenceChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "motion-evidence-detail" && selectedMotionEvidenceId) {
      return (
        <MotionEvidenceDetailPage
          motionEvidenceId={selectedMotionEvidenceId}
          sources={data.sources}
          streams={data.streams}
          onOpenMotionEvidence={() => setPage("motion-evidence")}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "species-suggestions") {
      return (
        <SpeciesSuggestionsPage
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => openReviewQueue()}
          onUseAsCorrection={useSpeciesSuggestionAsCorrection}
        />
      );
    }

    if (page === "classifier-readiness") {
      return (
        <ClassifierReadinessPage
          onOpenAnalytics={() => setPage("analytics")}
          onOpenExports={() => setPage("exports")}
          onOpenEvent={openEvent}
          onOpenReview={() => openReviewQueue()}
          onOpenReviewForLabel={openReviewQueueForClassifierLabel}
          onOpenVisit={openVisit}
          onOpenSpeciesSuggestions={() => setPage("species-suggestions")}
          onOpenClassifierManifest={() => setPage("classifier-manifest")}
        />
      );
    }

    if (page === "classifier-manifest") {
      return (
        <ClassifierManifestPage
          onOpenClassifierReadiness={() => setPage("classifier-readiness")}
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => openReviewQueue()}
        />
      );
    }

    if (page === "stream-detail" && selectedStream) {
      return (
        <StreamDetailPage
          streamId={selectedStream.id}
          reviewQueue={data.reviewQueue}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenImport={() => setPage("import")}
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => openReviewQueue()}
        />
      );
    }

    if (page === "event-detail" && selectedEventId) {
      return (
        <EventDetailPage
          eventId={selectedEventId}
          onOpenStream={openStream}
          onOpenVisit={openVisit}
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => openReviewQueue()}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenMotionEvidence={openMotionEvidence}
        />
      );
    }

    if (page === "visit-detail" && selectedVisitId) {
      return (
        <VisitDetailPage
          visitId={selectedVisitId}
          onOpenStream={openStream}
          onOpenEvent={openEvent}
          onOpenExports={() => setPage("exports")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenMotionEvidence={openMotionEvidence}
          onCorrectionSaved={refreshAfterVisitCorrection}
          correctionPrefill={visitCorrectionPrefill}
        />
      );
    }

    if (page === "review") {
      return (
        <ReviewQueuePage
          items={data.reviewQueue}
          initialContext={reviewQueueInitialContext}
          onCreateCorrection={createCorrection}
          onInitialContextConsumed={() => setReviewQueueInitialContext(null)}
          onOpenEvent={openEvent}
          onOpenExports={() => setPage("exports")}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "analytics") {
      return (
        <AnalyticsPage
          analytics={data.analytics}
          datasetCoverage={data.datasetCoverage}
          datasetQuality={data.datasetQuality}
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => openReviewQueue()}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenStream={selectedStream ? () => openStream(selectedStream.id) : undefined}
        />
      );
    }

    if (page === "exports") {
      return (
        <ExportsPage
          exports={data.exports}
          datasetCoverage={data.datasetCoverage}
          datasetQuality={data.datasetQuality}
          onOpenReview={() => openReviewQueue()}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onExportsChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "saved-media-retention") {
      return <SavedMediaRetentionPage />;
    }

    if (page === "worker-status") {
      return <WorkerStatusPage />;
    }

    return (
      <LocalDataPage
        onOpenDashboard={() => setPage("dashboard")}
        onOpenImport={() => setPage("import")}
        onOpenStreams={() => setPage("streams")}
        onOpenReview={() => openReviewQueue()}
        onOpenExports={() => setPage("exports")}
        onOpenDetectionProposals={() => setPage("detection-proposals")}
        onResetComplete={refreshAfterLocalReset}
      />
      );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark">MB</span>
          <div>
            <strong>MockingBird</strong>
            <span>Outdoor video intelligence</span>
          </div>
        </div>
        <nav className="nav-list" aria-label="Product navigation">
          <span className="nav-section-label">Product loop</span>
          {navItems.map((item) => (
            <button
              className={page === item.page ? "nav-item active" : "nav-item"}
              key={item.page}
              onClick={() => setPage(item.page)}
            >
              {item.label}
            </button>
          ))}
          {selectedStream || selectedEventId || selectedVisitId ? (
            <span className="nav-section-label">Current context</span>
          ) : null}
          {selectedStream ? (
            <button
              className={page === "stream-detail" ? "nav-item active" : "nav-item"}
              onClick={() => openStream(selectedStream.id)}
            >
              Stream Detail
            </button>
          ) : null}
          {selectedEventId ? (
            <button
              className={page === "event-detail" ? "nav-item active" : "nav-item"}
              onClick={() => openEvent(selectedEventId)}
            >
              Event Detail
            </button>
          ) : null}
          {selectedVisitId ? (
            <button
              className={page === "visit-detail" ? "nav-item active" : "nav-item"}
              onClick={() => openVisit(selectedVisitId)}
            >
              Visit Detail
            </button>
          ) : null}
        </nav>
        <div className="sidebar-footer">
          <span>Local API</span>
          <strong>{apiClient.baseUrl}</strong>
        </div>
      </aside>
      <main className="main-content">{renderPage()}</main>
    </div>
  );
}
