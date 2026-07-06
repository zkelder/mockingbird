import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  EventDetail,
  MediaAsset,
  ReviewLabel,
  Stream,
  VisitDetail,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

type BirdLogStatusFilter = "all" | "reviewed";
type BirdLogEntryStatus = "reviewed";
type BirdLogTargetType = "event" | "visit";

interface BirdLogPageProps {
  sources: CameraSource[];
  streams: Stream[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenStreams: () => void;
  onOpenImport: () => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
}

interface BirdLogEntry {
  id: string;
  status: BirdLogEntryStatus;
  label: string;
  suggestedLabel?: string | null;
  title: string;
  timestamp?: string | null;
  sourceName: string;
  streamName: string;
  zoneName?: string | null;
  mediaAsset?: MediaAsset | null;
  targetType: BirdLogTargetType;
  targetId: string;
}

function targetKey(targetType: string, targetId: string): string {
  return `${targetType}:${targetId}`;
}

function latestLabelsByTarget(labels: ReviewLabel[]): ReviewLabel[] {
  const byTarget = new Map<string, ReviewLabel>();
  for (const label of [...labels].sort((left, right) => compareDates(right.created_at, left.created_at))) {
    const key = targetKey(label.target_type, label.target_id);
    if (!byTarget.has(key)) {
      byTarget.set(key, label);
    }
  }
  return [...byTarget.values()];
}

function compareDates(left?: string | null, right?: string | null): number {
  const leftTime = left ? new Date(left).getTime() : 0;
  const rightTime = right ? new Date(right).getTime() : 0;
  return leftTime - rightTime;
}

function seenTimestamp(
  eventStartedAt?: string | null,
  asset?: MediaAsset | null,
  fallback?: string | null,
): string | null {
  return asset?.created_at ?? eventStartedAt ?? fallback ?? null;
}

function streamSourceName(
  streamId: string,
  streams: Stream[],
  sources: CameraSource[],
  asset?: MediaAsset | null,
): string {
  const mediaSource = asset?.source_id
    ? sources.find((source) => source.id === asset.source_id)
    : null;
  if (mediaSource) {
    return mediaSource.name;
  }
  const stream = streams.find((item) => item.id === streamId);
  return sources.find((source) => source.id === stream?.source_id)?.name ?? "Unknown camera";
}

function reviewedEntryFromVisit(
  label: ReviewLabel,
  detail: VisitDetail,
  sources: CameraSource[],
): BirdLogEntry {
  return {
    id: `reviewed-${label.id}`,
    status: "reviewed",
    label: label.label,
    suggestedLabel: detail.visit.species_guess ?? detail.visit.subject_label,
    title: detail.event.title,
    timestamp: seenTimestamp(detail.event.started_at, detail.media_asset, label.created_at),
    sourceName: streamSourceName(detail.stream.id, [detail.stream], sources, detail.media_asset),
    streamName: detail.stream.name,
    zoneName: detail.primary_zone?.name ?? null,
    mediaAsset: detail.media_asset,
    targetType: "visit",
    targetId: detail.visit.id,
  };
}

function reviewedEntryFromEvent(
  label: ReviewLabel,
  detail: EventDetail,
  sources: CameraSource[],
): BirdLogEntry {
  return {
    id: `reviewed-${label.id}`,
    status: "reviewed",
    label: label.label,
    suggestedLabel: detail.event.detections[0]?.label ?? null,
    title: detail.event.title,
    timestamp: seenTimestamp(detail.event.started_at, detail.media_asset, label.created_at),
    sourceName: streamSourceName(detail.stream.id, [detail.stream], sources, detail.media_asset),
    streamName: detail.stream.name,
    zoneName: detail.primary_zone?.name ?? null,
    mediaAsset: detail.media_asset,
    targetType: "event",
    targetId: detail.event.id,
  };
}

function fallbackReviewedEntry(
  label: ReviewLabel,
  streams: Stream[],
  sources: CameraSource[],
): BirdLogEntry {
  return {
    id: `reviewed-${label.id}`,
    status: "reviewed",
    label: label.label,
    title: "Reviewed outdoor activity",
    timestamp: seenTimestamp(null, null, label.created_at),
    sourceName: sources[0]?.name ?? "Unknown camera",
    streamName: streams[0]?.name ?? "Unknown stream",
    targetType: label.target_type === "visit" ? "visit" : "event",
    targetId: label.target_id,
  };
}

function dateBucket(timestamp?: string | null): string {
  if (!timestamp) {
    return "Unknown date";
  }

  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  if (date.toDateString() === today.toDateString()) {
    return "Today";
  }
  if (date.toDateString() === yesterday.toDateString()) {
    return "Yesterday";
  }

  return date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function entrySearchText(entry: BirdLogEntry): string {
  return [
    entry.label,
    entry.suggestedLabel ?? "",
    entry.title,
    entry.sourceName,
    entry.streamName,
    entry.zoneName ?? "",
    entry.mediaAsset?.original_filename ?? "",
  ]
    .join(" ")
    .toLowerCase();
}

export function BirdLogPage({
  sources,
  streams,
  onOpenEvent,
  onOpenVisit,
  onOpenStreams,
  onOpenImport,
  onOpenReview,
  onOpenExports,
}: BirdLogPageProps) {
  const [reviewedEntries, setReviewedEntries] = useState<BirdLogEntry[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<BirdLogStatusFilter>("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadReviewedEntries() {
      setIsLoading(true);
      setError(null);
      try {
        const labels = await apiClient.getReviewLabels();
        const latestLabels = latestLabelsByTarget(labels).filter(
          (label) => label.target_type === "visit" || label.target_type === "event",
        );
        const entries = await Promise.all(
          latestLabels.map(async (label) => {
            try {
              if (label.target_type === "visit") {
                return reviewedEntryFromVisit(
                  label,
                  await apiClient.getVisitDetail(label.target_id),
                  sources,
                );
              }
              return reviewedEntryFromEvent(
                label,
                await apiClient.getEventDetail(label.target_id),
                sources,
              );
            } catch {
              return fallbackReviewedEntry(label, streams, sources);
            }
          }),
        );

        if (isMounted) {
          setReviewedEntries(entries);
        }
      } catch (caught) {
        if (isMounted) {
          setError(caught instanceof Error ? caught.message : "Could not load Bird Log.");
          setReviewedEntries([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadReviewedEntries();

    return () => {
      isMounted = false;
    };
  }, [sources, streams]);

  const entries = useMemo(() => {
    return [...reviewedEntries].sort((left, right) =>
      compareDates(right.timestamp, left.timestamp),
    );
  }, [reviewedEntries]);

  const sourceOptions = useMemo(
    () =>
      [...new Set(entries.map((entry) => entry.sourceName))]
        .filter(Boolean)
        .sort((left, right) => left.localeCompare(right)),
    [entries],
  );

  const filteredEntries = useMemo(() => {
    const query = search.trim().toLowerCase();
    return entries.filter((entry) => {
      const matchesStatus = statusFilter === "all" || entry.status === statusFilter;
      const matchesSource = sourceFilter === "all" || entry.sourceName === sourceFilter;
      const matchesSearch = !query || entrySearchText(entry).includes(query);
      return matchesStatus && matchesSource && matchesSearch;
    });
  }, [entries, search, sourceFilter, statusFilter]);

  const groupedEntries = useMemo(() => {
    const groups = new Map<string, BirdLogEntry[]>();
    for (const entry of filteredEntries) {
      const bucket = dateBucket(entry.timestamp);
      groups.set(bucket, [...(groups.get(bucket) ?? []), entry]);
    }
    return [...groups.entries()];
  }, [filteredEntries]);

  const reviewedCount = entries.filter((entry) => entry.status === "reviewed").length;
  const uniqueLabels = new Set(entries.map((entry) => entry.label.trim()).filter(Boolean));
  const latestReviewed = entries.find((entry) => entry.status === "reviewed") ?? null;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Reviewed activity history"
        title="Bird Log"
        description="A local history of reviewed bird or outdoor activity created by user corrections."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenReview}>
              Review
            </button>
            <button className="secondary-action" onClick={onOpenExports}>
              Export reviewed data
            </button>
          </>
        }
      />

      {error ? <div className="error-panel">{error}</div> : null}

      <section className="bird-log-summary-grid">
        <div className="bird-log-summary-card">
          <span>Reviewed observations</span>
          <strong>{reviewedCount}</strong>
        </div>
        <div className="bird-log-summary-card">
          <span>Unique labels</span>
          <strong>{uniqueLabels.size}</strong>
        </div>
        <div className="bird-log-summary-card">
          <span>Latest reviewed</span>
          <strong>{latestReviewed ? formatLabel(latestReviewed.label) : "None yet"}</strong>
          {latestReviewed?.timestamp ? <small>{formatDateTime(latestReviewed.timestamp)}</small> : null}
        </div>
      </section>

      <section className="panel bird-log-filter-panel">
        <label>
          Search
          <input
            onChange={(event) => setSearch(event.target.value)}
            placeholder="species, activity, camera, zone"
            value={search}
          />
        </label>
        <label>
          Status
          <select
            onChange={(event) => setStatusFilter(event.target.value as BirdLogStatusFilter)}
            value={statusFilter}
          >
            <option value="all">All</option>
            <option value="reviewed">Reviewed</option>
          </select>
        </label>
        <label>
          Camera / Source
          <select onChange={(event) => setSourceFilter(event.target.value)} value={sourceFilter}>
            <option value="all">All cameras</option>
            {sourceOptions.map((sourceName) => (
              <option key={sourceName} value={sourceName}>
                {sourceName}
              </option>
            ))}
          </select>
        </label>
      </section>

      {isLoading ? <div className="panel">Loading Bird Log...</div> : null}

      {!isLoading && entries.length === 0 ? (
        <EmptyState
          title="No bird activity logged yet"
          description="Capture or import an image, analyze it, then review/correct the suggestion to build your Bird Log."
          action={
            <>
              <button className="primary-action" onClick={onOpenStreams}>
                Cameras / Streams
              </button>
              <button className="secondary-action" onClick={onOpenImport}>
                Import image
              </button>
            </>
          }
        />
      ) : null}

      {!isLoading && entries.length > 0 && filteredEntries.length === 0 ? (
        <EmptyState
          title="No matching activity"
          description="Try a different label, status, or camera filter."
        />
      ) : null}

      {!isLoading && filteredEntries.length > 0 ? (
        <div className="bird-log-group-list">
          {groupedEntries.map(([group, groupEntries]) => (
            <section className="bird-log-group" key={group}>
              <div className="section-heading">
                <h2>{group}</h2>
                <StatusPill label={`${groupEntries.length} seen`} tone="quiet" />
              </div>
              <div className="bird-log-entry-list">
                {groupEntries.map((entry) => (
                  <article className="bird-log-entry" key={entry.id}>
                    {entry.mediaAsset ? (
                      <MediaAssetPreview asset={entry.mediaAsset} compact />
                    ) : (
                      <div className="bird-log-image-placeholder">
                        <strong>Snapshot / Image</strong>
                        <span>No source image attached</span>
                      </div>
                    )}
                    <div className="bird-log-entry-body">
                      <div className="item-title-row">
                        <div>
                          <span className="meta-text">Reviewed</span>
                          <h3>{formatLabel(entry.label)}</h3>
                        </div>
                        <StatusPill label="Reviewed" tone="good" />
                      </div>
                      <p>{entry.title}</p>
                      <div className="source-connection-meta">
                        <span>
                          Seen: {entry.timestamp ? formatDateTime(entry.timestamp) : "Unknown time"}
                        </span>
                        <span>Camera / Source: {entry.sourceName}</span>
                        <span>Stream: {entry.streamName}</span>
                        {entry.zoneName ? <span>Zone: {entry.zoneName}</span> : null}
                      </div>
                      <div className="bird-log-label-row">
                        <span>Corrected label</span>
                        <strong>{formatLabel(entry.label)}</strong>
                        {entry.suggestedLabel ? (
                          <small>Suggested: {formatLabel(entry.suggestedLabel)}</small>
                        ) : null}
                      </div>
                      <div className="detail-actions">
                        <button
                          className="secondary-action"
                          onClick={() =>
                            entry.targetType === "visit"
                              ? onOpenVisit(entry.targetId)
                              : onOpenEvent(entry.targetId)
                          }
                          type="button"
                        >
                          View reviewed result
                        </button>
                        {entry.mediaAsset ? (
                          <a
                            className="inline-link"
                            href={apiClient.mediaFileUrl(entry.mediaAsset.id)}
                            rel="noreferrer"
                            target="_blank"
                          >
                            View source image
                          </a>
                        ) : null}
                        <button className="secondary-action" onClick={onOpenExports} type="button">
                          Export reviewed data
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : null}

      <section className="notice-panel compact-notice">
        <strong>Truth boundary</strong>
        <span>
          Bird Log reads existing review and correction data. It does not analyze images, create
          corrections, mark items reviewed, or generate exports automatically.
        </span>
      </section>
    </div>
  );
}
