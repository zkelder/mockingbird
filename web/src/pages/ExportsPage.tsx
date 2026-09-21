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

function manifestDownloadFilename(manifest: DatasetExportManifest): string {
  const slug = manifest.export.name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  const day = manifest.export.created_at.slice(0, 10);
  return `${slug || "dataset-export"}-${day}-${manifest.export.id}.json`;
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
  // Broader Wildlife Maturity v1: mirrors unknownBirdRecordCount above --
  // see docs/broader-wildlife-maturity-v1-contract.md.
  const unknownAnimalRecordCount =
    manifest?.records.filter((record) => record.label === "unknown_animal").length ?? 0;
  const skippedNeedsReviewCount = manifest?.skipped_reasons.needs_review ?? 0;
  const skippedReasonEntries = manifest ? sortedEntries(manifest.skipped_reasons) : [];

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

  function downloadManifest() {
    if (!manifest) {
      return;
    }
    setError(null);
    const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: "application/json" });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = manifestDownloadFilename(manifest);
    link.click();
    URL.revokeObjectURL(objectUrl);
    setMessage("Manifest download started.");
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Local dataset output"
        title="Dataset Exports"
        description="Generate local reviewed datasets from corrected events and visits. Corrected taxonomy labels export as truth; detections stay attached as evidence."
        actions={
          <button className="secondary-action" onClick={onOpenReview}>
            Open Review Queue
          </button>
        }
      />

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <details className="panel export-readiness-details review-secondary-details">
        <summary>
          <span>Dataset readiness details</span>
          <strong>QA and coverage</strong>
        </summary>
        <div className="export-readiness-content">
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
        </div>
      </details>

      <section className="split-grid">
        <form className="panel export-form" onSubmit={createExport}>
          <div className="section-heading">
            <div>
              <h2>Create reviewed-only export</h2>
              <span className="meta-text">
                Exports use reviewed correction truth. Suggestions remain evidence.
              </span>
            </div>
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
          <div className="export-settings-strip" aria-label="Default export settings">
            <EvidenceBadge
              label={reviewedOnly ? "Reviewed only" : "Includes unreviewed"}
              tone="truth"
            />
            <EvidenceBadge
              label={includeDetections ? "Detections as evidence" : "Detection evidence omitted"}
              tone="quiet"
            />
            <EvidenceBadge
              label={includeZoneContext ? "Zone context included" : "Zone context omitted"}
              tone="quiet"
            />
          </div>
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
                description="Correct Visits first, then generate a reviewed local dataset."
              />
            ) : null}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Manifest preview</h2>
          {manifest ? (
            <>
              <StatusPill
                label={`${manifest.records.length} ready record${
                  manifest.records.length === 1 ? "" : "s"
                }`}
                tone={manifest.records.length > 0 ? "good" : "quiet"}
              />
              <button className="secondary-action" onClick={downloadManifest} type="button">
                Download manifest JSON
              </button>
            </>
          ) : null}
        </div>

        {isLoadingManifest ? <span className="meta-text">Loading manifest...</span> : null}

        {manifest ? (
          <div className="manifest-layout">
            <div className="export-proof-note">
              <EvidenceBadge label="Export proof" tone="truth" />
              <div>
                <strong>These records are local dataset/export output.</strong>
                <span>
                  Reviewed corrections are truth. Detections and proposals are evidence.
                  Reviewed-only exports exclude unreviewed candidates.
                </span>
              </div>
            </div>
            <div className="manifest-summary">
              <div>
                <span className="meta-text">Total records</span>
                <strong>{manifest.records.length}</strong>
              </div>
              <div>
                <span className="meta-text">Generated</span>
                <strong>{formatDateTime(manifest.generated_at)}</strong>
              </div>
              <div>
                <span className="meta-text">Skipped</span>
                <strong>{manifest.skipped_count}</strong>
              </div>
              <div>
                <span className="meta-text">Scope</span>
                <strong>
                  {manifest.export.reviewed_only ? "Reviewed only" : "Includes unreviewed"}
                </strong>
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
                <span className="meta-text">Unknown animal records</span>
                <strong>{unknownAnimalRecordCount}</strong>
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
                <strong>Skipped records</strong>
                <span>
                  Skips show records excluded by reviewed-only settings or missing product context.
                </span>
                <div className="skipped-reason-list">
                  {skippedReasonEntries.map(([reason, count]) => (
                    <span key={reason}>
                      {formatLabel(reason)}: {count}
                    </span>
                  ))}
                </div>
                <button className="secondary-action" onClick={onOpenReview}>
                  Review skipped activity
                </button>
                <button className="secondary-action" onClick={onOpenDetectionProposals}>
                  Advanced proposal evidence
                </button>
              </div>
            ) : null}

            <div className="record-list">
              {manifest.records.map((record) => (
                <article className="record-card" key={record.record_id}>
                  <div className="item-title-row">
                    <div>
                      <span className="meta-text">
                        Export record {record.record_id}
                      </span>
                      <h3>{record.label_display_name ?? formatLabel(record.label)}</h3>
                      <p>
                        Correction truth exports as <strong>{record.label}</strong>; subject context is{" "}
                        <strong>{formatLabel(record.subject_label)}</strong>.
                      </p>
                    </div>
                    <div className="record-status-stack">
                      <EvidenceBadge label="Corrected label is truth" tone="truth" />
                      <EvidenceBadge
                        label={record.reviewed ? "Reviewed" : "Unreviewed"}
                        tone={record.reviewed ? "truth" : "review"}
                      />
                      {record.is_species ? (
                        <EvidenceBadge label="Reviewed species truth" tone="truth" />
                      ) : null}
                      {record.label === "unknown_bird" ? (
                        <EvidenceBadge label="Unknown bird record" tone="review" />
                      ) : null}
                      {record.label === "unknown_animal" ? (
                        <EvidenceBadge label="Unknown animal record" tone="review" />
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
                  <div className="record-proof-grid">
                    <div>
                      <span>Event ID</span>
                      <strong>{record.event_id}</strong>
                    </div>
                    <div>
                      <span>Visit ID</span>
                      <strong>{record.visit_id ?? "None"}</strong>
                    </div>
                    <div>
                      <span>Source ID</span>
                      <strong>{record.source_id}</strong>
                    </div>
                    <div>
                      <span>Stream ID</span>
                      <strong>{record.stream_id}</strong>
                    </div>
                    <div>
                      <span>Zone</span>
                      <strong>
                        {record.zone_name
                          ? `${record.zone_name} (${formatLabel(record.zone_type ?? "unknown")})`
                          : "Unzoned"}
                      </strong>
                      <small>{record.zone_id ?? "No zone id"}</small>
                    </div>
                    <div>
                      <span>Media path</span>
                      <strong>
                        {record.media_path ? mediaReferenceName(record.media_path) : "Reference pending"}
                      </strong>
                      <small>{record.media_path ?? "No local media path on this record"}</small>
                    </div>
                    <div>
                      <span>Reviewed</span>
                      <strong>{record.reviewed ? "true" : "false"}</strong>
                    </div>
                    <div>
                      <span>Dataset ready</span>
                      <strong>{record.dataset_ready ? "true" : "false"}</strong>
                    </div>
                    <div>
                      <span>Started</span>
                      <strong>{formatDateTime(record.started_at)}</strong>
                    </div>
                    <div>
                      <span>Detections/proposals context</span>
                      <strong>
                        {record.detections.length} evidence item
                        {record.detections.length === 1 ? "" : "s"}
                      </strong>
                    </div>
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
