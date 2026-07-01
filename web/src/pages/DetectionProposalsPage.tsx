import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  DetectionProposal,
  DetectionProposalDecision,
  DetectionProposalDecisionResult,
  MediaAsset,
  Stream,
  Zone,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface DetectionProposalsPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenImport: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
  onProposalChanged: () => Promise<void>;
}

function statusTone(status: DetectionProposal["status"]): "good" | "review" | "quiet" {
  if (status === "proposed") {
    return "review";
  }
  if (status === "accepted" || status === "converted") {
    return "good";
  }
  return "quiet";
}

export function DetectionProposalsPage({
  streams,
  sources,
  onOpenImport,
  onOpenEvent,
  onOpenVisit,
  onOpenReview,
  onOpenExports,
  onProposalChanged,
}: DetectionProposalsPageProps) {
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [proposals, setProposals] = useState<DetectionProposal[]>([]);
  const [zonesByStream, setZonesByStream] = useState<Record<string, Zone[]>>({});
  const [selectedMediaId, setSelectedMediaId] = useState("");
  const [selectedZoneId, setSelectedZoneId] = useState("");
  const [label, setLabel] = useState("animal_candidate");
  const [confidence, setConfidence] = useState("0.75");
  const [suggestedEventType, setSuggestedEventType] = useState("animal_visit");
  const [suggestedSubjectLabel, setSuggestedSubjectLabel] = useState("unknown_animal");
  const [suggestedSpecies, setSuggestedSpecies] = useState("");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<DetectionProposalDecisionResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaById = useMemo(
    () => new Map(mediaAssets.map((asset) => [asset.id, asset])),
    [mediaAssets],
  );
  const streamById = useMemo(() => new Map(streams.map((stream) => [stream.id, stream])), [streams]);
  const sourceNames = useMemo(
    () => new Map(sources.map((source) => [source.id, source.name])),
    [sources],
  );
  const zoneById = useMemo(() => {
    const entries = Object.values(zonesByStream)
      .flat()
      .map((zone) => [zone.id, zone] as const);
    return new Map(entries);
  }, [zonesByStream]);

  const selectedMedia = mediaById.get(selectedMediaId) ?? null;
  const selectedZones = selectedMedia ? zonesByStream[selectedMedia.stream_id] ?? [] : [];

  async function loadPageData(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const [nextMediaAssets, nextProposals] = await Promise.all([
        apiClient.getMediaAssets(),
        apiClient.getDetectionProposals(),
      ]);
      const nextZonesByStream: Record<string, Zone[]> = {};
      await Promise.all(
        streams.map(async (stream) => {
          nextZonesByStream[stream.id] = await apiClient.getStreamZones(stream.id);
        }),
      );

      setMediaAssets(nextMediaAssets);
      setProposals(nextProposals);
      setZonesByStream(nextZonesByStream);
      setSelectedMediaId((current) =>
        current && nextMediaAssets.some((asset) => asset.id === current)
          ? current
          : nextMediaAssets[0]?.id ?? "",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load detection proposals.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadPageData();
  }, [streams]);

  useEffect(() => {
    setSelectedZoneId((current) =>
      current && selectedZones.some((zone) => zone.id === current) ? current : "",
    );
  }, [selectedMediaId, selectedZones]);

  async function submitProposal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedMedia) {
      setError("Import local media before creating a detection proposal.");
      return;
    }

    const parsedConfidence = Number(confidence);
    if (!Number.isFinite(parsedConfidence) || parsedConfidence < 0 || parsedConfidence > 1) {
      setError("Confidence must be a number from 0 to 1.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setMessage(null);
    setResult(null);
    try {
      const proposal = await apiClient.createDetectionProposal({
        media_asset_id: selectedMedia.id,
        stream_id: selectedMedia.stream_id,
        zone_id: selectedZoneId || undefined,
        label: label.trim() || "animal_candidate",
        confidence: parsedConfidence,
        suggested_event_type: suggestedEventType.trim() || "animal_visit",
        suggested_subject_label: suggestedSubjectLabel.trim() || "unknown_animal",
        suggested_species: suggestedSpecies.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      setMessage(`Created proposal ${proposal.id}. Review it before it becomes a product event.`);
      setNotes("");
      await loadPageData({ showLoading: false });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Detection proposal could not be created.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function decideProposal(
    proposal: DetectionProposal,
    decision: DetectionProposalDecision,
  ) {
    setActionId(`${proposal.id}:${decision}`);
    setError(null);
    setMessage(null);
    setResult(null);
    try {
      const nextResult = await apiClient.decideDetectionProposal(proposal.id, {
        decision,
        event_title:
          decision === "reject"
            ? undefined
            : `Review proposed ${formatLabel(proposal.suggested_subject_label)}`,
        subject_label: decision === "reject" ? undefined : proposal.suggested_subject_label,
        species_guess: decision === "reject" ? undefined : proposal.suggested_species,
        notes:
          decision === "reject"
            ? "Rejected during proposal review."
            : "Converted proposal into a reviewable event and visit.",
      });
      setResult(nextResult);
      setMessage(
        decision === "reject"
          ? "Proposal rejected. No event or visit was created."
          : "Proposal is now a reviewable event and visit. Correct it before export.",
      );
      await loadPageData({ showLoading: false });
      await onProposalChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Proposal decision could not be saved.");
    } finally {
      setActionId(null);
    }
  }

  const sortedProposals = [...proposals].reverse();

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Detection pipeline interface"
        title="Detection Proposals"
        description="Turn proposed outdoor activity from local media into reviewable events and visits. Corrections remain the dataset truth for exports and analytics."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenImport}>
              Import Media
            </button>
            <button className="secondary-action" onClick={onOpenReview}>
              Review Queue
            </button>
          </>
        }
      />

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      {result ? (
        <section className="panel import-result-panel">
          <div>
            <span className="meta-text">Review and correct converted proposals before export.</span>
            <h2>{formatLabel(result.proposal.status)} proposal</h2>
            <p>
              {result.proposal.status === "rejected"
                ? "No product event was created."
                : "A needs-review event and visit now carry the proposal as detection evidence."}
            </p>
          </div>
          <div className="detail-actions">
            {result.event ? (
              <button className="primary-action" onClick={() => onOpenEvent(result.event!.id)}>
                Event detail
              </button>
            ) : null}
            {result.visit ? (
              <button className="secondary-action" onClick={() => onOpenVisit(result.visit!.id)}>
                Visit detail
              </button>
            ) : null}
            <button className="secondary-action" onClick={onOpenExports}>
              Dataset exports
            </button>
            <StatusPill label={`${result.review_queue_count} needs review`} tone="review" />
          </div>
        </section>
      ) : null}

      <section className="manual-import-layout detection-proposal-layout">
        <form className="panel manual-import-form" onSubmit={submitProposal}>
          <div className="section-heading">
            <h2>Create proposal</h2>
            <StatusPill label="Evidence only" tone="quiet" />
          </div>
          <div className="import-flow-strip">
            <span>Media asset</span>
            <span>Detection proposal</span>
            <span>Review event/visit</span>
            <span>Correction/export truth</span>
          </div>
          <label>
            Media asset
            <select
              disabled={mediaAssets.length === 0}
              value={selectedMediaId}
              onChange={(event) => setSelectedMediaId(event.target.value)}
            >
              {mediaAssets.map((asset) => {
                const stream = streamById.get(asset.stream_id);
                const sourceName = stream ? sourceNames.get(stream.source_id) : undefined;
                return (
                  <option key={asset.id} value={asset.id}>
                    {asset.original_filename} - {stream?.name ?? asset.stream_id}
                    {sourceName ? ` - ${sourceName}` : ""}
                  </option>
                );
              })}
            </select>
          </label>
          <label>
            Zone
            <select
              disabled={!selectedMedia}
              value={selectedZoneId}
              onChange={(event) => setSelectedZoneId(event.target.value)}
            >
              <option value="">Unzoned</option>
              {selectedZones.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name} - {formatLabel(zone.zone_type)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Proposal label
            <input value={label} onChange={(event) => setLabel(event.target.value)} />
          </label>
          <label>
            Confidence
            <input
              max="1"
              min="0"
              onChange={(event) => setConfidence(event.target.value)}
              step="0.01"
              type="number"
              value={confidence}
            />
          </label>
          <label>
            Suggested event type
            <input
              value={suggestedEventType}
              onChange={(event) => setSuggestedEventType(event.target.value)}
            />
          </label>
          <label>
            Suggested subject label
            <input
              value={suggestedSubjectLabel}
              onChange={(event) => setSuggestedSubjectLabel(event.target.value)}
            />
          </label>
          <label>
            Suggested species
            <input
              value={suggestedSpecies}
              onChange={(event) => setSuggestedSpecies(event.target.value)}
              placeholder="optional"
            />
          </label>
          <label>
            Notes
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="optional proposal context"
            />
          </label>
          <button
            className="primary-action"
            disabled={isSubmitting || !selectedMedia}
            type="submit"
          >
            {isSubmitting ? "Creating..." : "Create proposal"}
          </button>
          {!selectedMedia && !isLoading ? (
            <span className="meta-text">Local imported media is required before proposals.</span>
          ) : null}
        </form>

        <div className="panel">
          <div className="section-heading">
            <h2>Proposal queue</h2>
            <button className="secondary-action" onClick={() => void loadPageData()}>
              Refresh
            </button>
          </div>
          {isLoading ? <span className="meta-text">Loading detection proposals...</span> : null}
          <div className="media-list detection-proposal-list">
            {sortedProposals.map((proposal) => {
              const asset = mediaById.get(proposal.media_asset_id);
              const stream = streamById.get(proposal.stream_id);
              const zone = proposal.zone_id ? zoneById.get(proposal.zone_id) : null;
              const canDecide = proposal.status === "proposed";
              return (
                <article className="media-list-item detection-proposal-card" key={proposal.id}>
                  <div className="item-title-row">
                    <div>
                      <span className="meta-text">{formatDateTime(proposal.created_at)}</span>
                      <h3>{formatLabel(proposal.label)}</h3>
                    </div>
                    <StatusPill label={formatLabel(proposal.status)} tone={statusTone(proposal.status)} />
                  </div>
                  {asset ? <MediaAssetPreview asset={asset} compact /> : null}
                  <div className="detection-proposal-meta">
                    <div className="data-row">
                      <span>Stream</span>
                      <strong>{stream?.name ?? proposal.stream_id}</strong>
                    </div>
                    <div className="data-row">
                      <span>Zone</span>
                      <strong>{zone?.name ?? proposal.zone_id ?? "Unzoned"}</strong>
                    </div>
                    <div className="data-row">
                      <span>Confidence</span>
                      <strong>{Math.round(proposal.confidence * 100)}%</strong>
                    </div>
                    <div className="data-row">
                      <span>Suggested truth</span>
                      <strong>
                        {formatLabel(proposal.suggested_species ?? proposal.suggested_subject_label)}
                      </strong>
                    </div>
                  </div>
                  {proposal.notes ? <p>{proposal.notes}</p> : null}
                  <div className="detail-actions">
                    {canDecide ? (
                      <>
                        <button
                          className="primary-action"
                          disabled={actionId === `${proposal.id}:convert_to_event`}
                          onClick={() => void decideProposal(proposal, "convert_to_event")}
                        >
                          Convert to review
                        </button>
                        <button
                          className="secondary-action"
                          disabled={actionId === `${proposal.id}:reject`}
                          onClick={() => void decideProposal(proposal, "reject")}
                        >
                          Reject
                        </button>
                      </>
                    ) : null}
                    {proposal.event_id ? (
                      <button className="secondary-action" onClick={() => onOpenEvent(proposal.event_id!)}>
                        Event detail
                      </button>
                    ) : null}
                    {proposal.visit_id ? (
                      <button className="secondary-action" onClick={() => onOpenVisit(proposal.visit_id!)}>
                        Visit detail
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
            {!isLoading && proposals.length === 0 ? (
              <EmptyState
                title="No detection proposals yet"
                description="Create a proposal from imported local media, then convert it into review when it represents outdoor activity."
                action={
                  <button className="secondary-action" onClick={onOpenImport}>
                    Import media
                  </button>
                }
              />
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}
