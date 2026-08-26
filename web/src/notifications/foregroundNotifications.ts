import type { ProductAlert, UserNotificationPreferences } from "../api/types";

/**
 * Calm Attention & Notifications v1 -- Phase 22 architecture decision B:
 * "local/in-app/browser-active notification delivery," background Web
 * Push explicitly deferred (see docs/calm-attention-notifications-v1-
 * report.md "PWA / browser notification decision"). These are plain
 * page-level `Notification` calls, never a service-worker `push`/
 * `notificationclick` handler -- they only ever fire while this tab's own
 * JavaScript is still running (open or backgrounded, not closed), which is
 * exactly Option B's boundary and exactly why no deep-link URL scheme is
 * needed here: `onclick` below runs this same page's own in-app navigation
 * directly (see `App.tsx`'s `openAlertAction`), not `clients.openWindow`.
 *
 * Every check here is pure and unit-tested (`tests/foregroundNotifications.
 * test.ts` if/when a frontend unit-test harness is added -- today verified
 * via `e2e/notification-preferences.spec.ts`'s real-browser behavior) so a
 * silent regression cannot start over-notifying.
 */

/** Only `urgency === "immediate"` ever becomes a live OS-level interruption
 * (Phase 3: "Do NOT make wildlife detections immediate by default" --
 * Discovery/Insight/Needs Help content is `digest`/`in_app_only` and is
 * surfaced only in the Attention Center/bell badge, never popped live). */
export function isImmediatelyNotifiable(alert: ProductAlert): boolean {
  return alert.urgency === "immediate" && alert.status === "unread";
}

function categoryEnabled(alert: ProductAlert, preferences: UserNotificationPreferences): boolean {
  switch (alert.attention_category) {
    case "discovery":
      return preferences.discovery_enabled;
    case "insight":
      return preferences.insight_enabled;
    case "needs_help":
      return preferences.needs_help_enabled;
    case "observatory_health":
      return preferences.observatory_health_enabled;
    default:
      return true;
  }
}

/** Phase 17: quiet hours affect delivery only, never the underlying
 * attention condition. Evaluated in the *viewer's own browser-local time*
 * -- deliberately not a stored server/Place timezone, since there isn't
 * one (see mockingbird.time_utils.resolve_host_local_timezone's own
 * docstring) and the viewer's own device clock is the one honestly
 * correct notion of "local" for whoever is about to be interrupted. A
 * window that wraps past midnight (e.g. 22:00-07:00) is handled directly,
 * not by rejecting the wrap. */
export function isWithinQuietHours(preferences: UserNotificationPreferences, now: Date): boolean {
  if (!preferences.quiet_hours_enabled) return false;
  const minuteOfDay = now.getHours() * 60 + now.getMinutes();
  const { quiet_hours_start_minute: start, quiet_hours_end_minute: end } = preferences;
  if (start === end) return false; // a zero-length window never suppresses anything
  if (start < end) return minuteOfDay >= start && minuteOfDay < end;
  return minuteOfDay >= start || minuteOfDay < end; // wraps past midnight
}

export function shouldDeliverForegroundNotification(
  alert: ProductAlert,
  preferences: UserNotificationPreferences,
  now: Date,
): boolean {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return false;
  if (!preferences.browser_notifications_enabled) return false;
  if (!isImmediatelyNotifiable(alert)) return false;
  if (!categoryEnabled(alert, preferences)) return false;
  if (isWithinQuietHours(preferences, now)) return false;
  return true;
}

/** Fires one calm, plain-copy browser notification for `alert`. `tag`
 * dedupes so the same alert id can never stack two OS notifications, and
 * `onOpen` is called (not a URL navigation) so clicking it drives this
 * same page's own in-app router directly -- see the module docstring. */
export function deliverForegroundNotification(alert: ProductAlert, onOpen: () => void): void {
  try {
    const notification = new Notification(alert.title, {
      body: alert.message,
      tag: alert.id,
      // Calm-copy discipline (Phase 30): no icon badge count, no
      // exclamation-mark styling -- plain title/body only.
    });
    notification.onclick = () => {
      window.focus();
      onOpen();
      notification.close();
    };
  } catch {
    // Some browsers/contexts throw synchronously (e.g. an insecure
    // origin, or a platform that requires `showNotification` via a
    // service-worker registration instead of the page constructor).
    // A failed live interruption must never lose the underlying
    // attention item -- it is still visible in the Attention Center on
    // this alert's very next poll (Phase 27: delivery failure never
    // loses the product event).
  }
}
