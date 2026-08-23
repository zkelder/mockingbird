import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { EventDetail, MediaAsset, MotionEvidence, ReviewLabel, TaxonomyLabel } from "../api/types";
import { DetectionEvidenceCard } from "../components/DetectionEvidenceCard";
import { DetectionProposalEvidenceCard } from "../components/DetectionProposalEvidenceCard";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { StatusPill } from "../components/StatusPill";
import { TaxonomyBadge } from "../components/TaxonomyBadge";
import { displayTaxonomyLabel, findTaxonomyLabel, isBirdReviewLabel } from "../components/taxonomy";
import { formatDateTime, formatLabel } from "../utils";

interface EventDetailPageProps {
  eventId: string;
  onOpenStream: (streamId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenExports: () => void;
  onOpenReview: () => void;
  onOpenDetectionProposals: () => void;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
}

const eventReviewBoundaryCopy =
  "This Event is reviewable context. Labels become truth only after Visit correction.";

function compareReviewLabelsNewestFirst(first: ReviewLabel, second: ReviewLabel): number {
  const timeDelta =
    new Date(second.created_at).getTime() - new Date(first.created_at).getTime();
  return timeDelta !== 0 ? timeDelta : second.id.localeCompare(first.id);
}

function sortReviewLabelsNewestFirst(labels: ReviewLabel[]): ReviewLabel[] {
  return [...labels].sort(compareReviewLabelsNewestFirst);
}

export function EventDetailPage({
  eventId,
  onOpenStream,
  onOpenVisit,
  onOpenExports,
  onOpenReview,
  onOpenDetectionProposals,
  onOpenMotionEvidence,
}: EventDetailPageProps) {
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadDetail() {
      setIsLoading(true);
      setError(null);
      try {
        const nextDetail = await apiClient.getEventDetail(eventId);
        if (isMounted) {
          setDetail(nextDetail);
        }
      } catch (caught) {
        if (isMounted) {
          setError(caught instanceof Error ? caught.message : "Could not load event detail.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      isMounted = false;
    };
  }, [eventId]);

  useEffect(() => {
    let isMounted = true;

    async function loadTaxonomy() {
      try {
        const labels = await apiClient.getTaxonomyLabels();
        if (isMounted) {
          setTaxonomyLabels(labels);
        }
      } catch {
        if (isMounted) {
          setTaxonomyLabels([]);
        }
      }
    }

    void loadTaxonomy();

    return () => {
      isMounted = false;
    };
  }, []);

  if (isLoading) {
    return <div className="panel">Loading event detail...</div>;
  }

  if (error || !detail) {
    return <div className="error-panel">{error ?? "Event detail is unavailable."}</div>;
  }

  const runById = new Map(detail.detection_runs.map((run) => [run.id, run]));
  const reviewLabelsNewestFirst = sortReviewLabelsNewestFirst(detail.review_labels);
  const latestReviewLabel = reviewLabelsNewestFirst[0] ?? null;
  const olderReviewLabels = reviewLabelsNewestFirst.slice(1);
  const speciesVisits = detail.visits.filter(
    (visit) =>
      isBirdReviewLabel(visit.reviewed_label, taxonomyLabels) ||
      isBirdReviewLabel(visit.species_guess, taxonomyLabels) ||
      isBirdReviewLabel(visit.subject_label, taxonomyLabels),
  );
  const visitsNeedingSpeciesReview = speciesVisits.filter(
    (visit) => visit.review_status === "needs_review" || !visit.reviewed_label,
  );
  const reviewedSpeciesVisits = speciesVisits.filter((visit) => visit.reviewed_label);
  const isMotionEvidenceEvent = detail.event.event_type === "motion_evidence";
  const webhookProvenance = detail.motion_evidence
    ? getWebhookEvidenceProvenance(detail.motion_evidence)
    : null;
  const hasWebhookEvidence = Boolean(webhookProvenance?.isWebhook);
  const hasSavedPreviewMedia = isSavedPreviewMedia(detail.media_asset);
  const hasFolderImportMedia = isFolderImportMedia(detail.media_asset);
  const mediaProvenance = formatMediaProvenance(detail.media_asset);
  const mediaContextTitle = hasWebhookEvidence
    ? "Webhook metadata evidence"
    : hasFolderImportMedia
    ? "Folder-imported media"
    : hasSavedPreviewMedia
      ? "Saved preview media"
      : "Attached media";
  const mediaContextBadge = hasWebhookEvidence
    ? "Generic webhook ingest"
    : hasFolderImportMedia
    ? "Folder-imported media"
    : hasSavedPreviewMedia
      ? "Saved local media"
      : "Reviewable Event/Visit";
  const folderRelativePath = extractSafeRelativePath(
    detail.media_asset?.notes ?? "",
    "relative_source_path",
  );
  const folderCopyMode = extractSafeNoteValue(detail.media_asset?.notes ?? "", "copy_mode");

  return (
    <div className="page-stack">
      <div className="stream-detail-heading">
        <div>
          <span className="page-eyebrow">Event case file</span>
          <StatusPill
            label={formatLabel(detail.event.review_status)}
            tone={detail.event.review_status === "needs_review" ? "review" : "good"}
          />
          <h1>{detail.event.title}</h1>
          <p>{detail.review_summary}</p>
        </div>
        <StatusPill
          label={detail.dataset_ready ? "Ready for local dataset export" : "Needs review before export"}
          tone={detail.dataset_ready ? "good" : "review"}
        />
      </div>

      {isMotionEvidenceEvent ? (
        <section className="notice-panel">
          <strong>Promoted activity evidence</strong>
          <span>
            Created from promoted activity evidence.{" "}
            {hasWebhookEvidence
              ? "This Event came from evidence created from generic webhook metadata. "
              : ""}
            {hasFolderImportMedia
              ? "This Event came from evidence linked to folder-imported local media. "
              : ""}
            {eventReviewBoundaryCopy}
          </span>
        </section>
      ) : null}

      {isMotionEvidenceEvent ? (
        <section className="panel promoted-review-context-panel">
          <div className="section-heading">
            <div>
              <h2>Promoted evidence context</h2>
              <span className="meta-text">
                Source, Stream, Zone, and media context stay visible while review remains separate.
              </span>
            </div>
            <EvidenceBadge
              label={mediaContextBadge}
              tone="evidence"
            />
          </div>
          <p className="evidence-panel-copy">
            {hasWebhookEvidence
              ? "This Event came from evidence created from generic webhook metadata."
              : detail.media_asset
              ? mediaProvenance
              : "Created from promoted activity evidence without attached media."}{" "}
            {eventReviewBoundaryCopy}
          </p>
          <div className="promoted-review-context-grid">
            <ContextItem label="Source" value={detail.stream.source_id} />
            <ContextItem label="Stream" value={detail.stream.name} detail={detail.stream.id} />
            <ContextItem
              label="Zone"
              value={
                detail.primary_zone
                  ? `${detail.primary_zone.name} (${formatLabel(detail.primary_zone.zone_type)})`
                  : "Unzoned"
              }
              detail={detail.primary_zone?.id}
            />
            <ContextItem label="Evidence source" value="Promoted activity evidence" />
            {detail.motion_evidence ? (
              <ContextItem
                label="Advanced evidence"
                value={detail.motion_evidence.id}
                detail={formatLabel(detail.motion_evidence.status)}
              />
            ) : null}
            <ContextItem
              label={mediaContextTitle}
              value={detail.media_asset?.original_filename ?? "No attached media"}
              detail={detail.media_asset?.id}
            />
            {hasWebhookEvidence && webhookProvenance ? (
              <>
                <ContextItem
                  label="Provider"
                  value={webhookProvenance.providerKey ?? "webhook_future"}
                />
                <ContextItem
                  label="External event ID"
                  value={formatWebhookValue(webhookProvenance.externalEventId)}
                />
                <ContextItem
                  label="Untrusted external label"
                  value={formatWebhookValue(webhookProvenance.externalLabel)}
                  detail="Evidence metadata only"
                />
                <ContextItem
                  label="Untrusted external confidence"
                  value={formatWebhookValue(webhookProvenance.externalConfidence)}
                  detail="Not review truth"
                />
                <ContextItem
                  label="Webhook timestamp"
                  value={formatWebhookValue(webhookProvenance.externalTimestamp)}
                />
              </>
            ) : null}
            {hasFolderImportMedia ? (
              <>
                <ContextItem label="Provider" value="folder_import_future" />
                <ContextItem
                  label="Original relative path"
                  value={folderRelativePath ?? "not available"}
                />
                <ContextItem
                  label="Import context"
                  value={folderCopyMode ? formatLabel(folderCopyMode) : "Imported local media"}
                />
              </>
            ) : null}
          </div>
        </section>
      ) : null}

      {hasWebhookEvidence ? (
        <section className="notice-panel">
          <strong>Webhook metadata evidence</strong>
          <span>
            Generic webhook ingest provided safe provenance only. Untrusted external labels and
            confidence are not confirmed labels; Visit correction remains the truth boundary for
            analytics and exports.
          </span>
        </section>
      ) : null}

      {detail.motion_evidence ? (
        <SourceEvidenceTracePanel
          mediaAsset={detail.media_asset}
          motionEvidence={detail.motion_evidence}
          onOpenMotionEvidence={onOpenMotionEvidence}
          onOpenVisit={onOpenVisit}
        />
      ) : null}

      {latestReviewLabel ? (
        <CorrectionTruthPanel
          latest={latestReviewLabel}
          older={olderReviewLabels}
          taxonomyLabels={taxonomyLabels}
        />
      ) : null}

      <section className="case-summary-grid">
        <div className="panel case-summary-card">
          <span className="meta-text">Event type</span>
          <strong>{formatLabel(detail.event.event_type)}</strong>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Stream</span>
          <button className="text-action" onClick={() => onOpenStream(detail.stream.id)}>
            {detail.stream.name}
          </button>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Zone context</span>
          <strong>
            {detail.primary_zone
              ? `${detail.primary_zone.name} (${formatLabel(detail.primary_zone.zone_type)})`
              : "Unzoned"}
          </strong>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Timing</span>
          <strong>{formatDateTime(detail.event.started_at)}</strong>
          <span className="meta-text">
            Ended: {detail.event.ended_at ? formatDateTime(detail.event.ended_at) : "Open"}
          </span>
        </div>
        {detail.media_asset ? (
          <div className="panel case-summary-card">
            <span className="meta-text">Media</span>
            <strong>{detail.media_asset.original_filename}</strong>
            <span className="meta-text">
              {hasFolderImportMedia
                ? "Folder-imported media"
                : hasSavedPreviewMedia
                  ? "Saved preview media"
                  : "Local media reference"}
            </span>
          </div>
        ) : null}
      </section>

      <section className="panel species-review-panel">
        <div className="section-heading">
          <div>
            <h2>Species review context</h2>
            <span className="meta-text">
              Bird visits stay reviewable until a corrected species or label becomes local dataset truth.
            </span>
          </div>
          <EvidenceBadge
            label={`${visitsNeedingSpeciesReview.length} needing species review`}
            tone={visitsNeedingSpeciesReview.length > 0 ? "review" : "truth"}
          />
        </div>
        <div className="species-state-grid">
          <div>
            <span className="meta-text">Bird/species visits</span>
            <strong>{speciesVisits.length}</strong>
          </div>
          <div>
            <span className="meta-text">Reviewed species</span>
            <strong>{reviewedSpeciesVisits.length}</strong>
          </div>
          <div>
            <span className="meta-text">Dataset export</span>
            <strong>
              {detail.dataset_ready ? "Ready for species dataset export" : "Resolve species first"}
            </strong>
          </div>
        </div>
        {speciesVisits.length > 0 ? (
          <div className="species-visit-list">
            {speciesVisits.map((visit) => {
              const visitLabel = visit.reviewed_label ?? visit.species_guess ?? visit.subject_label;
              const preview = detail.visit_previews?.[visit.id];
              return (
                <button
                  className="detail-link-card"
                  key={visit.id}
                  onClick={() => onOpenVisit(visit.id)}
                  type="button"
                >
                  {preview ? (
                    <div className="detail-link-card-preview">
                      {preview.content_type.startsWith("audio/") ? (
                        <div className="detail-link-card-preview-audio" aria-hidden="true">🔊 Heard</div>
                      ) : (
                        <img alt="" src={`${apiClient.baseUrl}${preview.preview_url}`} />
                      )}
                    </div>
                  ) : null}
                  <span>{displayTaxonomyLabel(visitLabel, taxonomyLabels)}</span>
                  <TaxonomyBadge label={findTaxonomyLabel(visitLabel, taxonomyLabels)} value={visitLabel} />
                  <strong>{visit.reviewed_label ? "Reviewed species" : "Resolve species"}</strong>
                </button>
              );
            })}
          </div>
        ) : (
          <span className="meta-text">No bird species visits are attached to this event.</span>
        )}
      </section>

      {detail.media_asset ? (
        <section className="panel media-evidence-panel">
          <div className="section-heading">
            <h2>{mediaContextTitle}</h2>
            <span className="meta-text">{mediaProvenance}</span>
          </div>
          <MediaAssetPreview asset={detail.media_asset} />
          <div className="attached-media-provenance">
            <strong>Review boundary</strong>
            <span>{eventReviewBoundaryCopy}</span>
            {hasFolderImportMedia ? (
              <span>This Event came from evidence linked to folder-imported local media.</span>
            ) : null}
            {detail.review_labels.length === 0 ? (
              <span>No label has been confirmed yet.</span>
            ) : null}
          </div>
          {hasFolderImportMedia ? (
            <div className="promoted-review-context-grid">
              <ContextItem label="Provider" value="folder_import_future" />
              <ContextItem
                label="Original relative path"
                value={folderRelativePath ?? "not available"}
              />
              <ContextItem
                label="Import context"
                value={folderCopyMode ? formatLabel(folderCopyMode) : "Imported local media"}
              />
              <ContextItem label="Truth boundary" value="Visit correction decides labels" />
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Suggestions as evidence</h2>
            <EvidenceBadge label="Not dataset truth" />
          </div>
          <p className="evidence-panel-copy">
            Suggestion labels help explain why this case exists. Review labels and
            corrections decide what exports and analytics count as truth.
          </p>
          <div className="evidence-list">
            {detail.event.detections.length > 0 ? (
              detail.event.detections.map((detection) => (
                <DetectionEvidenceCard
                  detection={detection}
                  key={detection.id}
                  statusLabel={detail.dataset_ready ? "Corrected truth available" : "Needs review"}
                  zoneLabel={
                    detail.primary_zone && detection.zone_id === detail.primary_zone.id
                      ? detail.primary_zone.name
                      : undefined
                  }
                />
              ))
            ) : (
              <span className="meta-text">No detections are attached to this manual media event.</span>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="section-heading">
            <h2>Visits</h2>
          </div>
          <div className="list-stack">
            {detail.visits.map((visit) => {
              const preview = detail.visit_previews?.[visit.id];
              return (
                <button className="detail-link-card" key={visit.id} onClick={() => onOpenVisit(visit.id)}>
                  {preview ? (
                    <div className="detail-link-card-preview">
                      {preview.content_type.startsWith("audio/") ? (
                        <div className="detail-link-card-preview-audio" aria-hidden="true">🔊 Heard</div>
                      ) : (
                        <img alt="" src={`${apiClient.baseUrl}${preview.preview_url}`} />
                      )}
                    </div>
                  ) : null}
                  <span>
                    {displayTaxonomyLabel(
                      visit.reviewed_label ?? visit.species_guess ?? visit.subject_label,
                      taxonomyLabels,
                    )}
                  </span>
                  <strong>{formatLabel(visit.review_status)}</strong>
                </button>
              );
            })}
            {detail.visits.length === 0 ? (
              <span className="meta-text">No visits are attached to this event.</span>
            ) : null}
          </div>
        </div>
      </section>

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Correction history</h2>
          </div>
          <div className="history-list">
            {reviewLabelsNewestFirst.map((label) => (
              <ReviewLabelHistoryItem
                key={label.id}
                reviewLabel={label}
                taxonomyLabels={taxonomyLabels}
              />
            ))}
            {reviewLabelsNewestFirst.length === 0 ? (
              <span className="meta-text">No correction history yet.</span>
            ) : null}
          </div>
        </div>

        <div className="panel case-readiness-panel">
          <div>
            <h2>Dataset readiness</h2>
            <p>{detail.review_summary}</p>
          </div>
          {!detail.dataset_ready ? (
            <button className="primary-action" onClick={onOpenReview}>
              Open Review Queue
            </button>
          ) : null}
          {detail.detection_proposals.length > 0 ? (
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
            </button>
          ) : null}
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        </div>
      </section>

      {detail.detection_proposals.length > 0 ? (
        <section className="panel">
          <div className="section-heading">
            <h2>Suggestion provenance</h2>
            <EvidenceBadge label="Evidence source" />
          </div>
          <p className="evidence-panel-copy">
            This event came from suggestion evidence. Its suggested label and confidence explain the
            source, while reviewed corrections decide dataset truth.
          </p>
          <div className="evidence-list">
            {detail.detection_proposals.map((proposal) => (
              <DetectionProposalEvidenceCard
                key={proposal.id}
                proposal={proposal}
                run={runById.get(proposal.run_id)}
                taxonomyLabels={taxonomyLabels}
                zoneLabel={
                  detail.primary_zone && proposal.zone_id === detail.primary_zone.id
                    ? detail.primary_zone.name
                    : undefined
                }
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function SourceEvidenceTracePanel({
  mediaAsset,
  motionEvidence,
  onOpenMotionEvidence,
  onOpenVisit,
}: {
  mediaAsset?: MediaAsset | null;
  motionEvidence: MotionEvidence;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onOpenVisit: (visitId: string) => void;
}) {
  const webhookProvenance = getWebhookEvidenceProvenance(motionEvidence);

  return (
    <section className="panel source-evidence-trace-panel">
      <div className="section-heading">
        <div>
          <h2>Source evidence trace</h2>
          <span className="meta-text">
            This Event is linked back to the activity evidence that created review context.
          </span>
        </div>
        <EvidenceBadge label="Evidence trace" tone="evidence" />
      </div>
      <div className="motion-review-context-grid">
        <ContextItem
          label="Advanced evidence"
          value={motionEvidence.id}
          detail={formatLabel(motionEvidence.status)}
        />
        <ContextItem
          label="Promoted Event"
          value={motionEvidence.promoted_event_id ?? "not linked"}
        />
        <ContextItem
          label="Promoted Visit"
          value={motionEvidence.promoted_visit_id ?? "not linked"}
        />
        <ContextItem
          label="Best frame"
          value={motionEvidence.snapshot_media_asset_id ?? mediaAsset?.id ?? "none"}
        />
        <ContextItem label="Stream" value={motionEvidence.stream_id ?? "none"} />
        <ContextItem
          label="Activity area"
          value={motionEvidence.zone_id ?? "Automatic activity area"}
        />
        {webhookProvenance.isWebhook ? (
          <ContextItem
            label="Provider"
            value={webhookProvenance.providerKey ?? "webhook_future"}
            detail="Evidence metadata only"
          />
        ) : null}
      </div>
      <div className="detail-actions">
        <button
          className="secondary-action"
          onClick={() => onOpenMotionEvidence(motionEvidence.id)}
          type="button"
        >
          Open advanced evidence
        </button>
        {motionEvidence.promoted_visit_id ? (
          <button
            className="secondary-action"
            onClick={() => onOpenVisit(motionEvidence.promoted_visit_id!)}
            type="button"
          >
            Open Visit
          </button>
        ) : null}
        <span className="field-helper">
          Correction remains truth after inspecting source evidence.
        </span>
      </div>
    </section>
  );
}

function CorrectionTruthPanel({
  latest,
  older,
  taxonomyLabels,
}: {
  latest: ReviewLabel;
  older: ReviewLabel[];
  taxonomyLabels: TaxonomyLabel[];
}) {
  return (
    <section className="panel correction-truth-panel">
      <div className="section-heading">
        <div>
          <h2>Latest correction truth</h2>
          <span className="meta-text">
            ReviewLabel history is the audit trail for analytics and exports.
          </span>
        </div>
        <EvidenceBadge label="Correction truth" tone="truth" />
      </div>
      <div className="correction-truth-latest">
        <strong>{displayTaxonomyLabel(latest.label, taxonomyLabels)}</strong>
        <span>
          {formatLabel(latest.target_type)} correction - {formatDateTime(latest.created_at)}
        </span>
        {latest.notes ? <p>{latest.notes}</p> : null}
      </div>
      {older.length > 0 ? (
        <details className="correction-history-details">
          <summary>{older.length} older correction{older.length === 1 ? "" : "s"}</summary>
          <div className="history-list">
            {older.map((label) => (
              <ReviewLabelHistoryItem
                key={label.id}
                reviewLabel={label}
                taxonomyLabels={taxonomyLabels}
              />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function ReviewLabelHistoryItem({
  reviewLabel,
  taxonomyLabels,
}: {
  reviewLabel: ReviewLabel;
  taxonomyLabels: TaxonomyLabel[];
}) {
  return (
    <div className="history-item">
      <strong>{displayTaxonomyLabel(reviewLabel.label, taxonomyLabels)}</strong>
      <span>
        {formatLabel(reviewLabel.target_type)} correction -{" "}
        {formatDateTime(reviewLabel.created_at)}
      </span>
      {reviewLabel.notes ? <p>{reviewLabel.notes}</p> : null}
    </div>
  );
}

function ContextItem({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string | null;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && detail !== value ? <small>{detail}</small> : null}
    </div>
  );
}

function isSavedPreviewMedia(asset: MediaAsset | null | undefined): boolean {
  const notes = asset?.notes?.toLowerCase() ?? "";
  return (
    notes.includes("saved explicit external_url still-image preview") ||
    notes.includes("provider_key=external_url")
  );
}

function isFolderImportMedia(asset: MediaAsset | null | undefined): boolean {
  const notes = asset?.notes?.toLowerCase() ?? "";
  return (
    notes.includes("provider_key=folder_import_future") ||
    notes.includes("imported explicit folder/trail-cam media as mediaasset only")
  );
}

function formatMediaProvenance(asset: MediaAsset | null | undefined): string {
  if (!asset) {
    return "No attached media is available for this review context.";
  }
  if (isFolderImportMedia(asset)) {
    const relativePath = extractSafeRelativePath(asset.notes ?? "", "relative_source_path");
    if (relativePath) {
      return `This Event came from evidence linked to folder-imported local media from ${relativePath}.`;
    }
    return "This Event came from evidence linked to folder-imported local media.";
  }
  if (isSavedPreviewMedia(asset)) {
    const host = extractSafeNoteValue(asset.notes ?? "", "url_host");
    if (host) {
      return `This review context is linked to saved local media from external URL host ${host}.`;
    }
    return "This review context is linked to saved local media from an external URL preview.";
  }
  return "This review context is linked to saved local media.";
}

interface WebhookEvidenceProvenance {
  isWebhook: boolean;
  providerKey: string | null;
  externalEventId: string | null;
  externalLabel: string | null;
  externalConfidence: string | null;
  externalTimestamp: string | null;
}

function getWebhookEvidenceProvenance(evidence: MotionEvidence): WebhookEvidenceProvenance {
  const providerKey = formatOptionalConfigValue(evidence.scoring_config.provider_key);
  const source = formatOptionalConfigValue(evidence.scoring_config.source);
  return {
    isWebhook: providerKey === "webhook_future" || source === "webhook_metadata_motion_event",
    providerKey,
    externalEventId: formatOptionalConfigValue(evidence.scoring_config.external_event_id),
    externalLabel: formatOptionalConfigValue(evidence.scoring_config.external_label_untrusted),
    externalConfidence: formatOptionalConfigValue(
      evidence.scoring_config.external_confidence_untrusted,
    ),
    externalTimestamp: formatOptionalConfigValue(evidence.scoring_config.external_timestamp),
  };
}

function formatOptionalConfigValue(
  value: string | number | boolean | string[] | null | undefined,
): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return String(value);
}

function formatWebhookValue(value: string | null): string {
  return value && value.trim() ? value : "not provided";
}

function extractSafeNoteValue(notes: string, key: string): string | null {
  const prefixes = [`${key}=`, `${key}:`];
  const line = notes
    .split(/\r?\n/)
    .find((entry) => prefixes.some((prefix) => entry.trim().startsWith(prefix)));
  if (!line) {
    return null;
  }

  const trimmed = line.trim();
  const prefix = prefixes.find((entry) => trimmed.startsWith(entry));
  const rawValue = prefix ? trimmed.slice(prefix.length).trim() : "";
  const safeValue = rawValue.replace(/[^A-Za-z0-9.:\[\]-]/g, "").slice(0, 120);
  return safeValue || null;
}

function extractSafeRelativePath(notes: string, key: string): string | null {
  const rawValue = extractRawNoteValue(notes, key);
  if (!rawValue) {
    return null;
  }

  const normalized = rawValue.trim().replace(/\\/g, "/");
  if (
    !normalized ||
    normalized.startsWith("/") ||
    normalized.startsWith("~/") ||
    /^[A-Za-z]:/.test(normalized)
  ) {
    return null;
  }

  const segments = normalized.split("/").filter(Boolean);
  if (segments.length === 0 || segments.some((segment) => segment === "..")) {
    return null;
  }

  return segments
    .map((segment) => segment.replace(/[^A-Za-z0-9._ -]/g, "-").slice(0, 80))
    .join("/")
    .slice(0, 180);
}

function extractRawNoteValue(notes: string, key: string): string | null {
  const prefixes = [`${key}=`, `${key}:`];
  const line = notes
    .split(/\r?\n/)
    .find((entry) => prefixes.some((prefix) => entry.trim().startsWith(prefix)));
  if (!line) {
    return null;
  }

  const trimmed = line.trim();
  const prefix = prefixes.find((entry) => trimmed.startsWith(entry));
  return prefix ? trimmed.slice(prefix.length).trim() : null;
}
