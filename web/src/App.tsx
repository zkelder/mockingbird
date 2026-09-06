import { useEffect, useMemo, useRef, useState } from "react";
import { apiClient, onSessionExpired } from "./api/client";
import type {
  ActivityLibraryFilters,
  AnalyticsSummary,
  CameraSource,
  CurrentUser,
  DatasetCoverageSummary,
  DatasetExport,
  DatasetQualitySummary,
  HealthStatus,
  ModelReadinessSummary,
  ProductAlertAction,
  ReviewCorrectionResult,
  ReviewQueueItem,
  SetupState,
  SpeciesSuggestion,
  Stream,
  UserRole,
} from "./api/types";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AlertsControl, AlertsInboxPage } from "./components/AlertsInbox";
import { ActivityLibraryPage, activityLibraryPath } from "./pages/ActivityLibraryPage";
import { BirdLogPage } from "./pages/BirdLogPage";
import { CameraSetupPage } from "./pages/CameraSetupPage";
import { CameraConfigurationPage } from "./pages/CameraConfigurationPage";
import { OnboardingWizard } from "./components/OnboardingWizard";
import { ClassifierManifestPage } from "./pages/ClassifierManifestPage";
import { EcologicalDestinationsPage } from "./pages/EcologicalDestinationsPage";
import { ClassifierReadinessPage } from "./pages/ClassifierReadinessPage";
import { CollectionsPage } from "./pages/CollectionsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DetectionProposalsPage } from "./pages/DetectionProposalsPage";
import { EventDetailPage } from "./pages/EventDetailPage";
import { ExportsPage } from "./pages/ExportsPage";
import { FeatureStoryPage } from "./pages/FeatureStoryPage";
import { FolderImportPage } from "./pages/FolderImportPage";
import { LocalDataPage } from "./pages/LocalDataPage";
import { ManualImportPage } from "./pages/ManualImportPage";
import { ModelAdaptersPage } from "./pages/ModelAdaptersPage";
import { MotionEvidenceDetailPage } from "./pages/MotionEvidenceDetailPage";
import { MotionEvidencePage } from "./pages/MotionEvidencePage";
import { PlaceActivityReportPage } from "./pages/PlaceActivityReportPage";
import { PlaceStoryPage } from "./pages/PlaceStoryPage";
import { TaxonStoryPage } from "./pages/TaxonStoryPage";
import {
  ReviewQueuePage,
  type ReviewQueueInitialContext,
} from "./pages/ReviewQueuePage";
import { SavedMediaRetentionPage } from "./pages/SavedMediaRetentionPage";
import { SignInPage } from "./pages/SignInPage";
import { SpeciesSuggestionsPage } from "./pages/SpeciesSuggestionsPage";
import { StreamDetailPage } from "./pages/StreamDetailPage";
import { StreamsPage } from "./pages/StreamsPage";
import { UsersPage } from "./pages/UsersPage";
import { YardMapPage } from "./pages/YardMapPage";
import { VisitDetailPage } from "./pages/VisitDetailPage";
import { WorkerStatusPage } from "./pages/WorkerStatusPage";
import {
  type AppRoute,
  type Page,
  readAppRoute,
  writeAppRoute,
} from "./navigation";

interface AppData {
  health: HealthStatus | null;
  sources: CameraSource[];
  streams: Stream[];
  reviewQueue: ReviewQueueItem[];
  exports: DatasetExport[];
  analytics: AnalyticsSummary | null;
  datasetCoverage: DatasetCoverageSummary | null;
  datasetQuality: DatasetQualitySummary | null;
  modelReadiness: ModelReadinessSummary | null;
}

interface VisitCorrectionPrefill {
  visitId: string;
  label: string;
  speciesSuggestionId: string;
  suggestedCommonName?: string | null;
  suggestedScientificName?: string | null;
}

const initialData: AppData = {
  health: null,
  sources: [],
  streams: [],
  reviewQueue: [],
  exports: [],
  analytics: null,
  datasetCoverage: null,
  datasetQuality: null,
  modelReadiness: null,
};

// `minRole` (Local Identity, Multi-User & Organization Access v1) hides a
// nav item entirely below that role rather than showing it disabled --
// every mutation these pages can reach is still independently enforced
// server-side regardless of what this list shows (see mockingbird.api.auth
// ROUTE_POLICY); this is UX calm, not the authorization boundary itself.
// Omitted `minRole` means every signed-in role (Viewer floor) sees it.
const productNavItems: Array<{ page: Page; label: string; minRole?: UserRole }> = [
  { page: "dashboard", label: "Dashboard" },
  { page: "streams", label: "Cameras" },
  { page: "import", label: "Import Media" },
  { page: "review", label: "Review", minRole: "reviewer" },
  { page: "bird-log", label: "Bird Log" },
  { page: "place-activity-report", label: "Place Report" },
  { page: "place-story", label: "Place Story" },
  { page: "activity-library", label: "Activity" },
  { page: "analytics", label: "Insights" },
  { page: "ecological-destinations", label: "Ecological Destinations" },
  { page: "settings", label: "Settings" },
  { page: "users", label: "Users", minRole: "administrator" },
];

const ROLE_RANK: Record<UserRole, number> = { viewer: 0, reviewer: 1, administrator: 2 };

function roleAtLeast(role: UserRole, minimum: UserRole): boolean {
  return ROLE_RANK[role] >= ROLE_RANK[minimum];
}

// Bird Log (the doctrine's "Remember" step -- product-doctrine.md's core
// Observe -> Discover -> Understand -> Confirm -> Remember -> Improve loop,
// and the durable home for confirmed wildlife truth) predates the
// product/advanced nav split and was carried into advancedNavItems by that
// split along with genuinely technical pages (Analyzers, Classifier
// Readiness). Working App v1 acceptance found this left it unreachable
// through ordinary navigation on any day with no wildlife visits so far
// today (the Today report's own "Top visitors -> Bird Log" link only
// renders once topTaxa is non-empty) -- a nontechnical user had no way to
// browse their Wildlife Journal without first discovering and enabling
// "Developer Mode." Promoted to the persistent primary nav above instead.
//
// Import Media (the "recorded wildlife media" acquisition family this
// milestone's A3 explicitly names as an accepted v0.1 acquisition choice)
// moved out of advancedNavItems for the identical reason, found by this
// milestone's own first-hour investigation: `manual_media` is a normal,
// undisguised Add Camera choice in CameraSetupPage's dropdown (in fact the
// current default selection), but its own completion step -- actually
// importing files into the Source/Stream it creates -- lived only on this
// Developer-Mode-gated page. A user who picked the default acquisition
// choice during setup had no discoverable way to finish it.
const advancedNavItems: Array<{ page: Page; label: string }> = [
  { page: "yard-map", label: "Yard & Camera Map" },
  { page: "exports", label: "Exports / Data" },
  { page: "folder-import", label: "Folder Import" },
  { page: "saved-media-retention", label: "Saved Media Retention" },
  { page: "motion-evidence", label: "Advanced Evidence" },
  { page: "detection-proposals", label: "Detection Proposals" },
  { page: "model-adapters", label: "Analyzers" },
  { page: "species-suggestions", label: "Species Suggestions" },
  { page: "classifier-readiness", label: "Classifier Readiness" },
  { page: "classifier-manifest", label: "Classifier Manifest" },
  { page: "settings", label: "Local Data" },
];

const advancedPages = new Set<Page>([
  ...advancedNavItems.map((item) => item.page),
  "motion-evidence-detail",
]);

// Calm Attention & Notifications v1: maps a Place Story `PlaceStoryEventKind`
// (carried on an `open_place_story` alert action as `story_kind`) onto
// PlaceStoryPage's existing group filter -- see that page's own
// `KINDS_BY_GROUP`, mirrored here rather than imported to avoid a
// page-into-App dependency for one small lookup table.
function placeStoryCategoryForKind(kind: string | null | undefined): "all" | "wildlife" | "place" | "context" {
  if (kind === "return" || kind === "regularity_change" || kind === "diversity_milestone" || kind === "noteworthy_activity" || kind === "first_seen") {
    return "wildlife";
  }
  if (kind === "feature_change" || kind === "phenology") {
    return "place";
  }
  if (kind === "comparison_insight") {
    return "context";
  }
  return "all";
}

export default function App() {
  const [initialRoute] = useState<AppRoute>(() => readAppRoute());
  const [page, setPageState] = useState<Page>(initialRoute.page);
  const [selectedStreamId, setSelectedStreamId] = useState<string | null>(
    initialRoute.streamId ?? null,
  );
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    initialRoute.eventId ?? null,
  );
  const [selectedVisitId, setSelectedVisitId] = useState<string | null>(
    initialRoute.visitId ?? null,
  );
  // Calm Attention & Notifications v1: set only by `openAlertAction`'s
  // `open_place_story` branch, immediately before navigating -- see that
  // function and `placeStoryCategoryForKind` below.
  const [placeStoryInitialCategory, setPlaceStoryInitialCategory] = useState<
    "all" | "wildlife" | "place" | "context"
  >("all");
  const [selectedMotionEvidenceId, setSelectedMotionEvidenceId] = useState<string | null>(
    initialRoute.motionEvidenceId ?? null,
  );
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(
    initialRoute.collectionId ?? null,
  );
  // Place Story Deep Dives & Representative Evidence v1.
  const [selectedTaxonLabel, setSelectedTaxonLabel] = useState<string | null>(
    initialRoute.taxonLabel ?? null,
  );
  const [selectedFeatureStoryId, setSelectedFeatureStoryId] = useState<string | null>(
    initialRoute.featureId ?? null,
  );
  const [reviewQueueInitialContext, setReviewQueueInitialContext] =
    useState<ReviewQueueInitialContext | null>(null);
  const [visitCorrectionPrefill, setVisitCorrectionPrefill] =
    useState<VisitCorrectionPrefill | null>(null);
  const [data, setData] = useState<AppData>(initialData);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);
  const [isAdvancedNavOpen, setIsAdvancedNavOpen] = useState(false);
  const [isDeveloperMode, setIsDeveloperMode] = useState(false);
  // Mobile & Remote Experience v1: the sidebar previously had no compact
  // form at phone widths -- it simply un-pinned and stacked, in full, above
  // every page's own content (every nav destination, every time). Below
  // the mobile nav breakpoint (760px, see styles.css) the sidebar becomes an
  // off-canvas drawer, opened from a small top bar and/or the bottom nav's
  // "More" button, closed on navigation/Escape/backdrop click. Irrelevant
  // (and harmless) above that breakpoint, where the sidebar renders inline
  // as before.
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const mobileNavToggleRef = useRef<HTMLButtonElement>(null);
  // `null` while unknown. A read failure fails open (treated as complete)
  // rather than trapping an existing user behind a broken wizard -- see
  // docs/local-product-packaging-design.md.
  const [setupState, setSetupState] = useState<SetupState | null>(null);
  // Local Identity, Multi-User & Organization Access v1: unlike
  // `setupState`'s fail-open convention above, an auth check that cannot
  // be confirmed must fail CLOSED -- "loading" renders nothing sensitive
  // rather than assuming signed-in.
  const [authStatus, setAuthStatus] = useState<"loading" | "authenticated" | "unauthenticated">(
    "loading",
  );
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  function applyRoute(route: AppRoute) {
    setPageState(route.page);
    if (route.streamId !== undefined) {
      setSelectedStreamId(route.streamId);
    }
    if (route.eventId !== undefined) {
      setSelectedEventId(route.eventId);
    }
    if (route.visitId !== undefined) {
      setSelectedVisitId(route.visitId);
    }
    if (route.motionEvidenceId !== undefined) {
      setSelectedMotionEvidenceId(route.motionEvidenceId);
    }
    if (route.collectionId !== undefined) {
      setSelectedCollectionId(route.collectionId);
    }
    if (route.taxonLabel !== undefined) {
      setSelectedTaxonLabel(route.taxonLabel);
    }
    if (route.featureId !== undefined) {
      setSelectedFeatureStoryId(route.featureId);
    }
  }

  function navigate(route: AppRoute, replace = false) {
    writeAppRoute(route, replace);
    applyRoute(route);
  }

  function setPage(nextPage: Page) {
    navigate({ page: nextPage });
  }

  async function loadAppData(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    setLoadWarnings([]);
    try {
      const [
        healthResult,
        sourcesResult,
        streamsResult,
        reviewQueueResult,
        exportsResult,
        analyticsResult,
        datasetCoverageResult,
        datasetQualityResult,
        modelReadinessResult,
      ] = await Promise.allSettled([
        apiClient.getHealth(),
        apiClient.getSources(),
        apiClient.getStreams(),
        apiClient.getReviewQueue(),
        apiClient.getDatasetExports(),
        apiClient.getAnalyticsSummary(),
        apiClient.getDatasetCoverageSummary(),
        apiClient.getDatasetQualitySummary(),
        apiClient.getModelReadinessSummary(),
      ]);

      if (
        healthResult.status !== "fulfilled" ||
        sourcesResult.status !== "fulfilled" ||
        streamsResult.status !== "fulfilled"
      ) {
        const message =
          "MockingBird reached the local app, but its camera data could not be loaded.";
        if (data.health) {
          setLoadWarnings([`${message} Existing screen data was kept; retry when ready.`]);
        } else {
          setError(message);
        }
        return;
      }

      const optionalResults: Array<[string, PromiseSettledResult<unknown>]> = [
        ["Review activity", reviewQueueResult],
        ["Exports", exportsResult],
        ["Analytics", analyticsResult],
        ["Dataset coverage", datasetCoverageResult],
        ["Dataset quality", datasetQualityResult],
        ["Identification readiness", modelReadinessResult],
      ];
      setLoadWarnings(
        optionalResults
          .filter(([, result]) => result.status === "rejected")
          .map(([label]) => `${label} is temporarily unavailable.`),
      );

      setData({
        health: healthResult.value,
        sources: sourcesResult.value,
        streams: streamsResult.value,
        reviewQueue:
          reviewQueueResult.status === "fulfilled"
            ? reviewQueueResult.value
            : data.reviewQueue,
        exports: exportsResult.status === "fulfilled" ? exportsResult.value : data.exports,
        analytics:
          analyticsResult.status === "fulfilled" ? analyticsResult.value : data.analytics,
        datasetCoverage:
          datasetCoverageResult.status === "fulfilled"
            ? datasetCoverageResult.value
            : data.datasetCoverage,
        datasetQuality:
          datasetQualityResult.status === "fulfilled"
            ? datasetQualityResult.value
            : data.datasetQuality,
        modelReadiness:
          modelReadinessResult.status === "fulfilled"
            ? modelReadinessResult.value
            : data.modelReadiness,
      });
      setSelectedStreamId((current) => current ?? streamsResult.value[0]?.id ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load MockingBird data.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  // Only fetches once a session is confirmed -- otherwise a signed-out
  // load would fire a burst of calls that all 401 (harmless server-side,
  // but noisy and would briefly show a misleading "camera data could not
  // be loaded" error instead of the sign-in screen).
  useEffect(() => {
    if (authStatus === "authenticated") {
      void loadAppData();
    }
  }, [authStatus]);

  useEffect(() => {
    void apiClient
      .getSetupState()
      .then(setSetupState)
      .catch(() => setSetupState({ completed: true, current_step: "done", updated_at: new Date().toISOString() }));
  }, []);

  function checkSession() {
    return apiClient
      .getCurrentUser()
      .then((user) => {
        setCurrentUser(user);
        setAuthStatus("authenticated");
      })
      .catch(() => {
        setCurrentUser(null);
        setAuthStatus("unauthenticated");
      });
  }

  useEffect(() => {
    void checkSession();
    // A session can end between page loads for reasons this tab did
    // nothing wrong to cause: it expired, an Administrator disabled the
    // account, or the password changed elsewhere. `onSessionExpired` fires
    // once, centrally, on any 401 from any API call -- see client.ts.
    return onSessionExpired(() => {
      setCurrentUser(null);
      setAuthStatus("unauthenticated");
    });
  }, []);

  function handleSignedIn(user: CurrentUser) {
    setCurrentUser(user);
    setAuthStatus("authenticated");
  }

  function handleSignOut() {
    void apiClient.signOut().finally(() => {
      setCurrentUser(null);
      setAuthStatus("unauthenticated");
      // Drop any data fetched under the previous session out of memory
      // rather than leaving it visible for the instant before the sign-in
      // screen renders, and so a different user signing in next doesn't
      // briefly see a stale screen from someone else's session.
      setData(initialData);
    });
  }

  function handleOnboardingFinished() {
    setSetupState((current) => (current ? { ...current, completed: true } : current));
    void loadAppData({ showLoading: false });
  }

  useEffect(() => {
    if (initialRoute.recoveredFromUnknownPath) {
      writeAppRoute({ page: "dashboard" }, true);
    }
    function handleBrowserNavigation() {
      applyRoute(readAppRoute());
      setReviewQueueInitialContext(null);
      setVisitCorrectionPrefill(null);
    }
    window.addEventListener("popstate", handleBrowserNavigation);
    return () => window.removeEventListener("popstate", handleBrowserNavigation);
  }, []);

  // Close the mobile drawer on every navigation (including browser
  // back/forward, since `page` changes there too) -- a reviewer stepping
  // from the drawer into Review should land on the page, not the drawer
  // still open over it.
  useEffect(() => {
    setIsMobileNavOpen(false);
  }, [page]);

  // Escape closes the drawer and returns focus to the control that opened
  // it, matching the disclosure-pattern behavior a phone/keyboard user
  // expects from any off-canvas panel.
  useEffect(() => {
    if (!isMobileNavOpen) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsMobileNavOpen(false);
        mobileNavToggleRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMobileNavOpen]);

  const isAdvancedPageActive = advancedPages.has(page);

  useEffect(() => {
    if (isAdvancedPageActive) {
      setIsAdvancedNavOpen(true);
    }
  }, [isAdvancedPageActive]);

  const selectedStream = useMemo(
    () => data.streams.find((stream) => stream.id === selectedStreamId) ?? data.streams[0],
    [data.streams, selectedStreamId],
  );

  function openStream(streamId: string) {
    navigate({ page: "stream-detail", streamId });
  }

  function openCameraConfiguration(streamId: string) {
    navigate({ page: "camera-configuration", streamId });
  }

  function openEvent(eventId: string) {
    navigate({ page: "event-detail", eventId });
  }

  function openVisit(visitId: string, prefill?: Omit<VisitCorrectionPrefill, "visitId">) {
    setVisitCorrectionPrefill(prefill ? { visitId, ...prefill } : null);
    navigate({ page: "visit-detail", visitId });
  }

  function openMotionEvidence(motionEvidenceId: string) {
    navigate({ page: "motion-evidence-detail", motionEvidenceId });
  }

  function openReviewQueue(context?: ReviewQueueInitialContext | null) {
    setReviewQueueInitialContext(context ?? null);
    setPage("review");
  }

  function openActivityLibrary(filters: ActivityLibraryFilters) {
    const path = activityLibraryPath(filters);
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState({}, "", path);
    }
    applyRoute({ page: "activity-library" });
  }

  function openCollections(collectionId?: string) {
    navigate(collectionId ? { page: "collection-detail", collectionId } : { page: "collections" });
  }

  // Shared by YardMapPage's identical inline callback and
  // PlaceActivityReportPage's per-taxon "View in Bird Log" links: with no
  // label, opens Bird Log's overview; with one, deep-links straight to
  // that species' own history.
  function openBirdLogLabel(label?: string) {
    if (!label) {
      setPage("bird-log");
      return;
    }
    const path = `/bird-log/${encodeURIComponent(label)}`;
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState({}, "", path);
    }
    applyRoute({ page: "bird-log" });
  }

  // Place Story Deep Dives & Representative Evidence v1: a bookmarkable,
  // reload-safe deep dive on one taxon/Feature -- see navigation.ts.
  function openTaxonStory(label: string) {
    navigate({ page: "taxon-story", taxonLabel: label });
  }

  function openFeatureStory(featureId: string) {
    navigate({ page: "feature-story", featureId });
  }

  function openAlertAction(action: ProductAlertAction) {
    if (action.action_type === "review_visit" && action.visit_id) {
      openVisit(action.visit_id);
      return;
    }
    if (action.action_type === "open_stream" && action.stream_id) {
      openStream(action.stream_id);
      return;
    }
    if (action.action_type === "open_storage_retention") {
      // Saved Media Retention is superseded by Local Data's own Storage &
      // Retention section (see that page's on-page copy) -- no anchor-
      // scroll convention exists in this codebase, so this opens Local
      // Data as a whole rather than inventing one for this alone.
      setPage("settings");
      return;
    }
    if (action.action_type === "open_wildlife_journal") {
      const path = action.label ? `/bird-log/${encodeURIComponent(action.label)}` : "/bird-log";
      window.history.pushState({}, "", path);
      applyRoute({ page: "bird-log" });
      return;
    }
    if (action.action_type === "open_place_story") {
      // Place Story Deep Dives & Representative Evidence v1: the
      // underlying attention signal already carries a precise
      // `taxon_label`/`feature_id` when its own Story event has one (see
      // `ProductRepository.sync_attention_signals`) -- land directly on
      // that taxon's/Feature's own Story instead of the coarser
      // category-group timeline whenever it does.
      if (action.taxon_label) {
        openTaxonStory(action.taxon_label);
        return;
      }
      if (action.feature_id) {
        openFeatureStory(action.feature_id);
        return;
      }
      // Calm Attention & Notifications v1, Phase 25: no precise taxon/
      // Feature on this action -- land already scoped to the right
      // category group instead of an unfiltered timeline.
      setPlaceStoryInitialCategory(placeStoryCategoryForKind(action.story_kind));
      window.history.pushState({}, "", "/place-story");
      applyRoute({ page: "place-story" });
      return;
    }
    if (action.action_type === "open_place_report") {
      window.history.pushState({}, "", "/place-report");
      applyRoute({ page: "place-activity-report" });
    }
  }

  function openFocusedFastReview(visitIds: string[]) {
    const boundedVisitIds = visitIds.slice(0, 50);
    if (boundedVisitIds.length === 0) {
      return;
    }
    openReviewQueue({
      source: "activity-library",
      status: "unreviewed",
      visitIds: boundedVisitIds,
      openFastReview: true,
    });
  }

  function openReviewQueueForClassifierLabel(label: string) {
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      openReviewQueue();
      return;
    }
    openReviewQueue({
      source: "classifier-readiness",
      sourceLabel: trimmedLabel,
      search: trimmedLabel,
      correctionLabel: trimmedLabel,
      status: "unreviewed",
    });
  }

  function useSpeciesSuggestionAsCorrection(suggestion: SpeciesSuggestion) {
    if (!suggestion.visit_id) {
      return;
    }
    openVisit(suggestion.visit_id, {
      label: suggestion.suggested_label,
      speciesSuggestionId: suggestion.id,
      suggestedCommonName: suggestion.suggested_common_name,
      suggestedScientificName: suggestion.suggested_scientific_name,
    });
  }

  async function createCorrection(
    item: ReviewQueueItem,
    label: string,
    notes: string,
  ): Promise<ReviewCorrectionResult> {
    // Corrections are dataset-grade user labels that refresh queue and analytics state.
    const result = await apiClient.createReviewLabel({
      target_type: item.visit_id ? "visit" : "event",
      target_id: item.visit_id ?? item.event_id ?? item.id,
      label,
      notes: notes || undefined,
    });
    await loadAppData({ showLoading: false });
    return result;
  }

  async function refreshAfterLocalReset() {
    setSelectedEventId(null);
    setSelectedVisitId(null);
    setSelectedMotionEvidenceId(null);
    setVisitCorrectionPrefill(null);
    await loadAppData({ showLoading: false });
  }

  async function refreshAfterVisitCorrection() {
    setVisitCorrectionPrefill(null);
    await loadAppData({ showLoading: false });
  }

  function renderPage() {
    if (page === "users" && currentUser) {
      return <UsersPage currentUser={currentUser} />;
    }

    if (isLoading && page !== "dashboard") {
      return <div className="panel">Loading MockingBird...</div>;
    }

    if (error && page !== "dashboard") {
      return (
        <div className="error-panel">
          <strong>Could not reach the MockingBird API.</strong>
          <span>{error}</span>
          <span>API base: {apiClient.baseUrl}</span>
          <button className="secondary-action" onClick={() => void loadAppData()}>
            Retry
          </button>
        </div>
      );
    }

    if (page === "dashboard") {
      return (
        <DashboardPage
          health={data.health}
          onOpenStream={openStream}
          onOpenStreams={() => setPage("streams")}
          onOpenCameraConfiguration={openCameraConfiguration}
          onAddCamera={() => setPage("camera-setup")}
          onOpenReview={openReviewQueue}
          onOpenBirdLog={() => setPage("bird-log")}
          onOpenInsights={() => setPage("analytics")}
          onOpenVisit={openVisit}
          onOpenPlaceActivityReport={() => setPage("place-activity-report")}
          onOpenPlaceStory={() => setPage("place-story")}
          onOpenFeatureStory={openFeatureStory}
          onOpenTaxonStory={openTaxonStory}
          onOpenAlertsInbox={() => setPage("alerts-inbox")}
        />
      );
    }

    if (page === "streams") {
      return (
        <StreamsPage
          streams={data.streams}
          sources={data.sources}
          reviewQueue={data.reviewQueue}
          datasetExports={data.exports}
          onOpenImport={() => setPage("import")}
          onOpenStream={openStream}
          onOpenCameraConfiguration={openCameraConfiguration}
          onOpenMotionEvidence={openMotionEvidence}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenReview={() => openReviewQueue()}
          onOpenReviewForStream={(streamId) =>
            openReviewQueue({ source: "live-motion", search: streamId, status: "unreviewed" })
          }
          onOpenBirdLog={() => setPage("bird-log")}
          onOpenExports={() => setPage("exports")}
          onAddCamera={() => setPage("camera-setup")}
          onSourcesChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "yard-map") {
      return (
        <YardMapPage
          onOpenStream={openStream}
          onOpenVisit={openVisit}
          onOpenFastReview={openFocusedFastReview}
          onOpenActivityLibrary={openActivityLibrary}
          onOpenBirdLog={(label) => {
            const path = `/bird-log/${encodeURIComponent(label)}`;
            if (`${window.location.pathname}${window.location.search}` !== path) {
              window.history.pushState({}, "", path);
            }
            applyRoute({ page: "bird-log" });
          }}
        />
      );
    }

    if (page === "camera-setup") {
      return (
        <CameraSetupPage
          onCancel={() => setPage("streams")}
          onComplete={(streamId) => openStream(streamId)}
          onSourcesChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "camera-configuration" && selectedStreamId) {
      return (
        <CameraConfigurationPage
          streamId={selectedStreamId}
          onCancel={() => openStream(selectedStreamId)}
          onSaved={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "import") {
      return (
        <ManualImportPage
          streams={data.streams}
          sources={data.sources}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenStream={openStream}
          onOpenStreams={() => setPage("streams")}
          onOpenFolderImport={() => setPage("folder-import")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenReview={() => openReviewQueue()}
          onImportComplete={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "folder-import") {
      return (
        <FolderImportPage
          streams={data.streams}
          sources={data.sources}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenStream={openStream}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onImportComplete={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "detection-proposals") {
      return (
        <DetectionProposalsPage
          streams={data.streams}
          sources={data.sources}
          onOpenImport={() => setPage("import")}
          onOpenModelAdapters={() => setPage("model-adapters")}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
          onProposalChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "model-adapters") {
      return (
        <ModelAdaptersPage
          onOpenImport={() => setPage("import")}
          onOpenStreams={() => setPage("streams")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => openReviewQueue()}
          onOpenBirdLog={() => setPage("bird-log")}
          onOpenExports={() => setPage("exports")}
          onProposalChanged={() => loadAppData({ showLoading: false })}
          modelReadiness={data.modelReadiness}
        />
      );
    }

    if (page === "motion-evidence") {
      return (
        <MotionEvidencePage
          streams={data.streams}
          sources={data.sources}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenMotionEvidence={openMotionEvidence}
          onOpenReview={() => openReviewQueue()}
          onEvidenceChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "motion-evidence-detail" && selectedMotionEvidenceId) {
      return (
        <MotionEvidenceDetailPage
          motionEvidenceId={selectedMotionEvidenceId}
          sources={data.sources}
          streams={data.streams}
          onOpenMotionEvidence={() => setPage("motion-evidence")}
          onOpenReview={() => openReviewQueue()}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "species-suggestions") {
      return (
        <SpeciesSuggestionsPage
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenReview={() => openReviewQueue()}
          onUseAsCorrection={useSpeciesSuggestionAsCorrection}
        />
      );
    }

    if (page === "classifier-readiness") {
      return (
        <ClassifierReadinessPage
          onOpenAnalytics={() => setPage("analytics")}
          onOpenExports={() => setPage("exports")}
          onOpenEvent={openEvent}
          onOpenReview={() => openReviewQueue()}
          onOpenReviewForLabel={openReviewQueueForClassifierLabel}
          onOpenVisit={openVisit}
          onOpenSpeciesSuggestions={() => setPage("species-suggestions")}
          onOpenClassifierManifest={() => setPage("classifier-manifest")}
        />
      );
    }

    if (page === "classifier-manifest") {
      return (
        <ClassifierManifestPage
          onOpenClassifierReadiness={() => setPage("classifier-readiness")}
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => openReviewQueue()}
        />
      );
    }

    if (page === "ecological-destinations") {
      return <EcologicalDestinationsPage onOpenVisit={openVisit} />;
    }

    if (page === "stream-detail" && selectedStream) {
      return (
        <StreamDetailPage
          streamId={selectedStream.id}
          reviewQueue={data.reviewQueue}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenActivity={() => setPage("activity-library")}
          onOpenInsights={() => setPage("analytics")}
          onOpenImport={() => setPage("import")}
          onOpenExports={() => setPage("exports")}
          onOpenReview={openReviewQueue}
          onOpenMotionEvidence={openMotionEvidence}
          onOpenCameraSetup={() => openCameraConfiguration(selectedStream.id)}
          onReviewActivityCreated={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "event-detail" && selectedEventId) {
      return (
        <EventDetailPage
          eventId={selectedEventId}
          onOpenStream={openStream}
          onOpenVisit={openVisit}
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => openReviewQueue()}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenMotionEvidence={openMotionEvidence}
        />
      );
    }

    if (page === "visit-detail" && selectedVisitId) {
      return (
        <VisitDetailPage
          visitId={selectedVisitId}
          onOpenStream={openStream}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenExports={() => setPage("exports")}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenMotionEvidence={openMotionEvidence}
          onCorrectionSaved={refreshAfterVisitCorrection}
          correctionPrefill={visitCorrectionPrefill}
          onOpenCollections={() => openCollections()}
          onOpenActivityLibrary={openActivityLibrary}
          onOpenEcologicalDestinations={() => setPage("ecological-destinations")}
        />
      );
    }

    if (page === "activity-library") {
      return (
        <ActivityLibraryPage
          sources={data.sources}
          streams={data.streams}
          onOpenVisit={openVisit}
          onOpenFocusedFastReview={openFocusedFastReview}
          onOpenExports={() => setPage("exports")}
          onOpenCollections={() => openCollections()}
        />
      );
    }

    if (page === "review") {
      return (
        <ReviewQueuePage
          items={data.reviewQueue}
          initialContext={reviewQueueInitialContext}
          onCreateCorrection={createCorrection}
          onFastReviewChanged={() => loadAppData({ showLoading: false })}
          onInitialContextConsumed={() => setReviewQueueInitialContext(null)}
          onOpenEvent={openEvent}
          onOpenAnalytics={() => setPage("analytics")}
          onOpenClassifierReadiness={() => setPage("classifier-readiness")}
          onOpenExports={() => setPage("exports")}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "bird-log") {
      return (
        <BirdLogPage
          sources={data.sources}
          streams={data.streams}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenStreams={() => setPage("streams")}
          onOpenImport={() => setPage("import")}
          onOpenReview={() => openReviewQueue()}
          onOpenExports={() => setPage("exports")}
          onOpenCollections={() => openCollections()}
          onOpenPlaceActivityReport={() => setPage("place-activity-report")}
          onOpenTaxonStory={openTaxonStory}
        />
      );
    }

    if (page === "place-activity-report") {
      return (
        <PlaceActivityReportPage
          sources={data.sources}
          onOpenBirdLog={openBirdLogLabel}
          onOpenFeatureStory={openFeatureStory}
          onOpenTaxonStory={openTaxonStory}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "taxon-story" && selectedTaxonLabel) {
      return (
        <TaxonStoryPage
          onOpenBirdLog={openBirdLogLabel}
          onOpenFeatureStory={openFeatureStory}
          onOpenPlaceActivityReport={() => setPage("place-activity-report")}
          onOpenVisit={openVisit}
          taxonLabel={selectedTaxonLabel}
        />
      );
    }

    if (page === "feature-story" && selectedFeatureStoryId) {
      return (
        <FeatureStoryPage
          featureId={selectedFeatureStoryId}
          onOpenBirdLog={openBirdLogLabel}
          onOpenPlaceActivityReport={() => setPage("place-activity-report")}
          onOpenTaxonStory={openTaxonStory}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "place-story") {
      return (
        <PlaceStoryPage
          initialCategory={placeStoryInitialCategory}
          onOpenBirdLog={openBirdLogLabel}
          onOpenFeatureStory={openFeatureStory}
          onOpenPlaceActivityReport={() => setPage("place-activity-report")}
          onOpenTaxonStory={openTaxonStory}
          onOpenVisit={openVisit}
        />
      );
    }

    if (page === "collections" || (page === "collection-detail" && selectedCollectionId)) {
      return (
        <CollectionsPage
          collectionId={page === "collection-detail" ? selectedCollectionId : null}
          sources={data.sources}
          streams={data.streams}
          onOpenActivityLibrary={() => setPage("activity-library")}
          onOpenCollection={openCollections}
          onOpenVisit={openVisit}
          onOpenFocusedFastReview={openFocusedFastReview}
        />
      );
    }

    if (page === "analytics") {
      return (
        <AnalyticsPage
          analytics={data.analytics}
          sources={data.sources}
          streams={data.streams}
          datasetCoverage={data.datasetCoverage}
          datasetQuality={data.datasetQuality}
          onOpenExports={() => setPage("exports")}
          onOpenReview={() => openReviewQueue()}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onOpenStream={(streamId) => {
            const targetStreamId = streamId ?? selectedStream?.id;
            if (targetStreamId) openStream(targetStreamId);
          }}
          onOpenActivityLibrary={openActivityLibrary}
          onOpenBirdLog={() => setPage("bird-log")}
        />
      );
    }

    if (page === "exports") {
      return (
        <ExportsPage
          exports={data.exports}
          datasetCoverage={data.datasetCoverage}
          datasetQuality={data.datasetQuality}
          onOpenReview={() => openReviewQueue()}
          onOpenEvent={openEvent}
          onOpenVisit={openVisit}
          onOpenDetectionProposals={() => setPage("detection-proposals")}
          onExportsChanged={() => loadAppData({ showLoading: false })}
        />
      );
    }

    if (page === "saved-media-retention") {
      return <SavedMediaRetentionPage />;
    }

    if (page === "alerts-inbox") {
      return <AlertsInboxPage onAction={openAlertAction} />;
    }

    if (page === "worker-status") {
      return <WorkerStatusPage />;
    }

    return (
      <LocalDataPage
        onOpenDashboard={() => setPage("dashboard")}
        onOpenImport={() => setPage("import")}
        onOpenStreams={() => setPage("streams")}
        onOpenReview={() => openReviewQueue()}
        onOpenExports={() => setPage("exports")}
        onOpenDetectionProposals={() => setPage("detection-proposals")}
        onResetComplete={refreshAfterLocalReset}
      />
      );
  }

  // Local Identity, Multi-User & Organization Access v1: previously gated
  // to the dashboard route only (a real user's browser always opened
  // there first, and every deep link kept working unaffected during a
  // fresh install -- see docs/local-product-packaging-design.md). Now
  // global instead: onboarding's own "account" step is how the very first
  // Administrator gets created, so every route is equally meaningless
  // until that exists, not just the dashboard.
  if (setupState !== null && !setupState.completed) {
    return <OnboardingWizard onAccountCreated={handleSignedIn} onFinished={handleOnboardingFinished} />;
  }

  // Deliberately renders nothing (not even a loading shell) while auth
  // status is still unknown -- fail closed, not "assume signed in."
  if (setupState === null || authStatus === "loading") {
    return null;
  }

  if (authStatus === "unauthenticated" || !currentUser) {
    return <SignInPage onSignedIn={handleSignedIn} />;
  }

  const visibleProductNavItems = productNavItems.filter(
    (item) => !item.minRole || roleAtLeast(currentUser.role, item.minRole),
  );

  // Bottom-nav destinations for phone widths (below the 760px mobile nav
  // breakpoint, see styles.css): the 4 most common daily-loop destinations
  // this milestone's own mobile archaeology named (Today, Story, Cameras,
  // Review-or-Bird-Log depending on role), plus a "More" button that opens
  // the same full drawer as the top bar's hamburger -- deliberately small
  // (Phase 3: "do not put twelve destinations into a bottom bar"), never a
  // second, separate navigation model from `productNavItems` above.
  const mobileNavItems: Array<{ page: Page; label: string }> = [
    { page: "dashboard", label: "Today" },
    { page: "place-story", label: "Story" },
    { page: "streams", label: "Cameras" },
    roleAtLeast(currentUser.role, "reviewer")
      ? { page: "review", label: "Review" }
      : { page: "bird-log", label: "Bird Log" },
  ];

  return (
    <>
      <header className="mobile-topbar">
        <button
          aria-controls="primary-navigation"
          aria-expanded={isMobileNavOpen}
          aria-label={isMobileNavOpen ? "Close navigation" : "Open navigation"}
          className="mobile-nav-toggle"
          onClick={() => setIsMobileNavOpen((current) => !current)}
          ref={mobileNavToggleRef}
          type="button"
        >
          <span aria-hidden="true" className="mobile-nav-toggle-icon" />
        </button>
        <div className="brand-block">
          <span className="brand-mark">MB</span>
          <strong>MockingBird</strong>
        </div>
        <AlertsControl onAction={openAlertAction} onOpenInbox={() => setPage("alerts-inbox")} />
      </header>
      {isMobileNavOpen ? (
        <div
          aria-hidden="true"
          className="sidebar-backdrop"
          onClick={() => setIsMobileNavOpen(false)}
        />
      ) : null}
      <div className="app-shell">
        <aside className={isMobileNavOpen ? "sidebar sidebar-open" : "sidebar"} id="primary-navigation">
          <div className="brand-block">
          <span className="brand-mark">MB</span>
          <div>
            <strong>MockingBird</strong>
            <span>Outdoor video intelligence</span>
          </div>
        </div>
        <AlertsControl onAction={openAlertAction} onOpenInbox={() => setPage("alerts-inbox")} />
        <nav className="nav-list" aria-label="Product navigation">
          <span className="nav-section-label">Product loop</span>
          {visibleProductNavItems.map((item) => (
            <button
              className={page === item.page ? "nav-item active" : "nav-item"}
              key={item.page}
              onClick={() => setPage(item.page)}
            >
              {item.label}
            </button>
          ))}
          <button
            aria-pressed={isDeveloperMode}
            className={`nav-item developer-mode-toggle${isDeveloperMode ? " active" : ""}`}
            onClick={() => setIsDeveloperMode((current) => !current)}
            type="button"
          >
            {isDeveloperMode ? "Hide Developer Mode" : "Developer Mode"}
          </button>
          {isDeveloperMode || isAdvancedPageActive ? (
            <details
              className="nav-group"
              open={isAdvancedNavOpen || isAdvancedPageActive}
              onToggle={(event) => setIsAdvancedNavOpen(event.currentTarget.open)}
            >
              <summary>Developer tools</summary>
              <div className="nav-group-items">
                {advancedNavItems.map((item) => (
                  <button
                    className={page === item.page ? "nav-item active" : "nav-item"}
                    key={item.page}
                    onClick={() => setPage(item.page)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </details>
          ) : null}
          {selectedStream || selectedEventId || selectedVisitId ? (
            <span className="nav-section-label">Current context</span>
          ) : null}
          {selectedStream ? (
            <button
              className={page === "stream-detail" ? "nav-item active" : "nav-item"}
              onClick={() => openStream(selectedStream.id)}
            >
              Stream Detail
            </button>
          ) : null}
          {selectedEventId ? (
            <button
              className={page === "event-detail" ? "nav-item active" : "nav-item"}
              onClick={() => openEvent(selectedEventId)}
            >
              Event Detail
            </button>
          ) : null}
          {selectedVisitId ? (
            <button
              className={page === "visit-detail" ? "nav-item active" : "nav-item"}
              onClick={() => openVisit(selectedVisitId)}
            >
              Visit Detail
            </button>
          ) : null}
        </nav>
        <div className="account-menu">
          <div className="account-menu-identity">
            <strong>{currentUser.display_name}</strong>
            <span>{currentUser.role}</span>
          </div>
          <button className="text-action" onClick={handleSignOut} type="button">
            Sign out
          </button>
        </div>
        <div className="sidebar-footer">
          <span>Local app</span>
          <strong>{apiClient.baseUrl || "This device"}</strong>
        </div>
      </aside>
      <main className="main-content">
        {loadWarnings.length > 0 ? (
          <div className="notice-panel app-load-warning" role="status">
            <strong>Some supporting information could not refresh.</strong>
            <span>{loadWarnings.join(" ")}</span>
            <button className="text-action" onClick={() => void loadAppData({ showLoading: false })}>
              Retry
            </button>
          </div>
        ) : null}
        {renderPage()}
      </main>
      </div>
      <nav aria-label="Primary" className="mobile-bottom-nav">
        {mobileNavItems.map((item) => (
          <button
            className={page === item.page ? "mobile-bottom-nav-item active" : "mobile-bottom-nav-item"}
            key={item.page}
            onClick={() => setPage(item.page)}
            type="button"
          >
            {item.label}
          </button>
        ))}
        <button
          aria-controls="primary-navigation"
          aria-expanded={isMobileNavOpen}
          className="mobile-bottom-nav-item"
          onClick={() => setIsMobileNavOpen((current) => !current)}
          type="button"
        >
          More
        </button>
      </nav>
    </>
  );
}
