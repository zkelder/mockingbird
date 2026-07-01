import { useState } from "react";
import type { ReviewCorrectionResult, ReviewQueueItem } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatLabel } from "../utils";

interface ReviewQueuePageProps {
  items: ReviewQueueItem[];
  onCreateCorrection: (
    item: ReviewQueueItem,
    label: string,
    notes: string,
  ) => Promise<ReviewCorrectionResult>;
  onOpenEvent: (eventId: string) => void;
  onOpenExports: () => void;
  onOpenVisit: (visitId: string) => void;
}

export function ReviewQueuePage({
  items,
  onCreateCorrection,
  onOpenEvent,
  onOpenExports,
  onOpenVisit,
}: ReviewQueuePageProps) {
  const [drafts, setDrafts] = useState<Record<string, { label: string; notes: string }>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function saveCorrection(item: ReviewQueueItem) {
    const draft = drafts[item.id] ?? { label: item.suggested_label ?? "", notes: "" };
    if (!draft.label.trim()) {
      setMessage("Add a label before saving a correction.");
      return;
    }

    setSavingId(item.id);
    setMessage(null);
    try {
      const result = await onCreateCorrection(item, draft.label.trim(), draft.notes.trim());
      setMessage(
        `Correction saved as local dataset truth. ${result.review_queue_count} item${
          result.review_queue_count === 1 ? "" : "s"
        } still need review.`,
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correction could not be saved.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Dataset-grade truth"
        title="Review Queue"
        description="Confirm or correct outdoor activity before it becomes analytics and local export data."
        actions={
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        }
      />
      {message ? <div className="notice-panel">{message}</div> : null}
      {items.length === 0 ? (
        <EmptyState
          title="All demo visits and events are reviewed."
          description="Corrections are available as local dataset-grade labels for exports and analytics."
          action={
            <button className="primary-action" onClick={onOpenExports}>
              Generate dataset export
            </button>
          }
        />
      ) : null}
      <div className="queue-list">
        {items.map((item) => {
          const draft = drafts[item.id] ?? {
            label: item.suggested_label ?? "",
            notes: "",
          };
          return (
            <article className="queue-card" key={item.id}>
              <div className="item-title-row">
                <div>
                  <span className="meta-text">{formatLabel(item.item_type)}</span>
                  <h2>{item.title}</h2>
                </div>
                <div className="detail-actions">
                  {item.visit_id ? (
                    <button className="text-action" onClick={() => onOpenVisit(item.visit_id!)}>
                      Visit detail
                    </button>
                  ) : item.event_id ? (
                    <button className="text-action" onClick={() => onOpenEvent(item.event_id!)}>
                      Event detail
                    </button>
                  ) : null}
                  <StatusPill label={formatLabel(item.review_status)} tone="review" />
                </div>
              </div>
              <p>
                {item.reason} Detections are evidence; your correction becomes local dataset truth.
              </p>
              <div className="queue-meta">
                <span>Suggested: {formatLabel(item.suggested_label ?? "unknown")}</span>
                <span>Event: {item.event_id ?? "n/a"}</span>
                <span>Visit: {item.visit_id ?? "n/a"}</span>
              </div>
              <div className="correction-form">
                <label>
                  Label
                  <input
                    value={draft.label}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [item.id]: { ...draft, label: event.target.value },
                      }))
                    }
                    placeholder="confirmed species or event label"
                  />
                </label>
                <label>
                  Notes
                  <textarea
                    value={draft.notes}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [item.id]: { ...draft, notes: event.target.value },
                      }))
                    }
                    placeholder="optional review note"
                  />
                </label>
                <button
                  className="primary-action"
                  disabled={savingId === item.id}
                  onClick={() => void saveCorrection(item)}
                >
                  {savingId === item.id ? "Saving..." : "Save correction"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
