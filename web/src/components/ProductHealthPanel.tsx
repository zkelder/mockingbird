import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { ProductHealthStatus } from "../api/types";
import { StatusPill } from "./StatusPill";
import { formatDateTime } from "../utils";

/**
 * MockingBird Installable Local Product v1: one lightweight, basic-first
 * product status area (see docs/local-product-packaging-design.md).
 * Consolidates facts that already exist elsewhere (storage, camera
 * attention, observation counts, backup status) rather than computing
 * anything new; advanced-only facts stay collapsed, matching the existing
 * Observation panel's "Advanced diagnostics" convention. An unreadable
 * status is a silent no-op, not an error banner -- this is a supporting
 * summary, not required product context.
 */
export function ProductHealthPanel() {
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

  const storageLabel = !health.storage_writable
    ? "Not writable"
    : health.storage_low_space
      ? "Low space"
      : "Writable";

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
          <strong>Storage</strong> {storageLabel}
        </span>
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
      <details className="review-diagnostic-details">
        <summary>Advanced diagnostics</summary>
        <div className="review-diagnostic-grid">
          <span>App version: {health.app_version}</span>
          <span>Database format: {health.database_schema_version}</span>
          {health.log_path ? <span>Log file: {health.log_path}</span> : null}
          {health.backup.last_backup_at ? (
            <span>Last backup: {formatDateTime(health.backup.last_backup_at)}</span>
          ) : null}
        </div>
      </details>
    </section>
  );
}
