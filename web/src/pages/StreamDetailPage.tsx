import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { Event, ReviewQueueItem, Stream, Visit, Zone } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { StreamPanel } from "../components/StreamPanel";
import { formatDateTime, formatLabel } from "../utils";

interface StreamDetailPageProps {
  streamId: string;
  reviewQueue: ReviewQueueItem[];
}

interface StreamDetailState {
  stream: Stream;
  zones: Zone[];
  events: Event[];
  visitsByEvent: Record<string, Visit[]>;
}

export function StreamDetailPage({ streamId, reviewQueue }: StreamDetailPageProps) {
  const [detail, setDetail] = useState<StreamDetailState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadStreamDetail() {
      setIsLoading(true);
      setError(null);
      try {
        const [stream, zones, events] = await Promise.all([
          apiClient.getStream(streamId),
          apiClient.getStreamZones(streamId),
          apiClient.getStreamEvents(streamId),
        ]);
        const visitPairs = await Promise.all(
          events.map(async (event) => [event.id, await apiClient.getEventVisits(event.id)] as const),
        );
        if (isMounted) {
          setDetail({
            stream,
            zones,
            events,
            visitsByEvent: Object.fromEntries(visitPairs),
          });
        }
      } catch (caught) {
        if (isMounted) {
          setError(caught instanceof Error ? caught.message : "Could not load stream.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadStreamDetail();

    return () => {
      isMounted = false;
    };
  }, [streamId]);

  if (isLoading) {
    return <div className="panel">Loading stream...</div>;
  }

  if (error || !detail) {
    return <div className="error-panel">{error ?? "Stream detail is unavailable."}</div>;
  }

  const streamReviewItems = reviewQueue.filter((item) => item.stream_id === detail.stream.id);

  return (
    <div className="page-stack">
      <div className="stream-detail-heading">
        <div>
          <StatusPill label={detail.stream.is_live ? "Demo live" : "Offline"} tone="good" />
          <h1>{detail.stream.name}</h1>
          <p>{detail.stream.description}</p>
        </div>
        {streamReviewItems.length > 0 ? (
          <StatusPill label={`${streamReviewItems.length} needs review`} tone="review" />
        ) : null}
      </div>

      <StreamPanel stream={detail.stream} zones={detail.zones} events={detail.events} />

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Zones</h2>
          </div>
          <div className="list-stack">
            {detail.zones.map((zone) => (
              <div className="summary-row" key={zone.id}>
                <span>{zone.name}</span>
                <strong>{formatLabel(zone.zone_type)}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="section-heading">
            <h2>Review hints</h2>
          </div>
          <div className="list-stack">
            {streamReviewItems.length > 0 ? (
              streamReviewItems.map((item) => (
                <div className="queue-mini" key={item.id}>
                  <strong>{item.title}</strong>
                  <span>{item.reason}</span>
                </div>
              ))
            ) : (
              <span className="meta-text">No stream items need review.</span>
            )}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Stream events</h2>
        </div>
        <div className="event-list">
          {detail.events.map((event) => {
            const visits = detail.visitsByEvent[event.id] ?? [];
            return (
              <article className="event-card" key={event.id}>
                <div className="item-title-row">
                  <h3>{event.title}</h3>
                  <StatusPill
                    label={formatLabel(event.review_status)}
                    tone={event.review_status === "needs_review" ? "review" : "good"}
                  />
                </div>
                <span className="meta-text">{formatDateTime(event.started_at)}</span>
                <div className="tag-row">
                  {event.detections.map((detection) => (
                    <span className="tag" key={detection.id}>
                      {formatLabel(detection.label)} {Math.round(detection.confidence * 100)}%
                    </span>
                  ))}
                </div>
                {visits.length > 0 ? (
                  <div className="visit-strip">
                    {visits.map((visit) => (
                      <span key={visit.id}>
                        {formatLabel(visit.reviewed_label ?? visit.species_guess ?? visit.subject_label)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
