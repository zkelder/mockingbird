import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  DatasetCoverageSummary,
  DatasetExport,
  DatasetExportManifest,
  DatasetQualitySummary,
} from "../api/types";
import { DatasetCoveragePanel } from "../components/DatasetCoveragePanel";
import { DatasetQualityPanel } from "../components/DatasetQualityPanel";
import { DetectionEvidenceCard } from "../components/DetectionEvidenceCard";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel, sortedEntries } from "../utils";

interface ExportsPageProps {
  exports: DatasetExport[];
  datasetCoverage: DatasetCoverageSummary | null;
  datasetQuality: DatasetQualitySummary | null;
  onOpenReview: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenDetectionProposals: () => void;
  onExportsChanged: () => Promise<void>;
}

function mediaReferenceName(mediaPath: string): string {
  const normalizedPath = mediaPath.replace(/\\/g, "/");
  const pathParts = normalizedPath.split("/").filter(Boolean);
  return pathParts[pathParts.length - 1] ?? mediaPath;
}

export function ExportsPage({
  exports,
  datasetCoverage,
  datasetQuality,
  onOpenReview,
  onOpenEvent,
  onOpenVisit,
  onOpenDetectionProposals,
  onExportsChanged,
}: ExportsPageProps) {
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
  const speciesRecordCount = manifest?.records.filter((record) => record.is_species).length ?? 0;
  const unknownBirdRecordCount =
    manifest?.records.filter((record) => record.label === "unknown_bird").length ?? 0;
  const skippedNeedsReviewCount = manifest?.skipped_reasons.needs_review ?? 0;

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
      <PageHeader
        eyebrow="Local dataset output"
        title="Dataset Exports"
        description="Generate local reviewed datasets from corrected events and visits. Corrected taxonomy labels export as truth; detections stay attached as evidence."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenReview}>
              Open Review Queue
            </button>
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
            </button>
          </>
        }
      />

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}
      <section className="notice-panel">
        <strong>Reviewed corrections export as truth</strong>
        <span>
          Raw MediaAssets, MotionEvidence, DetectionProposal evidence, and unreviewed Visits are
          context only. Review corrections decide what counts in local dataset exports.
        </span>
      </section>

      <DatasetQualityPanel
        quality={datasetQuality}
        onOpenEvent={onOpenEvent}
        onOpenReview={onOpenReview}
        onOpenVisit={onOpenVisit}
      />

      <DatasetCoveragePanel
        coverage={datasetCoverage}
        onOpenReview={onOpenReview}
        variant="compact"
      />

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
              <EmptyState
                title="No dataset exports yet"
                description="Correct Visits in the Review Queue first, then generate a reviewed local dataset. Evidence and unreviewed Visits are not export truth."
              />
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

            <div className="species-export-summary">
              <div>
                <span className="meta-text">Reviewed species labels</span>
                <strong>{speciesRecordCount}</strong>
              </div>
              <div>
                <span className="meta-text">Unknown bird records</span>
                <strong>{unknownBirdRecordCount}</strong>
              </div>
              <div>
                <span className="meta-text">Skipped needs review</span>
                <strong>{skippedNeedsReviewCount}</strong>
              </div>
              <div>
                <span className="meta-text">Dataset truth</span>
                <strong>Corrected taxonomy labels</strong>
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
                <button className="secondary-action" onClick={onOpenReview}>
                  Review skipped activity
                </button>
                <button className="secondary-action" onClick={onOpenDetectionProposals}>
                  Open proposal evidence
                </button>
              </div>
            ) : null}

            <div className="record-list">
              {manifest.records.map((record) => (
                <article className="record-card" key={record.record_id}>
                  <div className="item-title-row">
                    <div>
                      <span className="meta-text">
                        {record.media_path
                          ? "Imported media record with corrected local truth"
                          : "Corrected label will be used as local truth"}
                      </span>
                      <h3>{record.label_display_name ?? formatLabel(record.label)}</h3>
                    </div>
                    <div className="record-status-stack">
                      <EvidenceBadge label="Corrected label is truth" tone="truth" />
                      {record.is_species ? (
                        <EvidenceBadge label="Reviewed species truth" tone="truth" />
                      ) : null}
                      {record.label === "unknown_bird" ? (
                        <EvidenceBadge label="Unknown bird record" tone="review" />
                      ) : null}
                      {record.label_category ? (
                        <EvidenceBadge
                          label={`${formatLabel(record.label_category)}${
                            record.is_species ? " species" : ""
                          }`}
                          tone="quiet"
                        />
                      ) : null}
                      <StatusPill
                        label={record.dataset_ready ? "Ready for local dataset export" : "Needs review"}
                        tone={record.dataset_ready ? "good" : "review"}
                      />
                    </div>
                  </div>
                  <div className="record-meta-grid">
                    <span>Stream: {record.stream_id}</span>
                    <span>
                      Zone:{" "}
                      {record.zone_name
                        ? `${record.zone_name} (${formatLabel(record.zone_type ?? "unknown")})`
                        : "Unzoned"}
                    </span>
                    <span>
                      Media:{" "}
                      {record.media_path
                        ? `${mediaReferenceName(record.media_path)} (local reference)`
                        : "Reference pending"}
                    </span>
                    <span>
                      Detections: {record.detections.length} evidence item
                      {record.detections.length === 1 ? "" : "s"}
                    </span>
                    <span>Export label id: {record.label}</span>
                  </div>
                  {manifest.export.include_detections && record.detections.length > 0 ? (
                    <div className="export-evidence-list">
                      {record.detections.map((detection) => (
                        <DetectionEvidenceCard
                          compact
                          detection={detection}
                          key={detection.id}
                          statusLabel="Export evidence"
                          zoneLabel={record.zone_name ?? undefined}
                        />
                      ))}
                    </div>
                  ) : null}
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
