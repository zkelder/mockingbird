export type Page =
  | "dashboard"
  | "streams"
  | "yard-map"
  | "camera-setup"
  | "camera-configuration"
  | "import"
  | "folder-import"
  | "model-adapters"
  | "detection-proposals"
  | "motion-evidence"
  | "motion-evidence-detail"
  | "species-suggestions"
  | "classifier-readiness"
  | "classifier-manifest"
  | "stream-detail"
  | "event-detail"
  | "visit-detail"
  | "activity-library"
  | "collections"
  | "collection-detail"
  | "review"
  | "bird-log"
  | "place-activity-report"
  | "place-story"
  | "taxon-story"
  | "feature-story"
  | "alerts-inbox"
  | "analytics"
  | "ecological-destinations"
  | "exports"
  | "saved-media-retention"
  | "worker-status"
  | "settings"
  | "users";

export interface AppRoute {
  page: Page;
  streamId?: string | null;
  eventId?: string | null;
  visitId?: string | null;
  motionEvidenceId?: string | null;
  collectionId?: string | null;
  // Place Story Deep Dives & Representative Evidence v1: the canonical
  // taxonomy label (never a display string) a Taxon Story page is showing.
  taxonLabel?: string | null;
  // Place Story Deep Dives & Representative Evidence v1: the Place Feature
  // id a Feature Story page is showing.
  featureId?: string | null;
  recoveredFromUnknownPath?: boolean;
}

const pagePaths: Partial<Record<Page, string>> = {
  dashboard: "/",
  streams: "/cameras",
  "yard-map": "/yard-map",
  "camera-setup": "/cameras/setup",
  import: "/import",
  "folder-import": "/folder-import",
  "model-adapters": "/analyzers",
  "detection-proposals": "/proposals",
  "motion-evidence": "/evidence",
  "species-suggestions": "/species-suggestions",
  "classifier-readiness": "/classifier-readiness",
  "classifier-manifest": "/classifier-manifest",
  "activity-library": "/activity",
  collections: "/collections",
  review: "/review",
  "bird-log": "/bird-log",
  "place-activity-report": "/place-report",
  "place-story": "/place-story",
  "alerts-inbox": "/alerts",
  analytics: "/analytics",
  "ecological-destinations": "/ecological-destinations",
  exports: "/exports",
  "saved-media-retention": "/retention",
  "worker-status": "/worker-status",
  settings: "/local-data",
  users: "/users",
};

const pathPages = new Map(
  Object.entries(pagePaths).map(([page, path]) => [path, page as Page]),
);

function decodeIdentifier(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

export function readAppRoute(pathname = window.location.pathname): AppRoute {
  const normalizedPath = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const knownPage = pathPages.get(normalizedPath);
  if (knownPage) {
    return { page: knownPage };
  }

  const segments = normalizedPath.split("/").filter(Boolean);
  const identifier = decodeIdentifier(segments[1]);
  if (segments.length === 2 && identifier) {
    if (segments[0] === "streams") {
      return { page: "stream-detail", streamId: identifier };
    }
    if (segments[0] === "events") {
      return { page: "event-detail", eventId: identifier };
    }
    if (segments[0] === "visits") {
      return { page: "visit-detail", visitId: identifier };
    }
    if (segments[0] === "evidence") {
      return { page: "motion-evidence-detail", motionEvidenceId: identifier };
    }
    if (segments[0] === "bird-log") {
      return { page: "bird-log" };
    }
    if (segments[0] === "collections") {
      return { page: "collection-detail", collectionId: identifier };
    }
  }

  if (segments.length === 3 && segments[0] === "cameras" && segments[2] === "edit") {
    const streamId = decodeIdentifier(segments[1]);
    if (streamId) {
      return { page: "camera-configuration", streamId };
    }
  }

  // Place Story Deep Dives & Representative Evidence v1: /place-story/
  // taxon/:label and /place-story/feature/:id -- bookmarkable, reload-safe
  // deep-dive routes. An unresolvable label/id is not a routing concern:
  // the page itself renders an honest not-found state (mirrors every other
  // detail page's `error-panel` convention), matching this router's own
  // "recover to dashboard only on a genuinely unrecognized path shape"
  // discipline.
  if (segments.length === 3 && segments[0] === "place-story") {
    const identifier = decodeIdentifier(segments[2]);
    if (identifier && segments[1] === "taxon") {
      return { page: "taxon-story", taxonLabel: identifier };
    }
    if (identifier && segments[1] === "feature") {
      return { page: "feature-story", featureId: identifier };
    }
  }

  return { page: "dashboard", recoveredFromUnknownPath: normalizedPath !== "/" };
}

export function pathForAppRoute(route: AppRoute): string {
  if (route.page === "stream-detail" && route.streamId) {
    return `/streams/${encodeURIComponent(route.streamId)}`;
  }
  if (route.page === "event-detail" && route.eventId) {
    return `/events/${encodeURIComponent(route.eventId)}`;
  }
  if (route.page === "visit-detail" && route.visitId) {
    return `/visits/${encodeURIComponent(route.visitId)}`;
  }
  if (route.page === "motion-evidence-detail" && route.motionEvidenceId) {
    return `/evidence/${encodeURIComponent(route.motionEvidenceId)}`;
  }
  if (route.page === "collection-detail" && route.collectionId) {
    return `/collections/${encodeURIComponent(route.collectionId)}`;
  }
  if (route.page === "camera-configuration" && route.streamId) {
    return `/cameras/${encodeURIComponent(route.streamId)}/edit`;
  }
  if (route.page === "taxon-story" && route.taxonLabel) {
    return `/place-story/taxon/${encodeURIComponent(route.taxonLabel)}`;
  }
  if (route.page === "feature-story" && route.featureId) {
    return `/place-story/feature/${encodeURIComponent(route.featureId)}`;
  }
  return pagePaths[route.page] ?? "/";
}

export function writeAppRoute(route: AppRoute, replace = false): void {
  const path = pathForAppRoute(route);
  if (replace) {
    window.history.replaceState({}, "", path);
  } else if (window.location.pathname !== path) {
    window.history.pushState({}, "", path);
  }
}
