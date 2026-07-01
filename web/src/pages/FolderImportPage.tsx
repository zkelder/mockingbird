import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  FolderImportPreview,
  FolderImportResult,
  Stream,
  Zone,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatLabel } from "../utils";

interface FolderImportPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenStream: (streamId: string) => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onOpenDetectionProposals: () => void;
  onImportComplete: () => Promise<void>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kib = bytes / 1024;
  if (kib < 1024) {
    return `${kib.toFixed(1)} KiB`;
  }

  return `${(kib / 1024).toFixed(1)} MiB`;
}

export function FolderImportPage({
  streams,
  sources,
  onOpenEvent,
  onOpenVisit,
  onOpenStream,
  onOpenReview,
  onOpenExports,
  onOpenDetectionProposals,
  onImportComplete,
}: FolderImportPageProps) {
  const [folderPath, setFolderPath] = useState("");
  const [selectedStreamId, setSelectedStreamId] = useState(streams[0]?.id ?? "");
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedZoneId, setSelectedZoneId] = useState("");
  const [subjectLabel, setSubjectLabel] = useState("unknown_bird");
  const [speciesGuess, setSpeciesGuess] = useState("");
  const [notes, setNotes] = useState("");
  const [limit, setLimit] = useState("");
  const [preview, setPreview] = useState<FolderImportPreview | null>(null);
  const [result, setResult] = useState<FolderImportResult | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isLoadingZones, setIsLoadingZones] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sourceNames = useMemo(
    () => new Map(sources.map((source) => [source.id, source.name])),
    [sources],
  );
  const selectedStream = streams.find((stream) => stream.id === selectedStreamId) ?? null;

  useEffect(() => {
    setSelectedStreamId((current) =>
      current && streams.some((stream) => stream.id === current) ? current : streams[0]?.id ?? "",
    );
  }, [streams]);

  useEffect(() => {
    let isMounted = true;

    async function loadZones() {
      if (!selectedStreamId) {
        setZones([]);
        setSelectedZoneId("");
        return;
      }

      setIsLoadingZones(true);
      try {
        const nextZones = await apiClient.getStreamZones(selectedStreamId);
        if (isMounted) {
          setZones(nextZones);
          setSelectedZoneId((current) =>
            current && nextZones.some((zone) => zone.id === current) ? current : "",
          );
        }
      } catch (caught) {
        if (isMounted) {
          setZones([]);
          setSelectedZoneId("");
          setError(caught instanceof Error ? caught.message : "Could not load stream zones.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingZones(false);
        }
      }
    }

    void loadZones();

    return () => {
      isMounted = false;
    };
  }, [selectedStreamId]);

  async function previewFolder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedPath = folderPath.trim();
    if (!trimmedPath) {
      setError("Choose a local folder path before previewing.");
      return;
    }

    setIsPreviewing(true);
    setError(null);
    setMessage(null);
    setResult(null);
    try {
      const nextPreview = await apiClient.previewFolderImport({ folder_path: trimmedPath });
      setPreview(nextPreview);
      setMessage(
        `${nextPreview.supported_count} supported file${
          nextPreview.supported_count === 1 ? "" : "s"
        } found for local import.`,
      );
    } catch (caught) {
      setPreview(null);
      setError(caught instanceof Error ? caught.message : "Folder preview could not be loaded.");
    } finally {
      setIsPreviewing(false);
    }
  }

  async function importFolder() {
    const trimmedPath = folderPath.trim();
    if (!trimmedPath) {
      setError("Choose a local folder path before importing.");
      return;
    }
    if (!selectedStreamId) {
      setError("Choose a stream for this folder import.");
      return;
    }

    const parsedLimit = limit.trim() ? Number(limit) : undefined;
    if (parsedLimit !== undefined && (!Number.isInteger(parsedLimit) || parsedLimit < 1)) {
      setError("Import limit must be a whole number greater than zero.");
      return;
    }

    setIsImporting(true);
    setError(null);
    setMessage(null);
    try {
      const nextResult = await apiClient.importFolderMedia({
        folder_path: trimmedPath,
        stream_id: selectedStreamId,
        zone_id: selectedZoneId || undefined,
        subject_label: subjectLabel.trim() || "unknown_bird",
        species_guess: speciesGuess.trim() || undefined,
        notes: notes.trim() || undefined,
        limit: parsedLimit,
      });
      setResult(nextResult);
      setMessage(
        `${nextResult.imported_count} file${
          nextResult.imported_count === 1 ? "" : "s"
        } imported into review.`,
      );
      await onImportComplete();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Folder import could not be created.");
    } finally {
      setIsImporting(false);
    }
  }

  const importedRows = result
    ? result.media_assets.map((asset, index) => ({
        asset,
        event: result.events[index],
        visit: result.visits[index],
      }))
    : [];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="User-controlled source path"
        title="Folder Import"
        description="Import local media into reviewable outdoor events. Media stays local; review and correct imported observations before export."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
            </button>
            {selectedStream ? (
              <button className="secondary-action" onClick={() => onOpenStream(selectedStream.id)}>
                Open stream context
              </button>
            ) : null}
          </>
        }
      />

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="folder-import-layout">
        <form className="panel manual-import-form" onSubmit={previewFolder}>
          <div className="section-heading">
            <h2>Preview folder</h2>
            <StatusPill label="Non-recursive" tone="quiet" />
          </div>
          <div className="import-flow-strip">
            <span>Local folder</span>
            <span>Supported media</span>
            <span>Review events</span>
            <span>Export after correction</span>
          </div>
          <label>
            Folder path
            <input
              value={folderPath}
              onChange={(event) => {
                setFolderPath(event.target.value);
                setPreview(null);
                setResult(null);
              }}
              placeholder="/path/to/local/media"
            />
          </label>
          <button className="primary-action" disabled={isPreviewing} type="submit">
            {isPreviewing ? "Previewing..." : "Preview supported files"}
          </button>
        </form>

        <div className="panel manual-import-form">
          <div className="section-heading">
            <h2>Import settings</h2>
            <StatusPill label="Media stays local" tone="quiet" />
          </div>
          <label>
            Stream
            <select
              disabled={streams.length === 0}
              value={selectedStreamId}
              onChange={(event) => setSelectedStreamId(event.target.value)}
            >
              {streams.map((stream) => (
                <option key={stream.id} value={stream.id}>
                  {stream.name} - {sourceNames.get(stream.source_id) ?? stream.source_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Zone
            <select
              disabled={!selectedStreamId || isLoadingZones}
              value={selectedZoneId}
              onChange={(event) => setSelectedZoneId(event.target.value)}
            >
              <option value="">Unzoned</option>
              {zones.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name} - {formatLabel(zone.zone_type)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Initial subject label
            <input value={subjectLabel} onChange={(event) => setSubjectLabel(event.target.value)} />
          </label>
          <label>
            Species guess
            <input
              value={speciesGuess}
              onChange={(event) => setSpeciesGuess(event.target.value)}
              placeholder="optional"
            />
          </label>
          <label>
            Notes
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="optional review context"
            />
          </label>
          <label>
            Import limit
            <input
              min="1"
              onChange={(event) => setLimit(event.target.value)}
              placeholder="optional"
              type="number"
              value={limit}
            />
          </label>
          <button
            className="primary-action"
            disabled={isImporting || !preview || !selectedStreamId}
            onClick={() => void importFolder()}
            type="button"
          >
            {isImporting ? "Importing..." : "Import previewed media"}
          </button>
        </div>
      </section>

      {preview ? (
        <section className="split-grid">
          <div className="panel">
            <div className="section-heading">
              <h2>Supported files</h2>
              <StatusPill label={`${preview.supported_count} ready`} tone="good" />
            </div>
            <div className="folder-file-list">
              {preview.supported_files.map((candidate) => (
                <div className="folder-file-row" key={candidate.path}>
                  <div>
                    <strong>{candidate.filename}</strong>
                    <span>{candidate.content_type}</span>
                  </div>
                  <span>{formatBytes(candidate.file_size_bytes)}</span>
                </div>
              ))}
              {preview.supported_files.length === 0 ? (
                <EmptyState
                  title="No supported media found"
                  description="Supported folder imports are JPG, PNG, WebP, MP4, and MOV files in this folder."
                />
              ) : null}
            </div>
          </div>

          <div className="panel">
            <div className="section-heading">
              <h2>Skipped files</h2>
              <StatusPill label={`${preview.skipped_count} skipped`} tone="quiet" />
            </div>
            <div className="folder-file-list">
              {preview.skipped_files.map((skipped) => (
                <div className="folder-file-row" key={`${skipped.filename}-${skipped.reason}`}>
                  <div>
                    <strong>{skipped.filename}</strong>
                    <span>{formatLabel(skipped.reason)}</span>
                  </div>
                </div>
              ))}
              {preview.skipped_files.length === 0 ? (
                <span className="meta-text">No unsupported files in this preview.</span>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {result ? (
        <section className="panel">
          <div className="section-heading">
            <h2>Imported into review</h2>
            <StatusPill label={`${result.review_queue_count} needs review`} tone="review" />
          </div>
          <div className="summary-row">
            <span>
              Imported {result.imported_count} file{result.imported_count === 1 ? "" : "s"} from{" "}
              {result.folder_path}
            </span>
            <div className="detail-actions">
              <button className="secondary-action" onClick={onOpenReview}>
                Review Queue
              </button>
              <button className="secondary-action" onClick={onOpenExports}>
                Dataset Exports
              </button>
              <button className="secondary-action" onClick={onOpenDetectionProposals}>
                Generate demo proposal
              </button>
            </div>
          </div>
          <div className="folder-import-results">
            {importedRows.slice(0, 6).map(({ asset, event, visit }) => (
              <article className="media-list-item" key={asset.id}>
                <MediaAssetPreview asset={asset} compact />
                <div className="detail-actions">
                  <button className="text-action" onClick={() => onOpenEvent(event.id)}>
                    Event detail
                  </button>
                  <button className="text-action" onClick={() => onOpenVisit(visit.id)}>
                    Visit detail
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
