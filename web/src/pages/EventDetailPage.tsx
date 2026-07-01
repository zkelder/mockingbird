import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { Detection, EventDetail } from "../api/types";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface EventDetailPageProps {
  eventId: string;
  onOpenStream: (streamId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenExports: () => void;
  onOpenReview: () => void;
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

export function EventDetailPage({
  eventId,
  onOpenStream,
  onOpenVisit,
  onOpenExports,
  onOpenReview,
}: EventDetailPageProps) {
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadDetail() {
      setIsLoading(true);
      setError(null);
      try {
        const nextDetail = await apiClient.getEventDetail(eventId);
        if (isMounted) {
          setDetail(nextDetail);
        }
      } catch (caught) {
        if (isMounted) {
          setError(caught instanceof Error ? caught.message : "Could not load event detail.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      isMounted = false;
    };
  }, [eventId]);

  if (isLoading) {
    return <div className="panel">Loading event detail...</div>;
  }

  if (error || !detail) {
    return <div className="error-panel">{error ?? "Event detail is unavailable."}</div>;
  }

  return (
    <div className="page-stack">
      <div className="stream-detail-heading">
        <div>
          <span className="page-eyebrow">Event case file</span>
          <StatusPill
            label={formatLabel(detail.event.review_status)}
            tone={detail.event.review_status === "needs_review" ? "review" : "good"}
          />
          <h1>{detail.event.title}</h1>
          <p>{detail.review_summary}</p>
        </div>
        <StatusPill
          label={detail.dataset_ready ? "Ready for local dataset export" : "Needs review before export"}
          tone={detail.dataset_ready ? "good" : "review"}
        />
      </div>

      <section className="case-summary-grid">
        <div className="panel case-summary-card">
          <span className="meta-text">Event type</span>
          <strong>{formatLabel(detail.event.event_type)}</strong>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Stream</span>
          <button className="text-action" onClick={() => onOpenStream(detail.stream.id)}>
            {detail.stream.name}
          </button>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Zone context</span>
          <strong>
            {detail.primary_zone
              ? `${detail.primary_zone.name} (${formatLabel(detail.primary_zone.zone_type)})`
              : "Unzoned"}
          </strong>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Timing</span>
          <strong>{formatDateTime(detail.event.started_at)}</strong>
          <span className="meta-text">
            Ended: {detail.event.ended_at ? formatDateTime(detail.event.ended_at) : "Open"}
          </span>
        </div>
        {detail.media_asset ? (
          <div className="panel case-summary-card">
            <span className="meta-text">Media</span>
            <strong>{detail.media_asset.original_filename}</strong>
            <span className="meta-text">Local import reference</span>
          </div>
        ) : null}
      </section>

      {detail.media_asset ? (
        <section className="panel media-evidence-panel">
          <div className="section-heading">
            <h2>Imported media</h2>
            <span className="meta-text">Local evidence for this review event</span>
          </div>
          <MediaAssetPreview asset={detail.media_asset} />
        </section>
      ) : null}

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Detections as evidence</h2>
          </div>
          <div className="evidence-list">
            {detail.event.detections.length > 0 ? (
              detail.event.detections.map((detection) => (
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
              ))
            ) : (
              <span className="meta-text">No detections are attached to this manual media event.</span>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="section-heading">
            <h2>Visits</h2>
          </div>
          <div className="list-stack">
            {detail.visits.map((visit) => (
              <button className="detail-link-card" key={visit.id} onClick={() => onOpenVisit(visit.id)}>
                <span>{formatLabel(visit.reviewed_label ?? visit.species_guess ?? visit.subject_label)}</span>
                <strong>{formatLabel(visit.review_status)}</strong>
              </button>
            ))}
            {detail.visits.length === 0 ? (
              <span className="meta-text">No visits are attached to this event.</span>
            ) : null}
          </div>
        </div>
      </section>

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Correction history</h2>
          </div>
          <div className="history-list">
            {detail.review_labels.map((label) => (
              <div className="history-item" key={label.id}>
                <strong>{formatLabel(label.label)}</strong>
                <span>
                  {formatLabel(label.target_type)} correction - {formatDateTime(label.created_at)}
                </span>
                {label.notes ? <p>{label.notes}</p> : null}
              </div>
            ))}
            {detail.review_labels.length === 0 ? (
              <span className="meta-text">No correction history yet.</span>
            ) : null}
          </div>
        </div>

        <div className="panel case-readiness-panel">
          <div>
            <h2>Dataset readiness</h2>
            <p>{detail.review_summary}</p>
          </div>
          {!detail.dataset_ready ? (
            <button className="primary-action" onClick={onOpenReview}>
              Open Review Queue
            </button>
          ) : null}
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        </div>
      </section>
    </div>
  );
}
