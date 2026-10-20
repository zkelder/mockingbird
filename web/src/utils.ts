import type {
  CameraHealthState,
  ListEvidenceModality,
  PlaceActivityReportRegularityNarrative,
  PlaceActivityReportSeasonalPattern,
  PlaceActivityReportTaxonChangeStatus,
  SpeciesHistoricalStatus,
  WeatherConditions,
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

/**
 * Place / Yard Intelligence v2: same "only when it says something the
 * historical/change badges above did not already say" discipline --
 * `"first_record"`/`"new"`/`"occasional"`/plain `"regular"` render nothing
 * here (their equivalent already shows via `historicalStatusBadge`/
 * `changeStatusBadge`), so a taxon never carries a redundant third badge
 * saying the same thing twice.
 */
export function regularityNarrativeBadge(
  narrative: PlaceActivityReportRegularityNarrative | null | undefined,
): { label: string; tone: "good" | "quiet" } | null {
  switch (narrative?.state) {
    case "becoming_regular":
      return { label: "Becoming a regular visitor", tone: "good" };
    case "quieter_lately":
      return { label: "Quieter than usual lately", tone: "quiet" };
    case "returned_after_absence":
      return { label: "Back after a quiet stretch", tone: "quiet" };
    default:
      return null;
  }
}

/** `null` for every non-"established_pattern" status, including the
 * common, honest "insufficient_history" case -- see `seasonal_pattern.py`'s
 * own docstring for why that is the expected state for a young
 * installation. */
export function seasonalPatternNote(
  pattern: PlaceActivityReportSeasonalPattern | null | undefined,
): string | null {
  if (pattern?.status !== "established_pattern") {
    return null;
  }
  return pattern.current_month_is_typical ? "Typical for this time of year" : null;
}

/** Plain calendar-date formatting (`YYYY-MM-DD` inputs -- Place Story event
 * dates, phenology intervals, feature-change effective dates -- never a
 * datetime with a time-of-day component to show). */
export function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export function formatMonthYear(value: string): string {
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "long", timeZone: "UTC" }).format(
    new Date(`${value}T00:00:00Z`),
  );
}

/** Local-calendar-date rendering of a real instant (e.g. "first observed
 * here on <date>" facts) -- distinct from `formatDate`'s UTC-pinned
 * plain-date-*literal* handling (Place Story event dates, phenology
 * intervals, which already are a bare calendar date with no instant to
 * convert). This one input genuinely is a timestamp and must resolve to
 * the viewer's own local calendar day, not be read back as if it were
 * already a date string. */
export function formatDateFromInstant(value: string): string {
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(
    new Date(value),
  );
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

// Owner-Only Release Polish & Acceptance v1 (O-1): a recording imported with
// no capture-time fact is anchored internally at 1970 (the raw timestamp is
// kept for ordering and provenance). `formatDateTime` omits the year, so that
// placeholder used to read as a real recent date ("Dec 31, 7:00 PM"). The
// server's `capture_time_known` fact -- never the date's age -- decides.
export const CAPTURE_TIME_UNKNOWN_LABEL = "Capture time unknown";

// Everyday Wildlife Experience & Presentation Refinement v1: surfaces that
// show a bare instant with no per-record `capture_time_known` fact (Alerts,
// Local Data's oldest/newest media) mirror the server's own placeholder
// prefilter (`CAPTURE_TIME_PLACEHOLDER_PREFILTER_CEILING`, 1971-01-01): no
// real MockingBird observation, import or alert can predate it, so an instant
// before it is the epoch anchor of a recording with no capture-time fact and
// is never rendered as a date. Nothing is invented in its place.
const PLACEHOLDER_INSTANT_CEILING_MS = Date.UTC(1971, 0, 1);

export function isPlaceholderInstant(value: string): boolean {
  const parsed = new Date(value).getTime();
  return !Number.isNaN(parsed) && parsed < PLACEHOLDER_INSTANT_CEILING_MS;
}

export function formatInstantOrUnknown(value: string, format: (value: string) => string = formatDateTime): string {
  return isPlaceholderInstant(value) ? CAPTURE_TIME_UNKNOWN_LABEL : format(value);
}

export function formatCaptureDateTime(value: string, captureTimeKnown: boolean | undefined): string {
  return captureTimeKnown === false ? CAPTURE_TIME_UNKNOWN_LABEL : formatDateTime(value);
}

// Owner-Only Release Polish & Acceptance v1 (O-2): what an empty
// `detections` list actually means. Those are separate stored detection
// records; Visits found by the Observation Engine (live or by offline
// analysis of an imported recording) and by sound analysis never carry any
// -- their saved evidence frames/clips are the evidence. Only a manual or
// folder media import is honestly a "manual media" record.
export function noDetectionRecordsMessage(
  eventType: string,
  acquisitionType: "recorded_video" | "continuous_live" | "unknown" | undefined,
  scope: "visit" | "event",
): string {
  if (eventType === "observation_engine_candidate") {
    const foundBy =
      acquisitionType === "recorded_video"
        ? "Found by offline analysis of an imported recording."
        : acquisitionType === "continuous_live"
          ? "Found by live observation."
          : "Found by automatic analysis.";
    return `${foundBy} No separate detection records are stored for this ${scope}; review its saved evidence frames instead.`;
  }
  if (eventType === "acoustic_observation_candidate") {
    return `Found by sound analysis. No separate detection records are stored for this ${scope}; review its saved recording instead.`;
  }
  if (eventType === "manual_media_import" || eventType === "folder_media_import") {
    return `No detections are attached to this manual media ${scope}.`;
  }
  return `No detection records are attached to this ${scope}.`;
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

// Environmental Context v2 (see docs/environmental-context-v2-contract.md
// "Phase 16"): a small, restrained sentence describing conditions, composed
// server-side (`condition_bands.describe_current_conditions`) from this
// Place's own Place-relative temperature band plus sky/precipitation --
// never a bare number presented as more precise than it is. `air_temperature_
// c` is shown alongside as a supplementary, honest raw reading (converted to
// Fahrenheit only for display; the stored/API value stays Celsius). Shared
// by EnvironmentalContextCard (Today) and VisitDetailPage (a Visit's own
// Conditions card) so the two surfaces can never phrase the same fact
// differently. Returns `null` when there is nothing to show -- callers
// treat that as silence, never an error state.
export function formatWeatherLine(weather: WeatherConditions): string | null {
  if (weather.status !== "available" && weather.status !== "stale") {
    return null;
  }
  if (weather.air_temperature_c == null) {
    return weather.summary_text ?? null;
  }
  const fahrenheit = Math.round((weather.air_temperature_c * 9) / 5 + 32);
  const staleSuffix = weather.status === "stale" ? " (last updated a while ago)" : "";
  return weather.summary_text
    ? `${fahrenheit}°F, ${weather.summary_text}${staleSuffix}`
    : `${fahrenheit}°F${staleSuffix}`;
}

// Habitat & Phenology Foundation v1: `value` is a plain UTC calendar date
// (`YYYY-MM-DD`, no time-of-day component -- see PlacePhenologyObservation's
// own docstring) -- never route it through `new Date(value)`'s default local-
// timezone formatting, which would risk rendering it as the *previous*
// calendar day for any negative-UTC-offset viewer (the exact
// `new Date("YYYY-MM-DD")` pitfall PlaceActivityReportPage.tsx's own
// `parseLocalDateInput` already documents and avoids for input parsing).
// Anchoring to UTC midnight and formatting with `timeZone: "UTC"` keeps the
// displayed date identical to the stored value for every viewer.
export function formatCalendarDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

// Habitat & Phenology Foundation v1: shared by HabitatPhenologyCard (the
// Today card) and PlaceActivityReportPage (the read-only history view) so
// the two never drift into presenting the same interval differently.
export function phenologyDateRange(startDate: string, endDate: string | null | undefined): string {
  if (!endDate || endDate === startDate) {
    return `Noted ${formatCalendarDate(startDate)}`;
  }
  return `${formatCalendarDate(startDate)} – ${formatCalendarDate(endDate)}`;
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

// Everyday UX & Accessibility Closure v1: a failure caught in a page handler
// is shown to the person using MockingBird, so it must read as a product
// message. `ApiError` (and page/`withTimeout`-authored `Error`s) already carry
// human-written text and pass through. A built-in JavaScript runtime error --
// a response body that was not valid JSON ("Unexpected token '<'"), or a
// "Cannot read properties of undefined" slip -- is developer language that
// tells a person nothing actionable, so the page's own fallback is shown
// instead. The raw error still goes to the console for diagnosis; nothing is
// swallowed.
const DEVELOPER_ERROR_NAMES = new Set([
  "TypeError",
  "SyntaxError",
  "RangeError",
  "ReferenceError",
  "EvalError",
  "URIError",
]);

export function userFacingErrorMessage(caught: unknown, fallback: string): string {
  if (!(caught instanceof Error)) {
    return fallback;
  }
  if (DEVELOPER_ERROR_NAMES.has(caught.name)) {
    console.error(caught);
    return fallback;
  }
  return caught.message.trim() || fallback;
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

/**
 * Merge a bounded MediaAsset picker window with separately-hydrated assets.
 *
 * Remaining Performance P1 Closure v1 (P1-7). Pages that used to hold the
 * whole MediaAsset library now read two bounded sets -- a recent window for
 * their picker, and exactly the assets their already-bounded list
 * references. This joins the two into the single newest-first list those
 * pages previously derived from the library, de-duplicated by id.
 */
export function mergeMediaAssets<T extends { id: string; created_at: string }>(
  ...groups: T[][]
): T[] {
  const byId = new Map<string, T>();
  for (const group of groups) {
    for (const asset of group) {
      if (!byId.has(asset.id)) {
        byId.set(asset.id, asset);
      }
    }
  }
  return [...byId.values()].sort(
    (first, second) => Date.parse(second.created_at) - Date.parse(first.created_at),
  );
}
