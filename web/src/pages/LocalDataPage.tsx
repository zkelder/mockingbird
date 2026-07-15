import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { LocalBackupSummary, LocalDataStatus } from "../api/types";
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

function formatBytes(value: number) {
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value / 1024;
  let unitIndex = 0;
  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024;
    unitIndex += 1;
  }
  return `${amount >= 10 ? amount.toFixed(0) : amount.toFixed(1)} ${units[unitIndex]}`;
}

function formatBackupTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
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
  const [backups, setBackups] = useState<LocalBackupSummary[]>([]);
  const [unreadableBackupCount, setUnreadableBackupCount] = useState(0);
  const [isLoadingBackups, setIsLoadingBackups] = useState(true);
  const [backupOperation, setBackupOperation] = useState<string | null>(null);
  const [confirmingRestoreId, setConfirmingRestoreId] = useState<string | null>(null);
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

  async function loadBackups(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingBackups(true);
    }
    try {
      const library = await apiClient.getLocalBackups();
      setBackups(library.backups);
      setUnreadableBackupCount(library.unreadable_backup_count);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load local backups.");
    } finally {
      if (showLoading) {
        setIsLoadingBackups(false);
      }
    }
  }

  useEffect(() => {
    void loadStatus();
    void loadBackups();
  }, []);

  function upsertBackup(backup: LocalBackupSummary) {
    setBackups((current) =>
      [backup, ...current.filter((item) => item.id !== backup.id)].sort(
        (left, right) =>
          new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
      ),
    );
  }

  async function createBackup() {
    setBackupOperation("create");
    setError(null);
    setMessage(null);
    try {
      const result = await apiClient.createLocalBackup();
      upsertBackup(result.backup);
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create a local backup.");
    } finally {
      setBackupOperation(null);
    }
  }

  async function importBackup(file: File) {
    setBackupOperation("import");
    setError(null);
    setMessage(null);
    try {
      const result = await apiClient.importLocalBackup(file);
      upsertBackup(result.backup);
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not import that backup.");
    } finally {
      setBackupOperation(null);
    }
  }

  async function verifyBackup(backupId: string) {
    setBackupOperation(`verify:${backupId}`);
    setError(null);
    setMessage(null);
    try {
      const result = await apiClient.verifyLocalBackup(backupId);
      upsertBackup(result.backup);
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not verify that backup.");
    } finally {
      setBackupOperation(null);
    }
  }

  async function restoreBackup(backupId: string) {
    if (confirmingRestoreId !== backupId) {
      setConfirmingRestoreId(backupId);
      setMessage(null);
      return;
    }

    setBackupOperation(`restore:${backupId}`);
    setError(null);
    setMessage(null);
    try {
      const result = await apiClient.restoreLocalBackup(backupId);
      setStatus(result.status);
      await onResetComplete();
      await loadBackups({ showLoading: false });
      setConfirmingRestoreId(null);
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not restore that backup.");
    } finally {
      setBackupOperation(null);
    }
  }

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
      setMessage("Sample walkthrough restored. Your real cameras and product data were preserved.");
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
                <span>Data format</span>
                <strong>
                  Version {status.database_schema_version} of{" "}
                  {status.database_schema_current_version}
                </strong>
              </div>
              <div className="data-row">
                <span>Integrity check</span>
                <strong>
                  {status.database_integrity_check === "ok" ? "Passed" : "Not required"}
                </strong>
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
              <div>
                <h2>Backup and Recovery</h2>
                <p>Protect the complete local database and managed media together.</p>
              </div>
              <StatusPill label="Explicit local action" tone="quiet" />
            </div>
            <p>
              Every backup is checked before it is kept. Restore checks it again, stops active
              MockingBird camera work, and creates a separate safety backup before replacing data.
            </p>
            <div className="local-data-actions">
              <button
                className="primary-action"
                disabled={backupOperation !== null}
                onClick={() => void createBackup()}
              >
                {backupOperation === "create" ? "Creating and checking..." : "Create backup"}
              </button>
              <label className="secondary-action backup-file-action">
                {backupOperation === "import" ? "Importing and checking..." : "Import backup"}
                <input
                  type="file"
                  accept=".mbbackup,application/zip"
                  disabled={backupOperation !== null}
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    event.currentTarget.value = "";
                    if (file) {
                      void importBackup(file);
                    }
                  }}
                />
              </label>
              <button
                className="secondary-action"
                disabled={backupOperation !== null}
                onClick={() => void loadBackups()}
              >
                Refresh backups
              </button>
            </div>

            {unreadableBackupCount > 0 ? (
              <div className="error-panel">
                {unreadableBackupCount} backup file{unreadableBackupCount === 1 ? " is" : "s are"}
                unreadable and will not be offered for restore.
              </div>
            ) : null}

            {isLoadingBackups ? <div className="backup-empty">Loading local backups...</div> : null}
            {!isLoadingBackups && backups.length === 0 ? (
              <div className="backup-empty">
                No backups yet. Create one before longer camera sessions or major app updates.
              </div>
            ) : null}

            <div className="backup-list">
              {backups.map((backup) => {
                const isConfirmingRestore = confirmingRestoreId === backup.id;
                const isVerifying = backupOperation === `verify:${backup.id}`;
                const isRestoring = backupOperation === `restore:${backup.id}`;
                return (
                  <article className="backup-card" key={backup.id}>
                    <div className="section-heading">
                      <div>
                        <strong>
                          {backup.kind === "pre_restore" ? "Before restore" : "Local backup"}
                        </strong>
                        <span className="meta-text">{formatBackupTime(backup.created_at)}</span>
                      </div>
                      <StatusPill
                        label={
                          !backup.restore_compatible
                            ? "Different storage layout"
                            : backup.verification_status === "verified"
                              ? "Verified"
                              : "Ready to verify"
                        }
                        tone={
                          !backup.restore_compatible
                            ? "review"
                            : backup.verification_status === "verified"
                              ? "good"
                              : "quiet"
                        }
                      />
                    </div>
                    <div className="backup-meta-grid">
                      <div className="data-row">
                        <span>Complete artifact</span>
                        <strong>{formatBytes(backup.archive_size_bytes)}</strong>
                      </div>
                      <div className="data-row">
                        <span>Database</span>
                        <strong>{formatBytes(backup.database_size_bytes)}</strong>
                      </div>
                      <div className="data-row">
                        <span>Managed media</span>
                        <strong>
                          {backup.media_file_count} file{backup.media_file_count === 1 ? "" : "s"} ·{" "}
                          {formatBytes(backup.media_size_bytes)}
                        </strong>
                      </div>
                    </div>
                    {isConfirmingRestore ? (
                      <div className="notice-panel">
                        <strong>Confirm restore</strong>
                        <span>
                          Current local data and managed media will be replaced. Active camera work
                          will stop, and a verified safety backup will be created first.
                        </span>
                      </div>
                    ) : null}
                    <div className="local-data-actions">
                      <button
                        className="secondary-action"
                        disabled={backupOperation !== null}
                        onClick={() => void verifyBackup(backup.id)}
                      >
                        {isVerifying ? "Checking..." : "Verify"}
                      </button>
                      <a
                        className="secondary-action"
                        href={apiClient.localBackupDownloadUrl(backup.id)}
                      >
                        Download copy
                      </a>
                      <button
                        className={isConfirmingRestore ? "primary-action" : "secondary-action"}
                        disabled={backupOperation !== null || !backup.restore_compatible}
                        onClick={() => void restoreBackup(backup.id)}
                      >
                        {isRestoring
                          ? "Restoring safely..."
                          : isConfirmingRestore
                            ? "Confirm restore"
                            : "Restore"}
                      </button>
                      {isConfirmingRestore ? (
                        <button
                          className="secondary-action"
                          disabled={backupOperation !== null}
                          onClick={() => setConfirmingRestoreId(null)}
                        >
                          Cancel
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="panel local-data-card">
            <div className="section-heading">
              <h2>Reset Demo Data</h2>
              <StatusPill label="Local metadata only" tone="quiet" />
            </div>
            <p>
              Reset restores the seeded source, stream, zones, events, visits, review label, and
              dataset export manifest. Real cameras, their Zones and observations, other exports,
              and local media are preserved.
            </p>
            {isConfirmingReset ? (
              <div className="notice-panel">
                <strong>Confirm reset</strong>
                <span>
                  This will replace only the sample walkthrough with its seeded product loop state.
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
