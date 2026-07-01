import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type { DatasetExport, DatasetExportManifest } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel, sortedEntries } from "../utils";

interface ExportsPageProps {
  exports: DatasetExport[];
  onExportsChanged: () => Promise<void>;
}

export function ExportsPage({ exports, onExportsChanged }: ExportsPageProps) {
  const [localExports, setLocalExports] = useState<DatasetExport[]>(exports);
  const [selectedExportId, setSelectedExportId] = useState<string | null>(exports[0]?.id ?? null);
  const [manifest, setManifest] = useState<DatasetExportManifest | null>(null);
  const [name, setName] = useState("Reviewed local dataset");
  const [reviewedOnly, setReviewedOnly] = useState(true);
  const [includeDetections, setIncludeDetections] = useState(true);
  const [includeZoneContext, setIncludeZoneContext] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoadingManifest, setIsLoadingManifest] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLocalExports(exports);
    setSelectedExportId((current) => current ?? exports[0]?.id ?? null);
  }, [exports]);

  useEffect(() => {
    let isMounted = true;

    async function loadManifest() {
      if (!selectedExportId) {
        setManifest(null);
        return;
      }

      setIsLoadingManifest(true);
      setError(null);
      try {
        const nextManifest = await apiClient.getDatasetExportManifest(selectedExportId);
        if (isMounted) {
          setManifest(nextManifest);
        }
      } catch (caught) {
        if (isMounted) {
          setError(caught instanceof Error ? caught.message : "Could not load export manifest.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingManifest(false);
        }
      }
    }

    void loadManifest();

    return () => {
      isMounted = false;
    };
  }, [selectedExportId]);

  async function createExport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Export name is required.");
      return;
    }

    setIsCreating(true);
    setMessage(null);
    setError(null);
    try {
      const detail = await apiClient.createDatasetExport({
        name: trimmedName,
        reviewed_only: reviewedOnly,
        include_detections: includeDetections,
        include_zone_context: includeZoneContext,
      });
      setLocalExports((current) => [...current, detail.export]);
      setSelectedExportId(detail.export.id);
      setManifest(detail.manifest);
      setName("Reviewed local dataset");
      setMessage("Reviewed local dataset manifest generated in memory.");
      await onExportsChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create dataset export.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="page-stack">
      <div className="section-heading">
        <div>
          <h1>Dataset Exports</h1>
          <p className="meta-text">
            Exports are local reviewed data generated from corrected events and visits.
          </p>
        </div>
      </div>

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="split-grid">
        <form className="panel export-form" onSubmit={createExport}>
          <div className="section-heading">
            <h2>Create export</h2>
          </div>
          <label>
            Export name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="checkbox-row">
            <input
              checked={reviewedOnly}
              onChange={(event) => setReviewedOnly(event.target.checked)}
              type="checkbox"
            />
            Reviewed local dataset only
          </label>
          <label className="checkbox-row">
            <input
              checked={includeDetections}
              onChange={(event) => setIncludeDetections(event.target.checked)}
              type="checkbox"
            />
            Include detections as evidence
          </label>
          <label className="checkbox-row">
            <input
              checked={includeZoneContext}
              onChange={(event) => setIncludeZoneContext(event.target.checked)}
              type="checkbox"
            />
            Include zone context
          </label>
          <button className="primary-action" disabled={isCreating} type="submit">
            {isCreating ? "Creating..." : "Generate manifest"}
          </button>
        </form>

        <div className="panel">
          <div className="section-heading">
            <h2>Existing exports</h2>
          </div>
          <div className="export-list">
            {localExports.map((datasetExport) => (
              <button
                className={`export-list-item${
                  selectedExportId === datasetExport.id ? " selected" : ""
                }`}
                key={datasetExport.id}
                onClick={() => setSelectedExportId(datasetExport.id)}
                type="button"
              >
                <span>{datasetExport.name}</span>
                <strong>{datasetExport.record_count} records</strong>
                <small>
                  {datasetExport.reviewed_only ? "Reviewed only" : "Includes unreviewed"} -{" "}
                  {formatDateTime(datasetExport.created_at)}
                </small>
                <StatusPill
                  label={formatLabel(datasetExport.status)}
                  tone={datasetExport.status === "ready" ? "good" : "quiet"}
                />
              </button>
            ))}
            {localExports.length === 0 ? (
              <span className="meta-text">No dataset exports yet.</span>
            ) : null}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Manifest preview</h2>
          {manifest ? (
            <StatusPill
              label={`${manifest.records.length} ready record${
                manifest.records.length === 1 ? "" : "s"
              }`}
              tone={manifest.records.length > 0 ? "good" : "quiet"}
            />
          ) : null}
        </div>

        {isLoadingManifest ? <span className="meta-text">Loading manifest...</span> : null}

        {manifest ? (
          <div className="manifest-layout">
            <div className="manifest-summary">
              <div>
                <span className="meta-text">Generated</span>
                <strong>{formatDateTime(manifest.generated_at)}</strong>
              </div>
              <div>
                <span className="meta-text">Skipped</span>
                <strong>{manifest.skipped_count}</strong>
              </div>
              <div>
                <span className="meta-text">Detections</span>
                <strong>{manifest.export.include_detections ? "Evidence included" : "Omitted"}</strong>
              </div>
              <div>
                <span className="meta-text">Zones</span>
                <strong>{manifest.export.include_zone_context ? "Context included" : "Omitted"}</strong>
              </div>
            </div>

            {manifest.skipped_count > 0 ? (
              <div className="notice-panel">
                <strong>Skipped because it still needs review</strong>
                {sortedEntries(manifest.skipped_reasons).map(([reason, count]) => (
                  <span key={reason}>
                    {formatLabel(reason)}: {count}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="record-list">
              {manifest.records.map((record) => (
                <article className="record-card" key={record.record_id}>
                  <div className="item-title-row">
                    <div>
                      <span className="meta-text">Corrected label will be used as local truth</span>
                      <h3>{formatLabel(record.label)}</h3>
                    </div>
                    <StatusPill
                      label={record.dataset_ready ? "Ready for local dataset export" : "Needs review"}
                      tone={record.dataset_ready ? "good" : "review"}
                    />
                  </div>
                  <div className="record-meta-grid">
                    <span>Stream: {record.stream_id}</span>
                    <span>
                      Zone:{" "}
                      {record.zone_name
                        ? `${record.zone_name} (${formatLabel(record.zone_type ?? "unknown")})`
                        : "Unzoned"}
                    </span>
                    <span>Media: {record.media_path ?? "Reference pending"}</span>
                    <span>
                      Detections: {record.detections.length} evidence item
                      {record.detections.length === 1 ? "" : "s"}
                    </span>
                  </div>
                </article>
              ))}
              {manifest.records.length === 0 ? (
                <span className="meta-text">No records are ready for this manifest.</span>
              ) : null}
            </div>

            <details className="manifest-json">
              <summary>Manifest JSON preview</summary>
              <pre>{JSON.stringify(manifest, null, 2)}</pre>
            </details>
          </div>
        ) : null}
      </section>
    </div>
  );
}
