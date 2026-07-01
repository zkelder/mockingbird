import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type { Detection, VisitDetail } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface VisitDetailPageProps {
  visitId: string;
  onOpenStream: (streamId: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenExports: () => void;
  onCorrectionSaved: () => Promise<void>;
}

function bboxSummary(detection: Detection): string {
  if (!detection.bbox) {
    return "No box";
  }

  return `Box ${Math.round(detection.bbox.x * 100)}%, ${Math.round(
    detection.bbox.y * 100,
  )}% / ${Math.round(detection.bbox.width * 100)}% x ${Math.round(
    detection.bbox.height * 100,
  )}%`;
}

export function VisitDetailPage({
  visitId,
  onOpenStream,
  onOpenEvent,
  onOpenExports,
  onCorrectionSaved,
}: VisitDetailPageProps) {
  const [detail, setDetail] = useState<VisitDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");

  async function loadDetail(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const nextDetail = await apiClient.getVisitDetail(visitId);
      setDetail(nextDetail);
      setLabel((current) =>
        current ||
        nextDetail.visit.reviewed_label ||
        nextDetail.visit.species_guess ||
        nextDetail.visit.subject_label,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load visit detail.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    setMessage(null);
    setLabel("");
    setNotes("");
    void loadDetail();
  }, [visitId]);

  async function saveCorrection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setMessage("Add a label before saving a correction.");
      return;
    }

    setIsSaving(true);
    setMessage(null);
    setError(null);
    try {
      await apiClient.createReviewLabel({
        target_type: "visit",
        target_id: visitId,
        label: trimmedLabel,
        notes: notes.trim() || undefined,
      });
      setMessage("Corrected label will be used as local dataset truth.");
      await loadDetail({ showLoading: false });
      await onCorrectionSaved();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correction could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return <div className="panel">Loading visit detail...</div>;
  }

  if (error || !detail) {
    return <div className="error-panel">{error ?? "Visit detail is unavailable."}</div>;
  }

  const visitLabel = detail.visit.reviewed_label ?? detail.visit.species_guess ?? detail.visit.subject_label;

  return (
    <div className="page-stack">
      <div className="stream-detail-heading">
        <div>
          <span className="page-eyebrow">Visit case file</span>
          <StatusPill
            label={formatLabel(detail.visit.review_status)}
            tone={detail.visit.review_status === "needs_review" ? "review" : "good"}
          />
          <h1>{formatLabel(visitLabel)} visit</h1>
          <p>{detail.review_summary}</p>
        </div>
        <StatusPill
          label={detail.dataset_ready ? "Ready for local dataset export" : "Needs review before export"}
          tone={detail.dataset_ready ? "good" : "review"}
        />
      </div>

      {message ? <div className="notice-panel">{message}</div> : null}

      <section className="case-summary-grid">
        <div className="panel case-summary-card">
          <span className="meta-text">Subject</span>
          <strong>{formatLabel(detail.visit.subject_label)}</strong>
          {detail.visit.confidence ? (
            <span className="meta-text">{Math.round(detail.visit.confidence * 100)}% confidence</span>
          ) : null}
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Species guess</span>
          <strong>{formatLabel(detail.visit.species_guess ?? "unknown")}</strong>
          <span className="meta-text">
            Reviewed: {formatLabel(detail.visit.reviewed_label ?? "not reviewed")}
          </span>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Event</span>
          <button className="text-action" onClick={() => onOpenEvent(detail.event.id)}>
            {detail.event.title}
          </button>
          <span className="meta-text">{formatDateTime(detail.event.started_at)}</span>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Stream and zone</span>
          <button className="text-action" onClick={() => onOpenStream(detail.stream.id)}>
            {detail.stream.name}
          </button>
          <span className="meta-text">
            {detail.primary_zone
              ? `${detail.primary_zone.name} (${formatLabel(detail.primary_zone.zone_type)})`
              : "Unzoned"}
          </span>
        </div>
      </section>

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Detections as evidence</h2>
          </div>
          <div className="evidence-list">
            {detail.detections.map((detection) => (
              <div className="evidence-card" key={detection.id}>
                <div className="item-title-row">
                  <strong>{formatLabel(detection.label)}</strong>
                  <span>{Math.round(detection.confidence * 100)}%</span>
                </div>
                <span className="meta-text">
                  Zone:{" "}
                  {detail.primary_zone && detection.zone_id === detail.primary_zone.id
                    ? detail.primary_zone.name
                    : detection.zone_id ?? "Unzoned"}
                </span>
                <span className="meta-text">{bboxSummary(detection)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="section-heading">
            <h2>Correction history</h2>
          </div>
          <div className="history-list">
            {detail.review_labels.map((reviewLabel) => (
              <div className="history-item" key={reviewLabel.id}>
                <strong>{formatLabel(reviewLabel.label)}</strong>
                <span>
                  {formatLabel(reviewLabel.target_type)} correction -{" "}
                  {formatDateTime(reviewLabel.created_at)}
                </span>
                {reviewLabel.notes ? <p>{reviewLabel.notes}</p> : null}
              </div>
            ))}
            {detail.review_labels.length === 0 ? (
              <span className="meta-text">No correction history yet.</span>
            ) : null}
          </div>
        </div>
      </section>

      {detail.visit.review_status === "needs_review" ? (
        <section className="panel">
          <div className="section-heading">
            <h2>Correct visit label</h2>
          </div>
          <form className="correction-form" onSubmit={saveCorrection}>
            <label>
              Label
              <input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="confirmed label"
              />
            </label>
            <label>
              Notes
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="optional review note"
              />
            </label>
            <button className="primary-action" disabled={isSaving} type="submit">
              {isSaving ? "Saving..." : "Save correction"}
            </button>
          </form>
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        </section>
      ) : (
        <section className="panel case-readiness-panel">
          <div>
            <h2>Dataset readiness</h2>
            <p>{detail.review_summary}</p>
          </div>
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        </section>
      )}
    </div>
  );
}
