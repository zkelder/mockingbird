import type { DatasetQualityIssue, DatasetQualitySummary } from "../api/types";
import { formatLabel } from "../utils";
import { EvidenceBadge } from "./EvidenceBadge";

interface DatasetQualityPanelProps {
  quality: DatasetQualitySummary | null;
  onOpenEvent?: (eventId: string) => void;
  onOpenExports?: () => void;
  onOpenReview: () => void;
  onOpenVisit?: (visitId: string) => void;
  variant?: "full" | "compact";
}

function severityTone(severity: string): "evidence" | "truth" | "review" | "quiet" {
  if (severity === "high" || severity === "medium") {
    return "review";
  }
  return "quiet";
}

function issueAction(
  issue: DatasetQualityIssue,
  onOpenEvent?: (eventId: string) => void,
  onOpenVisit?: (visitId: string) => void,
) {
  if (issue.visit_id && onOpenVisit) {
    return (
      <button className="text-action" onClick={() => onOpenVisit(issue.visit_id!)}>
        Visit detail
      </button>
    );
  }
  if (issue.event_id && onOpenEvent) {
    return (
      <button className="text-action" onClick={() => onOpenEvent(issue.event_id!)}>
        Event detail
      </button>
    );
  }
  return null;
}

export function DatasetQualityPanel({
  quality,
  onOpenEvent,
  onOpenExports,
  onOpenReview,
  onOpenVisit,
  variant = "full",
}: DatasetQualityPanelProps) {
  if (!quality) {
    return (
      <section className="panel dataset-quality-panel">
        <div className="section-heading">
          <h2>Dataset QA</h2>
        </div>
        <span className="meta-text">Dataset QA is unavailable.</span>
      </section>
    );
  }

  const isCompact = variant === "compact";
  const cleanupCount = quality.high_count + quality.medium_count;
  const visibleIssues = isCompact ? quality.issues.slice(0, 2) : quality.issues;

  return (
    <section className={`panel dataset-quality-panel ${isCompact ? "compact" : ""}`}>
      <div className="section-heading">
        <div>
          <h2>Dataset QA</h2>
          <span className="meta-text">
            Corrected labels are local dataset truth. QA highlights review cleanup before exports
            and coverage for future model work.
          </span>
        </div>
        <EvidenceBadge
          label={cleanupCount > 0 ? `${cleanupCount} cleanup target${cleanupCount === 1 ? "" : "s"}` : "QA clean"}
          tone={cleanupCount > 0 ? "review" : "truth"}
        />
      </div>

      <div className="quality-metric-grid">
        <div>
          <span className="meta-text">QA issues</span>
          <strong>{quality.issue_count}</strong>
        </div>
        <div>
          <span className="meta-text">High / medium</span>
          <strong>
            {quality.high_count}/{quality.medium_count}
          </strong>
        </div>
        <div>
          <span className="meta-text">Unknown labels needing review</span>
          <strong>{quality.unknown_label_count}</strong>
        </div>
        <div>
          <span className="meta-text">Freeform labels outside taxonomy</span>
          <strong>{quality.freeform_label_count}</strong>
        </div>
      </div>

      {!isCompact ? (
        <div className="quality-secondary-grid">
          <div>
            <span className="meta-text">Export-ready records</span>
            <strong>{quality.export_ready_count}</strong>
          </div>
          <div>
            <span className="meta-text">Records needing cleanup before export</span>
            <strong>{quality.needs_review_count}</strong>
          </div>
          <div>
            <span className="meta-text">Missing zone/media context</span>
            <strong>
              {quality.missing_zone_count}/{quality.missing_media_count}
            </strong>
          </div>
          <div>
            <span className="meta-text">Conflicts / false positives</span>
            <strong>
              {quality.conflicting_correction_count}/{quality.false_positive_count}
            </strong>
          </div>
        </div>
      ) : null}

      {visibleIssues.length > 0 ? (
        <div className="quality-issue-list">
          {visibleIssues.map((issue) => (
            <article className="quality-issue-card" key={issue.id}>
              <div>
                <div className="quality-issue-title">
                  <strong>{issue.title}</strong>
                  <EvidenceBadge label={formatLabel(issue.severity)} tone={severityTone(issue.severity)} />
                  <EvidenceBadge label={formatLabel(issue.issue_type)} tone="quiet" />
                </div>
                <p>{issue.description}</p>
                <span className="meta-text">{issue.suggested_action}</span>
              </div>
              <div className="detail-actions">
                {issueAction(issue, onOpenEvent, onOpenVisit)}
                {issue.issue_type === "needs_review" ? (
                  <button className="text-action" onClick={onOpenReview}>
                    Review Queue
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <span className="meta-text">No dataset QA warnings are visible right now.</span>
      )}

      <div className="detail-actions">
        {quality.needs_review_count > 0 || quality.unknown_label_count > 0 ? (
          <button className="secondary-action" onClick={onOpenReview}>
            Review cleanup
          </button>
        ) : null}
        {onOpenExports ? (
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        ) : null}
      </div>
    </section>
  );
}
