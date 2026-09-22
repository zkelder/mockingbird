import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { UserNotificationPreferences, UserNotificationPreferencesUpdate } from "../api/types";
import { StatusPill } from "./StatusPill";

/**
 * Calm Attention & Notifications v1, Phase 16/17/29: one signed-in user's
 * own delivery preferences. Deliberately not a "notification settings
 * cockpit" -- four category toggles mirroring the product's own attention
 * taxonomy, one quiet-hours window, and one explicit, plainly-explained
 * browser-notification opt-in. Never requested on page load; never blocks
 * any other part of the product if left off or denied.
 */

const CATEGORY_TOGGLES: Array<{
  field: keyof Pick<
    UserNotificationPreferences,
    "discovery_enabled" | "insight_enabled" | "needs_help_enabled" | "observatory_health_enabled"
  >;
  label: string;
  description: string;
}> = [
  {
    field: "discovery_enabled",
    label: "New & unusual wildlife",
    description: "A first-ever species, a meaningful return, or a particularly good moment.",
  },
  {
    field: "insight_enabled",
    label: "Insights & summaries",
    description: "Regularity changes, mature Place Feature comparisons, and the daily/weekly recap.",
  },
  {
    field: "needs_help_enabled",
    label: "Needs Help",
    description: "Observations that could use your review. Shown in-app only, never a live interruption.",
  },
  {
    field: "observatory_health_enabled",
    label: "Observatory health",
    description: "A camera that has genuinely stopped observing, or a real storage problem.",
  },
];

function minutesToTimeInputValue(minutes: number): string {
  const hours = Math.floor(minutes / 60)
    .toString()
    .padStart(2, "0");
  const mins = (minutes % 60).toString().padStart(2, "0");
  return `${hours}:${mins}`;
}

function timeInputValueToMinutes(value: string): number | null {
  const match = /^(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function browserNotificationSupportState(): "unsupported" | "default" | "granted" | "denied" {
  if (typeof Notification === "undefined") return "unsupported";
  return Notification.permission;
}

export function NotificationPreferences() {
  const [preferences, setPreferences] = useState<UserNotificationPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [permission, setPermission] = useState(browserNotificationSupportState());

  useEffect(() => {
    let active = true;
    apiClient
      .getNotificationPreferences()
      .then((result) => {
        if (active) setPreferences(result);
      })
      .catch(() => {
        if (active) setError("Notification preferences could not load right now.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function save(update: UserNotificationPreferencesUpdate) {
    setError(null);
    // Optimistic: every toggle/time input here is a controlled element
    // reading straight from `preferences`, so it must update in the same
    // tick as the click/change or the browser's own native toggle would
    // flash and then revert the instant this component re-renders with
    // the still-old value. Reconciled with the server's own response
    // below; a failure still leaves the optimistic value showing, with an
    // error banner explaining the save did not persist.
    setPreferences((current) => (current ? { ...current, ...update } : current));
    try {
      const result = await apiClient.updateNotificationPreferences(update);
      setPreferences(result);
    } catch {
      setError("That change could not be saved. Try again when the local app is ready.");
    }
  }

  async function requestBrowserPermission() {
    if (typeof Notification === "undefined") return;
    const result = await Notification.requestPermission();
    setPermission(result);
    if (result === "granted") await save({ browser_notifications_enabled: true });
  }

  return (
    <section className="panel local-data-card">
      <div className="section-heading">
        <div>
          <h2>Notifications</h2>
          <p>MockingBird stays quiet by default and only ever tells you what these categories allow.</p>
        </div>
      </div>

      {isLoading ? <div className="backup-empty">Loading notification preferences...</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      {!isLoading && preferences ? (
        <>
          <div className="data-row-list">
            {CATEGORY_TOGGLES.map((toggle) => (
              <label className="data-row" key={toggle.field}>
                <span>
                  <strong>{toggle.label}</strong>
                  <br />
                  <span className="meta-text">{toggle.description}</span>
                </span>
                <input
                  checked={preferences[toggle.field]}
                  onChange={(event) => void save({ [toggle.field]: event.target.checked })}
                  type="checkbox"
                />
              </label>
            ))}
          </div>

          <label className="data-row">
            <span>
              <strong>Quiet hours</strong>
              <br />
              <span className="meta-text">
                Pause a live browser interruption during these hours, in your own device's local time. Everything
                still appears in the Attention Center and any digest — quiet hours affect delivery only.
              </span>
            </span>
            <input
              checked={preferences.quiet_hours_enabled}
              onChange={(event) => void save({ quiet_hours_enabled: event.target.checked })}
              type="checkbox"
            />
          </label>
          {preferences.quiet_hours_enabled ? (
            <div className="data-row">
              <span>From</span>
              <input
                onChange={(event) => {
                  const minutes = timeInputValueToMinutes(event.target.value);
                  if (minutes !== null) void save({ quiet_hours_start_minute: minutes });
                }}
                type="time"
                value={minutesToTimeInputValue(preferences.quiet_hours_start_minute)}
              />
              <span>to</span>
              <input
                onChange={(event) => {
                  const minutes = timeInputValueToMinutes(event.target.value);
                  if (minutes !== null) void save({ quiet_hours_end_minute: minutes });
                }}
                type="time"
                value={minutesToTimeInputValue(preferences.quiet_hours_end_minute)}
              />
            </div>
          ) : null}

          <div className="data-row">
            <div>
              <strong>Browser notifications</strong>
              <br />
              <span className="meta-text">
                A live interruption on this device while MockingBird's tab is open (or backgrounded, not closed) —
                only for a sustained camera/storage problem, never for ordinary wildlife activity. This never leaves
                your device: no cloud or push service is involved.
              </span>
            </div>
            {permission === "unsupported" ? (
              <StatusPill label="Not supported in this browser" tone="quiet" />
            ) : permission === "denied" ? (
              <StatusPill label="Blocked — change this in your browser's site settings" tone="review" />
            ) : permission === "granted" ? (
              <label className="data-row">
                <span>Enabled</span>
                <input
                  checked={preferences.browser_notifications_enabled}
                  onChange={(event) => void save({ browser_notifications_enabled: event.target.checked })}
                  type="checkbox"
                />
              </label>
            ) : (
              <button className="secondary-action" onClick={() => void requestBrowserPermission()} type="button">
                Enable browser notifications
              </button>
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}
