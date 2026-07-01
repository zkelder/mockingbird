import { useEffect, useMemo, useState } from "react";
import { apiClient } from "./api/client";
import type {
  AnalyticsSummary,
  CameraSource,
  DatasetExport,
  HealthStatus,
  ReviewLabel,
  ReviewQueueItem,
  Stream,
} from "./api/types";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ExportsPage } from "./pages/ExportsPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { StreamDetailPage } from "./pages/StreamDetailPage";
import { StreamsPage } from "./pages/StreamsPage";

type Page = "dashboard" | "streams" | "stream-detail" | "review" | "analytics" | "exports";

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
  { page: "review", label: "Review Queue" },
  { page: "analytics", label: "Analytics" },
  { page: "exports", label: "Dataset Exports" },
];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedStreamId, setSelectedStreamId] = useState<string | null>(null);
  const [data, setData] = useState<AppData>(initialData);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadAppData() {
    setIsLoading(true);
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
      setIsLoading(false);
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

  async function createCorrection(
    item: ReviewQueueItem,
    label: string,
    notes: string,
  ): Promise<ReviewLabel> {
    // Corrections are dataset-grade user labels; status transitions arrive in a later API phase.
    return apiClient.createReviewLabel({
      target_type: item.visit_id ? "visit" : "event",
      target_id: item.visit_id ?? item.event_id ?? item.id,
      label,
      notes: notes || undefined,
    });
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
          onOpenStream={openStream}
        />
      );
    }

    if (page === "streams") {
      return <StreamsPage streams={data.streams} sources={data.sources} onOpenStream={openStream} />;
    }

    if (page === "stream-detail" && selectedStream) {
      return <StreamDetailPage streamId={selectedStream.id} reviewQueue={data.reviewQueue} />;
    }

    if (page === "review") {
      return <ReviewQueuePage items={data.reviewQueue} onCreateCorrection={createCorrection} />;
    }

    if (page === "analytics") {
      return <AnalyticsPage analytics={data.analytics} />;
    }

    return <ExportsPage exports={data.exports} />;
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
          {navItems.map((item) => (
            <button
              className={page === item.page ? "nav-item active" : "nav-item"}
              key={item.page}
              onClick={() => setPage(item.page)}
            >
              {item.label}
            </button>
          ))}
          {selectedStream ? (
            <button
              className={page === "stream-detail" ? "nav-item active" : "nav-item"}
              onClick={() => openStream(selectedStream.id)}
            >
              Stream Detail
            </button>
          ) : null}
        </nav>
        <div className="sidebar-footer">
          <span>API</span>
          <strong>{apiClient.baseUrl}</strong>
        </div>
      </aside>
      <main className="main-content">{renderPage()}</main>
    </div>
  );
}
