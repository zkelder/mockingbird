import { useCallback, useEffect, useState } from "react";
import { ApiError, apiClient } from "../api/client";
import type {
  CameraSource,
  DashboardSummary,
  DashboardVisitSummary,
  CameraHealthSummary,
  HealthStatus,
  PlaceActivityReportResponse,
  PlaceBiodiversitySummaryResponse,
  PlaceEnvironmentalContext,
  PlaceFeature,
  PlaceFeatureChangeEventCreate,
  PlaceFeatureCreate,
  PlaceFeatureObservationLinkCreate,
  PlaceFeatureUpdate,
  PlaceFeaturesSummary,
  PlaceHabitatContext,
  PlaceHabitatFactCreate,
  PlaceHabitatFactUpdate,
  PlacePhenologyObservationCreate,
  PlacePhenologyObservationUpdate,
  PlaceYearOverYearResponse,
  StorageSummary,
  Stream,
  StreamRuntimeStatus,
  Zone,
} from "../api/types";
import { BiodiversitySummaryCard } from "../components/BiodiversitySummaryCard";
import { EmptyState } from "../components/EmptyState";
import { EnvironmentalContextCard } from "../components/EnvironmentalContextCard";
import { HabitatPhenologyCard } from "../components/HabitatPhenologyCard";
import { LiveCameraOverview } from "../components/LiveCameraOverview";
import { PlaceFeaturesCard } from "../components/PlaceFeaturesCard";
import { ProductHealthPanel } from "../components/ProductHealthPanel";
import { StatusPill } from "../components/StatusPill";
import { TodayAttentionSummary } from "../components/TodayAttentionSummary";
import { TodayReportPanel } from "../components/TodayReportPanel";
import { WeeklySummaryCard } from "../components/WeeklySummaryCard";
import { YearOverYearCard } from "../components/YearOverYearCard";
import {
  cameraHealthLabel,
  cameraHealthTone,
  effectiveSpeciesText,
  formatDateTime,
  formatLabel,
  historicalStatusBadge,
  modalityBadge,
  unconfirmedActivityText,
} from "../utils";

interface ReviewQueueFocus {
  source: "live-motion";
  search: string;
  status: "unreviewed";
}

interface DashboardPageProps {
  health: HealthStatus | null;
  onOpenStream: (streamId: string) => void;
  onOpenStreams: () => void;
  onOpenCameraConfiguration: (streamId: string) => void;
  onAddCamera: () => void;
  onOpenReview: (context?: ReviewQueueFocus) => void;
  onOpenBirdLog: () => void;
  onOpenInsights: () => void;
  onOpenVisit: (visitId: string) => void;
  onOpenPlaceActivityReport: () => void;
  onOpenPlaceStory: () => void;
  onOpenAlertsInbox: () => void;
}

const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;

// The Place Activity Report is period-scoped; "today" is the browser's own
// local midnight-to-midnight span, converted to the UTC instants the report
// API expects. MockingBird has no per-Place timezone setting (see "Local
// time and DST correctness" in docs/place-activity-report-contract.md), so
// this mirrors what a normal user means by "today" on the device in front
// of them; the report's own per-Visit hour bucketing still resolves this
// single-site install's actual host timezone independently.
function todayLocalRange(): { start_at: string; end_at: string } {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start_at: start.toISOString(), end_at: end.toISOString() };
}

// Everyday Product / Discovery UX Closure v1: `getDashboardSummary`'s "today"
// (Best Moments/New Today/Recent Regulars/Cameras needing attention) used to
// default to the *server's* local time, which could disagree with this same
// page's own `todayLocalRange()` browser-local boundary above near local
// midnight or across devices on different timezones. `YYYY-MM-DD` in the
// browser's own local calendar -- deliberately not `toISOString()`, which
// would convert to UTC and reintroduce the exact drift this fixes.
function todayLocalDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// cameraHealthLabel/cameraHealthTone now live in ../utils (First-Hour
// Onboarding + Whole-Product Observability Closure v1, "B7 health model")
// -- shared with Yard & Camera Map so the same CameraHealthState can never
// show a different label/tone on two different pages again.

function outcomeLabel(visit: DashboardVisitSummary): string {
  if (visit.review_outcome === "needs_review") {
    // Everyday Product / Discovery UX Closure v1: the identical Visit could
    // read "Likely American Robin" in Best Moments (effectiveSpeciesText,
    // above) but a generic "Needs review" here in Recent Activity -- consult
    // the same suggestion instead of discarding it.
    const suggestion = effectiveSpeciesText(visit);
    return suggestion ? `Needs review — ${suggestion}` : "Needs review";
  }
  if (visit.review_outcome === "confirmed_bird") {
    return visit.reviewed_label
      ? `Confirmed bird: ${formatLabel(visit.reviewed_label)}`
      : "Confirmed bird observation";
  }
  if (visit.review_outcome === "non_bird") {
    return visit.reviewed_label
      ? `Reviewed activity: ${formatLabel(visit.reviewed_label)}`
      : "Reviewed non-bird activity";
  }
  if (visit.review_outcome === "false_positive") {
    return "False-positive outcome";
  }
  if (visit.review_outcome === "blank") {
    return "Blank outcome";
  }
  if (visit.review_outcome === "ambiguous") {
    return "Ambiguous or unknown outcome";
  }
  if (visit.review_outcome === "rejected") {
    return "Dismissed outcome";
  }
  return visit.reviewed_label
    ? `Reviewed outcome: ${formatLabel(visit.reviewed_label)}`
    : "Reviewed outcome";
}

function durationLabel(seconds: number): string {
  if (seconds <= 0) {
    return "Instant";
  }
  if (seconds < 60) {
    return `${Math.round(seconds)} sec`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return remainder ? `${minutes} min ${remainder} sec` : `${minutes} min`;
}

function VisitPreview({ visit }: { visit: DashboardVisitSummary }) {
  const [unavailable, setUnavailable] = useState(false);
  const badge = modalityBadge(visit.evidence_modality);
  if (!visit.primary_evidence || unavailable) {
    return <div className="dashboard-visit-preview dashboard-preview-unavailable">Preview unavailable</div>;
  }
  // Acoustic / BirdNET Observation Foundation v1, extended by Everyday
  // Discovery / Product Experience v2 (Phase B): audio-only evidence has no
  // visual thumbnail to show here -- an honest "heard, not seen" icon,
  // never a fabricated image standing in for it. Full playback is
  // available from Visit Detail. Uses `evidence_modality`, not a raw
  // content-type sniff, so a collapsed "seen and heard" row (whose primary
  // evidence is always the image side -- see docs/multimodal-list-
  // presentation-contract.md) never mistakenly renders as audio-only.
  if (visit.evidence_modality === "acoustic") {
    return (
      <div className="dashboard-visit-preview dashboard-preview-audio" aria-label="Heard, no image evidence">
        🔊
      </div>
    );
  }
  return (
    <div className="dashboard-visit-preview-wrap">
      <img
        alt={`Visit from ${formatDateTime(visit.captured_at)}`}
        className="dashboard-visit-preview"
        onError={() => setUnavailable(true)}
        src={`${apiClient.baseUrl}${visit.primary_evidence.preview_url}`}
      />
      {badge ? (
        <span className="dashboard-visit-preview-badge" title={badge.label}>
          {badge.icon}
        </span>
      ) : null}
    </div>
  );
}

function VisitContext({ visit }: { visit: DashboardVisitSummary }) {
  return (
    <span className="meta-text">
      {visit.stream_name} · {visit.zone_name ? visit.zone_name : "No Zone"} · {durationLabel(visit.duration_seconds)}
    </span>
  );
}

// Everyday Discovery / Product Experience v2 (Phase B): the ordinary-
// language modality line for a row's text column -- "Seen and heard" (or,
// on the rare row `VisitPreview` cannot badge visually, "Heard"). `null`
// (nothing rendered) for the ordinary single-visual case.
function ModalityNote({ visit }: { visit: DashboardVisitSummary }) {
  const badge = modalityBadge(visit.evidence_modality);
  if (!badge) return null;
  return <span className="meta-text dashboard-visit-modality">{badge.icon} {badge.label}</span>;
}

export function DashboardPage({
  health,
  onOpenStream,
  onOpenStreams,
  onOpenCameraConfiguration,
  onAddCamera,
  onOpenReview,
  onOpenBirdLog,
  onOpenInsights,
  onOpenVisit,
  onOpenPlaceActivityReport,
  onOpenPlaceStory,
  onOpenAlertsInbox,
}: DashboardPageProps) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [report, setReport] = useState<PlaceActivityReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [monitorActionError, setMonitorActionError] = useState<string | null>(null);
  const [durableStatusByStream, setDurableStatusByStream] = useState<
    Record<string, StreamRuntimeStatus>
  >({});
  const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);
  // Environmental Context Foundation v1: a deliberately separate fetch from
  // the report above, not a field on it -- see docs/environmental-context-
  // foundation-v1-contract.md "API surface". `.catch(() => null)` matches
  // every other optional fact here: absence must never block the rest of
  // the dashboard from rendering.
  const [environmentalContext, setEnvironmentalContext] = useState<PlaceEnvironmentalContext | null>(
    null,
  );
  // Habitat & Phenology Foundation v1: a third, equally separate fetch --
  // see docs/habitat-phenology-foundation-v1-contract.md "Frontend
  // surface". Same absence-safety discipline as environmentalContext above.
  const [habitatContext, setHabitatContext] = useState<PlaceHabitatContext | null>(null);
  // Biodiversity & Place Intelligence v1: a fourth, equally separate fetch
  // -- see docs/biodiversity-place-intelligence-v1-contract.md. Same
  // absence-safety discipline as the two context fetches above.
  const [biodiversitySummary, setBiodiversitySummary] = useState<PlaceBiodiversitySummaryResponse | null>(
    null,
  );
  // Place Features & Habitat Change v2: a fifth, equally separate fetch --
  // see docs/place-features-habitat-change-v2-contract.md "Product
  // surfaces". Same absence-safety discipline as the other context
  // fetches above. `zones` is fetched here (not a new separate top-level
  // fetch) purely to populate PlaceFeaturesCard's optional camera-link
  // picker with real names -- it is not otherwise used by this page.
  const [placeFeatures, setPlaceFeatures] = useState<PlaceFeature[] | null>(null);
  const [placeFeaturesSummary, setPlaceFeaturesSummary] = useState<PlaceFeaturesSummary | null>(null);
  const [zones, setZones] = useState<Zone[] | null>(null);
  // Multi-Camera Place Feature Linking & Cross-View Habitat Context v1:
  // fetched here for the identical reason `zones` is above -- purely to
  // populate PlaceFeaturesCard's camera/Zone-view picker with real names;
  // not otherwise used by this page.
  const [placeFeatureSources, setPlaceFeatureSources] = useState<CameraSource[] | null>(null);
  const [placeFeatureStreams, setPlaceFeatureStreams] = useState<Stream[] | null>(null);
  // Year-over-Year Seasonality & Long-Term Place Memory v1: a sixth,
  // equally separate fetch -- see docs/year-over-year-seasonality-long-
  // term-place-memory-v1-report.md. Same absence-safety discipline as the
  // other context fetches above; always the current Place-local month (no
  // params), so it needs no re-fetch when the report period picker changes.
  const [yearOverYear, setYearOverYear] = useState<PlaceYearOverYearResponse | null>(null);

  const refreshDashboard = useCallback(async (initialLoad = false) => {
    if (initialLoad) {
      setIsLoading(true);
    } else {
      setIsRefreshing(true);
    }
    try {
      const [
        nextSummary,
        monitoringStatuses,
        nextStorageSummary,
        nextReport,
        nextEnvironmentalContext,
        nextHabitatContext,
        nextBiodiversitySummary,
        nextPlaceFeatures,
        nextPlaceFeaturesSummary,
        nextZones,
        nextPlaceFeatureSources,
        nextPlaceFeatureStreams,
        nextYearOverYear,
      ] = await Promise.all([
        apiClient.getDashboardSummary(todayLocalDateString()),
        apiClient.getStreamMonitoringStatuses().catch(() => null),
        apiClient.getStorageRetentionSummary().catch(() => null),
        apiClient.getPlaceActivityReport(todayLocalRange()).catch(() => null),
        apiClient.getTodayEnvironmentalContext().catch(() => null),
        apiClient.getPlaceHabitatContext().catch(() => null),
        apiClient.getPlaceBiodiversitySummary().catch(() => null),
        apiClient.getPlaceFeatures().catch(() => null),
        apiClient.getPlaceFeaturesSummary().catch(() => null),
        apiClient.getZones().catch(() => null),
        apiClient.getSources().catch(() => null),
        apiClient.getStreams().catch(() => null),
        apiClient.getPlaceYearOverYear().catch(() => null),
      ]);
      setSummary(nextSummary);
      setStorageSummary(nextStorageSummary);
      setReport(nextReport);
      setEnvironmentalContext(nextEnvironmentalContext);
      setHabitatContext(nextHabitatContext);
      setBiodiversitySummary(nextBiodiversitySummary);
      setPlaceFeatures(nextPlaceFeatures);
      setPlaceFeaturesSummary(nextPlaceFeaturesSummary);
      setZones(nextZones);
      setPlaceFeatureSources(nextPlaceFeatureSources);
      setPlaceFeatureStreams(nextPlaceFeatureStreams);
      setYearOverYear(nextYearOverYear);
      if (monitoringStatuses) {
        setDurableStatusByStream(
          Object.fromEntries(
            monitoringStatuses.items.map((status) => [status.stream_id, status]),
          ),
        );
      }
      setRefreshError(null);
    } catch {
      // Keep the last product snapshot visible during a transient local API failure.
      setRefreshError("Could not refresh daily operations.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refreshDashboard(true);
    const refreshTimer = window.setInterval(
      () => void refreshDashboard(),
      DASHBOARD_REFRESH_INTERVAL_MS,
    );
    return () => window.clearInterval(refreshTimer);
  }, [refreshDashboard]);

  // Environmental Context Foundation v1: the only place a coordinate is
  // ever entered (see docs/environmental-context-foundation-v1-contract.md
  // "Frontend surface") -- no new page, no new nav entry. Re-fetches only
  // the environmental context afterward, not the whole dashboard, so a
  // location edit cannot appear to also refresh unrelated Visit/health data.
  const saveEnvironmentalContextLocation = useCallback(
    async (latitude: number | null, longitude: number | null, weatherEnabled: boolean) => {
      await apiClient.updateEnvironmentalContextSettings({ latitude, longitude, weather_enabled: weatherEnabled });
      const nextEnvironmentalContext = await apiClient.getTodayEnvironmentalContext().catch(() => null);
      setEnvironmentalContext(nextEnvironmentalContext);
    },
    [],
  );

  // Habitat & Phenology Foundation v1: the only place these are edited --
  // no new page, no new nav entry, mirroring the precedent above exactly.
  // Each mutation re-fetches only the habitat/phenology bundle afterward,
  // not the whole dashboard.
  const refreshHabitatContext = useCallback(async () => {
    const next = await apiClient.getPlaceHabitatContext().catch(() => null);
    setHabitatContext(next);
  }, []);

  const addHabitatFact = useCallback(
    async (payload: PlaceHabitatFactCreate) => {
      await apiClient.createPlaceHabitatFact(payload);
      await refreshHabitatContext();
    },
    [refreshHabitatContext],
  );

  const updateHabitatFact = useCallback(
    async (factId: string, payload: PlaceHabitatFactUpdate) => {
      await apiClient.updatePlaceHabitatFact(factId, payload);
      await refreshHabitatContext();
    },
    [refreshHabitatContext],
  );

  const removeHabitatFact = useCallback(
    async (factId: string) => {
      await apiClient.deletePlaceHabitatFact(factId);
      await refreshHabitatContext();
    },
    [refreshHabitatContext],
  );

  const addPhenologyObservation = useCallback(
    async (payload: PlacePhenologyObservationCreate) => {
      await apiClient.createPlacePhenologyObservation(payload);
      await refreshHabitatContext();
    },
    [refreshHabitatContext],
  );

  const updatePhenologyObservation = useCallback(
    async (observationId: string, payload: PlacePhenologyObservationUpdate) => {
      await apiClient.updatePlacePhenologyObservation(observationId, payload);
      await refreshHabitatContext();
    },
    [refreshHabitatContext],
  );

  const removePhenologyObservation = useCallback(
    async (observationId: string) => {
      await apiClient.deletePlacePhenologyObservation(observationId);
      await refreshHabitatContext();
    },
    [refreshHabitatContext],
  );

  // Place Features & Habitat Change v2: the only place these are edited --
  // no new page, no new nav entry, mirroring the Habitat & Phenology
  // precedent above exactly. Each mutation re-fetches only the Feature
  // bundle afterward, not the whole dashboard.
  const refreshPlaceFeatures = useCallback(async () => {
    const [nextFeatures, nextSummary] = await Promise.all([
      apiClient.getPlaceFeatures().catch(() => null),
      apiClient.getPlaceFeaturesSummary().catch(() => null),
    ]);
    setPlaceFeatures(nextFeatures);
    setPlaceFeaturesSummary(nextSummary);
  }, []);

  const addPlaceFeature = useCallback(
    async (payload: PlaceFeatureCreate) => {
      await apiClient.createPlaceFeature(payload);
      await refreshPlaceFeatures();
    },
    [refreshPlaceFeatures],
  );

  const updatePlaceFeature = useCallback(
    async (featureId: string, payload: PlaceFeatureUpdate) => {
      await apiClient.updatePlaceFeature(featureId, payload);
      await refreshPlaceFeatures();
    },
    [refreshPlaceFeatures],
  );

  // Returns a user-safe explanation instead of throwing when the deletion
  // is blocked (409 -- the Feature has recorded change history; see
  // ProductRepository.remove_place_feature), so the card can explain
  // "deactivate it instead" rather than failing silently.
  const removePlaceFeature = useCallback(
    async (featureId: string): Promise<string | null> => {
      try {
        await apiClient.deletePlaceFeature(featureId);
        await refreshPlaceFeatures();
        return null;
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          return error.message;
        }
        return "Could not remove that feature. Try again.";
      }
    },
    [refreshPlaceFeatures],
  );

  const addPlaceFeatureChangeEvent = useCallback(
    async (payload: PlaceFeatureChangeEventCreate) => {
      await apiClient.createPlaceFeatureChangeEvent(payload);
      await refreshPlaceFeatures();
    },
    [refreshPlaceFeatures],
  );

  // Multi-Camera Place Feature Linking & Cross-View Habitat Context v1:
  // add/remove one observation view without disturbing any already-linked
  // ones. Both return a user-safe explanation instead of throwing when
  // rejected (422 -- an invalid/mismatched Zone or an already-linked
  // duplicate view; see ProductRepository.add_place_feature_observation_
  // link), mirroring `removePlaceFeature`'s identical discipline.
  const addPlaceFeatureObservationLink = useCallback(
    async (featureId: string, payload: PlaceFeatureObservationLinkCreate): Promise<string | null> => {
      try {
        await apiClient.addPlaceFeatureObservationLink(featureId, payload);
        await refreshPlaceFeatures();
        return null;
      } catch (error) {
        if (error instanceof ApiError && error.status === 422) {
          return error.message;
        }
        return "Could not link that view. Try again.";
      }
    },
    [refreshPlaceFeatures],
  );

  const removePlaceFeatureObservationLink = useCallback(
    async (featureId: string, linkId: string): Promise<string | null> => {
      try {
        await apiClient.removePlaceFeatureObservationLink(featureId, linkId);
        await refreshPlaceFeatures();
        return null;
      } catch {
        return "Could not remove that view. Try again.";
      }
    },
    [refreshPlaceFeatures],
  );

  async function handleDurableMonitoringAction(
    streamId: string,
    action: "enable" | "disable" | "retry",
  ) {
    setMonitorActionError(null);
    const idempotencyKey =
      globalThis.crypto?.randomUUID?.() ??
      `dashboard-monitoring-${action}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    try {
      const result =
        action === "retry"
          ? await apiClient.retryStreamMonitoring(streamId, {
              idempotency_key: idempotencyKey,
            })
          : await apiClient.updateStreamMonitoringPolicy(streamId, {
              enabled: action === "enable",
              idempotency_key: idempotencyKey,
            });
      setDurableStatusByStream((current) => ({
        ...current,
        [streamId]: result.runtime,
      }));
      await refreshDashboard();
    } catch {
      setMonitorActionError(
        "Could not update persistent monitoring. Open Stream Detail to check this camera.",
      );
    }
  }

  function openVisitReview(visit: DashboardVisitSummary) {
    onOpenReview({ source: "live-motion", search: visit.id, status: "unreviewed" });
  }

  if (isLoading && !summary) {
    return <div className="panel">Loading daily operations…</div>;
  }

  if (!summary) {
    return (
      <div className="error-panel">
        <strong>Daily operations are unavailable.</strong>
        <span>{refreshError ?? "MockingBird could not load its current Stream activity."}</span>
        <button className="secondary-action" onClick={() => void refreshDashboard()} type="button">
          Retry
        </button>
      </div>
    );
  }

  const { today } = summary;
  // Everyday Discovery / Product Experience v2 (Phase C): "New today"/
  // "Recent regulars" are the *complete* wildlife-inclusive list (Today's
  // digest above only ever names its own top-5 "highlights"), so a species
  // already named there would otherwise repeat one section down -- the
  // exact "redundant cards"/"repeated information across sections"
  // anti-pattern this milestone's own archaeology flagged. Filter out
  // anything the digest already named by label; both sections now show
  // only what the digest's own bounded top-5 didn't already cover.
  const highlightedLabels = new Set(report?.digest.primary_highlights.map((h) => h.label) ?? []);
  const newTodayOverflow = today.new_today.filter((species) => !highlightedLabels.has(species.label));
  const recentRegularsOverflow = today.recent_regulars.filter(
    (species) => !highlightedLabels.has(species.label),
  );
  const dayHasAnyOwnActivity =
    today.best_moments.length > 0 || newTodayOverflow.length > 0 || recentRegularsOverflow.length > 0;
  return (
    <div className="page-stack dashboard-operations-page">
      <section className="dashboard-hero dashboard-operations-hero">
        <div>
          <StatusPill
            label={health?.status === "ok" ? "Local app connected" : "Local status unavailable"}
            tone={health?.status === "ok" ? "good" : "review"}
          />
          <h1>Today in Your Yard</h1>
          <p>
            What visited, how often, and where — for {summary.local_day}.
          </p>
        </div>
        <div className="hero-actions">
          <button className="primary-action" onClick={onAddCamera} type="button">
            Add Camera
          </button>
          <button className="primary-action" onClick={onOpenStreams} type="button">
            Open Cameras / Streams
          </button>
          <button className="secondary-action" onClick={onOpenInsights} type="button">
            Zone & Feeder Insights
          </button>
          <button className="secondary-action" onClick={() => void refreshDashboard()} type="button">
            {isRefreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </section>

      {refreshError ? (
        <div className="dashboard-refresh-notice" role="status">
          <span>Could not refresh. Showing the last successful dashboard data.</span>
          <button className="text-action" onClick={() => void refreshDashboard()} type="button">
            Retry
          </button>
        </div>
      ) : null}
      {summary.warnings.length > 0 ? (
        <div className="dashboard-refresh-notice" role="status">
          <span>{summary.warnings[0]}</span>
          {summary.warnings.length > 1 ? <span>+{summary.warnings.length - 1} more Stream updates</span> : null}
        </div>
      ) : null}
      {storageSummary?.storage_warning ? (
        <div className="dashboard-refresh-notice" role="status">
          <span>{storageSummary.storage_warning}</span>
        </div>
      ) : null}

      <TodayAttentionSummary onOpenAlertsInbox={onOpenAlertsInbox} />
      <TodayReportPanel
        configuredStreamCount={summary.headline.configured_stream_count}
        isLoading={isLoading}
        monitoredStreamCount={summary.headline.monitored_stream_count}
        onAddCamera={onAddCamera}
        onOpenBirdLog={onOpenBirdLog}
        onOpenReview={() => onOpenReview()}
        onOpenStreams={onOpenStreams}
        report={report}
      />
      {/* Place / Yard Intelligence v2, Phase 13: a sibling of the report
          panel above, same reasoning as the other sibling cards below --
          see docs/place-yard-intelligence-v2-contract.md section 3.7. */}
      <WeeklySummaryCard weeklyDigest={report?.weekly_digest} />
      {/* Environmental Context Foundation v1: a sibling of the report panel
          above, not nested inside it -- see docs/environmental-context-
          foundation-v1-contract.md "Frontend surface" and this component's
          own docstring for why. */}
      <EnvironmentalContextCard
        context={environmentalContext}
        onSaveLocation={saveEnvironmentalContextLocation}
      />
      {/* Habitat & Phenology Foundation v1: a third sibling card, same
          reasoning as EnvironmentalContextCard above -- see
          docs/habitat-phenology-foundation-v1-contract.md "Frontend
          surface". */}
      <HabitatPhenologyCard
        context={habitatContext}
        onAddHabitatFact={addHabitatFact}
        onAddPhenologyObservation={addPhenologyObservation}
        onRemoveHabitatFact={removeHabitatFact}
        onRemovePhenologyObservation={removePhenologyObservation}
        onUpdateHabitatFact={updateHabitatFact}
        onUpdatePhenologyObservation={updatePhenologyObservation}
      />
      {/* Place Features & Habitat Change v2: a fifth sibling card, same
          reasoning as EnvironmentalContextCard/HabitatPhenologyCard above --
          see docs/place-features-habitat-change-v2-contract.md "Product
          surfaces". */}
      <PlaceFeaturesCard
        features={placeFeatures}
        onAddChangeEvent={addPlaceFeatureChangeEvent}
        onAddFeature={addPlaceFeature}
        onAddObservationLink={addPlaceFeatureObservationLink}
        onRemoveFeature={removePlaceFeature}
        onRemoveObservationLink={removePlaceFeatureObservationLink}
        onUpdateFeature={updatePlaceFeature}
        sources={placeFeatureSources}
        streams={placeFeatureStreams}
        summary={placeFeaturesSummary}
        zones={zones}
      />
      {/* Biodiversity & Place Intelligence v1: a fourth sibling card, same
          reasoning as EnvironmentalContextCard/HabitatPhenologyCard above --
          see docs/biodiversity-place-intelligence-v1-contract.md. */}
      <BiodiversitySummaryCard onOpenBirdLog={onOpenBirdLog} summary={biodiversitySummary} />
      {/* Year-over-Year Seasonality & Long-Term Place Memory v1: a fifth
          sibling card, same reasoning as the others above -- see
          docs/year-over-year-seasonality-long-term-place-memory-v1-report.md. */}
      <YearOverYearCard comparison={yearOverYear} onOpenBirdLog={onOpenBirdLog} />
      {/* Everyday Discovery / Product Experience v2 (Phase G): Today's own
          report above only ever shows one busiest_zone winner and a single
          change sentence -- this links to the fuller exploration surface
          over the same underlying Place Activity Report, for a period the
          reviewer chooses. Deliberately not the "Zone & Feeder Insights"
          button above (a separate, bird-only, differently-computed BI
          surface) -- the two are never the same link. */}
      <div className="place-report-entry-link">
        <button className="text-action" onClick={onOpenPlaceActivityReport} type="button">
          See the full place report
        </button>
        {/* Place Story & Seasonal Timeline v1: the longitudinal "what
            happened here, over time" sibling to the full place report --
            deliberately a separate link, not folded into the one above
            (Bird Log = granular history, Place Report = the current
            picture, Place Story = meaningful history over time). */}
        <button className="text-action" onClick={onOpenPlaceStory} type="button">
          See the Place Story
        </button>
      </div>

      <section aria-label="Recent highlights" className="page-stack">
        {dayHasAnyOwnActivity ? (
          <>
            {today.best_moments.length > 0 ? (
              <section className="panel">
                <div className="section-heading">
                  <div>
                    <h2>Best moments</h2>
                    <span className="meta-text">The encounters most worth opening today</span>
                  </div>
                </div>
                <div className="dashboard-visit-list">
                  {today.best_moments.map((visit) => (
                    <article className="dashboard-visit-row" key={visit.id}>
                      <VisitPreview visit={visit} />
                      <div>
                        <strong>
                          {effectiveSpeciesText(visit) ??
                            unconfirmedActivityText(visit.primary_evidence?.content_type)}
                        </strong>
                        <VisitContext visit={visit} />
                        <ModalityNote visit={visit} />
                        <span className="meta-text">{formatDateTime(visit.captured_at)}</span>
                      </div>
                      <button className="text-action" onClick={() => onOpenVisit(visit.id)} type="button">View</button>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {newTodayOverflow.length > 0 || recentRegularsOverflow.length > 0 ? (
              <section className="dashboard-observation-grid dashboard-secondary-section">
                {newTodayOverflow.length > 0 ? (
                  <section className="panel">
                    <div className="section-heading"><div><h2>New today</h2><span className="meta-text">Beyond today’s highlights above</span></div></div>
                    {newTodayOverflow.map((species) => {
                      const badge = historicalStatusBadge(species.historical_status);
                      return (
                        <article className="dashboard-observation-row" key={species.label}>
                          <VisitPreview visit={species.latest_visit} />
                          <div>
                            <strong>{species.display_name}</strong>
                            <span>{badge?.label ?? "First confirmed here today"}</span>
                          </div>
                          <button className="text-action" onClick={() => onOpenVisit(species.latest_visit.id)} type="button">View</button>
                        </article>
                      );
                    })}
                  </section>
                ) : null}
                {recentRegularsOverflow.length > 0 ? (
                  <section className="panel">
                    <div className="section-heading"><div><h2>Recent regulars</h2><span className="meta-text">Beyond today’s highlights above</span></div></div>
                    {recentRegularsOverflow.map((species) => (
                      <article className="dashboard-observation-row" key={species.label}>
                        <VisitPreview visit={species.latest_visit} />
                        <div>
                          <strong>{species.display_name}</strong>
                          <span>Regular here · seen on {species.distinct_days_seen} of the last 14 days</span>
                        </div>
                        <button className="text-action" onClick={() => onOpenVisit(species.latest_visit.id)} type="button">View</button>
                      </article>
                    ))}
                  </section>
                ) : null}
              </section>
            ) : null}
          </>
        ) : (
          // Everyday Discovery / Product Experience v2 (Phase C/M): one
          // calm note instead of three separate "nothing here" cards
          // (Best moments / New today / Recent regulars) -- Today’s report
          // above already gave the honest reason (no monitoring yet,
          // genuinely quiet day, ...); repeating "nothing to show" three
          // more times in three more words is noise, not information.
          <section className="panel">
            <EmptyState
              title="Nothing else to show for today yet"
              description="New animal activity, new species, and regulars will appear here as today unfolds."
            />
          </section>
        )}
      </section>

      {monitorActionError ? <div className="dashboard-action-error" role="alert">{monitorActionError}</div> : null}
      {today.observation_health.length > 0 ? (
        <section className="panel dashboard-camera-attention" aria-label="Cameras needing attention">
          <div className="section-heading">
            <div>
              <h2>Cameras needing attention</h2>
              <span className="meta-text">
                {/* Multi-Camera Place Experience v2: every currently-armed
                    camera being unhealthy at once is materially different
                    from one of several -- Phase 21 ("if all active cameras
                    stop... Product should clearly communicate"). Computed
                    from two already-returned facts (the unhealthy list vs.
                    `headline.monitored_stream_count`, the same "currently
                    armed" denominator Today's own camera filter already
                    uses), never a new backend computation. `observation_
                    health` is bounded to 12 (see the schema), so this stays
                    exact within this milestone's own supported concurrency
                    envelope; a Place with more unhealthy cameras than that
                    is already well beyond it. */}
                {summary.headline.monitored_stream_count > 0 &&
                today.observation_health.length >= summary.headline.monitored_stream_count
                  ? "MockingBird is not currently observing visually — every armed camera needs attention."
                  : "Compact observation-health facts from enabled Streams"}
              </span>
            </div>
            <StatusPill
              label={`${today.observation_health.length} needs attention`}
              tone={
                summary.headline.monitored_stream_count > 0 &&
                today.observation_health.length >= summary.headline.monitored_stream_count
                  ? "alert"
                  : "review"
              }
            />
          </div>
          <div className="dashboard-visit-list">
            {today.observation_health.map((camera) => (
              <article className="dashboard-visit-row" key={camera.stream_id}>
                <div>
                  <StatusPill label={cameraHealthLabel(camera.state)} tone={cameraHealthTone(camera.state)} />
                  <strong>{camera.stream_name}</strong>
                  <span className="meta-text">{camera.source_name} · {formatLabel(camera.desired_mode)} / {formatLabel(camera.actual_state)}</span>
                  <span className="meta-text">
                    Last good frame {camera.last_good_frame_at ? formatDateTime(camera.last_good_frame_at) : "not yet received"}
                    {camera.last_evidence_persisted_at ? ` · Evidence write ${formatDateTime(camera.last_evidence_persisted_at)}` : ""}
                    {camera.next_retry_at ? ` · Next retry ${formatDateTime(camera.next_retry_at)}` : ""}
                  </span>
                  <span className="meta-text">{camera.failure_reason ?? camera.message}</span>
                  {camera.connectivity_reason === "host_unreachable" ? (
                    <span className="meta-text">
                      The camera kept working while disconnected
                      {typeof camera.backlog_pending_count === "number"
                        ? ` and has ${camera.backlog_pending_count} item(s) waiting to sync`
                        : ""}
                      .
                    </span>
                  ) : null}
                </div>
                <div className="detail-actions">
                  <button className="secondary-action" onClick={() => onOpenStream(camera.stream_id)} type="button">Open Stream</button>
                  {camera.desired_mode === "armed" ? <button className="secondary-action" onClick={() => void handleDurableMonitoringAction(camera.stream_id, "retry")} type="button">Retry now</button> : null}
                  <button className="text-action" onClick={() => onOpenCameraConfiguration(camera.stream_id)} type="button">Edit camera setup</button>
                  {camera.desired_mode === "armed" ? <button className="text-action" onClick={() => void handleDurableMonitoringAction(camera.stream_id, "disable")} type="button">Disable monitoring</button> : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      <LiveCameraOverview
        onOpenReview={(streamId) =>
          onOpenReview({ source: "live-motion", search: streamId, status: "unreviewed" })
        }
        onOpenStream={onOpenStream}
        onOpenCameraConfiguration={onOpenCameraConfiguration}
        onToggleMonitoring={(stream, runtime) =>
          void handleDurableMonitoringAction(
            stream.stream_id,
            runtime.desired_mode === "armed" ? "disable" : "enable",
          )
        }
        runtimeByStream={durableStatusByStream}
        streams={summary.streams}
      />

      {/* Everyday Discovery / Product Experience v2 (Phase C): app/storage/
          backup health is real, useful information, but it is not "what
          happened here today" -- moved below the wildlife-discovery content
          instead of leading the page, matching the milestone's priority
          order (product-doctrine.md: this is a nature observatory, not an
          operations dashboard). */}
      <ProductHealthPanel storageSummary={storageSummary} />

      <section className="panel dashboard-recent-activity">
        <div className="section-heading">
          <div>
            <h2>Recent activity</h2>
            <span className="meta-text">Newest Visits across Streams</span>
          </div>
          <span className="meta-text">Updated {formatDateTime(summary.generated_at)}</span>
        </div>
        {summary.recent_activity.length > 0 ? (
          <div className="dashboard-visit-list">
            {summary.recent_activity.map((visit) => (
              <article className="dashboard-visit-row dashboard-activity-row" key={visit.id}>
                <VisitPreview visit={visit} />
                <div>
                  <strong>{outcomeLabel(visit)}</strong>
                  <span>{formatDateTime(visit.captured_at)}</span>
                  <VisitContext visit={visit} />
                  <ModalityNote visit={visit} />
                </div>
                <div className="detail-actions">
                  {visit.review_status === "needs_review" ? (
                    <button className="secondary-action" onClick={() => openVisitReview(visit)} type="button">Review</button>
                  ) : (
                    <button className="secondary-action" onClick={() => onOpenVisit(visit.id)} type="button">Visit detail</button>
                  )}
                  <button className="text-action" onClick={() => onOpenStream(visit.stream_id)} type="button">Stream</button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No recent activity"
            description="Captured Visits will appear here after activity becomes reviewable."
            action={<button className="secondary-action" onClick={onOpenStreams} type="button">Open Cameras / Streams</button>}
          />
        )}
      </section>
    </div>
  );
}
