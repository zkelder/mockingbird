import { useAttention } from "../attention/AttentionProvider";

/**
 * Calm Attention & Notifications v1, Phase 20: Today surfaces unread
 * attention naturally -- "2 things worth noticing" -- without duplicating
 * the full Attention Center (`AlertsControl`/`AlertsInboxPage`) inline.
 * Renders nothing at all when there is genuinely nothing unread (Phase 20:
 * "Keep Today calm").
 *
 * Attention Integrity & Health Reliability v1: reads the one shared app-
 * shell attention summary instead of fetching its own, so this line and the
 * header badge can never disagree. A failed refresh stays silent here, as
 * before -- this is a calm, optional summary line, not a load-bearing part
 * of Today, and the header control already reports refresh trouble.
 */
export function TodayAttentionSummary({ onOpenAlertsInbox }: { onOpenAlertsInbox: () => void }) {
  const { unreadCount } = useAttention();

  if (!unreadCount) return null;

  return (
    <button className="today-attention-summary" onClick={onOpenAlertsInbox} type="button">
      {unreadCount === 1 ? "1 thing worth noticing" : `${unreadCount} things worth noticing`}
    </button>
  );
}
