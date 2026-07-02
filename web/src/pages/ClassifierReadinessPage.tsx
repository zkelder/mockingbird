import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { ClassifierReadinessReport } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatLabel } from "../utils";

interface ClassifierReadinessPageProps {
  onOpenAnalytics: () => void;
  onOpenClassifierManifest: () => void;
  onOpenExports: () => void;
  onOpenReview: () => void;
  onOpenSpeciesSuggestions: () => void;
}

export function ClassifierReadinessPage({
  onOpenAnalytics,
  onOpenClassifierManifest,
  onOpenExports,
  onOpenReview,
  onOpenSpeciesSuggestions,
}: ClassifierReadinessPageProps) {
  const [report, setReport] = useState<ClassifierReadinessReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadReport() {
    setIsLoading(true);
    setError(null);
    try {
      setReport(await apiClient.getClassifierReadiness());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load classifier readiness.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadReport();
  }, []);

  const missingTargetPreview = useMemo(
    () => report?.missing_target_labels.slice(0, 24) ?? [],
    [report],
  );

  if (isLoading) {
    return <div className="panel">Loading classifier readiness...</div>;
  }

  if (error) {
    return (
      <div className="error-panel">
        <strong>Could not load classifier readiness.</strong>
        <span>{error}</span>
        <button className="secondary-action" onClick={() => void loadReport()}>
          Retry
        </button>
      </div>
    );
  }

  if (!report) {
    return <div className="panel">Classifier readiness is unavailable.</div>;
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Future classifier export"
        title="Classifier Readiness"
        description="Classifier readiness summarizes reviewed media-backed examples that could support a future custom bird classifier. It does not generate datasets, train models, or create reviewed truth."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenClassifierManifest}>
              View manifest preview
            </button>
            <button className="secondary-action" onClick={onOpenReview}>
              Review Queue
            </button>
            <button className="secondary-action" onClick={onOpenAnalytics}>
              Analytics
            </button>
          </>
        }
      />

      <section className="notice-panel">
        <strong>Reviewed corrections are the only training truth</strong>
        <span>
          SpeciesSuggestion status is review evidence, not training truth. MotionEvidence and
          DetectionProposal records are evidence only. The manifest preview is browser/reporting
          only; generated dataset files and classifier training remain future work.
        </span>
      </section>

      <section className="panel classifier-readiness-status">
        <div>
          <div className="quality-issue-title">
            <h2>Readiness status</h2>
            <StatusPill
              label={report.ready_for_manifest_export ? "Ready for future manifest export" : "Not ready"}
              tone={report.ready_for_manifest_export ? "good" : "review"}
            />
          </div>
          <p>{report.recommended_next_step}</p>
        </div>
        <div className="detail-actions">
          <button className="secondary-action" onClick={onOpenExports}>
            Dataset Exports
          </button>
          <button className="secondary-action" onClick={onOpenClassifierManifest}>
            View manifest preview
          </button>
          <button className="secondary-action" onClick={() => void loadReport()}>
            Refresh
          </button>
        </div>
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Reviewed examples"
          value={report.reviewed_examples}
          detail="correction truth"
        />
        <MetricCard
          label="Media-backed"
          value={report.media_backed_reviewed_examples}
          detail="reviewed examples with media"
        />
        <MetricCard
          label="Export-ready"
          value={report.export_ready_examples}
          detail="known taxonomy species"
        />
        <MetricCard
          label="Missing targets"
          value={report.missing_target_labels.length}
          detail="target species without media-backed truth"
        />
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Unknown labels"
          value={report.unknown_label_count}
          detail="not species truth"
        />
        <MetricCard
          label="False positives"
          value={report.false_positive_count}
          detail="excluded from species export"
        />
        <MetricCard
          label="Out of taxonomy"
          value={report.out_of_taxonomy_count}
          detail="needs label cleanup"
        />
        <MetricCard label="Skip reasons" value={report.skipped.length} detail="why records wait" />
      </section>

      <section className="panel classifier-readiness-panel">
        <div className="section-heading">
          <div>
            <h2>Species examples</h2>
            <span className="meta-text">Reviewed taxonomy species that have classifier-ready signal</span>
          </div>
          <EvidenceBadge label="Reviewed correction truth" tone="truth" />
        </div>
        {report.species.length > 0 ? (
          <div className="readiness-table" role="table" aria-label="Classifier species readiness">
            <div className="readiness-table-row readiness-table-head" role="row">
              <span role="columnheader">Label</span>
              <span role="columnheader">Reviewed</span>
              <span role="columnheader">Media-backed</span>
              <span role="columnheader">Export-ready</span>
              <span role="columnheader">Warnings</span>
            </div>
            {report.species.map((species) => (
              <div className="readiness-table-row" key={species.label} role="row">
                <strong role="cell">{formatLabel(species.label)}</strong>
                <span role="cell">{species.reviewed_examples}</span>
                <span role="cell">{species.media_backed_examples}</span>
                <span role="cell">{species.export_ready_examples}</span>
                <span className="readiness-warning-list" role="cell">
                  {species.warnings.length > 0
                    ? species.warnings.map((warning) => (
                        <EvidenceBadge label={formatLabel(warning)} tone="review" key={warning} />
                      ))
                    : "No warnings"}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No classifier-ready species yet"
            description="Review media-backed visits with taxonomy species labels before future manifest export."
            action={
              <button className="secondary-action" onClick={onOpenReview}>
                Open Review Queue
              </button>
            }
          />
        )}
      </section>

      <section className="split-grid">
        <div className="panel classifier-readiness-panel">
          <div className="section-heading">
            <div>
              <h2>Missing target labels</h2>
              <span className="meta-text">{report.missing_target_labels.length} missing</span>
            </div>
          </div>
          {report.missing_target_labels.length > 0 ? (
            <>
              <div className="tag-row">
                {missingTargetPreview.map((label) => (
                  <span className="tag" key={label}>
                    {formatLabel(label)}
                  </span>
                ))}
              </div>
              {report.missing_target_labels.length > missingTargetPreview.length ? (
                <span className="meta-text">
                  {report.missing_target_labels.length - missingTargetPreview.length} more target
                  labels need reviewed media-backed examples.
                </span>
              ) : null}
            </>
          ) : (
            <EmptyState
              title="All target labels have media-backed examples"
              description="Future manifest work can still use readiness warnings before export."
            />
          )}
        </div>

        <div className="panel classifier-readiness-panel">
          <div className="section-heading">
            <div>
              <h2>Skipped records</h2>
              <span className="meta-text">Reasons records are not classifier-ready</span>
            </div>
          </div>
          {report.skipped.length > 0 ? (
            <div className="readiness-summary-list">
              {report.skipped.map((item) => (
                <div className="summary-row" key={item.reason}>
                  <span>{formatLabel(item.reason)}</span>
                  <strong>{item.count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No skipped records"
              description="Every reviewed candidate currently meets the readiness policy."
            />
          )}
        </div>
      </section>

      <section className="panel classifier-readiness-panel">
        <div className="section-heading">
          <div>
            <h2>Warnings</h2>
            <span className="meta-text">Use these before deciding on future manifest export</span>
          </div>
          <button className="secondary-action" onClick={onOpenSpeciesSuggestions}>
            Species Suggestions
          </button>
        </div>
        {report.warnings.length > 0 ? (
          <div className="readiness-warning-stack">
            {report.warnings.map((warning) => (
              <div className="notice-panel readiness-warning" key={warning}>
                <strong>{warning}</strong>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No report-level warnings"
            description="The readiness report has no current warnings, but export generation remains future work."
          />
        )}
      </section>
    </div>
  );
}
