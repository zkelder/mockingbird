import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  SavedMediaCleanupDryRunResponse,
  SavedMediaRetentionItem,
  SavedMediaRetentionReportResponse,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

const riskLevels = ["low", "medium", "high", "protected"];

function formatBytes(bytes?: number | null): string {
  if (bytes == null) {
    return "Unknown";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function riskTone(riskLevel: string): "low" | "medium" | "high" | "protected" | "unknown" {
  if (
    riskLevel === "low" ||
    riskLevel === "medium" ||
    riskLevel === "high" ||
    riskLevel === "protected"
  ) {
    return riskLevel;
  }
  return "unknown";
}

function riskDescription(riskLevel: string): string {
  if (riskLevel === "low") {
    return "Unlinked saved preview media";
  }
  if (riskLevel === "medium") {
    return "Linked to pending or ignored evidence";
  }
  if (riskLevel === "high") {
    return "Linked to promoted Event/Visit context";
  }
  if (riskLevel === "protected") {
    return "Protected media with reviewed correction context";
  }
  return "Inspect manually before cleanup";
}

function yesNo(value: boolean): string {
  return value ? "Yes" : "No";
}

function RetentionWarningList({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <div className="retention-warning-list">
      {warnings.map((warning) => (
        <span key={warning}>{warning}</span>
      ))}
    </div>
  );
}

function RetentionLinkage({ item }: { item: SavedMediaRetentionItem }) {
  return (
    <div className="retention-linkage-grid">
      <div>
        <span>MotionEvidence</span>
        <strong>{item.linked_motion_evidence_count}</strong>
      </div>
      <div>
        <span>Events</span>
        <strong>{item.linked_event_count}</strong>
      </div>
      <div>
        <span>Visits</span>
        <strong>{item.linked_visit_count}</strong>
      </div>
      <div>
        <span>Reviewed truth</span>
        <strong>{item.reviewed_truth_count}</strong>
      </div>
    </div>
  );
}

function RetentionItemCard({ item }: { item: SavedMediaRetentionItem }) {
  return (
    <article className="retention-item-card">
      <div className="section-heading">
        <div>
          <h3>{item.file_name ?? item.media_asset_id}</h3>
          <span className="meta-text">{item.media_asset_id}</span>
        </div>
        <span className={`risk-badge risk-badge-${riskTone(item.risk_level)}`}>
          {formatLabel(item.risk_level)}
        </span>
      </div>

      <p className="retention-risk-copy">{riskDescription(item.risk_level)}</p>

      <div className="retention-detail-grid">
        <div>
          <span>Media state</span>
          <strong>{formatLabel(item.media_state)}</strong>
        </div>
        <div>
          <span>Size</span>
          <strong>{formatBytes(item.size_bytes)}</strong>
        </div>
        <div>
          <span>Content type</span>
          <strong>{item.content_type ?? "Unknown"}</strong>
        </div>
        <div>
          <span>Provider</span>
          <strong>{item.provider_key ?? "Unknown"}</strong>
        </div>
        <div>
          <span>Source</span>
          <strong>{item.source_id ?? "None"}</strong>
        </div>
        <div>
          <span>Stream</span>
          <strong>{item.stream_id ?? "None"}</strong>
        </div>
        <div>
          <span>Saved</span>
          <strong>{item.created_at ? formatDateTime(item.created_at) : "Unknown"}</strong>
        </div>
        <div>
          <span>Fetched</span>
          <strong>{item.fetched_at ? formatDateTime(item.fetched_at) : "Unknown"}</strong>
        </div>
      </div>

      <RetentionLinkage item={item} />

      <div className="retention-provenance">
        <span>Provenance</span>
        <strong>{item.provenance ?? "Saved external_url preview"}</strong>
      </div>

      <div className="notice-panel compact-notice">
        <strong>Recommended action</strong>
        <span>{item.recommended_action}</span>
      </div>

      <RetentionWarningList warnings={item.warnings} />
    </article>
  );
}

export function SavedMediaRetentionPage() {
  const [report, setReport] = useState<SavedMediaRetentionReportResponse | null>(null);
  const [dryRunResult, setDryRunResult] = useState<SavedMediaCleanupDryRunResponse | null>(null);
  const [selectedRiskLevels, setSelectedRiskLevels] = useState<string[]>(["low"]);
  const [includeProtected, setIncludeProtected] = useState(false);
  const [mode, setMode] = useState("delete_file_only");
  const [isLoading, setIsLoading] = useState(true);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dryRunError, setDryRunError] = useState<string | null>(null);

  async function loadReport(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      setReport(await apiClient.getSavedMediaRetentionReport());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load saved media retention.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadReport();
  }, []);

  const sortedItems = useMemo(() => {
    if (!report) {
      return [];
    }
    const order = { protected: 0, high: 1, medium: 2, low: 3 };
    return [...report.items].sort((first, second) => {
      const firstOrder = order[first.risk_level as keyof typeof order] ?? 4;
      const secondOrder = order[second.risk_level as keyof typeof order] ?? 4;
      return firstOrder - secondOrder || first.media_asset_id.localeCompare(second.media_asset_id);
    });
  }, [report]);

  function toggleRiskLevel(riskLevel: string) {
    setSelectedRiskLevels((current) =>
      current.includes(riskLevel)
        ? current.filter((selected) => selected !== riskLevel)
        : [...current, riskLevel],
    );
  }

  async function runDryRun() {
    setIsDryRunning(true);
    setDryRunError(null);
    try {
      setDryRunResult(
        await apiClient.dryRunSavedMediaCleanup({
          risk_levels: selectedRiskLevels,
          include_protected: includeProtected,
          mode,
        }),
      );
    } catch (caught) {
      setDryRunError(
        caught instanceof Error ? caught.message : "Could not run saved media dry-run.",
      );
    } finally {
      setIsDryRunning(false);
    }
  }

  if (isLoading) {
    return <div className="panel">Loading saved media retention...</div>;
  }

  if (error) {
    return (
      <div className="error-panel">
        <strong>Saved media retention is unavailable.</strong>
        <span>{error}</span>
        <button className="secondary-action" onClick={() => void loadReport()}>
          Retry
        </button>
      </div>
    );
  }

  if (!report) {
    return <div className="panel">Saved media retention is unavailable.</div>;
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Local storage visibility"
        title="Saved Media Retention"
        description="Review saved external_url preview media, risk level, and dry-run cleanup planning without deleting files, deleting records, or changing reviewed truth."
        actions={
          <button className="secondary-action" onClick={() => void loadReport({ showLoading: false })}>
            Refresh report
          </button>
        }
      />

      <section className="notice-panel retention-boundary-panel">
        <strong>Dry run only</strong>
        <span>No files deleted. No records deleted. No truth changed.</span>
      </section>

      <section className="panel retention-report-status">
        <div>
          <h2>Report status</h2>
          <p>
            Generated {formatDateTime(report.generated_at)}. The report reads saved preview media
            metadata and linkage only.
          </p>
        </div>
        <StatusPill label={report.dry_run_only ? "Dry-run only" : "Check report"} tone="review" />
      </section>

      {report.summary.warnings.length > 0 ? (
        <section className="notice-panel readiness-warning">
          <strong>Report warnings</strong>
          <RetentionWarningList warnings={report.summary.warnings} />
        </section>
      ) : null}

      <section className="metric-grid">
        <MetricCard label="Saved previews" value={report.summary.total_items} detail="reported items" />
        <MetricCard
          label="Known bytes"
          value={formatBytes(report.summary.total_known_bytes)}
          detail={`${report.summary.unknown_size_count} unknown size`}
        />
        <MetricCard label="Low risk" value={report.summary.low_risk_count} detail="unlinked media" />
        <MetricCard
          label="Protected"
          value={report.summary.protected_count}
          detail="reviewed correction context"
        />
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Medium risk"
          value={report.summary.medium_risk_count}
          detail="pending or ignored evidence"
        />
        <MetricCard
          label="High risk"
          value={report.summary.high_risk_count}
          detail="promoted Event/Visit context"
        />
        <MetricCard
          label="Unknown size"
          value={report.summary.unknown_size_count}
          detail="metadata incomplete"
        />
        <MetricCard label="Dry-run only" value={report.dry_run_only ? "Yes" : "No"} />
      </section>

      <section className="panel retention-dry-run-panel">
        <div className="section-heading">
          <div>
            <h2>Dry-run cleanup</h2>
            <span className="meta-text">
              Plan future cleanup candidates by risk level. This action writes nothing.
            </span>
          </div>
          <StatusPill label="No files deleted" tone="review" />
        </div>

        <div className="retention-dry-run-form">
          <fieldset>
            <legend>Risk level</legend>
            <div className="retention-checkbox-grid">
              {riskLevels.map((riskLevel) => (
                <label className="checkbox-row" key={riskLevel}>
                  <input
                    checked={selectedRiskLevels.includes(riskLevel)}
                    onChange={() => toggleRiskLevel(riskLevel)}
                    type="checkbox"
                  />
                  {formatLabel(riskLevel)}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="checkbox-row retention-include-protected">
            <input
              checked={includeProtected}
              onChange={(event) => setIncludeProtected(event.target.checked)}
              type="checkbox"
            />
            Include protected media
          </label>

          <label>
            Mode
            <select onChange={(event) => setMode(event.target.value)} value={mode}>
              <option value="delete_file_only">delete_file_only</option>
              <option value="delete_media_asset">delete_media_asset</option>
              <option value="archive">archive</option>
            </select>
          </label>
        </div>

        <div className="notice-panel compact-notice">
          <strong>Dry run only. No files or records were deleted.</strong>
          <span>
            Protected media is skipped unless included here, and this page still performs only a
            dry-run cleanup preview.
          </span>
        </div>

        <div className="detail-actions">
          <button
            className="primary-action"
            disabled={isDryRunning}
            onClick={() => void runDryRun()}
            type="button"
          >
            {isDryRunning ? "Running dry-run..." : "Run dry-run"}
          </button>
        </div>

        {dryRunError ? <div className="error-panel compact-error">{dryRunError}</div> : null}

        {dryRunResult ? (
          <section className="retention-dry-run-result">
            <div className="section-heading">
              <div>
                <h3>Dry-run cleanup preview</h3>
                <span className="meta-text">
                  Dry run only. No files or records were deleted.
                </span>
              </div>
              <StatusPill label={dryRunResult.dry_run ? "Dry run" : "Check result"} tone="review" />
            </div>

            <div className="retention-dry-run-summary">
              <div>
                <span>Would delete files</span>
                <strong>{dryRunResult.total_would_delete_files}</strong>
              </div>
              <div>
                <span>Would delete records</span>
                <strong>{dryRunResult.total_would_delete_records}</strong>
              </div>
              <div>
                <span>Known bytes</span>
                <strong>{formatBytes(dryRunResult.total_known_bytes_to_delete)}</strong>
              </div>
              <div>
                <span>Skipped</span>
                <strong>{dryRunResult.skipped_count}</strong>
              </div>
              <div>
                <span>Protected skipped</span>
                <strong>{dryRunResult.protected_skipped_count}</strong>
              </div>
              <div>
                <span>Creates truth</span>
                <strong>{yesNo(dryRunResult.creates_truth)}</strong>
              </div>
              <div>
                <span>Deletes truth</span>
                <strong>{yesNo(dryRunResult.deletes_truth)}</strong>
              </div>
            </div>

            <RetentionWarningList warnings={dryRunResult.warnings} />

            {dryRunResult.items.length > 0 ? (
              <div className="retention-dry-run-items">
                {dryRunResult.items.map((item) => (
                  <article className="retention-dry-run-item" key={item.media_asset_id}>
                    <div className="section-heading">
                      <div>
                        <h4>{item.file_name ?? item.media_asset_id}</h4>
                        <span className="meta-text">{item.media_asset_id}</span>
                      </div>
                      <span className={`risk-badge risk-badge-${riskTone(item.risk_level)}`}>
                        {formatLabel(item.risk_level)}
                      </span>
                    </div>
                    <div className="retention-detail-grid">
                      <div>
                        <span>Would delete file</span>
                        <strong>{yesNo(item.would_delete_file)}</strong>
                      </div>
                      <div>
                        <span>Would delete record</span>
                        <strong>{yesNo(item.would_delete_record)}</strong>
                      </div>
                      <div>
                        <span>Would skip</span>
                        <strong>{yesNo(item.would_skip)}</strong>
                      </div>
                      <div>
                        <span>Skip reason</span>
                        <strong>{item.skip_reason ? formatLabel(item.skip_reason) : "None"}</strong>
                      </div>
                      <div>
                        <span>Size</span>
                        <strong>{formatBytes(item.size_bytes)}</strong>
                      </div>
                    </div>
                    <RetentionWarningList warnings={item.warnings} />
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No dry-run candidates"
                description="The selected risk filters did not return saved preview media candidates."
              />
            )}
          </section>
        ) : null}
      </section>

      <section className="panel retention-item-list-panel">
        <div className="section-heading">
          <div>
            <h2>Saved preview MediaAssets</h2>
            <span className="meta-text">
              File names, safe provenance, linkage counts, and risk level only.
            </span>
          </div>
        </div>

        {sortedItems.length > 0 ? (
          <div className="retention-item-list">
            {sortedItems.map((item) => (
              <RetentionItemCard item={item} key={item.media_asset_id} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No saved preview media"
            description="Saved external_url previews will appear here after an explicit save action."
          />
        )}
      </section>
    </div>
  );
}
