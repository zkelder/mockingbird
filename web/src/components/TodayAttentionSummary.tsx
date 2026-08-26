import { useEffect, useState } from "react";
import { apiClient } from "../api/client";

/**
 * Calm Attention & Notifications v1, Phase 20: Today surfaces unread
 * attention naturally -- "2 things worth noticing" -- without duplicating
 * the full Attention Center (`AlertsControl`/`AlertsInboxPage`) inline.
 * Renders nothing at all when there is genuinely nothing unread (Phase 20:
 * "Keep Today calm"); a self-contained fetch, independent of the rest of
 * Dashboard's own polling, so a failure here can never affect the report
 * above it.
 */
export function TodayAttentionSummary({ onOpenAlertsInbox }: { onOpenAlertsInbox: () => void }) {
  const [unreadCount, setUnreadCount] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    apiClient
      .getAlertUnread()
      .then((result) => {
        if (active) setUnreadCount(result.unread_count);
      })
      .catch(() => {
        // Silent: this is a calm, optional summary line, not a load-
        // bearing part of Today -- a failure here must not add an error
        // banner to an otherwise-healthy Dashboard.
      });
    return () => {
      active = false;
    };
  }, []);

  if (!unreadCount) return null;

  return (
    <button className="today-attention-summary" onClick={onOpenAlertsInbox} type="button">
      {unreadCount === 1 ? "1 thing worth noticing" : `${unreadCount} things worth noticing`}
    </button>
  );
}
