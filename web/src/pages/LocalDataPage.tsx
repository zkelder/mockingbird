import { useEffect, useState } from "react";
import { apiClient, ApiError } from "../api/client";
import type {
  LocalBackupSummary,
  LocalDataStatus,
  StorageCleanupHistoryItem,
  StorageCleanupPreviewResponse,
  StorageRetentionSettings,
  StorageSummary,
  StructuredError,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatBytes, formatLabel } from "../utils";

interface LocalDataPageProps {
  onOpenDashboard: () => void;
  onOpenImport: () => void;
  onOpenStreams: () => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onOpenDetectionProposals: () => void;
  onResetComplete: () => Promise<void>;
}

function formatBackupTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function storageRequestKey(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function cleanupBatchCanPurge(batch: StorageCleanupHistoryItem) {
  if (!batch.recovery_expires_at || !["quarantined", "restore_conflict"].includes(batch.state)) {
    return false;
  }
  return new Date(batch.recovery_expires_at).getTime() <= Date.now();
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
  // Structured error surfacing (P0): populated only when a caught ApiError
  // carries one (today, only a database-write failure does) -- see
  // `applyError`. Reset alongside `error` everywhere so a later, unrelated
  // failure can never show a stale "Advanced details" block.
  const [errorDetail, setErrorDetail] = useState<StructuredError | undefined>(undefined);
  const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);
  const [storageSettings, setStorageSettings] = useState<StorageRetentionSettings | null>(null);
  const [cleanupHistory, setCleanupHistory] = useState<StorageCleanupHistoryItem[]>([]);
  const [cleanupPreview, setCleanupPreview] = useState<StorageCleanupPreviewResponse | null>(null);
  const [isLoadingStorage, setIsLoadingStorage] = useState(true);
  const [storageOperation, setStorageOperation] = useState<string | null>(null);
  const [isConfirmingCleanup, setIsConfirmingCleanup] = useState(false);
  const [confirmingPurgeId, setConfirmingPurgeId] = useState<string | null>(null);

  // Populates both `error` (always) and `errorDetail` (only when the
  // caught failure is an ApiError carrying a well-shaped structuredError --
  // today, only a database-write failure does). Used by every backup/
  // storage-retention operation below, whose failures are the ones this
  // milestone's structured-error taxonomy actually touched.
  function applyError(caught: unknown, fallback: string): void {
    setError(caught instanceof Error ? caught.message : fallback);
    setErrorDetail(caught instanceof ApiError ? caught.structuredError : undefined);
  }

  async function loadStatus(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    setErrorDetail(undefined);
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
    setErrorDetail(undefined);
    try {
      const library = await apiClient.getLocalBackups();
      setBackups(library.backups);
      setUnreadableBackupCount(library.unreadable_backup_count);
    } catch (caught) {
      applyError(caught, "Could not load local backups.");
    } finally {
      if (showLoading) {
        setIsLoadingBackups(false);
      }
    }
  }

  async function loadStorage(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingStorage(true);
    }
    setErrorDetail(undefined);
    try {
      const [summary, settings, history] = await Promise.all([
        apiClient.getStorageRetentionSummary(),
        apiClient.getStorageRetentionSettings(),
        apiClient.getStorageRetentionCleanupHistory(),
      ]);
      setStorageSummary(summary);
      setStorageSettings(settings);
      setCleanupHistory(history.items);
    } catch (caught) {
      applyError(caught, "Could not load storage retention status.");
    } finally {
      if (showLoading) {
        setIsLoadingStorage(false);
      }
    }
  }

  useEffect(() => {
    void loadStatus();
    void loadBackups();
    void loadStorage();
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
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const result = await apiClient.createLocalBackup();
      upsertBackup(result.backup);
      setMessage(result.message);
    } catch (caught) {
      applyError(caught, "Could not create a local backup.");
    } finally {
      setBackupOperation(null);
    }
  }

  async function importBackup(file: File) {
    setBackupOperation("import");
    setError(null);
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const result = await apiClient.importLocalBackup(file);
      upsertBackup(result.backup);
      setMessage(result.message);
    } catch (caught) {
      applyError(caught, "Could not import that backup.");
    } finally {
      setBackupOperation(null);
    }
  }

  async function verifyBackup(backupId: string) {
    setBackupOperation(`verify:${backupId}`);
    setError(null);
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const result = await apiClient.verifyLocalBackup(backupId);
      upsertBackup(result.backup);
      setMessage(result.message);
    } catch (caught) {
      applyError(caught, "Could not verify that backup.");
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
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const result = await apiClient.restoreLocalBackup(backupId);
      setStatus(result.status);
      await onResetComplete();
      await loadBackups({ showLoading: false });
      setConfirmingRestoreId(null);
      setMessage(result.message);
    } catch (caught) {
      applyError(caught, "Could not restore that backup.");
    } finally {
      setBackupOperation(null);
    }
  }

  async function saveStorageSettings() {
    if (!storageSettings) {
      return;
    }
    setStorageOperation("settings");
    setError(null);
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const { persisted, recommended_defaults, updated_at, last_automatic_run_at, last_automatic_result, message: _message, policy_revision: _revision, ...payload } = storageSettings;
      const updated = await apiClient.updateStorageRetentionSettings({
        ...payload,
        idempotency_key: storageRequestKey("storage-settings"),
      });
      setStorageSettings(updated);
      setMessage(updated.message);
    } catch (caught) {
      applyError(caught, "Could not update storage retention settings.");
    } finally {
      setStorageOperation(null);
    }
  }

  async function previewStorageCleanup() {
    setStorageOperation("preview");
    setError(null);
    setErrorDetail(undefined);
    setMessage(null);
    setIsConfirmingCleanup(false);
    try {
      const preview = await apiClient.previewStorageRetentionCleanup();
      setCleanupPreview(preview);
      setMessage(preview.message);
    } catch (caught) {
      applyError(caught, "Could not preview cleanup.");
    } finally {
      setStorageOperation(null);
    }
  }

  async function executeStorageCleanup() {
    if (!cleanupPreview) {
      return;
    }
    if (!isConfirmingCleanup) {
      setIsConfirmingCleanup(true);
      return;
    }
    setStorageOperation("cleanup");
    setError(null);
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const result = await apiClient.executeStorageRetentionCleanup({
        preview_token: cleanupPreview.preview_token,
        confirm: true,
        idempotency_key: storageRequestKey("storage-cleanup"),
      });
      setMessage(result.message);
      setCleanupPreview(null);
      setIsConfirmingCleanup(false);
      await loadStorage({ showLoading: false });
    } catch (caught) {
      applyError(caught, "Could not move eligible media to recovery.");
    } finally {
      setStorageOperation(null);
    }
  }

  async function restoreStorageCleanup(batchId: string) {
    setStorageOperation(`restore:${batchId}`);
    setError(null);
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const result = await apiClient.restoreStorageRetentionCleanup(
        batchId,
        storageRequestKey("storage-restore"),
      );
      setMessage(result.message);
      await loadStorage({ showLoading: false });
    } catch (caught) {
      applyError(caught, "Could not restore the recovery batch.");
    } finally {
      setStorageOperation(null);
    }
  }

  async function purgeStorageCleanup(batchId: string) {
    if (confirmingPurgeId !== batchId) {
      setConfirmingPurgeId(batchId);
      setMessage(null);
      return;
    }
    setStorageOperation(`purge:${batchId}`);
    setError(null);
    setErrorDetail(undefined);
    setMessage(null);
    try {
      const result = await apiClient.purgeStorageRetentionCleanup(
        batchId,
        storageRequestKey("storage-purge"),
      );
      setConfirmingPurgeId(null);
      setMessage(result.message);
      await loadStorage({ showLoading: false });
    } catch (caught) {
      applyError(caught, "Could not permanently delete that recovery batch.");
    } finally {
      setStorageOperation(null);
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
    setErrorDetail(undefined);
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
      {error ? (
        <div className="error-panel">
          {error}
          {errorDetail ? (
            <details className="review-diagnostic-details">
              <summary>Advanced details</summary>
              <div className="review-diagnostic-grid">
                <span>Code: {errorDetail.code}</span>
                <span>Recoverability: {formatLabel(errorDetail.recoverability)}</span>
                {errorDetail.diagnostic ? (
                  <span>
                    Diagnostic:{" "}
                    {Object.entries(errorDetail.diagnostic)
                      .map(([key, value]) => `${key}: ${String(value)}`)
                      .join(", ")}
                  </span>
                ) : null}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

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
                <span>Storage</span>
                <strong>Local SQLite database</strong>
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
                <h2>Storage &amp; Retention</h2>
                <p>Previewed cleanup keeps protected evidence and moves eligible media to local recovery first.</p>
              </div>
              <StatusPill
                label={storageSettings?.automatic_cleanup_enabled ? "Automatic cleanup on" : "Automatic cleanup off"}
                tone={storageSettings?.automatic_cleanup_enabled ? "review" : "good"}
              />
            </div>

            {isLoadingStorage ? <div className="backup-empty">Loading storage safety status...</div> : null}
            {!isLoadingStorage && storageSummary ? (
              <>
                <section className="metric-grid" aria-label="Managed storage summary">
                  <MetricCard
                    label="Managed media"
                    value={storageSummary.total_managed_media_count}
                    detail={formatBytes(storageSummary.total_managed_media_bytes)}
                  />
                  <MetricCard
                    label="Active Visit evidence"
                    value={storageSummary.active_visit_media_count}
                    detail={formatBytes(storageSummary.active_visit_media_bytes)}
                  />
                  <MetricCard
                    label="Superseded only"
                    value={storageSummary.superseded_only_media_count}
                    detail={formatBytes(storageSummary.superseded_only_media_bytes)}
                  />
                  <MetricCard
                    label="Orphaned managed media"
                    value={storageSummary.orphaned_managed_media_count}
                    detail={formatBytes(storageSummary.orphaned_managed_media_bytes)}
                  />
                </section>
                <div className="data-row">
                  <span>Oldest managed file</span>
                  <strong>{storageSummary.oldest_managed_media_at ? formatBackupTime(storageSummary.oldest_managed_media_at) : "None"}</strong>
                </div>
                <div className="data-row">
                  <span>Newest managed file</span>
                  <strong>{storageSummary.newest_managed_media_at ? formatBackupTime(storageSummary.newest_managed_media_at) : "None"}</strong>
                </div>
                <div className="data-row">
                  <span>Local database</span>
                  <strong>{storageSummary.approximate_database_bytes === null || storageSummary.approximate_database_bytes === undefined ? "Size unavailable" : formatBytes(storageSummary.approximate_database_bytes)}</strong>
                </div>
                <div className="data-row">
                  <span>Free disk space</span>
                  <strong>{formatBytes(storageSummary.disk_free_bytes)} of {formatBytes(storageSummary.disk_total_bytes)}</strong>
                </div>
                <div className="data-row">
                  <span>Storage writable</span>
                  <strong>{storageSummary.is_writable ? "Yes" : "No -- check folder permissions"}</strong>
                </div>
                <div className="data-row">
                  <span>Protected review context</span>
                  <strong>
                    {storageSummary.unresolved_visit_evidence_count} unresolved · {storageSummary.reviewed_bird_wildlife_evidence_count} reviewed wildlife · {storageSummary.reviewed_non_bird_blank_ambiguous_evidence_count} reviewed other
                  </strong>
                </div>
                {storageSummary.storage_warning ? <div className="notice-panel">{storageSummary.storage_warning}</div> : null}
              </>
            ) : null}

            {storageSettings ? (
              <>
                <div className="notice-panel">
                  <strong>Safe default</strong>
                  <span>Automatic cleanup starts off. Active primary evidence, unresolved work, reviewed wildlife, export context, incomplete files, and uncertain links are retained.</span>
                </div>
                <div className="backup-meta-grid">
                  <label className="data-row">
                    <span>Automatic cleanup</span>
                    <input
                      checked={storageSettings.automatic_cleanup_enabled}
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, automatic_cleanup_enabled: event.target.checked })}
                      type="checkbox"
                    />
                  </label>
                  <label className="data-row">
                    <span>Frequency</span>
                    <select
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, cleanup_frequency: event.target.value as StorageRetentionSettings["cleanup_frequency"] })}
                      value={storageSettings.cleanup_frequency}
                    >
                      <option value="weekly">Weekly</option>
                      <option value="daily">Daily</option>
                    </select>
                  </label>
                  <label className="data-row">
                    <span>Reviewed other evidence age</span>
                    <select
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, reviewed_non_bird_age_days: Number(event.target.value) })}
                      value={storageSettings.reviewed_non_bird_age_days}
                    >
                      <option value={30}>30 days</option>
                      <option value={90}>90 days</option>
                      <option value={180}>180 days</option>
                      <option value={365}>1 year</option>
                    </select>
                  </label>
                  <label className="data-row">
                    <span>Superseded evidence age</span>
                    <select
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, superseded_evidence_age_days: Number(event.target.value) })}
                      value={storageSettings.superseded_evidence_age_days}
                    >
                      <option value={30}>30 days</option>
                      <option value={90}>90 days</option>
                      <option value={180}>180 days</option>
                      <option value={365}>1 year</option>
                    </select>
                  </label>
                  <label className="data-row">
                    <span>Orphaned media age</span>
                    <select
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, orphaned_media_age_days: Number(event.target.value) })}
                      value={storageSettings.orphaned_media_age_days}
                    >
                      <option value={7}>7 days</option>
                      <option value={30}>30 days</option>
                      <option value={90}>90 days</option>
                      <option value={180}>180 days</option>
                    </select>
                  </label>
                  <label className="data-row">
                    <span>Rejected analysis media age</span>
                    <select
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, rejected_analysis_media_age_days: event.target.value === "none" ? null : Number(event.target.value) })}
                      value={storageSettings.rejected_analysis_media_age_days ?? "none"}
                    >
                      <option value="none">Keep forever (default)</option>
                      <option value={7}>7 days</option>
                      <option value={30}>30 days</option>
                      <option value={90}>90 days</option>
                      <option value={180}>180 days</option>
                    </select>
                  </label>
                  <label className="data-row">
                    <span>Managed-media target</span>
                    <select
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, maximum_managed_media_bytes: event.target.value === "none" ? null : Number(event.target.value) })}
                      value={storageSettings.maximum_managed_media_bytes ?? "none"}
                    >
                      <option value="none">No target</option>
                      <option value={1_073_741_824}>1 GB</option>
                      <option value={5_368_709_120}>5 GB</option>
                      <option value={10_737_418_240}>10 GB</option>
                    </select>
                  </label>
                </div>
                <div className="local-data-actions">
                  <span className="secondary-action">Unresolved Visit evidence is always protected</span>
                  <label className="secondary-action">
                    <input
                      checked={storageSettings.retain_reviewed_bird_wildlife_evidence}
                      disabled={storageOperation !== null}
                      onChange={(event) => setStorageSettings({ ...storageSettings, retain_reviewed_bird_wildlife_evidence: event.target.checked })}
                      type="checkbox"
                    />
                    Keep reviewed wildlife evidence
                  </label>
                  <button className="secondary-action" disabled={storageOperation !== null} onClick={() => void saveStorageSettings()} type="button">
                    {storageOperation === "settings" ? "Saving..." : "Save retention settings"}
                  </button>
                </div>
                <div className="data-row">
                  <span>Last automatic maintenance</span>
                  <strong>{storageSettings.last_automatic_run_at ? formatBackupTime(storageSettings.last_automatic_run_at) : "Not run"}</strong>
                </div>
              </>
            ) : null}

            <div className="local-data-actions">
              <button className="primary-action" disabled={storageOperation !== null} onClick={() => void previewStorageCleanup()} type="button">
                {storageOperation === "preview" ? "Calculating preview..." : "Preview cleanup"}
              </button>
              <button className="secondary-action" disabled={storageOperation !== null} onClick={() => void loadStorage()} type="button">
                Refresh storage status
              </button>
            </div>

            {cleanupPreview ? (
              <div className="notice-panel">
                <strong>Eligible to remove: {cleanupPreview.eligible_media_count} item{cleanupPreview.eligible_media_count === 1 ? "" : "s"} · {formatBytes(cleanupPreview.estimated_recoverable_bytes)} recoverable</strong>
                <span>Preview expires {formatBackupTime(cleanupPreview.expires_at)}. The server selected categories only; this page never selects media files.</span>
                {cleanupPreview.categories.map((category) => (
                  <span key={category.category}>{category.category.replace(/_/g, " ")}: {category.media_count} · {formatBytes(category.bytes)}</span>
                ))}
                <strong>Protected evidence</strong>
                {cleanupPreview.protected_counts.map((category) => (
                  <span key={category.category}>{category.category.replace(/_/g, " ")}: {category.media_count} retained · {formatBytes(category.bytes)}</span>
                ))}
                <span>Affected Visits: {cleanupPreview.affected_visit_count}</span>
                {cleanupPreview.warnings.map((warning) => <span key={warning}>{warning}</span>)}
                {isConfirmingCleanup ? <span>Confirm to move this unchanged preview into recovery. No reviewed truth is created or deleted.</span> : null}
                <div className="local-data-actions">
                  <button
                    className={isConfirmingCleanup ? "primary-action" : "secondary-action"}
                    disabled={storageOperation !== null || cleanupPreview.eligible_media_count === 0}
                    onClick={() => void executeStorageCleanup()}
                    type="button"
                  >
                    {storageOperation === "cleanup" ? "Moving to recovery..." : isConfirmingCleanup ? "Confirm: Move to recovery" : "Move to recovery"}
                  </button>
                  <button className="secondary-action" disabled={storageOperation !== null} onClick={() => { setCleanupPreview(null); setIsConfirmingCleanup(false); }} type="button">Discard preview</button>
                </div>
              </div>
            ) : null}

            {cleanupHistory.length > 0 ? (
              <div className="backup-list">
                {cleanupHistory.map((batch) => (
                  <article className="backup-card" key={batch.batch_id}>
                    <div className="section-heading">
                      <div>
                        <strong>{batch.origin === "automatic" ? "Automatic cleanup" : "Manual cleanup"}</strong>
                        <span className="meta-text">{formatBackupTime(batch.created_at)}</span>
                      </div>
                      <StatusPill label={batch.state.replace(/_/g, " ")} tone={batch.can_restore ? "review" : "quiet"} />
                    </div>
                    <div className="backup-meta-grid">
                      <div className="data-row"><span>Moved to recovery</span><strong>{batch.media_count} · {formatBytes(batch.recovered_bytes)}</strong></div>
                      <div className="data-row"><span>Recovery deadline</span><strong>{batch.recovery_expires_at ? formatBackupTime(batch.recovery_expires_at) : "Not available"}</strong></div>
                      <div className="data-row"><span>Skipped / failed</span><strong>{batch.skipped_count} / {batch.failed_count}</strong></div>
                      <div className="data-row"><span>Permanently deleted</span><strong>{batch.permanently_purged_count}</strong></div>
                    </div>
                    <p>{batch.message}</p>
                    {batch.can_restore ? (
                      <div className="local-data-actions">
                        <button className="secondary-action" disabled={storageOperation !== null} onClick={() => void restoreStorageCleanup(batch.batch_id)} type="button">
                          {storageOperation === `restore:${batch.batch_id}` ? "Restoring..." : "Restore media"}
                        </button>
                      </div>
                    ) : null}
                    {cleanupBatchCanPurge(batch) ? (
                      <div className="local-data-actions">
                        {confirmingPurgeId === batch.batch_id ? (
                          <div className="notice-panel">
                            <strong>Confirm permanent deletion</strong>
                            <span>The recovery window has ended. This cannot be undone.</span>
                          </div>
                        ) : null}
                        <button
                          className={confirmingPurgeId === batch.batch_id ? "primary-action" : "secondary-action"}
                          disabled={storageOperation !== null}
                          onClick={() => void purgeStorageCleanup(batch.batch_id)}
                          type="button"
                        >
                          {storageOperation === `purge:${batch.batch_id}`
                            ? "Permanently deleting..."
                            : confirmingPurgeId === batch.batch_id
                              ? "Confirm: Permanently delete"
                              : "Permanently delete"}
                        </button>
                        {confirmingPurgeId === batch.batch_id ? (
                          <button
                            className="secondary-action"
                            disabled={storageOperation !== null}
                            onClick={() => setConfirmingPurgeId(null)}
                            type="button"
                          >
                            Cancel
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}
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
                          will stop, and a verified safety backup will be created first. Any camera
                          that was continuously monitoring will be paused after restore -- resume it
                          from Stream Detail when you're ready.
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
