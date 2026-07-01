import { useEffect, useMemo, useState } from "react";
import { apiClient } from "./api/client";
import type {
  AnalyticsSummary,
  CameraSource,
  DatasetExport,
  HealthStatus,
  ReviewCorrectionResult,
  ReviewQueueItem,
  Stream,
} from "./api/types";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DetectionProposalsPage } from "./pages/DetectionProposalsPage";
import { EventDetailPage } from "./pages/EventDetailPage";
import { ExportsPage } from "./pages/ExportsPage";
import { FolderImportPage } from "./pages/FolderImportPage";
import { LocalDataPage } from "./pages/LocalDataPage";
import { ManualImportPage } from "./pages/ManualImportPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { StreamDetailPage } from "./pages/StreamDetailPage";
import { StreamsPage } from "./pages/StreamsPage";
import { VisitDetailPage } from "./pages/VisitDetailPage";

type Page =
  | "dashboard"
  | "streams"
  | "import"
  | "folder-import"
  | "detection-proposals"
  | "stream-detail"
  | "event-detail"
  | "visit-detail"
  | "review"
  | "analytics"
  | "exports"
  | "settings";

interface AppData {
  health: HealthStatus | null;
  sources: CameraSource[];
  streams: Stream[];
  reviewQueue: ReviewQueueItem[];
  exports: DatasetExport[];
  analytics: AnalyticsSummary | null;
}

const initialData: AppData = {
  health: null,
  sources: [],
  streams: [],
  reviewQueue: [],
  exports: [],
  analytics: null,
};

const navItems: Array<{ page: Page; label: string }> = [
  { page: "dashboard", label: "Dashboard" },
  { page: "streams", label: "Streams" },
  { page: "import", label: "Import Media" },
  { page: "folder-import", label: "Folder Import" },
  { page: "detection-proposals", label: "Detection Proposals" },
  { page: "review", label: "Review" },
  { page: "analytics", label: "Analytics" },
  { page: "exports", label: "Exports" },
  { page: "settings", label: "Local Data" },
];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedStreamId, setSelectedStreamId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedVisitId, setSelectedVisitId] = useState<string | null>(null);
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
      const [health, sources, streams, reviewQueue, exports, analytics] = await Promise.all([
        apiClient.getHealth(),
        apiClient.getSources(),
        apiClient.getStreams(),
        apiClient.getReviewQueue(),
        apiClient.getDatasetExports(),
        apiClient.getAnalyticsSummary(),
      ]);

      setData({ health, sources, streams, reviewQueue, exports, analytics });
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

  function openVisit(visitId: string) {
    setSelectedVisitId(visitId);
    setPage("visit-detail");
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
          streams={data.streams}
          analytics={data.analytics}
          reviewQueue={data.reviewQueue}
          exports={data.exports}
          onOpenStream={openStream}
          onOpenImport={() => setPage("import")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenReview={() => setPage("review")}
          onOpenExports={() => setPage("exports")}
        />
      );
    }

    if (page === "streams") {
      return <StreamsPage streams={data.streams} sources={data.sources} onOpenStream={openStream} />;
    }

    if (page === "import") {
      return (
        <ManualImportPage
          streams={data.streams}
          sources={data.sources}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenStream={openStream}
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
          onOpenReview={() => setPage("review")}
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
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => setPage("review")}
          onOpenExports={() => setPage("exports")}
          onProposalChanged={() => loadAppData({ showLoading: false })}
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
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => setPage("review")}
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
          onOpenReview={() => setPage("review")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
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
          onCorrectionSaved={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "review") {
      return (
        <ReviewQueuePage
          items={data.reviewQueue}
          onCreateCorrection={createCorrection}
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
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => setPage("review")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenStream={selectedStream ? () => openStream(selectedStream.id) : undefined}
        />
      );
    }

    if (page === "exports") {
      return (
        <ExportsPage
          exports={data.exports}
          onOpenReview={() => setPage("review")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onExportsChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    return (
      <LocalDataPage
        onOpenDashboard={() => setPage("dashboard")}
        onOpenImport={() => setPage("import")}
        onOpenStreams={() => setPage("streams")}
        onOpenReview={() => setPage("review")}
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
