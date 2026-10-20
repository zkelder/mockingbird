import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { apiClient } from "../api/client";
import type { ProductAlert, ProductAlertAction, ProductAlertUnreadResponse, UserNotificationPreferences } from "../api/types";
import {
  deliverForegroundNotification,
  shouldDeliverForegroundNotification,
} from "../notifications/foregroundNotifications";

/**
 * Attention Integrity & Health Reliability v1: the one app-shell source of
 * the signed-in user's attention summary (`GET /api/alerts/unread`).
 *
 * Before this, each mounted `AlertsControl` (the mobile top bar and the
 * sidebar both render one) ran its own 60 s poll, and `TodayAttentionSummary`
 * fetched the same summary independently -- three requests for one fact,
 * able to disagree with each other for up to a minute after a "Mark read."
 * Now there is exactly one poll per signed-in shell, every consumer reads
 * the same state, and a read/dismiss mutation's response (already the
 * caller's refreshed summary) is applied here directly so the badge, the
 * drawer and Today change together.
 *
 * Foreground browser notifications are delivered from here for the same
 * reason: once per genuinely new alert, not once per mounted control.
 *
 * Mounted with `key={currentUser.id}` so a different signed-in user always
 * starts from a fresh, empty state -- never another user's counts or "seen"
 * set. The Alerts Inbox page keeps its own paginated fetch; it only reports
 * its mutations back here.
 */

export interface AttentionState {
  unreadCount: number;
  recent: ProductAlert[];
  /** `false` until the first summary has loaded (or failed). */
  loaded: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  markRead: (alertId: string) => Promise<void>;
  dismiss: (alertId: string) => Promise<void>;
  markVisibleRead: (alertIds: string[]) => Promise<void>;
}

const AttentionContext = createContext<AttentionState | null>(null);

export const ATTENTION_POLL_INTERVAL_MS = 60_000;

export function AttentionProvider({
  children,
  onAction,
}: {
  children: ReactNode;
  onAction: (action: ProductAlertAction) => void;
}) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [recent, setRecent] = useState<ProductAlert[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // `null` means "no summary has been seen yet" -- deliberately distinct
  // from an empty set, so the first summary after opening the app never
  // fires a flood of live notifications for attention items that already
  // existed. Only an id genuinely new since the previous summary is ever
  // eligible for a live interruption (Calm Attention Phase 8).
  const seenAlertIdsRef = useRef<Set<string> | null>(null);
  const preferencesRef = useRef<UserNotificationPreferences | null>(null);
  // A ref, not a dependency: App.tsx does not memoize `onAction`, and the
  // poll below must not be torn down and restarted on every re-render.
  const onActionRef = useRef(onAction);
  onActionRef.current = onAction;
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const apply = useCallback((result: ProductAlertUnreadResponse) => {
    if (!mountedRef.current) return;
    setUnreadCount(result.unread_count);
    setRecent(result.recent);
    setLoaded(true);
    setError(null);
    const previouslySeen = seenAlertIdsRef.current;
    seenAlertIdsRef.current = new Set(result.recent.map((alert) => alert.id));
    const preferences = preferencesRef.current;
    if (!previouslySeen || !preferences) return;
    const now = new Date();
    for (const alert of result.recent) {
      if (previouslySeen.has(alert.id)) continue;
      if (!shouldDeliverForegroundNotification(alert, preferences, now)) continue;
      deliverForegroundNotification(alert, () => onActionRef.current(alert.action));
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [result, preferences] = await Promise.all([
        apiClient.getAlertUnread(),
        apiClient.getNotificationPreferences().catch(() => null),
      ]);
      if (preferences) preferencesRef.current = preferences;
      apply(result);
    } catch {
      if (!mountedRef.current) return;
      setLoaded(true);
      setError("Recent alerts could not refresh. The last available alerts are still shown.");
    }
  }, [apply]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), ATTENTION_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const markRead = useCallback(async (alertId: string) => {
    apply(await apiClient.markAlertRead(alertId));
  }, [apply]);
  const dismiss = useCallback(async (alertId: string) => {
    apply(await apiClient.dismissAlert(alertId));
  }, [apply]);
  const markVisibleRead = useCallback(async (alertIds: string[]) => {
    apply(await apiClient.markVisibleAlertsRead(alertIds));
  }, [apply]);

  const value = useMemo<AttentionState>(
    () => ({ unreadCount, recent, loaded, error, refresh, markRead, dismiss, markVisibleRead }),
    [unreadCount, recent, loaded, error, refresh, markRead, dismiss, markVisibleRead],
  );
  return <AttentionContext.Provider value={value}>{children}</AttentionContext.Provider>;
}

export function useAttention(): AttentionState {
  const value = useContext(AttentionContext);
  if (!value) {
    throw new Error("useAttention must be used inside AttentionProvider");
  }
  return value;
}
