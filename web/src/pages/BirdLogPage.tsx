import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  ClassifierSupportingEvidence,
  DashboardTodaySpecies,
  Stream,
  WildlifeJournalGalleryOrder,
  WildlifeJournalHistoryRequest,
  WildlifeJournalHistoryResponse,
  WildlifeJournalLabelSummary,
  WildlifeJournalObservation,
  WildlifeJournalOrder,
  WildlifeJournalRangePreset,
  WildlifeJournalRepresentative,
  WildlifeJournalOverviewResponse,
  VisitCollectionSummary,
  VisitTagSummary,
  Zone,
} from "../api/types";
import { activityLibraryPath } from "./ActivityLibraryPage";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import {
  changeStatusBadge,
  formatDateTime,
  historicalStatusBadge,
  modalityBadge,
  regularityNarrativeBadge,
  seasonalPatternNote,
} from "../utils";

interface BirdLogPageProps {
  sources: CameraSource[];
  streams: Stream[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenStreams: () => void;
  onOpenImport: () => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onOpenCollections: () => void;
  onOpenPlaceActivityReport: () => void;
  // Place Story Deep Dives & Representative Evidence v1.
  onOpenTaxonStory: (label: string) => void;
}

interface JournalLocation {
  order: WildlifeJournalOrder;
  preset: WildlifeJournalRangePreset;
  startDate: string;
  endDate: string;
  streamId: string;
  zoneId: string;
  favoritesOnly: boolean;
  tagId: string;
  galleryOrder: WildlifeJournalGalleryOrder;
  offset: number;
}

const overviewOrders: Array<{ value: WildlifeJournalOrder; label: string }> = [
  { value: "most_recent", label: "Most recently observed" },
  { value: "most_observed", label: "Most observed" },
  { value: "alphabetical", label: "Alphabetical" },
  { value: "first_observed", label: "First observed" },
];

const rangeOptions: Array<{ value: WildlifeJournalRangePreset; label: string }> = [
  { value: "all_time", label: "All time" },
  { value: "today", label: "Today" },
  { value: "last_7_days", label: "Last 7 days" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "this_year", label: "This year" },
  { value: "custom", label: "Custom range" },
];

function localDateInputValue(value = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function validOption<T extends string>(value: string | null, options: readonly T[], fallback: T): T {
  return value && options.includes(value as T) ? (value as T) : fallback;
}

function readJournalLocation(): JournalLocation {
  const params = new URLSearchParams(window.location.search);
  const parsedOffset = Number.parseInt(params.get("offset") ?? "0", 10);
  return {
    order: validOption(
      params.get("order"),
      overviewOrders.map((option) => option.value),
      "most_recent",
    ),
    preset: validOption(
      params.get("range"),
      rangeOptions.map((option) => option.value),
      "all_time",
    ),
    startDate: params.get("from") ?? "",
    endDate: params.get("to") ?? "",
    streamId: params.get("stream") ?? "",
    zoneId: params.get("zone") ?? "",
    favoritesOnly: params.get("favorites") === "1",
    tagId: params.get("tag") ?? "",
    galleryOrder: validOption(params.get("gallery"), ["newest", "oldest"], "newest"),
    offset: Number.isFinite(parsedOffset) && parsedOffset >= 0 ? parsedOffset : 0,
  };
}

function readJournalLabel(pathname = window.location.pathname): string | null {
  const normalizedPath = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const segments = normalizedPath.split("/").filter(Boolean);
  if (segments.length !== 2 || segments[0] !== "bird-log") return null;
  try {
    return decodeURIComponent(segments[1]).trim() || null;
  } catch {
    return null;
  }
}

function journalPath(label: string | null, location: JournalLocation): string {
  const params = new URLSearchParams();
  if (!label) {
    if (location.order !== "most_recent") params.set("order", location.order);
    return `/bird-log${params.size ? `?${params.toString()}` : ""}`;
  }
  if (location.preset !== "all_time") params.set("range", location.preset);
  if (location.startDate) params.set("from", location.startDate);
  if (location.endDate) params.set("to", location.endDate);
  if (location.streamId) params.set("stream", location.streamId);
  if (location.zoneId) params.set("zone", location.zoneId);
  if (location.favoritesOnly) params.set("favorites", "1");
  if (location.tagId) params.set("tag", location.tagId);
  if (location.galleryOrder !== "newest") params.set("gallery", location.galleryOrder);
  if (location.offset > 0) params.set("offset", String(location.offset));
  const path = `/bird-log/${encodeURIComponent(label)}`;
  return `${path}${params.size ? `?${params.toString()}` : ""}`;
}

function writeJournalUrl(label: string | null, location: JournalLocation, replace = false): void {
  const path = journalPath(label, location);
  if (replace) {
    window.history.replaceState({}, "", path);
  } else if (`${window.location.pathname}${window.location.search}` !== path) {
    window.history.pushState({}, "", path);
  }
}

function navigatePath(path: string): void {
  if (`${window.location.pathname}${window.location.search}` !== path) {
    window.history.pushState({}, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function historyRequest(location: JournalLocation): WildlifeJournalHistoryRequest {
  return {
    preset: location.preset,
    start_date: location.startDate || null,
    end_date: location.endDate || null,
    stream_id: location.streamId || null,
    zone_id: location.zoneId || null,
    favorites_only: location.favoritesOnly,
    tag_id: location.tagId || null,
    gallery_order: location.galleryOrder,
    page_size: 24,
    offset: location.offset,
  };
}

function durationLabel(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds % 60)} sec`;
}

function hourLabel(hour: number): string {
  const suffix = hour < 12 ? "AM" : "PM";
  return `${hour % 12 || 12} ${suffix}`;
}

function thumbnailAlt(label: string, observedAt: string): string {
  return `${label}, reviewed observation ${formatDateTime(observedAt)}`;
}

function JournalThumbnail({
  label,
  observedAt,
  representative,
}: {
  label: string;
  observedAt: string;
  representative?: WildlifeJournalRepresentative | WildlifeJournalObservation | null;
}) {
  const [failed, setFailed] = useState(false);
  const evidence = representative?.primary_evidence;
  useEffect(() => setFailed(false), [evidence?.media_asset_id]);
  if (!evidence || failed) {
    return <div className="journal-thumbnail-fallback">No saved thumbnail</div>;
  }
  // Acoustic / BirdNET Observation Foundation v1: an honest "heard, not
  // seen" state, never the same copy a genuinely missing image uses.
  if (evidence.content_type.startsWith("audio/")) {
    return (
      <div className="journal-thumbnail-fallback journal-thumbnail-audio" aria-label={`${label}, heard ${formatDateTime(observedAt)}`}>
        🔊 Heard
      </div>
    );
  }
  return (
    <img
      alt={thumbnailAlt(label, observedAt)}
      loading="lazy"
      onError={() => setFailed(true)}
      src={`${apiClient.baseUrl}${evidence.preview_url}`}
    />
  );
}

type LikelySightingEvidenceSource = "identification" | "visit_preview" | "unavailable";

interface LikelySightingEvidenceState {
  source: LikelySightingEvidenceSource;
  imageUrl: string | null;
  onImageError: () => void;
}

/**
 * Likely Sightings Evidence Fidelity & ID Honesty v1.
 *
 * `GET /api/bird-log/likely` (`ProductRepository.list_likely_species_
 * overview` -> `_stream_visit_summary_from_models`) only ever returns a
 * Visit's generic, persisted `is_primary` evidence frame -- never the
 * frame the species classifier actually read. Those are frequently
 * different images: Same-Frame Species Evidence v1 (docs/same-frame-
 * species-evidence-contract.md) can feed BioCLIP a same-frame/persisted-
 * crop asset that never becomes the Visit's primary evidence at all.
 * Showing the generic frame under a specific species name without saying
 * so implies evidence that may not exist.
 *
 * This resolves the real classified image by reusing the exact,
 * already-shipped `VisitDetail.classifier_supporting_evidence` contract
 * (docs/visit-classifier-evidence-visibility-contract.md) that Visit
 * Detail's own "Species suggestion evidence" panel already renders --
 * the same source-of-truth read (the suggestion's own recorded
 * `evidence_region.classifier_input`), already existence/Stream-
 * ownership/gallery-dedup checked server side. Deliberately not a second,
 * frontend-reimplemented reading of the raw suggestion JSON: that would
 * both duplicate that server-side logic and skip its safety checks.
 *
 * One extra `GET /api/visits/{id}/detail` per visible card is the
 * accepted cost of reusing that real contract instead of guessing; see
 * the milestone report for why a lighter, list-scoped backend field would
 * be a better long-term contract than N per-card detail fetches.
 *
 * Never claims more than is proven: while resolution is in flight, and
 * whenever it comes back empty (most Visits today -- the same-frame/
 * persisted-crop resolver often does not fire), the card falls back to
 * the Visit's generic preview honestly labeled "Visit preview" rather
 * than silently upgrading it to look like identification evidence.
 */
function useLikelySightingEvidence(species: DashboardTodaySpecies): LikelySightingEvidenceState {
  const visitId = species.latest_visit.id;
  const primary = species.latest_visit.primary_evidence ?? null;
  const [supporting, setSupporting] = useState<ClassifierSupportingEvidence | null | undefined>(undefined);
  const [identificationFailed, setIdentificationFailed] = useState(false);
  const [previewFailed, setPreviewFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setSupporting(undefined);
    setIdentificationFailed(false);
    setPreviewFailed(false);
    void apiClient
      .getVisitDetail(visitId)
      .then((detail) => {
        if (active) setSupporting(detail.classifier_supporting_evidence ?? null);
      })
      .catch(() => {
        // Best-effort only, same posture as this page's other provisional
        // reads: a failed lookup falls back to the honest Visit preview
        // below rather than blocking or misrepresenting the card.
        if (active) setSupporting(null);
      });
    return () => {
      active = false;
    };
  }, [visitId]);

  if (supporting && !identificationFailed) {
    return {
      imageUrl: `${apiClient.baseUrl}${supporting.frame.preview_url}`,
      onImageError: () => setIdentificationFailed(true),
      source: "identification",
    };
  }
  if (primary && !previewFailed) {
    return {
      imageUrl: `${apiClient.baseUrl}${primary.preview_url}`,
      onImageError: () => setPreviewFailed(true),
      source: "visit_preview",
    };
  }
  return { imageUrl: null, onImageError: () => {}, source: "unavailable" };
}

function LikelySightingCard({
  onOpenVisit,
  species,
}: {
  onOpenVisit: (visitId: string) => void;
  species: DashboardTodaySpecies;
}) {
  const evidence = useLikelySightingEvidence(species);
  const alt =
    evidence.source === "identification"
      ? `Evidence for provisional ${species.display_name} suggestion`
      : `Visit preview, not confirmed as the evidence for the provisional ${species.display_name} suggestion`;
  return (
    <article className="journal-label-card">
      <button className="journal-label-image" onClick={() => onOpenVisit(species.latest_visit.id)} type="button">
        {evidence.imageUrl ? (
          <img alt={alt} loading="lazy" onError={evidence.onImageError} src={evidence.imageUrl} />
        ) : (
          <div className="journal-thumbnail-fallback">No saved thumbnail</div>
        )}
      </button>
      <div className="journal-label-card-body">
        <div className="section-heading">
          <div><h2>Likely {species.display_name}</h2><span className="meta-text">Not yet confirmed</span></div>
        </div>
        {evidence.source === "unavailable" ? null : (
          <EvidenceBadge
            label={evidence.source === "identification" ? "Identification evidence" : "Visit preview"}
            tone={evidence.source === "identification" ? "evidence" : "quiet"}
          />
        )}
        <button className="secondary-action" onClick={() => onOpenVisit(species.latest_visit.id)} type="button">Confirm or correct</button>
      </div>
    </article>
  );
}

function Sparkline({ activity }: { activity: WildlifeJournalLabelSummary["recent_activity"] }) {
  const maximum = Math.max(...activity.map((day) => day.count), 1);
  return (
    <div aria-label="Recent reviewed observations" className="journal-sparkline">
      {activity.map((day) => (
        <span
          key={day.local_date}
          style={{ height: `${Math.max(4, Math.round((day.count / maximum) * 30))}px` }}
          title={`${day.local_date}: ${day.count} reviewed observations`}
        />
      ))}
    </div>
  );
}

function BreakdownList({
  items,
  title,
}: {
  items: WildlifeJournalHistoryResponse["stream_breakdown"];
  title: string;
}) {
  if (items.length === 0) return <span className="meta-text">No current {title.toLowerCase()} in this scope.</span>;
  return (
    <div className="journal-breakdown" aria-label={title}>
      {items.map((item) => (
        <div key={item.id}>
          <span>{item.name}</span>
          <strong>{item.count}</strong>
        </div>
      ))}
    </div>
  );
}

export function BirdLogPage({
  streams,
  onOpenVisit,
  onOpenStreams,
  onOpenReview,
  onOpenCollections,
  onOpenPlaceActivityReport,
  onOpenTaxonStory,
}: BirdLogPageProps) {
  const [journalLabel, setJournalLabel] = useState<string | null>(readJournalLabel);
  const [location, setLocation] = useState<JournalLocation>(readJournalLocation);
  const [customStartDate, setCustomStartDate] = useState(location.startDate || localDateInputValue());
  const [customEndDate, setCustomEndDate] = useState(location.endDate || localDateInputValue());
  const [zones, setZones] = useState<Zone[]>([]);
  const [overview, setOverview] = useState<WildlifeJournalOverviewResponse | null>(null);
  const [history, setHistory] = useState<WildlifeJournalHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collections, setCollections] = useState<VisitCollectionSummary[]>([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [collectionMessage, setCollectionMessage] = useState<string | null>(null);
  const [tags, setTags] = useState<VisitTagSummary[]>([]);
  const [selectedTagId, setSelectedTagId] = useState("");
  const [tagMessage, setTagMessage] = useState<string | null>(null);
  const [likelySpecies, setLikelySpecies] = useState<DashboardTodaySpecies[]>([]);

  useEffect(() => {
    let active = true;
    void apiClient
      .getLikelySpeciesOverview()
      .then((next) => {
        if (active) setLikelySpecies(next.species);
      })
      .catch(() => {
        // Best-effort only: Bird Log's confirmed history remains fully
        // usable without provisional suggestions.
        if (active) setLikelySpecies([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    void apiClient
      .getZones()
      .then((next) => {
        if (active) setZones(next);
      })
      .catch(() => {
        if (active) setZones([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => { void apiClient.getVisitCollections().then(setCollections).catch(() => setCollections([])); }, []);
  useEffect(() => { void apiClient.getVisitTags().then(setTags).catch(() => setTags([])); }, []);

  async function addObservationToCollection(visitId: string) {
    const collection = collections.find((item) => item.id === selectedCollectionId);
    if (!collection) { setCollectionMessage("Choose a Collection before adding this Visit."); return; }
    try {
      const response = await apiClient.addVisitToCollection(collection.id, visitId, {
        expected_state_token: collection.state_token,
        idempotency_key: `journal-collection-${crypto.randomUUID()}`,
      });
      setCollectionMessage(response.result.status === "updated" ? `Added Visit to ${collection.name}.` : `This Visit is already in ${collection.name}.`);
      setCollections((current) => current.map((item) => item.id === response.collection.id ? response.collection : item));
    } catch (caught) { setCollectionMessage(caught instanceof Error ? caught.message : "Could not add this Visit to the Collection."); }
  }

  async function addObservationTag(visitId: string) {
    const tag = tags.find((item) => item.id === selectedTagId);
    if (!tag) { setTagMessage("Choose a tag before adding it to this Visit."); return; }
    try {
      const response = await apiClient.addVisitTag(tag.id, visitId, {
        expected_state_token: tag.state_token,
        idempotency_key: `journal-tag-${crypto.randomUUID()}`,
      });
      setTagMessage(response.result.status === "updated" ? `Added ${tag.name}.` : `This Visit already has ${tag.name}.`);
      setTags((current) => current.map((item) => item.id === response.tag.id ? response.tag : item));
      setHistory((current) => current ? {
        ...current,
        gallery: {
          ...current.gallery,
          observations: current.gallery.observations.map((item) => item.visit_id === visitId && response.result.status === "updated"
            ? { ...item, tags: [...item.tags, response.tag.name].sort((left, right) => left.localeCompare(right)) }
            : item),
        },
      } : current);
    } catch (caught) { setTagMessage(caught instanceof Error ? caught.message : "Could not add this tag to the Visit."); }
  }

  useEffect(() => {
    function handlePopState() {
      const next = readJournalLocation();
      const nextLabel = readJournalLabel();
      setJournalLabel(nextLabel);
      setLocation(next);
      setCustomStartDate(next.startDate || localDateInputValue());
      setCustomEndDate(next.endDate || localDateInputValue());
      setError(null);
      if (nextLabel) {
        setHistory(null);
      } else {
        setOverview(null);
      }
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    if (!journalLabel) {
      void apiClient
        .getWildlifeJournal(location.order, location.streamId || undefined)
        .then((next) => {
          if (active) setOverview(next);
        })
        .catch(() => {
          if (active) setError("Could not load Bird Log. Your reviewed activity remains in the Activity Library.");
        })
        .finally(() => {
          if (active) setIsLoading(false);
        });
    } else {
      void apiClient
        .getWildlifeJournalHistory(journalLabel, historyRequest(location))
        .then((next) => {
          if (active) setHistory(next);
        })
        .catch((caught) => {
          if (active) setError(caught instanceof Error ? caught.message : "Could not load this Bird Log history.");
        })
        .finally(() => {
          if (active) setIsLoading(false);
        });
    }
    return () => {
      active = false;
    };
  }, [journalLabel, location]);

  const visibleZones = useMemo(
    () => zones.filter((zone) => !location.streamId || zone.stream_id === location.streamId),
    [location.streamId, zones],
  );

  const commitLocation = (next: JournalLocation) => {
    setLocation(next);
    writeJournalUrl(journalLabel, next);
  };

  const navigateJournalLabel = (nextLabel: string | null) => {
    writeJournalUrl(nextLabel, location);
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  const openActivityLibrary = () => {
    if (!history) return;
    const drilldown = history.activity_library_drilldown;
    navigatePath(activityLibraryPath({
      review_filter: drilldown.review_filter,
      confirmed_label: drilldown.confirmed_label,
      start_at: drilldown.start_date ?? null,
      end_at: drilldown.end_date ?? null,
      stream_id: drilldown.stream_id ?? null,
      zone_id: drilldown.zone_id ?? null,
      favorites_only: location.favoritesOnly,
    }));
  };

  const loadMore = async () => {
    if (!journalLabel || !history?.gallery.next_offset || isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const next = await apiClient.getWildlifeJournalHistory(journalLabel, {
        ...historyRequest(location),
        offset: history.gallery.next_offset,
      });
      setHistory((current) => {
        if (!current) return next;
        const existing = new Set(current.gallery.observations.map((item) => item.visit_id));
        return {
          ...next,
          gallery: {
            ...next.gallery,
            observations: [
              ...current.gallery.observations,
              ...next.gallery.observations.filter((item) => !existing.has(item.visit_id)),
            ],
          },
        };
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load more reviewed observations.");
    } finally {
      setIsLoadingMore(false);
    }
  };

  if (!journalLabel) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Reviewed wildlife history"
          title="Bird Log"
          description="Confirmed wildlife from current reviewed corrections. Suggestions and unresolved activity stay in review context."
          actions={
            <>
              <button className="secondary-action" onClick={() => navigatePath("/analytics")} type="button">Insights</button>
              <button className="secondary-action" onClick={onOpenReview} type="button">Review Queue</button>
              <button className="secondary-action" onClick={onOpenCollections} type="button">Collections</button>
              <button className="secondary-action" onClick={onOpenPlaceActivityReport} type="button">Full Place Report</button>
            </>
          }
        />
        <section className="panel journal-controls">
          <label>
            Order labels by
            <select
              onChange={(event) => commitLocation({ ...location, order: event.target.value as WildlifeJournalOrder })}
              value={location.order}
            >
              {overviewOrders.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        </section>
        {likelySpecies.length > 0 ? (
          <section className="panel journal-likely-panel" aria-label="Likely sightings awaiting confirmation">
            <div className="section-heading">
              <div>
                <h2>Likely sightings</h2>
                <span className="meta-text">
                  Automatic AI species suggestions, not yet confirmed. Open a Visit to confirm or correct it.
                </span>
              </div>
              <StatusPill label="AI suggestion" tone="quiet" />
            </div>
            <section className="journal-label-grid" aria-label="Likely species awaiting confirmation">
              {likelySpecies.map((species) => (
                <LikelySightingCard key={species.label} onOpenVisit={onOpenVisit} species={species} />
              ))}
            </section>
          </section>
        ) : null}
        {error ? <div className="error-panel">{error}</div> : null}
        {isLoading && !overview ? <div className="panel">Loading Bird Log…</div> : null}
        {overview?.labels.length === 0 && !isLoading ? (
          <EmptyState
            title={streams.length === 0 ? "No cameras connected yet" : "No confirmed wildlife observations yet"}
            description={streams.length === 0 ? "Add a camera or local media Source, then review outdoor activity." : "Review a Visit to create a confirmed local wildlife observation. Suggestions are not Bird Log entries."}
            action={<button className="secondary-action" onClick={streams.length === 0 ? onOpenStreams : onOpenReview} type="button">{streams.length === 0 ? "Add Camera" : "Open Review Queue"}</button>}
          />
        ) : null}
        {overview?.labels.length ? (
          <section className="journal-label-grid" aria-label="Confirmed wildlife labels">
            {overview.labels.map((item) => (
              <article className="journal-label-card" key={item.label}>
                <button className="journal-label-image" onClick={() => navigateJournalLabel(item.label)} type="button">
                  <JournalThumbnail label={item.display_name} observedAt={item.latest_observed_at} representative={item.representative} />
                </button>
                <div className="journal-label-card-body">
                  <div className="section-heading">
                    <div>
                      <h2>{item.display_name}</h2>
                      <span className="meta-text">{item.observation_count} reviewed observation{item.observation_count === 1 ? "" : "s"}</span>
                      {(() => {
                        // Everyday Discovery / Product Experience v2 (Phase
                        // E/H): the canonical New/Regular badge, now visible
                        // at grid level for the first time -- previously
                        // only `is_regular` (never "new") rendered here. See
                        // docs/canonical-new-regular-species-contract.md.
                        // Falls back to the older `is_regular`-only signal
                        // when `historical_status` is the backend's own
                        // documented defensive-fallback `null` (a label
                        // outside the canonical call's Stream scope) --
                        // never silently drops an honest "Regular here".
                        const badge =
                          historicalStatusBadge(item.historical_status) ??
                          (item.is_regular ? { label: "Regular here", tone: "good" as const } : null);
                        return badge ? <StatusPill label={badge.label} tone={badge.tone} /> : null;
                      })()}
                      {(() => {
                        const badge = changeStatusBadge(item.change_status);
                        return badge ? <StatusPill label={badge.label} tone={badge.tone} /> : null;
                      })()}
                    </div>
                    <Sparkline activity={item.recent_activity} />
                  </div>
                  <div className="journal-label-facts">
                    <span>First: <strong>{formatDateTime(item.first_observed_at)}</strong></span>
                    <span>Latest: <strong>{formatDateTime(item.latest_observed_at)}</strong></span>
                    <span>{item.stream_count} Stream{item.stream_count === 1 ? "" : "s"} · {item.zone_count} Zone{item.zone_count === 1 ? "" : "s"}</span>
                  </div>
                  <button className="secondary-action" onClick={() => navigateJournalLabel(item.label)} type="button">Open history</button>
                </div>
              </article>
            ))}
          </section>
        ) : null}
      </div>
    );
  }

  const activeHistory = history;
  // Everyday Product / Discovery UX Closure v1: a multi-subject Visit
  // Assembly Event (schema 36) can have two simultaneous individuals of the
  // same species -- with nothing marking them as concurrent, a same-species
  // pair on this page read as a plausible duplicate/glitch rather than two
  // real individuals. Detected within the currently-loaded gallery page
  // only (no extra request): count each event_id's occurrences among the
  // observations already fetched.
  const galleryEventIdCounts = new Map<string, number>();
  for (const observation of activeHistory?.gallery.observations ?? []) {
    galleryEventIdCounts.set(
      observation.event_id,
      (galleryEventIdCounts.get(observation.event_id) ?? 0) + 1,
    );
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Reviewed wildlife history"
        title={activeHistory ? activeHistory.display_name : "Bird Log"}
        description="One bounded history of current reviewed observations. Open a Visit for full evidence and correction audit context."
        actions={
          <>
            <button className="secondary-action" onClick={() => navigateJournalLabel(null)} type="button">All Bird Log species</button>
            <button className="secondary-action" onClick={openActivityLibrary} type="button">Open Activity Library</button>
            <button className="secondary-action" onClick={onOpenCollections} type="button">Collections</button>
          </>
        }
      />
      <section className="panel journal-filter-panel">
        <label>
          Date range
          <select
            onChange={(event) => {
              const preset = event.target.value as WildlifeJournalRangePreset;
              commitLocation({
                ...location,
                preset,
                startDate: preset === "custom" ? customStartDate : "",
                endDate: preset === "custom" ? customEndDate : "",
                offset: 0,
              });
            }}
            value={location.preset}
          >
            {rangeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        {location.preset === "custom" ? (
          <>
            <label>From <input max={customEndDate} onChange={(event) => setCustomStartDate(event.target.value)} type="date" value={customStartDate} /></label>
            <label>To <input min={customStartDate} onChange={(event) => setCustomEndDate(event.target.value)} type="date" value={customEndDate} /></label>
            <button
              className="primary-action"
              disabled={!customStartDate || !customEndDate || customEndDate < customStartDate}
              onClick={() => commitLocation({ ...location, startDate: customStartDate, endDate: customEndDate, offset: 0 })}
              type="button"
            >Apply</button>
          </>
        ) : null}
        <label>
          Stream
          <select onChange={(event) => commitLocation({ ...location, streamId: event.target.value, zoneId: "", offset: 0 })} value={location.streamId}>
            <option value="">All Streams</option>
            {streams.map((stream) => <option key={stream.id} value={stream.id}>{stream.name}</option>)}
          </select>
        </label>
        <label>
          Zone
          <select onChange={(event) => commitLocation({ ...location, zoneId: event.target.value, offset: 0 })} value={location.zoneId}>
            <option value="">All Zones</option>
            {visibleZones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
          </select>
        </label>
        <label>
          Gallery order
          <select onChange={(event) => commitLocation({ ...location, galleryOrder: event.target.value as WildlifeJournalGalleryOrder, offset: 0 })} value={location.galleryOrder}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </label>
        <label>
          Favorites
          <select onChange={(event) => commitLocation({ ...location, favoritesOnly: event.target.value === "yes", offset: 0 })} value={location.favoritesOnly ? "yes" : "all"}>
            <option value="all">All reviewed Visits</option>
            <option value="yes">Favorites only</option>
          </select>
        </label>
        <label>
          Gallery tag
          <select onChange={(event) => commitLocation({ ...location, tagId: event.target.value, offset: 0 })} value={location.tagId}>
            <option value="">All tags</option>
            {tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
          </select>
        </label>
        <label>
          Add to Collection
          <select value={selectedCollectionId} onChange={(event) => setSelectedCollectionId(event.target.value)}>
            <option value="">Choose Collection</option>
            {collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
          </select>
        </label>
      </section>
      {error ? <div className="error-panel">{error}</div> : null}
      {collectionMessage ? <div className="notice-panel" role="status">{collectionMessage}</div> : null}
      {tagMessage ? <div className="notice-panel" role="status">{tagMessage}</div> : null}
      {isLoading && !activeHistory ? <div className="panel">Loading reviewed Bird Log history…</div> : null}
      {activeHistory ? (
        <>
          <div className="journal-scope-note">{activeHistory.scope.start_date ?? "All recorded dates"}{activeHistory.scope.end_date ? ` to ${activeHistory.scope.end_date}` : ""}{activeHistory.scope.favorites_only ? " · favorites only" : ""}{activeHistory.scope.tag_id ? " · gallery tag filter" : ""} · local time ({activeHistory.scope.timezone_name})</div>
          <div className="today-report-footer">
            <button className="text-action" onClick={() => onOpenTaxonStory(activeHistory.label)} type="button">
              See {activeHistory.display_name}&rsquo;s story
            </button>
          </div>
          {activeHistory.observation_count === 0 ? (
            <EmptyState
              title="No active confirmed observations in this scope"
              description="This label may have been revised, reopened, superseded, or filtered out. Review history remains available on individual Visits."
              action={<button className="secondary-action" onClick={() => commitLocation({ ...location, preset: "all_time", startDate: "", endDate: "", streamId: "", zoneId: "", favoritesOnly: false, tagId: "", offset: 0 })} type="button">Clear Bird Log filters</button>}
            />
          ) : (
            <>
              {(() => {
                // Everyday Discovery / Product Experience v2 (Phase E/H):
                // the canonical, always-on New/Regular badge -- unlike
                // `is_new_label_in_range` below, this is never hidden just
                // because the viewer is on the default "all_time" scope.
                // Replaces this page's own former hand-rolled maturity-
                // gated wording ternary; both Today and Bird Log now word
                // this identically because both read the same shared
                // `historicalStatusBadge` helper over the same backend
                // field. See docs/canonical-new-regular-species-contract.md.
                const badge =
                  historicalStatusBadge(activeHistory.historical_status) ??
                  (activeHistory.is_regular ? { label: "Regular here", tone: "good" as const } : null);
                if (!badge) return null;
                const regularityBadge = regularityNarrativeBadge(activeHistory.regularity_narrative);
                return (
                  <div className="section-heading">
                    <span className="meta-text">
                      Confirmed on {activeHistory.distinct_confirmed_usable_days} well-monitored days in this Place's recent history
                    </span>
                    <StatusPill label={badge.label} tone={badge.tone} />
                    {regularityBadge ? <StatusPill label={regularityBadge.label} tone={regularityBadge.tone} /> : null}
                  </div>
                );
              })()}
              {seasonalPatternNote(activeHistory.seasonal_pattern) ? (
                <p className="meta-text">{seasonalPatternNote(activeHistory.seasonal_pattern)}</p>
              ) : null}
              {activeHistory.change_status ? (
                <div className="section-heading">
                  <span className="meta-text">
                    Recent: {activeHistory.change_status.recent_presence_days} of {activeHistory.change_status.recent_usable_day_count} usable monitored days
                    {" · "}
                    Reference: {activeHistory.change_status.reference_presence_days} of {activeHistory.change_status.reference_usable_day_count} usable monitored days
                  </span>
                  {(() => {
                    const badge = changeStatusBadge(activeHistory.change_status);
                    return badge ? <StatusPill label={badge.label} tone={badge.tone} /> : null;
                  })()}
                </div>
              ) : null}
              <section className="metric-grid journal-metrics">
                <MetricCard label="Observations" value={activeHistory.observation_count} detail="current reviewed truth" />
                <MetricCard label="Busiest Stream" value={activeHistory.busiest_stream?.name ?? "—"} detail={activeHistory.busiest_stream ? `${activeHistory.busiest_stream.count} observations` : "No activity"} />
                <MetricCard label="Busiest Zone" value={activeHistory.busiest_zone?.name ?? "—"} detail={activeHistory.busiest_zone ? `${activeHistory.busiest_zone.count} observations` : "No Zone context"} />
                <MetricCard label="Peak hour" value={activeHistory.peak_activity_hour == null ? "—" : hourLabel(activeHistory.peak_activity_hour)} detail="local time" />
              </section>
              {activeHistory.is_new_label_in_range ? (
                <div className="notice-panel">
                  <strong>
                    {activeHistory.baseline_maturity === "established"
                      ? "New to your reviewed history in this range"
                      : "First confirmed record so far in this range"}
                  </strong>
                  <span>
                    {activeHistory.baseline_maturity === "established"
                      ? "This is a local MockingBird record milestone, not an ecological claim."
                      : "MockingBird hasn't accumulated enough monitored history yet to call this ecologically new -- just the first time it's been confirmed here."}
                  </span>
                </div>
              ) : null}
              <section className="journal-history-grid">
                <div className="panel"><h2>First recorded</h2>{activeHistory.first_observation ? <button className="journal-observation-link" onClick={() => onOpenVisit(activeHistory.first_observation!.visit_id)} type="button">{formatDateTime(activeHistory.first_observation.observed_at)} · {activeHistory.first_observation.stream_name}</button> : null}</div>
                <div className="panel"><h2>Most recent</h2>{activeHistory.latest_observation ? <button className="journal-observation-link" onClick={() => onOpenVisit(activeHistory.latest_observation!.visit_id)} type="button">{formatDateTime(activeHistory.latest_observation.observed_at)} · {activeHistory.latest_observation.stream_name}</button> : null}</div>
              </section>
              {activeHistory.place_context ? (
                // Biodiversity & Place Intelligence v1: context tied to the
                // single most recent reviewed observation only -- never a
                // per-Visit or statistical summary, and never phrased as a
                // cause. See docs/biodiversity-place-intelligence-v1-contract.md.
                <section className="journal-history-grid">
                  <div className="panel">
                    <h2>Habitat &amp; environment</h2>
                    <span className="meta-text">
                      Recorded alongside the most recent sighting, {formatDateTime(activeHistory.place_context.observed_at)} — association only, never a cause.
                    </span>
                    {activeHistory.place_context.environmental_context.available ? (
                      <p className="meta-text">
                        {activeHistory.place_context.environmental_context.daylight_state === "day"
                          ? "Recorded during daylight"
                          : "Recorded at night"}
                      </p>
                    ) : null}
                    {activeHistory.place_context.phenology_context.length > 0 ? (
                      <ul className="habitat-phenology-list">
                        {activeHistory.place_context.phenology_context.map((observation) => (
                          <li key={observation.id}>
                            <strong>{observation.subject_label}</strong> &middot; {observation.phenomenon}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {/* Place / Yard Intelligence v2, Phase 11: distinct from
                        the single-most-recent-sighting snapshot above -- a
                        pattern across this taxon's whole reviewed history.
                        Association language only, never a cause. */}
                    {(activeHistory.habitat_associations ?? [])
                      .filter((association) => association.status !== "no_clear_association")
                      .map((association) => (
                        <p className="meta-text" key={`${association.subject_label}-${association.phenomenon}`}>
                          {association.status === "more_common_under_condition" ? "Observed more often" : "Observed less often"}
                          {" while "}
                          {association.phenomenon} was current ({association.subject_label})
                        </p>
                      ))}
                    {/* Environmental Context v2: identical association-
                        language-only, all-matches-listed convention as
                        habitat_associations above -- see docs/
                        environmental-context-v2-contract.md "Phase 6/16". */}
                    {(activeHistory.weather_associations ?? [])
                      .filter((association) => association.status !== "no_clear_association")
                      .map((association) => (
                        <p className="meta-text" key={association.condition}>
                          {association.status === "more_common_under_condition" ? "Observed more often" : "Observed less often"}
                          {" during "}
                          {association.condition_label}
                        </p>
                      ))}
                  </div>
                </section>
              ) : null}
              <section className="journal-history-grid">
                <div className="panel"><h2>Stream activity</h2><BreakdownList items={activeHistory.stream_breakdown} title="Streams" /></div>
                <div className="panel"><h2>Zone activity</h2><BreakdownList items={activeHistory.zone_breakdown} title="Zones" /></div>
              </section>
              <section className="panel">
                <div className="section-heading"><div><h2>Activity by hour</h2><span className="meta-text">Confirmed wildlife only, local time.</span></div></div>
                <div className="journal-hour-grid" aria-label="Confirmed observations by local hour">{activeHistory.activity_by_hour.map((bucket) => <span key={bucket.hour}>{hourLabel(bucket.hour)} <strong>{bucket.count}</strong></span>)}</div>
              </section>
              <section className="journal-gallery" aria-label="Reviewed observation gallery">
                <div className="section-heading"><div><h2>Reviewed observation gallery</h2><span className="meta-text">{activeHistory.gallery.order === "newest" ? "Newest first" : "Oldest first"} · one safe primary preview per Visit.</span></div></div>
                {activeHistory.gallery.observations.length === 0 ? <EmptyState title="No observations match this tag" description="The reviewed-label counts and milestones above remain unchanged by tag filtering." /> : null}
                {activeHistory.gallery.observations.map((observation) => (
                  <article className="journal-gallery-card" key={observation.visit_id}>
                    <button className="journal-gallery-image" onClick={() => onOpenVisit(observation.visit_id)} type="button"><JournalThumbnail label={observation.display_name} observedAt={observation.observed_at} representative={observation} /></button>
                    <div className="journal-gallery-body">
                      <div className="section-heading"><div><h3>{formatDateTime(observation.observed_at)}</h3><span className="meta-text">{observation.source_name} · {observation.stream_name}{observation.zone_name ? ` · ${observation.zone_name}` : ""}</span></div><div className="journal-gallery-status-pills">{(galleryEventIdCounts.get(observation.event_id) ?? 0) > 1 ? <StatusPill label="Shared encounter" tone="quiet" /> : null}{(() => {
                        // Everyday Discovery / Product Experience v2 (Phase
                        // B): a confidently-associated visual+acoustic pair
                        // already collapsed into this one card server-side
                        // -- see docs/multimodal-list-presentation-contract.md.
                        const badge = modalityBadge(observation.evidence_modality);
                        return badge ? <StatusPill label={badge.label} tone="quiet" /> : null;
                      })()}<StatusPill label="Confirmed" tone="good" /></div></div>
                      <div className="journal-gallery-facts"><span>Duration <strong>{durationLabel(observation.duration_seconds)}</strong></span><span>{observation.primary_evidence?.content_type.startsWith("audio/") ? "Evidence clip" : "Evidence frames"} <strong>{observation.evidence_frame_count}</strong></span></div>
                      <div className="journal-gallery-milestones">{observation.is_favorite ? <StatusPill label="Favorite" tone="good" /> : null}{observation.has_note ? <StatusPill label="Note" tone="quiet" /> : null}{observation.collection_count > 0 ? <StatusPill label={`${observation.collection_count} Collection${observation.collection_count === 1 ? "" : "s"}`} tone="quiet" /> : null}{observation.tags.map((tag) => <StatusPill key={tag} label={tag} tone="quiet" />)}{observation.has_curation_history ? <StatusPill label="Curated" tone="quiet" /> : null}{observation.has_review_revision ? <StatusPill label="Revised" tone="quiet" /> : null}{observation.is_first_on_stream ? <StatusPill label="First on Stream" tone="quiet" /> : null}{observation.is_first_in_zone ? <StatusPill label="First in Zone" tone="quiet" /> : null}</div>
                      <button className="secondary-action" onClick={() => onOpenVisit(observation.visit_id)} type="button">Open Visit Detail</button>
                      <button className="text-action" disabled={!selectedCollectionId} onClick={() => void addObservationToCollection(observation.visit_id)} type="button">Add to Collection</button>
                      <button className="text-action" disabled={!selectedTagId} onClick={() => void addObservationTag(observation.visit_id)} type="button">Add tag</button>
                    </div>
                  </article>
                ))}
                {activeHistory.gallery.has_more ? <button className="secondary-action" disabled={isLoadingMore} onClick={() => void loadMore()} type="button">{isLoadingMore ? "Loading…" : "Load more observations"}</button> : null}
              </section>
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
