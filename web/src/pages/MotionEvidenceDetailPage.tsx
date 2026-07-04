import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { CameraSource, MediaAsset, MotionEvidence, Stream } from "../api/types";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface MotionEvidenceDetailPageProps {
  motionEvidenceId: string;
  sources: CameraSource[];
  streams: Stream[];
  onOpenMotionEvidence: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
}

interface WebhookEvidenceProvenance {
  isWebhook: boolean;
  providerKey: string | null;
  candidateType: string | null;
  externalEventId: string | null;
  externalLabel: string | null;
  externalConfidence: string | null;
  externalTimestamp: string | null;
}

export function MotionEvidenceDetailPage({
  motionEvidenceId,
  sources,
  streams,
  onOpenMotionEvidence,
  onOpenEvent,
  onOpenVisit,
}: MotionEvidenceDetailPageProps) {
  const [evidence, setEvidence] = useState<MotionEvidence | null>(null);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadDetail() {
      setIsLoading(true);
      setError(null);
      try {
        const [nextEvidence, nextMediaAssets] = await Promise.all([
          apiClient.getMotionEvidence(motionEvidenceId),
          apiClient.getMediaAssets().catch(() => []),
        ]);
        if (isMounted) {
          setEvidence(nextEvidence);
          setMediaAssets(nextMediaAssets);
        }
      } catch (caught) {
        if (isMounted) {
          setError(
            caught instanceof Error ? caught.message : "Could not load MotionEvidence detail.",
          );
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
  }, [motionEvidenceId]);

  const sourceById = useMemo(() => new Map(sources.map((source) => [source.id, source])), [sources]);
  const streamById = useMemo(() => new Map(streams.map((stream) => [stream.id, stream])), [streams]);
  const mediaById = useMemo(
    () => new Map(mediaAssets.map((asset) => [asset.id, asset])),
    [mediaAssets],
  );
  const attachedMedia = evidence?.snapshot_media_asset_id
    ? mediaById.get(evidence.snapshot_media_asset_id) ?? null
    : null;
  const source = evidence?.source_id ? sourceById.get(evidence.source_id) : null;
  const stream = evidence?.stream_id ? streamById.get(evidence.stream_id) : null;
  const webhookProvenance = evidence ? getWebhookEvidenceProvenance(evidence) : null;
  const providerContext =
    evidence && webhookProvenance?.isWebhook
      ? webhookProvenance.providerKey ?? "webhook_future"
      : evidence
        ? formatOptionalConfigValue(evidence.scoring_config.provider_key) ??
          formatOptionalConfigValue(evidence.scoring_config.source) ??
          "local motion evidence"
        : "local motion evidence";

  if (isLoading) {
    return <div className="panel">Loading MotionEvidence detail...</div>;
  }

  if (error || !evidence) {
    return (
      <div className="error-panel">
        <strong>MotionEvidence detail is unavailable.</strong>
        <span>{error ?? "No MotionEvidence record was found."}</span>
        <div className="detail-actions">
          <button className="secondary-action" onClick={onOpenMotionEvidence} type="button">
            Back to Motion Evidence
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-stack motion-evidence-detail-page">
      <PageHeader
        eyebrow="Source evidence"
        title={`MotionEvidence ${evidence.id}`}
        description="Inspect the evidence that can explain Event/Visit review context. Evidence is not truth."
        actions={
          <button className="secondary-action" onClick={onOpenMotionEvidence} type="button">
            Back to Motion Evidence
          </button>
        }
      />

      <section className="notice-panel motion-status-note">
        <div>
          <strong>Evidence is not truth</strong>
          <span>Corrections create dataset-grade truth for analytics and exports.</span>
        </div>
        <StatusPill label={formatLabel(evidence.status)} tone={statusTone(evidence.status)} />
      </section>

      <section className="panel motion-evidence-detail">
        <div className="section-heading">
          <div>
            <h2>Evidence summary</h2>
            <span className="meta-text">Source, stream, zone, motion score, and promoted links.</span>
          </div>
          <EvidenceBadge label="Review context" tone="evidence" />
        </div>

        <div className="motion-evidence-detail-grid">
          <DetailItem label="Status" value={formatLabel(evidence.status)} />
          <DetailItem label="Zone" value={evidence.zone_id} />
          <DetailItem label="Peak change" value={formatPercent(evidence.peak_changed_ratio)} />
          <DetailItem label="Triggered frames" value={`${evidence.triggered_frame_count}`} />
          <DetailItem label="Frame/time range" value={formatRange(evidence)} />
          <DetailItem label="Best frame/time" value={formatBestMoment(evidence)} />
          <DetailItem label="Created" value={formatDateTime(evidence.created_at)} />
          <DetailItem label="Provider context" value={providerContext} />
        </div>
      </section>

      <section className="panel motion-evidence-detail">
        <div className="section-heading">
          <div>
            <h2>Source/Stream/Zone context</h2>
            <span className="meta-text">Adapters stay below these product-level review concepts.</span>
          </div>
          <EvidenceBadge label="Product context" tone="evidence" />
        </div>
        <div className="motion-review-context-grid">
          <ContextItem
            label="Source"
            value={source?.name ?? evidence.source_id ?? "none"}
            detail={evidence.source_id}
          />
          <ContextItem
            label="Stream"
            value={stream?.name ?? evidence.stream_id ?? "none"}
            detail={evidence.stream_id}
          />
          <ContextItem label="Zone" value={evidence.zone_id} />
          <ContextItem
            label="Attached media"
            value={evidence.snapshot_media_asset_id ?? "none"}
            detail={attachedMedia?.original_filename}
          />
          <ContextItem label="Promoted Event" value={evidence.promoted_event_id ?? "none"} />
          <ContextItem label="Promoted Visit" value={evidence.promoted_visit_id ?? "none"} />
          {webhookProvenance?.isWebhook ? (
            <>
              <ContextItem
                label="Candidate type"
                value={formatWebhookValue(webhookProvenance.candidateType)}
              />
              <ContextItem
                label="External event ID"
                value={formatWebhookValue(webhookProvenance.externalEventId)}
              />
              <ContextItem
                label="Untrusted label"
                value={formatWebhookValue(webhookProvenance.externalLabel)}
                detail="Evidence metadata only"
              />
              <ContextItem
                label="Untrusted confidence"
                value={formatWebhookValue(webhookProvenance.externalConfidence)}
                detail="Not review truth"
              />
              <ContextItem
                label="Webhook timestamp"
                value={formatWebhookValue(webhookProvenance.externalTimestamp)}
              />
            </>
          ) : null}
        </div>
        <div className="detail-actions">
          {evidence.promoted_event_id ? (
            <button
              className="secondary-action"
              onClick={() => onOpenEvent(evidence.promoted_event_id!)}
              type="button"
            >
              Open Event
            </button>
          ) : null}
          {evidence.promoted_visit_id ? (
            <button
              className="secondary-action"
              onClick={() => onOpenVisit(evidence.promoted_visit_id!)}
              type="button"
            >
              Open Visit
            </button>
          ) : null}
        </div>
      </section>

      <section className="panel motion-evidence-detail">
        <div className="section-heading">
          <div>
            <h2>Media context</h2>
            <span className="meta-text">Attached media is visual evidence context only.</span>
          </div>
          <EvidenceBadge
            label={evidence.snapshot_media_asset_id ? "Media attached" : "No media"}
            tone={evidence.snapshot_media_asset_id ? "evidence" : "quiet"}
          />
        </div>
        {evidence.snapshot_media_asset_id ? (
          <div className="attached-media-context">
            <div className="attached-media-id-row">
              <span>MediaAsset ID</span>
              <strong>{evidence.snapshot_media_asset_id}</strong>
            </div>
            {attachedMedia ? (
              <MediaAssetPreview asset={attachedMedia} compact />
            ) : (
              <div className="notice-panel">
                <strong>Media details not loaded</strong>
                <span>The evidence still stores this MediaAsset reference.</span>
              </div>
            )}
            <div className="detail-actions">
              <a
                className="secondary-action"
                href={apiClient.mediaFileUrl(evidence.snapshot_media_asset_id)}
                rel="noreferrer"
                target="_blank"
              >
                Open media file
              </a>
            </div>
          </div>
        ) : (
          <p className="media-empty-note">
            No media is attached. MotionEvidence can still explain why review context exists.
          </p>
        )}
      </section>

      <section className="panel motion-evidence-detail">
        <div className="section-heading">
          <div>
            <h2>Scoring context</h2>
            <span className="meta-text">Safe evidence metadata for review and traceability.</span>
          </div>
        </div>
        <div className="motion-config-list">
          {Object.entries(evidence.scoring_config).length > 0 ? (
            Object.entries(evidence.scoring_config).map(([key, value]) => (
              <span key={key}>
                {formatLabel(key)}: {String(value)}
              </span>
            ))
          ) : (
            <span>No scoring configuration attached.</span>
          )}
        </div>
        {evidence.notes ? <p className="media-readonly-note">{evidence.notes}</p> : null}
      </section>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
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

function statusTone(status: MotionEvidence["status"]): "good" | "review" | "quiet" {
  if (status === "pending") {
    return "review";
  }
  if (status === "promoted") {
    return "good";
  }
  return "quiet";
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatRange(evidence: MotionEvidence): string {
  if (evidence.start_time || evidence.end_time) {
    return `${evidence.start_time ?? "start unknown"} -> ${evidence.end_time ?? "end unknown"}`;
  }
  if (evidence.start_frame_index !== null && evidence.start_frame_index !== undefined) {
    return `frames ${evidence.start_frame_index} -> ${evidence.end_frame_index ?? "unknown"}`;
  }
  return "range unavailable";
}

function formatBestMoment(evidence: MotionEvidence): string {
  if (evidence.best_frame_time) {
    return evidence.best_frame_time;
  }
  if (evidence.best_frame_index !== null && evidence.best_frame_index !== undefined) {
    return `frame ${evidence.best_frame_index}`;
  }
  return "best moment unavailable";
}

function getWebhookEvidenceProvenance(evidence: MotionEvidence): WebhookEvidenceProvenance {
  const providerKey = formatOptionalConfigValue(evidence.scoring_config.provider_key);
  const source = formatOptionalConfigValue(evidence.scoring_config.source);
  const isWebhook =
    providerKey === "webhook_future" || source === "webhook_metadata_motion_event";

  return {
    isWebhook,
    providerKey,
    candidateType: formatOptionalConfigValue(evidence.scoring_config.candidate_type),
    externalEventId: formatOptionalConfigValue(evidence.scoring_config.external_event_id),
    externalLabel: formatOptionalConfigValue(evidence.scoring_config.external_label_untrusted),
    externalConfidence: formatOptionalConfigValue(
      evidence.scoring_config.external_confidence_untrusted,
    ),
    externalTimestamp: formatOptionalConfigValue(evidence.scoring_config.external_timestamp),
  };
}

function formatOptionalConfigValue(value: string | number | boolean | undefined): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  return String(value);
}

function formatWebhookValue(value: string | null): string {
  return value && value.trim() ? value : "not provided";
}
