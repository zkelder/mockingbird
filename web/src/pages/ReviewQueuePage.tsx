import { useState } from "react";
import type { ReviewLabel, ReviewQueueItem } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { formatLabel } from "../utils";

interface ReviewQueuePageProps {
  items: ReviewQueueItem[];
  onCreateCorrection: (
    item: ReviewQueueItem,
    label: string,
    notes: string,
  ) => Promise<ReviewLabel>;
}

export function ReviewQueuePage({ items, onCreateCorrection }: ReviewQueuePageProps) {
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
      await onCreateCorrection(item, draft.label.trim(), draft.notes.trim());
      setMessage("Correction saved as a dataset-grade label.");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correction could not be saved.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="page-stack">
      <div className="section-heading">
        <h1>Review Queue</h1>
      </div>
      {message ? <div className="notice-panel">{message}</div> : null}
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
                <StatusPill label={formatLabel(item.review_status)} tone="review" />
              </div>
              <p>{item.reason}</p>
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
                    placeholder="confirmed label"
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
