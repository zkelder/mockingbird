import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ActivityLibraryFilters,
  ActivityLibraryReviewFilter,
  ActivityLibraryVisitSummary,
  CameraSource,
  Stream,
  VisitCollectionSummary,
  Zone,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

const reviewOptions: Array<{ value: ActivityLibraryReviewFilter; label: string }> = [
  { value: "all", label: "All outcomes" },
  { value: "needs_review", label: "Needs review" },
  { value: "reviewed_observation", label: "Reviewed observations" },
  { value: "confirmed_wildlife", label: "Confirmed wildlife" },
  { value: "non_bird", label: "Non-bird activity" },
  { value: "blank_false", label: "Blank / false activity" },
  { value: "ambiguous_unknown", label: "Ambiguous / unknown" },
];

function requestKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function CollectionImage({ collection }: { collection: VisitCollectionSummary }) {
  const evidence = collection.representative_evidence;
  if (!evidence) return <div className="activity-thumbnail activity-thumbnail-missing">No active preview</div>;
  return <img alt={`Representative Visit in ${collection.name}`} className="activity-thumbnail" src={`${apiClient.baseUrl}${evidence.preview_url}`} />;
}

interface CollectionsPageProps {
  collectionId: string | null;
  sources: CameraSource[];
  streams: Stream[];
  onOpenActivityLibrary: () => void;
  onOpenCollection: (collectionId?: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenFocusedFastReview: (visitIds: string[]) => void;
}

export function CollectionsPage({
  collectionId,
  sources,
  streams,
  onOpenActivityLibrary,
  onOpenCollection,
  onOpenVisit,
  onOpenFocusedFastReview,
}: CollectionsPageProps) {
  const [collections, setCollections] = useState<VisitCollectionSummary[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editing, setEditing] = useState<VisitCollectionSummary | null>(null);
  const [detail, setDetail] = useState<VisitCollectionSummary | null>(null);
  const [visits, setVisits] = useState<ActivityLibraryVisitSummary[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [zones, setZones] = useState<Zone[]>([]);
  const [filters, setFilters] = useState<ActivityLibraryFilters>({ review_filter: "all" });
  const [isLoadingVisits, setIsLoadingVisits] = useState(false);

  const refreshCollections = async () => {
    try {
      setCollections(await apiClient.getVisitCollections());
      setLoaded(true);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not refresh Collections. Your current view was kept.");
    }
  };

  useEffect(() => { void refreshCollections(); }, []);

  useEffect(() => {
    let active = true;
    void apiClient.getZones().then((next) => { if (active) setZones(next); }).catch(() => { if (active) setZones([]); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!collectionId) { setDetail(null); return; }
    let active = true;
    void apiClient.getVisitCollection(collectionId).then((next) => {
      if (active) setDetail(next);
    }).catch((caught) => {
      if (active) { setDetail(null); setMessage(caught instanceof Error ? caught.message : "This Collection is unavailable."); }
    });
    return () => { active = false; };
  }, [collectionId]);

  useEffect(() => {
    if (!collectionId || detail?.archived_at) return;
    let active = true;
    setIsLoadingVisits(true);
    void apiClient.searchVisitCollection(collectionId, { ...filters, page_size: 24, offset }).then((result) => {
      if (!active) return;
      setVisits(result.visits);
      setHasMore(result.has_more);
    }).catch((caught) => {
      if (active) setMessage(caught instanceof Error ? caught.message : "Could not refresh this Collection. Your previous results were kept.");
    }).finally(() => { if (active) setIsLoadingVisits(false); });
    return () => { active = false; };
  }, [collectionId, detail?.archived_at, filters, offset]);

  const visibleZones = useMemo(
    () => zones.filter((zone) => !filters.stream_id || zone.stream_id === filters.stream_id),
    [filters.stream_id, zones],
  );

  async function saveCollection() {
    const trimmedName = name.trim();
    if (!trimmedName) { setMessage("Give the Collection a name."); return; }
    try {
      if (editing) {
        await apiClient.updateVisitCollection(editing.id, {
          name: trimmedName,
          description: description || null,
          expected_state_token: editing.state_token,
          idempotency_key: requestKey("collection-update"),
        });
        setMessage("Collection updated.");
      } else {
        await apiClient.createVisitCollection({ name: trimmedName, description: description || null, idempotency_key: requestKey("collection-create") });
        setMessage("Collection created. Add Visits from Activity Library or Visit Detail.");
      }
      setName(""); setDescription(""); setEditing(null);
      await refreshCollections();
    } catch (caught) { setMessage(caught instanceof Error ? caught.message : "Could not save this Collection."); }
  }

  async function archiveCollection(collection: VisitCollectionSummary) {
    if (!window.confirm(`Archive “${collection.name}”? Visits, media, notes, and reviewed labels will remain unchanged.`)) return;
    try {
      await apiClient.archiveVisitCollection(collection.id, { expected_state_token: collection.state_token, idempotency_key: requestKey("collection-archive") });
      setMessage("Collection archived. Its memberships remain historical context only.");
      await refreshCollections();
      if (collectionId === collection.id) onOpenCollection();
    } catch (caught) { setMessage(caught instanceof Error ? caught.message : "Could not archive this Collection."); }
  }

  function editCollection(collection: VisitCollectionSummary) {
    setEditing(collection); setName(collection.name); setDescription(collection.description ?? "");
  }

  if (!collectionId) {
    return <div className="page-stack">
      <PageHeader eyebrow="Private organization" title="Visit Collections" description="Create local galleries for Visits. Collections do not duplicate media or change reviewed truth." actions={<button className="secondary-action" onClick={onOpenActivityLibrary} type="button">Open Activity Library</button>} />
      <section className="panel">
        <div className="section-heading"><div><h2>{editing ? "Edit Collection" : "Create Collection"}</h2><span className="meta-text">Up to 100 active local Collections.</span></div></div>
        <label>Collection name <input value={name} maxLength={80} onChange={(event) => setName(event.target.value)} /></label><span className="field-helper">{name.length}/80 characters</span>
        <label>Description <textarea value={description} maxLength={1000} onChange={(event) => setDescription(event.target.value)} /></label><span className="field-helper">{description.length}/1000 characters</span>
        <div className="detail-actions"><button className="primary-action" onClick={() => void saveCollection()} type="button">{editing ? "Save Collection" : "Create Collection"}</button>{editing ? <button className="secondary-action" onClick={() => { setEditing(null); setName(""); setDescription(""); }} type="button">Cancel</button> : null}</div>
      </section>
      {message ? <div className="notice-panel" role="status">{message}</div> : null}
      {!loaded ? <div className="panel">Loading Collections…</div> : null}
      {loaded && collections.length === 0 ? <EmptyState title="No Collections yet" description="Create a local gallery, then add Visits from their detail page or the Activity Library." /> : null}
      <section className="activity-visit-list" aria-label="Visit Collections">
        {collections.map((collection) => <article className="panel activity-visit-card" key={collection.id}>
          <CollectionImage collection={collection} />
          <div className="activity-visit-summary"><strong>{collection.name}</strong><span>{collection.description || "No description"}</span><span>{collection.active_visit_count} active Visit{collection.active_visit_count === 1 ? "" : "s"}</span><span>Updated {formatDateTime(collection.updated_at)}</span>{collection.latest_active_visit_at ? <span>Latest Visit {formatDateTime(collection.latest_active_visit_at)}</span> : null}</div>
          <div className="activity-visit-actions"><button className="secondary-action" onClick={() => onOpenCollection(collection.id)} type="button">Open Collection</button><button className="text-action" onClick={() => editCollection(collection)} type="button">Edit</button><button className="text-action destructive-action" onClick={() => void archiveCollection(collection)} type="button">Archive</button></div>
        </article>)}
      </section>
    </div>;
  }

  if (!detail) return <div className="page-stack"><PageHeader eyebrow="Private organization" title="Collection" description="Loading Collection…" /><div className="panel">{message ?? "Loading…"}</div></div>;
  if (detail.archived_at) return <div className="page-stack"><PageHeader eyebrow="Private organization" title={detail.name} description="This Collection is archived. Its Visits and media remain unchanged." actions={<button className="secondary-action" onClick={() => onOpenCollection()} type="button">All Collections</button>} /><div className="notice-panel">Archived {formatDateTime(detail.archived_at)}. Historical memberships are retained without exposing an active gallery.</div></div>;

  return <div className="page-stack">
    <PageHeader eyebrow="Private organization" title={detail.name} description={detail.description || "A local Visit gallery. It does not change reviewed truth."} actions={<><button className="secondary-action" onClick={() => onOpenCollection()} type="button">All Collections</button><button className="secondary-action" onClick={() => onOpenCollection()} type="button">Manage Collection</button></>} />
    <section className="panel activity-library-filters"><div className="activity-filter-grid">
      <label>Order <select value={filters.oldest_first ? "oldest" : "newest"} onChange={(event) => { setFilters({ ...filters, oldest_first: event.target.value === "oldest" }); setOffset(0); }}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label>
      <label>Review outcome <select value={filters.review_filter ?? "all"} onChange={(event) => { setFilters({ ...filters, review_filter: event.target.value as ActivityLibraryReviewFilter }); setOffset(0); }}>{reviewOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <label>Label <input value={filters.confirmed_label ?? ""} onChange={(event) => { setFilters({ ...filters, confirmed_label: event.target.value || null }); setOffset(0); }} placeholder="Reviewed label" /></label>
      <label>Stream <select value={filters.stream_id ?? ""} onChange={(event) => { setFilters({ ...filters, stream_id: event.target.value || null, zone_id: null }); setOffset(0); }}><option value="">All Streams</option>{streams.map((stream) => <option key={stream.id} value={stream.id}>{stream.name}</option>)}</select></label>
      <label>Zone <select value={filters.zone_id ?? ""} onChange={(event) => { setFilters({ ...filters, zone_id: event.target.value || null }); setOffset(0); }}><option value="">All Zones</option>{visibleZones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}</select></label>
    </div></section>
    {message ? <div className="notice-panel" role="status">{message}</div> : null}
    <section className="activity-library-results"><div className="section-heading"><div><h2>Active Visits</h2><span className="meta-text">Superseded Visits remain in provenance, not this gallery.</span></div>{isLoadingVisits ? <span className="meta-text">Refreshing…</span> : null}</div>
      {visits.length === 0 && !isLoadingVisits ? <EmptyState title="No active Visits match this Collection" description="Add a Visit from Activity Library or Visit Detail, or clear these filters." /> : <div className="activity-visit-list">{visits.map((visit) => <article className="panel activity-visit-card" key={visit.id}>{visit.primary_evidence ? <img alt="Primary Visit evidence" className="activity-thumbnail" src={`${apiClient.baseUrl}${visit.primary_evidence.preview_url}`} /> : <div className="activity-thumbnail activity-thumbnail-missing">No preview</div>}<div className="activity-visit-summary"><strong>{formatDateTime(visit.activity_started_at)}</strong><span>{visit.stream_name} · {visit.zone_name ?? "No Zone"}</span><StatusPill label={formatLabel(visit.review_outcome)} tone={visit.review_outcome === "needs_review" ? "review" : "good"} />{visit.is_favorite ? <StatusPill label="Favorite" tone="good" /> : null}{visit.has_note ? <StatusPill label="Note" tone="quiet" /> : null}{visit.tags.map((tag) => <StatusPill key={tag} label={tag} tone="quiet" />)}</div><div className="activity-visit-actions"><button className="secondary-action" onClick={() => onOpenVisit(visit.id)} type="button">Open Visit</button>{visit.review_outcome === "needs_review" ? <button className="text-action" onClick={() => onOpenFocusedFastReview([visit.id])} type="button">Fast Review</button> : null}</div></article>)}</div>}
    </section>
    <div className="activity-library-pagination"><button className="secondary-action" disabled={offset === 0 || isLoadingVisits} onClick={() => setOffset(Math.max(0, offset - 24))} type="button">Newer</button><span>{offset > 0 ? `Page ${Math.floor(offset / 24) + 1}` : "Newest Visits"}</span><button className="secondary-action" disabled={!hasMore || isLoadingVisits} onClick={() => setOffset(offset + 24)} type="button">Older</button></div>
  </div>;
}
