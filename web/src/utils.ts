import type {
  CameraHealthState,
  ListEvidenceModality,
  PlaceActivityReportTaxonChangeStatus,
  SpeciesHistoricalStatus,
} from "./api/types";

/**
 * First-Hour Onboarding + Whole-Product Observability Closure v1 ("B7
 * health model"): the single canonical presentation for `CameraHealthState`,
 * shared by every surface that renders it (Dashboard, Yard & Camera Map,
 * and any future one) so the same backend state can never show a different
 * label/tone on two different pages again -- a real, confirmed divergence
 * this milestone's own investigation found (Dashboard distinguished
 * `camera_unavailable`/`no_recent_frame`/`evidence_storage_degraded`/
 * `setup_incomplete` into four distinct labels; Yard Map collapsed all four
 * to the identical "Unavailable"). Standardizes on the more differentiated
 * set -- a specific reason is more actionable than a generic one (see "Do
 * not collapse every failure into 'Camera unavailable'" in the governing
 * milestone brief) -- rather than the reverse.
 */
export function cameraHealthLabel(state: CameraHealthState): string {
  return {
    healthy: "Healthy",
    starting: "Starting",
    waiting_for_capacity: "Waiting for capacity",
    camera_unavailable: "Camera unavailable",
    no_recent_frame: "No recent frame",
    evidence_storage_degraded: "Evidence storage degraded",
    recovering: "Recovering",
    stopped: "Monitoring stopped",
    setup_incomplete: "Setup incomplete",
  }[state];
}

/**
 * Camera / Source + Multi-Camera Maturity v1, Phase F: a fourth tone so a
 * bounded, self-healing `recovering` state no longer renders identically to
 * `camera_unavailable`/`no_recent_frame` (retries exhausted, genuinely
 * needs attention) -- a real, confirmed conflation this milestone's own
 * archaeology found ("recovering/reprovisioning state should not look like
 * permanent failure"). `waiting_for_capacity`/`evidence_storage_degraded`/
 * `setup_incomplete` deliberately keep their existing "review" tone --
 * unrelated to the specific conflation this fixes.
 */
export function cameraHealthTone(state: CameraHealthState): "good" | "review" | "alert" | "quiet" {
  if (state === "healthy") return "good";
  if (state === "stopped" || state === "starting") return "quiet";
  if (state === "camera_unavailable" || state === "no_recent_frame") return "alert";
  return "review";
}

export function formatLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Gate C -- Meaningful Change Detection / Baseline Comparison v1 (see
 * docs/meaningful-change-detection-contract.md). Shared by Today
 * (`TodayReportPanel`) and Bird Log (`BirdLogPage`) so both surfaces use
 * identical wording for the same underlying fact. Only the two "there is
 * something worth saying" statuses render a badge at all --
 * `insufficient_baseline`/`insufficient_recent_coverage`/`no_supported_
 * change` (and no change_status at all, e.g. a purely-provisional taxon)
 * render nothing, keeping an ordinary row calm rather than decorating every
 * species with a "no change" pill. Deliberately "quiet" tone for both
 * directions -- more or fewer recent sightings is a recorded fact, never a
 * value judgment (a squirrel visiting more often is not "good news").
 */
export function changeStatusBadge(
  changeStatus: PlaceActivityReportTaxonChangeStatus | null | undefined,
): { label: string; tone: "good" | "quiet" } | null {
  switch (changeStatus?.status) {
    case "higher_recent_presence":
      return { label: "More often recently", tone: "quiet" };
    case "lower_recent_presence":
      return { label: "Fewer recent visits", tone: "quiet" };
    default:
      return null;
  }
}

/**
 * The normal-consumer species answer for one Visit summary: human-confirmed
 * truth first, otherwise an automatic AI suggestion prefixed "Likely" so it
 * is never mistaken for reviewed truth, otherwise null (caller falls back
 * to its own "not confirmed" copy). Mirrors the resolution rule the backend
 * already applies everywhere `reviewed_label ?? species_guess` is read --
 * see the Automatic Species Suggestion v1 milestone.
 */
export function effectiveSpeciesText(visit: {
  reviewed_label?: string | null;
  has_suggestion?: boolean;
  suggested_label?: string | null;
}): string | null {
  if (visit.reviewed_label) {
    return formatLabel(visit.reviewed_label);
  }
  if (visit.has_suggestion && visit.suggested_label) {
    return `Likely ${formatLabel(visit.suggested_label)}`;
  }
  return null;
}

/**
 * The unconfirmed-activity fallback copy for one Visit summary, used only
 * when `effectiveSpeciesText` returns null (no reviewed label, no
 * suggestion). Acoustic / BirdNET Observation Foundation v1: honest about
 * whether the underlying evidence was heard or seen -- "Animal detected"
 * (implying a visual sighting) would be misleading for an audio-only Visit.
 */
export function unconfirmedActivityText(evidenceContentType?: string | null): string {
  return evidenceContentType?.startsWith("audio/")
    ? "Bird heard — species not confirmed"
    : "Animal detected — species not confirmed";
}

/**
 * Everyday Discovery / Product Experience v2 (Phase B/J; see docs/
 * multimodal-list-presentation-contract.md): ordinary-language modality
 * badge for a list row, shared by Today and Bird Log so the same underlying
 * fact never reads differently on two surfaces. Deliberately `null` for the
 * plain "visual" case -- an ordinary photo Visit needs no special callout;
 * only the cases worth a reader's attention (audio-only, or a collapsed
 * "seen and heard" pair) get a badge at all, matching this file's existing
 * "only render a pill when there is something worth saying" convention
 * (see `changeStatusBadge`).
 */
export function modalityBadge(
  modality: ListEvidenceModality,
): { label: string; icon: string } | null {
  switch (modality) {
    case "acoustic":
      return { label: "Heard", icon: "🔊" };
    case "seen_and_heard":
      return { label: "Seen and heard", icon: "👁️🔊" };
    default:
      return null;
  }
}

/**
 * Everyday Discovery / Product Experience v2 (Phase E; see docs/canonical-
 * new-regular-species-contract.md): the single canonical New/Regular
 * wording, shared by Today and Bird Log so the same `historical_status`
 * value never reads differently on two surfaces (mirrors the identical
 * server-side wording in `mockingbird.analytics.daily_digest`). `null` for
 * "seen_before" -- the calm, ordinary case gets no badge at all.
 */
export function historicalStatusBadge(
  status: SpeciesHistoricalStatus | null | undefined,
): { label: string; tone: "good" | "quiet" } | null {
  switch (status) {
    case "new":
      return { label: "New to your reviewed history", tone: "good" };
    case "first_record":
      return { label: "First confirmed record so far", tone: "quiet" };
    case "regular":
      return { label: "Regular here", tone: "good" };
    default:
      return null;
  }
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

// Environmental Context Foundation v1: sunrise/sunset are already known to
// be "today" (or the Visit's own day) from context, so showing the date
// again would be redundant -- nearest-minute precision only, matching how
// precisely this feature ever actually knows the moment (never seconds).
export function formatTimeOfDay(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function sortedEntries(record: Record<string, number>): Array<[string, number]> {
  return Object.entries(record).sort((a, b) => b[1] - a[1]);
}

/**
 * The containing folder of a local file path, for display only. Used to show
 * "where MockingBird stores its data" without exposing the database
 * filename/engine itself (handles both `/` and Windows `\` separators).
 */
export function parentDirectory(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const lastSlash = normalized.lastIndexOf("/");
  return lastSlash <= 0 ? path : path.slice(0, lastSlash);
}

/**
 * Bound how long a UI waits on one network action. A slow or unreachable
 * local device (for example a Camera Node that stopped responding) must
 * become a clear, actionable message -- never a button left gray forever
 * with no explanation. Does not cancel the underlying request; it only
 * bounds how long the UI keeps waiting on it, which is what "the button
 * is stuck" actually needs fixed.
 */
export function withTimeout<T>(promise: Promise<T>, timeoutMs: number, action: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`${action} timed out. Check the connection and try again.`));
    }, timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

export function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value / 1024;
  let unitIndex = 0;
  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024;
    unitIndex += 1;
  }
  return `${amount >= 10 ? amount.toFixed(0) : amount.toFixed(1)} ${units[unitIndex]}`;
}
