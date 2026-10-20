import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { OrphanMediaScanResponse, OrphanQuarantineBatch } from "../api/types";
import { formatBytes, userFacingErrorMessage } from "../utils";

// Orphan Media Integrity & Recovery v1. A check is report-only; moving files to
// the recovery folder is a separate, confirmed action. Nothing is ever deleted.
export function StorageIntegrityPanel() {
  const [scan, setScan] = useState<OrphanMediaScanResponse | null>(null);
  const [batches, setBatches] = useState<OrphanQuarantineBatch[]>([]);
  const [operation, setOperation] = useState<string | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadBatches() {
    try {
      setBatches((await apiClient.getOrphanMediaQuarantineHistory()).batches);
    } catch {
      setBatches([]);
    }
  }

  useEffect(() => {
    void loadBatches();
  }, []);

  async function run(name: string, action: () => Promise<void>, fallback: string) {
    setOperation(name);
    setError(null);
    setMessage(null);
    try {
      await action();
    } catch (caught) {
      setError(userFacingErrorMessage(caught, fallback));
    } finally {
      setOperation(null);
    }
  }

  const unowned = scan?.findings.filter((item) => item.kind === "unowned") ?? [];

  return (
    <div className="storage-integrity" aria-label="Storage integrity">
      <h3>Storage integrity</h3>
      <p className="meta-text">
        Checks that every saved photo or clip belongs to an observation. Checking changes nothing.
      </p>
      <div className="local-data-actions">
        <button
          className="secondary-action"
          disabled={operation !== null}
          onClick={() =>
            void run(
              "scan",
              async () => {
                setIsConfirming(false);
                setScan(await apiClient.scanOrphanMedia());
              },
              "Could not check storage integrity.",
            )
          }
          type="button"
        >
          {operation === "scan" ? "Checking..." : "Check storage integrity"}
        </button>
      </div>

      {error ? <p role="alert">{error}</p> : null}
      {message ? <p role="status">{message}</p> : null}

      {scan ? (
        <div className="notice-panel" role="status">
          <strong>
            {scan.status === "clean"
              ? "No unowned media found"
              : scan.status === "incomplete"
                ? "Check could not finish"
                : `Unowned media found: ${scan.orphan_count} · ${formatBytes(scan.orphan_bytes)}`}
          </strong>
          {scan.status === "clean" ? null : <span>{scan.message}</span>}
          {scan.status === "orphans_found" ? (
            <>
              <details className="advanced-details">
                <summary>Review files ({unowned.length}{scan.findings_truncated ? "+" : ""})</summary>
                <ul>
                  {unowned.map((item) => (
                    <li key={item.relative_path}>
                      {item.relative_path} · {formatBytes(item.size_bytes)}
                    </li>
                  ))}
                </ul>
                {scan.findings_truncated ? (
                  <span>Only the first files are listed. Move these, then check again.</span>
                ) : null}
              </details>
              {isConfirming ? (
                <span>
                  Confirm to move the listed files to a recovery folder. They are not deleted and can be moved back.
                </span>
              ) : null}
              <div className="local-data-actions">
                <button
                  className={isConfirming ? "primary-action" : "secondary-action"}
                  disabled={operation !== null || unowned.length === 0}
                  onClick={() => {
                    if (!isConfirming) {
                      setIsConfirming(true);
                      return;
                    }
                    void run(
                      "quarantine",
                      async () => {
                        const result = await apiClient.quarantineOrphanMedia(unowned.map((item) => item.relative_path));
                        setMessage(result.message);
                        setIsConfirming(false);
                        setScan(null);
                        await loadBatches();
                      },
                      "Could not move the unowned media safely.",
                    );
                  }}
                  type="button"
                >
                  {operation === "quarantine"
                    ? "Moving..."
                    : isConfirming
                      ? "Confirm: Move to recovery folder"
                      : "Review recovery options"}
                </button>
                {isConfirming ? (
                  <button className="secondary-action" disabled={operation !== null} onClick={() => setIsConfirming(false)} type="button">
                    Cancel
                  </button>
                ) : null}
              </div>
            </>
          ) : null}
          {scan.unsafe_entry_count > 0 ? (
            <span>{scan.unsafe_entry_count} unusual item(s) (links or special files) were skipped and left untouched.</span>
          ) : null}
          {scan.status === "incomplete" ? (
            <details className="advanced-details">
              <summary>Details</summary>
              <span>{scan.incomplete_reasons.join(", ")}</span>
            </details>
          ) : null}
        </div>
      ) : null}

      {batches.length > 0 ? (
        <details className="advanced-details">
          <summary>Unowned media moved to recovery ({batches.length})</summary>
          {batches.map((batch) => (
            <div className="data-row" key={batch.batch_id}>
              <span>
                {new Date(batch.created_at).toLocaleString()} · {batch.moved_count - batch.restored_count > 0 ? `${batch.moved_count - batch.restored_count} still in recovery` : "all moved back"}
              </span>
              {batch.moved_count - batch.restored_count > 0 ? (
                <button
                  className="secondary-action"
                  disabled={operation !== null}
                  onClick={() =>
                    void run(
                      `restore:${batch.batch_id}`,
                      async () => {
                        const result = await apiClient.restoreOrphanMediaQuarantine(batch.batch_id);
                        setMessage(result.message);
                        await loadBatches();
                      },
                      "Could not move the files back.",
                    )
                  }
                  type="button"
                >
                  {operation === `restore:${batch.batch_id}` ? "Moving back..." : "Move back"}
                </button>
              ) : null}
            </div>
          ))}
        </details>
      ) : null}
    </div>
  );
}
