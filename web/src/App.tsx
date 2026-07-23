import { useEffect, useMemo, useState } from "react";
import { apiClient } from "./api/client";
import type {
  ActivityLibraryFilters,
  AnalyticsSummary,
  CameraSource,
  DatasetCoverageSummary,
  DatasetExport,
  DatasetQualitySummary,
  HealthStatus,
  ModelReadinessSummary,
  ProductAlertAction,
  ReviewCorrectionResult,
  ReviewQueueItem,
  SpeciesSuggestion,
  Stream,
} from "./api/types";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AlertsControl, AlertsInboxPage } from "./components/AlertsInbox";
import { ActivityLibraryPage, activityLibraryPath } from "./pages/ActivityLibraryPage";
import { BirdLogPage } from "./pages/BirdLogPage";
import { CameraSetupPage } from "./pages/CameraSetupPage";
import { ClassifierManifestPage } from "./pages/ClassifierManifestPage";
import { ClassifierReadinessPage } from "./pages/ClassifierReadinessPage";
import { CollectionsPage } from "./pages/CollectionsPage";
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
import {
  type AppRoute,
  type Page,
  readAppRoute,
  writeAppRoute,
} from "./navigation";

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

const productNavItems: Array<{ page: Page; label: string }> = [
  { page: "dashboard", label: "Overview" },
  { page: "streams", label: "Cameras / Streams" },
  { page: "activity-library", label: "Activity Library" },
  { page: "review", label: "Review Queue" },
  { page: "bird-log", label: "Bird Log" },
  { page: "exports", label: "Exports / Data" },
];

const advancedNavItems: Array<{ page: Page; label: string }> = [
  { page: "import", label: "Import Media" },
  { page: "folder-import", label: "Folder Import" },
  { page: "analytics", label: "Analytics" },
  { page: "saved-media-retention", label: "Saved Media Retention" },
  { page: "motion-evidence", label: "Advanced Evidence" },
  { page: "detection-proposals", label: "Detection Proposals" },
  { page: "model-adapters", label: "Analyzers" },
  { page: "species-suggestions", label: "Species Suggestions" },
  { page: "classifier-readiness", label: "Classifier Readiness" },
  { page: "classifier-manifest", label: "Classifier Manifest" },
  { page: "settings", label: "Local Data" },
];

const advancedPages = new Set<Page>([
  ...advancedNavItems.map((item) => item.page),
  "motion-evidence-detail",
]);

export default function App() {
  const [initialRoute] = useState<AppRoute>(() => readAppRoute());
  const [page, setPageState] = useState<Page>(initialRoute.page);
  const [selectedStreamId, setSelectedStreamId] = useState<string | null>(
    initialRoute.streamId ?? null,
  );
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    initialRoute.eventId ?? null,
  );
  const [selectedVisitId, setSelectedVisitId] = useState<string | null>(
    initialRoute.visitId ?? null,
  );
  const [selectedMotionEvidenceId, setSelectedMotionEvidenceId] = useState<string | null>(
    initialRoute.motionEvidenceId ?? null,
  );
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(
    initialRoute.collectionId ?? null,
  );
  const [reviewQueueInitialContext, setReviewQueueInitialContext] =
    useState<ReviewQueueInitialContext | null>(null);
  const [visitCorrectionPrefill, setVisitCorrectionPrefill] =
    useState<VisitCorrectionPrefill | null>(null);
  const [data, setData] = useState<AppData>(initialData);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);
  const [isAdvancedNavOpen, setIsAdvancedNavOpen] = useState(false);

  function applyRoute(route: AppRoute) {
    setPageState(route.page);
    if (route.streamId !== undefined) {
      setSelectedStreamId(route.streamId);
    }
    if (route.eventId !== undefined) {
      setSelectedEventId(route.eventId);
    }
    if (route.visitId !== undefined) {
      setSelectedVisitId(route.visitId);
    }
    if (route.motionEvidenceId !== undefined) {
      setSelectedMotionEvidenceId(route.motionEvidenceId);
    }
    if (route.collectionId !== undefined) {
      setSelectedCollectionId(route.collectionId);
    }
  }

  function navigate(route: AppRoute, replace = false) {
    writeAppRoute(route, replace);
    applyRoute(route);
  }

  function setPage(nextPage: Page) {
    navigate({ page: nextPage });
  }

  async function loadAppData(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    setLoadWarnings([]);
    try {
      const [
        healthResult,
        sourcesResult,
        streamsResult,
        reviewQueueResult,
        exportsResult,
        analyticsResult,
        datasetCoverageResult,
        datasetQualityResult,
        modelReadinessResult,
      ] = await Promise.allSettled([
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

      if (
        healthResult.status !== "fulfilled" ||
        sourcesResult.status !== "fulfilled" ||
        streamsResult.status !== "fulfilled"
      ) {
        const message =
          "MockingBird reached the local app, but its camera data could not be loaded.";
        if (data.health) {
          setLoadWarnings([`${message} Existing screen data was kept; retry when ready.`]);
        } else {
          setError(message);
        }
        return;
      }

      const optionalResults: Array<[string, PromiseSettledResult<unknown>]> = [
        ["Review activity", reviewQueueResult],
        ["Exports", exportsResult],
        ["Analytics", analyticsResult],
        ["Dataset coverage", datasetCoverageResult],
        ["Dataset quality", datasetQualityResult],
        ["Identification readiness", modelReadinessResult],
      ];
      setLoadWarnings(
        optionalResults
          .filter(([, result]) => result.status === "rejected")
          .map(([label]) => `${label} is temporarily unavailable.`),
      );

      setData({
        health: healthResult.value,
        sources: sourcesResult.value,
        streams: streamsResult.value,
        reviewQueue:
          reviewQueueResult.status === "fulfilled"
            ? reviewQueueResult.value
            : data.reviewQueue,
        exports: exportsResult.status === "fulfilled" ? exportsResult.value : data.exports,
        analytics:
          analyticsResult.status === "fulfilled" ? analyticsResult.value : data.analytics,
        datasetCoverage:
          datasetCoverageResult.status === "fulfilled"
            ? datasetCoverageResult.value
            : data.datasetCoverage,
        datasetQuality:
          datasetQualityResult.status === "fulfilled"
            ? datasetQualityResult.value
            : data.datasetQuality,
        modelReadiness:
          modelReadinessResult.status === "fulfilled"
            ? modelReadinessResult.value
            : data.modelReadiness,
      });
      setSelectedStreamId((current) => current ?? streamsResult.value[0]?.id ?? null);
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

  useEffect(() => {
    if (initialRoute.recoveredFromUnknownPath) {
      writeAppRoute({ page: "dashboard" }, true);
    }
    function handleBrowserNavigation() {
      applyRoute(readAppRoute());
      setReviewQueueInitialContext(null);
      setVisitCorrectionPrefill(null);
    }
    window.addEventListener("popstate", handleBrowserNavigation);
    return () => window.removeEventListener("popstate", handleBrowserNavigation);
  }, []);

  const isAdvancedPageActive = advancedPages.has(page);

  useEffect(() => {
    if (isAdvancedPageActive) {
      setIsAdvancedNavOpen(true);
    }
  }, [isAdvancedPageActive]);

  const selectedStream = useMemo(
    () => data.streams.find((stream) => stream.id === selectedStreamId) ?? data.streams[0],
    [data.streams, selectedStreamId],
  );

  function openStream(streamId: string) {
    navigate({ page: "stream-detail", streamId });
  }

  function openEvent(eventId: string) {
    navigate({ page: "event-detail", eventId });
  }

  function openVisit(visitId: string, prefill?: Omit<VisitCorrectionPrefill, "visitId">) {
    setVisitCorrectionPrefill(prefill ? { visitId, ...prefill } : null);
    navigate({ page: "visit-detail", visitId });
  }

  function openMotionEvidence(motionEvidenceId: string) {
    navigate({ page: "motion-evidence-detail", motionEvidenceId });
  }

  function openReviewQueue(context?: ReviewQueueInitialContext | null) {
    setReviewQueueInitialContext(context ?? null);
    setPage("review");
  }

  function openActivityLibrary(filters: ActivityLibraryFilters) {
    const path = activityLibraryPath(filters);
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState({}, "", path);
    }
    applyRoute({ page: "activity-library" });
  }

  function openCollections(collectionId?: string) {
    navigate(collectionId ? { page: "collection-detail", collectionId } : { page: "collections" });
  }

  function openAlertAction(action: ProductAlertAction) {
    if (action.action_type === "review_visit" && action.visit_id) {
      openVisit(action.visit_id);
      return;
    }
    if (action.action_type === "open_stream" && action.stream_id) {
      openStream(action.stream_id);
      return;
    }
    if (action.action_type === "open_storage_retention") {
      setPage("saved-media-retention");
      return;
    }
    if (action.action_type === "open_wildlife_journal") {
      const path = action.label ? `/bird-log/${encodeURIComponent(action.label)}` : "/bird-log";
      window.history.pushState({}, "", path);
      applyRoute({ page: "bird-log" });
    }
  }

  function openFocusedFastReview(visitIds: string[]) {
    const boundedVisitIds = visitIds.slice(0, 50);
    if (boundedVisitIds.length === 0) {
      return;
    }
    openReviewQueue({
      source: "activity-library",
      status: "unreviewed",
      visitIds: boundedVisitIds,
      openFastReview: true,
    });
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
    if (isLoading && page !== "dashboard") {
      return <div className="panel">Loading MockingBird...</div>;
    }

    if (error && page !== "dashboard") {
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
          onOpenStream={openStream}
          onOpenStreams={() => setPage("streams")}
          onAddCamera={() => setPage("camera-setup")}
          onOpenReview={openReviewQueue}
          onOpenBirdLog={() => setPage("bird-log")}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "streams") {
      return (
        <StreamsPage
          streams={data.streams}
          sources={data.sources}
          reviewQueue={data.reviewQueue}
          datasetExports={data.exports}
          onOpenImport={() => setPage("import")}
          onOpenStream={openStream}
          onOpenMotionEvidence={openMotionEvidence}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenReview={() => openReviewQueue()}
          onOpenReviewForStream={(streamId) =>
            openReviewQueue({ source: "live-motion", search: streamId, status: "unreviewed" })
          }
          onOpenBirdLog={() => setPage("bird-log")}
          onOpenExports={() => setPage("exports")}
          onAddCamera={() => setPage("camera-setup")}
          onSourcesChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "camera-setup") {
      return (
        <CameraSetupPage
          onCancel={() => setPage("streams")}
          onComplete={(streamId) => openStream(streamId)}
          onSourcesChanged={() => loadAppData({ showLoading: false })}
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
          onOpenReview={() => openReviewQueue()}
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
          onOpenStreams={() => setPage("streams")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => openReviewQueue()}
          onOpenBirdLog={() => setPage("bird-log")}
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
          onOpenReview={() => openReviewQueue()}
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
          onOpenReview={openReviewQueue}
          onOpenMotionEvidence={openMotionEvidence}
          onReviewActivityCreated={() => loadAppData({ showLoading: false })}
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
          onOpenVisit={openVisit}
          onOpenExports={() => setPage("exports")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenMotionEvidence={openMotionEvidence}
          onCorrectionSaved={refreshAfterVisitCorrection}
          correctionPrefill={visitCorrectionPrefill}
          onOpenCollections={() => openCollections()}
          onOpenActivityLibrary={openActivityLibrary}
        />
      );
    }

    if (page === "activity-library") {
      return (
        <ActivityLibraryPage
          sources={data.sources}
          streams={data.streams}
          onOpenVisit={openVisit}
          onOpenFocusedFastReview={openFocusedFastReview}
          onOpenExports={() => setPage("exports")}
          onOpenCollections={() => openCollections()}
        />
      );
    }

    if (page === "review") {
      return (
        <ReviewQueuePage
          items={data.reviewQueue}
          initialContext={reviewQueueInitialContext}
          onCreateCorrection={createCorrection}
          onFastReviewChanged={() => loadAppData({ showLoading: false })}
          onInitialContextConsumed={() => setReviewQueueInitialContext(null)}
          onOpenEvent={openEvent}
          onOpenAnalytics={() => setPage("analytics")}
          onOpenClassifierReadiness={() => setPage("classifier-readiness")}
          onOpenExports={() => setPage("exports")}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "bird-log") {
      return (
        <BirdLogPage
          sources={data.sources}
          streams={data.streams}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenStreams={() => setPage("streams")}
          onOpenImport={() => setPage("import")}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
          onOpenCollections={() => openCollections()}
        />
      );
    }

    if (page === "collections" || (page === "collection-detail" && selectedCollectionId)) {
      return (
        <CollectionsPage
          collectionId={page === "collection-detail" ? selectedCollectionId : null}
          sources={data.sources}
          streams={data.streams}
          onOpenActivityLibrary={() => setPage("activity-library")}
          onOpenCollection={openCollections}
          onOpenVisit={openVisit}
          onOpenFocusedFastReview={openFocusedFastReview}
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
          onOpenStream={(streamId) => {
            const targetStreamId = streamId ?? selectedStream?.id;
            if (targetStreamId) openStream(targetStreamId);
          }}
          onOpenActivityLibrary={openActivityLibrary}
          onOpenBirdLog={() => setPage("bird-log")}
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

    if (page === "alerts-inbox") {
      return <AlertsInboxPage onAction={openAlertAction} />;
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
        <AlertsControl onAction={openAlertAction} onOpenInbox={() => setPage("alerts-inbox")} />
        <nav className="nav-list" aria-label="Product navigation">
          <span className="nav-section-label">Product loop</span>
          {productNavItems.map((item) => (
            <button
              className={page === item.page ? "nav-item active" : "nav-item"}
              key={item.page}
              onClick={() => setPage(item.page)}
            >
              {item.label}
            </button>
          ))}
          <details
            className="nav-group"
            open={isAdvancedNavOpen || isAdvancedPageActive}
            onToggle={(event) => setIsAdvancedNavOpen(event.currentTarget.open)}
          >
            <summary>Advanced / Developer tools</summary>
            <div className="nav-group-items">
              {advancedNavItems.map((item) => (
                <button
                  className={page === item.page ? "nav-item active" : "nav-item"}
                  key={item.page}
                  onClick={() => setPage(item.page)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </details>
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
          <span>Local app</span>
          <strong>{apiClient.baseUrl || "This device"}</strong>
        </div>
      </aside>
      <main className="main-content">
        {loadWarnings.length > 0 ? (
          <div className="notice-panel app-load-warning" role="status">
            <strong>Some supporting information could not refresh.</strong>
            <span>{loadWarnings.join(" ")}</span>
            <button className="text-action" onClick={() => void loadAppData({ showLoading: false })}>
              Retry
            </button>
          </div>
        ) : null}
        {renderPage()}
      </main>
    </div>
  );
}
