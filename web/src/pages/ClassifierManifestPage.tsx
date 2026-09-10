import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ClassifierManifestFileExportResponse,
  ClassifierTrainingManifestResponse,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel, sortedEntries } from "../utils";

interface ClassifierManifestPageProps {
  onOpenClassifierReadiness: () => void;
  onOpenExports: () => void;
  onOpenReview: () => void;
}

function compactId(value?: string | null): string {
  return value && value.trim() ? value : "None";
}

function formatList(values: string[]): string {
  return values.length > 0 ? values.join(", ") : "None";
}

function buildManifestJson(manifest: ClassifierTrainingManifestResponse): string {
  return JSON.stringify(manifest, null, 2);
}

function formatBytes(bytes?: number | null): string {
  if (bytes == null) {
    return "Planned";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function countSkippedReasons(manifest: ClassifierTrainingManifestResponse): Record<string, number> {
  return manifest.skipped_records.reduce<Record<string, number>>((counts, record) => {
    counts[record.reason] = (counts[record.reason] ?? 0) + 1;
    return counts;
  }, {});
}

export function ClassifierManifestPage({
  onOpenClassifierReadiness,
  onOpenExports,
  onOpenReview,
}: ClassifierManifestPageProps) {
  const [manifest, setManifest] = useState<ClassifierTrainingManifestResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [includeCsv, setIncludeCsv] = useState(false);
  const [includeSummary, setIncludeSummary] = useState(true);
  const [outputName, setOutputName] = useState("");
  const [splitSeed, setSplitSeed] = useState("");
  const [exportResult, setExportResult] =
    useState<ClassifierManifestFileExportResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportAction, setExportAction] = useState<"dry_run" | "create" | null>(null);
  // Render caps only -- the manifest walks every reviewed/dataset-ready
  // Visit with no limit, so both lists grow with the size of the whole
  // locally reviewed dataset. Mirrors StreamDetailPage's "Show more events"
  // convention.
  const [visibleExampleCount, setVisibleExampleCount] = useState(15);
  const [visibleSkippedCount, setVisibleSkippedCount] = useState(15);

  async function loadManifest() {
    setIsLoading(true);
    setError(null);
    setMessage(null);
    try {
      setManifest(await apiClient.getClassifierTrainingManifest());
      setVisibleExampleCount(15);
      setVisibleSkippedCount(15);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load classifier manifest.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadManifest();
  }, []);

  const manifestJson = useMemo(() => (manifest ? buildManifestJson(manifest) : ""), [manifest]);
  const skippedReasonCounts = useMemo(
    () => (manifest ? countSkippedReasons(manifest) : {}),
    [manifest],
  );
  const warnings = useMemo(
    () => Array.from(new Set([...(manifest?.warnings ?? []), ...(manifest?.summary.warnings ?? [])])),
    [manifest],
  );

  async function copyJson() {
    if (!manifestJson) {
      return;
    }
    setError(null);
    setMessage(null);
    if (!navigator.clipboard?.writeText) {
      setError("Clipboard access is not available in this browser. Use Download JSON preview instead.");
      return;
    }
    try {
      await navigator.clipboard.writeText(manifestJson);
      setMessage("Manifest JSON copied to clipboard.");
    } catch {
      setError("Clipboard copy failed. Use Download JSON preview instead.");
    }
  }

  function downloadJsonPreview() {
    if (!manifestJson) {
      return;
    }
    setError(null);
    const blob = new Blob([manifestJson], { type: "application/json" });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = "classifier-training-manifest-preview.json";
    link.click();
    URL.revokeObjectURL(objectUrl);
    setMessage("Browser JSON preview download started.");
  }

  async function runMetadataExport(dryRun: boolean) {
    setExportAction(dryRun ? "dry_run" : "create");
    setExportError(null);
    setExportMessage(null);
    try {
      const result = await apiClient.createClassifierManifestExport({
        include_csv: includeCsv,
        include_summary: includeSummary,
        output_name: outputName.trim() ? outputName.trim() : null,
        split_seed: splitSeed.trim() ? splitSeed.trim() : null,
        media_policy: "reference_only",
        dry_run: dryRun,
      });
      setExportResult(result);
      setExportMessage(
        dryRun
          ? "Dry run complete. No files were written."
          : "Metadata export created. Review the local output directory before external training work.",
      );
    } catch (caught) {
      setExportError(caught instanceof Error ? caught.message : "Could not create metadata export.");
    } finally {
      setExportAction(null);
    }
  }

  async function copyOutputDirectory() {
    if (!exportResult?.output_directory) {
      return;
    }
    setExportError(null);
    if (!navigator.clipboard?.writeText) {
      setExportError("Clipboard access is not available in this browser.");
      return;
    }
    try {
      await navigator.clipboard.writeText(exportResult.output_directory);
      setExportMessage("Output directory copied to clipboard.");
    } catch {
      setExportError("Clipboard copy failed.");
    }
  }

  if (isLoading) {
    return <div className="panel">Loading classifier manifest preview...</div>;
  }

  if (error && !manifest) {
    return (
      <div className="error-panel">
        <strong>Could not load classifier manifest preview.</strong>
        <span>{error}</span>
        <button className="secondary-action" onClick={() => void loadManifest()}>
          Retry
        </button>
      </div>
    );
  }

  if (!manifest) {
    return <div className="panel">Classifier manifest preview is unavailable.</div>;
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Developer tool"
        title="Classifier Training Manifest"
        description="Developer-facing manifest preview for later external training review. It does not copy media, train models, or create reviewed truth."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenClassifierReadiness}>
              Classifier Readiness
            </button>
            <button className="secondary-action" onClick={() => void copyJson()}>
              Copy JSON
            </button>
            <button className="secondary-action" onClick={downloadJsonPreview}>
              Download JSON preview
            </button>
          </>
        }
      />

      <section className="notice-panel">
        <strong>Developer tool — metadata preview only</strong>
        <span>
          Use Exports / Data for the product path. Manifest files are future classifier review
          metadata and do not replace corrections.
        </span>
      </section>

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="notice-panel">
        <strong>Reviewed corrections are training truth</strong>
        <span>Metadata export does not review Visits, train models, or create truth.</span>
      </section>

      <section className="metric-grid">
        <MetricCard label="Examples" value={manifest.summary.examples} detail="reviewed media-backed" />
        <MetricCard label="Skipped" value={manifest.summary.skipped} detail="explicit reasons" />
        <MetricCard label="Labels" value={Object.keys(manifest.summary.labels).length} detail="included classes" />
        <MetricCard label="Taxonomy" value={manifest.taxonomy.length} detail="target species" />
      </section>

      <section className="panel classifier-manifest-export-panel">
        <div className="section-heading">
          <div>
            <h2>Metadata export</h2>
            <span className="meta-text">
              This writes classifier manifest metadata files only. It does not copy media, train
              models, or create reviewed truth.
            </span>
          </div>
          <EvidenceBadge label="reference_only" tone="quiet" />
        </div>

        <div className="manifest-export-form" aria-label="Classifier manifest metadata export">
          <label className="checkbox-row">
            <input
              checked={includeCsv}
              onChange={(event) => setIncludeCsv(event.target.checked)}
              type="checkbox"
            />
            Include manifest.csv
          </label>
          <label className="checkbox-row">
            <input
              checked={includeSummary}
              onChange={(event) => setIncludeSummary(event.target.checked)}
              type="checkbox"
            />
            Include summary.json
          </label>
          <label>
            Output name
            <input
              onChange={(event) => setOutputName(event.target.value)}
              placeholder="optional-safe-export-name"
              value={outputName}
            />
          </label>
          <label>
            Split seed
            <input
              onChange={(event) => setSplitSeed(event.target.value)}
              placeholder="optional seed note"
              value={splitSeed}
            />
          </label>
          <div className="locked-field">
            <span className="metric-label">Media policy</span>
            <strong>reference_only</strong>
          </div>
        </div>

        <div className="notice-panel manifest-truth-boundary">
          <strong>Export boundary</strong>
          <span>Uses reviewed corrections only. Suggestions and evidence stay evidence.</span>
        </div>

        <div className="detail-actions">
          <button
            className="secondary-action"
            disabled={exportAction !== null}
            onClick={() => void runMetadataExport(true)}
            type="button"
          >
            {exportAction === "dry_run" ? "Checking..." : "Dry run"}
          </button>
          <button
            className="primary-action"
            disabled={exportAction !== null}
            onClick={() => void runMetadataExport(false)}
            type="button"
          >
            {exportAction === "create" ? "Creating..." : "Create metadata export"}
          </button>
        </div>

        {exportMessage ? <div className="notice-panel">{exportMessage}</div> : null}
        {exportError ? <div className="error-panel">{exportError}</div> : null}

        {exportResult ? (
          <div className="manifest-export-result">
            <div className="section-heading">
              <div>
                <h3>{exportResult.dry_run ? "Dry-run plan" : "Created export"}</h3>
                <span className="meta-text">
                  {exportResult.dry_run
                    ? "Dry run: no files written"
                    : `Created ${formatDateTime(exportResult.created_at)}`}
                </span>
              </div>
              <StatusPill
                label={exportResult.dry_run ? "No files written" : "Metadata files created"}
                tone={exportResult.dry_run ? "review" : "good"}
              />
            </div>

            <div className="manifest-export-grid">
              <div>
                <span className="metric-label">Export ID</span>
                <strong>{exportResult.export_id}</strong>
              </div>
              <div>
                <span className="metric-label">Examples</span>
                <strong>{exportResult.examples}</strong>
              </div>
              <div>
                <span className="metric-label">Skipped</span>
                <strong>{exportResult.skipped}</strong>
              </div>
              <div>
                <span className="metric-label">Output directory</span>
                <strong>{exportResult.output_directory ?? "None"}</strong>
              </div>
            </div>

            {exportResult.output_directory ? (
              <div className="detail-actions">
                <button
                  className="secondary-action"
                  onClick={() => void copyOutputDirectory()}
                  type="button"
                >
                  Copy output directory
                </button>
              </div>
            ) : null}

            <div className="manifest-file-list" role="table" aria-label="Classifier manifest export files">
              <div className="manifest-file-row manifest-file-head" role="row">
                <span role="columnheader">Name</span>
                <span role="columnheader">Relative path</span>
                <span role="columnheader">Content type</span>
                <span role="columnheader">Size</span>
              </div>
              {exportResult.files.map((file) => (
                <div className="manifest-file-row" key={file.name} role="row">
                  <strong role="cell">{file.name}</strong>
                  <span role="cell">{file.relative_path}</span>
                  <span role="cell">{file.content_type}</span>
                  <span role="cell">{formatBytes(file.size_bytes)}</span>
                </div>
              ))}
            </div>

            {exportResult.warnings.length > 0 ? (
              <div className="readiness-warning-stack">
                {exportResult.warnings.map((warning) => (
                  <div className="notice-panel readiness-warning" key={warning}>
                    <strong>{warning}</strong>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="panel manifest-preview-status">
        <div>
          <div className="quality-issue-title">
            <h2>Preview summary</h2>
            <StatusPill
              label={manifest.examples.length > 0 ? "Contains examples" : "No examples yet"}
              tone={manifest.examples.length > 0 ? "good" : "review"}
            />
          </div>
          <p>
            Version {manifest.manifest_version} generated {formatDateTime(manifest.generated_at)}.
          </p>
        </div>
        <div className="detail-actions">
          <button className="secondary-action" onClick={() => void loadManifest()}>
            Refresh
          </button>
          <button className="secondary-action" onClick={onOpenReview}>
            Review Queue
          </button>
          <button className="secondary-action" onClick={onOpenExports}>
            Dataset Exports
          </button>
        </div>
      </section>

      <section className="split-grid">
        <div className="panel classifier-manifest-panel">
          <div className="section-heading">
            <div>
              <h2>Label summary</h2>
              <span className="meta-text">Included examples by normalized taxonomy label</span>
            </div>
          </div>
          {Object.keys(manifest.summary.labels).length > 0 ? (
            <div className="readiness-summary-list">
              {sortedEntries(manifest.summary.labels).map(([label, count]) => (
                <div className="summary-row" key={label}>
                  <span>{formatLabel(label)}</span>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No included labels"
              description="Review media-backed Visits with target bird labels first."
            />
          )}
        </div>

        <div className="panel classifier-manifest-panel">
          <div className="section-heading">
            <div>
              <h2>Split summary</h2>
              <span className="meta-text">Deterministic preview split assignment</span>
            </div>
          </div>
          {Object.keys(manifest.summary.splits).length > 0 ? (
            <div className="readiness-summary-list">
              {sortedEntries(manifest.summary.splits).map(([split, count]) => (
                <div className="summary-row" key={split}>
                  <span>{formatLabel(split)}</span>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No split assignments"
              description="No reviewed examples are included yet."
            />
          )}
        </div>
      </section>

      <section className="panel classifier-manifest-panel">
        <div className="section-heading">
          <div>
            <h2>Examples</h2>
            <span className="meta-text">Reviewed media-backed examples included in the preview</span>
          </div>
          <EvidenceBadge label="Reviewed correction truth" tone="truth" />
        </div>
        {manifest.examples.length > 0 ? (
          <>
            <span className="meta-text">
              Showing {Math.min(visibleExampleCount, manifest.examples.length)} of{" "}
              {manifest.examples.length}
            </span>
            <div className="manifest-example-table" role="table" aria-label="Classifier manifest examples">
            <div className="manifest-example-row manifest-example-head" role="row">
              <span role="columnheader">Label and split</span>
              <span role="columnheader">Visit/Event</span>
              <span role="columnheader">Media</span>
              <span role="columnheader">Context</span>
              <span role="columnheader">Quality</span>
            </div>
            {manifest.examples.slice(0, visibleExampleCount).map((example) => (
              <div className="manifest-example-row" key={example.example_id} role="row">
                <div role="cell">
                  <strong>{formatLabel(example.label)}</strong>
                  <span className="manifest-inline-badges">
                    <EvidenceBadge label={formatLabel(example.split)} tone="quiet" />
                    {example.common_name ? (
                      <EvidenceBadge label={example.common_name} tone="truth" />
                    ) : null}
                  </span>
                </div>
                <div role="cell">
                  <span>Visit {example.visit_id}</span>
                  <span>Event {compactId(example.event_id)}</span>
                  <span>Review {compactId(example.reviewed_label_id)}</span>
                </div>
                <div role="cell">
                  <span>{example.media_asset_id}</span>
                  <small>{compactId(example.local_media_path)}</small>
                </div>
                <div role="cell">
                  <span>Source {compactId(example.source_id)}</span>
                  <span>Stream {compactId(example.stream_id)}</span>
                  <span>Zone {compactId(example.zone_id)}</span>
                </div>
                <div role="cell">
                  {example.quality_flags.length > 0 ? (
                    <span className="manifest-inline-badges">
                      {example.quality_flags.map((flag) => (
                        <EvidenceBadge label={formatLabel(flag)} tone="review" key={flag} />
                      ))}
                    </span>
                  ) : (
                    <span>No flags</span>
                  )}
                </div>
              </div>
            ))}
            </div>
            {manifest.examples.length > visibleExampleCount ? (
              <div className="panel-actions">
                <button
                  className="secondary-action"
                  onClick={() => setVisibleExampleCount((current) => current + 20)}
                  type="button"
                >
                  Show more examples ({manifest.examples.length - visibleExampleCount} more)
                </button>
              </div>
            ) : null}
          </>
        ) : (
          <EmptyState
            title="No manifest examples yet"
            description="Only reviewed media-backed target bird species examples appear here."
            action={
              <button className="secondary-action" onClick={onOpenReview}>
                Open Review Queue
              </button>
            }
          />
        )}
      </section>

      <section className="split-grid">
        <div className="panel classifier-manifest-panel">
          <div className="section-heading">
            <div>
              <h2>Skipped reason summary</h2>
              <span className="meta-text">Why candidate records are excluded</span>
            </div>
          </div>
          {Object.keys(skippedReasonCounts).length > 0 ? (
            <div className="readiness-summary-list">
              {sortedEntries(skippedReasonCounts).map(([reason, count]) => (
                <div className="summary-row" key={reason}>
                  <span>{formatLabel(reason)}</span>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No skipped records"
              description="Every candidate currently meets the manifest preview policy."
            />
          )}
        </div>

        <div className="panel classifier-manifest-panel">
          <div className="section-heading">
            <div>
              <h2>Warnings</h2>
              <span className="meta-text">Read before future export or training work</span>
            </div>
          </div>
          {warnings.length > 0 ? (
            <div className="readiness-warning-stack">
              {warnings.map((warning) => (
                <div className="notice-panel readiness-warning" key={warning}>
                  <strong>{warning}</strong>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No manifest warnings"
              description="The preview has no report-level warnings right now."
            />
          )}
        </div>
      </section>

      <section className="panel classifier-manifest-panel">
        <div className="section-heading">
          <div>
            <h2>Skipped records</h2>
            <span className="meta-text">Record-level exclusions with details</span>
          </div>
        </div>
        {manifest.skipped_records.length > 0 ? (
          <>
            <span className="meta-text">
              Showing {Math.min(visibleSkippedCount, manifest.skipped_records.length)} of{" "}
              {manifest.skipped_records.length}
            </span>
            <div className="manifest-skipped-list">
              {manifest.skipped_records.slice(0, visibleSkippedCount).map((record) => (
                <article className="record-card" key={record.record_id}>
                  <div className="section-heading">
                    <div>
                      <span className="meta-text">{record.record_type}</span>
                      <h3>{formatLabel(record.reason)}</h3>
                    </div>
                    <EvidenceBadge label="Skipped" tone="review" />
                  </div>
                  <div className="record-meta-grid">
                    <span>Visit {compactId(record.visit_id)}</span>
                    <span>Event {compactId(record.event_id)}</span>
                    <span>Media {compactId(record.media_asset_id)}</span>
                    <span>Label {record.label ? formatLabel(record.label) : "None"}</span>
                  </div>
                  {record.detail ? <p className="meta-text">{record.detail}</p> : null}
                </article>
              ))}
            </div>
            {manifest.skipped_records.length > visibleSkippedCount ? (
              <div className="panel-actions">
                <button
                  className="secondary-action"
                  onClick={() => setVisibleSkippedCount((current) => current + 20)}
                  type="button"
                >
                  Show more records ({manifest.skipped_records.length - visibleSkippedCount} more)
                </button>
              </div>
            ) : null}
          </>
        ) : (
          <EmptyState
            title="No skipped records"
            description="No candidate records are excluded from the current preview."
          />
        )}
      </section>

      <section className="panel classifier-manifest-panel">
        <div className="section-heading">
          <div>
            <h2>Taxonomy entries</h2>
            <span className="meta-text">Target species metadata included with the preview</span>
          </div>
        </div>
        {manifest.taxonomy.length > 0 ? (
          <div className="taxonomy-preview-grid">
            {manifest.taxonomy.map((entry) => (
              <article className="record-card" key={entry.label}>
                <span className="meta-text">{entry.taxonomy_id ?? entry.label}</span>
                <h3>{entry.common_name ?? formatLabel(entry.label)}</h3>
                <div className="record-meta-grid">
                  <span>Label {entry.label}</span>
                  <span>Scientific {entry.scientific_name ?? "None"}</span>
                  <span>Aliases {entry.aliases.length}</span>
                  <span>{formatList(entry.aliases)}</span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No taxonomy entries"
            description="The manifest preview has no taxonomy metadata to display."
          />
        )}
      </section>

      <details className="manifest-json">
        <summary>Raw JSON preview</summary>
        <pre>{manifestJson}</pre>
      </details>
    </div>
  );
}
