import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ActivityLibraryFilters,
  ActivityLibraryReviewFilter,
  ActivityLibrarySavedView,
  ActivityLibraryVisitSummary,
  CameraSource,
  Stream,
  VisitCollectionSummary,
  VisitTagSummary,
  Zone,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

const MAX_SELECTION = 50;

const defaultFilters: ActivityLibraryFilters = {
  review_filter: "all",
};

const reviewFilterOptions: Array<{ value: ActivityLibraryReviewFilter; label: string }> = [
  { value: "all", label: "All activity" },
  { value: "needs_review", label: "Needs review" },
  { value: "reviewed_observation", label: "Reviewed observations" },
  { value: "confirmed_wildlife", label: "Confirmed wildlife" },
  { value: "non_bird", label: "Non-bird activity" },
  { value: "blank_false", label: "Blank / false activity" },
  { value: "blank", label: "Blank activity" },
  { value: "ambiguous_unknown", label: "Ambiguous / unknown" },
];

interface ActivityLibraryPageProps {
  sources: CameraSource[];
  streams: Stream[];
  onOpenVisit: (visitId: string) => void;
  onOpenFocusedFastReview: (visitIds: string[]) => void;
  onOpenExports: () => void;
  onOpenCollections: () => void;
}

function dateInputValue(value?: string | null): string {
  return value ? value.slice(0, 10) : "";
}

function normalizedFilters(filters: ActivityLibraryFilters): ActivityLibraryFilters {
  return {
    ...defaultFilters,
    ...filters,
    stream_id: filters.stream_id || null,
    source_id: filters.source_id || null,
    zone_id: filters.zone_id || null,
    confirmed_label: filters.confirmed_label?.trim() || null,
    favorites_only: Boolean(filters.favorites_only),
    has_note: filters.has_note ?? null,
    collection_id: filters.collection_id || null,
    tag_id: filters.tag_id || null,
    search: filters.search?.trim() || null,
    start_at: dateInputValue(filters.start_at),
    end_at: dateInputValue(filters.end_at),
  };
}

function filtersFromUrl(): { filters: ActivityLibraryFilters; offset: number } {
  const params = new URLSearchParams(window.location.search);
  const review = params.get("review") as ActivityLibraryReviewFilter | null;
  const validReview = reviewFilterOptions.some((option) => option.value === review);
  const parsedOffset = Number.parseInt(params.get("offset") ?? "0", 10);
  return {
    filters: normalizedFilters({
      review_filter: validReview && review ? review : "all",
      stream_id: params.get("stream"),
      source_id: params.get("source"),
      zone_id: params.get("zone"),
      confirmed_label: params.get("label"),
      has_suggestion:
        params.get("suggestion") === "1"
          ? true
          : params.get("suggestion") === "0"
            ? false
            : null,
      favorites_only: params.get("favorites") === "1",
      has_note:
        params.get("note") === "1" ? true : params.get("note") === "0" ? false : null,
      collection_id: params.get("collection"),
      tag_id: params.get("tag"),
      search: params.get("q"),
      start_at: params.get("from"),
      end_at: params.get("to"),
    }),
    offset: Number.isFinite(parsedOffset) && parsedOffset >= 0 ? parsedOffset : 0,
  };
}

export function activityLibraryPath(filters: ActivityLibraryFilters, offset = 0): string {
  const params = new URLSearchParams();
  if (filters.review_filter && filters.review_filter !== "all") {
    params.set("review", filters.review_filter);
  }
  if (filters.stream_id) params.set("stream", filters.stream_id);
  if (filters.source_id) params.set("source", filters.source_id);
  if (filters.zone_id) params.set("zone", filters.zone_id);
  if (filters.confirmed_label) params.set("label", filters.confirmed_label);
  if (filters.has_suggestion === true) params.set("suggestion", "1");
  if (filters.has_suggestion === false) params.set("suggestion", "0");
  if (filters.favorites_only) params.set("favorites", "1");
  if (filters.has_note === true) params.set("note", "1");
  if (filters.has_note === false) params.set("note", "0");
  if (filters.collection_id) params.set("collection", filters.collection_id);
  if (filters.tag_id) params.set("tag", filters.tag_id);
  if (filters.search) params.set("q", filters.search);
  if (filters.start_at) params.set("from", dateInputValue(filters.start_at));
  if (filters.end_at) params.set("to", dateInputValue(filters.end_at));
  if (offset > 0) params.set("offset", String(offset));
  return `/activity${params.size ? `?${params.toString()}` : ""}`;
}

function writeLibraryUrl(filters: ActivityLibraryFilters, offset: number, replace = false): void {
  const path = activityLibraryPath(filters, offset);
  if (replace) {
    window.history.replaceState({}, "", path);
  } else if (`${window.location.pathname}${window.location.search}` !== path) {
    window.history.pushState({}, "", path);
  }
}

function apiDateBounds(filters: ActivityLibraryFilters): ActivityLibraryFilters {
  const localStart = (value: string) => {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day, 0, 0, 0, 0).toISOString();
  };
  const localEnd = (value: string) => {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day, 23, 59, 59, 999).toISOString();
  };
  return {
    ...filters,
    start_at: filters.start_at ? localStart(dateInputValue(filters.start_at)) : null,
    end_at: filters.end_at ? localEnd(dateInputValue(filters.end_at)) : null,
  };
}

function durationLabel(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds % 60)} sec`;
}

function outcomeTone(outcome: ActivityLibraryVisitSummary["review_outcome"]): "good" | "review" | "quiet" {
  if (outcome === "confirmed_bird" || outcome === "reviewed_other") return "good";
  if (outcome === "needs_review") return "review";
  return "quiet";
}

export function ActivityLibraryPage({
  sources,
  streams,
  onOpenVisit,
  onOpenFocusedFastReview,
  onOpenExports,
  onOpenCollections,
}: ActivityLibraryPageProps) {
  const initial = useMemo(filtersFromUrl, []);
  const [filters, setFilters] = useState<ActivityLibraryFilters>(initial.filters);
  const [offset, setOffset] = useState(initial.offset);
  const [visits, setVisits] = useState<ActivityLibraryVisitSummary[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [savedViews, setSavedViews] = useState<ActivityLibrarySavedView[]>([]);
  const [saveName, setSaveName] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [isUpdatingOrganization, setIsUpdatingOrganization] = useState(false);
  const [thumbnailFailures, setThumbnailFailures] = useState<Set<string>>(new Set());
  const [collections, setCollections] = useState<VisitCollectionSummary[]>([]);
  const [bulkCollectionId, setBulkCollectionId] = useState("");
  const [tags, setTags] = useState<VisitTagSummary[]>([]);
  const [manageableTags, setManageableTags] = useState<VisitTagSummary[]>([]);
  const [bulkTagId, setBulkTagId] = useState("");
  const [newTagName, setNewTagName] = useState("");
  const [tagManagementMessage, setTagManagementMessage] = useState<string | null>(null);

  const selectedVisits = useMemo(
    () => visits.filter((visit) => selectedIds.includes(visit.id)),
    [selectedIds, visits],
  );
  const selectedNeedsReviewIds = useMemo(
    () =>
      selectedVisits
        .filter((visit) => visit.review_outcome === "needs_review")
        .map((visit) => visit.id),
    [selectedVisits],
  );

  async function refreshSavedViews() {
    try {
      setSavedViews(await apiClient.getActivityLibrarySavedViews());
    } catch {
      // Activity search remains available when optional organizational metadata cannot load.
    }
  }

  async function refreshTags() {
    try {
      const [suggestions, manageable] = await Promise.all([
        apiClient.getVisitTags(),
        apiClient.getManageableVisitTags(),
      ]);
      setTags(suggestions);
      setManageableTags(manageable);
    } catch {
      setTags([]);
      setManageableTags([]);
    }
  }

  useEffect(() => {
    void refreshSavedViews();
    void apiClient.getVisitCollections().then(setCollections).catch(() => setCollections([]));
    void refreshTags();
    let active = true;
    void apiClient
      .getZones()
      .then((loadedZones) => {
        if (active) setZones(loadedZones);
      })
      .catch(() => {
        if (active) setZones([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    void apiClient
      .searchActivityLibrary({ ...apiDateBounds(filters), page_size: 24, offset })
      .then((result) => {
        if (!active) return;
        setVisits(result.visits);
        setHasMore(result.has_more);
      })
      .catch((caught) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : "Could not refresh activity.");
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters, offset, refreshVersion]);

  useEffect(() => {
    function handlePopState() {
      const next = filtersFromUrl();
      setFilters(next.filters);
      setOffset(next.offset);
      setSelectedIds([]);
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function commitFilters(next: ActivityLibraryFilters) {
    const normalized = normalizedFilters(next);
    setFilters(normalized);
    setOffset(0);
    setSelectedIds([]);
    setMessage(null);
    writeLibraryUrl(normalized, 0);
  }

  function goToOffset(nextOffset: number) {
    setOffset(Math.max(0, nextOffset));
    setSelectedIds([]);
    writeLibraryUrl(filters, Math.max(0, nextOffset));
  }

  function toggleSelected(visitId: string, selected: boolean) {
    setSelectedIds((current) => {
      if (!selected) return current.filter((id) => id !== visitId);
      if (current.includes(visitId)) return current;
      if (current.length >= MAX_SELECTION) {
        setMessage(`Select up to ${MAX_SELECTION} Visits at a time.`);
        return current;
      }
      return [...current, visitId];
    });
  }

  async function saveCurrentView() {
    const name = saveName.trim();
    if (!name) {
      setMessage("Name this view before saving it.");
      return;
    }
    try {
      await apiClient.createActivityLibrarySavedView({ name, filters });
      setSaveName("");
      setMessage(`Saved “${name}”.`);
      await refreshSavedViews();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not save this view.");
    }
  }

  async function renameSavedView(view: ActivityLibrarySavedView) {
    const name = window.prompt("Rename saved view", view.name)?.trim();
    if (!name || name === view.name) return;
    try {
      await apiClient.updateActivityLibrarySavedView(view.id, { name });
      await refreshSavedViews();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not rename this view.");
    }
  }

  async function deleteSavedView(view: ActivityLibrarySavedView) {
    if (!window.confirm(`Delete saved view “${view.name}”?`)) return;
    try {
      await apiClient.deleteActivityLibrarySavedView(view.id);
      await refreshSavedViews();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not delete this view.");
    }
  }

  async function exportSelected() {
    if (selectedIds.length === 0) return;
    try {
      const result = await apiClient.createActivityLibraryExportSelection({
        name: `Activity Library selection ${new Date().toLocaleDateString()}`,
        visit_ids: selectedIds,
      });
      const excluded = result.excluded.length;
      if (result.export) {
        setMessage(
          `Created reviewed export with ${result.included_visit_ids.length} Visit${
            result.included_visit_ids.length === 1 ? "" : "s"
          }${excluded ? `; ${excluded} unresolved or superseded Visit${excluded === 1 ? " was" : "s were"} excluded` : ""}.`,
        );
      } else {
        setMessage("No selected Visits had current reviewed truth to export.");
      }
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not create the reviewed export.");
    }
  }

  async function bulkSetFavorite(action: "favorite" | "unfavorite") {
    if (selectedIds.length === 0 || isUpdatingOrganization) return;
    setIsUpdatingOrganization(true);
    try {
      const result = await apiClient.bulkUpdateVisitOrganization({
        visit_ids: selectedIds,
        action,
        idempotency_key: `activity-organization-${crypto.randomUUID()}`,
      });
      const skipped = result.results.filter((item) => item.status === "skipped").length;
      const updated = result.results.length - skipped;
      setMessage(
        `${action === "favorite" ? "Favorited" : "Unfavorited"} ${updated} Visit${updated === 1 ? "" : "s"}${skipped ? `; ${skipped} superseded or unavailable Visit${skipped === 1 ? " was" : "s were"} skipped` : ""}.`,
      );
      setSelectedIds([]);
      setRefreshVersion((value) => value + 1);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not update the selected Visits.");
    } finally {
      setIsUpdatingOrganization(false);
    }
  }

  async function bulkUpdateCollection(action: "add" | "remove") {
    const collection = collections.find((item) => item.id === bulkCollectionId);
    if (!collection || selectedIds.length === 0) return;
    try {
      const result = await apiClient.bulkUpdateVisitCollectionMemberships({
        collection_id: collection.id,
        visit_ids: selectedIds,
        action,
        expected_state_token: collection.state_token,
        idempotency_key: `activity-collection-${crypto.randomUUID()}`,
      });
      const changed = result.results.filter((item) => item.status === "updated").length;
      const skipped = result.results.filter((item) => item.status.startsWith("skipped_")).length;
      const unchanged = result.results.length - changed - skipped;
      setMessage(`${action === "add" ? "Added" : "Removed"} ${changed} Visit${changed === 1 ? "" : "s"}${unchanged ? `; ${unchanged} already ${action === "add" ? "present" : "absent"}` : ""}${skipped ? `; ${skipped} unavailable or superseded Visit${skipped === 1 ? " was" : "s were"} skipped` : ""}.`);
      setCollections((current) => current.map((item) => item.id === result.collection.id ? result.collection : item));
      setSelectedIds([]);
      setRefreshVersion((value) => value + 1);
    } catch (caught) { setMessage(caught instanceof Error ? caught.message : "Could not update Collection membership."); }
  }

  async function bulkUpdateTag(action: "add" | "remove") {
    const tag = tags.find((item) => item.id === bulkTagId);
    if (!tag || selectedIds.length === 0) return;
    try {
      const result = await apiClient.bulkUpdateVisitTags({
        tag_id: tag.id,
        visit_ids: selectedIds,
        action,
        expected_state_token: tag.state_token,
        idempotency_key: `activity-tag-${crypto.randomUUID()}`,
      });
      const counts = result.results.reduce<Record<string, number>>((current, item) => {
        current[item.status] = (current[item.status] ?? 0) + 1;
        return current;
      }, {});
      const unchanged = action === "add" ? counts.already_present : counts.already_absent;
      const unavailable = (counts.skipped_unavailable ?? 0) + (counts.skipped_superseded ?? 0);
      const limit = counts.skipped_limit ?? 0;
      setMessage(
        `${action === "add" ? "Added" : "Removed"} ${counts.updated ?? 0} tag membership${counts.updated === 1 ? "" : "s"}`
        + `${unchanged ? `; ${unchanged} already ${action === "add" ? "present" : "absent"}` : ""}`
        + `${unavailable ? `; ${unavailable} unavailable or superseded` : ""}`
        + `${limit ? `; ${limit} skipped at the 20-tag Visit limit` : ""}.`,
      );
      setTags((current) => current.map((item) => item.id === result.tag.id ? result.tag : item));
      setManageableTags((current) => current.map((item) => item.id === result.tag.id ? result.tag : item));
      setSelectedIds([]);
      setRefreshVersion((value) => value + 1);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not update tags.");
    }
  }

  async function createTag() {
    if (!newTagName.trim()) { setTagManagementMessage("Name the new tag first."); return; }
    try {
      const created = await apiClient.createVisitTag({
        name: newTagName,
        idempotency_key: `activity-tag-create-${crypto.randomUUID()}`,
      });
      await refreshTags();
      setNewTagName("");
      setTagManagementMessage(`Created ${created.name}.`);
    } catch (caught) { setTagManagementMessage(caught instanceof Error ? caught.message : "Could not create this tag."); }
  }

  async function renameTag(tag: VisitTagSummary) {
    const name = window.prompt("Rename tag", tag.name)?.trim();
    if (!name || name === tag.name) return;
    try {
      const updated = await apiClient.updateVisitTag(tag.id, {
        name,
        expected_state_token: tag.state_token,
        idempotency_key: `activity-tag-rename-${crypto.randomUUID()}`,
      });
      await refreshTags();
      setTagManagementMessage(`Renamed tag to ${updated.name}.`);
      setRefreshVersion((value) => value + 1);
    } catch (caught) { setTagManagementMessage(caught instanceof Error ? caught.message : "Could not rename this tag."); }
  }

  async function archiveTag(tag: VisitTagSummary) {
    if (!window.confirm(`Archive tag “${tag.name}”? Existing Visit memberships remain historical.`)) return;
    try {
      await apiClient.archiveVisitTag(tag.id, {
        expected_state_token: tag.state_token,
        idempotency_key: `activity-tag-archive-${crypto.randomUUID()}`,
      });
      await refreshTags();
      setBulkTagId((current) => current === tag.id ? "" : current);
      if (filters.tag_id === tag.id) commitFilters({ ...filters, tag_id: null });
      setTagManagementMessage(`Archived ${tag.name}. Existing Visits, media, notes, favorites, and Collections are unchanged.`);
      setRefreshVersion((value) => value + 1);
    } catch (caught) { setTagManagementMessage(caught instanceof Error ? caught.message : "Could not archive this tag."); }
  }

  const selectedStreamMissing = Boolean(
    filters.stream_id && !streams.some((stream) => stream.id === filters.stream_id),
  );
  const selectedSourceMissing = Boolean(
    filters.source_id && !sources.some((source) => source.id === filters.source_id),
  );
  const selectedZoneMissing = Boolean(
    filters.zone_id && !zones.some((zone) => zone.id === filters.zone_id),
  );
  const isDefaultView =
    filters.review_filter === "all" &&
    !filters.stream_id &&
    !filters.source_id &&
    !filters.zone_id &&
    !filters.confirmed_label &&
    filters.has_suggestion === null &&
    !filters.favorites_only &&
    filters.has_note === null &&
    !filters.collection_id &&
    !filters.tag_id &&
    !filters.search &&
    !filters.start_at &&
    !filters.end_at;

  return (
    <div className="page-stack activity-library-page">
      <PageHeader
        eyebrow="Activity Library"
        title="Find captured activity"
        description="Search active Visits across Streams, then inspect evidence, review unresolved activity, or export only existing reviewed truth."
        actions={<button className="secondary-action" onClick={onOpenCollections} type="button">Collections</button>}
      />

      <section className="panel activity-library-filters">
        <div className="activity-filter-grid">
          <label>
            Activity
            <select
              value={filters.review_filter ?? "all"}
              onChange={(event) => commitFilters({ ...filters, review_filter: event.target.value as ActivityLibraryReviewFilter })}
            >
              {reviewFilterOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label>
            Stream
            <select
              value={filters.stream_id ?? ""}
              onChange={(event) => commitFilters({ ...filters, stream_id: event.target.value || null })}
            >
              <option value="">All Streams</option>
              {selectedStreamMissing ? <option value={filters.stream_id ?? ""}>Unavailable Stream</option> : null}
              {streams.map((stream) => <option key={stream.id} value={stream.id}>{stream.name}</option>)}
            </select>
          </label>
          <label>
            Camera / Source
            <select
              value={filters.source_id ?? ""}
              onChange={(event) => commitFilters({ ...filters, source_id: event.target.value || null })}
            >
              <option value="">All cameras</option>
              {selectedSourceMissing ? <option value={filters.source_id ?? ""}>Unavailable camera</option> : null}
              {sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
            </select>
          </label>
          <label>
            Zone
            <select
              value={filters.zone_id ?? ""}
              onChange={(event) => commitFilters({ ...filters, zone_id: event.target.value || null })}
            >
              <option value="">All Zones</option>
              {selectedZoneMissing ? <option value={filters.zone_id ?? ""}>Unavailable Zone</option> : null}
              {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
            </select>
          </label>
          <label>
            Suggestion evidence
            <select
              value={filters.has_suggestion === true ? "yes" : filters.has_suggestion === false ? "no" : "all"}
              onChange={(event) => commitFilters({
                ...filters,
                has_suggestion: event.target.value === "yes" ? true : event.target.value === "no" ? false : null,
              })}
            >
              <option value="all">Any suggestion state</option>
              <option value="yes">Has suggestion evidence</option>
              <option value="no">No suggestion evidence</option>
            </select>
          </label>
          <label>
            Favorite
            <select
              value={filters.favorites_only ? "yes" : "all"}
              onChange={(event) => commitFilters({ ...filters, favorites_only: event.target.value === "yes" })}
            >
              <option value="all">All Visits</option>
              <option value="yes">Favorites only</option>
            </select>
          </label>
          <label>
            Private note
            <select
              value={filters.has_note === true ? "yes" : filters.has_note === false ? "no" : "all"}
              onChange={(event) => commitFilters({ ...filters, has_note: event.target.value === "yes" ? true : event.target.value === "no" ? false : null })}
            >
              <option value="all">Any note state</option>
              <option value="yes">Has note</option>
              <option value="no">No note</option>
            </select>
          </label>
          <label>
            Collection
            <select value={filters.collection_id ?? ""} onChange={(event) => commitFilters({ ...filters, collection_id: event.target.value || null })}>
              <option value="">All Collections</option>
              {collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
            </select>
          </label>
          <label>Tag <select value={filters.tag_id ?? ""} onChange={(event) => commitFilters({ ...filters, tag_id: event.target.value || null })}><option value="">All tags</option>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select></label>
          <label>
            From
            <input type="date" value={dateInputValue(filters.start_at)} onChange={(event) => commitFilters({ ...filters, start_at: event.target.value || null })} />
          </label>
          <label>
            To
            <input type="date" value={dateInputValue(filters.end_at)} onChange={(event) => commitFilters({ ...filters, end_at: event.target.value || null })} />
          </label>
          <label>
            Confirmed label
            <input
              value={filters.confirmed_label ?? ""}
              onChange={(event) => setFilters({ ...filters, confirmed_label: event.target.value })}
              onBlur={() => commitFilters(filters)}
              placeholder="e.g. northern cardinal"
            />
          </label>
          <label className="activity-search-field">
            Search labels, Streams, Sources, or Zones
            <input
              value={filters.search ?? ""}
              onChange={(event) => setFilters({ ...filters, search: event.target.value })}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  commitFilters(filters);
                }
              }}
              onBlur={() => commitFilters(filters)}
              placeholder="Search activity"
            />
          </label>
        </div>
        <div className="activity-library-filter-actions">
          <button className="secondary-action" onClick={() => commitFilters(defaultFilters)} type="button">Reset filters</button>
          <label className="activity-save-view">
            <span>Save current view</span>
            <input value={saveName} onChange={(event) => setSaveName(event.target.value)} placeholder="View name" maxLength={80} />
          </label>
          <button className="secondary-action" onClick={() => void saveCurrentView()} type="button">Save view</button>
        </div>
      </section>

      {savedViews.length > 0 ? (
        <section className="panel activity-saved-views">
          <div className="section-heading"><div><h2>Saved views</h2><p>Local filter presets only; they do not run in the background.</p></div></div>
          <div className="activity-saved-view-list">
            {savedViews.map((view) => (
              <div key={view.id} className="activity-saved-view">
                <button className="text-action" type="button" onClick={() => commitFilters(view.filters)}>{view.name}</button>
                <span>
                  {reviewFilterOptions.find((option) => option.value === (view.filters.review_filter ?? "all"))?.label ?? "Saved filters"}
                </span>
                <button className="text-action" type="button" onClick={() => void renameSavedView(view)}>Rename</button>
                <button className="text-action destructive-action" type="button" onClick={() => void deleteSavedView(view)}>Delete</button>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="panel activity-saved-views">
        <div className="section-heading"><div><h2>Tag management</h2><p>Private Visit organization only. Tags never change reviewed labels, evidence, or Collections.</p></div></div>
        <div className="activity-library-filter-actions">
          <label className="activity-save-view"><span>New tag</span><input maxLength={50} onChange={(event) => setNewTagName(event.target.value)} value={newTagName} /></label>
          <span className="meta-text">{newTagName.length}/50 characters</span>
          <button className="secondary-action" disabled={!newTagName.trim()} onClick={() => void createTag()} type="button">Create tag</button>
        </div>
        {manageableTags.length ? <div className="activity-saved-view-list">{manageableTags.map((tag) => <div className="activity-saved-view" key={tag.id}><strong>{tag.name}</strong><span>{tag.active_visit_count} active Visit{tag.active_visit_count === 1 ? "" : "s"}</span><button className="text-action" onClick={() => void renameTag(tag)} type="button">Rename</button><button className="text-action destructive-action" onClick={() => void archiveTag(tag)} type="button">Archive</button></div>)}</div> : <p className="meta-text">No active tags yet.</p>}
        {tagManagementMessage ? <p className="meta-text">{tagManagementMessage}</p> : null}
      </section>

      {selectedIds.length > 0 ? (
        <section className="notice-panel activity-library-selection" role="status">
          <strong>{selectedIds.length} selected</strong>
          <span>
            {selectedNeedsReviewIds.length} needs review; reviewed export will exclude unresolved or superseded Visits.
          </span>
          <div>
            <button
              className="primary-action"
              disabled={selectedNeedsReviewIds.length === 0}
              onClick={() => onOpenFocusedFastReview(selectedNeedsReviewIds)}
              type="button"
            >
              Open selected in Fast Review
            </button>
            <button className="secondary-action" onClick={() => void exportSelected()} type="button">Export selected reviewed</button>
            <button className="secondary-action" disabled={isUpdatingOrganization} onClick={() => void bulkSetFavorite("favorite")} type="button">Favorite selected</button>
            <button className="secondary-action" disabled={isUpdatingOrganization} onClick={() => void bulkSetFavorite("unfavorite")} type="button">Unfavorite selected</button>
            <label>Collection <select value={bulkCollectionId} onChange={(event) => setBulkCollectionId(event.target.value)}><option value="">Choose Collection</option>{collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}</select></label>
            <button className="secondary-action" disabled={!bulkCollectionId} onClick={() => void bulkUpdateCollection("add")} type="button">Add selected to Collection</button>
            <button className="secondary-action" disabled={!bulkCollectionId} onClick={() => void bulkUpdateCollection("remove")} type="button">Remove selected from Collection</button>
            <label>Tag <select value={bulkTagId} onChange={(event) => setBulkTagId(event.target.value)}><option value="">Choose tag</option>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select></label><button className="secondary-action" disabled={!bulkTagId} onClick={() => void bulkUpdateTag("add")} type="button">Add tag</button><button className="secondary-action" disabled={!bulkTagId} onClick={() => void bulkUpdateTag("remove")} type="button">Remove tag</button>
            <button className="text-action" onClick={() => setSelectedIds([])} type="button">Clear selection</button>
            {message?.startsWith("Created reviewed export") ? <button className="text-action" onClick={onOpenExports} type="button">Open Exports</button> : null}
          </div>
          {message ? <span>{message}</span> : null}
        </section>
      ) : null}

      {message && selectedIds.length === 0 ? <div className="notice-panel" role="status">{message}</div> : null}
      {error ? <div className="error-panel"><strong>Could not refresh Activity Library.</strong><span>{error}</span><button className="secondary-action" onClick={() => setRefreshVersion((value) => value + 1)} type="button">Retry</button></div> : null}

      <section className="activity-library-results">
        <div className="section-heading">
          <div><h2>{isDefaultView ? "Newest active Visits" : "Matching active Visits"}</h2><p>Newest first. Superseded Visits remain on their provenance links, not in this list.</p></div>
          {isLoading ? <span className="meta-text">Refreshing…</span> : null}
        </div>
        {visits.length === 0 && !isLoading ? (
          <EmptyState
            title={isDefaultView ? "No captured activity yet" : "No active Visits match these filters"}
            description={isDefaultView ? "Capture or import activity to start a Visit history." : "Try clearing a filter or widening the date range."}
            action={!isDefaultView ? <button className="secondary-action" onClick={() => commitFilters(defaultFilters)} type="button">Reset filters</button> : undefined}
          />
        ) : (
          <div className="activity-visit-list">
            {visits.map((visit) => {
              const thumbnailUnavailable = !visit.primary_evidence || thumbnailFailures.has(visit.id);
              const selected = selectedIds.includes(visit.id);
              return (
                <article className="panel activity-visit-card" key={visit.id}>
                  <label className="activity-select-control">
                    <input checked={selected} onChange={(event) => toggleSelected(visit.id, event.target.checked)} type="checkbox" />
                    <span>Select</span>
                  </label>
                  {thumbnailUnavailable ? (
                    <div className="activity-thumbnail activity-thumbnail-missing">No preview</div>
                  ) : (
                    <img
                      alt="Primary Visit evidence"
                      className="activity-thumbnail"
                      onError={() => setThumbnailFailures((current) => new Set([...current, visit.id]))}
                      src={`${apiClient.baseUrl}${visit.primary_evidence?.preview_url ?? ""}`}
                    />
                  )}
                  <div className="activity-visit-summary">
                    <div className="activity-visit-title">
                      <strong>{formatDateTime(visit.activity_started_at)}</strong>
                      <StatusPill label={formatLabel(visit.review_outcome)} tone={outcomeTone(visit.review_outcome)} />
                    </div>
                    <span>{durationLabel(visit.duration_seconds)} · {visit.stream_name} · {visit.source_name}</span>
                    <span>Zone: {visit.zone_name ?? "No Zone"}</span>
                    {visit.reviewed_label ? <span>Confirmed: {formatLabel(visit.reviewed_label)}</span> : null}
                    {visit.has_suggestion ? <span>Suggestion evidence: {formatLabel(visit.suggested_label ?? "available")}</span> : null}
                    {visit.is_favorite ? <StatusPill label="Favorite" tone="good" /> : null}
                    {visit.has_note ? <StatusPill label="Note" tone="quiet" /> : null}
                    {visit.collection_count > 0 ? <StatusPill label={`${visit.collection_count} Collection${visit.collection_count === 1 ? "" : "s"}`} tone="quiet" /> : null}
                    {visit.tags.map((tag) => <StatusPill key={tag} label={tag} tone="quiet" />)}
                    {visit.evidence_frame_count > 1 ? <span>{visit.evidence_frame_count} evidence frames</span> : null}
                    {visit.curation_actions.length > 0 ? <span>Curated: {visit.curation_actions.map(formatLabel).join(", ")}</span> : null}
                  </div>
                  <div className="activity-visit-actions">
                    <button className="secondary-action" onClick={() => onOpenVisit(visit.id)} type="button">Open Visit</button>
                    {visit.review_outcome === "needs_review" ? <button className="text-action" onClick={() => onOpenFocusedFastReview([visit.id])} type="button">Fast Review</button> : null}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <div className="activity-library-pagination">
        <button className="secondary-action" disabled={offset === 0 || isLoading} onClick={() => goToOffset(Math.max(0, offset - 24))} type="button">Newer</button>
        <span>{offset > 0 ? `Showing page ${Math.floor(offset / 24) + 1}` : "Showing newest activity"}</span>
        <button className="secondary-action" disabled={!hasMore || isLoading} onClick={() => goToOffset(offset + 24)} type="button">Older</button>
      </div>
    </div>
  );
}
