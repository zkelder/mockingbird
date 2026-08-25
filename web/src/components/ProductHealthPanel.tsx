import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { ProductHealthStatus, StorageSummary } from "../api/types";
import { StatusPill } from "./StatusPill";
import { formatBytes, formatDateTime } from "../utils";

interface ProductHealthPanelProps {
  /** Already fetched by the Dashboard for its own storage-warning banner --
   * threaded in here rather than a second fetch (this panel has exactly one
   * call site today). `null`/`undefined` while unavailable or not yet
   * loaded simply omits the facts that depend on it, matching this panel's
   * existing "unreadable status is a silent no-op" convention. */
  storageSummary?: StorageSummary | null;
}

/**
 * MockingBird Installable Local Product v1: one lightweight, basic-first
 * product status area (see docs/local-product-packaging-design.md).
 * Consolidates facts that already exist elsewhere (storage, camera
 * attention, observation counts, backup status) rather than computing
 * anything new; advanced-only facts stay collapsed, matching the existing
 * Observation panel's "Advanced diagnostics" convention. An unreadable
 * status is a silent no-op, not an error banner -- this is a supporting
 * summary, not required product context.
 *
 * Appliance / Storage / Privacy / Recovery v1, Phase C/N: extended (still a
 * compact panel, not a storage-administrator console -- that remains Local
 * Data's job) to also show total storage usage, the graduated 4-tier
 * storage_health_tier reading, and a plain-language category breakdown.
 */
export function ProductHealthPanel({ storageSummary }: ProductHealthPanelProps = {}) {
  const [health, setHealth] = useState<ProductHealthStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    void apiClient
      .getProductHealth()
      .then((next) => {
        if (!cancelled) setHealth(next);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  if (!health) {
    return null;
  }

  // Not-writable is a permissions problem, orthogonal to the disk-space
  // tier ladder below -- it stays the most severe, distinct state and is
  // never masked by an otherwise-"healthy" tier reading. Writable/low-space
  // are otherwise the same disk facts the tier ladder already summarizes
  // more precisely, so the old tri-state line is replaced rather than
  // duplicated alongside it.
  const storageStateLabel = !health.storage_writable
    ? "Not writable"
    : {
        healthy: "Healthy",
        getting_low: "Getting low",
        action_recommended: "Action recommended",
        critical: "Critically low",
      }[health.storage_health_tier];

  const totalUsageBytes =
    storageSummary != null
      ? storageSummary.total_managed_media_bytes + (storageSummary.approximate_database_bytes ?? 0)
      : null;
  const cleanupEligibleBytes =
    storageSummary != null
      ? storageSummary.superseded_only_media_bytes + storageSummary.orphaned_managed_media_bytes
      : null;

  return (
    <section aria-label="MockingBird status" className="panel product-health-panel">
      <div className="section-heading">
        <div>
          <h2>MockingBird status</h2>
          <span className="meta-text">{health.message}</span>
        </div>
        <StatusPill label={health.ready ? "Ready" : "Needs attention"} tone={health.ready ? "good" : "review"} />
      </div>
      <div className="monitoring-continuity-facts">
        <span>
          <strong>Storage</strong> {storageStateLabel}
        </span>
        {totalUsageBytes != null ? (
          <span>
            <strong>Total usage</strong> {formatBytes(totalUsageBytes)}
          </span>
        ) : null}
        <span>
          <strong>Cameras needing attention</strong> {health.cameras.needs_attention_count}
        </span>
        <span>
          <strong>Observing</strong> {health.observation.monitored_stream_count} of{" "}
          {health.observation.configured_stream_count} cameras
        </span>
        <span>
          <strong>Backup</strong>{" "}
          {health.backup.has_backup ? (
            health.backup.last_backup_verified ? "Verified" : "Not yet verified"
          ) : health.backup.suggest_first_backup ? (
            <a href="/local-data">Create your first backup</a>
          ) : (
            "None yet"
          )}
        </span>
      </div>
      {storageSummary ? (
        <span className="meta-text">
          {formatBytes(storageSummary.active_visit_media_bytes)} in active use ·{" "}
          {storageSummary.reviewed_bird_wildlife_evidence_count} confirmed wildlife photo
          {storageSummary.reviewed_bird_wildlife_evidence_count === 1 ? "" : "s"} kept ·{" "}
          {formatBytes(cleanupEligibleBytes ?? 0)} eligible for cleanup
        </span>
      ) : null}
      {health.backup.suggest_first_backup ? (
        <div className="notice-panel">
          <span>
            You haven't created a backup yet. Your local data (Streams, Zones, reviewed Visits,
            and history) can be protected in one click from{" "}
            <a href="/local-data">Local Data</a>.
          </span>
        </div>
      ) : null}
      {health.previous_shutdown_clean === false ? (
        <div className="notice-panel">
          <span>MockingBird did not shut down cleanly last time. Your local data is unaffected.</span>
        </div>
      ) : null}
      {health.database_migrated_from_version != null ? (
        <div className="notice-panel">
          <span>
            MockingBird updated your data on this start (format {health.database_migrated_from_version}{" "}
            &rarr; {health.database_schema_version}). A backup from just before the update was made
            automatically and is available in <a href="/local-data">Local Data</a>.
          </span>
        </div>
      ) : null}
      <details className="review-diagnostic-details">
        <summary>Advanced diagnostics</summary>
        <div className="review-diagnostic-grid">
          <span>App version: {health.app_version}</span>
          <span>Database format: {health.database_schema_version}</span>
          <span>Backup format: {health.backup_format_version}</span>
          <span>Camera Node API: {health.camera_node_api_version}</span>
          <span>Transport protocol: {health.transport_protocol_version}</span>
          {health.log_path ? <span>Log file: {health.log_path}</span> : null}
          {health.backup.last_backup_at ? (
            <span>Last backup: {formatDateTime(health.backup.last_backup_at)}</span>
          ) : null}
        </div>
      </details>
    </section>
  );
}
