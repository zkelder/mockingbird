import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type { AlertCategory, AttentionCategory, ProductAlert, ProductAlertAction, UserNotificationPreferences } from "../api/types";
import {
  deliverForegroundNotification,
  shouldDeliverForegroundNotification,
} from "../notifications/foregroundNotifications";
import { EmptyState } from "./EmptyState";
import { PageHeader } from "./PageHeader";
import { StatusPill } from "./StatusPill";
import { formatDateTime } from "../utils";

const filters: Array<{ value: AlertCategory | undefined; label: string }> = [
  { value: undefined, label: "All" },
  { value: "review", label: "Review" },
  { value: "insight", label: "Insight" },
  { value: "monitoring", label: "Monitoring" },
  { value: "storage", label: "Storage" },
  // Everyday Product / Discovery UX Closure v1: the visible label says "Bird
  // Log" (the product-facing name used by nav/Today/Insights everywhere
  // else); the filter `value` stays "journal" -- it's the internal
  // AlertCategory key, not user-visible text.
  { value: "journal", label: "Bird Log" },
];

// Calm Attention & Notifications v1, Phase 2: the small, plain-language
// taxonomy shown next to each item so a user learns "what kind of thing is
// this" without ever seeing an internal `AlertCategory` name like
// "journal"/"monitoring" (see PlaceStoryEntry's identical "never render the
// internal enum name directly" discipline).
const ATTENTION_CATEGORY_LABEL: Record<AttentionCategory, string> = {
  discovery: "Discovery",
  insight: "Insight",
  needs_help: "Needs Help",
  observatory_health: "Observatory Health",
};

function actionLabel(action: ProductAlertAction): string {
  if (action.action_type === "review_visit") return "Review Visit";
  if (action.action_type === "open_stream") return "Open Stream";
  if (action.action_type === "open_storage_retention") return "Open Storage & Retention";
  if (action.action_type === "open_place_story") return "View in Place Story";
  if (action.action_type === "open_place_report") return "View report";
  return "Open Bird Log";
}

function tone(alert: ProductAlert): "good" | "review" | "quiet" {
  if (alert.severity === "high") return "review";
  if (alert.status === "resolved" || alert.status === "dismissed") return "quiet";
  return "good";
}

function AlertRow({
  alert,
  onAction,
  onChanged,
}: {
  alert: ProductAlert;
  onAction: (action: ProductAlertAction) => void;
  onChanged: () => Promise<void>;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function update(kind: "read" | "dismiss") {
    setIsSaving(true);
    setError(null);
    try {
      if (kind === "read") await apiClient.markAlertRead(alert.id);
      else await apiClient.dismissAlert(alert.id);
      await onChanged();
    } catch {
      setError("That alert could not be updated. Try again when the local app is ready.");
    } finally {
      setIsSaving(false);
    }
  }
  async function openAction() {
    if (alert.status === "unread") await update("read");
    onAction(alert.action);
  }
  return (
    <article className={`alert-row alert-${alert.severity}`}>
      <div className="alert-row-heading">
        <div>
          <h3>{alert.title}</h3>
          <span className="meta-text">
            {ATTENTION_CATEGORY_LABEL[alert.attention_category]} · {formatDateTime(alert.created_at)}
          </span>
        </div>
        <StatusPill label={alert.status} tone={tone(alert)} />
      </div>
      <p>{alert.message}</p>
      {alert.stream_name || alert.zone_name ? <span className="meta-text">{[alert.stream_name, alert.zone_name].filter(Boolean).join(" · ")}</span> : null}
      {error ? <span className="error-text">{error}</span> : null}
      <div className="detail-actions">
        <button className="secondary-action" disabled={isSaving} onClick={() => void openAction()} type="button">{actionLabel(alert.action)}</button>
        {alert.status === "unread" ? <button className="text-action" disabled={isSaving} onClick={() => void update("read")} type="button">Mark read</button> : null}
        {alert.status !== "dismissed" && alert.status !== "resolved" ? <button className="text-action" disabled={isSaving} onClick={() => void update("dismiss")} type="button">Dismiss</button> : null}
      </div>
    </article>
  );
}

export function AlertsControl({
  onOpenInbox,
  onAction,
}: {
  onOpenInbox: () => void;
  onAction: (action: ProductAlertAction) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const controlRef = useRef<HTMLDivElement | null>(null);
  const [alerts, setAlerts] = useState<ProductAlert[]>([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Calm Attention & Notifications v1: `null` means "no poll has completed
  // yet" -- deliberately distinct from an empty set, so the very first
  // poll after opening the app never fires a flood of live notifications
  // for attention items that already existed before this page loaded.
  // Only an id that is genuinely new *since the previous poll* is ever
  // eligible for a live interruption (Phase 8: cooldowns/hysteresis).
  const seenAlertIdsRef = useRef<Set<string> | null>(null);
  // A ref, not a `useCallback` dependency: `onAction` is a fresh function
  // identity on every parent render (App.tsx does not memoize it), and
  // `refresh`'s own identity must stay stable so the 60s poll interval
  // below is not torn down and restarted on every unrelated re-render.
  const onActionRef = useRef(onAction);
  onActionRef.current = onAction;
  const refresh = useCallback(async () => {
    try {
      const [result, preferences] = await Promise.all([
        apiClient.getAlertUnread(),
        apiClient.getNotificationPreferences().catch(() => null),
      ]);
      setUnread(result.unread_count);
      setAlerts(result.recent);
      setError(null);
      const previouslySeen = seenAlertIdsRef.current;
      seenAlertIdsRef.current = new Set(result.recent.map((alert) => alert.id));
      if (previouslySeen && preferences) {
        const now = new Date();
        for (const alert of result.recent) {
          if (previouslySeen.has(alert.id)) continue;
          if (!shouldDeliverForegroundNotification(alert, preferences, now)) continue;
          deliverForegroundNotification(alert, () => onActionRef.current(alert.action));
        }
      }
    } catch {
      setError("Recent alerts could not refresh. The last available alerts are still shown.");
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    return () => window.clearInterval(timer);
  }, [refresh]);
  // UI/UX & First-Run Adoption v1: this popover could only be closed by
  // clicking its own button again -- no Escape, no outside click.
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
        controlRef.current?.querySelector<HTMLButtonElement>(".alerts-button")?.focus();
      }
    }
    function handlePointerDown(event: MouseEvent) {
      if (controlRef.current && !controlRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [isOpen]);

  return (
    <div className="alerts-control" ref={controlRef}>
      <button aria-expanded={isOpen} className="alerts-button" onClick={() => setIsOpen((value) => !value)} type="button">
        Alerts{unread ? <span className="alerts-badge">{unread > 99 ? "99+" : unread}</span> : null}
      </button>
      {isOpen ? (
        <section className="alerts-drawer" aria-label="Recent alerts">
          <div className="section-heading"><div><h2>Alerts</h2><span className="meta-text">Local attention items only.</span></div><button className="text-action" onClick={onOpenInbox} type="button">Open inbox</button></div>
          {error ? <div className="error-panel">{error}</div> : null}
          {!alerts.length ? <EmptyState title="Nothing worth noticing right now" description="A new species, a meaningful change, review work, or a real observatory issue will appear here — MockingBird stays quiet otherwise." /> : alerts.slice(0, 5).map((alert) => <AlertRow alert={alert} key={alert.id} onAction={onAction} onChanged={refresh} />)}
        </section>
      ) : null}
    </div>
  );
}

export function AlertsInboxPage({ onAction }: { onAction: (action: ProductAlertAction) => void }) {
  const [category, setCategory] = useState<AlertCategory | undefined>();
  const [alerts, setAlerts] = useState<ProductAlert[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const load = useCallback(async (offset = 0, append = false) => {
    setIsLoading(true);
    try {
      const result = await apiClient.getAlerts(category, offset);
      setAlerts((current) => append ? [...current, ...result.items] : result.items);
      setNextOffset(result.next_offset ?? null);
      setError(null);
    } catch {
      setError("Alerts could not refresh. The last available inbox is still shown.");
    } finally { setIsLoading(false); }
  }, [category]);
  useEffect(() => { void load(); }, [load]);
  async function markVisibleRead() {
    await apiClient.markVisibleAlertsRead(alerts.filter((item) => item.status === "unread").map((item) => item.id));
    await load();
  }
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Local attention" title="Alerts Inbox" description="Important local review work and safe operational conditions. Opening an alert never starts monitoring or cleanup." actions={<button className="secondary-action" disabled={!alerts.some((item) => item.status === "unread")} onClick={() => void markVisibleRead()} type="button">Mark visible read</button>} />
      <section className="panel alert-filters" aria-label="Alert filters">
        {filters.map((filter) => <button className={category === filter.value ? "primary-action" : "secondary-action"} key={filter.label} onClick={() => setCategory(filter.value)} type="button">{filter.label}</button>)}
      </section>
      {error ? <div className="error-panel">{error}</div> : null}
      {isLoading && !alerts.length ? <div className="panel">Loading local alerts…</div> : null}
      {!isLoading && !alerts.length ? <EmptyState title="No alerts in this view" description="Resolved alert history and new local attention items will appear here when available." /> : null}
      <section className="alerts-inbox-list">{alerts.map((alert) => <AlertRow alert={alert} key={alert.id} onAction={onAction} onChanged={() => load()} />)}</section>
      {nextOffset !== null ? <button className="secondary-action" disabled={isLoading} onClick={() => void load(nextOffset, true)} type="button">{isLoading ? "Loading…" : "Load more alerts"}</button> : null}
    </div>
  );
}
