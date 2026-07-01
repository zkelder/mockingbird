import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { LocalDataStatus } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";

interface LocalDataPageProps {
  onOpenDashboard: () => void;
  onOpenImport: () => void;
  onOpenStreams: () => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onOpenDetectionProposals: () => void;
  onResetComplete: () => Promise<void>;
}

export function LocalDataPage({
  onOpenDashboard,
  onOpenImport,
  onOpenStreams,
  onOpenReview,
  onOpenExports,
  onOpenDetectionProposals,
  onResetComplete,
}: LocalDataPageProps) {
  const [status, setStatus] = useState<LocalDataStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isResetting, setIsResetting] = useState(false);
  const [isConfirmingReset, setIsConfirmingReset] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      setStatus(await apiClient.getLocalDataStatus());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load local data status.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  async function resetDemoData() {
    if (!isConfirmingReset) {
      setIsConfirmingReset(true);
      setMessage("Confirm reset to restore the seeded local product loop.");
      return;
    }

    setIsResetting(true);
    setError(null);
    setMessage(null);
    try {
      setStatus(await apiClient.resetDemoData());
      await onResetComplete();
      setIsConfirmingReset(false);
      setMessage("Demo data reset. Local zones, corrections, and exports are back to seed state.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reset demo data.");
    } finally {
      setIsResetting(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Local-first storage"
        title="Local Data"
        description="MockingBird keeps product metadata, imported media references, drawn zones, review corrections, analytics inputs, and dataset export manifests locally."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenDashboard}>
              Dashboard
            </button>
            <button className="secondary-action" onClick={() => void loadStatus()}>
              Refresh status
            </button>
          </>
        }
      />

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      {isLoading ? <div className="panel">Loading local data status...</div> : null}

      {!isLoading && status ? (
        <>
          <section className="metric-grid">
            <MetricCard label="Sources" value={status.source_count} detail="local source records" />
            <MetricCard label="Streams" value={status.stream_count} detail="video-centered views" />
            <MetricCard label="Zones" value={status.zone_count} detail="user-authored context" />
            <MetricCard
              label="Media"
              value={status.media_asset_count}
              detail="local import references"
            />
          </section>

          <section className="metric-grid">
            <MetricCard label="Events" value={status.event_count} detail="outdoor activity" />
            <MetricCard label="Visits" value={status.visit_count} detail="reviewable observations" />
            <MetricCard
              label="Needs review"
              value={status.needs_review_count}
              detail="local correction work"
            />
            <MetricCard
              label="Corrections"
              value={status.review_label_count}
              detail="dataset-grade labels"
            />
            <MetricCard
              label="Proposals"
              value={status.detection_proposal_count}
              detail={`${status.detection_run_count} detection runs`}
            />
            <MetricCard
              label="Exports"
              value={status.dataset_export_count}
              detail="local dataset manifests"
            />
          </section>

          <section className="split-grid">
            <div className="panel local-data-card">
              <div className="section-heading">
                <h2>Database</h2>
                <StatusPill
                  label={status.database_ready ? "Ready" : "Unavailable"}
                  tone={status.database_ready ? "good" : "review"}
                />
              </div>
              <div className="data-row">
                <span>Location</span>
                <strong>{status.database_path ?? status.database_url}</strong>
              </div>
              <div className="data-row">
                <span>Configuration</span>
                <strong>{status.using_default_database ? "Default local database" : "Environment override"}</strong>
              </div>
              <div className="data-row">
                <span>Seed data</span>
                <strong>{status.seed_data_present ? "Present" : "Missing"}</strong>
              </div>
              <div className="data-row">
                <span>Dataset exports</span>
                <strong>{status.dataset_export_count}</strong>
              </div>
              <p>{status.local_first_note}</p>
              <p>Imported media files stay in the configured local media root and are not analyzed or transcoded.</p>
            </div>

            <div className="panel local-data-card">
              <div className="section-heading">
                <h2>Product Loop</h2>
              </div>
              <p>
                These records support the stream-first loop from outdoor streams to zones, events,
                visits, review corrections, analytics, and local dataset exports.
              </p>
              <div className="local-data-actions">
                <button className="secondary-action" onClick={onOpenImport}>
                  Import Media
                </button>
                <button className="secondary-action" onClick={onOpenStreams}>
                  Streams
                </button>
                <button className="secondary-action" onClick={onOpenReview}>
                  Review Queue
                </button>
                <button className="secondary-action" onClick={onOpenDetectionProposals}>
                  Detection Proposals
                </button>
                <button className="secondary-action" onClick={onOpenExports}>
                  Dataset Exports
                </button>
              </div>
            </div>
          </section>

          <section className="panel local-data-card">
            <div className="section-heading">
              <h2>Reset Demo Data</h2>
              <StatusPill label="Local metadata only" tone="quiet" />
            </div>
            <p>
              Reset restores the seeded source, stream, zones, events, visits, review label, and
              dataset export manifest. It does not delete media files or write export archives.
            </p>
            {isConfirmingReset ? (
              <div className="notice-panel">
                <strong>Confirm reset</strong>
                <span>
                  This will replace local demo metadata with the seeded product loop state.
                </span>
              </div>
            ) : null}
            <div className="local-data-actions">
              <button
                className={isConfirmingReset ? "primary-action" : "secondary-action"}
                disabled={isResetting}
                onClick={() => void resetDemoData()}
              >
                {isResetting
                  ? "Resetting..."
                  : isConfirmingReset
                    ? "Confirm reset"
                    : "Reset demo data"}
              </button>
              {isConfirmingReset ? (
                <button
                  className="secondary-action"
                  disabled={isResetting}
                  onClick={() => {
                    setIsConfirmingReset(false);
                    setMessage(null);
                  }}
                >
                  Cancel
                </button>
              ) : null}
            </div>
          </section>
        </>
      ) : null}

      {!isLoading && !status && !error ? (
        <EmptyState
          title="Local data status is unavailable"
          description="The local database status could not be loaded from the MockingBird API."
        />
      ) : null}
    </div>
  );
}
